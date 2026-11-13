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
from demo_server import create_server

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
            columns = {r['name'] for r in con.execute('PRAGMA table_info(users)')}
            if 'role' not in columns:
                con.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'VOTER' CHECK(role IN ('MANAGER','VOTER'))")
                con.execute("UPDATE users SET role='MANAGER' WHERE id IN (SELECT creator_id FROM elections)")
            for table, changes in {
                'elections': [('planned_end','INTEGER'), ('submissions_open','INTEGER NOT NULL DEFAULT 0'),('allow_submissions','INTEGER NOT NULL DEFAULT 0'),
                    ('auto_publish','INTEGER NOT NULL DEFAULT 0 CHECK(auto_publish IN (0,1))'),
                    ('voting_mode','TEXT'),('max_choices','INTEGER NOT NULL DEFAULT 1'),('score_optional','INTEGER NOT NULL DEFAULT 0'),
                    ('current_round','INTEGER NOT NULL DEFAULT 1'),('paused','INTEGER NOT NULL DEFAULT 0'),('revisions','INTEGER NOT NULL DEFAULT 0'),
                    ('announcement',"TEXT NOT NULL DEFAULT ''"),('tags',"TEXT NOT NULL DEFAULT ''"),('invite_salt',"TEXT NOT NULL DEFAULT ''"),('invite_hash',"TEXT NOT NULL DEFAULT ''")],
                'users': [('password_set','INTEGER NOT NULL DEFAULT 0')],
                'rounds': [('snapshot',"TEXT NOT NULL DEFAULT ''"),('eligible',"TEXT NOT NULL DEFAULT ''"),('is_runoff','INTEGER NOT NULL DEFAULT 0')],
                'candidates': [('description',"TEXT NOT NULL DEFAULT ''"),('image_id','TEXT REFERENCES images(id)'),
                    ('submitter_id','INTEGER REFERENCES users(id)'),('review_status',"TEXT NOT NULL DEFAULT 'APPROVED' CHECK(review_status IN ('PENDING','APPROVED','REJECTED'))"),
                    ('review_reason',"TEXT NOT NULL DEFAULT ''"),('active','INTEGER NOT NULL DEFAULT 1')]
            }.items():
                current={r['name'] for r in con.execute(f'PRAGMA table_info({table})')}
                for column, definition in changes:
                    if column not in current: con.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
            con.executescript('''CREATE TABLE IF NOT EXISTS preferences (
                ballot_id INTEGER NOT NULL REFERENCES ballots(id), candidate_id INTEGER NOT NULL REFERENCES candidates(id),
                position INTEGER NOT NULL CHECK(position BETWEEN 1 AND 20),
                PRIMARY KEY(ballot_id,candidate_id), UNIQUE(ballot_id,position));
                CREATE TABLE IF NOT EXISTS event_access (election_id INTEGER REFERENCES elections(id), user_id INTEGER REFERENCES users(id),
                PRIMARY KEY(election_id,user_id));
                CREATE TABLE IF NOT EXISTS attempt_limits (key TEXT PRIMARY KEY, count INTEGER NOT NULL, reset_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS event_changes (id INTEGER PRIMARY KEY, election_id INTEGER REFERENCES elections(id),
                    round_number INTEGER NOT NULL, actor_id INTEGER REFERENCES users(id), kind TEXT NOT NULL,
                    announcement TEXT NOT NULL, created INTEGER NOT NULL);''')
    finally:
        con.close()


def refresh(con):
    from publication import refresh as refresh_publication
    return refresh_publication(con)


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
    from voting_rules import submit
    return submit(con, event_id, user_id, form)


def get_results(con, event_id):
    from voting_rules import counts, event_row
    event = event_row(con.execute('SELECT * FROM elections WHERE id=?', (event_id,)).fetchone())
    return counts(con, event)['rows']


def app(env, start):
    from web4 import dispatch
    return dispatch(env, start)


if __name__ == '__main__':
    import sys
    sys.modules['app'] = sys.modules[__name__]
    init_db()
    from maintenance import start_maintenance
    start_maintenance()
    print('Open http://127.0.0.1:8000 - VoteLab workspace.', flush=True)
    with create_server('127.0.0.1', 8000, app) as server:
        server.serve_forever()
