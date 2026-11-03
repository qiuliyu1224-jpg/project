"""Versioned rules and round-aware counting for VoteLab."""
import json
import time
from app import Problem, scalar

METHODS = {'SINGLE': ('单／多选', 'Single / multiple choice'),
           'SCORE': ('星级评分', 'Star rating'),
           'MAJORITY': ('多数决选', 'Majority / runoff'),
           'RCV': ('排序投票 RCV', 'Ranked-choice voting')}


def event_row(row):
    result = dict(row)
    result['method'] = result.get('voting_mode') or result['method']
    return result


def current_round(con, event):
    return con.execute('SELECT * FROM rounds WHERE election_id=? AND number=?',
                       (event['id'], event['current_round'])).fetchone()


def candidates(con, event, allrows=False):
    rows = con.execute('SELECT * FROM candidates WHERE election_id=? AND active=1' +
                       ('' if allrows else " AND review_status='APPROVED'") + ' ORDER BY id',
                       (event['id'],)).fetchall()
    rnd = current_round(con, event)
    eligible = json.loads(rnd['eligible']) if rnd and rnd['eligible'] else None
    return [r for r in rows if allrows or eligible is None or r['id'] in eligible]


def validate(con, event, form):
    ids = [r['id'] for r in candidates(con, event)]
    allowed = {str(cid) for cid in ids}
    method = event['method']
    if method in ('SINGLE', 'MAJORITY'):
        raw = form.get('candidate', [])
        limit = event['max_choices'] if method == 'SINGLE' else 1
        if not 1 <= len(raw) <= limit or len(raw) != len(set(raw)) or any(v not in allowed for v in raw):
            raise Problem(f'Choose 1–{limit} different valid options / 请选择1～{limit}个不同的有效选项。')
        return [(int(cid), 1) for cid in raw]
    if any(k.startswith(('score_', 'rank_')) and k.split('_', 1)[1] not in allowed for k in form):
        raise Problem('Unknown option in ballot / 选票包含不属于本轮的作品。')
    selections = []
    prefix = 'rank_' if method == 'RCV' else 'score_'
    for cid in ids:
        raw = scalar(form, prefix + str(cid))
        if raw == '':
            if method == 'SCORE' and not event['score_optional']:
                raise Problem('Rate every option / 本活动使用旧版全部必评规则，请为所有作品评分。')
            continue
        permitted = [str(i) for i in range(1, len(ids)+1)] if method == 'RCV' else list('012345')
        if raw not in permitted: raise Problem('Invalid score or rank / 分数须为0～5整数，排序须使用有效名次。')
        selections.append((cid, int(raw)))
    if not selections: raise Problem('Choose at least one option / 请至少评分或排序一个作品。')
    if method == 'RCV' and sorted(value for _, value in selections) != list(range(1, len(selections)+1)):
        raise Problem('Ranks must start at 1, with no gaps or duplicates / 排序须从1开始，不能重复或跳号。')
    return selections


def snapshot(con, event):
    rnd = current_round(con, event)
    data = {'title': event['title'], 'method': event['method'], 'max_choices': event['max_choices'],
            'score_optional': event['score_optional'],
            'entries': [dict(c) for c in candidates(con, event)]}
    con.execute('UPDATE rounds SET snapshot=? WHERE id=?', (json.dumps(data, ensure_ascii=False), rnd['id']))


