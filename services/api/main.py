"""Local-first demonstration API. Not a multi-tenant production service."""
from __future__ import annotations
import io, os, re, json, secrets
from .github_client import collect_public_repository, collect_public_repositories, GithubCollectionError
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .core import extract_skills, extract_skills_with_sources, readiness, job_requirements, recommend_projects, evidence_from_github, verify_challenge, TAXONOMY

app=FastAPI(title='CODEVERSE Evidence Engine',version='0.1.0',docs_url='/api/docs',redoc_url=None)
STUDIO=Path(__file__).resolve().parents[2]/'apps/studio/index.html'
MAX_CV=2*1024*1024

@app.middleware('http')
async def security_headers(request:Request,call_next):
    if os.environ.get('CODEVERSE_SECURE_MODE') == '1':
        from fastapi.responses import JSONResponse
        # Legacy demonstration pages and unguarded APIs stay available in development
        # but are hidden in secure deployments to prevent role-policy bypass.
        legacy_pages = {'/studio','/workspace','/career-journey','/github-start.html',
                        '/city-explorer.html','/apps/studio','/apps/workspace'}
        path = request.url.path
        safe_public = path in {'/api/health','/api/secure/config','/secure','/start','/admin',
                               '/api/github/repositories','/internal/metrics'}
        if path in legacy_pages or (path.startswith('/api/') and not (
                path.startswith('/api/secure/') or path.startswith('/api/v1/') or safe_public)):
            return JSONResponse(status_code=403, content={'detail':'Legacy demo route disabled in secure mode'})
    response=await call_next(request)
    response.headers.update({'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','X-Frame-Options':'DENY','Cache-Control':'no-store','Content-Security-Policy':"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data: https://avatars.githubusercontent.com; connect-src 'self' https://*.supabase.co https://api.github.com; frame-src 'self' http://127.0.0.1:3000 http://localhost:3000"})
    if request.url.path == '/' or request.url.path.startswith('/assets/'):
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self' https://*.supabase.co https://api.github.com; "
            "img-src 'self' data: https://avatars.githubusercontent.com; "
            "font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
    if request.url.path in ('/secure', '/start', '/admin'):
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self' https:; img-src 'self' data:; "
            "frame-src 'none'; object-src 'none'; frame-ancestors 'none'"
        )
    if request.url.path.startswith('/api/secure/') and response.status_code in (401,403):
        try:
            from .security_portal import ACCESS_EVENTS
            if ACCESS_EVENTS is not None:
                ACCESS_EVENTS.labels(role='anonymous' if response.status_code == 401 else 'restricted',
                                     action='http_access',outcome='denied').inc()
        except ImportError:
            pass
    return response

@app.get('/studio')
def studio():return FileResponse(STUDIO,media_type='text/html')



@app.get('/api/health')
def health():return {'status':'ok','mode':'secure','production_ready':False}

@app.get('/api/taxonomy')
def taxonomy(search:str='',limit:int=Query(default=50,ge=1,le=300)):
    term=search.strip().casefold()
    return {'count':len(TAXONOMY['technologies']), 'results':[t for t in TAXONOMY['technologies'] if term in t['name'].casefold() or term in t['category'].casefold()][:min(300,max(1,limit))]}

def normalize_spaced_pdf_text(text:str)->tuple[str,bool]:
    """Repair PDF generators that insert spaces between every glyph.

    Apply only to long, predominantly single-character sequences separated by
    one space, while preserving >=2 spaces between actual words. Does not OCR.
    """
    fixed=[];changed=False
    for line in text.splitlines():
        pieces=re.split(r'( {2,})',line)
        for i,part in enumerate(pieces):
            if i%2:continue
            parts=part.split(' ')
            words=[x for x in parts if x]
            if (len(words)>=6 and sum(len(x)==1 for x in words)/len(words)>.80) or (2<=len(words)<=4 and all(len(x)==1 for x in words)):
                pieces[i]=''.join(parts);changed=True
        fixed.append(''.join(pieces))
    return '\n'.join(fixed),changed

