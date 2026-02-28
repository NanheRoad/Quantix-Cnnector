from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from collections import deque
from typing import Any

try:
    import serial
    from serial.tools import list_ports
except Exception:  # pragma: no cover
    serial = None
    list_ports = None


LINE_ENDING_MAP = {
    "none": b"",
    "cr": b"\r",
    "lf": b"\n",
    "crlf": b"\r\n",
}


class SerialDebugService:
    def __init__(self) -> None:
        self._ser = None
        self._lock = asyncio.Lock()
        self._last_error: str | None = None
        self._settings: dict[str, Any] = {}
        self._logs: deque[dict[str, Any]] = deque(maxlen=1000)
        self._log_seq = 0

    async def list_ports(self) -> list[dict[str, Any]]:
        if list_ports is None:
            return []

        ports = list(list_ports.comports())
        ports.sort(key=lambda item: item.device)
        return [
            {
                "device": item.device,
                "name": item.name,
                "description": item.description,
                "hwid": item.hwid,
                "manufacturer": item.manufacturer,
                "serial_number": item.serial_number,
            }
            for item in ports
        ]

    async def open(self, params: dict[str, Any]) -> dict[str, Any]:
        if serial is None:
            raise RuntimeError("pyserial is not installed")

        port = str(params.get("port", "")).strip()
        if not port:
            raise ValueError("port is required")

        baudrate = int(params.get("baudrate", 9600))
        bytesize = int(params.get("bytesize", 8))
        parity = str(params.get("parity", "N")).upper()
        stopbits = float(params.get("stopbits", 1))
        timeout_ms = int(params.get("timeout_ms", 300))

        async with self._lock:
            await self._close_unlocked()
            try:
                self._ser = serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    bytesize=bytesize,
                    parity=parity,
                    stopbits=stopbits,
                    timeout=max(timeout_ms, 1) / 1000,
                )
                self._ser.reset_input_buffer()
                self._ser.reset_output_buffer()
                self._settings = {
                    "port": port,
                    "baudrate": baudrate,
                    "bytesize": bytesize,
                    "parity": parity,
                    "stopbits": stopbits,
                    "timeout_ms": timeout_ms,
                }
                self._last_error = None
                self._append_log(
                    direction="SYS",
                    payload=b"",
                    display_text=f"Connected: {port} {baudrate}/{bytesize}/{parity}/{stopbits}",
                )
            except Exception as exc:
                self._ser = None
                self._last_error = str(exc)
                self._append_log(direction="ERR", payload=b"", display_text=f"Open failed: {exc}")
                raise RuntimeError(f"open failed: {exc}") from exc

            return await self._status_unlocked()

    async def close(self) -> dict[str, Any]:
        async with self._lock:
            await self._close_unlocked()
            return await self._status_unlocked()

    async def status(self) -> dict[str, Any]:
        async with self._lock:
            return await self._status_unlocked()

    async def send(self, *, data: str, data_format: str, encoding: str, line_ending: str) -> dict[str, Any]:
        async with self._lock:
            ser = self._ensure_connected_unlocked()

            payload = self._build_payload(
                data=str(data),
                data_format=str(data_format),
                encoding=str(encoding),
                line_ending=str(line_ending),
            )
            sent = ser.write(payload)
            ser.flush()
            self._append_log(direction="TX", payload=payload, display_text=self._render_payload_text(payload, encoding))
            return {
                "ok": True,
                "bytes_sent": sent,
                "payload_hex": payload.hex(" "),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def read(self, *, max_bytes: int, timeout_ms: int, encoding: str) -> dict[str, Any]:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be > 0")

        async with self._lock:
            ser = self._ensure_connected_unlocked()

            original_timeout = ser.timeout
            payload = b""
            try:
                ser.timeout = max(timeout_ms, 0) / 1000
                in_waiting = int(getattr(ser, "in_waiting", 0) or 0)
                if in_waiting > 0:
                    payload = ser.read(min(max_bytes, in_waiting))
                else:
                    payload = ser.read(1)

                if payload and len(payload) < max_bytes:
                    remaining = max_bytes - len(payload)
                    more_waiting = int(getattr(ser, "in_waiting", 0) or 0)
                    if more_waiting > 0:
                        payload += ser.read(min(remaining, more_waiting))
            finally:
                ser.timeout = original_timeout

            if payload:
                self._append_log(direction="RX", payload=payload, display_text=self._render_payload_text(payload, encoding))

            return {
                "ok": True,
                "bytes_read": len(payload),
                "payload_text": payload.decode(encoding, errors="replace") if payload else "",
                "payload_hex": payload.hex(" "),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def pull_logs(self, *, last_seq: int, limit: int = 200) -> dict[str, Any]:
        if limit <= 0:
            limit = 1
        if limit > 500:
            limit = 500

        async with self._lock:
            if last_seq < 0:
                last_seq = 0

            entries = [item for item in self._logs if int(item.get("seq", 0)) > last_seq]
            if len(entries) > limit:
                entries = entries[-limit:]

            return {
                "ok": True,
                "entries": entries,
                "next_seq": self._log_seq,
            }

    async def _close_unlocked(self) -> None:
        previous_port = self._settings.get("port")
        was_connected = bool(self._ser is not None and getattr(self._ser, "is_open", False))
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
        self._ser = None
        if was_connected and previous_port:
            self._append_log(direction="SYS", payload=b"", display_text=f"Disconnected: {previous_port}")

    async def _status_unlocked(self) -> dict[str, Any]:
        connected = bool(self._ser is not None and getattr(self._ser, "is_open", False))
        return {
            "ok": True,
            "connected": connected,
            "settings": self._settings,
            "last_error": self._last_error,
        }

    def _ensure_connected_unlocked(self):
        if self._ser is None or not getattr(self._ser, "is_open", False):
            raise RuntimeError("serial debugger is not connected")
        return self._ser

    def _build_payload(self, *, data: str, data_format: str, encoding: str, line_ending: str) -> bytes:
        normalized_format = data_format.lower()
        if normalized_format == "hex":
            cleaned = data.replace(" ", "")
            try:
                raw = bytes.fromhex(cleaned)
            except ValueError as exc:
                raise ValueError(f"invalid hex payload: {exc}") from exc
        else:
            try:
                raw = data.encode(encoding)
            except LookupError as exc:
                raise ValueError(f"unsupported encoding: {encoding}") from exc

        ending = LINE_ENDING_MAP.get(line_ending.lower())
        if ending is None:
            raise ValueError(f"unsupported line_ending: {line_ending}")
        return raw + ending

    def _append_log(self, *, direction: str, payload: bytes, display_text: str = "") -> None:
        self._log_seq += 1
        self._logs.append(
            {
                "seq": self._log_seq,
                "direction": direction,
                "bytes": len(payload),
                "text": display_text,
                "hex": payload.hex(" "),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    def _render_payload_text(self, payload: bytes, encoding: str) -> str:
        if not payload:
            return ""
        try:
            return payload.decode(encoding, errors="replace")
        except LookupError:
            return payload.decode("utf-8", errors="replace")


serial_debug_service = SerialDebugService()
