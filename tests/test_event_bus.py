import asyncio
import unittest

from core.event_bus.in_memory import InMemoryEventBus


class ExampleEvent:
    pass


class InMemoryEventBusTests(unittest.TestCase):
    def test_publishes_event_to_one_handler(self) -> None:
        received: list[ExampleEvent] = []

        async def handler(event: ExampleEvent) -> None:
            received.append(event)

        event_bus = InMemoryEventBus()
        event_bus.subscribe(ExampleEvent, handler)
        event = ExampleEvent()

        asyncio.run(event_bus.publish(event))

        self.assertEqual(received, [event])

    def test_publishes_event_to_multiple_handlers(self) -> None:
        received: list[str] = []

        async def first_handler(_: ExampleEvent) -> None:
            received.append("first")

        async def second_handler(_: ExampleEvent) -> None:
            received.append("second")

        event_bus = InMemoryEventBus()
        event_bus.subscribe(ExampleEvent, first_handler)
        event_bus.subscribe(ExampleEvent, second_handler)

        asyncio.run(event_bus.publish(ExampleEvent()))

        self.assertCountEqual(received, ["first", "second"])

    def test_handler_error_does_not_stop_other_handlers(self) -> None:
        received: list[str] = []

        async def failing_handler(_: ExampleEvent) -> None:
            raise RuntimeError("handler failed")

        async def successful_handler(_: ExampleEvent) -> None:
            received.append("success")

        event_bus = InMemoryEventBus()
        event_bus.subscribe(ExampleEvent, failing_handler)
        event_bus.subscribe(ExampleEvent, successful_handler)

        with self.assertLogs("core.event_bus.in_memory", level="ERROR"):
            asyncio.run(event_bus.publish(ExampleEvent()))

        self.assertEqual(received, ["success"])
