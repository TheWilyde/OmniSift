"""API dependencies - re-exports from core.auth for cleaner imports."""

from app.core.auth import (
    get_current_user,
    get_current_user_required,
    require_role,
    require_any_role,
    require_admin,
    require_finance,
    require_legal,
    require_general,
    optional_impersonation,
)

__all__ = [
    "get_current_user",
    "get_current_user_required",
    "require_role",
    "require_any_role",
    "require_admin",
    "require_finance",
    "require_legal",
    "require_general",
    "optional_impersonation",
]