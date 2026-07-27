# Content distribution runbook

Запускайте команды из корня проекта с активированным project environment. Scheduler не следует запускать чаще, чем длится один production run: lock защищает от overlap, но не заменяет корректное расписание.

## 1. Preflight

```text
python -m scripts.check_distribution_config
```

Preflight выполняет только локальные проверки конфигурации и runtime paths.

## 2. Ручной scheduled runner

```text
python -m scripts.run_scheduled_distribution
```

Runner запускает один production cycle:
`python -m agents.ai_scout.agent --production-run --confirm-send`.

## 3. Windows Task Scheduler

Создайте задачу с рабочим каталогом корня проекта и action на существующий Python environment:

```text
python -m scripts.run_scheduled_distribution
```

Передайте необходимые env через системную конфигурацию/профиль задачи; не записывайте credentials в arguments.

## 4. Status report

```text
python -m scripts.report_distribution_status
python -m scripts.report_distribution_status --json
```

Отчёт read-only. Он показывает persisted delivery/growth events и attention-required destinations.

## 5. Exit codes

- `0` — успешно;
- `1` — production/preflight failure;
- `2` — lock contention;
- `3` — startup/configuration failure.

## 6. Recovery

- Lock contention: дождитесь завершения текущего run; stale lock старше установленного TTL удаляется следующим запуском.
- Failed: проверьте status report и конфигурацию перед следующим due run.
- Unknown: не повторяйте вручную без подтверждения remote outcome; сохранённое состояние terminal.
- Stale pending: следующий due запуск обрабатывает его по существующей pending TTL policy.

## 7. Credential rotation

Обновите credentials в защищённом env/config store, выполните preflight, затем запустите следующий scheduled run. Не выводите и не передавайте secrets через CLI arguments; старые значения удаляйте после проверки нового окружения.
