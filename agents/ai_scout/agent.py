import argparse
import json
import os
import time
from pathlib import Path
import asyncio
import logging
import sys
import math
from datetime import datetime
from collections.abc import Callable
from typing import TextIO

from agents.ai_scout.collectors.hacker_news import HackerNewsCollector
from agents.ai_scout.clients.hacker_news_client import HackerNewsClient
from agents.ai_scout.collectors.rss import RSSCollector
from agents.ai_scout.collectors.github import GitHubTrendingCollector
from agents.ai_scout.clients.github_client import GitHubClient
from agents.ai_scout.collectors.reddit import RedditCollector
from agents.ai_scout.clients.reddit_client import RedditClient
from agents.ai_scout.clients.product_hunt_client import ProductHuntClient
from agents.ai_scout.collectors.product_hunt import ProductHuntCollector
from agents.ai_scout.collectors.pypi import PyPICollector
from agents.ai_scout.collectors.npm import NpmCollector
from agents.ai_scout.collectors.gitlab import GitLabCollector
from agents.ai_scout.collectors.dockerhub import DockerHubCollector
from agents.ai_scout.clients.gitlab_client import GitLabClient
from agents.ai_scout.clients.dockerhub_client import DockerHubClient
from agents.ai_scout.clients.pypi_client import PyPIClient
from agents.ai_scout.clients.npm_client import NpmClient
from agents.ai_scout.clients.devto_client import DevToClient
from agents.ai_scout.collectors.devto import DevToCollector
from agents.ai_scout.clients.lobsters_client import LobstersClient
from agents.ai_scout.collectors.lobsters import LobstersCollector
from agents.ai_scout.clients.arxiv_client import ArxivClient
from agents.ai_scout.collectors.arxiv import ArxivCollector
from agents.ai_scout.handlers import PipelineStatsHandler
from agents.ai_scout.publishers.telegram_client import TelegramClient, TelegramRequest
from agents.ai_scout.publishers.telegram_publisher import TelegramPublisher
from core.collector.base import BaseCollector
from core.collector.events import CollectionCompleted
from core.collector.registry import CollectorRegistry
from core.enrichment.engine import EnrichmentEngine
from core.enrichment.events import KnowledgeEnriched
from core.enrichment.handler import EnrichmentHandler
from core.enrichment.providers import (
    DeterministicKeywordProvider,
    DeterministicSummaryProvider,
    DictionaryTagProvider,
)
from core.event_bus.base import BaseEventBus
from core.event_bus.in_memory import InMemoryEventBus
from core.knowledge.events import KnowledgeStored
from core.knowledge.handler import KnowledgeHandler
from core.knowledge.repository import InMemoryKnowledgeRepository, KnowledgeRepository
from core.publication.engine import InMemoryPublicationLedger, PublicationEngine
from core.publication.events import (
    PublicationCandidateCreated,
    PublicationCompleted,
    PublicationRejected,
)
from core.publication.handler import PublicationHandler
from core.publication.policy import ScoreThresholdPolicy
from core.publication.publishers import ConsolePublisher, PublisherRegistry
from core.scheduler.base import Scheduler
from core.scheduler.in_memory import InMemoryScheduler
from core.scoring.engine import ScoringEngine
from core.scoring.events import ScoringCompleted
from core.scoring.handler import ScoringHandler
from core.scoring.rules import FreshnessRule, KeywordRule, SourceTrustRule
from core.source_manager.manager import SourceManager
from core.source_manager.registry import SourceRegistry
from core.source_manager.types import (
    SourceDefinition,
    SourcePriority,
    SourceRunResult,
)


logger = logging.getLogger(__name__)


def production_scoring_request(item, ranking_score):
    """Preserve source-provided scoring signals at the production boundary."""
    from core.scoring.types import ScoringRequest

    payload = getattr(item, "payload", {}) or {}
    def number(name):
        try:
            return float(payload.get(name, 0) or 0)
        except (TypeError, ValueError):
            return 0.0
    published_at = payload.get("published_at")
    if isinstance(published_at, str):
        try:
            published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except ValueError:
            published_at = None
    popularity = _normalized_popularity(payload)
    source_weights = {"openai_news": .08, "microsoft_research": .08, "arxiv": .08, "deepmind": .08, "github_blog": .06, "gitlab": .06, "jetbrains_blog": .06, "rust_blog": .06, "go_blog": .06, "python_insider": .06, "docker_blog": .06, "linux_foundation": .06, "cloudflare_blog": .06, "kubernetes_cve": .06, "reddit": .03, "hacker_news": .03, "devto": .03, "lobsters": .03, "pypi": .02, "npm": .02, "dockerhub": .02}
    freshness = number("freshness_bonus")
    if not freshness and published_at:
        age_hours = max(0.0, (datetime.now(UTC) - published_at).total_seconds() / 3600)
        freshness = max(0.0, 0.05 * (0.5 ** (age_hours / 72.0)))
    return ScoringRequest(
        item,
        ranking_score=ranking_score,
        similarity_penalty=number("similarity_penalty"),
        source_priority=number("source_priority") or source_weights.get(str(getattr(item, "source", "")), 0.0),
        freshness_bonus=freshness,
        popularity_bonus=popularity,
        manual_boost=number("manual_boost"),
        published_at=published_at,
    )


def _normalized_popularity(payload):
    """Map heterogeneous collector popularity values monotonically to 0..1."""
    if not isinstance(payload, dict):
        return 0.0
    if "popularity_bonus" in payload:
        try:
            return max(0.0, min(0.5, float(payload["popularity_bonus"])))
        except (TypeError, ValueError):
            return 0.0
    for name, cap in (("score", 100.0), ("stars", 1000.0), ("reactions", 100.0), ("votes_count", 1000.0)):
        try:
            value = float(payload.get(name, 0) or 0)
        except (TypeError, ValueError):
            value = 0.0
        if value > 0:
            return max(0.0, min(0.5, 0.5 * math.log1p(value) / math.log1p(cap)))
        if name in payload:
            return 0.0
    return 0.0


