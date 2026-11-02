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
            columns = {r['name'] for r in con.execute('PRAGMA table_info(users)')}
            if 'role' not in columns:
                con.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'VOTER' CHECK(role IN ('MANAGER','VOTER'))")
                con.execute("UPDATE users SET role='MANAGER' WHERE id IN (SELECT creator_id FROM elections)")
            for table, changes in {
                'elections': [('planned_end','INTEGER'), ('submissions_open','INTEGER NOT NULL DEFAULT 0'),('allow_submissions','INTEGER NOT NULL DEFAULT 0')],
                'candidates': [('description',"TEXT NOT NULL DEFAULT ''"),('image_id','TEXT REFERENCES images(id)'),
                    ('submitter_id','INTEGER REFERENCES users(id)'),('review_status',"TEXT NOT NULL DEFAULT 'APPROVED' CHECK(review_status IN ('PENDING','APPROVED','REJECTED'))"),
                    ('review_reason',"TEXT NOT NULL DEFAULT ''")]
            }.items():
                current={r['name'] for r in con.execute(f'PRAGMA table_info({table})')}
                for column, definition in changes:
                    if column not in current: con.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
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
        ids = [r['id'] for r in con.execute("SELECT id FROM candidates WHERE election_id=? AND review_status='APPROVED' ORDER BY id", (event_id,))]
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
                       "WHERE c.election_id=? AND c.review_status='APPROVED' GROUP BY c.id ORDER BY total DESC,c.id", (event_id,)).fetchall()


def app(env, start):
    from web3 import dispatch
    return dispatch(env, start)


if __name__ == '__main__':
    import sys
    sys.modules['app'] = sys.modules[__name__]
    init_db()
    print('Open http://127.0.0.1:8000 - VoteLab workspace.', flush=True)
    with make_server('127.0.0.1', 8000, app) as server:
        server.serve_forever()
