# 梅特勒托利多电子天平/台秤串口通讯说明（MT-SICS 常见场景）

> 适用范围：常见支持 MT-SICS 或兼容 ASCII 命令集的梅特勒托利多设备
> 接口类型：RS232 / USB 虚拟串口
> 目标：用于 Quantix Connector 协议模板快速落地（读取重量 + 手动去皮/清零）

---

## 1. 通讯架构

### 1.1 接口说明

- 物理接口：RS232 或 USB（映射为虚拟串口）
- 逻辑接口：Serial（COM）
- 通讯编码：ASCII
- 行结束符：常见为 `CRLF`（`\r\n`），部分型号仅 `CR`（`\r`）

### 1.2 协议特征

- 多数设备支持 MT-SICS 命令风格
- 查询命令为短字符串（如 `SI`）
- 响应通常为文本行，包含状态位、数值、单位

---

## 2. 串口参数建议

### 2.1 推荐起始参数

| 参数 | 推荐值 |
|------|--------|
| 波特率 | 9600 |
| 数据位 | 8 |
| 校验位 | None（N） |
| 停止位 | 1 |
| 流控 | None |

### 2.2 常见备选组合

| 参数 | 备选值 |
|------|--------|
| 波特率 | 2400 / 4800 / 19200 |
| 校验位 | Even / Odd |
| 数据位 | 7 / 8 |

说明：最终以设备手册配置页为准。若设备连通失败，优先核对波特率、校验位、结束符。

---

## 3. 常用命令（典型 MT-SICS 场景）

| 命令 | 功能 | 备注 |
|------|------|------|
| `SI` | 读取稳定重量 | 常用于轮询读取 |
| `S` | 读取当前重量 | 部分型号支持 |
| `T` | 去皮 | 用于手动控制 |
| `Z` | 清零 | 用于手动控制 |
| `I0` | 查询设备信息 | 部分型号支持 |

命令结束符通常为 `\r\n`，例如 `SI\r\n`。

---

## 4. 响应格式与解析建议

### 4.1 常见响应形态

1. 纯数字或数字+单位

```text
12.345 g
```

2. 带状态位的 MT-SICS 文本（示意）

```text
S S      12.345 g
```

3. 不稳定状态（示意）

```text
S I      12.346 g
```

### 4.2 解析策略

- 第一阶段先“提到数字”为目标，使用宽松正则：

```regex
([-+]?[0-9]+(?:\.[0-9]+)?)
```

- 第二阶段再按机型优化为严格正则（避免误匹配）。
- 若设备响应包含单位（g/kg），建议单位固定由模板变量控制，避免解析抖动。

---

## 5. Quantix 协议模板（可直接使用）

```json
{
  "name": "梅特勒托利多-天平台秤通用模板(Serial)",
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

---

## 6. 设备创建时连接参数示例（非模板字段）

```json
{
  "port": "/dev/ttyUSB0",
  "baudrate": 9600,
  "bytesize": 8,
  "parity": "N",
  "stopbits": 1
}
```

Windows 示例：`"port": "COM3"`

---

## 7. 快速验收步骤

1. 仅保留读取流程（`send_query -> wait_response -> receive_raw -> parse_weight`），确认 `weight` 有值。
2. 在手动控制页测试 `tare`、`zero`，确认接口返回成功。
3. 再按设备实际响应微调 `weight_pattern` 和 `read_command`。

---

## 8. 常见问题排查

### 8.1 一直 `offline`

- 串口参数不匹配（波特率/校验位/停止位）
- 串口号错误（`/dev/ttyUSB0` / `COMx`）
- 结束符不匹配（设备只收 `\r`，但发了 `\r\n`）

### 8.2 有响应但 `weight` 为空

- 正则未匹配到数字
- 响应字段不是预期格式（需抓原始报文调整 `weight_pattern`）

### 8.3 手动去皮/清零失败

- `tare`/`zero` 步骤不是 `trigger=manual`
- 命令字不符合设备机型

### 8.4 重量值异常

- 解析提取到错误字段
- 设备实际单位为 `g`，但模板 `unit` 写成 `kg`

---

## 9. 机型适配建议

- 先确认设备是否启用 MT-SICS 或兼容命令模式。
- 若手册命令与本文不同，以手册优先，仅替换模板中的变量：
  - `read_command`
  - `tare_command`
  - `zero_command`
  - `weight_pattern`
- 先“可读到值”再“严格解析”。
