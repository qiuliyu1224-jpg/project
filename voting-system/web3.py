"""Routes for structured entries, applications and unified code-only accounts."""
import hmac
import re
import secrets
import sqlite3
import time
from http.cookies import SimpleCookie,CookieError
from urllib.parse import parse_qs
import app as core
import entries
from app import e,scalar,Problem
from ui3 import View
from auth import issue_code,consume_code


def dispatch(env,start):
    path=env.get('PATH_INFO','/')
    if path in ('/static/style.css','/static/entries.css','/static/app.js'):
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
    con=core.connect(); user=None; form={}; view=View(lang,csrf,user,path)
    t=view.t; hidden=view.hidden; link=view.link; button=view.button
    def response(body,status=200):
        phrases={200:'OK',303:'See Other',400:'Bad Request',401:'Unauthorized',403:'Forbidden',404:'Not Found',409:'Conflict',413:'Content Too Large',429:'Too Many Requests',500:'Internal Server Error'}
        start(f'{status} {phrases.get(status,"Error")}',headers); return [body.encode('utf-8')]
    def redirect(url): headers.append(('Location',url)); return response('',303)
    def require():
        if not user: raise Problem('Please log in first / 请先登录。',401)
    def get_event(eid):
        ev=con.execute('SELECT * FROM elections WHERE id=?',(eid,)).fetchone()
        if not ev: raise Problem('Event not found / 活动不存在。',404)
        return ev
    def require_owner(ev):
        require()
        if ev['creator_id']!=user['id']: raise Problem('Only the event creator may do this / 仅活动创建者可操作。',403)
    def cs(eid,allrows=False): return con.execute('SELECT * FROM candidates WHERE election_id=?'+('' if allrows else " AND review_status='APPROVED'")+' ORDER BY id',(eid,)).fetchall()
    def review_labels(): return {'PENDING':t('待审核','Pending'),'APPROVED':t('已通过','Approved'),'REJECTED':t('已驳回','Rejected')}
    try:
        with con: core.refresh(con)
        user=con.execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=? AND s.expires>?',(token,int(time.time()))).fetchone()
        view.user=user
        media=re.fullmatch('/media/([a-f0-9]{40})',path)
        if media:
            image=con.execute("SELECT i.content FROM images i JOIN candidates c ON c.image_id=i.id JOIN elections ev ON ev.id=c.election_id WHERE i.id=? AND ((c.review_status='APPROVED' AND (ev.status<>'DRAFT' OR ev.submissions_open=1)) OR ev.creator_id=? OR c.submitter_id=?) LIMIT 1",(media[1],user['id'] if user else -1,user['id'] if user else -1)).fetchone()
            if not image: raise Problem('Image not found / 图片不可访问。',404)
            start('200 OK',[('Content-Type','image/jpeg'),('Cache-Control','private, no-store'),('X-Content-Type-Options','nosniff')]); return [image['content']]
        query=parse_qs(env.get('QUERY_STRING',''))
        if env['REQUEST_METHOD']=='POST':
            form,files=entries.read_form(env)
            if not hmac.compare_digest(scalar(form,'csrf'),csrf): raise Problem('Form expired. Reload and retry / 表单已过期，请刷新后重试。',403)
            if path=='/language':
                language=scalar(form,'lang'); target=scalar(form,'next','/')
                if language not in ('zh','en'): raise Problem('Unsupported language / 不支持该语言。')
                if not re.fullmatch(r'/[a-zA-Z0-9/_-]*',target): target='/'
                headers.append(('Set-Cookie',f'lang={language}; SameSite=Lax; Path=/; Max-Age=31536000')); return redirect(target)
            if path=='/auth/code':
                phone,purpose=scalar(form,'phone').strip(),scalar(form,'purpose')
                row=con.execute('SELECT 1 FROM users WHERE phone=?',(phone,)).fetchone()
                if purpose=='login' and not row: raise Problem('Create an account first / 账号未注册，请先点击注册账号。')
                if purpose=='register' and row: raise Problem('Account already exists; log in / 账号已存在，请直接登录。',409)
                code=issue_code(con,phone,browser,purpose)
                return response(view.auth(purpose=='register',phone,scalar(form,'name'),code))
            if path in ('/login','/register'):
                phone=scalar(form,'phone').strip(); purpose=path[1:]
                if not re.fullmatch(r'[0-9]{8,15}',phone): raise Problem('Invalid phone format / 手机号格式不正确。')
                row=con.execute('SELECT * FROM users WHERE phone=?',(phone,)).fetchone()
                if purpose=='register':
                    name=scalar(form,'name').strip()
                    if not 1<=len(name)<=60: raise Problem('Name must be 1–60 characters / 名称需1–60字。')
                    if row: raise Problem('Account already exists / 账号已存在。',409)
                elif not row: raise Problem('Create an account first / 请先注册账号。',401)
                consume_code(con,phone,browser,purpose,scalar(form,'code'))
                with con:
                    if purpose=='register':
                        salt=secrets.token_hex(16)
                        uid=con.execute('INSERT INTO users(phone,name,salt,password_hash) VALUES(?,?,?,?)',(phone,name,salt,core.password_hash(secrets.token_urlsafe(32),salt))).lastrowid
                    else: uid=row['id']
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
            match=re.fullmatch(r'/e/(\d+)/(open|close|publish|vote|confirm|edit|collect|apply|review)',path)
            if not match: raise Problem('Not found / 页面不存在。',404)
            eid,action=int(match[1]),match[2]; event=get_event(eid)
            if action in ('vote','confirm'):
                if event['status']!='OPEN' or event['ends_at']<=time.time(): raise Problem('ELECTION_CLOSED / 投票已结束或尚未开始。')
                if action=='vote': core.submit_ballot(con,eid,user['id'],form); return redirect(f'/e/{eid}')
                if con.execute('SELECT 1 FROM ballots WHERE election_id=? AND user_id=?',(eid,user['id'])).fetchone(): raise Problem('ALREADY_VOTED / 本轮已经投过票。')
                candidates=cs(eid); selected={}
                if event['method']=='SINGLE':
                    value=scalar(form,'candidate')
                    if value not in [str(c['id']) for c in candidates]: raise Problem('Select one valid option / 请选择一个有效选项。')
                    selected['candidate']=value
                else:
                    for c in candidates:
                        value=scalar(form,'score_'+str(c['id']))
                        if value not in ('0','1','2','3','4','5'): raise Problem('Rate every option from 0 to 5 / 请为每个选项评0–5整数分。')
                        selected['score_'+str(c['id'])]=value
                summary=''.join(f'<div class="summary-row"><span>{e(c["name"])}</span><strong>{selected.get("score_"+str(c["id"]),t("已选择","Selected"))}</strong></div>' for c in candidates if event['method']=='SCORE' or selected['candidate']==str(c['id']))
                fields=''.join(f'<input type="hidden" name="{e(k)}" value="{e(v)}">' for k,v in selected.items())
                body=view.head(t('确认你的选择','Review your ballot'),t('目前尚未保存。请核对，成功保存后不能修改。','Not saved yet. Check carefully; a saved ballot cannot be edited.'))+f'<div class="panel narrow"><h2>{e(event["title"])}</h2>{summary}<form method="post" action="/e/{eid}/vote">{hidden()}{fields}<div class="button-row"><button class="btn">{t("确认提交","Confirm and submit")}</button>{link("/e/"+str(eid),t("返回重选","Choose again"))}</div></form></div>'
                return response(view.page(t('核对选票','Review ballot'),body))
            if action=='apply':
                with con:
                    con.execute('BEGIN IMMEDIATE'); entries.apply_entry(con,eid,user['id'],form,files)
                return redirect('/my-entries')
            require_owner(event)
            with con:
                con.execute('BEGIN IMMEDIATE'); core.refresh(con); event=get_event(eid)
                if action in ('edit','review','collect','open') and event['status']!='DRAFT': raise Problem('Entries and rules are locked / 开票后名单和规则锁定。',409)
                if action=='edit': entries.save_event(con,user['id'],form,files,eid)
                elif action=='collect':
                    if not event['allow_submissions']: raise Problem('Enable applications in the editor first / 请先在编辑页允许报名。')
                    if not event['planned_end'] or event['planned_end']<=time.time()+60: raise Problem('Update the deadline / 请先更新截止时间。')
                    con.execute('UPDATE elections SET submissions_open=1 WHERE id=?',(eid,))
                elif action=='review':
                    cid=scalar(form,'candidate_id'); verdict=scalar(form,'verdict'); reason=scalar(form,'reason').strip()
                    candidate=con.execute('SELECT * FROM candidates WHERE id=? AND election_id=?',(cid,eid)).fetchone()
                    if not candidate or verdict not in ('APPROVED','REJECTED') or len(reason)>500: raise Problem('Invalid review / 审核内容无效。')
                    if candidate['submitter_id'] in (None,user['id']): raise Problem('Use the editor for creator entries / 创建者选项请在编辑页操作。')
                    if verdict=='REJECTED' and not reason: raise Problem('Give a rejection reason / 请填写驳回原因。')
                    con.execute('UPDATE candidates SET review_status=?,review_reason=? WHERE id=?',(verdict,reason,cid))
                elif action=='open':
                    pending=con.execute("SELECT COUNT(*) FROM candidates WHERE election_id=? AND review_status='PENDING'",(eid,)).fetchone()[0]
                    if len(cs(eid))<2 or pending: raise Problem('Need 2 approved entries and no pending reviews / 至少需2项通过审核，并先处理全部待审作品。')
                    end=event['planned_end'] or int(time.time())+event['duration']*60
                    if not time.time()+60<end<=time.time()+entries.MAX_DAYS*86400: raise Problem('Update the end date before starting / 请更新截止时间后开票。')
                    con.execute("UPDATE elections SET status='OPEN',ends_at=?,submissions_open=0 WHERE id=?",(end,eid))
                elif action=='close':
                    if event['status']!='OPEN': raise Problem('Voting is not open / 当前不在投票中。',409)
                    con.execute("UPDATE elections SET status='CLOSED' WHERE id=?",(eid,))
                elif action=='publish':
                    if event['status']!='CLOSED': raise Problem('Close voting first / 请先关闭投票。',409)
                    con.execute('UPDATE elections SET published=1 WHERE id=?',(eid,))
                con.execute('INSERT INTO audit(election_id,actor_id,action,created) VALUES(?,?,?,?)',(eid,user['id'],action,int(time.time())))
            return redirect(f'/e/{eid}/review' if action=='review' else f'/e/{eid}/preview' if action=='edit' else f'/e/{eid}')
        if env['REQUEST_METHOD']!='GET': raise Problem('Unsupported method / 不支持的请求。')
        if path in ('/login','/register'): return response(view.auth(path=='/register'))
        if path=='/create':
            require(); return response(view.page(t('创建活动','Create event'),view.head(t('创建一场新活动','Create a new event'),t('从模板开始，或自定义图片、名称和介绍。','Start with a template, or add your own images, names and descriptions.'))+view.event_form(template=scalar(query,'template','custom')),'dashboard'))
        if path=='/my-entries':
            require(); rows=con.execute('SELECT c.*,ev.title FROM candidates c JOIN elections ev ON ev.id=c.election_id WHERE c.submitter_id=? AND ev.creator_id<>? ORDER BY c.id DESC',(user['id'],user['id'])).fetchall()
            body=view.head(t('我的作品','My entries'),t('查看审核状态和创建者的反馈。','Track review status and creator feedback.')); labels=review_labels()
            for c in rows:
                image=f'<img class="submission-thumb" src="/media/{c["image_id"]}" alt="{e(c["name"])}">' if c['image_id'] else ''
                body+=f'<article class="panel submission-card">{image}<div><span class="badge draft">{labels[c["review_status"]]}</span><h3>{e(c["name"])}</h3><p class="entry-description">{e(c["description"])}</p><p class="helper">{e(c["title"])}</p><p>{e(c["review_reason"])}</p>{link("/e/"+str(c["election_id"]),t("查看活动","View event"))}</div></article>'
            if not rows: body+=f'<div class="empty">{t("暂无报名作品，到广场寻找正在报名的活动。","No submissions yet. Explore events accepting entries.")}</div>'
            return response(view.page(t('我的作品','My entries'),body,'my-entries'))
        if path in ('/','/dashboard','/my-votes'):
            if path!='/': require()
            section='gallery' if path=='/' else path[1:]
            if path=='/dashboard': rows=con.execute('SELECT * FROM elections WHERE creator_id=? ORDER BY id DESC',(user['id'],)).fetchall()
            elif path=='/my-votes': rows=con.execute('SELECT ev.* FROM elections ev JOIN ballots b ON b.election_id=ev.id WHERE b.user_id=? ORDER BY b.id DESC',(user['id'],)).fetchall()
            else: rows=con.execute("SELECT * FROM elections WHERE status<>'DRAFT' OR submissions_open=1 ORDER BY status='OPEN' DESC,id DESC").fetchall()
            title=t('管理我的活动','Manage my events') if section=='dashboard' else t('我的投票','My votes') if section=='my-votes' else t('发现值得支持的想法','Discover ideas worth supporting')
            action=link('/create',t('＋ 创建活动','＋ Create event'),'') if user else link('/register',t('注册并参与','Create an account'),'')
            body=view.head(title,t('一个账号，可以创建活动、提交作品，也可以投票。','One account lets you create events, submit entries and vote.'),action)
            if section=='gallery': body+=f'<section class="hero"><div class="hero-copy"><p class="eyebrow">{t("每一个好想法，都值得被看见","MAKE YOUR VOICE COUNT")}</p><h2>{t("先看清楚，再做选择。<br>让图片与故事一起说话。","See the entry.<br>Understand the story.<br>Make your choice.")}</h2><p>{t("浏览图片、阅读介绍，提交作品或参与投票。","Browse images and descriptions, submit your work or vote.")}</p></div><div class="hero-art"><div class="hero-symbol">✦</div></div></section>'
            body+=f'<div class="stats"><div class="stat"><label>{t("活动数量","Events")}</label><strong>{len(rows):02d}</strong></div><div class="stat"><label>{t("投票中","Voting open")}</label><strong>{sum(r["status"]=="OPEN" for r in rows):02d}</strong></div><div class="stat"><label>{t("开放报名","Accepting entries")}</label><strong>{sum(bool(r["status"]=="DRAFT" and r["submissions_open"]) for r in rows):02d}</strong></div></div>'
            selected=scalar(query,'status','ALL'); filters=[('ALL',t('全部','All')),('OPEN',t('投票中','Voting')),('ENTRIES',t('报名中','Applications')),('CLOSED',t('已结束','Closed'))]+([('DRAFT',t('草稿','Drafts'))] if section=='dashboard' else [])
            tabs=''.join(f'<a class="{"active" if selected==value else ""}" href="{path}?status={value}">{label}</a>' for value,label in filters)
            body+=f'<div class="toolbar"><div class="tabs">{tabs}</div><input class="search" data-search aria-label="{t("搜索活动","Search events")}" placeholder="{t("搜索活动","Search events")}"></div><div class="grid">'; count=0
            for index,row in enumerate(rows):
                phase='ENTRIES' if row['status']=='DRAFT' and row['submissions_open'] else row['status']
                if selected!='ALL' and selected!=phase: continue
                count+=1; approved=cs(row['id']); votes=con.execute('SELECT COUNT(*) FROM ballots WHERE election_id=?',(row['id'],)).fetchone()[0]; photo=next((c['image_id'] for c in approved if c['image_id']),None)
                cover=f'<img class="event-cover-photo" src="/media/{photo}" alt="{e(row["title"])}" loading="lazy">' if photo else f'<div class="cover tone{index%3}"><span class="cover-type">VOTELAB · {row["id"]:03d}</span><span class="glyph">{"◉" if row["method"]=="SINGLE" else "✦"}</span></div>'
                method=t('单选','Single choice') if row['method']=='SINGLE' else t('星星评分','Star rating')
                body+=f'<article class="event-card" data-title="{e(row["title"])}"><a href="/e/{row["id"]}">{cover}<div class="card-body"><div class="card-top">{view.badge(row)}<span>{t("私密结果","PRIVATE RESULTS") if row["visibility"]=="PRIVATE" else t("公开结果","PUBLIC RESULTS")}</span></div><h3>{e(row["title"])}</h3><p class="helper">{method}</p><div class="card-meta"><span>{len(approved)} {t("项已确认","approved")}</span><span>{votes} {t("张选票","ballots")}</span></div><div class="card-footer">{t("查看活动","View event")} →</div></div></a></article>'
            body+=f'</div><div data-no-matches class="empty" hidden>{t("没有匹配的活动。","No matching events.")}</div>'
            if not count: body+=f'<div class="empty">{t("暂无活动，试试其他筛选或创建一个。","No events. Try another filter or create one.")}</div>'
            return response(view.page(title,body,section))
        match=re.fullmatch(r'/e/(\d+)(/preview|/edit|/results|/apply|/review)?',path)
        if not match: raise Problem('Not found / 页面不存在。',404)
        eid,suffix=int(match[1]),match[2] or ''; event=get_event(eid); owner=bool(user and user['id']==event['creator_id'])
        if suffix in ('/edit','/preview','/review'): require_owner(event)
        if event['status']=='DRAFT' and not event['submissions_open'] and not owner: raise Problem('Draft not public / 草稿尚未公开。',403)
        candidates=cs(eid)
        if suffix=='/edit':
            if event['status']!='DRAFT': raise Problem('Published rules are locked / 已开票，不能修改。',409)
            return response(view.page(t('编辑活动','Edit event'),view.head(t('编辑草稿','Edit draft'))+view.event_form(event,cs(eid,True)),'dashboard'))
        if suffix=='/apply':
            require()
            if owner: return redirect(f'/e/{eid}/edit')
            if event['status']!='DRAFT' or not event['submissions_open'] or (event['planned_end'] or 0)<=time.time(): raise Problem('Applications are closed / 报名已关闭。',409)
            if con.execute('SELECT 1 FROM candidates WHERE election_id=? AND submitter_id=?',(eid,user['id'])).fetchone(): return redirect('/my-entries')
            body=view.head(t('报名并提交作品','Submit an entry'),e(event['title'])+' · '+t('每个账号限1份报名作品，审核通过后进入投票。','One submission per account; approval is needed before voting.'))
            body+=f'<form class="panel narrow" method="post" enctype="multipart/form-data">{hidden()}<label class="field">{t("作品名称","Entry name")}<input name="name" maxlength="80" required></label><label class="field">{t("作品图片（必填）","Entry image (required)")}<input type="file" name="image" accept="image/jpeg,image/png,image/webp" data-image-input required><small>{t("JPEG、PNG或WebP，最多5MB。","JPEG, PNG or WebP; up to 5 MB.")}</small></label><div class="standalone-preview"></div><label class="field">{t("介绍（可选）","Description (optional)")}<textarea name="description" maxlength="1000" rows="5"></textarea></label><button class="btn">{t("提交审核","Submit for review")}</button></form>'
            return response(view.page(t('提交作品','Submit entry'),body,'my-entries'))
        if suffix=='/review':
            body=view.head(t('审核参赛作品','Review submissions'),e(event['title']),link(f'/e/{eid}',t('返回活动','Back to event'))); labels=review_labels(); count=0
            for c in cs(eid,True):
                if c['submitter_id'] in (None,user['id']): continue
                count+=1; image=f'<img class="submission-thumb" src="/media/{c["image_id"]}" alt="{e(c["name"])}">' if c['image_id'] else ''; controls=''
                if event['status']=='DRAFT': controls=f'<form method="post" action="/e/{eid}/review">{hidden()}<input type="hidden" name="candidate_id" value="{c["id"]}"><label class="field">{t("反馈／驳回原因","Feedback / rejection reason")}<textarea name="reason" maxlength="500" rows="2">{e(c["review_reason"])}</textarea></label><button class="btn" name="verdict" value="APPROVED">{t("通过","Approve")}</button><button class="btn secondary" name="verdict" value="REJECTED">{t("驳回","Reject")}</button></form>'
                body+=f'<article class="panel submission-card">{image}<div><span class="badge draft">{labels[c["review_status"]]}</span><h3>{e(c["name"])}</h3><p class="entry-description">{e(c["description"])}</p>{controls}</div></article>'
            if not count: body+=f'<div class="empty">{t("暂无参赛者提交作品。","No participant submissions yet.")}</div>'
            return response(view.page(t('审核作品','Review submissions'),body,'dashboard'))
        count=con.execute('SELECT COUNT(*) FROM ballots WHERE election_id=?',(eid,)).fetchone()[0]
        if suffix=='/results':
            if event['status']!='CLOSED' or not (owner or (event['published'] and event['visibility']=='PUBLIC')): raise Problem('Results private or unpublished / 结果未发布或仅创建者可查看。',403)
            rows=core.get_results(con,eid); maximum=max([r['total'] for r in rows]+[1])
            body=view.head(e(event['title']),t('仅显示汇总，不公开谁投给谁。','Aggregate results only; voter choices are not disclosed.'),link(f'/e/{eid}',t('返回活动','Back to event')))
            body+=f'<section class="panel"><h2>{t("评分总分","Total scores") if event["method"]=="SCORE" else t("得票统计","Vote counts")}</h2><p class="helper">{count} {t("张有效选票。相同总计显示并列，不自动分配奖项。","valid ballots. Equal totals share a rank; awards are not automatically assigned.")}</p>'
            previous=None; rank=0
            for index,r in enumerate(rows):
                if r['total']!=previous: rank=index+1
                previous=r['total']; body+=f'<div class="result-row"><span>{rank:02d}</span><strong>{e(r["name"])}</strong><div class="bar-track"><div class="bar" style="width:{r["total"]/maximum*100:.1f}%"></div></div><strong>{r["total"]}</strong></div>'
            body+=f'</section><div class="notice info">{t("奖项分配、平票加赛和PDF导出待实现。","Award allocation, tie runoffs and PDF export remain unfinished.")}</div>'
            return response(view.page(t('结果','Results'),body))
        preview=suffix=='/preview' or (event['status']=='DRAFT' and owner)
        already=bool(user and con.execute('SELECT 1 FROM ballots WHERE election_id=? AND user_id=?',(eid,user['id'])).fetchone()); can_vote=bool(user and not preview and not already and event['status']=='OPEN')
        body=view.head(e(event['title']),t('先浏览图片和介绍，再选择或评分。','Review images and descriptions before choosing or scoring.'),link('/dashboard' if owner else '/',t('← 返回','← Back')))
        if preview: body+=f'<div class="notice info">{t("预览不计票，也不会自动开启报名或投票。检查图片、名称、介绍与日期后，再确认下一步。","Preview saves no ballots and does not automatically open applications or voting. Check entries and dates before confirming the next step.")}</div>'
        if already: body+=f'<div class="notice success">✓ {t("投票已成功保存，本轮无需再次提交。","Your ballot is saved. Do not submit another ballot this round.")} (ALREADY_VOTED)</div>'
        saved={}
        if already:
            own=con.execute('SELECT c.candidate_id,c.score FROM choices c JOIN ballots b ON b.id=c.ballot_id WHERE b.election_id=? AND b.user_id=?',(eid,user['id'])).fetchall()
            if event['method']=='SINGLE' and own: saved['candidate']=str(own[0]['candidate_id'])
            else: saved={'score_'+str(c['candidate_id']):str(c['score']) for c in own}
        body+=f'<div class="detail-layout"><section><form method="post" action="/e/{eid}/confirm">{hidden()}{view.cards(event,candidates,can_vote,saved)}'
        if not candidates: body+=f'<div class="empty">{t("暂无通过审核的选项，审核通过后会在这里展示。","No approved entries yet. Approved entries will appear here.")}</div>'
        if can_vote: body+=f'<div class="sticky-actions"><small>{t("先核对，再提交；成功后不能修改。","Review before submitting; a successful ballot cannot be edited.")}</small><button class="btn">{t("核对选票","Review ballot")} →</button></div>'
        method=t('单选','Single choice') if event['method']=='SINGLE' else t('0–5星评分','0–5 star rating')
        body+=f'</form></section><aside class="rule-panel"><div class="panel"><p class="eyebrow">{t("活动信息","EVENT INFORMATION")}</p><h2>{t("参与规则","Participation rules")}</h2>{view.badge(event)}<ul class="rule-list"><li>{method}</li><li>{t("每人每轮一张选票","One ballot per account per round")}</li><li>{t("截止至","Ends at")}: {view.stamp(event["ends_at"] or event["planned_end"])}</li><li>{count} {t("张选票","ballots")}</li><li>{t("发布后公开结果","Results public after publication") if event["visibility"]=="PUBLIC" else t("结果仅创建者可见","Results visible to creator only")}</li><li>{t("每个选项都须评0–5整数分，0分有效。","Rate every option 0–5; zero is valid.") if event["method"]=="SCORE" else t("只能选择一项。","Choose exactly one option.")}</li></ul>'
        if not user: body+=link('/login',t('登录参与','Log in to participate'),'')
        if user and not owner and event['status']=='DRAFT' and event['submissions_open']: body+=link(f'/e/{eid}/apply',t('报名并提交作品','Enter and submit work'),'')
        if owner and event['status']=='DRAFT':
            pending=con.execute("SELECT COUNT(*) FROM candidates WHERE election_id=? AND review_status='PENDING'",(eid,)).fetchone()[0]
            body+=f'<p class="helper">{pending} {t("项作品待审核。","submissions pending review.")}</p><div class="button-row">'+link(f'/e/{eid}/edit',t('返回编辑','Edit draft'))+link(f'/e/{eid}/review',t('审核报名','Review submissions'))
            if event['allow_submissions'] and not event['submissions_open']: body+=button(f'/e/{eid}/collect',t('开放报名征集','Open applications'))
            body+=button(f'/e/{eid}/open',t('锁定名单并开始投票','Lock entries and start voting'),confirm=t('确认锁定名单并开票？之后不能再报名或修改选项。','Lock entries and start voting? Applications and entry editing will close.'))+'</div>'
        if owner and event['status']=='OPEN': body+=button(f'/e/{eid}/close',t('关闭投票','Close voting'),'danger',t('确定关闭？之后不再接受新票。','Close voting? No new ballots will be accepted.'))
        if owner and event['status']=='CLOSED' and not event['published']: body+=button(f'/e/{eid}/publish',t('发布结果','Publish results'))
        if event['status']=='CLOSED':
            body+=link(f'/e/{eid}/results',t('查看结果','View results'),'') if owner or (event['published'] and event['visibility']=='PUBLIC') else f'<p class="helper">{t("等待发布，或结果仅创建者可见。","Awaiting publication, or results are creator-only.")}</p>'
        body+='</div></aside></div>'
        return response(view.page(t('活动详情','Event details'),body,'dashboard' if owner else 'gallery'))
    except Problem as error:
        con.rollback(); message=error.message
        if ' / ' in message: message=message.split(' / ',1)[0 if lang=='en' else 1]
        elif lang=='zh': message=next((v for k,v in {'ALREADY_VOTED':'本轮已经投过票。','ELECTION_CLOSED':'投票已结束或尚未开始。','INVALID_FORMAT':'选票不完整或格式不正确，请检查选项及评分。'}.items() if k in message),'操作未完成，请核对输入和活动状态。')
        body=view.head(t('这一步没有完成','This action was not completed'),e(message))+f'<div class="panel narrow"><p>{t("上传失败时请返回修改，浏览器可能要求重新选择文件。投票结果不确定时先检查我的投票。","Return to edit if upload fails; the browser may require selecting files again. Check My votes if a ballot result is uncertain.")}</p><div class="button-row"><button class="btn secondary" type="button" data-go-back>{t("返回修改","Go back to edit")}</button>{link("/register",t("注册账号","Create account"))}{link("/my-votes",t("检查我的投票","Check my votes"))}{link("/",t("活动广场","Explore"))}</div></div>'
        return response(view.page(t('操作未完成','Action not completed'),body),error.status)
    except sqlite3.IntegrityError:
        con.rollback(); return response(view.page(t('未保存','Not saved'),view.head(t('没有保存更改','Changes were not saved'),t('账号已存在、选项冲突或状态已变化，请检查。','Account exists, entries conflict or state changed. Please check.'))),409)
    except sqlite3.Error:
        con.rollback(); return response(view.page(t('保存失败','Save failed'),view.head(t('暂时无法保存','Unable to save'),t('请先检查提交状态，再重试。','Check submission status before retrying.'))),500)
    finally: con.close()
