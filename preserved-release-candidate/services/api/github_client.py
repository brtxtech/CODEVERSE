"""Bounded public GitHub collector: no cloning or arbitrary URLs."""
import base64
import httpx
from .core import evidence_from_github

ALLOWED_MANIFESTS=('package.json','requirements.txt','pyproject.toml','Cargo.toml','Dockerfile','docker-compose.yml','compose.yaml','tsconfig.json','.github/workflows/ci.yml')
BASE='https://api.github.com'

class GithubCollectionError(Exception): pass

async def collect_public_repository(owner:str, repo:str, token:str|None=None)->dict:
    """Fetch metadata and at most nine known small files; obey API rate limit signals."""
    headers={'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'codeverse-evidence-mvp'}
    if token: headers['Authorization']=f'Bearer {token}'
    async with httpx.AsyncClient(base_url=BASE,headers=headers,timeout=12,follow_redirects=False) as client:
        info=await client.get(f'/repos/{owner}/{repo}')
        if info.status_code==404:raise GithubCollectionError('Repository not found or not public')
        if info.status_code in (403,429):raise GithubCollectionError('GitHub API quota or access limit reached. Retry later.')
        if info.status_code!=200:raise GithubCollectionError(f'GitHub unavailable (HTTP {info.status_code})')
        meta=info.json()
        if meta.get('private'):raise GithubCollectionError('Private repositories are not supported by the public collector')
        if meta.get('size',0)>100_000:raise GithubCollectionError('Repository exceeds MVP size limit')
        sha=meta.get('default_branch','HEAD')
        files={}
        for path in ALLOWED_MANIFESTS:
            response=await client.get(f'/repos/{owner}/{repo}/contents/{path}',params={'ref':sha})
            if response.status_code in (403,429):break
            if response.status_code!=200:continue
            obj=response.json()
            if not isinstance(obj,dict) or obj.get('encoding')!='base64' or obj.get('size',0)>100_000:continue
            try:files[path]=base64.b64decode(obj['content'],validate=False).decode('utf-8')
            except (ValueError,UnicodeError,KeyError):continue
        repository={'full_name':meta.get('full_name',f'{owner}/{repo}'),'sha':sha}
        result=evidence_from_github(repository,files)
        return {'repository':repository['full_name'],'stars':meta.get('stargazers_count',0),'pushed_at':meta.get('pushed_at'),
            'evidence':result,'files_checked':list(files),'note':'Metadata and manifest signals only; developer authorship is not verified.'}
