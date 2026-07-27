"""Read-only operational report for local distribution and growth events."""
import argparse
import json
import sys
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from dataclasses import asdict
from core.analytics import DistributionEventStore
from core.growth import GrowthEventStore
from core.reporting import ReportingService

class _ReadOnlyDatabase:
    def __init__(self, path): self.path = Path(path)
    @contextmanager
    def connect(self):
        if not self.path.exists(): raise FileNotFoundError(self.path)
        uri = "file:" + self.path.resolve().as_posix() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True); conn.row_factory = sqlite3.Row
        try: yield conn
        finally: conn.close()

def build_report(article_id=None, campaign_id=None, database=None):
    if database is None:
        database = _ReadOnlyDatabase(Path(__file__).resolve().parents[1] / "runtime" / "ai_scout.db")
    service = ReportingService(DistributionEventStore(database), GrowthEventStore(database))
    distribution = service.distribution_summary(article_id)
    growth = service.growth_summary(campaign_id)
    funnel = service.conversion_funnel(campaign_id) if campaign_id else None
    destinations = [asdict(item) for item in distribution.destinations]
    attention = []
    for item in destinations:
        reasons = []
        if item["failed"]: reasons.append("failed")
        if item["unknown"]: reasons.append("unknown")
        if item["deferred"]: reasons.append("deferred")
        if item["attempted"] > item["succeeded"] + item["failed"] + item["unknown"]: reasons.append("unresolved_attempts")
        if reasons: attention.append({"destination": item["destination"], "reasons": reasons})
    return {"distribution": {"destinations": destinations}, "growth": asdict(growth), "funnel": asdict(funnel) if funnel else None, "attention_required": attention}

def _human(report):
    lines = ["Distribution status", "==================="]
    for item in report["distribution"]["destinations"]:
        lines.append(f"{item['destination']}: attempted={item['attempted']} succeeded={item['succeeded']} failed={item['failed']} unknown={item['unknown']} deferred={item['deferred']} skipped={item['skipped']} success_rate={item['success_rate']} remote_publications={item['remote_publications']}")
    growth = report["growth"]
    lines += ["", "Growth summary", "--------------", f"visits={growth['visits']} started={growth['subscription_started']} confirmed={growth['subscription_confirmed']} cancelled={growth['subscription_cancelled']}", f"unique_anonymous_ids={growth['unique_anonymous_ids']} unique_subscriber_ids={growth['unique_subscriber_ids']}"]
    if report["funnel"]:
        funnel = report["funnel"]; lines += ["", "Conversion funnel", "-----------------", f"visits={funnel['visits']} started={funnel['started']} confirmed={funnel['confirmed']} visit_to_started={funnel['visit_to_started']} started_to_confirmed={funnel['started_to_confirmed']} visit_to_confirmed={funnel['visit_to_confirmed']}"]
    lines += ["", "Attention required", "------------------"]
    lines.extend(f"{x['destination']}: {', '.join(x['reasons'])}" for x in report["attention_required"])
    if not report["attention_required"]: lines.append("none")
    return "\n".join(lines)

def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only distribution status report")
    parser.add_argument("--article-id")
    parser.add_argument("--campaign-id")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        report = build_report(args.article_id, args.campaign_id)
        print(json.dumps(report, sort_keys=True, separators=(",", ":")) if args.as_json else _human(report))
        return 0
    except Exception as exc:
        print(f"report failed: {type(exc).__name__}", file=sys.stderr)
        return 1

if __name__ == "__main__": raise SystemExit(main())
