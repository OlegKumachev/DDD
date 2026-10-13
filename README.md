# Restaurant Booking (DDD + Clean Architecture)

Учебный проект (bounded context **Booking**) — бронирование столиков ресторана.
Демонстрирует тактические паттерны DDD и принципы Чистой архитектуры на Python.

## Структура (Dependency Rule: зависимости направлены строго внутрь)

- `src/booking/domain` — доменное ядро, не зависит ни от кого:
  агрегаты `Reservation` и `Table` (Entity + Aggregate Root), Value Objects
  (`TimeSlot`, `PartySize`, `Capacity`, `TableId`), инварианты, доменные события,
  доменный сервис (`TableAllocationService`), фабрики, порты репозиториев,
  доменные исключения.
- `src/booking/application` — use-cases (хендлеры), команды (Input DTO),
  порт `UnitOfWork`.
- `src/booking/infrastructure` — адаптеры: транзакционные in-memory
  репозитории и UoW; SQLAlchemy-реализации (SQLite) с конвертацией ORM <-> агрегат.
- `src/booking/entrypoints` — пример HTTP entrypoint (FastAPI-скелет,
  Composition Root: здесь собираются зависимости).
- `tests/` — тесты домена, репозиториев, UoW и use-cases.

## Ключевые решения

- **Агрегат = граница согласованности.** Вся бизнес-логика (переходы статусов,
  инварианты) — в методах агрегатов; use-cases только оркестрируют.
- **Ссылки между агрегатами — по ID** (`Reservation` хранит `TableId`,
  а не объект `Table`).
- **Repository — порт внутри, адаптер снаружи.** Порты объявлены в домене
  как `Protocol`, реализации — в infrastructure.
- **Unit of Work — граница транзакции.** Репозитории внутри UoW делят одну
  транзакцию: in-memory реализация копит изменения в pending и применяет их
  только в `commit()`, `rollback()` отбрасывает; SQLAlchemy-версия — одна
  session на транзакцию.
- **Доменные события** накапливаются агрегатами и отдаются наружу через
  `uow.collect_new_events()` после commit (готовность к message bus).
- **Ошибки домена** — иерархия `DomainError` (`NoSuitableTableError`,
  `TableUnavailableError`, ...), а не голый `ValueError`.
- **Выбор стола**: use-case берёт кандидатов по вместимости из `TableRepository`,
  исключает занятые (пересечение слотов через `TimeSlot.overlaps`) и передаёт
  Domain Service только свободные.

## Быстрый старт (тесты)

```bash
python -m venv .venv
. .venv/Scripts/activate        # Windows; Linux/Mac: source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check .
```

Тесты репозиториев и UoW параметризованы и выполняются против **обеих**
реализаций (in-memory и SQLAlchemy + SQLite). Если SQLAlchemy не установлен,
эти варианты пропускаются.

## Доменные термины (Ubiquitous Language)

- Reservation — бронь
- TimeSlot — временной слот (start/end), умеет проверять пересечения
- PartySize — количество гостей
- Table / Capacity — стол и вместимость
- TableStatus — ACTIVE / OUT_OF_SERVICE
- ReservationStatus — CREATED -> CONFIRMED -> COMPLETED, отмена (CANCELLED)
  идемпотентна и запрещена для COMPLETED

## Use-cases

| Хендлер | Команда | Результат |
|---|---|---|
| `CreateTableHandler` | `CreateTable` | id стола |
| `CreateReservationHandler` | `CreateReservation` | id брони (сразу CONFIRMED) |
| `ConfirmReservationHandler` | `ConfirmReservation` | назначает стол и подтверждает |
| `CancelReservationHandler` | `CancelReservation` | отмена (идемпотентна) |
