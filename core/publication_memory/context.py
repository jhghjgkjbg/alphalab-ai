from dataclasses import dataclass

@dataclass(frozen=True)
class EditorialMemoryContext:
    entries: tuple[dict, ...]
    def instructions(self):
        return "Avoid repeating headlines or opening paragraphs, avoid publishing the same story twice, and preserve editorial style consistency.\n" + "\n".join(f"{e.get('title','')} | {e.get('published_at','')} | {e.get('source','')} | {e.get('canonical_url','')}" for e in self.entries)

def load_editorial_memory(store, maximum=10):
    rows=store.latest(maximum) if hasattr(store,"latest") else []
    return EditorialMemoryContext(tuple({k:r.get(k,"") for k in ("title","en_title","published_at","created_at","source","canonical_url")} for r in rows[:maximum]))
