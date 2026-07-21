from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class KnowledgeEnriched:
    event_id: UUID
    event_version: int
    occurred_at: datetime
    document_id: UUID
    previous_version: int
    current_version: int
    correlation_id: UUID
    warnings: tuple[str, ...]
