"""Audited interface features. All writes use authenticated, owner-scoped workspace revisions."""
from __future__ import annotations
import csv, io, json, re, time, uuid, hashlib, base64, binascii
from datetime import datetime,timezone
from urllib.parse import urlparse
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,Field,ConfigDict
from . import glass_workspace as g
from .security_portal import context
from .core import normalize_skill,job_requirements
router=APIRouter(prefix='/api/v1/glass',tags=['Audited workspace features'])
def now():return datetime.now(timezone.utc).isoformat()
def submitted(p):
    if not p.get('submitted_at'):raise HTTPException(409,'Submit your seven-step profile first')

def skill_details(p):
    items={}
    def add(name,source,reference):
        key=normalize_skill(name)
        if not key:return
        row=items.setdefault(key,{'id':key,'name':name,'sources':[],'mastery':'Not assessed'})
        evidence={'kind':source,'reference':reference}
        if evidence not in row['sources']:row['sources'].append(evidence)
    history=p.get('journey',[])
    for name in history[0].get('skills',[]) if history else []:add(name,'CV claim','Uploaded or pasted CV')
    if len(history)>1:
        for repo in history[1].get('repositories',[]):
            if repo.get('language'):add(repo['language'],'Repository language',repo.get('full_name') or repo.get('name'))
        for scan in history[1].get('manifest_scans',[]):
            for e in scan.get('evidence',[]):
                if e.get('skill'):add(e['skill'],'Manifest evidence',scan['repository']+' @ '+scan.get('sha','')[:12])
    ratings={normalize_skill(k):v for k,v in (history[2].get('ratings',{}) if len(history)>2 else {}).items()}
    for row in items.values():
        row['self_rating']=ratings.get(row['id'])
        row['evidence_score']=min(3,len({s['kind'] for s in row['sources']}))
        row['status']='Repository evidence' if any(s['kind']!='CV claim' for s in row['sources']) else 'Self-reported'
        row['related_repositories']=[r['id'] for r in g.rank_catalog([row['id']]) if r['match_score']][:3]
    return sorted(items.values(),key=lambda r:r['name'].casefold())

def suggested_companies(target):
    if target in ('telecom','network'):items=[('Nokia','https://www.nokia.com/about-us/careers/'),('Ericsson','https://www.ericsson.com/en/careers'),('Orange','https://orange.jobs/')]
    elif target in ('ai-ml','llm','research'):items=[('Hugging Face','https://huggingface.co/join-us'),('Mistral AI','https://mistral.ai/careers/'),('Google','https://www.google.com/about/careers/applications/')]
    else:items=[('OVHcloud','https://careers.ovhcloud.com/'),('GitLab','https://about.gitlab.com/jobs/'),('Canonical','https://canonical.com/careers')]
    return [{'id':str(uuid.uuid5(uuid.NAMESPACE_URL,url)),'name':name,'url':url,'provider':'greenhouse' if name=='GitLab' else '','board':'gitlab' if name=='GitLab' else ''} for name,url in items]

class Revision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:int=Field(ge=0)
class Reopen(Revision):
    step:int=Field(ge=1,le=7)
    confirmed:bool=False
@router.post('/journey/reopen')
async def reopen(body:Reopen,ctx=Depends(context)):
    state=await g.load(ctx['user']);p=state['payload'];history=p.get('journey',[])
    if state['revision']!=body.revision:raise HTTPException(409,'Reload before editing')
    if not body.confirmed or body.step>len(history):raise HTTPException(422,'Confirm an existing step to edit')
    drafts=p.setdefault('drafts',{})
    for index,result in enumerate(history[body.step-1:],body.step):drafts[str(index)]=result
    p['journey']=history[:body.step-1];p.pop('submitted_at',None)
    revision=await g.save(ctx['user'],p,state['revision'])
    return {'revision':revision,'next_step':body.step,'downstream_review_required':True}
class Draft(Revision):
    step:int=Field(ge=1,le=7)
    values:dict=Field(default_factory=dict)
