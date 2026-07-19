from typing import Generic, TypeVar, Type, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    """
    Generic repository providing plain database access.

    Repositories only talk to the database - no business rules here.
    That belongs in the service layer.
    """

    def __init__(self, model: Type[ModelType], db: Session):
        self.model = model
        self.db = db

    def get(self, id: int) -> Optional[ModelType]:
        return self.db.get(self.model, id)

    def get_all(self) -> List[ModelType]:
        return self.db.query(self.model).all()

    def create(self, obj: ModelType) -> ModelType:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, obj: ModelType) -> ModelType:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, obj: ModelType) -> None:
        self.db.delete(obj)
        self.db.commit()

    def exists(self, id: int) -> bool:
        return self.db.query(self.model.id).filter(self.model.id == id).first() is not None

    def count(self) -> int:
        return self.db.query(func.count(self.model.id)).scalar() or 0

    def paginate(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        return self.db.query(self.model).offset(skip).limit(limit).all()

    def filter(self, **kwargs) -> List[ModelType]:
        return self.db.query(self.model).filter_by(**kwargs).all()

    def bulk_create(self, objs: List[ModelType]) -> List[ModelType]:
        self.db.add_all(objs)
        self.db.commit()
        for obj in objs:
            self.db.refresh(obj)
        return objs
