from collections.abc import Callable
from datetime import UTC, datetime
from typing import TextIO

from core.publication.base import Publisher
from core.publication.types import PublicationCandidate, PublishResult


Clock = Callable[[], datetime]


class PublisherRegistry:
    def __init__(self) -> None:
        self._publishers: dict[str, Publisher] = {}

    def register(self, publisher: Publisher) -> None:
        channel = publisher.channel_name
        if not channel:
            raise ValueError("channel_name must not be empty")
        if channel in self._publishers:
            raise ValueError(f"publisher is already registered: {channel}")
        self._publishers[channel] = publisher

    def get(self, channel_name: str) -> Publisher:
        return self._publishers[channel_name]

    def channels(self) -> tuple[str, ...]:
        return tuple(self._publishers)


class ConsolePublisher:
    def __init__(self, output: TextIO, clock: Clock | None = None) -> None:
        self._output = output
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def channel_name(self) -> str:
        return "console"

    async def publish(self, candidate: PublicationCandidate) -> PublishResult:
        print(f"Title: {candidate.title}", file=self._output)
        print(f"URL: {candidate.url or '<unknown>'}", file=self._output)
        print(f"Source: {candidate.source}", file=self._output)
        print(f"Summary: {candidate.summary}", file=self._output)
        print(f"Keywords: {', '.join(candidate.keywords)}", file=self._output)
        print(f"Tags: {', '.join(candidate.tags)}", file=self._output)
        print(f"Total score: {candidate.total_score}", file=self._output)
        print("Reasons:", file=self._output)
        for reason in candidate.reasons:
            print(f"- {reason}", file=self._output)
        print(f"Publication candidate ID: {candidate.candidate_id}", file=self._output)
        print(file=self._output)
        return PublishResult(
            channel=self.channel_name,
            success=True,
            external_id=str(candidate.candidate_id),
            published_at=self._clock(),
            error_message=None,
        )
