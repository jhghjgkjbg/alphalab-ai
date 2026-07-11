# Knowledge Pipeline

Knowledge Pipeline принимает завершённые результаты Collector через события и сохраняет уникальные `SourceItem` за repository-портом.

## Компоненты

- `KnowledgeRepository` — Protocol хранения SourceItem;
- `InMemoryKnowledgeRepository` — локальная MVP-реализация;
- `KnowledgeHandler` — handler события `CollectionCompleted`.

## Дедупликация

Уникальный ключ записи — пара `(source, external_id)`. Одинаковые external ID разных источников считаются разными записями. При повторной доставке одного события repository не создаёт дубли.

## Границы

- Handler не получает данные напрямую от агента или Collector;
- Repository не знает о событиях и Event Bus;
- AIScout не вызывает Repository;
- in-memory реализация не является постоянным хранилищем;
- преобразование SourceItem в каноническое знание пока не выполняется.

Подключение PostgreSQL, миграций, транзакций и persistent event processing не входит в TASK-0007.
