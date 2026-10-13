from __future__ import annotations

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ReservationModel(Base):
    __tablename__ = "reservations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    slot_start: Mapped[datetime]
    slot_end: Mapped[datetime]
    party_size: Mapped[int]
    table_id: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(16))


class TableModel(Base):
    __tablename__ = "tables"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    capacity: Mapped[int]
    status: Mapped[str] = mapped_column(String(16))


def create_tables(engine) -> None:
    Base.metadata.create_all(engine)
