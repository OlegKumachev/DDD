from __future__ import annotations


class DomainError(Exception):
    """Базовое доменное исключение: нарушено бизнес-правило."""


class NoSuitableTableError(DomainError):
    """Нет стола, подходящего по вместимости и статусу."""


class TableNotFoundError(DomainError):
    """Стол с указанным идентификатором не найден."""


class TableUnavailableError(DomainError):
    """Стол занят на пересекающийся слот или выведен из обслуживания."""


class ReservationNotFoundError(DomainError):
    """Бронь с указанным идентификатором не найдена."""


class InvalidReservationStateError(DomainError):
    """Недопустимый переход статуса брони."""


class TableNotAssignedError(DomainError):
    """Операция требует назначенного стола, но стол не назначен."""
