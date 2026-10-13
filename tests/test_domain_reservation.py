from datetime import datetime, timedelta

import pytest

from booking.domain.events import ReservationCompleted, ReservationConfirmed, ReservationCreated
from booking.domain.exceptions import InvalidReservationStateError, TableNotAssignedError
from booking.domain.factory import ReservationFactory
from booking.domain.model import (
    PartySize,
    ReservationAggregate,
    ReservationStatus,
    TableId,
    TimeSlot,
)

START = datetime(2030, 1, 1, 19, 0)


def make_reservation() -> ReservationAggregate:
    return ReservationFactory.create(slot_start=START, duration_min=90, party_size=3)


def test_timeslot_invariant_start_before_end():
    with pytest.raises(ValueError):
        TimeSlot(start=START, end=START)


def test_timeslot_overlaps():
    slot = TimeSlot(start=START, end=START + timedelta(minutes=90))
    overlapping = TimeSlot(start=START + timedelta(minutes=30), end=START + timedelta(minutes=120))
    touching = TimeSlot(start=START + timedelta(minutes=90), end=START + timedelta(minutes=180))

    assert slot.overlaps(overlapping)
    assert slot.overlaps(slot)
    assert not slot.overlaps(touching)


def test_party_size_invariant():
    with pytest.raises(ValueError):
        PartySize(0)


def test_factory_creates_valid_aggregate_with_created_event():
    agg = make_reservation()
    assert agg.root.status == ReservationStatus.CREATED
    assert agg.root.table_id is None
    assert isinstance(agg.events[0], ReservationCreated)


def test_assign_table_only_while_created():
    agg = make_reservation()
    agg.assign_table(TableId("T1"))
    agg.assign_table(TableId("T2"))
    agg.confirm()
    with pytest.raises(InvalidReservationStateError):
        agg.assign_table(TableId("T3"))


def test_confirm_without_table_forbidden():
    agg = make_reservation()
    with pytest.raises(TableNotAssignedError):
        agg.confirm()


def test_confirm_happy_path():
    agg = make_reservation()
    agg.assign_table(TableId("T1"))
    agg.confirm()
    assert agg.root.status == ReservationStatus.CONFIRMED
    assert isinstance(agg.events[-1], ReservationConfirmed)


def test_cancel_is_idempotent():
    agg = make_reservation()
    agg.cancel()
    agg.cancel()
    assert agg.root.status == ReservationStatus.CANCELLED
    cancel_events = [e for e in agg.events if type(e).__name__ == "ReservationCancelled"]
    assert len(cancel_events) == 1


def test_cannot_cancel_completed():
    agg = make_reservation()
    agg.assign_table(TableId("T1"))
    agg.confirm()
    agg.mark_completed()
    with pytest.raises(InvalidReservationStateError):
        agg.cancel()


def test_mark_completed_from_confirmed_emits_event():
    agg = make_reservation()
    agg.assign_table(TableId("T1"))
    agg.confirm()
    agg.mark_completed()
    assert agg.root.status == ReservationStatus.COMPLETED
    assert isinstance(agg.events[-1], ReservationCompleted)


def test_mark_completed_requires_confirmed():
    agg = make_reservation()
    with pytest.raises(InvalidReservationStateError):
        agg.mark_completed()
