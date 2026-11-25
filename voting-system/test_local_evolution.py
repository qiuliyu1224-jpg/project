"""Local-only upgrade, export, recovery and fair revote acceptance scenarios."""
import csv
import gc
import io
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from xml.etree import ElementTree
import app
import exports
import storage
import voting_rules as rules
from local_tools import LocalTools
from test_app import Client
import test_app as fixtures
import test_v4 as v4


class EvolutionTests(unittest.TestCase):
    setUp=fixtures.VotingTests.setUp
    tearDown=fixtures.VotingTests.tearDown
    form=fixtures.VotingTests.form
    create=fixtures.VotingTests.create
    ids=fixtures.VotingTests.ids
    open=fixtures.VotingTests.open
    event=v4.V4Tests.event
    result=v4.V4Tests.result
    set_entries=v4.V4Tests.set_entries
    stored_ballots=v4.V4Tests.stored_ballots

    def revote(self,eid,**changes):
        with app.connect() as con: rid=rules.current_round(con,self.event(eid))['id']
        fields={'round_id':str(rid),'reason':'Retest the tied result fairly','acknowledge':'1','deadline':self.form()['deadline']}
        return self.owner.post(f'/e/{eid}/revote',{**fields,**changes})

    def test_majority_cutoff_includes_everyone_at_boundary_and_then_resolves(self):
        eid=self.create('MAJORITY'); a,b,c=self.set_entries(eid); self.open(eid)
        self.stored_ballots(eid,[[(a,1)]]*2+[[(b,1)],[(c,1)]])
        self.owner.post(f'/e/{eid}/close',{})
        self.assertEqual(self.result(eid)['state'],'CUTOFF_TIE')
        self.assertEqual(self.revote(eid)[0],303)
        self.assertEqual(self.result(eid)['ballots'],0)
        self.assertEqual({r['id'] for r in self.result(eid)['rows']},{a,b,c})
        self.assertEqual(self.voter.post(f'/e/{eid}/vote',{'candidate':str(b)})[0],303)
        self.assertEqual(self.result(eid)['winner'],b)
        self.assertEqual(self.result(eid,1)['ballots'],4)

    def test_majority_revote_without_majority_can_require_top_two_again(self):
        eid=self.create('MAJORITY'); a,b,c=self.set_entries(eid); self.open(eid)
        self.stored_ballots(eid,[[(a,1)],[(b,1)],[(c,1)]])
        self.owner.post(f'/e/{eid}/close',{}); self.revote(eid)
        # Reuse the existing fixture voters, which may vote once in this new round.
        with app.connect() as con:
            rid=rules.current_round(con,self.event(eid))['id']
            uids=[r[0] for r in con.execute('SELECT id FROM users ORDER BY id')]
            for uid,cid in zip(uids,[a,a,a,b,b,c]):
                bid=con.execute('INSERT INTO ballots(election_id,round_id,user_id) VALUES(?,?,?)',(eid,rid,uid)).lastrowid
                con.execute('INSERT INTO choices VALUES(?,?,?,1)',(bid,eid,cid))
        self.owner.post(f'/e/{eid}/close',{})
        self.assertEqual(self.result(eid)['state'],'RUNOFF_REQUIRED')
        self.assertEqual(self.owner.post(f'/e/{eid}/next-round',{'deadline':self.form()['deadline']})[0],303)
        self.assertEqual(self.event(eid)['current_round'],3)

    def test_final_tie_has_fresh_ballots_and_stale_form_is_rejected(self):
        eid=self.create('MAJORITY'); a,b=self.ids(eid); self.open(eid)
        self.voter.post(f'/e/{eid}/vote',{'candidate':str(a)}); self.other.post(f'/e/{eid}/vote',{'candidate':str(b)})
        self.owner.post(f'/e/{eid}/close',{})
        with app.connect() as con: old=rules.current_round(con,self.event(eid))['id']
        self.assertEqual(self.result(eid)['state'],'FINAL_TIE')
        self.assertEqual(self.revote(eid)[0],303)
        self.assertEqual(self.revote(eid,round_id=str(old))[0],409)
        self.assertEqual(self.voter.post(f'/e/{eid}/vote',{'candidate':str(a),'round_id':str(old)})[0],409)
        self.assertEqual(self.voter.post(f'/e/{eid}/vote',{'candidate':str(a)})[0],303)
        self.assertEqual(self.result(eid,1)['ballots'],2)
        with app.connect() as con:
            self.assertEqual(con.execute("SELECT kind FROM event_changes WHERE election_id=?",(eid,)).fetchone()[0],'TIE_REVOTE')

    def test_rcv_lowest_tie_restarts_whole_roster_without_random_elimination(self):
        eid=self.create('RCV'); a,b,c=self.set_entries(eid); self.open(eid)
        self.stored_ballots(eid,[[a],[a],[b],[c]]); self.owner.post(f'/e/{eid}/close',{})
        self.assertEqual(self.result(eid)['state'],'ELIMINATION_TIE')
        self.assertEqual(self.revote(eid)[0],303)
        self.assertEqual({r['id'] for r in self.result(eid)['rows']},{a,b,c})
        self.assertEqual(self.result(eid,1)['rounds'][0]['counts'],{a:2,b:1,c:1})

    def test_choice_tie_only_includes_joint_leaders(self):
        a,b,c=self.set_entries(self.eid); self.open()
        self.stored_ballots(self.eid,[[(a,1)],[(b,1)]])
        self.owner.post(f'/e/{self.eid}/close',{}); self.assertEqual(self.revote(self.eid)[0],303)
        self.assertEqual({r['id'] for r in self.result(self.eid)['rows']},{a,b})
        self.assertEqual(self.voter.post(f'/e/{self.eid}/vote',{'candidate':str(c)})[0],400)

    def test_score_tie_uses_average_and_does_not_treat_skipped_as_zero(self):
        eid=self.create('SCORE'); a,b,c=self.set_entries(eid); self.open(eid)
        self.stored_ballots(eid,[[(a,5),(b,5)],[(b,5)]])
        self.owner.post(f'/e/{eid}/close',{}); self.assertEqual(self.revote(eid)[0],303)
        self.assertEqual({r['id'] for r in self.result(eid)['rows']},{a,b})
        self.assertEqual(self.result(eid,1)['rows'][0]['average'],5)

    def test_no_votes_can_be_reopened_but_unique_winner_cannot(self):
        self.open(); self.owner.post(f'/e/{self.eid}/close',{})
        self.assertEqual(self.revote(self.eid)[0],303)
        self.voter.post(f'/e/{self.eid}/vote',{'candidate':str(self.ids()[0])})
        self.owner.post(f'/e/{self.eid}/close',{})
        self.assertEqual(self.revote(self.eid)[0],409)

    def test_revote_requires_owner_notice_confirmation_deadline_and_current_round(self):
        self.open(); self.owner.post(f'/e/{self.eid}/close',{})
        for changes in ({'reason':''},{'acknowledge':''},{'deadline':'bad'},{'deadline':'2020-01-01T00:00'},{'round_id':'999999'}):
            self.assertIn(self.revote(self.eid,**changes)[0],(400,409))
        self.assertEqual(self.other.post(f'/e/{self.eid}/revote',{})[0],403)
        self.assertEqual(self.event(self.eid)['current_round'],1)

    def test_exports_follow_private_publication_and_invitation_permissions(self):
        eid=self.create(visibility='PRIVATE'); self.open(eid)
        for ending in ('results.csv','chart.svg'):
            self.assertEqual(self.owner.request(f'/e/{eid}/{ending}')[0],403)
        self.owner.post(f'/e/{eid}/close',{})
        for ending in ('results.csv','chart.svg'):
            self.assertEqual(self.owner.request(f'/e/{eid}/{ending}')[0],200)
            self.assertEqual(self.voter.request(f'/e/{eid}/{ending}')[0],403)
        data=self.form(); data['invite_code']='private-test'
        _,_,headers=self.owner.post('/create',data); gated=int(headers['Location'].split('/')[2])
        self.open(gated); self.owner.post(f'/e/{gated}/close',{})
        self.assertEqual(self.voter.request(f'/e/{gated}/results.csv')[0],403)
        self.voter.post(f'/e/{gated}/access',{'invite_code':'private-test'})
        self.assertEqual(self.voter.request(f'/e/{gated}/results.csv')[0],200)

    def test_csv_preserves_zero_and_missing_and_contains_no_voter_identity(self):
        eid=self.create('SCORE'); a,b,c=self.set_entries(eid); self.open(eid)
        self.voter.post(f'/e/{eid}/vote',{f'score_{a}':'0',f'score_{b}':'5'})
        self.owner.post(f'/e/{eid}/close',{})
        status,body,headers=self.owner.request(f'/e/{eid}/results.csv')
        self.assertEqual(status,200); self.assertIn('attachment',headers['Content-Disposition'])
        rows=list(csv.DictReader(io.StringIO(body.lstrip('\ufeff'))))
        by_id={int(r['entry_id']):r for r in rows}
        self.assertEqual(by_id[a]['average'],'0.0'); self.assertEqual(by_id[c]['average'],'')
        self.assertNotIn('user_id',body); self.assertNotIn('87654321',body)
        self.assertEqual(exports.safe_cell(' =HYPERLINK("x")'),'\' =HYPERLINK("x")')

    def test_rcv_csv_includes_every_count_and_svg_is_parseable(self):
        eid=self.create('RCV'); a,b,c=self.set_entries(eid); self.open(eid)
        self.stored_ballots(eid,[[a,b],[a,b],[b,a],[b,a],[c,a]])
        self.owner.post(f'/e/{eid}/close',{})
        _,body,_=self.owner.request(f'/e/{eid}/results.csv')
        rows=list(csv.DictReader(io.StringIO(body.lstrip('\ufeff'))))
        self.assertEqual({r['rcv_count'] for r in rows},{'1','2'})
        for kind in ('bar','line','horizontal'):
            status,svg,_=self.owner.request(f'/e/{eid}/chart.svg?chart={kind}&count=2')
            self.assertEqual(status,200); ElementTree.fromstring(svg)
        self.assertEqual(self.owner.request(f'/e/{eid}/chart.svg?chart=bad')[0],400)
        self.assertEqual(self.owner.request(f'/e/{eid}/chart.svg?count=99')[0],400)

    def test_historical_export_is_unchanged_after_revote(self):
        self.open(); self.owner.post(f'/e/{self.eid}/close',{})
        before=self.owner.request(f'/e/{self.eid}/results.csv?round=1')[1]
        self.revote(self.eid); self.owner.post(f'/e/{self.eid}/close',{})
        self.assertEqual(self.owner.request(f'/e/{self.eid}/results.csv?round=1')[1],before)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.original=app.DB; app.DB=self.root/'voting.sqlite3'; app.init_db()
        self.database=app.DB
    def tearDown(self):
        app.DB=self.original; gc.collect(); self.tmp.cleanup()
    def execute(self,sql):
        con=app.connect()
        try:
            with con: return con.execute(sql).fetchall()
        finally: con.close()
    def test_restore_saves_before_snapshot_and_clears_sessions(self):
        self.execute("INSERT INTO users(phone,name,salt,password_hash) VALUES('12345678','Before','00','hash')")
        self.execute("INSERT INTO sessions VALUES('old-token',1,9999999999)")
        backup=storage.backup_database(self.database)
        self.execute("UPDATE users SET name='After'")
        recovery=storage.restore_database(self.database,backup)
        self.assertEqual(self.execute('SELECT name FROM users')[0][0],'Before')
        self.assertEqual(self.execute('SELECT COUNT(*) FROM sessions')[0][0],0)
        with sqlite3.connect(recovery) as con: self.assertEqual(con.execute('SELECT name FROM users').fetchone()[0],'After')
        con.close()
    def test_corrupt_foreign_and_newer_backups_leave_active_data_unchanged(self):
        for kind in ('corrupt','foreign','newer'):
            backup=self.root/(kind+'.sqlite3')
            if kind=='corrupt': backup.write_bytes(b'bad SQLite data')
            elif kind=='foreign':
                with sqlite3.connect(backup) as con: con.execute('CREATE TABLE something(x)')
                con.close()
            else:
                storage.copy_database(self.database,backup)
                with sqlite3.connect(backup) as con: con.execute('PRAGMA user_version=9999')
                con.close()
            before=self.database.read_bytes()
            with self.assertRaises((ValueError,sqlite3.Error)): storage.restore_database(self.database,backup)
            self.assertEqual(before,self.database.read_bytes())
        self.assertEqual(list(self.root.glob('*.partial')),[])
    def test_failed_migration_never_replaces_active_database(self):
        backup=storage.backup_database(self.database); before=self.database.read_bytes()
        def fail(_): raise ValueError('synthetic migration failure')
        with self.assertRaises(ValueError): storage.restore_database(self.database,backup,prepare=fail)
        self.assertEqual(before,self.database.read_bytes())
    def test_failed_replacement_keeps_active_data_and_recovery_snapshot(self):
        backup=storage.backup_database(self.database); before=self.database.read_bytes()
        with patch('storage.os.replace',side_effect=OSError('synthetic blocked rename')):
            with self.assertRaises(OSError): storage.restore_database(self.database,backup)
        self.assertEqual(before,self.database.read_bytes())


