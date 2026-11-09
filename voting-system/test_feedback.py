"""Focused v0.4.2 regressions. Uses only a fresh, temporary database.

Normal unittest discovery includes these checks. Static JavaScript checks
supplement the isolated browser validation.
"""

from contextlib import closing
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from urllib.parse import urlencode, urlsplit


import app
from ui4 import View


SOURCE = Path(__file__).resolve().parent
DELIVERY_NOTE = SOURCE / 'release' / 'READ ME FIRST.txt'


class HtmlStructure(HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, source):
        super().__init__()
        self.stack = []
        self.elements = []
        self.nested_labels = []
        self.text = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        parents = [item[0] for item in self.stack]
        self.elements.append((tag, values, parents))
        if tag == 'label' and 'label' in parents:
            self.nested_labels.append(values)
        if tag not in self.VOID:
            self.stack.append((tag, values))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, text):
        self.text.append(text)


class Client:
    def __init__(self, language='zh'):
        self.cookies = {'lang': language}

    def request(self, path, fields=None, accept='text/html'):
        body = urlencode(fields or {}, doseq=True).encode()
        url = urlsplit(path)
        env = {
            'REQUEST_METHOD': 'POST' if fields is not None else 'GET',
            'PATH_INFO': url.path,
            'QUERY_STRING': url.query,
            'CONTENT_LENGTH': str(len(body)),
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'wsgi.input': io.BytesIO(body),
            'HTTP_COOKIE': '; '.join(key + '=' + value for key, value in self.cookies.items()),
            'HTTP_ACCEPT': accept,
        }
        meta = {}

        def start(status, headers):
            meta['status'] = int(status.split()[0])
            meta['headers'] = dict(headers)
            for name, value in headers:
                if name == 'Set-Cookie':
                    key, content = value.split(';')[0].split('=', 1)
                    self.cookies[key] = content

        content = b''.join(app.app(env, start)).decode('utf-8')
        return meta['status'], content, meta['headers']

    def post(self, path, fields, accept='text/html'):
        _, page, _ = self.request('/login')
        csrf = re.search(r'name="csrf" value="([a-f0-9]+)"', page)[1]
        return self.request(path, {**fields, 'csrf': csrf}, accept)


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='votelab-v042-', dir=SOURCE)
        self.previous_db = app.DB
        app.DB = Path(self.directory.name) / 'isolated.sqlite3'
        app.init_db()

    def tearDown(self):
        app.DB = self.previous_db
        self.directory.cleanup()

    def business_counts(self):
        tables = ('users', 'elections', 'rounds', 'candidates', 'ballots', 'choices', 'preferences', 'images')
        with closing(app.connect()) as con:
            return {table: con.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0] for table in tables}

    def test_auth_labels_are_separate_and_show_password_is_optional(self):
        for language in ('zh', 'en'):
            for path in ('/login', '/register', '/reset'):
                with self.subTest(language=language, path=path):
                    status, page, _ = Client(language).request(path)
                    self.assertEqual(status, 200)
                    html = HtmlStructure(page)
                    self.assertEqual(html.nested_labels, [])
                    show = [attrs for tag, attrs, _ in html.elements if 'data-show-password' in attrs]
                    self.assertEqual(len(show), 1)
                    self.assertEqual(show[0].get('type'), 'checkbox')
                    self.assertNotIn('required', show[0])
                    self.assertNotIn('checked', show[0])
                    self.assertIn('显示密码（可选）' if language == 'zh' else 'Show password', ''.join(html.text))

    def test_registration_and_reset_explain_existing_length_and_confirmation(self):
        for language in ('zh', 'en'):
            for path in ('/register', '/reset'):
                with self.subTest(language=language, path=path):
                    _, page, _ = Client(language).request(path)
                    html = HtmlStructure(page)
                    visible = ' '.join(html.text)
                    self.assertRegex(visible, r'8[–～-]128')
                    self.assertRegex(visible, r'两次|一致|相同' if language == 'zh' else r'(?i)match|same')
                    self.assertNotRegex(visible, r'(?i)uppercase|lowercase|special character|大写|小写|特殊字符')
                    passwords = [attrs for tag, attrs, _ in html.elements if tag == 'input' and attrs.get('name') in ('password', 'password_confirm')]
                    self.assertEqual(len(passwords), 2)
                    for attrs in passwords:
                        self.assertEqual(attrs.get('type'), 'password')
                        self.assertEqual(attrs.get('minlength'), '8')
                        self.assertEqual(attrs.get('maxlength'), '128')

    def test_code_controls_expose_async_status_and_noscript_fallback(self):
        for path in ('/register', '/reset'):
            _, page, _ = Client().request(path)
            html = HtmlStructure(page)
            buttons = [attrs for tag, attrs, _ in html.elements if tag == 'button' and 'data-get-code' in attrs]
            self.assertEqual(len(buttons), 1, path)
            self.assertEqual(buttons[0].get('formaction'), '/auth/code')
            self.assertIn('formnovalidate', buttons[0])
            status = [attrs for tag, attrs, _ in html.elements if 'data-code-status' in attrs]
            self.assertEqual(len(status), 1)
            self.assertEqual(status[0].get('aria-live'), 'polite')

    def test_async_code_success_returns_json_without_creating_accounts(self):
        secret = 'Typed-but-never-reflected-123'
        client = Client('en')
        before = self.business_counts()
        status, body, headers = client.post('/auth/code', {'phone': '96234001', 'purpose': 'register', 'password': secret, 'password_confirm': secret}, 'application/json')
        self.assertEqual(status, 200)
        self.assertTrue(headers['Content-Type'].startswith('application/json'))
        payload = json.loads(body)
        self.assertEqual(set(payload), {'code', 'message'})
        self.assertRegex(payload['code'], r'^\d{6}$')
        self.assertRegex(payload['message'], r'(?i)5|five')
        self.assertNotIn(secret, body)
        self.assertEqual(self.business_counts(), before)

    def test_async_code_error_returns_json_and_does_not_create_demo_records(self):
        client = Client('en')
        status, body, headers = client.post('/auth/code', {'phone': 'invalid', 'purpose': 'register'}, 'application/json')
        self.assertEqual(status, 400)
        self.assertTrue(headers['Content-Type'].startswith('application/json'))
        payload = json.loads(body)
        self.assertEqual(set(payload), {'error'})
        self.assertTrue(payload['error'])
        self.assertTrue(all(value == 0 for value in self.business_counts().values()))

    def test_password_length_boundaries_and_confirmation_keep_existing_rules(self):
        cases = [('12345678', '12345678', 303), ('1' * 128, '1' * 128, 303), ('1' * 7, '1' * 7, 400), ('1' * 129, '1' * 129, 400), ('12345678', '87654321', 400)]
        client = Client('en')
        for index, (password, confirm, expected) in enumerate(cases):
            with self.subTest(length=len(password), matches=password == confirm):
                phone = str(96234010 + index)
                status, body, _ = client.post('/auth/code', {'phone': phone, 'purpose': 'register'})
                self.assertEqual(status, 200)
                code = re.search(r'class="otp-code">([0-9]{6})', body)[1]
                actual, _, _ = client.post('/register', {'phone': phone, 'name': 'Synthetic fixture', 'password': password, 'password_confirm': confirm, 'code': code})
                self.assertEqual(actual, expected)
        self.assertEqual(self.business_counts()['users'], 2)

    def test_homepage_examples_are_labeled_and_leave_database_empty(self):
        for language in ('zh', 'en'):
            client = Client(language)
            for _ in range(2):
                status, page, _ = client.request('/')
                self.assertEqual(status, 200)
                self.assertIn('data-demo-example', page)
                self.assertIn('演示示例' if language == 'zh' else 'Illustrative example', page)
                self.assertTrue(all(value == 0 for value in self.business_counts().values()))

    def test_homepage_explains_shared_website_and_independent_local_packages(self):
        for language in ('zh', 'en'):
            _, page, _ = Client(language).request('/')
            text = ' '.join(HtmlStructure(page).text)
            self.assertRegex(text, r'同一.*(?:网址|链接|服务)' if language == 'zh' else r'(?i)same shared website address')
            self.assertRegex(text, r'每台.*(?:独立|各自)|独立' if language == 'zh' else r'(?i)separate.*each computer')

    def test_event_placeholders_use_general_examples(self):
        for language in ('zh', 'en'):
            page = View(language, 'test-csrf', None).event_form()
            html = HtmlStructure(page)
            placeholders = ' '.join(attrs['placeholder'] for _, attrs, _ in html.elements if attrs.get('placeholder'))
            self.assertNotRegex(placeholders, r'(?i)奶龙|dragon|cutest|cute')
            self.assertTrue(placeholders)

    def test_get_code_javascript_uses_async_response_without_form_reset(self):
        script = (SOURCE / 'static' / 'v4.js').read_text(encoding='utf-8')
        self.assertIn('data-get-code', script)
        self.assertIn('preventDefault()', script)
        self.assertRegex(script, r'fetch\([\s\S]{0,50}/auth/code')
        self.assertIn('application/json', script)
        self.assertNotRegex(script, r'\.reset\s*\(')
        self.assertNotRegex(script, r'new\s+FormData\s*\(\s*form\s*\)')

    @unittest.skipUnless(DELIVERY_NOTE.is_file(), 'Release instructions are not included in this source copy.')
    def test_delivery_note_distinguishes_shared_server_from_local_copies(self):
        text = DELIVERY_NOTE.read_text(encoding='utf-8')
        self.assertRegex(text, r'(?i)each computer|每台电脑')
        self.assertRegex(text, r'(?i)same.*(?:link|url|server)|同一.*(?:网址|链接|服务)')
        self.assertRegex(text, r'(?i)separate|independent|独立')


if __name__ == '__main__':
    unittest.main(verbosity=2)
