from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from typing_extensions import Self

from booking.application.unit_of_work import UnitOfWork
from booking.infrastructure.repositories import (
    InMemoryReservationRepository,
    InMemoryTableRepository,
    SqlAlchemyReservationRepository,
    SqlAlchemyTableRepository,
)


class InMemoryUnitOfWork(UnitOfWork):
    """Транзакционный UoW без БД: для тестов и демо."""

    def __init__(self) -> None:
        self.reservations = InMemoryReservationRepository()
        self.tables = InMemoryTableRepository()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type:
            self.rollback()

    def commit(self) -> None:
        self.reservations.commit()
        self.tables.commit()

    def rollback(self) -> None:
        self.reservations.rollback()
        self.tables.rollback()

    def collect_new_events(self) -> Iterator[Any]:
        yield from self.reservations.collect_new_events()
        yield from self.tables.collect_new_events()


class SqlAlchemyUnitOfWork(UnitOfWork):
    """UoW на SQLAlchemy: одна session == одна транзакция."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory
        self.session = None
        self.reservations: SqlAlchemyReservationRepository | None = None
        self.tables: SqlAlchemyTableRepository | None = None

    def __enter__(self) -> Self:
        self.session = self._session_factory()
        self.reservations = SqlAlchemyReservationRepository(self.session)
        self.tables = SqlAlchemyTableRepository(self.session)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type:
            self.rollback()
        if self.session is not None:
            self.session.close()
            self.session = None

    def commit(self) -> None:
        if self.session is None:
            raise RuntimeError("UnitOfWork used outside of context manager")
        self.reservations.persist()
        self.tables.persist()
        self.session.commit()

    def rollback(self) -> None:
        if self.session is not None:
            self.session.rollback()
        if self.reservations is not None:
            self.reservations.rollback()
        if self.tables is not None:
            self.tables.rollback()

    def collect_new_events(self) -> Iterator[Any]:
        yield from self.reservations.collect_new_events()
        yield from self.tables.collect_new_events()
