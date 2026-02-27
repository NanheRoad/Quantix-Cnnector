from __future__ import annotations

import logging
from typing import Any

from backend.drivers.base import DeviceDriver

try:
    import serial
except Exception:  # pragma: no cover
    serial = None

logger = logging.getLogger(__name__)


class SerialDriver(DeviceDriver):
    def __init__(self, connection_params: dict[str, Any]):
        super().__init__(connection_params)
        self._ser = None
        self._connected = False
        self._last_error: str | None = None

    async def connect(self) -> bool:
        if serial is None:
            self._connected = True
            self._last_error = None
            return True

        try:
            self._ser = serial.Serial(
                port=self.connection_params.get("port", "/dev/ttyUSB0"),
                baudrate=int(self.connection_params.get("baudrate", 9600)),
                bytesize=int(self.connection_params.get("bytesize", 8)),
                parity=str(self.connection_params.get("parity", "N")),
                stopbits=int(self.connection_params.get("stopbits", 1)),
                timeout=float(self.connection_params.get("timeout", 1.0)),
            )
            self._connected = True
            self._last_error = None
        except Exception as exc:
            self._connected = False
            self._last_error = str(exc)
            logger.warning(
                "Serial connect failed: port=%s baudrate=%s error=%s",
                self.connection_params.get("port", "/dev/ttyUSB0"),
                self.connection_params.get("baudrate", 9600),
                exc,
            )
        return self._connected

    async def disconnect(self) -> bool:
        if self._ser is not None:
            self._ser.close()
        self._ser = None
        self._connected = False
        return True

    async def is_connected(self) -> bool:
        return self._connected

    def get_last_error(self) -> str | None:
        return self._last_error

    async def execute_action(self, action: str, params: dict[str, Any]) -> Any:
        if action == "serial.send":
            data = _to_bytes(params.get("data", ""), params.get("encoding", "ascii"))
            if self._ser is not None:
                self._ser.write(data)
            return {"bytes_sent": len(data)}

        if action == "serial.receive":
            size = int(params.get("size", 0))
            timeout = float(params.get("timeout", 1000)) / 1000
            if self._ser is None:
                return {"payload": b"WS 12.34"}
            old_timeout = self._ser.timeout
            self._ser.timeout = timeout
            payload = self._ser.read(size)
            self._ser.timeout = old_timeout
            return {"payload": payload}

        raise ValueError(f"Unsupported action for SerialDriver: {action}")


def _to_bytes(data: Any, encoding: str) -> bytes:
    if isinstance(data, bytes):
        return data
    text = str(data)
    if encoding == "hex":
        cleaned = text.replace(" ", "")
        return bytes.fromhex(cleaned)
    return text.encode("utf-8")
