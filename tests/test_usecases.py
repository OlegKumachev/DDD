from datetime import datetime, timedelta

import pytest

from booking.application.commands import (
    CancelReservation,
    ConfirmReservation,
    CreateReservation,
    CreateTable,
)
from booking.application.handlers import (
    CancelReservationHandler,
    ConfirmReservationHandler,
    CreateReservationHandler,
    CreateTableHandler,
)
from booking.domain.exceptions import (
    InvalidReservationStateError,
    NoSuitableTableError,
    ReservationNotFoundError,
    TableNotFoundError,
    TableUnavailableError,
)
from booking.domain.factory import ReservationFactory
from booking.domain.model import ReservationStatus, TableStatus, TimeSlot
from booking.domain.services import TableAllocationService

START = datetime(2030, 1, 1, 19, 0)
SLOT = TimeSlot(start=START, end=START + timedelta(minutes=90))


def make_reservation_cmd(**overrides) -> CreateReservation:
    params = {"slot_start": START, "duration_min": 90, "party_size": 2}
    params.update(overrides)
    return CreateReservation(**params)


def create_reservation(uow, **overrides) -> str:
    handler = CreateReservationHandler(uow, TableAllocationService())
    return handler(make_reservation_cmd(**overrides))


def seed_created_reservation(uow) -> str:
    agg = ReservationFactory.create(slot_start=START, duration_min=90, party_size=2)
    with uow:
        uow.reservations.add(agg)
        uow.commit()
    return agg.root.id


def test_create_table_happy_path(uow):
    table_id = CreateTableHandler(uow)(CreateTable(capacity=4, table_id="T1"))
    assert table_id == "T1"

    with uow:
        assert uow.tables.get("T1") is not None


def test_create_reservation_picks_smallest_suitable_table(uow):
    CreateTableHandler(uow)(CreateTable(capacity=2, table_id="TS"))
    CreateTableHandler(uow)(CreateTable(capacity=4, table_id="TB"))

    reservation_id = create_reservation(uow, party_size=3)

    with uow:
        saved = uow.reservations.get(reservation_id)
        assert saved is not None
        assert saved.root.status == ReservationStatus.CONFIRMED
        assert saved.root.table_id.value == "TB"


def test_create_reservation_without_suitable_table(uow):
    CreateTableHandler(uow)(CreateTable(capacity=2, table_id="TS"))
    handler = CreateReservationHandler(uow, TableAllocationService())

    with pytest.raises(NoSuitableTableError):
        handler(make_reservation_cmd(party_size=5))


def test_double_booking_same_table_leaves_no_free_table(uow):
    CreateTableHandler(uow)(CreateTable(capacity=4, table_id="T1"))
    handler = CreateReservationHandler(uow, TableAllocationService())

    handler(make_reservation_cmd())
    with pytest.raises(NoSuitableTableError):
        handler(make_reservation_cmd())


def test_overlapping_slot_on_other_table_is_allowed(uow):
    CreateTableHandler(uow)(CreateTable(capacity=4, table_id="T1"))
    CreateTableHandler(uow)(CreateTable(capacity=4, table_id="T2"))
    handler = CreateReservationHandler(uow, TableAllocationService())

    first_id = handler(make_reservation_cmd())
    second_id = handler(
        make_reservation_cmd(slot_start=START + timedelta(minutes=30), duration_min=60)
    )

    with uow:
        first = uow.reservations.get(first_id)
        second = uow.reservations.get(second_id)
        assert first.root.table_id.value == "T1"
        assert second.root.table_id.value == "T2"


def test_touching_slots_on_same_table_are_allowed(uow):
    CreateTableHandler(uow)(CreateTable(capacity=4, table_id="T1"))
    handler = CreateReservationHandler(uow, TableAllocationService())

    handler(make_reservation_cmd())
    second_id = handler(make_reservation_cmd(slot_start=START + timedelta(minutes=90)))

    with uow:
        assert uow.reservations.get(second_id) is not None


