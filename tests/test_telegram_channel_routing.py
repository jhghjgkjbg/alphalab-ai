import asyncio
import unittest
from types import SimpleNamespace

from core.delivery import DeliveryOrchestrator, DeliveryPlan
from core.editorial.channels import PublicationChannels
from core.renderers.telegram import TelegramView


class _Publisher:
    def __init__(self): self.views = []
    async def publish(self, view):
        self.views.append(view)
        return SimpleNamespace(success=True)


class TelegramChannelRoutingTests(unittest.TestCase):
    def test_en_and_ru_use_distinct_publishers_and_views(self):
        en, ru = _Publisher(), _Publisher()
        report = asyncio.run(DeliveryOrchestrator(
            telegram_publisher=en, telegram_publisher_ru=ru, confirm_send=True
        ).deliver(
            None, DeliveryPlan(PublicationChannels(True, True, True)),
            telegram_en_view=TelegramView("English", "English summary", (), {}, "en"),
            telegram_ru_view=TelegramView("Русский", "Русское резюме", (), {}, "ru"),
        ))
        self.assertEqual(report.telegram_en, "sent")
        self.assertEqual(report.telegram_ru, "sent")
        self.assertEqual(len(en.views), 1)
        self.assertEqual(len(ru.views), 1)
        self.assertEqual(en.views[0].language, "en")
        self.assertEqual(ru.views[0].language, "ru")
        self.assertNotEqual(en, ru)


if __name__ == "__main__":
    unittest.main()
