"""Saved grants are browser-scoped, optional and independently revocable."""
import gc, tempfile, time, unittest
from pathlib import Path
import app
from test_app import Client


class SavedAccountTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.previous=app.DB
        app.DB=Path(self.tmp.name)/'accounts.sqlite3'
        app.init_db()
        self.c=Client('en')
        self.c.register('80000001','First')
        self.c.register('80000002','Second')

    def tearDown(self):
        app.DB=self.previous
        gc.collect()
        self.tmp.cleanup()

    def remember(self,phone):
        self.assertEqual(self.c.post('/login',{'phone':phone,'password':'Test-only-pass123','remember':'1'})[0],303)
        with app.connect() as con:
            return con.execute('SELECT id FROM users WHERE phone=?',(phone,)).fetchone()[0]

    def test_switch_optional_and_browser_scoped(self):
        self.assertNotIn('First',self.c.request('/accounts')[1])
        first=self.remember('80000001'); self.remember('80000002')
        self.assertIn('First',self.c.request('/accounts')[1])
        self.assertNotIn('First',Client('en').request('/accounts')[1])
        self.assertEqual(Client('en').post('/accounts/select',{'user_id':first})[0],401)
        old=self.c.cookies['session']
        self.assertEqual(self.c.post('/switch-account',{})[2]['Location'],'/accounts')
        self.assertEqual(self.c.post('/accounts/select',{'user_id':first})[0],303)
        with app.connect() as con:
            self.assertIsNone(con.execute('SELECT 1 FROM sessions WHERE token=?',(old,)).fetchone())
            self.assertEqual(con.execute('SELECT user_id FROM sessions WHERE token=?',(self.c.cookies['session'],)).fetchone()[0],first)
        self.assertIn('<html lang="en">',self.c.request('/')[1])
        self.c.post('/accounts/remove',{'user_id':first})
        self.assertEqual(self.c.post('/accounts/select',{'user_id':first})[0],401)
        with app.connect() as con:
            self.assertIsNotNone(con.execute('SELECT 1 FROM users WHERE id=?',(first,)).fetchone())

    def test_logout_expiry_reset_and_csrf(self):
        first=self.remember('80000001')
        self.assertEqual(self.c.request('/accounts/select',{'user_id':first,'csrf':'wrong'})[0],403)
        with app.connect() as con: con.execute('UPDATE remembered_accounts SET expires=?',(int(time.time())-1,))
        self.assertEqual(self.c.post('/accounts/select',{'user_id':first})[0],401)
        self.remember('80000001'); self.c.post('/logout',{})
        self.assertEqual(self.c.post('/accounts/select',{'user_id':first})[0],401)
        self.remember('80000001')
        code=self.c.code('80000001','reset')
        self.assertEqual(self.c.post('/reset',{'phone':'80000001','password':'Changed-pass123','password_confirm':'Changed-pass123','code':code})[0],303)
        self.assertEqual(self.c.post('/accounts/select',{'user_id':first})[0],401)


if __name__=='__main__': unittest.main()
