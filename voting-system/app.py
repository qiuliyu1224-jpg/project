"""Local COMP3500 teaching prototype. Standard library only; not production hosting."""
import hashlib
import hmac
import html
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from http.cookies import SimpleCookie, CookieError
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get('VOTING_DB', str(ROOT / 'data' / 'voting.sqlite3')))
CSRF_KEY = secrets.token_bytes(32)  # restarting invalidates open forms, not stored ballots


class Problem(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status


def connect():
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    return con


def init_db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = connect()
    try:
        with con:
            con.executescript((ROOT / 'schema.sql').read_text(encoding='utf-8'))
    finally:
        con.close()


def refresh(con):
    con.execute("UPDATE elections SET status='CLOSED' WHERE status='OPEN' AND ends_at<=?", (int(time.time()),))


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 240000).hex()


def e(value):
    return html.escape(str(value), quote=True)


def scalar(form, key, default=''):
    values = form.get(key, [default])
    if len(values) != 1:
        raise Problem('INVALID_FORMAT: repeated field.')
    return values[0]


def create_event(con, user_id, form):
    title = scalar(form, 'title').strip()
    names = [n.strip() for n in scalar(form, 'candidates').splitlines() if n.strip()]
    method, visibility = scalar(form, 'method'), scalar(form, 'visibility')
    try:
        duration = int(scalar(form, 'duration'))
    except ValueError:
        raise Problem('Duration must be a whole number of minutes.')
    if not 1 <= len(title) <= 100 or not 2 <= len(names) <= 20:
        raise Problem('Provide a title (1–100 characters) and 2–20 candidates.')
    if len(set(names)) != len(names) or any(len(n) > 80 for n in names):
        raise Problem('Candidate names must be distinct and at most 80 characters.')
    if method not in ('SINGLE', 'SCORE') or visibility not in ('PUBLIC', 'PRIVATE'):
        raise Problem('INVALID_FORMAT: unknown method or visibility.')
    if not 1 <= duration <= 10080:
        raise Problem('Duration must be 1–10080 minutes.')
    cur = con.execute('INSERT INTO elections(creator_id,title,method,visibility,duration) VALUES(?,?,?,?,?)',
                      (user_id, title, method, visibility, duration))
    event_id = cur.lastrowid
    con.executemany('INSERT INTO candidates(election_id,name) VALUES(?,?)', [(event_id, n) for n in names])
    con.execute('INSERT INTO rounds(election_id) VALUES(?)', (event_id,))
    return event_id


def submit_ballot(con, event_id, user_id, form):
    # Lock before checking the deadline and duplicates, then commit everything together.
    con.execute('BEGIN IMMEDIATE')
    try:
        refresh(con)
        event = con.execute('SELECT * FROM elections WHERE id=?', (event_id,)).fetchone()
        if not event:
            raise Problem('Event not found.', 404)
        if event['status'] != 'OPEN' or event['ends_at'] <= time.time():
            raise Problem('ELECTION_CLOSED: voting is not open.')
        rid = con.execute('SELECT id FROM rounds WHERE election_id=? AND number=1', (event_id,)).fetchone()['id']
        if con.execute('SELECT 1 FROM ballots WHERE round_id=? AND user_id=?', (rid, user_id)).fetchone():
            raise Problem('ALREADY_VOTED: one ballot per round.')
        ids = [r['id'] for r in con.execute('SELECT id FROM candidates WHERE election_id=? ORDER BY id', (event_id,))]
        selections = []
        if event['method'] == 'SINGLE':
            raw = scalar(form, 'candidate')
            if raw not in [str(i) for i in ids]:
                raise Problem('INVALID_FORMAT: select one candidate from this event.')
            selections = [(int(raw), 1)]
        else:
            for cid in ids:
                raw = scalar(form, 'score_' + str(cid))
                if raw not in ('0', '1', '2', '3', '4', '5'):
                    raise Problem('INVALID_FORMAT: rate every candidate, using integers 0–5. Unanswered is not zero.')
                selections.append((cid, int(raw)))
        bid = con.execute('INSERT INTO ballots(election_id,round_id,user_id) VALUES(?,?,?)',
                          (event_id, rid, user_id)).lastrowid
        con.executemany('INSERT INTO choices(ballot_id,election_id,candidate_id,score) VALUES(?,?,?,?)',
                        [(bid, event_id, cid, score) for cid, score in selections])
        con.commit()
        return bid
    except Exception:
        con.rollback()
        raise


