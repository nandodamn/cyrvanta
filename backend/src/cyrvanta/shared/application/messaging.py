from typing import Protocol

from cyrvanta.shared.domain.events import DomainEvent


class EventRecorder(Protocol):
    async def add(self, event: DomainEvent) -> None: ...


class EventHandler(Protocol):
    async def __call__(self, event: DomainEvent) -> None: ...
