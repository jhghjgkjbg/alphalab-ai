import unittest
from pathlib import Path


class WebsiteSearchScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = Path(__file__).parents[1].joinpath("agents", "ai_scout", "web", "static", "app.js").read_text(encoding="utf-8")

    def test_debounce_and_empty_search_use_same_load_path(self):
        self.assertIn("setTimeout(() => load(true), 280)", self.script)
        self.assertIn("clearTimeout(state.searchTimer)", self.script)
        self.assertIn("const q = search.value.trim(); if (q) p.set('q', q);", self.script)

    def test_abort_and_stale_response_guards(self):
        self.assertIn("state.controller.abort()", self.script)
        self.assertIn("new AbortController()", self.script)
        self.assertIn("signal: controller.signal", self.script)
        self.assertIn("requestId !== state.requestId", self.script)
        self.assertIn("e.name !== 'AbortError'", self.script)

    def test_filters_sort_and_load_more_are_preserved(self):
        self.assertIn("p.set('category', $('category').value)", self.script)
        self.assertIn("p.set('source', $('source').value)", self.script)
        self.assertIn("sort: $('sort').value", self.script)
        self.assertIn("state.page++; load(false)", self.script)
        self.assertIn("setAttribute('aria-busy', 'true')", self.script)
        self.assertIn("setAttribute('aria-busy', 'false')", self.script)


if __name__ == "__main__": unittest.main()
