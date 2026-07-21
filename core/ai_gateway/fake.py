from .types import AIRequest, AIResponse, AIUsage


class FakeAIProvider:
    name = "fake"

    async def execute(self, request: AIRequest) -> AIResponse:
        return AIResponse(True, f"fake:{request.operation}:{request.input}", AIUsage("fake", request.model or "fake-model", len(request.input), 1, 0.0))
