import argparse
import hashlib
import http.cookiejar
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPCookieProcessor, HTTPRedirectHandler, Request
import struct
import zlib

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class Client:
    def __init__(self, base):
        self.base = base
        self.opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()), NoRedirect())

    def request(self, path, fields=None, upload=None):
        headers = {}
        data = None
        if fields is not None:
            if upload:
                boundary = 'VoteLabVerificationBoundary'
                data = bytearray()
                for key, values in fields.items():
                    for value in values if isinstance(values, list) else [values]:
                        data.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
                name, blob = upload
                data.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="image.png"\r\nContent-Type: image/png\r\n\r\n'.encode())
                data.extend(blob)
                data.extend(f'\r\n--{boundary}--\r\n'.encode())
                data = bytes(data)
                headers['Content-Type'] = 'multipart/form-data; boundary=' + boundary
            else:
                data = urlencode(fields, doseq=True).encode()
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
        try:
            response = self.opener.open(Request(self.base + path, data=data, headers=headers), timeout=6)
        except HTTPError as exc:
            response = exc
        with response:
            return response.code, response.read(), response.headers

    def post(self, path, fields, upload=None):
        status, page, _ = self.request('/login')
        assert status == 200, (status, path)
        csrf = re.search(rb'name="csrf" value="([a-f0-9]+)"', page)[1].decode()
        return self.request(path, {**fields, 'csrf': csrf}, upload)

    def register(self, phone, name):
        status, body, _ = self.post('/auth/code', {'phone': phone, 'purpose': 'register'})
        assert status == 200, status
        code = re.search(rb'class="otp-code">([0-9]{6})', body)[1].decode()
        status, _, _ = self.post('/register', {'phone': phone, 'name': name, 'password': 'Fixture-Only-2026', 'password_confirm': 'Fixture-Only-2026', 'code': code})
        assert status == 303, status

    def login(self, phone):
        status, _, _ = self.post('/login', {'phone': phone, 'password': 'Fixture-Only-2026'})
        assert status == 303, status

def check_request(client, path, expected, fields=None, upload=None):
    result = client.request(path) if fields is None else client.post(path, fields, upload)
    assert result[0] == expected, (path, result[0], expected)
    return result

def fixture_png():
    def chunk(kind, payload):
        return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload))
    rgb_pixel = b'\x00\x00\xff'
    pixels = (b'\x00' + rgb_pixel * 48) * 36
    header = struct.pack('>IIBBBBB', 48, 36, 8, 2, 0, 0, 0)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', header) + chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b'')

def before(base, path):
    owner, voter = Client(base), Client(base)
    owner.register('92340001', 'Release verification owner')
    voter.register('92340002', 'Release verification voter')
    deadline = (datetime.now(timezone(timedelta(hours=8))) + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
    _, _, headers = check_request(owner, '/create', 303, {'title': 'Release verification event', 'method': 'SCORE', 'visibility': 'PUBLIC', 'deadline': deadline, 'entry_key': ['a', 'b'], 'entry_name_a': 'Verification Alpha', 'entry_name_b': 'Verification Beta'}, ('entry_image_a', fixture_png()))
    event = '/e/' + headers['Location'].split('/')[2]
    check_request(owner, event + '/open', 303, {})
    _, event_body, _ = check_request(voter, event, 200)
    score_field = re.search(rb'name="(score_[0-9]+)"', event_body)[1].decode()
    round_id = re.search(rb'name="round_id" value="([0-9]+)"', event_body)[1].decode()
    media = re.search(rb'(/media/[a-f0-9]{40})', event_body)[1].decode()
    _, image_body, _ = check_request(voter, media, 200)
    assert image_body.startswith(b'\xff\xd8')
    vote = {'round_id': round_id, score_field: 5}
    _, confirm, _ = check_request(voter, event + '/confirm', 200, vote)
    assert score_field.encode() in confirm
    check_request(voter, event + '/vote', 303, vote)
    path.write_text(json.dumps({'event': event, 'media': media, 'sha': hashlib.sha256(image_body).hexdigest(), 'vote': vote}))
    print('BEFORE: registered two fixture accounts, created and opened score event, fetched image, confirmed and submitted single rating.')

def after(base, path):
    fixture = json.loads(path.read_text())
    event, media, vote = fixture['event'], fixture['media'], fixture['vote']
    owner, voter = Client(base), Client(base)
    owner.login('92340001')
    voter.login('92340002')
    _, image_body, _ = check_request(voter, media, 200)
    assert hashlib.sha256(image_body).hexdigest() == fixture['sha']
    check_request(voter, '/language', 303, {'lang': 'en', 'next': '/'})
    _, duplicate, _ = check_request(voter, event + '/vote', 400, vote)
    assert b'ALREADY_VOTED' in duplicate
    check_request(owner, event + '/close', 303, {})
    check_request(owner, event + '/publish', 303, {})
    guest = Client(base)
    check_request(guest, '/language', 303, {'lang': 'en', 'next': '/'})
    _, results, _ = check_request(guest, event + '/results', 200)
    assert b'5.00 / 5' in results and b'1 ratings' in results and b'Not rated' in results
    print('AFTER: fixture accounts, image bytes and rating persisted, duplicate rejected, public results show 5.00 / 5 with one rating and the skipped entry unrated.')


parser = argparse.ArgumentParser(description='Exercise VoteLab using fictional accounts and a temporary database.')
parser.add_argument('phase', choices=['before', 'after'])
parser.add_argument('base')
parser.add_argument('fixture', type=Path)
args = parser.parse_args()
globals()[args.phase](args.base, args.fixture)

