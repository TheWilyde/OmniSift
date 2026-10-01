"""Authentication dependencies and utilities."""

from typing import Optional
from uuid import UUID, uuid4
from fastapi import Depends, Header, HTTPException, Request, status
from jose import jwt, JWTError

from app.core.config import settings
from app.schemas.auth import UserContext


# Development mode: allow role impersonation via header
IMPERSONATE_ROLE_HEADER = "X-Impersonate-Role"


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    impersonate_role: Optional[str] = Header(None, alias=IMPERSONATE_ROLE_HEADER),
) -> UserContext:
    """
    Get current user context from JWT token or development impersonation header.
    
    Production: Validates Bearer token, extracts user_id and roles.
    Development: If X-Impersonate-Role header is present, creates a user context
    with that role. Otherwise falls back to token or default 'general' role.
    """
    # Development mode: check for impersonation header first
    if settings.environment == "development" and impersonate_role:
        # Validate the role is one of the known roles
        valid_roles = ["general", "finance", "legal", "admin", "hr"]
        if impersonate_role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid impersonation role: {impersonate_role}. Valid roles: {valid_roles}",
            )
        
        # Create a deterministic UUID for the impersonated user
        impersonated_user_id = uuid4()  # In real app, might map to a test user
        
        return UserContext(
            user_id=impersonated_user_id,
            roles=[impersonate_role],
            is_impersonated=True,
            impersonated_role=impersonate_role,
        )
    
    # Production or no impersonation: parse Bearer token
    if not authorization:
        # No token provided - return default general user in dev, error in prod
        if settings.environment == "development":
            return UserContext(
                user_id=uuid4(),
                roles=["general"],
                is_impersonated=False,
                impersonated_role=None,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Parse Bearer token
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Decode and validate JWT
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        
        # Extract user_id from sub claim
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        try:
            user_id = UUID(user_id_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: malformed subject",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Extract roles
        roles = payload.get("roles", ["general"])
        if not isinstance(roles, list):
            roles = ["general"]
        
        return UserContext(
            user_id=user_id,
            roles=roles,
            is_impersonated=False,
            impersonated_role=None,
        )
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_required(
    user: UserContext = Depends(get_current_user),
) -> UserContext:
    """Dependency that requires authentication (no anonymous fallback)."""
    return user


def require_role(required_role: str):
    """Create a dependency that requires a specific role."""
    async def role_checker(user: UserContext = Depends(get_current_user_required)) -> UserContext:
        if not user.has_role(required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required",
            )
        return user
    return role_checker


def require_any_role(required_roles: list[str]):
    """Create a dependency that requires any of the specified roles."""
    async def role_checker(user: UserContext = Depends(get_current_user_required)) -> UserContext:
        if not user.has_any_role(required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of roles {required_roles} required",
            )
        return user
    return role_checker


# Common role dependencies
require_admin = require_role("admin")
require_finance = require_role("finance")
require_legal = require_role("legal")
require_general = require_role("general")