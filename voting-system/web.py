"""Workspace UI and routes. Real SMS delivery is intentionally not configured."""
import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from http.cookies import SimpleCookie, CookieError
from urllib.parse import parse_qs
import app as core
from app import Problem, e, scalar


def now():
    return int(time.time())


def stamp(value):
    return datetime.fromtimestamp(value, timezone.utc).astimezone().strftime('%m/%d %H:%M %Z') if value else 'Not started / 尚未开始'


def issue_code(con, phone, browser, purpose):
    if not re.fullmatch(r'[0-9]{8,15}',phone) or purpose not in ('login','register'):
        raise Problem('Enter an 8–15 digit phone account / 手机号需为8–15位数字。')
    row=con.execute('SELECT * FROM verification_codes WHERE phone=? AND browser=? AND purpose=?',(phone,browser,purpose)).fetchone()
    if row and now()-row['created']<60:
        raise Problem('Please wait 60 seconds before requesting another code / 请等待60秒后再获取。',429)
    code=f'{secrets.randbelow(1000000):06d}'
    digest=hmac.new(core.CSRF_KEY,(phone+browser+purpose+code).encode(),'sha256').hexdigest()
    with con:
        con.execute('INSERT OR REPLACE INTO verification_codes VALUES(?,?,?,?,?,?,0)',(phone,browser,purpose,digest,now()+300,now()))
    return code


def consume_code(con,phone,browser,purpose,code):
    row=con.execute('SELECT * FROM verification_codes WHERE phone=? AND browser=? AND purpose=?',(phone,browser,purpose)).fetchone()
    if not row or row['expires']<=now() or row['attempts']>=5:
        raise Problem('Code expired or too many attempts. Request a new code / 验证码过期或尝试过多，请重新获取。')
    digest=hmac.new(core.CSRF_KEY,(phone+browser+purpose+code).encode(),'sha256').hexdigest()
    if not hmac.compare_digest(row['code_hash'],digest):
        with con:
            con.execute('UPDATE verification_codes SET attempts=attempts+1 WHERE phone=? AND browser=? AND purpose=?',(phone,browser,purpose))
        raise Problem('Incorrect verification code / 验证码不正确。')
    with con:
        con.execute('DELETE FROM verification_codes WHERE phone=? AND browser=? AND purpose=?',(phone,browser,purpose))


