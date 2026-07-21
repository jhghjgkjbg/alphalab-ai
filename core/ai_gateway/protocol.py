from typing import Protocol

from .types import AIRequest, AIResponse


class AIProvider(Protocol):
    @property
    def name(self) -> str: ...

    async def execute(self, request: AIRequest) -> AIResponse: ...
