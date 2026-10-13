from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ReservationCreated:
    reservation_id: str
    occurred_at: datetime


@dataclass(frozen=True)
class ReservationConfirmed:
    reservation_id: str
    occurred_at: datetime


@dataclass(frozen=True)
class ReservationCancelled:
    reservation_id: str
    occurred_at: datetime


@dataclass(frozen=True)
class ReservationCompleted:
    reservation_id: str
    occurred_at: datetime


@dataclass(frozen=True)
class TableAssigned:
    reservation_id: str
    table_id: str
    occurred_at: datetime


@dataclass(frozen=True)
class TableCreated:
    table_id: str
    capacity: int
    occurred_at: datetime


@dataclass(frozen=True)
class TableMarkedOutOfService:
    table_id: str
    occurred_at: datetime


@dataclass(frozen=True)
class TableReactivated:
    table_id: str
    occurred_at: datetime
