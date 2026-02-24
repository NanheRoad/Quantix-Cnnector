from __future__ import annotations

import asyncio
import uuid
from typing import Any

from backend.drivers.base import DeviceDriver, MessageHandler

try:
    from gmqtt import Client as MQTTClient
except Exception:  # pragma: no cover
    MQTTClient = None


class MqttDriver(DeviceDriver):
    def __init__(self, connection_params: dict[str, Any]):
        super().__init__(connection_params)
        self._client = None
        self._connected = False
        self._handler: MessageHandler | None = None

    def register_message_handler(self, handler: MessageHandler) -> None:
        self._handler = handler

    async def connect(self) -> bool:
        if MQTTClient is None:
            self._connected = True
            return True

        host = self.connection_params.get("host", "127.0.0.1")
        port = int(self.connection_params.get("port", 1883))

        client_id = f"quantix-{uuid.uuid4().hex[:8]}"
        self._client = MQTTClient(client_id)

        username = self.connection_params.get("username")
        password = self.connection_params.get("password")
        if username:
            self._client.set_auth_credentials(username, password)

        self._client.on_message = self._on_message
        await self._client.connect(host, port=port, keepalive=30)
        self._connected = True
        return True

    async def disconnect(self) -> bool:
        if self._client is not None:
            await self._client.disconnect()
        self._connected = False
        self._client = None
        return True

    async def is_connected(self) -> bool:
        return self._connected

    async def execute_action(self, action: str, params: dict[str, Any]) -> Any:
        if action == "mqtt.subscribe":
            topic = str(params.get("topic", ""))
            qos = int(params.get("qos", 0))
            if self._client is not None:
                self._client.subscribe(topic, qos=qos)
            return {"topic": topic, "qos": qos}

        if action == "mqtt.publish":
            topic = str(params.get("topic", ""))
            payload = params.get("payload", "")
            qos = int(params.get("qos", 0))
            if self._client is not None:
                self._client.publish(topic, payload, qos=qos)
            return {"topic": topic, "published": True}

        if action == "mqtt.on_message":
            return {"ok": True}

        raise ValueError(f"Unsupported action for MqttDriver: {action}")

    def _on_message(self, client, topic, payload, qos, properties) -> None:
        _ = (client, qos, properties)
        if self._handler is None:
            return

        raw_payload = payload if isinstance(payload, bytes) else str(payload).encode("utf-8")
        asyncio.create_task(self._handler(topic, raw_payload))
