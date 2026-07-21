import json
import unittest

from core.ai_enrichment.providers.openrouter import OpenRouterProvider, _SCHEMA
from core.ai_enrichment.registry import AIProviderRegistry
from core.ai_response import DefaultResponseParser
from core.prompts.types import Prompt
from core.prompts import DefaultPromptBuilder
from core.publication.builder import PublicationBuilder


class _Response:
    id = "or-resp"
    choices = (type("Choice", (), {"message": type("Message", (), {"content": json.dumps({"short_summary": "ok", "translation": "Перевод", "confidence": 0.8})})()})(),)
    usage = type("Usage", (), {"prompt_tokens": 4, "completion_tokens": 6})()


class _Client:
    def __init__(self): self.calls = []
    class chat:
        class completions:
            calls = []
            @classmethod
            def create(cls, **kwargs): cls.calls.append(kwargs); return _Response()


class OpenRouterProviderTests(unittest.TestCase):
    def test_schema_contains_bilingual_field_descriptions(self):
        props = _SCHEMA["properties"]
        self.assertIn("English news headline only", props["en_title"]["description"])
        self.assertIn("English summary only", props["en_body"]["description"])
        self.assertIn("never copy or transliterate en_title", props["ru_title"]["description"])
        self.assertIn("Russian summary in Cyrillic only", props["ru_body"]["description"])

    def test_prompt_contains_explicit_bilingual_instructions(self):
        publication = PublicationBuilder().build({"id": "p", "title": "Title", "summary": "Summary", "url": "https://example.com", "source": "test"})
        prompt = DefaultPromptBuilder().build(publication)
        self.assertIn("en_title", prompt.system_prompt)
        self.assertIn("en_body MUST be written in English", prompt.system_prompt)
        self.assertIn("ru_title", prompt.system_prompt)
        self.assertIn("ru_body MUST be written in Russian using Cyrillic", prompt.system_prompt)
        self.assertIn("idiomatic Russian news headline", prompt.system_prompt)
        self.assertIn("never transliterate", prompt.system_prompt)
        self.assertIn("never copy the English title", prompt.system_prompt)
        self.assertIn("adapt it naturally", prompt.system_prompt)

    def test_registry_keeps_noop_default_and_registers_openrouter(self):
        registry = AIProviderRegistry.with_noop()
        self.assertEqual(registry.default_provider().enrich(Prompt("", "")).provider, "noop")
        self.assertEqual(registry.get("openrouter").name, "openrouter")

    def test_missing_key_does_not_call_http(self):
        self.assertEqual(OpenRouterProvider().enrich(Prompt("", "")).finish_reason, "configuration_error")

    def test_chat_completion_is_single_structured_call(self):
        _Client.chat.completions.calls = []
        provider = OpenRouterProvider(api_key="test-only", model="test/model", client=_Client())
        raw = provider.enrich(Prompt("system", "user"), tasks=(object(), object()))
        self.assertEqual(len(_Client.chat.completions.calls), 1)
        call = _Client.chat.completions.calls[0]
        self.assertEqual(call["response_format"]["type"], "json_schema")
        self.assertTrue(call["response_format"]["json_schema"]["strict"])
        self.assertEqual(DefaultResponseParser().parse(raw).short_summary, "ok")
        self.assertEqual(raw.input_tokens, 4)

    def test_provider_exception_is_safe(self):
        class Failing:
            class chat:
                class completions:
                    @staticmethod
                    def create(**kwargs): raise TimeoutError("timeout")
        raw = OpenRouterProvider(api_key="test-only", client=Failing()).enrich(Prompt("", ""))
        self.assertIn("TimeoutError", raw.finish_reason)


if __name__ == "__main__": unittest.main()
