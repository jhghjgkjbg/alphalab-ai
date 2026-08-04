from .builder import PublicationBuilder
from .engine import ScoredPublicationEngine

class PublicationCompositionRoot:
    """Explicit dependency assembly for publication delivery."""
    def __init__(self, *, publisher, renderer=None, minimum_score=0.0, top_n=10, dry_run=False, memory=None, articles_store=None, builder=None, editorial_engine=None, channel_policy=None, quality_engine=None, ranking_engine=None, metrics_engine=None, ai_enrichment_engine=None, website_renderer=None, telegram_renderer=None, website_publisher=None, telegram_publisher_en=None, telegram_publisher_ru=None, x_publisher=None, x_enabled=False, linkedin_publisher=None, linkedin_enabled=False, medium_publisher=None, medium_enabled=False, substack_publisher=None, substack_enabled=False, substack_audience="everyone", substack_publication_url="", devto_publisher=None, devto_enabled=False, devto_publish=False, devto_organization_id=None, hashnode_publisher=None, hashnode_enabled=False, reddit_publisher=None, reddit_enabled=False, provider_registry=None, selected_provider=None, delivery_orchestrator=None, language_variant_engine=None):
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
        self.x_publisher = x_publisher
        self.x_enabled = bool(x_enabled)
        self.linkedin_publisher = linkedin_publisher
        self.linkedin_enabled = bool(linkedin_enabled)
        self.medium_publisher, self.medium_enabled = medium_publisher, bool(medium_enabled)
        self.substack_publisher, self.substack_enabled = substack_publisher, bool(substack_enabled)
        self.substack_audience = substack_audience; self.substack_publication_url = substack_publication_url
        self.devto_publisher, self.devto_enabled = devto_publisher, bool(devto_enabled)
        self.devto_publish, self.devto_organization_id = bool(devto_publish), devto_organization_id
        self.hashnode_publisher, self.hashnode_enabled = hashnode_publisher, bool(hashnode_enabled)
        self.hashnode_publish = bool(getattr(hashnode_publisher, "publish_mode", False))
        self.hashnode_publication_id = getattr(hashnode_publisher, "publication_id", "")
        self.reddit_publisher, self.reddit_enabled = reddit_publisher, bool(reddit_enabled)
        self.reddit_subreddit = getattr(reddit_publisher, "subreddit", "")
        self.reddit_post_kind = getattr(reddit_publisher, "post_kind", "self")
        self.reddit_include_tracking = getattr(reddit_publisher, "include_tracking", False)
        self.reddit_require_manual_rule_review = True
        self.publish_at = None
        self.delivery_orchestrator = delivery_orchestrator
        self.destinations = {"website": self.website_publisher, "telegram_en": self.telegram_publisher_en, "telegram_ru": self.telegram_publisher_ru}
        self.telegram_publisher = self.telegram_publisher_en
        self.editorial_engine = editorial_engine
        self.engine = ScoredPublicationEngine(publisher, minimum_score, top_n, dry_run, memory, articles_store, publication_builder=self.builder, renderer=self.renderer, editorial_engine=editorial_engine, channel_policy=channel_policy, quality_engine=quality_engine, ranking_engine=ranking_engine, metrics_engine=metrics_engine, ai_enrichment_engine=ai_enrichment_engine, website_renderer=website_renderer, telegram_renderer=telegram_renderer, website_publisher=website_publisher, language_variant_engine=language_variant_engine)

    def build(self):
        return self.engine

    @classmethod
    def from_settings(cls, settings, reddit_remote_transport=None):
        """Assemble the shared production graph from the configured Settings."""
        from core.ai_enrichment import AIEnrichmentEngine, AIProviderRegistry
        from core.ai_enrichment.engine import NoOpAIProvider
        from core.ai_enrichment.providers.openrouter import OpenRouterProvider
        from core.ai_enrichment.providers.openai import OpenAIProvider
        from core.language_variants import LanguageVariantEngine
        from core.renderers import WebsiteRenderer, TelegramRenderer
        from core.publishers.website import WebsitePublisher
        from core.publishers.hashnode import HashnodePublisher
        from core.publishers.reddit import RedditDraftPublisher
        from core.publishers.reddit_remote import RedditRemotePublisher, RedditBridgeHttpTransport
        from core.publishers.telegram import TelegramViewPublisher
        from core.delivery import DeliveryOrchestrator
        from core.storage import SQLitePublishedArticlesStore
        from core.analytics import DistributionEventStore
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
        async def x_request(url, payload, timeout_seconds, headers):
            import httpx
            async with httpx.AsyncClient(timeout=timeout_seconds, headers=headers) as client:
                return await client.post(url, json=dict(payload))
        import importlib
        TelegramClient = importlib.import_module("agents.ai_scout.publishers.telegram_client").TelegramClient
        retry = dict(max_attempts=getattr(settings, "telegram_max_attempts", 3), retry_base_seconds=getattr(settings, "telegram_retry_base_seconds", 1.0), retry_max_seconds=getattr(settings, "telegram_retry_max_seconds", 15.0))
        import os
        try: telegram_timeout = float(os.getenv("TELEGRAM_REQUEST_TIMEOUT_SECONDS", getattr(settings, "telegram_request_timeout_seconds", 3)))
        except (TypeError, ValueError): telegram_timeout = 3.0
        if telegram_timeout <= 0: telegram_timeout = 3.0
        en_client = TelegramClient(str(getattr(settings, "telegram_bot_token", "")), str(getattr(settings, "telegram_en_chat_id", "")), telegram_timeout, request, **retry)
        ru_client = TelegramClient(str(getattr(settings, "telegram_bot_token", "")), str(getattr(settings, "telegram_ru_chat_id", "")), telegram_timeout, request, **retry)
        en_publisher, ru_publisher = TelegramViewPublisher(en_client), TelegramViewPublisher(ru_client)
        analytics_store = DistributionEventStore()
        delivery = DeliveryOrchestrator(website_publisher, en_publisher, telegram_publisher_ru=ru_publisher, analytics_store=analytics_store)
        x_publisher = None
        x_enabled = bool(getattr(settings, "x_enabled", False))
        if x_enabled:
            token = str(getattr(settings, "x_bearer_token", "") or "")
            if not token: raise ValueError("missing X bearer token")
            from core.publishers.x import XPublisher
            x_publisher = XPublisher(token, x_request, getattr(settings, "x_api_base_url", "https://api.x.com"), getattr(settings, "x_request_timeout_seconds", 10))
        linkedin_publisher = None
        linkedin_enabled = bool(getattr(settings, "linkedin_enabled", False))
        if linkedin_enabled:
            token = str(getattr(settings, "linkedin_access_token", "") or "")
            author = str(getattr(settings, "linkedin_author_urn", "") or "")
            if not token: raise ValueError("missing LinkedIn access token")
            if not author: raise ValueError("missing LinkedIn author URN")
            from core.publishers.linkedin import LinkedInPublisher
            linkedin_publisher = LinkedInPublisher(token, author, x_request, getattr(settings, "linkedin_api_base_url", "https://api.linkedin.com"), getattr(settings, "linkedin_api_version", "202601"), getattr(settings, "linkedin_request_timeout_seconds", 10))
        medium_publisher = None
        medium_enabled = bool(getattr(settings, "medium_enabled", False))
        if medium_enabled:
            token = str(getattr(settings, "medium_integration_token", "") or "")
            author = str(getattr(settings, "medium_author_id", "") or "")
            status = str(getattr(settings, "medium_publish_status", "draft"))
            if not token: raise ValueError("missing Medium integration token")
            if not author: raise ValueError("missing Medium author ID")
            if status not in {"draft", "public", "unlisted"}: raise ValueError("invalid Medium publish status")
            from core.publishers.medium import MediumPublisher
            medium_publisher = MediumPublisher(token, author, x_request, getattr(settings, "medium_api_base_url", "https://api.medium.com"), getattr(settings, "medium_request_timeout_seconds", 10), status)
        substack_publisher = None
        substack_enabled = bool(getattr(settings, "substack_enabled", False))
        if substack_enabled:
            audience = str(getattr(settings, "substack_default_audience", "everyone"))
            if audience not in {"everyone", "free", "paid"}: raise ValueError("invalid Substack audience")
            from core.publishers.substack import SubstackDraftPublisher
            substack_publisher = SubstackDraftPublisher(getattr(settings, "substack_outbox_directory", "runtime/substack_outbox"))
        devto_publisher = None; devto_enabled = bool(getattr(settings, "devto_enabled", False))
        if devto_enabled:
            key=str(getattr(settings,"devto_api_key","") or "")
            if not key: raise ValueError("missing Dev.to API key")
            org=getattr(settings,"devto_organization_id",None)
            if org is not None and int(org)<=0: raise ValueError("invalid Dev.to organization ID")
            from core.publishers.devto import DevToPublisher
            devto_publisher=DevToPublisher(key,x_request,getattr(settings,"devto_api_base_url","https://dev.to"),getattr(settings,"devto_request_timeout_seconds",10))
        hashnode_enabled = bool(getattr(settings, "hashnode_enabled", False)); hashnode_publisher = None
        if hashnode_enabled:
            token = str(getattr(settings, "hashnode_personal_access_token", "") or "")
            publication_id = str(getattr(settings, "hashnode_publication_id", "") or "")
            if not token or not publication_id or not bool(getattr(settings, "hashnode_require_pro", True)):
                raise ValueError("invalid Hashnode configuration")
            hashnode_publisher = HashnodePublisher(token, publication_id, x_request, getattr(settings, "hashnode_api_url", "https://gql-beta.hashnode.com/"), getattr(settings, "hashnode_request_timeout_seconds", 10), getattr(settings, "hashnode_publish", False))
        reddit_enabled=bool(getattr(settings,"reddit_enabled",False)); reddit_publisher=None
        if reddit_enabled:
            from core.renderers.reddit import normalize_subreddit
            subreddit=normalize_subreddit(getattr(settings,"reddit_subreddit","")); kind=getattr(settings,"reddit_post_kind","self")
            if kind not in {"self","link"}: raise ValueError("reddit_invalid_post_kind")
            mode = str(getattr(settings, "reddit_mode", "draft_export"))
            if mode == "remote_publish":
                transport = reddit_remote_transport or RedditBridgeHttpTransport(getattr(settings, "reddit_devvit_endpoint", ""), getattr(settings, "reddit_bridge_token", ""), getattr(settings, "reddit_http_timeout_seconds", 10))
                reddit_publisher = RedditRemotePublisher(transport)
            else:
                reddit_publisher=RedditDraftPublisher(getattr(settings,"reddit_outbox_directory","runtime/reddit_outbox"), subreddit, kind, getattr(settings,"reddit_include_tracking",False), getattr(settings,"reddit_require_manual_rule_review",True))
        store = SQLitePublishedArticlesStore()
        root = cls(publisher=en_publisher, renderer=telegram_renderer, articles_store=store, ai_enrichment_engine=ai_engine, provider_registry=registry, selected_provider=provider, website_renderer=website_renderer, telegram_renderer=telegram_renderer, website_publisher=website_publisher, telegram_publisher_en=en_publisher, telegram_publisher_ru=ru_publisher, x_publisher=x_publisher, x_enabled=x_enabled, linkedin_publisher=linkedin_publisher, linkedin_enabled=linkedin_enabled, medium_publisher=medium_publisher, medium_enabled=medium_enabled, substack_publisher=substack_publisher, substack_enabled=substack_enabled, substack_audience=getattr(settings, "substack_default_audience", "everyone"), substack_publication_url=getattr(settings, "substack_publication_url", ""), devto_publisher=devto_publisher, devto_enabled=devto_enabled, devto_publish=getattr(settings, "devto_publish", False), devto_organization_id=getattr(settings, "devto_organization_id", None), hashnode_publisher=hashnode_publisher, hashnode_enabled=hashnode_enabled, reddit_publisher=reddit_publisher, reddit_enabled=reddit_enabled, delivery_orchestrator=delivery, language_variant_engine=LanguageVariantEngine())
        root.publish_at = getattr(settings, "publish_at", None)
        return root

def build_publication_engine(*, publisher, renderer, **kwargs):
    return PublicationCompositionRoot(publisher=publisher, renderer=renderer, **kwargs).build()
