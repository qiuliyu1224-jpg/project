"""Read-only view regressions for the review feedback; no personal database."""
from html.parser import HTMLParser
import time
import unittest

from ui4 import View


class Elements(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.elements = []
        self.text = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def handle_data(self, value):
        self.text.append(value)


class NavigationViewTests(unittest.TestCase):
    def view(self, lang='en', user=True):
        account = {'id': 7, 'name': 'Example account'} if user else None
        return View(lang, 'synthetic-csrf', account, '/create')

    def event(self, method='SINGLE'):
        return {'id': 17, 'title': 'Example activity', 'method': method,
                'max_choices': 3, 'allow_submissions': 0,
                'planned_end': int(time.time()) + 86400,
                'visibility': 'PUBLIC', 'tags': '', 'paused': 0}

    def test_create_and_edit_have_deterministic_back_destinations(self):
        for lang in ('zh', 'en'):
            for event, target in ((None, '/dashboard'), (self.event(), '/e/17')):
                with self.subTest(lang=lang, target=target):
                    html = Elements(self.view(lang).event_form(event))
                    back = [attrs for tag, attrs in html.elements
                            if tag == 'a' and 'data-nav-back' in attrs]
                    self.assertEqual(len(back), 1)
                    self.assertEqual(back[0]['href'], target)

    def test_switch_account_is_authenticated_post_with_csrf(self):
        for lang, label in (('en', 'Switch account'), ('zh', '切换账号')):
            page = self.view(lang).page('Example', '')
            self.assertRegex(page, r'<form[^>]+method="post"[^>]+action="/switch-account"[^>]*><input type="hidden" name="csrf" value="synthetic-csrf">')
            self.assertIn(label, page)
            self.assertIn('action="/logout"', page)
        self.assertNotIn('action="/switch-account"', self.view(user=False).page('Example', ''))

    def test_personal_account_name_and_initial_excluded_from_online_translation(self):
        page = self.view().page('Example', '')
        self.assertIn('<span data-no-translate>Example account</span>', page)
        self.assertIn('<span class="avatar" data-no-translate>', page)

    def test_english_authentication_and_creation_static_text_are_english(self):
        view = self.view()
        pages = [view.auth(), view.auth(register=True), view.auth(reset=True),
                 view.event_form(), view.examples()]
        for page in pages:
            self.assertNotRegex(' '.join(Elements(page).text), r'[\u3400-\u9fff]')
        auth = view.auth()
        for name in ('China +86', 'Hong Kong +852', 'Macao +853', 'Taiwan +886'):
            self.assertIn(name, auth)

    def test_formal_template_names_replace_casual_wording(self):
        for lang in ('zh', 'en'):
            page = self.view(lang).event_form()
            self.assertNotIn('大家来选一个', page)
            self.assertNotIn('Popular templates', page)
            self.assertNotIn('常用模板', page)
            self.assertIn('Activity templates' if lang == 'en' else '活动模板', page)
            self.assertIn('Single-choice voting' if lang == 'en' else '单选投票', page)

    def test_result_visibility_explains_automatic_publication_and_private_option(self):
        for lang in ('zh', 'en'):
            page = self.view(lang).event_form()
            self.assertIn('Automatically publish results when voting ends' if lang == 'en' else '结束后自动发布结果', page)
            self.assertIn('Only me' if lang == 'en' else '仅自己查看结果', page)
            self.assertIn('name="visibility"', page)

    def test_maximum_selection_control_only_applies_to_single_multiple(self):
        for method in ('SINGLE', 'MAJORITY', 'SCORE', 'RCV'):
            page = Elements(self.view().event_form(self.event(method)))
            groups = [a for _, a in page.elements if 'data-choice-limit' in a]
            limits = [a for tag, a in page.elements if tag == 'input' and a.get('name') == 'max_choices']
            self.assertEqual(len(groups), 1)
            self.assertEqual(len(limits), 1)
            self.assertEqual('hidden' in groups[0], method != 'SINGLE')
            self.assertEqual('disabled' in limits[0], method != 'SINGLE')
            self.assertEqual('required' in limits[0], method == 'SINGLE')
            self.assertEqual(limits[0]['value'], '3')
        majority = self.view().event_form(self.event('MAJORITY'))
        self.assertIn('one entry per voter per round', majority)


if __name__ == '__main__':
    unittest.main(verbosity=2)
