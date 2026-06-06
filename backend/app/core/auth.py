import os
import secrets
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

# Load API key from environment
API_KEY = os.getenv("CHRONOLENS_API_KEY")

if not API_KEY:
    # Auto-generate if not set (for dev only)
    API_KEY = secrets.token_urlsafe(32)
    print(f"\n⚠️  No CHRONOLENS_API_KEY in .env — using generated key for this session:")
    print(f"   {API_KEY}\n")
    print("Add this to your .env file for persistent auth:")
    print(f"   CHRONOLENS_API_KEY={API_KEY}\n")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Verify API key from request header."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide X-API-Key header."
        )
    
    # Constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(api_key, API_KEY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key."
        )
    
    return api_key