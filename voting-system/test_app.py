import io
import gc
import re
import tempfile
import time
import unittest
from pathlib import Path
from urllib.parse import urlencode
import app


class Client:
    def __init__(self):
        self.cookies = {}

    def request(self, path, fields=None):
        raw = urlencode(fields or {}, doseq=True).encode()
        env = {'REQUEST_METHOD':'POST' if fields is not None else 'GET', 'PATH_INFO':path,
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


class VotingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        app.DB = Path(self.temp.name)/'test.sqlite3'
        app.init_db()
        self.owner, self.voter = Client(), Client()
        for client, phone in ((self.owner,'12345678'),(self.voter,'87654321')):
            self.assertEqual(client.post('/register',{'phone':phone,'name':'Demo','password':'demo-pass-123'})[0],303)
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
        self.assertEqual(Client().post('/register',{'phone':'12345678','name':'Other','password':'demo-pass-123'})[0],409)


if __name__ == '__main__':
    unittest.main(verbosity=2)