def get_results(con, event_id):
    return con.execute('SELECT c.id,c.name,COALESCE(SUM(v.score),0) AS total FROM candidates c '
                       'LEFT JOIN choices v ON v.candidate_id=c.id AND v.election_id=c.election_id '
                       'WHERE c.election_id=? GROUP BY c.id ORDER BY total DESC,c.id', (event_id,)).fetchall()


CSS = '''body{font:16px/1.6 system-ui,sans-serif;background:#f5f6f8;color:#17202c;margin:0}
main{max-width:880px;margin:28px auto;padding:24px;background:white;border:1px solid #ddd;border-radius:12px}
a{color:#164ca0}header{display:flex;gap:20px;align-items:center;flex-wrap:wrap;border-bottom:1px solid #ddd;padding-bottom:12px}
h1{font-size:26px}h2{font-size:20px}label{display:block;margin:12px 0}input:not([type=radio]):not([type=hidden]),select,textarea{display:block;padding:9px;max-width:95%;width:420px;font:inherit;border:1px solid #888;border-radius:4px}
button{background:#203e69;color:white;padding:10px 18px;border:0;border-radius:5px;cursor:pointer;font:inherit;margin:6px 8px 6px 0}
.card{border:1px solid #ccc;padding:16px;margin:16px 0;border-radius:8px}.notice{background:#fff5dc;padding:12px;border-left:4px solid #a97100}
.muted{color:#545b65}fieldset{border:1px solid #ccc;margin:16px 0}.stars{display:flex;gap:10px;flex-wrap:wrap}.stars label{cursor:pointer}.stars input{accent-color:#164ca0}
table{border-collapse:collapse;width:100%}th,td{padding:10px;border:1px solid #ccc;text-align:left}.bar{height:12px;background:#203e69}form{margin:8px 0}small{font-size:13px}'''


