"""GitHub webhook signature validation utility; not an exposed webhook endpoint."""
import hashlib,hmac

def verify_github_signature(body:bytes,signature:str|None,secret:str)->bool:
    if not secret or not signature or not signature.startswith('sha256='):
        return False
    candidate=signature[len('sha256='):]
    if len(candidate)!=64 or any(ch not in '0123456789abcdef' for ch in candidate):
        return False
    expected=hmac.new(secret.encode('utf-8'),body,hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected,candidate)
