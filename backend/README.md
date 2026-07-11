# AlphaLab AI Backend

Foundation Backend AlphaLab AI на FastAPI. На текущем этапе доступны только корневой endpoint и проверка состояния. Настроены базовая конфигурация, логирование и жизненный цикл приложения. База данных, Redis, AI-интеграции, авторизация, агенты и прикладные роутеры не подключены.

## Требования

- Python 3.12;
- `uv`.

## Установка

Команды выполняются из каталога `backend`.

При необходимости установите управляемый `uv` интерпретатор Python 3.12:

```bash
uv python install 3.12
```

Создайте окружение и установите зависимости из `pyproject.toml`:

```bash
uv sync
```

`uv sync` устанавливает runtime- и development-зависимости, включая средства тестирования.

## Запуск

Запустите development-сервер:

```bash
uv run fastapi dev app/main.py
```

Приложение будет доступно по адресу `http://127.0.0.1:8000`.

## Endpoints

- `GET /` — имя и версия приложения;
- `GET /health` — состояние приложения;
- `/docs` — интерактивная документация OpenAPI, автоматически предоставляемая FastAPI.

Проверка через PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/
Invoke-RestMethod http://127.0.0.1:8000/health
```

Проверка через curl:

```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/health
```

## Остановка

Остановите development-сервер сочетанием `Ctrl+C`.

## Конфигурация

Настройки читаются из переменных окружения с префиксом `ALPHALAB_` и, при наличии, из файла `backend/.env`.

Доступные параметры:

- `ALPHALAB_APP_NAME` — имя приложения, по умолчанию `AlphaLab AI`;
- `ALPHALAB_APP_VERSION` — версия API, по умолчанию `0.1.0`;
- `ALPHALAB_ENVIRONMENT` — `development`, `test` или `production`;
- `ALPHALAB_LOG_LEVEL` — `DEBUG`, `INFO`, `WARNING`, `ERROR` или `CRITICAL`.

## Тестирование

```bash
uv run pytest
```

## Архитектурные границы

- `app/api/` — будущая композиция HTTP routers;
- `app/core/` — конфигурация, доступ к settings и lifespan;
- `app/logging/` — единая настройка логирования;
- `app/middleware/` — будущие middleware;
- `app/exceptions/` — будущая иерархия и обработчики исключений;
- `app/dependencies/` — будущие FastAPI dependencies;
- `app/services/health.py` — точка расширения Health Service;
- `app/repositories/` — будущий Repository Layer;
- `app/ai/` — будущий AI Layer;
- `app/integrations/` — адаптеры внешних систем;
- `app/workers/` — фоновые обработчики.

## Ограничения текущего этапа

Каталоги приложения подготовлены как архитектурные границы для следующих задач, но пока не содержат прикладных реализаций. Не создавайте подключения к инфраструктуре или бизнес-логику без отдельной Backlog-задачи.
