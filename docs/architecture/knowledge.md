# Knowledge Pipeline

## Статус

- Backlog-задачи: TASK-0007, TASK-0009, TASK-0010.
- Статус: canonical in-memory MVP.

## Поток

```text
CollectionCompleted
        |
        v
KnowledgeHandler
        |
        +--> KnowledgeNormalizer(SourceItem)
        |          |
        |          v
        |    KnowledgeDocument
        |          |
        +--> KnowledgeRepository.add(document)
                   |
                   +--> duplicate: stop
                   |
                   +--> new: KnowledgeStored(document_id)
```

KnowledgeHandler изолирует ошибку нормализации одного элемента, продолжает обработку и сохраняет статистику `received/stored/duplicates/failed` по исходному event ID.

## Repository

Repository хранит только KnowledgeDocument. MVP-порт предоставляет `add`, `get`, `get_by_source_key`, `all` и `count`. Два словарных индекса обеспечивают быстрый lookup по UUID и по `(source, source_external_id)`.

Порт также предоставляет `update(document, expected_version)`. Update успешен только если текущая версия совпадает с expected version, новая версия равна `expected+1`, а ID и source key не изменились. Конфликт не перезаписывает документ.

Возвращается исходный immutable KnowledgeDocument, поэтому вызывающая сторона не может изменить состояние Repository через полученный объект.

## KnowledgeStored

Событие версии 1 содержит только envelope, document ID, source identity и correlation ID. Документ не дублируется в событии. Потребитель обязан получить актуальный документ через read-only repository-порт.

## Ограничения

- нет транзакционной связи add/publish;
- нет PostgreSQL, outbox и durable delivery;
- хранится только последняя версия документа;
- нет удаления, поиска и версионирования содержимого;
- нет LLM enrichment и embeddings.
