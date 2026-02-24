from __future__ import annotations

import asyncio
from typing import Any

from backend.drivers.base import DeviceDriver


class TcpDriver(DeviceDriver):
    def __init__(self, connection_params: dict[str, Any]):
        super().__init__(connection_params)
        self.reader = None
        self.writer = None
        self._connected = False

    async def connect(self) -> bool:
        host = self.connection_params.get("host")
        port = int(self.connection_params.get("port", 0))
        if not host or not port:
            self._connected = True
            return True

        try:
            self.reader, self.writer = await asyncio.open_connection(host, port)
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    async def disconnect(self) -> bool:
        if self.writer is not None:
            self.writer.close()
            await self.writer.wait_closed()
        self.reader = None
        self.writer = None
        self._connected = False
        return True

    async def is_connected(self) -> bool:
        return self._connected

    async def execute_action(self, action: str, params: dict[str, Any]) -> Any:
        if action == "tcp.send":
            data = _to_bytes(params.get("data", ""), params.get("encoding", "ascii"))
            if self.writer is not None:
                self.writer.write(data)
                await self.writer.drain()
            return {"bytes_sent": len(data)}

        if action == "tcp.receive":
            size = int(params.get("size", 0))
            timeout = float(params.get("timeout", 1000)) / 1000
            if self.reader is None:
                return {"payload": b"0.0"}
            payload = await asyncio.wait_for(self.reader.read(size), timeout=timeout)
            return {"payload": payload}

        raise ValueError(f"Unsupported action for TcpDriver: {action}")


def _to_bytes(data: Any, encoding: str) -> bytes:
    if isinstance(data, bytes):
        return data
    text = str(data)
    if encoding == "hex":
        cleaned = text.replace(" ", "")
        return bytes.fromhex(cleaned)
    return text.encode("utf-8")
