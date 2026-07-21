from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from core.publication.base import (
    PublicationDocument,
    PublicationLedger,
    PublicationPolicy,
    ScoringView,
)
from core.publication.publishers import PublisherRegistry
from core.publication.types import (
    PublicationCandidate,
    PublicationPlan,
    PublishResult,
    build_candidate_id,
)
from core.publication.types import PublicationRequest, PublicationResult, PublishedItem, PublicationStats


Clock = Callable[[], datetime]


class InMemoryPublicationLedger(PublicationLedger):
    def __init__(self) -> None:
        self._processed: set[UUID] = set()

    def is_processed(self, candidate_id: UUID) -> bool:
        return candidate_id in self._processed

    def mark_processed(self, candidate_id: UUID) -> bool:
        if candidate_id in self._processed:
            return False
        self._processed.add(candidate_id)
        return True


class PublicationEngine:
    def __init__(
        self,
        policy: PublicationPolicy,
        publishers: PublisherRegistry,
        *,
        clock: Clock | None = None,
    ) -> None:
        self._policy = policy
        self._publishers = publishers
        self._clock = clock or (lambda: datetime.now(UTC))

    def plan(
        self,
        document: PublicationDocument,
        scoring: ScoringView,
    ) -> PublicationPlan:
        decision = self._policy.evaluate(scoring.total_score)
        if not decision.accepted:
            return PublicationPlan(decision=decision, candidate=None)

        candidate = PublicationCandidate(
            candidate_id=build_candidate_id(document.id, decision.policy_version),
            document_id=document.id,
            source=document.source,
            title=document.title,
            url=document.url,
            summary=document.summary,
            keywords=tuple(document.keywords),
            tags=tuple(document.tags),
            total_score=scoring.total_score,
            reasons=tuple(scoring.reasons),
            channels=decision.channels,
            correlation_id=scoring.correlation_id,
            created_at=self._clock(),
        )
        return PublicationPlan(decision=decision, candidate=candidate)

    async def publish(
        self,
        candidate: PublicationCandidate,
    ) -> tuple[PublishResult, ...]:
        results = []
        for channel in candidate.channels:
            try:
                publisher = self._publishers.get(channel)
                results.append(await publisher.publish(candidate))
            except Exception as exc:
                results.append(
                    PublishResult(
                        channel=channel,
                        success=False,
                        external_id=None,
                        published_at=self._clock(),
                        error_message=f"{type(exc).__name__}: {exc}",
                    )
                )
        return tuple(results)


