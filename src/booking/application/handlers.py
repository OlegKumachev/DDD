from __future__ import annotations

from booking.application.commands import (
    CancelReservation,
    ConfirmReservation,
    CreateReservation,
    CreateTable,
)
from booking.application.unit_of_work import UnitOfWork
from booking.domain.exceptions import (
    ReservationNotFoundError,
    TableNotFoundError,
    TableUnavailableError,
)
from booking.domain.factory import ReservationFactory, TableFactory
from booking.domain.model import TableId, TableStatus
from booking.domain.services import TableAllocationService


class CreateTableHandler:

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def __call__(self, cmd: CreateTable) -> str:
        table = TableFactory.create(capacity=cmd.capacity, table_id=cmd.table_id)
        with self.uow:
            self.uow.tables.add(table)
            self.uow.commit()
        return table.root.id


class CreateReservationHandler:

    def __init__(self, uow: UnitOfWork, allocator: TableAllocationService) -> None:
        self.uow = uow
        self.allocator = allocator

    def __call__(self, cmd: CreateReservation) -> str:
        with self.uow:
            reservation = ReservationFactory.create(
                slot_start=cmd.slot_start,
                duration_min=cmd.duration_min,
                party_size=cmd.party_size,
            )

            candidates = self.uow.tables.list_by_min_capacity(cmd.party_size)
            free_tables = [
                table
                for table in candidates
                if not self.uow.reservations.list_active_for_table(
                    table.root.id, reservation.root.slot
                )
            ]
            table_id = self.allocator.allocate(reservation.root, free_tables)

            reservation.assign_table(table_id)
            reservation.confirm()

            self.uow.reservations.add(reservation)
            self.uow.commit()

        return reservation.root.id


class ConfirmReservationHandler:

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def __call__(self, cmd: ConfirmReservation) -> None:
        with self.uow:
            reservation = self.uow.reservations.get(cmd.reservation_id)
            if reservation is None:
                raise ReservationNotFoundError(cmd.reservation_id)

            table = self.uow.tables.get(cmd.table_id)
            if table is None:
                raise TableNotFoundError(cmd.table_id)
            if table.root.status != TableStatus.ACTIVE:
                raise TableUnavailableError(f"table {cmd.table_id} is out of service")

            if self.uow.reservations.list_active_for_table(cmd.table_id, reservation.root.slot):
                raise TableUnavailableError(
                    f"table {cmd.table_id} is already booked for an overlapping slot"
                )

            reservation.assign_table(TableId(cmd.table_id))
            reservation.confirm()
            self.uow.commit()


class CancelReservationHandler:

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def __call__(self, cmd: CancelReservation) -> None:
        with self.uow:
            reservation = self.uow.reservations.get(cmd.reservation_id)
            if reservation is None:
                raise ReservationNotFoundError(cmd.reservation_id)

            reservation.cancel()
            self.uow.commit()
