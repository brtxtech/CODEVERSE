"""Security/role/sequence tests with Supabase adapter stub. No network calls."""
import pytest
from fastapi.testclient import TestClient
from services.api.main import app
from services.api import security_portal as sec


class MemoryStore:
    def __init__(self, role='developer', n=0, submitted=False):
        self.role=role
        self.records=[{'step':i,'status':'completed','result':{},'completed_at':'2026-01-01'} for i in range(1,n+1)]
        self.is_submitted=submitted
        self.events=[]
        self.data=[]
    async def profile(self,user):
        return {'id':user,'role':self.role,'display_name':'Test user','email':'test@example.com',
                'university':'','github_username':'','created_at':'2026-01-01'}
    async def steps(self,user):return self.records
    async def finalized(self,user):return self.is_submitted
    async def save_step(self,user,step,result):
        self.records.append({'step':step,'status':'completed','result':result,'completed_at':'2026-01-01'})
    async def submit(self,user):self.is_submitted=True
    async def audit(self,actor,role,action,outcome,detail=None):self.events.append((action,outcome,detail))
    async def request(self,method,table,*,params=None,payload=None,prefer=None):
        self.data.append((method,table,params,payload))
        if table=='codeverse_security_events' and method=='GET':return []
        return None


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('CODEVERSE_REQUIRE_ADMIN_MFA','0')
    fake=MemoryStore()
    monkeypatch.setattr(sec,'store',fake)
    async def user_override():return '11111111-1111-4111-8111-111111111111'
    app.dependency_overrides[sec.authenticated_user]=user_override
    with TestClient(app) as test:
        yield test, fake
    app.dependency_overrides.clear()


def test_guest_cannot_use_secure_pages_without_token(monkeypatch):
    # No fake auth override, so protected routes require a verified issuer/JWT.
    monkeypatch.delenv('CODEVERSE_JWT_ISSUER',raising=False)
    with TestClient(app) as c:
        r=c.get('/api/secure/admin/events')
        assert r.status_code in (401,503)
        r=c.get('/api/secure/jobs')
        assert r.status_code in (401,503)


def test_developer_cannot_access_admin(client):
    c,f=client
    assert c.get('/api/secure/admin/events').status_code==403
    assert c.get('/api/secure/admin/overview').status_code==403
    assert any(k=='role_access' and outcome=='denied' for k,outcome,_ in f.events)


def test_recruiter_cannot_use_developer_steps(client):
    c,f=client;f.role='recruiter'
    assert c.get('/api/secure/recruiter').status_code==200
    assert c.post('/api/secure/journey/steps/3',json={'acknowledge':True}).status_code==403
    assert c.get('/api/secure/jobs').status_code==403


def test_security_admin_only_security_events(client):
    c,f=client;f.role='security_admin'
    assert c.get('/api/secure/admin/events').status_code==200
    assert c.get('/api/secure/admin/overview').status_code==200
    assert c.post('/api/secure/journey/steps/3',json={'acknowledge':True}).status_code==403
    assert c.get('/api/secure/jobs').status_code==403


def test_sequence_enforced_prevents_skip(client):
    c,f=client
    r=c.post('/api/secure/journey/steps/4',json={'career':'backend'})
    assert r.status_code==409
    assert 'step 1' in r.json()['detail']
    assert not f.records


def test_step_validation_requires_acknowledgement(client):
    c,f=client
    f.records=[{'step':i,'status':'completed'} for i in (1,2)]
    assert c.post('/api/secure/journey/steps/3',json={'acknowledge':False}).status_code==422
    assert c.post('/api/secure/journey/steps/3',json={'acknowledge':True}).status_code==200
    assert sec.current_index(f.records)==4
    assert c.post('/api/secure/journey/steps/3',json={'acknowledge':True}).status_code==409


def test_career_whitelist(client):
    c,f=client
    f.records=[{'step':i,'status':'completed'} for i in (1,2,3)]
    assert c.post('/api/secure/journey/steps/4',json={'career':'security_admin'}).status_code==422
    assert c.post('/api/secure/journey/steps/4',json={'career':'telecom'}).status_code==200


def test_submission_gate_controls_jobs(client):
    c,f=client
    assert c.get('/api/secure/jobs').status_code==403
    assert c.post('/api/secure/journey/submit').status_code==409
    f.records=[{'step':i,'status':'completed'} for i in range(1,8)]
    assert c.post('/api/secure/journey/submit').json()['jobs_unlocked'] is True
    r=c.get('/api/secure/jobs')
    assert r.status_code==200
    assert r.json()['employment_listings_verified'] is False


def test_no_client_role_change_field(client):
    c,f=client
    assert c.patch('/api/secure/profile',json={'role':'security_admin'}).status_code==422
    # Pydantic ignores unknown fields; it never forwards role to Supabase.
    assert f.role=='developer'
    assert not any('role' in (entry[3] or {}) for entry in f.data)


def test_no_github_fake_urls():
    assert sec.is_valid_github('https://github.com/example-user')=='example-user'
    from fastapi import HTTPException
    for bad in ['https://github.com/owner/repo','https://github.com/example?query=1','example/repo']:
        with pytest.raises(HTTPException):sec.is_valid_github(bad)


def test_metrics_rejects_incorrect_secret(client,monkeypatch):
    c,_=client
    monkeypatch.setenv('CODEVERSE_METRICS_TOKEN','very-secret-test-token')
    assert c.get('/internal/metrics').status_code==404
    assert c.get('/internal/metrics',headers={'Authorization':'Bearer wrong'}).status_code==404
    assert c.get('/internal/metrics',headers={'Authorization':'Bearer very-secret-test-token'}).status_code==200


def test_secure_mode_blocks_legacy_demo(client,monkeypatch):
    c,_=client
    monkeypatch.setenv('CODEVERSE_SECURE_MODE','1')
    for path in ['/career-journey','/studio','/workspace','/api/taxonomy']:
        assert c.get(path).status_code==403
    assert c.get('/secure').status_code==200


def test_step_count_and_completion():
    assert sec.current_index([])==1
    assert sec.current_index([{'step':1,'status':'completed'},{'step':2,'status':'completed'}])==3
    assert sec.current_index([{'step':i,'status':'completed'} for i in range(1,8)])==8
