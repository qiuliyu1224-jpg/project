"""Disposable browser fixture. Never reads the desktop user's VoteLab database."""
from pathlib import Path
import json, os, sys, time
from datetime import datetime

repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(repo/'voting-system'))
import app, entries, run_votelab
from test_app import Client

folder=Path(sys.argv[1]).resolve()
folder.mkdir(parents=True,exist_ok=True)
app.DB=folder/'voting.sqlite3'
if app.DB.exists(): raise RuntimeError('The browser fixture requires a fresh directory')
app.init_db()
owner,voter,other=Client('en'),Client('en'),Client('en')
for client,phone,name in ((owner,'80000001','Test organiser'),(voter,'80000002','Test voter'),(other,'80000003','Test other')):
    assert client.register(phone,name)[0]==303

def create(title,method='SCORE'):
    form={'title':title,'method':method,'visibility':'PUBLIC','deadline':datetime.fromtimestamp(time.time()+86400,entries.TZ).strftime('%Y-%m-%dT%H:%M'),
          'entry_key':['a','b','c'],'entry_name_a':'Entry Alpha','entry_name_b':'Entry Beta','entry_name_c':'Entry Gamma',
          'entry_description_a':'Compare the work before rating.','entry_description_b':'A second entry for evaluation.','entry_description_c':'A third entry for evaluation.'}
    assets=repo/'voting-system/static/assets'
    files={f'entry_image_{key}':(assets/f'example-{name}.webp').read_bytes() for key,name in zip('abc',['entries','choice','projects'])}
    status,body,headers=owner.post('/create',form,files);assert status==303,body
    eid=int(headers['Location'].split('/')[2]);assert owner.post(f'/e/{eid}/open',{})[0]==303
    return eid

score=create('Sample entry evaluation')
closing=create('Sample closing event','SINGLE')
failure=create('Sample submission recovery')
state={'score':score,'closing':closing,'failure':failure,'owner':owner.cookies,'voter':voter.cookies,'other':other.cookies}
(folder/'fixture.json').write_text(json.dumps(state),encoding='utf-8')
os.environ['VOTELAB_DATA_DIR']=str(folder)
sys.argv=['run_votelab.py','--no-browser','--port','0']
run_votelab.main()
