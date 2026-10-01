"""Core package initialization."""

from app.core.config import settings, get_settings
from app.core.database import (
    Base,
    engine,
    async_session_maker,
    get_async_session,
    get_async_session_context,
    init_db,
    close_db,
)
from app.core.security import (
    pwd_context,
    create_access_token,
    create_refresh_token,
    verify_password,
    get_password_hash,
    decode_token,
    get_token_expiration,
)
from app.core.auth import (
    get_current_user,
    get_current_user_required,
    require_role,
    require_any_role,
    require_admin,
    require_finance,
    require_legal,
    require_general,
)

__all__ = [
    # Config
    "settings",
    "get_settings",
    # Database
    "Base",
    "engine",
    "async_session_maker",
    "get_async_session",
    "get_async_session_context",
    "init_db",
    "close_db",
    # Security
    "pwd_context",
    "create_access_token",
    "create_refresh_token",
    "verify_password",
    "get_password_hash",
    "decode_token",
    "get_token_expiration",
    # Auth
    "get_current_user",
    "get_current_user_required",
    "require_role",
    "require_any_role",
    "require_admin",
    "require_finance",
    "require_legal",
    "require_general",
]