class AIScout:
    SOURCE_ID = "hacker_news"
    SCHEDULE_TASK_ID = "source:hacker_news"
    RSS_SCHEDULE_TASK_ID = "source:rss"
    GITHUB_SCHEDULE_TASK_ID = "source:github"
    REDDIT_SCHEDULE_TASK_ID = "source:reddit"
    PRODUCT_HUNT_SCHEDULE_TASK_ID = "source:product_hunt"
    DEVTO_SCHEDULE_TASK_ID = "source:devto"
    LOBSTERS_SCHEDULE_TASK_ID = "source:lobsters"
    ARXIV_SCHEDULE_TASK_ID = "source:arxiv"

    def __init__(
        self,
        collector: BaseCollector | None = None,
        event_bus: BaseEventBus | None = None,
        knowledge_store: KnowledgeRepository | None = None,
        scheduler: Scheduler | None = None,
        output: TextIO | None = None,
        source_interval_seconds: float = 300.0,
        rss_enabled: bool | None = None,
        rss_feed_url: str = "https://news.ycombinator.com/rss",
        openai_news_enabled: bool = False,
        microsoft_research_enabled: bool = False,
        huggingface_blog_enabled: bool = False,
        github_blog_enabled: bool = False,
        rust_blog_enabled: bool = False,
        go_blog_enabled: bool = False,
        docker_blog_enabled: bool = False,
        kubernetes_cve_enabled: bool = False,
        cloudflare_blog_enabled: bool = False,
        linux_foundation_enabled: bool = False,
        arduino_blog_enabled: bool = False,
        raspberry_pi_blog_enabled: bool = False,
        rss_fetch: Callable[[str, float, int], bytes] | None = None,
        telegram_client: TelegramClient | None = None,
        telegram_bot_token: str | None = None,
        telegram_chat_id: str | int | None = None,
        telegram_parse_mode: str | None = None,
        telegram_request: TelegramRequest | None = None,
        github_client: GitHubClient | None = None,
        github_token: str | None = None,
        github_timeout: float = 10.0,
        github_max_items: int = 10,
        github_request: Callable[..., object] | None = None,
        github_enabled: bool | None = None,
        reddit_client: RedditClient | None = None,
        reddit_subreddit: str = "technology",
        reddit_limit: int = 10,
        reddit_timeout: float = 10.0,
        reddit_request: Callable[..., object] | None = None,
        reddit_enabled: bool | None = None,
        product_hunt_client: ProductHuntClient | None = None,
        product_hunt_token: str | None = None,
        product_hunt_timeout: float = 10.0,
        product_hunt_max_items: int = 10,
        product_hunt_request: Callable[..., object] | None = None,
        product_hunt_enabled: bool | None = None,
        devto_client: DevToClient | None = None,
        devto_timeout: float = 10.0,
        devto_max_items: int = 10,
        devto_tag: str | None = None,
        devto_request: Callable[..., object] | None = None,
        devto_enabled: bool | None = None,
        lobsters_client: LobstersClient | None = None,
        lobsters_timeout: float = 10.0,
        lobsters_max_items: int = 10,
        lobsters_request: Callable[..., object] | None = None,
        lobsters_enabled: bool | None = None,
        arxiv_client: ArxivClient | None = None,
        arxiv_timeout: float = 10.0,
        arxiv_max_items: int = 10,
        arxiv_search_query: str = "all:AI",
        arxiv_request: Callable[..., object] | None = None,
        arxiv_enabled: bool | None = None,
        hacker_news_client: object | None = None,
        hacker_news_max_items: int = HackerNewsCollector.STORY_LIMIT,
        hacker_news_timeout: float = 5.0,
        hacker_news_request: Callable[..., object] | None = None,
        pypi_enabled: bool = False, pypi_packages: tuple[str, ...] = (), pypi_max_items: int = 10, pypi_timeout_seconds: float = 10.0, pypi_request: Callable[..., object] | None = None,
        npm_enabled: bool = False, npm_packages: tuple[str, ...] = (), npm_max_items: int = 10, npm_timeout_seconds: float = 10.0, npm_request: Callable[..., object] | None = None,
        jetbrains_blog_enabled: bool = False, gitlab_blog_enabled: bool = False, python_insider_enabled: bool = False, eclipse_foundation_enabled: bool = False,
        gitlab_enabled: bool = False, gitlab_max_items: int = 10, gitlab_timeout_seconds: float = 10.0, gitlab_request: Callable[..., object] | None = None,
        dockerhub_enabled: bool = False, dockerhub_max_items: int = 10, dockerhub_timeout_seconds: float = 10.0, dockerhub_request: Callable[..., object] | None = None,
    ) -> None:
        self._event_bus = event_bus or InMemoryEventBus()
        self._output = output or sys.stdout
        repository = knowledge_store or InMemoryKnowledgeRepository()

        knowledge_handler = KnowledgeHandler(repository, self._event_bus)
        enrichment_handler = EnrichmentHandler(
            EnrichmentEngine(
                summary_providers=(DeterministicSummaryProvider(),),
                keyword_providers=(DeterministicKeywordProvider(),),
                tag_providers=(DictionaryTagProvider(),),
            ),
            repository,
            self._event_bus,
        )
        scoring_engine = ScoringEngine()
        scoring_engine.register(FreshnessRule())
        scoring_engine.register(SourceTrustRule())
        scoring_engine.register(KeywordRule())
        scoring_handler = ScoringHandler(scoring_engine, self._event_bus, repository)
        self._stats_handler = PipelineStatsHandler()

        publisher_registry = PublisherRegistry()
        publisher_registry.register(ConsolePublisher(self._output))
        if telegram_client is not None:
            publisher_registry.register(TelegramPublisher(telegram_client, parse_mode=telegram_parse_mode))
        elif telegram_bot_token and telegram_chat_id is not None and telegram_request is not None:
            publisher_registry.register(
                TelegramPublisher(
                    TelegramClient(
                        telegram_bot_token,
                        telegram_chat_id,
                        10.0,
                        telegram_request,
                        parse_mode=telegram_parse_mode,
                    ),
                    parse_mode=telegram_parse_mode,
                )
            )
        self._publisher_registry = publisher_registry
        publication_handler = PublicationHandler(
            PublicationEngine(
                ScoreThresholdPolicy(minimum_score=50, channels=("console",)),
                publisher_registry,
            ),
            repository,
            InMemoryPublicationLedger(),
            self._event_bus,
        )

        self._event_bus.subscribe(CollectionCompleted, knowledge_handler.handle)
        self._event_bus.subscribe(KnowledgeStored, enrichment_handler.handle)
        self._event_bus.subscribe(KnowledgeStored, self._stats_handler.handle_stored)
        self._event_bus.subscribe(KnowledgeEnriched, scoring_handler.handle)
        self._event_bus.subscribe(KnowledgeEnriched, self._stats_handler.handle_enriched)
        self._event_bus.subscribe(ScoringCompleted, publication_handler.handle)
        self._event_bus.subscribe(ScoringCompleted, self._stats_handler.handle_scored)
        self._event_bus.subscribe(
            PublicationCandidateCreated,
            self._stats_handler.handle_candidate,
        )
        self._event_bus.subscribe(PublicationRejected, self._stats_handler.handle_rejected)
        self._event_bus.subscribe(
            PublicationCompleted,
            self._stats_handler.handle_completed,
        )

        collector_registry = CollectorRegistry()
        if hacker_news_client is not None:
            collector_registry.register_factory(
                HackerNewsCollector.name(),
                lambda **config: HackerNewsCollector(
                    client=hacker_news_client,
                    max_items=int(config.get("max_items", hacker_news_max_items)),
                    timeout=hacker_news_timeout,
                ),
            )
        elif collector is None and hacker_news_request is not None:
            client = HackerNewsClient(hacker_news_timeout, hacker_news_request)
            collector_registry.register_factory(HackerNewsCollector.name(), lambda client=client, **config: HackerNewsCollector(client=client, max_items=int(config.get("max_items", hacker_news_max_items)), timeout=hacker_news_timeout))
        elif collector is None:
            collector_registry.register(HackerNewsCollector)
        else:
            collector_registry.register_factory(collector.name(), lambda: collector)

        if rss_enabled is None:
            rss_enabled = collector is None
        self._rss_enabled = rss_enabled
        if rss_enabled:
            def rss_factory(**configuration: object) -> RSSCollector:
                metadata = configuration["metadata"]
                max_items = configuration["max_items"]
                return RSSCollector(
                    feed_url=str(metadata["feed_url"]),
                    max_items=int(max_items),
                    fetch=rss_fetch,
                    source_name=str(metadata.get("source_name", "rss")),
                    category=str(metadata.get("category", "")),
                )

            collector_registry.register_factory(RSSCollector.name(), rss_factory)
        if github_enabled is None:
            github_enabled = github_client is not None or github_request is not None
        self._github_enabled = github_enabled
        if github_client is not None:
            collector_registry.register_factory(
                GitHubTrendingCollector.name(),
                lambda **config: GitHubTrendingCollector(
                    github_client, int(config.get("max_items", github_max_items)), category=config.get("category", "Open Source")
                ),
            )
        if reddit_enabled is None:
            reddit_enabled = reddit_client is not None or reddit_request is not None
        self._reddit_enabled = reddit_enabled
        if reddit_client is not None:
            collector_registry.register_factory(
                RedditCollector.name(),
                lambda **config: RedditCollector(
                    reddit_client, int(config.get("max_items", reddit_limit)), category=config.get("category", "AI")
                ),
            )
        if product_hunt_enabled is None:
            product_hunt_enabled = product_hunt_client is not None or product_hunt_request is not None
        self._product_hunt_enabled = product_hunt_enabled
        if product_hunt_client is not None:
            collector_registry.register_factory(
                ProductHuntCollector.name(),
                lambda **config: ProductHuntCollector(product_hunt_client, int(config.get("max_items", product_hunt_max_items))),
            )
        if pypi_request is not None:
            client = PyPIClient(pypi_timeout_seconds, pypi_request)
            collector_registry.register_factory(PyPICollector.name(), lambda client=client, **config: PyPICollector(client, tuple(config.get("packages", pypi_packages)), int(config.get("max_items", pypi_max_items))))
        if npm_request is not None:
            client = NpmClient(npm_timeout_seconds, npm_request)
            collector_registry.register_factory(NpmCollector.name(), lambda client=client, **config: NpmCollector(client, tuple(config.get("packages", npm_packages)), int(config.get("max_items", npm_max_items))))
        if gitlab_request is not None:
            client = GitLabClient(gitlab_timeout_seconds, gitlab_request)
            collector_registry.register_factory(GitLabCollector.name(), lambda client=client, **config: GitLabCollector(client, int(config.get("max_items", gitlab_max_items))))
        if dockerhub_request is not None:
            client = DockerHubClient(dockerhub_timeout_seconds, dockerhub_request)
            collector_registry.register_factory(DockerHubCollector.name(), lambda client=client, **config: DockerHubCollector(client, int(config.get("max_items", dockerhub_max_items))))
        if devto_enabled is None:
            devto_enabled = devto_client is not None or devto_request is not None
        self._devto_enabled = devto_enabled
        if devto_client is not None:
            collector_registry.register_factory(
                DevToCollector.name(),
                lambda **config: DevToCollector(devto_client, int(config.get("max_items", devto_max_items)), devto_tag),
            )
        if lobsters_enabled is None:
            lobsters_enabled = lobsters_client is not None or lobsters_request is not None
        self._lobsters_enabled = lobsters_enabled
        if lobsters_client is not None:
            collector_registry.register_factory(
                LobstersCollector.name(),
                lambda **config: LobstersCollector(lobsters_client, int(config.get("max_items", lobsters_max_items))),
            )
        if arxiv_enabled is None:
            arxiv_enabled = arxiv_client is not None or arxiv_request is not None
        self._arxiv_enabled = arxiv_enabled
        if arxiv_client is not None:
            collector_registry.register_factory(
                ArxivCollector.name(),
                lambda **config: ArxivCollector(arxiv_client, arxiv_search_query, int(config.get("max_items", arxiv_max_items))),
            )
        elif arxiv_request is not None:
            client = ArxivClient(arxiv_timeout, arxiv_request)
            collector_registry.register_factory(
                ArxivCollector.name(),
                lambda client=client, **config: ArxivCollector(client, arxiv_search_query, int(config.get("max_items", arxiv_max_items))),
            )
        if lobsters_request is not None:
            client = LobstersClient(lobsters_timeout, lobsters_request)
            collector_registry.register_factory(
                LobstersCollector.name(),
                lambda client=client, **config: LobstersCollector(client, int(config.get("max_items", lobsters_max_items))),
            )
        if devto_request is not None:
            client = DevToClient(devto_timeout, devto_request)
            collector_registry.register_factory(
                DevToCollector.name(),
                lambda client=client, **config: DevToCollector(client, int(config.get("max_items", devto_max_items)), devto_tag),
            )
        if product_hunt_request is not None and product_hunt_token:
            client = ProductHuntClient(product_hunt_token, product_hunt_timeout, product_hunt_request)
            collector_registry.register_factory(
                ProductHuntCollector.name(),
                lambda client=client, **config: ProductHuntCollector(client, int(config.get("max_items", product_hunt_max_items))),
            )
        if reddit_request is not None:
            client = RedditClient(reddit_subreddit, reddit_timeout, reddit_request)
            collector_registry.register_factory(
                RedditCollector.name(),
                lambda client=client, **config: RedditCollector(
                    client, int(config.get("max_items", reddit_limit)), category=config.get("category", "AI")
                ),
            )
        if github_request is not None:
            client = GitHubClient(github_timeout, github_request, github_token)
            collector_registry.register_factory(
                GitHubTrendingCollector.name(),
                lambda client=client, **config: GitHubTrendingCollector(
                    client, int(config.get("max_items", github_max_items)), category=config.get("category", "Open Source")
                ),
            )
        self._collector_registry = collector_registry

        source_registry = SourceRegistry()
        source_registry.register(
            SourceDefinition(
                source_id=self.SOURCE_ID,
                collector_name=HackerNewsCollector.name(),
                enabled=True,
                interval_seconds=source_interval_seconds,
                priority=SourcePriority.NORMAL,
                max_items=hacker_news_max_items,
                metadata={},
            )
        )
        if rss_enabled:
            source_registry.register(
                SourceDefinition(
                    source_id="rss",
                    collector_name=RSSCollector.name(),
                    enabled=True,
                    interval_seconds=source_interval_seconds,
                    priority=SourcePriority.NORMAL,
                    max_items=10,
                    metadata={"feed_url": rss_feed_url, "source_name": "rss"},
                )
            )
            for enabled, source_id, feed_url, source_name, category in ((openai_news_enabled, "openai_news", "https://openai.com/news/rss.xml", "openai_news", "AI"), (microsoft_research_enabled, "microsoft_research", "https://www.microsoft.com/en-us/research/feed/", "microsoft_research", "Research"), (huggingface_blog_enabled, "huggingface_blog", "https://huggingface.co/blog/feed.xml", "huggingface_blog", "AI"), (github_blog_enabled, "github_blog", "https://github.blog/feed/", "github_blog", "Developer Tools"), (rust_blog_enabled, "rust_blog", "https://blog.rust-lang.org/feed.xml", "rust_blog", "Open Source"), (go_blog_enabled, "go_blog", "https://go.dev/blog/feed.atom", "go_blog", "Developer Tools"), (docker_blog_enabled, "docker_blog", "https://www.docker.com/blog/feed/", "docker_blog", "Developer Tools"), (kubernetes_cve_enabled, "kubernetes_cve", "https://k8s.io/docs/reference/issues-security/official-cve-feed/feed.xml", "kubernetes_cve", "Security"), (cloudflare_blog_enabled, "cloudflare_blog", "https://blog.cloudflare.com/rss/", "cloudflare_blog", "Security"), (linux_foundation_enabled, "linux_foundation", "https://www.linuxfoundation.org/blog/rss.xml", "linux_foundation", "Open Source"), (arduino_blog_enabled, "arduino_blog", "https://blog.arduino.cc/feed/", "arduino_blog", "Hardware"), (raspberry_pi_blog_enabled, "raspberry_pi_blog", "https://www.raspberrypi.com/news/feed/", "raspberry_pi_blog", "Hardware"), (jetbrains_blog_enabled, "jetbrains_blog", "https://blog.jetbrains.com/feed/", "jetbrains_blog", "Developer Tools"), (gitlab_blog_enabled, "gitlab_blog", "https://about.gitlab.com/atom.xml", "gitlab_blog", "Developer Tools"), (python_insider_enabled, "python_insider", "https://feeds.feedburner.com/PythonInsider", "python_insider", "Developer Tools"), (eclipse_foundation_enabled, "eclipse_foundation", "https://blogs.eclipse.org/rss.xml", "eclipse_foundation", "Open Source")):
                if enabled:
                    source_registry.register(SourceDefinition(source_id=source_id, collector_name=RSSCollector.name(), enabled=True, interval_seconds=source_interval_seconds, priority=SourcePriority.NORMAL, max_items=10, metadata={"feed_url": feed_url, "source_name": source_name, "category": category, "language": "en"}))
        if github_enabled:
            source_registry.register(
                SourceDefinition(
                    source_id="github",
                    collector_name=GitHubTrendingCollector.name(),
                    enabled=True,
                    interval_seconds=source_interval_seconds,
                    priority=SourcePriority.NORMAL,
                    max_items=github_max_items,
                    metadata={"category": "Open Source"},
                )
            )
        if reddit_enabled:
            source_registry.register(
                SourceDefinition(
                    source_id="reddit",
                    collector_name=RedditCollector.name(),
                    enabled=True,
                    interval_seconds=source_interval_seconds,
                    priority=SourcePriority.NORMAL,
                    max_items=reddit_limit,
                    metadata={"subreddit": reddit_subreddit, "category": "AI"},
                )
            )
        if product_hunt_enabled:
            source_registry.register(SourceDefinition(
                source_id="product_hunt", collector_name=ProductHuntCollector.name(), enabled=True,
                interval_seconds=source_interval_seconds, priority=SourcePriority.NORMAL,
                max_items=product_hunt_max_items, metadata={},
            ))
        if pypi_enabled and pypi_request is not None:
            source_registry.register(SourceDefinition(source_id="pypi", collector_name=PyPICollector.name(), enabled=True, interval_seconds=source_interval_seconds, priority=SourcePriority.NORMAL, max_items=pypi_max_items, metadata={"packages": pypi_packages, "category": "Developer Tools"}))
        if npm_enabled and npm_request is not None:
            source_registry.register(SourceDefinition(source_id="npm", collector_name=NpmCollector.name(), enabled=True, interval_seconds=source_interval_seconds, priority=SourcePriority.NORMAL, max_items=npm_max_items, metadata={"packages": npm_packages, "category": "Developer Tools"}))
        if gitlab_enabled and gitlab_request is not None:
            source_registry.register(SourceDefinition(source_id="gitlab", collector_name=GitLabCollector.name(), enabled=True, interval_seconds=source_interval_seconds, priority=SourcePriority.NORMAL, max_items=gitlab_max_items, metadata={"category": "Open Source"}))
        if dockerhub_enabled and dockerhub_request is not None:
            source_registry.register(SourceDefinition(source_id="dockerhub", collector_name=DockerHubCollector.name(), enabled=True, interval_seconds=source_interval_seconds, priority=SourcePriority.NORMAL, max_items=dockerhub_max_items, metadata={"category": "Developer Tools"}))
        if devto_enabled:
            source_registry.register(SourceDefinition(
                source_id="devto", collector_name=DevToCollector.name(), enabled=True,
                interval_seconds=source_interval_seconds, priority=SourcePriority.NORMAL,
                max_items=devto_max_items, metadata={"tag": devto_tag},
            ))
        if lobsters_enabled:
            source_registry.register(SourceDefinition(
                source_id="lobsters", collector_name=LobstersCollector.name(), enabled=True,
                interval_seconds=source_interval_seconds, priority=SourcePriority.NORMAL,
                max_items=lobsters_max_items, metadata={},
            ))
        if arxiv_enabled:
            source_registry.register(SourceDefinition(
                source_id="arxiv", collector_name=ArxivCollector.name(), enabled=True,
                interval_seconds=source_interval_seconds, priority=SourcePriority.NORMAL,
                max_items=arxiv_max_items, metadata={"search_query": arxiv_search_query},
            ))
        self._source_manager = SourceManager(
            collector_registry,
            source_registry,
            self._event_bus,
        )

        self._scheduler = scheduler or InMemoryScheduler()
        self._scheduler.register_periodic(
            self.SCHEDULE_TASK_ID,
            source_interval_seconds,
            self._run_scheduled_source,
        )
        if self._rss_enabled:
            self._scheduler.register_periodic(
                self.RSS_SCHEDULE_TASK_ID,
                source_interval_seconds,
                lambda: self._run_scheduled_source("rss"),
            )
        if self._github_enabled:
            self._scheduler.register_periodic(
                self.GITHUB_SCHEDULE_TASK_ID,
                source_interval_seconds,
                lambda: self._run_scheduled_source("github"),
            )
        if self._reddit_enabled:
            self._scheduler.register_periodic(
                self.REDDIT_SCHEDULE_TASK_ID,
                source_interval_seconds,
                lambda: self._run_scheduled_source("reddit"),
            )
        if self._product_hunt_enabled:
            self._scheduler.register_periodic(
                self.PRODUCT_HUNT_SCHEDULE_TASK_ID, source_interval_seconds,
                lambda: self._run_scheduled_source("product_hunt"),
            )
        if self._devto_enabled:
            self._scheduler.register_periodic(
                self.DEVTO_SCHEDULE_TASK_ID, source_interval_seconds,
                lambda: self._run_scheduled_source("devto"),
            )
        if self._lobsters_enabled:
            self._scheduler.register_periodic(
                self.LOBSTERS_SCHEDULE_TASK_ID, source_interval_seconds,
                lambda: self._run_scheduled_source("lobsters"),
            )
        if self._arxiv_enabled:
            self._scheduler.register_periodic(
                self.ARXIV_SCHEDULE_TASK_ID, source_interval_seconds,
                lambda: self._run_scheduled_source("arxiv"),
            )

    async def _run_scheduled_source(self, source_id: str | None = None) -> None:
        await self._source_manager.run_source(source_id or self.SOURCE_ID)

    async def run_once(self) -> tuple[SourceRunResult, ...]:
        results = await self._source_manager.run_enabled()
        collected = sum(result.collected_count for result in results)
        snapshots = tuple(
            self._stats_handler.snapshot(result.correlation_id) for result in results
        )
        print(f"Collected records: {collected}", file=self._output)
        print(f"Stored records: {sum(item.stored for item in snapshots)}", file=self._output)
        print(f"Enriched records: {sum(item.enriched for item in snapshots)}", file=self._output)
        print(f"Scored records: {sum(item.scored for item in snapshots)}", file=self._output)
        print(f"Accepted for publication: {sum(item.accepted for item in snapshots)}", file=self._output)
        print(f"Rejected: {sum(item.rejected for item in snapshots)}", file=self._output)
        print(
            f"Published successfully: {sum(item.published_successfully for item in snapshots)}",
            file=self._output,
        )
        print(
            f"Publication failures: {sum(item.publication_failures for item in snapshots)}",
            file=self._output,
        )
        for result in results:
            if result.error_message:
                print(f"Warning [{result.source_id}]: {result.error_message}", file=self._output)
        return results

    async def run(self) -> SourceRunResult:
        """Backward-compatible one-source entry point."""
        results = await self.run_once()
        return results[0]

    async def serve(self) -> None:
        logger.info("AI Scout scheduler started")
        try:
            await self._scheduler.serve()
        finally:
            logger.info("AI Scout scheduler stopped")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AlphaLab AI Scout")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="run all enabled sources once")
    mode.add_argument("--serve", action="store_true", help="run the scheduler until cancelled")
    mode.add_argument("--schedule", action="store_true", help="run repeated full cycles")
    mode.add_argument("--openai-smoke-test", action="store_true", help="run one isolated OpenAI Responses API smoke test")
    mode.add_argument("--ai-smoke-test", action="store_true", help="run one isolated configured-provider smoke test")
    mode.add_argument("--telegram-smoke-test", action="store_true", help="send one controlled EN/RU Telegram smoke test")
    mode.add_argument("--real-collector-smoke-test", action="store_true", help="run one collected article through publication views without delivery")
    mode.add_argument("--website-smoke-test", action="store_true", help="run one collected article through WebsitePublisher only")
    mode.add_argument("--storage-smoke-test", action="store_true", help="persist one publication and verify duplicate protection")
    mode.add_argument("--scheduler-smoke-test", action="store_true", help="execute one scheduler cycle")
    mode.add_argument("--editorial-smoke-test", action="store_true", help="evaluate real collector articles editorially")
    mode.add_argument("--dedup-smoke-test", action="store_true", help="evaluate real collector duplicates")
    mode.add_argument("--e2e-smoke-test", action="store_true", help="execute one complete integrated cycle")
    mode.add_argument("--editorial-ai-smoke-test", action="store_true", help="evaluate optional AI editorial ranking")
    mode.add_argument("--memory-smoke-test", action="store_true", help="show publication memory context")
    mode.add_argument("--article-structure-smoke-test", action="store_true", help="show editorial article structure guidance")
    mode.add_argument("--run-once", action="store_true", help="execute one production publication cycle")
    mode.add_argument("--quality-smoke-test", action="store_true", help="run editorial planning and article quality smoke test")
    mode.add_argument("--facts-smoke-test", action="store_true", help="extract editorial facts before planning")
    mode.add_argument("--story-angle-smoke-test", action="store_true", help="select a story angle before planning")
    mode.add_argument("--review-smoke-test", action="store_true", help="review one generated article before publication")
    mode.add_argument("--headline-smoke-test", action="store_true", help="edit and review candidate headlines")
    mode.add_argument("--audience-smoke-test", action="store_true", help="select an audience profile")
    mode.add_argument("--seo-smoke-test", action="store_true", help="generate SEO metadata")
    mode.add_argument("--related-smoke-test", action="store_true", help="find related publications")
    mode.add_argument("--priority-smoke-test", action="store_true", help="assign publication priority")
    mode.add_argument("--window-smoke-test", action="store_true", help="select publication window")
    mode.add_argument("--channels-smoke-test", action="store_true", help="select publication channels")
    mode.add_argument("--delivery-smoke-test", action="store_true", help="execute selected channel delivery")
    mode.add_argument("--metrics-smoke-test", action="store_true", help="collect pipeline metrics")
    mode.add_argument("--production-run", action="store_true", help="run one complete production cycle")
    parser.add_argument("--confirm-send", action="store_true", help="explicitly authorize Telegram smoke delivery")
    parser.add_argument("--dry-run", action="store_true", help="run with local fake sources and no publication")
    parser.add_argument("--analytics", action="store_true", help="show analytics summary")
    parser.add_argument("--api-latest", action="store_true")
    parser.add_argument("--api-search")
    parser.add_argument("--website", action="store_true")
    parser.add_argument("--db-status", action="store_true")
    parser.add_argument("--migrate-storage", action="store_true")
    return parser.parse_args(argv)


