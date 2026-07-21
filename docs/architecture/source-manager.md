# Source Manager

## Назначение

SourceManager является единственной границей запуска Collectors. Он получает SourceRegistry, CollectorRegistry и EventPublisher, но ничего не знает о Scheduler или downstream pipeline.

```text
source_id
   |
   v
SourceRegistry ──> SourceDefinition
   |
   v
CollectorRegistry.create(collector_name)
   |
   v
BaseCollector.collect()
   |
   v
CollectionCompleted
```

## SourceDefinition

Immutable definition содержит source ID, имя Collector, enabled, интервал, priority, max items и read-only metadata. Enable/disable заменяет объект, не мутируя старую ссылку.

Priority допускает `critical`, `high`, `normal`, `low`, но сложная priority queue пока отсутствует. Enabled-источники запускаются в порядке регистрации.

## Ошибки

- неизвестный source → `not_found`;
- disabled source → `skipped`;
- исключение Collector → failed CollectionCompleted и failed SourceRunResult;
- ошибка одного источника не отменяет следующий.

Correlation ID создаётся на запуск или принимается вызывающей стороной и переносится в CollectionCompleted.

## Scheduler integration

Composition root регистрирует callback вида `SourceManager.run_source(source_id)`. Scheduler не знает Collector, а SourceManager не знает интервал запуска. Эта граница позволит позже загрузить SourceDefinition из YAML или БД без изменения SourceManager.

## Новые источники

GitHub, Product Hunt и другие источники добавляются как новые BaseCollector, явная регистрация класса/factory и SourceDefinition. Автоматическое сканирование импортов не используется.

## Вне MVP

- YAML/JSON/DB configuration;
- сложная priority queue и concurrency limits;
- per-source retry/rate limits;
- dynamic reload;
- PostgreSQL, Redis, Celery и Workflow Engine.
