"""Bearer token authentication middleware."""
import os
from fastapi import Request, status
from fastapi.responses import JSONResponse

API_TOKEN = os.getenv("API_TOKEN", "demo-token-123")

# Paths that don't require authentication
PUBLIC_PATHS = {"/api/health"}


async def auth_middleware(request: Request, call_next):
    """Check Bearer token for non-public endpoints."""
    path = request.url.path

    # Public paths don't need auth
    if path in PUBLIC_PATHS:
        return await call_next(request)

    # GET /api/stocks (search) is also public for MVP convenience
    if path == "/api/stocks" and request.method == "GET":
        return await call_next(request)

    # Check Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Missing or invalid Authorization header"},
        )

    token = auth_header[7:]  # Remove "Bearer " prefix
    if token != API_TOKEN:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Invalid API token"},
        )

    return await call_next(request)