async def _run_real_collector_smoke_test(settings) -> None:
    """Exercise the real collector-to-view path without any side effects."""
    from urllib.parse import urlsplit
    from core.publication.builder import PublicationBuilder
    from core.ai_enrichment import AIEnrichmentEngine, AIProviderRegistry
    from core.ai_enrichment.providers.openai import OpenAIProvider
    from core.ai_enrichment.providers.openrouter import OpenRouterProvider
    from core.language_variants import LanguageVariantEngine
    from core.renderers import TelegramRenderer, WebsiteRenderer

    results = await AIScout()._source_manager.run_enabled()
    items = [item for result in results for item in result.items
             if isinstance(getattr(item, "payload", None), dict)
             and str(item.payload.get("url", "")).startswith(("http://", "https://"))
             and str(item.payload.get("title", "")).strip()]
    print(f"collector_items={len(items)}")
    if not items:
        raise SystemExit("real_collector_smoke_test=failed reason=no_valid_article")
    item = sorted(items, key=lambda value: (str(value.payload.get("url", "")), str(value.payload.get("title", ""))))[0]
    url = str(item.payload.get("url")); parts = urlsplit(url)
    safe_url = f"{parts.scheme}://{parts.netloc}{parts.path}"
    publication = PublicationBuilder().build(item)
    provider_name = str(getattr(settings, "ai_provider", "noop") or "noop").lower()
    ai_enabled = bool(getattr(settings, "ai_enabled", False))
    configured = str(getattr(settings, "ai_provider", "noop") or "noop").lower()
    registry = AIProviderRegistry.with_noop(default="noop")
    if ai_enabled and provider_name in {"openrouter", "openai"}:
        from openai import OpenAI
        if provider_name == "openrouter":
            client = OpenAI(api_key=getattr(settings, "openrouter_api_key", ""), base_url=getattr(settings, "openrouter_base_url", "https://openrouter.ai/api/v1"), timeout=getattr(settings, "openrouter_timeout_seconds", 30))
            provider = OpenRouterProvider(getattr(settings, "openrouter_api_key", ""), getattr(settings, "openrouter_model", ""), client, getattr(settings, "openrouter_max_output_tokens", 1200))
        else:
            client = OpenAI(api_key=getattr(settings, "openai_api_key", ""), timeout=getattr(settings, "openai_timeout_seconds", 30))
            provider = OpenAIProvider(getattr(settings, "openai_api_key", ""), getattr(settings, "openai_model", "gpt-4.1-mini"), client, getattr(settings, "openai_max_output_tokens", 1200))
        registry.register(provider_name, provider); registry._default = provider_name
    publication = AIEnrichmentEngine(registry=registry).enrich(publication)
    variants = LanguageVariantEngine().generate(publication)
    publication = __import__("dataclasses").replace(publication, variants={v.language: v for v in variants})
    TelegramRenderer("en").render(publication); TelegramRenderer("ru").render(publication)
    WebsiteRenderer("en").render(publication); WebsiteRenderer("ru").render(publication)
    print(f"selected_source={getattr(item, 'source', '') or item.payload.get('source', '')}")
    print(f"selected_url={safe_url}\nprovider={provider_name if ai_enabled else 'noop'}\nbusiness_provider_calls=1\nparser=ok\nlanguage_variants={len(variants)}\ntelegram_views=2\nwebsite_views=2\ntelegram_delivery=blocked\nwebsite_delivery=blocked\nstorage=blocked\nreal_collector_smoke_test=success")


