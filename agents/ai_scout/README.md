# AI Scout

AI Scout — первый рабочий вертикальный срез AlphaLab AI. Он получает десять верхних материалов из официального Hacker News API, преобразует их в типы Collector Framework, сохраняет уникальные записи в памяти и выводит краткий результат в консоль.

## Поток

```text
Hacker News API
      ↓
HackerNewsCollector
      ↓
CollectionCompleted
      ↓
InMemoryEventBus
      ↓
KnowledgeHandler
      ↓
InMemoryKnowledgeRepository
```

AIScout не вызывает Repository напрямую. Он публикует immutable событие, а подписанный `KnowledgeHandler` сохраняет уникальные записи. После обработки AIScout выводит статистику и материалы в консоль.

## Запуск

Из корня репозитория:

```bash
python -m agents.ai_scout.agent
```

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
- HTML и содержимое внешних страниц не загружаются и не парсятся.

## Тестирование

```bash
python -m unittest discover -s tests -p "test_ai_scout.py" -v
```

Тесты используют внедрённую функцию загрузки и не обращаются к интернету.
