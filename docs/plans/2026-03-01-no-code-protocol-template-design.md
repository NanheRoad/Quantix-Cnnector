# 无代码协议模板编辑器设计文档

**日期**: 2026-03-01
**项目**: Quantix Connector - 协议模板无代码配置功能

---

## 1. 概述

### 1.1 目标

在现有协议模板编辑器的基础上，新增**无代码配置模式**，用户通过表单向导和可视化配置即可完成协议模板创建，无需直接编写JSON。两种模式并存，可随时切换。

### 1.2 设计原则

- **YAGNI**: 第一版支持全量协议类型，但不实现高级特性（如条件分支、循环）
- **DRY**: 复用现有的JSON模板结构和验证逻辑
- **渐进增强**: 从表单生成的JSON应与手写JSON完全兼容
- **实时反馈**: 左右分屏实时预览，配置即验证

---

## 2. 整体架构

### 2.1 组件结构

```
frontend/pages/protocol_editor.py (扩展现有文件)
├── 模式切换器（顶部）
│   ├── [JSON 编辑] [表单配置] 切换按钮
│   └── 状态：当前模式 + JSON 是否有效
├── JSON 编辑模式（现有实现）
│   └── CodeMirror 编辑器
└── 表单配置模式（新增）
    ├── 左侧：配置表单区（折叠面板）
    │   ├── 面板1：基本信息
    │   ├── 面板2：协议类型选择
    │   ├── 面板3：变量定义
    │   ├── 面板4：步骤配置（动态）
    │   └── 面板5：输出映射
    └── 右侧：实时 JSON 预览
        └── CodeMirror（只读 + 一键复制）

backend/api/protocols.py (扩展现有文件)
└── POST /api/protocols/{protocol_id}/test-step (新增接口)
    └── 单步执行测试，支持 setup/poll/event 三种位置（不支持 manual，manual只能通过设备执行接口）
```

### 2.2 数据流

```
用户填写表单
    ↓
表单状态变化 (Dash State)
    ↓
JSON 生成器 (generate_json_from_form)
    ↓
实时预览更新（右侧面板）
    ↓
保存时提交到后端 /api/protocols
```

### 2.3 关键技术决策

1. **状态同步**: 使用 `dcc.Store` 存储 `form_mode` 和 `template_data`
2. **模式切换**: 双向转换（JSON ↔ 表单值）
3. **实时验证**: 表单变化触发验证回调，更新JSON和错误提示

---

## 3. 协议类型与动态表单

### 3.1 协议类型选择器

四种协议类型，每种对应不同的模板结构：

| 协议类型 | 模板结构 | 默认步骤类型 | 特殊配置项 |
|---------|---------|-------------|-----------|
| **Modbus TCP** | `steps[]` | poll（轮询）+ manual（手动控制） | slave_id, register类型 |
| **Modbus RTU** | `steps[]` | poll（轮询）+ manual（手动控制） | slave_id, register类型 |
| **MQTT** | `setup_steps[]` + `message_handler{}` + `steps[]` | setup（订阅）+ event（消息处理）+ manual（手动控制） | topic, qos |
| **Serial** | `steps[]` | poll（发送→接收）+ manual（手动控制） | 命令格式、超时 |
| **TCP** | `steps[]` | poll（发送→接收）+ manual（手动控制） | 数据格式、超时 |

**关键修复**：MQTT协议使用独立的顶层结构（`setup_steps` + `message_handler`），与轮询类协议的 `steps` 结构分离，符合现有系统契约。

### 3.2 分支模板结构生成

```python
def render_protocol_form(protocol_type: str, form_data: dict) -> html.Div:
    """根据协议类型渲染对应的表单配置"""

    common_fields = [
        render_basic_info_panel(),
        render_variables_panel(),
    ]

    # 根据协议类型渲染不同的步骤配置面板
    if protocol_type in ["modbus_tcp", "modbus_rtu", "serial", "tcp"]:
        # 轮询类协议：生成 steps[]
        steps_panel = render_polling_steps_panel(
            form_data.get("steps", []),
            protocol_type
        )
    elif protocol_type == "mqtt":
        # MQTT协议：生成 setup_steps[] + message_handler{} + steps[]（manual）
        steps_panel = render_mqtt_steps_panel(
            form_data.get("setup_steps", []),
            form_data.get("message_handler", {}),
            form_data.get("steps", [])  # 仅包含 manual 步骤
        )
    else:
        steps_panel = html.Div("不支持的协议类型")

    return html.Div([
        *common_fields,
        steps_panel,
        render_output_panel()
    ])
```

