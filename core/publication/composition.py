from .builder import PublicationBuilder
from .engine import ScoredPublicationEngine

class PublicationCompositionRoot:
    """Explicit dependency assembly for publication delivery."""
    def __init__(self, *, publisher, renderer=None, minimum_score=0.0, top_n=10, dry_run=False, memory=None, articles_store=None, builder=None, editorial_engine=None, channel_policy=None, quality_engine=None, ranking_engine=None, metrics_engine=None, ai_enrichment_engine=None, website_renderer=None, telegram_renderer=None, website_publisher=None, telegram_publisher_en=None, telegram_publisher_ru=None, provider_registry=None, selected_provider=None, delivery_orchestrator=None, language_variant_engine=None):
        self.builder = builder or PublicationBuilder()
        self.renderer = renderer
        self.publisher = publisher
        self.articles_store = articles_store
        self.sqlite_publication_store = articles_store
        self.ai_enrichment_engine = ai_enrichment_engine
        self.provider_registry = provider_registry
        self.selected_provider = selected_provider
        self.website_renderer = website_renderer
        self.telegram_renderer = telegram_renderer
        self.website_publisher = website_publisher
        self.telegram_publisher_en = telegram_publisher_en or publisher
        self.telegram_publisher_ru = telegram_publisher_ru
        self.delivery_orchestrator = delivery_orchestrator
        self.telegram_publisher = self.telegram_publisher_en
        self.editorial_engine = editorial_engine
        self.engine = ScoredPublicationEngine(publisher, minimum_score, top_n, dry_run, memory, articles_store, publication_builder=self.builder, renderer=self.renderer, editorial_engine=editorial_engine, channel_policy=channel_policy, quality_engine=quality_engine, ranking_engine=ranking_engine, metrics_engine=metrics_engine, ai_enrichment_engine=ai_enrichment_engine, website_renderer=website_renderer, telegram_renderer=telegram_renderer, website_publisher=website_publisher, language_variant_engine=language_variant_engine)

    def build(self):
        return self.engine

    @classmethod
    def from_settings(cls, settings):
        """Assemble the shared production graph from the configured Settings."""
        from core.ai_enrichment import AIEnrichmentEngine, AIProviderRegistry
        from core.ai_enrichment.engine import NoOpAIProvider
        from core.ai_enrichment.providers.openrouter import OpenRouterProvider
        from core.ai_enrichment.providers.openai import OpenAIProvider
        from core.language_variants import LanguageVariantEngine
        from core.renderers import WebsiteRenderer, TelegramRenderer
        from core.publishers.website import WebsitePublisher
        from core.publishers.telegram import TelegramViewPublisher
        from core.delivery import DeliveryOrchestrator
        from core.storage import SQLitePublishedArticlesStore
        registry = AIProviderRegistry(default="noop")
        provider = NoOpAIProvider(); registry.register("noop", provider)
        name = str(getattr(settings, "ai_provider", "noop") or "noop").lower()
        enabled = bool(getattr(settings, "ai_enabled", False))
        if enabled and name == "openrouter":
            from openai import OpenAI
            key = str(getattr(settings, "openrouter_api_key", "") or "")
            if not key: raise ValueError("missing OpenRouter API key")
            provider = OpenRouterProvider(key, settings.openrouter_model, OpenAI(api_key=key, base_url=settings.openrouter_base_url, timeout=settings.openrouter_timeout_seconds, max_retries=settings.openrouter_max_retries), settings.openrouter_max_output_tokens)
            registry.register(name, provider); registry._default = name
        elif enabled and name == "openai":
            from openai import OpenAI
            key = str(getattr(settings, "openai_api_key", "") or "")
            if not key: raise ValueError("missing OpenAI API key")
            provider = OpenAIProvider(key, settings.openai_model, OpenAI(api_key=key, timeout=settings.openai_timeout_seconds, max_retries=settings.openai_max_retries), settings.openai_max_output_tokens)
            registry.register(name, provider); registry._default = name
        ai_engine = AIEnrichmentEngine(registry=registry)
        website_renderer = WebsiteRenderer("en")
        telegram_renderer = TelegramRenderer("en")
        website_publisher = WebsitePublisher(lambda view: True)
        async def request(url, payload, timeout_seconds):
            import httpx
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                return await client.post(url, json=dict(payload))
        import importlib
        TelegramClient = importlib.import_module("agents.ai_scout.publishers.telegram_client").TelegramClient
        en_client = TelegramClient(str(getattr(settings, "telegram_bot_token", "")), str(getattr(settings, "telegram_en_chat_id", "")), 3, request)
        ru_client = TelegramClient(str(getattr(settings, "telegram_bot_token", "")), str(getattr(settings, "telegram_ru_chat_id", "")), 3, request)
        en_publisher, ru_publisher = TelegramViewPublisher(en_client), TelegramViewPublisher(ru_client)
        delivery = DeliveryOrchestrator(website_publisher, en_publisher, telegram_publisher_ru=ru_publisher)
        store = SQLitePublishedArticlesStore()
        return cls(publisher=en_publisher, renderer=telegram_renderer, articles_store=store, ai_enrichment_engine=ai_engine, provider_registry=registry, selected_provider=provider, website_renderer=website_renderer, telegram_renderer=telegram_renderer, website_publisher=website_publisher, telegram_publisher_en=en_publisher, telegram_publisher_ru=ru_publisher, delivery_orchestrator=delivery, language_variant_engine=LanguageVariantEngine())

def build_publication_engine(*, publisher, renderer, **kwargs):
    return PublicationCompositionRoot(publisher=publisher, renderer=renderer, **kwargs).build()
