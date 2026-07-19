from typing import Generic, TypeVar, List

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORMBase(BaseModel):
    """Base schema for models read back out of the ORM."""

    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    """Generic pagination envelope returned by list endpoints."""

    items: List[T]
    total: int
    skip: int
    limit: int


class Message(BaseModel):
    detail: str
