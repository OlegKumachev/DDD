from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol

from typing_extensions import Self

from booking.domain.repository import ReservationRepository, TableRepository


class UnitOfWork(Protocol):
    reservations: ReservationRepository
    tables: TableRepository

    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type, exc, tb) -> None: ...

    def commit(self) -> None: ...
    def rollback(self) -> None: ...

    def collect_new_events(self) -> Iterator[Any]:
        ...