def counts(con, event, number=None):
    rnd = con.execute('SELECT * FROM rounds WHERE election_id=? AND number=?',
                      (event['id'], number or event['current_round'])).fetchone()
    data = json.loads(rnd['snapshot']) if rnd['snapshot'] else {'method': event['method'],
        'entries': [dict(c) for c in candidates(con, event)]}
    method = data['method']
    rows = []
    for c in data['entries']:
        total, n = con.execute('SELECT COALESCE(SUM(c.score),0),COUNT(*) FROM choices c JOIN ballots b ON b.id=c.ballot_id WHERE b.round_id=? AND c.candidate_id=?', (rnd['id'], c['id'])).fetchone()
        rows.append({'id': c['id'], 'name': c['name'], 'total': total, 'n': n,
                     'average': total/n if n else None})
    ballots = con.execute('SELECT COUNT(*) FROM ballots WHERE round_id=?', (rnd['id'],)).fetchone()[0]
    result = {'rows': rows, 'ballots': ballots, 'method': method, 'winner': None,
              'state': 'NO_VOTES', 'rounds': [], 'tied': [], 'finalists': []}
    if method == 'RCV':
        ballots_ranked = []
        for b in con.execute('SELECT id FROM ballots WHERE round_id=? ORDER BY id', (rnd['id'],)):
            ballots_ranked.append([r[0] for r in con.execute('SELECT candidate_id FROM preferences WHERE ballot_id=? ORDER BY position', (b['id'],))])
        alive = {c['id'] for c in rows}
        while alive:
            totals = dict.fromkeys(sorted(alive), 0)
            for ballot in ballots_ranked:
                choice = next((cid for cid in ballot if cid in alive), None)
                if choice is not None: totals[choice] += 1
            active = sum(totals.values())
            step = {'counts': totals, 'active': active, 'exhausted': ballots-active}
            result['rounds'].append(step)
            if not active: result['state'] = 'NO_ACTIVE_BALLOTS'; break
            winner = next((cid for cid, votes in totals.items() if votes > active/2), None)
            if winner is not None: result.update(state='WINNER', winner=winner); break
            low = min(totals.values()); tied = [cid for cid,v in totals.items() if v == low]
            if len(tied) > 1: result.update(state='ELIMINATION_TIE', tied=tied); break
            step['eliminated'] = tied[0]; alive.remove(tied[0])
        return result
    rows.sort(key=lambda r: (-(r['average'] if method == 'SCORE' and r['average'] is not None else r['total']) if r['n'] or method != 'SCORE' else float('inf'), r['id']))
    if not ballots: return result
    if method == 'MAJORITY':
        if rows[0]['total'] > ballots/2: result.update(state='WINNER', winner=rows[0]['id'])
        elif rnd['is_runoff']:
            result.update(state='FINAL_TIE', tied=[r['id'] for r in rows if r['total']==rows[0]['total']])
        elif len(rows) > 2 and rows[1]['total'] == rows[2]['total']:
            result.update(state='CUTOFF_TIE', tied=[r['id'] for r in rows if r['total']==rows[1]['total']])
        else: result.update(state='RUNOFF_REQUIRED', finalists=[r['id'] for r in rows[:2]])
    else: result['state'] = 'RANKED'
    return result


def submit(con, eid, uid, form):
    con.execute('BEGIN IMMEDIATE')
    try:
        event = event_row(con.execute('SELECT * FROM elections WHERE id=?', (eid,)).fetchone())
        if event['status'] != 'OPEN' or event['paused'] or event['ends_at'] <= time.time():
            raise Problem('Voting closed or paused / 投票尚未开始、已截止或正在暂停修改。',409)
        rnd = current_round(con, event)
        if scalar(form,'round_id') != str(rnd['id']):
            raise Problem('Round changed; reload the event / 轮次已改变，请重新打开活动核对后投票。',409)
        if con.execute('SELECT 1 FROM ballots WHERE round_id=? AND user_id=?', (rnd['id'],uid)).fetchone():
            raise Problem('ALREADY_VOTED / 本轮已经投过票。')
        selections = validate(con,event,form)
        bid = con.execute('INSERT INTO ballots(election_id,round_id,user_id) VALUES(?,?,?)', (eid,rnd['id'],uid)).lastrowid
        if event['method']=='RCV':
            con.executemany('INSERT INTO preferences VALUES(?,?,?)',[(bid,cid,value) for cid,value in selections])
        else:
            con.executemany('INSERT INTO choices VALUES(?,?,?,?)',[(bid,eid,cid,value) for cid,value in selections])
        con.commit(); return bid
    except Exception:
        con.rollback(); raise
