# AGENTS.md

## 1. 项目目标
- 项目名称：Quantix Connector。
- 业务目标：统一接入计量设备（Modbus/MQTT/串口/TCP），实时采集重量并推送到 Web 前端。
- 开发目标：保持代码可运行、可调试、可扩展，避免“只改页面不改后端契约”的漂移。

## 2. 先读哪些文件
- 方案文档：[docs/plans/2026-02-24-quantix-device-management-system-design.md](docs/plans/2026-02-24-quantix-device-management-system-design.md)
- 模板说明：[docs/protocol-template-json-guide.md](docs/protocol-template-json-guide.md)
- 后端入口：[backend/main.py](backend/main.py)
- 前端入口：[app.py](app.py)
- 调试经验库：[debug.md](debug.md)

## 3. 架构总览
- 后端：FastAPI + 服务层（DeviceManager / ProtocolExecutor）+ 驱动层 + SQLite(Peewee)。
- 前端：Dash 多页签（实时大屏、设备配置、协议模板）。
- 实时链路：DeviceManager -> EventBus -> WebSocket `/ws` -> Dashboard。
- 模板执行：ProtocolExecutor 解释 JSON（trigger/action/params/parse/output）。

## 4. 关键目录与职责
- `backend/api/`: 路由与鉴权（设备、协议模板、WebSocket）。
- `backend/services/`: 业务核心。
  - `device_manager.py`: 生命周期、重连、轮询、手动执行。
  - `protocol_executor.py`: 模板解释执行。
  - `event_bus.py`: 广播队列。
- `backend/drivers/`: 协议驱动实现与工厂。
- `backend/database/`: 模型、连接、系统模板种子。
- `frontend/pages/`: 页面布局。
- `assets/`: 全局 CSS（输入框/下拉框/表格样式）。

## 5. 协议模板关键规则
- 轮询读取步骤：`trigger = "poll"`。
- 手动控制步骤：`trigger = "manual"`，仅能通过 `/api/devices/{id}/execute`。
- MQTT 模板：必须使用 `setup_steps` + `message_handler`，不要放到普通轮询 `steps`。
- 输出统一走 `output`，常见字段：`weight`、`unit`。

## 6. 后端行为约束
- `/api/devices/{id}/execute` 必须校验步骤 `trigger == "manual"`，否则返回 `403`。
- 设备必须包含唯一 `device_code`（建议格式：`^[A-Z0-9][A-Z0-9_-]{0,63}$`）。
- 除 `/{device_id}` 路由外，必须支持 `/api/devices/by-code/{device_code}` 进行设备识别与操作（查询/更新/删除/启停/执行）。
- API 默认使用 `X-API-Key` 鉴权；WebSocket 使用 `?api_key=...`。
- `SIMULATE_ON_CONNECT_FAIL=true` 时，连接失败会返回模拟数据；`false` 时应离线/报错。

## 7. 前端交互约束
- 可枚举字段优先下拉，不让用户手填协议枚举值。
- “新建设备”必须提供“设备编号（device_code）”输入项，并在设备列表/控制入口可见。
- 设置项必须附带说明文案（用途、单位、影响）。
- 同一行输入控件高度保持一致（由 `assets/app.css` 控制）。
- 采集频率输入单位是“次/秒”，提交时转换为 `poll_interval(秒)=1/频率`。

## 8. 本地运行与检查
```bash
pip install -r requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
# 新终端
python app.py
```

语法检查：
```bash
python -m compileall backend frontend config app.py scripts
```

## 9. 常用环境变量
- `API_KEY`: API 鉴权 key（默认 `quantix-dev-key`）。
- `DB_TYPE`: `sqlite` / `mysql`。
- `DB_NAME`: 数据库名（SQLite 默认 `quantix.db`）。
- `BACKEND_HOST` / `BACKEND_PORT`: 后端地址。
- `FRONTEND_HOST` / `FRONTEND_PORT`: 前端地址。
- `SIMULATE_ON_CONNECT_FAIL`: 连接失败是否启用模拟数据。

## 10. 修改清单（每次改动尽量满足）
- 是否更新了对应文档（尤其模板 JSON 结构变更）。
- 是否保持 API 与前端字段一致。
- 是否保留了手动步骤 403 保护。
- 是否通过 `compileall`。

## 11. 常见问题排查
- 设备一直 `offline`：
  - 检查连接参数与模板协议是否匹配。
  - 检查是否关闭了模拟模式（`SIMULATE_ON_CONNECT_FAIL=false`）。
- `/api/*` 返回 401：
  - 检查 `X-API-Key`。
- 前端控件错位：
  - 检查 `assets/app.css` 是否生效，必要时强刷页面。

## 12. 持续进化要求（必须执行）
- 任何功能开发、重构、修复完成后，都要检查是否需要更新本文件：
  - 新增了约束、流程、契约、排错手段时，必须补充到 `AGENTS.md`。
  - 若规则变化会影响前后端协作，必须在同次提交中同步更新。
- 任何 Bug 修复后，都要同步沉淀到 `debug.md`：
  - 至少记录“现象、根因、修复、验证、预防”五项。
  - 同类问题第二次出现时，要把“检测脚本/断言/测试用例”补齐，避免重复踩坑。
- 新增的工程约定应满足“可检查、可复现、可回归”三原则：
  - 可检查：有明确命令、日志或接口行为可验证。
  - 可复现：有最小复现场景或输入。
  - 可回归：至少有一条可自动化的回归手段（测试、脚本或静态检查）。

## 13. Debug 沉淀标准（关联 `debug.md`）
- 每条记录必须有唯一 ID（如 `DBG-2026-02-28-01`）和日期。
- 每条记录必须标注影响范围（前端/后端/驱动/数据库/部署）。
- 每条记录必须附带验证证据（命令、返回码、日志片段或截图路径）。
- 每条记录必须给出“是否已加回归防护”，未加时要写明原因和计划日期。
