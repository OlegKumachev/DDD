from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from booking.domain.model import (
    Capacity,
    PartySize,
    Reservation,
    ReservationAggregate,
    ReservationStatus,
    Table,
    TableAggregate,
    TableId,
    TableStatus,
    TimeSlot,
)
from booking.domain.repository import ReservationRepository, TableRepository
from booking.infrastructure.orm import ReservationModel, TableModel

_ACTIVE_STATUSES = frozenset({ReservationStatus.CREATED, ReservationStatus.CONFIRMED})


class InMemoryReservationRepository(ReservationRepository):
    def __init__(self) -> None:
        self._saved: dict[str, ReservationAggregate] = {}
        self._pending: dict[str, ReservationAggregate] = {}
        self._seen: dict[str, ReservationAggregate] = {}

    def get(self, reservation_id: str) -> ReservationAggregate | None:
        agg = self._pending.get(reservation_id) or self._saved.get(reservation_id)
        if agg is not None:
            self._seen[reservation_id] = agg
        return agg

    def add(self, reservation: ReservationAggregate) -> None:
        self._pending[reservation.root.id] = reservation
        self._seen[reservation.root.id] = reservation

    def list_active_for_table(self, table_id: str, slot: TimeSlot) -> list[ReservationAggregate]:
        merged = {**self._saved, **self._pending}
        result = [
            agg
            for agg in merged.values()
            if agg.root.table_id is not None
            and agg.root.table_id.value == table_id
            and agg.root.status in _ACTIVE_STATUSES
            and agg.root.slot.overlaps(slot)
        ]
        for agg in result:
            self._seen[agg.root.id] = agg
        return result

    def collect_new_events(self) -> list[Any]:
        events = [event for agg in self._seen.values() for event in agg.events]
        self._seen.clear()
        return events

    def commit(self) -> None:
        self._saved.update(self._pending)
        self._pending.clear()

    def rollback(self) -> None:
        self._pending.clear()
        self._seen.clear()


class InMemoryTableRepository(TableRepository):
    def __init__(self) -> None:
        self._saved: dict[str, TableAggregate] = {}
        self._pending: dict[str, TableAggregate] = {}
        self._seen: dict[str, TableAggregate] = {}

    def get(self, table_id: str) -> TableAggregate | None:
        agg = self._pending.get(table_id) or self._saved.get(table_id)
        if agg is not None:
            self._seen[table_id] = agg
        return agg

    def add(self, table: TableAggregate) -> None:
        self._pending[table.root.id] = table
        self._seen[table.root.id] = table

    def list_by_min_capacity(self, capacity: int) -> list[TableAggregate]:
        merged = {**self._saved, **self._pending}
        result = [
            agg
            for agg in merged.values()
            if agg.root.status == TableStatus.ACTIVE and agg.root.capacity.value >= capacity
        ]
        for agg in result:
            self._seen[agg.root.id] = agg
        return result

    def collect_new_events(self) -> list[Any]:
        events = [event for agg in self._seen.values() for event in agg.events]
        self._seen.clear()
        return events

    def commit(self) -> None:
        self._saved.update(self._pending)
        self._pending.clear()

    def rollback(self) -> None:
        self._pending.clear()
        self._seen.clear()


def _reservation_to_row(agg: ReservationAggregate) -> ReservationModel:
    root = agg.root
    return ReservationModel(
        id=root.id,
        slot_start=root.slot.start,
        slot_end=root.slot.end,
        party_size=root.party_size.value,
        table_id=root.table_id.value if root.table_id else None,
        status=root.status.value,
    )


def _reservation_from_row(row: ReservationModel) -> ReservationAggregate:
    root = Reservation(
        reservation_id=row.id,
        slot=TimeSlot(start=row.slot_start, end=row.slot_end),
        party_size=PartySize(row.party_size),
        table_id=TableId(row.table_id) if row.table_id else None,
        status=ReservationStatus(row.status),
    )
    return ReservationAggregate(root)


def _table_to_row(agg: TableAggregate) -> TableModel:
    root = agg.root
    return TableModel(id=root.id, capacity=root.capacity.value, status=root.status.value)


def _table_from_row(row: TableModel) -> TableAggregate:
    root = Table(table_id=row.id, capacity=Capacity(row.capacity), status=TableStatus(row.status))
    return TableAggregate(root)


class SqlAlchemyReservationRepository(ReservationRepository):
    def __init__(self, session: Session) -> None:
        self._session = session
        self._added: dict[str, ReservationAggregate] = {}
        self._loaded: dict[str, ReservationAggregate] = {}

    def get(self, reservation_id: str) -> ReservationAggregate | None:
        row = self._session.get(ReservationModel, reservation_id)
        if row is None:
            return None
        agg = _reservation_from_row(row)
        self._loaded[agg.root.id] = agg
        return agg

    def add(self, reservation: ReservationAggregate) -> None:
        self._added[reservation.root.id] = reservation
        self._session.add(_reservation_to_row(reservation))

    def list_active_for_table(self, table_id: str, slot: TimeSlot) -> list[ReservationAggregate]:
        stmt = (
            select(ReservationModel)
            .where(ReservationModel.table_id == table_id)
            .where(ReservationModel.slot_start < slot.end)
            .where(ReservationModel.slot_end > slot.start)
            .where(ReservationModel.status.in_([s.value for s in _ACTIVE_STATUSES]))
        )
        result: list[ReservationAggregate] = []
        for row in self._session.scalars(stmt).all():
            agg = _reservation_from_row(row)
            self._loaded[agg.root.id] = agg
            result.append(agg)
        return result

    def persist(self) -> None:
        """Синхронизирует изменения загруженных агрегатов в сессию (INSERT/UPDATE)."""
        for agg in self._loaded.values():
            self._session.merge(_reservation_to_row(agg))

    def collect_new_events(self) -> list[Any]:
        seen = {**self._added, **self._loaded}
        events = [event for agg in seen.values() for event in agg.events]
        self._added.clear()
        self._loaded.clear()
        return events

    def rollback(self) -> None:
        self._added.clear()
        self._loaded.clear()


class SqlAlchemyTableRepository(TableRepository):
    def __init__(self, session: Session) -> None:
        self._session = session
        self._added: dict[str, TableAggregate] = {}
        self._loaded: dict[str, TableAggregate] = {}

    def get(self, table_id: str) -> TableAggregate | None:
        row = self._session.get(TableModel, table_id)
        if row is None:
            return None
        agg = _table_from_row(row)
        self._loaded[agg.root.id] = agg
        return agg

    def add(self, table: TableAggregate) -> None:
        self._added[table.root.id] = table
        self._session.add(_table_to_row(table))

    def list_by_min_capacity(self, capacity: int) -> list[TableAggregate]:
        stmt = (
            select(TableModel)
            .where(TableModel.capacity >= capacity)
            .where(TableModel.status == TableStatus.ACTIVE.value)
        )
        result: list[TableAggregate] = []
        for row in self._session.scalars(stmt).all():
            agg = _table_from_row(row)
            self._loaded[agg.root.id] = agg
            result.append(agg)
        return result

    def persist(self) -> None:
        for agg in self._loaded.values():
            self._session.merge(_table_to_row(agg))

    def collect_new_events(self) -> list[Any]:
        seen = {**self._added, **self._loaded}
        events = [event for agg in seen.values() for event in agg.events]
        self._added.clear()
        self._loaded.clear()
        return events

    def rollback(self) -> None:
        self._added.clear()
        self._loaded.clear()
