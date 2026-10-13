import pytest

from booking.domain.events import TableCreated, TableMarkedOutOfService, TableReactivated
from booking.domain.factory import TableFactory
from booking.domain.model import Capacity, TableStatus


def test_capacity_invariant():
    with pytest.raises(ValueError):
        Capacity(0)


def test_table_factory_starts_active_with_created_event():
    agg = TableFactory.create(capacity=4, table_id="T1")
    assert agg.root.status == TableStatus.ACTIVE
    assert agg.root.capacity.value == 4
    assert isinstance(agg.events[0], TableCreated)


def test_can_seat_respects_status_and_capacity():
    agg = TableFactory.create(capacity=4, table_id="T1")
    assert agg.can_seat(4)
    assert not agg.can_seat(5)
    agg.mark_out_of_service()
    assert not agg.can_seat(1)


def test_mark_out_of_service_is_idempotent():
    agg = TableFactory.create(capacity=4, table_id="T1")
    agg.mark_out_of_service()
    agg.mark_out_of_service()
    assert agg.root.status == TableStatus.OUT_OF_SERVICE
    events = [e for e in agg.events if isinstance(e, TableMarkedOutOfService)]
    assert len(events) == 1


def test_reactivate_returns_to_active():
    agg = TableFactory.create(capacity=4, table_id="T1")
    agg.mark_out_of_service()
    agg.reactivate()
    assert agg.root.status == TableStatus.ACTIVE
    assert isinstance(agg.events[-1], TableReactivated)


def test_table_factory_generates_unique_ids():
    first = TableFactory.create(capacity=2)
    second = TableFactory.create(capacity=2)
    assert first.root.id != second.root.id
    assert isinstance(first.events[0], TableCreated)
