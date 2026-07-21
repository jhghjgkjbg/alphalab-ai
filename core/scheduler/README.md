# In-Memory Scheduler

Scheduler регистрирует периодические async callbacks, вычисляет fixed-delay next run и хранит минимальную статистику. Он не знает, вызывает callback Collector, SourceManager или другой application service.

`InMemoryScheduler` использует внедряемые clock и sleep, не создаёт потоки и не является singleton. Ошибка callback сохраняется в task stats и не останавливает запуск других due-задач.

MVP не содержит cron, persistent schedules, distributed locks, priority queue, APScheduler, Celery или Redis.