### 3.3 JSON生成器的协议分支逻辑

```python
def generate_json_from_form(form_data: dict, protocol_type: str) -> dict:
    """将表单数据转换为JSON模板（协议分支结构）"""

    template = {
        "name": form_data.get("name"),
        "description": form_data.get("description"),
        "protocol_type": protocol_type,
        "variables": form_data.get("variables", []),
        "output": form_data.get("output", {})
    }

    if protocol_type in ["modbus_tcp", "modbus_rtu", "serial", "tcp"]:
        # 轮询类协议：使用 steps[]
        template["steps"] = form_data.get("steps", [])

    elif protocol_type == "mqtt":
        # MQTT协议：使用独立结构
        template["setup_steps"] = form_data.get("setup_steps", [])
        template["message_handler"] = form_data.get("message_handler", {})
        template["steps"] = [
            s for s in form_data.get("steps", [])
            if s.get("trigger") == "manual"  # MQTT的steps只包含manual控制步骤
        ]

    return template
```

### 3.4 协议类型切换行为

- 切换类型 → 清空步骤配置（不同协议结构不兼容）
- 保留基本信息和变量定义
- 显示确认提示："切换协议类型将清空步骤配置，是否确认？"

---

## 4. 步骤配置与预设模板

### 4.1 步骤配置UI

```
┌─────────────────────────────────────────────────────────┐
│ ⚙️ 步骤配置                           [+ 添加步骤]       │
├─────────────────────────────────────────────────────────┤
│ ┌───────────────────────────────────────────────────┐  │
│ │ 步骤 1: 读取重量               [↑] [↓] [测试] [删除] │  │
│ │ 触发方式: ○轮询 ●手动 ○连接时 ○事件              │  │
│ │ 动作: Modbus 读取输入寄存器 ▼                     │  │
│ │ 参数: slave_id=${slave_id}, address=0, count=2    │  │
│ │ 解析: registers[0] * 65536 + registers[1]         │  │
│ │ [展开详情 ▼]                                      │  │
│ └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 4.2 预设步骤模板库

**Modbus 预设步骤**:

- 读取输入寄存器（poll）
- 读取保持寄存器（poll）
- 写入线圈（manual）
- 写入寄存器（manual）

**MQTT 预设步骤**:

- 订阅主题（setup，放入 `setup_steps[]`）
- 处理JSON消息（event，放入 `message_handler{}`）
- 发布控制命令（manual，放入 `steps[]`）
- 订阅+手动控制完整模板（包含setup/event/manual三种步骤）

**Serial 预设步骤**:

- 发送命令并接收（poll，包含send→delay→receive）

### 4.3 智能参数提示

参数输入时自动提供可用的占位符：

```python
dcc.Dropdown(
    id={"type": "step-param", "field": "slave_id"},
    options=[
        {"label": "1 (固定值)", "value": "1"},
        {"label": "${slave_id} (变量)", "value": "${slave_id}"},
        {"label": "${steps.step1.result} (步骤结果)", "value": "${steps.step1.result}"}
    ]
)
```

### 4.4 实时测试验证（完整方案）

**方案：前端语法验证 + 后端单步执行测试**

采用**两层验证+执行**策略：

**单步测试限制说明**：
- **无上下文执行**: 单步测试默认不提供前置步骤的上下文（`context["steps"] = {}`）
- **依赖注入可选**: 如需测试依赖前置步骤的步骤，可在请求体中注入 `previous_steps`
- **失败即特性**: 如果步骤引用 `${steps.xxx.result}` 但前置步骤未执行，测试会失败（符合预期）

**第一层：前端语法验证（实时，无副作用）**

```python
# frontend/pages/protocol_editor.py (新增)