def test_cancel_reservation(uow):
    CreateTableHandler(uow)(CreateTable(capacity=4, table_id="T1"))
    reservation_id = create_reservation(uow)

    CancelReservationHandler(uow)(CancelReservation(reservation_id=reservation_id))

    with uow:
        saved = uow.reservations.get(reservation_id)
        assert saved.root.status == ReservationStatus.CANCELLED


def test_cancel_twice_is_idempotent(uow):
    CreateTableHandler(uow)(CreateTable(capacity=4, table_id="T1"))
    reservation_id = create_reservation(uow)
    cancel = CancelReservationHandler(uow)

    cancel(CancelReservation(reservation_id=reservation_id))
    cancel(CancelReservation(reservation_id=reservation_id))


def test_cancel_unknown_reservation(uow):
    with pytest.raises(ReservationNotFoundError):
        CancelReservationHandler(uow)(CancelReservation(reservation_id="nope"))


def test_cancel_completed_reservation_forbidden(uow):
    CreateTableHandler(uow)(CreateTable(capacity=4, table_id="T1"))
    reservation_id = create_reservation(uow)

    with uow:
        loaded = uow.reservations.get(reservation_id)
        assert loaded is not None
        loaded.mark_completed()
        uow.commit()

    with pytest.raises(InvalidReservationStateError):
        CancelReservationHandler(uow)(CancelReservation(reservation_id=reservation_id))


def test_confirm_reservation_assigns_table_and_confirms(uow):
    CreateTableHandler(uow)(CreateTable(capacity=4, table_id="T1"))
    reservation_id = seed_created_reservation(uow)

    ConfirmReservationHandler(uow)(
        ConfirmReservation(reservation_id=reservation_id, table_id="T1")
    )

    with uow:
        saved = uow.reservations.get(reservation_id)
        assert saved.root.status == ReservationStatus.CONFIRMED
        assert saved.root.table_id.value == "T1"


def test_confirm_unknown_table(uow):
    reservation_id = seed_created_reservation(uow)

    with pytest.raises(TableNotFoundError):
        ConfirmReservationHandler(uow)(
            ConfirmReservation(reservation_id=reservation_id, table_id="GHOST")
        )


def test_confirm_out_of_service_table(uow):
    CreateTableHandler(uow)(CreateTable(capacity=4, table_id="T1"))
    with uow:
        loaded = uow.tables.get("T1")
        assert loaded is not None
        loaded.mark_out_of_service()
        uow.commit()

    reservation_id = seed_created_reservation(uow)

    with pytest.raises(TableUnavailableError):
        ConfirmReservationHandler(uow)(
            ConfirmReservation(reservation_id=reservation_id, table_id="T1")
        )


def test_confirm_already_booked_table_rejected(uow):
    CreateTableHandler(uow)(CreateTable(capacity=4, table_id="T1"))
    CreateReservationHandler(uow, TableAllocationService())(make_reservation_cmd())

    second_id = seed_created_reservation(uow)

    with pytest.raises(TableUnavailableError):
        ConfirmReservationHandler(uow)(
            ConfirmReservation(reservation_id=second_id, table_id="T1")
        )


def test_failed_usecase_leaves_no_active_reservations(uow):
    CreateTableHandler(uow)(CreateTable(capacity=2, table_id="TS"))
    handler = CreateReservationHandler(uow, TableAllocationService())

    with pytest.raises(NoSuitableTableError):
        handler(make_reservation_cmd(party_size=5))

    with uow:
        assert uow.reservations.list_active_for_table("TS", SLOT) == []


def test_all_tables_active_after_seed(uow):
    CreateTableHandler(uow)(CreateTable(capacity=6, table_id="T6"))
    with uow:
        loaded = uow.tables.get("T6")
        assert loaded is not None
        assert loaded.root.status == TableStatus.ACTIVE