class LocalToolsTests(unittest.TestCase):
    setUp=StorageTests.setUp
    tearDown=StorageTests.tearDown
    def request(self,path='/',fields=None,cookie=None,host='127.0.0.1:8765'):
        from urllib.parse import urlencode,urlsplit
        token='a'*48; split=urlsplit(path); meta={}
        payload=urlencode(fields or {}).encode()
        env={'REQUEST_METHOD':'POST' if fields is not None else 'GET','PATH_INFO':split.path,'QUERY_STRING':split.query,
             'CONTENT_LENGTH':str(len(payload)),'CONTENT_TYPE':'application/x-www-form-urlencoded','wsgi.input':io.BytesIO(payload),
             'HTTP_COOKIE':cookie or '', 'HTTP_HOST':host,'SERVER_PORT':'8765'}
        def start(status,headers): meta.update(status=int(status.split()[0]),headers=dict(headers))
        handler=LocalTools(lambda env,start: app.app(env,start),self.root,token,threading.RLock(),lambda:None)
        body=b''.join(handler(env,start)).decode('utf-8'); return meta,body
    def test_launch_capability_is_required_and_url_is_cleaned(self):
        self.assertEqual(self.request('/_votelab/tools')[0]['status'],403)
        self.assertEqual(self.request('/?local=bad')[0]['status'],403)
        self.assertEqual(self.request('/?local='+'a'*48,host='attacker.example:8765')[0]['status'],403)
        meta,_=self.request('/?local='+'a'*48)
        self.assertEqual(meta['status'],303); self.assertEqual(meta['headers']['Location'],'/')
        self.assertIn('HttpOnly',meta['headers']['Set-Cookie'])
    def test_tools_backup_and_forged_restore_are_distinct_from_account_access(self):
        cookie='votelab_operator='+'a'*48
        meta,body=self.request('/_votelab/tools',cookie=cookie)
        self.assertEqual(meta['status'],200); self.assertIn('Back up now',body)
        meta,_=self.request('/_votelab/tools',{'csrf':'a'*48,'action':'backup'},cookie)
        self.assertEqual(meta['status'],200); self.assertEqual(len(list((self.root/'backups').glob('*.sqlite3'))),1)
        for fields in ({'csrf':'wrong','action':'backup'}, {'csrf':'a'*48,'action':'restore','backup':'../../voting.sqlite3','confirm_restore':'RESTORE'}):
            self.assertEqual(self.request('/_votelab/tools',fields,cookie)[0]['status'],400)
        self.assertNotIn('Local data &amp; upgrades',self.request('/')[1])


if __name__=='__main__': unittest.main()
