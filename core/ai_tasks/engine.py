class AITaskEngine:
    def __init__(self,rules=None): self.rules=tuple(sorted(rules or (),key=lambda r:r.priority))
    def select(self,publication):
        tasks=[]
        for rule in self.rules: tasks.extend(rule.select(publication))
        return tuple(sorted({t.name:t for t in tasks}.values(),key=lambda t:(t.priority,t.name)))
