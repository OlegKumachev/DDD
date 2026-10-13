from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CreateTable:
    capacity: int
    table_id: str | None = None


@dataclass(frozen=True)
class CreateReservation:
    slot_start: datetime
    duration_min: int
    party_size: int


@dataclass(frozen=True)
class ConfirmReservation:
    reservation_id: str
    table_id: str


@dataclass(frozen=True)
class CancelReservation:
    reservation_id: str
