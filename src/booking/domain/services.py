from __future__ import annotations

from collections.abc import Iterable

from .exceptions import NoSuitableTableError
from .model import Reservation, TableAggregate, TableId


class TableAllocationService:

    def allocate(self, reservation: Reservation, tables: Iterable[TableAggregate]) -> TableId:
        suitable = [t for t in tables if t.can_seat(reservation.party_size.value)]
        if not suitable:
            raise NoSuitableTableError(
                f"no ACTIVE table for party size {reservation.party_size.value}"
            )
        chosen = min(suitable, key=lambda t: t.root.capacity.value)
        return TableId(chosen.root.id)
