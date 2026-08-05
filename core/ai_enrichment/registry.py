from .engine import NoOpAIProvider
from .providers.openai import OpenAIProvider
from .providers.openrouter import OpenRouterProvider
from .providers.gemini import GeminiProvider
from .providers.anthropic import AnthropicProvider
class AIProviderRegistry:
    def __init__(self, default="noop", order=None): self._providers={}; self._default=default; self.order=tuple(order or ())
    def register(self,name,provider): self._providers[str(name)]=provider
    def get(self,name): return self._providers.get(name)
    def default_provider(self): return self._providers.get(self._default)
    def ordered(self):
        names = self.order or ((self._default,) if self._default else tuple(self._providers))
        return tuple((name, self._providers[name]) for name in names if name in self._providers)
    @classmethod
    def with_noop(cls, default="noop", *, openai=None, openrouter=None, gemini=None, anthropic=None, order=None):
        r=cls(default, order=order); r.register("noop",NoOpAIProvider()); r.register("openai", openai or OpenAIProvider()); r.register("openrouter", openrouter or OpenRouterProvider()); r.register("gemini", gemini or GeminiProvider()); r.register("anthropic", anthropic or AnthropicProvider()); return r
