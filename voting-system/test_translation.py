"""Translation isolation, tokens, external failure handling and UTF-8 limits."""
import io
import json
import sqlite3
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import translation as tr


class TranslationTests(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(':memory:')
        tr._failures.clear()

    def tearDown(self):
        self.con.close()

    def test_tokens_are_bound_to_session_source_and_short_expiry(self):
        token = tr.make_token('校园摄影', 'session1', b'test-key', now=1000)
        self.assertEqual(tr.verify_token(token, 'session1', b'test-key', now=1001), '校园摄影')
        for context, key, now, candidate in [
            ('session2', b'test-key', 1001, token),
            ('session1', b'wrong-key', 1001, token),
            ('session1', b'test-key', 1181, token),
            ('session1', b'test-key', 1001, token[:-1] + ('A' if token[-1] != 'A' else 'B')),
            ('session1', b'test-key', 1001, 'bad')]:
            with self.assertRaises(ValueError):
                tr.verify_token(candidate, context, key, now=now)

    def test_render_marks_visible_content_not_original_forms_or_identities(self):
        page = ('<!doctype html><html><head><title>摄影活动</title></head><body><main>'
                '<h1>摄影活动 &amp; 摄影作品</h1><p>作品介绍</p>'
                '<input name="title" value="摄影活动"><textarea>保留原文</textarea>'
                '<div data-no-translate>张三</div><div class="side-bottom">李四</div>'
                '<script>const value="中文";</script><style>.x{content:"中文"}</style>'
                '</main></body></html>')
        marked = tr.mark_page(page, 'en', 'ctx', b'key')
        self.assertIn('data-translation-token=', marked)
        self.assertIn('data-translation-source="摄影活动 &amp; 摄影作品"', marked)
        self.assertIn('<input name="title" value="摄影活动">', marked)
        self.assertIn('<textarea>保留原文</textarea>', marked)
        self.assertIn('<div data-no-translate>张三</div>', marked)
        self.assertIn('<div class="side-bottom">李四</div>', marked)
        self.assertIn('<script>const value="中文";</script>', marked)
        self.assertIn('<title>VoteLab</title>', marked)
        self.assertEqual(marked.count('/static/translation.js'), 1)
        self.assertEqual(tr.mark_page(page, 'zh', 'ctx', b'key'), page)

    def test_svg_gets_tspan_not_html_span_and_scripts_not_escaped(self):
        value = '<html><body><svg><title>图表</title><text>校园作品</text></svg></body></html>'
        marked = tr.mark_page(value, 'en', 'ctx', b'key')
        self.assertIn('<tspan data-translation-token=', marked)
        self.assertNotIn('<span', marked)
        self.assertIn('<title>VoteLab</title>', marked)

    def test_success_is_cached_and_source_edits_get_new_translations(self):
        with patch.object(tr, '_request', return_value='Campus photo') as provider:
            a = tr.translate(self.con, '校园照片')
            b = tr.translate(self.con, '校园照片')
            c = tr.translate(self.con, '校园照片新')
        self.assertTrue(a['ok']); self.assertFalse(a['cached'])
        self.assertTrue(b['cached']); self.assertTrue(c['ok'])
        self.assertEqual(provider.call_count, 2)
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM content_translations').fetchone()[0], 2)

    def test_long_sources_are_split_below_provider_byte_limit(self):
        source = '校园摄影作品' * 100
        chunks = list(tr._chunks(source))
        self.assertEqual(''.join(chunks), source)
        self.assertTrue(all(len(x.encode('utf-8')) <= 500 for x in chunks))
        with patch.object(tr, '_request', return_value='Campus photo') as provider:
            value = tr.translate(self.con, source)
        self.assertTrue(value['ok'])
        self.assertEqual(provider.call_count, len(chunks))

    def test_provider_failure_does_not_cache_original_or_repeat_requests(self):
        with patch.object(tr, '_request', side_effect=OSError('offline')) as provider:
            value = tr.translate(self.con, '中文内容')
            again = tr.translate(self.con, '中文内容')
        self.assertFalse(value['ok']); self.assertFalse(again['ok'])
        self.assertEqual(value['text'], 'Translation unavailable')
        self.assertEqual(value['source'], '中文内容')
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM content_translations').fetchone()[0], 0)

    def test_never_commits_or_transmits_during_business_transaction(self):
        self.con.execute('CREATE TABLE ballot (value TEXT)')
        self.con.execute('INSERT INTO ballot VALUES (?)', ('pending',))
        with patch.object(tr, '_request') as provider:
            result = tr.translate(self.con, '不可发送')
        self.assertFalse(result['ok']); provider.assert_not_called()
        self.assertTrue(self.con.in_transaction)
        self.con.rollback()
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM ballot').fetchone()[0], 0)

    def test_daily_budget_denies_network_and_cache_still_works(self):
        tr.init_schema(self.con)
        with patch.object(tr, 'DAILY_BUDGET', 4), patch.object(tr, '_request', return_value='Photo') as provider:
            a = tr.translate(self.con, '作品图')
            b = tr.translate(self.con, '其他作品')
            c = tr.translate(self.con, '作品图')
        self.assertTrue(a['ok']); self.assertFalse(b['ok']); self.assertTrue(c['cached'])
        self.assertEqual(provider.call_count, 1)

    def test_provider_validation_and_html_output_are_plain_text(self):
        sample = json.dumps({'responseStatus': 200, 'responseData': {'translatedText': '&lt;img src=x&gt;'}}).encode()
        with patch.object(tr, 'urlopen', return_value=io.BytesIO(sample)) as network:
            result = tr._request('作品', 1)
        self.assertEqual(result, '<img src=x>')
        query = parse_qs(urlsplit(network.call_args.args[0].full_url).query)
        self.assertEqual(query['q'], ['作品']); self.assertEqual(query['langpair'], ['zh-CN|en'])
        self.assertTrue(network.call_args.args[0].full_url.startswith('https://api.mymemory.translated.net/get?'))
        for sample in [
            [],
            {'responseStatus': 200, 'responseData': None},
            {'responseStatus': 429, 'responseData': {'translatedText': 'LIMIT'}},
            {'responseStatus': 200, 'quotaFinished': True, 'responseData': {'translatedText': 'No'}},
            {'responseStatus': 200, 'responseData': {'translatedText': '仍然中文'}}]:
            with patch.object(tr, 'urlopen', return_value=io.BytesIO(json.dumps(sample).encode())):
                with self.assertRaises(ValueError): tr._request('作品', 1)


if __name__ == '__main__':
    unittest.main()
