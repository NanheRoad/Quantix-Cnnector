from __future__ import annotations

import random
from typing import Any

from backend.drivers.base import DeviceDriver
from config.settings import settings

try:
    from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient
except Exception:  # pragma: no cover
    AsyncModbusTcpClient = None
    AsyncModbusSerialClient = None


class ModbusDriver(DeviceDriver):
    def __init__(self, connection_params: dict[str, Any]):
        super().__init__(connection_params)
        self.client = None
        self._connected = False

    async def connect(self) -> bool:
        host = self.connection_params.get("host")
        port_name = self.connection_params.get("port")

        if host and AsyncModbusTcpClient is not None:
            client = AsyncModbusTcpClient(
                host=host,
                port=int(self.connection_params.get("port", 502)),
            )
            self._connected = await client.connect()
            self.client = client if self._connected else None
            if self._connected:
                return True
            if settings.simulate_on_connect_fail:
                self.client = None
                self._connected = True
                return True
            return False

        if not host and port_name and AsyncModbusSerialClient is not None:
            client = AsyncModbusSerialClient(
                port=port_name,
                baudrate=int(self.connection_params.get("baudrate", 9600)),
                parity=str(self.connection_params.get("parity", "N")),
                stopbits=int(self.connection_params.get("stopbits", 1)),
                bytesize=int(self.connection_params.get("bytesize", 8)),
                timeout=float(self.connection_params.get("timeout", 1.0)),
            )
            self._connected = await client.connect()
            self.client = client if self._connected else None
            if self._connected:
                return True
            if settings.simulate_on_connect_fail:
                self.client = None
                self._connected = True
                return True
            return False

        # Fallback mode for local development without hardware/dependencies.
        self._connected = True
        return True

    async def disconnect(self) -> bool:
        if self.client is not None:
            self.client.close()
        self.client = None
        self._connected = False
        return True

    async def is_connected(self) -> bool:
        return self._connected

    async def execute_action(self, action: str, params: dict[str, Any]) -> Any:
        if self.client is None:
            return self._simulate(action, params)

        slave_id = int(params.get("slave_id", 1))
        address = int(params.get("address", 0))

        if action == "modbus.read_input_registers":
            count = int(params.get("count", 2))
            result = await self.client.read_input_registers(address=address, count=count, slave=slave_id)
            if result.isError():
                raise RuntimeError(str(result))
            return {"registers": list(result.registers)}

        if action == "modbus.read_holding_registers":
            count = int(params.get("count", 2))
            result = await self.client.read_holding_registers(address=address, count=count, slave=slave_id)
            if result.isError():
                raise RuntimeError(str(result))
            return {"registers": list(result.registers)}

        if action == "modbus.read_coils":
            count = int(params.get("count", 8))
            result = await self.client.read_coils(address=address, count=count, slave=slave_id)
            if result.isError():
                raise RuntimeError(str(result))
            return {"coils": list(result.bits)[:count]}

        if action == "modbus.read_discrete_inputs":
            count = int(params.get("count", 8))
            result = await self.client.read_discrete_inputs(address=address, count=count, slave=slave_id)
            if result.isError():
                raise RuntimeError(str(result))
            return {"coils": list(result.bits)[:count]}

        if action == "modbus.write_register":
            value = int(params.get("value", 0))
            result = await self.client.write_register(address=address, value=value, slave=slave_id)
            if result.isError():
                raise RuntimeError(str(result))
            return {"ok": True}

        if action == "modbus.write_coil":
            value = bool(params.get("value", 0))
            result = await self.client.write_coil(address=address, value=value, slave=slave_id)
            if result.isError():
                raise RuntimeError(str(result))
            return {"ok": True}

        raise ValueError(f"Unsupported action for ModbusDriver: {action}")

    # 生成模拟数据
    def _simulate(self, action: str, params: dict[str, Any]) -> Any:
        if action.startswith("modbus.read"):
            count = int(params.get("count", 2))
            kg = random.uniform(0.0, 30.0)
            raw = int(kg * 1000)
            hi = (raw >> 16) & 0xFFFF
            lo = raw & 0xFFFF
            registers = [hi, lo]
            while len(registers) < count:
                registers.append(0)
            return {"registers": registers[:count], "coils": [True, False, True, False]}

        if action.startswith("modbus.write"):
            return {"ok": True}

        raise ValueError(f"Unsupported action for ModbusDriver: {action}")
