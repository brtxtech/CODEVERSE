import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from services.api.ledger import Ledger
from services.api.main import app

def test_tenant_isolation_and_erasure(tmp_path):
    store=Ledger(tmp_path/'ledger.sqlite')
    tid=store.create_target('alice','Backend',[{'skill':'python','weight':1,'required_level':2}])
    store.add_evidence('alice','python',2,.35,'cv_claim')
    first=store.evaluate('alice',tid)
    assert first['score']>0
    assert len(store.history('alice',tid))==1
    with pytest.raises(KeyError):store.evaluate('bob',tid)
    with pytest.raises(KeyError):store.history('bob',tid)
    assert store.delete_owner('alice')['deleted']
    with pytest.raises(KeyError):store.evaluate('alice',tid)

def test_unreviewed_milestone_does_not_raise_score(tmp_path):
    store=Ledger(tmp_path/'test.db')
    tid=store.create_target('alice','DevOps',[{'skill':'docker','weight':1,'required_level':2}])
    mid=store.create_milestone('alice',tid,'docker',['Dockerfile','tests'])
    baseline=store.evaluate('alice',tid)['score']
    result=store.submit_milestone('alice',mid,'https://github.com/example/repo/commit/abc')
    assert result['verified'] is False
    assert store.evaluate('alice',tid)['score']==baseline
    with pytest.raises(KeyError):store.submit_milestone('bob',mid,'https://github.com/example/repo/commit/def')

def test_claim_confidence_is_capped(tmp_path):
    store=Ledger(tmp_path/'test.db')
    store.add_evidence('alice','python',4,1,'cv_claim')
    with store.db() as db:
        assert db.execute('SELECT confidence FROM evidence').fetchone()[0]==.35
    with pytest.raises(ValueError):store.add_evidence('alice','python',4,1,'reviewed_project')

def test_persistent_routes_fail_closed_without_config(monkeypatch):
    monkeypatch.delenv('CODEVERSE_JWT_ISSUER',raising=False)
    monkeypatch.delenv('CODEVERSE_LEDGER_DB',raising=False)
    client=TestClient(app)
    assert client.post('/api/v1/targets',json={'job_title':'Backend','requirements':[{'skill':'python'}]}).status_code==503
    assert client.delete('/api/v1/account').status_code==503

def test_public_scan_claim_cannot_be_manually_asserted(monkeypatch,tmp_path):
    from services.api.identity import authenticated_user
    app.dependency_overrides[authenticated_user]=lambda:'alice'
    monkeypatch.setenv('CODEVERSE_LEDGER_DB',str(tmp_path/'test.db'))
    try:
        client=TestClient(app)
        r=client.post('/api/v1/evidence',json={'skill':'kubernetes','source':'github_static','level':4,'confidence':1})
        assert r.status_code==422
        r=client.post('/api/v1/evidence',json={'skill':'python','source':'cv_claim','level':4,'confidence':1})
        assert r.status_code==200
    finally:
        app.dependency_overrides.clear()

def test_webhook_signature():
    from services.api.webhook_security import verify_github_signature
    import hashlib,hmac
    body=b'{"action":"push"}'
    sig='sha256='+hmac.new(b'secret',body,hashlib.sha256).hexdigest()
    assert verify_github_signature(body,sig,'secret')
    assert not verify_github_signature(body+b'!',sig,'secret')
    assert not verify_github_signature(body,sig,'')
