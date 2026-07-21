import asyncio
import io
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from core.publication.engine import PublicationEngine
from core.publication.policy import ScoreThresholdPolicy
from core.publication.publishers import ConsolePublisher, PublisherRegistry
from core.publication.types import build_candidate_id


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


def policy() -> ScoreThresholdPolicy:
    return ScoreThresholdPolicy(50, ("console",), clock=lambda: NOW)


def document():
    return SimpleNamespace(
        id=uuid4(), source="hacker_news", title="OpenAI story",
        url="https://example.com/story", summary="Summary",
        keywords=("openai",), tags=("ai",),
    )


def scoring(total_score: int):
    return SimpleNamespace(
        total_score=total_score,
        reasons=("reason",),
        correlation_id=uuid4(),
    )


class PublicationPolicyTests(unittest.TestCase):
    def test_rejects_score_below_threshold(self) -> None:
        decision = policy().evaluate(49)
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.channels, ())

    def test_accepts_score_equal_to_threshold(self) -> None:
        decision = policy().evaluate(50)
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.channels, ("console",))

    def test_accepts_score_above_threshold(self) -> None:
        self.assertTrue(policy().evaluate(80).accepted)

    def test_candidate_id_is_stable_for_document_and_policy_version(self) -> None:
        document_id = uuid4()
        self.assertEqual(
            build_candidate_id(document_id, 1),
            build_candidate_id(document_id, 1),
        )
        self.assertNotEqual(
            build_candidate_id(document_id, 1),
            build_candidate_id(document_id, 2),
        )

    def test_engine_creates_candidate_only_when_accepted(self) -> None:
        registry = PublisherRegistry()
        registry.register(ConsolePublisher(io.StringIO(), clock=lambda: NOW))
        engine = PublicationEngine(policy(), registry, clock=lambda: NOW)
        item = document()

        rejected = engine.plan(item, scoring(49))
        accepted = engine.plan(item, scoring(50))

        self.assertIsNone(rejected.candidate)
        self.assertIsNotNone(accepted.candidate)
        self.assertEqual(accepted.candidate.channels, ("console",))
        self.assertEqual(accepted.candidate.created_at, NOW)


if __name__ == "__main__":
    unittest.main()
