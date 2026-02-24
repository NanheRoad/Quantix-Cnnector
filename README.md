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
