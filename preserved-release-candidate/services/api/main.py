"""Local-first demonstration API. Not a multi-tenant production service."""
from __future__ import annotations
import io, os, re, json, secrets
from .github_client import collect_public_repository, GithubCollectionError
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .core import extract_skills, readiness, job_requirements, recommend_projects, evidence_from_github, verify_challenge, TAXONOMY

app=FastAPI(title='CODEVERSE Evidence Engine',version='0.1.0',docs_url='/api/docs',redoc_url=None)
STUDIO=Path(__file__).resolve().parents[2]/'apps/studio/index.html'
MAX_CV=2*1024*1024

@app.middleware('http')
async def security_headers(request:Request,call_next):
    response=await call_next(request)
    response.headers.update({'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','X-Frame-Options':'DENY','Cache-Control':'no-store','Content-Security-Policy':"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'"})
    return response

@app.get('/studio')
def studio():return FileResponse(STUDIO,media_type='text/html')

@app.get('/api/health')
def health():return {'status':'ok','mode':'local_demo','production_ready':False}

@app.get('/api/taxonomy')
def taxonomy(search:str='',limit:int=Query(default=50,ge=1,le=300)):
    term=search.strip().casefold()
    return {'count':len(TAXONOMY['technologies']), 'results':[t for t in TAXONOMY['technologies'] if term in t['name'].casefold() or term in t['category'].casefold()][:min(300,max(1,limit))]}

@app.post('/api/cv/extract')
async def extract_cv(file:UploadFile=File(...)):
    fname=(file.filename or '').lower(); ext=Path(fname).suffix
    if ext not in ('.txt','.pdf','.docx'):raise HTTPException(415,'Use TXT, PDF or DOCX')
    raw=await file.read(MAX_CV+1)
    if len(raw)>MAX_CV:raise HTTPException(413,'CV exceeds 2MB')
    try:
        if ext=='.pdf':
            if not raw.startswith(b'%PDF-'):raise ValueError('Invalid PDF signature')
            from pypdf import PdfReader
            pdf=PdfReader(io.BytesIO(raw));
            if len(pdf.pages)>25:raise ValueError('PDF has too many pages')
            text='\n'.join((page.extract_text() or '') for page in pdf.pages)
        elif ext=='.docx':
            if raw[:2]!=b'PK':raise ValueError('Invalid DOCX signature')
            from docx import Document
            text='\n'.join(p.text for p in Document(io.BytesIO(raw)).paragraphs)
        else:
            text=raw.decode('utf-8-sig')
    except Exception as exc:raise HTTPException(422,'Unable to parse document') from exc
    # Avoid returning raw CV data. No persistence or external AI calls.
    return {'skills':extract_skills(text[:150_000]),'extraction':'deterministic_local','stored':False,'warning':'CV matches are self-reported claims, not verified proficiency.'}

class Req(BaseModel):
    skill:str=Field(min_length=1,max_length=100)
    weight:float=Field(default=1,ge=0,le=100)
    required_level:float=Field(default=2,gt=0,le=4)
class Evidence(BaseModel):
    id:str|None=None
    skill:str=Field(min_length=1,max_length=100)
    level:float=Field(ge=0,le=4)
    confidence:float=Field(ge=0,le=1)
    freshness:float=Field(default=1,ge=0,le=1)
    source:str='cv_claim'
class Milestone(BaseModel):
    weight:float=Field(default=1,ge=0,le=100)
    verified:bool=False
class Evaluation(BaseModel):
    requirements:list[Req]=Field(min_length=1,max_length=60)
    evidence:list[Evidence]=Field(default_factory=list,max_length=500)
    milestones:list[Milestone]=Field(default_factory=list,max_length=100)
    experience:float=Field(default=0,ge=0,le=1)

@app.post('/api/readiness/evaluate')
def evaluate(body:Evaluation):
    result=readiness([r.model_dump() for r in body.requirements],[e.model_dump() for e in body.evidence], [m.model_dump() for m in body.milestones],body.experience)
    result['recommendations']=recommend_projects(result)
    return result

class JobInput(BaseModel):
    text:str=Field(min_length=15,max_length=20_000)
@app.post('/api/jobs/parse')
def parse_job(body:JobInput):
    return {'requirements':job_requirements(body.text),'method':'taxonomy_keyword','requires_review':True}

class PublicScan(BaseModel):
    repository:str=Field(pattern=r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$',max_length=200)

@app.post('/api/github/public-scan')
async def public_scan(body:PublicScan):
    owner,repo=body.repository.split('/')
    try:return await collect_public_repository(owner,repo)
    except GithubCollectionError as exc:raise HTTPException(400,str(exc)) from exc

class GithubScan(BaseModel):
    repo:str=Field(pattern=r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$',max_length=200)
    sha:str=Field(default='',max_length=80)
    files:dict[str,str]=Field(default_factory=dict,max_length=30)
@app.post('/api/github/static-evidence')
def static_evidence(body:GithubScan):
    if sum(len(s) for s in body.files.values())>500_000:raise HTTPException(413,'Source excerpt limit exceeded')
    return {'evidence':evidence_from_github({'full_name':body.repo,'sha':body.sha},body.files),'executed_code':False,'attribution_verified':False}

class ChallengeProof(BaseModel):
    criteria:list[str]
    proofs:list[str]
@app.post('/api/projects/check')
def check_project(body:ChallengeProof):return verify_challenge(body.criteria,body.proofs)

# Authenticated, opt-in persistent API; imported last to avoid model-definition cycle.
from .protected import router as protected_router
app.include_router(protected_router)

from .workflow_api import router as workflow_router
app.include_router(workflow_router)

WORKSPACE=Path(__file__).resolve().parents[2]/'apps/workspace/index.html'
@app.get('/workspace')
def workspace():return FileResponse(WORKSPACE,media_type='text/html')

from .github_webhooks import router as github_webhook_router
app.include_router(github_webhook_router)
