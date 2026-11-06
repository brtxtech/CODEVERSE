"""GitHub App installation token exchange; backend only, never exposed to browsers."""
import os, time, re
from pathlib import Path
import httpx

class GitHubAppConfigurationError(RuntimeError): pass

def app_jwt(now=None):
    import jwt
    app_id=os.getenv('GITHUB_APP_ID','')
    key_path=os.getenv('GITHUB_PRIVATE_KEY_PATH','')
    if not app_id.isdigit() or not key_path:
        raise GitHubAppConfigurationError('GitHub App ID and private-key path required')
    path=Path(key_path).expanduser().resolve()
    if not path.is_file() or not path.is_relative_to(Path(os.getenv('CODEVERSE_SECRETS_ROOT',path.parent)).resolve()):
        raise GitHubAppConfigurationError('Private key must be an existing file in the designated secrets directory')
    t=int(now if now is not None else time.time())
    return jwt.encode({'iat':t-60,'exp':t+540,'iss':app_id},path.read_bytes(),algorithm='RS256')

async def installation_token(installation_id:int):
    if installation_id <= 0:raise ValueError('Invalid installation ID')
    token=app_jwt()
    async with httpx.AsyncClient(timeout=10,follow_redirects=False) as client:
        response=await client.post(f'https://api.github.com/app/installations/{installation_id}/access_tokens',
            headers={'Authorization':f'Bearer {token}','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
        response.raise_for_status()
        data=response.json()
        if not isinstance(data.get('token'),str):raise RuntimeError('Missing installation token')
        return data['token']

async def permitted_repo(installation_id:int,owner:str,repo:str):
    if not re.fullmatch(r'[\w.-]{1,100}',owner) or not re.fullmatch(r'[\w.-]{1,100}',repo):
        raise ValueError('Invalid repository identifier')
    token=await installation_token(installation_id)
    async with httpx.AsyncClient(timeout=10,follow_redirects=False) as client:
        r=await client.get(f'https://api.github.com/repos/{owner}/{repo}',headers={
          'Authorization':f'Bearer {token}','Accept':'application/vnd.github+json'})
        if r.status_code==404:return False
        r.raise_for_status()
        return r.json().get('full_name','').lower()==f'{owner}/{repo}'.lower()
