"""Version four views, retaining the existing visual design."""
from ui3 import View as Base
from app import e, VERSION
from voting_rules import METHODS
from ui_icons import icon
import re


class View(Base):
    def page(self,title,body,section='gallery'):
        body=body.replace('<div class="hero-symbol">✦</div>','<img class="hero-vote" src="/static/assets/hero-vote.webp" alt="" aria-hidden="true">')
        guide=f'<button type="button" class="guide-open" data-guide-open>{icon("book")}{self.t("操作指南","Quick guide")}</button>'
        if self.path=='/':
            body+=f'<div class="guide-entry">{icon("book")}<span>{self.t("第一次使用？","First time here?")}</span><button type="button" class="text-button" data-guide-open>{self.t("5步操作指南","5-step guide")} →</button></div>'
        page=super().page(title,body,section)
        if getattr(self,'local_operator',False):
            page=page.replace('</nav>',f'<a href="/_votelab/tools"><span class="nav-icon">⚙</span>{self.t("本机数据与升级","Local data & upgrades")}</a></nav>',1)
        navicons={'/':'explore','/dashboard':'calendar','/my-entries':'image','/my-votes':'check','/_votelab/tools':'database'}
        page=re.sub(r'(<a[^>]+href="([^"]+)"[^>]*><span class="nav-icon">).*?(</span>)',lambda m:m[1]+icon(navicons.get(m[2],'explore'))+m[3],page)
        page=page.replace('<span class="brand-mark">V</span>',f'<span class="brand-mark">{icon("ballot")}</span>')
        page=page.replace('<div class="top-actions">','<div class="top-actions">'+guide,1)
        auth_page=self.path in ('/login','/register','/reset')
        page=page.replace('<body>',f'<body data-authenticated="{int(bool(self.user))}" data-auth-page="{int(auth_page)}" data-guide-user="{self.user["id"] if self.user else "guest"}">')
        if getattr(self,'guide_welcome',False) and self.user:
            hint=f'<aside class="guide-hint" data-guide-hint role="status"><strong>{self.t("第一次使用？操作指南在这里。","First time here? Your quick guide is here.")}</strong><p>{self.t("投票、创建活动、报名作品，随时查看，不必实际提交。","Learn to vote, create events or submit entries. No real submission is needed.")}</p><button class="text-button" type="button" data-guide-open>{self.t("查看指南","View guide")}</button><button class="text-button" type="button" data-dismiss-hint>{self.t("知道了","Got it")}</button></aside>'
            page=page.replace('</header><main>','</header>'+hint+'<main>',1)
        page=page.replace('</head>','<link rel="stylesheet" href="/static/refined.css"></head>')
        return page.replace('<script defer src="/static/app.js"></script>','<script defer src="/static/app.js"></script><script defer src="/static/v4.js"></script><script defer src="/static/experience.js"></script><script defer src="/static/guide.js"></script><script defer src="/static/demo.js"></script>').replace('VoteLab<small>03</small>',f'VoteLab<small>{VERSION}</small>')

    def method(self,event):
        return self.t(*METHODS[event['method']])

    def event_form(self,event=None,candidates=None,template='custom'):
        body=super().event_form(event,candidates,template)
        start=body.index('<select name="method">'); end=body.index('</select>',start)+len('</select>')
        mode=event['method'] if event else 'SCORE' if template=='photo' else 'SINGLE'
        options=''.join(f'<option value="{key}" {"selected" if key==mode else ""}>{self.t(*labels)}</option>' for key,labels in METHODS.items())
        body=body[:start]+f'<select name="method">{options}</select>'+body[end:]
        limit=event['max_choices'] if event else 1
        extra=f'''<label class="field" data-choice-limit {"hidden" if mode!='SINGLE' else ''}>{self.t('每人最多选几项（单／多选）','Maximum selections (single / multiple choice)')}<input type="number" name="max_choices" min="1" max="20" value="{limit}" {"required" if mode=='SINGLE' else 'disabled'}><small>{self.t('1为单选；3表示可选1～3个不同作品，每个作品加1票。','1 means single choice; 3 allows 1–3 different entries, one vote per entry.')}</small></label>
        <p class="helper" data-majority-note {"hidden" if mode!='MAJORITY' else ''}>{self.t('多数决选每人每轮选1个作品；第一轮无人过半时，前两名进入第二轮重新投票。','Majority runoff allows one entry per voter per round. If nobody has more than half in round one, voters choose again between the top two.')}</p>
        <label class="field">{self.t('活动邀请码（可选）','Event invitation code (optional)')}<input name="invite_code" minlength="4" maxlength="64" autocomplete="off"><small>{self.t('限制参与者时设置。编辑时留空保留原码；邀请码不等于学校身份验证。','Set a code to restrict access. Leave blank when editing to retain it. This does not verify school membership.')}</small></label>'''
        if event: extra+=f'<label class="check-row"><input type="checkbox" name="remove_invite" value="1">{self.t("取消邀请码限制","Remove invitation-code restriction")}</label>'
        extra+=f'<label class="field">{self.t("活动标签（可选）","Event tags (optional)")}<input name="tags" maxlength="120" value="{e(event["tags"]) if event else ""}" placeholder="{self.t("例如：校园、摄影、创意","For example: campus, photography, creativity")}"></label>'
        body=body.replace('<label class="field">'+self.t('结果权限','Result visibility'),extra+'<label class="field">'+self.t('结果权限','Result visibility'))
        body=body.replace(self.t('逐项填写图片、名称和介绍。普通选项图片可选；参赛者报名图片必填。','Add images, names and descriptions individually. Creator images are optional; participant images are required.'),self.t('逐项填写名称和介绍，图片可选。','Add a name and description for each entry. Images are optional.'))
        if event and event['paused']:
            body=body.replace(f'action="/e/{event["id"]}/edit"',f'action="/e/{event["id"]}/revision"')
            body=body.replace('<h2>'+self.t('活动设置','Event settings')+'</h2>',f'<h2>{self.t("暂停期间修改","Edit while paused")}</h2><label class="field">{self.t("修改公告（必填）","Change announcement (required)")}<textarea name="announcement" required maxlength="1000"></textarea></label>')
            body=body.replace(self.t('保存并预览','Save and preview'),self.t('保存修改并预览','Save changes and preview'))
            participant_controls=''
            for candidate in candidates or []:
                if candidate['submitter_id'] not in (None,self.user['id']):
                    participant_controls+=f'<label class="check-row"><input type="checkbox" name="exclude_candidate" value="{candidate["id"]}">{self.t("移出本轮：","Remove from next round: ")}{e(candidate["name"])}</label>'
            if participant_controls:
                body=body.replace('<div data-entry-list>',f'<section><h3>{self.t("参赛者作品名单","Participant entries")}</h3><p>{self.t("可移出，但不能代替参赛者改写内容。移出后新开轮次，旧票保留。","You may remove an entry but cannot rewrite it on behalf of its author. Removal starts a fresh round; previous ballots remain in history.")}</p>{participant_controls}</section><div data-entry-list>')
        return body

    def auth(self,register=False,phone='',name='',code=None,reset=False):
        t=self.t; flow='reset' if reset else 'register' if register else 'login'
        title=t('重置密码','Reset password') if reset else t('创建账号','Create account') if register else t('登录','Log in')
        notice=f'<div class="notice"><strong>{t("演示验证码（未发送短信）","DEMO CODE — no SMS sent")}</strong><strong class="otp-code">{e(code)}</strong>{t("5分钟有效，仅当前浏览器可用。","Valid for 5 minutes in this browser.")}</div>' if code else ''
        purpose='reset' if reset else 'register'
        country=f'<label class="field">{t("国家／地区","Country / region")}<select name="country"><option value="">{t("原有演示账号／已含区号","Legacy demo / full number")}</option><option value="86">{t("中国","China")} +86</option><option value="852">{t("香港","Hong Kong")} +852</option><option value="853">{t("澳门","Macao")} +853</option><option value="886">{t("台湾","Taiwan")} +886</option><option value="44">UK +44</option><option value="1">US / Canada +1</option><option value="61">Australia +61</option></select></label>'
        fields=(f'<label class="field">{t("称呼","Display name")}<input name="name" value="{e(name)}" required maxlength="60"></label>' if register else '')
        fields+=country+f'<label class="field">{t("手机号","Phone number")}<input name="phone" inputmode="tel" value="{e(phone)}" required autocomplete="tel"><small>{t("选择区号后填写本地号码；旧演示账号00000001／00000002选择第一项。","Select the country code and enter the local number. For demo accounts 00000001 / 00000002 choose the first option.")}</small></label>'
        password_help=t('密码长度为8～128个字符。','Use 8–128 characters.')
        fields+=f'<div class="field"><label for="account-password">{t("新密码" if reset else "密码","New password" if reset else "Password")}</label><input id="account-password" type="password" name="password" minlength="8" maxlength="128" required aria-describedby="password-help" autocomplete="{"current-password" if flow=="login" else "new-password"}"><small id="password-help">{password_help}</small></div>'
        if register or reset:
            fields+=f'<label class="field">{t("确认密码","Confirm password")}<input type="password" name="password_confirm" minlength="8" maxlength="128" required autocomplete="new-password"><small>{t("请再次输入相同密码。","Enter the same password again.")}</small></label>'
        fields+=f'<label class="password-visibility"><input type="checkbox" data-show-password> {t("显示密码（可选）","Show password (optional)")}</label>'
        if register or reset:
            fields+=f'<input type="hidden" name="purpose" value="{purpose}"><div class="field"><label for="account-code">{t("验证码","Verification code")}</label><div class="code-field"><input id="account-code" name="code" inputmode="numeric" pattern="[0-9]{{6}}" required maxlength="6" autocomplete="one-time-code"><button class="btn secondary" formaction="/auth/code" formnovalidate data-get-code>{t("获取验证码","Get code")}</button></div></div><div class="notice" data-code-status role="status" aria-live="polite" hidden></div>'
        form=f'<form method="post" action="/{flow}">{self.hidden()}{fields}<button class="btn full-width">{title}</button></form>'
        links=self.link('/login',t('登录','Log in'))+self.link('/register',t('注册账号','Create account'))+self.link('/reset',t('忘记密码／旧账号设置密码','Forgot password / set a legacy account password'))
        story=f'<aside class="auth-intro"><p class="eyebrow">VOTELAB</p><h2>{t("每一次选择，都有依据。","Every choice deserves a reason.")}</h2><p>{t("创建活动、提交作品，也为你支持的想法投票。","Create events, submit work and vote for ideas you support.")}</p><img src="/static/assets/login-vote.webp" alt="" class="login-art" aria-hidden="true"></aside>'
        return self.page(title,f'<div class="auth-layout">{story}<section class="panel auth-panel">'+self.head(title)+f'{notice}{form}<div class="button-row">{links}</div><p class="helper">{t("课程演示，验证码显示在页面，不证明手机号归属。请勿使用真实银行或常用密码。","Class demo: codes appear on screen and do not verify phone ownership. Use a fictional password.")}</p></section></div>')

    def examples(self):
        t=self.t
        examples=[('entries',t('作品评选','Entry evaluation'),t('星级评分','Star rating'),t('对提交的作品进行评价与选择。','Evaluate and compare submitted work.'),'photo','image'),('choice',t('方案投票','Proposal voting'),t('单／多选','Single / multiple choice'),t('就多个备选方案进行投票表决。','Choose between alternative proposals.'),'choice','check'),('projects',t('项目展示','Project showcase'),t('排序投票','Ranked-choice voting'),t('为候选项目排序，表达偏好。','Rank projects to express your preferences.'),'custom','calendar')]
        cards=''
        for key,name,method,desc,template,symbol in examples:
            live=key=='entries'
            label=t('可操作演示','Interactive demo') if live else t('展示示例','Display example')
            detail=t('体验评分、核对、演示提交与结果。','Try rating, review, demo submission and results.') if live else desc
            trigger='data-vote-demo-open' if live else f'data-example-info="{key}"'
            action=t('进入演示体验','Try the interactive demo') if live else t('查看示例说明','View example details')
            cards+=f'<article class="example-card {"example-interactive" if live else ""}"><div class="example-copy"><span class="example-kind">{label}</span><h3>{name}</h3><p class="example-method">{icon(symbol)}{method}</p><p class="helper">{detail}</p></div><img src="/static/assets/example-{key}.webp" alt="{name}" loading="lazy"><button type="button" class="example-action" {trigger}>{action} {icon("arrow")}</button></article>'
        return f'<section class="demo-example" data-demo-example><div class="example-grid">{cards}</div><p class="helper">{t("作品评选可操作；方案投票、项目展示保留为展示示例。演示记录不计入正式活动。本地安装包在每台电脑上各自保存数据。","Entry evaluation is interactive; proposal voting and project showcase are display examples. Demo records never enter real events. Local packages store separate data on each computer.")}</p><noscript><p class="notice">{t("示例体验需要启用 JavaScript；正式活动仍可通过页面链接使用。","Enable JavaScript to try the examples. Real event pages remain available through ordinary links.")}</p></noscript><details class="helper"><summary>{t("本地活动能否跨设备共享？","Can local activities be shared across devices?")}</summary><p>{t("若将来提供共享部署，参与者需打开同一共享网址。当前本地安装包在每台电脑上各自保存数据，不会自动同步。","A shared deployment would require the same shared website address for all participants. Current local packages store separate data on each computer and do not automatically sync.")}</p></details></section>'

    def cards(self,event,candidates,interactive,selected=None):
        t=self.t; selected=selected or {}; out='<div class="candidate-grid">'
        values=selected.get('candidate',[])
        if isinstance(values,str): values=[values]
        for index,c in enumerate(candidates):
            cid=c['id']; disabled='' if interactive else 'disabled'
            cover=f'<div class="image-frame"><img class="entry-photo" src="/media/{c["image_id"]}" alt="{e(c["name"])}" loading="lazy"><span class="image-fallback" hidden>{t("图片暂不可用，仍可阅读作品资料","Image unavailable. Entry details are still available.")}</span></div>' if c['image_id'] else f'<div class="cover tone{index%3}"><span class="cover-type">{t("未添加图片","No image")}</span><span class="glyph">{e(c["name"][0])}</span></div>'
            if event['method'] in ('SINGLE','MAJORITY'):
                kind='checkbox' if event['method']=='SINGLE' and event['max_choices']>1 else 'radio'
                control=f'<label class="candidate-title"><input type="{kind}" name="candidate" value="{cid}" {"checked" if str(cid) in values else ""} {disabled}> {e(c["name"])}</label>'
            elif event['method']=='RCV':
                options=f'<option value="">{t("不排序","Not ranked")}</option>'+''.join(f'<option value="{i}" {"selected" if selected.get("rank_"+str(cid))==str(i) else ""}>{i}</option>' for i in range(1,len(candidates)+1))
                control=f'<strong>{e(c["name"])}</strong><label class="field">{t("偏好名次","Preference rank")}<select name="rank_{cid}" {disabled}>{options}</select></label>'
            else:
                control=f'<strong>{e(c["name"])}</strong><div class="stars">'
                for score in range(6):
                    checked='checked' if selected.get('score_'+str(cid))==str(score) else ''
                    control+=f'<label class="star-choice {"star-zero" if not score else ""}"><input type="radio" name="score_{cid}" value="{score}" {checked} {disabled}>{t("0分","Zero") if not score else "★"}<span>{score}</span></label>'
                if interactive and event['score_optional']: control+=f'<button type="button" class="text-button" data-clear-score>{t("清除评分","Clear")}</button>'
                control+='</div><div class="selected-note">'+t('可以不评；未评不计入平均分。' if event['score_optional'] else '本活动须评全部作品。','You may skip this entry; skipped ratings do not count.' if event['score_optional'] else 'Rate every entry in this legacy event.')+'</div>'
            out+=f'<article class="candidate">{cover}<div class="candidate-content">{control}<p class="entry-description">{e(c["description"])}</p></div></article>'
        return out+'</div>'
