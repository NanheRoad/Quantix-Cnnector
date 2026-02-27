#!/usr/bin/env python3
"""
虚拟串口模拟器 - 单文件版本
支持创建虚拟串口对，Modbus RTU Master/Slave 模式
兼容 Windows 和 macOS/Linux
"""

import sys
import time
import threading
import socket
import select
import struct
import math
import random
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple, List, Callable

try:
    import serial
    import serial.tools.list_ports
    from serial.serialutil import SerialException
except ImportError:
    print("Error: pyserial is required")
    print("Please run: pip install pyserial")
    sys.exit(1)

try:
    from pymodbus.utilities import computeCRC
except ImportError:
    # fallback CRC implementation
    def computeCRC(data: bytes) -> int:
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc


class Platform(Enum):
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"


class Mode(Enum):
    RAW = "原始串口"
    MODBUS_MASTER = "Modbus RTU Master"
    MODBUS_SLAVE = "Modbus RTU Slave"


class DataPattern(Enum):
    FIXED = "固定值"
    RANDOM = "随机"
    SINE_WAVE = "正弦波"
    RANDOM_WALK = "随机游走"


def get_platform() -> Platform:
    """检测当前平台"""
    if sys.platform.startswith('win'):
        return Platform.WINDOWS
    elif sys.platform.startswith('darwin'):
        return Platform.MACOS
    else:
        return Platform.LINUX


