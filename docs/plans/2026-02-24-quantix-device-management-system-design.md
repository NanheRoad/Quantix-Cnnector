# Quantix 设备管理系统设计文档

**日期**: 2026-02-24
**项目名称**: Quantix Connector - 计量设备管理系统

---

## 1. 系统概述

### 1.1 目标

构建一个计量设备管理系统，支持电子台秤、天平、地磅等设备的实时数据采集与管理。

### 1.2 核心功能

- 支持 Modbus、MQTT、串口等多种协议
- **低代码协议配置**：可视化流程编排，无需编程即可适配新设备
- 自定义采集频率（每秒读取次数）
- 实时显示设备承重数据
- 设备配置管理（增删改查）
- 自动重连机制
- 协议模板管理（可复用、可导出导入）

### 1.3 部署架构

**混合架构**：本地边缘服务 + Web 前端

- 本地服务处理设备连接和实时数据采集
- 用户通过浏览器访问前端界面
- 预留云端管理能力扩展

### 1.4 设备规模与性能要求

- **中型规模**：11-100 台设备
- **数据模式**：仅实时数据展示，无历史存储

### 1.5 非功能性需求

| 指标            | 目标值        | 说明                             |
| --------------- | ------------- | -------------------------------- |
| 数据采集延迟    | < 500ms       | 从设备读取到前端显示的端到端延迟 |
| WebSocket 并发  | ≥ 30 连接    | 支持同时 30 个浏览器客户端监听   |
| 采集精度        | ±1% 采集间隔 | 实际采集频率与配置误差范围       |
| 设备重连时间    | < 30s         | 设备断线后最大重连时间           |
| 系统可用性      | 99%           | 月度可用性目标                   |
| 单设备 CPU 占用 | < 1%          | 每个设备采集任务 CPU 占用        |

### 1.6 验收标准

**功能验收**：

- [ ] 支持 Modbus TCP 设备连接和数据读取
- [ ] 支持 MQTT 设备订阅和数据接收
- [ ] 支持串口设备连接和数据读取
- [ ] 协议模板编辑器可创建、编辑、删除模板
- [ ] 设备管理支持增删改查和启用/禁用
- [ ] 实时数据大屏显示所有设备重量
- [ ] 设备离线自动重连
- [ ] API Key 认证保护 API

**性能验收**：

- [ ] 50 台设备同时采集，CPU < 50%
- [ ] 100 台设备同时采集，CPU < 80%（上限验证）
- [ ] 数据更新延迟 < 500ms（99 分位）
- [ ] WebSocket 支持 30 个并发客户端
- [ ] 连续运行 24 小时无内存泄漏

---

## 2. 技术栈

| 层级        | 技术选型                           | 说明                           |
| ----------- | ---------------------------------- | ------------------------------ |
| 前端        | Dash 3.x + feffery-antd-components | Python 全栈 Web 框架           |
| 后端        | FastAPI                            | 异步高性能 API 服务            |
| 数据库      | SQLite (Peewee ORM)                | 轻量级，预留 MySQL 切换        |
| 实时通信    | WebSocket                          | 低延迟数据推送                 |
| Modbus 驱动 | pymodbus                           | 支持 Modbus TCP/RTU            |
| MQTT 驱动   | gmqtt                              | 异步 MQTT 客户端               |
| 配置管理    | 环境变量 + SQLite                  | 系统配置、设备数据存储在数据库 |

---

## 3. 系统架构

