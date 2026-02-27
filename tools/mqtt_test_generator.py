#!/usr/bin/env python3
"""
MQTT 称量数据测试生成器
用于模拟称重设备：
1) 周期发布重量数据
2) 订阅手动控制命令（去皮/清零）
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from datetime import datetime
from typing import Any

import gmqtt


# ==================== 配置区域 ====================

# MQTT Broker 配置
MQTT_BROKER_HOST = "192.168.18.196"
MQTT_BROKER_PORT = 1883
MQTT_USERNAME = None
MQTT_PASSWORD = None

# Topic 配置
MQTT_DATA_TOPIC = "sensor/weight"  # 重量数据发布主题
MQTT_CMD_TOPIC = "sensor/weight/cmd"  # 手动控制命令订阅主题
MQTT_ACK_TOPIC = "sensor/weight/ack"  # 命令执行结果回执主题

# 数据生成配置
DEVICE_ID = "SCALE-001"
PUBLISH_INTERVAL = 1.0  # 秒

# 重量模拟配置
WEIGHT_MIN = 0.0
WEIGHT_MAX = 1000.0
WEIGHT_STABLE = True  # True: 平稳变化，False: 随机跳变

# JSON 数据格式（固定字段）
JSON_FORMAT = {
    "device_id": DEVICE_ID,
    "timestamp": "",
    "weight": 0.0,  # 净重
    "unit": "kg",
    "status": "stable",
}


class MQTTDataGenerator:
    """MQTT 数据生成器"""

    def __init__(
        self,
        host: str = MQTT_BROKER_HOST,
        port: int = MQTT_BROKER_PORT,
        username: str | None = MQTT_USERNAME,
        password: str | None = MQTT_PASSWORD,
        data_topic: str = MQTT_DATA_TOPIC,
        cmd_topic: str = MQTT_CMD_TOPIC,
        ack_topic: str = MQTT_ACK_TOPIC,
        interval: float = PUBLISH_INTERVAL,
        json_template: dict[str, Any] | None = None,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.data_topic = data_topic
        self.cmd_topic = cmd_topic
        self.ack_topic = ack_topic
        self.interval = interval
        self.json_template = json_template or JSON_FORMAT.copy()

        self.client: gmqtt.Client | None = None
        self.running = False

        # raw_weight: 传感器原始重量；tare_offset: 去皮偏移；weight=raw_weight-tare_offset
        self.raw_weight = WEIGHT_MIN
        self.tare_offset = 0.0

        self.last_command: str | None = None
        self.last_command_time: str | None = None

        self.published_count = 0
        self.start_time: float | None = None

    def on_connect(self, client: gmqtt.Client, flags: int, rc: int, properties: Any):
        _ = (client, flags, properties)
        if rc == 0:
            print(f"[ok] connected broker: {self.host}:{self.port}")
            print(f"[ok] publish topic: {self.data_topic}")
            print(f"[ok] subscribe cmd topic: {self.cmd_topic}")
            if self.client is not None:
                self.client.subscribe(self.cmd_topic, qos=1)
        else:
            print(f"[err] connect failed, rc={rc}")

    def on_disconnect(self, client: gmqtt.Client, packet: Any):
        _ = (client, packet)
        print("[warn] disconnected from broker")
        self.running = False

    def on_message(self, client: gmqtt.Client, topic: str, payload: bytes, qos: int, properties: Any):
        _ = (client, qos, properties)
        if topic != self.cmd_topic:
            return
        self._handle_command(payload)

    def _handle_command(self, payload: bytes) -> None:
        payload_text = payload.decode("utf-8", errors="ignore").strip()
        command, command_detail = self._parse_command(payload_text)

        now = datetime.now().isoformat()
        ok = True
        message = ""

        if command == "tare":
            self.tare_offset = self.raw_weight
            message = "tare applied"
        elif command == "zero":
            self.raw_weight = 0.0
            self.tare_offset = 0.0
            message = "zero applied"
        else:
            ok = False
            message = f"unsupported command: {command_detail}"

        self.last_command = command_detail
        self.last_command_time = now
        net_weight = self.current_weight()
        print(
            f"[cmd] raw='{payload_text}' parsed='{command_detail}' "
            f"result={'ok' if ok else 'failed'} weight={net_weight:.2f}kg "
            f"raw_weight={self.raw_weight:.2f} offset={self.tare_offset:.2f}"
        )

        ack = {
            "type": "command_ack",
            "device_id": DEVICE_ID,
            "timestamp": now,
            "command": command_detail,
            "ok": ok,
            "message": message,
            "weight": round(net_weight, 2),
            "raw_weight": round(self.raw_weight, 2),
            "tare_offset": round(self.tare_offset, 2),
            "unit": "kg",
        }
        self._publish_ack(ack)

    def _parse_command(self, payload_text: str) -> tuple[str, str]:
        """
        支持两种命令格式：
        1) JSON: {"cmd":"tare"} 或 {"command":"zero"}
        2) 纯文本: tare / zero
        """
        command_raw = payload_text
        try:
            body = json.loads(payload_text)
            if isinstance(body, dict):
                command_raw = str(body.get("cmd") or body.get("command") or body.get("action") or "")
        except json.JSONDecodeError:
            pass

        normalized = command_raw.strip().lower()
        if normalized in {"tare", "去皮"}:
            return "tare", command_raw
        if normalized in {"zero", "clear_zero", "清零", "归零", "置零"}:
            return "zero", command_raw
        return "unsupported", command_raw

    def _publish_ack(self, ack: dict[str, Any]) -> None:
        if self.client is None or not self.client.is_connected:
            return
        payload = json.dumps(ack, ensure_ascii=False)
        self.client.publish(self.ack_topic, payload.encode("utf-8"), qos=1)

    def generate_raw_weight(self) -> float:
        if WEIGHT_STABLE:
            self.raw_weight += random.uniform(-5.0, 5.0)
            self.raw_weight = max(WEIGHT_MIN, min(WEIGHT_MAX, self.raw_weight))
            return round(self.raw_weight, 2)
        self.raw_weight = round(random.uniform(WEIGHT_MIN, WEIGHT_MAX), 2)
        return self.raw_weight

    def current_weight(self) -> float:
        # 实际净重允许为负（极少见）；这里统一夹到 >=0 便于演示
        return max(0.0, self.raw_weight - self.tare_offset)

    def generate_payload(self) -> dict[str, Any]:
        self.generate_raw_weight()
        weight = round(self.current_weight(), 2)

        payload = self.json_template.copy()
        payload["timestamp"] = datetime.now().isoformat()
        payload["weight"] = weight
        payload["raw_weight"] = round(self.raw_weight, 2)
        payload["tare_offset"] = round(self.tare_offset, 2)
        payload["last_command"] = self.last_command
        payload["last_command_time"] = self.last_command_time

        if weight <= 0.0001:
            payload["status"] = "zero"
        elif weight > WEIGHT_MAX * 0.99:
            payload["status"] = "overload"
        else:
            payload["status"] = "stable"

        return payload

    async def connect(self) -> bool:
        self.client = gmqtt.Client(self.client_id())

        if self.username and self.password:
            self.client.set_auth_credentials(self.username, self.password)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        try:
            await self.client.connect(self.host, self.port, version=4)
            await asyncio.sleep(0.5)
            return self.client.is_connected
        except Exception as exc:
            print(f"[err] connect exception: {exc}")
            return False

    def client_id(self) -> str:
        return f"mqtt_generator_{int(time.time())}"

    async def start(self):
        if not await self.connect():
            print("[err] cannot connect broker, exit")
            return

        self.running = True
        self.start_time = time.time()
        print(f"[run] publish interval={self.interval}s")
        print(f"[run] weight range={WEIGHT_MIN}~{WEIGHT_MAX}kg")
        print("[run] press Ctrl+C to stop\n")

        try:
            while self.running:
                payload = self.generate_payload()
                payload_json = json.dumps(payload, ensure_ascii=False)

                assert self.client is not None
                self.client.publish(self.data_topic, payload_json.encode("utf-8"), qos=1)
                self.published_count += 1

                elapsed = max(time.time() - (self.start_time or time.time()), 1e-6)
                rate = self.published_count / elapsed
                print(f"[{self.published_count:5d}] {payload_json} (rate={rate:.1f} msg/s)")
                await asyncio.sleep(self.interval)
        except KeyboardInterrupt:
            print("\n[stop] keyboard interrupt")
        finally:
            await self.stop()

    async def stop(self):
        self.running = False
        if self.client and self.client.is_connected:
            await self.client.disconnect()

        if self.start_time:
            elapsed = time.time() - self.start_time
            avg_rate = self.published_count / max(elapsed, 1e-6)
            print("\n[stats]")
            print(f"  duration={elapsed:.1f}s")
            print(f"  published={self.published_count}")
            print(f"  avg_rate={avg_rate:.2f} msg/s")


def print_config() -> None:
    print("Current config:")
    print(f"  Broker:   {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}")
    print(f"  Data:     {MQTT_DATA_TOPIC}")
    print(f"  Cmd:      {MQTT_CMD_TOPIC}")
    print(f"  Ack:      {MQTT_ACK_TOPIC}")
    print(f"  Device:   {DEVICE_ID}")
    print(f"  Interval: {PUBLISH_INTERVAL}s")
    print(f"  Range:    {WEIGHT_MIN}~{WEIGHT_MAX}kg")
    print()


async def main():
    print_config()
    generator = MQTTDataGenerator(
        host=MQTT_BROKER_HOST,
        port=MQTT_BROKER_PORT,
        username=MQTT_USERNAME,
        password=MQTT_PASSWORD,
        data_topic=MQTT_DATA_TOPIC,
        cmd_topic=MQTT_CMD_TOPIC,
        ack_topic=MQTT_ACK_TOPIC,
        interval=PUBLISH_INTERVAL,
        json_template=JSON_FORMAT,
    )
    await generator.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[exit] bye")
