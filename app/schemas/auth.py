"""Authentication and authorization schemas."""

from typing import List, Optional
from pydantic import BaseModel, Field
import uuid


class UserContext(BaseModel):
    """User context with roles for authorization."""
    user_id: uuid.UUID
    roles: List[str] = Field(default_factory=lambda: ["general"])
    is_impersonated: bool = False
    impersonated_role: Optional[str] = None
    
    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles
    
    def has_any_role(self, roles: List[str]) -> bool:
        """Check if user has any of the specified roles."""
        return any(role in self.roles for role in roles)


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str  # user_id
    roles: List[str] = Field(default_factory=lambda: ["general"])
    exp: int
    type: str  # "access" or "refresh"


class TokenResponse(BaseModel):
    """Token response schema."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginRequest(BaseModel):
    """Login request schema."""
    username: str
    password: str


class AuthMeResponse(BaseModel):
    """Response for /auth/me endpoint."""
    user_id: uuid.UUID
    roles: List[str]
    is_impersonated: bool = False
    impersonated_role: Optional[str] = None