from dataclasses import dataclass

@dataclass(frozen=True)
class EditorialFacts:
    verified_facts: tuple[str, ...] = ()
    important_numbers: tuple[str, ...] = ()
    people: tuple[str, ...] = ()
    organizations: tuple[str, ...] = ()
    technologies: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()

class FactExtractor:
    def extract(self, publication) -> EditorialFacts:
        return EditorialFacts(verified_facts=(publication.title,), organizations=(publication.source,), technologies=(publication.category,))
