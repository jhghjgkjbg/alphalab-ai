# Локальная инфраструктура в Docker

Docker Compose запускает только инфраструктурные сервисы AlphaLab AI:

- PostgreSQL 18.4;
- Redis 8.8.0.

Backend и другие компоненты проекта в Compose пока не подключены.

## Требования

- Docker Engine или Docker Desktop;
- Docker Compose v2 (`docker compose`).

## Подготовка окружения

Из корня репозитория создайте локальный файл окружения на основе примера.

PowerShell:

```powershell
Copy-Item .env.example .env
```

Linux и macOS:

```bash
cp .env.example .env
```

Перед использованием вне локальной среды обязательно замените демонстрационные учетные данные и заполните секреты. Файл `.env` исключен из Git.

## Запуск

```bash
docker compose up -d
```

Проверить состояние и healthcheck сервисов:

```bash
docker compose ps
```

Посмотреть логи:

```bash
docker compose logs -f postgres redis
```

## Остановка

Остановить контейнеры, сохранив данные в именованных volumes:

```bash
docker compose down
```

Удалить контейнеры вместе с локальными данными PostgreSQL и Redis:

```bash
docker compose down --volumes
```

Команда с `--volumes` необратимо удаляет локальные данные и должна использоваться только осознанно.

## Проверка конфигурации

Проверить итоговую конфигурацию без запуска контейнеров:

```bash
docker compose config
```

Для проверки с явным файлом окружения:

```bash
docker compose --env-file .env.example config
```

## Подключения с локальной машины

- PostgreSQL: `localhost:5432`;
- Redis: `localhost:6379`.

Параметры PostgreSQL задаются через `.env`. Именованные volumes `postgres_data` и `redis_data` сохраняют данные между перезапусками контейнеров. Оба сервиса подключены к изолированной bridge-сети `alphalab-network`.
