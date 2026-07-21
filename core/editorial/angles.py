from dataclasses import dataclass

@dataclass(frozen=True)
class StoryAngle:
    name: str
    guidance: str

class StoryAngleSelector:
    ANGLES={
        "security":"Security", "vulnerability":"Security",
        "research":"Research", "paper":"Research",
        "tutorial":"Tutorial", "how to":"Tutorial",
        "github":"Open Source", "open source":"Open Source",
        "release":"Product Release", "launch":"Product Release",
        "infrastructure":"Infrastructure", "kubernetes":"Infrastructure",
        "breaking":"Breaking News", "urgent":"Breaking News",
        "deep dive":"Technical Deep Dive", "architecture":"Technical Deep Dive",
        "opinion":"Opinion", "analysis":"Industry Analysis",
    }
    def select(self, publication):
        text=(str(publication.title)+" "+str(publication.summary)).casefold()
        for key,name in self.ANGLES.items():
            if key in text: return StoryAngle(name, {"Security":"explain risks, affected systems, and mitigation","Research":"emphasize methodology, limitations, and significance","Tutorial":"emphasize actionable steps","Product Release":"focus on capabilities and practical impact"}.get(name,"explain technical impact"))
        return StoryAngle("Industry Analysis","explain implications and broader industry context")
