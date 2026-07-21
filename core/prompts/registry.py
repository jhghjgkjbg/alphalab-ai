from .builder import DefaultPromptBuilder
class PromptRegistry:
    def __init__(self): self._items={"default":DefaultPromptBuilder()}
    def register(self,name,builder): self._items[name]=builder
    def get(self,name="default"): return self._items[name]
