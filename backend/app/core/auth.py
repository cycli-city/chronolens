import os
import jwt
import httpx
from jwt.algorithms import ECAlgorithm
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
FALLBACK_API_KEY = os.getenv("CHRONOLENS_API_KEY", "")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

_jwks_cache = None


def _get_public_key():
    """Fetch Supabase's public JWKS and return the EC public key."""
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    try:
        url = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        jwks = resp.json()
        key_data = jwks["keys"][0]
        _jwks_cache = ECAlgorithm.from_jwk(key_data)
        return _jwks_cache
    except Exception as e:
        print(f"Failed to fetch JWKS: {e}")
        return None


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token."
        )

    # Try ES256 via Supabase JWKS
    if SUPABASE_URL:
        try:
            public_key = _get_public_key()
            if public_key:
                payload = jwt.decode(
                    api_key,
                    public_key,
                    algorithms=["ES256"],
                    options={"verify_aud": False}
                )
                return payload.get("sub", "anonymous")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired.")
        except jwt.InvalidTokenError as e:
            print(f"ES256 decode failed: {e}")

    # Fallback to static API key for local dev
    import secrets
    if FALLBACK_API_KEY and secrets.compare_digest(api_key, FALLBACK_API_KEY):
        return "local_dev_user"

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid token or API key."
    )