def validate_step_syntax(step: dict, protocol_type: str) -> dict:
    """前端实时验证步骤语法（不连接设备）"""

    errors = []
    warnings = []

    # 必填字段检查（params 可选）
    required_fields = ["id", "name", "action"]  # 移除 params
    for field in required_fields:
        if field not in step:
            errors.append(f"缺少必填字段: {field}")

    # Action 合法性检查
    valid_actions = get_valid_actions_for_protocol(protocol_type)
    if step.get("action") not in valid_actions:
        errors.append(f"不支持的 action: {step.get('action')}")

    # 占位符语法检查（仅当 params 存在时）
    params = step.get("params", {})
    if params:  # params 可选，只在存在时验证
        for key, value in params.items():
            if isinstance(value, str):
                placeholders = extract_placeholders(value)
                for ph in placeholders:
                    if not is_valid_placeholder(ph):
                        errors.append(f"无效的占位符: {ph}")

    # 解析规则语法检查
    if "parse" in step:
        parse_type = step["parse"].get("type")
        if parse_type == "expression":
            expr = step["parse"].get("expression", "")
            if not validate_expression_syntax(expr):
                errors.append("表达式语法错误")
        elif parse_type == "regex":
            pattern = step["parse"].get("pattern", "")
            if not validate_regex_syntax(pattern):
                errors.append("正则表达式语法错误")

    # 写操作警告
    if is_write_action(step.get("action")):
        if step.get("trigger") != "manual":
            errors.append("写操作必须设置为 trigger=manual")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }

def is_write_action(action: str) -> bool:
    """判断是否为写操作（白名单策略：只列已知的控制类写操作）"""
    control_write_actions = {
        "modbus.write_register",
        "modbus.write_coil",
        "mqtt.publish",
    }
    return action in control_write_actions
```

**第二层：后端单步执行测试（新增接口）**

```python
# backend/api/schemas.py (扩展)

from typing import Any, Literal
from pydantic import Field, field_validator

class StepTestRequest(BaseModel):
    connection_params: dict
    template_variables: dict = Field(default_factory=dict)  # 避免可变默认值
    step_id: str                       # 要测试的步骤ID
    step_context: Literal["setup", "poll", "event"]  # 步骤所在位置（manual不支持，保持项目契约）
    allow_write: bool = False          # 是否允许写操作（默认False）
    test_payload: str = None           # event 类型测试数据（从请求体传入，不污染模板）
    previous_steps: dict = Field(default_factory=dict)  # 可选：注入前置步骤上下文（格式：{step_id: {"result": ...}}）

    @field_validator("previous_steps", mode="before")
    @classmethod
    def validate_previous_steps(cls, v: Any) -> dict:
        """验证 previous_steps 格式：每个 value 必须包含 'result' 键"""
        if not isinstance(v, dict):
            raise ValueError("previous_steps 必须是字典")
        for step_id, step_data in v.items():
            if not isinstance(step_data, dict):
                raise ValueError(f"previous_steps['{step_id}'] 必须是字典")
            if "result" not in step_data:
                raise ValueError(f"previous_steps['{step_id}'] 必须包含 'result' 键")
        return v

# backend/api/protocols.py (扩展现有文件，新增接口)