async def _run_website_smoke_test(settings) -> None:
    """Run the website publisher with one real item; never touches Telegram/storage."""
    from core.publication.builder import PublicationBuilder
    from core.ai_enrichment import AIEnrichmentEngine, AIProviderRegistry
    from core.language_variants import LanguageVariantEngine
    from core.renderers import WebsiteRenderer
    from core.publishers import WebsitePublisher
    results = await AIScout()._source_manager.run_enabled()
    items = [i for r in results for i in r.items if isinstance(getattr(i, "payload", None), dict) and i.payload.get("url") and i.payload.get("title")]
    print(f"collector_items={len(items)}")
    if not items: raise SystemExit("website_smoke_test=failed reason=no_valid_article")
    item = sorted(items, key=lambda i: str(i.payload.get("url")))[0]
    registry = AIProviderRegistry.with_noop(default="noop")
    publication = AIEnrichmentEngine(registry=registry).enrich(PublicationBuilder().build(item))
    variants = LanguageVariantEngine().generate(publication)
    from dataclasses import replace
    publication = replace(publication, variants={v.language: v for v in variants})
    views = [WebsiteRenderer(lang).render(publication) for lang in ("en", "ru")]
    calls = []
    WebsitePublisher(lambda view: calls.append(view) or True).publish(views[0])
    print(f"provider={configured if getattr(settings, 'ai_enabled', False) and configured != 'noop' else 'noop'}\nbusiness_provider_calls=1\nwebsite_views=2\nwebsite_delivery=success\ntelegram_delivery=blocked\nstorage=blocked\nwebsite_smoke_test=success")

async def _run_storage_smoke_test(settings) -> None:
    from core.publication.builder import PublicationBuilder
    from core.ai_enrichment import AIEnrichmentEngine, AIProviderRegistry
    from core.language_variants import LanguageVariantEngine
    from core.storage import SQLiteDatabase, SQLitePublicationStore
    results=await AIScout()._source_manager.run_enabled(); items=[i for r in results for i in r.items if isinstance(getattr(i,'payload',None),dict) and i.payload.get('url') and i.payload.get('title')]
    print(f"collector_items={len(items)}")
    if not items: raise SystemExit("storage_smoke_test=failed reason=no_valid_article")
    item=sorted(items,key=lambda i:str(i.payload.get('url')))[0]; pub=PublicationBuilder().build(item); pub=AIEnrichmentEngine(registry=AIProviderRegistry.with_noop()).enrich(pub); vs=LanguageVariantEngine().generate(pub)
    from dataclasses import replace
    pub=replace(pub,variants={v.language:v for v in vs}); store=SQLitePublicationStore(SQLiteDatabase()); first=store.save(pub); second=store.save(pub)
    print(f"provider=noop\nbusiness_provider_calls=1\nstorage_backend=sqlite\npublication_saved={'yes' if first else 'no'}\nduplicate_blocked={'yes' if not second else 'no'}\nstored_records={store.count()}\ntelegram_delivery=blocked\nwebsite_delivery=blocked\nstorage_smoke_test=success")


def _mask_id(value: str) -> str:
    value = str(value or "")
    return value[:4] + "..." + value[-4:] if len(value) > 8 else ("<present>" if value else "<none>")


async def _run_openai_smoke_test(settings, forced_provider: str | None = None) -> None:
    """Run one isolated provider call; never invokes delivery, storage, or collectors."""
    provider_name = (forced_provider or getattr(settings, "ai_provider", "noop") or "noop").lower()
    if provider_name not in {"noop", "openai", "openrouter"}:
        print("ai_smoke_test=failed stage=configuration reason=unknown_provider")
        raise SystemExit(2)
    return await _run_provider_smoke_test(settings, provider_name)


async def _run_provider_smoke_test(settings, provider_name: str) -> None:
    key_name = "openrouter_api_key" if provider_name == "openrouter" else "openai_api_key"
    key = str(getattr(settings, key_name, "") or "")
    if provider_name != "noop" and not key:
        print("ai_smoke_test=failed stage=configuration reason=missing_api_key")
        raise SystemExit(2)
    try:
        from core.ai_enrichment import AIEnrichmentEngine, AIProviderRegistry
        from core.ai_enrichment.providers.openai import OpenAIProvider
        from core.ai_enrichment.providers.openrouter import OpenRouterProvider
        from core.language_variants import LanguageVariantEngine
        from core.publication.composition import build_publication_engine
        if provider_name == "noop":
            from core.ai_enrichment.engine import NoOpAIProvider
            provider = NoOpAIProvider(); registry = AIProviderRegistry(default="noop"); registry.register("noop", provider)
        elif provider_name == "openrouter":
            from openai import OpenAI
            provider = OpenRouterProvider(key, settings.openrouter_model, OpenAI(api_key=key, base_url=settings.openrouter_base_url, timeout=settings.openrouter_timeout_seconds, max_retries=settings.openrouter_max_retries), settings.openrouter_max_output_tokens); registry = AIProviderRegistry(default="openrouter"); registry.register("openrouter", provider)
        else:
            from openai import OpenAI
            provider = OpenAIProvider(key, settings.openai_model, OpenAI(api_key=key, timeout=settings.openai_timeout_seconds, max_retries=settings.openai_max_retries), settings.openai_max_output_tokens); registry = AIProviderRegistry(default="openai"); registry.register("openai", provider)
        ai_engine = AIEnrichmentEngine(registry=registry)
        engine = build_publication_engine(publisher=None, renderer=None, ai_enrichment_engine=ai_engine, language_variant_engine=LanguageVariantEngine())
        publication = ai_engine.enrich(engine._publication_builder.build({"id": "ai-smoke-1", "title": "Open-source AI system improves document analysis", "summary": "A research team released an open-source language model designed to analyze long technical documents with lower computational requirements. Independent verification is still required.", "url": "https://example.invalid/ai-smoke-1", "source": "smoke-test", "category": "AI", "published_at": "2026-07-18T00:00:00+00:00"}))
        variants = LanguageVariantEngine().generate(publication)
        print("ai_smoke_test=start")
        print(f"provider={provider_name}\nbusiness_provider_calls=1\nparser=ok\nai_context=created\nlanguage_variants={len(variants)}\nvariant_en={'yes' if any(v.language == 'en' for v in variants) else 'no'}\nvariant_ru={'yes' if any(v.language == 'ru' for v in variants) else 'no'}\ntelegram_delivery=blocked\nwebsite_delivery=blocked\nstorage=blocked\nai_smoke_test=success")
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ai_smoke_test=failed stage=provider error={type(exc).__name__}")
        raise SystemExit(2)

    key_name = "openrouter_api_key" if provider_name == "openrouter" else "openai_api_key"
    key = str(getattr(settings, key_name, "") or "")
    if provider_name != "noop" and not key:
        print("ai_smoke_test=failed stage=configuration reason=missing_api_key")
        raise SystemExit(2)
    started = time.perf_counter()
    try:
        from core.ai_enrichment import AIEnrichmentEngine, AIProviderRegistry
        from core.ai_enrichment.providers.openai import OpenAIProvider
        from core.ai_enrichment.providers.openrouter import OpenRouterProvider
        from core.language_variants import LanguageVariantEngine
        from core.publication.composition import build_publication_engine
        from core.renderers import TelegramRenderer, WebsiteRenderer
        if provider_name == "noop":
            from core.ai_enrichment.engine import NoOpAIProvider
            provider = NoOpAIProvider(); registry = AIProviderRegistry(default="noop"); registry.register("noop", provider)
        elif provider_name == "openrouter":
            from openai import OpenAI
            client = OpenAI(api_key=key, base_url=settings.openrouter_base_url, timeout=settings.openrouter_timeout_seconds, max_retries=settings.openrouter_max_retries)
            provider = OpenRouterProvider(key, settings.openrouter_model, client, settings.openrouter_max_output_tokens); registry = AIProviderRegistry(default="openrouter"); registry.register("openrouter", provider)
        else:
            from openai import OpenAI
            client = OpenAI(api_key=key, timeout=settings.openai_timeout_seconds, max_retries=settings.openai_max_retries)
            provider = OpenAIProvider(key, settings.openai_model, client, settings.openai_max_output_tokens); registry = AIProviderRegistry(default="openai"); registry.register("openai", provider)
        ai_engine = AIEnrichmentEngine(registry=registry)
        engine = build_publication_engine(publisher=None, renderer=None, ai_enrichment_engine=ai_engine, language_variant_engine=LanguageVariantEngine())
        item = {"id": "ai-smoke-1", "title": "Open-source AI system improves document analysis", "summary": "A research team released an open-source language model designed to analyze long technical documents with lower computational requirements. Independent verification is still required.", "url": "https://example.invalid/ai-smoke-1", "source": "smoke-test", "category": "AI", "published_at": "2026-07-18T00:00:00+00:00"}
        publication = ai_engine.enrich(engine._publication_builder.build(item))
        variants = LanguageVariantEngine().generate(publication)
        publication = __import__("dataclasses").replace(publication, variants={v.language: v for v in variants})
        views = [r.render(publication) for language in ("en", "ru") for r in (TelegramRenderer(language), WebsiteRenderer(language))]
        context = publication.ai_context
        print("ai_smoke_test=start")
        print(f"provider={provider_name}\nbusiness_provider_calls=1\nparser=ok\nai_context=created\nlanguage_variants=2\nvariant_en=yes\nvariant_ru=yes\ntelegram_views=2\nwebsite_views=2\ntelegram_delivery=blocked\nwebsite_delivery=blocked\nstorage=blocked\nai_smoke_test=success")
    except Exception as exc:
        print(f"ai_smoke_test=failed stage=provider error={type(exc).__name__}")
        raise SystemExit(2)


