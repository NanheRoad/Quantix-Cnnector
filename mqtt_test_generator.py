#!/usr/bin/env python3
"""
MQTT 称量数据测试生成器
用于模拟称重设备向 MQTT Broker 发送测试数据
"""

import asyncio
import json
import random
import time
from datetime import datetime
from typing import Any

import gmqtt


# ==================== 配置区域 ====================

# MQTT Broker 配置
MQTT_BROKER_HOST = "192.168.18.196"  # 修改为你的 Broker IP
MQTT_BROKER_PORT = 1883
MQTT_USERNAME = None  # 如果需要认证，设置为用户名
MQTT_PASSWORD = None  # 如果需要认证，设置为密码

# Topic 配置
MQTT_TOPIC = "sensor/weight"  # 发布主题

# 数据生成配置
DEVICE_ID = "SCALE-001"  # 设备ID
PUBLISH_INTERVAL = 1.0  # 发布间隔（秒）

# 重量模拟配置
WEIGHT_MIN = 0.0  # 最小重量（kg）
WEIGHT_MAX = 1000.0  # 最大重量（kg）
WEIGHT_STABLE = True  # True: 重量稳定变化，False: 随机跳变

# JSON 数据格式（可自定义）
JSON_FORMAT = {
    "device_id": DEVICE_ID,
    "timestamp": "",  # 自动填充时间戳
    "weight": 0.0,  # 自动填充重量
    "unit": "kg",
    "status": "stable"  # stable | unstable | error
}

# ==================== 生成器类 ====================

class MQTTDataGenerator:
    """MQTT 数据生成器"""

    def __init__(
        self,
        host: str = MQTT_BROKER_HOST,
        port: int = MQTT_BROKER_PORT,
        username: str | None = MQTT_USERNAME,
        password: str | None = MQTT_PASSWORD,
        topic: str = MQTT_TOPIC,
        interval: float = PUBLISH_INTERVAL,
        json_template: dict[str, Any] | None = None,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.topic = topic
        self.interval = interval
        self.json_template = json_template or JSON_FORMAT.copy()

        self.client: gmqtt.Client | None = None
        self.running = False
        self.current_weight = WEIGHT_MIN

        # 统计信息
        self.published_count = 0
        self.start_time = None

    def on_connect(self, client: gmqtt.Client, flags: int, rc: int, properties: Any):
        """连接回调"""
        if rc == 0:
            print(f"✓ 成功连接到 MQTT Broker: {self.host}:{self.port}")
            print(f"✓ 发布主题: {self.topic}")
        else:
            print(f"✗ 连接失败，返回码: {rc}")

    def on_disconnect(self, client: gmqtt.Client, packet: Any):
        """断开连接回调"""
        print(f"✗ 与 Broker 断开连接")
        self.running = False

    def on_message(self, client: gmqtt.Client, topic: str, payload: bytes, qos: int, properties: Any):
        """消息接收回调（如需订阅）"""
        pass

    def generate_weight(self) -> float:
        """生成重量数据"""
        if WEIGHT_STABLE:
            # 稳定变化：每次小幅度变化
            change = random.uniform(-5.0, 5.0)
            self.current_weight += change
            # 限制在范围内
            self.current_weight = max(WEIGHT_MIN, min(WEIGHT_MAX, self.current_weight))
            return round(self.current_weight, 2)
        else:
            # 随机跳变
            return round(random.uniform(WEIGHT_MIN, WEIGHT_MAX), 2)

    def generate_payload(self) -> dict[str, Any]:
        """生成 JSON 数据包"""
        weight = self.generate_weight()

        # 复制模板
        payload = self.json_template.copy()

        # 填充动态数据
        payload["timestamp"] = datetime.now().isoformat()
        payload["weight"] = weight

        # 根据重量设置状态
        if weight < WEIGHT_MIN * 0.01:
            payload["status"] = "zero"
        elif weight > WEIGHT_MAX * 0.99:
            payload["status"] = "overload"
        else:
            payload["status"] = "stable"

        return payload

    async def connect(self) -> bool:
        """连接到 MQTT Broker"""
        self.client = gmqtt.Client(self.client_id())

        if self.username and self.password:
            self.client.set_auth_credentials(self.username, self.password)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        try:
            await self.client.connect(self.host, self.port, version=4)
            await asyncio.sleep(0.5)  # 等待连接完成
            return self.client.is_connected
        except Exception as e:
            print(f"✗ 连接异常: {e}")
            return False

    def client_id(self) -> str:
        """生成客户端 ID"""
        return f"mqtt_generator_{int(time.time())}"

    async def start(self):
        """启动数据生成"""
        if not await self.connect():
            print("无法连接到 Broker，退出")
            return

        self.running = True
        self.start_time = time.time()
        print(f"\n▶ 开始生成数据，间隔: {self.interval}秒")
        print(f"   重量范围: {WEIGHT_MIN} ~ {WEIGHT_MAX} kg")
        print(f"   按 Ctrl+C 停止\n")

        try:
            while self.running:
                payload = self.generate_payload()
                payload_json = json.dumps(payload, ensure_ascii=False)

                # 发布消息
                self.client.publish(
                    self.topic,
                    payload_json.encode(),
                    qos=1,  # QoS 1: 至少一次
                )

                self.published_count += 1

                # 打印发送信息
                elapsed = time.time() - self.start_time
                rate = self.published_count / elapsed if elapsed > 0 else 0
                print(f"[{self.published_count:5d}] {payload_json} (速率: {rate:.1f} msg/s)")

                await asyncio.sleep(self.interval)

        except KeyboardInterrupt:
            print("\n\n▶ 收到停止信号")
        finally:
            await self.stop()

    async def stop(self):
        """停止生成器"""
        self.running = False
        if self.client and self.client.is_connected:
            await self.client.disconnect()

        if self.start_time:
            elapsed = time.time() - self.start_time
            print(f"\n📊 统计信息:")
            print(f"   运行时长: {elapsed:.1f} 秒")
            print(f"   发布消息: {self.published_count} 条")
            print(f"   平均速率: {self.published_count / elapsed:.2f} msg/s")


# ==================== 命令行入口 ====================

def print_banner():
    """打印横幅"""
    print("""
╔════════════════════════════════════════════════════════════╗
║        MQTT 称量数据测试生成器 v1.0                        ║
║        用于模拟称重设备发送测试数据                        ║
╚════════════════════════════════════════════════════════════╝
    """)


def print_config():
    """打印配置信息"""
    print("当前配置:")
    print(f"  Broker: {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}")
    print(f"  Topic:  {MQTT_TOPIC}")
    print(f"  设备ID: {DEVICE_ID}")
    print(f"  间隔:   {PUBLISH_INTERVAL}秒")
    print(f"  重量:   {WEIGHT_MIN} ~ {WEIGHT_MAX} kg")
    print()


async def main():
    """主函数"""
    print_banner()
    print_config()

    # 创建生成器
    generator = MQTTDataGenerator(
        host=MQTT_BROKER_HOST,
        port=MQTT_BROKER_PORT,
        username=MQTT_USERNAME,
        password=MQTT_PASSWORD,
        topic=MQTT_TOPIC,
        interval=PUBLISH_INTERVAL,
        json_template=JSON_FORMAT,
    )

    await generator.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已退出")
