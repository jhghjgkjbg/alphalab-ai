# AI Scout Event-Driven Vertical Slice

## Статус

- Backlog-задачи: TASK-0006, TASK-0007.
- Статус: рабочий событийный MVP.
- Внешний источник: официальный Hacker News API v0.

## Назначение

AI Scout проверяет сквозной путь от внешнего источника до Knowledge Repository без прямой связи между агентом и хранилищем.

## Поток данных

```text
Hacker News API
       |
       v
HackerNewsCollector
       |
       v
 CollectorResult
       |
       | AIScout creates
       v
CollectionCompleted
       |
       | publish
       v
InMemoryEventBus
       |
       | subscribed handler
       v
 KnowledgeHandler
       |
       v
InMemoryKnowledgeRepository
```

## Ответственность AIScout

AIScout является composition root вертикального среза:

1. создаёт или получает Collector, Event Bus, Handler и Repository;
2. подписывает `KnowledgeHandler.handle` на `CollectionCompleted`;
3. запускает Collector;
4. преобразует `CollectorResult` в immutable versioned event;
5. публикует событие и ждёт завершения handlers;
6. выводит количество собранных и новых записей.

Метод `run()` не обращается к Knowledge Repository. Число новых элементов получается из результата обработки, сохранённого Handler по `event_id`.

## CollectionCompleted

Событие принадлежит Collector-домену и содержит:

- UUID события и correlation ID;
- номер версии контракта;
- UTC-время возникновения;
- имя и итоговый статус Collector;
- immutable tuple SourceItem;
- immutable tuple диагностических ошибок.

Текущая версия контракта — `1`.

## Совместимость

`agents.ai_scout.knowledge_store.KnowledgeStore` оставлен как alias `InMemoryKnowledgeRepository` для совместимости TASK-0006. Новый pipeline не использует его как прямую зависимость метода `run()`.

## Ошибки

- Ошибки отдельных материалов остаются частью `CollectorResult` и события.
- Ошибка одного event handler логируется Event Bus и не отменяет другие handlers.
- Неуспешный Collector всё равно публикует `CollectionCompleted`, позволяя подписчикам наблюдать завершение без данных.

## Границы MVP

- нет Redis, PostgreSQL и внешнего брокера;
- нет LLM, Telegram и Product Hunt;
- нет durable delivery и межпроцессной передачи;
- нет канонизации SourceItem в полноценную Knowledge Model;
- консольный вывод остаётся локальным интерфейсом наблюдения.
