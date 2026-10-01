"""API package initialization."""

from app.api import health, documents, auth

__all__ = ["health", "documents", "auth"]