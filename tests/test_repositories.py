from datetime import datetime, timedelta

from booking.domain.factory import ReservationFactory, TableFactory
from booking.domain.model import ReservationStatus, TableId, TimeSlot

START = datetime(2030, 1, 1, 19, 0)


def test_table_roundtrip_preserves_state(uow):
    with uow:
        uow.tables.add(TableFactory.create(capacity=4, table_id="T1"))
        uow.commit()

    with uow:
        loaded = uow.tables.get("T1")
        assert loaded is not None
        assert loaded.root.capacity.value == 4
        assert loaded.root.status.value == "ACTIVE"


def test_reservation_roundtrip_preserves_state(uow):
    agg = ReservationFactory.create(slot_start=START, duration_min=90, party_size=3)
    agg.assign_table(TableId("T1"))
    agg.confirm()

    with uow:
        uow.reservations.add(agg)
        uow.commit()

    with uow:
        loaded = uow.reservations.get(agg.root.id)
        assert loaded is not None
        assert loaded.root.status == ReservationStatus.CONFIRMED
        assert loaded.root.table_id.value == "T1"
        assert loaded.root.slot.overlaps(agg.root.slot)


def test_list_by_min_capacity_filters_capacity_and_status(uow):
    with uow:
        uow.tables.add(TableFactory.create(capacity=2, table_id="TS"))
        uow.tables.add(TableFactory.create(capacity=6, table_id="TB"))
        uow.commit()

    with uow:
        assert {t.root.id for t in uow.tables.list_by_min_capacity(4)} == {"TB"}

        loaded = uow.tables.get("TB")
        assert loaded is not None
        loaded.mark_out_of_service()
        uow.commit()

    with uow:
        assert uow.tables.list_by_min_capacity(4) == []


def test_list_active_for_table_excludes_cancelled_and_other_tables(uow):
    overlap = ReservationFactory.create(slot_start=START, duration_min=90, party_size=2)
    overlap.assign_table(TableId("T1"))
    overlap.confirm()

    cancelled = ReservationFactory.create(slot_start=START, duration_min=90, party_size=2)
    cancelled.assign_table(TableId("T1"))
    cancelled.cancel()

    other_table = ReservationFactory.create(slot_start=START, duration_min=90, party_size=2)
    other_table.assign_table(TableId("T9"))

    with uow:
        uow.reservations.add(overlap)
        uow.reservations.add(cancelled)
        uow.reservations.add(other_table)
        uow.commit()

    with uow:
        slot = TimeSlot(start=START, end=datetime(2030, 1, 1, 19, 30))
        active = uow.reservations.list_active_for_table("T1", slot)
        assert [a.root.id for a in active] == [overlap.root.id]


def test_list_active_for_table_ignores_touching_slot(uow):
    existing = ReservationFactory.create(slot_start=START, duration_min=90, party_size=2)
    existing.assign_table(TableId("T1"))
    existing.confirm()

    with uow:
        uow.reservations.add(existing)
        uow.commit()

    with uow:
        touching = TimeSlot(start=START + timedelta(minutes=90), end=START + timedelta(minutes=150))
        assert uow.reservations.list_active_for_table("T1", touching) == []