class ScoredPublicationEngine:
    def __init__(self, publisher=None, minimum_score: float = 0.0, top_n: int = 10, dry_run: bool = False, memory=None, articles_store=None, publication_builder=None, renderer=None, editorial_engine=None, channel_policy=None, quality_engine=None, ranking_engine=None, metrics_engine=None, ai_enrichment_engine=None, website_renderer=None, telegram_renderer=None, website_publisher=None, language_variant_engine=None) -> None:
        self._publisher, self._minimum, self._top_n, self._dry_run, self._memory, self._articles_store = publisher, minimum_score, top_n, dry_run, memory, articles_store
        self._publication_builder, self._renderer = publication_builder, renderer
        self._editorial_engine = editorial_engine
        self._channel_policy = channel_policy
        self._quality_engine = quality_engine
        self._ranking_engine = ranking_engine
        self._metrics_engine = metrics_engine
        self._ai_enrichment_engine = ai_enrichment_engine
        self._website_renderer, self._telegram_renderer = website_renderer, telegram_renderer
        self._website_publisher = website_publisher
        self._language_variant_engine = language_variant_engine

    async def publish_scored(self, items) -> PublicationResult:
        candidates = list(items or ())
        candidates.sort(key=lambda x: (-float(getattr(x, "final_score", 0)), str(getattr(x, "item", x))))
        for position, scored in enumerate(candidates, 1):
            score = float(getattr(scored, "final_score", 0))
            item = getattr(scored, "item", scored)
            title = getattr(item, "title", None) or (getattr(item, "payload", {}) or {}).get("title", "")
            record = getattr(item, "external_id", None) or getattr(item, "url", None) or "<unknown>"
            passes = score >= self._minimum
            print(f"publication decision: record={record} title={title!r} score={score:.4f} threshold={self._minimum:.4f} position={position} minimum={'yes' if passes else 'no'} top_n={'yes' if position <= self._top_n else 'no'} dry_run={self._dry_run} reason={'accepted' if passes and position <= self._top_n else 'below_threshold' if not passes else 'outside_top_n'}")
        eligible = [x for x in candidates if float(getattr(x, "final_score", 0)) >= self._minimum][:self._top_n]
        seen = set(); published = []; duplicates = 0
        for scored in eligible:
            item = getattr(scored, "item", scored); key = getattr(item, "external_id", None) or getattr(item, "url", None) or str(item)
            if key in seen: duplicates += 1; continue
            seen.add(key)
            vector = tuple((getattr(item, "payload", {}) or {}).get("embedding", ()))
            payload = getattr(item, "payload", {}) or {}
            article_id = str(getattr(item, "external_id", "")); url = str(payload.get("url", ""))
            if self._articles_store is not None and hasattr(self._articles_store, "contains") and self._articles_store.contains(article_id, url):
                duplicates += 1; print(f"publication skipped: reason=duplicate article_id={article_id}"); continue
            print(f"publication allowed: article_id={article_id}")
            if self._memory is not None and vector and self._memory.contains(vector):
                duplicates += 1; continue
            if self._dry_run or self._publisher is None:
                published.append(PublishedItem(item, True, None)); continue
            publish_input = item
            if self._publication_builder is not None:
                publication = self._publication_builder.build(item)
                if self._editorial_engine is not None:
                    publication = self._editorial_engine.apply(publication)
                if self._channel_policy is not None and publication.variants.get("en"):
                    self._channel_policy.apply(publication.variants["en"])
                if self._quality_engine is not None:
                    publication = self._quality_engine.score(publication)
                if self._ranking_engine is not None:
                    publication = self._ranking_engine.rank(publication)
                if self._metrics_engine is not None:
                    publication = replace(publication, metrics=self._metrics_engine.collect(publication))
                if self._ai_enrichment_engine is not None:
                    publication = self._ai_enrichment_engine.enrich(publication)
                if self._language_variant_engine is not None:
                    variants = self._language_variant_engine.generate(publication)
                    publication = replace(publication, variants={v.language: v for v in variants})
                if self._telegram_renderer is not None:
                    self._telegram_view = self._telegram_renderer.render(publication)
                if self._website_renderer is not None:
                    self._website_view = self._website_renderer.render(publication)
                    if self._website_publisher is not None and not self._dry_run:
                        self._website_publisher.publish(self._website_view)
                if self._renderer is not None:
                    publish_input = self._renderer.render(publication)
            result = await self._publisher.publish(publish_input)
            ok = getattr(result, "ok", getattr(result, "success", False)) is True
            message_id = getattr(result, "message_id", getattr(result, "external_id", None))
            if ok and not self._dry_run and self._memory is not None:
                from core.publication_memory.memory import PublicationMemory
                self._memory.add(PublicationMemory(str(payload.get("title", "")), str(payload.get("url", "")), str(getattr(item, "source", "")), datetime.now(UTC), vector, str(payload.get("category", ""))))
            if ok and not self._dry_run and self._articles_store is not None:
                from core.api.schemas import PublishedArticle
                try:
                    website_data = self._website_view if self._website_view is not None else None
                    stored_title = getattr(website_data, "title", None) or getattr(publication, "title", None) or payload.get("title", "")
                    stored_summary = getattr(website_data, "summary", None) or getattr(publication, "summary", None) or payload.get("summary", "")
                    stored_url = getattr(website_data, "url", None) or getattr(publication, "url", None) or payload.get("url", "")
                    stored_source = getattr(website_data, "source", None) or getattr(publication, "source", None) or getattr(item, "source", "")
                    stored_category = getattr(website_data, "category", None) or getattr(publication, "category", None) or payload.get("category", "")
                    stored_language = getattr(website_data, "language", None) or getattr(publication, "language", None) or "en"
                    stored_score = getattr(website_data, "score", None) if website_data is not None else None
                    if stored_score is None:
                        stored_score = getattr(publication, "score", 0)
                    article_to_store = PublishedArticle(str(getattr(item, "external_id", "")), datetime.now(UTC).isoformat(), str(stored_title), str(stored_summary), str(stored_url), str(stored_source), str(stored_category), str(stored_language), float(stored_score or 0))
                    row = self._articles_store.append(article_to_store)
                except Exception:
                    pass
            published.append(PublishedItem(item, ok, str(message_id) if message_id is not None else None))
        return PublicationResult(tuple(published), PublicationStats(len(candidates), len(eligible), sum(x.success for x in published), duplicates))
