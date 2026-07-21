# AI Scout

AI Scout — первый рабочий вертикальный срез AlphaLab AI. Он получает десять верхних материалов из официального Hacker News API, преобразует их в типы Collector Framework, сохраняет уникальные записи в памяти и выводит краткий результат в консоль.

## Поток

```text
Scheduler → SourceManager → HackerNewsCollector
      ↓
CollectionCompleted → KnowledgeHandler
      ↓
KnowledgeStored → EnrichmentHandler
      ↓
KnowledgeEnriched → ScoringHandler
      ↓
ScoringCompleted → PublicationHandler
      ↓
PublicationPolicy
      ├─ rejected → PublicationRejected
      ↓ accepted
PublicationCandidateCreated → ConsolePublisher
      ↓
PublicationCompleted
```

После `ScoringCompleted` PublicationHandler применяет threshold policy. Только accepted-кандидаты передаются `ConsolePublisher`. Publisher не принимает решение и не вызывается для rejected score.

AIScout не вызывает Repository, Scoring Engine, Publication Engine или Publisher напрямую.

Количество новых записей считается отдельным `PipelineStatsHandler`, подписанным на `KnowledgeStored`; внутренняя статистика KnowledgeHandler при этом сохраняется для диагностики.

## Однократный запуск

Из корня репозитория:

```bash
python -m agents.ai_scout.agent --once
```

Все enabled-источники запускаются по одному разу, pipeline полностью завершается, печатается статистика, после чего процесс останавливается.

Статистика включает collected, stored, enriched, scored, accepted, rejected, successful publications и publication failures.

## Режим сервиса

```bash
python -m agents.ai_scout.agent --serve
```

Scheduler ждёт ближайший `next_run_at` без busy loop и запускает SourceManager callback. Процесс работает до cancellation или `Ctrl+C`; запуск и остановка логируются.

Для запуска необходим Python 3.11 или новее и исходящий HTTPS-доступ к `hacker-news.firebaseio.com`. Сторонние Python-зависимости не требуются.

## Поведение

- запрашивается список top stories;
- загружаются первые 10 идентификаторов;
- каждый корректный материал преобразуется в `SourceItem`;
- при отсутствии внешнего URL используется страница обсуждения Hacker News;
- timeout, HTTP-ошибка или некорректная отдельная запись не отменяют остальные результаты;
- ошибка запроса списка top stories завершает запуск со статусом `failed`;
- повторная пара `(source, external_id)` не сохраняется второй раз;
- завершение Collector публикуется как `CollectionCompleted` версии 1.

## Ограничения

- события и данные существуют только в памяти процесса;
- нет PostgreSQL, Redis, LLM и отправки уведомлений;
- нет retry, параллельной загрузки, rate limiting и постоянного расписания;
- расписания и источники существуют только в памяти;
- HTML и содержимое внешних страниц не загружаются и не парсятся.

## Тестирование

```bash
python -m unittest discover -s tests -p "test_ai_scout.py" -v
```

Тесты используют внедрённую функцию загрузки и не обращаются к интернету.