@router.post("/{protocol_id}/test-step")
async def test_single_step(
    protocol_id: int,
    payload: StepTestRequest
) -> dict[str, Any]:
    """
    单步执行测试（新增接口）

    - 执行指定的单个步骤
    - 支持 setup/poll/event 三种位置（不支持 manual，保持项目契约）
    - 默认拒绝写操作（allow_write=False）
    """
    row = ProtocolTemplate.get_or_none(ProtocolTemplate.id == protocol_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Protocol not found")

    # 查找目标步骤
    step = find_step_in_template(row.template, payload.step_id, payload.step_context)
    if not step:
        raise HTTPException(status_code=404, detail=f"Step not found: {payload.step_id}")

    # 安全检查：拒绝写操作（除非显式允许）
    if not payload.allow_write and is_write_action(step.get("action")):
        return {
            "ok": False,
            "error": "写操作需要显式设置 allow_write=true",
            "action": step.get("action"),
            "safety_warning": "该操作可能修改设备状态"
        }

    driver = build_driver(row.protocol_type, payload.connection_params)
    executor = ProtocolExecutor()

    try:
        connected = await driver.connect()
        if not connected:
            return {"ok": False, "error": "connect failed"}

        # 执行单步（真正单步，可选注入前置上下文）
        result = await execute_single_step(
            executor, row.template, step, payload.step_context,
            driver, payload.template_variables, payload.test_payload,
            payload.previous_steps
        )

        return {
            "ok": True,
            "step_id": payload.step_id,
            "step_result": result.get("step_result"),
            "rendered_output": result.get("rendered_output"),
            "action": step.get("action")
        }

    except ValueError as ve:
        # 参数验证错误（如缺少 test_payload）
        return {"ok": False, "error": str(ve)}
    except Exception as exc:
        # 执行错误
        return {"ok": False, "error": str(exc)}
    finally:
        await driver.disconnect()

async def execute_single_step(
    executor: ProtocolExecutor,
    template: dict,
    step: dict,
    step_context: Literal["setup", "poll", "event"],
    driver,
    variables: dict,
    test_payload: str = None,
    previous_steps: dict = None
) -> dict:
    """
    真正执行单个步骤

    返回统一的字典结构，方便前端解析：
    {"step_result": ..., "rendered_output": {...}}

    上下文说明：
    - 默认无前置上下文（context["steps"] = {}）
    - 可通过 previous_steps 注入依赖的前置步骤结果
    - 如果步骤引用 ${steps.xxx.result} 但未提供，会解析失败
    """

    # 构建上下文：前置步骤 + 变量
    steps_context = previous_steps if previous_steps else {}
    context = {"steps": steps_context, **variables}

    if step_context == "setup":
        # 执行单个 setup 步骤
        raw_result = await executor._execute_step(driver, step, context)
        # 合并顺序：previous_steps 在前，当前步骤结果在后（避免覆盖本次结果）
        merged_steps = {**steps_context, step["id"]: {"result": raw_result}}
        output = executor.render_output(template, {"steps": merged_steps, **variables})
        return {
            "step_result": raw_result,  # 步骤原始返回值
            "rendered_output": output  # 最终映射输出
        }

    elif step_context == "poll":
        # 执行单个 poll 步骤
        raw_result = await executor._execute_step(driver, step, context)
        # 合并顺序：previous_steps 在前，当前步骤结果在后（避免覆盖本次结果）
        merged_steps = {**steps_context, step["id"]: {"result": raw_result}}
        output = executor.render_output(template, {"steps": merged_steps, **variables})
        return {
            "step_result": raw_result,  # 步骤原始返回值
            "rendered_output": output  # 最终映射输出
        }

    elif step_context == "event":
        # 执行 message_handler（需要模拟 payload）
        if not test_payload:
            raise ValueError("event 步骤测试需要提供 test_payload")

        # 构建完整的 event 上下文（与 run_message_handler 内部逻辑一致）
        steps_context = previous_steps if previous_steps else {}
        text_payload = test_payload.decode("utf-8", errors="ignore") if isinstance(test_payload, bytes) else str(test_payload)
        event_context = {
            "payload": text_payload,
            "steps": steps_context,
            **variables,
        }

        # 直接执行 message_handler 步骤（skip_driver=True，因为 event 不需要 driver 操作）
        raw_result = await executor._execute_step(driver, step, event_context, skip_driver=True)

        # 构建完整上下文用于 render_output（与 run_message_handler 一致）
        event_context["message_handler"] = {"result": raw_result}
        output = executor.render_output(template, event_context)

        # 返回统一的字段：
        # - step_result: message_handler 的原始解析结果（与其他场景类型一致）
        # - rendered_output: 模板 output 映射后的最终输出
        return {
            "step_result": raw_result,  # message_handler 解析后的原始值
            "rendered_output": output  # 最终映射输出（如 {"weight": 123.45}）
        }

    else:
        raise ValueError(f"Unknown step context: {step_context}")

def find_step_in_template(template: dict, step_id: str, step_context: Literal["setup", "poll", "event"]) -> dict | None:
    """从模板中查找指定步骤（支持 event，manual 已由模型校验拦截）"""
    if step_context == "setup":
        for step in template.get("setup_steps", []):
            if step.get("id") == step_id:
                return step
    elif step_context == "event":
        handler = template.get("message_handler", {})
        if handler.get("id") == step_id:
            return handler
    elif step_context == "poll":
        # poll: 只匹配 trigger=poll 或未设置（默认poll）
        for step in template.get("steps", []):
            if step.get("id") == step_id:
                trigger = step.get("trigger", "poll")  # 默认为 poll
                if trigger == "poll":
                    return step
    # manual 已由 StepTestRequest 的 Literal 校验拦截，不会进入此分支
    return None

def is_write_action(action: str) -> bool:
    """判断是否为写操作（白名单策略）"""
    control_write_actions = {
        "modbus.write_register",
        "modbus.write_coil",
        "mqtt.publish",
    }
    return action in control_write_actions
```

**前端验证时机**：

1. **实时验证**：用户编辑步骤时，前端立即验证语法并显示错误
2. **保存前验证**：点击保存时，再次验证所有步骤
3. **单步测试**：用户点击"测试步骤"按钮，调用后端单步执行接口

**前端UI示例**：

```
┌─────────────────────────────────────────────────────────┐
│ 步骤 1: 读取重量               [↑] [↓] [✓检查] [▶测试]   │
│ ✅ 语法验证通过                                          │
│ ───────────────────────────────────────────────────────│
│ 触发方式: ○轮询 ●手动 ○连接时 ○事件                      │
│ 动作: Modbus 读取输入寄存器 ▼                            │
│ 参数: slave_id=${slave_id}, address=0, count=2           │
│                                                         │
│ 测试结果: ✅ 执行成功，result=123.45                     │
└─────────────────────────────────────────────────────────┘
```

**方案优势**：

1. **前端实时反馈**: 用户编辑时立即看到语法错误
2. **真正单步执行**: 后端只执行指定的单个步骤，不依赖上下文
3. **覆盖完整**: 支持所有步骤类型（包括 MQTT message_handler 的 event）
4. **安全可控**: 默认拒绝写操作，需要显式确认
5. **独立接口**: 新增 `/test-step` 接口，不影响现有完整测试

**接口对比**：

| 接口 | 用途 | 执行范围 | 是否连接设备 |
|------|------|---------|-------------|
| `POST /api/protocols/{id}/test` | 完整测试 | setup + poll（非MQTT） | ✅ |
| `POST /api/protocols/{id}/test-step` | 单步测试 | 单个步骤（支持setup/poll/event，不支持manual） | ✅ |
| 前端语法验证 | 语法检查 | 无执行 | ❌ |

**说明**：
- 现有 `/test` 接口对 MQTT 协议只执行 setup_steps，不执行 message_handler（event）
- 新增 `/test-step` 接口不支持 manual 步骤，保持项目契约（manual 只能通过设备执行接口）

---

## 5. 可视化解析向导

### 5.1 解析向导流程

```
第1步：选择解析类型 (📊表达式 | 🔍正则 | ✂️子串 | 📦结构体)
    ↓
第2步：输入示例数据 (粘贴实际数据或加载测试数据)
    ↓
第3步：选择提取方式 (智能推荐或手动配置)
    ↓
第4步：预览结果 (显示生成的规则和提取结果)
```

### 5.2 智能解析推荐

```python
def suggest_parse_method(sample_data: str) -> dict:
    """根据示例数据智能推荐解析方法"""

    is_json = sample_data.strip().startswith('{')
    has_numbers = bool(re.search(r'\d+\.?\d*', sample_data))

    if is_json:
        return {
            "method": "regex",
            "pattern": r'"weight"\s*:\s*([-+]?[0-9]*\.?[0-9]+)',
            "reason": "检测到JSON格式"
        }
    elif has_numbers:
        if re.search(r'\d+\.?\d*\s*[a-zA-Z]+', sample_data):
            return {
                "method": "regex",
                "pattern": r'([-+]?[0-9]*\.?[0-9]+)\s*([a-zA-Z]+)',
                "reason": "检测到数字+单位格式"
            }
        else:
            return {
                "method": "expression",
                "expression": "float(payload)",
                "reason": "检测到纯数字"
            }

    return {"method": "substring", "reason": "无法自动识别"}
```

### 5.3 解析模板库

- `extract_json_field`: 提取JSON字段
- `extract_number_with_unit`: 提取数字+单位
- `extract_first_number`: 提取第一个数字
- `modbus_32bit_combine`: Modbus 32位组合
- `modbus_scale_divide`: Modbus 缩放转换

---

## 6. 实时预览与数据同步

### 6.1 分屏布局

- **左侧**: 配置表单区（可滚动，折叠面板）
- **右侧**: 实时JSON预览（固定，只读CodeMirror + 复制按钮）
- **底部**: 验证状态（✅有效 / ⚠️警告 / ❌错误）

### 6.2 数据同步机制

```python
# 表单 → JSON
@app.callback(
    Output("json-preview", "children"),
    Output("json-validation-status", "children"),
    Input({"type": "form-field"}, "value"),
    State("template-data-store", "data")
)
def update_json_preview(form_values, stored_data):
    template_data = merge_form_data(stored_data, form_values)
    json_str = json.dumps(template_data, indent=2, ensure_ascii=False)
    validation = validate_template_structure(template_data)
    return json_str, validation["message"]

# JSON → 表单
@app.callback(
    Output({"type": "form-field"}, "value"),
    Input("json-editor", "value")
)
def update_form_from_json(json_str):
    template_data = json.loads(json_str)
    return extract_form_values(template_data)
```

### 6.3 实时验证（协议分支）

```python
def validate_template_structure(template: dict) -> dict:
    """验证模板结构的完整性（协议分支逻辑）"""
    errors = []
    warnings = []

    # 通用必填字段检查
    required_fields = ["name", "protocol_type", "output"]
    for field in required_fields:
        if field not in template:
            errors.append(f"缺少必填字段: {field}")

    protocol_type = template.get("protocol_type")

    # 协议特定检查（分支验证）
    if protocol_type in ["modbus_tcp", "modbus_rtu", "serial", "tcp"]:
        # 轮询类协议：必须有 steps[]
        if "steps" not in template:
            errors.append(f"{protocol_type}协议必须配置 steps 数组")
        else:
            for i, step in enumerate(template.get("steps", [])):
                if "action" not in step:
                    errors.append(f"步骤{i+1}缺少 action 定义")
                if "trigger" not in step:
                    warnings.append(f"步骤{i+1}未指定 trigger，默认为 poll")

    elif protocol_type == "mqtt":
        # MQTT协议：必须有 setup_steps[] 和 message_handler{}
        if "setup_steps" not in template or not template["setup_steps"]:
            errors.append("MQTT协议必须配置 setup_steps 数组")
        if "message_handler" not in template:
            errors.append("MQTT协议必须配置 message_handler 对象")
        else:
            handler = template["message_handler"]
            if "action" not in handler:
                errors.append("message_handler 缺少 action 定义")
            if "trigger" not in handler:
                warnings.append("message_handler 未指定 trigger，应为 event")

        # MQTT 的 steps[] 仅用于 manual 控制步骤（可选）
        if "steps" in template:
            for i, step in enumerate(template["steps"]):
                if step.get("trigger") != "manual":
                    warnings.append(f"MQTT协议的steps[{i}]应为manual触发，当前为{step.get('trigger')}")
                if is_write_action(step.get("action")) and step.get("trigger") != "manual":
                    errors.append(f"写操作{step.get('action')}必须设置为manual触发")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }
