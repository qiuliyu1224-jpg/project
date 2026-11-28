"""Round-aware bilingual VoteLab routes."""
import hmac
import json
import re
import secrets
import sqlite3
import time
from datetime import datetime
from http.cookies import SimpleCookie, CookieError
from urllib.parse import parse_qs
import app as core
import entries
import lifecycle
import voting_rules as rules
from app import Problem, e, scalar
from auth import issue_code, consume_code
from ui4 import View


def dispatch(env,start):
    path=env.get('PATH_INFO','/')
    if path in ('/static/style.css','/static/entries.css','/static/app.js','/static/v4.js'):
        data=(core.ROOT/path.lstrip('/')).read_bytes()
        start('200 OK',[('Content-Type',('text/css' if path.endswith('.css') else 'application/javascript')+'; charset=utf-8'),('Cache-Control','no-cache')]); return [data]
    cookies=SimpleCookie()
    try: cookies.load(env.get('HTTP_COOKIE',''))
    except CookieError: pass
    token=cookies['session'].value if 'session' in cookies else ''
    browser=cookies['browser'].value if 'browser' in cookies else ''
    if not re.fullmatch('[a-f0-9]{48}',browser): browser=secrets.token_hex(24)
    lang=cookies['lang'].value if 'lang' in cookies else 'zh'
    if lang not in ('zh','en'): lang='zh'
    csrf=hmac.new(core.CSRF_KEY,(browser+'|'+token).encode(),'sha256').hexdigest()
    headers=[('Content-Type','text/html; charset=utf-8'),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),('Referrer-Policy','same-origin'),('Content-Security-Policy',"default-src 'self'; img-src 'self' blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; form-action 'self'; frame-ancestors 'none'"),('Set-Cookie',f'browser={browser}; HttpOnly; SameSite=Lax; Path=/')]
    con=core.connect(); user=None; form={}; event=None
    view=View(lang,csrf,user,path); t=view.t; hidden=view.hidden; link=view.link; button=view.button
    def response(body,status=200):
        phrase={200:'OK',303:'See Other',400:'Bad Request',401:'Unauthorized',403:'Forbidden',404:'Not Found',409:'Conflict',413:'Content Too Large',429:'Too Many Requests',500:'Internal Server Error'}
        start(f'{status} {phrase.get(status,"Error")}',headers); return [body.encode('utf-8')]
    def redirect(url): headers.append(('Location',url)); return response('',303)
    def require():
        if not user: raise Problem('Please log in to continue / 请先登录后再操作。',401)
    def get_event(eid):
        row=con.execute('SELECT * FROM elections WHERE id=?',(eid,)).fetchone()
        if not row: raise Problem('Event not found / 活动不存在。',404)
        return rules.event_row(row)
    def owner(ev): return bool(user and ev['creator_id']==user['id'])
    def require_owner(ev):
        require()
        if not owner(ev): raise Problem('Only the creator can do this / 仅活动创建者可执行此操作。',403)
    def access(ev): return not ev['invite_hash'] or owner(ev) or bool(user and con.execute('SELECT 1 FROM event_access WHERE election_id=? AND user_id=?',(ev['id'],user['id'])).fetchone())
    def cs(ev,allrows=False): return rules.candidates(con,ev,allrows)
    def audit(eid,action): con.execute('INSERT INTO audit(election_id,actor_id,action,created) VALUES(?,?,?,?)',(eid,user['id'],action,int(time.time())))
    def attempt(key,success=False):
        row=con.execute('SELECT * FROM attempt_limits WHERE key=?',(key,)).fetchone()
        if success:
            with con: con.execute('DELETE FROM attempt_limits WHERE key=?',(key,))
            return
        if row and row['reset_at']>time.time() and row['count']>=10:
            raise Problem('Too many attempts; try again in 15 minutes / 尝试次数过多，请15分钟后再试。',429)
        with con:
            if not row or row['reset_at']<=time.time(): con.execute('INSERT OR REPLACE INTO attempt_limits VALUES(?,1,?)',(key,int(time.time())+900))
            else: con.execute('UPDATE attempt_limits SET count=count+1 WHERE key=?',(key,))
    def phone_number():
        phone=re.sub(r'[\s()-]','',scalar(form,'phone').strip()); country=scalar(form,'country')
        if country:
            formats={'86':r'1[0-9]{10}','852':r'[0-9]{8}','853':r'[0-9]{8}','886':r'[0-9]{8,10}','44':r'[0-9]{9,11}','1':r'[0-9]{10}','61':r'[0-9]{9,10}'}
            if country not in formats or not re.fullmatch(formats[country],phone): raise Problem('Check the local phone format and country code / 请检查国家区号及本地手机号格式。')
            phone=country+phone
        if not re.fullmatch('[0-9]{8,15}',phone): raise Problem('Phone account must contain 8–15 digits including country code / 手机号账号须为8～15位数字（含区号）。')
        return phone
    def password():
        value=scalar(form,'password')
        if not 8<=len(value)<=128: raise Problem('Password must be 8–128 characters / 密码须为8～128个字符。')
        if value!=scalar(form,'password_confirm'): raise Problem('Passwords do not match / 两次密码输入不一致。')
        return value
    try:
        with con: core.refresh(con)
        user=con.execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=? AND s.expires>?',(token,int(time.time()))).fetchone(); view.user=user
        query=parse_qs(env.get('QUERY_STRING',''))
        media=re.fullmatch('/media/([a-f0-9]{40})',path)
        if media:
            matches=con.execute('SELECT c.*,ev.creator_id,ev.status,ev.submissions_open,ev.invite_hash FROM candidates c JOIN elections ev ON ev.id=c.election_id WHERE c.image_id=?',(media[1],)).fetchall()
            allowed=False
            for c in matches:
                uid=user['id'] if user else -1
                visible=c['submitter_id']==uid or c['creator_id']==uid or (c['active'] and c['review_status']=='APPROVED' and (c['status']!='DRAFT' or c['submissions_open']))
                gated=not c['invite_hash'] or c['creator_id']==uid or bool(user and con.execute('SELECT 1 FROM event_access WHERE election_id=? AND user_id=?',(c['election_id'],uid)).fetchone())
                if visible and gated: allowed=True; break
            image=con.execute('SELECT content FROM images WHERE id=?',(media[1],)).fetchone() if allowed else None
            if not image: raise Problem('Image unavailable / 图片不可访问。',404)
            start('200 OK',[('Content-Type','image/jpeg'),('Cache-Control','private, no-store'),('X-Content-Type-Options','nosniff')]); return [image['content']]
        if env['REQUEST_METHOD']=='POST':
            form,files=entries.read_form(env)
            if not hmac.compare_digest(scalar(form,'csrf'),csrf): raise Problem('Form expired; reload and try again / 表单已过期，请刷新页面后重新操作。',403)
            if path=='/language':
                language=scalar(form,'lang'); target=scalar(form,'next','/')
                if language not in ('zh','en'): raise Problem('Unsupported language / 不支持该语言。')
                if not re.fullmatch(r'/[a-zA-Z0-9/_-]*',target): target='/'
                headers.append(('Set-Cookie',f'lang={language}; SameSite=Lax; Path=/; Max-Age=31536000')); return redirect(target)
            if path=='/auth/code':
                phone=phone_number(); purpose=scalar(form,'purpose')
                row=con.execute('SELECT * FROM users WHERE phone=?',(phone,)).fetchone()
                if purpose in ('login','reset') and not row: raise Problem('Account not registered; create an account / 此账号未注册，请先注册。',401)
                if purpose=='register' and row: raise Problem('Account exists; log in instead / 此账号已注册，请直接登录。',409)
                code=issue_code(con,phone,browser,purpose)
                return response(view.auth(purpose=='register',phone,scalar(form,'name'),code,reset=purpose=='reset'))
            if path in ('/login','/register','/reset'):
                phone=phone_number(); row=con.execute('SELECT * FROM users WHERE phone=?',(phone,)).fetchone()
                if path=='/login': attempt('login:'+phone)
                if path=='/register':
                    if row: raise Problem('Account already exists / 账号已存在，请登录。',409)
                    name=scalar(form,'name').strip()
                    if not 1<=len(name)<=60: raise Problem('Display name must be 1–60 characters / 称呼须为1～60字。')
                    pw=password(); consume_code(con,phone,browser,'register',scalar(form,'code'))
                    with con:
                        salt=secrets.token_hex(16)
                        uid=con.execute('INSERT INTO users(phone,name,salt,password_hash,password_set) VALUES(?,?,?,?,1)',(phone,name,salt,core.password_hash(pw,salt))).lastrowid
                else:
                    if not row: raise Problem('Create an account first / 此账号未注册，请先注册。',401)
                    uid=row['id']
                    if path=='/reset':
                        pw=password(); consume_code(con,phone,browser,'reset',scalar(form,'code'))
                        with con:
                            salt=secrets.token_hex(16); con.execute('UPDATE users SET salt=?,password_hash=?,password_set=1 WHERE id=?',(salt,core.password_hash(pw,salt),uid)); con.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
                    elif not row['password_set']:
                        raise Problem('This legacy account needs a password; use Forgot password / 旧账号尚未设置密码，请点击忘记密码获取演示验证码后设置。',401)
                    elif not hmac.compare_digest(core.password_hash(scalar(form,'password'),row['salt']),row['password_hash']):
                        raise Problem('Incorrect phone number or password / 手机号或密码不正确。',401)
                    if path=='/login': attempt('login:'+phone,success=True)
                with con:
                    newtoken=secrets.token_hex(32); con.execute('INSERT INTO sessions VALUES(?,?,?)',(newtoken,uid,int(time.time())+7200))
                headers.append(('Set-Cookie',f'session={newtoken}; HttpOnly; SameSite=Lax; Path=/; Max-Age=7200')); return redirect('/')
            require()
            if path=='/logout':
                with con: con.execute('DELETE FROM sessions WHERE token=?',(token,))
                headers.append(('Set-Cookie','session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0')); return redirect('/login')
            if path=='/create':
                with con:
                    con.execute('BEGIN IMMEDIATE'); eid=entries.save_event(con,user['id'],form,files)
                return redirect(f'/e/{eid}/preview')
            match=re.fullmatch(r'/e/(\d+)/(open|close|publish|vote|confirm|edit|collect|apply|review|access|pause|revision|resume|next-round)',path)
            if not match: raise Problem('Page not found / 页面不存在。',404)
            eid,action=int(match[1]),match[2]; event=get_event(eid)
            if action=='access':
                attempt(f'access:{eid}:{user["id"]}')
                value=scalar(form,'invite_code')
                if not event['invite_hash'] or not hmac.compare_digest(core.password_hash(value,event['invite_salt']),event['invite_hash']): raise Problem('Incorrect invitation code / 邀请码不正确，请联系活动发起者。',403)
                with con: con.execute('INSERT OR IGNORE INTO event_access VALUES(?,?)',(eid,user['id']))
                attempt(f'access:{eid}:{user["id"]}',success=True)
                return redirect(f'/e/{eid}')
            if not access(event): raise Problem('Enter the event invitation code first / 请先进入活动填写邀请码。',403)
            if action in ('vote','confirm'):
                rnd=rules.current_round(con,event)
                if event['status']!='OPEN' or event['paused'] or event['ends_at']<=time.time(): raise Problem('Voting closed or paused / 投票尚未开始、已截止或正在暂停修改。',409)
                if scalar(form,'round_id')!=str(rnd['id']): raise Problem('Round changed; reload / 轮次已改变，请刷新页面后重新核对。',409)
                if con.execute('SELECT 1 FROM ballots WHERE round_id=? AND user_id=?',(rnd['id'],user['id'])).fetchone(): raise Problem('ALREADY_VOTED / 本轮已经投过票。')
                if action=='vote': rules.submit(con,eid,user['id'],form); return redirect(f'/e/{eid}')
                selections=rules.validate(con,event,form); candidates={c['id']:c for c in cs(event)}
                summary=''.join(f'<div class="summary-row"><span>{e(candidates[cid]["name"])}</span><strong>{value if event["method"] in ("SCORE","RCV") else t("已选择","Selected")}</strong></div>' for cid,value in sorted(selections,key=lambda x:x[1]) if cid in candidates)
                fields=f'<input type="hidden" name="round_id" value="{rnd["id"]}">'
                for cid,value in selections:
                    key='candidate' if event['method'] in ('SINGLE','MAJORITY') else ('rank_' if event['method']=='RCV' else 'score_')+str(cid)
                    fields+=f'<input type="hidden" name="{key}" value="{cid if key=="candidate" else value}">'
                body=view.head(t('确认你的选择','Review your ballot'),t('尚未保存。请核对后确认提交。','Not saved yet. Check your choices, then confirm.'))+f'<section class="panel narrow"><h2>{e(event["title"])}</h2>{summary}<form method="post" action="/e/{eid}/vote">{hidden()}{fields}<div class="button-row"><button class="btn">{t("确认提交","Confirm and submit")}</button>{link(f"/e/{eid}",t("返回重选","Choose again"))}</div></form></section>'
                return response(view.page(t('核对选票','Review ballot'),body))
            if action=='apply':
                with con:
                    con.execute('BEGIN IMMEDIATE'); entries.apply_entry(con,eid,user['id'],form,files)
                return redirect('/my-entries')
            require_owner(event)
            with con:
                con.execute('BEGIN IMMEDIATE'); core.refresh(con); event=get_event(eid)
                if action in ('edit','review','collect','open') and event['status']!='DRAFT': raise Problem('Use Pause and edit for locked events / 活动已锁定，请使用暂停并修改入口。',409)
                if action=='edit': entries.save_event(con,user['id'],form,files,eid)
                elif action=='collect':
                    if not event['allow_submissions']: raise Problem('Enable applications in the editor / 请先在编辑页允许报名。')
                    if not event['planned_end'] or event['planned_end']<=time.time()+60: raise Problem('Update the deadline first / 请先更新截止时间。')
                    con.execute('UPDATE elections SET submissions_open=1 WHERE id=?',(eid,))
                elif action=='review':
                    candidate=con.execute('SELECT * FROM candidates WHERE id=? AND election_id=? AND active=1',(scalar(form,'candidate_id'),eid)).fetchone(); verdict=scalar(form,'verdict'); reason=scalar(form,'reason').strip()
                    if not candidate or candidate['review_status']!='PENDING' or verdict not in ('APPROVED','REJECTED'): raise Problem('This submission has already been reviewed or is invalid / 作品已审核或审核请求无效。',409)
                    if candidate['submitter_id'] in (None,user['id']): raise Problem('Creator entries use the editor / 创建者作品请在编辑页处理。')
                    if len(reason)>500 or (verdict=='REJECTED' and not reason): raise Problem('A rejection needs a reason of 1–500 characters / 驳回时须填写原因，最多500字。')
                    con.execute('UPDATE candidates SET review_status=?,review_reason=? WHERE id=?',(verdict,reason,candidate['id']))
                elif action=='open': lifecycle.open_event(con,event)
                elif action=='close':
                    if event['status']!='OPEN': raise Problem('Voting is already closed / 投票已关闭。',409)
                    con.execute("UPDATE elections SET status='CLOSED',paused=0 WHERE id=?",(eid,))
                elif action=='publish':
                    if event['status']!='CLOSED': raise Problem('Close voting first / 请先结束投票。',409)
                    if event['method']=='MAJORITY' and rules.counts(con,event)['state']=='RUNOFF_REQUIRED': raise Problem('Complete the runoff before publishing final results / 需要完成第二轮决选后才能发布最终结果。',409)
                    con.execute('UPDATE elections SET published=1 WHERE id=?',(eid,))
                elif action=='pause':
                    if event['status']!='OPEN' or event['paused'] or event['revisions']>=3: raise Problem('Cannot pause: voting closed, already paused or 3 revisions used / 无法暂停：投票已结束、已暂停或三次修改机会已用完。',409)
                    rules.snapshot(con,event); con.execute('UPDATE elections SET paused=1 WHERE id=?',(eid,))
                elif action=='revision': lifecycle.revision(con,event,user['id'],form,files)
                elif action=='resume':
                    if not event['paused'] or event['status']!='OPEN': raise Problem('Event is not paused / 活动当前未暂停。',409)
                    if event['ends_at']<=time.time(): raise Problem('Update deadline before resuming / 截止时间已到，不能恢复投票。',409)
                    if len(cs(event))<2 or (event['method']=='SINGLE' and event['max_choices']>len(cs(event))): raise Problem('Need at least 2 entries and a valid selection limit / 至少需2项作品，最多可选数量不能超过作品数。',409)
                    con.execute('UPDATE elections SET paused=0 WHERE id=?',(eid,))
                elif action=='next-round': lifecycle.next_round(con,event,form)
                audit(eid,action)
            if action in ('pause','revision'): return redirect(f'/e/{eid}/revision' if action=='pause' else f'/e/{eid}/preview')
            return redirect(f'/e/{eid}/review' if action=='review' else f'/e/{eid}/preview' if action=='edit' else f'/e/{eid}')
        if env['REQUEST_METHOD']!='GET': raise Problem('Unsupported request / 不支持的请求。',400)
        if path in ('/login','/register','/reset'): return response(view.auth(path=='/register',reset=path=='/reset'))
        if path=='/create':
            require(); return response(view.page(t('创建活动','Create event'),view.head(t('创建一场新活动','Create a new event'))+view.event_form(template=scalar(query,'template','custom')),'dashboard'))
        if path=='/my-entries':
            require(); rows=con.execute('SELECT c.*,ev.title,ev.status,ev.submissions_open FROM candidates c JOIN elections ev ON ev.id=c.election_id WHERE c.submitter_id=? AND c.active=1 AND ev.creator_id<>? ORDER BY c.id DESC',(user['id'],user['id'])).fetchall()
            body=view.head(t('我的作品','My entries'),t('查看审核结果；被驳回的作品可在报名期间修改重交。','Check review results. Rejected entries can be edited and resubmitted while applications are open.'))
            for c in rows:
                image=f'<img class="submission-thumb" src="/media/{c["image_id"]}" alt="{e(c["name"])}">' if c['image_id'] else ''
                labels={'PENDING':t('待审核','Pending'),'APPROVED':t('已通过','Approved'),'REJECTED':t('已驳回','Rejected')}
                edit=link(f'/e/{c["election_id"]}/apply',t('修改并重新提交','Edit and resubmit')) if c['review_status']=='REJECTED' and c['status']=='DRAFT' and c['submissions_open'] else ''
                body+=f'<article class="panel submission-card">{image}<div><span class="badge draft">{labels[c["review_status"]]}</span><h3>{e(c["name"])}</h3><p>{e(c["description"])}</p><p class="helper">{e(c["title"])}</p><p>{e(c["review_reason"])}</p>{edit}{link(f"/e/{c['election_id']}",t("查看活动","View event"))}</div></article>'
            if not rows: body+=f'<div class="empty">{t("暂无报名作品。","No submissions yet.")}</div>'
            return response(view.page(t('我的作品','My entries'),body,'my-entries'))
        if path in ('/','/dashboard','/my-votes'):
            if path!='/': require()
            section='gallery' if path=='/' else path[1:]
            if path=='/dashboard': raw=con.execute('SELECT * FROM elections WHERE creator_id=? ORDER BY id DESC',(user['id'],)).fetchall()
            elif path=='/my-votes': raw=con.execute('SELECT DISTINCT ev.* FROM elections ev JOIN ballots b ON b.election_id=ev.id WHERE b.user_id=? ORDER BY ev.id DESC',(user['id'],)).fetchall()
            else: raw=con.execute("SELECT * FROM elections WHERE status<>'DRAFT' OR submissions_open=1 ORDER BY status='OPEN' DESC,id DESC").fetchall()
            rows=[rules.event_row(r) for r in raw]
            title=t('我的活动','My events') if section=='dashboard' else t('我的投票','My votes') if section=='my-votes' else t('发现值得支持的想法','Discover ideas worth supporting')
            body=view.head(title,t('浏览作品，参与评选。','Explore entries and make your choice.'),link('/create',t('＋ 创建活动','＋ Create event'),'') if user else link('/register',t('注册并参与','Create account'),''))
            if path=='/': body+=f'<section class="hero"><div class="hero-copy"><p class="eyebrow">VOTELAB</p><h2>{t("先看清楚，再做选择。","See the entry. Make your choice.")}</h2><p>{t("单／多选、多数决选、排序或星级评分。","Single / multiple choice, majority, ranked choice and star ratings.")}</p></div><div class="hero-art"><div class="hero-symbol">✦</div></div></section>'
            selected=scalar(query,'status','ALL'); filters=[('ALL',t('全部','All')),('OPEN',t('投票中','Voting')),('ENTRIES',t('报名中','Applications')),('CLOSED',t('已结束','Closed'))]+([('DRAFT',t('草稿','Drafts'))] if path=='/dashboard' else [])
            tabs=''.join(f'<a class="{"active" if selected==value else ""}" href="{path}?status={value}">{label}</a>' for value,label in filters)
            body+=f'<div class="toolbar"><div class="tabs">{tabs}</div><input class="search" data-search placeholder="{t("搜索名称或活动编号，如 V000005","Search title or event code, e.g. V000005")}"></div><div class="grid">'; count=0
            for index,ev in enumerate(rows):
                phase='ENTRIES' if ev['status']=='DRAFT' and ev['submissions_open'] else ev['status']
                if selected!='ALL' and selected!=phase: continue
                count+=1; approved=cs(ev); rnd=rules.current_round(con,ev); votes=con.execute('SELECT COUNT(*) FROM ballots WHERE round_id=?',(rnd['id'],)).fetchone()[0]
                photo=next((c['image_id'] for c in approved if c['image_id']),None) if access(ev) else None
                cover=f'<img class="event-cover-photo" src="/media/{photo}" alt="{e(ev["title"])}" loading="lazy">' if photo else f'<div class="cover tone{index%3}"><span class="glyph">✦</span></div>'
                body+=f'<article class="event-card" data-title="{e(ev["title"])} {e(ev["tags"])} V{ev["id"]:06d}"><a href="/e/{ev["id"]}">{cover}<div class="card-body">{view.badge(ev)}<h3>{e(ev["title"])}</h3><p>{view.method(ev)}</p><p class="helper">{e(ev["tags"])}</p><p class="helper">V{ev["id"]:06d} · {t("需要邀请码","Invitation required") if ev["invite_hash"] else t("开放参与","Open access")}</p><div class="card-meta"><span>{len(approved)} {t("项作品","entries")}</span><span>{votes} {t("张本轮选票","ballots this round")}</span></div><div class="card-footer">{t("查看活动","View event")} →</div></div></a></article>'
            body+=f'</div><div data-no-matches class="empty" hidden>{t("没有匹配的活动。","No matching events.")}</div>'
            if not count: body+=f'<div class="empty">{t("暂无活动。","No events yet.")}</div>'
            return response(view.page(title,body,section))
        match=re.fullmatch(r'/e/(\d+)(/preview|/edit|/results|/apply|/review|/revision|/status)?',path)
        if not match: raise Problem('Page not found / 页面不存在。',404)
        eid=int(match[1]); suffix=match[2] or ''; event=get_event(eid)
        if suffix in ('/preview','/edit','/review','/revision'): require_owner(event)
        if event['status']=='DRAFT' and not event['submissions_open'] and not owner(event): raise Problem('Draft not public / 草稿尚未公开。',403)
        if not access(event):
            require()
            body=view.head(t('此活动需要邀请码','Invitation required'),e(event['title']))+f'<form class="panel narrow" method="post" action="/e/{eid}/access">{hidden()}<label class="field">{t("请输入发起者提供的邀请码","Enter the code supplied by the organiser")}<input name="invite_code" required maxlength="64" autocomplete="off"></label><button class="btn">{t("进入活动","Enter event")}</button></form>'
            return response(view.page(t('输入邀请码','Enter invitation code'),body))
        if suffix=='/status':
            start('200 OK',[('Content-Type','application/json'),('Cache-Control','no-store')]); return [json.dumps({'status':event['status'],'paused':event['paused'],'round':event['current_round'],'ends_at':event['ends_at']}).encode()]
        if suffix in ('/edit','/revision'):
            if suffix=='/edit' and event['status']!='DRAFT': raise Problem('Voting rules are locked; pause first / 活动已锁定，请先暂停修改。',409)
            if suffix=='/revision' and not event['paused']: raise Problem('Pause first / 请先暂停投票。',409)
            return response(view.page(t('编辑活动','Edit event'),view.head(t('编辑活动','Edit event'))+view.event_form(event,cs(event,True)),'dashboard'))
        if suffix=='/apply':
            require()
            if owner(event): return redirect(f'/e/{eid}/edit')
            if event['status']!='DRAFT' or not event['submissions_open'] or event['planned_end']<=time.time(): raise Problem('Applications closed / 报名已关闭。',409)
            previous=con.execute('SELECT * FROM candidates WHERE election_id=? AND submitter_id=? AND active=1',(eid,user['id'])).fetchone()
            if previous and previous['review_status']!='REJECTED': return redirect('/my-entries')
            body=view.head(t('报名并提交作品','Submit an entry'),e(event['title']))
            if previous: body+=f'<div class="notice error" role="alert">{t("上次驳回原因：","Previous rejection: ")}{e(previous["review_reason"])}</div>'
            name=previous['name'] if previous else ''; desc=previous['description'] if previous else ''
            body+=f'<form class="panel narrow" method="post" enctype="multipart/form-data">{hidden()}<label class="field">{t("作品名称","Entry name")}<input name="name" maxlength="80" required value="{e(name)}"></label><label class="field">{t("作品图片（可选）","Entry image (optional)")}<input type="file" name="image" accept="image/jpeg,image/png,image/webp" data-image-input><small>JPEG / PNG / WebP · 5 MB</small></label><div class="standalone-preview"></div>'
            if previous and previous['image_id']: body+=f'<img class="submission-thumb" src="/media/{previous["image_id"]}" alt="{e(name)}"><label class="helper"><input type="checkbox" name="remove_image" value="1">{t("移除旧图","Remove previous image")}</label>'
            body+=f'<label class="field">{t("介绍（可选）","Description (optional)")}<textarea name="description" maxlength="1000" rows="5">{e(desc)}</textarea></label><button class="btn">{t("提交审核","Submit for review")}</button></form>'
            return response(view.page(t('提交作品','Submit entry'),body,'my-entries'))
        if suffix=='/review':
            done=scalar(query,'tab')=='done'; labels={'PENDING':t('待审核','Pending'),'APPROVED':t('已通过','Approved'),'REJECTED':t('已驳回','Rejected')}
            body=view.head(t('审核参赛作品','Review submissions'),e(event['title']),link(f'/e/{eid}',t('返回活动','Back to event')))+f'<div class="tabs"><a href="/e/{eid}/review">{t("待审核","Pending")}</a><a href="/e/{eid}/review?tab=done">{t("已审核","Reviewed")}</a></div>'; count=0
            for c in cs(event,True):
                if c['submitter_id'] in (None,user['id']) or (c['review_status']=='PENDING')==done: continue
                count+=1; image=f'<img class="submission-thumb" src="/media/{c["image_id"]}" alt="{e(c["name"])}">' if c['image_id'] else ''
                body+=f'<article class="panel submission-card">{image}<div><span class="badge draft">{labels[c["review_status"]]}</span><h3>{e(c["name"])}</h3><p>{e(c["description"])}</p>'
                if not done and event['status']=='DRAFT':
                    body+=f'<form method="post">{hidden()}<input type="hidden" name="candidate_id" value="{c["id"]}"><label class="field">{t("反馈／驳回原因（驳回时必填）","Feedback / rejection reason (required to reject)")}<textarea name="reason" maxlength="500" rows="2"></textarea></label><button class="btn" name="verdict" value="APPROVED">{t("通过","Approve")}</button><button class="btn secondary" name="verdict" value="REJECTED">{t("驳回","Reject")}</button></form>'
                else: body+=f'<p>{e(c["review_reason"])}</p>'
                body+='</div></article>'
            if not count: body+=f'<div class="empty">{t("暂无已审核作品。" if done else "待审核作品已处理完毕。","No reviewed entries." if done else "No pending submissions.")}</div>'
            return response(view.page(t('审核作品','Review submissions'),body,'dashboard'))
        rnd=rules.current_round(con,event); count=con.execute('SELECT COUNT(*) FROM ballots WHERE round_id=?',(rnd['id'],)).fetchone()[0]
        can_result=event['status']=='CLOSED' and (owner(event) or (event['published'] and event['visibility']=='PUBLIC'))
        if suffix=='/results':
            if not can_result: raise Problem('Results not published or private / 结果尚未发布或仅创建者可查看。',403)
            try: number=int(scalar(query,'round',str(event['current_round'])))
            except ValueError: raise Problem('Invalid round / 轮次无效。')
            if not 1<=number<=event['current_round']: raise Problem('Round not found / 轮次不存在。',404)
            result=rules.counts(con,event,number); body=view.head(e(event['title']),t('按轮次查看汇总，旧轮选票不会混入本轮。','Round totals are kept separate; earlier ballots never count in a new round.'),link(f'/e/{eid}',t('返回活动','Back to event')))
            body+='<div class="tabs">'+''.join(f'<a href="/e/{eid}/results?round={n}">{t("轮次","Round")} {n}</a>' for n in range(1,event['current_round']+1))+'</div>'
            states={'NO_VOTES':t('暂无有效选票，不产生赢家。','No valid ballots; no winner.'),'NO_ACTIVE_BALLOTS':t('有效偏好已用尽，不产生赢家。','No continuing preferences; no winner.'),'ELIMINATION_TIE':t('最低票并列，计票暂停；不会随机淘汰。','Lowest count tied; counting stops without random elimination.'),'CUTOFF_TIE':t('决选入围边界并列，需处理平票后再推进。','Runoff cutoff tied; resolve the tie before proceeding.'),'FINAL_TIE':t('决选平票，结果待处理。','Final round tied; resolution pending.'),'RUNOFF_REQUIRED':t('无人过半，需要前两名进入第二轮重新投票。','No majority; the top two need a new runoff ballot.'),'RANKED':t('相同结果显示并列，奖项名额另行处理。','Equal results share a rank. Award allocation is separate.'),'WINNER':t('已产生过半赢家。','A candidate has a majority.')}
            body+=f'<section class="panel"><h2>{t("评分平均分（0～5）","Average rating (0–5)") if result["method"]=="SCORE" else t("计票结果","Count results")}</h2><p>{result["ballots"]} {t("张本轮有效选票","valid ballots in this round")}</p><div class="notice info">{states[result["state"]]}</div>'
            names={r['id']:r['name'] for r in result['rows']}
            if result['winner'] is not None: body+=f'<h3>{t("赢家：","Winner: ")}{e(names[result["winner"]])}</h3>'
            if result['method']=='RCV':
                for index,step in enumerate(result['rounds'],1):
                    body+=f'<h3>{t("计票轮","Count")} {index}</h3><p>{t("有效偏好票／耗尽票","Continuing / exhausted")}: {step["active"]} / {step["exhausted"]}</p>'
                    body+=''.join(f'<div class="summary-row"><span>{e(names[cid])}</span><strong>{value}</strong></div>' for cid,value in step['counts'].items())
                    if 'eliminated' in step: body+=f'<p>{t("淘汰：","Eliminated: ")}{e(names[step["eliminated"]])}</p>'
            else:
                previous=object(); rank=0
                for index,row in enumerate(result['rows'],1):
                    value=row['average'] if result['method']=='SCORE' else row['total']
                    if value!=previous: rank=index
                    previous=value
                    display=t('未评分','Not rated') if value is None else f'{value:.2f} / 5' if result['method']=='SCORE' else str(value)
                    detail=f'{row["n"]} '+t('人评分','ratings') if result['method']=='SCORE' else ''
                    body+=f'<div class="summary-row"><span>{rank}. {e(row["name"])}</span><strong>{display}<small> {detail}</small></strong></div>'
            body+='</section>'
            if owner(event) and number==event['current_round'] and result['state']=='RUNOFF_REQUIRED':
                deadline=datetime.fromtimestamp(time.time()+86400,entries.TZ).strftime('%Y-%m-%dT%H:%M')
                body+=f'<form class="panel" method="post" action="/e/{eid}/next-round">{hidden()}<label class="field">{t("第二轮截止时间","Runoff deadline")}<input type="datetime-local" name="deadline" required value="{deadline}"></label><button class="btn">{t("开启前两名决选（重新投票）","Open top-two runoff (new ballots)")}</button></form>'
            body+=f'<p class="helper">{t("奖项分配与平票联合审批尚未实现；系统不会擅自决定并列赢家。","Award allocation and joint tie-resolution approval remain unfinished. The system does not invent a tie-break winner.")}</p>'
            return response(view.page(t('结果','Results'),body))
        preview=suffix=='/preview' or (event['status']=='DRAFT' and owner(event)); candidates=cs(event)
        own=con.execute('SELECT id FROM ballots WHERE round_id=? AND user_id=?',(rnd['id'],user['id'] if user else -1)).fetchone()
        can_vote=bool(user and not preview and not own and event['status']=='OPEN' and not event['paused'])
        body=view.head(e(event['title']),f'V{eid:06d} · '+view.method(event),link('/dashboard' if owner(event) else '/',t('← 返回','← Back')))
        if preview: body+=f'<div class="notice info">{t("预览不计票。确认设置、作品和截止时间后再开启投票。","Preview saves no ballots. Check settings, entries and deadline before starting.")}</div>'
        if event['announcement']: body+=f'<div class="notice info"><strong>{t("活动公告：","Announcement: ")}</strong>{e(event["announcement"])}</div>'
        changes=con.execute('SELECT * FROM event_changes WHERE election_id=? ORDER BY id DESC',(eid,)).fetchall()
        if changes:
            body+=f'<details class="panel"><summary>{t("查看修改记录","View change history")}</summary>'
            for change in changes: body+=f'<p><strong>{view.stamp(change["created"])} · {t("轮次","Round")} {change["round_number"]}</strong><br>{e(change["announcement"])}</p>'
            body+='</details>'
        if own: body+=f'<div class="notice success">✓ {t("投票已成功保存，本轮无需再次提交。","Your ballot is saved. Do not submit again this round.")} (ALREADY_VOTED)</div>'
        if event['paused']: body+=f'<div class="notice error">{t("活动正在暂停修改，暂时不能投票。","Voting is paused while the organiser makes changes.")}</div>'
        saved={}
        if own:
            if event['method']=='RCV': saved={'rank_'+str(r['candidate_id']):str(r['position']) for r in con.execute('SELECT * FROM preferences WHERE ballot_id=?',(own['id'],))}
            else:
                choices=con.execute('SELECT candidate_id,score FROM choices WHERE ballot_id=?',(own['id'],)).fetchall()
                saved={'candidate':[str(c['candidate_id']) for c in choices]} if event['method'] in ('SINGLE','MAJORITY') else {'score_'+str(c['candidate_id']):str(c['score']) for c in choices}
        body+=f'<div class="detail-layout"><section><form method="post" action="/e/{eid}/confirm" data-ballot data-limit="{event["max_choices"]}" data-method="{event["method"]}">{hidden()}<input type="hidden" name="round_id" value="{rnd["id"]}">{view.cards(event,candidates,can_vote,saved)}'
        if not candidates: body+=f'<div class="empty">{t("暂无通过审核的作品。","No approved entries yet.")}</div>'
        if can_vote: body+=f'<div class="sticky-actions"><small data-selection-count aria-live="polite"></small><button class="btn">{t("核对选票","Review ballot")} →</button></div>'
        elif not own: body+=f'<p class="helper">{t("当前不能投票：请登录，并等待活动开始；暂停或截止后不接收新票。","Voting is unavailable. Sign in and wait for voting to open; paused or closed events accept no ballots.")}</p>'
        descriptions={'SINGLE':t(f'每人最多选{event["max_choices"]}个不同作品，每个作品加1票。',f'Select up to {event["max_choices"]} different entries; each gets one vote.'),'SCORE':t('可只评部分作品，至少评1项；未评不计为0分，按平均分排名。' if event['score_optional'] else '旧版活动：全部作品必评；结果显示平均分。','Rate at least one entry; skipped entries do not count as zero. Rank by average.' if event['score_optional'] else 'Legacy event: all entries must be rated; results show averages.'),'RCV':t('可只排部分作品；从1开始，不重复、不跳号。计票遇最低票并列时暂停。','Rank any subset from 1 without gaps or duplicates. Lowest-count ties stop counting.'),'MAJORITY':t('每轮选1项；超过本轮有效票50%获胜，否则前两名重新投票。','Choose one each round. More than 50% wins; otherwise the top two need a fresh vote.')}
        body+=f'</form></section><aside class="rule-panel"><div class="panel"><h2>{t("参与规则","Participation rules")}</h2>{view.badge(event)}<ul class="rule-list"><li>{descriptions[event["method"]]}</li><li>{t("当前轮次","Current round")}: {event["current_round"]}</li><li>{t("截止至","Ends at")}: {view.stamp(event["ends_at"] or event["planned_end"])}</li><li>{count} {t("张本轮选票","ballots this round")}</li><li>{t("发布后公开结果","Public results after publication") if event["visibility"]=="PUBLIC" else t("结果仅创建者可见","Creator-only results")}</li></ul>'
        if not user: body+=link('/login',t('登录参与','Log in to participate'),'')
        if user and not owner(event) and event['status']=='DRAFT' and event['submissions_open']: body+=link(f'/e/{eid}/apply',t('报名并提交作品','Submit an entry'),'')
        if owner(event):
            if event['status']=='DRAFT':
                pending=sum(c['review_status']=='PENDING' for c in cs(event,True)); body+=f'<p class="helper">{pending} {t("项待审核","pending reviews")}</p><div class="button-row">'+link(f'/e/{eid}/edit',t('返回编辑','Edit event'))+link(f'/e/{eid}/review',t('审核报名','Review entries'))
                if event['allow_submissions'] and not event['submissions_open']: body+=button(f'/e/{eid}/collect',t('开放报名','Open applications'))
                body+=button(f'/e/{eid}/open',t('确认设置并开始投票','Confirm settings and start voting'),confirm=t('请确认作品、投票方式、数量与截止时间。开票后修改需要暂停并公告。','Confirm entries, rules, selection limit and deadline. Later edits require pausing and an announcement.'))+'</div>'
            if event['status']=='OPEN':
                if event['paused']:
                    body+=link(f'/e/{eid}/revision',t('编辑暂停中的活动','Edit paused event'))+button(f'/e/{eid}/resume',t('确认修改并恢复投票','Confirm and resume'))
                elif event['revisions']<3: body+=button(f'/e/{eid}/pause',t(f'暂停并修改（剩余{3-event["revisions"]}次）',f'Pause and edit ({3-event["revisions"]} left)'),confirm=t('暂停期间所有人都不能投票；修改须公告。','Voting stops for everyone while paused. Changes require an announcement.'))
                body+=button(f'/e/{eid}/close',t('关闭投票','Close voting'),'danger',t('确认关闭投票？','Close voting?'))
            if event['status']=='CLOSED' and not event['published']: body+=button(f'/e/{eid}/publish',t('发布结果','Publish results'))
        if can_result: body+=link(f'/e/{eid}/results',t('查看结果／历史轮次','View results / round history'),'')
        elif event['status']=='CLOSED': body+=f'<p>{t("等待发布结果，或结果仅创建者可见。","Awaiting publication, or results are private.")}</p>'
        body+='</div></aside></div>'
        if event['status']=='OPEN': body+=f'<div data-event-status="/e/{eid}/status" data-state="{event["status"]}" data-paused="{event["paused"]}" data-round="{event["current_round"]}" data-end="{event["ends_at"]}"></div>'
        return response(view.page(t('活动详情','Event details'),body,'dashboard' if owner(event) else 'gallery'))
    except Problem as error:
        con.rollback(); message=error.message
        if ' / ' in message: message=message.split(' / ',1)[0 if lang=='en' else 1]
        body=view.head(t('无法完成这一步','Unable to complete this step'))+f'<section class="panel narrow"><div class="notice error" role="alert"><strong>{e(message)}</strong></div><div class="button-row">'
        if not user or path in ('/login','/register','/reset','/auth/code'):
            body+=link('/login',t('登录账号','Log in'))+link('/register',t('注册账号','Create account'))+link('/reset',t('重置密码','Reset password'))
        else:
            body+=f'<button class="btn secondary" type="button" data-go-back>{t("返回修改","Go back to edit")}</button>'
            if path.endswith('/vote'): body+=link('/my-votes',t('检查是否已投成功','Check My votes'))
            if event: body+=link(f'/e/{event["id"]}',t('返回活动','Back to event'))
        body+='</div></section>'
        return response(view.page(t('操作未完成','Action not completed'),body),error.status)
    except (TimeoutError,ConnectionError):
        con.rollback(); return response(view.page(t('请求超时','Request timed out'),view.head(t('连接中断，尚未完成操作','Connection interrupted before completion'),t('请检查网络；投票请先查看我的投票，避免重复操作。','Check your connection. For a ballot, check My votes before trying again.'))),408)
    except sqlite3.IntegrityError:
        con.rollback(); return response(view.page(t('未保存','Not saved'),view.head(t('未保存更改','Changes were not saved'),t('账号或选项冲突，或状态已变化。请检查提交状态后再试。','Account or entry conflict, or state changed. Check submission status before retrying.'))),409)
    except sqlite3.Error:
        con.rollback(); return response(view.page(t('保存失败','Save failed'),view.head(t('暂时无法保存','Unable to save'),t('请先检查提交状态，再重试。','Check submission status before retrying.'))),500)
    finally: con.close()
