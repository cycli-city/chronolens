import os
import jwt
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
FALLBACK_API_KEY = os.getenv("CHRONOLENS_API_KEY", "")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key or token."
        )

    # Try Supabase JWT
    if SUPABASE_JWT_SECRET:
        try:
            payload = jwt.decode(
                api_key,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False}
            )
            return payload.get("sub", "anonymous")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired.")
        except jwt.InvalidTokenError as e:
            print(f"JWT decode failed: {e}")
            print(f"Secret length: {len(SUPABASE_JWT_SECRET)}")
            print(f"Token prefix: {api_key[:20]}")
    else:
        print("WARNING: SUPABASE_JWT_SECRET is not set or empty")

    # Fallback to static API key
    import secrets
    if FALLBACK_API_KEY and secrets.compare_digest(api_key, FALLBACK_API_KEY):
        return "local_dev_user"

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid token or API key."
    )