"""Acceptance scenarios for review fixes, methods and safe event evolution."""
import json
import re
import time
import unittest
from datetime import datetime
import app
import entries
import voting_rules as rules
from test_app import Client, picture
import test_app as fixtures


class V4Tests(unittest.TestCase):
    setUp=fixtures.VotingTests.setUp
    tearDown=fixtures.VotingTests.tearDown
    form=fixtures.VotingTests.form
    create=fixtures.VotingTests.create
    ids=fixtures.VotingTests.ids
    open=fixtures.VotingTests.open
    counts=fixtures.VotingTests.counts
    apply=fixtures.VotingTests.apply
    submitted=fixtures.VotingTests.submitted

    def event(self,eid):
        with app.connect() as con: return rules.event_row(con.execute('SELECT * FROM elections WHERE id=?',(eid,)).fetchone())
    def result(self,eid,number=None):
        with app.connect() as con: return rules.counts(con,self.event(eid),number)
    def uid(self,phone):
        with app.connect() as con: return con.execute('SELECT id FROM users WHERE phone=?',(phone,)).fetchone()[0]
    def set_entries(self,eid,n=3):
        data=self.form(self.event(eid)['method']); data['entry_key']=[str(i) for i in range(n)]
        old=self.ids(eid)
        for i in range(n):
            data['entry_name_'+str(i)]='Entry '+str(i)
            if i<len(old): data['entry_id_'+str(i)]=str(old[i])
        self.assertEqual(self.owner.post(f'/e/{eid}/edit',data)[0],303)
        return self.ids(eid)
    def stored_ballots(self,eid,ballots):
        ev=self.event(eid)
        with app.connect() as con:
            rid=rules.current_round(con,ev)['id']
            for index,selection in enumerate(ballots):
                uid=con.execute('INSERT INTO users(phone,name,salt,password_hash) VALUES(?,?,?,?)',(f'9000{index:04d}',f'Example {index}','00'*16,'unused')).lastrowid
                bid=con.execute('INSERT INTO ballots(election_id,round_id,user_id) VALUES(?,?,?)',(eid,rid,uid)).lastrowid
                if ev['method']=='RCV': con.executemany('INSERT INTO preferences VALUES(?,?,?)',[(bid,cid,i+1) for i,cid in enumerate(selection)])
                else: con.executemany('INSERT INTO choices VALUES(?,?,?,?)',[(bid,eid,cid,value) for cid,value in selection])

    def test_multiselect_limit_and_confirmed_fields(self):
        ids=self.set_entries(self.eid,3); data=self.form(); data.update(entry_key=['0','1','2'],max_choices='3')
        for i,cid in enumerate(ids): data.update({f'entry_name_{i}':f'Entry {i}',f'entry_id_{i}':str(cid)})
        self.assertEqual(self.owner.post(f'/e/{self.eid}/edit',data)[0],303); self.open()
        status,body,_=self.voter.post(f'/e/{self.eid}/confirm',{'candidate':[str(i) for i in ids]})
        self.assertEqual(status,200); self.assertEqual(body.count('name="candidate"'),3); self.assertEqual(self.counts(),(0,0))
        self.assertEqual(self.voter.post(f'/e/{self.eid}/vote',{'candidate':[str(i) for i in ids]})[0],303)
        self.assertEqual(self.counts(),(1,3))
        self.assertEqual(self.other.post(f'/e/{self.eid}/vote',{'candidate':[str(ids[0])]*2})[0],400)

    def test_limit_exceeds_approved_count_cannot_open(self):
        data=self.form(); data['max_choices']='3'; self.owner.post(f'/e/{self.eid}/edit',data)
        self.assertEqual(self.owner.post(f'/e/{self.eid}/open',{})[0],400)

    def test_optional_zero_and_average_without_missing_zero(self):
        eid=self.create('SCORE'); a,b=self.ids(eid); self.open(eid)
        self.assertEqual(self.voter.post(f'/e/{eid}/vote',{f'score_{a}':'0'})[0],303)
        self.assertEqual(self.other.post(f'/e/{eid}/vote',{f'score_{a}':'5',f'score_{b}':'4'})[0],303)
        results={r['id']:r for r in self.result(eid)['rows']}
        self.assertEqual((results[a]['average'],results[a]['n']),(2.5,2)); self.assertEqual((results[b]['average'],results[b]['n']),(4,1))
        self.owner.post(f'/e/{eid}/close',{}); body=self.owner.request(f'/e/{eid}/results')[1]
        self.assertIn('4.00 / 5',body); self.assertIn('人评分',body)

    def test_unrated_entry_not_treated_as_zero(self):
        eid=self.create('SCORE'); a,b=self.ids(eid); self.open(eid)
        self.voter.post(f'/e/{eid}/vote',{f'score_{a}':'0'})
        result=self.result(eid); self.assertEqual(result['rows'][0]['id'],a); self.assertIsNone(result['rows'][1]['average'])

    def test_rcv_validation_and_saved_rank(self):
        eid=self.create('RCV'); a,b=self.ids(eid); self.open(eid)
        for data in ({},{f'rank_{a}':'2'},{f'rank_{a}':'1',f'rank_{b}':'1'},{f'rank_{a}':'1.5'}): self.assertEqual(self.voter.post(f'/e/{eid}/vote',data)[0],400)
        self.assertEqual(self.voter.post(f'/e/{eid}/confirm',{f'rank_{a}':'1'})[0],200)
        self.assertEqual(self.voter.post(f'/e/{eid}/vote',{f'rank_{a}':'1'})[0],303)
        self.assertEqual(self.result(eid)['winner'],a)
        self.assertIn(f'name="rank_{a}" disabled',self.voter.request(f'/e/{eid}')[1])

    def test_rcv_transfer_and_exhaustion(self):
        eid=self.create('RCV'); a,b,c=self.set_entries(eid); self.open(eid)
        self.stored_ballots(eid,[[a,b],[a,b],[b,a],[b,a],[c,a]])
        result=self.result(eid); self.assertEqual(result['winner'],a); self.assertEqual(len(result['rounds']),2)
        self.assertEqual(result['rounds'][0]['eliminated'],c); self.assertEqual(result['rounds'][1]['counts'][a],3)

    def test_rcv_lowest_tie_not_randomly_eliminated(self):
        eid=self.create('RCV'); a,b,c=self.set_entries(eid); self.open(eid)
        self.stored_ballots(eid,[[a],[a],[b],[c]])
        result=self.result(eid); self.assertEqual(result['state'],'ELIMINATION_TIE'); self.assertEqual(result['tied'],[b,c]); self.assertIsNone(result['winner'])

    def test_rcv_empty_and_exhausted_preferences(self):
        eid=self.create('RCV'); a,b,c=self.set_entries(eid); self.open(eid)
        self.assertEqual(self.result(eid)['state'],'NO_ACTIVE_BALLOTS')
        self.stored_ballots(eid,[[a],[a],[a],[b],[b],[c]])
        result=self.result(eid); self.assertEqual(result['rounds'][1]['exhausted'],1); self.assertEqual(result['winner'],a)

    def test_majority_rounds_are_separate_and_require_new_votes(self):
        eid=self.create('MAJORITY'); a,b,c=self.set_entries(eid); self.open(eid)
        self.stored_ballots(eid,[[(a,1)]]*4+[[(b,1)]]*3+[[(c,1)]]*2)
        self.owner.post(f'/e/{eid}/close',{}); self.assertEqual(self.result(eid)['state'],'RUNOFF_REQUIRED')
        self.assertEqual(self.owner.post(f'/e/{eid}/publish',{})[0],409)
        deadline=self.form()['deadline']; self.assertEqual(self.owner.post(f'/e/{eid}/next-round',{'deadline':deadline})[0],303)
        self.assertEqual(self.result(eid)['ballots'],0); self.assertEqual(self.result(eid,1)['ballots'],9)
        self.assertEqual(self.voter.post(f'/e/{eid}/vote',{'candidate':str(c)})[0],400)
        self.assertEqual(self.voter.post(f'/e/{eid}/vote',{'candidate':str(a)})[0],303)
        self.assertEqual(self.result(eid)['winner'],a)

    def test_majority_cutoff_tie_and_no_votes_do_not_start_runoff(self):
        eid=self.create('MAJORITY'); a,b,c=self.set_entries(eid); self.open(eid)
        self.stored_ballots(eid,[[(a,1)]]*2+[[(b,1)],[(c,1)]])
        self.owner.post(f'/e/{eid}/close',{}); self.assertEqual(self.result(eid)['state'],'CUTOFF_TIE')
        self.assertEqual(self.owner.post(f'/e/{eid}/next-round',{'deadline':self.form()['deadline']})[0],409)

    def test_rejection_resubmit_and_pending_done_tabs(self):
        eid=self.create(accepting=True,empty=True); self.owner.post(f'/e/{eid}/collect',{}); self.apply(eid)
        row=self.submitted(eid); data={'candidate_id':str(row['id']),'verdict':'REJECTED','reason':'Please explain the entry'}
        self.owner.post(f'/e/{eid}/review',data)
        self.assertNotIn('Applicant',self.owner.request(f'/e/{eid}/review')[1]); self.assertIn('Applicant',self.owner.request(f'/e/{eid}/review?tab=done')[1])
        self.assertIn('Please explain the entry',self.voter.request(f'/e/{eid}/apply')[1])
        self.assertEqual(self.voter.post(f'/e/{eid}/apply',{'name':'Revised','description':'Updated explanation'})[0],303)
        self.assertEqual(self.submitted(eid)['id'],row['id']); self.assertEqual(self.submitted(eid)['review_status'],'PENDING')

    def test_invitation_protects_votes_results_and_images(self):
        data=self.form(); data['invite_code']='group-only-123'
        status,_,headers=self.owner.post('/create',data,{'entry_image_a':picture()}); self.assertEqual(status,303); eid=int(headers['Location'].split('/')[2]); self.open(eid)
        image=self.submitted(eid)['image_id']; a=self.ids(eid)[0]
        self.assertIn('此活动需要邀请码',self.voter.request(f'/e/{eid}')[1]); self.assertEqual(self.voter.request('/media/'+image)[0],404)
        self.assertEqual(self.voter.post(f'/e/{eid}/vote',{'candidate':str(a)})[0],403)
        self.assertEqual(self.voter.post(f'/e/{eid}/access',{'invite_code':'wrong'})[0],403)
        self.assertEqual(self.voter.post(f'/e/{eid}/access',{'invite_code':'group-only-123'})[0],303)
        self.assertEqual(self.voter.request('/media/'+image)[0],200); self.assertEqual(self.voter.post(f'/e/{eid}/vote',{'candidate':str(a)})[0],303)

    def test_pause_text_changes_retain_votes_and_resume(self):
        self.open(); ids=self.ids(); self.voter.post(f'/e/{self.eid}/vote',{'candidate':str(ids[0])})
        self.assertEqual(self.owner.post(f'/e/{self.eid}/pause',{})[0],303)
        self.assertEqual(self.other.post(f'/e/{self.eid}/vote',{'candidate':str(ids[0])})[0],409)
        data=self.form(); data.update(entry_id_a=str(ids[0]),entry_id_b=str(ids[1]),title='Updated title',announcement='Clarified the title')
        self.assertEqual(self.owner.post(f'/e/{self.eid}/revision',data)[0],303)
        self.assertEqual(self.event(self.eid)['current_round'],1); self.assertEqual(self.result(self.eid)['ballots'],1)
        self.assertEqual(self.owner.post(f'/e/{self.eid}/resume',{})[0],303)
        self.assertEqual(self.other.post(f'/e/{self.eid}/vote',{'candidate':str(ids[1])})[0],303)

    def test_image_replacement_creates_round_and_rejects_stale_ballot(self):
        self.open(); ids=self.ids(); self.voter.post(f'/e/{self.eid}/vote',{'candidate':str(ids[0])})
        with app.connect() as con: old=rules.current_round(con,self.event(self.eid))['id']
        self.owner.post(f'/e/{self.eid}/pause',{})
        data=self.form(); data.update(entry_id_a=str(ids[0]),entry_id_b=str(ids[1]),announcement='Replaced the entry image')
        self.assertEqual(self.owner.post(f'/e/{self.eid}/revision',data,{'entry_image_a':picture('blue')})[0],303)
        self.assertEqual(self.event(self.eid)['current_round'],2); self.assertEqual(self.result(self.eid)['ballots'],0); self.assertEqual(self.result(self.eid,1)['ballots'],1)
        self.owner.post(f'/e/{self.eid}/resume',{})
        self.assertEqual(self.other.post(f'/e/{self.eid}/vote',{'candidate':str(ids[0]),'round_id':str(old)})[0],409)
        self.assertEqual(self.voter.post(f'/e/{self.eid}/vote',{'candidate':str(ids[0])})[0],303)

    def test_revision_needs_notice_and_limits_three(self):
        self.open(); ids=self.ids(); data=self.form(); data.update(entry_id_a=str(ids[0]),entry_id_b=str(ids[1]))
        self.owner.post(f'/e/{self.eid}/pause',{}); self.assertEqual(self.owner.post(f'/e/{self.eid}/revision',data)[0],400)
        data['announcement']='Clarified description'
        for _ in range(3): self.assertEqual(self.owner.post(f'/e/{self.eid}/revision',data)[0],303)
        self.assertEqual(self.owner.post(f'/e/{self.eid}/revision',data)[0],409)
        self.owner.post(f'/e/{self.eid}/resume',{}); self.assertEqual(self.owner.post(f'/e/{self.eid}/pause',{})[0],409)

    def test_status_refresh_closes_without_manual_close(self):
        self.open()
        with app.connect() as con: con.execute('UPDATE elections SET ends_at=?,paused=1 WHERE id=?',(int(time.time())-1,self.eid))
        status,body,_=self.voter.request(f'/e/{self.eid}/status'); self.assertEqual(status,200); self.assertEqual(json.loads(body)['status'],'CLOSED'); self.assertEqual(json.loads(body)['paused'],0)

    def test_password_reset_invalidates_old_session(self):
        guest=Client(); code=guest.code('87654321','reset'); data={'phone':'87654321','password':'New-password123','password_confirm':'New-password123','code':code}
        self.assertEqual(guest.post('/reset',data)[0],303); self.assertEqual(self.voter.request('/my-entries')[0],401)
        self.assertEqual(Client().login('87654321')[0],401); self.assertEqual(Client().post('/login',{'phone':'87654321','password':'New-password123'})[0],303)
        self.assertEqual(guest.post('/reset',data)[0],400)

    def test_country_format_and_error_actions(self):
        guest=Client(); self.assertEqual(guest.post('/auth/code',{'phone':'123','country':'86','purpose':'register'})[0],400)
        self.assertEqual(guest.post('/auth/code',{'phone':'13800000000','country':'86','purpose':'register'})[0],200)
        status,body,_=guest.request('/create'); self.assertEqual(status,401); self.assertIn('登录账号',body)
        self.assertNotIn('上传失败时',body)
        self.assertIn(f'V{self.eid:06d}',self.owner.request('/dashboard')[1])

    def test_background_deadline_task_and_idempotent_migration(self):
        from maintenance import start_maintenance
        self.open()
        with app.connect() as con: con.execute('UPDATE elections SET ends_at=? WHERE id=?',(int(time.time())-1,self.eid))
        stop,worker=start_maintenance(interval=0.02)
        try:
            deadline=time.monotonic()+2
            while self.event(self.eid)['status']!='CLOSED' and time.monotonic()<deadline: time.sleep(0.02)
            self.assertEqual(self.event(self.eid)['status'],'CLOSED')
        finally: stop.set(); worker.join(timeout=2)
        app.init_db(); app.init_db()
        self.assertEqual(self.event(self.eid)['title'],'Test event')

    def test_old_required_scoring_is_not_silently_reinterpreted(self):
        eid=self.create('SCORE'); a,b=self.ids(eid)
        with app.connect() as con: con.execute('UPDATE elections SET score_optional=0 WHERE id=?',(eid,))
        self.open(eid)
        self.assertEqual(self.voter.post(f'/e/{eid}/vote',{f'score_{a}':'5'})[0],400)
        self.assertEqual(self.voter.post(f'/e/{eid}/vote',{f'score_{a}':'5',f'score_{b}':'0'})[0],303)

    def test_password_login_attempt_limit(self):
        guest=Client()
        for _ in range(10): self.assertEqual(guest.post('/login',{'phone':'87654321','password':'wrong'})[0],401)
        self.assertEqual(guest.login('87654321')[0],429)

    def test_participant_removal_starts_new_round_and_keeps_old_ballot(self):
        eid=self.create(accepting=True); self.owner.post(f'/e/{eid}/collect',{}); self.apply(eid)
        with app.connect() as con: c=con.execute("SELECT * FROM candidates WHERE election_id=? AND review_status='PENDING'",(eid,)).fetchone()
        self.owner.post(f'/e/{eid}/review',{'candidate_id':str(c['id']),'verdict':'APPROVED','reason':''}); self.open(eid)
        self.voter.post(f'/e/{eid}/vote',{'candidate':str(c['id'])}); self.owner.post(f'/e/{eid}/pause',{})
        ids=[cid for cid in self.ids(eid) if cid!=c['id']]
        data=self.form(accepting=True); data.update(entry_id_a=str(ids[0]),entry_id_b=str(ids[1]),announcement='Removed an entry; voting restarts',exclude_candidate=[str(c['id'])])
        self.assertEqual(self.owner.post(f'/e/{eid}/revision',data)[0],303)
        self.assertNotIn(c['id'],[r['id'] for r in self.result(eid)['rows']]); old=self.result(eid,1)
        self.assertEqual(old['ballots'],1); self.assertEqual(next(r['total'] for r in old['rows'] if r['id']==c['id']),1)
        with app.connect() as con: self.assertEqual(con.execute('SELECT COUNT(*) FROM event_changes WHERE election_id=?',(eid,)).fetchone()[0],1)


if __name__=='__main__': unittest.main()
