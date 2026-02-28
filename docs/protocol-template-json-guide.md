# 协议模板 JSON 编写说明

本文说明 Quantix 的协议模板 JSON 如何编写，适用于设备模板创建页面中的“模板 JSON”输入框。

## 1. 最小可用模板（轮询类：Modbus/串口/TCP）

```json
{
  "name": "标准 Modbus 电子台秤",
  "protocol_type": "modbus_tcp",
  "variables": [
    { "name": "slave_id", "type": "int", "default": 1, "label": "从站地址" },
    { "name": "address", "type": "int", "default": 0, "label": "寄存器地址" }
  ],
  "steps": [
    {
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
    }
  ],
  "output": {
    "weight": "${steps.read_weight.result}",
    "unit": "kg"
  }
}
```

## 2. 顶层字段说明

- `name`: 模板名称（建议包含品牌/型号）。
- `protocol_type`: 协议类型，可用值：`modbus_tcp`、`mqtt`、`serial`、`tcp`。
- `variables`: 变量定义列表，供设备实例配置时填写。
- `steps`: 步骤列表（轮询或手动步骤）。
- `setup_steps`: 连接成功后执行一次（常用于 MQTT 订阅）。
- `message_handler`: 事件触发处理（常用于 MQTT 消息处理）。
- `output`: 输出映射，通常输出 `weight` 和 `unit`。

## 3. 步骤字段说明

- `id`: 步骤唯一标识，后续 `output` 会引用它。
- `name`: 步骤显示名。
- `trigger`: 执行时机。
- `action`: 动作名（由驱动层执行）。
- `params`: 动作参数，支持占位符 `${...}`。
- `parse`: 解析规则（可选）。

## 4. trigger 可选值

- `poll`: 周期执行（默认）。
- `manual`: 手动触发（仅能通过 `/api/devices/{id}/execute` 执行）。
- `setup`: 连接后执行一次。
- `event`: 事件触发（如 MQTT 收到消息）。

## 5. parse 解析类型

- `expression`: 表达式解析（推荐），示例：`registers[0] * 65536 + registers[1]`。
- `regex`: 正则提取。
- `substring`: 子串截取。
- `struct`: 二进制结构体解析。

说明：`expression` 支持变量 `registers`、`coils`、`payload`、`steps`。

## 6. 占位符规则

- `${slave_id}`: 取变量值。
- `${steps.read_weight.result}`: 取前序步骤结果。
- `${message_handler.result}`: 取事件处理结果（MQTT）。

## 7. MQTT 模板示例（推送模型）

