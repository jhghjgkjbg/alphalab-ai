# Scoring канонического знания

## Статус

- Backlog-задачи: TASK-0008 — TASK-0010.
- Статус: deterministic event-driven MVP.

## Входной контракт

Scoring Engine не импортирует KnowledgeDocument. Structural `ScorableItem` требует только `source`, `collected_at`, `title`, `summary` и `content`. KnowledgeDocument соответствует этому контракту без адаптера.

## Pipeline

```text
KnowledgeEnriched(document_id)
          |
          v
ScoringHandler
          |
          +--> KnowledgeReader.get(document_id)
          |             |
          |             v
          |      KnowledgeDocument
          |             |
          +--> ScoringEngine
                    |
                    v
ScoringCompleted
```

ScoringHandler знает публичное KnowledgeEnriched и read-only Protocol `KnowledgeReader`, но не SourceItem, Collector, конкретный Repository или AI Scout. KnowledgeStored намеренно не подписан на ScoringHandler: оценка выполняется только после enrichment.

ScoringCompleted является входом PublicationHandler. Scoring не решает, следует ли публиковать результат, и не знает о каналах доставки.

## MVP rules

- FreshnessRule использует `collected_at` и внедряемый clock;
- SourceTrustRule использует `source`;
- KeywordRule анализирует enriched `title + summary + content`;
- DuplicateRule не запускается, поскольку дубли остановлены до KnowledgeStored.

## Будущий LLMRule

LLMRule сможет анализировать те же канонические поля через внешний нейтральный порт. SDK провайдеров, timeout, budget и fallback не должны проникать в Alpha Core и требуют отдельного ADR.

## Ограничения

- score не сохраняется;
- нет LLM и динамических весов;
- ошибка rule завершает конкретную оценку;
- нет retry и dead-letter queue.
