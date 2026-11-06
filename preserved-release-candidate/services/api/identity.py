"""Validate Supabase access JWT against remote JWKS; no unsigned tokens, no fallback identity."""
import os
from functools import lru_cache
from fastapi import Header, HTTPException

def authenticated_user(authorization: str | None = Header(default=None)) -> str:
    issuer=os.environ.get('CODEVERSE_JWT_ISSUER','').rstrip('/')
    audience=os.environ.get('CODEVERSE_JWT_AUDIENCE','authenticated')
    if not issuer:
        raise HTTPException(503,'Protected API disabled until verified identity provider is configured')
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401,'Authentication required')
    try:
        import jwt
        # Never accept a client-supplied JWKS URL; derive from trusted env configuration.
        token=authorization[7:]
        key=jwks_client(issuer).get_signing_key_from_jwt(token)
        payload=jwt.decode(token,key.key,algorithms=['RS256','ES256'],audience=audience,issuer=issuer,
                           options={'require':['exp','iat','sub','iss','aud']},leeway=30)
        if payload.get('role')!='authenticated' or not payload.get('sub'):
            raise ValueError('Not an authenticated user')
        return payload['sub']
    except Exception as exc:
        raise HTTPException(401,'Invalid or expired access token') from exc

@lru_cache(maxsize=8)
def jwks_client(issuer:str):
    from jwt import PyJWKClient
    return PyJWKClient(issuer+'/.well-known/jwks.json',cache_jwk_set=True,lifespan=300,timeout=5)
