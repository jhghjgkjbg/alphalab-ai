from dataclasses import dataclass


@dataclass(frozen=True)
class EditorialReview:
    quality_score: int
    approved: bool
    review_notes: tuple[str, ...] = ()


class EditorialReviewer:
    """Deterministic final review; it never rewrites or calls an AI provider."""

    def __init__(self, minimum_score: int = 60):
        self.minimum_score = int(minimum_score)

    def review(self, publication, headline=None) -> EditorialReview:
        title = str(getattr(publication, "title", "") or "").strip()
        summary = str(getattr(publication, "summary", "") or "").strip()
        url = str(getattr(publication, "canonical_url", "") or getattr(publication, "url", "") or "").strip()
        notes: list[str] = []
        score = 100
        if not title:
            score -= 30; notes.append("missing_title")
        if len(summary) < 40:
            score -= 15; notes.append("limited_context")
        if not url:
            score -= 15; notes.append("missing_canonical_url")
        if headline is not None and not str(headline).strip():
            score -= 20; notes.append("missing_selected_headline")
        if summary and title.casefold() == summary.casefold():
            score -= 10; notes.append("repetition")
        score = max(0, min(100, score))
        approved = score >= self.minimum_score and bool(title and summary)
        if not approved and not notes:
            notes.append("quality_below_threshold")
        return EditorialReview(score, approved, tuple(notes))
