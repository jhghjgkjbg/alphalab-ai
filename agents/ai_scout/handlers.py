from dataclasses import dataclass
from uuid import UUID

from core.enrichment.events import KnowledgeEnriched
from core.knowledge.events import KnowledgeStored
from core.publication.events import (
    PublicationCandidateCreated,
    PublicationCompleted,
    PublicationRejected,
)
from core.scoring.events import ScoringCompleted


@dataclass(frozen=True, slots=True)
class PipelineStats:
    stored: int = 0
    enriched: int = 0
    scored: int = 0
    accepted: int = 0
    rejected: int = 0
    published_successfully: int = 0
    publication_failures: int = 0


class PipelineStatsHandler:
    def __init__(self) -> None:
        self._stats: dict[UUID, PipelineStats] = {}

    async def handle_stored(self, event: KnowledgeStored) -> None:
        self._increment(event.correlation_id, "stored")

    async def handle_enriched(self, event: KnowledgeEnriched) -> None:
        self._increment(event.correlation_id, "enriched")

    async def handle_scored(self, event: ScoringCompleted) -> None:
        self._increment(event.correlation_id, "scored")

    async def handle_candidate(self, event: PublicationCandidateCreated) -> None:
        self._increment(event.correlation_id, "accepted")

    async def handle_rejected(self, event: PublicationRejected) -> None:
        self._increment(event.correlation_id, "rejected")

    async def handle_completed(self, event: PublicationCompleted) -> None:
        current = self.snapshot(event.correlation_id)
        successes = sum(result.success for result in event.results)
        failures = len(event.results) - successes
        self._stats[event.correlation_id] = PipelineStats(
            stored=current.stored,
            enriched=current.enriched,
            scored=current.scored,
            accepted=current.accepted,
            rejected=current.rejected,
            published_successfully=current.published_successfully + successes,
            publication_failures=current.publication_failures + failures,
        )

    def snapshot(self, correlation_id: UUID) -> PipelineStats:
        return self._stats.get(correlation_id, PipelineStats())

    def new_items(self, correlation_id: UUID) -> int:
        return self.snapshot(correlation_id).stored

    def _increment(self, correlation_id: UUID, field: str) -> None:
        current = self.snapshot(correlation_id)
        values = {
            "stored": current.stored,
            "enriched": current.enriched,
            "scored": current.scored,
            "accepted": current.accepted,
            "rejected": current.rejected,
            "published_successfully": current.published_successfully,
            "publication_failures": current.publication_failures,
        }
        values[field] += 1
        self._stats[correlation_id] = PipelineStats(**values)
