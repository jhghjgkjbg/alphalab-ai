from .types import AITask
class LanguageTaskRule:
    priority=10
    def select(self,p): return [] if len(getattr(p,"variants",{}))>1 else [AITask("translation")]
class EditorialTaskRule:
    priority=20
    def select(self,p): return [AITask("summary"),AITask("category"),AITask("headline")]
class QualityTaskRule:
    priority=30
    def select(self,p): return [AITask("headline",priority=5)] if p.final_quality_score<.4 else []
class ChannelTaskRule:
    priority=40
    def __init__(self,telegram=True,website=True): self.telegram=telegram; self.website=website
    def select(self,p): return ([AITask("hashtags")] if self.telegram else [])+([AITask("keywords")] if self.website else [])
