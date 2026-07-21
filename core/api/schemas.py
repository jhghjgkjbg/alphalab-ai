from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any

@dataclass(frozen=True, slots=True)
class PublishedArticle:
    id: str; published_at: str; title: str; summary: str; url: str; source: str; category: str = ""; language: str = "en"; score: float = 0.0; trend_bonus: float = 0.0; reputation: float = 0.0; editorial_score: float = 0.0; editorial_verdict: str = ""
    def to_dict(self): return asdict(self)
