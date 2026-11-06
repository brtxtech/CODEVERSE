import asyncio,base64,copy,hashlib,json,subprocess,sys
import pytest,httpx
from fastapi import HTTPException
from test_glass_workspace import client
from services.api import glass_workspace as g,glass_features as f
from services.api.core import normalize_skill,extract_skills

def finished_payload():
    return {'journey':[{'skills':['Python','Docker','FastAPI'],'profile':{'full_name':'Test Student'}},{'repositories':[{'full_name':'octocat/api','language':'Python'}],'manifest_scans':[]},{'ratings':{'Python':2}},{'target':'backend','location':'Remote'},{},{},{}],'submitted_at':'2026-11-01T00:00:00Z','companies':[],'applications':[{'id':'kept'}]}

def test_language_id_collision_fixed_without_losing_technologies():
    assert [normalize_skill(x) for x in ['C','C++','C#']]==['c','cpp','csharp']
    skills=extract_skills('Built separate projects in C, C++ and C# with Python.')
    assert {'c','cpp','csharp','python'} <= {s['id'] for s in skills}
    ids=[t['id'] for t in g.TAXONOMY['technologies']]
    assert len(ids)==305 and len(set(ids))==305

def test_drafts_preserve_structured_profile_and_exclude_original_cv(client):
    c,db=client
    r=c.put('/api/v1/glass/journey/draft',json={'revision':0,'step':1,'values':{'text':'Confidential CV statement using Python and Docker','profile':{'full_name':'Test Student','education':'M1 Computer Science'}}})
    assert r.status_code==200
    draft=db['user-a']['payload']['drafts']['1']
    assert draft['profile']['education']=='M1 Computer Science'
    assert 'text' not in draft and 'Python' in draft['skills']
    assert c.put('/api/v1/glass/journey/draft',json={'revision':1,'step':1,'values':{'role':'security_admin'}}).status_code==422

def test_edit_invalidates_only_downstream_reviews_and_preserves_work(client):
    c,db=client;db['user-a']={'revision':4,'payload':finished_payload()}
    assert c.post('/api/v1/glass/journey/reopen',json={'revision':4,'step':4,'confirmed':False}).status_code==422
    assert c.post('/api/v1/glass/journey/reopen',json={'revision':4,'step':4,'confirmed':True}).status_code==200
    p=db['user-a']['payload'];assert len(p['journey'])==3 and 'submitted_at' not in p
    assert p['applications']==[{'id':'kept'}] and p['drafts']['4']['target']=='backend'
    assert c.get('/api/v1/glass/jobs').status_code==409

def test_self_ratings_are_explicit_and_do_not_become_mastery(client):
    c,db=client;db['user-a']={'revision':1,'payload':finished_payload()}
    d=c.get('/api/v1/glass/dashboard').json();row=next(s for s in d['skill_details'] if s['id']=='python')
    assert row['self_rating']==2 and row['mastery']=='Not assessed'
    assert 'Not a proficiency' in d['score_method']
    p=finished_payload();p['journey']=p['journey'][:2];p.pop('submitted_at');db['user-a']={'revision':1,'payload':p}
    assert c.post('/api/v1/glass/journey/3',json={'acknowledge':True,'ratings':{'Python':8}}).status_code==422

def test_learning_progress_is_persistent_revision_checked_and_target_scoped(client):
    c,db=client;db['user-a']={'revision':1,'payload':finished_payload()}
    body={'revision':1,'skill':'python','index':1,'completed':True,'proof_url':'https://github.com/octocat/api'}
    r=c.post('/api/v1/glass/learning/progress',json=body);assert r.status_code==200
    assert db['user-a']['payload']['learning_progress']['python']['1']['completed']
    assert c.post('/api/v1/glass/learning/progress',json=body).status_code==409
    assert c.post('/api/v1/glass/learning/progress',json={**body,'revision':2,'skill':'unrelated'}).status_code==422

def test_offer_ranking_filters_location_and_marks_missing_requirements_unknown():
    p=finished_payload();offers=[{'id':'1','title':'Python FastAPI developer','description':'Docker PostgreSQL','location':'Remote'},{'id':'2','title':'Unspecified internship','location':'Remote'},{'id':'3','title':'Python engineer','location':'Paris'}]
    rows=f.rank_offers(p,offers,'remote');assert len(rows)==2 and rows[0]['id']=='1'
    assert rows[0]['match_percent']==75 and rows[1]['match_percent'] is None
    assert f.rank_offers(p,offers,'Madrid')==[]