def dispatch(env,start):
    path=env.get('PATH_INFO','/')
    if path in ('/static/style.css','/static/app.js'):
        content=(core.ROOT/path.lstrip('/')).read_bytes()
        start('200 OK',[('Content-Type','text/css' if path.endswith('.css') else 'application/javascript'),('Cache-Control','no-cache')])
        return [content]
    cookies=SimpleCookie()
    try: cookies.load(env.get('HTTP_COOKIE',''))
    except CookieError: pass
    token=cookies['session'].value if 'session' in cookies else ''
    browser=cookies['browser'].value if 'browser' in cookies else ''
    if not re.fullmatch('[a-f0-9]{48}',browser): browser=secrets.token_hex(24)
    csrf=hmac.new(core.CSRF_KEY,(browser+'|'+token).encode(),'sha256').hexdigest()
    query=parse_qs(env.get('QUERY_STRING',''))
    headers=[('Content-Type','text/html; charset=utf-8'),('Cache-Control','no-store'),
        ('X-Content-Type-Options','nosniff'),('Referrer-Policy','same-origin'),
        ('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; form-action 'self'; frame-ancestors 'none'"),
        ('Set-Cookie',f'browser={browser}; HttpOnly; SameSite=Lax; Path=/')]
    con=core.connect()
    user=None
    form={}
    def response(body,status=200):
        phrases={200:'OK',303:'See Other',400:'Bad Request',401:'Unauthorized',403:'Forbidden',404:'Not Found',409:'Conflict',413:'Content Too Large',429:'Too Many Requests',500:'Internal Server Error'}
        start(f'{status} {phrases.get(status,"Error")}',headers)
        return [body.encode('utf-8')]
    def redirect(url):
        headers.append(('Location',url)); return response('',303)
    def hidden(): return f'<input type="hidden" name="csrf" value="{csrf}">'
    def button(url,label,kind='',confirm=''):
        ask=f' data-confirm="{e(confirm)}"' if confirm else ''
        return f'<form class="inline-form" method="post" action="{url}"{ask}>{hidden()}<button class="btn {kind}">{label}</button></form>'
    def link(url,label,kind='secondary'): return f'<a class="btn {kind}" href="{url}">{label}</a>'
    def require(role=None):
        if not user: raise Problem('Please log in first / 请先登录。',401)
        if role and user['role']!=role: raise Problem('FORBIDDEN: this account does not have this role / 此账号没有该角色权限。',403)
    def badge(status):
        label={'DRAFT':'Draft 草稿','OPEN':'Live 投票中','CLOSED':'Closed 已结束'}[status]
        return f'<span class="badge {status.lower()}">{label}</span>'
    def layout(title,body,section='gallery'):
        name=e(user['name']) if user else 'Guest / 访客'
        role='Manager / 管理者' if user and user['role']=='MANAGER' else 'Voter / 投票者' if user else 'Browse before signing in'
        nav=[('/', '◈','活动广场','gallery')]
        if user and user['role']=='MANAGER': nav.append(('/dashboard','▦','管理工作台','dashboard'))
        if user: nav.append(('/my-votes','✓','我的投票','my-votes'))
        nav_html=''.join(f'<a class="{"active" if key==section else ""}" href="{url}"><span class="nav-icon">{icon}</span>{label}</a>' for url,icon,label,key in nav)
        auth=button('/logout','Log out / 退出','ghost small') if user else link('/login','Log in / 登录','small')
        return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)} · VoteLab</title><link rel="stylesheet" href="/static/style.css"><script defer src="/static/app.js"></script></head><body><aside class="sidebar"><a class="brand" href="/"><span class="brand-mark">V</span>VoteLab<span style="font-size:10px;color:#adc19a">02</span></a><div class="tag">EVERY CHOICE COUNTS</div><div class="nav-label">WORKSPACE / 工作空间</div><nav>{nav_html}</nav><div class="side-bottom"><span class="avatar">{e((user['name'] if user else 'G')[0])}</span>{name}<p>{role}</p><small>COMP3500 · Local preview<br>本地演示 · 不含真实短信服务</small></div></aside><div class="workspace"><header class="topbar"><div class="breadcrumb">Workspace / {e(title)}</div><div class="top-actions"><span class="local-tag">● LOCAL DEMO</span>{auth}</div></header><main>{body}<p class="footnote">VoteLab · COMP3500 Software Engineering · Local prototype / 本地原型，请使用虚构资料。</p></main></div></body></html>'''
    def heading(eyebrow,title,sub='',action=''):
        return f'<div class="page-head"><div><p class="eyebrow">{eyebrow}</p><h1>{title}</h1><p class="sub">{sub}</p></div>{action}</div>'
    def password_field():
        return '<label class="field">Password / 密码<div class="password-wrap"><input id="password" name="password" type="password" minlength="8" maxlength="128" autocomplete="current-password" required><button class="password-toggle" type="button" data-password="password" aria-pressed="false">Show 显示</button></div></label>'
    def auth_page(register=False,role='VOTER',phone='',code=None):
        role=role if role in ('MANAGER','VOTER') else 'VOTER'
        flow='register' if register else 'login'
        title='创建账号' if register else '欢迎回来'
        extra=f'<label class="field">Display name / 名称<input name="name" maxlength="60" required></label>' if register else ''
        notice=f'<div class="notice">LOCAL CODE / 本地模拟验证码<strong class="otp-code">{code}</strong>有效5分钟，仅当前浏览器可用。未发送短信，也不证明手机号归属。</div>' if code else ''
        tabs=''.join(f'<a class="{"active" if role==r else ""}" href="/{flow}?role={r}">{label}</a>' for r,label in [('VOTER','Voter / 投票者'),('MANAGER','Manager / 管理者')])
        phonefield=f'<label class="field">Phone account / 手机号账号<input name="phone" inputmode="numeric" pattern="[0-9]{{8,15}}" value="{e(phone)}" placeholder="输入8–15位数字" required></label>'
        otp=f'<label class="field">Verification code / 验证码<input name="code" inputmode="numeric" pattern="[0-9]{{6}}" maxlength="6" placeholder="6位验证码" required></label>'
        # Registration always checks a code; login supports either password or a one-time code.
        main=f'<form method="post" action="/{flow}">{hidden()}<input type="hidden" name="role" value="{role}">{extra}{phonefield}{password_field()}{otp if register else ""}<button class="btn" style="width:100%">{"Create account / 创建账号" if register else "Sign in / 登录"} →</button></form>'
        codeform=f'<form method="post" action="/auth/code">{hidden()}<input type="hidden" name="purpose" value="{flow}"><input type="hidden" name="role" value="{role}">{phonefield}<button class="btn secondary">获取演示验证码 / Get demo code</button></form>'
        loginotp='' if register else f'<details {"open" if code else ""}><summary>Use a one-time code / 使用验证码登录</summary><form method="post" action="/login">{hidden()}<input type="hidden" name="role" value="{role}"><input type="hidden" name="login_method" value="code">{phonefield}{otp}<button class="btn">Verify and sign in / 验证登录</button></form>{codeform}</details>'
        note='<p class="helper">本地演示允许自行创建管理账号；管理者仅能管理自己创建的活动，不是全站超级管理员。</p>' if role=='MANAGER' else '<p class="helper">投票账号参与活动；不能创建、修改或关闭活动。</p>'
        left='<div class="auth-story"><p class="eyebrow">A PLACE FOR EVERY VOICE</p><h2>Good ideas.<br>Fair choices.<br>Your voice.</h2><p>让每一次选择都有依据。<br>清楚的规则，可核对的结果。</p><div class="auth-feature">01 / Separate roles · 明确角色权限</div><div class="auth-feature">02 / Review before voting · 确认后提交</div><div class="auth-feature">03 / Transparent totals · 清楚的结果汇总</div></div>'
        right=f'<div class="auth-form"><p class="eyebrow">{"JOIN VOTELAB" if register else "WELCOME BACK"}</p><h2>{title}</h2><p class="sub">选择与你账号一致的身份继续。</p><div class="role-tabs">{tabs}</div>{notice}{codeform if register else ""}{main}{loginotp}{note}<div class="divider"></div><a class="helper" href="/{"login" if register else "register"}?role={role}">{"已有账号？登录 →" if register else "还没有账号？注册 →"}</a><p class="helper">演示管理账号 00000001；投票账号 00000002<br>演示密码均为 VoteDemo2026!</p></div>'
        return layout(title,f'<div class="auth-shell">{left}{right}</div>','auth')
    def event_form(event=None,candidates=None):
        title=e(event['title']) if event else ''
        names=e('\n'.join(c['name'] for c in candidates)) if candidates else ''
        method=event['method'] if event else 'SINGLE'
        visibility=event['visibility'] if event else 'PUBLIC'
        duration=event['duration'] if event else 60
        action=f'/e/{event["id"]}/edit' if event else '/create'
        return f'''<div class="stepper"><span class="current"><b>1</b>Configure 配置</span><span><b>2</b>Preview 预览</span><span><b>3</b>Publish 发布</span></div><form class="panel narrow" method="post" action="{action}">{hidden()}<h2>活动设置</h2><p class="helper">发布前可以修改；开启后投票规则锁定。</p><label class="field">Event title / 活动名称<input name="title" maxlength="100" value="{title}" placeholder="例如：校园创意作品评选" required></label><div class="form-grid"><label class="field">Voting method / 投票方式<select name="method"><option value="SINGLE" {"selected" if method=="SINGLE" else ""}>Single choice / 单选</option><option value="SCORE" {"selected" if method=="SCORE" else ""}>Star rating / 0–5星评分</option></select><small>单选选一项；评分需为每个作品评分。</small></label><label class="field">Duration / 持续时间（分钟）<input name="duration" type="number" min="1" max="10080" value="{duration}" required><small>确认发布后开始计时，最多7天。</small></label></div><label class="field">Entries / 候选人或作品，每行一个<textarea name="candidates" rows="6" placeholder="作品 A&#10;作品 B&#10;作品 C" required>{names}</textarea><small>2–20项，名称不能重复。发布后不能更换。</small></label><label class="field">Results visibility / 结果权限<select name="visibility"><option value="PUBLIC" {"selected" if visibility=="PUBLIC" else ""}>Public after publication / 发布后公开</option><option value="PRIVATE" {"selected" if visibility=="PRIVATE" else ""}>Manager only / 仅所属管理者</option></select></label><button class="btn">Save and preview / 保存并预览 →</button></form>'''
    def candidate_cards(event,candidates,interactive,selected=None):
        selected=selected or {}
        output='<div class="candidate-grid">'
        for index,c in enumerate(candidates):
            cid=c['id']; mode=event['method']
            cover=f'<div class="cover tone{index%3}"><span class="cover-type">ENTRY {index+1:02d}</span><span class="glyph">{e(c["name"][0])}</span></div>'
            disabled='' if interactive else 'disabled'
            if mode=='SINGLE':
                check='checked' if selected.get('candidate')==str(cid) else ''
                control=f'<label class="candidate-title"><input type="radio" name="candidate" value="{cid}" {check} {disabled} required>{e(c["name"])}</label><p class="helper">选择此项 / Select this entry</p>'
            else:
                control=f'<div class="candidate-title">{e(c["name"])}</div><div class="stars" role="group" aria-label="{e(c["name"])} rating">'
                for score in range(6):
                    check='checked' if selected.get('score_'+str(cid))==str(score) else ''
                    label='0 分' if score==0 else '★'
                    control+=f'<label class="star-choice {"star-zero" if score==0 else ""}"><input type="radio" name="score_{cid}" value="{score}" {check} {disabled} required aria-label="{score}分">{label}<span>{score if score else "Zero"}</span></label>'
                control+='</div><div class="selected-note">请选择分数 · 未选不等于零分</div>'
            output+=f'<article class="candidate">{cover}<div class="candidate-content">{control}</div></article>'
        return output+'</div>'
    try:
        with con: core.refresh(con)
        user=con.execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=? AND s.expires>?',(token,now())).fetchone()
        if env['REQUEST_METHOD']=='POST':
            try: size=int(env.get('CONTENT_LENGTH') or 0)
            except ValueError: raise Problem('Invalid request length.')
            if not 0<=size<=32768: raise Problem('Request too large.',413)
            try: form=parse_qs(env['wsgi.input'].read(size).decode('utf-8'),keep_blank_values=True)
            except UnicodeError: raise Problem('Invalid text encoding.')
            if not hmac.compare_digest(scalar(form,'csrf'),csrf): raise Problem('Form expired. Reload and retry / 表单过期，请刷新后重试。',403)
            if path=='/auth/code':
                phone,purpose=scalar(form,'phone').strip(),scalar(form,'purpose')
                code=issue_code(con,phone,browser,purpose)
                return response(auth_page(purpose=='register',scalar(form,'role','VOTER'),phone,code))
            if path in ('/register','/login'):
                phone,password=scalar(form,'phone').strip(),scalar(form,'password')
                role=scalar(form,'role','VOTER')
                if role not in ('MANAGER','VOTER') or not re.fullmatch(r'[0-9]{8,15}',phone): raise Problem('Invalid phone account or role.')
                if path=='/register':
                    name=scalar(form,'name').strip()
                    if not 1<=len(name)<=60 or not 8<=len(password)<=128: raise Problem('Name: 1–60 characters. Password: 8–128 characters.')
                    consume_code(con,phone,browser,'register',scalar(form,'code'))
                    salt=secrets.token_hex(16)
                    with con:
                        uid=con.execute('INSERT INTO users(phone,name,salt,password_hash,role) VALUES(?,?,?,?,?)',(phone,name,salt,core.password_hash(password,salt),role)).lastrowid
                else:
                    row=con.execute('SELECT * FROM users WHERE phone=?',(phone,)).fetchone()
                    if scalar(form,'login_method')=='code':
                        consume_code(con,phone,browser,'login',scalar(form,'code'))
                        valid=bool(row)
                    else:
                        valid=bool(row and 8<=len(password)<=128 and hmac.compare_digest(row['password_hash'],core.password_hash(password,row['salt'])))
                    if not valid: raise Problem('Incorrect account, password or code / 账号、密码或验证码不正确。',401)
                    if row['role']!=role: raise Problem('This account uses the other role. Switch login tab / 账号角色不匹配，请切换登录身份。',403)
                    uid=row['id']
                newtoken=secrets.token_hex(32)
                with con: con.execute('INSERT INTO sessions VALUES(?,?,?)',(newtoken,uid,now()+7200))
                headers.append(('Set-Cookie',f'session={newtoken}; HttpOnly; SameSite=Lax; Path=/; Max-Age=7200'))
                return redirect('/dashboard' if role=='MANAGER' else '/')
            require()
            if path=='/logout':
                with con: con.execute('DELETE FROM sessions WHERE token=?',(token,))
                headers.append(('Set-Cookie','session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0'))
                return redirect('/login')
            if path=='/create':
                require('MANAGER')
                with con: eid=core.create_event(con,user['id'],form)
                return redirect(f'/e/{eid}/preview')
            match=re.fullmatch(r'/e/(\d+)/(open|close|publish|vote|confirm|edit)',path)
            if not match: raise Problem('Not found.',404)
            eid,action=int(match[1]),match[2]
            event=con.execute('SELECT * FROM elections WHERE id=?',(eid,)).fetchone()
            if not event: raise Problem('Not found.',404)
            candidates=con.execute('SELECT * FROM candidates WHERE election_id=? ORDER BY id',(eid,)).fetchall()
            if action in ('vote','confirm'):
                require('VOTER')
                if event['status']!='OPEN' or event['ends_at']<=time.time(): raise Problem('ELECTION_CLOSED: voting is not open.')
                if action=='vote':
                    core.submit_ballot(con,eid,user['id'],form)
                    return redirect(f'/e/{eid}')
                # The review page validates first but does not save a ballot.
                selected={}
                for c in candidates:
                    if event['method']=='SCORE':
                        value=scalar(form,'score_'+str(c['id']))
                        if value not in ('0','1','2','3','4','5'): raise Problem('INVALID_FORMAT: rate every entry from 0 to 5 / 请完成所有评分。')
                        selected['score_'+str(c['id'])]=value
                if event['method']=='SINGLE':
                    value=scalar(form,'candidate')
                    if value not in [str(c['id']) for c in candidates]: raise Problem('INVALID_FORMAT: select one entry.')
                    selected['candidate']=value
                rows=''.join(f'<div class="summary-row"><span>{e(c["name"])}</span><strong>{selected.get("score_"+str(c["id"]),"Selected / 已选择")}</strong></div>' for c in candidates if event['method']=='SCORE' or selected['candidate']==str(c['id']))
                fields=''.join(f'<input type="hidden" name="{e(k)}" value="{e(v)}">' for k,v in selected.items())
                content=heading('REVIEW YOUR BALLOT','确认你的选择','还没有提交。请核对后确认，成功保存后不能修改。')
                content+=f'<div class="panel narrow"><h2>{e(event["title"])}</h2>{rows}<form method="post" action="/e/{eid}/vote">{hidden()}{fields}<div class="button-row"><button class="btn">Confirm and submit / 确认提交</button><a class="btn secondary" href="/e/{eid}">返回重选 / Choose again</a></div></form><p class="helper">最终提交时会再次检查截止时间和重复投票。</p></div>'
                return response(layout('Confirm ballot',content))
            require('MANAGER')
            with con:
                con.execute('BEGIN IMMEDIATE'); core.refresh(con)
                event=con.execute('SELECT * FROM elections WHERE id=?',(eid,)).fetchone()
                if event['creator_id']!=user['id']: raise Problem('FORBIDDEN: only the event owner can manage it.',403)
                expected={'open':'DRAFT','edit':'DRAFT','close':'OPEN','publish':'CLOSED'}[action]
                if event['status']!=expected: raise Problem('Rules are locked in this state / 当前状态不能执行此操作。',409)
                if action=='edit':
                    # Reuse creation validation, then move the validated settings atomically.
                    tempid=core.create_event(con,user['id'],form)
                    temp=con.execute('SELECT * FROM elections WHERE id=?',(tempid,)).fetchone()
                    con.execute('UPDATE elections SET title=?,method=?,visibility=?,duration=? WHERE id=?',(temp['title'],temp['method'],temp['visibility'],temp['duration'],eid))
                    con.execute('DELETE FROM candidates WHERE election_id=?',(eid,))
                    con.execute('UPDATE candidates SET election_id=? WHERE election_id=?',(eid,tempid))
                    con.execute('DELETE FROM rounds WHERE election_id=?',(tempid,)); con.execute('DELETE FROM elections WHERE id=?',(tempid,))
                elif action=='open': con.execute("UPDATE elections SET status='OPEN',ends_at=? WHERE id=?",(now()+event['duration']*60,eid))
                elif action=='close': con.execute("UPDATE elections SET status='CLOSED' WHERE id=?",(eid,))
                else: con.execute('UPDATE elections SET published=1 WHERE id=?',(eid,))
                con.execute('INSERT INTO audit(election_id,actor_id,action,created) VALUES(?,?,?,?)',(eid,user['id'],action,now()))
            return redirect(f'/e/{eid}/preview' if action=='edit' else f'/e/{eid}')

        if env['REQUEST_METHOD']!='GET': raise Problem('Unsupported method.')
        if path in ('/login','/register'):
            return response(auth_page(path=='/register',scalar(query,'role','VOTER')))
        if path=='/create':
            require('MANAGER')
            return response(layout('Create event',heading('PROGRAM SETUP','创建一场新活动','先明确规则，再邀请大家参与。')+event_form(),'dashboard'))
        if path in ('/','/dashboard','/my-votes'):
            if path=='/dashboard': require('MANAGER')
            if path=='/my-votes': require()
            if path=='/dashboard': rows=con.execute('SELECT * FROM elections WHERE creator_id=? ORDER BY id DESC',(user['id'],)).fetchall()
            elif path=='/my-votes': rows=con.execute('SELECT e.* FROM elections e JOIN ballots b ON b.election_id=e.id WHERE b.user_id=? ORDER BY b.id DESC',(user['id'],)).fetchall()
            else: rows=con.execute("SELECT * FROM elections WHERE status<>'DRAFT' ORDER BY status='OPEN' DESC,id DESC").fetchall()
            section='dashboard' if path=='/dashboard' else 'my-votes' if path=='/my-votes' else 'gallery'
            manager=bool(user and user['role']=='MANAGER')
            title={'gallery':'发现值得支持的想法','dashboard':'管理你的投票活动','my-votes':'你的选择，已被记录'}[section]
            action=link('/create','＋ Create event / 创建活动','') if manager else link('/login?role=VOTER','参与投票 →','') if not user else ''
            content=heading('VOTELAB / COMMUNITY CHOICE',title,'从浏览作品，到认真选择。每一张票，都有明确的规则。',action)
            if section=='gallery':
                content+='<section class="hero"><div class="hero-copy"><p class="eyebrow">MAKE YOUR VOICE COUNT</p><h2>好想法，值得被看见。<br>把选择交给每一个人。</h2><p>探索正在进行的评选，了解作品，再用单选或星星评分表达你的支持。</p><span class="helper">01 浏览作品　02 登录参与　03 确认提交</span></div><div class="hero-art"><div class="hero-symbol">✦</div></div></section>'
            total=len(rows); live=sum(r['status']=='OPEN' for r in rows)
            draft=sum(r['status']=='DRAFT' for r in rows)
            count=con.execute('SELECT COUNT(*) FROM ballots b JOIN elections e ON e.id=b.election_id'+(' WHERE e.creator_id=?' if section=='dashboard' else ' WHERE b.user_id=?' if section=='my-votes' else ''),((user['id'],) if section in ('dashboard','my-votes') else ())).fetchone()[0]
            content+=f'<div class="stats"><div class="stat"><label>{"My programs / 我的活动" if manager and section=="dashboard" else "Programs / 活动数量"}</label><strong>{total:02d}</strong></div><div class="stat"><label>Live now / 正在进行</label><strong>{live:02d}</strong><span>{draft} drafts / 草稿</span></div><div class="stat"><label>Submitted ballots / 已提交选票</label><strong>{count:02d}</strong></div></div>'
            selected=scalar(query,'status','ALL'); selected=selected if selected in ('ALL','OPEN','CLOSED','DRAFT') else 'ALL'
            tabs=''.join(f'<a class="{"active" if selected==s else ""}" href="{path}?status={s}">{label}</a>' for s,label in [('ALL','All / 全部'),('OPEN','Live / 进行中'),('CLOSED','Closed / 已结束')]+([('DRAFT','Drafts / 草稿')] if section=='dashboard' else []))
            content+=f'<div class="toolbar"><div class="tabs">{tabs}</div><input class="search" data-search aria-label="搜索活动" placeholder="Search programs / 搜索活动"></div><div class="grid">'
            shown=0
            for index,row in enumerate(rows):
                if selected!='ALL' and row['status']!=selected: continue
                shown+=1
                num=con.execute('SELECT COUNT(*) FROM candidates WHERE election_id=?',(row['id'],)).fetchone()[0]
                votes=con.execute('SELECT COUNT(*) FROM ballots WHERE election_id=?',(row['id'],)).fetchone()[0]
                method='Single choice / 单选' if row['method']=='SINGLE' else 'Star rating / 星评分'
                glyph='◉' if row['method']=='SINGLE' else '✦'
                label='管理活动' if section=='dashboard' else '查看活动'
                if section=='my-votes': label='查看已投活动'
                content+=f'<article class="event-card" data-title="{e(row["title"])}"><a href="/e/{row["id"]}"><div class="cover tone{index%3}"><span class="cover-type">VOTELAB · PROGRAM {row["id"]:03d}</span><span class="glyph">{glyph}</span></div><div class="card-body"><div class="card-top">{badge(row["status"])}<span>{"PRIVATE RESULTS" if row["visibility"]=="PRIVATE" else "PUBLIC RESULTS"}</span></div><h3>{e(row["title"])}</h3><p class="helper">{method}</p><div class="card-meta"><span>{num} entries / 作品</span><span>{votes} ballots / 选票</span></div><div class="card-footer"><span>{label} →</span><span>#{row["id"]:03d}</span></div></div></a></article>'
            content+='</div><div data-no-matches class="empty" hidden>没有匹配的活动，请换个关键词。</div>'
            if not shown: content+='<div class="empty"><h2>这里还没有活动</h2><p>试试其他筛选，或创建一场新的评选。</p></div>'
            return response(layout(title,content,section))
        match=re.fullmatch(r'/e/(\d+)(/preview|/results|/edit)?',path)
        if not match: raise Problem('Not found.',404)
        eid,suffix=int(match[1]),match[2] or ''
        event=con.execute('SELECT * FROM elections WHERE id=?',(eid,)).fetchone()
        if not event: raise Problem('Not found.',404)
        owner=bool(user and user['id']==event['creator_id'] and user['role']=='MANAGER')
        if (event['status']=='DRAFT' or suffix in ('/edit','/preview')) and not owner: raise Problem('FORBIDDEN: only the owner can view drafts.',403)
        candidates=con.execute('SELECT * FROM candidates WHERE election_id=? ORDER BY id',(eid,)).fetchall()
        if suffix=='/edit':
            if event['status']!='DRAFT': raise Problem('Published rules are locked.',409)
            return response(layout('Edit draft',heading('PROGRAM SETUP','编辑活动草稿','修改后请重新预览。')+event_form(event,candidates),'dashboard'))
        count=con.execute('SELECT COUNT(*) FROM ballots WHERE election_id=?',(eid,)).fetchone()[0]
        if suffix=='/results':
            if event['status']!='CLOSED' or not (owner or (event['published'] and event['visibility']=='PUBLIC')): raise Problem('Results are private or awaiting publication / 结果未发布或你没有查看权限。',403)
            results=core.get_results(con,eid)
            content=heading('RESULTS / 汇总结果',e(event['title']),'仅显示汇总数据，不展示投票者与选项的关联。',link(f'/e/{eid}','返回活动'))
            content+=f'<div class="stats"><div class="stat"><label>Valid ballots / 有效选票</label><strong>{count}</strong></div><div class="stat"><label>Entries / 参评项</label><strong>{len(candidates)}</strong></div><div class="stat"><label>Counting / 计票方式</label><strong style="font-size:19px">{"Total scores" if event["method"]=="SCORE" else "Vote counts"}</strong></div></div><section class="panel"><h2>{"评分总分" if event["method"]=="SCORE" else "得票统计"}</h2><p class="helper">按总计降序排列；同值不代表已分配奖项。</p>'
            maximum=max([r['total'] for r in results]+[1])
            for index,r in enumerate(results): content+=f'<div class="result-row"><span>{index+1:02d}</span><strong>{e(r["name"])}</strong><div class="bar-track"><div class="bar" style="width:{r["total"]/maximum*100:.1f}%"></div></div><strong>{r["total"]}</strong></div>'
            content+='</section><div class="notice info">奖项自动分配、平票加赛和PDF导出仍待实现；图中顺序不自动宣布获奖者。</div>'
            return response(layout('Results',content))
        preview=suffix=='/preview' or event['status']=='DRAFT'
        already=bool(user and con.execute('SELECT 1 FROM ballots WHERE election_id=? AND user_id=?',(eid,user['id'])).fetchone())
        can_vote=bool(not preview and user and user['role']=='VOTER' and not already and event['status']=='OPEN')
        method='Single choice / 单选' if event['method']=='SINGLE' else 'Star rating / 0–5评分'
        content=heading('PROGRAM / '+method,e(event['title']),'先了解规则，再做出你的选择。',link('/dashboard' if owner else '/','← 返回'))
        if preview: content+='<div class="notice info">PREVIEW / 发布前预览：不会提交选票，也不会启动活动。可返回编辑，确认后再开启。</div><div class="stepper"><span><b>1</b>Configure 配置</span><span class="current"><b>2</b>Preview 预览</span><span><b>3</b>Publish 发布</span></div>'
        if already: content+='<div class="notice success">✓ SUCCESS / 投票已成功保存。本轮无需再次提交。ALREADY_VOTED</div>'
        content+='<div class="detail-layout"><section>'
        saved={}
        if already:
            own_choices=con.execute('SELECT c.candidate_id,c.score FROM choices c JOIN ballots b ON b.id=c.ballot_id WHERE b.election_id=? AND b.user_id=?',(eid,user['id'])).fetchall()
            if event['method']=='SINGLE' and own_choices: saved['candidate']=str(own_choices[0]['candidate_id'])
            else: saved={'score_'+str(c['candidate_id']):str(c['score']) for c in own_choices}
        content+=f'<form method="post" action="/e/{eid}/confirm">{hidden()}{candidate_cards(event,candidates,can_vote,saved)}'
        if can_vote: content+='<div class="sticky-actions"><div><strong>Ready to vote? / 准备好了吗？</strong><br><small>先核对，再提交；成功后不能修改。</small></div><button class="btn">Review ballot / 核对选票 →</button></div>'
        content+='</form></section><aside class="rule-panel"><div class="panel"><p class="eyebrow">PROGRAM DETAILS</p><h2>投票规则</h2>'+badge(event['status'])+f'<ul class="rule-list"><li>方式 / {method}</li><li>名额 / 每人每轮一张选票</li><li>截止 / {stamp(event["ends_at"])}</li><li>参与 / {count} 张已提交选票</li><li>结果 / {"发布后公开" if event["visibility"]=="PUBLIC" else "仅所属管理者"}</li><li>{"每位作品必须评0–5整数分，0分有效。" if event["method"]=="SCORE" else "只能选择一项。"}</li></ul>'
        if not user: content+=link('/login?role=VOTER','登录参与投票 →','')
        elif user['role']=='MANAGER': content+='<p class="helper">当前为管理账号。请使用投票账号参与投票。</p>'
        if owner and event['status']=='DRAFT': content+='<div class="button-row">'+link(f'/e/{eid}/edit','返回编辑')+button(f'/e/{eid}/open','Publish / 发布开启')+'</div>'
        if owner and event['status']=='OPEN': content+=button(f'/e/{eid}/close','Close voting / 关闭投票','danger','确定关闭？关闭后不再接受新票。')
        if owner and event['status']=='CLOSED' and not event['published']: content+=button(f'/e/{eid}/publish','Publish results / 发布结果')
        if event['status']=='CLOSED':
            if owner or (event['published'] and event['visibility']=='PUBLIC'): content+=link(f'/e/{eid}/results','View results / 查看结果','')
            else: content+='<p class="helper">等待结果发布，或结果仅限所属管理者查看。</p>'
        content+='</div></aside></div>'
        return response(layout('Program details',content,'dashboard' if owner else 'gallery'))
    except Problem as err:
        back='/login' if err.status==401 else '/'
        body=heading('PLEASE CHECK','这一步还没有完成',e(err.message))+f'<div class="panel narrow"><p>没有确认成功时，请先查看“我的投票”，不要重复提交。</p><div class="button-row">{link(back,"返回 / Go back")}{link("/my-votes","检查我的投票")}</div></div>'
        return response(layout('Action not completed',body),err.status)
    except sqlite3.IntegrityError:
        return response(layout('Not saved',heading('DATA CHECK','数据没有保存','账号已存在或数据发生冲突。请核对提交状态。')),409)
    except sqlite3.Error:
        return response(layout('Save failed',heading('SAVE FAILED','暂时无法保存','未确认成功，请先检查我的投票再重试。')),500)
    finally:
        con.close()
