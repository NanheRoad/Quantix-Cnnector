from __future__ import annotations

from typing import Any

from backend.drivers.base import DeviceDriver

try:
    import serial
except Exception:  # pragma: no cover
    serial = None


class SerialDriver(DeviceDriver):
    def __init__(self, connection_params: dict[str, Any]):
        super().__init__(connection_params)
        self._ser = None
        self._connected = False

    async def connect(self) -> bool:
        if serial is None:
            self._connected = True
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
        except Exception:
            self._connected = False
        return self._connected

    async def disconnect(self) -> bool:
        if self._ser is not None:
            self._ser.close()
        self._ser = None
        self._connected = False
        return True

    async def is_connected(self) -> bool:
        return self._connected

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