### 3.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         前端层 (Dash)                            │
│  ┌─────────────────┐              ┌─────────────────┐            │
│  │  实时数据大屏    │              │  设备配置页面    │            │
│  └─────────────────┘              └─────────────────┘            │
└──────────────────────────────┬──────────────────────────────────┘
                               │ WebSocket
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                         接口层 (FastAPI)                         │
│  ┌─────────────────┐              ┌─────────────────┐            │
│  │  RESTful API    │              │  WebSocket      │            │
│  │  /devices/*     │              │  /ws            │            │
│  └─────────────────┘              └─────────────────┘            │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                         服务层                                   │
│  ┌─────────────────┐              ┌─────────────────┐            │
│  │  DeviceManager  │              │  DataCollector  │            │
│  │  设备生命周期    │              │  数据采集调度    │            │
│  └─────────────────┘              └─────────────────┘            │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                       设备驱动层                                 │
│  ┌─────────────────┐              ┌─────────────────┐            │
│  │  ModbusDriver   │              │  MQTTDriver     │            │
│  └─────────────────┘              └─────────────────┘            │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                       物理设备层                                 │
│    电子台秤、天平、地磅... (Modbus/MQTT 协议)                    │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 项目结构

```
quantix-connector/
├── app.py                        # Dash 应用入口
├── config/
│   ├── __init__.py
│   └── settings.py              # 系统配置（环境变量管理）
├── backend/
│   ├── __init__.py
│   ├── main.py                  # FastAPI 应用
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py            # Peewee 模型
│   │   └── connection.py        # 数据库连接管理
│   ├── api/
│   │   ├── __init__.py
│   │   ├── devices.py           # 设备 CRUD API
│   │   ├── protocols.py         # 协议模板 CRUD API
│   │   └── websocket.py         # WebSocket 端点
│   ├── services/
│   │   ├── __init__.py
│   │   ├── device_manager.py    # 设备管理服务
│   │   ├── data_collector.py    # 数据采集调度器
│   │   └── protocol_executor.py # 协议流程执行器
│   └── drivers/
│       ├── __init__.py
│       ├── base.py              # 设备驱动基类（抽象接口）
│       ├── modbus_driver.py     # Modbus TCP/RTU 实现
│       ├── mqtt_driver.py       # MQTT 实现
│       ├── tcp_driver.py        # TCP 原始连接
│       └── serial_driver.py     # 串口连接
├── frontend/
│   ├── __init__.py
│   ├── pages/
│   │   ├── dashboard.py         # 实时数据大屏
│   │   ├── device_config.py     # 设备配置页面
│   │   └── protocol_editor.py   # 协议模板编辑器
│   └── components/
│       ├── device_card.py       # 设备卡片组件
│       └── protocol_step_editor.py # 协议步骤编辑器组件
└── requirements.txt
```

---

## 4. 核心组件设计

### 4.1 设备驱动基类

```python
# backend/drivers/base.py
from abc import ABC, abstractmethod

class DeviceDriver(ABC):
    """设备驱动抽象基类"""

    @abstractmethod
    async def connect(self) -> bool:
        """连接设备"""
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """断开连接"""
        pass

    @abstractmethod
    async def read_weight(self) -> float:
        """读取当前重量"""
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        """检查连接状态"""
        pass
```

### 4.2 低代码协议适配系统

#### 4.2.1 设计理念

**核心概念**：协议模板 (Protocol Template)

每个设备类型对应一个协议模板，定义了如何与设备交互。用户通过可视化界面配置协议模板，无需编写代码。

#### 4.2.2 协议模板结构

```python
# 协议模板 JSON 结构
{
    "name": "某品牌电子台秤",
    "description": "通过 Modbus TCP 读取重量",
    "protocol_type": "modbus_tcp",      # 底层传输协议
    "variables": [                       # 可配置变量
        {
            "name": "slave_id",
            "type": "int",
            "default": 1,
            "label": "从站地址",
            "description": "Modbus 从站 ID"
        },
        {
            "name": "register_address",
            "type": "int",
            "default": 0,
            "label": "寄存器地址",
            "description": "重量数据起始地址"
        }
    ],
    # === 轮询模式设备（Modbus/串口）使用 ===
    "steps": [                           # 交互步骤（流程编排）
        {
            "id": "read_weight",
            "name": "读取重量",
            "trigger": "poll",            # poll=轮询执行, manual=手动触发
            "action": "modbus.read_input_registers",
            "params": {
                "slave_id": "${slave_id}",
                "address": "${register_address}",
                "count": 2
            },
            "parse": {                    # 数据解析规则
                "type": "expression",
                "expression": "registers[0] * 256 + registers[1] / 1000"
            }
        }
    ],
    # === 推送模式设备（MQTT）使用 ===
    "setup_steps": [                     # 连接时执行一次
        {
            "id": "subscribe",
            "name": "订阅重量主题",
            "trigger": "setup",
            "action": "mqtt.subscribe",
            "params": {
                "topic": "${topic}",
                "qos": 1
            }
        }
    ],
    "message_handler": {                  # 消息到达时触发
        "id": "handle_message",
        "name": "处理接收到的消息",
        "trigger": "event",
        "action": "mqtt.on_message",
        "parse": {
            "type": "regex",
            "pattern": "\"weight\"\\s*:\\s*([-+]?[0-9]*\\.?[0-9]+)",
            "group": 1
        }
    },
    "output": {
        "weight": "${steps.read_weight.result}",   # 或 ${message_handler.result}
        "unit": "kg"
    }
}
```

**步骤触发类型 (`trigger`)**：
- `poll`: 按 `poll_interval` 周期执行（Modbus/串口读取）
- `manual`: 仅通过 API 手动触发（写操作）
- `setup`: 连接成功后执行一次（MQTT 订阅）
- `event`: 事件触发（MQTT 消息到达）
- **默认值**：`steps` 数组中的步骤默认为 `poll`，可省略

#### 4.2.3 支持的 Action 类型

| Action 类型                       | 中文说明                   | 用途                           | 参数                     | 执行时机             |
| --------------------------------- | -------------------------- | ------------------------------ | ------------------------ | -------------------- |
| **Modbus 读取**             |                            |                                |                          |                      |
| `modbus.read_input_registers`   | 读取实时数据（输入寄存器） | 读取重量、温度等传感器只读数据 | address, count, slave_id | 轮询步骤             |
| `modbus.read_holding_registers` | 读取配置值（保持寄存器）   | 读取设备参数设置               | address, count, slave_id | 轮询步骤             |
| `modbus.read_coils`             | 读取开关状态（线圈）       | 读取继电器、开关状态           | address, count, slave_id | 轮询步骤             |
| `modbus.read_discrete_inputs`   | 读取离散输入               | 读取只读开关量信号             | address, count, slave_id | 轮询步骤             |
| **Modbus 写入**             |                            |                                |                          |                      |
| `modbus.write_register`         | 写单个寄存器               | 设置设备参数（**仅手动触发**） | address, value, slave_id | **手动触发** |
| `modbus.write_coil`             | 写单个线圈                 | 控制继电器等（**仅手动触发**） | address, value, slave_id | **手动触发** |
| **MQTT**                    |                            |                                |                          |                      |
| `mqtt.subscribe`                | 订阅主题                   | 连接时订阅，接收推送消息       | topic, qos               | **连接时一次** |
| `mqtt.on_message`               | 消息到达处理               | 定义收到消息后的处理逻辑       | parse规则                | **事件触发**   |
| **TCP**                     |                            |                                |                          |                      |
| `tcp.send`                      | TCP 发送                   | 发送原始 TCP 数据              | data (hex/ascii)         | 轮询步骤             |
| `tcp.receive`                   | TCP 接收                   | 接收 TCP 数据                  | size, timeout            | 轮询步骤             |
| **串口**                    |                            |                                |                          |                      |
| `serial.send`                   | 串口发送                   | 发送串口数据                   | data (hex/ascii)         | 轮询步骤             |
| `serial.receive`                | 串口接收                   | 接收串口数据                   | size, timeout            | 轮询步骤             |
| **数据处理**                |                            |                                |                          |                      |
| `delay`                         | 延迟等待                   | 等待指定时间                   | milliseconds             | 轮询步骤             |
| `transform.base64_decode`       | Base64 解码                | 解码 Base64 数据               | input                    | 内联解析             |
| `transform.hex_decode`          | 十六进制解码               | 解码十六进制字符串             | input                    | 内联解析             |
| `transform.regex_extract`       | 正则提取                   | 使用正则表达式提取数据         | input, pattern, group    | 内联解析             |
| `transform.substring`           | 提取子串                   | 按位置提取子串                 | input, start, end        | 内联解析             |
| `transform.struct_parse`        | 结构体解析                 | 解析二进制结构体               | input, format            | 内联解析             |

**重要说明**：
- **轮询步骤**：按 `poll_interval` 周期执行，用于读取数据
- **手动触发**：仅通过用户手动操作触发（如前端按钮、API 调用），**绝不自动周期执行**
- **连接时一次**：设备连接成功后执行一次，用于建立订阅
- **事件触发**：MQTT 消息到达时触发
- **内联解析**：作为其他步骤的 `parse` 配置使用

#### 4.2.4 数据解析方式

**1. 表达式解析（安全沙箱）**

```json
{
    "type": "expression",
    "expression": "registers[0] * 256 + registers[1] / 1000"
}
```

**支持的变量**：`registers`, `coils`, `payload`, `steps`

**安全限制**：

- 使用 `simpleeval` 库而非 `eval`，提供受限的 Python 表达式求值
- 仅支持数学运算、列表/字典访问、比较运算
- **仅允许白名单函数调用**：`int()`, `float()`, `str()`, `abs()`, `round()`, `min()`, `max()`
- **禁止**：非白名单函数调用、属性访问、导入语句、Lambda、任意代码执行

**实现示例**：

```python
from simpleeval import simple_eval

SAFE_FUNCTIONS = {
    'int': int, 'float': float, 'str': str,
    'abs': abs, 'round': round, 'min': min, 'max': max
}

result = simple_eval(
    expression,
    names={'registers': registers, 'payload': payload},
    functions=SAFE_FUNCTIONS
)
```

**2. 正则提取**

```json
{
    "type": "regex",
    "pattern": "Weight:\\s*([0-9.]+)\\s*(kg|g)",
    "group": 1
}
```

**3. 位置提取**

```json
{
    "type": "substring",
    "start": 2,
    "end": 6,
    "encoding": "utf-8"
}
```

**4. 结构体解析**（二进制协议）

```json
{
    "type": "struct",
    "format": ">HHH",  # 大端序，3个 unsigned short
    "fields": ["header", "weight_high", "weight_low"]
}
```

#### 4.2.5 Modbus 协议基础知识

Modbus 定义了主从设备之间交换数据的存储区域：

| 名称                                   | 功能码 | 读写 | 说明       | 典型用途                     |
| -------------------------------------- | ------ | ---- | ---------- | ---------------------------- |
| **线圈 Coils**                   | 0x01   | RW   | 单个位     | 控制继电器、启动/停止设备    |
| **离散输入 Discrete Inputs**     | 0x02   | R    | 单个位     | 读取限位开关、报警状态       |
| **保持寄存器 Holding Registers** | 0x03   | RW   | 16位寄存器 | 设置参数、读取配置值         |
| **输入寄存器 Input Registers**   | 0x04   | R    | 16位寄存器 | 读取传感器数据（重量、温度） |

**对于计量设备**：

- 重量数据通常存储在 **输入寄存器**（只读，设备自动更新）
- 或 **保持寄存器**（可能包含去皮、置零等控制功能）

#### 4.2.6 数据库模型更新

```python
# backend/database/models.py
from peewee import *
from datetime import datetime
import os

def get_database():
    """工厂函数，后期可切换数据库"""
    db_type = os.getenv('DB_TYPE', 'sqlite')
    if db_type == 'mysql':
        return MySQLDatabase(
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT', 3306))
        )
    return SqliteDatabase('quantix.db')

database = get_database()

class BaseModel(Model):
    class Meta:
        database = database

class ProtocolTemplate(BaseModel):
    """协议模板"""
    id = AutoField()
    name = CharField(max_length=100)                    # 模板名称
    description = TextField(null=True)                  # 描述
    protocol_type = CharField(max_length=50)            # 传输协议类型
    template = JSONField()                              # 完整的流程配置
    is_system = BooleanField(default=False)             # 是否系统预置模板
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'protocol_templates'

class Device(BaseModel):
    """设备实例"""
    id = AutoField()
    name = CharField(max_length=100)                    # 设备名称
    protocol_template = ForeignKeyField(ProtocolTemplate, backref='devices')
    connection_params = JSONField()                     # 传输层连接参数
    template_variables = JSONField()                    # 协议模板的变量值
    poll_interval = FloatField(default=1.0)             # 采集间隔（秒）
    enabled = BooleanField(default=True)                # 是否启用
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'devices'
```

#### 4.2.7 连接参数格式（传输层）

**Modbus TCP**:

```json
{
    "host": "192.168.1.100",
    "port": 502
}
```

**Modbus RTU (串口)**:

```json
{
    "port": "/dev/ttyUSB0",
    "baudrate": 9600,
    "bytesize": 8,
    "parity": "N",
    "stopbits": 1
}
```

**MQTT**:

```json
{
    "host": "192.168.1.100",
    "port": 1883,
    "username": null,
    "password": null
}
```

**TCP 原始连接**:

```json
{
    "host": "192.168.1.100",
    "port": 8000
}
```

**串口连接**:

```json
{
    "port": "/dev/ttyUSB0",
    "baudrate": 9600,
    "bytesize": 8,
    "parity": "N",
    "stopbits": 1
}
```

---

### 4.3 预置协议模板示例

#### 4.3.1 标准 Modbus 电子台秤

```json
{
    "name": "标准 Modbus 电子台秤",
    "description": "适用于大多数支持 Modbus TCP 的电子台秤",
    "protocol_type": "modbus_tcp",
    "variables": [
        {"name": "slave_id", "type": "int", "default": 1, "label": "从站地址"},
        {"name": "address", "type": "int", "default": 0, "label": "数据地址"}
    ],
    "steps": [{
        "id": "read_weight",
        "name": "读取重量",
        "trigger": "poll",
        "action": "modbus.read_input_registers",
        "params": {
            "slave_id": "${slave_id}",
            "address": "${address}",
            "count": 2
        },
        "parse": {
            "type": "expression",
            "expression": "registers[0] * 65536 + registers[1]"
        }
    }],
    "output": {
        "weight": "${steps.read_weight.result}",
        "unit": "kg"
    }
}
```

#### 4.3.2 MQTT 重量传感器

```json
{
    "name": "MQTT 重量传感器",
    "description": "通过 MQTT 接收重量数据（推送模式）",
    "protocol_type": "mqtt",
    "variables": [
        {"name": "topic", "type": "string", "default": "sensor/weight", "label": "主题"}
    ],
    "setup_steps": [
        {
            "id": "subscribe",
            "name": "订阅重量主题",
            "trigger": "setup",
            "action": "mqtt.subscribe",
            "params": {
                "topic": "${topic}",
                "qos": 1
            }
        }
    ],
    "message_handler": {
        "id": "handle_message",
        "name": "处理接收到的消息",
        "trigger": "event",
        "action": "mqtt.on_message",
        "parse": {
            "type": "regex",
            "pattern": "\"weight\"\\s*:\\s*([-+]?[0-9]*\\.?[0-9]+)",
            "group": 1
        }
    },
    "output": {
        "weight": "${message_handler.result}",
        "unit": "kg"
    }
}
```

**说明**：MQTT 设备使用推送模式。`setup_steps` 在连接时执行一次建立订阅，`message_handler` 在消息到达时触发。

#### 4.3.3 串口天平（ASCII 协议）

```json
{
    "name": "串口天平 ASCII 协议",
    "description": "通过串口发送命令读取天平重量",
    "protocol_type": "serial",
    "variables": [
        {"name": "baudrate", "type": "int", "default": 9600, "label": "波特率"}
    ],
    "steps": [
        {
            "id": "send_command",
            "name": "发送读取命令",
            "trigger": "poll",
            "action": "serial.send",
            "params": {
                "data": "W\\r\\n"
            }
        },
        {
            "id": "wait",
            "name": "等待响应",
            "trigger": "poll",
            "action": "delay",
            "params": {
                "milliseconds": 100
            }
        },
        {
            "id": "receive",
            "name": "接收响应",
            "trigger": "poll",
            "action": "serial.receive",
            "params": {
                "size": 20,
                "timeout": 1000
            },
            "parse": {
                "type": "regex",
                "pattern": "WS\\s+([0-9.]+)",
                "group": 1
            }
        }
    ],
    "output": {
        "weight": "${steps.receive.result}",
        "unit": "g"
    }
}
```

**说明**：轮询模式下所有步骤默认 `trigger: "poll"`，按顺序执行。

---

## 5. 前端协议编辑器设计

### 5.1 协议模板编辑器界面

```
┌─────────────────────────────────────────────────────────────────┐
│  协议模板编辑器 - 新建模板                        [保存] [取消]  │
├─────────────────────────────────────────────────────────────────┤
│  基本信息                                                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 模板名称: [某品牌电子台秤_______________]                   │  │
│  │ 描述:     [通过 Modbus TCP 读取重量__________]             │  │
│  │ 传输协议: [Modbus TCP ▼]                                  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  变量定义                                              [+ 添加变量]│
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 变量名       │ 类型  │ 默认值 │ 说明                      │  │
│  │ slave_id     │ int   │ 1      │ 从站地址                  │  │
│  │ register_addr│ int   │ 0      │ 寄存器地址                │  │
│  │ [+ 添加变量]                                                │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  交互流程                                              [+ 添加步骤]│
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 步骤 1: 读取重量                          [↑] [↓] [删除]   │  │
│  │ ┌─────────────────────────────────────────────────────┐   │  │
│  │ │ 操作: [读取实时数据(输入寄存器) ▼]                    │   │  │
│  │ │       - 读取配置值(保持寄存器)                         │   │  │
│  │ │       - 读取开关状态(线圈)                             │   │  │
│  │ │       - TCP 发送 / 接收                                │   │  │
│  │ │       - 串口 发送 / 接收                                │   │  │
│  │ │                                                      │   │  │
│  │ │ 参数:                                                │   │  │
│  │ │   从站地址: ${slave_id}                              │   │  │
│  │ │   起始地址: ${register_addr}                         │   │  │
│  │ │   读取数量: [2]                                       │   │  │
│  │ │                                                      │   │  │
│  │ │ 数据解析: [表达式解析 ▼]                              │   │  │
│  │ │   - 正则表达式提取                                    │   │  │
│  │ │   - 位置提取                                          │   │  │
│  │ │   - 结构体解析                                        │   │  │
│  │ │                                                      │   │  │
│  │ │   表达式: registers[0] * 256 + registers[1] / 1000   │   │  │
│  │ └─────────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  输出映射                                                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ weight: ${steps.步骤1.result}                              │  │
│  │ unit: kg                                                   │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 设备实例配置界面

```
┌─────────────────────────────────────────────────────────────────┐
│  新建设备 - 选择协议模板                        [保存] [取消]    │
├─────────────────────────────────────────────────────────────────┤
│  协议模板: [某品牌电子台秤 ▼]           [+] 创建新模板          │
│                                                                  │
│  连接参数                                                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 主机: [192.168.1.100________________]                     │  │
│  │ 端口: [502________________________________]              │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  模板变量                                                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 从站地址 (slave_id):     [1________________]              │  │
│  │ 寄存器地址 (register_addr): [0________________]            │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  采集设置                                                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 采集间隔: [1.0____] 秒                                     │  │
│  │ 启用设备: [✓]                                              │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. API 接口设计

### 6.1 协议模板 API

| 方法   | 路径                       | 描述             |
| ------ | -------------------------- | ---------------- |
| GET    | /api/protocols             | 获取协议模板列表 |
| POST   | /api/protocols             | 创建协议模板     |
| GET    | /api/protocols/{id}        | 获取单个模板     |
| PUT    | /api/protocols/{id}        | 更新模板         |
| DELETE | /api/protocols/{id}        | 删除模板         |
| POST   | /api/protocols/{id}/test   | 测试模板连接     |
| POST   | /api/protocols/import      | 导入模板（JSON） |
| GET    | /api/protocols/{id}/export | 导出模板         |

### 6.2 设备 API

| 方法   | 路径                           | 描述             |
| ------ | ------------------------------ | ---------------- |
| GET    | /api/devices                   | 获取设备列表     |
| POST   | /api/devices                   | 创建设备         |
| GET    | /api/devices/{id}              | 获取单个设备     |
| PUT    | /api/devices/{id}              | 更新设备         |
| DELETE | /api/devices/{id}              | 删除设备         |
| POST   | /api/devices/{id}/enable       | 启用设备         |
| POST   | /api/devices/{id}/disable      | 禁用设备         |
| POST   | /api/devices/{id}/execute      | **手动执行步骤** |

**手动执行步骤 API**：
```json
POST /api/devices/{id}/execute
{
    "step_id": "tare_zero",      // 要执行的步骤 ID
    "params": {}                  // 覆盖默认参数（可选）
}
```
**安全约束**：
- 服务端**必须校验** `step.trigger == "manual"`，否则返回 403 Forbidden
- 用于触发协议模板中定义为"手动触发"的步骤（如 `modbus.write_register`），防止误操作
- 记录所有手动执行操作到审计日志

### 6.3 WebSocket

| 路径 | 描述         |
| ---- | ------------ |
| /ws  | 实时数据推送 |

### 6.4 认证与授权

**V1 阶段（局域网场景）**：

- API Key 认证：环境变量配置固定 API Key
- WebSocket 连接时通过 URL 参数传递：`ws://host/ws?api_key=xxx`
- 适合受信任的局域网环境

> **安全警告**：URL 参数可能被记录在代理/日志中。此方案仅适用于短期开发环境。生产环境建议：
> - 强制使用 TLS (wss://)
> - 使用短期 Token 替代固定 API Key
> - 或改用 WebSocket 子协议认证

**V2 阶段（多用户场景）**：

- JWT Token 认证
- 用户角色：管理员、操作员、只读用户

**权限矩阵**：

| 操作             | 管理员 | 操作员 | 只读 |
| ---------------- | ------ | ------ | ---- |
| 查看设备         | ✓     | ✓     | ✓   |
| 启用/禁用设备    | ✓     | ✓     | ✗   |
| 创建/编辑设备    | ✓     | ✗     | ✗   |
| 删除设备         | ✓     | ✗     | ✗   |
| **手动执行步骤** | ✓     | ✓     | ✗   |
| 编辑协议模板     | ✓     | ✗     | ✗   |
| 导入/导出模板    | ✓     | ✓     | ✗   |

**配置方式**：

```bash
# V1: 环境变量
export API_KEY="your-secret-key-here"

# V2: 数据库用户表
```

---

## 7. 数据流设计

### 7.1 启动流程

```
1. FastAPI 应用启动
   ↓
2. 加载环境变量配置（API Key、日志级别等）
   ↓
3. 初始化 SQLite 数据库，加载设备和协议模板
   ↓
4. DeviceManager 为每个启用设备创建对应驱动实例
   ↓
5. DataCollector 启动异步采集任务（每设备独立任务）
   ↓
6. 系统进入运行状态
```

**配置数据源说明**：

- **系统配置**（API Key、端口、日志级别）：环境变量
- **设备配置、协议模板**：SQLite 数据库（通过 Web UI 或 API 管理）
- **导出/导入**：支持将设备配置导出为 JSON/YAML 备份，但不作为运行时数据源

### 7.2 实时数据采集循环（使用协议执行器）

```
┌─────────────┐    ┌─────────────────────┐    ┌─────────────┐
│   设备1     │    │     设备2           │    │   设备N     │
│  (Modbus)   │    │     (MQTT)          │    │  (Modbus)   │
└──────┬──────┘    └──────────┬──────────┘    └──────┬──────┘
       │                    │                      │
       ▼                    ▼                      ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ ProtocolExecutor│ │ ProtocolExecutor│ │ ProtocolExecutor│
│ 轮询执行:       │ │ 连接时订阅:     │ │ 轮询执行:       │
│ 1. read_weight  │ │ 1. subscribe    │ │ 1. read_weight  │
│   (每周期)      │ │   (仅一次)       │ │   (每周期)      │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                  │                      │
         │         ┌────────┴────────┐              │
         │         ▼                 ▼              │
         │    ┌─────────┐      ┌─────────┐          │
         │    │ MQTT    │      │ 消息    │          │
         │    │ Broker  │─────│ 推送    │          │
         │    └─────────┘      └────┬────┘          │
         │                           │              │
         └───────────────┬───────────┴──────────────┘
                         ▼
         ┌─────────────────────────────────────────────────┐
         │              WebSocket 广播                      │
         │  {device_id, device_name, weight, unit,         │
         │   timestamp, status}                            │
         └───────────────────┬─────────────────────────────┘
                             │
                             ▼
         ┌─────────────────────────────────────────────────┐
         │            Dash 前端更新                         │
         │     更新所有连接的浏览器页面                      │
         └─────────────────────────────────────────────────┘
```

**说明**：
- **Modbus 设备**：按 `poll_interval` 周期轮询读取
- **MQTT 设备**：连接时订阅一次，后续由 Broker 主动推送消息

### 7.3 WebSocket 消息格式

```json
{
    "type": "weight_update",
    "device_id": 1,
    "device_name": "电子台秤-01",
    "weight": 12.345,
    "unit": "kg",
    "timestamp": "2026-02-24T10:30:45.123Z",
    "status": "online"
}
```

**状态值**:

- `online`: 设备在线，数据正常
- `offline`: 设备离线
- `error`: 设备故障

---

## 8. 错误处理与容错

### 8.1 自动重连策略

| 场景           | 处理方式                                       |
| -------------- | ---------------------------------------------- |
| 连接失败       | 指数退避重连：1s → 2s → 4s → 8s → 最大 30s |
| 连续失败 10 次 | 标记设备为故障状态，暂停采集                   |
| 用户重新启用   | 重置故障状态，重新尝试连接                     |
| 读取超时       | 记录日志，不中断采集任务                       |

### 8.2 设备状态指示

| 状态    | 前端显示              |
| ------- | --------------------- |
| online  | 绿色指示灯 + 实时重量 |
| offline | 灰色指示灯 + "离线"   |
| error   | 红色指示灯 + 错误信息 |

### 8.3 日志记录

- 所有错误记录到日志文件
- 设备连接/断开事件记录
- 采集失败记录

---

## 9. 前端页面设计

### 9.1 实时数据大屏 (Dashboard)

- 卡片式布局展示所有设备
- 每个卡片显示：
  - 设备名称
  - 当前重量（大字号）
  - 单位
  - 状态指示灯
  - 最后更新时间
- 支持自定义卡片大小和位置

### 9.2 设备配置页面

- 设备列表表格
- 新增/编辑设备表单
- 选择协议模板后显示对应的模板变量
- 连接参数配置
- 启用/禁用切换按钮

### 9.3 协议模板管理页面

- 协议模板列表（区分系统预置和用户自定义）
- 协议模板编辑器（可视化流程编排）
- 模板导入/导出功能

---

## 10. 部署说明

### 10.1 开发环境

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化数据库（包含预置协议模板）
python -c "from backend.database.connection import init_db; init_db()"

# 启动后端
uvicorn backend.main:app --reload

# 启动前端（新终端）
python app.py
```

### 10.2 生产环境

```bash
# 使用 gunicorn 启动
gunicorn backend.main:app -w 4 -k uvicorn.workers.UvicornWorker

# 或使用 systemd service
# 待补充
```

---

## 11. 后期扩展

### 11.1 数据库切换

**数据迁移工具**：

```bash
# 1. 导出 SQLite 数据
python scripts/migrate_db.py --export sqlite_backup.json

# 2. 修改环境变量切换到 MySQL
export DB_TYPE=mysql
export DB_NAME=quantix
export DB_USER=root
export DB_PASSWORD=password
export DB_HOST=localhost
export DB_PORT=3306

# 3. 导入数据到 MySQL
python scripts/migrate_db.py --import sqlite_backup.json
```

**字段兼容性说明**：

- `JSONField` 在 SQLite 中存储为 TEXT，MySQL 中使用 JSON 类型
- `DateTimeField` 在两者中兼容
- 迁移脚本会自动处理类型转换

**Peewee 配置**：

```python
# 使用 Peewee 的数据库抽象层，大部分代码无需修改
# 只需在 get_database() 函数中切换数据库实例
```

### 11.2 预留扩展功能

- 历史数据存储与查询
- 数据告警规则（超重报警、设备离线通知）
- 多用户权限管理
- 云端数据同步
- 数据报表导出
- 更多协议支持（OPC-UA、HTTP API 等）

---

**文档版本**: 2.4
**更新日期**: 2026-02-24
**更新内容**:
- 新增低代码协议适配器设计
- 修正 MQTT 订阅模型（连接时订阅 + 事件触发）
- 修正数据流图，区分轮询和推送模式
- 写操作归类为"手动触发"，防止误操作
- 完善表达式解析安全规则表述
- 统一 WebSocket 并发指标为 30
- 新增 API Key 安全警告
- 新增手动执行步骤 API `/api/devices/{id}/execute`
- **新增**：服务端必须校验 `trigger == "manual"`，否则返回 403
- 统一协议模板结构，添加 `trigger` 字段及默认值说明
- 统一规模目标与性能验收（100 台上限）
- 修复权限矩阵 Markdown 格式，新增"手动执行步骤"权限
- 新增认证授权设计（API Key / JWT）
- 明确配置数据源（SQLite 唯一数据源）
- 完善 MySQL 迁移策略
- 新增非功能性需求和验收标准
- 补齐串口协议示例的 `trigger` 字段
