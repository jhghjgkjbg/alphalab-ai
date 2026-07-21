import unittest
from agents.ai_scout.telegram_smoke import validate_preflight, mask_target, selected_model, smoke_model_line


class TelegramSmokeSafetyTests(unittest.TestCase):
    def valid(self, **kw):
        data = dict(confirm_send=True, provider="openrouter", token="token", en_target="en", ru_target="ru", en_text="English", ru_text="Русский текст")
        data.update(kw); return validate_preflight(**data)

    def test_confirmation_required(self): self.assertEqual(self.valid(confirm_send=False).reason, "confirm_send_required")
    def test_noop_blocked(self): self.assertEqual(self.valid(provider="noop").reason, "real_ai_provider_required")
    def test_token_required(self): self.assertEqual(self.valid(token="").reason, "missing_telegram_token")
    def test_en_target_required(self): self.assertEqual(self.valid(en_target="").reason, "missing_en_target")
    def test_ru_target_required(self): self.assertEqual(self.valid(ru_target="").reason, "missing_ru_target")
    def test_targets_must_differ(self): self.assertEqual(self.valid(ru_target="en").reason, "targets_must_differ")
    def test_empty_views_blocked(self): self.assertEqual(self.valid(en_text="").reason, "empty_en_view")
    def test_russian_title_required(self): self.assertEqual(self.valid(ru_title="English", ru_body="Русский").reason, "ru_title_not_cyrillic")
    def test_russian_body_required(self): self.assertEqual(self.valid(ru_title="Русский", ru_body="English").reason, "ru_body_not_cyrillic")
    def test_russian_title_and_body_pass(self): self.assertTrue(self.valid(ru_title="Русский", ru_body="Русский текст").ok)
    def test_length_limit(self): self.assertEqual(self.valid(en_text="x" * 4097).reason, "telegram_length_limit")
    def test_valid_preflight(self): self.assertTrue(self.valid().ok)
    def test_masking(self): self.assertEqual(mask_target("123456"), "12***56")
    def test_default_model_is_preserved(self):
        settings = type("Settings", (), {"openrouter_model": "deepseek/deepseek-chat-v3"})()
        self.assertEqual(selected_model(settings), "deepseek/deepseek-chat-v3")

    def test_environment_override_model_is_selected(self):
        settings = type("Settings", (), {"openrouter_model": "test/override"})()
        self.assertEqual(selected_model(settings), "test/override")

    def test_smoke_logs_selected_model(self):
        settings = type("Settings", (), {"openrouter_model": "test/override"})()
        self.assertEqual(smoke_model_line(settings), "model=test/override")

    def test_real_collector_smoke_flag_is_available(self):
        from agents.ai_scout.agent import parse_args
        self.assertTrue(parse_args(["--real-collector-smoke-test"]).real_collector_smoke_test)


if __name__ == "__main__": unittest.main()
