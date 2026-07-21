from core.renderers.telegram import TelegramView
class TelegramViewPublisher:
    def __init__(self, sender): self.sender=sender
    async def publish(self, view: TelegramView):
        return await self.sender.send_message(view.text)
TelegramPublisher = TelegramViewPublisher
