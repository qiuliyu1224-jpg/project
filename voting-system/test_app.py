import io
import gc
import re
import tempfile
import time
import unittest
from pathlib import Path
from urllib.parse import urlencode, urlsplit
import app


class Client:
    def __init__(self):
        self.cookies = {}

    def request(self, path, fields=None):
        raw = urlencode(fields or {}, doseq=True).encode()
        url=urlsplit(path)
        env = {'REQUEST_METHOD':'POST' if fields is not None else 'GET', 'PATH_INFO':url.path,'QUERY_STRING':url.query,
               'CONTENT_LENGTH':str(len(raw)), 'wsgi.input':io.BytesIO(raw),
               'HTTP_COOKIE':'; '.join(k+'='+v for k,v in self.cookies.items())}
        meta = {}
        def start(status, headers):
            meta.update(status=int(status.split()[0]), headers=dict(headers))
            for k,v in headers:
                if k == 'Set-Cookie':
                    name,value = v.split(';')[0].split('=',1)
                    self.cookies[name] = value
        body = b''.join(app.app(env,start)).decode()
        return meta['status'], body, meta['headers']

    def post(self, path, fields):
        _, body, _ = self.request('/login')
        csrf = re.search(r'name="csrf" value="([a-f0-9]+)"',body)[1]
        return self.request(path,{**fields,'csrf':csrf})

    def register(self, phone, name='Demo', role='VOTER'):
        status,body,_=self.post('/auth/code',{'phone':phone,'purpose':'register','role':role})
        if status != 200: return status,body,{}
        code=re.search(r'class="otp-code">([0-9]{6})',body)[1]
        return self.post('/register',{'phone':phone,'name':name,'password':'demo-pass-123','role':role,'code':code})


class VotingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        app.DB = Path(self.temp.name)/'test.sqlite3'
        app.init_db()
        self.owner, self.voter = Client(), Client()
        for client, phone in ((self.owner,'12345678'),(self.voter,'87654321')):
            self.assertEqual(client.register(phone,role='MANAGER' if client is self.owner else 'VOTER')[0],303)
        self.eid = self.create()

    def tearDown(self):
        gc.collect()
        self.temp.cleanup()

    def create(self, method='SINGLE', visibility='PUBLIC'):
        status, _, headers = self.owner.post('/create',{'title':'Test event','method':method,
            'visibility':visibility,'candidates':'Alpha\nBeta','duration':'60'})
        self.assertEqual(status,303)
        return int(headers['Location'].split('/')[2])

    def open(self, eid=None):
        eid = eid or self.eid
        self.assertEqual(self.owner.post(f'/e/{eid}/open',{})[0],303)

    def ids(self,eid=None):
        with app.connect() as con:
            return [r[0] for r in con.execute('SELECT id FROM candidates WHERE election_id=?',(eid or self.eid,))]

    def test_preview_has_no_ballot_and_cannot_vote(self):
        self.assertIn('PREVIEW',self.owner.request(f'/e/{self.eid}/preview')[1])
        self.assertEqual(self.voter.post(f'/e/{self.eid}/vote',{'candidate':str(self.ids()[0])})[0],400)
        with app.connect() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM ballots').fetchone()[0],0)

    def test_single_vote_persists_and_duplicate_rejected(self):
        self.open()
        payload = {'candidate':str(self.ids()[0])}
        self.assertEqual(self.voter.post(f'/e/{self.eid}/vote',payload)[0],303)
        self.assertIn('ALREADY_VOTED',self.voter.post(f'/e/{self.eid}/vote',payload)[1])
        with app.connect() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM ballots').fetchone()[0],1)
            self.assertEqual(app.get_results(con,self.eid)[0]['total'],1)

    def test_foreign_candidate_and_multiple_choices_rejected(self):
        other = self.create()
        self.open()
        self.assertEqual(self.voter.post(f'/e/{self.eid}/vote',{'candidate':str(self.ids(other)[0])})[0],400)
        self.assertEqual(self.voter.post(f'/e/{self.eid}/vote',{'candidate':[str(i) for i in self.ids()]})[0],400)

    def test_score_zero_is_valid_missing_and_out_of_range_are_not(self):
        eid = self.create('SCORE')
        self.open(eid)
        a,b = self.ids(eid)
        for data in ({f'score_{a}':'0'}, {f'score_{a}':'0',f'score_{b}':'6'},
                     {f'score_{a}':'1.5',f'score_{b}':'3'}):
            self.assertEqual(self.voter.post(f'/e/{eid}/vote',data)[0],400)
        self.assertEqual(self.voter.post(f'/e/{eid}/vote',{f'score_{a}':'0',f'score_{b}':'5'})[0],303)
        body=self.voter.request(f'/e/{eid}')[1]
        self.assertIn(f'name="score_{a}" value="0" checked disabled',body)
        self.assertIn(f'name="score_{b}" value="5" checked disabled',body)
        with app.connect() as con:
            self.assertEqual([r['total'] for r in app.get_results(con,eid)],[5,0])
            self.assertEqual(con.execute('SELECT COUNT(*) FROM ballots').fetchone()[0],1)

    def test_deadline_rejects_vote_without_browser_refresh(self):
        self.open()
        with app.connect() as con:
            con.execute('UPDATE elections SET ends_at=? WHERE id=?',(int(time.time())-1,self.eid))
        self.assertIn('ELECTION_CLOSED',self.voter.post(f'/e/{self.eid}/vote',{'candidate':str(self.ids()[0])})[1])
        with app.connect() as con:
            self.assertEqual(con.execute('SELECT status FROM elections WHERE id=?',(self.eid,)).fetchone()[0],'CLOSED')

    def test_results_wait_for_closure_and_publication(self):
        self.open()
        self.assertEqual(self.owner.request(f'/e/{self.eid}/results')[0],403)
        self.owner.post(f'/e/{self.eid}/close',{})
        self.assertEqual(self.owner.request(f'/e/{self.eid}/results')[0],200)
        self.assertEqual(self.voter.request(f'/e/{self.eid}/results')[0],403)
        self.owner.post(f'/e/{self.eid}/publish',{})
        self.assertEqual(Client().request(f'/e/{self.eid}/results')[0],200)

    def test_private_results_stay_private_after_publication(self):
        eid = self.create(visibility='PRIVATE')
        self.open(eid)
        self.owner.post(f'/e/{eid}/close',{})
        self.owner.post(f'/e/{eid}/publish',{})
        self.assertEqual(self.voter.request(f'/e/{eid}/results')[0],403)
        self.assertEqual(self.owner.request(f'/e/{eid}/results')[0],200)

    def test_unauthorized_lifecycle_and_draft_access(self):
        self.assertEqual(self.voter.request(f'/e/{self.eid}/preview')[0],403)
        self.assertEqual(self.voter.post(f'/e/{self.eid}/open',{})[0],403)
        self.open()
        self.assertEqual(self.voter.post(f'/e/{self.eid}/close',{})[0],403)
        self.assertEqual(Client().post(f'/e/{self.eid}/vote',{'candidate':'1'})[0],401)

    def test_csrf_required_and_logout_invalidates_session(self):
        self.assertEqual(self.owner.request('/create',{'title':'X'})[0],403)
        self.assertEqual(self.owner.post('/logout',{})[0],303)
        self.assertEqual(self.owner.request('/create')[0],401)

    def test_failed_save_rolls_back_all_data(self):
        self.open()
        with app.connect() as con:
            con.execute("CREATE TRIGGER fail_choice BEFORE INSERT ON choices BEGIN SELECT RAISE(ABORT,'test failure'); END")
        self.assertEqual(self.voter.post(f'/e/{self.eid}/vote',{'candidate':str(self.ids()[0])})[0],409)
        with app.connect() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM ballots').fetchone()[0],0)
            self.assertEqual(con.execute('SELECT COUNT(*) FROM choices').fetchone()[0],0)
            con.execute('DROP TRIGGER fail_choice')
        self.assertEqual(self.voter.post(f'/e/{self.eid}/vote',{'candidate':str(self.ids()[0])})[0],303)

    def test_html_escaped(self):
        with app.connect() as con:
            con.execute('UPDATE elections SET title=? WHERE id=?',('<script>alert(1)</script>',self.eid))
        body = self.owner.request(f'/e/{self.eid}')[1]
        self.assertNotIn('<script>',body)
        self.assertIn('&lt;script&gt;',body)

    def test_login_wrong_password_and_existing_account(self):
        self.assertEqual(Client().post('/login',{'phone':'12345678','password':'wrong-pass'})[0],401)
        self.assertEqual(Client().register('12345678',name='Other')[0],409)

    def test_voter_cannot_create_and_login_cannot_change_role(self):
        self.assertEqual(self.voter.request('/create')[0],403)
        self.assertEqual(self.voter.post('/create',{'title':'Forged'})[0],403)
        self.assertEqual(Client().post('/login',{'phone':'87654321','password':'demo-pass-123','role':'MANAGER'})[0],403)
        self.open()
        self.assertEqual(self.owner.post(f'/e/{self.eid}/vote',{'candidate':str(self.ids()[0])})[0],403)

    def test_registration_requires_code_and_code_is_one_use(self):
        guest=Client()
        payload={'phone':'11112222','password':'demo-pass-123','name':'Guest','role':'VOTER'}
        self.assertEqual(guest.post('/register',payload)[0],400)
        status,body,_=guest.post('/auth/code',{'phone':'11112222','purpose':'register'})
        self.assertEqual(status,200)
        code=re.search(r'class="otp-code">([0-9]{6})',body)[1]
        self.assertEqual(guest.post('/register',{**payload,'code':code})[0],303)
        self.assertEqual(guest.post('/register',{**payload,'code':code})[0],400)

    def test_code_cooldown_expiry_attempt_limit_and_browser_binding(self):
        guest=Client()
        fields={'phone':'87654321','purpose':'login'}
        _,body,_=guest.post('/auth/code',fields)
        code=re.search(r'class="otp-code">([0-9]{6})',body)[1]
        self.assertEqual(guest.post('/auth/code',fields)[0],429)
        self.assertEqual(Client().post('/login',{'phone':'87654321','code':code,'login_method':'code'})[0],400)
        wrong='000000' if code!='000000' else '111111'
        for _ in range(5): self.assertEqual(guest.post('/login',{'phone':'87654321','code':wrong,'login_method':'code'})[0],400)
        self.assertEqual(guest.post('/login',{'phone':'87654321','code':code,'login_method':'code'})[0],400)
        with app.connect() as con: con.execute('UPDATE verification_codes SET attempts=0,expires=?',(int(time.time())-1,))
        self.assertEqual(guest.post('/login',{'phone':'87654321','code':code,'login_method':'code'})[0],400)

    def test_code_login_success(self):
        guest=Client()
        _,body,_=guest.post('/auth/code',{'phone':'87654321','purpose':'login'})
        code=re.search(r'class="otp-code">([0-9]{6})',body)[1]
        self.assertEqual(guest.post('/login',{'phone':'87654321','code':code,'login_method':'code','role':'VOTER'})[0],303)
        self.assertEqual(guest.request('/my-votes')[0],200)

    def test_draft_edit_and_published_lock(self):
        data={'title':'Updated event','method':'SCORE','visibility':'PRIVATE','duration':'30','candidates':'New A\nNew B\nNew C'}
        self.assertEqual(self.owner.post(f'/e/{self.eid}/edit',data)[0],303)
        self.assertEqual(len(self.ids()),3)
        body=self.owner.request(f'/e/{self.eid}/preview')[1]
        self.assertIn('Updated event',body)
        self.assertIn('New C',body)
        self.open()
        self.assertEqual(self.owner.post(f'/e/{self.eid}/edit',data)[0],409)

    def test_confirmation_does_not_save_until_final_submit(self):
        self.open()
        data={'candidate':str(self.ids()[0])}
        self.assertEqual(self.voter.post(f'/e/{self.eid}/confirm',data)[0],200)
        with app.connect() as con: self.assertEqual(con.execute('SELECT COUNT(*) FROM ballots').fetchone()[0],0)
        self.assertEqual(self.voter.post(f'/e/{self.eid}/vote',data)[0],303)

    def test_assets_search_and_password_toggle_controls(self):
        self.assertEqual(self.voter.request('/static/style.css')[0],200)
        self.assertEqual(self.voter.request('/static/app.js')[0],200)
        self.assertIn('data-password',Client().request('/login')[1])
        self.open()
        self.assertIn('data-search',self.voter.request('/')[1])
        self.assertNotIn('Test event',self.voter.request('/?status=CLOSED')[1])


if __name__ == '__main__':
    unittest.main(verbosity=2)
