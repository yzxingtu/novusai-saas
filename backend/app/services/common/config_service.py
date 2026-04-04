"""Compatibility shim for storage config service import paths."""

from app.configs.service import ConfigService  # noqa: F401

__all__ = ["ConfigService"]
