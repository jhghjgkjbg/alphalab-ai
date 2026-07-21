# Publication Pipeline

Publication принимает ScoringCompleted, применяет независимую Policy, создаёт immutable candidate и вызывает только выбранные каналы.

ScoreThresholdPolicy MVP получает threshold и channels из composition root. ConsolePublisher только доставляет candidate и не принимает решений. PublisherRegistry и InMemoryPublicationLedger являются локальными объектами без singleton.

Candidate ID — стабильный UUIDv5 от document ID и policy version. Ledger предотвращает повторный вызов Publisher. Ошибка одного канала превращается в failed PublishResult и не останавливает остальные.
