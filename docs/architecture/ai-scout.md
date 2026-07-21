# AI Scout Canonical Pipeline

## Статус

- Backlog-задачи: TASK-0006 — TASK-0010.
- Статус: рабочий in-memory vertical slice.

## Полный поток

```text
InMemoryScheduler
       |
       v
SourceManager
       |
       v
Hacker News API
       |
       v
HackerNewsCollector
       |
       v
CollectionCompleted[SourceItem]
       |
       v
KnowledgeHandler
       |
       v
KnowledgeNormalizer
       |
       v
KnowledgeDocument
       |
       v
InMemoryKnowledgeRepository
       |
       v
KnowledgeStored(document_id)
       |
       v
EnrichmentHandler
       |
       v
EnrichmentEngine
       |
       v
KnowledgeDocument v2
       |
       v
KnowledgeEnriched(document_id)
       |
       v
ScoringHandler -- read by ID --> KnowledgeDocument
       |
       v
ScoringCompleted
       |
       v
PublicationHandler -- read by source key --> KnowledgeDocument
       |
       +--> PublicationRejected
       |
       v
PublicationCandidateCreated
       |
       v
ConsolePublisher
       |
       v
PublicationCompleted
       |
       v
Console
```

## Composition root

AIScout создаёт SourceRegistry, CollectorRegistry, SourceManager, Scheduler, Event Bus, Repository, Knowledge/Enrichment/Scoring/Publication handlers, Policy, Publisher Registry и Ledger. Collector вызывается только SourceManager. AIScout не вызывает `collect()`, PublicationEngine или Publisher напрямую.

`--once` вызывает `SourceManager.run_enabled()` и завершается после pipeline. `--serve` передаёт управление Scheduler до cancellation.

## Correlation

Один correlation ID проходит через CollectionCompleted, KnowledgeStored, KnowledgeEnriched и ScoringCompleted. Каждое событие имеет собственный event ID и версию.

## Console projection

ConsolePublisher получает готовый PublicationCandidate с title, URL, summary, keywords, tags, source, score и reasons. Прямой console handler на ScoringCompleted удалён.

## Границы

- нет Workflow Engine, PostgreSQL, Redis и внешнего брокера;
- нет LLM, embeddings, Telegram и FastAPI;
- KnowledgeStore alias оставлен только для совместимости импортов и не используется новым pipeline;
- score и документы не переживают завершение процесса.
