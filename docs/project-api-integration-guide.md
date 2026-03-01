# Quantix Connector 项目 API 对接文档

> 目的：供其他项目（后端服务、前端系统、AI Agent）快速对接 Quantix Connector，读取设备实时重量并执行控制。
> 文档基于当前代码实现（FastAPI 路由 + Pydantic 模型）整理。

---

## 1. 接口总览

- 协议：HTTP/HTTPS + WebSocket
- 默认本地地址：`http://127.0.0.1:8000`
- 健康检查：`GET /health`
- 实时推送：`WS /ws?api_key=...`
- 鉴权：`X-API-Key`（推荐），也支持 query 参数 `api_key`

### 1.1 OpenAPI（可机器读取）

FastAPI 默认暴露：

- `GET /openapi.json`：完整机器可读 API 结构（建议 AI/代码生成器优先读取）
- `GET /docs`：Swagger UI

---

## 2. 鉴权

### 2.1 API Key

默认环境变量：

- `API_KEY=quantix-dev-key`

请求时携带其一：

1. Header：`X-API-Key: quantix-dev-key`（推荐）
2. Query：`?api_key=quantix-dev-key`

### 2.2 失败响应

```json
{
  "detail": "Invalid API key"
}
```

状态码：`401`

---

## 3. 通用约定

### 3.1 时间格式

- 时间戳为 ISO8601（UTC），如：`2026-03-01T08:15:30.123456+00:00`

### 3.2 设备编号规范（device_code）

- 正则：`^[A-Z0-9][A-Z0-9_-]{0,63}$`
- 系统会自动转大写并去首尾空格

示例合法值：`SCALE_01`、`DEV-000001`、`LINEA-A1`

### 3.3 错误格式

多数错误响应为：

```json
{
  "detail": "错误信息"
}
```

---

## 4. 快速对接流程（推荐）

1. 调用 `GET /api/devices` 获取本地已接入设备清单（含每个设备当前 `runtime`）。
2. 选定目标设备后，调用 `GET /api/devices/by-code/{device_code}` 获取单设备快照（最新状态/重量/错误）。
3. 建立 `WS /ws?api_key=...` 长连接，持续接收实时重量更新。
4. 如需执行控制动作（去皮/清零等），调用 `POST /api/devices/by-code/{device_code}/execute`。

### 4.1 如何获知本地设备信息

“本地设备信息”通常分为两类：

1. 已在 Quantix 中注册的业务设备：`GET /api/devices`
2. 本机可用串口资源（用于现场接线排查）：`GET /api/serial-debug/ports`

`GET /api/devices` 返回示例（节选）：

```json
[
  {
    "id": 1,
    "device_code": "SCALE_01",
    "name": "一号秤",
    "protocol_template_id": 3,
    "enabled": true,
    "runtime": {
      "status": "online",
      "weight": 12.34,
      "unit": "kg",
      "timestamp": "2026-03-01T08:10:01+00:00",
      "error": null
    }
  }
]
```

`GET /api/serial-debug/ports` 返回示例（节选）：

```json
{
  "ok": true,
  "ports": [
    {
      "device": "/dev/ttyUSB0",
      "description": "USB-Serial Controller"
    }
  ]
}
```

### 4.2 如何实时获取本地设备值

推荐“主推送 + 兜底轮询”双通道：

1. 主通道：WebSocket `WS /ws?api_key=...`，监听 `type=weight_update`。
2. 兜底通道：若 WebSocket 断开，短周期调用 `GET /api/devices/by-code/{device_code}` 获取最新 `runtime`。
3. 恢复策略：WebSocket 重连成功后停止兜底轮询。

> 结论：要“实时”就优先 WebSocket；HTTP `GET` 适合快照查询和断线兜底，不建议仅靠 HTTP 轮询长期承载高频实时场景。

---

## 5. 设备 API（/api/devices）

> 所有接口都需要 API Key。

