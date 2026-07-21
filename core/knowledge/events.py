from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

@dataclass(frozen=True, slots=True)
class KnowledgeStored:
    event_id: UUID
    event_version: int
    occurred_at: datetime
    document_id: UUID
    source: str
    source_external_id: str
    correlation_id: UUID
