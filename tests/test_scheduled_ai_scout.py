import ast
import asyncio
import io
import pathlib
import unittest

from agents.ai_scout.agent import AIScout, parse_args
from agents.ai_scout.collectors.hacker_news import HackerNewsCollector
from core.knowledge.repository import InMemoryKnowledgeRepository
from core.scheduler.in_memory import InMemoryScheduler
from core.source_manager.types import SourceRunStatus


def mocked_collector() -> HackerNewsCollector:
    def fetch_json(url: str, _: float) -> object:
        if url.endswith("topstories.json"):
            return [501]
        return {
            "id": 501,
            "title": "Scheduled OpenAI story",
            "url": "https://example.com/501",
        }

    return HackerNewsCollector(fetch_json=fetch_json)


class ScheduledAIScoutTests(unittest.TestCase):
    def test_once_runs_complete_mocked_pipeline(self) -> None:
        repository = InMemoryKnowledgeRepository()
        output = io.StringIO()
        scout = AIScout(
            collector=mocked_collector(),
            knowledge_store=repository,
            output=output,
        )

        results = asyncio.run(scout.run_once())

        self.assertEqual(results[0].status, SourceRunStatus.SUCCESS)
        self.assertEqual(repository.count(), 1)
        self.assertEqual(repository.all()[0].version, 2)
        self.assertIn("Collected records: 1", output.getvalue())
        self.assertIn("Stored records: 1", output.getvalue())
        self.assertIn("Enriched records: 1", output.getvalue())
        self.assertIn("Scored records: 1", output.getvalue())
        self.assertIn("Accepted for publication: 1", output.getvalue())
        self.assertIn("Rejected: 0", output.getvalue())
        self.assertIn("Published successfully: 1", output.getvalue())
        self.assertIn("Publication failures: 0", output.getvalue())
        self.assertIn("Total score:", output.getvalue())

    def test_scheduled_callback_runs_source_manager(self) -> None:
        scheduler = InMemoryScheduler()
        repository = InMemoryKnowledgeRepository()
        scout = AIScout(
            collector=mocked_collector(),
            scheduler=scheduler,
            knowledge_store=repository,
            output=io.StringIO(),
        )

        succeeded = asyncio.run(scheduler.run_task(scout.SCHEDULE_TASK_ID))

        self.assertTrue(succeeded)
        self.assertEqual(repository.count(), 1)
        self.assertEqual(scheduler.tasks()[0].run_count, 1)

    def test_cli_modes_are_parsed(self) -> None:
        self.assertTrue(parse_args(["--once"]).once)
        self.assertTrue(parse_args(["--serve"]).serve)

    def test_ai_scout_does_not_call_collector_collect_directly(self) -> None:
        path = pathlib.Path("agents/ai_scout/agent.py")
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        direct_calls = [
            ast.unparse(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "collect"
        ]
        self.assertEqual(direct_calls, [])


if __name__ == "__main__":
    unittest.main()