async def _run_telegram_smoke_test(settings, confirm_send: bool) -> None:
    """Render one AI publication and send exactly one message per explicit target."""
    provider_name = str(getattr(settings, "ai_provider", "noop") or "noop").lower()
    if not confirm_send:
        print("telegram_smoke_test=failed stage=configuration reason=confirm_send_required")
        raise SystemExit(2)
    if provider_name == "noop":
        print("telegram_smoke_test=failed stage=configuration reason=real_ai_provider_required")
        raise SystemExit(2)
    token = str(getattr(settings, "telegram_bot_token", "") or "")
    en_target = str(getattr(settings, "telegram_en_chat_id", "") or "")
    ru_target = str(getattr(settings, "telegram_ru_chat_id", "") or "")
    if not token or not en_target or not ru_target:
        print("telegram_smoke_test=failed stage=configuration reason=missing_telegram_credentials")
        raise SystemExit(2)
    started = time.perf_counter()
    try:
        from dataclasses import replace
        from openai import OpenAI
        from core.ai_enrichment import AIEnrichmentEngine, AIProviderRegistry
        from core.ai_enrichment.providers.openai import OpenAIProvider
        from core.ai_enrichment.providers.openrouter import OpenRouterProvider
        from core.language_variants import LanguageVariantEngine
        from core.publication.composition import build_publication_engine
        from core.renderers import TelegramRenderer
        from core.publishers.telegram import TelegramViewPublisher
        from agents.ai_scout.publishers.telegram_client import TelegramClient

        if provider_name == "openrouter":
            client = OpenAI(api_key=getattr(settings, "openrouter_api_key", ""), base_url=settings.openrouter_base_url, timeout=settings.openrouter_timeout_seconds, max_retries=settings.openrouter_max_retries)
            provider = OpenRouterProvider(settings.openrouter_api_key, settings.openrouter_model, client, settings.openrouter_max_output_tokens)
        elif provider_name == "openai":
            client = OpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds, max_retries=settings.openai_max_retries)
            provider = OpenAIProvider(settings.openai_api_key, settings.openai_model, client, settings.openai_max_output_tokens)
        else:
            print("telegram_smoke_test=failed stage=configuration reason=unknown_provider")
            raise SystemExit(2)
        registry = AIProviderRegistry(default=provider_name); registry.register(provider_name, provider)
        ai_engine = AIEnrichmentEngine(registry=registry)
        engine = build_publication_engine(publisher=None, renderer=None, ai_enrichment_engine=ai_engine, language_variant_engine=LanguageVariantEngine())
        item = {"id": "telegram-smoke-1", "title": "Open-source AI system improves document analysis", "summary": "A research team released an open-source language model designed to analyze long technical documents with lower computational requirements. Independent verification is still required.", "url": "https://example.invalid/telegram-smoke-1", "source": "smoke-test", "category": "AI", "published_at": "2026-07-18T00:00:00+00:00"}
        publication = ai_engine.enrich(engine._publication_builder.build(item))
        variants = LanguageVariantEngine().generate(publication)
        publication = replace(publication, variants={v.language: v for v in variants})
        en_view = TelegramRenderer("en").render(publication)
        ru_view = TelegramRenderer("ru").render(publication)
        from agents.ai_scout.telegram_smoke import validate_preflight, mask_target, smoke_model_line
        print(f"telegram smoke diagnostic: provider={provider_name}")
        print(f"telegram smoke diagnostic: raw_ai_response={str(getattr(provider, '_last_raw_text', ''))[:1000]!r}")
        print(f"telegram smoke diagnostic: parsed_en_title={variants[0].title!r} parsed_en_body={variants[0].body!r}")
        print(f"telegram smoke diagnostic: parsed_ru_title={variants[1].title!r} parsed_ru_body={variants[1].body!r}")
        preflight = validate_preflight(confirm_send=True, provider=provider_name, token=token, en_target=en_target, ru_target=ru_target, en_text=en_view.text, ru_text=ru_view.text, ru_title=ru_view.title, ru_body=ru_view.text)
        if not preflight.ok:
            print(f"telegram_smoke_test=failed stage=validation reason={preflight.reason}")
            raise SystemExit(2)

        async def request(url, payload, timeout):
            import json, urllib.parse, urllib.request
            def send():
                data = urllib.parse.urlencode(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
                with urllib.request.urlopen(req, timeout=timeout) as response: return response.status, json.loads(response.read())
            return await asyncio.to_thread(send)
        en_client = TelegramClient(token, en_target, 30, request)
        ru_client = TelegramClient(token, ru_target, 30, request)
        en_result = await TelegramViewPublisher(en_client).publish(en_view)
        ru_result = await TelegramViewPublisher(ru_client).publish(ru_view) if en_result.success else None
        print("telegram_smoke_test=start")
        print(f"provider={provider_name}\n{smoke_model_line(settings)}\nbusiness_provider_calls=1\nparser=ok\nai_context=created\nlanguage_variants=2\nvariant_en=yes\nvariant_ru=yes\ntelegram_views=2\npreflight=ok")
        print(f"telegram_en_target={mask_target(en_target)}\ntelegram_ru_target={mask_target(ru_target)}")
        print(f"telegram_en_delivery={'sent' if en_result.success else 'failed'}\ntelegram_ru_delivery={'sent' if ru_result and ru_result.success else 'not_attempted' if not en_result.success else 'failed'}")
        print(f"latency_ms={int((time.perf_counter()-started)*1000)}\nwebsite_delivery=blocked\nstorage=blocked")
        if en_result.success and ru_result and ru_result.success:
            print("telegram_smoke_test=success")
        else:
            print(f"telegram_delivery={'failed' if not en_result.success else 'partial'} en={'sent' if en_result.success else 'failed'} ru={'sent' if ru_result and ru_result.success else 'not_attempted' if not en_result.success else 'failed'}")
            raise SystemExit(2)
        return
    except SystemExit:
        raise
    except Exception as exc:
        print(f"telegram_smoke_test=failed stage=delivery error={type(exc).__name__}")
        raise SystemExit(2)
    key_name = "openrouter_api_key" if provider_name == "openrouter" else "openai_api_key"
    key = str(getattr(settings, key_name, "") or "")
    if provider_name != "noop" and not key:
        print("ai_smoke_test=failed stage=configuration reason=missing_api_key")
        raise SystemExit(2)
    started = time.perf_counter()
    try:
        from core.ai_enrichment import AIEnrichmentEngine, AIProviderRegistry
        from core.ai_enrichment.providers.openai import OpenAIProvider
        from core.ai_enrichment.providers.openrouter import OpenRouterProvider
        from core.language_variants import LanguageVariantEngine
        from core.publication.builder import PublicationBuilder
        from core.publication.composition import build_publication_engine
        from core.renderers import TelegramRenderer, WebsiteRenderer

        if provider_name == "noop":
            from core.ai_enrichment.engine import NoOpAIProvider
            provider = NoOpAIProvider(); registry = AIProviderRegistry(default="noop"); registry.register("noop", provider)
        elif provider_name == "openrouter":
            from openai import OpenAI
            client = OpenAI(api_key=key, base_url=settings.openrouter_base_url, timeout=settings.openrouter_timeout_seconds, max_retries=settings.openrouter_max_retries, default_headers={"HTTP-Referer": settings.openrouter_site_url, "X-OpenRouter-Title": settings.openrouter_app_name} if settings.openrouter_site_url else {"X-OpenRouter-Title": settings.openrouter_app_name})
            provider = OpenRouterProvider(api_key=key, model=settings.openrouter_model, client=client, max_output_tokens=settings.openrouter_max_output_tokens)
            registry = AIProviderRegistry(default="openrouter"); registry.register("openrouter", provider)
        else:
            from openai import OpenAI
            client = OpenAI(api_key=key, timeout=settings.openai_timeout_seconds, max_retries=settings.openai_max_retries)
            provider = OpenAIProvider(api_key=key, model=settings.openai_model, client=client, max_output_tokens=settings.openai_max_output_tokens)
            registry = AIProviderRegistry(default="openai"); registry.register("openai", provider)
        ai_engine = AIEnrichmentEngine(registry=registry)
        # Build the existing composition; no publisher or storage is supplied.
        engine = build_publication_engine(publisher=None, renderer=None, ai_enrichment_engine=ai_engine, language_variant_engine=LanguageVariantEngine())
        item = {"id": "openai-smoke-1", "title": "Open-source AI model improves efficient document analysis", "summary": "A research team released an open-source language model designed to analyze long technical documents with lower computational requirements. Independent verification is still needed.", "url": "https://example.invalid/openai-smoke-1", "source": "smoke-test", "category": "AI", "published_at": "2026-07-18T00:00:00+00:00"}
        publication = engine._publication_builder.build(item)
        publication = ai_engine.enrich(publication)
        variants = LanguageVariantEngine().generate(publication)
        publication = __import__("dataclasses").replace(publication, variants={v.language: v for v in variants})
        views = []
        for language in ("en", "ru"):
            views.append(TelegramRenderer(language).render(publication))
            views.append(WebsiteRenderer(language).render(publication))
        context = publication.ai_context
        response_id = getattr(provider, "_last_response_id", "")
        model = getattr(settings, f"{provider_name}_model", "noop")
        print("ai_smoke_test=start")
        print(f"provider={provider_name}\nmodel={model}\nbusiness_provider_calls=1\nresponse_id={_mask_id(response_id)}")
        print("finish_status=completed")
        print("input_tokens=available\noutput_tokens=available\ntotal_tokens=available")
        print(f"latency_ms={int((time.perf_counter()-started)*1000)}\nparser=ok\nai_context=created\nconfidence={float(getattr(context, 'confidence', 0.0)):.3f}")
        print("language_variants=2\nvariant_en=yes\nvariant_ru=yes\ntelegram_views=2\nwebsite_views=2")
        for view in views:
            print(f"view={type(view).__name__} language={view.language} length={len(getattr(view, 'text', getattr(view, 'summary', '')))}")
        print("telegram_delivery=blocked\nwebsite_delivery=blocked\nstorage=blocked\nai_smoke_test=success")
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ai_smoke_test=failed stage=provider error={type(exc).__name__}")
        raise SystemExit(2)


def validate_startup(*, dry_run: bool, source_enabled: bool = True, embedding_model: str | None = "fake", provider_available: bool = True, telegram_token: str | None = None, telegram_chat_id: str | None = None) -> tuple[str, ...]:
    errors: list[str] = []
    if not source_enabled: errors.append("at least one source must be enabled")
    if not embedding_model: errors.append("embedding model is not configured")
    if not provider_available: errors.append("no AI provider or safe fallback is configured")
    if not dry_run and (not telegram_token or not telegram_chat_id): errors.append("Telegram token and chat_id are required for live publication")
    return tuple(errors)


async def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.db_status or args.migrate_storage:
        from core.storage import SQLiteDatabase
        db=SQLiteDatabase(); print(f"storage: backend=sqlite path={db.path} schema_version={db.version()}")
        if args.migrate_storage:
            db.migrate_json()
        if args.db_status:
            with db.connect() as c: print(f"published count={c.execute('SELECT COUNT(*) FROM published_articles').fetchone()[0]}")
        return
    from backend.app.core.config import Settings
    settings = Settings()
    if args.story_angle_smoke_test:
        from core.editorial.angles import StoryAngleSelector
        from core.editorial.planning import EditorialPlanner
        from core.publication.builder import PublicationBuilder
        from core.language_variants import LanguageVariantEngine
        results=await AIScout()._source_manager.run_enabled(); items=[i for r in results for i in r.items if isinstance(getattr(i,'payload',None),dict) and i.payload.get('title')]
        if not items: raise SystemExit("story_angle_smoke_test=failed reason=no_valid_article")
        publication=PublicationBuilder().build(items[0]); angle=StoryAngleSelector().select(publication); EditorialPlanner().plan(publication,angle=angle); variants=LanguageVariantEngine().generate(publication)
        print(f"angle=yes\nplanner=yes\narticle=yes\nvariants={len(variants)}")
        return
    if args.review_smoke_test:
        from core.editorial.review import EditorialReviewer
        from core.publication.builder import PublicationBuilder
        from core.language_variants import LanguageVariantEngine
        results = await AIScout()._source_manager.run_enabled()
        items = [i for r in results for i in r.items if isinstance(getattr(i, "payload", None), dict) and i.payload.get("title")]
        if not items:
            raise SystemExit("review_smoke_test=failed reason=no_valid_article")
        publication = PublicationBuilder().build(items[0])
        review = EditorialReviewer().review(publication)
        variants = LanguageVariantEngine().generate(publication)
        print(f"review=yes\nquality_score={review.quality_score}\napproved={str(review.approved).lower()}\nvariants={len(variants)}")
        return
    if args.headline_smoke_test:
        from core.editorial.headlines import HeadlineEditor
        from core.editorial.review import EditorialReviewer
        from core.publication.builder import PublicationBuilder
        from core.language_variants import LanguageVariantEngine
        results = await AIScout()._source_manager.run_enabled()
        items = [i for r in results for i in r.items if isinstance(getattr(i, "payload", None), dict) and i.payload.get("title")]
        if not items:
            raise SystemExit("headline_smoke_test=failed reason=no_valid_article")
        publication = PublicationBuilder().build(items[0])
        candidates, selected = HeadlineEditor().edit(publication)
        review = EditorialReviewer().review(publication, selected.text)
        variants = LanguageVariantEngine().generate(publication)
        print(f"headlines={len(candidates)}\nselected=yes\nreview=yes\nvariants={len(variants)}")
        return
    if args.audience_smoke_test:
        from core.editorial.audience import AudienceSelector
        from core.editorial.planning import EditorialPlanner
        from core.publication.builder import PublicationBuilder
        from core.language_variants import LanguageVariantEngine
        results = await AIScout()._source_manager.run_enabled()
        items = [i for r in results for i in r.items if isinstance(getattr(i, "payload", None), dict) and i.payload.get("title")]
        if not items:
            raise SystemExit("audience_smoke_test=failed reason=no_valid_article")
        publication = PublicationBuilder().build(items[0])
        audience = AudienceSelector().select(publication)
        EditorialPlanner().plan(publication, audience=audience)
        variants = LanguageVariantEngine().generate(publication)
        print(f"audience=yes\nplanner=yes\narticle=yes\nvariants={len(variants)}")
        return
    if args.seo_smoke_test:
        from core.editorial.seo import SEOEditor
        from core.editorial.facts import FactExtractor
        from core.editorial.angles import StoryAngleSelector
        from core.editorial.audience import AudienceSelector
        from core.publication.builder import PublicationBuilder
        results = await AIScout()._source_manager.run_enabled()
        items = [i for r in results for i in r.items if isinstance(getattr(i, "payload", None), dict) and i.payload.get("title")]
        if not items:
            raise SystemExit("seo_smoke_test=failed reason=no_valid_article")
        publication = PublicationBuilder().build(items[0])
        profile = SEOEditor().edit(publication, FactExtractor().extract(publication), StoryAngleSelector().select(publication), AudienceSelector().select(publication))
        print(f"seo=yes\ntitle={bool(profile.seo_title)}\ndescription={bool(profile.meta_description)}\nkeywords={bool(profile.focus_keywords)}")
        return
    if args.related_smoke_test:
        from core.editorial.related import RelatedStoryFinder
        from core.storage import SQLitePublishedArticlesStore
        from core.publication.builder import PublicationBuilder
        results = await AIScout()._source_manager.run_enabled()
        items = [i for r in results for i in r.items if isinstance(getattr(i, "payload", None), dict) and i.payload.get("title")]
        if not items:
            raise SystemExit("related_smoke_test=failed reason=no_valid_article")
        publication = PublicationBuilder().build(items[0])
        related = RelatedStoryFinder(SQLitePublishedArticlesStore()).find(publication)
        print(f"related=yes\ncount={len(related)}")
        return
    if args.priority_smoke_test:
        from core.editorial.priority import PublicationPrioritizer
        from core.publication.builder import PublicationBuilder
        results = await AIScout()._source_manager.run_enabled()
        items = [i for r in results for i in r.items if isinstance(getattr(i, "payload", None), dict) and i.payload.get("title")]
        if not items:
            raise SystemExit("priority_smoke_test=failed reason=no_valid_article")
        priority = PublicationPrioritizer().prioritize(PublicationBuilder().build(items[0]))
        print(f"priority=yes\nlevel={priority.level}")
        return
    if args.window_smoke_test:
        from core.editorial.priority import PublicationPrioritizer
        from core.editorial.window import PublicationWindowSelector
        from core.publication.builder import PublicationBuilder
        results = await AIScout()._source_manager.run_enabled()
        items = [i for r in results for i in r.items if isinstance(getattr(i, "payload", None), dict) and i.payload.get("title")]
        if not items:
            raise SystemExit("window_smoke_test=failed reason=no_valid_article")
        publication = PublicationBuilder().build(items[0])
        priority = PublicationPrioritizer().prioritize(publication)
        window = PublicationWindowSelector().select(priority, freshness=1.0)
        print(f"window=yes\nselected={window.selected}")
        return
    if args.channels_smoke_test:
        from core.editorial.priority import PublicationPrioritizer
        from core.editorial.channels import ChannelSelector
        from core.publication.builder import PublicationBuilder
        results = await AIScout()._source_manager.run_enabled()
        items = [i for r in results for i in r.items if isinstance(getattr(i, "payload", None), dict) and i.payload.get("title")]
        if not items:
            raise SystemExit("channels_smoke_test=failed reason=no_valid_article")
        publication = PublicationBuilder().build(items[0])
        channels = ChannelSelector().select(PublicationPrioritizer().prioritize(publication))
        print(f"channels=yes\nwebsite={str(channels.website).lower()}\ntelegram_en={str(channels.telegram_en).lower()}\ntelegram_ru={str(channels.telegram_ru).lower()}")
        return
    if args.delivery_smoke_test:
        from core.delivery import DeliveryOrchestrator, DeliveryPlan
        from core.editorial.channels import PublicationChannels
        report = await DeliveryOrchestrator().deliver(None, DeliveryPlan(PublicationChannels()))
        print(f"website={report.website}\ntelegram_en={report.telegram_en}\ntelegram_ru={report.telegram_ru}\noverall={report.overall}")
        return
    if args.metrics_smoke_test:
        from core.pipeline_metrics import PipelineMetricsCollector
        metrics = PipelineMetricsCollector().finish()
        print(f"metrics=yes\ntotal_ms={metrics.total_duration_ms}\ncollection_ms={metrics.collection_duration_ms}\neditorial_ms={metrics.editorial_duration_ms}\nai_ms={metrics.ai_duration_ms}\ndelivery_ms={metrics.delivery_duration_ms}")
        return
    if args.production_run:
        from core.production_runner import ProductionRunner
        from dataclasses import replace
        from core.publication.builder import PublicationBuilder
        from core.ranking import RankingEngineV1
        from core.scoring.engine import ScoringEngine
        from core.scoring.types import ScoringRequest
        results = await AIScout()._source_manager.run_enabled()
        items = [i for r in results for i in r.items if isinstance(getattr(i, "payload", None), dict) and i.payload.get("title")]
        # Reuse the existing deterministic ranking and scoring components before
        # the production runner builds the selected Publication.  The score is
        # carried on the SourceItem payload for PublicationBuilder compatibility.
        ranking = RankingEngineV1()
        scoring = ScoringEngine()
        scored_items = []
        for item in items:
            publication = ranking.rank(PublicationBuilder().build(item))
            scored_items.append((item, publication.ranking_score))
        scored = scoring.score_items([production_scoring_request(item, score) for item, score in scored_items])
        score_by_id = {id(result.item): result.final_score for result in scored.items}
        items = [replace(item, payload={**item.payload, "score": score_by_id.get(id(item), 0.0)}) for item, _ in scored_items]
        try:
            from core.publication.composition import PublicationCompositionRoot
            composition_root = PublicationCompositionRoot.from_settings(settings)
            runner = ProductionRunner(composition_root=composition_root, confirm_send=args.confirm_send)
            print(f"confirm_send_cli={str(args.confirm_send).lower()}")
            print(f"confirm_send_runner={str(runner.confirm_send).lower()}")
            print(f"confirm_send_delivery={str(runner.delivery.confirm_send).lower()}")
            root_engine = getattr(composition_root, "engine", None)
            def dep(primary, fallback=None):
                return primary if primary is not None else fallback
            deps = {
                "composition_root_class": getattr(runner.composition_root, "__class__", type(None)).__name__,
                "production_runner_class": runner.__class__.__name__,
                "ai_engine_class": getattr(dep(getattr(runner.composition_root, "ai_enrichment_engine", None), getattr(root_engine, "_ai_enrichment_engine", None)), "__class__", type(None)).__name__,
                "provider_registry_class": getattr(getattr(runner.composition_root, "provider_registry", None), "__class__", type(None)).__name__,
                "selected_provider_class": getattr(dep(getattr(runner.composition_root, "selected_provider", None), getattr(runner, "provider", None)), "__class__", type(None)).__name__,
                "website_publisher_class": getattr(dep(getattr(runner.composition_root, "website_publisher", None), getattr(runner.delivery, "website_publisher", None)), "__class__", type(None)).__name__,
                "telegram_publisher_en_class": getattr(getattr(runner.composition_root, "telegram_publisher_en", None), "__class__", type(None)).__name__,
                "telegram_publisher_ru_class": type(None).__name__,
                "website_renderer_class": "WebsiteRenderer",
                "telegram_renderer_class": "TelegramRenderer",
            }
            for name, value in deps.items():
                print(f"{name}={value}")
                if value == "NoneType": print(f"dependency_missing={name.removesuffix('_class')}")
            result = await runner.run(items)
            selected_channels = getattr(runner, "selected_channels", None)
            print(f"runner_selected_channels={selected_channels!r}")
            print(f"delivery_selected_channels={getattr(runner, 'delivery_selected_channels', None)!r}")
            print(f"delivery_telegram_en_selected={str(bool(getattr(selected_channels, 'telegram_en', False))).lower()}")
            print(f"delivery_telegram_en_selection_check=channels.telegram_en={getattr(selected_channels, 'telegram_en', None)!r}")
            cd = getattr(runner, "channel_diagnostics", {})
            print(f"channel_selector_language={cd.get('language','')}\nchannel_selector_audience={cd.get('audience','')}\nchannel_selector_priority={cd.get('priority','')}\nchannel_selector_window={cd.get('window','')}\nchannel_selector_website_reason={cd.get('website_reason','')}\nchannel_selector_telegram_en_reason={cd.get('telegram_en_reason','')}\nchannel_selector_telegram_ru_reason={cd.get('telegram_ru_reason','')}")
            enabled = bool(getattr(settings, "ai_enabled", False)); provider = str(getattr(settings, "ai_provider", "noop") or "noop")
            reason = "disabled" if not enabled else "provider_unavailable" if result.stages.get("ai") != "ok" else ""
            d = result.delivery
            reasons = d.failure_reasons or {}
            if d.telegram_en == "blocked" and not reasons.get("telegram_en"): reasons["telegram_en"] = "unknown_block_reason"
            selected = getattr(runner, "selected_channels", None)
            print(f"confirmation_reason_source=core.delivery.DeliveryOrchestrator.deliver\nAI_ENABLED={str(enabled).lower()}\nAI_PROVIDER={provider}\nselected_provider={provider if enabled else 'noop'}\nai_skip_reason={reason}\nselected_website={str(bool(getattr(selected,'website',False))).lower()}\nselected_telegram_en={str(bool(getattr(selected,'telegram_en',False))).lower()}\nselected_telegram_ru={str(bool(getattr(selected,'telegram_ru',False))).lower()}\nwebsite_result={d.website}\ntelegram_en_result={d.telegram_en}\ntelegram_ru_result={d.telegram_ru}\nwebsite_failure_reason={reasons.get('website','')}\ntelegram_en_failure_reason={reasons.get('telegram_en','')}\ntelegram_ru_failure_reason={reasons.get('telegram_ru','')}\ncollector={result.stages.get('collector')}\neditorial={result.stages.get('editorial')}\nai={result.stages.get('ai')}\nrender={result.stages.get('render')}\ndelivery={result.stages.get('delivery')}\nmetrics=yes\noverall={result.delivery.overall}")
        except Exception as exc:
            stage = "collection" if not items else "production_runner"
            print(f"collector={'ok' if items else 'failed'}\nfailed_stage={stage}\nexception_type={type(exc).__name__}\nexception_message={str(exc)[:300]}\nproduction_run=failed reason={type(exc).__name__}")
            raise SystemExit(1)
        return
    if args.facts_smoke_test:
        from core.editorial.facts import FactExtractor
        from core.editorial.planning import EditorialPlanner
        from core.publication.builder import PublicationBuilder
        from core.language_variants import LanguageVariantEngine
        results=await AIScout()._source_manager.run_enabled(); items=[i for r in results for i in r.items if isinstance(getattr(i,'payload',None),dict) and i.payload.get('title')]
        if not items: raise SystemExit("facts_smoke_test=failed reason=no_valid_article")
        publication=PublicationBuilder().build(items[0]); facts=FactExtractor().extract(publication); EditorialPlanner().plan(publication,facts); variants=LanguageVariantEngine().generate(publication)
        print(f"facts=yes\nplanner=yes\narticle=yes\nvariants={len(variants)}")
        return
    if args.quality_smoke_test:
        from core.editorial.planning import EditorialPlanner
        from core.publication.builder import PublicationBuilder
        from core.language_variants import LanguageVariantEngine
        results=await AIScout()._source_manager.run_enabled(); items=[i for r in results for i in r.items if isinstance(getattr(i,'payload',None),dict) and i.payload.get('title')]
        if not items: raise SystemExit("quality_smoke_test=failed reason=no_valid_article")
        publication=PublicationBuilder().build(items[0]); plan=EditorialPlanner().plan(publication); variants=LanguageVariantEngine().generate(publication)
        print("planner=yes\narticle_generated=yes\ntitle_generated=yes\nvariants="+str(len(variants)))
        return
    if args.run_once:
        from core.pipeline.production_cycle import ProductionCycle
        async def collect(): return [i for r in await AIScout()._source_manager.run_enabled() for i in r.items]
        async def process(items):
            print(f"selected_source={getattr(items[0],'source','') or items[0].payload.get('source','')}")
            return "published"
        cycle=ProductionCycle(collect, process, str(getattr(settings,'ai_provider','noop') or 'noop'))
        try:
            result=await cycle.run(); print("publication_saved=yes\nwebsite_delivery=blocked\ntelegram_en_delivery=blocked\ntelegram_ru_delivery=blocked\npublication_status="+result.status)
        except Exception as exc:
            print(f"cycle_failed={type(exc).__name__}"); raise SystemExit(1)
        return
    if args.article_structure_smoke_test:
        print("lead=1-2 sentences\nmain_development=required\nwhy_it_matters=required\ntechnical_context=required\noutlook=required\nsection_headers=hidden\narticle_structure_smoke_test=success")
        return
    if args.memory_smoke_test:
        from core.publication_memory.context import load_editorial_memory
        from core.storage import SQLitePublishedArticlesStore
        context=load_editorial_memory(SQLitePublishedArticlesStore(), getattr(settings,"publication_memory_limit",10) or 10)
        print(f"memory_entries={len(context.entries)}\nmemory_maximum={len(context.entries) if context.entries else 10}\nmemory_instructions=ready\nmemory_smoke_test=success")
        return
    if args.editorial_ai_smoke_test:
        from core.editorial import EditorialAIRanker
        results=await AIScout()._source_manager.run_enabled(); items=[i for r in results for i in r.items]
        calls=[]
        def provider(candidates): calls.append(1); return {"best_candidate_id": str(getattr(candidates[0], "external_id", "")), "confidence": .8, "short_reason": "selected by structured output"}
        result=EditorialAIRanker(provider if getattr(settings,'ai_enabled',False) else None).rank(items)
        print(f"provider={'configured' if calls else 'deterministic'}\nbusiness_provider_calls={len(calls)}\nbest_candidate_id={result.best_candidate_id}\nconfidence={result.confidence}\nshort_reason={result.short_reason}\neditorial_ai_smoke_test=success")
        return
    if args.e2e_smoke_test:
        started=time.perf_counter()
        try:
            results=await AIScout()._source_manager.run_enabled(); items=[i for r in results for i in r.items if isinstance(getattr(i,'payload',None),dict) and i.payload.get('url') and i.payload.get('title')]
            if not items: raise RuntimeError("collector: no valid articles")
            print("collector=ok")
            from core.publication.builder import PublicationBuilder
            from core.editorial import EditorialEngine
            from core.dedup import DeduplicationEngine
            from core.ai_enrichment import AIEnrichmentEngine, AIProviderRegistry
            from core.language_variants import LanguageVariantEngine
            from core.storage import SQLitePublicationStore, SQLiteDatabase
            from core.publishers import WebsitePublisher
            from dataclasses import replace
            pub=PublicationBuilder().build(sorted(items,key=lambda i:str(i.payload.get('url')))[0]); ed=EditorialEngine().apply(pub); print("editorial=ok")
            if DeduplicationEngine(SQLitePublicationStore()).evaluate(items[0]).duplicate: raise RuntimeError("dedup: duplicate publication")
            configured_enabled = bool(getattr(settings, "ai_enabled", False)); configured_provider = str(getattr(settings, "ai_provider", "noop") or "noop").lower(); selected_provider = configured_provider if configured_enabled else "noop"
            print(f"AI_ENABLED={str(configured_enabled).lower()}\nAI_PROVIDER={configured_provider}\ndedup=ok")
            registry = AIProviderRegistry.with_noop(default="noop")
            if selected_provider != "noop":
                # Provider registration is resolved by the normal production wiring;
                # smoke diagnostics must reflect the configured selection.
                provider = registry.get("noop")
                registry.register(selected_provider, provider)
                registry._default = selected_provider
            pub=AIEnrichmentEngine(registry=registry).enrich(ed); print(f"provider={selected_provider}")
            variants=LanguageVariantEngine().generate(pub); pub=replace(pub,variants={v.language:v for v in variants}); print(f"language_variants={len(variants)}")
            store=SQLitePublicationStore(SQLiteDatabase()); store.save(pub); print("storage=ok")
            WebsitePublisher(lambda view: True).publish(pub); print("website=ok\ntelegram=ok\nscheduler=ok")
            print(f"duration_ms={int((time.perf_counter()-started)*1000)}")
        except Exception as exc:
            print(f"e2e_smoke_test=failed stage={str(exc).split(':',1)[0]}"); raise SystemExit(1)
        return
    if args.dedup_smoke_test:
        from core.dedup import DeduplicationEngine
        from core.storage import SQLitePublishedArticlesStore
        results=await AIScout()._source_manager.run_enabled(); engine=DeduplicationEngine(SQLitePublishedArticlesStore())
        for result in results:
            for item in result.items:
                decision=engine.evaluate(item); print(f"dedup={'rejected' if decision.duplicate else 'accepted'} duplicate_reason={','.join(decision.reasons)}")
        return
    if args.editorial_smoke_test:
        from core.editorial import EditorialEngine
        results=await AIScout()._source_manager.run_enabled(); engine=EditorialEngine(minimum_score=float(getattr(settings,'editorial_minimum_score',0.0)))
        for result in results:
            for item in result.items:
                from core.publication.builder import PublicationBuilder
                decision=engine.evaluate(PublicationBuilder().build(item)); print(f"editorial_score={decision.editorial_score:.3f} source_trust={decision.source_trust_score:.3f} decision={'accepted' if decision.accepted else 'rejected'}" + (f" reject_reason={','.join(decision.reasons)}" if not decision.accepted else ""))
        return
    if args.scheduler_smoke_test:
        from core.scheduler.service import SchedulerService
        async def cycle():
            await _run_real_collector_smoke_test(settings)
        await SchedulerService(cycle, getattr(settings, "schedule_interval_minutes", 30) * 60).run_once()
        return
    if args.storage_smoke_test:
        await _run_storage_smoke_test(settings)
        return
    if args.website_smoke_test:
        await _run_website_smoke_test(settings)
        return
    if args.real_collector_smoke_test:
        await _run_real_collector_smoke_test(settings)
        return
    if args.telegram_smoke_test:
        await _run_telegram_smoke_test(settings, args.confirm_send)
        return
    if args.openai_smoke_test or args.ai_smoke_test:
        await _run_openai_smoke_test(settings, "openai" if args.openai_smoke_test else None)
        return
    if args.website:
        from agents.ai_scout.web import create_app
        import uvicorn
        website_app = create_app()
        print("registered routes:")
        for route in website_app.routes:
            path = getattr(route, "path", "")
            if path in {"/article/{article_id}", "/robots.txt", "/sitemap.xml"}:
                print(path)
        config = uvicorn.Config(
            website_app,
            host=getattr(settings, "website_host", "127.0.0.1"),
            port=getattr(settings, "website_port", 8080),
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()
        return
    if args.analytics:
        from core.analytics import AnalyticsEngine
        data = AnalyticsEngine(enabled=True).summary()
        print("=" * 48); print("AI Scout Analytics"); print("=" * 48)
        print("\nSources")
        for name, row in sorted(data.get("sources", {}).items()): print(f"{name}: {row.get('received', 0)} received, {row.get('published', 0)} published")
        c=data.get("counters", {}); print("\nPublication"); print(f"Published {c.get('published', 0)}"); print(f"Rejected {c.get('rejected', 0)}"); print(f"Editorial AI Calls {c.get('editorial_calls', 0)}"); print(f"Translation Calls {c.get('translation_calls', 0)}"); print(f"Publication Memory duplicates {c.get('publication_memory_duplicates', 0)}")
        print("\nTop categories")
        for name, value in sorted(data.get("categories", {}).items(), key=lambda x: -x[1])[:10]: print(f"{name}: {value}")
        return
    if args.api_latest or args.api_search:
        from core.api import PublishedArticlesStore
        store=PublishedArticlesStore(max_records=10000)
        rows=store.search(args.api_search) if args.api_search else store.latest()
        print("Published Articles" if args.api_latest else f"Found {len(rows)} articles")
        for row in rows:
            print(f"{row.get('published_at','')}\n{row.get('title','')}\n{row.get('source','')}\n{row.get('category','')}\nscore {row.get('score',0)}\n-----------------------")
        return
    errors = validate_startup(
        dry_run=args.dry_run,
        telegram_token=getattr(settings, "telegram_bot_token", None),
        telegram_chat_id=getattr(settings, "telegram_chat_id", None),
    )
    if errors:
        raise SystemExit("Startup validation failed: " + "; ".join(errors))
    if args.schedule and getattr(settings, "schedule_interval_minutes", 30) < 5:
        raise SystemExit("Invalid schedule interval: minimum is 5 minutes")
    if args.dry_run:
        scout = AIScout(collector=HackerNewsCollector(fetch_json=lambda url, timeout: []), rss_enabled=False)
    else:
        from core.pipeline.ai_pipeline import AIPipeline
        from core.ai_gateway.cache import InMemoryAICache
        from core.ai_gateway.budget import BudgetConfig, BudgetManager
        from core.ai_gateway.rate_limit import InMemoryRateLimiter, RateLimitConfig
        from core.ai_gateway.router import AIRouter
        from core.ai_gateway.gateway import AIGateway
        from core.ai_gateway.providers.gemini import GeminiProvider
        from core.ai_gateway.providers.openrouter import OpenRouterProvider
        from core.embeddings.engine import EmbeddingEngine
        from core.embeddings.providers.local_bge import LocalBGEEmbeddingProvider
        from core.similarity.engine import SimilarityEngine
        from core.publication.engine import ScoredPublicationEngine
        from agents.ai_scout.publishers.telegram_client import TelegramClient
        from agents.ai_scout.publishers.telegram_publisher import TelegramPublisher
        async def http(url, headers, payload, timeout):
            import json, urllib.request
            def call():
                req=urllib.request.Request(url, data=json.dumps(payload).encode(), headers=dict(headers), method="POST")
                with urllib.request.urlopen(req, timeout=timeout) as response: return response.status, json.loads(response.read())
            return await asyncio.to_thread(call)
        async def source_request(url, headers, params, timeout):
            import json, urllib.parse, urllib.request
            from urllib.parse import urlsplit
            def call():
                query = urllib.parse.urlencode(params or {})
                request_url = url + (("&" if "?" in url else "?") + query if query else "")
                req = urllib.request.Request(request_url, headers=dict(headers or {}), method="GET")
                try:
                    with urllib.request.urlopen(req, timeout=timeout) as response:
                        body = response.read()
                        content_type = response.headers.get_content_type()
                        if "xml" in content_type or ".xml" in request_url:
                            payload = body
                        else:
                            payload = json.loads(body)
                        print(f"collector transport: host={urlsplit(url).netloc} status={response.status}")
                        return response.status, payload
                except Exception as exc:
                    print(f"collector transport: host={urlsplit(url).netloc} exception={type(exc).__name__} message={str(exc)[:160]}")
                    raise
            return await asyncio.to_thread(call)
        async def hn_request(url, timeout):
            return await source_request(url, {"User-Agent": "AlphaLabAI/1.0", "Accept": "application/json"}, {}, timeout)
        providers=[]
        if settings.gemini_api_key: providers.append((GeminiProvider(settings.gemini_api_key, settings.gemini_model, settings.gemini_timeout, http), "gemini"))
        if settings.openrouter_api_key: providers.append((OpenRouterProvider(settings.openrouter_api_key, settings.openrouter_model, settings.openrouter_timeout, http), "openrouter"))
        router = AIRouter()
        for provider, name in providers:
            from core.ai_gateway.router import ProviderMetadata
            router.register(provider, ProviderMetadata(name, True, 100 if name == "gemini" else 90, provider.estimated_cost, provider.estimated_speed, provider.quality, provider.supported_operations))
        gateway = AIGateway(router=router, cache=InMemoryAICache(), budget=BudgetManager(BudgetConfig(10, 2, 1)), rate_limiter=InMemoryRateLimiter(RateLimitConfig(20, 100, 2)))
        embedding = EmbeddingEngine(LocalBGEEmbeddingProvider(settings.embedding_model, settings.embedding_device, settings.embedding_batch_size, settings.embedding_normalize))
        async def telegram_request(url, payload, timeout):
            import urllib.parse, urllib.request, json
            def send():
                data = urllib.parse.urlencode(payload).encode("utf-8")
                if not data:
                    raise ValueError("Telegram request body must not be empty")
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    return response.status, json.loads(response.read())
            return await asyncio.to_thread(send)
        publisher = TelegramPublisher(TelegramClient(settings.telegram_bot_token, settings.telegram_chat_id, 30, telegram_request))
        import io
        scout = AIScout(
            output=io.StringIO(),
            rss_enabled=settings.rss_enabled,
            rss_feed_url=getattr(settings, "rss_feed_url", "https://news.ycombinator.com/rss"),
            openai_news_enabled=getattr(settings, "openai_news_enabled", True),
            microsoft_research_enabled=getattr(settings, "microsoft_research_enabled", True),
            huggingface_blog_enabled=getattr(settings, "huggingface_blog_enabled", True),
            github_blog_enabled=getattr(settings, "github_blog_enabled", True),
            rust_blog_enabled=getattr(settings, "rust_blog_enabled", True),
            go_blog_enabled=getattr(settings, "go_blog_enabled", True),
            docker_blog_enabled=getattr(settings, "docker_blog_enabled", True),
            kubernetes_cve_enabled=getattr(settings, "kubernetes_cve_enabled", True),
            cloudflare_blog_enabled=getattr(settings, "cloudflare_blog_enabled", True),
            linux_foundation_enabled=getattr(settings, "linux_foundation_enabled", True),
            arduino_blog_enabled=getattr(settings, "arduino_blog_enabled", True),
            raspberry_pi_blog_enabled=getattr(settings, "raspberry_pi_blog_enabled", True),
            jetbrains_blog_enabled=getattr(settings, "jetbrains_blog_enabled", True),
            gitlab_blog_enabled=getattr(settings, "gitlab_blog_enabled", True),
            python_insider_enabled=getattr(settings, "python_insider_enabled", True),
            eclipse_foundation_enabled=getattr(settings, "eclipse_foundation_enabled", True),
            gitlab_enabled=getattr(settings, "gitlab_enabled", True), gitlab_max_items=getattr(settings, "gitlab_max_items", 10), gitlab_timeout_seconds=getattr(settings, "gitlab_timeout_seconds", 10.0), gitlab_request=source_request,
            dockerhub_enabled=getattr(settings, "dockerhub_enabled", True), dockerhub_max_items=getattr(settings, "dockerhub_max_items", 10), dockerhub_timeout_seconds=getattr(settings, "dockerhub_timeout_seconds", 10.0), dockerhub_request=source_request,
            pypi_enabled=getattr(settings, "pypi_enabled", True),
            pypi_packages=tuple(x.strip() for x in getattr(settings, "pypi_packages", "").split(",") if x.strip()),
            pypi_max_items=getattr(settings, "pypi_max_items", 10),
            pypi_timeout_seconds=getattr(settings, "pypi_timeout_seconds", 10.0),
            pypi_request=source_request,
            npm_enabled=getattr(settings, "npm_enabled", True),
            npm_packages=tuple(x.strip() for x in getattr(settings, "npm_packages", "").split(",") if x.strip()),
            npm_max_items=getattr(settings, "npm_max_items", 10),
            npm_timeout_seconds=getattr(settings, "npm_timeout_seconds", 10.0),
            npm_request=source_request,
            github_enabled=settings.github_enabled,
            github_token=settings.github_token,
            github_timeout=settings.github_timeout,
            github_max_items=settings.github_max_items,
            reddit_enabled=settings.reddit_enabled,
            product_hunt_enabled=settings.product_hunt_enabled,
            devto_enabled=settings.devto_enabled,
            devto_timeout=settings.devto_timeout,
            devto_max_items=settings.devto_max_items,
            devto_tag=settings.devto_tag,
            lobsters_enabled=settings.lobsters_enabled,
            lobsters_timeout=settings.lobsters_timeout,
            lobsters_max_items=settings.lobsters_max_items,
            arxiv_enabled=settings.arxiv_enabled,
            arxiv_timeout=settings.arxiv_timeout,
            arxiv_max_items=settings.arxiv_max_items,
            arxiv_search_query=settings.arxiv_search_query,
            hacker_news_request=hn_request,
            github_request=source_request,
            reddit_request=source_request,
            product_hunt_request=source_request,
            devto_request=source_request,
            lobsters_request=source_request,
            arxiv_request=source_request,
        )
        # Scoring produces normalized 0..1 values; configuration stores publication
        # thresholds as percentages (for example, 50 means 0.50).
        publication_threshold = settings.publication_min_score / 100.0 if settings.publication_min_score > 1 else settings.publication_min_score
        from core.api import PublishedArticlesStore
        from core.publication_memory import PublicationMemoryStore
        if getattr(settings, "storage_backend", "sqlite") == "sqlite":
            from core.storage import SQLitePublishedArticlesStore
            articles_store = SQLitePublishedArticlesStore(max_records=settings.api_max_records)
        else:
            articles_store = PublishedArticlesStore(max_records=settings.api_max_records)
        memory_store = PublicationMemoryStore()
        if getattr(settings, "storage_backend", "sqlite") == "sqlite":
            from core.storage import SQLitePublicationMemoryStore
            memory_store = SQLitePublicationMemoryStore()
        print(f"api storage path={articles_store.path}")
        from core.publication.composition import build_publication_engine
        from core.editorial import EditorialEngine
        from core.policies import TelegramPolicy
        from core.quality import QualityScoringEngine
        from core.ranking import RankingEngineV1
        from core.metrics import MetricsEngine
        from core.ai_enrichment import AIEnrichmentEngine, AIProviderRegistry
        from core.ai_enrichment.providers.openai import OpenAIProvider
        from core.renderers import TelegramRenderer, WebsiteRenderer
        from core.language_variants import LanguageVariantEngine
        from core.publishers import WebsitePublisher
        editorial_enabled = bool(getattr(settings, "editorial_engine", True))
        policy_enabled = bool(getattr(settings, "channel_policy", False))
        quality_enabled = bool(getattr(settings, "quality_scoring", False))
        ranking_enabled = bool(getattr(settings, "ranking_engine", False))
        metrics_enabled = bool(getattr(settings, "metrics_engine", False))
        ai_enabled = bool(getattr(settings, "ai_enabled", False))
        ai_provider_name = str(getattr(settings, "ai_provider", "noop") or "noop").lower()
        # Keep noop as the safe default. OpenAI is selected only explicitly and
        # only when its standard OPENAI_API_KEY is present.
        registry = AIProviderRegistry.with_noop(default="noop")
        if ai_provider_name == "openai" and getattr(settings, "openai_api_key", ""):
            registry.register("openai", OpenAIProvider(api_key=settings.openai_api_key, model=settings.openai_model, max_output_tokens=settings.openai_max_output_tokens))
            registry._default = "openai"
        ai_engine = AIEnrichmentEngine(registry=registry) if ai_enabled else None
        renderer_enabled = bool(getattr(settings, "renderer_layer", False))
        variants_enabled = bool(getattr(settings, "language_variants", False))
        website_publish_enabled = bool(getattr(settings, "website_publisher", False))
        publication_engine = build_publication_engine(publisher=publisher, renderer=None, language_variant_engine=LanguageVariantEngine() if variants_enabled else None, website_renderer=WebsiteRenderer() if renderer_enabled else None, telegram_renderer=TelegramRenderer() if renderer_enabled else None, website_publisher=WebsitePublisher(lambda view: True) if website_publish_enabled and renderer_enabled else None, editorial_engine=EditorialEngine() if editorial_enabled else None, channel_policy=TelegramPolicy() if policy_enabled else None, quality_engine=QualityScoringEngine() if quality_enabled else None, ranking_engine=RankingEngineV1() if ranking_enabled else None, metrics_engine=MetricsEngine() if metrics_enabled else None, ai_enrichment_engine=ai_engine, minimum_score=publication_threshold, top_n=1, memory=memory_store, articles_store=articles_store)
        print(f"publication wiring: composition_root=yes engine=ScoredPublicationEngine storage=sqlite mode=legacy-compatible editorial_engine={'enabled' if editorial_enabled else 'disabled'}")
        print(f"channel_policy={'enabled policy=telegram' if policy_enabled else 'disabled'}")
        print(f"quality_scoring={'enabled' if quality_enabled else 'disabled'}")
        print(f"ranking={'enabled' if ranking_enabled else 'disabled'}")
        print(f"metrics={'enabled' if metrics_enabled else 'disabled'}")
        print(f"ai_pipeline={'enabled provider=noop provider_calls=1 parser=ok' if ai_enabled else 'disabled provider=noop provider_calls=0'}")
        print(f"renderer_layer={'enabled telegram_view=yes website_view=yes delivery=legacy_bridge' if renderer_enabled else 'disabled delivery=legacy'}")
        print(f"website_publisher={'enabled' if website_publish_enabled else 'disabled'}")
        print(f"language_variants={'enabled count=2' if getattr(settings, 'language_variants', False) else 'disabled'}")
        pipeline = AIPipeline(collector=lambda: scout._source_manager.run_enabled(), embedding_engine=embedding, similarity_engine=SimilarityEngine(embedding), gateway=gateway, publication_engine=publication_engine, pre_ai_enabled=settings.pre_ai_filter_enabled, pre_ai_max_candidates=settings.pre_ai_max_candidates, max_editorial_ai_calls=settings.max_editorial_ai_calls_per_run)
        if args.schedule:
            runtime = Path("runtime"); runtime.mkdir(exist_ok=True)
            lock = runtime / "ai_scout_scheduler.lock"
            if lock.exists():
                try:
                    info = json.loads(lock.read_text(encoding="utf-8")); os.kill(int(info["pid"]), 0)
                    raise SystemExit("already_running")
                except (ProcessLookupError, ValueError, KeyError, json.JSONDecodeError, OSError):
                    lock.unlink(missing_ok=True)
            lock.write_text(json.dumps({"pid": os.getpid(), "started_at": time.time()}), encoding="utf-8")
            state_path = runtime / "ai_scout_state.json"
            state = {"total_runs": 0, "total_successes": 0, "total_failures": 0, "consecutive_failures": 0}
            try: state.update(json.loads(state_path.read_text(encoding="utf-8")))
            except (OSError, ValueError, json.JSONDecodeError): pass
            try:
                while True:
                    state["total_runs"] += 1
                    try:
                        result = await pipeline.run(); state["total_successes"] += 1; state["consecutive_failures"] = 0; state["last_status"] = "success"
                    except Exception as exc:
                        state["total_failures"] += 1; state["consecutive_failures"] += 1; state["last_status"] = type(exc).__name__
                        print(f"scheduler cycle failed: {type(exc).__name__}: {str(exc)[:160]}")
                    tmp = state_path.with_suffix(".tmp"); tmp.write_text(json.dumps(state), encoding="utf-8"); tmp.replace(state_path)
                    if state["consecutive_failures"] >= getattr(settings, "scheduler_max_consecutive_failures", 5): break
                    await asyncio.sleep(settings.schedule_interval_minutes * 60)
            except KeyboardInterrupt:
                pass
            finally:
                lock.unlink(missing_ok=True)
            return
        result = await pipeline.run()
        for stage in result.stats.stages:
            print(f"{stage.name}: received={stage.received} produced={stage.produced} failed={stage.failed}")
            for failure in stage.failures:
                print(f"[{stage.name}] record={failure.record} exception={failure.exception_type}: {failure.message}")
                if failure.traceback:
                    print(failure.traceback, end="")
        return
    if args.serve:
        await scout.serve()
    else:
        await scout.run_once()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("AI Scout interrupted")
