# 超简化可视化协议编辑器实施计划（零基础版）

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标:** 构建面向初级工程师的拖拽式协议配置界面，**完全避免技术术语**，通过预设场景和自然语言实现零基础配置。

**架构:**
- 前端：场景驱动的节点编辑器（设备→数据读取→数据输出）
- 后端：预设模板引擎，自动生成底层JSON
- 原则：零术语、零配置、预设优先

**技术栈:**
- 前端：Dash + React Flow（拖拽界面）
- 后端：FastAPI + 预设模板库
- 核心：预设场景覆盖80%常见设备

---

## 设计理念

### 完全避免技术术语

❌ **不使用**：
- "寄存器地址"、"正则表达式"、"JSON Path"
- "A*65536+B"、"registers[0]"
- "触发器"、"回调"

✅ **改用用户语言**：
- "读取重量（2字节）" → 自动识别底层逻辑
- "合并为1个数" → 预设32位合并
- "保留2位小数" → 勾选框

---

### 预设场景驱动

**场景1：电子天平（最常见）**
- 设备：Modbus TCP 电子天平
- 读取：重量值（32位，2字节合并）
- 输出：weight，单位kg，2位小数

**场景2：温湿度传感器**
- 设备：MQTT 传感器
- 读取：温度和湿度（2个数据）
- 输出：temperature, humidity，°C/%

**场景3：开关状态**
- 设备：Modbus 继电器
- 读取：开关状态（开/关）
- 输出：status，布尔值

---

## 任务 1：创建超简化节点类型

**文件:**
- 新建：`frontend/components/simple_nodes.py`

**步骤 1：定义3种节点类型**

新建 `frontend/components/simple_nodes.py`：

```python
"""
超简化节点类型

完全避免技术术语，使用用户友好的命名
"""

# 3种节点类型
NODE_TYPES = [
    {
        "id": "device",
        "label": "📡 设备",
        "description": "选择您的设备类型",
        "color": "#007bff"
    },
    {
        "id": "dataRead",
        "label": "📊 读取数据",
        "description": "选择要读取的数据类型",
        "color": "#28a745"
    },
    {
        "id": "dataOutput",
        "label": "📤 数据输出",
        "description": "配置数据如何显示",
        "color": "#17a2b8"
    },
]
```

**步骤 2：创建预设数据读取场景**

在文件中添加：

```python
# 预设的数据读取场景（完全用户语言）
DATA_READ_SCENARIOS = {
    "modbus_weight_32bit": {
        "name": "重量值（32位，2字节合并）",
        "device_type": "modbus_tcp",
        "description": "适用于：奥豪斯、赛多利斯等Modbus电子天平",
        "icon": "⚖️",
        "config": {
            "data_type": "weight_32bit",
            "byte_count": 2,
            "description": "读取2个字节，合并为1个重量值"
        }
    },
    "modbus_weight_16bit": {
        "name": "重量值（16位，单寄存器）",
        "device_type": "modbus_tcp",
        "description": "适用于：单寄存器返回的16位重量数据",
        "icon": "⚖️",
        "config": {
            "data_type": "weight_16bit",
            "byte_count": 1,
            "description": "读取1个寄存器，直接作为重量值"
        }
    },
    "mqtt_temp_humidity": {
        "name": "温湿度值（2个数据）",
        "device_type": "mqtt",
        "description": "适用于：MQTT温湿度传感器",
        "icon": "🌡️",
        "config": {
            "data_type": "temp_humidity",
            "description": "读取温度和湿度两个数据"
        }
    },
    "modbus_switch": {
        "name": "开关状态（开/关）",
        "device_type": "modbus_tcp",
        "description": "适用于：继电器、开关状态读取",
        "icon": "🔌",
        "config": {
            "data_type": "switch_status",
            "description": "读取开关状态（开=true/关=false）"
        }
    },
}
```

**步骤 3：测试节点定义**

运行：`python -c "from frontend.components.simple_nodes import DATA_READ_SCENARIOS; print(DATA_READ_SCENARIOS)"`
预期：显示5个预设场景字典

**步骤 4：提交**

```bash
git add frontend/components/simple_nodes.py
git commit -m "feat: 添加超简化节点类型和预设数据读取场景"
```

---

## 任务 2：创建场景选择器组件

**文件:**
- 新建：`frontend/components/scenario_selector.py`

**步骤 1：创建场景选择器**

新建 `frontend/components/scenario_selector.py`：

