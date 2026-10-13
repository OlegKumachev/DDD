import pytest

from booking.infrastructure.uow import InMemoryUnitOfWork


def _sqlalchemy_uow(tmp_path):
    pytest.importorskip("sqlalchemy", reason="SQLAlchemy is not installed")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from booking.infrastructure import orm
    from booking.infrastructure.uow import SqlAlchemyUnitOfWork

    engine = create_engine(f"sqlite:///{(tmp_path / 'booking.db').as_posix()}")
    orm.create_tables(engine)
    return SqlAlchemyUnitOfWork(sessionmaker(bind=engine, expire_on_commit=False))


@pytest.fixture(params=["in_memory", "sqlalchemy"])
def uow(request, tmp_path):

    if request.param == "in_memory":
        return InMemoryUnitOfWork()
    return _sqlalchemy_uow(tmp_path)
