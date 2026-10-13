import pytest

from booking.domain.events import TableCreated
from booking.domain.factory import TableFactory


def test_commit_persists_changes(uow):
    with uow:
        uow.tables.add(TableFactory.create(capacity=4, table_id="T1"))
        uow.commit()

    with uow:
        assert uow.tables.get("T1") is not None


def test_rollback_discards_uncommitted_changes(uow):
    with uow:
        uow.tables.add(TableFactory.create(capacity=4, table_id="T1"))
        uow.rollback()

    with uow:
        assert uow.tables.get("T1") is None


def test_exception_in_context_triggers_rollback(uow):
    with pytest.raises(RuntimeError), uow:
        uow.tables.add(TableFactory.create(capacity=4, table_id="T1"))
        raise RuntimeError("boom")

    with uow:
        assert uow.tables.get("T1") is None


def test_collect_new_events_after_commit(uow):
    agg = TableFactory.create(capacity=4, table_id="T1")
    with uow:
        uow.tables.add(agg)
        uow.commit()
        events = list(uow.collect_new_events())

    assert any(isinstance(e, TableCreated) for e in events)


def test_collect_new_events_empty_after_rollback(uow):
    agg = TableFactory.create(capacity=4, table_id="T1")
    with uow:
        uow.tables.add(agg)
        uow.rollback()
        assert list(uow.collect_new_events()) == []