## 5.1 数据模型

### DeviceCreate

```json
{
  "device_code": "SCALE_01",
  "name": "一号秤",
  "protocol_template_id": 1,
  "connection_params": {},
  "template_variables": {},
  "poll_interval": 1.0,
  "enabled": true
}
```

字段说明：

- `device_code` string 必填，唯一，匹配正则
- `name` string 必填，唯一
- `protocol_template_id` int 必填
- `connection_params` object 可选，默认 `{}`
- `template_variables` object 可选，默认 `{}`
- `poll_interval` float 可选，默认 `1.0`（秒）
- `enabled` bool 可选，默认 `true`

### DeviceUpdate

与 `DeviceCreate` 字段一致，但均可选（局部更新语义）。

### ExecuteStepRequest

```json
{
  "step_id": "tare",
  "params": {
    "value": 1
  }
}
```

- `step_id` string 必填
- `params` object 可选，默认 `{}`，用于覆盖模板步骤参数

## 5.2 返回对象（Device）

```json
{
  "id": 1,
  "device_code": "SCALE_01",
  "name": "一号秤",
  "protocol_template_id": 1,
  "connection_params": {},
  "template_variables": {},
  "poll_interval": 1.0,
  "enabled": true,
  "created_at": "2026-03-01T08:00:00+00:00",
  "updated_at": "2026-03-01T08:00:00+00:00"
}
```

`GET` 详情接口额外包含 `runtime` 字段：

```json
{
  "runtime": {
    "type": "weight_update",
    "device_id": 1,
    "device_name": "一号秤",
    "device_code": "SCALE_01",
    "weight": 12.34,
    "unit": "kg",
    "timestamp": "2026-03-01T08:10:01+00:00",
    "status": "online",
    "error": null
  }
}
```

## 5.3 接口列表

### 5.3.1 列表与创建

- `GET /api/devices`：获取全部设备（含运行态）
- `POST /api/devices`：创建设备

常见错误：

- `404`：`Protocol template not found`
- `409`：`Device code already exists` / `Device name already exists`

### 5.3.2 按 device_id

- `GET /api/devices/{device_id}`
- `PUT /api/devices/{device_id}`
- `DELETE /api/devices/{device_id}`
- `POST /api/devices/{device_id}/enable`
- `POST /api/devices/{device_id}/disable`
- `POST /api/devices/{device_id}/execute`

### 5.3.3 按 device_code（推荐对接）

- `GET /api/devices/by-code/{device_code}`
- `PUT /api/devices/by-code/{device_code}`
- `DELETE /api/devices/by-code/{device_code}`
- `POST /api/devices/by-code/{device_code}/enable`
- `POST /api/devices/by-code/{device_code}/disable`
- `POST /api/devices/by-code/{device_code}/execute`

为什么推荐 by-code：跨环境迁移时 `device_id` 可能变化，但 `device_code` 可保持稳定。

## 5.4 执行手动步骤（核心约束）

调用 `/execute` 时：

- 设备未启用：返回 `400`，`Device is disabled`
- 步骤不存在：返回 `404`
- 步骤不是手动触发（`trigger != manual`）：返回 `403`

成功示例：

```json
{
  "step_id": "tare",
  "result": {
    "topic": "sensor/weight/cmd",
    "published": true
  },
  "output": {
    "weight": "12.34",
    "unit": "kg"
  }
}
```

---

## 6. 协议模板 API（/api/protocols）

## 6.1 数据模型

### ProtocolTemplateCreate

```json
{
  "name": "标准 Modbus 模板",
  "description": "读取重量",
  "protocol_type": "modbus_tcp",
  "template": {},
  "is_system": false
}
```

### ProtocolTemplateUpdate

可更新字段（全可选）：

- `name`
- `description`
- `protocol_type`
- `template`

## 6.2 接口列表

