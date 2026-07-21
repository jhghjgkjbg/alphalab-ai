# Scoring Engine

Scoring Engine детерминированно оценивает объекты Knowledge системой независимых правил. Он не использует LLM, внешние API или постоянное хранилище.

## Почему независимые правила

Каждое правило отвечает за один фактор оценки и возвращает объяснимый `RuleResult`. Такое разделение позволяет тестировать, версионировать, добавлять и удалять факторы без изменения Engine или других правил.

## Входной контракт

Engine принимает структурный `ScorableItem` Protocol с полями:

- `source`;
- `collected_at`;
- `title`;
- `summary`;
- `content`.

Новый scoring DTO не создаётся. Канонический `KnowledgeDocument` соответствует Protocol автоматически, но Scoring не импортирует его конкретный класс.

## Жизненный цикл оценки

1. Composition root создаёт локальный `ScoringEngine`.
2. Экземпляры правил регистрируются в явном порядке.
3. `score(item)` последовательно вызывает каждое правило.
4. `score_delta` суммируются в `total_score`.
5. Immutable `ScoreResult` сохраняет ordered details и reasons.

Глобальный singleton отсутствует. Два Engine могут иметь разные наборы правил.

## Событийная интеграция

`ScoringHandler` принимает `KnowledgeEnriched`, загружает уже обогащённый документ по `document_id` через read-only `KnowledgeReader`, запускает Engine и публикует immutable `ScoringCompleted` версии 1. `KnowledgeStored` больше не запускает scoring. Handler не знает о SourceItem, Collector или конкретном Repository.

## MVP-правила

- `FreshnessRule`: `+30` до 24 часов, `+20` до 72 часов, `+10` до 7 дней, затем `0`; clock внедряется.
- `SourceTrustRule`: Hacker News `+20`, GitHub и Product Hunt `+15`, другие источники `0`.
- `DuplicateRule`: дубликат `-100`, уникальный объект `0`; checker внедряется и может быть sync или async.
- `KeywordRule`: `+5` за уникальное совпавшее ключевое слово, максимум `+20`.

## Добавление правила

1. Унаследовать класс от `BaseRule`.
2. Определить стабильное уникальное `name()`.
3. Реализовать async `score(item)` без изменения item.
4. Возвращать `RuleResult` с понятной причиной.
5. Добавить изолированные тесты и тест композиции.
6. Зарегистрировать экземпляр в composition root.

## Будущий LLMRule

`LLMRule` сможет реализовать тот же `BaseRule`, но должен находиться во внешнем integration-слое. Alpha Core не должен импортировать SDK провайдера. В ядро может передаваться только абстрактный scoring-порт и нормализованный результат. Политика timeout, стоимости и fallback потребует отдельного ADR.

## Запрещённые зависимости

В модуле запрещены FastAPI, backend, Collector, Event Bus, Repository, SQLAlchemy, PostgreSQL, Redis, HTTP-клиенты, OpenAI, Anthropic и Telegram.

## Вне MVP

- хранение результатов;
- динамическая конфигурация весов;
- нормализация итогового score;
- обработка ошибок и timeout отдельных правил;
- параллельный запуск правил;
- rule dependencies и условные правила;
- LLM-оценка;
- хранение и доставка scoring events за пределами in-memory процесса.
