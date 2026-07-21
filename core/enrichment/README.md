# Enrichment Pipeline

Enrichment дополняет канонический KnowledgeDocument производными полями summary, keywords и tags без изменения исходного объекта.

MVP использует три детерминированных provider: ограниченное summary, ordered keywords с ru/en stop-words и tags по фиксированному словарю категорий. Engine изолирует ошибку provider и сохраняет её в warnings.

EnrichmentHandler создаёт новую immutable версию документа, выполняет optimistic update и публикует KnowledgeEnriched только после успешной записи. Модуль не использует LLM, внешние API или глобальный singleton.
