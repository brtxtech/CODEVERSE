"""Authenticated GitHub event ingress, durable bounded queue, and idempotent delivery storage.

The queue does not grant evidence: a worker must validate installation access and authorship.
"""
import os, sqlite3, json
from pathlib import Path
from datetime import datetime,timezone
from fastapi import APIRouter,Request,HTTPException
from .webhook_security import verify_github_signature

router=APIRouter(tags=['GitHub App webhook'])
ALLOWED={'push','installation','installation_repositories','pull_request','workflow_run'}
MAX_BYTES=256_000

def init_queue(db_path):
    db=sqlite3.connect(str(db_path),timeout=5)
    db.execute('''CREATE TABLE IF NOT EXISTS github_deliveries(
      delivery_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, installation_id INTEGER,
      repo TEXT, action TEXT, status TEXT NOT NULL DEFAULT 'pending',
      received_at TEXT NOT NULL, error TEXT)''')
    db.commit()
    return db

def enqueue(db_path,delivery_id,event_type,payload):
    installation=payload.get('installation') or {}
    repo=(payload.get('repository') or {}).get('full_name')
    action=payload.get('action')
    with init_queue(db_path) as db:
        cursor=db.execute('INSERT OR IGNORE INTO github_deliveries(delivery_id,event_type,installation_id,repo,action,received_at) VALUES(?,?,?,?,?,?)',
          (delivery_id,event_type,installation.get('id'),repo,action,datetime.now(timezone.utc).isoformat()))
        return cursor.rowcount==1

@router.post('/api/webhooks/github')
async def github_webhook(request:Request):
    secret=os.getenv('GITHUB_WEBHOOK_SECRET','')
    queue=os.getenv('CODEVERSE_WEBHOOK_DB','')
    if not secret or not queue:raise HTTPException(503,'Webhook delivery persistence not configured')
    size=request.headers.get('content-length')
    if size and (not size.isdigit() or int(size)>MAX_BYTES):raise HTTPException(413,'Payload too large')
    body=await request.body()
    if len(body)>MAX_BYTES:raise HTTPException(413,'Payload too large')
    if not verify_github_signature(body,request.headers.get('x-hub-signature-256'),secret):
        raise HTTPException(401,'Invalid webhook signature')
    event=request.headers.get('x-github-event','')
    delivery=request.headers.get('x-github-delivery','')
    if not delivery or len(delivery)>128:raise HTTPException(400,'Delivery ID required')
    if event not in ALLOWED:return {'accepted':False,'reason':'Ignored event type'}
    try:payload=json.loads(body)
    except ValueError:raise HTTPException(400,'Invalid JSON payload')
    if not isinstance(payload,dict):raise HTTPException(400,'Expected object payload')
    if not (payload.get('installation') or {}).get('id'):
        raise HTTPException(400,'Installation ID required')
    Path(queue).parent.mkdir(parents=True,exist_ok=True)
    created=enqueue(queue,delivery,event,payload)
    return {'accepted':True,'queued':created,'duplicate':not created,'verification':'signature_valid','evidence_verified':False}
