from dataclasses import dataclass
import inspect


@dataclass(frozen=True)
class DeliveryPlan:
    channels: object
    window: object = None


@dataclass(frozen=True)
class DeliveryReport:
    website: str
    telegram_en: str
    telegram_ru: str
    overall: str
    failure_reasons: dict = None


class DeliveryOrchestrator:
    def __init__(self, website_publisher=None, telegram_publisher=None, require_confirmation=True, confirm_send=None, telegram_publisher_ru=None):
        self.website_publisher = website_publisher
        self.telegram_publisher = telegram_publisher
        self.telegram_publisher_ru = telegram_publisher_ru
        self.confirm_send = bool(require_confirmation if confirm_send is None else confirm_send)

    async def _call(self, publisher, view):
        result = publisher.publish(view)
        return await result if inspect.isawaitable(result) else result

    @staticmethod
    def _normalize(result):
        ok = getattr(result, "success", getattr(result, "ok", result is not False))
        if ok:
            return "sent", ""
        reason = getattr(result, "failure_reason", None) or getattr(result, "error", None) or getattr(result, "error_message", None) or getattr(result, "description", None) or "publisher_failed"
        return "failed", str(reason)

    async def deliver(self, publication, plan: DeliveryPlan, website_view=None, telegram_en_view=None, telegram_ru_view=None):
        c = plan.channels
        statuses = {"website": "blocked", "telegram_en": "blocked", "telegram_ru": "blocked"}
        reasons = {name: "policy_block" for name in statuses}
        for name, enabled, publisher, view in (("website", getattr(c, "website", False), self.website_publisher, website_view), ("telegram_en", getattr(c, "telegram_en", False), self.telegram_publisher, telegram_en_view), ("telegram_ru", getattr(c, "telegram_ru", False), self.telegram_publisher_ru or self.telegram_publisher, telegram_ru_view)):
            if not enabled: continue
            reasons.pop(name, None)
            if name.startswith("telegram") and not self.confirm_send:
                statuses[name] = "blocked"; reasons[name] = "confirmation_required"; continue
            if publisher is None:
                reasons[name] = "publisher_missing"; continue
            if view is None:
                reasons[name] = "view_missing"; continue
            try:
                statuses[name], reasons[name] = self._normalize(await self._call(publisher, view))
            except Exception as exc:
                statuses[name] = "failed"; reasons[name] = type(exc).__name__
        overall = "sent" if any(v == "sent" for v in statuses.values()) and not any(v == "failed" for v in statuses.values()) else "failed" if any(v == "failed" for v in statuses.values()) else "blocked"
        return DeliveryReport(**statuses, overall=overall, failure_reasons=reasons)