class VirtualSerialPair:
    """虚拟串口对管理器"""

    def __init__(self, port_a: str = None, port_b: str = None, baudrate: int = 9600):
        self.platform = get_platform()
        self.port_a = port_a
        self.port_b = port_b
        self.baudrate = baudrate
        self.running = False
        self.callback = None
        self.thread = None

        # 数据存储
        self.data_buffer_a = []
        self.data_buffer_b = []
        self.lock = threading.Lock()

    def create_virtual_pair(self) -> Tuple[str, str]:
        """创建虚拟串口对"""
        if self.platform == Platform.WINDOWS:
            return self._create_windows_pair()
        else:
            return self._create_pty_pair()

    def _create_windows_pair(self) -> Tuple[str, str]:
        """Windows: 使用TCP转发模拟虚拟串口对"""
        # 创建两个TCP端口作为串口模拟
        self.tcp_port_a = 20000
        self.tcp_port_b = 20001

        print(f"\n[Windows模式] Creating virtual serial pair:")
        print(f"  Port A: COM_TCP_{self.tcp_port_a} (模拟)")
        print(f"  Port B: COM_TCP_{self.tcp_port_b} (模拟)")
        print(f"\n提示: Windows下建议使用两个物理串口或com0com创建的虚拟串口对")
        print(f"可以配置程序连接到实际存在的串口\n")

        return f"TCP_PORT_{self.tcp_port_a}", f"TCP_PORT_{self.tcp_port_b}"

    def _create_pty_pair(self) -> Tuple[str, str]:
        """macOS/Linux: 使用pty创建伪终端对"""
        try:
            import pty
            import os

            master_a, slave_a = pty.openpty()
            master_b, slave_b = pty.openpty()

            self.master_a = master_a
            self.master_b = master_b
            self.slave_name_a = os.ttyname(slave_a)
            self.slave_name_b = os.ttyname(slave_b)

            print(f"\n[Unix Mode] Creating virtual serial pair:")
            print(f"  Port A: {self.slave_name_a}")
            print(f"  Port B: {self.slave_name_b}\n")

            return self.slave_name_a, self.slave_name_b

        except (ImportError, OSError) as e:
            print(f"Warning: Cannot create PTY ({e})")
            print("Will use TCP forwarding as fallback")
            return self._create_windows_pair()

    def start_forwarding(self, callback: Callable[[str, bytes], None]):
        """启动数据转发"""
        self.callback = callback
        self.running = True

        if self.platform == Platform.WINDOWS or not hasattr(self, 'master_a'):
            self.thread = threading.Thread(target=self._tcp_forward_loop, daemon=True)
        else:
            self.thread = threading.Thread(target=self._pty_forward_loop, daemon=True)

        self.thread.start()

    def _tcp_forward_loop(self):
        """TCP转发循环"""
        server_a = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_b = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_a.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_b.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            server_a.bind(('127.0.0.1', self.tcp_port_a))
            server_b.bind(('127.0.0.1', self.tcp_port_b))
            server_a.listen(1)
            server_b.listen(1)

            print(f"[TCP Forwarding] Listening on ports {self.tcp_port_a} 和 {self.tcp_port_b}")
            print("Connect serial tools to these ports for testing\n")

            conn_a = None
            conn_b = None

            server_a.settimeout(1)
            server_b.settimeout(1)

            while self.running:
                try:
                    if conn_a is None:
                        try:
                            conn_a, addr = server_a.accept()
                            self.callback("PORT_A", b"[Connected] " + str(addr).encode())
                        except socket.timeout:
                            continue

                    if conn_b is None:
                        try:
                            conn_b, addr = server_b.accept()
                            self.callback("PORT_B", b"[Connected] " + str(addr).encode())
                        except socket.timeout:
                            continue

                    # 双向转发
                    if conn_a and conn_b:
                        readable, _, _ = select.select([conn_a, conn_b], [], [], 0.1)

                        for sock in readable:
                            try:
                                data = sock.recv(1024)
                                if data:
                                    if sock == conn_a:
                                        conn_b.sendall(data)
                                        self.callback("A->B", data)
                                    else:
                                        conn_a.sendall(data)
                                        self.callback("B->A", data)
                                else:
                                    # 连接断开
                                    if sock == conn_a:
                                        conn_a.close()
                                        conn_a = None
                                    else:
                                        conn_b.close()
                                        conn_b = None
                            except:
                                pass

                except Exception as e:
                    if self.running:
                        time.sleep(0.1)

        except Exception as e:
            print(f"[Error] TCP forwarding: {e}")
        finally:
            server_a.close()
            server_b.close()

    def _pty_forward_loop(self):
        """PTY转发循环"""
        try:
            import os
            import fcntl
            import os

            os.set_blocking(self.master_a, False)
            os.set_blocking(self.master_b, False)

            while self.running:
                try:
                    readable, _, _ = select.select([self.master_a, self.master_b], [], [], 0.1)

                    for master in readable:
                        try:
                            data = os.read(master, 1024)
                            if data:
                                if master == self.master_a:
                                    os.write(self.master_b, data)
                                    self.callback("A->B", data)
                                else:
                                    os.write(self.master_a, data)
                                    self.callback("B->A", data)
                        except (OSError, BlockingIOError):
                            pass

                except Exception as e:
                    if self.running:
                        time.sleep(0.01)

        except Exception as e:
            print(f"[Error] PTY forwarding: {e}")

    def stop(self):
        """停止转发"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)

    def write_to_a(self, data: bytes):
        """向端口A写入数据"""
        if self.platform == Platform.WINDOWS:
            # TCP模式下通过回调处理
            self.callback("WRITE_A", data)
        elif hasattr(self, 'master_b'):
            try:
                import os
                os.write(self.master_b, data)
            except:
                pass

    def write_to_b(self, data: bytes):
        """向端口B写入数据"""
        if self.platform == Platform.WINDOWS:
            self.callback("WRITE_B", data)
        elif hasattr(self, 'master_a'):
            try:
                import os
                os.write(self.master_a, data)
            except:
                pass


class ModbusSlave:
    """Modbus RTU 从设备模拟器"""

    def __init__(self, unit_id: int = 1):
        self.unit_id = unit_id
        self.holding_registers = [100 + i for i in range(100)]  # 40001-40100
        self.input_registers = [200 + i for i in range(100)]     # 30001-30100
        self.coils = [True, False] * 50                          # 00001-00100
        self.discrete_inputs = [False, True] * 50                # 10001-10100

        # 数据模拟配置
        self.pattern = DataPattern.RANDOM_WALK
        self.sine_phase = 0.0
        self.last_update = time.time()

    def update_simulation(self):
        """更新模拟数据"""
        now = time.time()
        if now - self.last_update < 0.1:  # 100ms更新一次
            return
        self.last_update = now

        for i in range(len(self.holding_registers)):
            if self.pattern == DataPattern.FIXED:
                pass
            elif self.pattern == DataPattern.RANDOM:
                self.holding_registers[i] = random.randint(0, 65535)
            elif self.pattern == DataPattern.SINE_WAVE:
                self.sine_phase += 0.1
                value = int(32768 + 32767 * math.sin(self.sine_phase + i * 0.1))
                self.holding_registers[i] = max(0, min(65535, value))
            elif self.pattern == DataPattern.RANDOM_WALK:
                change = random.randint(-10, 10)
                self.holding_registers[i] = max(0, min(65535, self.holding_registers[i] + change))

        # 输入寄存器也同步更新
        self.input_registers = [x + 1000 for x in self.holding_registers[:100]]

    def process_request(self, request: bytes) -> Optional[bytes]:
        """处理Modbus请求并返回响应"""
        if len(request) < 4:
            return None

        slave_addr = request[0]
        function_code = request[1]

        if slave_addr != self.unit_id and slave_addr != 0:
            return None

        try:
            if function_code == 0x01:  # 读线圈
                return self._read_coils(request)
            elif function_code == 0x02:  # 读离散输入
                return self._read_discrete_inputs(request)
            elif function_code == 0x03:  # 读保持寄存器
                return self._read_holding_registers(request)
            elif function_code == 0x04:  # 读输入寄存器
                return self._read_input_registers(request)
            elif function_code == 0x05:  # 写单个线圈
                return self._write_single_coil(request)
            elif function_code == 0x06:  # 写单个寄存器
                return self._write_single_register(request)
            elif function_code == 0x0F:  # 写多个线圈
                return self._write_multiple_coils(request)
            elif function_code == 0x10:  # 写多个寄存器
                return self._write_multiple_registers(request)
            else:
                # 异常响应
                return self._exception_response(function_code, 0x01)

        except Exception as e:
            return self._exception_response(function_code, 0x02)

    def _read_holding_registers(self, request: bytes) -> bytes:
        """功能码03: 读保持寄存器"""
        start_addr = struct.unpack('>H', request[2:4])[0]
        quantity = struct.unpack('>H', request[4:6])[0]

        if quantity > 125 or start_addr + quantity > len(self.holding_registers):
            return self._exception_response(0x03, 0x02)

        data = bytearray([self.unit_id, 0x03, quantity * 2])
        for i in range(quantity):
            addr = start_addr + i
            if addr < len(self.holding_registers):
                value = self.holding_registers[addr]
                data.extend(struct.pack('>H', value))

        crc = computeCRC(bytes(data[:-2]))
        data.extend(struct.pack('<H', crc))
        return bytes(data)

    def _read_input_registers(self, request: bytes) -> bytes:
        """功能码04: 读输入寄存器"""
        start_addr = struct.unpack('>H', request[2:4])[0]
        quantity = struct.unpack('>H', request[4:6])[0]

        if quantity > 125 or start_addr + quantity > len(self.input_registers):
            return self._exception_response(0x04, 0x02)

        data = bytearray([self.unit_id, 0x04, quantity * 2])
        for i in range(quantity):
            addr = start_addr + i
            if addr < len(self.input_registers):
                value = self.input_registers[addr]
                data.extend(struct.pack('>H', value))

        crc = computeCRC(bytes(data[:-2]))
        data.extend(struct.pack('<H', crc))
        return bytes(data)

    def _read_coils(self, request: bytes) -> bytes:
        """功能码01: 读线圈"""
        start_addr = struct.unpack('>H', request[2:4])[0]
        quantity = struct.unpack('>H', request[4:6])[0]

        if quantity > 2000 or start_addr + quantity > len(self.coils):
            return self._exception_response(0x01, 0x02)

        byte_count = (quantity + 7) // 8
        data = bytearray([self.unit_id, 0x01, byte_count])

        for i in range(byte_count):
            byte_val = 0
            for bit in range(8):
                addr = start_addr + i * 8 + bit
                if addr < min(start_addr + quantity, len(self.coils)):
                    if self.coils[addr]:
                        byte_val |= (1 << bit)
            data.append(byte_val)

        crc = computeCRC(bytes(data[:-2]))
        data.extend(struct.pack('<H', crc))
        return bytes(data)

    def _read_discrete_inputs(self, request: bytes) -> bytes:
        """功能码02: 读离散输入"""
        start_addr = struct.unpack('>H', request[2:4])[0]
        quantity = struct.unpack('>H', request[4:6])[0]

        if quantity > 2000 or start_addr + quantity > len(self.discrete_inputs):
            return self._exception_response(0x02, 0x02)

        byte_count = (quantity + 7) // 8
        data = bytearray([self.unit_id, 0x02, byte_count])

        for i in range(byte_count):
            byte_val = 0
            for bit in range(8):
                addr = start_addr + i * 8 + bit
                if addr < min(start_addr + quantity, len(self.discrete_inputs)):
                    if self.discrete_inputs[addr]:
                        byte_val |= (1 << bit)
            data.append(byte_val)

        crc = computeCRC(bytes(data[:-2]))
        data.extend(struct.pack('<H', crc))
        return bytes(data)

    def _write_single_coil(self, request: bytes) -> bytes:
        """功能码05: 写单个线圈"""
        addr = struct.unpack('>H', request[2:4])[0]
        value = struct.unpack('>H', request[4:6])[0]

        if addr >= len(self.coils):
            return self._exception_response(0x05, 0x02)

        self.coils[addr] = (value == 0xFF00)

        # 回显请求
        crc = computeCRC(request[:6])
        response = bytearray(request[:6])
        response.extend(struct.pack('<H', crc))
        return bytes(response)

    def _write_single_register(self, request: bytes) -> bytes:
        """功能码06: 写单个寄存器"""
        addr = struct.unpack('>H', request[2:4])[0]
        value = struct.unpack('>H', request[4:6])[0]

        if addr >= len(self.holding_registers):
            return self._exception_response(0x06, 0x02)

        self.holding_registers[addr] = value

        # 回显请求
        crc = computeCRC(request[:6])
        response = bytearray(request[:6])
        response.extend(struct.pack('<H', crc))
        return bytes(response)

    def _write_multiple_coils(self, request: bytes) -> bytes:
        """功能码15: 写多个线圈"""
        start_addr = struct.unpack('>H', request[2:4])[0]
        quantity = struct.unpack('>H', request[4:6])[0]
        byte_count = request[6]

        if quantity > 1968 or start_addr + quantity > len(self.coils):
            return self._exception_response(0x0F, 0x02)

        for i in range(quantity):
            addr = start_addr + i
            byte_idx = i // 8
            bit_idx = i % 8
            if byte_idx < byte_count:
                self.coils[addr] = bool(request[7 + byte_idx] & (1 << bit_idx))

        # 响应: 地址, 数量
        response = bytearray([self.unit_id, 0x0F])
        response.extend(request[2:6])
        crc = computeCRC(bytes(response[:-2]))
        response.extend(struct.pack('<H', crc))
        return bytes(response)

    def _write_multiple_registers(self, request: bytes) -> bytes:
        """功能码16: 写多个寄存器"""
        start_addr = struct.unpack('>H', request[2:4])[0]
        quantity = struct.unpack('>H', request[4:6])[0]
        byte_count = request[6]

        if quantity > 123 or start_addr + quantity > len(self.holding_registers):
            return self._exception_response(0x10, 0x02)

        for i in range(quantity):
            addr = start_addr + i
            if addr < len(self.holding_registers):
                offset = 7 + i * 2
                if offset + 1 < len(request):
                    self.holding_registers[addr] = struct.unpack('>H', request[offset:offset+2])[0]

        # 响应: 地址, 数量
        response = bytearray([self.unit_id, 0x10])
        response.extend(request[2:6])
        crc = computeCRC(bytes(response[:-2]))
        response.extend(struct.pack('<H', crc))
        return bytes(response)

    def _exception_response(self, function_code: int, exception_code: int) -> bytes:
        """生成异常响应"""
        response = bytearray([self.unit_id, function_code | 0x80, exception_code])
        crc = computeCRC(bytes(response[:-2]))
        response.extend(struct.pack('<H', crc))
        return bytes(response)


class ModbusMaster:
    """Modbus RTU 主设备模拟器"""

    def __init__(self, unit_id: int = 1, poll_interval: float = 1.0):
        self.unit_id = unit_id
        self.poll_interval = poll_interval
        self.running = False
        self.send_callback = None

    def set_send_callback(self, callback: Callable[[bytes], None]):
        """设置发送回调"""
        self.send_callback = callback

    def start_polling(self):
        """开始轮询"""
        self.running = True
        thread = threading.Thread(target=self._poll_loop, daemon=True)
        thread.start()

    def _poll_loop(self):
        """轮询循环"""
        while self.running:
            self._read_holding_registers(0, 10)
            time.sleep(self.poll_interval)

    def _read_holding_registers(self, start_addr: int, quantity: int):
        """读保持寄存器"""
        request = struct.pack('>BBHH', self.unit_id, 0x03, start_addr, quantity)
        crc = computeCRC(request)
        request += struct.pack('<H', crc)

        if self.send_callback:
            self.send_callback(request)

    def send_custom_request(self, function_code: int, data: bytes):
        """发送自定义请求"""
        request = bytearray([self.unit_id, function_code])
        request.extend(data)
        crc = computeCRC(bytes(request[:-2]))
        request.extend(struct.pack('<H', crc))

        if self.send_callback:
            self.send_callback(bytes(request))

    def stop(self):
        """停止轮询"""
        self.running = False


class SerialSimulator:
    """串口模拟器主类"""

    def __init__(self):
        self.platform = get_platform()
        self.virtual_pair = None
        self.mode = Mode.MODBUS_SLAVE
        self.modbus_slave = ModbusSlave()
        self.modbus_master = None
        self.serial_port = None
        self.running = False

        # 显示配置
        self.show_hex = True
        self.show_timestamp = True

        # 统计
        self.rx_count = 0
        self.tx_count = 0

        # 周期性发送配置
        self.auto_send_enabled = False
        self.auto_send_interval = 1.0  # 秒
        self.auto_send_data = bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x01])  # 默认Modbus读请求
        self.auto_send_thread = None

    def list_available_ports(self):
        """列出可用串口"""
        print("\n═══════════════ 可用串口 ═══════════════")
        ports = serial.tools.list_ports.comports()
        if not ports:
            print("  没有找到可用串口")
        else:
            for i, port in enumerate(ports, 1):
                print(f"  {i}. {port.device} - {port.description}")
        print("═══════════════════════════════════════\n")

    def create_virtual_serial_pair(self) -> bool:
        """创建虚拟串口对"""
        try:
            self.virtual_pair = VirtualSerialPair()
            port_a, port_b = self.virtual_pair.create_virtual_pair()
            print(f"[成功] 虚拟串口对已创建")
            print(f"  Port A: {port_a}")
            print(f"  Port B: {port_b}")
            return True
        except Exception as e:
            print(f"[错误] 创建虚拟串口失败: {e}")
            return False

    def connect_to_serial(self, port: str, baudrate: int = 9600) -> bool:
        """连接到串口"""
        try:
            # 如果是TCP端口，使用socket
            if port.startswith("TCP_PORT"):
                print(f"[信息] TCP模式，使用socket连接")
                return True

            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
            print(f"[成功] 已连接到 {port} @ {baudrate}")
            return True
        except SerialException as e:
            print(f"[错误] 连接失败: {e}")
            return False

    def set_mode(self, mode: Mode):
        """设置工作模式"""
        self.mode = mode
        print(f"[信息] 模式已切换为: {mode.value}")

        if mode == Mode.MODBUS_SLAVE:
            self.modbus_slave = ModbusSlave()
            self.modbus_master = None
        elif mode == Mode.MODBUS_MASTER:
            self.modbus_master = ModbusMaster()
            if self.serial_port:
                self.modbus_master.set_send_callback(self._send_data)
            self.modbus_master.start_polling()

    def start(self):
        """启动模拟器"""
        self.running = True

        if self.virtual_pair:
            self.virtual_pair.start_forwarding(self._on_data_received)

        # 启动模拟数据更新线程
        sim_thread = threading.Thread(target=self._simulation_loop, daemon=True)
        sim_thread.start()

        # 主循环
        self._main_loop()

    def _simulation_loop(self):
        """模拟数据更新循环"""
        while self.running:
            if self.mode == Mode.MODBUS_SLAVE:
                self.modbus_slave.update_simulation()
            time.sleep(0.1)

    def _main_loop(self):
        """主交互循环"""
        print("\n═══════════════ Commands ═══════════════════")
        print(" m - Switch mode")
        print(" s - Send data")
        print(" a - Auto send (periodic)")
        print(" c - Configuration")
        print(" l - Statistics")
        print(" q - Quit")
        print("═══════════════════════════════════════\n")

        while self.running:
            try:
                cmd = input("> ").strip().lower()

                if cmd == 'm':
                    self._cmd_switch_mode()
                elif cmd == 's':
                    self._cmd_send_data()
                elif cmd == 'a':
                    self._cmd_auto_send()
                elif cmd == 'c':
                    self._cmd_config()
                elif cmd == 'l':
                    self._cmd_stats()
                elif cmd == 'q':
                    self.stop()
                    break
                elif cmd == 'help':
                    print(" m - Mode | s - Send | a - Auto send | c - Config | l - Stats | q - Quit")

            except KeyboardInterrupt:
                print("\n[信息] 按 'q' 退出")
            except EOFError:
                break

    def _on_data_received(self, source: str, data: bytes):
        """数据接收回调"""
        self.rx_count += 1

        # 如果是Modbus Slave模式，处理请求
        if self.mode == Mode.MODBUS_SLAVE and len(data) >= 4:
            response = self.modbus_slave.process_request(data)
            if response:
                self._send_data(response)
                self.tx_count += 1

        # 显示接收的数据
        self._print_data("RX", source, data)

    def _send_data(self, data: bytes):
        """发送数据"""
        self.tx_count += 1

        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.write(data)
            except:
                pass

        self._print_data("TX", "", data)

    def _print_data(self, direction: str, source: str, data: bytes):
        """打印数据"""
        if not data:
            return

        timestamp = ""
        if self.show_timestamp:
            timestamp = datetime.now().strftime("[%H:%M:%S.%f")[:-3] + "] "

        source_str = f"[{source}] " if source else ""

        if self.show_hex:
            hex_str = " ".join(f"{b:02X}" for b in data)
            print(f"{timestamp}{source_str}{direction}: {hex_str} ({len(data)} bytes)")
        else:
            try:
                ascii_str = data.decode('ascii', errors='replace')
                print(f"{timestamp}{source_str}{direction}: {ascii_str}")
            except:
                print(f"{timestamp}{source_str}{direction}: {data}")

    def _cmd_switch_mode(self):
        """切换模式命令"""
        print("\n可用模式:")
        print(" 1. 原始串口")
        print(" 2. Modbus RTU Slave")
        print(" 3. Modbus RTU Master")

        choice = input("选择模式 (1-3): ").strip()
        modes = {
            '1': Mode.RAW,
            '2': Mode.MODBUS_SLAVE,
            '3': Mode.MODBUS_MASTER
        }

        if choice in modes:
            self.set_mode(modes[choice])
        else:
            print("无效选择")

    def _cmd_send_data(self):
        """发送数据命令"""
        data_str = input("输入HEX数据 (如: 01 03 00 00 00 01): ").strip()
        try:
            data = bytes.fromhex(data_str.replace(" ", ""))
            self._send_data(data)
        except ValueError:
            print("无效的HEX数据")

    def _cmd_config(self):
        """配置命令"""
        print("\nConfiguration:")
        print(" 1. Display HEX/ASCII")
        print(" 2. Display timestamp")
        print(" 3. Modbus slave address")
        print(" 4. Data pattern (for Slave mode)")

        choice = input("Select (1-4): ").strip()

        if choice == '1':
            self.show_hex = not self.show_hex
            print(f"HEX Display: {'ON' if self.show_hex else 'OFF'}")
        elif choice == '2':
            self.show_timestamp = not self.show_timestamp
            print(f"Timestamp: {'ON' if self.show_timestamp else 'OFF'}")
        elif choice == '3':
            addr = input("Slave address (1-247): ").strip()
            try:
                addr_int = int(addr)
                if 1 <= addr_int <= 247:
                    self.modbus_slave.unit_id = addr_int
                    print(f"Slave address set to: {addr_int}")
                else:
                    print("Address range: 1-247")
            except ValueError:
                print("Invalid address")
        elif choice == '4':
            print("\nData patterns:")
            print(" 1. Fixed value")
            print(" 2. Random")
            print(" 3. Sine wave")
            print(" 4. Random walk")
            pattern_choice = input("Select (1-4): ").strip()
            patterns = {
                '1': DataPattern.FIXED,
                '2': DataPattern.RANDOM,
                '3': DataPattern.SINE_WAVE,
                '4': DataPattern.RANDOM_WALK
            }
            if pattern_choice in patterns:
                self.modbus_slave.pattern = patterns[pattern_choice]
                print(f"Data pattern: {self.modbus_slave.pattern.value}")

    def _cmd_stats(self):
        """统计命令"""
        print(f"\n═══════════════ Statistics ═══════════════")
        print(f" RX: {self.rx_count} packets")
        print(f" TX: {self.tx_count} packets")
        print(f" Mode: {self.mode.value}")
        if self.mode == Mode.MODBUS_SLAVE:
            print(f" Slave Address: {self.modbus_slave.unit_id}")
            print(f" Data Pattern: {self.modbus_slave.pattern.value}")
        print(f" Auto Send: {'ON' if self.auto_send_enabled else 'OFF'}")
        if self.auto_send_enabled:
            print(f"   Interval: {self.auto_send_interval}s")
            print(f"   Data: {' '.join(f'{b:02X}' for b in self.auto_send_data)}")
        print("═══════════════════════════════════════\n")

    def _cmd_auto_send(self):
        """周期性发送配置命令"""
        print("\n═══════════════ Auto Send ═══════════════")
        print(f" Status: {'ON' if self.auto_send_enabled else 'OFF'}")
        if self.auto_send_enabled:
            print(f" Interval: {self.auto_send_interval}s")
            print(f" Data: {' '.join(f'{b:02X}' for b in self.auto_send_data)}")
        print("═══════════════════════════════════════\n")

        print("Options:")
        print(" 1. Start auto send")
        print(" 2. Stop auto send")
        print(" 3. Set interval (seconds)")
        print(" 4. Set data (HEX)")
        print(" 5. Quick presets")

        choice = input("Select (1-5): ").strip()

        if choice == '1':
            if not self.auto_send_enabled:
                self.auto_send_enabled = True
                self.auto_send_thread = threading.Thread(target=self._auto_send_loop, daemon=True)
                self.auto_send_thread.start()
                print(f"[Auto Send] Started - Interval: {self.auto_send_interval}s")
            else:
                print("[Auto Send] Already running")
        elif choice == '2':
            self.auto_send_enabled = False
            print("[Auto Send] Stopped")
        elif choice == '3':
            interval = input("Interval in seconds (e.g., 0.5, 1, 2): ").strip()
            try:
                self.auto_send_interval = float(interval)
                print(f"[Auto Send] Interval set to {self.auto_send_interval}s")
            except ValueError:
                print("Invalid interval")
        elif choice == '4':
            data_str = input("HEX data (e.g., 01 03 00 00 00 01): ").strip()
            try:
                self.auto_send_data = bytes.fromhex(data_str.replace(" ", ""))
                print(f"[Auto Send] Data set to: {' '.join(f'{b:02X}' for b in self.auto_send_data)}")
            except ValueError:
                print("Invalid HEX data")
        elif choice == '5':
            print("\nQuick Presets:")
            print(" 1. Modbus Read Holding Reg (01 03 00 00 00 01)")
            print(" 2. Modbus Read Input Reg (01 04 00 00 00 01)")
            print(" 3. Modbus Read Coils (01 01 00 00 00 08)")
            print(" 4. Custom test pattern (AA BB CC DD)")
            preset = input("Select preset (1-4): ").strip()
            if preset == '1':
                self.auto_send_data = bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x01])
                print("[Auto Send] Set to: Modbus Read Holding Reg")
            elif preset == '2':
                self.auto_send_data = bytes([0x01, 0x04, 0x00, 0x00, 0x00, 0x01])
                print("[Auto Send] Set to: Modbus Read Input Reg")
            elif preset == '3':
                self.auto_send_data = bytes([0x01, 0x01, 0x00, 0x00, 0x00, 0x08])
                print("[Auto Send] Set to: Modbus Read Coils")
            elif preset == '4':
                self.auto_send_data = bytes([0xAA, 0xBB, 0xCC, 0xDD])
                print("[Auto Send] Set to: Custom test pattern")

    def _auto_send_loop(self):
        """周期性发送循环"""
        while self.auto_send_enabled and self.running:
            self._send_data(self.auto_send_data)
            time.sleep(self.auto_send_interval)

    def stop(self):
        """停止模拟器"""
        print("\n[信息] 正在停止...")
        self.running = False
        self.auto_send_enabled = False

        if self.virtual_pair:
            self.virtual_pair.stop()

        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()

        if self.modbus_master:
            self.modbus_master.stop()

        if self.auto_send_thread:
            self.auto_send_thread.join(timeout=2)


def print_banner():
    """打印程序标题"""
    print("""