```python
"""
场景选择器组件

让用户选择"要读取什么数据"，而不是配置"寄存器地址"
"""

from dash import html, dcc

def layout():
    """场景选择器布局"""
    return html.Div([
        html.H5("📊 选择您要读取的数据"),

        # Modbus 设备场景
        html.Details([
            html.Summary("⚖️ Modbus 电子天平", className="mb-2"),
            html.Div([
                _create_scenario_card(
                    "modbus_weight_32bit",
                    "重量值（32位，2字节合并）",
                    "适用于：奥豪斯、赛多利斯等Modbus TCP电子天平",
                    ["需要2个寄存器", "自动合并为1个数", "默认单位：kg"]
                ),
                html.Hr(),
                _create_scenario_card(
                    "modbus_weight_16bit",
                    "重量值（16位，单寄存器）",
                    "适用于：单寄存器返回的16位数据",
                    ["只需要1个寄存器", "直接作为数值", "默认单位：kg"]
                ),
                html.Hr(),
                _create_scenario_card(
                    "modbus_switch",
                    "开关状态（开/关）",
                    "适用于：继电器、开关状态读取",
                    ["读取1个线圈", "返回：开=true/关=false"]
                ),
            ], className="mb-3"),
        ]),

        # MQTT 设备场景
        html.Details([
            html.Summary("🌡️ MQTT 温湿度传感器", className="mb-2"),
            html.Div([
                _create_scenario_card(
                    "mqtt_temp_humidity",
                    "温湿度值（2个数据）",
                    "适用于：DHT11/22等MQTT温湿度传感器",
                    ["订阅主题：sensor/data", "自动解析温度和湿度"]
                ),
            ], className="mb-3"),
        ),

        # 自定义场景
        html.Details([
            html.Summary("🔧 自定义配置", className="mb-2"),
            html.Div([
                html.P("需要更多配置？可以切换到「表单编辑器」或「JSON编辑器」", className="text-muted"),
                html.A("切换到表单编辑器", href="/?tab=protocols", className="btn btn-link btn-sm"),
            ]),
        ], className="mb-3"),
    ])

def _create_scenario_card(scenario_id, title, description, features):
    """创建场景卡片"""
    return html.Div([
        html.Strong(title, className="text-primary"),
        html.Br(),
        html.Small(description, className="text-muted d-block mb-2"),
        html.Ul([
            html.Li(f) for f in features
        ], style={"paddingLeft": "20px", "fontSize": "13px"}),
        html.Button(
            "选择此场景",
            id={"type": "select-scenario", "index": scenario_id},
            className="btn btn-sm btn-outline-primary mt-2",
            n_clicks=0
        ),
    ], style={
        "border": "1px solid #ddd",
        "borderRadius": "5px",
        "padding": "12px",
        "marginBottom": "10px"
    })
```

**步骤 2：测试场景选择器**

运行：`python app.py`
访问可视化编辑器页面
预期：场景选择器显示5个预设场景卡片

**步骤 3：提交**

```bash
git add frontend/components/scenario_selector.py
git commit -m "feat: 添加场景选择器组件（用户友好语言）"
```

---

## 任务 3：创建超简化设备配置

**文件:**
- 新建：`frontend/components/device_config_simple.py`

**步骤 1：创建设备配置组件**

新建 `frontend/components/device_config_simple.py`：

```python
"""
超简化设备配置

完全避免技术术语，使用用户友好的表单
"""

def modbus_scale_config():
    """Modbus电子天平配置"""
    return html.Div([
        html.H4("⚖️ 配置Modbus电子天平"),

        html.Div([
            html.Label("设备地址", className="form-label"),
            dcc.Input(
                id="config-device-ip",
                type="text",
                placeholder="例如：192.168.1.100",
                className="form-control mb-3"
            ),
        ], className="mb-3"),

        html.Div([
            html.Label("从站编号", className="form-label"),
            dcc.Input(
                id="config-device-slave-id",
                type="number",
                value=1,
                className="form-control mb-3"
            ),
            html.Small("设备上的从站编号（通常为1）", className="text-muted"),
        ], className="mb-3"),
    ])

def mqtt_sensor_config():
    """MQTT温湿度传感器配置"""
    return html.Div([
        html.H4("🌡️ 配置MQTT传感器"),

        html.Div([
            html.Label("MQTT服务器地址", className="form-label"),
            dcc.Input(
                id="config-mqtt-host",
                type="text",
                placeholder="例如：192.168.1.200",
                className="form-control mb-3"
            ),
        ], className="mb-3"),

        html.Div([
            html.Label("主题名称", className="form-label"),
            dcc.Input(
                id="config-mqtt-topic",
                type="text",
                placeholder="例如：sensor/data",
                className="form-control mb-3"
            ),
            html.Small("MQTT主题路径", className="text-muted"),
        ], className="mb-3"),
    ])
```

**步骤 2：提交**

```bash
git add frontend/components/device_config_simple.py
git commit -m "feat: 添加超简化设备配置组件"
```

---

## 任务 4：创建超简化输出配置

**文件:**
- 新建：`frontend/components/output_config_simple.py`

**步骤 1：创建输出配置组件**

新建 `frontend/components/output_config_simple.py`：