@router.put('/journey/draft')
async def draft(body:Draft,ctx=Depends(context)):
    state=await g.load(ctx['user']);p=state['payload']
    if state['revision']!=body.revision:raise HTTPException(409,'Reload before saving draft')
    if body.step!=len(p.get('journey',[]))+1:raise HTTPException(409,'Draft must belong to the current step')
    # Validate with the actual stage schema; retain extracted skills, never the full uploaded CV.
    try:values=g.Stage.model_validate(body.values).model_dump()
    except Exception as e:raise HTTPException(422,'Invalid profile draft fields') from e
    if body.step==1:
        values['skills']=[x['name'] for x in g.extract_skills(values.pop('text',''))]
    p.setdefault('drafts',{})[str(body.step)]=values
    return {'revision':await g.save(ctx['user'],p,state['revision']),'stored':'Structured fields and extracted skill claims; original CV text excluded'}
class Milestone(Revision):
    skill:str=Field(min_length=1,max_length=100)
    index:int=Field(ge=0,le=3)
    completed:bool
    proof_url:str=Field(default='',max_length=300)
@router.post('/learning/progress')
async def progress(body:Milestone,ctx=Depends(context)):
    state=await g.load(ctx['user']);p=state['payload'];submitted(p)
    if state['revision']!=body.revision:raise HTTPException(409,'Reload before updating progress')
    data=g.dashboard_data(p)
    if normalize_skill(body.skill) not in {normalize_skill(r['skill']) for r in data['plans']}:raise HTTPException(422,'Choose a skill from your roadmap')
    if body.proof_url and urlparse(body.proof_url).scheme!='https':raise HTTPException(422,'Evidence link must use HTTPS')
    key=normalize_skill(body.skill);entries=p.setdefault('learning_progress',{}).setdefault(key,{})
    entries[str(body.index)]={'completed':body.completed,'proof_url':body.proof_url,'updated_at':now(),'verification':'Self-reported completion; not independently verified'}
    return {'revision':await g.save(ctx['user'],p,state['revision']),'progress':entries}

@router.get('/integrations')
async def integrations(ctx=Depends(context)):
    gmail=await g.get_secret(ctx['user'],'gmail') if g.os.getenv('CODEVERSE_ENCRYPTION_KEY') else None
    return {'gmail':{'configured':bool(g.os.getenv('GOOGLE_CLIENT_ID') and g.os.getenv('GOOGLE_CLIENT_SECRET')),'connected':bool(gmail),'tested_at':gmail.get('tested_at') if gmail else None},'python':{'configured':bool(g.os.getenv('CODEVERSE_RUNNER_URL') and g.os.getenv('CODEVERSE_RUNNER_TOKEN'))},'allowed_api_hosts':[s.strip() for s in g.os.getenv('CODEVERSE_CONNECTOR_HOSTS','api.github.com,huggingface.co').split(',') if s.strip()]}
@router.post('/gmail/disconnect')
async def disconnect(ctx=Depends(context)):
    for provider in ['gmail','gmail-state']:
        await g.store.request('DELETE','codeverse_private_integrations',params={'user_id':f'eq.{ctx["user"]}','provider':f'eq.{provider}'},prefer='return=minimal')
    return {'disconnected':True,'note':'Local authorization removed. Revoke the application in Google Account permissions to invalidate the grant at Google.'}

class RankedOffers(BaseModel):
    offers:list[dict]=Field(max_length=200)
    location:str|None=Field(default=None,max_length=150)
@router.post('/jobs/rank')
async def rank_jobs(body:RankedOffers,ctx=Depends(context)):
    p=(await g.load(ctx['user']))['payload'];submitted(p)
    location=body.location if body.location is not None else (p.get('journey',[{},{},{},{}])[3].get('location','') if len(p.get('journey',[]))>3 else '')
    return {'offers':rank_offers(p,body.offers,location),'location_filter':location,'method':'Keyword technology overlap, not a hiring probability'}
