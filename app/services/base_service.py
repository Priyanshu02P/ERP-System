from typing import Generic, TypeVar, List, Optional

from app.db.repositories.base_repository import BaseRepository
from app.services.exceptions import NotFoundError

ModelType = TypeVar("ModelType")


class BaseService(Generic[ModelType]):
    """
    Thin wrapper around a repository providing generic CRUD with a
    consistent not-found error. Concrete services extend this with
    the actual business rules for their entity.
    """

    def __init__(self, repository: BaseRepository[ModelType], entity_name: str = "Entity"):
        self.repository = repository
        self.entity_name = entity_name

    def get(self, id: int) -> ModelType:
        obj = self.repository.get(id)
        if obj is None:
            raise NotFoundError(f"{self.entity_name} with id={id} not found")
        return obj

    def get_all(self) -> List[ModelType]:
        return self.repository.get_all()

    def get_page(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        return self.repository.paginate(skip=skip, limit=limit)

    def count(self) -> int:
        return self.repository.count()

    def create(self, obj: ModelType) -> ModelType:
        return self.repository.create(obj)

    def update(self, obj: ModelType) -> ModelType:
        return self.repository.update(obj)

    def delete(self, id: int) -> None:
        obj = self.get(id)
        self.repository.delete(obj)
