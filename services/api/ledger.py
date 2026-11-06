"""Local development evidence ledger. Tenant-scoped queries and append-only score snapshots.
Production deployments MUST replace SQLite with the supplied PostgreSQL/RLS schema.
"""
import sqlite3, json, hashlib, secrets
from datetime import datetime,timezone
from pathlib import Path
from .core import readiness, normalize_skill

def now():return datetime.now(timezone.utc).isoformat()
class Ledger:
    def __init__(self,path):
        self.path=str(path)
        self._init()
    def db(self):
        conn=sqlite3.connect(self.path,timeout=8)
        conn.row_factory=sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA busy_timeout=4000')
        return conn
    def _init(self):
        with self.db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS targets(id TEXT PRIMARY KEY,owner TEXT NOT NULL,job_title TEXT NOT NULL,requirements TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS targets_owner ON targets(owner);
            CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY,owner TEXT NOT NULL,skill TEXT NOT NULL,level REAL NOT NULL,confidence REAL NOT NULL,freshness REAL NOT NULL,source TEXT NOT NULL,repo TEXT,commit_sha TEXT,created_at TEXT NOT NULL,UNIQUE(owner,skill,source,repo,commit_sha));
            CREATE INDEX IF NOT EXISTS evidence_owner ON evidence(owner);
            CREATE TABLE IF NOT EXISTS milestones(id TEXT PRIMARY KEY,owner TEXT NOT NULL,target_id TEXT NOT NULL,skill TEXT NOT NULL,criteria TEXT NOT NULL,verification_status TEXT NOT NULL DEFAULT 'pending',review_reference TEXT,created_at TEXT NOT NULL,FOREIGN KEY(target_id) REFERENCES targets(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS snapshots(id TEXT PRIMARY KEY,owner TEXT NOT NULL,target_id TEXT NOT NULL,score REAL NOT NULL,details TEXT NOT NULL,input_hash TEXT NOT NULL,created_at TEXT NOT NULL,FOREIGN KEY(target_id) REFERENCES targets(id) ON DELETE CASCADE);
            CREATE INDEX IF NOT EXISTS snapshots_owner_target ON snapshots(owner,target_id,created_at);
            """)
    def create_target(self,owner,title,requirements):
        ident=secrets.token_hex(16)
        with self.db() as db:db.execute('INSERT INTO targets VALUES(?,?,?,?,?)',(ident,owner,title,json.dumps(requirements,sort_keys=True),now()))
        return ident
    def add_evidence(self,owner,skill,level,confidence,source,freshness=1,repo=None,commit_sha=None):
        if source not in ('cv_claim','github_static','reviewed_project'):
            raise ValueError('Invalid evidence source')
        if source=='reviewed_project':raise ValueError('Reviewed evidence requires a separate trusted review process')
        if source=='cv_claim':confidence=min(confidence,0.35)
        if source=='github_static':confidence=min(confidence,0.65)
        if not 0<=level<=4 or not 0<=confidence<=1 or not 0<=freshness<=1:raise ValueError('Invalid evidence range')
        ident=secrets.token_hex(16)
        with self.db() as db:
            db.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?,?,?)',(ident,owner,normalize_skill(skill),level,confidence,freshness,source,repo,commit_sha,now()))
        return ident
    def evaluate(self,owner,target_id):
        with self.db() as db:
            target=db.execute('SELECT * FROM targets WHERE id=? AND owner=?',(target_id,owner)).fetchone()
            if not target:raise KeyError('Target not found')
            evidence=[dict(r) for r in db.execute('SELECT * FROM evidence WHERE owner=?',(owner,))]
            milestones=[{'weight':1,'verified':r['verification_status']=='reviewed'} for r in db.execute('SELECT * FROM milestones WHERE owner=? AND target_id=?',(owner,target_id))]
            requirements=json.loads(target['requirements'])
            result=readiness(requirements,evidence,milestones)
            fingerprint=hashlib.sha256(json.dumps({'requirements':requirements,'evidence':evidence,'milestones':milestones},sort_keys=True).encode()).hexdigest()
            ident=secrets.token_hex(16)
            db.execute('INSERT INTO snapshots VALUES(?,?,?,?,?,?,?)',(ident,owner,target_id,result['score'],json.dumps(result),fingerprint,now()))
            return {'snapshot_id':ident,'target_id':target_id,'input_hash':fingerprint,**result}
    def history(self,owner,target_id):
        with self.db() as db:
            if not db.execute('SELECT 1 FROM targets WHERE owner=? AND id=?',(owner,target_id)).fetchone():raise KeyError('Target not found')
            return [dict(row) for row in db.execute('SELECT id,score,input_hash,created_at FROM snapshots WHERE owner=? AND target_id=? ORDER BY created_at,id',(owner,target_id))]
    def create_milestone(self,owner,target_id,skill,criteria):
        if not 1<=len(criteria)<=20:raise ValueError('Criteria count invalid')
        ident=secrets.token_hex(16)
        with self.db() as db:
            if not db.execute('SELECT 1 FROM targets WHERE owner=? AND id=?',(owner,target_id)).fetchone():raise KeyError('Target not found')
            db.execute('INSERT INTO milestones(id,owner,target_id,skill,criteria,created_at) VALUES(?,?,?,?,?,?)',(ident,owner,target_id,normalize_skill(skill),json.dumps(criteria),now()))
        return ident
    def submit_milestone(self,owner,milestone_id,reference):
        with self.db() as db:
            result=db.execute("UPDATE milestones SET verification_status='submitted',review_reference=? WHERE owner=? AND id=? AND verification_status='pending'",(reference,owner,milestone_id))
            if result.rowcount!=1:raise KeyError('Milestone not found or already submitted')
        return {'verification_status':'submitted','verified':False,'requires_review':True}
    def delete_owner(self,owner):
        with self.db() as db:
            for table in ('snapshots','milestones','evidence','targets'):
                db.execute(f'DELETE FROM {table} WHERE owner=?',(owner,))
        return {'deleted':True,'scope':'local evidence ledger only','other_processors_notified':False}
