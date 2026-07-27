from typing import Literal
from datetime import datetime, UTC

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    publish_at: datetime | None = Field(default=None, validation_alias=AliasChoices("ALPHALAB_PUBLISH_AT", "publish_at"))

    @field_validator("publish_at")
    @classmethod
    def _publish_at_must_be_aware(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("publish_at must include timezone offset")
        return value.astimezone(UTC) if value is not None else None
    public_base_url: str = Field(default="https://alphalabai.online", validation_alias=AliasChoices("ALPHALAB_PUBLIC_BASE_URL", "PUBLIC_BASE_URL", "public_base_url"))
    telegram_max_attempts: int = Field(default=3, validation_alias=AliasChoices("ALPHALAB_TELEGRAM_MAX_ATTEMPTS", "TELEGRAM_MAX_ATTEMPTS", "telegram_max_attempts"))
    telegram_retry_base_seconds: float = Field(default=1.0, validation_alias=AliasChoices("ALPHALAB_TELEGRAM_RETRY_BASE_SECONDS", "TELEGRAM_RETRY_BASE_SECONDS", "telegram_retry_base_seconds"))
    telegram_retry_max_seconds: float = Field(default=15.0, validation_alias=AliasChoices("ALPHALAB_TELEGRAM_RETRY_MAX_SECONDS", "TELEGRAM_RETRY_MAX_SECONDS", "telegram_retry_max_seconds"))
    x_enabled: bool = Field(default=False, validation_alias=AliasChoices("ALPHALAB_X_ENABLED", "x_enabled"))
    x_bearer_token: str = Field(default="", validation_alias=AliasChoices("ALPHALAB_X_BEARER_TOKEN", "x_bearer_token"))
    x_api_base_url: str = Field(default="https://api.x.com", validation_alias=AliasChoices("ALPHALAB_X_API_BASE_URL", "x_api_base_url"))
    x_request_timeout_seconds: int = Field(default=10, validation_alias=AliasChoices("ALPHALAB_X_REQUEST_TIMEOUT_SECONDS", "x_request_timeout_seconds"))
    linkedin_enabled: bool = Field(default=False, validation_alias=AliasChoices("ALPHALAB_LINKEDIN_ENABLED", "linkedin_enabled"))
    linkedin_access_token: str = Field(default="", validation_alias=AliasChoices("ALPHALAB_LINKEDIN_ACCESS_TOKEN", "linkedin_access_token"))
    linkedin_author_urn: str = Field(default="", validation_alias=AliasChoices("ALPHALAB_LINKEDIN_AUTHOR_URN", "linkedin_author_urn"))
    linkedin_api_base_url: str = Field(default="https://api.linkedin.com", validation_alias=AliasChoices("ALPHALAB_LINKEDIN_API_BASE_URL", "linkedin_api_base_url"))
    linkedin_api_version: str = Field(default="202601", validation_alias=AliasChoices("ALPHALAB_LINKEDIN_API_VERSION", "linkedin_api_version"))
    linkedin_request_timeout_seconds: int = Field(default=10, validation_alias=AliasChoices("ALPHALAB_LINKEDIN_REQUEST_TIMEOUT_SECONDS", "linkedin_request_timeout_seconds"))
    medium_enabled: bool = Field(default=False, validation_alias=AliasChoices("ALPHALAB_MEDIUM_ENABLED", "medium_enabled"))
    medium_integration_token: str = Field(default="", validation_alias=AliasChoices("ALPHALAB_MEDIUM_INTEGRATION_TOKEN", "medium_integration_token"))
    medium_author_id: str = Field(default="", validation_alias=AliasChoices("ALPHALAB_MEDIUM_AUTHOR_ID", "medium_author_id"))
    medium_api_base_url: str = Field(default="https://api.medium.com", validation_alias=AliasChoices("ALPHALAB_MEDIUM_API_BASE_URL", "medium_api_base_url"))
    medium_request_timeout_seconds: int = Field(default=10, validation_alias=AliasChoices("ALPHALAB_MEDIUM_REQUEST_TIMEOUT_SECONDS", "medium_request_timeout_seconds"))
    medium_publish_status: str = Field(default="draft", validation_alias=AliasChoices("ALPHALAB_MEDIUM_PUBLISH_STATUS", "medium_publish_status"))
    substack_enabled: bool = Field(default=False, validation_alias=AliasChoices("ALPHALAB_SUBSTACK_ENABLED", "substack_enabled"))
    substack_outbox_directory: str = Field(default="runtime/substack_outbox", validation_alias=AliasChoices("ALPHALAB_SUBSTACK_OUTBOX_DIRECTORY", "substack_outbox_directory"))
    substack_publication_url: str = Field(default="", validation_alias=AliasChoices("ALPHALAB_SUBSTACK_PUBLICATION_URL", "substack_publication_url"))
    substack_default_audience: str = Field(default="everyone", validation_alias=AliasChoices("ALPHALAB_SUBSTACK_DEFAULT_AUDIENCE", "substack_default_audience"))
    devto_enabled: bool = Field(default=False, validation_alias=AliasChoices("ALPHALAB_DEVTO_ENABLED", "devto_enabled"))
    devto_api_key: str = Field(default="", validation_alias=AliasChoices("ALPHALAB_DEVTO_API_KEY", "devto_api_key"))
    devto_api_base_url: str = Field(default="https://dev.to", validation_alias=AliasChoices("ALPHALAB_DEVTO_API_BASE_URL", "devto_api_base_url"))
    devto_request_timeout_seconds: int = Field(default=10, validation_alias=AliasChoices("ALPHALAB_DEVTO_REQUEST_TIMEOUT_SECONDS", "devto_request_timeout_seconds"))
    devto_publish: bool = Field(default=False, validation_alias=AliasChoices("ALPHALAB_DEVTO_PUBLISH", "devto_publish"))
    devto_organization_id: int | None = Field(default=None, validation_alias=AliasChoices("ALPHALAB_DEVTO_ORGANIZATION_ID", "devto_organization_id"))
    hashnode_enabled: bool = Field(default=False, validation_alias=AliasChoices("ALPHALAB_HASHNODE_ENABLED", "hashnode_enabled"))
    hashnode_personal_access_token: str = Field(default="", repr=False, validation_alias=AliasChoices("ALPHALAB_HASHNODE_PERSONAL_ACCESS_TOKEN", "hashnode_personal_access_token"))
    hashnode_publication_id: str = Field(default="", validation_alias=AliasChoices("ALPHALAB_HASHNODE_PUBLICATION_ID", "hashnode_publication_id"))
    hashnode_api_url: str = Field(default="https://gql-beta.hashnode.com/", validation_alias=AliasChoices("ALPHALAB_HASHNODE_API_URL", "hashnode_api_url"))
    hashnode_request_timeout_seconds: int = Field(default=10, validation_alias=AliasChoices("ALPHALAB_HASHNODE_REQUEST_TIMEOUT_SECONDS", "hashnode_request_timeout_seconds"))
    hashnode_publish: bool = Field(default=False, validation_alias=AliasChoices("ALPHALAB_HASHNODE_PUBLISH", "hashnode_publish"))
    hashnode_require_pro: bool = Field(default=True, validation_alias=AliasChoices("ALPHALAB_HASHNODE_REQUIRE_PRO", "hashnode_require_pro"))
    reddit_enabled: bool = Field(default=False, validation_alias=AliasChoices("ALPHALAB_REDDIT_ENABLED", "reddit_enabled"))
    reddit_outbox_directory: str = Field(default="runtime/reddit_outbox", validation_alias=AliasChoices("ALPHALAB_REDDIT_OUTBOX_DIRECTORY", "reddit_outbox_directory"))
    reddit_subreddit: str = Field(default="", validation_alias=AliasChoices("ALPHALAB_REDDIT_SUBREDDIT", "reddit_subreddit"))
    reddit_post_kind: str = Field(default="self", validation_alias=AliasChoices("ALPHALAB_REDDIT_POST_KIND", "reddit_post_kind"))
    reddit_include_tracking: bool = Field(default=False, validation_alias=AliasChoices("ALPHALAB_REDDIT_INCLUDE_TRACKING", "reddit_include_tracking"))
    reddit_require_manual_rule_review: bool = Field(default=True, validation_alias=AliasChoices("ALPHALAB_REDDIT_REQUIRE_MANUAL_RULE_REVIEW", "reddit_require_manual_rule_review"))
    app_name: str = "AlphaLab AI"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    telegram_bot_token: str | None = Field(default=None, validation_alias=AliasChoices("ALPHALAB_TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN", "telegram_bot_token"))
    telegram_chat_id: str | None = Field(default=None, validation_alias=AliasChoices("ALPHALAB_TELEGRAM_CHAT_ID", "TELEGRAM_CHAT_ID", "telegram_chat_id"))
    telegram_en_chat_id: str | None = Field(default=None, validation_alias=AliasChoices("ALPHALAB_TELEGRAM_EN_CHAT_ID", "TELEGRAM_EN_CHAT_ID", "telegram_en_chat_id"))
    telegram_ru_chat_id: str | None = Field(default=None, validation_alias=AliasChoices("ALPHALAB_TELEGRAM_RU_CHAT_ID", "TELEGRAM_RU_CHAT_ID", "telegram_ru_chat_id"))
    telegram_parse_mode: str | None = None
    github_token: str | None = None
    github_timeout: float = 10.0
    github_max_items: int = 10
    reddit_subreddit: str = "technology"
    reddit_limit: int = 10
    reddit_timeout: float = 10.0
    hacker_news_max_items: int = 10
    hacker_news_timeout: float = 5.0
    product_hunt_token: str | None = None
    product_hunt_timeout: float = 10.0
    product_hunt_max_items: int = 10
    devto_timeout: float = 10.0
    devto_max_items: int = 10
    devto_tag: str | None = None
    lobsters_timeout: float = 10.0
    lobsters_max_items: int = 10
    arxiv_timeout: float = 10.0
    arxiv_max_items: int = 10
    arxiv_search_query: str = "all:AI"
    gemini_api_key: str | None = Field(default=None, validation_alias=AliasChoices("ALPHALAB_GEMINI_API_KEY", "GEMINI_API_KEY", "gemini_api_key"))
    gemini_model: str = Field(default="gemini-1.5-flash", validation_alias=AliasChoices("ALPHALAB_GEMINI_MODEL", "GEMINI_MODEL", "gemini_model"))
    gemini_timeout: float = Field(default=30.0, validation_alias=AliasChoices("ALPHALAB_GEMINI_TIMEOUT", "GEMINI_TIMEOUT", "gemini_timeout"))
    openrouter_api_key: str | None = None
    openrouter_model: str = "deepseek/deepseek-chat-v3"
    openrouter_timeout: float = 30.0
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_device: str = "cpu"
    embedding_batch_size: int = 32
    embedding_normalize: bool = True
    similarity_threshold: float = 0.7
    similarity_top_k: int = 10
    ranking_batch_size: int = 16
    ranking_max_items: int = 100
    ranking_weights: str = "relevance=.25,novelty=.25,technical=.25,business=.25"
    ranking_min_score: float = 0.0
    publication_min_score: float = 50.0
    publication_top_n: int = 10
    publication_dry_run: bool = True
    source_interval_seconds: float = 300.0
    hacker_news_enabled: bool = True
    rss_enabled: bool = False
    github_enabled: bool = False
    reddit_enabled: bool = False
    product_hunt_enabled: bool = False
    devto_enabled: bool = False
    lobsters_enabled: bool = False
    arxiv_enabled: bool = False
    pre_ai_filter_enabled: bool = True
    pre_ai_max_candidates: int = 5
    pre_ai_exploration_slots: int = 1
    max_editorial_ai_calls_per_run: int = 5
    editorial_cache_ttl_hours: float = 168.0
    editorial_cost_mode: Literal["off", "economy", "standard"] = "standard"
    editorial_max_input_chars: int = 6000
    editorial_max_output_tokens: int = 700
    schedule_interval_minutes: int = 30
    scheduler_max_consecutive_failures: int = 5
    publication_history_ttl_hours: int = 168
    quality_scoring_weights: str = "importance=.30,verdict=.20,ranking=.15,freshness=.10,source=.10,popularity=.05,similarity=.05,category=.05"
    source_reputation: str = "hacker_news=1.0,github=.98,arxiv=.97,lobsters=.94,devto=.90,rss=.85"
    category_bonus: str = "AI=1.0,Open Source=1.0,LLM=1.0,Programming=.8,Research=.9"
    telegram_en_enabled: bool = True
    telegram_en_bot_token: str | None = None
    telegram_ru_enabled: bool = False
    telegram_ru_bot_token: str | None = None
    ru_translation_enabled: bool = False
    ru_translation_cache_ttl_hours: int = 720
    source_reputation_enabled: bool = True
    source_reputation_default: float = .60
    source_reputation_overrides: str = "openai=1.0,anthropic=.98,deepmind=.98,google=.96,microsoft=.95,github=.93,arxiv=.92,producthunt=.80,devto=.70,hacker_news=.65,lobsters=.60,reddit=.50"
    analytics_enabled: bool = True
    trend_boost_enabled: bool = True
    trend_similarity: float = .85
    api_enabled: bool = True
    api_max_records: int = 10000
    storage_backend: Literal["sqlite", "json"] = "sqlite"
    publication_model: bool = True
    renderer_layer: bool = False
    website_publisher: bool = False
    language_variants: bool = False
    publisher_layer: bool = True
    editorial_rules: bool = True
    channel_policy: bool = False
    quality_scoring: bool = False
    ranking_engine: bool = False
    metrics_engine: bool = False
    ai_layer: bool = True
    ai_provider: str = "noop"
    ai_enabled: bool = False
    openai_model: str = "gpt-4.1-mini"
    # OpenAI's standard environment variable is intentionally unprefixed.
    # The value is still exposed through the centralized Settings object.
    openai_api_key: str = Field(default="", validation_alias=AliasChoices("ALPHALAB_OPENAI_API_KEY", "OPENAI_API_KEY", "openai_api_key"))
    openai_timeout_seconds: int = 30
    openai_max_retries: int = 2
    openai_max_output_tokens: int = 1200
    openrouter_api_key: str = Field(default="", validation_alias=AliasChoices("ALPHALAB_OPENROUTER_API_KEY", "OPENROUTER_API_KEY", "openrouter_api_key"))
    openrouter_model: str = Field(default="deepseek/deepseek-chat-v3", validation_alias=AliasChoices("ALPHALAB_OPENROUTER_MODEL", "OPENROUTER_MODEL", "openrouter_model"))
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_timeout_seconds: int = Field(default=30, validation_alias=AliasChoices("ALPHALAB_OPENROUTER_TIMEOUT", "OPENROUTER_TIMEOUT", "openrouter_timeout_seconds"))
    openrouter_max_retries: int = 2
    openrouter_max_output_tokens: int = 1200
    openrouter_site_url: str = ""
    openrouter_app_name: str = "AlphaLab AI"
    prompt_pipeline: bool = True
    prompt_version: str = "v1"
    ai_task_engine: bool = True
    editorial_engine: bool = False
    response_parser: bool = True
    website_enabled: bool = True
    website_host: str = "127.0.0.1"
    website_port: int = 8080
    website_page_size: int = 20

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ALPHALAB_",
        extra="ignore",
    )
