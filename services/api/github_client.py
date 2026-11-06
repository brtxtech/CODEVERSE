"""GitHub public-data collector; static evidence, never claims authorship verification."""
from __future__ import annotations
import base64, re
import httpx
from .core import evidence_from_github
BASE='https://api.github.com'
ALLOWED_MANIFESTS=('package.json','angular.json','requirements.txt','pyproject.toml','Cargo.toml','Dockerfile','docker-compose.yml','compose.yaml','tsconfig.json','.github/workflows/ci.yml','.github/workflows/test.yml','go.mod','pom.xml')
class GithubCollectionError(Exception): pass

def _headers(token=None):
    h={'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'CODEVERSE-Career-Lab'}
    if token:h['Authorization']=f'Bearer {token}'
    return h

def _ensure(response):
    if response.status_code in (403,429):raise GithubCollectionError('GitHub rate limit or access restriction; retry later')
    if response.status_code>=500:raise GithubCollectionError('GitHub temporarily unavailable')

async def collect_public_repositories(owner:str, token:str|None=None, max_repos:int=100):
    if not re.fullmatch(r'[A-Za-z0-9-]{1,39}',owner):raise GithubCollectionError('Invalid GitHub account name')
    async with httpx.AsyncClient(base_url=BASE,headers=_headers(token),timeout=15,follow_redirects=False) as c:
        resp=await c.get(f'/users/{owner}')
        _ensure(resp)
        if resp.status_code!=200:raise GithubCollectionError(f'GitHub account unavailable (HTTP {resp.status_code})')
        typ=resp.json().get('type','User')
        endpoint=f'/orgs/{owner}/repos' if typ=='Organization' else f'/users/{owner}/repos'
        result=[]
        for page in range(1, min(5,(max_repos+99)//100+1)):
            r=await c.get(endpoint,params={'per_page':100,'page':page,'sort':'pushed','direction':'desc'})
            _ensure(r)
            if r.status_code!=200:raise GithubCollectionError(f'Repository listing failed (HTTP {r.status_code})')
            batch=r.json()
            if not isinstance(batch,list):raise GithubCollectionError('Unexpected GitHub response')
            for item in batch:
                if item.get('private') and not token:continue
                result.append({'full_name':item.get('full_name'),'name':item.get('name'),
                    'url':item.get('html_url'),'language':item.get('language'),
                    'stars':item.get('stargazers_count',0),'size':item.get('size',0),
                    'pushed_at':item.get('pushed_at'),'fork':bool(item.get('fork',False)),
                    'description':item.get('description'),'default_branch':item.get('default_branch'),
                    'private':bool(item.get('private',False))})
                if len(result)>=max_repos:break
            if len(result)>=max_repos or len(batch)<100:break
        return {'owner':owner,'account_type':typ,'repositories':result,'count':len(result),'scope':'public_only' if not token else 'authorized_token_scope'}

async def collect_public_repository(owner:str,repo:str,token:str|None=None)->dict:
    if not re.fullmatch(r'[A-Za-z0-9-]{1,39}',owner) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',repo):
        raise GithubCollectionError('Invalid repository identifier')
    async with httpx.AsyncClient(base_url=BASE,headers=_headers(token),timeout=15,follow_redirects=False) as c:
        info=await c.get(f'/repos/{owner}/{repo}')
        _ensure(info)
        if info.status_code==404:raise GithubCollectionError('Repository not found or not accessible')
        if info.status_code!=200:raise GithubCollectionError(f'GitHub unavailable (HTTP {info.status_code})')
        meta=info.json()
        if meta.get('private') and not token:raise GithubCollectionError('Private repository requires authorization')
        if meta.get('size',0)>100_000:raise GithubCollectionError('Repository exceeds configured scan limit')
        branch=meta.get('default_branch') or 'HEAD'
        branch_result=await c.get(f'/repos/{owner}/{repo}/branches/{branch}')
        _ensure(branch_result)
        if branch_result.status_code!=200:raise GithubCollectionError('Could not resolve default branch to commit')
        sha=branch_result.json().get('commit',{}).get('sha')
        if not sha or not re.fullmatch('[a-f0-9]{40}',sha):raise GithubCollectionError('Invalid commit SHA from GitHub')
        files={}
        for path in ALLOWED_MANIFESTS:
            response=await c.get(f'/repos/{owner}/{repo}/contents/{path}',params={'ref':sha})
            _ensure(response)
            if response.status_code!=200:continue
            obj=response.json()
            if not isinstance(obj,dict) or obj.get('encoding')!='base64' or obj.get('size',0)>100_000:continue
            try:files[path]=base64.b64decode(obj['content'],validate=False).decode('utf-8')[:100_000]
            except (ValueError,UnicodeError,KeyError):continue
        reference={'full_name':meta.get('full_name',f'{owner}/{repo}'),'sha':sha}
        evidence=evidence_from_github(reference,files)
        for ev in evidence:
            ev['evidence_type']='manifest_or_configuration'
            ev['repository_url']=meta.get('html_url')
            ev['authorship_status']='not_evaluated'
        return {'repository':reference['full_name'],'url':meta.get('html_url'),'sha':sha,
           'language':meta.get('language'),'stars':meta.get('stargazers_count',0),
           'size':meta.get('size',0),'fork':bool(meta.get('fork',False)),
           'pushed_at':meta.get('pushed_at'),'evidence':evidence,
           'files_checked':list(files),'authorship_verified':False,
           'note':'Static dependency/configuration evidence only. Does not prove developer authorship or proficiency.'}
