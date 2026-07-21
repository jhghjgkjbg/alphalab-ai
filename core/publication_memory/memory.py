from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from math import sqrt
from typing import Any

@dataclass(frozen=True, slots=True)
class PublicationMemory:
    title: str
    url: str
    source: str
    published_at: datetime
    embedding: tuple[float, ...] = ()
    category: str = ""

    def similar(self, vector: tuple[float, ...], threshold: float) -> bool:
        if not self.embedding or len(self.embedding) != len(vector): return False
        dot = sum(a*b for a,b in zip(self.embedding, vector)); na = sqrt(sum(a*a for a in self.embedding)); nb = sqrt(sum(b*b for b in vector))
        return na > 0 and nb > 0 and dot/(na*nb) > threshold
