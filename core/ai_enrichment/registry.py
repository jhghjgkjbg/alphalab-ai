from .engine import NoOpAIProvider
from .providers.openai import OpenAIProvider
from .providers.openrouter import OpenRouterProvider
class AIProviderRegistry:
    def __init__(self, default="noop"): self._providers={}; self._default=default
    def register(self,name,provider): self._providers[str(name)]=provider
    def get(self,name): return self._providers.get(name)
    def default_provider(self): return self._providers.get(self._default)
    @classmethod
    def with_noop(cls, default="noop", *, openai=None, openrouter=None):
        r=cls(default); r.register("noop",NoOpAIProvider()); r.register("openai", openai or OpenAIProvider()); r.register("openrouter", openrouter or OpenRouterProvider()); return r
