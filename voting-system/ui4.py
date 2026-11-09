"""Version four views, retaining the existing visual design."""
from ui3 import View as Base
from app import e
from voting_rules import METHODS


class View(Base):
    def page(self,title,body,section='gallery'):
        page=super().page(title,body,section)
        return page.replace('<script defer src="/static/app.js"></script>','<script defer src="/static/app.js"></script><script defer src="/static/v4.js"></script>').replace('VoteLab<small>03</small>','VoteLab<small>04</small>')

    def method(self,event):
        return self.t(*METHODS[event['method']])

    def event_form(self,event=None,candidates=None,template='custom'):
        body=super().event_form(event,candidates,template)
        start=body.index('<select name="method">'); end=body.index('</select>',start)+len('</select>')
        mode=event['method'] if event else 'SCORE' if template=='photo' else 'SINGLE'
        options=''.join(f'<option value="{key}" {"selected" if key==mode else ""}>{self.t(*labels)}</option>' for key,labels in METHODS.items())
        body=body[:start]+f'<select name="method">{options}</select>'+body[end:]
        limit=event['max_choices'] if event else 1
        extra=f'''<label class="field" data-choice-limit>{self.t('每人最多选几项（单／多选）','Maximum selections (single / multiple choice)')}<input type="number" name="max_choices" min="1" max="20" value="{limit}" required><small>{self.t('1为单选；3表示可选1～3个不同作品，每个作品加1票。','1 means single choice; 3 allows 1–3 different entries, one vote per entry.')}</small></label>
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
        country=f'<label class="field">{t("国家／地区","Country / region")}<select name="country"><option value="">{t("原有演示账号／已含区号","Legacy demo / full number")}</option><option value="86">中国 +86</option><option value="852">香港 +852</option><option value="853">澳门 +853</option><option value="886">台湾 +886</option><option value="44">UK +44</option><option value="1">US / Canada +1</option><option value="61">Australia +61</option></select></label>'
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
        return self.page(title,self.head(title)+f'<section class="panel narrow">{notice}{form}<div class="button-row">{links}</div><p class="helper">{t("课程演示，验证码显示在页面，不证明手机号归属。请勿使用真实银行或常用密码。","Class demo: codes appear on screen and do not verify phone ownership. Use a fictional password.")}</p></section>')

    def examples(self):
        t=self.t
        examples=[('A',t('城市光影','City light'), '4.50'), ('B',t('校园一角','Campus view'),'4.00'), ('C',t('自然印象','Nature study'),'3.50')]
        cards=''.join(f'<article class="candidate"><div class="cover tone{i}"><span class="cover-type">{t("示意封面","Illustrative cover")}</span><span class="glyph">{letter}</span></div><div class="candidate-content"><strong>{name}</strong><p>{score} / 5 · {t("示意评分","Sample rating")}</p></div></article>' for i,(letter,name,score) in enumerate(examples))
        return f'''<section class="panel demo-example" data-demo-example><span class="badge draft">{t('演示示例','Illustrative example')}</span><h2>{t('校园摄影作品评选','Campus photography competition')}</h2><p>{t('以下作品和评分仅用于说明操作流程。','The entries and scores below illustrate how the system works.')}</p><div class="candidate-grid">{cards}</div><ol><li>{t('创建活动，添加作品并预览。','Create an event, add entries and preview it.')}</li><li>{t('开放投票，参与者核对选择后提交。','Open voting. Voters review their choices before submitting.')}</li><li>{t('关闭活动，再发布和查看结果。','Close the event, then publish and view results.')}</li></ol><details><summary>{t('怎样让多人参加同一场活动？','How can people join the same event?')}</summary><p>{t('大家打开同一个共享网址，可参加同一场活动。本地运行包在每台电脑上各自保存活动和选票。','Use the same shared website address to join an event together. Local packages store separate events and ballots on each computer.')}</p></details></section>'''

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
