import json
import unittest
import asyncio
import contextlib
import io

from core.ai_enrichment.providers.openai import OpenAIProvider
from core.ai_response import DefaultResponseParser
from core.ai_response.types import RawAIResponse
from core.prompts.types import Prompt


class _Responses:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class _Client:
    def __init__(self, response):
        self.responses = _Responses(response)


class _Response:
    id = "resp_test"
    status = "completed"
    output_text = json.dumps({
        "headline_suggestions": ["A headline"], "short_summary": "Short",
        "long_summary": "Long", "seo_keywords": ["ai"], "hashtags": ["#ai"],
        "entities": ["Alpha"], "topics": ["Research"], "category_guess": "AI",
        "language": "en", "confidence": 0.9, "editor_notes": "",
        "translation": "Перевод", "translation_status": "complete",
    })
    usage = type("Usage", (), {"input_tokens": 10, "output_tokens": 20})()


class OpenAIProviderVerificationTests(unittest.TestCase):
    def setUp(self):
        self.prompt = Prompt("system", "user")

    def test_structured_responses_call_once_and_parse(self):
        client = _Client(_Response())
        raw = OpenAIProvider(api_key="test-only", client=client).enrich(self.prompt)
        self.assertEqual(len(client.responses.calls), 1)
        call = client.responses.calls[0]
        self.assertEqual(call["text"]["format"]["type"], "json_schema")
        self.assertTrue(call["text"]["format"]["strict"])
        parsed = DefaultResponseParser().parse(raw)
        self.assertEqual(parsed.short_summary, "Short")
        self.assertEqual(parsed.translation_status, "complete")
        self.assertEqual(raw.response_id, "resp_test")

    def test_missing_key_is_safe_configuration_error(self):
        raw = OpenAIProvider().enrich(self.prompt)
        self.assertEqual(raw.finish_reason, "configuration_error")

    def test_provider_exception_becomes_raw_error(self):
        class Failing:
            class responses:
                @staticmethod
                def create(**kwargs):
                    raise TimeoutError("timed out")
        raw = OpenAIProvider(api_key="test-only", client=Failing()).enrich(self.prompt)
        self.assertIn("TimeoutError", raw.finish_reason)

    def test_empty_response_parses_without_crash(self):
        response = type("Response", (), {"output_text": "", "usage": None, "id": "", "status": "completed"})()
        raw = OpenAIProvider(api_key="test-only", client=_Client(response)).enrich(self.prompt)
        self.assertEqual(DefaultResponseParser().parse(raw).short_summary, "")
        self.assertEqual(OpenAIProvider(api_key="test-only", client=_Client(response)).last_failure_kind, None)

    def test_credit_balance_exhausted_is_payment_required(self):
        class Failure(Exception):
            status_code = 402
            body = {"error": {"type": "insufficient_quota", "code": "credit_balance_exhausted"}}
        class Failing:
            class responses:
                @staticmethod
                def create(**kwargs): raise Failure()
        provider = OpenAIProvider(api_key="test-only", client=Failing())
        provider.enrich(self.prompt)
        self.assertEqual(provider.last_failure_kind, "payment_required")

    def test_insufficient_quota_is_payment_required(self):
        class Failure(Exception):
            status_code = 402
            body = {"error": {"type": "insufficient_quota", "code": "quota"}}
        class Failing:
            class responses:
                @staticmethod
                def create(**kwargs): raise Failure()
        provider = OpenAIProvider(api_key="test-only", client=Failing())
        provider.enrich(self.prompt)
        self.assertEqual(provider.last_failure_kind, "payment_required")

    def test_fenced_json_parses(self):
        raw = RawAIResponse(raw_text="```json\n{\"short_summary\":\"ok\"}\n```")
        self.assertEqual(DefaultResponseParser().parse(raw).short_summary, "ok")

    def test_authentication_and_rate_limit_errors_are_safe(self):
        for error in (PermissionError("authentication failed"), RuntimeError("rate limit")):
            class Failing:
                class responses:
                    @staticmethod
                    def create(_error=error, **kwargs):
                        raise _error
            raw = OpenAIProvider(api_key="test-only", client=Failing()).enrich(self.prompt)
            self.assertIn(type(error).__name__, raw.finish_reason)

    def test_noop_does_not_require_a_key(self):
        from core.ai_enrichment.engine import NoOpAIProvider
        self.assertEqual(NoOpAIProvider().enrich(self.prompt).provider, "noop")

    def test_smoke_cli_missing_key_makes_no_http_call(self):
        from agents.ai_scout.agent import _run_openai_smoke_test
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                asyncio.run(_run_openai_smoke_test(type("Settings", (), {"openai_api_key": "", "ai_provider": "openai"})()))
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("stage=configuration", output.getvalue())

    def test_smoke_flag_is_explicit(self):
        from agents.ai_scout.agent import parse_args
        self.assertTrue(parse_args(["--openai-smoke-test"]).openai_smoke_test)


if __name__ == "__main__":
    unittest.main()
