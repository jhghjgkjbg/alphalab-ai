from dataclasses import dataclass

@dataclass(frozen=True)
class EditorialPlan:
    key_facts: tuple[str, ...]
    technical_importance: str
    target_audience: str
    title_direction: str
    angle: str = "Industry Analysis"

class EditorialPlanner:
    def plan(self, publication, facts=None, angle=None, audience=None) -> EditorialPlan:
        key_facts=tuple(facts.verified_facts) if facts else (publication.title, publication.source)
        target = getattr(audience, "audience", None) or publication.target_audience or "technical readers"
        return EditorialPlan(key_facts, "assess technical significance", target, "clear factual news headline", getattr(angle, "name", "Industry Analysis"))