- `GET /api/protocols`：模板列表
- `POST /api/protocols`：新建模板
- `POST /api/protocols/import`：导入模板（按名称防重）
- `GET /api/protocols/{protocol_id}`：详情
- `PUT /api/protocols/{protocol_id}`：更新
- `DELETE /api/protocols/{protocol_id}`：删除
- `GET /api/protocols/{protocol_id}/export`：导出（name/description/protocol_type/template）

限制与错误：

- 模板被设备引用时，不允许修改/删除：`409`
- 系统模板不允许删除：`403`，`System protocol can not be deleted`
- 不存在：`404`

## 6.3 模板测试接口

### 6.3.1 全模板测试

`POST /api/protocols/{protocol_id}/test`

请求：

```json
{
  "connection_params": {},
  "template_variables": {}
}
```

响应：

```json
{
  "ok": true,
  "steps": {},
  "output": {
    "weight": 12.3,
    "unit": "kg"
  }
}
```

失败示例：

```json
{
  "ok": false,
  "error": "connect failed"
}
```

### 6.3.2 单步骤测试

`POST /api/protocols/{protocol_id}/test-step`

请求：

```json
{
  "connection_params": {},
  "template_variables": {},
  "step_id": "read_weight",
  "step_context": "poll",
  "allow_write": false,
  "test_payload": null,
  "previous_steps": {
    "step_a": {
      "result": {
        "value": 1
      }
    }
  }
}
```

字段约束：

- `step_context` 必须为：`setup` / `poll` / `event`
- `previous_steps` 必须是 `{step_id: {result: ...}}` 结构
- 写操作步骤（`modbus.write_register` / `modbus.write_coil` / `mqtt.publish`）默认禁止，需显式 `allow_write=true`

写操作安全拦截响应示例：

```json
{
  "ok": false,
  "error": "写操作需要显式设置 allow_write=true",
  "action": "mqtt.publish",
  "safety_warning": "该操作可能修改设备状态"
}
```

---

## 7. 串口调试 API（/api/serial-debug）

> 用于调试串口链路，不是生产业务数据接口，但对现场联调非常有用。

接口：

- `GET /api/serial-debug/ports`：列可用串口
- `GET /api/serial-debug/status`：当前调试连接状态
- `POST /api/serial-debug/open`：打开串口
- `POST /api/serial-debug/close`：关闭串口
- `POST /api/serial-debug/send`：发送数据
- `GET /api/serial-debug/read`：读取数据
- `GET /api/serial-debug/logs`：拉取日志流

### 7.1 open 请求体

```json
{
  "port": "COM3",
  "baudrate": 9600,
  "bytesize": 8,
  "parity": "N",
  "stopbits": 1.0,
  "timeout_ms": 300
}
```

`parity` 枚举：`N/E/O/M/S`

### 7.2 send 请求体

```json
{
  "data": "SI",
  "data_format": "text",
  "encoding": "utf-8",
  "line_ending": "crlf"
}
```

- `data_format`：`text` / `hex`
- `line_ending`：`none` / `cr` / `lf` / `crlf`

---

## 8. WebSocket 实时数据订阅

## 8.1 连接

- URL：`ws://127.0.0.1:8000/ws?api_key=quantix-dev-key`
- API Key 错误时直接关闭：`code=4401`

## 8.2 推送消息

### weight_update

```json
{
  "type": "weight_update",
  "device_id": 1,
  "device_name": "一号秤",
  "device_code": "SCALE_01",
  "weight": 12.34,
  "unit": "kg",
  "timestamp": "2026-03-01T08:10:01+00:00",
  "status": "online",
  "error": null
}
```

### ping

当 30 秒无新数据时服务端会发：

```json
{
  "type": "ping"
}
```

### 8.3 推荐消费策略（生产）

1. 客户端连接后，先缓存最近一次 `weight_update`。
2. 收到 `ping` 时保持连接即可，无需回包业务数据。
3. 若连接断开，按 1s/2s/5s 阶梯退避重连。
4. 重连期间使用 `GET /api/devices/by-code/{device_code}` 轮询兜底。
5. 同一设备以 `device_code` 做幂等键，避免多连接重复渲染。