def test_workflow_run_saves_actual_outputs_and_named_files(client,monkeypatch):
    c,db=client;code='print("[]")';p=finished_payload();p['datasets']=[{'id':'data','type':'csv','name':'people.csv','content':'name,age\nAda,20\n'}];p['nodes']=[{'id':'data-box','kind':'dataset','dataset':'data','outputName':'input.json'},{'id':'code-box','kind':'python','name':'Transform','code':code,'tested_code':hashlib.sha256(code.encode()).hexdigest(),'inputs':['data-box'],'outputName':'result.csv'}];db['user-a']={'revision':1,'payload':p}
    calls=[]
    async def execute(code,inputs):calls.append(inputs);return [{'name':'Ada','next_age':21}]
    async def audit(*args,**kwargs):pass
    monkeypatch.setattr(g,'execute_python',execute);monkeypatch.setattr(g.store,'audit',audit)
    r=c.post('/api/v1/glass/automation/execute',json={});assert r.status_code==200;r=r.json()
    assert r['status']=='completed' and calls==[[[{'name':'Ada','age':'20'}]]]
    assert 'next_age' in r['files']['code-box']['content']
    assert c.get('/api/v1/glass/state').json()['payload']['runs'][0]['id']==r['id']

def test_failed_run_preserves_partial_outputs_and_error(client,monkeypatch):
    c,db=client;code='broken';p=finished_payload();p['datasets']=[{'id':'data','type':'json','content':'[1,2]'}];p['nodes']=[{'id':'a','kind':'dataset','dataset':'data'},{'id':'b','kind':'python','code':code,'tested_code':hashlib.sha256(code.encode()).hexdigest(),'inputs':['a']}];db['user-a']={'revision':1,'payload':p}
    async def execute(code,inputs):raise HTTPException(422,'Execution limit')
    async def audit(*args,**kwargs):pass
    monkeypatch.setattr(g,'execute_python',execute);monkeypatch.setattr(g.store,'audit',audit)
    r=c.post('/api/v1/glass/automation/execute',json={}).json();assert r['status']=='failed' and r['outputs']['a']==[1,2]
    assert r['log'][-1]['node']=='b' and db['user-a']['payload']['runs'][0]['error']=='Execution limit'

def test_run_to_box_excludes_unrelated_downstream_email(client):
    c,db=client;p=finished_payload();p['datasets']=[{'id':'d','type':'txt','content':'hi'}];p['nodes']=[{'id':'a','kind':'dataset','dataset':'d'},{'id':'mail','kind':'gmail','operation':'send','inputs':['a']}];db['user-a']={'revision':1,'payload':p}
    result=c.post('/api/v1/glass/automation/validate',json={'target':'a'}).json();assert result['order']==['a'] and result['sends']==[]

def test_automatic_mail_requires_explicit_review(client,monkeypatch):
    c,db=client;p=finished_payload();p['nodes']=[{'id':'mail','kind':'gmail','operation':'send','to':'test@example.org','subject':'Test','body':'Reviewed message'}];db['user-a']={'revision':1,'payload':p};sent=[]
    async def token(user):return 'fixture'
    async def connected(user,provider):return {'tested_at':'2026-11-01'}
    monkeypatch.setattr(g,'get_secret',connected)
    async def send(body,ctx):sent.append(body.to);return {'sent':True,'id':'provider-id'}
    async def audit(*args,**kwargs):pass
    monkeypatch.setattr(g,'gmail_token',token);monkeypatch.setattr(g,'gmail_send',send);monkeypatch.setattr(g.store,'audit',audit)
    assert c.post('/api/v1/glass/automation/execute',json={}).status_code==422 and sent==[]
    assert c.post('/api/v1/glass/automation/execute',json={'confirm_email_send':True}).json()['status']=='completed'
    assert sent==['test@example.org']