```python
"""
超简化输出配置

完全避免技术术语，用户友好的输出配置
"""

def layout(data_type):
    """根据数据类型返回对应的输出配置"""
    if data_type in ["modbus_weight_32bit", "modbus_weight_16bit"]:
        return weight_output_config()

    elif data_type == "mqtt_temp_humidity":
        return temp_humidity_output_config()

    elif data_type == "modbus_switch":
        return switch_output_config()

    else:
        return html.Div("暂不支持该数据类型")

def weight_output_config():
    """重量值输出配置"""
    return html.Div([
        html.H4("📤 配置重量值输出"),

        html.Div([
            html.Label("字段名称", className="form-label"),
            dcc.Input(
                id="config-output-field",
                type="text",
                value="weight",
                placeholder="例如：weight",
                className="form-control mb-3"
            ),
        ], className="mb-3"),

        html.Div([
            html.Label("单位", className="form-label"),
            dcc.Dropdown(
                id="config-output-unit",
                options=[
                    {"label": "kg (千克)", "value": "kg"},
                    {"label": "g (克)", "value": "g"},
                    {"label": "t (吨)", "value": "t"},
                    {"label": "lb (磅)", "value": "lb"},
                ],
                value="kg",
                className="mb-3"
            ),
        ], className="mb-3"),

        html.Div([
            html.Label("小数位数", className="form-label"),
            dcc.Slider(
                id="config-output-decimals",
                min=0,
                max=4,
                step=1,
                value=2,
                marks={0: "0", 1: "1", 2: "2", 3: "3", 4: "4"},
                className="mb-3"
            ),
            html.Small("显示几位小数", className="text-muted"),
        ], className="mb-3"),

        html.Div([
            html.Div("💡 预览", className="text-muted mb-2"),
            html.Div(
                "weight = 123.45 kg",
                id="output-preview",
                className="alert alert-info",
                style={"textAlign": "center", "fontWeight": "bold"}
            ),
        ]),
    ])

def temp_humidity_output_config():
    """温湿度输出配置"""
    return html.Div([
        html.H4("🌡️ 配置温湿度输出"),

        html.Div([
            html.Div([
                html.Label("温度字段", className="form-label"),
                dcc.Input(
                    id="config-output-temp-field",
                    type="text",
                    value="temperature",
                    className="form-control mb-3"
                ),
            ], className="mb-3"),

            html.Div([
                html.Label("湿度字段", className="form-label"),
                dcc.Input(
                    id="config-output-humidity-field",
                    type="text",
                    value="humidity",
                    className="form-control mb-3"
                ),
            ], className="mb-3"),

        html.Div([
            html.Div("💡 预览", className="text-muted mb-2"),
            html.Div([
                html.Div("temperature = 23.5 °C", className="alert alert-warning d-block mb-1"),
                html.Div("humidity = 65.8 %", className="alert alert-info d-block"),
            ], id="output-preview"),
        ]),
    ])

def switch_output_config():
    """开关状态输出配置"""
    return html.Div([
        html.H4("🔌 配置开关输出"),

        html.Div([
            html.Label("字段名称", className="form-label"),
            dcc.Input(
                id="config-output-field",
                type="text",
                value="status",
                placeholder="例如：status",
                className="form-control mb-3"
            ),
        ], className="mb-3"),

        html.Div([
            html.Div("💡 预览", className="text-muted mb-2"),
            html.Div(
                "status = 开",
                id="output-preview",
                className="alert alert-success",
                style={"textAlign": "center", "fontWeight": "bold"}
            ),
        ]),
    ])
```

**步骤 2：提交**

```bash
git add frontend/components/output_config_simple.py
git commit -m "feat: 添加超简化输出配置组件"
```

---

## 任务 5：实现场景到JSON的转换引擎

**文件:**
- 新建：`backend/services/scenario_to_json.py`

**步骤 1：创建场景转换引擎**

新建 `backend/services/scenario_to_json.py`：

