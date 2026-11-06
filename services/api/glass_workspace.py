"""Glass workspace: public discovery, owner-scoped persistence and explicit integrations."""
from __future__ import annotations
import asyncio, base64, hashlib, json, os, re, secrets, subprocess, tempfile, time
from datetime import datetime, timezone
from pathlib import Path
from functools import lru_cache
from urllib.parse import urlencode, urlparse
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, ConfigDict
from .security_portal import context, store, configured
from .github_client import collect_public_repositories, collect_public_repository, GithubCollectionError, _headers
from .core import extract_skills, normalize_skill, TAXONOMY
from .role_recommender import recommend_roles

router=APIRouter(prefix='/api/v1/glass',tags=['Glass workspace'])
ROOT=Path(__file__).resolve().parents[2]
CATALOG=json.loads((ROOT/'data/repository-catalog.json').read_text())
PUBLIC_LIMITS={}
CATALOG_METRICS={}
def limited(request:Request):
    key=request.client.host if request.client else 'unknown';now=time.monotonic()
    if len(PUBLIC_LIMITS)>5000:PUBLIC_LIMITS.clear()
    recent=[t for t in PUBLIC_LIMITS.get(key,[]) if now-t<60]
    if len(recent)>=12:raise HTTPException(429,'Discovery limit reached. Retry in one minute.')
    PUBLIC_LIMITS[key]=recent+[now]

@lru_cache(maxsize=2000)
def catalog_refs(text,skills):
    return frozenset({normalize_skill(s) for s in skills}|{normalize_skill(x['name']) for x in extract_skills(text)})
def rank_catalog(skills:list[str],target:str='',rows=None,limit=18):
    terms={normalize_skill(s) for s in skills if s}
    ranked=[]
    for row in (rows if rows is not None else CATALOG):
        refs=catalog_refs(row['search_text'],tuple(row.get('skills',[])))
        matched=sorted(terms & refs)
        ranked.append({**row,'matched_skills':matched,'match_score':len(matched),
                       'reason':', '.join(matched) if matched else 'Explore a complementary technology'})
    return sorted(ranked,key=lambda r:(-r['match_score'],-(r.get('stars') or 0),r['id']))[:limit]

async def catalog_rows():
    # The bundled seed keeps public discovery available before deployment configuration.
    if os.getenv('SUPABASE_URL') and os.getenv('SUPABASE_SERVICE_ROLE_KEY'):
        try:
            rows=await store.request('GET','codeverse_repo_catalog',params={'select':'data','limit':'1000'})
            if rows:return [r['data'] for r in rows]
        except HTTPException:pass
    return CATALOG

@router.get('/catalog')
async def catalog(skills:str='',limit:int=18):
    limit=max(1,min(100,limit))
    rows=await catalog_rows()
    return {'repositories':rank_catalog(skills[:500].split(','),rows=rows,limit=limit),'count':len(rows),'metrics':'Live values are fetched separately; seed has no invented star counts.'}

@router.get('/discover')
async def discover(request:Request,owner:str):
    limited(request)
    try:result=await collect_public_repositories(owner,max_repos=100)
    except (GithubCollectionError,httpx.HTTPError) as e:raise HTTPException(422,'GitHub request failed: '+str(e)) from e
    # Enrich only the first 12 repositories to respect GitHub's unauthenticated quota.
    sem=asyncio.Semaphore(3)
    async with httpx.AsyncClient(timeout=12,headers=_headers(os.getenv('GITHUB_READ_TOKEN'))) as client:
        async def metrics(repo):
            repo['commits']=None;repo['commit_scope']='default branch';repo['technologies']=[repo['language']] if repo.get('language') else []
            async with sem:
                try:
                    r=await client.get(f'https://api.github.com/repos/{repo["full_name"]}/commits',params={'per_page':1})
                    if r.status_code==200:
                        last=re.search(r'[?&]page=(\d+)>; rel="last"',r.headers.get('link',''))
                        repo['commits']=int(last.group(1)) if last else len(r.json())
                    elif r.status_code==409:repo['commits']=0
                except httpx.HTTPError:pass
        await asyncio.gather(*(metrics(r) for r in result['repositories'][:12]))
    for r in result['repositories'][12:]:r.update(commits=None,technologies=[r['language']] if r.get('language') else [])
    skills=sorted({r['language'] for r in result['repositories'] if r.get('language')})
    return {**result,'skills':skills,'recommendations':rank_catalog(skills),'checked_at':datetime.now(timezone.utc).isoformat(),'truncated':len(result['repositories'])==100,'commit_limit':12}

