import unittest
from types import SimpleNamespace

from core.editorial.channels import ChannelSelector


class TelegramRuPolicyTests(unittest.TestCase):
    def test_ai_enriched_general_tech_with_ru_variant_selects_both_languages(self):
        priority = SimpleNamespace(level="normal")
        channels = ChannelSelector().select(
            priority,
            language="en",
            category="General Tech",
            ai_succeeded=True,
            has_ru_variant=True,
        )
        self.assertTrue(channels.website)
        self.assertTrue(channels.telegram_en)
        self.assertTrue(channels.telegram_ru)

    def test_missing_ru_variant_remains_blocked(self):
        channels = ChannelSelector().select(
            SimpleNamespace(level="normal"),
            language="en",
            category="General Tech",
            ai_succeeded=True,
            has_ru_variant=False,
        )
        self.assertFalse(channels.telegram_ru)


if __name__ == "__main__":
    unittest.main()
