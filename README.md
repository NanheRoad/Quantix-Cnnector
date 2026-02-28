# Quantix Connector

计量设备统一接入系统（FastAPI + Dash），支持 Modbus/MQTT/串口/TCP，实时采集重量并推送到前端。

## 快速启动

```bash
pip install -r requirements.txt

# 启动后端
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# 新终端启动前端
python app.py
```

默认 API Key：`quantix-dev-key`

## 关键功能

- 设备管理：新增/删除/启停设备
- 协议模板：JSON 模板化执行（poll/manual/setup/message_handler）
- 实时推送：WebSocket `/ws?api_key=...`
- 手动控制：`/api/devices/{id}/execute`（仅 `trigger=manual` 步骤）
- 串口调试：内置串口连通、发送、日志查看

## 设备编号（`device_code`）

设备支持独立编号字段 `device_code`，用于唯一标识和 API 定位。

- 唯一性：全局唯一
- 建议格式：`^[A-Z0-9][A-Z0-9_-]{0,63}$`
- 示例：`SCALE_01`、`LINE1-A-03`
- 兼容迁移：旧库启动时自动补齐编号（如 `DEV-000001`）并建立唯一索引

## API 鉴权

- HTTP：请求头 `X-API-Key: <your-key>`
- WebSocket：查询参数 `?api_key=<your-key>`

## 设备 API 示例

### 创建设备（含设备编号）

```http
POST /api/devices
Content-Type: application/json
X-API-Key: quantix-dev-key
```

```json
{
  "device_code": "SCALE_01",
  "name": "电子秤01",
  "protocol_template_id": 1,
  "connection_params": {"host": "127.0.0.1", "port": 502},
  "template_variables": {"slave_id": 1, "address": 0},
  "poll_interval": 1.0,
  "enabled": true
}
```

### 通过设备编号操作设备

- 获取设备：`GET /api/devices/by-code/{device_code}`
- 更新设备：`PUT /api/devices/by-code/{device_code}`
- 删除设备：`DELETE /api/devices/by-code/{device_code}`
- 启用设备：`POST /api/devices/by-code/{device_code}/enable`
- 禁用设备：`POST /api/devices/by-code/{device_code}/disable`
- 手动执行：`POST /api/devices/by-code/{device_code}/execute`

`device_id` 路由仍保留，兼容历史调用。

## WebSocket 实时订阅工具

项目内置工具：`tools/ws_realtime_subscriber.py`

安装依赖：

```bash
pip install websockets
```

常用示例：

```bash
# 订阅全部设备
python tools/ws_realtime_subscriber.py

# 只看某个 device_id
python tools/ws_realtime_subscriber.py --device-id 1

# 只看某个 device_code（新增）
python tools/ws_realtime_subscriber.py --device-code SCALE_01

# 连接远端后端
python tools/ws_realtime_subscriber.py --host 192.168.1.100 --port 8000

# 调试模式
python tools/ws_realtime_subscriber.py --show-ping --raw
```

输出示例（已包含 `device_code`）：

```text
[2026-02-28 14:30:45] device_id=1 device_code=SCALE_01 name=电子秤01 status=online weight=1250.5 kg
```

## 数据迁移工具

```bash
python scripts/migrate_db.py --export sqlite_backup.json
python scripts/migrate_db.py --import sqlite_backup.json
```

## 常用环境变量

- `API_KEY`: API 鉴权 key（默认 `quantix-dev-key`）
- `DB_TYPE`: `sqlite` / `mysql`
- `DB_NAME`: 数据库名（SQLite 默认 `quantix.db`）
- `BACKEND_HOST` / `BACKEND_PORT`: 后端地址
- `FRONTEND_HOST` / `FRONTEND_PORT`: 前端地址
- `SIMULATE_ON_CONNECT_FAIL`: 连接失败时是否启用模拟数据
