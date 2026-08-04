import asyncio
import unittest
from agents.ai_scout.clients.pypi_client import PyPIClient
from agents.ai_scout.clients.npm_client import NpmClient
from agents.ai_scout.collectors.pypi import PyPICollector
from agents.ai_scout.collectors.npm import NpmCollector

class PackageCollectorTests(unittest.TestCase):
    def test_pypi_mapping_and_limit(self):
        async def request(*_):
            return {"info": {"name": "transformers", "version": "1.0", "summary": "ML", "project_url": "https://pypi.org/project/transformers/"}, "releases": {"1.0": [{"upload_time_iso_8601": "2026-01-01T00:00:00Z"}]}}
        result = asyncio.run(PyPICollector(PyPIClient(2, request), ("transformers",), 1).collect())
        self.assertEqual(result.items[0].external_id, "transformers@1.0")
        self.assertEqual(result.items[0].source, "pypi")

    def test_npm_scoped_mapping(self):
        async def request(*_):
            return {"dist-tags": {"latest": "2.0.0"}, "time": {"2.0.0": "2026-01-01T00:00:00Z"}, "versions": {"2.0.0": {"name": "@anthropic-ai/sdk", "description": "SDK"}}}
        result = asyncio.run(NpmCollector(NpmClient(2, request), ("@anthropic-ai/sdk",), 1).collect())
        self.assertEqual(result.items[0].external_id, "@anthropic-ai/sdk@2.0.0")
        self.assertEqual(result.items[0].source, "npm")

    def test_malformed_package_isolated(self):
        async def request(url, *_):
            if "bad" in url: return 500, {}
            return {"info": {"name": "torch", "version": "1", "summary": ""}, "releases": {"1": []}}
        result = asyncio.run(PyPICollector(PyPIClient(2, request), ("bad", "torch"), 10).collect())
        self.assertEqual(len(result.items), 1)

