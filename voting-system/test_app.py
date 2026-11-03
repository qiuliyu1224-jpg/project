import gc,io,re,tempfile,time,unittest
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from PIL import Image
import app,entries


def picture(color='green',fmt='PNG'):
    stream=io.BytesIO(); Image.new('RGB',(48,36),color).save(stream,format=fmt); return stream.getvalue()


class Client:
    def __init__(self): self.cookies={}
    def request(self,path,fields=None,files=None,raw=None,content_type=None):
        if files is not None:
            boundary='VoteLabTestBoundary'
            parts=[]
            for key,values in (fields or {}).items():
                for value in values if isinstance(values,list) else [values]: parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
            for key,data in files.items():
                parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"; filename="image.png"\r\nContent-Type: image/png\r\n\r\n'.encode()+data+b'\r\n')
            parts.append(f'--{boundary}--\r\n'.encode()); body=b''.join(parts); content_type='multipart/form-data; boundary='+boundary
        else: body=raw if raw is not None else urlencode(fields or {},doseq=True).encode()
        url=urlsplit(path); meta={}
        env={'REQUEST_METHOD':'POST' if fields is not None or raw is not None else 'GET','PATH_INFO':url.path,'QUERY_STRING':url.query,'CONTENT_LENGTH':str(len(body)),'CONTENT_TYPE':content_type or 'application/x-www-form-urlencoded','wsgi.input':io.BytesIO(body),'HTTP_COOKIE':'; '.join(k+'='+v for k,v in self.cookies.items())}
        def start(status,headers):
            meta.update(status=int(status.split()[0]),headers=dict(headers))
            for key,value in headers:
                if key=='Set-Cookie':
                    name,data=value.split(';')[0].split('=',1); self.cookies[name]=data
        response=b''.join(app.app(env,start)); self.last_raw=response
        return meta['status'],response.decode('utf-8',errors='replace'),meta['headers']
    def post(self,path,fields,files=None):
        if re.fullmatch(r'/e/\d+/(vote|confirm)',path) and 'round_id' not in fields:
            with app.connect() as con:
                row=con.execute('SELECT r.id FROM rounds r JOIN elections ev ON ev.id=r.election_id AND ev.current_round=r.number WHERE ev.id=?',(int(path.split('/')[2]),)).fetchone()
            if row: fields={**fields,'round_id':str(row['id'])}
        _,body,_=self.request('/login'); csrf=re.search(r'name="csrf" value="([a-f0-9]+)"',body)[1]
        return self.request(path,{**fields,'csrf':csrf},files)
    def code(self,phone,purpose):
        status,body,_=self.post('/auth/code',{'phone':phone,'purpose':purpose})
        if status!=200: raise AssertionError((status,body))
        return re.search(r'class="otp-code">([0-9]{6})',body)[1]
    def register(self,phone,name='Tester'):
        return self.post('/register',{'phone':phone,'name':name,'password':'Test-only-pass123','password_confirm':'Test-only-pass123','code':self.code(phone,'register')})
    def login(self,phone): return self.post('/login',{'phone':phone,'password':'Test-only-pass123'})


class VotingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        app.DB=Path(self.tmp.name)/'test.sqlite3'; app.init_db()
        self.owner,self.voter,self.other=Client(),Client(),Client()
        self.assertEqual(self.owner.register('12345678','Owner')[0],303)
        self.assertEqual(self.voter.register('87654321','Participant')[0],303)
        self.assertEqual(self.other.register('11112222','Other')[0],303)
        self.eid=self.create()
    def tearDown(self): gc.collect(); self.tmp.cleanup()
    def form(self,method='SINGLE',visibility='PUBLIC',accepting=False,empty=False):
        data={'title':'Test event','method':method,'visibility':visibility,'deadline':datetime.fromtimestamp(time.time()+86400,entries.TZ).strftime('%Y-%m-%dT%H:%M')}
        if accepting: data['submissions_open']='1'
        if not empty: data.update(entry_key=['a','b'],entry_name_a='Alpha',entry_name_b='Beta',entry_description_a='First option',entry_description_b='Second option')
        return data
    def create(self,method='SINGLE',visibility='PUBLIC',accepting=False,empty=False,files=None,client=None):
        client=client or self.owner
        status,body,headers=client.post('/create',self.form(method,visibility,accepting,empty),files)
        self.assertEqual(status,303,body); return int(headers['Location'].split('/')[2])
    def ids(self,eid=None):
        with app.connect() as con: return [r[0] for r in con.execute("SELECT id FROM candidates WHERE election_id=? AND review_status='APPROVED' ORDER BY id",(eid or self.eid,))]
    def open(self,eid=None): self.assertEqual(self.owner.post(f'/e/{eid or self.eid}/open',{})[0],303)
    def counts(self):
        with app.connect() as con: return tuple(con.execute('SELECT (SELECT COUNT(*) FROM ballots),(SELECT COUNT(*) FROM choices)').fetchone())
    def apply(self,eid,name='Applicant',client=None):
        return (client or self.voter).post(f'/e/{eid}/apply',{'name':name,'description':'A submitted image'},{'image':picture()})
    def submitted(self,eid):
        with app.connect() as con: return con.execute('SELECT * FROM candidates WHERE election_id=?',(eid,)).fetchone()

    def test_preview_does_not_vote(self):
        self.assertIn('预览',self.owner.request(f'/e/{self.eid}/preview')[1]); self.assertEqual(self.voter.post(f'/e/{self.eid}/vote',{'candidate':str(self.ids()[0])})[0],409); self.assertEqual(self.counts(),(0,0))
    def test_single_duplicate_and_confirmation(self):
        self.open(); data={'candidate':str(self.ids()[0])}
        self.assertEqual(self.voter.post(f'/e/{self.eid}/confirm',data)[0],200); self.assertEqual(self.counts(),(0,0))
        self.assertEqual(self.voter.post(f'/e/{self.eid}/vote',data)[0],303); self.assertIn('本轮',self.voter.post(f'/e/{self.eid}/vote',data)[1]); self.assertEqual(self.counts(),(1,1))
    def test_foreign_candidate_and_multiple_single_rejected(self):
        other=self.create(); self.open()
        self.assertEqual(self.voter.post(f'/e/{self.eid}/vote',{'candidate':str(self.ids(other)[0])})[0],400)
        self.assertEqual(self.voter.post(f'/e/{self.eid}/vote',{'candidate':[str(i) for i in self.ids()]})[0],400); self.assertEqual(self.counts(),(0,0))
    def test_score_zero_missing_range_and_saved_readonly(self):
        eid=self.create('SCORE'); self.open(eid); a,b=self.ids(eid)
        for data in ({},{f'score_{a}':'0',f'score_{b}':'6'},{f'score_{a}':'1.5',f'score_{b}':'2'}): self.assertEqual(self.voter.post(f'/e/{eid}/vote',data)[0],400)
        self.assertEqual(self.voter.post(f'/e/{eid}/vote',{f'score_{a}':'0',f'score_{b}':'5'})[0],303)
        body=self.voter.request(f'/e/{eid}')[1]; self.assertIn(f'name="score_{a}" value="0" checked disabled',body)
        with app.connect() as con: self.assertEqual([r['total'] for r in app.get_results(con,eid)],[5,0])
    def test_deadline_final_check(self):
        self.open()
        with app.connect() as con: con.execute('UPDATE elections SET ends_at=? WHERE id=?',(int(time.time())-1,self.eid))
        self.assertEqual(self.voter.post(f'/e/{self.eid}/vote',{'candidate':str(self.ids()[0])})[0],409); self.assertEqual(self.counts(),(0,0))
    def test_result_publication_and_private_access(self):
        for visibility in ('PUBLIC','PRIVATE'):
            eid=self.create(visibility=visibility); self.open(eid)
            self.assertEqual(self.owner.request(f'/e/{eid}/results')[0],403)
            self.owner.post(f'/e/{eid}/close',{}); self.assertEqual(self.owner.request(f'/e/{eid}/results')[0],200)
            self.assertEqual(self.voter.request(f'/e/{eid}/results')[0],403); self.owner.post(f'/e/{eid}/publish',{})
            self.assertEqual(Client().request(f'/e/{eid}/results')[0],200 if visibility=='PUBLIC' else 403)
    def test_one_account_can_create_enter_and_vote(self):
        own=self.create(client=self.voter)
        self.assertEqual(self.voter.request('/dashboard')[0],200)
        self.open(); self.assertEqual(self.voter.post(f'/e/{self.eid}/vote',{'candidate':str(self.ids()[0])})[0],303)
        self.assertEqual(self.voter.post(f'/e/{self.eid}/close',{})[0],403)
        with app.connect() as con: self.assertNotEqual(con.execute('SELECT creator_id FROM elections WHERE id=?',(own,)).fetchone()[0],con.execute('SELECT creator_id FROM elections WHERE id=?',(self.eid,)).fetchone()[0])
    def test_draft_edit_preserves_ids_and_locks_after_open(self):
        ids=self.ids(); form=self.form('SCORE'); form.update(entry_id_a=str(ids[0]),entry_id_b=str(ids[1]),entry_name_a='Changed')
        self.assertEqual(self.owner.post(f'/e/{self.eid}/edit',form)[0],303); self.assertEqual(ids,self.ids()); self.assertIn('Changed',self.owner.request(f'/e/{self.eid}/preview')[1])
        self.open(); self.assertEqual(self.owner.post(f'/e/{self.eid}/edit',form)[0],409)
    def test_save_failure_rolls_back_and_retry(self):
        self.open()
        with app.connect() as con: con.execute("CREATE TRIGGER fail BEFORE INSERT ON choices BEGIN SELECT RAISE(ABORT,'failure'); END")
        data={'candidate':str(self.ids()[0])}; self.assertEqual(self.voter.post(f'/e/{self.eid}/vote',data)[0],409); self.assertEqual(self.counts(),(0,0))
        with app.connect() as con: con.execute('DROP TRIGGER fail')
        self.assertEqual(self.voter.post(f'/e/{self.eid}/vote',data)[0],303)
    def test_csrf_unauth_logout_and_password_login(self):
        self.assertEqual(self.owner.request('/create',{'title':'No CSRF'})[0],403); self.assertEqual(Client().request('/create')[0],401)
        self.assertIn('type="password"',Client().request('/login')[1])
        self.assertEqual(Client().post('/login',{'phone':'12345678','password':'wrong-password'})[0],401)
        self.owner.post('/logout',{}); self.assertEqual(self.owner.request('/create')[0],401)
    def test_password_registration_replay_and_duplicate(self):
        guest=Client(); self.assertEqual(guest.login('12345678')[0],303)
        self.assertEqual(guest.post('/register',{'phone':'12345678','name':'Dup','code':'000000'})[0],409)
        code=guest.code('33334444','register'); payload={'phone':'33334444','name':'New','password':'Test-only-pass123','password_confirm':'Test-only-pass123','code':code}
        self.assertEqual(guest.post('/register',payload)[0],303); self.assertEqual(guest.post('/login',{'phone':'33334444','code':code})[0],401)
    def test_codes_expiry_attempts_binding_and_cooldown(self):
        guest=Client(); code=guest.code('12345678','reset')
        self.assertEqual(guest.post('/auth/code',{'phone':'12345678','purpose':'reset'})[0],429)
        data={'phone':'12345678','password':'New-test-pass123','password_confirm':'New-test-pass123','code':code}
        self.assertEqual(Client().post('/reset',data)[0],400)
        wrong='000000' if code!='000000' else '111111'
        for _ in range(5): self.assertEqual(guest.post('/reset',{**data,'code':wrong})[0],400)
        self.assertEqual(guest.post('/reset',data)[0],400)
        with app.connect() as con: con.execute('UPDATE verification_codes SET attempts=0,expires=?',(int(time.time())-1,))
        self.assertEqual(guest.post('/reset',data)[0],400)
    def test_language_persists_across_pages_and_unsafe_redirect_blocked(self):
        self.assertIn('创建一场新活动',self.owner.request('/create')[1])
        self.assertEqual(self.owner.post('/language',{'lang':'en','next':'/create'})[2]['Location'],'/create')
        body=self.owner.request('/create')[1]; self.assertIn('Create a new event',body); self.assertNotIn('创建一场新活动',body)
        self.assertIn('My entries',self.owner.request('/my-entries')[1]); self.assertEqual(self.owner.post('/language',{'lang':'en','next':'//evil.example'})[2]['Location'],'/')
        self.assertEqual(self.owner.post('/language',{'lang':'xx'})[0],400)
    def test_templates_and_image_editor_replace_multiline_box(self):
        body=self.owner.request('/create?template=photo')[1]
        self.assertIn('multipart/form-data',body); self.assertIn('data-add-entry',body); self.assertNotIn('textarea name="candidates"',body); self.assertIn('datetime-local',body)
        self.assertIn('报名',body); self.assertEqual(Client().request('/static/entries.css')[0],200)
    def test_valid_images_persist_and_draft_media_private(self):
        eid=self.create(files={'entry_image_a':picture()}); row=self.submitted(eid)
        self.assertTrue(row['image_id']); self.assertEqual(self.owner.request('/media/'+row['image_id'])[0],200); self.assertEqual(self.voter.request('/media/'+row['image_id'])[0],404)
        self.open(eid); guest=Client(); self.assertEqual(guest.request('/media/'+row['image_id'])[0],200); self.assertEqual(guest.last_raw[:2],b'\xff\xd8')
        self.assertIn('/media/'+row['image_id'],guest.request(f'/e/{eid}')[1]); self.assertIn('First option',guest.request(f'/e/{eid}')[1])
    def test_invalid_oversize_and_svg_uploads_leave_no_partial_event(self):
        for data in (b'<svg onload="alert(1)"></svg>',b'not-an-image',b'x'*(5*1024*1024+1)):
            with app.connect() as con: count=con.execute('SELECT COUNT(*) FROM elections').fetchone()[0]
            self.assertEqual(self.owner.post('/create',self.form(),{'entry_image_a':data})[0],400)
            with app.connect() as con: self.assertEqual(count,con.execute('SELECT COUNT(*) FROM elections').fetchone()[0])
    def test_invalid_name_after_image_does_not_orphan_upload(self):
        data=self.form(); data['entry_name_b']='Alpha'
        self.assertEqual(self.owner.post('/create',data,{'entry_image_a':picture()})[0],400)
        with app.connect() as con: self.assertEqual(con.execute('SELECT COUNT(*) FROM images').fetchone()[0],0)
    def test_image_keep_replace_remove(self):
        eid=self.create(files={'entry_image_a':picture()}); original=self.submitted(eid); ids=self.ids(eid)
        data=self.form(); data.update(entry_id_a=str(ids[0]),entry_id_b=str(ids[1]))
        self.owner.post(f'/e/{eid}/edit',data); self.assertEqual(self.submitted(eid)['image_id'],original['image_id'])
        self.owner.post(f'/e/{eid}/edit',data,{'entry_image_a':picture('blue')}); self.assertNotEqual(self.submitted(eid)['image_id'],original['image_id'])
        data['remove_image_a']='1'; self.owner.post(f'/e/{eid}/edit',data); self.assertIsNone(self.submitted(eid)['image_id'])
    def test_deadline_future_and_30day_limit(self):
        for seconds in (-3600,31*86400):
            data=self.form(); data['deadline']=datetime.fromtimestamp(time.time()+seconds,entries.TZ).strftime('%Y-%m-%dT%H:%M')
            self.assertEqual(self.owner.post('/create',data)[0],400)
    def test_applications_not_public_until_explicit_collect(self):
        eid=self.create(accepting=True,empty=True)
        self.assertEqual(self.voter.request(f'/e/{eid}')[0],403); self.assertEqual(self.apply(eid)[0],409)
        self.assertEqual(self.owner.post(f'/e/{eid}/collect',{})[0],303); self.assertEqual(self.voter.request(f'/e/{eid}')[0],200)
    def test_application_pending_privacy_and_duplicate(self):
        eid=self.create(accepting=True,empty=True); self.owner.post(f'/e/{eid}/collect',{})
        self.assertEqual(self.apply(eid)[0],303); row=self.submitted(eid); self.assertEqual(row['review_status'],'PENDING')
        self.assertEqual(self.voter.request('/media/'+row['image_id'])[0],200); self.assertEqual(self.owner.request('/media/'+row['image_id'])[0],200); self.assertEqual(self.other.request('/media/'+row['image_id'])[0],404)
        self.assertNotIn('Applicant',self.other.request(f'/e/{eid}')[1]); self.assertEqual(self.apply(eid)[0],409)
        self.assertIn('待审核',self.voter.request('/my-entries')[1])
    def test_application_image_optional(self):
        eid=self.create(accepting=True,empty=True); self.owner.post(f'/e/{eid}/collect',{})
        self.assertEqual(self.voter.post(f'/e/{eid}/apply',{'name':'No image','description':''})[0],303)
    def test_review_permissions_rejection_reason_and_feedback(self):
        eid=self.create(accepting=True,empty=True); self.owner.post(f'/e/{eid}/collect',{}); self.apply(eid); row=self.submitted(eid)
        payload={'candidate_id':str(row['id']),'verdict':'REJECTED','reason':''}
        self.assertEqual(self.other.post(f'/e/{eid}/review',payload)[0],403); self.assertEqual(self.owner.post(f'/e/{eid}/review',payload)[0],400)
        payload['reason']='Please use a clearer image'; self.assertEqual(self.owner.post(f'/e/{eid}/review',payload)[0],303)
        self.assertIn('Please use a clearer image',self.voter.request('/my-entries')[1])
    def test_review_to_voting_complete_flow_and_lock(self):
        eid=self.create('SCORE',accepting=True); self.owner.post(f'/e/{eid}/collect',{}); self.apply(eid); row=None
        with app.connect() as con: row=con.execute("SELECT * FROM candidates WHERE election_id=? AND review_status='PENDING'",(eid,)).fetchone()
        self.assertEqual(self.owner.post(f'/e/{eid}/open',{})[0],400)
        review={'candidate_id':str(row['id']),'verdict':'APPROVED','reason':'Welcome'}
        self.assertEqual(self.owner.post(f'/e/{eid}/review',review)[0],303); self.assertIn('Applicant',self.other.request(f'/e/{eid}')[1]); self.open(eid)
        self.assertEqual(self.apply(eid,'Late',self.other)[0],409); self.assertEqual(self.owner.post(f'/e/{eid}/review',review)[0],409)
        payload={'score_'+str(cid):'5' for cid in self.ids(eid)}
        self.assertEqual(self.other.post(f'/e/{eid}/vote',payload)[0],303); self.assertEqual(self.counts(),(1,3))
    def test_creator_cannot_rewrite_participant_entry(self):
        eid=self.create(accepting=True,empty=True); self.owner.post(f'/e/{eid}/collect',{}); self.apply(eid); row=self.submitted(eid)
        data=self.form(accepting=True); data.update(entry_id_a=str(row['id']))
        self.assertEqual(self.owner.post(f'/e/{eid}/edit',data)[0],403); self.assertEqual(self.submitted(eid)['name'],'Applicant')
    def test_html_escaping(self):
        with app.connect() as con: con.execute('UPDATE elections SET title=? WHERE id=?',('<script>alert(1)</script>',self.eid))
        body=self.owner.request(f'/e/{self.eid}')[1]; self.assertNotIn('<script>',body); self.assertIn('&lt;script&gt;',body)
    def test_media_path_and_multipart_request_limit(self):
        self.assertEqual(Client().request('/media/../../app.py')[0],404)
        from io import BytesIO
        with self.assertRaises(app.Problem): entries.read_form({'CONTENT_LENGTH':str(entries.MAX_REQUEST+1),'wsgi.input':BytesIO(b'')})


if __name__=='__main__': unittest.main(verbosity=2)
