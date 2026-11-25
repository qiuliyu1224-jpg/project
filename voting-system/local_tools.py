"""OS-launch-authorised local tools. Ordinary website accounts cannot open this UI."""
import hmac
import re
import secrets
import sqlite3
import threading
from http.cookies import SimpleCookie, CookieError
from urllib.parse import parse_qs
from pathlib import Path
import storage


class LocalTools:
    def __init__(self, application, data_dir, token, gate, shutdown):
        self.application, self.data_dir, self.token = application, Path(data_dir), token
        self.gate, self.shutdown = gate, shutdown

    def __call__(self, env, start):
        with self.gate:
            cookies = SimpleCookie()
            try: cookies.load(env.get('HTTP_COOKIE', ''))
            except CookieError: pass
            path = env.get('PATH_INFO', '/')
            host = env.get('HTTP_HOST', '')
            same_host = host == '127.0.0.1:' + str(env.get('SERVER_PORT'))
            query = parse_qs(env.get('QUERY_STRING', ''))
            supplied = query.get('local', [''])[0]
            if path == '/' and env.get('REQUEST_METHOD') == 'GET' and supplied:
                if not same_host or not hmac.compare_digest(supplied.encode(), self.token.encode()):
                    start('403 Forbidden', [('Content-Type', 'text/plain')]); return [b'Invalid local launch.']
                start('303 See Other', [('Location', '/?lang='+query['lang'][0] if query.get('lang',[''])[0] in ('en','zh') else '/'), ('Cache-Control', 'no-store'),
                    ('Referrer-Policy', 'no-referrer'),
                    ('Set-Cookie', f'votelab_operator={self.token}; HttpOnly; SameSite=Strict; Path=/')])
                return [b'']
            operator = cookies['votelab_operator'].value if 'votelab_operator' in cookies else ''
            authorised = same_host and hmac.compare_digest(operator.encode(), self.token.encode())
            env['votelab.local_operator'] = authorised
            if path != '/_votelab/tools':
                return self.application(env,start)
            if not authorised:
                start('403 Forbidden', [('Content-Type', 'text/plain')])
                return [b'Open VoteLab by double-clicking the local application to manage this computer.']
            return self.tools(env,start,cookies)

    def tools(self, env, start, cookies):
        import app
        import entries
        from ui4 import View
        lang = cookies['lang'].value if 'lang' in cookies else 'en'
        browser = cookies['browser'].value if 'browser' in cookies else ''
        session = cookies['session'].value if 'session' in cookies else ''
        csrf = hmac.new(app.CSRF_KEY,(browser+'|'+session).encode(),'sha256').hexdigest()
        view = View(lang, csrf, None, '/_votelab/tools'); view.local_operator = True
        hidden = f'<input type="hidden" name="csrf" value="{self.token}">'
        t, esc = view.t, app.e
        notice = ''; status = '200 OK'
        if env.get('REQUEST_METHOD') == 'POST':
            try:
                form, files = entries.read_form(env)
                if not hmac.compare_digest(app.scalar(form,'csrf').encode(),self.token.encode()):
                    raise ValueError(t('操作已过期，请重新打开。','Action expired. Reopen this page.'))
                action = app.scalar(form,'action')
                if action == 'backup':
                    backup = storage.backup_database(app.DB)
                    notice = t('备份已保存：','Backup saved: ') + str(backup)
                elif action == 'restore':
                    name = app.scalar(form,'backup')
                    if not re.fullmatch(r'voting-\d{8}-\d{6}-\d{6}\.sqlite3',name):
                        raise ValueError('Choose a listed backup.')
                    selected = self.data_dir / 'backups' / name
                    if selected.is_symlink() or not selected.is_file():
                        raise ValueError('Backup is unavailable.')
                    if app.scalar(form,'confirm_restore') != 'RESTORE':
                        raise ValueError(t('请输入 RESTORE 确认替换本机全部数据。','Type RESTORE to confirm replacing all data on this computer.'))
                    database = app.DB
                    def migrate(staged):
                        try:
                            app.DB = staged
                            app.init_db()
                        finally:
                            app.DB = database
                    recovery = storage.restore_database(database,selected,prepare=migrate)
                    app.CSRF_KEY = secrets.token_bytes(32)
                    notice = t('已恢复，请重新登录。替换前备份：','Restored. Log in again. Before-restore backup: ') + str(recovery)
                elif action == 'quit':
                    start('200 OK',[('Content-Type','text/html; charset=utf-8'),('Cache-Control','no-store')])
                    threading.Thread(target=self.shutdown,daemon=True).start()
                    return [view.page(t('正在退出','Quitting'),view.head(t('VoteLab 正在安全退出','VoteLab is shutting down safely'),t('稍等片刻后可双击新版本，数据会保留。','Wait a moment, then double-click the new version. Your saved data stays on this computer.'))).encode()]
                else: raise ValueError('Unknown action.')
            except (ValueError, OSError, app.Problem, sqlite3.Error) as error:
                status = '400 Bad Request'
                notice = str(error)
        backups = sorted((self.data_dir / 'backups').glob('voting-*.sqlite3'), reverse=True)
        options = ''.join(f'<option value="{esc(p.name)}">{esc(p.name)} · {p.stat().st_size//1024} KB</option>' for p in backups if p.is_file() and not p.is_symlink())
        body = view.head(t('本机数据与升级','Local data & upgrades'),t('仅通过本机程序启动获得此入口。备份包含账号及选票，请妥善保管。','This page is authorised by the local launcher. Backups include accounts and ballots; keep them private.'),view.link('/',t('返回首页','Back home')))
        if notice: body += f'<div class="notice" style="overflow-wrap:anywhere" role="status">{esc(notice)}</div>'
        body += f'<section class="panel"><h2>{t("数据位置","Data location")}</h2><p style="overflow-wrap:anywhere" data-no-translate>{esc(self.data_dir)}</p><p>VoteLab {app.VERSION}</p><p>{t("升级：先使用下方安全退出，再解压并启动新版本。不要删除数据文件夹。","To upgrade: quit safely below, then extract and launch the new version. Keep the data folder.")}</p></section>'
        body += f'<section class="panel"><h2>{t("创建备份","Create backup")}</h2><p>{t("启动时自动备份；也可现在创建一致的完整快照。备份保存在上述数据目录的 backups 文件夹。","Startup creates a backup automatically. You can also save a complete snapshot now in the backups subfolder above.")}</p><form method="post">{view.hidden()}<button class="btn" name="action" value="backup">{t("立即备份","Back up now")}</button></form></section>'
        body += f'<form class="panel" method="post" data-confirm="{t("确认用备份替换本机全部账号、活动和选票？","Replace all local accounts, events and ballots with this backup?")}">{view.hidden()}<h2>{t("从备份恢复","Restore a backup")}</h2><p>{t("会替换全部本机数据，并退出所有账号。系统先检查备份并保留恢复前快照。只列出本机 backups 文件夹中的备份。","This replaces all local data and signs out all accounts. The backup is checked and a before-restore snapshot is saved. Only backups in this computer’s backups folder are listed.")}</p><label class="field">{t("选择备份","Choose backup")}<select name="backup" required>{options}</select></label><label class="field">{t("输入 RESTORE 确认","Type RESTORE to confirm")}<input name="confirm_restore" required pattern="RESTORE" autocomplete="off"></label><button class="btn secondary" name="action" value="restore" {"disabled" if not options else ""}>{t("恢复全部数据","Restore all data")}</button></form>'
        body += f'<section class="panel"><h2>{t("安全退出／准备升级","Quit safely / prepare upgrade")}</h2><p>{t("关闭浏览器不会停止后台。本按钮只退出当前 VoteLab，不结束其他程序。","Closing a browser does not stop the background app. This button stops only this VoteLab instance.")}</p>{view.button("/_votelab/tools",t("安全退出 VoteLab","Quit VoteLab safely"),confirm=t("确认退出当前 VoteLab？","Quit this VoteLab instance?"))}</section>'
        # Management actions use their own capability; the normal language form
        # still uses the application's session-bound CSRF token.
        body = body.replace(view.hidden(),hidden)
        body = body.replace('<button class="btn ">', '<button class="btn" name="action" value="quit">')
        start(status,[('Content-Type','text/html; charset=utf-8'),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),
                      ('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; form-action 'self'; frame-ancestors 'none'"),('Referrer-Policy','no-referrer')])
        return [view.page(t('本机数据与升级','Local data & upgrades'),body).encode('utf-8')]
