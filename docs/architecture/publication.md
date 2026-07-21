# Publication Pipeline

## Ответственности

```text
ScoringCompleted
       |
       v
PublicationHandler -- lookup --> KnowledgeDocument
       |
       v
PublicationPolicy
       |
       +--> rejected --> PublicationRejected
       |
       v
PublicationCandidate
       |
       v
Publisher(s)
       |
       v
PublicationCompleted
```

Policy принимает бизнес-решение. Engine создаёт candidate и координирует выбранные каналы. Publisher только доставляет уже одобренный candidate и не имеет права изменять threshold или выбирать канал.

## Policy MVP

`ScoreThresholdPolicy` принимает minimum score и ordered channels из composition root. В AI Scout настроены threshold `50`, version `1` и канал `console`. Score ниже 50 создаёт PublicationRejected; score 50 и выше принимается.

## Candidate

PublicationCandidate — immutable snapshot данных для доставки. Candidate ID — UUIDv5 от document ID и policy version, поэтому повторная оценка той же policy создаёт тот же identity. Коллекции keywords, tags, reasons и channels представлены tuple.

## Жизненный цикл accepted candidate

1. Handler загружает KnowledgeDocument через read-only Protocol.
2. Engine получает решение Policy и создаёт candidate.
3. Ledger проверяет candidate ID.
4. Handler публикует PublicationCandidateCreated.
5. Engine последовательно вызывает выбранные Publishers.
6. Исключение канала превращается в failed PublishResult.
7. Candidate отмечается обработанным.
8. Handler публикует PublicationCompleted с ordered results.

## Идемпотентность

InMemoryPublicationLedger хранит обработанные candidate ID. Повторный accepted event возвращает явный idempotent handling result, не вызывает Publisher и не создаёт повторный PublicationCompleted.

Ledger существует только в памяти. После рестарта гарантия теряется; production-версия потребует persistent unique constraint и атомарную claim-операцию.

## Несколько каналов

Policy возвращает ordered tuple каналов. Registry разрешает ровно один Publisher на channel name. Engine продолжает другие каналы после ошибки и агрегирует PublishResult.

Будущие Telegram, X, LinkedIn и website adapters реализуют Publisher Protocol вне decision logic. Их SDK не должны попадать в Policy или Engine.

## Границы MVP

- только ConsolePublisher;
- нет PostgreSQL/Redis ledger;
- нет retry, backoff и delivery receipts;
- нет Telegram, X, LinkedIn, email и webhook;
- нет ручной модерации и Workflow Engine;
- нет transactional outbox;
- конкурентная атомарная claim candidate пока отсутствует.
