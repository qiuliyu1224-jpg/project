"""Markup and asset checks complement browser motion/tour acceptance."""
import unittest
from ui4 import View
from test_app import Client

class RefinedViewTests(unittest.TestCase):
    def test_guide_and_local_styles_are_bilingual(self):
        for language,label in [('en','Quick guide'),('zh','操作指南')]:
            page=View(language,'test',{'id':1,'name':'Tester'},'/').page('Example','')
            self.assertIn(label,page)
            self.assertIn('data-guide-open',page)
            self.assertIn('/static/refined.css',page)
            self.assertIn('/static/experience.js',page)
            self.assertIn('data-authenticated="1"',page)
    def test_general_examples_are_not_real_results(self):
        page=View('en','test',None).examples()
        for name in ('Entry evaluation','Proposal voting','Project showcase'):
            self.assertIn(name,page)
        self.assertNotIn('Campus photography competition',page)
        self.assertNotIn('/create',page) # The guide never automatically creates events.
        self.assertIn('Demo records never enter real events',page)
        self.assertEqual(page.count('data-vote-demo-open'),1)
        self.assertEqual(page.count('data-example-info='),2)
    def test_artwork_and_scripts_are_local_public_assets(self):
        client=Client('en')
        for name in ('hero-vote','login-vote','example-entries','example-choice','example-projects'):
            status,_,headers=client.request('/static/assets/'+name+'.webp')
            self.assertEqual(status,200)
            self.assertEqual(headers['Content-Type'],'image/webp')
            self.assertEqual(client.last_raw[:4],b'RIFF')
        for name in ('refined.css','experience.js','guide.js','demo.js'):
            self.assertEqual(client.request('/static/'+name)[0],200)

if __name__=='__main__':unittest.main()
