from dataclasses import dataclass, replace
from core.pipeline_metrics import PipelineMetricsCollector
from core.publication.builder import PublicationBuilder
from core.editorial import (EditorialPlanner, FactExtractor, StoryAngleSelector, AudienceSelector, HeadlineEditor, SEOEditor, PublicationPrioritizer, PublicationWindowSelector, ChannelSelector)
from core.renderers.website import WebsiteRenderer
from core.renderers.telegram import TelegramRenderer
from core.publication.models import DEFAULT_PUBLIC_BASE_URL
from core.delivery import DeliveryOrchestrator, DeliveryPlan, DeliveryReport
from core.delivery import DestinationDelivery
from core.renderers.x import XRenderer
from core.renderers.linkedin import LinkedInRenderer
from core.renderers.medium import MediumRenderer
from core.renderers.substack import SubstackRenderer
from core.renderers.devto import DevToRenderer
from core.renderers.hashnode import HashnodeRenderer
from core.renderers.reddit import RedditRenderer
from core.dedup import DedupEngine
from core.dedup.normalize import normalize_url
from datetime import datetime, UTC
from core.scheduler.adaptive import AdaptivePublicationScheduler


@dataclass(frozen=True)
class ProductionRunResult:
    delivery: DeliveryReport
    metrics: object
    stages: dict[str, str]