```

---

## 7. 实现文件清单

### 7.1 前端文件

| 文件路径 | 修改类型 | 说明 |
|---------|---------|------|
| `app.py` | 重构 | 将协议编辑相关回调迁移到 `protocol_editor.py`（工作量较大，当前 app.py 中有约380+行协议相关逻辑） |
| `frontend/pages/protocol_editor.py` | 扩展 | 新增表单配置模式UI和所有回调逻辑（当前只有布局，回调在 app.py） |
| `frontend/components/protocol_step_editor.py` | 扩展 | 新增预设步骤模板和智能提示 |
| `assets/app.css` | 扩展 | 新增分屏布局和折叠面板样式 |

**代码组织原则**：遵循现有项目模式，页面级组件的回调逻辑放在对应的 `pages/*.py` 文件中，避免 `app.py` 和 `pages/` 的分裂维护。

**迁移复杂度说明**：
- 当前 `app.py` 中协议模板相关回调集中在 940-1164 行区域（约220行，包括 refresh_protocols、load_protocol_preset、create_protocol、load_protocol_for_edit、update_or_delete_protocol 等）
- `protocol_editor.py` 当前只有布局定义，没有回调逻辑
- 迁移需要仔细梳理回调依赖关系，避免破坏现有功能
- 建议分阶段迁移：先实现新功能（新回调写在 `protocol_editor.py`），再逐步迁移旧回调

### 7.2 后端文件

| 文件路径 | 修改类型 | 说明 |
|---------|---------|------|
| `backend/api/schemas.py` | 扩展 | 新增 `StepTestRequest` 模型 |
| `backend/api/protocols.py` | 扩展 | 新增 `/test-step` 接口，实现真正的单步执行测试 |
| `backend/services/protocol_executor.py` | 扩展 | （可选）新增公开方法 `execute_one_step()` 封装 `_execute_step()`，避免直接调用私有方法 |

### 7.3 实现注意事项

**依赖私有方法的改进建议**：
- 当前设计依赖 `ProtocolExecutor._execute_step()`（私有方法）
- 建议在实施时新增公开方法 `execute_one_step(driver, step, context, skip_driver=False)` 封装私有方法
- 这样可以降低后续重构的耦合风险，保持 API 稳定性

**代码组织**：
- 如果暂不添加公开方法，可在实现文档中标注"依赖私有方法，需注意重构风险"
- 优先实现新功能，再考虑重构 Executor 的公开接口

### 7.4 新增工具函数

```python
# frontend/pages/protocol_editor.py

# JSON 生成器（协议分支）
def generate_json_from_form(form_data: dict, protocol_type: str) -> dict:
    """将表单数据转换为JSON模板（根据协议类型分支）"""

# 表单数据提取器
def extract_form_values(template: dict) -> dict:
    """从JSON模板提取表单值"""

# 协议特定渲染器
def render_polling_steps_panel(steps: list, protocol_type: str) -> html.Div:
    """渲染轮询类协议步骤面板（Modbus/Serial/TCP）"""

def render_mqtt_steps_panel(setup_steps: list, message_handler: dict, manual_steps: list) -> html.Div:
    """渲染MQTT协议步骤面板（setup + message_handler + manual）"""

# 验证函数
def validate_template_structure(template: dict) -> dict:
    """验证模板结构的完整性（协议分支逻辑）"""

def validate_step_syntax(step: dict, protocol_type: str) -> dict:
    """前端实时验证步骤语法（不连接设备）"""

def is_write_action(action: str) -> bool:
    """判断是否为控制类写操作（白名单策略）"""

# 解析辅助函数
def suggest_parse_method(sample_data: str) -> dict:
    """根据示例数据智能推荐解析方法"""
```

---

## 8. 验收标准

### 8.1 功能验收

- [ ] 可以在JSON编辑和表单配置模式间切换
- [ ] 表单配置时右侧实时显示生成的JSON
- [ ] 选择协议类型后动态显示对应的配置项
- [ ] 可以从预设步骤模板添加步骤
- [ ] 参数输入时显示变量和步骤结果占位符
- [ ] **可以测试单个步骤**（调用 `/test-step` 接口，真正执行单个步骤）
- [ ] 解析向导可以根据示例数据生成解析规则
- [ ] 保存时验证JSON结构并显示错误/警告
- [ ] 手动编辑JSON后表单自动更新
- [ ] 前端语法验证实时检查步骤（params 可选）

### 8.2 兼容性验收

- [ ] 表单生成的JSON与手写JSON完全兼容
- [ ] 现有JSON模板可以加载到表单模式
- [ ] 四种协议类型（Modbus TCP/RTU、MQTT、Serial、TCP）全部支持
- [ ] 现有的协议模板导入/导出功能不受影响

### 8.3 安全性验收

- [ ] 前端语法验证能够检测写操作未设置为 `trigger=manual`
- [ ] 前端验证对**控制类写操作**强制要求 `trigger=manual`，否则阻止保存
- [ ] 调用手动执行API时，后端强制校验 `trigger == "manual"`，否则返回403（已有逻辑）
- [ ] `/test-step` 接口默认拒绝写操作（`allow_write=False`）
- [ ] 完整测试接口（`/api/protocols/{id}/test`）正常工作，无修改

**写操作定义（白名单策略）**：

- ✅ **控制类写操作**（必须 `trigger=manual`）：
  - `modbus.write_register`
  - `modbus.write_coil`
  - `mqtt.publish`

- ❌ **数据传输操作**（允许 `trigger=poll`）：
  - `serial.send`（串口轮询发送命令读取数据）
  - `tcp.send`（TCP轮询发送请求读取数据）

**白名单策略说明**：
- 只明确列出已知的控制类写操作
- 后续新增写操作时，需要评估并加入白名单
- 避免黑名单策略的遗漏风险

### 8.4 功能回归验收

- [ ] MQTT模板支持手动控制步骤（去皮/清零等），这些步骤保存在 `steps[]` 中且 `trigger=manual`
- [ ] 现有手动控制页面能正确提取MQTT模板的manual步骤
- [ ] 轮询类协议（Modbus/Serial/TCP）的manual步骤正常工作
- [ ] Serial/TCP协议的 `serial.send`/`tcp.send` 在 poll 模式下正常工作（不被误判为写操作）
- [ ] 切换协议类型时不影响已保存的模板
- [ ] message_handler 的 params 为可选，与现有执行器保持一致
- [ ] `/test-step` 接口能够测试 MQTT message_handler（event 类型）
- [ ] `/test-step` 接口不支持 manual 步骤测试（保持项目契约）
- [ ] `previous_steps` 参数格式正确：`{step_id: {"result": ...}}`，合并时本次结果优先

---

## 9. previous_steps 数据结构说明

### 9.1 数据格式

`previous_steps` 参数用于在单步测试时注入前置步骤的执行结果，格式如下：

```python
previous_steps = {
    "step1": {"result": 123.45},
    "step2": {"result": "OK"}
}
```

### 9.2 合并顺序

在构建执行上下文时，合并顺序为：
```python
merged_steps = {**previous_steps, step["id"]: {"result": raw_result}}
```

确保**本次步骤结果优先**，避免 `previous_steps` 中同 key 覆盖当前结果。

### 9.3 使用场景

- 测试依赖前置步骤结果的步骤（如 `${steps.step1.result}`）
- 无需执行完整流程，快速验证单步逻辑
- 模拟复杂依赖关系，定位问题步骤

### 9.4 验证规则

- `previous_steps` 为可选参数，默认为空字典 `{}`
- 格式验证：每个 value 必须是包含 `"result"` 键的字典
- 类型验证：`result` 值类型应符合步骤预期（数字/字符串/字典等）

---

## 10. 后续扩展方向

1. **协议模板市场**: 预置更多设备厂商的模板库
2. **AI智能推荐**: 根据设备型号自动推荐协议配置
3. **批量测试**: 一次性测试所有步骤并报告结果
4. **版本控制**: 协议模板的版本管理和变更历史
5. **协作编辑**: 多用户同时编辑协议模板

---

**文档版本**: 1.9
**最后更新**: 2026-03-01（第十五轮修订：补充私有方法依赖说明、精确定位app.py协议回调区域为940-1164行）
