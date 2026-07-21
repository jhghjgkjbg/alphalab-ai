# Canonical Knowledge

Модуль Knowledge преобразует транспортные `SourceItem` в единый immutable `KnowledgeDocument`, сохраняет документы и публикует компактные события об успешной вставке.

## Компоненты

- `models.py` — независимая каноническая модель и стабильная UUIDv5-идентификация;
- `normalizer.py` — граница преобразования SourceItem в KnowledgeDocument;
- `repository.py` — Protocol и in-memory хранилище документов;
- `handler.py` — обработка CollectionCompleted, нормализация, дедупликация и статистика;
- `events.py` — notification-событие KnowledgeStored версии 1.

## Идентичность и дедупликация

`KnowledgeDocument.id` детерминированно вычисляется из `(source, source_external_id)`. Новая запись имеет `version=1`. Repository поддерживает индекс по document ID и индекс по source key. Повторная пара source key не добавляется и не создаёт KnowledgeStored.

## Immutable-модель

KnowledgeDocument — frozen dataclass со slots. `keywords` и `tags` представлены tuple. `metadata` копируется в read-only mapping, а вложенные коллекции рекурсивно замораживаются.

## Нормализация MVP

Normalizer переносит title, URL, content, published_at и безопасные metadata. Summary, keywords и tags пока пусты. Язык определяется без внешних библиотек: кириллица → `ru`, латиница → `en`, иначе → `unknown`.

## Статистика Handler

Для каждого CollectionCompleted сохраняются показатели `received`, `stored`, `duplicates` и `failed`. Ошибка одной нормализации логируется и не отменяет остальные элементы.

## Версионное обновление

`update(document, expected_version)` применяет новую immutable-версию только при совпадении текущей версии. ID и source key менять запрещено. Enrichment создаёт версию `N+1`, сохраняя `created_at` и обновляя `updated_at`.

## Границы

Модель не зависит от Collector, Event Bus, Repository, Scoring, backend или AI Scout. Только Normalizer знает о SourceItem. KnowledgeStored содержит document ID, но не дублирует документ.
