# Canonical Knowledge Model

## Зачем нужен KnowledgeDocument

Источники поставляют данные в разных форматах. `KnowledgeDocument` создаёт единую стабильную модель для Scoring, будущих LLM enrichment, Search, API, Telegram и новых Collectors. Downstream-компоненты больше не должны понимать payload конкретного источника.

## Жизненный цикл

```text
SourceItem
    |
    v
KnowledgeNormalizer
    |
    v
KnowledgeDocument
    |
    v
KnowledgeRepository
    |
    v
KnowledgeStored(document_id)
```

SourceItem остаётся транспортным объектом Collector Framework. Только Normalizer преобразует его в каноническую модель.

## Идентификация

Document ID — UUIDv5 от фиксированного namespace AlphaLab AI и строки `(source, source_external_id)`. Для одной source key результат стабилен между процессами и перезапусками. Разные источники с одинаковым external ID создают разные документы.

Repository дедуплицирует по source key и дополнительно индексирует document ID.

## Поля MVP

Сейчас Normalizer заполняет:

- title, URL и content из payload;
- source identity и collected_at из SourceItem;
- published_at из metadata или payload;
- безопасные metadata без ключей секретов;
- created_at и updated_at через clock;
- language по детерминированной ru/en/unknown policy.

Summary, keywords и tags создаются пустыми immutable tuple/строкой.

## Enrichment и версии

Normalizer создаёт документ версии 1. Детерминированный Enrichment заполняет summary, keywords и tags, создавая новый immutable объект версии 2. ID и `created_at` сохраняются, `updated_at` изменяется. Repository применяет объект через optimistic locking.

Будущие классификаторы или LLM смогут создавать следующие версии с расширенным language, entities и quality metadata. Они также не должны изменять объект на месте.

## Immutability

KnowledgeDocument — frozen dataclass со slots. Keywords и tags — tuple. Metadata — read-only mapping; вложенные mappings и коллекции рекурсивно заморожены. Repository возвращает immutable документы без изменяемых внутренних контейнеров.

## Запрещённые зависимости

Модель не импортирует Collector, Event Bus, Repository, Scoring, backend, AI Scout или внешние библиотеки. Normalizer — единственная разрешённая граница, знающая SourceItem.

## Вне MVP

- LLM, embeddings и semantic search;
- PostgreSQL и миграции;
- постоянная document version history (MVP хранит только актуальную версию);
- HTML parsing и content extraction;
- taxonomy, entities и classifiers;
- update/merge/conflict policy;
- API и Telegram presentation.
