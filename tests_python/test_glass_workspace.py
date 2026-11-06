import copy,hashlib
import pytest
from fastapi.testclient import TestClient
from services.api.main import app
from services.api import glass_workspace as g
from services.api.security_portal import context

@pytest.fixture
def client(monkeypatch):
    db={}
    async def ctx():return {'user':'user-a','role':'visitor','profile':{'github_username':'octocat','role':'visitor'}}
    async def load(user):return copy.deepcopy(db.get(user,{'payload':{'journey':[]},'revision':0}))
    async def save(user,payload,revision):
        if db.get(user,{}).get('revision',0)!=revision:raise g.HTTPException(409,'Conflict')
        db[user]={'payload':copy.deepcopy(payload),'revision':revision+1};return revision+1
    async def repos(owner):return {'repositories':[{'name':'api','full_name':'octocat/api','language':'Python','stars':2}]}
    async def scan(owner,repo):return {'repository':owner+'/'+repo,'sha':'a'*40,'evidence':[{'skill':'fastapi'}]}
    monkeypatch.setattr(g,'collect_public_repository',scan)
    app.dependency_overrides[context]=ctx
    monkeypatch.setattr(g,'load',load);monkeypatch.setattr(g,'save',save);monkeypatch.setattr(g,'collect_public_repositories',repos)
    yield TestClient(app),db
    app.dependency_overrides.clear()

def test_seven_stages_are_sequential_and_keep_only_extracted_cv_signals(client):
    c,db=client
    assert c.post('/api/v1/glass/journey/7',json={'acknowledge':True}).status_code==409
    assert c.post('/api/v1/glass/journey/1',json={'text':'My CV: Python, Docker, FastAPI and SQL.'}).status_code==200
    first=db['user-a']['payload']['journey'][0]
    assert 'text' not in first and 'Python' in first['skills']
    assert c.post('/api/v1/glass/journey/2',json={}).status_code==200
    assert c.post('/api/v1/glass/journey/3',json={}).status_code==422
    assert c.post('/api/v1/glass/journey/3',json={'acknowledge':True}).status_code==200
    assert c.post('/api/v1/glass/journey/4',json={'target':'invented-role'}).status_code==422
    assert c.post('/api/v1/glass/journey/4',json={'target':'backend','location':'Caen'}).status_code==200
    for n in [5,6,7]:assert c.post(f'/api/v1/glass/journey/{n}',json={'acknowledge':True}).status_code==200
    assert db['user-a']['payload']['submitted_at']
    assert c.post('/api/v1/glass/journey/7',json={'acknowledge':True}).status_code==409
    result=c.get('/api/v1/glass/dashboard').json()
    assert result['target']['id']=='backend' and 0<=result['score']<=100

def test_workspace_rejects_stale_tabs_and_role_or_journey_injection(client):
    c,db=client
    assert c.patch('/api/v1/glass/state',json={'revision':0,'role':'security_admin'}).status_code==422
    assert c.patch('/api/v1/glass/state',json={'revision':0,'journey':[]}).status_code==422
    assert c.patch('/api/v1/glass/state',json={'revision':0,'companies':[{'name':'Company'}]}).status_code==200
    assert c.patch('/api/v1/glass/state',json={'revision':0,'companies':[]}).status_code==409
    assert len(db['user-a']['payload']['companies'])==1

def test_graph_requires_known_inputs_unique_ids_and_no_cycles():
    for graph in [[{'id':'a','kind':'python','inputs':['missing']}],[{'id':'a','kind':'python','inputs':['b']},{'id':'b','kind':'python','inputs':['a']}],[{'id':'a','kind':'dataset'},{'id':'a','kind':'dataset'}]]:
        with pytest.raises(ValueError):g.graph_order(graph)
    assert [n['id'] for n in g.graph_order([{'id':'b','kind':'python','inputs':['a']},{'id':'a','kind':'dataset'}])]==['a','b']

def test_unconfigured_runner_fails_without_executing_code(client,monkeypatch):
    c,_=client;monkeypatch.delenv('CODEVERSE_RUNNER_URL',raising=False)
    r=c.post('/api/v1/glass/automation/test',json={'code':'print(1)','input':[]})
    assert r.status_code==503 and 'runner' in r.json()['detail']

def test_automation_requires_test_and_never_sends_gmail(client,monkeypatch):
    c,db=client;code='print("{}")'
    db['user-a']={'revision':1,'payload':{'nodes':[{'id':'p','name':'Python','kind':'python','code':code,'inputs':[]},{'id':'g','kind':'gmail','inputs':['p']}], 'datasets':[]}}
    assert c.post('/api/v1/glass/automation/run',json={}).status_code==409
    db['user-a']['payload']['nodes'][0]['tested_code']=hashlib.sha256(code.encode()).hexdigest()
    async def execute(code,data):return {'result':1}
    async def token(user):return 'test-not-a-real-token'
    async def audit(*args,**kwargs):pass
    monkeypatch.setattr(g,'execute_python',execute);monkeypatch.setattr(g,'gmail_token',token);monkeypatch.setattr(g.store,'audit',audit)
    result=c.post('/api/v1/glass/automation/run',json={}).json()
    assert result['outputs']['g']['sent'] is False

def test_catalog_matching_uses_normalized_skills_and_no_fabricated_metrics():
    rows=g.rank_catalog(['Node.js','Python'])
    assert rows[0]['match_score']>0
    assert all(r['stars'] is None for r in rows)
    assert g.published_email('Apply: recruiting@example.org')=='recruiting@example.org'
    assert g.published_email('Recruiter Alice; company example.org') is None

def test_oauth_state_and_unconfirmed_writes_rejected(client):
    c,_=client
    assert c.get('/api/v1/glass/gmail/callback?state=forged&code=forged').status_code==400
    assert c.post('/api/v1/glass/gmail/send',json={'to':'test@example.org','subject':'Hello','body':'Test'}).status_code==422
    assert c.post('/api/v1/glass/projects',json={'template':'fastapi/fastapi','name':'demo'}).status_code==409

def test_protected_routes_fail_closed_without_identity_provider(monkeypatch):
    monkeypatch.delenv('CODEVERSE_JWT_ISSUER',raising=False);c=TestClient(app)
    for path in ['/state','/dashboard']:assert c.get('/api/v1/glass'+path).status_code==503
    assert c.post('/api/v1/glass/automation/run',json={}).status_code==503

def test_api_connector_rejects_unapproved_hosts_and_redirect_paths(client):
    c,_=client
    for host,path in [('127.0.0.1','/'),('metadata.google.internal','/'),('api.github.com','//evil.example/path'),('api.github.com','https://evil.example')]:
        r=c.post('/api/v1/glass/connectors/test',json={'name':'test','host':host,'path':path,'token':'not-a-real-key'})
        assert r.status_code==422

def test_state_is_scoped_to_the_authenticated_owner(client):
    c,db=client
    c.patch('/api/v1/glass/state',json={'revision':0,'companies':[{'name':'Private Company A'}]})
    async def user_b():return {'user':'user-b','role':'visitor','profile':{'github_username':'other','role':'visitor'}}
    app.dependency_overrides[context]=user_b
    state=c.get('/api/v1/glass/state').json()
    assert state['revision']==0 and 'Private Company A' not in str(state)
