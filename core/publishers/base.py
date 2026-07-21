from typing import Protocol, TypeVar
V=TypeVar("V")
class PublicationPublisher(Protocol[V]):
    def publish(self, view: V): ...