@router.get('/catalog/metrics')
async def repo_metrics(request:Request,repository:str):
    cached=CATALOG_METRICS.get(repository)
    if cached and time.monotonic()-cached[0]<600:return cached[1]
    limited(request)
    if repository not in {r['id'] for r in CATALOG}:raise HTTPException(422,'Choose a catalog repository')
    async with httpx.AsyncClient(timeout=12,headers=_headers(os.getenv('GITHUB_READ_TOKEN'))) as c:
        try:r=await c.get('https://api.github.com/repos/'+repository)
        except httpx.HTTPError as e:raise HTTPException(503,'GitHub unavailable') from e
    if r.status_code!=200:raise HTTPException(503,'GitHub rate limit or unavailable repository')
    d=r.json();metric={'stars':d['stargazers_count'],'archived':d['archived'],'license':(d.get('license') or {}).get('spdx_id'),'pushed_at':d.get('pushed_at'),'checked_at':datetime.now(timezone.utc).isoformat()}
    CATALOG_METRICS[repository]=(time.monotonic(),metric)
    for row in CATALOG:
        if row['id']==repository:row.update(metric)
    if os.getenv('SUPABASE_URL') and os.getenv('SUPABASE_SERVICE_ROLE_KEY'):
        try:await store.request('PATCH','codeverse_repo_catalog',params={'id':'eq.'+repository},payload={'data':next(row for row in CATALOG if row['id']==repository)},prefer='return=minimal')
        except HTTPException:pass
    return metric

async def load(user):
    rows=await store.request('GET','codeverse_workspace_state',params={'user_id':f'eq.{user}','select':'payload,revision','limit':'1'})
    return rows[0] if rows else {'payload':{'journey':[],'companies':[],'applications':[],'nodes':[],'datasets':[]},'revision':0}
async def save(user,payload,revision):
    if len(json.dumps(payload))>3_000_000:raise HTTPException(413,'Workspace limit is 3 MB')
    if revision:
        rows=await store.request('PATCH','codeverse_workspace_state',params={'user_id':f'eq.{user}','revision':f'eq.{revision}'},payload={'payload':payload,'revision':revision+1,'updated_at':datetime.now(timezone.utc).isoformat()},prefer='return=representation')
        if not rows:raise HTTPException(409,'Workspace changed in another tab. Reload before saving.')
    else:
        # No upsert: simultaneous first saves cannot overwrite another workspace.
        await store.request('POST','codeverse_workspace_state',payload={'user_id':user,'payload':payload,'revision':1},prefer='return=minimal')
    return revision+1

@router.get('/state')
async def state(ctx=Depends(context)):return await load(ctx['user'])

