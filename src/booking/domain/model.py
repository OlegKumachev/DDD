from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .events import (
    ReservationCancelled,
    ReservationCompleted,
    ReservationConfirmed,
    ReservationCreated,
    TableAssigned,
    TableCreated,
    TableMarkedOutOfService,
    TableReactivated,
)
from .exceptions import InvalidReservationStateError, TableNotAssignedError


def utcnow() -> datetime:
    """Текущее время UTC (datetime.utcnow() устарел начиная с Python 3.12)."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class TimeSlot:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start >= self.end:
            raise ValueError("TimeSlot invariant: start must be < end")

    def overlaps(self, other: TimeSlot) -> bool:
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True)
class PartySize:
    value: int

    def __post_init__(self) -> None:
        if self.value < 1:
            raise ValueError("PartySize invariant: must be >= 1")


@dataclass(frozen=True)
class Capacity:
    value: int

    def __post_init__(self) -> None:
        if self.value < 1:
            raise ValueError("Capacity invariant: must be >= 1")


@dataclass(frozen=True)
class TableId:
    value: str


class ReservationStatus(str, Enum):
    CREATED = "CREATED"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class TableStatus(str, Enum):
    ACTIVE = "ACTIVE"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"


class Reservation:

    def __init__(
        self,
        reservation_id: str,
        slot: TimeSlot,
        party_size: PartySize,
        table_id: TableId | None = None,
        status: ReservationStatus = ReservationStatus.CREATED,
    ) -> None:
        self.id = reservation_id
        self.slot = slot
        self.party_size = party_size
        self.table_id = table_id
        self.status = status


class Table:

    def __init__(
        self,
        table_id: str,
        capacity: Capacity,
        status: TableStatus = TableStatus.ACTIVE,
    ) -> None:
        self.id = table_id
        self.capacity = capacity
        self.status = status


class ReservationAggregate:

    def __init__(self, root: Reservation) -> None:
        self._root = root
        self.events: list[Any] = []

    @property
    def root(self) -> Reservation:
        return self._root

    @classmethod
    def create(cls, reservation_id: str, slot: TimeSlot, party_size: PartySize) -> ReservationAggregate:
        root = Reservation(reservation_id=reservation_id, slot=slot, party_size=party_size)
        agg = cls(root)
        agg.events.append(ReservationCreated(root.id, utcnow()))
        return agg

    def assign_table(self, table_id: TableId) -> None:
        if self._root.status != ReservationStatus.CREATED:
            raise InvalidReservationStateError("can assign table only for CREATED reservation")

        self._root.table_id = table_id
        self.events.append(TableAssigned(self._root.id, table_id.value, utcnow()))

    def confirm(self) -> None:
        if self._root.status != ReservationStatus.CREATED:
            raise InvalidReservationStateError("only CREATED reservation can be confirmed")

        if self._root.table_id is None:
            raise TableNotAssignedError("cannot confirm without assigned table")

        self._root.status = ReservationStatus.CONFIRMED
        self.events.append(ReservationConfirmed(self._root.id, utcnow()))

    def cancel(self) -> None:
        if self._root.status == ReservationStatus.COMPLETED:
            raise InvalidReservationStateError("cannot cancel COMPLETED reservation")

        if self._root.status == ReservationStatus.CANCELLED:
            return

        self._root.status = ReservationStatus.CANCELLED
        self.events.append(ReservationCancelled(self._root.id, utcnow()))

    def mark_completed(self) -> None:
        if self._root.status != ReservationStatus.CONFIRMED:
            raise InvalidReservationStateError("can complete only CONFIRMED reservation")

        self._root.status = ReservationStatus.COMPLETED
        self.events.append(ReservationCompleted(self._root.id, utcnow()))


class TableAggregate:

    def __init__(self, root: Table) -> None:
        self._root = root
        self.events: list[Any] = []

    @property
    def root(self) -> Table:
        return self._root

    @classmethod
    def create(cls, table_id: str, capacity: int) -> TableAggregate:
        agg = cls(Table(table_id=table_id, capacity=Capacity(capacity)))
        agg.events.append(TableCreated(table_id, capacity, utcnow()))
        return agg

    def can_seat(self, party_size: int) -> bool:
        return self._root.status == TableStatus.ACTIVE and self._root.capacity.value >= party_size

    def mark_out_of_service(self) -> None:
        if self._root.status == TableStatus.OUT_OF_SERVICE:
            return

        self._root.status = TableStatus.OUT_OF_SERVICE
        self.events.append(TableMarkedOutOfService(self._root.id, utcnow()))

    def reactivate(self) -> None:
        if self._root.status == TableStatus.ACTIVE:
            return

        self._root.status = TableStatus.ACTIVE
        self.events.append(TableReactivated(self._root.id, utcnow()))