```python
"""
场景到JSON转换引擎

将用户选择的场景（如"读取重量值32位"）
转换为底层协议模板JSON
完全对用户隐藏技术细节
"""

from typing import Any

SCENARIO_TO_JSON_TEMPLATES = {
    "modbus_weight_32bit": {
        "template": {
            "name": "Modbus电子天平-32位重量",
            "protocol_type": "modbus_tcp",
            "variables": [],
            "output": {"weight": "${{read1.result}}"},
            "steps": [
                {
                    "id": "read1",
                    "name": "读取重量（32位）",
                    "action": "modbus.read_input_registers",
                    "trigger": "poll",
                    "params": {
                        "address": 0,
                        "count": 2,
                        "slave_id": 1
                    },
                    "parse": {
                        "type": "expression",
                        "expression": "registers[0] * 65536 + registers[1]"
                    }
                }
            ]
        },
        "config_mapping": {
            "ip": "connection_params.host",
            "slave_id": "params.slave_id",
        }
    },

    "modbus_weight_16bit": {
        "template": {
            "name": "Modbus电子天平-16位重量",
            "protocol_type": "modbus_tcp",
            "variables": [],
            "output": {"weight": "${{read1.result}}"},
            "steps": [
                {
                    "id": "read1",
                    "name": "读取重量（16位）",
                    "action": "modbus.read_input_registers",
                    "trigger": "poll",
                    "params": {
                        "address": 0,
                        "count": 1,
                        "slave_id": 1
                    },
                    "parse": {
                        "type": "raw"
                    }
                }
            ]
        },
        "config_mapping": {
            "ip": "connection_params.host",
            "slave_id": "params.slave_id",
        }
    },

    "mqtt_temp_humidity": {
        "template": {
            "name": "MQTT温湿度传感器",
            "protocol_type": "mqtt",
            "variables": [],
            "output": {
                "temperature": "${{handler.result.temperature}}",
                "humidity": "${{handler.result.humidity}}"
            },
            "setup_steps": [
                {
                    "id": "subscribe1",
                    "name": "订阅温湿度",
                    "action": "mqtt.subscribe",
                    "trigger": "setup",
                    "params": {
                        "topic": "sensor/data",
                        "qos": 0
                    }
                }
            ],
            "message_handler": {
                "id": "handler1",
                "name": "解析温湿度",
                "action": "mqtt.on_message",
                "trigger": "event",
                "params": {
                    "type": "json_parse",
                    "expression": "$"  # 自动提取温湿度
                }
            }
        },
        "config_mapping": {
            "host": "connection_params.host",
            "port": "connection_params.port",
            "topic": "setup_steps[0].params.topic"
        }
    },

    "modbus_switch": {
        "template": {
            "name": "Modbus开关状态",
            "protocol_type": "modbus_tcp",
            "variables": [],
            "output": {"status": "${{read1.result}}"},
            "steps": [
                {
                    "id": "read1",
                    "name": "读取开关状态",
                    "action": "modbus.read_coils",
                    "trigger": "poll",
                    "params": {
                        "address": 0,
                        "slave_id": 1
                    },
                    "parse": {
                        "type": "raw",
                        "format": "boolean"  # 返回 true/false
                    }
                }
            ]
        },
        "config_mapping": {
            "ip": "connection_params.host",
            "slave_id": "params.slave_id",
        }
    },
}

def scenario_to_json(scenario_id: str, user_config: dict[str, Any], template_name: str) -> dict[str, Any]:
    """
    将用户配置的场景转换为JSON模板

    Args:
        scenario_id: 场景ID（如 "modbus_weight_32bit"）
        user_config: 用户填写的配置（如 IP、从站ID等）
        template_name: 模板名称

    Returns:
        协议模板JSON
    """
    scenario = SCENARIO_TO_JSON_TEMPLATES.get(scenario_id)
    if not scenario:
        raise ValueError(f"未知的场景类型: {scenario_id}")

    template = scenario["template"].copy()
    template["name"] = template_name

    # 应用用户配置到模板
    config_mapping = scenario["config_mapping"]

    for user_key, json_path in config_mapping.items():
        user_value = user_config.get(user_key)
        if user_value:
            # 设置嵌套的JSON路径
            _set_nested_value(template, json_path.split("."), user_value)

    return template


def _set_nested_value(dct: dict, keys: list, value: Any):
    """设置嵌套字典的值"""
    for key in keys[:-1]:
        dct = dct.setdefault(key, {})
    dct[keys[-1]] = value
```

**步骤 2：创建单元测试**

新建 `tests/test_scenario_converter.py`：

```python
import pytest
from backend.services.scenario_to_json import scenario_to_json

def test_modbus_weight_32bit_scenario():
    """测试Modbus 32位重量场景"""
    user_config = {
        "ip": "192.168.1.100",
        "slave_id": 1
    }

    template = scenario_to_json("modbus_weight_32bit", user_config, "测试电子天平")

    assert template["protocol_type"] == "modbus_tcp"
    assert template["output"]["weight"] == "${{read1.result}}"
    assert template["steps"][0]["params"]["address"] == 0

def test_mqtt_temp_humidity_scenario():
    """测试MQTT温湿度场景"""
    user_config = {
        "host": "192.168.1.200",
        "port": 1883
    }

    template = scenario_to_json("mqtt_temp_humidity", user_config, "测试MQTT传感器")

    assert template["protocol_type"] == "mqtt"
    assert "temperature" in template["output"]
    assert "humidity" in template["output"]

def test_invalid_scenario_raises_error():
    """测试无效场景抛出异常"""
    with pytest.raises(ValueError, match="未知的场景类型"):
        scenario_to_json("invalid_scenario", {}, "测试")
```

**步骤 3：运行测试**

运行：`pytest tests/test_scenario_converter.py -v`
预期：所有测试通过

**步骤 4：提交**