@app.post('/api/cv/extract')
async def extract_cv(file:UploadFile=File(...)):
    fname=(file.filename or '').lower(); ext=Path(fname).suffix
    if ext not in ('.txt','.pdf','.docx'):raise HTTPException(415,'Use TXT, PDF or DOCX')
    raw=await file.read(MAX_CV+1)
    if len(raw)>MAX_CV:raise HTTPException(413,'CV exceeds 2MB')
    pages=[];warnings=[]
    try:
        if ext=='.pdf':
            if not raw.startswith(b'%PDF-'):raise ValueError('Invalid PDF signature')
            from pypdf import PdfReader
            pdf=PdfReader(io.BytesIO(raw))
            if len(pdf.pages)>25:raise ValueError('PDF has too many pages')
            for i,page in enumerate(pdf.pages,1):
                content=page.extract_text() or ''
                content, repaired=normalize_spaced_pdf_text(content)
                if repaired:warnings.append(f'Page {i}: normalized unusual character-spaced PDF text; please review detected excerpts.')
                if not content.strip():warnings.append(f'Page {i} has no extractable text; scanned/image content may require OCR.')
                pages.append({'page':i,'text':content,'document':file.filename,'section':None})
        elif ext=='.docx':
            if raw[:2]!=b'PK':raise ValueError('Invalid DOCX signature')
            from docx import Document
            doc=Document(io.BytesIO(raw))
            blocks=[p.text for p in doc.paragraphs]
            for table in doc.tables:
                for row in table.rows:
                    blocks.append(' | '.join(cell.text for cell in row.cells))
            pages=[{'page':None,'text':'\n'.join(blocks),'document':file.filename,'section':None}]
        else:
            pages=[{'page':None,'text':raw.decode('utf-8-sig'),'document':file.filename,'section':None}]
    except Exception as exc:raise HTTPException(422,'Unable to parse document') from exc
    if not any(p['text'].strip() for p in pages):raise HTTPException(422,'No extractable text found. Scanned documents require an OCR step.')
    return {'skills':extract_skills_with_sources(pages),'extraction':'deterministic_local',
       'stored':False,'warnings':warnings,
       'warning':'CV matches are claims until supported by repository evidence; repository detection is not proof of authorship.'}

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

# Public discovery endpoints contain only public data. Production skill ledgers remain authenticated.
@app.get('/api/github/repositories')
async def github_repositories(owner:str=Query(min_length=1,max_length=39)):
    try:return await collect_public_repositories(owner)
    except GithubCollectionError as exc:raise HTTPException(400,str(exc)) from exc

@app.post('/api/github/analyze')
async def github_analyze(body:PublicScan):
    try:return await collect_public_repository(*body.repository.split('/'))
    except GithubCollectionError as exc:raise HTTPException(400,str(exc)) from exc

from .role_recommender import recommend_roles, skill_evidence_from_claims_and_repos
class RecommendedRolesInput(BaseModel):
    skills:list[str]=Field(default_factory=list,max_length=250)
    github_evidence:list[dict]=Field(default_factory=list,max_length=500)
@app.post('/api/jobs/profiles/recommended')
def recommended_roles(body:RecommendedRolesInput):
    return {'profiles':recommend_roles(body.skills,body.github_evidence),
      'method':'deterministic_skill_overlap','requirements_source':'curated_local_profiles','verified_employment_probability':False}

class UnifiedEvidenceInput(BaseModel):
    claims:list[dict]=Field(default_factory=list,max_length=250)
    repositories:list[dict]=Field(default_factory=list,max_length=100)
@app.post('/api/skills/consolidate')
def skills_consolidate(body:UnifiedEvidenceInput):
    return {'skills':skill_evidence_from_claims_and_repos(body.claims,body.repositories)}

@app.get('/api/jobs/live')
async def live_jobs(location:str=Query(default='',max_length=150)):
    from .career_pipeline import fetch_jobs,ProviderUnavailable
    try:
        jobs=await fetch_jobs(limit=40,pages=1)
    except ProviderUnavailable as exc:
        raise HTTPException(status_code=503,detail='Live provider unavailable; no vacancies were invented') from exc
    loc=location.strip().casefold()
    if loc:jobs=[j for j in jobs if loc in str(j.get('location','')).casefold() or (loc=='remote' and j.get('remote'))]
    return {'offers':jobs,'source':'Arbeitnow','count':len(jobs),'live_data':True}

# Production-capable security portal is opt-in and rejects requests without Supabase config.
from .security_portal import router as secure_router
app.include_router(secure_router)

# Glass workspace entrypoint; legacy routes remain preserved for operator use.
from .glass_workspace import router as glass_router
app.include_router(glass_router)
from .glass_features import router as glass_features_router
app.include_router(glass_features_router)
from fastapi.staticfiles import StaticFiles
DIST=Path(__file__).resolve().parents[2]/'dist'
if DIST.exists():
    app.mount('/',StaticFiles(directory=DIST,html=True),name='glass-frontend')