class ProductionRunner:
    @staticmethod
    def _has_cyrillic(text):
        return any("\u0400" <= ch <= "\u04ff" for ch in str(text or ""))

    @staticmethod
    def _has_latin(text):
        return any(("a" <= ch.lower() <= "z") for ch in str(text or ""))

    @staticmethod
    def _letter_counts(text):
        value = str(text or "")
        return (
            sum("\u0400" <= ch <= "\u04ff" for ch in value),
            sum("a" <= ch.lower() <= "z" for ch in value),
        )

    @classmethod
    def _valid_text(cls, text, language):
        value = " ".join(str(text or "").split())
        if not value or not any(ch.isalnum() for ch in value):
            return False
        cyr, latin = cls._letter_counts(value)
        if language == "ru":
            return cyr > latin
        return latin > cyr

    @staticmethod
    def _usable_content(title, content):
        title = " ".join(str(title or "").split())
        content = " ".join(str(content or "").split())
        return bool(content and content != title)

    def __init__(self, store=None, delivery=None, provider=None, composition_root=None, confirm_send=False, reservation_ttl_seconds=1800, pending_ttl_seconds=1800):
        self.composition_root = composition_root
        self.store = store or getattr(composition_root, "articles_store", None)
        self.provider = provider or getattr(composition_root, "ai_provider", None)
        self.ai_engine = getattr(composition_root, "ai_enrichment_engine", None)
        self.delivery = delivery or getattr(composition_root, "delivery_orchestrator", None) or DeliveryOrchestrator(getattr(composition_root, "website_publisher", None), getattr(composition_root, "telegram_publisher_en", None), telegram_publisher_ru=getattr(composition_root, "telegram_publisher_ru", None))
        # DeliveryOrchestrator's flag denotes that confirmation is required;
        # the CLI flag supplies that confirmation.
        self.confirm_send = bool(confirm_send)
        self.reservation_ttl_seconds = reservation_ttl_seconds
        self.pending_ttl_seconds = pending_ttl_seconds
        self.public_base_url = getattr(getattr(composition_root, "settings", None), "public_base_url", DEFAULT_PUBLIC_BASE_URL)
        self.delivery.confirm_send = self.confirm_send
        self.builder = getattr(composition_root, "builder", None) or PublicationBuilder()
        settings = getattr(composition_root, "settings", None)
        self.adaptive_scheduler = AdaptivePublicationScheduler(
            getattr(settings, "publication_high_priority_score", 90.0),
            getattr(settings, "publication_immediate_cooldown_minutes", 30.0),
        )
        self._adaptive_seeded = False

    @staticmethod
    def _select_best_candidate(items):
        def score(candidate):
            return float(
                getattr(
                    candidate,
                    "final_score",
                    getattr(candidate, "ranking_score", getattr(candidate, "score", 0)),
                ) or 0
            )

        winner = max(items, key=score)
        return getattr(winner, "item", winner)

    @staticmethod
    def _batch_deduplicate(items):
        engine = DedupEngine()
        unique, groups, _ = engine.deduplicate(items)
        # Keep the existing URL/title normalization, but do not suppress
        # distinct URLs merely because their titles match.
        kept = list(unique)
        for group in groups:
            by_url = {}
            for item in group.items:
                url = normalize_url(str(getattr(item, "payload", {}).get("url", "")))
                if url:
                    by_url.setdefault(url, []).append(item)
            if len(by_url) > 1:
                for item in group.items:
                    if item in kept:
                        kept.remove(item)
                for candidates in by_url.values():
                    kept.append(candidates[0])
                for item in group.items:
                    if not normalize_url(str(getattr(item, "payload", {}).get("url", ""))):
                        kept.append(item)
        return tuple(kept)

    def _published_filter(self, items):
        if self.store is None or not hasattr(self.store, "contains"):
            return tuple(items)
        result = []
        for item in items:
            payload = getattr(item, "payload", {}) or {}
            article_id = str(getattr(item, "external_id", None) or payload.get("article_id") or payload.get("id") or "")
            url = str(payload.get("url") or "")
            if not self.store.contains(article_id, url):
                result.append(item)
        return tuple(result)

    def _finalize_analytics(self, article_id, destination, row):
        analytics = getattr(self.delivery, "analytics_store", None)
        if analytics is None or not row:
            return
        status = str(row.get("status", ""))
        event_type = {"sent": "delivery_succeeded", "failed": "delivery_failed", "unknown": "delivery_unknown"}.get(status)
        if event_type is None:
            return
        try:
            from core.analytics.events import DistributionEvent
            analytics.append(DistributionEvent("", datetime.now(UTC), event_type, str(article_id), str(destination), status, int(row.get("attempt_count") or 0), row.get("external_id"), datetime.fromisoformat(row["scheduled_for"]) if row.get("scheduled_for") else None, row.get("error") or None, {}))
        except Exception:
            pass

    async def _run_single(self, items, _candidate_override=None):
        metrics = PipelineMetricsCollector(); stages = {}
        items = self._published_filter(self._batch_deduplicate(items))
        if not items: raise ValueError("no new candidates")
        metrics.count("candidates_collected", len(items)); stages["collector"] = "ok"
        if not self._adaptive_seeded and self.store is not None and hasattr(self.store, "latest_successful_publication_at"):
            self.adaptive_scheduler.seed_persisted_success(self.store.latest_successful_publication_at())
            self._adaptive_seeded = True
        immediate = self.adaptive_scheduler.select_immediate(items)
        candidate = _candidate_override or (getattr(immediate, "item", immediate) if immediate is not None else self._select_best_candidate(items))
        self.adaptive_decision = "immediate" if immediate is not None else "scheduled"
        reservation = None
        if self.store is not None and hasattr(self.store, "reserve"):
            payload = getattr(candidate, "payload", {}) or {}
            article_id = str(getattr(candidate, "external_id", None) or payload.get("article_id") or payload.get("id") or "")
            article_url = normalize_url(str(payload.get("url") or ""))
            reservation = (article_id, article_url)
            if not self.store.reserve(article_id, article_url, ttl_seconds=self.reservation_ttl_seconds):
                raise ValueError("candidate already reserved")
        try:
            publication = self.builder.build(candidate); stages["dedup"] = "ok"
            facts = FactExtractor().extract(publication); angle = StoryAngleSelector().select(publication); audience = AudienceSelector().select(publication)
            EditorialPlanner().plan(publication, facts=facts, angle=angle, audience=audience); stages["editorial"] = "ok"
            HeadlineEditor().edit(publication); SEOEditor().edit(publication, facts, angle, audience)
            priority = PublicationPrioritizer().prioritize(publication); window = PublicationWindowSelector().select(priority)
            if self.ai_engine:
                publication = self.ai_engine.enrich(publication)
        # Materialize the successful AI context into the immutable language
        # variants consumed by renderers.  Renderers intentionally know
        # nothing about provider-specific AIContext objects.
            context = getattr(publication, "ai_context", None)
            if self.ai_engine:
                ai_summary = ((getattr(context, "long_summary", "") or getattr(context, "short_summary", "") or getattr(context, "en_body", "")) if context else "")
                source_fallback = (getattr(publication, "metadata", {}) or {}).get("enrichment_mode") == "source_fallback"
                if not self._usable_content(publication.title, ai_summary) and not source_fallback:
                    failure_kind = getattr(self.provider, "last_failure_kind", None) or "unknown"
                    print("ai_enrichment_failed")
                    if failure_kind == "payment_required":
                        print("ai_provider_payment_required")
                    print("publication_blocked_empty_content")
                    raise ValueError("publication_blocked_empty_content")
            if context and (getattr(context, "short_summary", "") or getattr(context, "long_summary", "") or getattr(context, "headline_suggestions", ())):
                summary = getattr(context, "long_summary", "") or getattr(context, "short_summary", "")
                suggestions = getattr(context, "headline_suggestions", ()) or ()
                title = suggestions[0] if suggestions else publication.title
                if not self._valid_text(title, "en"):
                    title = publication.title if self._valid_text(publication.title, "en") else ""
                if not self._valid_text(summary, "en"):
                    summary = publication.summary if self._valid_text(publication.summary, "en") else ""
                translation = getattr(context, "translation", "") or ""
                ru_title = getattr(context, "ru_title", "") or ""
                ru_body = getattr(context, "ru_body", "") or ""
                variants = {lang: replace(v, title=(title if lang != "ru" else (ru_title or v.title)), summary=(summary if lang != "ru" else (ru_body or v.summary)), body=((v.body or summary or publication.summary) if lang != "ru" else (ru_body or v.body or v.summary))) for lang, v in publication.variants.items()}
                publication = replace(publication, title=title, summary=summary, variants=variants)
            en_variant = publication.variants.get("en")
            if not en_variant or not self._usable_content(en_variant.title, en_variant.summary or en_variant.body):
                print("publication_blocked_empty_content")
                raise ValueError("publication_blocked_empty_content")
        # Channel eligibility is evaluated after enrichment and variant
        # materialization, so RU eligibility can use the actual publication.
            has_ru_variant = "ru" in (getattr(publication, "variants", {}) or {})
            ai_succeeded = context is not None and bool(getattr(context, "confidence", 0) or getattr(context, "short_summary", "") or getattr(context, "long_summary", ""))
            channels = ChannelSelector().select(priority, window, audience, angle, publication.language, publication.category, ai_succeeded=ai_succeeded, has_ru_variant=has_ru_variant)
            en_variant = publication.variants.get("en")
            ru_variant = publication.variants.get("ru")
            en_ok = bool(en_variant and self._valid_text(en_variant.title, "en") and self._valid_text(en_variant.summary, "en"))
            ru_ok = bool(ru_variant and self._valid_text(ru_variant.title, "ru") and self._valid_text(ru_variant.body or ru_variant.summary, "ru"))
            channels = replace(channels, telegram_en=channels.telegram_en and en_ok, telegram_ru=channels.telegram_ru and ru_ok)
            if getattr(self.composition_root, "x_enabled", False) and getattr(self.composition_root, "x_publisher", None):
                channels = replace(channels, x=True)
            if getattr(self.composition_root, "linkedin_enabled", False) and getattr(self.composition_root, "linkedin_publisher", None):
                channels = replace(channels, linkedin=True)
            if getattr(self.composition_root, "medium_enabled", False) and getattr(self.composition_root, "medium_publisher", None):
                channels = replace(channels, medium=True)
            if getattr(self.composition_root, "substack_enabled", False) and getattr(self.composition_root, "substack_publisher", None):
                channels = replace(channels, substack=True)
            if getattr(self.composition_root, "devto_enabled", False) and getattr(self.composition_root, "devto_publisher", None):
                channels = replace(channels, devto=True)
            if getattr(self.composition_root, "hashnode_enabled", False) and getattr(self.composition_root, "hashnode_publisher", None):
                channels = replace(channels, hashnode=True)
            if getattr(self.composition_root, "reddit_enabled", False) and getattr(self.composition_root, "reddit_publisher", None):
                channels = replace(channels, reddit=True)
            self.selected_channels = channels
            self.delivery_selected_channels = channels
            self.channel_diagnostics = ChannelSelector().explain(
            priority, window, audience, angle, publication.language, publication.category,
            ai_succeeded=ai_succeeded, has_ru_variant=has_ru_variant,
        )
            stages["ai"] = "ok" if self.provider is not None or self.ai_engine is not None else "skipped"
            website_view = WebsiteRenderer("en").render(publication); telegram_view = TelegramRenderer("en", self.public_base_url).render(publication); telegram_ru_view = TelegramRenderer("ru", self.public_base_url).render(publication)
            x_view = XRenderer(self.public_base_url).render(publication) if getattr(self.composition_root, "x_enabled", False) and getattr(self.composition_root, "x_publisher", None) else None
            linkedin_view = LinkedInRenderer(self.public_base_url).render(publication) if getattr(self.composition_root, "linkedin_enabled", False) and getattr(self.composition_root, "linkedin_publisher", None) else None
            medium_view = MediumRenderer(self.public_base_url).render(publication) if getattr(self.composition_root, "medium_enabled", False) and getattr(self.composition_root, "medium_publisher", None) else None
            substack_view = SubstackRenderer(self.public_base_url).render(publication) if getattr(self.composition_root, "substack_enabled", False) and getattr(self.composition_root, "substack_publisher", None) else None
            devto_view = DevToRenderer(self.public_base_url, getattr(self.composition_root, "devto_publish", False), getattr(self.composition_root, "devto_organization_id", None)).render(publication) if getattr(self.composition_root, "devto_enabled", False) and getattr(self.composition_root, "devto_publisher", None) else None
            hashnode_view = HashnodeRenderer(self.public_base_url).render(publication, publish=getattr(self.composition_root, "hashnode_publish", False), publication_id=getattr(self.composition_root, "hashnode_publication_id", "")) if getattr(self.composition_root, "hashnode_enabled", False) and getattr(self.composition_root, "hashnode_publisher", None) else None
            reddit_view = RedditRenderer(self.public_base_url, getattr(self.composition_root, "reddit_subreddit", ""), getattr(self.composition_root, "reddit_post_kind", "self"), getattr(self.composition_root, "reddit_include_tracking", False), getattr(self.composition_root, "reddit_require_manual_rule_review", True)).render(publication) if getattr(self.composition_root, "reddit_enabled", False) and getattr(self.composition_root, "reddit_publisher", None) else None
            stages["render"] = "ok"
            if hasattr(self.delivery, "bindings"):
                scheduled = getattr(self.composition_root, "publish_at", None)
                bindings = [DestinationDelivery("website", self.delivery.website_publisher, website_view), DestinationDelivery("telegram_en", self.delivery.telegram_publisher, telegram_view, scheduled), DestinationDelivery("telegram_ru", self.delivery.telegram_publisher_ru or self.delivery.telegram_publisher, telegram_ru_view, scheduled)]
                if x_view is not None: bindings.append(DestinationDelivery("x", self.composition_root.x_publisher, x_view, scheduled))
                if linkedin_view is not None: bindings.append(DestinationDelivery("linkedin", self.composition_root.linkedin_publisher, linkedin_view, scheduled))
                if medium_view is not None: bindings.append(DestinationDelivery("medium", self.composition_root.medium_publisher, medium_view, scheduled))
                if substack_view is not None: bindings.append(DestinationDelivery("substack", self.composition_root.substack_publisher, substack_view, scheduled))
                if devto_view is not None: bindings.append(DestinationDelivery("devto", self.composition_root.devto_publisher, devto_view, scheduled))
                if hashnode_view is not None: bindings.append(DestinationDelivery("hashnode", self.composition_root.hashnode_publisher, hashnode_view, scheduled))
                if reddit_view is not None: bindings.append(DestinationDelivery("reddit", self.composition_root.reddit_publisher, reddit_view, scheduled))
                self.delivery.bindings = tuple(bindings)
            delivery_article_id = str(getattr(publication, "article_id", "") or getattr(publication, "publication_id", ""))
            delivery_url = str(getattr(publication, "canonical_url", "") or getattr(publication, "url", ""))
            skip_destinations = set()
            skip_reasons = {}
            if self.store is not None and hasattr(self.store, "prepare_delivery_attempt"):
                for destination in ("website", "telegram_en", "telegram_ru", "x", "linkedin", "medium", "substack", "devto", "hashnode", "reddit"):
                    if getattr(channels, destination, False):
                        if self.store.prepare_delivery_attempt(delivery_article_id, delivery_url, destination, self.pending_ttl_seconds, getattr(self.composition_root, "publish_at", None)) == "skip":
                            skip_destinations.add(destination)
                            rows = self.store.delivery_state(article_id=delivery_article_id, destination=destination) if hasattr(self.store, "delivery_state") else []
                            if rows:
                                state = rows[0].get("status")
                                skip_reasons[destination] = {"sent": "already_sent", "unknown": "unknown_terminal", "pending": "pending_not_stale"}.get(state, "already_sent")
                if hasattr(self.store, "delivery_state"):
                    current_states = {row["destination"]: row for row in (self.store.delivery_state(article_id=delivery_article_id) or [])}
                    self.delivery.bindings = tuple(replace(binding, attempt_number=int(current_states.get(binding.destination, {}).get("attempt_count", getattr(binding, "attempt_number", 1)))) for binding in self.delivery.bindings)
            report = await self.delivery.deliver(publication, DeliveryPlan(channels, window), website_view, telegram_view, telegram_ru_view, skip_destinations=skip_destinations, skip_reasons=skip_reasons)
            if skip_destinations and hasattr(self.store, "delivery_state"):
                restored = {}
                for destination in skip_destinations:
                    rows = self.store.delivery_state(article_id=delivery_article_id, destination=destination) or []
                    if rows:
                        row = rows[0]; restored[destination] = row
                        updated_statuses = {**(report.statuses or {}), destination: row["status"]}
                        report = replace(report, details={**(report.details or {}), destination: {"status": row["status"], "external_id": row["external_id"], "error": row["error"]}}, statuses=updated_statuses, website=(row["status"] if destination == "website" else report.website), telegram_en=(row["status"] if destination == "telegram_en" else report.telegram_en), telegram_ru=(row["status"] if destination == "telegram_ru" else report.telegram_ru))
            if report.website == "sent" and self.store is not None and hasattr(self.store, "append"):
                article_id = str(getattr(publication, "article_id", "") or getattr(publication, "publication_id", ""))
                article_url = str(getattr(publication, "canonical_url", "") or getattr(publication, "url", ""))
                already = bool(self.store.contains(article_id, article_url)) if hasattr(self.store, "contains") else False
                stored = None
                if not already:
                    stored = self.store.append(publication)
                if not already and stored is None:
                    report = replace(report, website="failed", overall="failed", failure_reasons={**(report.failure_reasons or {}), "website": "storage_failed"})
            if reservation and report.website == "sent":
                self.store.finalize_reservation(*reservation)
            elif reservation:
                self.store.release_reservation(*reservation)
            if immediate is not None and report.website == "sent":
                self.adaptive_scheduler.record_immediate_success()
            stages["delivery"] = report.overall
            if self.store is not None and hasattr(self.store, "record_delivery"):
                details = report.details or {}
                for destination in ("website", "telegram_en", "telegram_ru", "x", "linkedin", "medium", "substack", "devto", "hashnode", "reddit"):
                    if getattr(channels, destination, False):
                        detail = details.get(destination, {"status": (report.statuses or {}).get(destination, "blocked"), "error": (report.failure_reasons or {}).get(destination)})
                        if destination == "website":
                            detail = {**detail, "status": report.website, "error": (report.failure_reasons or {}).get(destination) or detail.get("error")}
                        saved = self.store.record_delivery(delivery_article_id, delivery_url, destination, detail.get("status", "failed"), detail.get("external_id"), detail.get("error") or None)
                        if saved:
                            rows = self.store.delivery_state(article_id=delivery_article_id, destination=destination) or []
                            if rows:
                                self._finalize_analytics(delivery_article_id, destination, rows[0])
            return ProductionRunResult(report, metrics.finish(), stages)
        except Exception:
            if reservation:
                self.store.release_reservation(*reservation)
            raise

    async def run(self, items):
        """Try ranked candidates in order, stopping after one successful publication."""
        candidates = self._published_filter(self._batch_deduplicate(items))
        if not candidates:
            raise ValueError("no new candidates")
        for candidate in candidates:
            candidate_id = str(getattr(candidate, "external_id", None) or (getattr(candidate, "payload", {}) or {}).get("id") or "")
            try:
                return await self._run_single(candidates, _candidate_override=candidate)
            except ValueError as exc:
                reason = str(exc)
                if reason in {"publication_blocked_empty_content", "candidate already reserved"}:
                    print(f"candidate_skipped_unusable_content={candidate_id}")
                    continue
                raise
        print("publication_result=no_usable_candidate")
        report = DeliveryReport("blocked", "blocked", "blocked", "blocked", failure_reasons={"publication": "no_usable_candidate"}, details={}, statuses={})
        return ProductionRunResult(report, PipelineMetricsCollector().finish(), {"delivery": "blocked"})