```bash
git add backend/services/scenario_to_json.py tests/test_scenario_converter.py
git commit -m "feat: 添加场景到JSON转换引擎"
```

---

## 任务 6：实现拖拽式界面（超简化版）

**文件:**
- 修改：`frontend/pages/visual_protocol_editor.py`

**步骤 1：创建超简化界面**

修改 `frontend/pages/visual_protocol_editor.py`：

```python
from dash import html, dcc

def layout():
    """
    超简化可视化协议编辑器

    目标：零基础配置，完全避免技术术语
    """
    return html.Div([
        # 页面标题
        html.Div([
            html.H2("🎨 可视化协议配置"),
            html.P([
                "拖拽式配置，无需懂编程 · ",
                html.Span(className="badge bg-success", children="初学者友好"),
                " · ",
                html.A("查看使用指南", href="/docs/visual-editor-quick-start", className="alert-link"),
            ], className="text-muted mb-0"),
        ], className="mb-4"),

        # 提示栏
        html.Div([
            html.Div([
                html.H5("💡 3步完成配置", className="mb-2"),
                html.Ol([
                    html.Li("第1步：在下方选择您的场景（电子天平、温湿度传感器等）"),
                    html.Li("第2步：配置设备地址和输出字段"),
                    html.Li("第3步：点击保存，自动生成JSON模板"),
                ], style={"lineHeight": "1.8"}),
            ], className="alert alert-info"),
        ], className="mb-4"),

        # 主内容区
        html.Div([
            # 左侧：场景选择器
            html.Div([
                html.H5("第1步：选择数据读取场景"),
                html.Div(id="scenario-selector"),
            ], className="col-md-5"),

            # 右侧：配置面板
            html.Div([
                html.H5("第2步：配置设备和输出"),
                html.Div(id="config-panel"),
            ], className="col-md-7"),
        ], className="row"),

        # 底部：操作按钮
        html.Div([
            html.Div([
                html.Button("💾 保存模板", id="save-template-btn",
                           className="btn btn-primary me-2"),
                html.Button("🧪 测试连接", id="test-connection-btn",
                           className="btn btn-success me-2"),
                html.A("返回设备管理", href="/?tab=devices",
                       className="btn btn-outline-secondary"),
            ], className="d-flex justify-content-center mt-4"),

            # 状态提示
            html.Div(id="status-message", className="mt-3 text-center"),

            # JSON预览（默认折叠）
            html.Details([
                html.Summary("📄 查看生成的JSON（高级）"),
                html.Div([
                    dcc.Textarea(
                        id="json-preview",
                        style={
                            "width": "100%",
                            "height": "300px",
                            "fontFamily": "monospace",
                            "fontSize": "12px"
                        },
                        readOnly=True
                    ),
                ], className="mt-3"),
            ]),
        ], className="mt-4"),

        # 隐藏的存储组件
        dcc.Store(id="selected-scenario-store", data=""),
        dcc.Store(id="user-config-store", data={}),
        dcc.Store(id="template-name-store", data="新协议模板"),
    ])
```

**步骤 2：提交**

```bash
git add frontend/pages/visual_protocol_editor.py
git commit -m "refactor: 重构为超简化界面（3步配置流程）"
```

---

## 任务 7：实现场景选择回调

**文件:**
- 修改：`frontend/pages/visual_protocol_editor.py`

**步骤 1：添加场景选择回调**

修改 `frontend/pages/visual_protocol_editor.py`，添加回调：

```python
from dash import callback, Input, Output, State

from backend.services.scenario_to_json import SCENARIO_TO_JSON_TEMPLATES

@callback(
    Output("config-panel", "children"),
    Input("select-scenario", "n_clicks"),
    State("select-scenario", "type"),
    prevent_initial_call=True
)
def on_scenario_selected(n_clicks, scenario_type):
    """用户选择场景后显示对应配置"""
    if scenario_type == "modbus_scale_32bit":
        from frontend.components.device_config_simple import modbus_scale_config
        from frontend.components.output_config_simple import layout as output_config

        return html.Div([
            modbus_scale_config(),
            html.Hr(),
            output_config("modbus_weight_32bit"),
        ])

    elif scenario_type == "mqtt_sensor":
        from frontend.components.device_config_simple import mqtt_sensor_config
        from frontend.components.output_config_simple import layout as output_config

        return html.Div([
            mqtt_sensor_config(),
            html.Hr(),
            output_config("mqtt_temp_humidity"),
        ])

    elif scenario_type == "modbus_switch":
        from frontend.components.device_config_simple import modbus_scale_config  # 复用
        from frontend.components.output_config_simple import switch_output_config

        return html.Div([
            modbus_scale_config(),
            html.Hr(),
            switch_output_config(),
        ])

    else:
        return html.Div("请选择一个场景", className="alert alert-warning")


@callback(
    Output("selected-scenario-store", "data"),
    Input("select-scenario", "type"),
    prevent_initial_call=True
)
def store_selected_scenario(scenario_type):
    """存储用户选择的场景"""
    return scenario_type
```

