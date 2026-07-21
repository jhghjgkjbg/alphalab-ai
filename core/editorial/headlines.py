from dataclasses import dataclass


@dataclass(frozen=True)
class HeadlineCandidate:
    text: str
    scores: dict[str, float]
    total_score: float


class HeadlineEditor:
    def edit(self, publication) -> tuple[tuple[HeadlineCandidate, ...], HeadlineCandidate]:
        title = str(getattr(publication, "title", "")).strip()
        base = title or "AI technology update"
        texts = (base, f"What {base} means for AI teams", f"The technical story behind {base}", f"{base}: key facts and practical impact", f"Why {base} matters now")
        candidates = tuple(HeadlineCandidate(t, {"clarity": .9, "technical_accuracy": .85, "curiosity": .8, "seo": .85, "clickworthiness": .8, "brevity": max(.4, 1 - len(t)/180)}, round(.7 + max(.0, 1-len(t)/300)*.3, 3)) for t in texts)
        return candidates, max(candidates, key=lambda c: c.total_score)
