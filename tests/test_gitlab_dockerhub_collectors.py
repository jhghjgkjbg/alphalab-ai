import asyncio
import unittest
from agents.ai_scout.clients.gitlab_client import GitLabClient
from agents.ai_scout.clients.dockerhub_client import DockerHubClient
from agents.ai_scout.collectors.gitlab import GitLabCollector
from agents.ai_scout.collectors.dockerhub import DockerHubCollector
class ApiCollectorTests(unittest.TestCase):
    def test_gitlab_mapping(self):
        async def req(*_): return [{"id": 42, "name_with_namespace": "org/p", "web_url": "https://gitlab.com/org/p", "star_count": 3, "last_activity_at": "2026-01-01T00:00:00Z"}]
        r=asyncio.run(GitLabCollector(GitLabClient(10, req),1).collect()); self.assertEqual(r.items[0].external_id,"42"); self.assertEqual(r.items[0].source,"gitlab")
    def test_dockerhub_mapping(self):
        async def req(*_): return {"results":[{"user":"library","name":"python","description":"","last_updated":"2026-01-01T00:00:00Z"}]}
        r=asyncio.run(DockerHubCollector(DockerHubClient(10, req),1).collect()); self.assertEqual(r.items[0].external_id,"library/python"); self.assertEqual(r.items[0].source,"dockerhub")
    def test_malformed_isolated(self):
        async def req(*_): return {"bad": True}
        self.assertEqual(len(asyncio.run(GitLabClient(10, req).fetch_projects(10))),0)
