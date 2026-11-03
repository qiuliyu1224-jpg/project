"""Localized presentation. User-provided text is escaped, never auto-translated."""
from datetime import datetime
from app import e
from entries import TZ


class View:
    def __init__(self,lang,csrf,user,path='/'):
        self.lang,self.csrf,self.user,self.path=lang,csrf,user,path

    def t(self,zh,en): return zh if self.lang=='zh' else en
    def hidden(self): return f'<input type="hidden" name="csrf" value="{self.csrf}">'
    def link(self,url,label,kind='secondary'): return f'<a class="btn {kind}" href="{url}">{label}</a>'
    def button(self,url,label,kind='',confirm=''):
        ask=f' data-confirm="{e(confirm)}"' if confirm else ''
        return f'<form class="inline-form" method="post" action="{url}"{ask}>{self.hidden()}<button class="btn {kind}">{label}</button></form>'
    def head(self,title,sub='',action=''):
        return f'<div class="page-head"><div><p class="eyebrow">VOTELAB · {self.t("一起选择","COMMUNITY CHOICE")}</p><h1>{title}</h1><p class="sub">{sub}</p></div>{action}</div>'
    def badge(self,event):
        t=self.t; phase='ENTRIES' if event['status']=='DRAFT' and event['submissions_open'] else event['status']
        label={'DRAFT':t('草稿','Draft'),'ENTRIES':t('报名中','Accepting entries'),'OPEN':t('投票中','Voting open'),'CLOSED':t('已结束','Closed')}[phase]
        return f'<span class="badge {"open" if phase in ("ENTRIES","OPEN") else phase.lower()}">{label}</span>'
    def stamp(self,ts): return datetime.fromtimestamp(ts,TZ).strftime('%Y-%m-%d %H:%M')+' (UTC+8)' if ts else self.t('尚未开始','Not started')
    def page(self,title,body,section='gallery'):
        t=self.t; user=self.user
        nav=[('/', '◈',t('活动广场','Explore'),'gallery')]
        if user: nav += [('/dashboard','▦',t('我的活动','My events'),'dashboard'),('/my-entries','▧',t('我的作品','My entries'),'my-entries'),('/my-votes','✓',t('我的投票','My votes'),'my-votes')]
        navhtml=''.join(f'<a class="{"active" if key==section else ""}" href="{url}"><span class="nav-icon">{icon}</span>{label}</a>' for url,icon,label,key in nav)
        auth=self.button('/logout',t('退出','Log out'),'ghost small') if user else self.link('/login',t('登录','Log in'),'small')
        signup='' if user else self.link('/register',t('注册账号','Create account'),'secondary small signup-link')
        language=f'<form method="post" action="/language" class="language-form">{self.hidden()}<input type="hidden" name="next" value="{e(self.path)}"><select name="lang" aria-label="{t("界面语言","Interface language")}" data-language><option value="zh" {"selected" if self.lang=="zh" else ""}>中文</option><option value="en" {"selected" if self.lang=="en" else ""}>English</option></select><button class="language-apply">{t("切换","Apply")}</button></form>'
        name=e(user['name']) if user else t('访客','Guest')
        return f'''<!doctype html><html lang="{'zh-CN' if self.lang=='zh' else 'en'}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)} · VoteLab</title><link rel="stylesheet" href="/static/style.css"><link rel="stylesheet" href="/static/entries.css"><script defer src="/static/app.js"></script></head><body><aside class="sidebar"><a class="brand" href="/"><span class="brand-mark">V</span>VoteLab<small>03</small></a><div class="tag">EVERY CHOICE COUNTS</div><div class="nav-label">{t('工作空间','WORKSPACE')}</div><nav>{navhtml}</nav><div class="side-bottom"><span class="avatar">{e((user['name'] if user else 'G')[0])}</span>{name}<p>{t('一个账号 · 创建 / 参赛 / 投票','One account · create / enter / vote')}</p><small>{t('课程演示 · 验证码为本地模拟','Class demo · codes are locally simulated')}</small></div></aside><div class="workspace"><header class="topbar"><div class="breadcrumb">VoteLab / {e(title)}</div><div class="top-actions">{language}{signup}{auth}</div></header><main>{body}<p class="footnote">{t('软件工程演示，请使用虚构资料。界面语言不会翻译用户内容。','Software engineering demo. Use fictional details. User content is not translated.')}</p></main></div></body></html>'''
    def auth(self,register=False,phone='',name='',code=None):
        t=self.t; flow='register' if register else 'login'; title=t('创建你的账号','Create your account') if register else t('欢迎回来','Welcome back')
        notice=f'<div class="notice">{t("本地模拟验证码","LOCAL DEMO CODE")}<strong class="otp-code">{code}</strong>{t("5分钟有效，仅当前浏览器可用。未发送短信，不证明手机号归属。","Valid for 5 minutes in this browser. No SMS sent; phone ownership is not verified.")}</div>' if code else ''
        nf=f'<label class="field">{t("你的称呼","Display name")}<input name="name" maxlength="60" value="{e(name)}" autocomplete="nickname" required></label>' if register else ''
        form=f'''<form method="post" action="/{flow}">{self.hidden()}<input type="hidden" name="purpose" value="{flow}">{nf}<label class="field">{t('手机号账号','Phone account')}<input name="phone" inputmode="numeric" pattern="[0-9]{{8,15}}" value="{e(phone)}" placeholder="{t('请输入8–15位数字','Enter 8–15 digits')}" autocomplete="tel" required></label><label class="field">{t('验证码','Verification code')}<div class="code-field"><input name="code" inputmode="numeric" pattern="[0-9]{{6}}" maxlength="6" placeholder="{t('6位验证码','6-digit code')}" autocomplete="one-time-code" required><button class="btn secondary" formaction="/auth/code" formnovalidate>{t('获取验证码','Get code')}</button></div></label><button class="btn full-width">{t('注册并继续','Create account') if register else t('验证并登录','Verify and sign in')} →</button></form>'''
        story=f'<div class="auth-story"><p class="eyebrow">{t("让每一次选择都有依据","A PLACE FOR EVERY VOICE")}</p><h2>{t("同一个账号。<br>不同的参与方式。","One account.<br>More ways<br>to participate.")}</h2><p>{t("创建活动、提交自己的作品，也为喜欢的选项投票。","Create events, submit work and vote for your favourites.")}</p><div class="auth-feature">01 / {t("图片、名称与介绍","Images, names and descriptions")}</div><div class="auth-feature">02 / {t("先审核，再进入投票","Reviewed before voting")}</div><div class="auth-feature">03 / {t("明确的反馈与结果","Clear feedback and results")}</div></div>'
        other=self.link('/login',t('已有账号？登录','Already registered? Log in')) if register else self.link('/register',t('没有账号？立即注册','New here? Create an account'),'secondary signup-link')
        right=f'<div class="auth-form"><h2>{title}</h2><p class="sub">{t("只需验证码，无需密码。一个手机号可创建活动、报名或投票。","Sign in with a code, not a password. One phone account can create, enter and vote.")}</p>{notice}{form}<div class="divider"></div>{other}<p class="helper">{t("演示账号00000001或00000002。验证码会在页面显示。","Demo accounts: 00000001 or 00000002. Codes appear on this page.")}</p></div>'
        return self.page(title,f'<div class="auth-shell">{story}{right}</div>','auth')
    def entry_editor(self,row=None,key='0'):
        t=self.t; cid=row['id'] if row else ''
        image=f'<img src="/media/{row["image_id"]}" alt="{e(row["name"])}" class="upload-preview">' if row and row['image_id'] else f'<div class="upload-empty">＋<small>{t("添加图片","Add image")}</small></div>'
        return f'''<section class="entry-editor" data-entry-row><input type="hidden" name="entry_key" value="{key}"><input type="hidden" name="entry_id_{key}" value="{cid}"><div class="entry-row-head"><strong data-entry-number>{t('投票选项','Voting option')}</strong><button class="text-button" type="button" data-remove-entry>{t('移除此项','Remove')}</button></div><div class="entry-fields"><div><label class="image-upload">{image}<input type="file" name="entry_image_{key}" accept="image/jpeg,image/png,image/webp" data-image-input aria-label="{t('上传图片','Upload image')}"><span>{t('上传或更换图片','Upload or replace image')}</span></label><label class="helper"><input type="checkbox" name="remove_image_{key}" value="1">{t('移除原图','Remove saved image')}</label><small class="helper">{t('JPEG / PNG / WebP，单张最多5MB。','JPEG / PNG / WebP, up to 5 MB each.')}</small></div><div><label class="field">{t('名称','Name')}<input name="entry_name_{key}" maxlength="80" value="{e(row['name']) if row else ''}" placeholder="{t('例如：睡觉奶龙','For example: Sleeping dragon')}" required></label><label class="field">{t('介绍（可选）','Description (optional)')}<textarea name="entry_description_{key}" maxlength="1000" rows="3" placeholder="{t('描述特点，最多1000字','Describe the entry in up to 1,000 characters')}">{e(row['description']) if row else ''}</textarea></label></div></div><p class="file-feedback" aria-live="polite"></p></section>'''
    def event_form(self,event=None,candidates=None,template='custom'):
        import time
        t=self.t
        templates={'custom':(t('自由创建','Start from scratch'),t('自定义名称与选项','Set your own title and options'),'SINGLE',0),'photo':(t('图片作品评选','Photo competition'),t('开放报名、审核后评分','Collect entries, review, then score'),'SCORE',1),'choice':(t('大家来选一个','Community choice'),t('图片或候选人单选投票','Choose one image, person or idea'),'SINGLE',0)}
        if template not in templates: template='custom'
        preset=templates[template]; method=event['method'] if event else preset[2]; accepting=event['allow_submissions'] if event else preset[3]
        deadline=(event['planned_end'] if event else None) or int(time.time())+86400
        endtext=datetime.fromtimestamp(deadline,TZ).strftime('%Y-%m-%dT%H:%M')
        owned=[c for c in (candidates or []) if c['submitter_id'] in (None,self.user['id'])]
        rows=''.join(self.entry_editor(c,str(i)) for i,c in enumerate(owned)) if event else '' if accepting else self.entry_editor(key='0')+self.entry_editor(key='1')
        aside=f'<aside class="template-panel panel"><p class="eyebrow">{t("创建向导","CREATE GUIDE")}</p><h3>{t("常用模板","Popular templates")}</h3>'
        if not event:
            for key,item in templates.items(): aside+=f'<a href="/create?template={key}" class="template-choice {"active" if key==template else ""}"><strong>{item[0]}</strong><small>{item[1]}</small></a>'
        else: aside+=f'<p class="helper">{t("参赛者提交的作品，请在审核页处理。","Review participant submissions separately.")}</p>'
        aside+=f'<div class="divider"></div><h3>{t("选项会怎样展示？","How entries appear")}</h3><div class="mini-preview"><div class="mini-image">▧</div><strong>{t("图片 + 名称","Image + name")}</strong><p class="helper">{t("介绍放在图片下方，大家可以先看、比较，再选择或评分。","Descriptions appear below images so voters can compare before choosing or scoring.")}</p></div><p class="helper">{t("模板只预设配置，不会自动生成作品。","Templates only preset settings; they do not generate entries.")}</p></aside>'
        visibility=event['visibility'] if event else 'PUBLIC'; action=f'/e/{event["id"]}/edit' if event else '/create'; title=e(event['title']) if event else ''
        form=f'''<form class="panel" method="post" enctype="multipart/form-data" action="{action}" data-event-form>{self.hidden()}<h2>{t('活动设置','Event settings')}</h2><label class="field">{t('活动名称','Event title')}<input name="title" maxlength="100" value="{title}" placeholder="{t('例如：选出最可爱的奶龙','For example: Choose the cutest dragon')}" required></label><div class="form-grid"><label class="field">{t('投票方式','Voting method')}<select name="method"><option value="SINGLE" {'selected' if method=='SINGLE' else ''}>{t('单选','Single choice')}</option><option value="SCORE" {'selected' if method=='SCORE' else ''}>{t('0–5星评分','0–5 star rating')}</option></select></label><label class="field">{t('投票截止至','Voting ends at')}<input name="deadline" type="datetime-local" value="{endtext}" required><small>{t('北京时间UTC+8。当前演示须设在1分钟后、30天内；上限可调整。','Beijing time, UTC+8. Demo limit: more than 1 minute ahead, within 30 days; configurable.')}</small></label></div><label class="field">{t('结果权限','Result visibility')}<select name="visibility"><option value="PUBLIC" {'selected' if visibility=='PUBLIC' else ''}>{t('发布后公开','Public after publication')}</option><option value="PRIVATE" {'selected' if visibility=='PRIVATE' else ''}>{t('仅活动创建者','Creator only')}</option></select></label><label class="check-row"><input type="checkbox" name="submissions_open" value="1" {'checked' if accepting else ''}> {t('允许参赛者报名提交作品','Allow participants to submit entries')}</label><p class="helper">{t('先保存、预览，再明确开放报名。审核后开票，开票后名单锁定。','Save and preview first, then explicitly open applications. Review submissions before voting; voting locks the list.')}</p><div class="divider"></div><h2>{t('添加投票选项','Add voting options')}</h2><p class="helper">{t('逐项填写图片、名称和介绍。普通选项图片可选；参赛者报名图片必填。','Add images, names and descriptions individually. Creator images are optional; participant images are required.')}</p><div data-entry-list>{rows}</div><button class="btn secondary" type="button" data-add-entry>＋ {t('添加一个选项','Add another option')}</button><p class="helper">{t('最多20项且不重名。报名活动可先不添加选项，开票前至少需2项通过。','Up to 20 distinct names. Application events may start empty; voting needs at least 2 approved entries.')}</p><template id="entry-template">{self.entry_editor(key='__KEY__')}</template><div class="sticky-actions"><small>{t('总上传最多24MB，保存后先预览。','Total upload limit: 24 MB. Preview before publishing.')}</small><button class="btn">{t('保存并预览','Save and preview')} →</button></div></form>'''
        return f'<p class="helper">{t("填写设置 → 预览检查 → 开放报名或开始投票","Configure → preview → open applications or start voting")}</p><div class="builder-layout">{form}{aside}</div>'
    def cards(self,event,candidates,interactive,selected=None):
        t=self.t; selected=selected or {}; out='<div class="candidate-grid">'
        for index,c in enumerate(candidates):
            cid=c['id']; disabled='' if interactive else 'disabled'
            cover=f'<img class="entry-photo" src="/media/{c["image_id"]}" alt="{e(c["name"])}" loading="lazy">' if c['image_id'] else f'<div class="cover tone{index%3}"><span class="cover-type">{t("选项","OPTION")} {index+1:02d}</span><span class="glyph">{e(c["name"][0])}</span></div>'
            if event['method']=='SINGLE':
                checked='checked' if selected.get('candidate')==str(cid) else ''
                control=f'<label class="candidate-title"><input type="radio" name="candidate" value="{cid}" {checked} {disabled} required> {e(c["name"])}</label>'
            else:
                control=f'<div class="candidate-title">{e(c["name"])}</div><div class="stars" role="group" aria-label="{e(c["name"])} {t("评分","rating")}">'
                for score in range(6):
                    checked='checked' if selected.get('score_'+str(cid))==str(score) else ''; label=t('0分','Zero') if not score else '★'
                    control+=f'<label class="star-choice {"star-zero" if not score else ""}"><input type="radio" name="score_{cid}" value="{score}" {checked} {disabled} required aria-label="{score}">{label}<span>{score}</span></label>'
                control+=f'</div><div class="selected-note">{t("请选择分数，未选不等于零分","Choose a score; unanswered is not zero")}</div>'
            out+=f'<article class="candidate">{cover}<div class="candidate-content">{control}<p class="entry-description">{e(c["description"])}</p></div></article>'
        return out+'</div>'
