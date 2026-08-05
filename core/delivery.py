from dataclasses import dataclass
import inspect
from datetime import datetime, UTC

def _utc(value):
    if value is None: return None
    if value.tzinfo is None: raise ValueError("naive scheduled_for is not allowed")
    return value.astimezone(UTC)

def is_delivery_due(scheduled_for, now):
    if scheduled_for is None: return True
    return _utc(scheduled_for) <= _utc(now)


@dataclass(frozen=True)
class DeliveryPlan:
    channels: object
    window: object = None

@dataclass(frozen=True)
class DestinationDelivery:
    destination: str
    publisher: object
    view: object
    scheduled_for: datetime | None = None
    attempt_number: int = 1


@dataclass(frozen=True)
class DeliveryReport:
    website: str
    telegram_en: str
    telegram_ru: str
    overall: str
    failure_reasons: dict = None
    details: dict = None
    statuses: dict = None


class DeliveryOrchestrator:
    def __init__(self, website_publisher=None, telegram_publisher=None, require_confirmation=True, confirm_send=None, telegram_publisher_ru=None, bindings=None, clock=None, analytics_store=None):
        self.website_publisher = website_publisher
        self.telegram_publisher = telegram_publisher
        self.telegram_publisher_ru = telegram_publisher_ru
        self.confirm_send = bool(require_confirmation if confirm_send is None else confirm_send)
        self.bindings = tuple(bindings or ())
        self.clock = clock or (lambda: datetime.now(UTC))
        self.analytics_store = analytics_store

    def _analytics(self, event_type, publication, binding, status, external_id=None, reason=None):
        if self.analytics_store is None: return
        try:
            from core.analytics.events import DistributionEvent
            article_id = str(getattr(publication, "article_id", "") or getattr(publication, "publication_id", ""))
            self.analytics_store.append(DistributionEvent("", datetime.now(UTC), event_type, article_id, binding.destination, status, int(getattr(binding, "attempt_number", 1)), external_id, binding.scheduled_for, reason, {}))
        except Exception:
            pass

    async def _call(self, publisher, view):
        result = publisher.publish(view)
        return await result if inspect.isawaitable(result) else result

    @staticmethod
    def _normalize(result):
        ok = getattr(result, "success", getattr(result, "ok", result is not False))
        if ok:
            return "sent", "", getattr(result, "message_id", None) or getattr(result, "external_id", None)
        reason = getattr(result, "failure_reason", None) or getattr(result, "error", None) or getattr(result, "error_message", None) or getattr(result, "description", None) or "publisher_failed"
        return ("unknown" if "timeout" in str(reason).lower() else "failed"), str(reason), None

    async def deliver(self, publication, plan: DeliveryPlan, website_view=None, telegram_en_view=None, telegram_ru_view=None, skip_destinations=None, skip_reasons=None):
        c = plan.channels
        statuses = {"website": "blocked", "telegram_en": "blocked", "telegram_ru": "blocked"}
        reasons = {name: "policy_block" for name in statuses}
        details = {}
        now = self.clock()
        skip_destinations = skip_destinations or set()
        skip_reasons = skip_reasons or {}
        bindings = self.bindings or (DestinationDelivery("website", self.website_publisher, website_view), DestinationDelivery("telegram_en", self.telegram_publisher, telegram_en_view), DestinationDelivery("telegram_ru", self.telegram_publisher_ru or self.telegram_publisher, telegram_ru_view))
        for binding in bindings:
            name, publisher, view = binding.destination, binding.publisher, binding.view
            enabled = getattr(c, name, True if self.bindings else False)
            statuses.setdefault(name, "blocked"); reasons.setdefault(name, "policy_block")
            if not enabled: continue
            if not is_delivery_due(binding.scheduled_for, now):
                statuses[name] = "pending"; reasons[name] = "scheduled_for_future"
                details[name] = {"status": "pending", "error": "scheduled_for_future", "deferred": True}
                self._analytics("delivery_deferred", publication, binding, "pending", reason="scheduled_for_future")
                continue
            reasons.pop(name, None)
            if name in skip_destinations:
                statuses[name] = "sent"
                details[name] = {"status": "sent", "external_id": None, "error": None}
                self._analytics("delivery_skipped", publication, binding, "skipped", reason=skip_reasons.get(name, "already_sent"))
                continue
            if (name.startswith("telegram") or name in {"x", "linkedin", "medium", "substack", "devto", "hashnode"}) and not self.confirm_send:
                statuses[name] = "blocked"; reasons[name] = "confirmation_required"
                self._analytics("delivery_skipped", publication, binding, "skipped", reason="confirmation_required")
                continue
            if publisher is None:
                reasons[name] = "publisher_missing"; continue
            if view is None:
                reasons[name] = "view_missing"; continue
            try:
                self._analytics("delivery_attempted", publication, binding, "pending")
                statuses[name], reasons[name], external_id = self._normalize(await self._call(publisher, view))
                details[name] = {"status": statuses[name], "external_id": external_id, "error": reasons[name]}
            except Exception as exc:
                statuses[name] = "unknown" if "timeout" in type(exc).__name__.lower() else "failed"; reasons[name] = type(exc).__name__
                details[name] = {"status": statuses[name], "external_id": None, "error": reasons[name]}
        # Aggregate only destinations that are enabled and have an instantiated
        # publisher. Optional, disabled, or unconfigured destinations must not
        # turn an otherwise successful delivery into a failure.
        active = [binding.destination for binding in bindings if getattr(c, binding.destination, True if self.bindings else False) and binding.publisher is not None]
        active_statuses = [statuses.get(name, "blocked") for name in active]
        for binding in bindings:
            enabled = bool(getattr(c, binding.destination, True if self.bindings else False))
            if enabled:
                status = statuses.get(binding.destination, "blocked")
                reason = reasons.get(binding.destination, "") or "none"
                print(f"destination={binding.destination} instantiated={'yes' if binding.publisher is not None else 'no'} enabled={'yes' if enabled else 'no'} result={status} failure_kind={reason}")
        if not active_statuses:
            overall = "blocked"
        elif any(status == "failed" for status in active_statuses):
            overall = "failed"
        elif all(status == "sent" for status in active_statuses):
            overall = "sent"
        else:
            overall = "blocked"
        return DeliveryReport(**{k: statuses.get(k, "blocked") for k in ("website", "telegram_en", "telegram_ru")}, overall=overall, failure_reasons=reasons, details=details, statuses=statuses)
