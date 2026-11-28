"""Transactional event changes and round history."""
import json
import time
from datetime import datetime
import entries
import voting_rules as rules
from app import Problem, scalar


def open_event(con,event):
    approved=rules.candidates(con,event)
    pending=con.execute("SELECT 1 FROM candidates WHERE election_id=? AND active=1 AND review_status='PENDING'",(event['id'],)).fetchone()
    if len(approved)<2 or pending: raise Problem('Approve at least 2 entries and finish pending reviews / 至少需2项通过审核，且须先处理全部待审作品。')
    if event['method']=='SINGLE' and event['max_choices']>len(approved): raise Problem('Selection limit exceeds entries / 最多可选数量超过作品数，请先调整。')
    end=event['planned_end'] or int(time.time())+event['duration']*60
    if end<=time.time()+60: raise Problem('Update the end time before starting / 截止时间已到，请先更新。')
    rules.snapshot(con,event)
    con.execute("UPDATE elections SET status='OPEN',paused=0,ends_at=?,submissions_open=0 WHERE id=?",(end,event['id']))


def revision(con,event,uid,form,files):
    if not event['paused'] or event['status']!='OPEN': raise Problem('Pause voting first / 请先暂停投票进入修改。',409)
    if event['revisions']>=3: raise Problem('All 3 revisions have been used / 三次修改机会已用完。',409)
    announcement=scalar(form,'announcement').strip()
    if not 1<=len(announcement)<=1000: raise Problem('Write a change announcement / 请填写修改公告，最多1000字。')
    if scalar(form,'method')!=event['method'] or scalar(form,'max_choices','1')!=str(event['max_choices']):
        raise Problem('Voting method and selection limit stay locked / 开票后投票方式与最多可选数量仍锁定。')
    before=[dict(c) for c in rules.candidates(con,event,True)]
    rnd=rules.current_round(con,event)
    if not rnd['snapshot']: rules.snapshot(con,event)
    con.execute("UPDATE elections SET status='DRAFT' WHERE id=?",(event['id'],))
    entries.save_event(con,uid,form,files,event['id'])
    exclusions=form.get('exclude_candidate',[])
    if len(exclusions)!=len(set(exclusions)): raise Problem('Repeated exclusion / 重复的移出请求。')
    for cid in exclusions:
        row=con.execute('SELECT * FROM candidates WHERE id=? AND election_id=? AND active=1',(cid,event['id'])).fetchone()
        if not row or row['submitter_id'] in (None,uid): raise Problem('Invalid participant exclusion / 移出作品请求无效。')
        con.execute('UPDATE candidates SET active=0 WHERE id=?',(cid,))
    after=[dict(c) for c in rules.candidates(con,event,True)]
    shape=lambda rows:[(c['id'],c['image_id'],c['review_status']) for c in rows]
    structural=shape(before)!=shape(after)
    if event['method']=='SCORE' and not event['score_optional']:
        # A legacy all-required ballot cannot be reinterpreted as optional average scoring.
        structural=True
    if not structural and new_end_shortened(event, con):
        raise Problem('Only extend the deadline when retaining ballots / 保留旧票时截止时间只能延长，不能提前。')
    if structural:
        number=event['current_round']+1
        con.execute('INSERT INTO rounds(election_id,number) VALUES(?,?)',(event['id'],number))
        con.execute('UPDATE elections SET current_round=? WHERE id=?',(number,event['id']))
        announcement+=' / '+('作品或评分规则已改变，开启新轮次，旧票保留但不计入本轮。')
    elif event['method']=='MAJORITY':
        # Preserve the runoff's existing eligibility; textual changes do not reset it.
        pass
    con.execute("UPDATE elections SET status='OPEN',paused=1,revisions=revisions+1,announcement=?,ends_at=planned_end,published=0 WHERE id=?",(announcement,event['id']))
    new=rules.event_row(con.execute('SELECT * FROM elections WHERE id=?',(event['id'],)).fetchone())
    con.execute('INSERT INTO event_changes(election_id,round_number,actor_id,kind,announcement,created) VALUES(?,?,?,?,?,?)',
                (event['id'],new['current_round'],uid,'NEW_ROUND' if structural else 'TEXT_OR_DEADLINE',announcement,int(time.time())))
    if structural: rules.snapshot(con,new)


def next_round(con,event,form):
    if event['status']!='CLOSED' or event['method']!='MAJORITY': raise Problem('Close a majority round first / 请先关闭多数决选轮次。',409)
    result=rules.counts(con,event)
    if result['state']!='RUNOFF_REQUIRED': raise Problem('No automatic runoff: winner, tie or no valid votes / 当前有赢家、平票或无有效票，不能自动开启决选。',409)
    try: end=int(datetime.strptime(scalar(form,'deadline'),'%Y-%m-%dT%H:%M').replace(tzinfo=entries.TZ).timestamp())
    except ValueError: raise Problem('Set a valid runoff end time / 请选择有效的决选截止时间。')
    if not time.time()+60<end<=time.time()+entries.MAX_DAYS*86400: raise Problem('Runoff deadline must be within 30 days / 决选截止时间须在1分钟后、30天内。')
    number=event['current_round']+1
    con.execute('INSERT INTO rounds(election_id,number,eligible,is_runoff) VALUES(?,?,?,1)',(event['id'],number,json.dumps(result['finalists'])))
    con.execute("UPDATE elections SET current_round=?,ends_at=?,planned_end=?,status='OPEN',published=0,announcement=? WHERE id=?",(number,end,end,'第二轮决选已开始，请重新投票。 / Runoff open: please cast a new ballot.',event['id']))
    new=rules.event_row(con.execute('SELECT * FROM elections WHERE id=?',(event['id'],)).fetchone()); rules.snapshot(con,new)


def new_end_shortened(event,con):
    end=con.execute('SELECT planned_end FROM elections WHERE id=?',(event['id'],)).fetchone()[0]
    return end < event['ends_at']
