import json
from collections import Counter
from .models import DistributionDestinationSummary, DistributionSummary, GrowthSummary, FunnelSummary

class ReportingService:
    """Read-only projections over the existing append-only event stores."""
    def __init__(self, distribution_store, growth_store):
        self.distribution_store = distribution_store
        self.growth_store = growth_store

    def _distribution_rows(self, article_id=None):
        db = self.distribution_store.database
        with db.connect() as c:
            if article_id is None:
                return [dict(r) for r in c.execute("SELECT * FROM distribution_events ORDER BY destination_id,occurred_at,event_id")]
            return [dict(r) for r in c.execute("SELECT * FROM distribution_events WHERE article_id=? ORDER BY destination_id,occurred_at,event_id", (str(article_id),))]

    def _growth_rows(self, campaign_id=None):
        db = self.growth_store.database
        with db.connect() as c:
            if campaign_id is None:
                return [dict(r) for r in c.execute("SELECT * FROM growth_events ORDER BY occurred_at,event_id")]
            return [dict(r) for r in c.execute("SELECT * FROM growth_events WHERE campaign_id=? ORDER BY occurred_at,event_id", (str(campaign_id),))]

    @staticmethod
    def _metadata(row):
        try:
            value = json.loads(row.get("metadata_json") or "{}")
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}

    def distribution_summary(self, article_id=None):
        grouped = {}
        for row in self._distribution_rows(article_id):
            destination = str(row.get("destination_id") or "")
            item = grouped.setdefault(destination, Counter())
            kind = str(row.get("event_type") or "")
            item[kind.removeprefix("delivery_")] += 1
            metadata = self._metadata(row)
            if kind == "delivery_succeeded" and metadata.get("remote_publication_performed") is not False:
                item["remote_publications"] += 1
        result = []
        for destination in sorted(grouped):
            counts = grouped[destination]; attempts = counts["attempted"]
            result.append(DistributionDestinationSummary(destination, attempts, counts["succeeded"], counts["failed"], counts["unknown"], counts["deferred"], counts["skipped"], counts["succeeded"] / attempts if attempts else None, counts["remote_publications"]))
        return DistributionSummary(tuple(result))

    def growth_summary(self, campaign_id=None):
        rows = self._growth_rows(campaign_id)
        events = Counter(str(r.get("event_type") or "") for r in rows)
        destinations = Counter(str(r.get("destination_id") or "") for r in rows if r.get("destination_id"))
        links = Counter(str(r.get("link_id") or "") for r in rows if r.get("link_id"))
        providers = Counter()
        for row in rows:
            provider = self._metadata(row).get("subscription_provider")
            if provider: providers[str(provider)] += 1
        return GrowthSummary(campaign_id, tuple(sorted(destinations.items())), tuple(sorted(links.items())), tuple(sorted(providers.items())), events["link_visited"], events["subscription_started"], events["subscription_confirmed"], events["subscription_cancelled"], len({r["anonymous_id"] for r in rows if r.get("anonymous_id")}), len({r["subscriber_id"] for r in rows if r.get("subscriber_id")}))

    def conversion_funnel(self, campaign_id):
        summary = self.growth_summary(campaign_id)
        return FunnelSummary(campaign_id, summary.visits, summary.subscription_started, summary.subscription_confirmed, summary.subscription_started / summary.visits if summary.visits else None, summary.subscription_confirmed / summary.subscription_started if summary.subscription_started else None, summary.subscription_confirmed / summary.visits if summary.visits else None)
