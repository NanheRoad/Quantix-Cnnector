from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable


MessageHandler = Callable[[str, bytes], Awaitable[None]]


class DeviceDriver(ABC):
    def __init__(self, connection_params: dict[str, Any]):
        self.connection_params = connection_params

    @abstractmethod
    async def connect(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def disconnect(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def is_connected(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def execute_action(self, action: str, params: dict[str, Any]) -> Any:
        raise NotImplementedError

    def register_message_handler(self, handler: MessageHandler) -> None:
        _ = handler
