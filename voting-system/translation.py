"""Optional online translations of rendered content, never of stored ballots.

MyMemory GET API: https://mymemory.translated.net/doc/spec.php
Anonymous usage: https://mymemory.translated.net/doc/usagelimits.php
Only signed strings actually rendered for a browser can use the HTTP endpoint.
Form values, source records, account names and images are never rewritten.
"""
import base64
import hashlib
import hmac
import html
from html.parser import HTMLParser
import json
import re
import sqlite3
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = 'https://api.mymemory.translated.net/get'
TIMEOUT = 5.0
TOTAL_TIMEOUT = 12.0
MAX_SOURCE = 4000
TOKEN_TTL = 180
DAILY_BUDGET = 5000
RESPONSE_LIMIT = 131072
_CJK = re.compile(r'[\u3400-\u9fff\uf900-\ufaff]')
_workers = threading.BoundedSemaphore(4)
_failure_lock = threading.Lock()
_failures = {}


def _b64(data):
    return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')


def _unb64(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def make_token(source, context, key, now=None):
    if not isinstance(source, str) or not 1 <= len(source) <= MAX_SOURCE:
        raise ValueError('Invalid translation source')
    expiry = int(time.time() if now is None else now) + TOKEN_TTL
    payload = _b64(json.dumps([source, 'en', expiry], ensure_ascii=False,
                              separators=(',', ':')).encode('utf-8'))
    signature = _b64(hmac.new(key, (str(context) + '|' + payload).encode(), hashlib.sha256).digest())
    return payload + '.' + signature


def verify_token(token, context, key, now=None):
    """Return a rendered source, bound to this browser/session and short lifetime."""
    try:
        if not isinstance(token, str) or len(token) > 24000:
            raise ValueError()
        payload, signature = token.split('.')
        expected = _b64(hmac.new(key, (str(context) + '|' + payload).encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError()
        source, target, expiry = json.loads(_unb64(payload).decode('utf-8'))
        current = int(time.time() if now is None else now)
        if (not isinstance(source, str) or not 1 <= len(source) <= MAX_SOURCE
                or target != 'en' or type(expiry) is not int
                or expiry < current or expiry > current + TOKEN_TTL + 5):
            raise ValueError()
        return source
    except (ValueError, TypeError, UnicodeError, KeyError):
        raise ValueError('Translation request expired or invalid') from None


def init_schema(con):
    con.execute('''CREATE TABLE IF NOT EXISTS content_translations (
        source_hash TEXT PRIMARY KEY, source TEXT NOT NULL,
        translated TEXT NOT NULL, updated INTEGER NOT NULL)''')
    con.execute('''CREATE TABLE IF NOT EXISTS translation_usage (
        day TEXT PRIMARY KEY, chars INTEGER NOT NULL CHECK(chars >= 0))''')


def _chunks(source):
    """Keep each provider q below its 500-byte UTF-8 limit, without lost text."""
    chunk = ''
    size = 0
    for char in source:
        width = len(char.encode('utf-8'))
        if chunk and size + width > 480:
            yield chunk
            chunk, size = '', 0
        chunk += char
        size += width
    if chunk:
        yield chunk


def _request(source, timeout):
    url = API_URL + '?' + urlencode({'q': source, 'langpair': 'zh-CN|en', 'mt': '1'})
    req = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'VoteLab-Classroom/0.4.4'})
    with urlopen(req, timeout=timeout) as response:
        raw = response.read(RESPONSE_LIMIT + 1)
        if len(raw) > RESPONSE_LIMIT:
            raise ValueError('Translation response too large')
    value = json.loads(raw.decode('utf-8'))
    if (not isinstance(value, dict) or str(value.get('responseStatus')) != '200'
            or value.get('quotaFinished')):
        raise ValueError('Translation service unavailable')
    data = value.get('responseData')
    if not isinstance(data, dict) or not isinstance(data.get('translatedText'), str):
        raise ValueError('Invalid translation response')
    result = html.unescape(data['translatedText']).strip()
    if (not result or len(result) > MAX_SOURCE * 5 or _CJK.search(result)
            or 'MYMEMORY WARNING' in result.upper() or 'QUERY LENGTH LIMIT' in result.upper()):
        raise ValueError('No usable English translation')
    return result


def translate(con, source):
    """Translate outside all application transactions, with bounded cached requests.

    The caller owns a dedicated per-request connection. Successful translations
    are cached by exact source; source edits naturally receive a new cache key.
    There are no writes to events, entries, accounts, rounds or votes.
    """
    unavailable = {'ok': False, 'text': 'Translation unavailable', 'source': source,
                   'cached': False, 'provider': 'MyMemory'}
    if not isinstance(source, str) or not 1 <= len(source) <= MAX_SOURCE:
        return unavailable
    if not _CJK.search(source):
        return {'ok': True, 'text': source, 'source': source, 'cached': True, 'provider': 'MyMemory'}
    # Never commit or hold an unrelated business operation while contacting a provider.
    if con.in_transaction:
        return unavailable
    digest = hashlib.sha256(source.encode('utf-8')).hexdigest()
    try:
        init_schema(con)
        row = con.execute('SELECT source, translated FROM content_translations WHERE source_hash=?',
                          (digest,)).fetchone()
    except sqlite3.Error:
        return unavailable
    if row and row[0] == source:
        return {'ok': True, 'text': row[1], 'source': source, 'cached': True, 'provider': 'MyMemory'}
    with _failure_lock:
        if _failures.get(digest, 0) > time.monotonic():
            return unavailable
    if not _workers.acquire(blocking=False):
        return unavailable
    try:
        # Reserve the per-installation anonymous allowance in a short transaction.
        day = time.strftime('%Y-%m-%d', time.gmtime())
        with con:
            con.execute('INSERT OR IGNORE INTO translation_usage VALUES(?, 0)', (day,))
            reserved = con.execute('UPDATE translation_usage SET chars=chars+? '
                                   'WHERE day=? AND chars+?<=?',
                                   (len(source), day, len(source), DAILY_BUDGET))
            if reserved.rowcount != 1:
                return unavailable
            con.execute('DELETE FROM translation_usage WHERE day < ?', (day,))
        deadline = time.monotonic() + TOTAL_TIMEOUT
        results = []
        for chunk in _chunks(source):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Translation timed out')
            results.append(_request(chunk, min(TIMEOUT, remaining)))
        result = ' '.join(results)
        with con:
            con.execute('INSERT OR REPLACE INTO content_translations VALUES(?,?,?,?)',
                        (digest, source, result, int(time.time())))
            # Limit growth without changing source records or vote history.
            con.execute('DELETE FROM content_translations WHERE source_hash IN '
                        '(SELECT source_hash FROM content_translations ORDER BY updated DESC LIMIT -1 OFFSET 2000)')
        return {'ok': True, 'text': result, 'source': source, 'cached': False, 'provider': 'MyMemory'}
    except (OSError, ValueError, TypeError, KeyError, TimeoutError, sqlite3.Error):
        with _failure_lock:
            if len(_failures) >= 1000:
                _failures.clear()
            _failures[digest] = time.monotonic() + 20
        return unavailable
    finally:
        _workers.release()


class _Page(HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta',
            'param', 'source', 'track', 'wbr'}
    SKIP = {'script', 'style', 'textarea', 'option', 'code', 'pre'}

    def __init__(self, context, key):
        super().__init__(convert_charrefs=True)
        self.context, self.key = context, key
        self.output, self.stack, self.tokens = [], [], {}
        self.marked = False

    def handle_decl(self, decl):
        self.output.append('<!' + decl + '>')

    def handle_comment(self, text):
        self.output.append('<!--' + text + '-->')

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        classes = set(values.get('class', '').split())
        skip = (tag in self.SKIP or 'data-no-translate' in values
                or bool(classes & {'side-bottom', 'avatar', 'translation-notice'}))
        self.output.append(self.get_starttag_text())
        if tag not in self.VOID:
            self.stack.append((tag, skip))

    def handle_startendtag(self, tag, attrs):
        self.output.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        self.output.append('</' + tag + '>')
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, text):
        tags = [tag for tag, _ in self.stack]
        if tags and tags[-1] in ('script', 'style'):
            self.output.append(text)
            return
        if 'title' in tags:
            # The visible breadcrumb is translated; do not put HTML in HTML/SVG titles.
            self.output.append('VoteLab' if _CJK.search(text) else html.escape(text, quote=False))
            return
        if (not _CJK.search(text) or any(skip for _, skip in self.stack)
                or not 1 <= len(text.strip()) <= MAX_SOURCE):
            self.output.append(html.escape(text, quote=False))
            return
        source = text.strip()
        token = self.tokens.setdefault(source, make_token(source, self.context, self.key))
        tag = 'tspan' if 'svg' in tags else 'span'
        self.output.append(f'<{tag} data-translation-token="{html.escape(token, quote=True)}" '
                           f'data-translation-source="{html.escape(source, quote=True)}" '
                           'title="Automatic translation by MyMemory">Translating...</' + tag + '>')
        self.marked = True


def mark_page(source, lang, context, key):
    """Mark only rendered Chinese text for asynchronous English translation.

    Source fields in editors are intentionally retained; translation must never
    silently rewrite a user's submission. Static English UI strings need no API.
    The root may add a data-no-translate attribute for any other identity label.
    """
    if lang != 'en' or 'data-translation-token=' in source:
        return source
    page = _Page(context, key)
    page.feed(source)
    page.close()
    result = ''.join(page.output)
    if page.marked:
        script = '<script defer src="/static/translation.js"></script>'
        result = result.replace('</body>', script + '</body>') if '</body>' in result else result + script
    return result
