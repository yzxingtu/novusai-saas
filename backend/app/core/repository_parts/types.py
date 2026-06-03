"""Shared typing primitives for repository mixins."""

from typing import TypeVar

from app.core.base_model import BaseModel

ModelType = TypeVar("ModelType", bound=BaseModel)

__all__ = ["ModelType"]