╔═══════════════════════════════════════════════╗
║     虚拟串口模拟器 v1.0                        ║
║     Virtual Serial Port Simulator              ║
║     支持 Modbus RTU Master/Slave               ║
╚═══════════════════════════════════════════════╝
    """)


def main_menu():
    """主菜单"""
    print("═══════════════ 主菜单 ════════════════")
    print(" 1. 创建虚拟串口对")
    print(" 2. 连接现有串口")
    print(" 3. 查看可用串口")
    print(" 4. 关于/帮助")
    print(" 0. 退出")
    print("═══════════════════════════════════════")


def main():
    """主函数"""
    try:
        # Windows彩色支持
        if sys.platform.startswith('win'):
            try:
                import colorama
                colorama.init()
            except ImportError:
                pass
    except:
        pass

    print_banner()

    simulator = SerialSimulator()

    while True:
        main_menu()
        choice = input("选择 (0-4): ").strip()

        if choice == '1':
            # 创建虚拟串口对
            if simulator.create_virtual_serial_pair():
                print("\n选择工作模式:")
                print(" 1. Modbus RTU Slave (默认)")
                print(" 2. Modbus RTU Master")
                print(" 3. 原始串口")

                mode_choice = input("选择 (1-3, 默认1): ").strip() or '1'
                modes = {'1': Mode.MODBUS_SLAVE, '2': Mode.MODBUS_MASTER, '3': Mode.RAW}
                simulator.set_mode(modes.get(mode_choice, Mode.MODBUS_SLAVE))

                print("\n[信息] 按 Ctrl+C 中断，输入 'q' 退出")
                simulator.start()
                break

        elif choice == '2':
            # 连接现有串口
            simulator.list_available_ports()
            port = input("输入串口名称 (如 COM3 或 /dev/ttyUSB0): ").strip()
            baudrate = input("波特率 (默认9600): ").strip() or '9600'

            if simulator.connect_to_serial(port, int(baudrate)):
                print("\n选择工作模式:")
                print(" 1. Modbus RTU Slave (默认)")
                print(" 2. Modbus RTU Master")
                print(" 3. 原始串口")

                mode_choice = input("选择 (1-3, 默认1): ").strip() or '1'
                modes = {'1': Mode.MODBUS_SLAVE, '2': Mode.MODBUS_MASTER, '3': Mode.RAW}
                simulator.set_mode(modes.get(mode_choice, Mode.MODBUS_SLAVE))

                print("\n[信息] 按 Ctrl+C 中断，输入 'q' 退出")
                simulator.start()
                break

        elif choice == '3':
            simulator.list_available_ports()

        elif choice == '4':
            print("\n═══════════════ 关于 ════════════════")
            print("虚拟串口模拟器 - 跨平台串口测试工具")
            print("\n支持功能:")
            print("  • 创建虚拟串口对 (macOS/Linux使用pty)")
            print("  • Modbus RTU Master/Slave模式")
            print("  • 原始串口数据收发")
            print("  • 实时数据显示")
            print("\n使用说明:")
            print("  • Windows: 建议使用com0com创建虚拟串口对")
            print("  • macOS/Linux: 自动创建PTY虚拟串口")
            print("  • Modbus Slave模式自动响应标准功能码")
            print("  • 数据可通过命令手动发送或自动轮询")
            print("═══════════════════════════════════════\n")

        elif choice == '0':
            print("退出程序")
            break

        else:
            print("无效选择")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[信息] 程序已中断")
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("程序结束")
