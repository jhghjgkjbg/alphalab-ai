from dataclasses import dataclass


@dataclass(frozen=True)
class AudienceProfile:
    audience: str
    expertise_level: str
    explanation_depth: str
    terminology_level: str


class AudienceSelector:
    def select(self, publication) -> AudienceProfile:
        text = (str(getattr(publication, "title", "")) + " " + str(getattr(publication, "summary", ""))).casefold()
        if any(k in text for k in ("kubernetes", "docker", "devops", "infrastructure")):
            return AudienceProfile("DevOps / Infrastructure", "advanced", "deep", "specialist")
        if any(k in text for k in ("research", "arxiv", "paper", "methodology")):
            return AudienceProfile("AI Researchers", "advanced", "deep", "specialist")
        if any(k in text for k in ("security", "vulnerability", "cve", "exploit")):
            return AudienceProfile("Security Professionals", "advanced", "deep", "specialist")
        if any(k in text for k in ("startup", "funding", "founder")):
            return AudienceProfile("Startup Founders", "intermediate", "moderate", "business-aware")
        if any(k in text for k in ("product", "launch", "roadmap")):
            return AudienceProfile("Product Managers", "intermediate", "moderate", "accessible")
        if any(k in text for k in ("machine learning", "ml", "model", "training")):
            return AudienceProfile("ML Engineers", "advanced", "deep", "specialist")
        if any(k in text for k in ("code", "software", "developer", "api")):
            return AudienceProfile("Software Developers", "intermediate", "moderate", "technical")
        return AudienceProfile("General Tech", "beginner", "moderate", "accessible")
