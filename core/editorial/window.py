from dataclasses import dataclass, replace


@dataclass(frozen=True)
class PublicationWindow:
    selected: str
    reason: str = ""


class PublicationWindowSelector:
    def select(self, priority, freshness=1.0, breaking_level=None, audience=None) -> PublicationWindow:
        level = breaking_level or getattr(priority, "level", "normal")
        if level == "breaking":
            return PublicationWindow("immediate", "breaking priority")
        if level == "high":
            return PublicationWindow("today", "high priority")
        if level == "low":
            return PublicationWindow("scheduled", "low priority")
        return PublicationWindow("today" if float(freshness) >= .35 else "scheduled", "freshness")

    def apply(self, publication, priority, **kwargs):
        return replace(publication, publication_window=self.select(priority, **kwargs))
