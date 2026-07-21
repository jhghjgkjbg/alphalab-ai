from collections.abc import Callable
from datetime import UTC, datetime

from core.publication.types import PublicationDecision


Clock = Callable[[], datetime]


class ScoreThresholdPolicy:
    def __init__(
        self,
        minimum_score: int,
        channels: tuple[str, ...],
        *,
        version: int = 1,
        clock: Clock | None = None,
    ) -> None:
        if version <= 0:
            raise ValueError("policy version must be positive")
        self._minimum_score = minimum_score
        self._channels = tuple(dict.fromkeys(channels))
        self._version = version
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def name(self) -> str:
        return "score_threshold"

    @property
    def version(self) -> int:
        return self._version

    def evaluate(self, total_score: int) -> PublicationDecision:
        accepted = total_score >= self._minimum_score
        channels = self._channels if accepted else ()
        reason = (
            f"Score {total_score} meets minimum {self._minimum_score}"
            if accepted
            else f"Score {total_score} is below minimum {self._minimum_score}"
        )
        return PublicationDecision(
            accepted=accepted,
            channels=channels,
            reason=reason,
            policy_name=self.name,
            policy_version=self.version,
            minimum_score=self._minimum_score,
            evaluated_at=self._clock(),
        )
