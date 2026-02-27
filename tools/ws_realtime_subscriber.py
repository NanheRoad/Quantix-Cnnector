#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from typing import Any

try:
    import websockets
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: websockets\n"
        "Install with: pip install websockets"
    ) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Quantix WebSocket real-time subscriber (single file).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Quantix backend host")
    parser.add_argument("--port", type=int, default=8000, help="Quantix backend port")
    parser.add_argument("--api-key", default="quantix-dev-key", help="API key for /ws")
    parser.add_argument("--device-id", type=int, default=None, help="Only show one device")
    parser.add_argument("--show-ping", action="store_true", help="Print ping messages")
    parser.add_argument("--raw", action="store_true", help="Print raw JSON message")
    parser.add_argument("--wss", action="store_true", help="Use wss:// instead of ws://")
    return parser.parse_args()


def format_timestamp(value: Any) -> str:
    if not value:
        return "-"
    raw = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return str(value)
    if dt.tzinfo is not None:
        dt = dt.astimezone()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def build_ws_url(host: str, port: int, api_key: str, use_wss: bool) -> str:
    scheme = "wss" if use_wss else "ws"
    return f"{scheme}://{host}:{port}/ws?api_key={api_key}"


async def run_subscriber(
    url: str,
    device_id: int | None,
    show_ping: bool,
    show_raw: bool,
) -> None:
    backoff = 1.0
    max_backoff = 30.0

    while True:
        try:
            print(f"[connect] {url}")
            async with websockets.connect(url, ping_interval=20, ping_timeout=20, open_timeout=10) as ws:
                print("[connected] waiting for real-time updates...")
                backoff = 1.0

                async for text in ws:
                    try:
                        message = json.loads(text)
                    except json.JSONDecodeError:
                        print(f"[non-json] {text}")
                        continue

                    if show_raw:
                        print(json.dumps(message, ensure_ascii=False))
                        continue

                    message_type = message.get("type")
                    if message_type == "ping":
                        if show_ping:
                            print("[ping]")
                        continue

                    if message_type != "weight_update":
                        print(f"[event:{message_type}] {message}")
                        continue

                    current_device_id = message.get("device_id")
                    if device_id is not None and current_device_id != device_id:
                        continue

                    ts = format_timestamp(message.get("timestamp"))
                    weight = message.get("weight")
                    unit = message.get("unit", "kg")
                    status = message.get("status", "-")
                    name = message.get("device_name", "-")
                    error = message.get("error")

                    line = (
                        f"[{ts}] device_id={current_device_id} name={name} "
                        f"status={status} weight={weight} {unit}"
                    )
                    if error:
                        line += f" error={error}"
                    print(line)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[disconnected] {exc}")
            print(f"[reconnect] retry in {backoff:.1f}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)


async def main() -> None:
    args = parse_args()
    url = build_ws_url(args.host, args.port, args.api_key, args.wss)
    await run_subscriber(
        url=url,
        device_id=args.device_id,
        show_ping=args.show_ping,
        show_raw=args.raw,
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[exit] stopped by user")