```json
{
  "name": "MQTT 重量传感器",
  "protocol_type": "mqtt",
  "variables": [
    { "name": "topic", "type": "string", "default": "sensor/weight", "label": "主题" }
  ],
  "setup_steps": [
    {
      "id": "subscribe",
      "name": "订阅主题",
      "trigger": "setup",
      "action": "mqtt.subscribe",
      "params": { "topic": "${topic}", "qos": 1 }
    }
  ],
  "message_handler": {
    "id": "handle_message",
    "name": "处理消息",
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

## 8. 手动控制步骤示例

```json
{
  "id": "tare_zero",
  "name": "去皮清零",
  "trigger": "manual",
  "action": "modbus.write_register",
  "params": {
    "slave_id": "${slave_id}",
    "address": 10,
    "value": 1
  }
}
```

注意：`manual` 步骤必须放在 `steps` 中，且后端会强制校验 `trigger == "manual"`。

## 9. 常见错误

- 轮询模板未配置 `steps`，导致无采集结果。
- MQTT 模板把订阅写在 `steps` 里，导致逻辑错误。
- `output.weight` 引用了不存在的步骤路径。
- 手动步骤不是 `manual` 触发，调用执行接口会返回 403。

## 10. MQTT 新手速查：先判断“消息长什么样”

配置 MQTT 模板时，不要先写正则。先看发布端实际消息，再决定 `parse`。

常见消息形态：

- 纯数字文本：`214.46`
- JSON：`{"weight":214.46,"unit":"kg"}`
- JSON（字段名不同）：`{"net_weight":214.46}`
- 普通文本：`WT=214.46kg`

建议流程（3 步）：

1. 用 MQTT 客户端先确认 payload 原文（不要猜格式）。
2. 只改 `message_handler.parse`，先让 `weight` 能提取出来。
3. 最后再补充 `output.unit` 或其他字段。

## 11. MQTT `parse` 可直接复制的示例

### 11.1 payload 是纯数字（如 `214.46`）

```json
"parse": {
  "type": "expression",
  "expression": "float(payload)"
}
```

### 11.2 payload 是 JSON，字段名是 `weight`（推荐）

```json
"parse": {
  "type": "regex",
  "pattern": "\"weight\"\\s*:\\s*([-+]?[0-9]*\\.?[0-9]+)",
  "group": 1
}
```

### 11.3 payload 是 JSON，但字段名是 `net_weight`

```json
"parse": {
  "type": "regex",
  "pattern": "\"net_weight\"\\s*:\\s*([-+]?[0-9]*\\.?[0-9]+)",
  "group": 1
}
```

### 11.4 payload 是普通文本（如 `WT=214.46kg`）

```json
"parse": {
  "type": "regex",
  "pattern": "WT=\\s*([-+]?[0-9]*\\.?[0-9]+)",
  "group": 1
}
```

## 12. 为什么有时会 `error`，有时只是重量为空

`status = error` 的典型原因：

- `expression` 计算抛异常（例如消息不是数字，却写了 `float(payload)`）。
- `parse.type` 写了不支持的类型。
- 模板缺少 `message_handler`，但设备是 MQTT。

不会报错但重量为空（`weight = null`）的典型原因：

- `regex` 没匹配到内容（例如消息字段名和正则不一致）。

排查顺序建议：

1. 先把 `parse` 改成最简单可通过的版本（与实际 payload 一致）。
2. 再看 `output.weight` 是否仍指向 `${message_handler.result}`。
3. 最后再优化正则（先可用，再优雅）。

## 13. MQTT 去皮/清零可直接用模板（手动控制）

下面模板适配本项目“手动控制”页面：

- 设备实时数据从 `data_topic` 读取（默认 `sensor/weight`）
- 手动命令发布到 `cmd_topic`（默认 `sensor/weight/cmd`）
- 包含两个手动步骤：`tare`（去皮）和 `zero`（清零）

```json
{
  "name": "MQTT 重量传感器（支持去皮清零）",
  "protocol_type": "mqtt",
  "variables": [
    { "name": "data_topic", "type": "string", "default": "sensor/weight", "label": "数据主题" },
    { "name": "cmd_topic", "type": "string", "default": "sensor/weight/cmd", "label": "控制主题" },
    { "name": "qos", "type": "int", "default": 1, "label": "QoS" }
  ],
  "setup_steps": [
    {
      "id": "subscribe_weight",
      "name": "订阅重量主题",
      "trigger": "setup",
      "action": "mqtt.subscribe",
      "params": { "topic": "${data_topic}", "qos": "${qos}" }
    }
  ],
  "steps": [
    {
      "id": "tare",
      "name": "去皮",
      "trigger": "manual",
      "action": "mqtt.publish",
      "params": {
        "topic": "${cmd_topic}",
        "payload": "{\"cmd\":\"tare\"}",
        "qos": "${qos}"
      }
    },
    {
      "id": "zero",
      "name": "清零",
      "trigger": "manual",
      "action": "mqtt.publish",
      "params": {
        "topic": "${cmd_topic}",
        "payload": "{\"cmd\":\"zero\"}",
        "qos": "${qos}"
      }
    }
  ],
  "message_handler": {
    "id": "handle_message",
    "name": "处理消息",
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

## 14. Modbus RTU 双向交互模板（读取 + 手动控制）

下面模板适用于串口 RTU 场景：

- `poll` 步骤：周期读取重量和状态码
- `manual` 步骤：去皮、清零、写目标值
- 可用于地磅、台秤、称重控制器等 RTU 设备

```json
{
  "name": "Modbus RTU 双向交互模板",
  "description": "轮询读取重量 + 手动去皮/清零/写入目标值",
  "protocol_type": "modbus_rtu",
  "variables": [
    { "name": "slave_id", "type": "int", "default": 1, "label": "从站地址" },
    { "name": "weight_addr", "type": "int", "default": 0, "label": "重量寄存器起始地址" },
    { "name": "status_addr", "type": "int", "default": 10, "label": "状态寄存器地址" },
    { "name": "tare_coil_addr", "type": "int", "default": 0, "label": "去皮线圈地址" },
    { "name": "zero_coil_addr", "type": "int", "default": 1, "label": "清零线圈地址" },
    { "name": "target_weight_addr", "type": "int", "default": 20, "label": "目标重量寄存器地址" },
    { "name": "scale", "type": "float", "default": 1000, "label": "重量缩放系数" }
  ],
  "steps": [
    {
      "id": "read_weight",
      "name": "读取重量",
      "trigger": "poll",
      "action": "modbus.read_input_registers",
      "params": {
        "slave_id": "${slave_id}",
        "address": "${weight_addr}",
        "count": 2
      },
      "parse": {
        "type": "expression",
        "expression": "(registers[0] * 65536 + registers[1]) / scale"
      }
    },
    {
      "id": "read_status",
      "name": "读取状态",
      "trigger": "poll",
      "action": "modbus.read_holding_registers",
      "params": {
        "slave_id": "${slave_id}",
        "address": "${status_addr}",
        "count": 1
      },
      "parse": {
        "type": "expression",
        "expression": "registers[0]"
      }
    },
    {
      "id": "tare",
      "name": "去皮",
      "trigger": "manual",
      "action": "modbus.write_coil",
      "params": {
        "slave_id": "${slave_id}",
        "address": "${tare_coil_addr}",
        "value": 1
      }
    },
    {
      "id": "zero",
      "name": "清零",
      "trigger": "manual",
      "action": "modbus.write_coil",
      "params": {
        "slave_id": "${slave_id}",
        "address": "${zero_coil_addr}",
        "value": 1
      }
    },
    {
      "id": "set_target_weight",
      "name": "写入目标重量",
      "trigger": "manual",
      "action": "modbus.write_register",
      "params": {
        "slave_id": "${slave_id}",
        "address": "${target_weight_addr}",
        "value": 1500
      }
    }
  ],
  "output": {
    "weight": "${steps.read_weight.result}",
    "status_code": "${steps.read_status.result}",
    "unit": "kg"
  }
}
```

### 14.1 参数解释（RTU）

- `weight_addr`: 重量高字寄存器起始地址（常见是 2 个 16bit 组合）。
- `scale`: 缩放系数。设备若返回克值可设 `1000` 转成 kg。
- `tare_coil_addr/zero_coil_addr`: 控制线圈地址，需按厂商手册填写。
- `target_weight_addr`: 写入目标值的寄存器地址（如配料设定值）。

### 14.2 设备实例连接参数（不是模板变量）

RTU 场景创建设备时，连接参数建议如下：

```json
{
  "port": "/dev/ttyUSB0",
  "baudrate": 9600,
  "bytesize": 8,
  "parity": "N",
  "stopbits": 1
}
```

### 14.3 调试顺序（RTU）

1. 先只保留 `read_weight`，确认 `weight` 能正常变化。
2. 再加 `read_status`，确认状态寄存器地址无误。
3. 最后测试 `manual` 步骤（去皮/清零/写入），检查是否返回 200。

常见问题：

- 一直 `offline`：串口参数或从站地址不匹配。
- 重量异常大/小：`scale` 或寄存器高低位组合不对。
- 手动执行返回 403：步骤没有设置 `trigger=manual`。

## 15. 梅特勒托利多天平/台秤通用模板（Serial 双向）

下面模板适配常见梅特勒托利多串口 ASCII/MT-SICS 风格命令，支持：

- 轮询读取重量（`SI`）
- 手动去皮（`T`）
- 手动清零（`Z`）

```json
{
  "name": "梅特勒托利多-天平/台秤通用模板(Serial)",
  "description": "轮询读取重量 + 手动去皮/清零，适配常见 MT-SICS/ASCII 串口设备",
  "protocol_type": "serial",
  "variables": [
    { "name": "read_command", "type": "string", "default": "SI\\r\\n", "label": "读取命令" },
    { "name": "tare_command", "type": "string", "default": "T\\r\\n", "label": "去皮命令" },
    { "name": "zero_command", "type": "string", "default": "Z\\r\\n", "label": "清零命令" },
    { "name": "receive_size", "type": "int", "default": 64, "label": "接收字节数" },
    { "name": "timeout_ms", "type": "int", "default": 1200, "label": "超时(ms)" },
    { "name": "weight_pattern", "type": "string", "default": "([-+]?[0-9]+(?:\\.[0-9]+)?)", "label": "重量正则" },
    { "name": "unit", "type": "string", "default": "kg", "label": "单位" }
  ],
  "steps": [
    {
      "id": "send_query",
      "name": "发送读取命令",
      "trigger": "poll",
      "action": "serial.send",
      "params": {
        "data": "${read_command}"
      }
    },
    {
      "id": "wait_response",
      "name": "等待响应",
      "trigger": "poll",
      "action": "delay",
      "params": {
        "milliseconds": 120
      }
    },
    {
      "id": "receive_raw",
      "name": "接收原始报文",
      "trigger": "poll",
      "action": "serial.receive",
      "params": {
        "size": "${receive_size}",
        "timeout": "${timeout_ms}"
      }
    },
    {
      "id": "parse_weight",
      "name": "提取重量",
      "trigger": "poll",
      "action": "transform.regex_extract",
      "params": {
        "input": "${steps.receive_raw.result.payload}",
        "pattern": "${weight_pattern}",
        "group": 1
      },
      "parse": {
        "type": "expression",
        "expression": "float(payload)"
      }
    },
    {
      "id": "tare",
      "name": "去皮",
      "trigger": "manual",
      "action": "serial.send",
      "params": {
        "data": "${tare_command}"
      }
    },
    {
      "id": "zero",
      "name": "清零",
      "trigger": "manual",
      "action": "serial.send",
      "params": {
        "data": "${zero_command}"
      }
    }
  ],
  "output": {
    "weight": "${steps.parse_weight.result}",
    "unit": "${unit}"
  }
}
```

### 15.1 梅特勒命令说明

- `SI`: 请求稳定重量（很多 MT-SICS 设备支持）。
- `T`: 去皮。
- `Z`: 清零。

注意：不同型号命令可能不同，若不匹配请用设备手册命令替换 `read_command/tare_command/zero_command`。

### 15.2 报文解析建议

默认正则 `([-+]?[0-9]+(?:\\.[0-9]+)?)` 适合大多数包含数字的文本报文。  
如果设备返回格式固定（例如 `S S      12.345 g`），建议改为更严格正则，避免误提取：

```json
{
  "type": "regex",
  "pattern": "S\\s+S\\s+([-+]?[0-9]*\\.?[0-9]+)",
  "group": 1
}
```

### 15.3 连接参数建议（梅特勒串口）

设备实例连接参数可先用：

```json
{
  "port": "/dev/ttyUSB0",
  "baudrate": 9600,
  "bytesize": 8,
  "parity": "N",
  "stopbits": 1
}
```

若通信失败，优先核对：波特率、校验位、停止位、命令结束符（是否 `\\r\\n`）。

### 15.4 快速验收

1. 先用 `read_command` 能稳定读到 `weight`。
2. 再测试手动控制页面的去皮/清零按钮是否 200 成功。
3. 查看前端实时卡片，确认单位与变化趋势正确。

---

## 16. 奥豪斯 Navigator 天平串口模板（Serial 双向）

下面模板适配奥豪斯 Navigator 系列（NV/NVL/NVT）电子天平的 USB 虚拟串口协议：

- 轮询读取重量（`P` 命令）
- 手动打印（`SP` 稳定值 / `IP` 当前显示）
- 手动去皮（`T`）
- 手动清零（`Z`）
- 支持切换单位（`U`）
- 支持切换模式（`M`）

```json
{
  "name": "奥豪斯 Navigator 天平 (NV/NVL/NVT)",
  "description": "适配奥豪斯 Navigator 系列电子天平，支持轮询读取、打印、去皮、清零、切换单位/模式",
  "protocol_type": "serial",
  "variables": [
    { "name": "poll_command", "type": "string", "default": "P\\r", "label": "轮询读取命令" },
    { "name": "print_stable_command", "type": "string", "default": "SP\\r", "label": "打印稳定值命令" },
    { "name": "print_current_command", "type": "string", "default": "IP\\r", "label": "打印当前显示命令" },
    { "name": "tare_command", "type": "string", "default": "T\\r", "label": "去皮命令" },
    { "name": "zero_command", "type": "string", "default": "Z\\r", "label": "清零命令" },
    { "name": "unit_command", "type": "string", "default": "U\\r", "label": "切换单位命令" },
    { "name": "mode_command", "type": "string", "default": "M\\r", "label": "切换模式命令" },
    { "name": "receive_size", "type": "int", "default": 64, "label": "接收字节数" },
    { "name": "timeout_ms", "type": "int", "default": 1200, "label": "超时(ms)" },
    { "name": "weight_pattern", "type": "string", "default": "\\s*([-+]?[0-9]+(?:\\.[0-9]+)?)\\s+([a-zA-Z]+)", "label": "重量和单位正则" },
    { "name": "default_unit", "type": "string", "default": "g", "label": "默认单位" }
  ],
  "steps": [
    {
      "id": "send_poll",
      "name": "发送轮询命令",
      "trigger": "poll",
      "action": "serial.send",
      "params": {
        "data": "${poll_command}"
      }
    },
    {
      "id": "wait_poll_response",
      "name": "等待响应",
      "trigger": "poll",
      "action": "delay",
      "params": {
        "milliseconds": 150
      }
    },
    {
      "id": "receive_poll_raw",
      "name": "接收轮询响应",
      "trigger": "poll",
      "action": "serial.receive",
      "params": {
        "size": "${receive_size}",
        "timeout": "${timeout_ms}"
      }
    },
    {
      "id": "parse_weight",
      "name": "解析重量和单位",
      "trigger": "poll",
      "action": "transform.regex_extract",
      "params": {
        "input": "${steps.receive_poll_raw.result.payload}",
        "pattern": "${weight_pattern}",
        "group": 1
      },
      "parse": {
        "type": "expression",
        "expression": "float(payload)"
      }
    },
    {
      "id": "parse_unit",
      "name": "解析单位",
      "trigger": "poll",
      "action": "transform.regex_extract",
      "params": {
        "input": "${steps.receive_poll_raw.result.payload}",
        "pattern": "${weight_pattern}",
        "group": 2
      },
      "parse": {
        "type": "expression",
        "expression": "payload.strip()"
      }
    },
    {
      "id": "print_stable",
      "name": "打印稳定值",
      "trigger": "manual",
      "action": "serial.send",
      "params": {
        "data": "${print_stable_command}"
      }
    },
    {
      "id": "print_current",
      "name": "打印当前显示",
      "trigger": "manual",
      "action": "serial.send",
      "params": {
        "data": "${print_current_command}"
      }
    },
    {
      "id": "tare",
      "name": "去皮",
      "trigger": "manual",
      "action": "serial.send",
      "params": {
        "data": "${tare_command}"
      }
    },
    {
      "id": "zero",
      "name": "清零",
      "trigger": "manual",
      "action": "serial.send",
      "params": {
        "data": "${zero_command}"
      }
    },
    {
      "id": "toggle_unit",
      "name": "切换单位",
      "trigger": "manual",
      "action": "serial.send",
      "params": {
        "data": "${unit_command}"
      }
    },
    {
      "id": "toggle_mode",
      "name": "切换模式",
      "trigger": "manual",
      "action": "serial.send",
      "params": {
        "data": "${mode_command}"
      }
    }
  ],
  "output": {
    "weight": "${steps.parse_weight.result}",
    "unit": "${steps.parse_unit.result}",
    "raw_payload": "${steps.receive_poll_raw.result.payload}"
  }
}
```

### 16.1 命令说明

Navigator 系列支持的主要命令：

| 命令 | 功能 | 模板变量 |
|------|------|----------|
| `P` | 立即打印当前重量 | `poll_command` |
| `SP` | 仅打印稳定值 | `print_stable_command` |
| `IP` | 打印当前显示（不稳定也可） | `print_current_command` |
| `T` | 去皮 | `tare_command` |
| `Z` | 清零 | `zero_command` |
| `U` | 切换显示单位 | `unit_command` |
| `M` | 切换称重模式 | `mode_command` |

其他可用命令（可按需添加）：

| 命令 | 功能 |
|------|------|
| `CP` | 连续打印 |
| `SLP` | 自动打印非零稳定值 |
| `SLZP` | 自动打印非零稳定值+零点 |
| `xP` | 每 x 秒打印（1-3600） |
| `0P` | 关闭自动打印 |
| `PM` | 打印当前模式 |
| `PU` | 打印当前单位 |
| `PV` | 打印软件版本 |

### 16.2 数据格式说明

Navigator 返回数据格式：

```
[weight:10][ ][unit:1~5][ ][stability:1][ ][NET:0|3][legend:0~16]\r\n
```

**示例数据**

```
*******200 g
********15 g   NET
*******124 g ? NET
********15 g   NET 00:00:02
***5:10.75 lb:oz ? NET ACCEPT 00:00:05
```

- `?` 标记表示不稳定
- `NET` 表示净重模式
- `lb:oz` 表示磅:盎司复合单位

默认正则 `\\s*([-+]?[0-9]+(?:\\.[0-9]+)?)\\s+([a-zA-Z]+)` 可提取：
- 第1组：重量值（如 `200`、`15.73`、`5:10.75`）
- 第2组：单位（如 `g`、`lb:oz`）

### 16.3 连接参数建议

奥豪斯 Navigator USB（虚拟串口）默认参数：

```json
{
  "port": "COM3",
  "baudrate": 2400,
  "bytesize": 7,
  "parity": "N",
  "stopbits": 1
}
```

可选配置（按设备实际设置）：

| 参数 | 可选值 |
|------|--------|
| 波特率 | 600 / 1200 / 2400 / 4800 / 9600 / 19200 |
| 校验位 | 7-even / 7-odd / 7-none / 8-none |
| 握手 | None / Xon-Xoff / RTS-CTS |

### 16.4 复合单位处理

当使用 `lb:oz` 等复合单位时，返回的 `weight` 会是 `5:10.75` 格式。
如需单独处理，可在解析步骤中添加自定义正则或表达式。

### 16.5 快速验收

1. 确认串口参数正确，能正常连接设备
2. 用轮询命令 `P` 确认能稳定读到 `weight` 和 `unit`
3. 测试手动控制页面的去皮/清零/打印按钮是否返回 200
4. 检查前端实时卡片，确认重量值和单位变化正确

常见问题：

- 读不到数据：检查波特率/校验位/停止位配置
- 重量为空：确认正则表达式是否匹配实际返回格式
- 单位错误：检查 `group: 2` 是否正确提取单位字段
