# Knowledge Pipeline

## Статус

- Backlog-задача: TASK-0007.
- Статус: событийный MVP с in-memory repository.
- Каноническая Knowledge Model: ещё не определена.

## Роль

Knowledge Pipeline принимает `CollectionCompleted` через `KnowledgeHandler` и сохраняет содержащиеся `SourceItem` за портом `KnowledgeRepository`.

```text
CollectionCompleted
        |
        v
 KnowledgeHandler
        |
        | save(SourceItem)
        v
KnowledgeRepository <|-- InMemoryKnowledgeRepository
```

## Repository-порт

`KnowledgeRepository` — структурный Protocol с операциями:

- `save(item)` — сохранить уникальный SourceItem и вернуть факт вставки;
- `all()` — вернуть записи в порядке вставки;
- `count()` — вернуть количество уникальных записей.

Уникальный ключ — `(source, external_id)`. Он предотвращает дубли при повторной доставке и допускает одинаковые external ID у разных источников.

## Handler

`KnowledgeHandler` является единственным участником текущего pipeline, который вызывает Repository. Он обрабатывает все items события и сохраняет количество новых записей по `event_id`. Эта статистика позволяет composition root показать результат обработки, не обращаясь к Repository напрямую.

## Идемпотентность

Повторная обработка одного `CollectionCompleted` не создаёт новые записи для уже сохранённых `(source, external_id)`. В памяти сохраняется первая версия элемента; политика обновления пока отсутствует.

## Архитектурные границы

- AIScout публикует событие, но не вызывает Repository.
- Event Bus не импортирует Knowledge.
- Repository не знает о событиях, handlers и Collector.
- Handler зависит от repository Protocol, а не от конкретного хранилища.
- In-memory реализация не должна проникать в доменные контракты.

## Ограничения MVP

- данные теряются при завершении процесса;
- нет транзакций и конкурентной синхронизации;
- нет обновления существующей записи;
- нет канонизации, поиска, версионирования знания и provenance graph;
- нет durable inbox для защиты от повторной доставки после рестарта.

PostgreSQL-адаптер и полноценная Knowledge Model должны появиться отдельными задачами без изменения producer-контракта `CollectionCompleted`.
