import asyncio
import logging
from collections import defaultdict
from typing import Any

from core.event_bus.base import BaseEventBus
from core.event_bus.types import EventHandler


logger = logging.getLogger(__name__)


class InMemoryEventBus(BaseEventBus):
    def __init__(self) -> None:
        self._handlers: dict[type[Any], list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type[Any], handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    async def publish(self, event: Any) -> None:
        handlers = tuple(self._handlers.get(type(event), ()))
        await asyncio.gather(
            *(self._invoke(handler, event) for handler in handlers),
        )

    @staticmethod
    async def _invoke(handler: EventHandler, event: Any) -> None:
        try:
            await handler(event)
        except Exception:
            handler_name = getattr(handler, "__qualname__", repr(handler))
            logger.exception(
                "Event handler failed",
                extra={
                    "event_type": type(event).__name__,
                    "handler": handler_name,
                },
            )
