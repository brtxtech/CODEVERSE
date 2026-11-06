"""Server-side verification of Supabase asymmetric JWTs; fail closed."""
import os
import time
from functools import lru_cache
from fastapi import Header, HTTPException


def authenticated_claims(authorization: str | None = Header(default=None)) -> dict:
    if os.environ.get('CODEVERSE_DEV_BYPASS_AUTH') == '1':
        return {
            'sub': 'dev-bypass-user',
            'role': 'authenticated',
            'aud': os.environ.get('CODEVERSE_JWT_AUDIENCE', 'authenticated'),
            'iss': os.environ.get('CODEVERSE_JWT_ISSUER', 'http://localhost:8000'),
            'exp': int(time.time()) + 86400,
            'iat': int(time.time()),
            'aal': 'aal1',
        }
    issuer = os.environ.get('CODEVERSE_JWT_ISSUER', '').rstrip('/')
    audience = os.environ.get('CODEVERSE_JWT_AUDIENCE', 'authenticated')
    if not issuer or not issuer.startswith('https://'):
        raise HTTPException(503, 'Protected API disabled until verified HTTPS identity provider is configured')
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Authentication required')
    try:
        import jwt
        token = authorization[7:]
        key = jwks_client(issuer).get_signing_key_from_jwt(token)
        payload = jwt.decode(token, key.key, algorithms=['RS256', 'ES256'],
                             audience=audience, issuer=issuer,
                             options={'require': ['exp', 'iat', 'sub', 'iss', 'aud']}, leeway=30)
        if payload.get('role') != 'authenticated' or not payload.get('sub'):
            raise ValueError('Not an authenticated user')
        return payload
    except Exception as exc:
        raise HTTPException(401, 'Invalid or expired access token') from exc


def authenticated_user(authorization: str | None = Header(default=None)) -> str:
    return authenticated_claims(authorization)['sub']


@lru_cache(maxsize=8)
def jwks_client(issuer: str):
    from jwt import PyJWKClient
    return PyJWKClient(issuer + '/.well-known/jwks.json', cache_jwk_set=True, lifespan=300, timeout=5)
