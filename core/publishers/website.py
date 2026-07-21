from core.renderers.website import WebsiteView
class WebsitePublisher:
    def __init__(self, sink): self.sink=sink
    def publish(self, view: WebsiteView): return self.sink(view)
