from dataclasses import dataclass

@dataclass(frozen=True)
class DistributionDestinationSummary:
    destination: str
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0
    unknown: int = 0
    deferred: int = 0
    skipped: int = 0
    success_rate: float | None = None
    remote_publications: int = 0

@dataclass(frozen=True)
class DistributionSummary:
    destinations: tuple[DistributionDestinationSummary, ...]

@dataclass(frozen=True)
class GrowthSummary:
    campaign_id: str | None
    by_destination: tuple[tuple[str, int], ...]
    by_link: tuple[tuple[str, int], ...]
    by_provider: tuple[tuple[str, int], ...]
    visits: int
    subscription_started: int
    subscription_confirmed: int
    subscription_cancelled: int
    unique_anonymous_ids: int
    unique_subscriber_ids: int

@dataclass(frozen=True)
class FunnelSummary:
    campaign_id: str
    visits: int
    started: int
    confirmed: int
    visit_to_started: float | None
    started_to_confirmed: float | None
    visit_to_confirmed: float | None
