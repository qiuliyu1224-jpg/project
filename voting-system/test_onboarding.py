"""New-user navigation checks against an isolated database, never desktop data."""
import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app
import entries
import time
from datetime import datetime
from test_app import Client
from ui4 import View

class OnboardingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        app.DB=Path(self.tmp.name)/'test.sqlite3'; app.init_db()
    def tearDown(self):
        gc.collect(); self.tmp.cleanup()
    def test_guest_lands_on_login_and_both_auth_pages_keep_language_control(self):
        c=Client()
        self.assertEqual(c.request('/')[2]['Location'],'/login')
        for path in ('/login','/register'):
            status,html,_=c.request(path)
            self.assertEqual(status,200);self.assertIn('data-auth-page="1"',html)
            self.assertIn('action="/language"',html);self.assertIn('<html lang="en">',html)
        c.post('/language',{'lang':'zh','next':'/register'})
        self.assertIn('<html lang="zh-CN">',c.request('/register')[1])
    def test_registration_and_login_expose_one_shot_hint_without_losing_language(self):
        c=Client('zh');self.assertEqual(c.register('88990011')[0],303)
        html=c.request('/')[1]
        self.assertIn('data-guide-hint',html);self.assertIn('<html lang="zh-CN">',html)
        self.assertIn('action="/language"',html);self.assertIn('data-auth-page="0"',html)
        self.assertNotIn('data-guide-hint',c.request('/')[1])
        c.post('/logout',{})
        self.assertEqual(c.request('/')[2]['Location'],'/login')
        self.assertEqual(c.login('88990011')[0],303)
        self.assertIn('data-guide-hint',c.request('/')[1]) # Browser suppresses repeat per account.
    def test_empty_home_and_entries_offer_practice_without_business_records(self):
        c=Client('en');c.register('88990012')
        html=c.request('/')[1]
        self.assertIn('data-voting-count="0"',html);self.assertIn('data-application-count="0"',html)
        self.assertIn('data-practice-open="voter"',html);self.assertIn('data-practice-open="entrant"',html)
        self.assertIn('data-practice-open="entrant"',c.request('/my-entries')[1])
        self.assertEqual(c.request('/static/guide.js')[0],200)
        with app.connect() as con:
            for table in ('elections','candidates','ballots','choices','preferences','images'):
                self.assertEqual(con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0],0)
    def test_other_version_identity_is_diagnostic_only_and_never_reused(self):
        import json
        from run_votelab import find_running_instance
        folder=Path(self.tmp.name);token='b'*48
        (folder/'running-instance.json').write_text(json.dumps({'application':'VoteLab','port':8765,'token':token}))
        with patch('run_votelab.build_opener') as factory:
            response=factory.return_value.open.return_value.__enter__.return_value
            response.status=200;response.read.return_value=json.dumps({'application':'VoteLab','token':token,'version':'0.4.8'}).encode()
            self.assertIsNone(find_running_instance(folder,timeout=0))
            self.assertEqual(find_running_instance(folder,timeout=0,details=True),{'address':'http://127.0.0.1:8765/','version':'0.4.8'})
            response.read.return_value=json.dumps({'application':'VoteLab','token':'wrong','version':'0.4.8'}).encode()
            self.assertIsNone(find_running_instance(folder,timeout=0,details=True))

    def test_application_deadline_has_clear_feedback_and_no_resubmit_link(self):
        owner,entrant=Client('en'),Client('en');owner.register('88990013');entrant.register('88990014')
        fields={'title':'Deadline fixture','method':'SCORE','visibility':'PUBLIC','submissions_open':'1','deadline':datetime.fromtimestamp(time.time()+86400,entries.TZ).strftime('%Y-%m-%dT%H:%M')}
        status,_,headers=owner.post('/create',fields);self.assertEqual(status,303);eid=int(headers['Location'].split('/')[2])
        self.assertEqual(owner.post(f'/e/{eid}/collect',{})[0],303)
        self.assertIn('Applications are open',entrant.request(f'/e/{eid}')[1])
        self.assertEqual(entrant.post(f'/e/{eid}/apply',{'name':'Deadline entry'})[0],303)
        with app.connect() as con:
            cid=con.execute('SELECT id FROM candidates WHERE election_id=?',(eid,)).fetchone()[0]
        self.assertEqual(owner.post(f'/e/{eid}/review',{'candidate_id':str(cid),'reason':'Please revise','verdict':'REJECTED'})[0],303)
        with app.connect() as con:
            with con:con.execute('UPDATE elections SET planned_end=? WHERE id=?',(int(time.time())-1,eid))
        page=entrant.request(f'/e/{eid}')[1]
        self.assertIn('application deadline has passed',page)
        self.assertNotIn(f'href="/e/{eid}/apply"',page)
        self.assertNotIn('Edit and resubmit',entrant.request('/my-entries')[1])
        self.assertEqual(entrant.post(f'/e/{eid}/apply',{'name':'Late entry'})[0],409)

if __name__=='__main__':unittest.main()
