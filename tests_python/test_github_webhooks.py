import hmac,hashlib,json
from fastapi.testclient import TestClient
from services.api.github_webhooks import enqueue,init_queue
from services.api.main import app

def test_deduplicate(tmp_path):
    path=tmp_path/'events.db'
    payload={'installation':{'id':7},'repository':{'full_name':'org/repo'}}
    assert enqueue(path,'a','push',payload)
    assert not enqueue(path,'a','push',payload)
    with init_queue(path) as db:
        assert db.execute('select count(*) from github_deliveries').fetchone()[0]==1

def test_webhook_signature_and_replay(monkeypatch,tmp_path):
    monkeypatch.setenv('GITHUB_WEBHOOK_SECRET','local-test-only')
    monkeypatch.setenv('CODEVERSE_WEBHOOK_DB',str(tmp_path/'events.db'))
    body=json.dumps({'installation':{'id':7},'repository':{'full_name':'org/repo'}}).encode()
    headers={'x-github-event':'push','x-github-delivery':'test-1','x-hub-signature-256':'sha256='+hmac.new(b'local-test-only',body,hashlib.sha256).hexdigest()}
    with TestClient(app) as client:
        assert client.post('/api/webhooks/github',data=body,headers={**headers,'x-hub-signature-256':'sha256='+'0'*64}).status_code==401
        first=client.post('/api/webhooks/github',data=body,headers=headers)
        assert first.status_code==200 and first.json()['queued'] is True
        repeated=client.post('/api/webhooks/github',data=body,headers=headers)
        assert repeated.status_code==200 and repeated.json()['duplicate'] is True
        assert repeated.json()['evidence_verified'] is False

def test_webhook_disabled(monkeypatch):
    monkeypatch.delenv('GITHUB_WEBHOOK_SECRET',raising=False)
    with TestClient(app) as client:
        assert client.post('/api/webhooks/github',data=b'{}').status_code==503
