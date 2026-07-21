from .telegram_publisher import TelegramPublisher

class RussianTelegramPublisher(TelegramPublisher):
    def _format(self, candidate):
        text=super()._format(candidate)
        return "🚀 Русский обзор\n\n" + text.replace("AI Summary", "Кратко").replace("Why this matters", "Почему это важно").replace("Who should read this", "Кому будет полезно").replace("AI Verdict", "Вердикт AI").replace("Original article", "Оригинал")
