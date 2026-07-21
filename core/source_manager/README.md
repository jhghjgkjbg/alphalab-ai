# Source Manager

SourceManager запускает зарегистрированный источник по ID, создаёт Collector через CollectorRegistry и публикует CollectionCompleted. Он не знает о Scheduler, Knowledge, Enrichment, Scoring или Repository.

SourceRegistry хранит immutable SourceDefinition. Enable/disable создаёт новый объект. Priority (`critical`, `high`, `normal`, `low`) подготовлен для будущей очереди; MVP сохраняет порядок регистрации.

Неизвестный и отключённый источник возвращают SourceRunResult без запуска. Исключение Collector превращается в failed CollectionCompleted и не мешает следующему источнику.