def test_binary_dataset_round_trips_and_invalid_payload_is_rejected():
    encoded=base64.b64encode(b'\x00\xffimage').decode();d={'type':'png','name':'sample.png','encoding':'base64','content':encoded,'media_type':'image/png'}
    value=f.dataset_value(d);output=f.output_file({'outputName':'copy.png'},value)
    assert output['encoding']=='base64' and base64.b64decode(output['content'])==b'\x00\xffimage'
    with pytest.raises(HTTPException):f.dataset_value({**d,'content':'%%%not-base64'})
    with pytest.raises(HTTPException):f.output_file({'outputName':'../../secret'},value)

def test_api_key_is_retained_only_for_same_host(client,monkeypatch):
    c,_=client;saved=[]
    async def secret(user,name):return {'host':'api.github.com','token':'existing-key'}
    async def request(config):return {'ok':True}
    async def put(user,name,config):saved.append(config)
    monkeypatch.setattr(g,'get_secret',secret);monkeypatch.setattr(g,'http_connector',request);monkeypatch.setattr(g,'put_secret',put)
    for host in ['api.github.com','huggingface.co']:assert c.post('/api/v1/glass/connectors/test',json={'name':'test','host':host,'path':'/','token':''}).status_code==200
    assert saved[0]['token']=='existing-key' and saved[1]['token']==''

def test_invalid_graph_and_company_urls_rejected_before_storage(client):
    c,_=client
    assert c.patch('/api/v1/glass/state',json={'revision':0,'nodes':[{'id':'a','kind':'python','inputs':['a']}]}).status_code==422
    assert c.patch('/api/v1/glass/state',json={'revision':0,'companies':[{'name':'Bad','url':'http://unsafe.example'}]}).status_code==422

def test_original_runnable_scaffold_tests_pass(tmp_path):
    template=next(t for t in g.CATALOG if t['id']=='pandas-dev/pandas');p=finished_payload();p['journey'][3]['target']='data'
    files=f.scaffold_files(template,p,'learning-lab')
    for name,content in files.items():(tmp_path/name).parent.mkdir(parents=True,exist_ok=True);(tmp_path/name).write_text(content)
    result=subprocess.run([sys.executable,'-m','unittest'],cwd=tmp_path,capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    assert 'LEARNING_PLAN.md' in files and 'main.py' in files

def test_repository_creation_initializes_real_files_and_retains_project(client,monkeypatch):
    c,db=client;db['user-a']={'revision':1,'payload':finished_payload()};written=[]
    actual_client=httpx.AsyncClient
    def handler(request):
        if request.url.path=='/user':return httpx.Response(200,json={'login':'octocat'})
        if request.url.path=='/user/repos':return httpx.Response(201,json={'full_name':'octocat/new-lab','html_url':'https://github.com/octocat/new-lab','name':'new-lab'})
        if request.method=='PUT':
            payload=json.loads(request.content);written.append((request.url.path,base64.b64decode(payload['content']).decode()));return httpx.Response(201,json={})
        return httpx.Response(404)
    def factory(*args,**kwargs):return actual_client(*args,transport=httpx.MockTransport(handler),**kwargs)
    async def audit(*args,**kwargs):pass
    monkeypatch.setattr(g.httpx,'AsyncClient',factory);monkeypatch.setattr(g.store,'audit',audit)
    result=c.post('/api/v1/glass/projects',json={'template':'fastapi/fastapi','name':'new-lab','confirmed':True},headers={'X-GitHub-Token':'fixture-token'});assert result.status_code==200,result.text
    body=result.json();assert body['commits']==len(written) and any(path.endswith('/app.py') for path,text in written)
    assert db['user-a']['payload']['created_projects'][0]['full_name']=='octocat/new-lab'

def test_zero_self_rating_survives_draft_and_skill_names_are_deduplicated(client):
    c,db=client;p=finished_payload();p['journey']=p['journey'][:2];p.pop('submitted_at');p['journey'][1]['manifest_scans']=[{'repository':'octocat/api','evidence':[{'skill':'fastapi'}]}];db['user-a']={'revision':1,'payload':p}
    assert c.put('/api/v1/glass/journey/draft',json={'revision':1,'step':3,'values':{'ratings':{'Python':0},'acknowledge':True}}).status_code==200
    assert db['user-a']['payload']['drafts']['3']['ratings']['Python']==0
    assert g.skills_from(p).count('FastAPI')==1
