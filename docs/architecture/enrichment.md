# Enrichment Pipeline

## Зачем Enrichment отделён от Normalizer

Normalizer создаёт минимальную каноническую форму из транспортного SourceItem. Enrichment вычисляет производные поля и может развиваться независимо. Это не смешивает ingestion с классификацией и позволяет повторно обогащать уже сохранённые документы.

## Поток

```text
KnowledgeStored(document_id)
          |
          v
EnrichmentHandler
          |
          +--> Repository.get(document_id)
          |
          v
EnrichmentEngine
   summary → keywords → tags
          |
          v
KnowledgeDocument version N+1
          |
          +--> Repository.update(expected_version=N)
          |
          +--> conflict: stop
          |
          v
KnowledgeEnriched
```

## Провайдеры MVP

- `DeterministicSummaryProvider` объединяет title и content и обрезает текст на границе слова.
- `DeterministicKeywordProvider` сохраняет первые уникальные токены, исключая ru/en stop-words и слишком короткие слова.
- `DictionaryTagProvider` назначает ordered tags `ai`, `llm`, `coding`, `security`, `startup`, `crypto`, `data` по фиксированному словарю.

Provider работают только с read-only `EnrichmentSource`. Ошибка одного provider становится warning и не отменяет остальные результаты.

## Версионный цикл

Исходный документ версии 1 не мутируется. Handler создаёт copy-on-write объект версии 2: ID и created_at сохраняются, updated_at обновляется. Следующие enrichment могут создавать версии N+1.

Repository хранит текущую версию и использует optimistic locking. Update отклоняется, если текущая версия уже изменилась, ID/source key отличаются или новая версия не равна expected+1.

## KnowledgeEnriched

Immutable-событие содержит document ID, предыдущую и текущую версии, correlation ID и immutable warnings. Полный документ в событии не передаётся.

## Будущие LLM-провайдеры

LLM providers смогут реализовать те же provider Protocol во внешнем integration-слое. Alpha Core не должен импортировать OpenAI/Anthropic SDK. До подключения нужны ADR по стоимости, timeout, retry, privacy и deterministic fallback.

## Запрещённые зависимости

Чистые Engine и providers не зависят от Collector, Event Bus, Repository, Scoring, AI Scout, backend и внешних SDK. Handler знает только KnowledgeStored, Repository port и EventPublisher port; он не знает Scoring или console.

## Вне MVP

- LLM, embeddings и внешние API;
- PostgreSQL и постоянная история версий;
- concurrent retry при version conflict;
- provider priorities и dependency graph;
- quality confidence и provenance результата;
- Workflow Engine и ручная модерация.