def rank_offers(p,offers,location=''):
    owned={normalize_skill(s) for s in g.skills_from(p)};target=g.dashboard_data(p)['target'];wanted={r['skill'] for r in target['requirements']}
    # Comma-separated alternatives reflect the exact locations entered in the profile.
    terms=[x.strip().casefold() for x in re.split('[,;]',location) if x.strip()]
    rows=[]
    for o in offers:
        where=o.get('location','');where=where.get('name','') if isinstance(where,dict) else str(where)
        if terms and not any(term in where.casefold() or (term=='remote' and (o.get('remote') or 'remote' in where.casefold())) for term in terms):continue
        required={r['skill'] for r in job_requirements(str(o.get('title',''))+' '+str(o.get('description','')))}
        matched=owned&required
        rows.append({**o,'location':where,'match_percent':round(100*len(matched)/len(required)) if required else None,'matched_skills':sorted(matched),'missing_skills':sorted(required-owned),'target_overlap':len(required&wanted),'requirements_source':'Published title/description taxonomy matches' if required else 'No recognized requirements; score unavailable'})
    return sorted(rows,key=lambda x:(-(x['match_percent'] if x['match_percent'] is not None else -1),-x['target_overlap'],str(x.get('title',''))))

# A resumable owner-scoped run ledger and per-node outputs.
def dataset_value(dataset):
    content=dataset.get('content','');kind=dataset.get('type','txt').lower()
    if dataset.get('encoding')=='base64':
        try:raw=base64.b64decode(content,validate=True)
        except (ValueError,binascii.Error) as e:raise HTTPException(422,'Invalid binary dataset encoding') from e
        if len(raw)>500000:raise HTTPException(422,'Dataset exceeds 500 KB')
        return {'filename':dataset.get('name','dataset.bin'),'media_type':dataset.get('media_type','application/octet-stream'),'base64':content}
    if not isinstance(content,str) or len(content.encode())>500000:raise HTTPException(422,'Text dataset exceeds 500 KB')
    try:
        if kind=='json':return json.loads(content)
        if kind=='csv':return list(csv.DictReader(io.StringIO(content)))
        return content
    except (ValueError,csv.Error) as e:raise HTTPException(422,'Invalid dataset content') from e

