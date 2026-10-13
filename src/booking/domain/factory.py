from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from .events import ReservationCreated
from .model import PartySize, Reservation, ReservationAggregate, TableAggregate, TimeSlot, utcnow


class ReservationFactory:
    @staticmethod
    def create(slot_start: datetime, duration_min: int, party_size: int) -> ReservationAggregate:
        if duration_min <= 0:
            raise ValueError("duration_min must be positive")

        reservation_id = str(uuid.uuid4())
        slot = TimeSlot(start=slot_start, end=slot_start + timedelta(minutes=duration_min))
        root = Reservation(reservation_id=reservation_id, slot=slot, party_size=PartySize(party_size))
        agg = ReservationAggregate(root)
        agg.events.append(ReservationCreated(root.id, utcnow()))
        return agg


class TableFactory:
    @staticmethod
    def create(capacity: int, table_id: str | None = None) -> TableAggregate:
        return TableAggregate.create(
            table_id=table_id or f"T-{uuid.uuid4().hex[:8]}",
            capacity=capacity,
        )