---

## 9. 典型集成示例

## 9.1 curl：按 device_code 查询设备

```bash
curl -s -H "X-API-Key: quantix-dev-key" \
  http://127.0.0.1:8000/api/devices/by-code/SCALE_01
```

## 9.2 curl：执行去皮（manual step）

```bash
curl -s -X POST \
  -H "X-API-Key: quantix-dev-key" \
  -H "Content-Type: application/json" \
  -d '{"step_id":"tare","params":{}}' \
  http://127.0.0.1:8000/api/devices/by-code/SCALE_01/execute
```

## 9.3 Python：订阅 WebSocket

```python
import asyncio
import json
import websockets

API_KEY = "quantix-dev-key"
URL = f"ws://127.0.0.1:8000/ws?api_key={API_KEY}"

async def main():
    async with websockets.connect(URL) as ws:
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            if data.get("type") == "weight_update":
                print(data["device_code"], data["weight"], data["unit"], data["status"])

asyncio.run(main())
```

## 9.4 Python：WebSocket 断线时 HTTP 兜底获取实时值

```python
import asyncio
import json
import requests
import websockets

BASE = "http://127.0.0.1:8000"
API_KEY = "quantix-dev-key"
DEVICE_CODE = "SCALE_01"
WS_URL = f"ws://127.0.0.1:8000/ws?api_key={API_KEY}"
HEADERS = {"X-API-Key": API_KEY}

def fetch_snapshot():
    url = f"{BASE}/api/devices/by-code/{DEVICE_CODE}"
    data = requests.get(url, headers=HEADERS, timeout=3).json()
    rt = data.get("runtime", {})
    print("[HTTP]", DEVICE_CODE, rt.get("weight"), rt.get("unit"), rt.get("status"))

async def stream():
    backoff = 1
    while True:
        try:
            async with websockets.connect(WS_URL) as ws:
                backoff = 1
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    if data.get("type") == "weight_update" and data.get("device_code") == DEVICE_CODE:
                        print("[WS]", DEVICE_CODE, data.get("weight"), data.get("unit"), data.get("status"))
        except Exception:
            fetch_snapshot()
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 5)

asyncio.run(stream())
```

---

## 10. AI Agent 对接建议（让 AI 一次写对）

给 AI 的关键约束建议直接贴入提示词：

1. 所有 HTTP 请求必须加 `X-API-Key`。
2. 设备操作优先使用 `/api/devices/by-code/{device_code}`，不要依赖 `device_id`。
3. 实时重量优先走 WebSocket `/ws`，并处理 `ping` 心跳。
4. 执行控制动作前，调用者需准备 `manual` 步骤 ID；若接口返回 `403`，说明步骤不是手动触发。
5. 解析错误时优先读取返回体 `detail` 或 `error` 字段。
6. 使用 `/openapi.json` 自动生成客户端类型与请求代码。

---

## 11. 附录：协议连接参数参考

不同 `protocol_type` 常见 `connection_params`：

- `modbus_tcp`：`{"host":"192.168.1.10","port":502,"timeout":1.0}`
- `modbus_rtu`：`{"port":"/dev/ttyUSB0","baudrate":9600,"parity":"N","stopbits":1,"bytesize":8,"timeout":1.0}`
- `mqtt`：`{"host":"127.0.0.1","port":1883,"username":"user","password":"pass"}`
- `serial`：`{"port":"/dev/ttyUSB0","baudrate":9600,"bytesize":8,"parity":"N","stopbits":1,"timeout":1.0}`
- `tcp`：`{"host":"192.168.1.20","port":9000}`

> 注意：`SIMULATE_ON_CONNECT_FAIL=true` 时，Modbus 连接失败可能进入模拟数据模式；生产环境建议按需关闭。
