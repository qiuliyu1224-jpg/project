"""Selection-limit regressions on temporary VoteLab fixtures only."""

from html.parser import HTMLParser
from pathlib import Path
import unittest

import app
import voting_rules as rules
import test_app as fixtures

SOURCE = Path(__file__).resolve().parent


class LimitControl(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.group = None
        self.input = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if 'data-choice-limit' in values:
            self.group = values
        if tag == 'input' and values.get('name') == 'max_choices':
            self.input = values


class ChoiceLimitRegressions(unittest.TestCase):
    setUp = fixtures.VotingTests.setUp
    tearDown = fixtures.VotingTests.tearDown
    form = fixtures.VotingTests.form
    create = fixtures.VotingTests.create
    ids = fixtures.VotingTests.ids

    def event(self, event_id):
        with app.connect() as con:
            return rules.event_row(con.execute('SELECT * FROM elections WHERE id=?', (event_id,)).fetchone())

    def create_with_limit(self, method, value=None, three_entries=False):
        data = self.form(method)
        if value is not None:
            data['max_choices'] = value
        if three_entries:
            data['entry_key'] = ['a', 'b', 'c']
            data['entry_name_c'] = 'Gamma'
        status, body, headers = self.owner.post('/create', data)
        self.assertEqual(status, 303, body[:300])
        return int(headers['Location'].split('/')[2])

    def revision_form(self, event_id):
        event = self.event(event_id)
        data = self.form(event['method'])
        ids = self.ids(event_id)
        data['entry_key'] = [str(index) for index in range(len(ids))]
        for index, candidate in enumerate(ids):
            data['entry_id_' + str(index)] = str(candidate)
            data['entry_name_' + str(index)] = ['Alpha', 'Beta', 'Gamma'][index]
        data.update(title='Updated title', announcement='Clarified the title')
        return data

    def test_non_single_creation_normalizes_stale_or_absent_limits(self):
        for method in ('MAJORITY', 'SCORE', 'RCV'):
            for stale_value in (None, '3', 'not-a-number', '0'):
                with self.subTest(method=method, stale_value=stale_value):
                    event_id = self.create_with_limit(method, stale_value)
                    self.assertEqual(self.event(event_id)['max_choices'], 1)

    def test_single_creation_still_validates_and_saves_limit(self):
        event_id = self.create_with_limit('SINGLE', '3', True)
        self.assertEqual(self.event(event_id)['max_choices'], 3)
        for value in ('0', '21', 'not-a-number'):
            data = self.form('SINGLE')
            data['max_choices'] = value
            self.assertEqual(self.owner.post('/create', data)[0], 400)

    def test_hidden_limit_is_disabled_for_each_non_single_edit(self):
        for method in ('SINGLE', 'MAJORITY', 'SCORE', 'RCV'):
            with self.subTest(method=method):
                event_id = self.create_with_limit(method, '3')
                status, body, _ = self.owner.request(f'/e/{event_id}/edit')
                self.assertEqual(status, 200)
                control = LimitControl(body)
                self.assertIsNotNone(control.group)
                self.assertIsNotNone(control.input)
                if method == 'SINGLE':
                    self.assertNotIn('hidden', control.group)
                    self.assertNotIn('disabled', control.input)
                else:
                    self.assertIn('hidden', control.group)
                    self.assertIn('disabled', control.input)

    def test_legacy_non_single_paused_edit_omits_limit_and_preserves_vote(self):
        for method in ('MAJORITY', 'SCORE', 'RCV'):
            with self.subTest(method=method):
                event_id = self.create_with_limit(method)
                with app.connect() as con:
                    con.execute('UPDATE elections SET max_choices=3 WHERE id=?', (event_id,))
                self.assertEqual(self.owner.post(f'/e/{event_id}/open', {})[0], 303)
                candidate = self.ids(event_id)[0]
                vote = {'candidate': str(candidate)} if method == 'MAJORITY' else {('score_' if method == 'SCORE' else 'rank_') + str(candidate): '1'}
                self.assertEqual(self.voter.post(f'/e/{event_id}/vote', vote)[0], 303)
                self.assertEqual(self.owner.post(f'/e/{event_id}/pause', {})[0], 303)
                data = self.revision_form(event_id)
                self.assertNotIn('max_choices', data)
                self.assertEqual(self.owner.post(f'/e/{event_id}/revision', data)[0], 303)
                event = self.event(event_id)
                self.assertEqual((event['method'], event['max_choices'], event['current_round'], event['revisions']), (method, 1, 1, 1))
                with app.connect() as con:
                    self.assertEqual(rules.counts(con, event)['ballots'], 1)

    def test_single_limit_stays_locked_during_pause(self):
        event_id = self.create_with_limit('SINGLE', '3', True)
        self.assertEqual(self.owner.post(f'/e/{event_id}/open', {})[0], 303)
        self.assertEqual(self.owner.post(f'/e/{event_id}/pause', {})[0], 303)
        data = self.revision_form(event_id)
        self.assertEqual(self.owner.post(f'/e/{event_id}/revision', data)[0], 400)
        data['max_choices'] = '2'
        self.assertEqual(self.owner.post(f'/e/{event_id}/revision', data)[0], 400)
        event = self.event(event_id)
        self.assertEqual((event['max_choices'], event['revisions'], event['paused']), (3, 0, 1))
        data['max_choices'] = '3'
        self.assertEqual(self.owner.post(f'/e/{event_id}/revision', data)[0], 303)

    def test_hidden_css_overrides_display_and_javascript_disables_input(self):
        css = '\n'.join(file.read_text(encoding='utf-8') for file in (SOURCE / 'static').glob('*.css'))
        self.assertRegex(css, r'\[data-choice-limit\]\[hidden\][^{]*\{[^}]*display\s*:\s*none')
        script = (SOURCE / 'static' / 'v4.js').read_text(encoding='utf-8')
        group = script[script.index('[data-choice-limit]'):]
        self.assertIn('.disabled', group.split('method.addEventListener', 1)[0])


if __name__ == '__main__':
    unittest.main(verbosity=2)

