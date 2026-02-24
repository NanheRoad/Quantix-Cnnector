from __future__ import annotations

from typing import Any

from backend.drivers.base import DeviceDriver
from backend.drivers.modbus_driver import ModbusDriver
from backend.drivers.mqtt_driver import MqttDriver
from backend.drivers.serial_driver import SerialDriver
from backend.drivers.tcp_driver import TcpDriver


def build_driver(protocol_type: str, connection_params: dict[str, Any]) -> DeviceDriver:
    normalized = protocol_type.lower()
    if normalized in {"modbus", "modbus_tcp", "modbus_rtu"}:
        return ModbusDriver(connection_params)
    if normalized == "mqtt":
        return MqttDriver(connection_params)
    if normalized == "tcp":
        return TcpDriver(connection_params)
    if normalized == "serial":
        return SerialDriver(connection_params)
    raise ValueError(f"Unsupported protocol_type: {protocol_type}")


__all__ = ["build_driver", "DeviceDriver"]
