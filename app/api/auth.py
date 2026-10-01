"""Authentication API routes."""

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.schemas.auth import AuthMeResponse, TokenResponse, LoginRequest
from app.core.security import create_access_token, create_refresh_token, verify_password, get_password_hash

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(login_data: LoginRequest) -> TokenResponse:
    """
    Login endpoint - in production this would validate against a user database.
    For development, accepts any credentials and returns a token with 'general' role.
    """
    # In production: verify against user database
    # user = await user_service.get_by_username(login_data.username)
    # if not user or not verify_password(login_data.password, user.hashed_password):
    #     raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Development: create a test user
    import uuid
    user_id = uuid.uuid4()
    
    access_token = create_access_token(
        subject=str(user_id),
        additional_claims={"roles": ["general"]},
    )
    refresh_token = create_refresh_token(subject=str(user_id))
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=30 * 60,  # 30 minutes
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str) -> TokenResponse:
    """Refresh access token using refresh token."""
    from app.core.security import decode_token
    
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    
    user_id = payload.get("sub")
    roles = payload.get("roles", ["general"])
    
    new_access_token = create_access_token(
        subject=user_id,
        additional_claims={"roles": roles},
    )
    new_refresh_token = create_refresh_token(subject=user_id)
    
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=30 * 60,
    )


@router.get("/me", response_model=AuthMeResponse)
async def get_me(user = Depends(get_current_user)) -> AuthMeResponse:
    """
    Get current user context.
    
    In development mode, use X-Impersonate-Role header to test different roles:
    - X-Impersonate-Role: general
    - X-Impersonate-Role: finance
    - X-Impersonate-Role: legal
    - X-Impersonate-Role: admin
    - X-Impersonate-Role: hr
    """
    return AuthMeResponse(
        user_id=user.user_id,
        roles=user.roles,
        is_impersonated=user.is_impersonated,
        impersonated_role=user.impersonated_role,
    )


@router.get("/me/debug")
async def get_me_debug(
    user = Depends(get_current_user),
    request = None,  # Will be injected by FastAPI
) -> dict:
    """Debug endpoint showing full request headers for impersonation testing."""
    from fastapi import Request
    
    # Get impersonation header if present
    impersonate_role = request.headers.get("X-Impersonate-Role") if request else None
    
    return {
        "user_id": str(user.user_id),
        "roles": user.roles,
        "impersonate_header": impersonate_role,
        "environment": "development" if True else "production",  # settings.environment
        "headers": dict(request.headers) if request else {},
    }