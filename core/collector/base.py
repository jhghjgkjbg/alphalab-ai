from abc import ABC, abstractmethod

from core.collector.types import CollectorResult


class BaseCollector(ABC):
    """Contract implemented by every Alpha Core collector."""

    @classmethod
    @abstractmethod
    def name(cls) -> str:
        """Return the stable, unique collector name."""

    @abstractmethod
    async def collect(self) -> CollectorResult:
        """Collect source items and return a completed collection result."""
