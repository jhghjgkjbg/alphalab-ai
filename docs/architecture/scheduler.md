# In-Memory Scheduler

## Ответственность

Scheduler хранит периодические задачи, вычисляет next run, запускает async callbacks и собирает runtime-статистику. Он не знает, что callback запускает SourceManager или Collector.

```text
clock ──> due calculation ──> async callback
                                  |
                                  v
                           task statistics
```

## Семантика MVP

- task ID уникален;
- интервал задаётся в секундах;
- fixed-delay: следующий запуск планируется от времени завершения;
- disabled task имеет `next_run_at=None`;
- manual run использует тот же механизм статистики;
- ошибки сохраняются в `last_error` и не останавливают другие due-задачи;
- snapshots задач immutable.

Статистика: `last_started_at`, `last_finished_at`, `next_run_at`, `run_count`, `failure_count`, `last_error`.

## Service loop

`serve()` запускает due-задачи и ждёт ближайший next run через внедрённый async sleep. Busy loop и фоновые потоки отсутствуют. `CancelledError` не подавляется, поэтому composition root корректно завершает процесс.

## Границы

Scheduler не импортирует Collector, SourceManager, Event Bus или pipeline-модули. Clock и sleep внедряются для тестов. APScheduler, Celery, Redis, cron expressions, persistence, distributed locks и misfire policy не входят в MVP.

Для 24/7 сервера потребуются supervisor/container restart policy, health monitoring, persistent schedule state и distributed ownership задачи.
