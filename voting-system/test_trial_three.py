"""Third-trial acceptance checks using isolated databases and sessions."""
import time
import unittest
from unittest.mock import patch
import re
import app
from test_app import Client
import test_app as fixtures


class ThirdTrialTests(unittest.TestCase):
    setUp=fixtures.VotingTests.setUp
    tearDown=fixtures.VotingTests.tearDown
    form=fixtures.VotingTests.form
    create=fixtures.VotingTests.create
    ids=fixtures.VotingTests.ids
    open=fixtures.VotingTests.open

    def test_fresh_and_invalid_language_default_to_english(self):
        guest=Client()
        for path in ('/','/login','/register','/reset'):
            status,html,_=guest.request(path)
            self.assertEqual(status,200)
            self.assertIn('<html lang="en">',html)
        guest.cookies['lang']='invalid'
        self.assertIn('<html lang="en">',guest.request('/')[1])
        guest.cookies['lang']='zh'
        self.assertIn('<html lang="zh-CN">',guest.request('/')[1])

    def test_auto_publication_and_three_charts_leave_ballots_unchanged(self):
        self.open()
        self.assertEqual(self.voter.post(f'/e/{self.eid}/vote',{'candidate':str(self.ids()[0])})[0],303)
        with app.connect() as con:
            con.execute('UPDATE elections SET ends_at=? WHERE id=?',(int(time.time())-1,self.eid))
        self.assertEqual(self.voter.request(f'/e/{self.eid}/results')[0],200)
        for kind in ('bar','horizontal','line'):
            status,html,_=self.voter.request(f'/e/{self.eid}/results?chart={kind}')
            self.assertEqual(status,200)
            self.assertIn('<svg',html)
            self.assertIn('Generate statistics chart',Client('en').request(f'/e/{self.eid}/results')[1])
        with app.connect() as con:
            row=con.execute('SELECT status,published FROM elections WHERE id=?',(self.eid,)).fetchone()
            self.assertEqual(tuple(row),('CLOSED',1))
            self.assertEqual(con.execute('SELECT COUNT(*) FROM ballots').fetchone()[0],1)
        self.assertEqual(self.voter.request(f'/e/{self.eid}/results?chart=script')[0],400)

    def test_private_and_invite_results_cannot_bypass_access_with_chart(self):
        eid=self.create(visibility='PRIVATE'); self.open(eid)
        self.owner.post(f'/e/{eid}/close',{})
        self.assertEqual(self.owner.request(f'/e/{eid}/results?chart=bar')[0],200)
        self.assertEqual(self.voter.request(f'/e/{eid}/results?chart=line')[0],403)
        data=self.form(); data['invite_code']='test-code-only'
        _,_,headers=self.owner.post('/create',data)
        invited=int(headers['Location'].split('/')[2]); self.open(invited)
        self.owner.post(f'/e/{invited}/close',{})
        status,html,_=self.voter.request(f'/e/{invited}/results?chart=bar')
        self.assertEqual(status,200)
        self.assertIn('href="/"',html)
        self.assertIn(f'action="/e/{invited}/access"',html)
        self.assertNotIn('<svg',html)

    def test_switch_account_revokes_only_current_session_and_preserves_data(self):
        old=self.owner.cookies['session']
        with app.connect() as con:
            uid=con.execute('SELECT user_id FROM sessions WHERE token=?',(old,)).fetchone()[0]
            con.execute('INSERT INTO sessions VALUES(?,?,?)',('another-device-session',uid,int(time.time())+1000))
        status,_,headers=self.owner.post('/switch-account',{})
        self.assertEqual((status,headers['Location']),(303,'/login'))
        with app.connect() as con:
            self.assertIsNone(con.execute('SELECT 1 FROM sessions WHERE token=?',(old,)).fetchone())
            self.assertIsNotNone(con.execute('SELECT 1 FROM sessions WHERE token=?',('another-device-session',)).fetchone())
            self.assertIsNotNone(con.execute('SELECT 1 FROM elections WHERE id=?',(self.eid,)).fetchone())
        self.assertEqual(self.owner.request('/dashboard')[0],401)
        self.assertEqual(self.owner.login('87654321')[0],303)
        self.assertEqual(self.owner.request(f'/e/{self.eid}/edit')[0],403)

    def test_creation_has_back_and_majority_limit_hidden(self):
        status,html,_=self.owner.request('/create')
        self.assertEqual(status,200)
        self.assertIn('href="/dashboard"',html)
        eid=self.create('MAJORITY')
        html=self.owner.request(f'/e/{eid}/edit')[1]
        self.assertRegex(html,r'data-choice-limit\s+hidden')
        self.assertRegex(html,r'name="max_choices"[^>]*disabled')

    def test_translation_endpoint_uses_signed_visible_text_and_caches(self):
        with app.connect() as con:
            con.execute('UPDATE elections SET title=? WHERE id=?',('校园摄影作品评选',self.eid))
        self.owner.cookies['lang']='en'
        html=self.owner.request(f'/e/{self.eid}/preview')[1]
        token=re.search(r'data-translation-token="([^"]+)"',html)[1]
        with patch('translation._request',return_value='Campus photography competition') as request:
            for _ in range(2):
                status,body,_=self.owner.post('/translate',{'token':token})
                self.assertEqual(status,200)
                self.assertIn('Campus photography competition',body)
            self.assertEqual(request.call_count,1)
            self.assertEqual(self.other.post('/translate',{'token':token})[0],403)
            self.owner.post('/switch-account',{})
            self.assertEqual(self.owner.post('/translate',{'token':token})[0],403)
        with app.connect() as con:
            self.assertEqual(con.execute('SELECT title FROM elections WHERE id=?',(self.eid,)).fetchone()[0],'校园摄影作品评选')


if __name__=='__main__': unittest.main()