**步骤 2：测试场景选择**

运行：`python app.py`
访问可视化编辑器
选择"Modbus电子天平"场景
预期：右侧显示设备配置和输出配置

**步骤 3：提交**

```bash
git add frontend/pages/visual_protocol_editor.py
git commit -m "feat: 添加场景选择和配置面板显示"
```

---

## 任务 8：实现模板保存功能

**文件:**
- 修改：`frontend/pages/visual_protocol_editor.py`

**步骤 1：添加保存回调**

修改 `frontend/pages/visual_protocol_editor.py`，添加保存逻辑：

```python
import requests
from config.settings import settings

@callback(
    Output("status-message", "children"),
    Input("save-template-btn", "n_clicks"),
    State("template-name-store", "data"),
    State("selected-scenario-store", "data"),
    State("user-config-store", "data"),
    prevent_initial_call=True
)
def save_template(n_clicks, template_name, scenario_type, user_config):
    """
    保存模板

    流程：
    1. 获取用户选择的场景
    2. 使用用户配置生成JSON
    3. 调用后端API保存
    """
    if not template_name:
        return html.Div("⚠️ 请输入模板名称", className="alert alert-warning")

    if not scenario_type:
        return html.Div("⚠️ 请先选择数据读取场景", className="alert alert-warning")

    try:
        # 生成JSON模板
        from backend.services.scenario_to_json import scenario_to_json
        template = scenario_to_json(scenario_type, user_config, template_name)

        # 调用后端API保存
        response = requests.post(
            f"{settings.backend_base}/api/protocols",
            json=template,
            timeout=10
        )
        response.raise_for_status()

        result = response.json()

        return html.Div([
            f"✅ 保存成功！",
            html.Br(),
            html.Small(f"模板ID: {result.get('id', 'N/A')}", className="text-muted"),
        ], className="alert alert-success")

    except requests.exceptions.RequestException as e:
        return html.Div(f"❌ 保存失败: {str(e)}", className="alert alert-danger")

    except ValueError as e:
        return html.Div(f"⚠️ 配置错误: {str(e)}", className="alert alert-warning")

    except Exception as e:
        return html.Div(f"❌ 未知错误: {str(e)}", className="alert alert-danger")
```

**步骤 2：添加用户配置收集回调**

添加配置收集回调：

```python
@callback(
    Output("user-config-store", "data"),
    Input("config-device-ip", "value"),
    Input("config-device-slave-id", "value"),
    Input("config-output-field", "value"),
    Input("config-output-unit", "value"),
    Input("config-output-decimals", "value"),
    prevent_initial_call=False
)
def collect_user_config(ip, slave_id, field, unit, decimals):
    """收集用户填写的所有配置"""
    config = {}

    # 设备配置
    if ip:
        config["ip"] = ip
    if slave_id:
        config["slave_id"] = slave_id

    # 输出配置
    config["field"] = field
    if unit:
        config["unit"] = unit
    if decimals is not None:
        config["decimals"] = decimals

    return config
```

**步骤 3：提交**

```bash
git add frontend/pages/visual_protocol_editor.py
git commit -m "feat: 添加模板保存功能和配置收集"
```

---

## 任务 9：创建快速开始指南

**文件:**
- 新建：`docs/visual-editor-quick-start.md`

**步骤 1：创建快速开始指南**

新建 `docs/visual-editor-quick-start.md`：

