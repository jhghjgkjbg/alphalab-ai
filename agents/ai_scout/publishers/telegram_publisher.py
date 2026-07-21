from __future__ import annotations

from datetime import UTC, datetime

from core.publication.types import PublicationCandidate, PublishResult

from .telegram_client import TelegramClient


class TelegramPublisher:
    """Publication adapter that renders candidates and delegates delivery."""

    def __init__(self, client: TelegramClient, *, parse_mode: str | None = None) -> None:
        self._client = client
        self._parse_mode = parse_mode

    @property
    def channel_name(self) -> str:
        return "telegram"

    async def publish(self, candidate: PublicationCandidate) -> PublishResult:
        text = self._format(candidate)
        result = await self._client.send_message(text)
        return PublishResult(
            channel=self.channel_name,
            success=result.success,
            external_id=str(result.message_id) if result.message_id is not None else None,
            published_at=datetime.now(UTC),
            error_message=result.error_message,
        )

    def _format(self, candidate: PublicationCandidate) -> str:
        score = getattr(candidate, "final_score", None)
        legacy_score = getattr(candidate, "total_score", None) if not hasattr(candidate, "item") else None
        if hasattr(candidate, "item"):
            score = score if score is not None else getattr(candidate, "total_score", None)
            candidate = candidate.item
        else:
            score = score if score is not None else getattr(candidate, "total_score", None)
        payload = getattr(candidate, "payload", None)
        payload = payload if isinstance(payload, dict) else {}
        metadata = getattr(candidate, "metadata", {}) or {}
        title = str(payload.get("title") or getattr(candidate, "title", None) or "New technology update").strip()
        url = str(payload.get("url") or getattr(candidate, "url", None) or "").strip()
        source = str(getattr(candidate, "source", None) or payload.get("source") or "").strip()
        enrichment = payload.get("enrichment") if isinstance(payload.get("enrichment"), dict) else {}
        summary = self._sentences(enrichment.get("summary") or payload.get("summary") or payload.get("content") or getattr(candidate, "summary", None))
        reasons = self._list_values(self._first(enrichment, payload, metadata, ("why_this_matters", "why_it_matters", "key_takeaways", "impact", "importance", "reasons", "insights")), 3)
        audience = self._list_values(self._first(enrichment, payload, metadata, ("audiences", "audience", "best_for", "who_should_read", "who_should_read_this", "target_audience", "relevant_for")), 3)
        score = score if score is not None else payload.get("score", metadata.get("score"))
        rating = self._rating(score)
        verdict = enrichment.get("verdict") or self._verdict(rating)
        blocks = [f"🚀 {title}", "━━━━━━━━━━━━━━━━━━"]
        if summary:
            blocks.extend(["🧠 AI Summary", summary])
        if reasons:
            blocks.extend(["💡 Why this matters", "\n".join(f"• {value}" for value in reasons)])
        if audience:
            blocks.extend(["🎯 Who should read this", "\n".join(f"• {value}" for value in audience)])
        if verdict:
            blocks.extend(["🤖 AI Verdict", str(verdict)])
        blocks.append(f"⭐ AI Scout Rating: {rating}/100")
        if legacy_score is not None:
            blocks.append(f"Score: {legacy_score}")
        if url:
            blocks.extend(["🔗 Original article", url])
        blocks.extend(["━━━━━━━━━━━━━━━━━━", "AI Scout"])
        text = "\n\n".join(blocks)
        return self._limit(text, url)

    @staticmethod
    def _sentences(value):
        if not value: return ""
        text = " ".join(str(value).split())
        parts = [part.strip() for part in text.replace("! ", "!\n").replace("? ", "?\n").replace(". ", ".\n").splitlines() if part.strip()]
        return " ".join(parts[:4])

    @staticmethod
    def _list_values(value, limit):
        if isinstance(value, dict): value = tuple(value.values())
        if isinstance(value, str):
            value = [line.strip(" •-\t") for line in value.replace(";", "\n").replace(",", "\n").splitlines()]
        if not isinstance(value, (list, tuple)): return ()
        result = []
        for item in value:
            text = " ".join(str(item).strip(" •-\t").split())
            if text and text.lower() not in {"none", "null"} and text.casefold() not in {x.casefold() for x in result}: result.append(text)
        return tuple(result[:limit])

    @staticmethod
    def _first(*mappings):
        keys = mappings[-1];
        for mapping in mappings[:-1]:
            if isinstance(mapping, dict):
                for key in keys:
                    if mapping.get(key): return mapping[key]
        return None

    @staticmethod
    def _rating(score):
        try:
            number = float(score)
            return max(0, min(100, round(number * 100 if 0 <= number <= 1 else number)))
        except (TypeError, ValueError): return 0

    @staticmethod
    def _verdict(rating):
        return "★★★★★ Must Read" if rating >= 90 else "★★★★ Worth Reading" if rating >= 75 else "★★★ Interesting" if rating >= 60 else "★★ Research" if rating >= 50 else ""

    @staticmethod
    def _limit(text, url):
        if len(text) <= 3900: return text
        footer = "\n\n━━━━━━━━━━━━━━━━━━\nAI Scout"
        suffix = ("\n\n🔗 Original article\n" + url if url else "") + footer
        return text[:max(0, 3900 - len(suffix))].rstrip() + suffix
