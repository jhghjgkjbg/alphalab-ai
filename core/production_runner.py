from dataclasses import dataclass, replace
from core.pipeline_metrics import PipelineMetricsCollector
from core.publication.builder import PublicationBuilder
from core.editorial import (EditorialPlanner, FactExtractor, StoryAngleSelector, AudienceSelector, HeadlineEditor, SEOEditor, PublicationPrioritizer, PublicationWindowSelector, ChannelSelector)
from core.renderers.website import WebsiteRenderer
from core.renderers.telegram import TelegramRenderer
from core.delivery import DeliveryOrchestrator, DeliveryPlan, DeliveryReport


@dataclass(frozen=True)
class ProductionRunResult:
    delivery: DeliveryReport
    metrics: object
    stages: dict[str, str]


class ProductionRunner:
    def __init__(self, store=None, delivery=None, provider=None, composition_root=None, confirm_send=False):
        self.composition_root = composition_root
        self.store = store or getattr(composition_root, "articles_store", None)
        self.provider = provider or getattr(composition_root, "ai_provider", None)
        self.ai_engine = getattr(composition_root, "ai_enrichment_engine", None)
        self.delivery = delivery or getattr(composition_root, "delivery_orchestrator", None) or DeliveryOrchestrator(getattr(composition_root, "website_publisher", None), getattr(composition_root, "telegram_publisher_en", None), telegram_publisher_ru=getattr(composition_root, "telegram_publisher_ru", None))
        # DeliveryOrchestrator's flag denotes that confirmation is required;
        # the CLI flag supplies that confirmation.
        self.confirm_send = bool(confirm_send)
        self.delivery.confirm_send = self.confirm_send
        self.builder = getattr(composition_root, "builder", None) or PublicationBuilder()

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

    async def run(self, items):
        metrics = PipelineMetricsCollector(); stages = {}
        if not items: raise ValueError("no candidates")
        metrics.count("candidates_collected", len(items)); stages["collector"] = "ok"
        publication = self.builder.build(self._select_best_candidate(items)); stages["dedup"] = "ok"
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
        if context and (getattr(context, "short_summary", "") or getattr(context, "long_summary", "") or getattr(context, "headline_suggestions", ())):
            summary = getattr(context, "long_summary", "") or getattr(context, "short_summary", "")
            suggestions = getattr(context, "headline_suggestions", ()) or ()
            title = suggestions[0] if suggestions else publication.title
            translation = getattr(context, "translation", "") or ""
            ru_title = getattr(context, "ru_title", "") or ""
            ru_body = getattr(context, "ru_body", "") or ""
            variants = {lang: replace(v, title=(title if lang != "ru" else (ru_title or v.title)), summary=(summary if lang != "ru" else (ru_body or v.summary)), body=((v.body or summary or publication.summary) if lang != "ru" else (ru_body or v.body or v.summary))) for lang, v in publication.variants.items()}
            publication = replace(publication, title=title, summary=summary, variants=variants)
        # Channel eligibility is evaluated after enrichment and variant
        # materialization, so RU eligibility can use the actual publication.
        has_ru_variant = "ru" in (getattr(publication, "variants", {}) or {})
        ai_succeeded = context is not None and bool(getattr(context, "confidence", 0) or getattr(context, "short_summary", "") or getattr(context, "long_summary", ""))
        channels = ChannelSelector().select(priority, window, audience, angle, publication.language, publication.category, ai_succeeded=ai_succeeded, has_ru_variant=has_ru_variant)
        self.selected_channels = channels
        self.delivery_selected_channels = channels
        self.channel_diagnostics = ChannelSelector().explain(
            priority, window, audience, angle, publication.language, publication.category,
            ai_succeeded=ai_succeeded, has_ru_variant=has_ru_variant,
        )
        stages["ai"] = "ok" if self.provider is not None or self.ai_engine is not None else "skipped"
        website_view = WebsiteRenderer("en").render(publication); telegram_view = TelegramRenderer("en").render(publication); telegram_ru_view = TelegramRenderer("ru").render(publication)
        stages["render"] = "ok"
        report = await self.delivery.deliver(publication, DeliveryPlan(channels, window), website_view, telegram_view, telegram_ru_view)
        if report.website == "sent" and self.store is not None and hasattr(self.store, "append"):
            article_id = str(getattr(publication, "article_id", "") or getattr(publication, "publication_id", ""))
            article_url = str(getattr(publication, "canonical_url", "") or getattr(publication, "url", ""))
            try:
                already = bool(self.store.contains(article_id, article_url)) if hasattr(self.store, "contains") else False
            except Exception:
                raise
            stored = None
            if not already:
                stored = self.store.append(publication)
            if not already and stored is None:
                report = replace(report, website="failed", overall="failed", failure_reasons={**(report.failure_reasons or {}), "website": "storage_failed"})
        stages["delivery"] = report.overall
        return ProductionRunResult(report, metrics.finish(), stages)
