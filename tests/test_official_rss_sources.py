import asyncio
import unittest

from agents.ai_scout.agent import AIScout
from agents.ai_scout.collectors.rss import RSSCollector


class OfficialRSSSourcesTests(unittest.TestCase):
    def test_official_sources_register_with_stable_slugs(self):
        scout = AIScout(
            rss_enabled=True,
            rss_fetch=lambda *_: b"<rss><channel><item><title>x</title><link>https://example.test/x</link></item></channel></rss>",
            openai_news_enabled=True,
            microsoft_research_enabled=True,
            huggingface_blog_enabled=True,
            github_blog_enabled=True,
            rust_blog_enabled=True,
            go_blog_enabled=True,
            docker_blog_enabled=True,
            kubernetes_cve_enabled=True,
            cloudflare_blog_enabled=True,
            linux_foundation_enabled=True,
            arduino_blog_enabled=True,
            raspberry_pi_blog_enabled=True,
            jetbrains_blog_enabled=True,
            gitlab_blog_enabled=True,
            python_insider_enabled=True,
            eclipse_foundation_enabled=True,
        )
        sources = scout._source_manager._source_registry._sources
        expected = {
            "openai_news": "https://openai.com/news/rss.xml",
            "microsoft_research": "https://www.microsoft.com/en-us/research/feed/",
            "huggingface_blog": "https://huggingface.co/blog/feed.xml",
            "github_blog": "https://github.blog/feed/",
            "rust_blog": "https://blog.rust-lang.org/feed.xml",
            "go_blog": "https://go.dev/blog/feed.atom",
            "docker_blog": "https://www.docker.com/blog/feed/",
            "kubernetes_cve": "https://k8s.io/docs/reference/issues-security/official-cve-feed/feed.xml",
            "cloudflare_blog": "https://blog.cloudflare.com/rss/",
            "linux_foundation": "https://www.linuxfoundation.org/blog/rss.xml",
            "arduino_blog": "https://blog.arduino.cc/feed/",
            "raspberry_pi_blog": "https://www.raspberrypi.com/news/feed/",
            "jetbrains_blog": "https://blog.jetbrains.com/feed/",
            "gitlab_blog": "https://about.gitlab.com/atom.xml",
            "python_insider": "https://feeds.feedburner.com/PythonInsider",
            "eclipse_foundation": "https://blogs.eclipse.org/rss.xml",
        }
        self.assertEqual(len(expected), 16)
        categories = {
            "openai_news": "AI", "microsoft_research": "Research", "huggingface_blog": "AI",
            "github_blog": "Developer Tools", "rust_blog": "Open Source", "go_blog": "Developer Tools",
            "docker_blog": "Developer Tools", "kubernetes_cve": "Security",
            "cloudflare_blog": "Security", "linux_foundation": "Open Source",
            "arduino_blog": "Hardware", "raspberry_pi_blog": "Hardware",
            "jetbrains_blog": "Developer Tools", "gitlab_blog": "Developer Tools",
            "python_insider": "Developer Tools", "eclipse_foundation": "Open Source",
        }
        self.assertEqual(len(sources), 18)  # HN, legacy RSS, plus these sixteen definitions
        for slug, url in expected.items():
            self.assertEqual(sources[slug].metadata["feed_url"], url)
            self.assertEqual(sources[slug].metadata["source_name"], slug)
            self.assertEqual(sources[slug].metadata["category"], categories[slug])
            self.assertEqual(sources[slug].max_items, 10)

    def test_each_flag_disables_only_its_source(self):
        flags = ("openai_news_enabled", "microsoft_research_enabled", "huggingface_blog_enabled", "github_blog_enabled", "rust_blog_enabled", "go_blog_enabled", "docker_blog_enabled", "kubernetes_cve_enabled", "cloudflare_blog_enabled", "linux_foundation_enabled", "arduino_blog_enabled", "raspberry_pi_blog_enabled", "jetbrains_blog_enabled", "gitlab_blog_enabled", "python_insider_enabled", "eclipse_foundation_enabled")
        for flag in flags:
            kwargs = {name: True for name in flags}
            kwargs[flag] = False
            scout = AIScout(rss_enabled=True, rss_fetch=lambda *_: b"<rss><channel/></rss>", **kwargs)
            self.assertNotIn(flag.removesuffix("_enabled"), scout._source_manager._source_registry._sources)

    def test_atom_and_guid_fallback_are_generic(self):
        feed = b"""<feed xmlns='http://www.w3.org/2005/Atom'><entry><title>Example</title><id>https://example.test/item</id><summary>Text</summary><updated>2026-01-01T00:00:00Z</updated></entry></feed>"""
        result = asyncio.run(RSSCollector("https://example.test/feed", fetch=lambda *_: feed, source_name="example").collect())
        self.assertEqual(result.items[0].payload["url"], "https://example.test/item")
        self.assertEqual(result.items[0].source, "example")


if __name__ == "__main__":
    unittest.main()