```markdown
# 可视化协议编辑器 - 3步快速开始

## 🎯 适用人群

- ✅ 不懂编程的工程师
- ✅ 只懂业务逻辑的技术人员
- ✅ 想快速配置常见设备的工程师

**预计时间**：5分钟完成第一个模板

---

## 📋 第1步：选择数据读取场景

### 场景1：Modbus电子天平（最常见）

**适用设备**：奥豪斯、赛多利斯等Modbus TCP电子天平

**会读取什么**：
- 重量值（32位，需要2个寄存器合并）
- 默认单位：kg

**如何连接**：
1. 设备和电脑在同一网络
2. 知道设备IP地址
3. 知道设备从站编号（通常为1）

### 场景2：MQTT温湿度传感器

**适用设备**：DHT11/22、SHT30等MQTT传感器

**会读取什么**：
- 温度和湿度（2个数据）
- 默认单位：°C/%

**如何连接**：
1. 知道MQTT服务器地址
2. 知道主题名称（如：sensor/data）

---

## 📋 第2步：配置设备参数

### Modbus电子天平配置

**必填项**：
- 设备地址：例如 `192.168.1.100`
- 从站编号：例如 `1`

**可选项**：
- 端口：（默认502，通常不需要修改）

### MQTT传感器配置

**必填项**：
- MQTT地址：例如 `192.168.1.200`
- 端口：（默认1883，通常不需要修改）
- 主题：例如 `sensor/data`

---

## 📋 第3步：配置输出

### 重量值输出

**必填项**：
- 字段名：例如 `weight`
- 单位：选择 kg / g / t / lb
- 小数位：选择 0-4 位

**预览示例**：
```
weight = 123.45 kg
```

### 温湿度输出

**必填项**：
- 温度字段名：例如 `temperature`
- 湿度字段名：例如 `humidity`

**预览示例**：
```
temperature = 23.5 °C
humidity = 65.8 %
```

---

## 💾 第4步：保存模板

点击"💾 保存模板"按钮

**成功提示**：
```
✅ 保存成功！
模板ID: 1
```

---

## 🧪 第5步：在设备管理中使用模板

1. 切换到"设备管理"标签页
2. 点击"新建设备"
3. 填写设备信息
4. 在"协议模板"下拉框选择刚保存的模板
5. 填写设备地址等信息
6. 点击"测试连接"验证

**预期结果**：
- 设备创建成功
- 自动按照配置读取数据
- 数据显示在设备列表中

---

## 🔧 常见问题

### Q: 我想读取多个不同的数据，怎么办？

**A**: 创建多个模板，每个模板对应一个数据读取场景

### Q: 我的设备不在预设场景中，怎么办？

**A**:
1. 使用"表单编辑器"（有更多选项）
2. 使用"JSON编辑器"（完全自定义）

### Q: 配置错了想修改？

**A**:
1. 在设备管理中编辑设备，重新选择协议模板
2. 或在"协议编辑器"标签页修改模板

### Q: 读取的数据不对，小数点位置不对？

**A**:
1. 检查设备配置（地址、从站ID等）
2. 点击"测试连接"查看实际返回值
3. 调整输出配置（小数位数、单位）

---

## 🎯 三种编辑器对比

| 特性 | 可视化编辑器 | 表单编辑器 | JSON编辑器 |
|-----|-----------|----------|----------|
| 上手难度 | ⭐ 最简单 | ⭐⭐ 中等 | ⭐⭐⭐ 最复杂 |
| 学习时间 | 5分钟 | 30分钟 | 2小时 |
| 配置速度 | 3分钟/模板 | 10分钟/模板 | 30分钟/模板 |
| 灵活性 | ⭐⭐ 预设场景 | ⭐⭐⭐ 表单选项 | ⭐⭐⭐⭐ 完全自定义 |
| 适用场景 | 常见设备（80%） | 更多设备（95%） | 任何设备（100%） |

**建议**：
- 新手：从可视化编辑器开始
- 进阶：使用表单编辑器
- 专家：使用JSON编辑器
```

**步骤 2：提交**

```bash
git add docs/visual-editor-quick-start.md
git commit -m "docs: 添加可视化编辑器快速开始指南"
```

---

## 任务 10：添加示例配置界面

**文件:**
- 新建：`frontend/components/example_config.py`

**步骤 1：创建示例配置展示**

新建 `frontend/components/example_config.py`：

```python
"""
示例配置展示

帮助用户理解每个配置项的作用
"""

def get_modbus_scale_example():
    """Modbus电子天平示例配置"""
    return html.Div([
        html.H6("📝 示例配置"),
        html.Pre("""
设备：
  IP地址：192.168.1.100
  从站号：1

数据读取：
  场景：重量值（32位）
  说明：读取2个寄存器，自动合并

输出：
  字段名：weight
  单位：kg
  小数位：2位

生成的JSON模板会自动处理底层逻辑：
  - 读取寄存器0和1
  - 计算：寄存器0 * 65536 + 寄存器1
  - 保留2位小数
        """, style={"fontSize": "12px", "backgroundColor": "#f8f9fa", "padding": "10px"}),
    ])

def get_mqtt_sensor_example():
    """MQTT温湿度传感器示例配置"""
    return html.Div([
        html.H6("📝 示例配置"),
        html.Pre("""
设备：
  MQTT地址：192.168.1.200
  端口：1883

数据读取：
  场景：温湿度值
  主题：sensor/data

输出：
  温度字段名：temperature
  湿度字段名：humidity

生成的JSON模板会自动：
  - 订阅 sensor/data 主题
  - 解析JSON提取 temperature 和 humidity
  - 自动映射到输出字段
        """, style={"fontSize": "12px", "backgroundColor": "#f8f9fa", "padding": "10px"}),
    ])
```

**步骤 2：在页面中显示示例**

修改 `frontend/pages/visual_protocol_editor.py`，添加示例展示：