class WorkspacePatch(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:int=Field(ge=0)
    companies:list[dict]|None=Field(default=None,max_length=100)
    applications:list[dict]|None=Field(default=None,max_length=300)
    nodes:list[dict]|None=Field(default=None,max_length=40)
    datasets:list[dict]|None=Field(default=None,max_length=30)
    skills_inventory:list[dict]|None=Field(default=None,max_length=50)
@router.patch('/state')
async def patch(body:WorkspacePatch,ctx=Depends(context)):
    current=await load(ctx['user'])
    if current['revision']!=body.revision:raise HTTPException(409,'Reload your workspace before saving')
    changes=body.model_dump(exclude={'revision'},exclude_none=True)
    if 'nodes' in changes:
        try:graph_order(changes['nodes'])
        except ValueError as e:raise HTTPException(422,str(e)) from e
    from .glass_features import dataset_value
    if 'datasets' in changes:
        ids=[d.get('id') for d in changes['datasets']]
        if len(set(ids))!=len(ids) or any(not isinstance(i,str) for i in ids):raise HTTPException(422,'Datasets require unique IDs')
        for d in changes['datasets']:dataset_value(d)
    if 'skills_inventory' in changes:
        for skill in changes['skills_inventory']:
            if not isinstance(skill.get('code',''),str) or len(skill.get('code',''))>20000:raise HTTPException(422,'Skill code exceeds limits')
    if 'companies' in changes:
        for c in changes['companies']:
            if not c.get('name') or len(str(c['name']))>160:raise HTTPException(422,'Company name is required')
            if c.get('url') and urlparse(c['url']).scheme!='https':raise HTTPException(422,'Career page must use HTTPS')
            if c.get('provider') not in (None,'','greenhouse','lever'):raise HTTPException(422,'Unsupported structured provider')
    payload=current['payload'];payload.update(changes)
    return {'revision':await save(ctx['user'],payload,current['revision'])}

class StudentProfile(BaseModel):
    model_config=ConfigDict(extra='forbid')
    full_name:str=Field(default='',max_length=120)
    university:str=Field(default='',max_length=160)
    education:str=Field(default='',max_length=300)
    experience:str=Field(default='',max_length=1500)
    availability:str=Field(default='',max_length=160)
    portfolio:str=Field(default='',max_length=300)
class Stage(BaseModel):
    model_config=ConfigDict(extra='forbid')
    text:str=Field(default='',max_length=12000)
    target:str=Field(default='',max_length=100)
    location:str=Field(default='',max_length=120)
    acknowledge:bool=False
    profile:StudentProfile=Field(default_factory=StudentProfile)
    ratings:dict[str,int]=Field(default_factory=dict,max_length=250)
@router.post('/journey/{step:int}')
async def journey(step:int,body:Stage,ctx=Depends(context)):
    state=await load(ctx['user']);p=state['payload'];history=p.setdefault('journey',[])
    if step!=len(history)+1 or not 1<=step<=7:raise HTTPException(409,'Complete each step in sequence')
    result=body.model_dump()
    if any(not 0<=level<=4 for level in body.ratings.values()):raise HTTPException(422,'Skill self-ratings must be between 0 and 4')
    if step==1:
        if len(body.text.strip())<10:raise HTTPException(422,'Add your CV or a short background')
        found=extract_skills(body.text);result['skills']=[s.get('name',s.get('id','')) if isinstance(s,dict) else s for s in found]
        result.pop('text',None)
        result['source']='CV skill claims; full CV text was not stored'
    elif step==2:
        # Identity is read from the authenticated Supabase GitHub identity, not an editable form.
        owner=ctx['profile'].get('github_username')
        if not owner:raise HTTPException(422,'Sign in with GitHub to attach your identity')
        try:repos=await collect_public_repositories(owner)
        except (GithubCollectionError,httpx.HTTPError) as e:raise HTTPException(422,'GitHub request failed: '+str(e)) from e
        scans=[];warnings=[]
        for repo in [r for r in repos['repositories'] if not r.get('fork')][:2]:
            try:
                scanned=await collect_public_repository(*repo['full_name'].split('/'))
                scans.append({'repository':scanned['repository'],'sha':scanned['sha'],'evidence':scanned['evidence']})
            except (GithubCollectionError,httpx.HTTPError):warnings.append('Manifest scan unavailable for '+repo['full_name'])
        result={'owner':owner,'repositories':repos['repositories'],'manifest_scans':scans,'warnings':warnings}

    elif step==4:
        if body.target not in {r['id'] for r in recommend_roles([],limit=20)}:raise HTTPException(422,'Select a career profile')
    elif not body.acknowledge:raise HTTPException(422,'Review this step before continuing')
    history.append(result)
    if step==5:
        from .glass_features import suggested_companies
        existing=p.setdefault('companies',[]);urls={c.get('url') for c in existing}
        existing.extend(c for c in suggested_companies(p['journey'][3].get('target','')) if c['url'] not in urls)
    p.get('drafts',{}).pop(str(step),None)
    if step==7:p['submitted_at']=datetime.now(timezone.utc).isoformat()
    revision=await save(ctx['user'],p,state['revision'])
    return {'result':result,'revision':revision,'submitted':step==7}

@router.post('/identity')
async def identity(request:Request,ctx=Depends(context)):
    # Supabase returns provider identity only after validating the access token.
    url,_=configured()
    async with httpx.AsyncClient(timeout=12) as c:
        r=await c.get(url+'/auth/v1/user',headers={'apikey':os.getenv('SUPABASE_ANON_KEY',''),'Authorization':request.headers.get('authorization','')})
    if r.status_code!=200:raise HTTPException(401,'Identity verification failed')
    identities=[x for x in r.json().get('identities',[]) if x.get('provider')=='github']
    if not identities:raise HTTPException(403,'Use GitHub sign-in to verify the account')
    info=identities[0].get('identity_data',{});owner=info.get('user_name') or info.get('preferred_username')
    if not owner or not re.fullmatch('[A-Za-z0-9-]{1,39}',owner):raise HTTPException(422,'GitHub identity has no valid username')
    await store.request('PATCH','codeverse_profiles',params={'id':f'eq.{ctx["user"]}'},payload={'github_username':owner,'display_name':str(info.get('full_name') or owner)[:120]},prefer='return=minimal')
    return {'github_username':owner}

def skills_from(p):
    history=p.get('journey',[]);skills=set(history[0].get('skills',[]) if history else [])
    if len(history)>1:
        skills.update(r['language'] for r in history[1].get('repositories',[]) if r.get('language'))
        skills.update(e['skill'] for scan in history[1].get('manifest_scans',[]) for e in scan.get('evidence',[]) if e.get('skill'))
    names={normalize_skill(t['name']):t['name'] for t in TAXONOMY['technologies']}
    return sorted({names.get(normalize_skill(s),s) for s in skills},key=str.casefold)
def learning_plan(skill,matched):
    key=normalize_skill(skill)
    plans={
      'python':['Build a CLI that validates and transforms a CSV dataset','Separate parsing and business rules; add pytest cases for invalid inputs','Package the tool with a reproducible environment and usage examples','Publish an original dataset analysis and document limitations'],
      'fastapi':['Create typed CRUD endpoints with Pydantic validation','Add JWT authorization, owner-scoped persistence and error handling','Write integration tests for access denial and invalid payloads','Containerize the API and publish an OpenAPI example'],
      'docker':['Build a multi-stage image with a non-root runtime user','Add a healthcheck, read-only filesystem and resource limits','Run an API and database with Compose and persistent volumes','Document deployment, rollback and secret configuration'],
      'postgresql':['Design a normalized schema with foreign keys and constraints','Implement parameterized queries and transactional updates','Use EXPLAIN to compare indexed and unindexed queries','Add migration and backup/restore instructions'],
      'sql':['Write joins and aggregates on a realistic relational dataset','Validate null handling and duplicate records with test queries','Design an index and inspect its query plan','Publish reproducible schema, queries and findings'],
      'typescript':['Enable strict mode and model domain objects with explicit types','Build a typed API client with loading and error states','Test user-visible behavior and remove unsafe type assertions','Publish a reusable module with examples'],
      'react':['Build a stateful interface from small accessible components','Integrate a real API with loading, empty and error states','Test keyboard interactions and asynchronous updates','Profile rerenders and publish a responsive demo'],
      'kubernetes':['Deploy a container with a Deployment and Service','Configure readiness/liveness probes and resource limits','Add ConfigMaps, Secrets references and a rolling update strategy','Practice rollback and document observed failure behavior'],
      'pytorch':['Create a train/validation/test split and a simple baseline','Train a small model and record reproducible random seeds','Report held-out metrics and inspect representative errors','Publish model limits, environment and an inference example'],
      '5g':['Map UE, RAN and core control/user-plane interfaces','Run an isolated software-only attach/session experiment','Collect logs and compare expected signaling with observations','Document topology, limitations and a reproducible experiment'],
    }
    steps=plans.get(key,[f'Build a minimal {skill} feature using a reference repository',f'Add tests for {skill} behavior and error conditions',f'Integrate {skill} into an original end-to-end project',f'Document setup, measured results and remaining {skill} limitations'])
    return {'skill':skill,'status':'build evidence' if matched else 'learn','steps':steps}

def dashboard_data(p,rows=None):
    skills=skills_from(p);history=p.get('journey',[]);profiles=recommend_roles(skills,limit=20)
    selected=next((r for r in profiles if len(history)>3 and r['id']==history[3].get('target')),profiles[0])
    from .glass_features import skill_details
    return {'skill_details':skill_details(p),'progress':p.get('learning_progress',{}),'student_profile':history[0].get('profile',{}) if history else {},'skills':skills,'profiles':profiles,'target':selected,'score':selected['match_percent'],
            'score_method':'Percentage of curated target technologies mentioned in CV, repository languages or scanned manifests. Not a proficiency or hiring score.',
            'recommendations':rank_catalog(skills+selected['missing_skills'],rows=rows),
            'plans':[learning_plan(s,s in selected['matched_skills']) for s in selected['matched_skills']+selected['missing_skills']]}
@router.get('/dashboard')
async def dashboard(ctx=Depends(context)):
    p=(await load(ctx['user']))['payload'];return dashboard_data(p,await catalog_rows())

class CreateProject(BaseModel):
    template:str=Field(max_length=180)
    name:str=Field(pattern='^[A-Za-z0-9_.-]{1,80}$')
    confirmed:bool=False
@router.post('/projects')
async def create_project(body:CreateProject,x_github_token:str=Header(default=''),ctx=Depends(context)):
    p=(await load(ctx['user']))['payload']
    if not p.get('submitted_at'):raise HTTPException(409,'Submit your profile first')
    template=next((r for r in CATALOG if r['id']==body.template),None)
    if not template or not body.confirmed:raise HTTPException(422,'Confirm a catalog reference and repository name')
    if not x_github_token:raise HTTPException(401,'Reconnect GitHub with public_repo authorization')
    async with httpx.AsyncClient(timeout=20,headers=_headers(x_github_token)) as c:
        who=await c.get('https://api.github.com/user')
        if who.status_code!=200 or who.json().get('login','').lower()!=ctx['profile'].get('github_username','').lower():raise HTTPException(403,'GitHub token belongs to another identity')
        readme=f'# {body.name}\n\nOriginal learning project inspired by [{template["id"]}]({template["url"]}).\n\nThis is a new scaffold, not copied upstream code. Review the upstream license before adapting code.\n\n## Plan\n'+ '\n'.join('- [ ] '+s for s in template['plan'])+'\n\n## Target skills\n'+template['search_text']
        # Atomic initial README via auto_init followed by content update. No false success on partial initialization.
        r=await c.post('https://api.github.com/user/repos',json={'name':body.name,'description':'CODEVERSE learning project inspired by '+template['id'],'private':False,'auto_init':False})
        if r.status_code!=201:raise HTTPException(422,'GitHub refused repository creation (check scope or duplicate name)')
        repo=r.json();write=await c.put('https://api.github.com/repos/'+repo['full_name']+'/contents/README.md',json={'message':'Initialize learning plan','content':base64.b64encode(readme.encode()).decode()})
    initialized=write.status_code==201;created_files=['README.md'] if initialized else [];file_errors=[]
    if initialized:
        from .glass_features import scaffold_files
        async with httpx.AsyncClient(timeout=20,headers=_headers(x_github_token)) as files_client:
            for path,content in scaffold_files(template,p,body.name).items():
                try:
                    result=await files_client.put('https://api.github.com/repos/'+repo['full_name']+'/contents/'+path,json={'message':'Add '+path,'content':base64.b64encode(content.encode()).decode()})
                    if result.status_code==201:created_files.append(path)
                    else:file_errors.append(path)
                except httpx.HTTPError:file_errors.append(path)
    latest=await load(ctx['user']);state=latest['payload'];state.setdefault('created_projects',[]).insert(0,{'full_name':repo['full_name'],'url':repo['html_url'],'reference':template['id'],'files':created_files,'missing_files':file_errors,'created_at':datetime.now(timezone.utc).isoformat()})
    await save(ctx['user'],state,latest['revision'])
    await store.audit(ctx['user'],ctx['role'],'learning_repository_created','allowed',{'repository':repo['full_name'],'initialized':write.status_code==201})
    return {'repository':repo,'initialized':write.status_code==201,'created_files':created_files,'commits':len(created_files),'missing_files':file_errors,'warning':('Some starter files failed: '+', '.join(file_errors)) if file_errors else (None if initialized else 'Repository created but README failed; add the plan manually.')}

# Career providers are fixed endpoints, never a server-side arbitrary URL fetcher.
@router.get('/jobs')
async def jobs(ctx=Depends(context)):
    p=(await load(ctx['user']))['payload']
    if not p.get('submitted_at'):raise HTTPException(409,'Submit your profile first')
    from .career_pipeline import fetch_jobs,ProviderUnavailable
    try:
        offers=await fetch_jobs(limit=80,pages=2)
        for offer in offers:offer['recruiter_email']=published_email(offer.get('description',''))
        return {'offers':offers,'provider':'Arbeitnow'}
    except ProviderUnavailable as e:raise HTTPException(503,'Job provider unavailable; try again later') from e

def published_email(text):
    # Extract only literal addresses in the published vacancy, never infer a person's address.
    match=re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',str(text))
    return match.group(0) if match else None

class CompanyFetch(BaseModel):
    provider:str=Field(pattern='^(greenhouse|lever)$')
    board:str=Field(pattern='^[A-Za-z0-9_-]{1,80}$')
@router.post('/companies/fetch')
async def company_fetch(body:CompanyFetch,ctx=Depends(context)):
    url=f'https://boards-api.greenhouse.io/v1/boards/{body.board}/jobs?content=true' if body.provider=='greenhouse' else f'https://api.lever.co/v0/postings/{body.board}?mode=json'
    async with httpx.AsyncClient(timeout=15,follow_redirects=False) as c:
        try:r=await c.get(url)
        except httpx.HTTPError as e:raise HTTPException(503,'Career provider unavailable') from e
    if r.status_code!=200:raise HTTPException(422,'Board not found or not publicly fetchable. Use the career page link.')
    items=r.json().get('jobs',[]) if body.provider=='greenhouse' else r.json()
    return {'offers':[{'id':str(j['id']),'title':j.get('title') or j.get('text'),'company':body.board,'location':j.get('location') or j.get('categories',{}).get('location',''),'url':j.get('absolute_url') or j.get('hostedUrl'),'recruiter_email':published_email(j.get('content') or j.get('descriptionPlain') or j.get('description') or ''),'source':body.provider,'description':re.sub(r'<[^>]+>',' ',str(j.get('content') or j.get('descriptionPlain') or j.get('description') or ''))[:15000]} for j in items[:200]]}

# All credentials are encrypted with an operator-managed key, never persisted in browser state.
def cipher():
    from cryptography.fernet import Fernet
    key=os.getenv('CODEVERSE_ENCRYPTION_KEY')
    if not key:raise HTTPException(503,'Integration encryption key is not configured')
    return Fernet(key.encode())
async def put_secret(user,provider,value):
    enc=cipher().encrypt(json.dumps(value).encode()).decode()
    await store.request('POST','codeverse_private_integrations',params={'on_conflict':'user_id,provider'},payload={'user_id':user,'provider':provider,'encrypted':enc},prefer='resolution=merge-duplicates,return=minimal')
async def get_secret(user,provider):
    rows=await store.request('GET','codeverse_private_integrations',params={'user_id':f'eq.{user}','provider':f'eq.{provider}','select':'encrypted'})
    if not rows:return None
    return json.loads(cipher().decrypt(rows[0]['encrypted'].encode()))
@router.post('/gmail/connect')
async def gmail_connect(ctx=Depends(context)):
    if not os.getenv('GOOGLE_CLIENT_ID') or not os.getenv('GOOGLE_CLIENT_SECRET'):raise HTTPException(503,'Google OAuth is not configured')
    nonce=secrets.token_urlsafe(32);state=ctx['user']+'.'+nonce
    await put_secret(ctx['user'],'gmail-state',{'hash':hashlib.sha256(state.encode()).hexdigest(),'expires':time.time()+600})
    url=os.environ['CODEVERSE_PUBLIC_URL'].rstrip('/')+'/api/v1/glass/gmail/callback'
    return {'url':'https://accounts.google.com/o/oauth2/v2/auth?'+urlencode({'client_id':os.environ['GOOGLE_CLIENT_ID'],'redirect_uri':url,'response_type':'code','scope':'https://www.googleapis.com/auth/gmail.send','state':state,'access_type':'offline','prompt':'consent'})}
@router.get('/gmail/callback')
async def gmail_callback(state:str='',code:str=''):
    if not re.fullmatch(r'[0-9a-f-]{36}\.[A-Za-z0-9_-]{30,100}',state):raise HTTPException(400,'Invalid OAuth state')
    user=state.split('.')[0];expected=await get_secret(user,'gmail-state')
    if not expected or expected.get('expires',0)<time.time() or not secrets.compare_digest(expected['hash'],hashlib.sha256(state.encode()).hexdigest()):raise HTTPException(400,'Expired OAuth state')
    await put_secret(user,'gmail-state',{'expires':0})
    async with httpx.AsyncClient(timeout=15) as c:
        r=await c.post('https://oauth2.googleapis.com/token',data={'client_id':os.environ['GOOGLE_CLIENT_ID'],'client_secret':os.environ['GOOGLE_CLIENT_SECRET'],'code':code,'grant_type':'authorization_code','redirect_uri':os.environ['CODEVERSE_PUBLIC_URL'].rstrip('/')+'/api/v1/glass/gmail/callback'})
    if r.status_code!=200 or not r.json().get('refresh_token'):raise HTTPException(400,'Google authorization failed; reconnect with consent')
    await put_secret(user,'gmail',{'refresh_token':r.json()['refresh_token']})
    return RedirectResponse('/?gmail=connected',status_code=303)
async def gmail_token(user):
    conf=await get_secret(user,'gmail')
    if not conf:raise HTTPException(409,'Connect Gmail first')
    async with httpx.AsyncClient(timeout=15) as c:
        r=await c.post('https://oauth2.googleapis.com/token',data={'client_id':os.getenv('GOOGLE_CLIENT_ID'),'client_secret':os.getenv('GOOGLE_CLIENT_SECRET'),'refresh_token':conf['refresh_token'],'grant_type':'refresh_token'})
    if r.status_code!=200:raise HTTPException(409,'Gmail authorization expired; reconnect')
    return r.json()['access_token']
@router.post('/gmail/test')
async def gmail_test(ctx=Depends(context)):
    await gmail_token(ctx['user'])
    conf=await get_secret(ctx['user'],'gmail');conf['tested_at']=datetime.now(timezone.utc).isoformat();await put_secret(ctx['user'],'gmail',conf)
    return {'ok':True,'tested':'OAuth token refresh; no email sent'}
class Mail(BaseModel):
    to:str=Field(pattern=r'^[^\s<>@\r\n]+@[^\s<>@\r\n]+\.[^\s<>@\r\n]+$',max_length=254)
    subject:str=Field(min_length=1,max_length=180)
    body:str=Field(min_length=1,max_length=15000)
    confirmed:bool=False
@router.post('/gmail/send')
async def gmail_send(body:Mail,ctx=Depends(context)):
    if not body.confirmed:raise HTTPException(422,'Confirm the recipient and message before sending')
    from email.message import EmailMessage
    token=await gmail_token(ctx['user']);msg=EmailMessage();msg['To']=body.to;msg['Subject']=body.subject;msg.set_content(body.body)
    async with httpx.AsyncClient(timeout=15) as c:
        r=await c.post('https://gmail.googleapis.com/gmail/v1/users/me/messages/send',headers={'Authorization':'Bearer '+token},json={'raw':base64.urlsafe_b64encode(msg.as_bytes()).decode()})
    if r.status_code!=200:raise HTTPException(502,'Gmail did not accept the email')
    await store.audit(ctx['user'],ctx['role'],'gmail_sent','allowed')
    return {'sent':True,'id':r.json()['id']}

# A typed DAG runner. Python executes only on a separately deployed isolated worker.
def graph_order(nodes):
    if not isinstance(nodes,list) or len(nodes)>40:raise ValueError('Maximum 40 boxes')
    for n in nodes:
        if not isinstance(n,dict) or not isinstance(n.get('id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',n['id']):raise ValueError('Invalid node identifier')
        if not isinstance(n.get('inputs',[]),list) or any(not isinstance(i,str) for i in n.get('inputs',[])):raise ValueError('Inputs must reference box IDs')
    ids={n.get('id') for n in nodes}
    if len(ids)!=len(nodes) or None in ids:raise ValueError('Unique node IDs are required')
    done=[];pending=list(nodes)
    while pending:
        ready=[n for n in pending if all(i in done for i in n.get('inputs',[]))]
        if not ready:raise ValueError('Graph has a cycle or a missing input')
        for n in ready:
            if n.get('kind') not in ('python','dataset','gmail','http'):raise ValueError('Unknown node kind')
            done.append(n['id']);pending.remove(n)
    return [next(n for n in nodes if n['id']==i) for i in done]
async def execute_python(code,data):
    url=os.getenv('CODEVERSE_RUNNER_URL');token=os.getenv('CODEVERSE_RUNNER_TOKEN')
    if not url or not token:raise HTTPException(503,'Isolated Python runner is not configured')
    async with httpx.AsyncClient(timeout=40) as c:
        try:r=await c.post(url.rstrip('/')+'/run',headers={'Authorization':'Bearer '+token},json={'code':code,'input':data})
        except httpx.HTTPError as e:raise HTTPException(503,'Python runner unavailable') from e
    if r.status_code!=200:raise HTTPException(422,'Python execution failed or exceeded limits')
    return r.json()
@router.post('/automation/run')
async def run_automation(ctx=Depends(context)):
    p=(await load(ctx['user']))['payload'];nodes=p.get('nodes',[])
    if not nodes:raise HTTPException(422,'Add at least one box')
    if len(nodes)>40:raise HTTPException(422,'Maximum 40 boxes')
    try:ordered=graph_order(nodes)
    except ValueError as e:raise HTTPException(422,str(e)) from e
    outputs={};log=[]
    for node in ordered:
        inputs=[outputs[i] for i in node.get('inputs',[])]
        if node['kind']=='dataset':
            dataset=next((d for d in p.get('datasets',[]) if d.get('id')==node.get('dataset')),None)
            if not dataset:raise HTTPException(422,'Dataset missing')
            outputs[node['id']]=dataset.get('content','')
        elif node['kind']=='python':
            code=str(node.get('code',''))[:20000]
            if node.get('tested_code')!=hashlib.sha256(code.encode()).hexdigest():raise HTTPException(409,'Test Python box '+str(node.get('name',''))+' before starting')
            outputs[node['id']]=await execute_python(code,inputs)
        elif node['kind']=='http':
            conf=await get_secret(ctx['user'],'http:'+str(node.get('connectorName','')))
            if not conf:raise HTTPException(409,'Configure and test this API connector first')
            outputs[node['id']]=await http_connector(conf)
        else:
            # Workflow start never silently sends mail; Gmail boxes produce reviewable drafts.
            await gmail_token(ctx['user']);outputs[node['id']]={'draft':inputs,'send_from':'Jobs → Gmail composer','sent':False}
        log.append({'node':node['id'],'status':'completed'})
    await store.audit(ctx['user'],ctx['role'],'automation_run','allowed',{'boxes':len(nodes)})
    return {'outputs':outputs,'log':log}

@router.get('/analyze')
async def analyze(request:Request,repository:str):
    limited(request)
    if not re.fullmatch(r'[A-Za-z0-9-]{1,39}/[A-Za-z0-9_.-]{1,100}',repository):raise HTTPException(422,'Invalid repository')
    try:return await collect_public_repository(*repository.split('/'))
    except (GithubCollectionError,httpx.HTTPError) as e:raise HTTPException(422,'GitHub request failed: '+str(e)) from e

class SkillTest(BaseModel):
    code:str=Field(min_length=1,max_length=20000)
    input:list=Field(default_factory=list,max_length=40)
@router.post('/automation/test')
async def test_skill(body:SkillTest,ctx=Depends(context)):
    output=await execute_python(body.code,body.input)
    return {'ok':True,'output':output,'tested_code':hashlib.sha256(body.code.encode()).hexdigest()}

class ConnectorConfig(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(pattern=r'^[A-Za-z0-9_-]{1,40}$')
    host:str=Field(pattern=r'^[A-Za-z0-9.-]{1,180}$')
    path:str=Field(default='/',min_length=1,max_length=500)
    token:str=Field(default='',max_length=2000)
def check_connector_destination(config):
    hosts={x.strip().lower() for x in os.getenv('CODEVERSE_CONNECTOR_HOSTS','api.github.com,huggingface.co').split(',') if x.strip()}
    host=config['host'].lower();path=config['path']
    if host not in hosts or not path.startswith('/') or path.startswith('//') or '#' in path or '\\' in path or any(ord(c)<32 for c in path):raise HTTPException(422,'Use an operator-allowed HTTPS host and a relative API path')
    return host,path
async def http_connector(config):
    host,path=check_connector_destination(config)
    headers={'User-Agent':'CODEVERSE-Connector','Accept':'application/json'}
    if config.get('token'):headers['Authorization']='Bearer '+config['token']
    async with httpx.AsyncClient(timeout=15,follow_redirects=False) as c:
        async with c.stream('GET','https://'+host+path,headers=headers) as r:
            if not 200<=r.status_code<300:raise HTTPException(422,'Connector returned HTTP '+str(r.status_code))
            raw=b''
            async for chunk in r.aiter_bytes():
                raw+=chunk
                if len(raw)>500_000:raise HTTPException(413,'Connector result exceeds 500 KB')
    try:return json.loads(raw)
    except ValueError:return raw.decode('utf-8',errors='replace')
@router.post('/connectors/test')
async def connector_test(body:ConnectorConfig,ctx=Depends(context)):
    config=body.model_dump()
    check_connector_destination(config)
    if not config['token']:
        old=await get_secret(ctx['user'],'http:'+body.name)
        if old and old.get('host','').lower()==config['host'].lower():config['token']=old.get('token','')
    result=await http_connector(config)
    config['tested_at']=datetime.now(timezone.utc).isoformat()
    await put_secret(ctx['user'],'http:'+body.name,config)
    return {'ok':True,'name':body.name,'sample':str(result)[:500],'credentials':'Encrypted server-side; not returned'}
