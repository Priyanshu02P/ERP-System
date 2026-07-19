import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.connection import Base
from app.db import models  # noqa: F401  (registers all models on Base.metadata)


@pytest.fixture()
def db_session():
    """
    Fresh in-memory SQLite database per test. Good enough for exercising the
    repository/service layers without needing a running Postgres instance.
    Note: SQLite doesn't enforce some things Postgres does (e.g. it's more
    lenient with certain constraint types), so integration tests against
    real Postgres are recommended before shipping to production.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
