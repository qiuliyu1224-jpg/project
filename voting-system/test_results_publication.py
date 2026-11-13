"""Result publication and charts, using isolated temporary databases only."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from xml.etree import ElementTree

import app
import charts
import publication
import voting_rules as rules


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = app.DB
        app.DB = Path(self.tmp.name) / 'test.sqlite3'
        self.original_connect = app.connect
        self.connections = []
        def tracked_connect():
            con = self.original_connect()
            self.connections.append(con)
            return con
        app.connect = tracked_connect
        app.init_db()
        with app.connect() as con:
            self.owner = con.execute(
                'INSERT INTO users(phone,name,salt,password_hash) VALUES(?,?,?,?)',
                ('80000001', 'Owner', '00'*16, 'fixture')
            ).lastrowid

    def tearDown(self):
        for con in self.connections:
            con.close()
        app.connect = self.original_connect
        app.DB = self.old_db
        self.tmp.cleanup()

    def event(self, method='SINGLE', visibility='PUBLIC', auto=1, status='OPEN', end=100):
        with app.connect() as con:
            eid = con.execute(
                'INSERT INTO elections(creator_id,title,method,voting_mode,visibility,duration,status,ends_at,auto_publish) '
                'VALUES(?,?,?,?,?,?,?,?,?)',
                (self.owner, 'Fixture', 'SCORE' if method == 'SCORE' else 'SINGLE', method, visibility, 60, status, end, auto)
            ).lastrowid
            rid = con.execute('INSERT INTO rounds(election_id,number) VALUES(?,1)', (eid,)).lastrowid
            ids = [con.execute('INSERT INTO candidates(election_id,name) VALUES(?,?)', (eid, name)).lastrowid for name in ('A','B','C')]
            return eid, rid, ids

    def ballots(self, eid, rid, choices):
        with app.connect() as con:
            for index, candidate in enumerate(choices):
                user = con.execute('INSERT INTO users(phone,name,salt,password_hash) VALUES(?,?,?,?)',
                                   (f'{eid:04d}{index:04d}', f'Voter {index}', '00'*16, 'fixture')).lastrowid
                bid = con.execute('INSERT INTO ballots(election_id,round_id,user_id) VALUES(?,?,?)', (eid,rid,user)).lastrowid
                con.execute('INSERT INTO choices VALUES(?,?,?,1)', (bid,eid,candidate))

    def stored(self, eid):
        with app.connect() as con:
            return dict(con.execute('SELECT * FROM elections WHERE id=?', (eid,)).fetchone())

    def test_expiry_publishes_only_opted_in_public_events_and_is_idempotent(self):
        public, _, _ = self.event()
        private, _, _ = self.event(visibility='PRIVATE')
        legacy, _, _ = self.event(auto=0)
        future, _, _ = self.event(end=300)
        draft, _, _ = self.event(status='DRAFT')
        with app.connect() as con:
            con.execute('UPDATE elections SET paused=1 WHERE id=?', (public,))
            first = publication.refresh(con, now=200)
            second = publication.refresh(con, now=200)
        self.assertEqual(first, {'closed':3,'published':1})
        self.assertEqual(second, {'closed':0,'published':0})
        self.assertEqual((self.stored(public)['status'], self.stored(public)['paused'], self.stored(public)['published']), ('CLOSED',0,1))
        self.assertEqual(self.stored(private)['published'], 0)
        self.assertEqual(self.stored(legacy)['published'], 0)
        self.assertEqual(self.stored(future)['status'], 'OPEN')
        self.assertEqual(self.stored(draft)['status'], 'DRAFT')

    def test_runoff_required_does_not_publish_first_round_as_final(self):
        eid,rid,ids = self.event(method='MAJORITY')
        self.ballots(eid,rid,[ids[0],ids[0],ids[1],ids[1],ids[2]])
        # A tied first place with a clear two-entry cutoff still needs a new vote.
        with app.connect() as con:
            publication.refresh(con, now=200)
            result=rules.counts(con,rules.event_row(con.execute('SELECT * FROM elections WHERE id=?',(eid,)).fetchone()))
        self.assertEqual(result['state'], 'RUNOFF_REQUIRED')
        self.assertEqual(self.stored(eid)['published'], 0)

    def test_runoff_final_tie_and_empty_results_remain_truthful_statuses(self):
        eid,rid,ids = self.event(method='MAJORITY')
        self.ballots(eid,rid,[ids[0],ids[1]])
        with app.connect() as con:
            con.execute('UPDATE rounds SET is_runoff=1,eligible=? WHERE id=?', (json.dumps(ids[:2]),rid))
            publication.refresh(con, now=200)
            result=rules.counts(con,rules.event_row(con.execute('SELECT * FROM elections WHERE id=?',(eid,)).fetchone()))
        self.assertEqual((result['state'],result['winner']), ('FINAL_TIE',None))
        self.assertEqual(self.stored(eid)['published'], 1)
        empty,_,_=self.event(method='SCORE')
        with app.connect() as con:
            publication.refresh(con, now=200)
            result=rules.counts(con,rules.event_row(con.execute('SELECT * FROM elections WHERE id=?',(empty,)).fetchone()))
        self.assertEqual(result['state'], 'NO_VOTES')
        self.assertEqual(self.stored(empty)['published'], 1)

    def test_majority_winner_and_closed_opt_in_are_published(self):
        eid,rid,ids = self.event(method='MAJORITY')
        self.ballots(eid,rid,[ids[0],ids[0],ids[1]])
        already_closed,_,_ = self.event(status='CLOSED')
        with app.connect() as con:
            result=publication.refresh(con, now=200)
        self.assertEqual(result['published'], 2)
        self.assertEqual(self.stored(eid)['published'], 1)
        self.assertEqual(self.stored(already_closed)['published'], 1)

    def test_migration_defaults_legacy_to_manual_and_does_not_change_existing_votes(self):
        eid,rid,ids = self.event(auto=0)
        self.ballots(eid,rid,[ids[0]])
        # Reproduce a pre-upgrade database without the new column.
        with app.connect() as con:
            con.execute('ALTER TABLE elections DROP COLUMN auto_publish')
        app.init_db()
        app.init_db()
        with app.connect() as con:
            self.assertEqual(con.execute('SELECT auto_publish FROM elections WHERE id=?',(eid,)).fetchone()[0],0)
            self.assertEqual(con.execute('SELECT COUNT(*) FROM ballots WHERE election_id=?',(eid,)).fetchone()[0],1)
            self.assertEqual(list(con.execute('PRAGMA foreign_key_check')), [])

    def test_refresh_does_not_commit_or_rollback_unrelated_caller_transaction(self):
        eid,_,_=self.event()
        con=app.connect()
        try:
            con.execute('BEGIN')
            con.execute('UPDATE elections SET title=? WHERE id=?', ('Uncommitted',eid))
            publication.refresh(con, now=200)
            con.rollback()
        finally:
            con.close()
        event=self.stored(eid)
        self.assertEqual((event['title'],event['status'],event['published']),('Fixture','OPEN',0))


class ChartTests(unittest.TestCase):
    def score(self):
        return {'method':'SCORE','ballots':2,'rows':[
            {'id':1,'name':'<script>alert("x")</script>','average':0,'n':1,'total':0},
            {'id':2,'name':'A & B','average':5,'n':1,'total':5},
            {'id':3,'name':'Not rated','average':None,'n':0,'total':0},
        ]}

    def test_chart_values_distinguish_zero_and_unrated_and_fixed_five_point_axis(self):
        result=self.score()
        data=charts.chart_data(result)
        self.assertEqual(data['maximum'],5)
        self.assertEqual([r['value'] for r in data['rows']],[0,5,None])
        self.assertEqual(data['rows'][2]['note'],'Not rated')
        for kind in charts.KINDS:
            with self.subTest(kind=kind):
                output=charts.render_chart(result,kind)
                self.assertNotIn('<script>',output)
                self.assertIn('&lt;script&gt;',output)
                self.assertIn('A &amp; B',output)
                self.assertIn('0.00',output)
                self.assertIn('5.00',output)
                svg=output[output.index('<svg'):output.index('</svg>')+6]
                ElementTree.fromstring(svg)

    def test_chart_selection_does_not_change_results_and_rejects_invalid_kind(self):
        result=self.score()
        before=copy.deepcopy(result)
        charts.render_chart(result,'line')
        self.assertEqual(result,before)
        with self.assertRaises(ValueError): charts.render_chart(result,'<script>')
        self.assertIn('not changes over time',charts.render_chart(result,'line'))

    def test_rcv_chart_uses_chosen_count_and_marks_eliminated_as_not_active(self):
        result={'method':'RCV','ballots':5,'rows':[
            {'id':1,'name':'A','total':0,'n':0},
            {'id':2,'name':'B','total':0,'n':0},
            {'id':3,'name':'C','total':0,'n':0}],
            'rounds':[{'counts':{1:2,2:2,3:1}},{'counts':{1:3,2:2}}]}
        first=charts.chart_data(result,rcv_round=1)
        final=charts.chart_data(result)
        self.assertEqual([r['value'] for r in first['rows']],[2,2,1])
        self.assertEqual([r['value'] for r in final['rows']],[3,2,None])
        self.assertEqual(final['rcv_round'],2)
        self.assertIn('reuse the same ranked ballots',final['caption'])
        for invalid in (0,3,'invalid'):
            with self.assertRaises(ValueError): charts.chart_data(result,rcv_round=invalid)

    def test_translated_labels_and_no_votes_remain_accessible(self):
        result={'method':'SINGLE','ballots':0,'rows':[{'id':1,'name':'原名','total':0,'n':0}]}
        output=charts.render_chart(result,labels={1:'Translated name'})
        self.assertIn('Translated name',output)
        self.assertNotIn('原名',output)
        self.assertIn('role="img"',output)
        for method,value in [('SCORE',6),('SINGLE',float('inf')),('SINGLE',-1)]:
            malformed={'method':method,'ballots':1,'rows':[{'id':1,'name':'X','total':value,'average':value,'n':1}]}
            with self.assertRaises(ValueError): charts.chart_data(malformed)


if __name__ == '__main__':
    unittest.main(verbosity=2)
