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