def app(env, start):
    cookies = SimpleCookie()
    try:
        cookies.load(env.get('HTTP_COOKIE', ''))
    except CookieError:
        pass
    token = cookies['session'].value if 'session' in cookies else ''
    browser = cookies['browser'].value if 'browser' in cookies else secrets.token_hex(24)
    if not re.fullmatch('[a-f0-9]{48}', browser):
        browser = secrets.token_hex(24)
    csrf = hmac.new(CSRF_KEY, (browser + '|' + token).encode(), 'sha256').hexdigest()
    headers = [('Content-Type', 'text/html; charset=utf-8'), ('Cache-Control', 'no-store'),
               ('X-Content-Type-Options', 'nosniff'), ('Referrer-Policy', 'same-origin'),
               ('Content-Security-Policy', "default-src 'self'; style-src 'unsafe-inline'; script-src 'none'; form-action 'self'; frame-ancestors 'none'"),
               ('Set-Cookie', f'browser={browser}; HttpOnly; SameSite=Lax; Path=/')]
    def response(body, status=200):
        phrases = {200:'OK',303:'See Other',400:'Bad Request',401:'Unauthorized',403:'Forbidden',404:'Not Found',409:'Conflict',413:'Content Too Large',500:'Internal Server Error'}
        start(f'{status} {phrases.get(status, "Error")}', headers)
        return [body.encode('utf-8')]
    def redirect(url):
        headers.append(('Location', url))
        return response('', 303)
    def hidden():
        return f'<input type="hidden" name="csrf" value="{csrf}">'
    def post(action, label):
        return f'<form method="post" action="{action}">{hidden()}<button>{label}</button></form>'
    con = connect()
    user = None
    path = env.get('PATH_INFO', '/')
    try:
        with con:
            refresh(con)
        user = con.execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=? AND s.expires>?',
                           (token, int(time.time()))).fetchone()
        def require_user():
            if not user:
                raise Problem('Please log in first / 请先登录。', 401)
        def page(title, content):
            auth = (e(user['name']) + post('/logout','Log out / 退出')) if user else '<a href="/login">Log in / 登录</a>'
            return f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)}</title><style>{CSS}</style><main><header><a href="/">VoteLab</a><a href="/create">Create / 创建</a>{auth}</header><p class="notice">Local prototype / 本地原型：phone-account login only, no SMS verification. Use fictional data / 请用虚构资料。</p><h1>{e(title)}</h1>{content}</main></html>'
        if env['REQUEST_METHOD'] == 'POST':
            try:
                size = int(env.get('CONTENT_LENGTH') or 0)
            except ValueError:
                raise Problem('Invalid request length.')
            if size > 32768 or size < 0:
                raise Problem('Request too large.', 413)
            try:
                form = parse_qs(env['wsgi.input'].read(size).decode('utf-8'), keep_blank_values=True)
            except UnicodeError:
                raise Problem('INVALID_FORMAT: invalid text encoding.')
            if not hmac.compare_digest(scalar(form,'csrf'), csrf):
                raise Problem('Form expired. Reload this page and try again.', 403)
            if path in ('/register','/login'):
                phone, password = scalar(form,'phone').strip(), scalar(form,'password')
                if not re.fullmatch(r'[0-9]{8,15}', phone) or not 8 <= len(password) <= 128:
                    raise Problem('Use an 8–15 digit phone account and an 8–128 character password.')
                if path == '/register':
                    name = scalar(form,'name').strip()
                    if not 1 <= len(name) <= 60:
                        raise Problem('Name must be 1–60 characters.')
                    salt = secrets.token_hex(16)
                    with con:
                        uid = con.execute('INSERT INTO users(phone,name,salt,password_hash) VALUES(?,?,?,?)',
                                          (phone,name,salt,password_hash(password,salt))).lastrowid
                else:
                    row = con.execute('SELECT * FROM users WHERE phone=?',(phone,)).fetchone()
                    if not row or not hmac.compare_digest(row['password_hash'],password_hash(password,row['salt'])):
                        raise Problem('Incorrect account or password.',401)
                    uid = row['id']
                newtoken = secrets.token_hex(32)
                with con:
                    con.execute('INSERT INTO sessions VALUES(?,?,?)',(newtoken,uid,int(time.time())+7200))
                headers.append(('Set-Cookie',f'session={newtoken}; HttpOnly; SameSite=Lax; Path=/; Max-Age=7200'))
                return redirect('/')
            require_user()
            if path == '/logout':
                with con:
                    con.execute('DELETE FROM sessions WHERE token=?',(token,))
                headers.append(('Set-Cookie','session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0'))
                return redirect('/')
            if path == '/create':
                with con:
                    eid = create_event(con,user['id'],form)
                return redirect(f'/e/{eid}/preview')
            match = re.fullmatch(r'/e/(\d+)/(open|close|publish|vote)',path)
            if not match:
                raise Problem('Not found.',404)
            eid, action = int(match[1]), match[2]
            if action == 'vote':
                submit_ballot(con,eid,user['id'],form)
                return redirect(f'/e/{eid}')
            with con:
                con.execute('BEGIN IMMEDIATE')
                refresh(con)
                event = con.execute('SELECT * FROM elections WHERE id=?',(eid,)).fetchone()
                if not event:
                    raise Problem('Not found.',404)
                if event['creator_id'] != user['id']:
                    raise Problem('FORBIDDEN: creator only.',403)
                expected = {'open':'DRAFT','close':'OPEN','publish':'CLOSED'}[action]
                if event['status'] != expected:
                    raise Problem('This action is not available in the current state.',409)
                if action == 'open':
                    con.execute("UPDATE elections SET status='OPEN',ends_at=? WHERE id=?",(int(time.time())+event['duration']*60,eid))
                elif action == 'close':
                    con.execute("UPDATE elections SET status='CLOSED' WHERE id=?",(eid,))
                else:
                    con.execute('UPDATE elections SET published=1 WHERE id=?',(eid,))
                con.execute('INSERT INTO audit(election_id,actor_id,action,created) VALUES(?,?,?,?)',(eid,user['id'],action,int(time.time())))
            return redirect(f'/e/{eid}')

        if env['REQUEST_METHOD'] != 'GET':
            raise Problem('Unsupported request method.')
        if path == '/':
            rows = con.execute("SELECT * FROM elections WHERE status<>'DRAFT' OR creator_id=? ORDER BY id DESC", (user['id'] if user else -1,)).fetchall()
            body = '<p>Single choice and 0–5 scoring / 单选与0–5评分</p>'
            for row in rows:
                body += f'<article class="card"><h2><a href="/e/{row["id"]}">{e(row["title"])}</a></h2>{e(row["method"])} · {e(row["status"])} · Results: {e(row["visibility"])}</article>'
            return response(page('Voting events / 投票活动',body or 'No events yet.'))
        if path in ('/login','/register'):
            register = path == '/register'
            body = f'<form method="post">{hidden()}'
            if register:
                body += '<label>Name / 名称<input name="name" maxlength="60" required></label>'
            body += '<label>Phone account / 手机号账号<input name="phone" inputmode="numeric" pattern="[0-9]{8,15}" required></label><label>Password / 密码<input type="password" name="password" minlength="8" maxlength="128" required></label><button>Continue / 继续</button></form>'
            body += '<a href="/register">Create a demo account / 注册演示账号</a>'
            return response(page('Register / 注册' if register else 'Log in / 登录',body))
        if path == '/create':
            require_user()
            body = f'<form method="post">{hidden()}<label>Title / 标题<input name="title" maxlength="100" required></label><label>Method / 方式<select name="method"><option value="SINGLE">Single choice / 单选</option><option value="SCORE">Score 0–5 / 评分</option></select></label><label>Candidates, one per line / 候选人每行一个<textarea name="candidates" rows="5" required></textarea></label><label>Results visibility / 结果可见性<select name="visibility"><option value="PUBLIC">Public / 公开</option><option value="PRIVATE">Creator only in this increment / 本轮仅创建者</option></select></label><label>Voting duration in minutes / 投票持续分钟数<input name="duration" type="number" min="1" max="10080" value="60" required></label><button>Save draft and preview / 保存并预览</button></form>'
            return response(page('Create event / 创建活动',body))
        match = re.fullmatch(r'/e/(\d+)(/preview|/results)?',path)
        if not match:
            raise Problem('Not found.',404)
        eid, suffix = int(match[1]), match[2] or ''
        event = con.execute('SELECT * FROM elections WHERE id=?',(eid,)).fetchone()
        if not event:
            raise Problem('Not found.',404)
        owner = bool(user and user['id'] == event['creator_id'])
        if event['status'] == 'DRAFT' and not owner:
            raise Problem('FORBIDDEN: draft is private.',403)
        candidates = con.execute('SELECT * FROM candidates WHERE election_id=? ORDER BY id',(eid,)).fetchall()
        if suffix == '/preview' and not owner:
            raise Problem('FORBIDDEN: preview is for the creator.',403)
        if suffix == '/results':
            if event['status'] != 'CLOSED' or not (owner or (event['published'] and event['visibility']=='PUBLIC')):
                raise Problem('Results are private or awaiting publication.',403)
            results = get_results(con,eid)
            count = con.execute('SELECT COUNT(*) FROM ballots WHERE election_id=?',(eid,)).fetchone()[0]
            body = f'<p>Submitted ballots / 已提交选票: {count}</p><table><tr><th>Candidate / 候选人</th><th>Total / 总计</th><th>Chart / 图表</th></tr>'
            max_total = max([r['total'] for r in results]+[1])
            for r in results:
                body += f'<tr><td>{e(r["name"])}</td><td>{r["total"]}</td><td><div class="bar" style="width:{r["total"]/max_total*100:.1f}%"></div></td></tr>'
            body += '</table><p>No award or tie decision is automated in this increment / 本轮仅显示汇总，不自动分配奖项或处理平票。</p>'
            return response(page('Results / 结果',body))
        preview = suffix == '/preview' or event['status']=='DRAFT'
        body = f'<p>Method / 方式: {e(event["method"])} · Status / 状态: {e(event["status"])} · Results / 结果: {e(event["visibility"])}</p>'
        if event['ends_at']:
            body += f'<p>Deadline (UTC): {datetime.fromtimestamp(event["ends_at"],timezone.utc).strftime("%Y-%m-%d %H:%M:%S")}</p>'
        if preview:
            body += f'<p class="notice">PREVIEW / 预览：no ballots can be submitted. Voting duration: {event["duration"]} minutes.</p>'
        already = bool(user and con.execute('SELECT 1 FROM ballots WHERE election_id=? AND user_id=?',(eid,user['id'])).fetchone())
        can_vote = bool(not preview and user and not already and event['status']=='OPEN')
        body += f'<form method="post" action="/e/{eid}/vote">{hidden()}'
        for c in candidates:
            if event['method'] == 'SINGLE':
                body += f'<label><input type="radio" name="candidate" value="{c["id"]}" required {"disabled" if not can_vote else ""}> {e(c["name"])}</label>'
            else:
                body += f'<fieldset><legend>{e(c["name"])}</legend><div class="stars">'
                for score in range(6):
                    label = '0 分 / zero' if score==0 else '★'*score + f' ({score})'
                    body += f'<label><input type="radio" name="score_{c["id"]}" value="{score}" required {"disabled" if not can_vote else ""}>{label}</label>'
                body += '</div><small>Choose a score / 请选择分数；未选不等于零分。</small></fieldset>'
        if can_vote:
            body += '<p>Check your selections before submitting. A successful ballot cannot be edited / 提交前请核对，成功后不能修改。</p><button>Confirm vote / 确认投票</button>'
        body += '</form>'
        if already:
            body += '<p class="notice">SUCCESS / 已成功提交。ALREADY_VOTED: no second ballot this round.</p>'
        if not user:
            body += '<p><a href="/login">Log in to vote / 登录后投票</a></p>'
        if owner and event['status']=='DRAFT':
            body += post(f'/e/{eid}/open','Confirm publication and open / 确认发布并开启')
            body += '<p class="muted">Draft editing is not implemented yet. To correct a draft, create a new one / 草稿编辑待实现；暂可重新创建。</p>'
        if owner and event['status']=='OPEN':
            body += post(f'/e/{eid}/close','Close voting / 关闭投票')
        if owner and event['status']=='CLOSED' and not event['published']:
            body += post(f'/e/{eid}/publish','Publish results / 发布结果')
        if event['status']=='CLOSED':
            body += f'<p><a href="/e/{eid}/results">View results (permission checked) / 查看结果（需权限）</a></p>'
        return response(page(event['title'],body))
    except Problem as err:
        return response(page('Action not completed / 操作未完成',f'<p>{e(err.message)}</p><p>Use your browser Back button to review your input. Check event status before retrying / 返回检查输入及活动状态。</p><a href="/">Home / 首页</a>'),err.status)
    except sqlite3.IntegrityError:
        return response(page('Not saved / 未保存','<p>Account already exists or data conflicts. Check submission status before retrying / 账号已存在或数据冲突，请先核对提交状态。</p>'),409)
    except sqlite3.Error:
        return response(page('Save failed / 保存失败','<p>No success was confirmed. Check your submission status before retrying / 未确认成功，请先检查是否已投票。</p>'),500)
    finally:
        con.close()


if __name__ == '__main__':
    init_db()
    print('Open http://127.0.0.1:8000 - local prototype, fictional data only.', flush=True)
    with make_server('127.0.0.1',8000,app) as server:
        server.serve_forever()