def output_file(node,value):
    name=str(node.get('outputName') or 'output.json')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',name) or name in ('.','..'):raise HTTPException(422,'Use a simple output filename')
    if isinstance(value,dict) and set(value)>={'filename','base64'} and not name.lower().endswith(('.json','.txt','.csv')):
        return {'name':name,'type':value.get('media_type','application/octet-stream'),'content':value['base64'],'encoding':'base64'}
    if name.lower().endswith('.csv'):
        if not isinstance(value,list) or any(not isinstance(x,dict) for x in value):raise HTTPException(422,'CSV output requires a JSON array of objects')
        buf=io.StringIO();keys=list(dict.fromkeys(k for row in value for k in row));writer=csv.DictWriter(buf,fieldnames=keys);writer.writeheader()
        for row in value:
            safe={k:("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v) for k,v in row.items()};writer.writerow(safe)
        return {'name':name,'type':'text/csv','content':buf.getvalue()}
    if name.lower().endswith('.txt'):return {'name':name,'type':'text/plain','content':value if isinstance(value,str) else json.dumps(value,ensure_ascii=False)}
    return {'name':name,'type':'application/json','content':json.dumps(value,indent=2,ensure_ascii=False)}

async def validate_flow(p,target=None,user=None):
    try:ordered=g.graph_order(p.get('nodes',[]))
    except ValueError as e:raise HTTPException(422,str(e)) from e
    if not ordered:raise HTTPException(422,'Add at least one box')
    if target:
        by={n['id']:n for n in ordered}
        if target not in by:raise HTTPException(404,'Box not found')
        needed=set()
        def ancestors(key):
            if key in needed:return
            needed.add(key)
            for parent in by[key].get('inputs',[]):ancestors(parent)
        ancestors(target);ordered=[n for n in ordered if n['id'] in needed]
    for n in ordered:
        if n['kind']=='dataset':
            d=next((d for d in p.get('datasets',[]) if d.get('id')==n.get('dataset')),None)
            if d is None:raise HTTPException(422,'Dataset missing for '+n.get('name',n['id']))
            dataset_value(d)
        if n['kind']=='python' and n.get('tested_code')!=hashlib.sha256(str(n.get('code','')).encode()).hexdigest():raise HTTPException(409,'Test the current Python code before starting '+n.get('name',n['id']))
        if user and n['kind']=='http':
            conf=await g.get_secret(user,'http:'+str(n.get('connectorName','')))
            if not conf or not conf.get('tested_at'):raise HTTPException(409,'Configure and test the API box before starting')
        if user and n['kind']=='gmail':
            conf=await g.get_secret(user,'gmail')
            if not conf or not conf.get('tested_at'):raise HTTPException(409,'Connect and test Gmail before starting')
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',str(n.get('outputName') or 'output.json')):raise HTTPException(422,'Invalid output filename')
    return ordered
class RunControl(BaseModel):
    model_config=ConfigDict(extra='forbid')
    target:str|None=Field(default=None,max_length=80)
    confirm_email_send:bool=False
@router.post('/automation/validate')
async def validate(body:RunControl|None=None,ctx=Depends(context)):
    p=(await g.load(ctx['user']))['payload'];ordered=await validate_flow(p,body.target if body else None,ctx['user'])
    return {'valid':True,'order':[n['id'] for n in ordered],'boxes':len(ordered),'sends':[{'name':n.get('name'),'to':n.get('to'),'subject':n.get('subject'),'body':n.get('body')} for n in ordered if n['kind']=='gmail' and n.get('operation')=='send']}
@router.post('/automation/execute')
async def execute(body:RunControl,ctx=Depends(context)):
    state=await g.load(ctx['user']);p=state['payload'];submitted(p);ordered=await validate_flow(p,body.target,ctx['user'])
    if any(n['kind']=='gmail' and n.get('operation')=='send' for n in ordered) and not body.confirm_email_send:raise HTTPException(422,'Review and confirm each configured email before starting')
    run={'id':str(uuid.uuid4()),'started_at':now(),'status':'running','log':[],'outputs':{},'files':{}};started=time.monotonic()
    try:
        for n in ordered:
            values=[run['outputs'][key] for key in n.get('inputs',[])];stamp=time.monotonic()
            if n['kind']=='dataset':value=dataset_value(next(d for d in p.get('datasets',[]) if d['id']==n['dataset']))
            elif n['kind']=='python':value=await g.execute_python(n['code'],values)
            elif n['kind']=='http':
                conf=await g.get_secret(ctx['user'],'http:'+str(n.get('connectorName','')))
                if not conf:raise HTTPException(409,'Configure and test the API connector first')
                value=await g.http_connector(conf)
            else:
                await g.gmail_token(ctx['user'])
                mail={'to':n.get('to',''),'subject':n.get('subject',''),'body':str(n.get('body','')).replace('{{input}}',json.dumps(values,ensure_ascii=False)).replace('{{github}}',ctx['profile'].get('github_username',''))}
                if n.get('operation')=='send':value=await g.gmail_send(g.Mail(**mail,confirmed=True),ctx)
                else:value={'draft':mail,'sent':False}
            run['outputs'][n['id']]=value;run['files'][n['id']]=output_file(n,value)
            if len(json.dumps(run))>650000:raise HTTPException(413,'Run output exceeds the 650 KB retention limit')
            run['log'].append({'node':n['id'],'name':n.get('name'), 'status':'completed','elapsed_ms':round((time.monotonic()-stamp)*1000)})
        run['status']='completed'
    except Exception as exc:
        run['status']='failed';run['error']=str(exc.detail) if isinstance(exc,HTTPException) else 'Provider or execution error';run['log'].append({'node':n['id'],'status':'failed','detail':run['error']})
    run['finished_at']=now();run['elapsed_ms']=round((time.monotonic()-started)*1000)
    # Trim bulky output and retain up to ten runs within a bounded workspace budget.
    if len(json.dumps(run))>650000:
        run['outputs']={};run['files']={};run['error']='Output exceeded retention limit';run['status']='failed'
    # Merge onto fresh state so edits made during a run are not overwritten.
    current=await g.load(ctx['user']);fresh=current['payload'];runs=[run]+fresh.get('runs',[])[:9]
    while len(json.dumps(runs))>900000 and len(runs)>1:runs.pop()
    fresh['runs']=runs
    revision=await g.save(ctx['user'],fresh,current['revision'])
    await g.store.audit(ctx['user'],ctx['role'],'automation_run', 'allowed' if run['status']=='completed' else 'error',{'run_id':run['id'],'boxes':len(ordered)})
    return {**run,'revision':revision}

@router.get('/connectors/{name}')
async def connector_metadata(name:str,ctx=Depends(context)):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',name):raise HTTPException(422,'Invalid connector name')
    conf=await g.get_secret(ctx['user'],'http:'+name)
    if not conf:raise HTTPException(404,'Connector not configured')
    return {'name':name,'host':conf['host'],'path':conf['path'],'has_token':bool(conf.get('token'))}

# Source files are original scaffolds; upstream source is never copied without license review.
def scaffold_files(template,p,name):
    category=template['category'];target=g.dashboard_data(p)['target']
    tasks='\n'.join('- [ ] '+step for skill in target['missing_skills'][:3] for step in g.learning_plan(skill,False)['steps'][:2])
    plan=f'# Learning plan\n\nTarget: {target["title"]}\n\nReference: {template["url"]}\n\n{tasks}\n\nThese are original starter files. A starter does not demonstrate skill mastery. Review the reference project license before reusing upstream code.\n'
    if category=='Frontend':
        files={'package.json':json.dumps({'name':name.lower(),'version':'0.1.0','private':True,'type':'module','scripts':{'dev':'vite --host 0.0.0.0','build':'tsc --noEmit && vite build','test':'node --test'},'devDependencies':{'typescript':'^5.9.0','vite':'^7.1.0'}},indent=2),'index.html':'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Learning project</title><main id="app"></main><script type="module" src="/src/main.ts"></script></html>', 'src/main.ts':'const app = document.querySelector<HTMLDivElement>("#app");\nif(app) app.textContent = "Your original learning project starts here.";\n','tsconfig.json':json.dumps({'compilerOptions':{'target':'ES2022','module':'ESNext','strict':True,'lib':['ES2022','DOM'],'moduleResolution':'Bundler'},'include':['src']},indent=2)}
    elif 'fastapi' in template['search_text'].lower() or 'backend'==target['id']:
        files={'app.py':'from fastapi import FastAPI\napp = FastAPI(title="Learning API")\n@app.get("/health")\ndef health():\n    return {"status": "ok"}\n','requirements.txt':'fastapi>=0.115,<1\nuvicorn>=0.30,<1\nhttpx>=0.27,<1\npytest>=8,<10\n','test_app.py':'from fastapi.testclient import TestClient\nfrom app import app\ndef test_health():\n    assert TestClient(app).get("/health").json() == {"status": "ok"}\n','RUN.md':'python -m venv .venv\n.venv/bin/pip install -r requirements.txt\n.venv/bin/python -m pytest\n.venv/bin/uvicorn app:app --reload\n'}
    else:
        files={'main.py':'"""Original JSON transformation starter. Replace the transformation with your feature."""\nimport json, sys\ndef transform(value):\n    return {"input": value, "status": "ready"}\nif __name__ == "__main__":\n    print(json.dumps(transform(json.load(sys.stdin))))\n','test_main.py':'import unittest\nfrom main import transform\nclass TransformTests(unittest.TestCase):\n    def test_preserves_input(self):\n        self.assertEqual(transform({"example": 1})["input"], {"example": 1})\nif __name__ == "__main__": unittest.main()\n','RUN.md':'Run tests: python -m unittest\nRun: echo \'{"example": 1}\' | python main.py\nExtend this starter with the technologies and tasks in LEARNING_PLAN.md.\n'}
    files['LEARNING_PLAN.md']=plan;files['.gitignore']='.venv/\n__pycache__/\nnode_modules/\n.env\ndist/\n'
    return files

@router.get('/repository/metrics')
async def public_repository_metrics(request:Request,repository:str):
    g.limited(request)
    if not re.fullmatch(r'[A-Za-z0-9-]{1,39}/[A-Za-z0-9_.-]{1,100}',repository):raise HTTPException(422,'Invalid repository reference')
    async with g.httpx.AsyncClient(timeout=12,headers=g._headers()) as client:
        try:response=await client.get('https://api.github.com/repos/'+repository+'/commits',params={'per_page':1})
        except g.httpx.HTTPError as e:raise HTTPException(503,'GitHub is unreachable; try again later') from e
    if response.status_code==409:return {'commits':0,'scope':'default branch'}
    if response.status_code!=200:raise HTTPException(503,'GitHub commit count is unavailable or rate-limited')
    last=re.search(r'[?&]page=(\d+)>; rel="last"',response.headers.get('link',''))
    return {'commits':int(last.group(1)) if last else len(response.json()),'scope':'default branch','checked_at':now()}