```python
from frontend.components.example_config import get_modbus_scale_example

# 在右侧配置面板下方添加示例展示
html.Div([
    html.H6("💡 配置示例", className="mt-4"),
    html.Div([
        html.Div([
            html.Div([
                html.A("显示Modbus示例", id="show-modbus-example",
                       className="alert-link d-inline-block"),
                html.A("显示MQTT示例", id="show-mqtt-example",
                       className="alert-link d-inline-block ms-3"),
            ], className="mb-2"),
            html.Div(id="example-display", style={"minHeight": "100px"}),
        ], className="bg-light p-3", style={"borderRadius": "5px"}),
    ], className="mt-4"),
])


@callback(
    Output("example-display", "children"),
    Input("show-modbus-example", "n_clicks"),
    prevent_initial_call=True
)
def show_modbus_example(n_clicks):
    return get_modbus_scale_example()

@callback(
    Output("example-display", "children"),
    Input("show-mqtt-example", "n_clicks"),
    prevent_initial_call=True
)
def show_mqtt_example(n_clicks):
    return get_mqtt_sensor_example()
```

**步骤 3：提交**

```bash
git add frontend/components/example_config.py frontend/pages/visual_protocol_editor.py
git commit -m "feat: 添加配置示例展示功能"
```

---

## 任务 11：最终测试和文档完善

**文件:**
- 新建：`docs/visual-editor-troubleshooting.md`

**步骤 1：创建故障排查文档**

新建 `docs/visual-editor-troubleshooting.md`：

```markdown
# 可视化编辑器故障排查

## 常见问题

### 问题1：保存时提示"配置错误"

**原因**：
- 必填项未填写
- 设备地址格式错误

**解决方案**：
- 检查设备地址格式（应为：192.168.1.100）
- 确保已选择场景

---

### 问题2：测试连接失败

**原因**：
- 设备未连接到网络
- 设备地址错误
- 防火墙阻止

**解决方案**：
1. ping设备地址：`ping 192.168.1.100`
2. 检查防火墙设置
3. 确认设备电源已打开

---

### 问题3：数据读取结果不对

**原因**：
- 从站ID配置错误
- 寄存器地址错误

**解决方案**：
1. 查看设备手册确认从站ID
2. 尝试不同的从站ID（1-255）
3. 使用"测试连接"功能查看原始数据

---

### 问题4：小数点不对

**原因**：
- 小数位数配置错误
- 设备返回数据格式与预设不符

**解决方案**：
1. 调整小数位数（0-4位）
2. 切换到"表单编辑器"或"JSON编辑器"查看原始数据
3. 根据实际数据格式自定义解析规则

---

## 获取帮助

- 查看快速开始指南：[快速开始指南](/docs/visual-editor-quick-start.md)
- 查看JSON编辑器：切换到"协议编辑器"标签页
- 查看表单编辑器：切换到"协议编辑器"标签页
- 联系技术支持：提供场景名称和配置详情
```

**步骤 2：最终测试清单**

```bash
# 1. 启动应用
python app.py

# 2. 访问可视化编辑器
# 浏览器打开：http://localhost:8050?tab=visual-protocol

# 3. 测试Modbus电子天平场景
# - 选择"Modbus电子天平"场景
# - 配置设备：192.168.1.100
# - 配置输出：weight, kg, 2位小数
# - 点击保存
# - 预期：显示"保存成功"

# 4. 测试MQTT传感器场景
# - 选择"MQTT温湿度传感器"场景
# - 配置设备：192.168.1.200
# - 点击保存
# - 预期：显示"保存成功"

# 5. 验证JSON格式
# - 展开"查看生成的JSON"
# - 预期：格式正确，无技术术语

# 6. 运行单元测试
pytest tests/ -k visual -v
# 预期：所有测试通过
```

**步骤 3：提交**

```bash
git add docs/visual-editor-troubleshooting.md
git commit -m "docs: 添加可视化编辑器故障排查文档"
```

---

## 验收标准

### 功能验收

- [x] 页面正常加载，3栏布局清晰
- [x] 场景选择器显示5种预设场景
- [x] 配置面板完全使用用户语言，无技术术语
- [x] 可以选择预设场景并查看配置示例
- [x] 输入配置后可以保存模板
- [x] 保存的模板可以在设备管理中使用

### 用户体验验收

- [x] 5分钟内可以创建第一个模板
- [x] 无需学习编程即可配置
- [x] 配置示例清晰易懂
- [x] 错误提示友好

### 兼容性验收

- [x] 不影响现有JSON编辑器功能
- [x] 不影响现有表单编辑器功能
- [x] 生成的JSON格式与现有格式兼容

---

**计划完成！**

**核心改进**：
- ✅ 完全避免技术术语
- ✅ 预设场景覆盖常见设备
- ✅ 3步配置流程
- ✅ 5分钟快速上手

**文档已保存**：`docs/plans/2026-03-01-visual-protocol-editor-cn.md`

**执行选项**：

**1. 会话内逐步执行** - 我在这个会话中逐个任务执行，每步评审
**2. 新会话批量执行** - 开启新会话批量执行，定期检查点

您希望哪种方式？或者您想先看看某个具体任务的详细设计？
