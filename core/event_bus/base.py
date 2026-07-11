from abc import ABC, abstractmethod
from typing import Any

from core.event_bus.types import EventHandler


class BaseEventBus(ABC):
    @abstractmethod
    def subscribe(self, event_type: type[Any], handler: EventHandler) -> None:
        """Subscribe an asynchronous handler to an exact event type."""

    @abstractmethod
    async def publish(self, event: Any) -> None:
        """Publish an event and wait until all subscribed handlers finish."""
