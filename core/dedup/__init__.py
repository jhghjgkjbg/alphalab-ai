from .engine import DedupEngine
from .types import DedupStats, DuplicateGroup, NormalizedItem

__all__ = ["DedupEngine", "DedupStats", "DuplicateGroup", "NormalizedItem"]
from .semantic import DeduplicationEngine, DeduplicationDecision
