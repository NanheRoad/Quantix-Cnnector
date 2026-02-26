# Quantix Connector

计量设备管理系统 MVP（FastAPI + Dash）。

## 快速启动

```bash
pip install -r requirements.txt

# 启动后端
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# 新终端启动前端
python app.py
```

默认 API Key：`quantix-dev-key`

可通过环境变量覆盖：

```bash
export API_KEY="your-secret-key"
export BACKEND_HOST="127.0.0.1"
export BACKEND_PORT="8000"
export FRONTEND_HOST="127.0.0.1"
export FRONTEND_PORT="8050"
```

## 数据迁移

```bash
python scripts/migrate_db.py --export sqlite_backup.json
python scripts/migrate_db.py --import sqlite_backup.json
```

## 说明

- 默认使用 SQLite（`quantix.db`）。
- 当 Modbus 设备连接失败时，默认启用模拟模式（`SIMULATE_ON_CONNECT_FAIL=true`）。
- WebSocket 推送地址：`ws://host:port/ws?api_key=...`

## WebSocket 实时订阅工具

项目提供了一个独立的 WebSocket 实时订阅工具 `ws_realtime_subscriber.py`，用于接收和显示计量设备的实时数据更新。

### 安装依赖

```bash
pip install websockets
```

### 基本用法

```bash
# 连接到本地后端，接收所有设备的实时数据
python ws_realtime_subscriber.py

# 指定主机和端口
python ws_realtime_subscriber.py --host 192.168.1.100 --port 8000

# 使用自定义 API Key
python ws_realtime_subscriber.py --api-key your-secret-key

# 只订阅特定设备
python ws_realtime_subscriber.py --device-id 1

# 使用 WebSocket Secure (wss://)
python ws_realtime_subscriber.py --wss

# 显示 ping 消息（用于调试连接）
python ws_realtime_subscriber.py --show-ping

# 显示原始 JSON 数据
python ws_realtime_subscriber.py --raw
```

### 功能特性

- **自动重连**: 连接断开时自动重连，采用指数退避策略（最大 30 秒）
- **时间戳格式化**: 自动将 ISO 8601 时间戳转换为本地时间格式
- **设备过滤**: 可选择只显示特定设备的数据
- **灵活输出**: 支持格式化输出或原始 JSON 输出

### 输出示例

```
[connect] ws://127.0.0.1:8000/ws?api_key=quantix-dev-key
[connected] waiting for real-time updates...
[2026-02-26 14:30:45] device_id=1 name=地磅01 status=online weight=1250.5 kg
[2026-02-26 14:30:46] device_id=2 name=台秤05 status=online weight=45.2 kg
[2026-02-26 14:30:47] device_id=1 name=地磅01 status=error weight= null kg error=Modbus timeout
```

### 消息类型

- `weight_update`: 设备重量数据更新
- `ping`: 心跳消息（默认不显示，使用 `--show-ping` 显示）
- 其他事件类型会以 `[event:type]` 格式显示
