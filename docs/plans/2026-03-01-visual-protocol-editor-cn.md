# 可视化流程图协议编辑器实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标:** 构建基于拖拽节点的可视化协议配置界面，作为**可选功能**与现有JSON编辑和表单编辑并存，不替代现有功能。

**架构:**
- 前端：React Flow 节点编辑器（4种节点类型：设备→数据源→转换→输出）
- 后端：复用现有 ProtocolExecutor，新增流程图转JSON转换层
- 存储：现有 SQLite（不变）

**技术栈:**
- 前端：Dash + React Flow（通过 CDN 集成，无需 npm 构建）
- 后端：FastAPI + 现有服务层
- 原则：YAGNI（只实现必要功能）、DRY（复用现有代码）

---

## 任务 1：项目依赖安装

**文件:**
- 修改：`requirements.txt`

**步骤 1：添加 React Flow 依赖**

```bash
echo "react-flow==0.3.0" >> requirements.txt
```

**步骤 2：安装依赖**

运行：`pip install -r requirements.txt`
预期：无错误，依赖安装成功

**步骤 3：提交**

```bash
git add requirements.txt
git commit -m "feat: 添加 React Flow 依赖（可选可视化编辑器）"
```

---

## 任务 2：创建可视化编辑器页面布局

**文件:**
- 新建：`frontend/pages/visual_protocol_editor.py`

**步骤 1：创建页面基础结构**

新建 `frontend/pages/visual_protocol_editor.py`：

```python
from dash import html, dcc

def layout():
    """
    可视化协议编辑器页面布局（可选功能）

    与现有 JSON 编辑和表单编辑并存，用户可自由切换
    """
    return html.Div([
        # 页面标题
        html.Div([
            html.H2("🎨 可视化协议模板编辑器"),
            html.P([
                "拖拽节点配置设备通信协议 · ",
                html.Span(className="badge bg-info", children="初学者友好"),
                " · ",
                html.A("切换到JSON编辑", href="/?tab=protocols", className="alert-link")
            ], className="text-muted mb-0"),
        ], className="mb-4"),

        # 主编辑区域（三栏布局）
        html.Div([
            # 左侧：节点库（25%）
            html.Div([
                html.H5("📦 节点库"),
                html.Hr(),
                html.Div(id="node-palette"),
                html.Hr(),
                html.H6("📚 快速开始"),
                html.Div([
                    "选择预设模板：",
                    dcc.Dropdown(
                        id="preset-selector",
                        options=[
                            {"label": "奥豪斯电子天平", "value": "ohaus_scale"},
                            {"label": "MQTT温湿度传感器", "value": "mqtt_sensor"},
                        ],
                        placeholder="选择预设模板...",
                        className="mb-2"
                    ),
                    html.Button("加载模板", id="load-preset-btn",
                                className="btn btn-sm btn-outline-secondary w-100"),
                ], className="mt-4"),
            ], className="col-md-3", style={
                "border": "1px solid #ddd",
                "padding": "15px",
                "borderRadius": "5px"
            }),

            # 中间：画布（50%）
            html.Div([
                html.Div([
                    html.Div([
                        html.H6("画布", className="d-inline-block"),
                        html.Small(" 拖拽节点到此处，连线配置数据流",
                                 className="text-muted ms-2"),
                    ], className="mb-2"),
                    html.Div(id="react-flow-container", style={
                        "width": "100%",
                        "height": "500px",
                        "border": "1px solid #ccc",
                        "borderRadius": "5px",
                        "backgroundColor": "#f8f9fa"
                    }),
                ], className="p-3", style={
                    "border": "1px solid #ddd",
                    "borderRadius": "5px"
                }),
            ], className="col-md-6"),

            # 右侧：JSON预览（25%）
            html.Div([
                html.H6("📄 生成的JSON"),
                html.Small(" 实时预览，可直接复制使用", className="text-muted d-block mb-2"),
                dcc.Textarea(
                    id="json-preview",
                    style={
                        "width": "100%",
                        "height": "500px",
                        "fontFamily": "monospace",
                        "fontSize": "12px",
                        "backgroundColor": "#f8f9fa",
                        "border": "1px solid #ddd",
                        "padding": "10px"
                    },
                    readOnly=True
                ),
                html.Button("📋 复制JSON", id="copy-json-btn",
                           className="btn btn-sm btn-outline-primary w-100 mt-2"),
            ], className="col-md-3"),
        ], className="row"),

        # 底部：操作按钮
        html.Div([
            html.Div([
                html.Button("💾 保存模板", id="save-template-btn",
                           className="btn btn-primary me-2"),
                html.Button("🧪 测试连接", id="test-connection-btn",
                           className="btn btn-success me-2"),
                html.Button("🔄 清空画布", id="clear-canvas-btn",
                           className="btn btn-secondary me-2"),
                html.A("返回JSON编辑", href="/?tab=protocols",
                       className="btn btn-outline-secondary"),
            ], className="d-flex justify-content-center mt-4"),

            # 状态提示
            html.Div(id="status-message", className="mt-3 text-center"),
        ], className="mt-4"),

        # 存储组件（隐藏）
        dcc.Store(id="nodes-store", data={"nodes": [], "edges": []}),
        dcc.Store(id="protocol-name-store", data="新协议模板"),
    ])
```

**步骤 2：在 app.py 中注册页面**

修改 `app.py`，在协议编辑器标签页附近添加（约500行）：

```python
# 导入可视化编辑器
from frontend.pages import visual_protocol_editor

# 在标签页列表中添加（保留现有标签）
app.layout.children.append(
    dcc.Tab(label="可视化编辑器", value="visual-protocol",
            children=visual_protocol_editor.layout())
)
```

**步骤 3：测试页面加载**

运行：`python app.py`
访问：`http://localhost:8050?tab=visual-protocol`
预期：页面正常显示，三栏布局完整

**步骤 4：提交**

```bash
git add frontend/pages/visual_protocol_editor.py app.py
git commit -m "feat: 添加可视化编辑器页面布局（可选功能）"
```

---

## 任务 3：实现节点调色板组件

**文件:**
- 新建：`frontend/components/node_palette.py`

**步骤 1：创建节点调色板**

新建 `frontend/components/node_palette.py`：

```python
from dash import html

# 4种节点类型定义
NODE_TYPES = [
    {
        "type": "device",
        "label": "📦 设备",
        "description": "设备配置（协议类型、地址等）",
        "color": "#007bff",
        "icon": "📦"
    },
    {
        "type": "dataSource",
        "label": "📨 数据源",
        "description": "从设备读取数据（寄存器/主题）",
        "color": "#28a745",
        "icon": "📨"
    },
    {
        "type": "transform",
        "label": "🔄 转换",
        "description": "数据处理（解析/计算/格式化）",
        "color": "#ffc107",
        "icon": "🔄"
    },
    {
        "type": "output",
        "label": "📤 输出",
        "description": "最终输出字段",
        "color": "#17a2b8",
        "icon": "📤"
    },
]

def create_draggable_node(node_type):
    """创建可拖拽的节点元素"""
    return html.Div([
        html.Div([
            html.Span(node_type["icon"], className="me-2"),
            html.Strong(node_type["label"]),
        ], style={
            "padding": "12px",
            "margin": "8px 0",
            "backgroundColor": node_type["color"],
            "color": "white",
            "borderRadius": "6px",
            "cursor": "grab",
            "textAlign": "center",
            "fontSize": "14px",
            "boxShadow": "0 2px 4px rgba(0,0,0,0.1)"
        }),
        html.Small(node_type["description"],
                 className="text-muted d-block px-1",
                 style={"fontSize": "11px"}),
    ], draggable=True, **{
        "data-node-type": node_type["type"],
        "style": {"marginBottom": "12px"}
    })

def layout():
    """节点调色板组件布局"""
    nodes = []
    for node_type in NODE_TYPES:
        nodes.append(create_draggable_node(node_type))

    return html.Div([
        html.P("💡 拖拽节点到画布开始配置", className="text-muted mb-3"),
        *nodes,
    ], id="node-palette")
```

**步骤 2：在页面中使用调色板**

修改 `frontend/pages/visual_protocol_editor.py`，导入调色板：

```python
from frontend.components.node_palette import layout as node_palette_layout

# 在布局中替换 html.Div(id="node-palette") 为：
node_palette_layout()
```

**步骤 3：测试节点显示**

运行：`python app.py`
访问可视化编辑器页面
预期：左侧显示4个可拖拽节点，带图标和描述

**步骤 4：提交**

```bash
git add frontend/components/node_palette.py frontend/pages/visual_protocol_editor.py
git commit -m "feat: 添加节点调色板组件"
```

---

## 任务 4：集成 React Flow 画布

**文件:**
- 新建：`frontend/assets/react_flow_canvas.js`
- 修改：`app.py`

**步骤 1：创建 React Flow 初始化脚本**

新建 `frontend/assets/react_flow_canvas.js`：

```javascript
/**
 * React Flow 画布初始化脚本
 * 功能：拖拽节点、连线、缩放、平移
 */

// 等待页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    window.initReactFlowCanvas = function(containerId) {
        const container = document.getElementById(containerId);
        if (!container) {
            console.error('未找到画布容器:', containerId);
            return;
        }

        // 动态加载 React 和 React Flow
        const loadReactFlow = async function() {
            try {
                // 使用 UMD 版本的 React 和 React Flow
                const [{ createElement, useState, useCallback },
                        { createRoot }] = await Promise.all([
                    import('https://unpkg.com/react@18/umd/react.production.min.js'),
                    import('https://unpkg.com/react-dom@18/umd/react-dom.production.min.js'),
                    import('https://unpkg.com/reactflow@11.10.0/dist/umd/index.js')
                ]);

                const React = createElement;
                const { ReactFlow, Background, Controls, MiniMap } = window.ReactFlow;

                // 创建画布组件
                function FlowChart() {
                    const [nodes, setNodes] = React.useState([]);
                    const [edges, setEdges] = React.useState([]);

                    // 拖拽放置节点
                    const onDrop = useCallback((event) => {
                        event.preventDefault();

                        const nodeType = event.dataTransfer.getData('application/reactflow');
                        if (!nodeType) return;

                        const position = {
                            x: event.clientX - container.getBoundingClientRect().left,
                            y: event.clientY - container.getBoundingClientRect().top,
                        };

                        const newNode = {
                            id: `${nodeType}-${Date.now()}`,
                            type: nodeType,
                            position,
                            data: {
                                label: getNodeLabel(nodeType),
                                nodeType: nodeType
                            },
                        };

                        setNodes((nds) => {
                            const updated = [...nds, newNode];
                            // 通知 Dash 更新存储
                            notifyDashUpdate(updated, edges);
                            return updated;
                        });
                    }, []);

                    // 连接节点
                    const onConnect = useCallback((params) => {
                        setEdges((eds) => {
                            const updated = [...eds, {
                                ...params,
                                animated: true,
                                style: { stroke: '#bbb' }
                            }];
                            notifyDashUpdate(nodes, updated);
                            return updated;
                        });
                    }, [nodes]);

                    // 允许节点拖动
                    const onNodesChange = useCallback((newNodes) => {
                        setNodes(newNodes);
                        notifyDashUpdate(newNodes, edges);
                    }, [edges]);

                    return React.createElement(ReactFlow, {
                        nodes: nodes,
                        edges: edges,
                        onNodesChange: onNodesChange,
                        onEdgesChange: onEdgesChange,
                        onDrop: onDrop,
                        onDragOver: (e) => {
                            e.preventDefault();
                            e.dataTransfer.dropEffect = 'move';
                        },
                        onConnect: onConnect,
                        fitView: true,
                        snapToGrid: true,
                        defaultEdgeOptions: { animated: true },
                    },
                        React.createElement(Background, {
                            variant: 'dots',
                            gap: 12,
                            size: 1,
                            color: '#e0e0e0'
                        }),
                        React.createElement(Controls, {
                            style: { display: 'flex', gap: '5px' }
                        }),
                        React.createElement(MiniMap, {
                            nodeColor: (node) => {
                                const colors = {
                                    'device': '#007bff',
                                    'dataSource': '#28a745',
                                    'transform': '#ffc107',
                                    'output': '#17a2b8'
                                };
                                return colors[node.data.nodeType] || '#ccc';
                            },
                            maskColor: 'rgba(0, 0, 0, 0.1)'
                        })
                    );
                }

                // 渲染到容器
                const root = createRoot(container);
                root.render(React.createElement(FlowChart));

                console.log('✅ React Flow 画布初始化成功');

            } catch (error) {
                console.error('❌ React Flow 加载失败:', error);
                container.innerHTML = `
                    <div style="padding: 20px; color: red;">
                        ⚠️ 画布加载失败，请刷新页面重试
                    </div>
                `;
            }
        };

        loadReactFlow();
    };
});

// 获取节点标签
function getNodeLabel(type) {
    const labels = {
        device: '📦 设备',
        dataSource: '📨 数据源',
        transform: '🔄 转换',
        output: '📤 输出'
    };
    return labels[type] || type;
}

// 通知 Dash 更新（通过自定义事件）
function notifyDashUpdate(nodes, edges) {
    const event = new CustomEvent('reactFlowChange', {
        detail: {
            nodes: nodes,
            edges: edges
        }
    });
    document.dispatchEvent(event);
}

// 监听来自 Dash 的更新（如加载预设）
document.addEventListener('loadPreset', function(event) {
    const preset = event.detail;
    if (window.updateFlowFromPreset) {
        window.updateFlowFromPreset(preset);
    }
});
```

**步骤 2：在 app.py 中添加脚本引用**

修改 `app.py`，在 `external_scripts` 列表中添加（约100行）：

```python
external_scripts = [
    # ... 现有脚本 ...
    "https://unpkg.com/react@18/umd/react.production.min.js",
    "https://unpkg.com/react-dom@18/umd/react-dom.production.min.js",
    "https://unpkg.com/reactflow@11.10.0/dist/umd/index.js",
    "/assets/react_flow_canvas.js",
]
```

**步骤 3：添加客户端回调**

在 `frontend/pages/visual_protocol_editor.py` 中添加：

```python
from dash import ClientsideFunction

@callback(
    Output("react-flow-container", "data-loaded"),
    Input("react-flow-container", "id")
)
def init_canvas(container_id):
    """初始化 React Flow 画布"""
    return ClientsideFunction(
        "initReactFlowCanvas",
        [Input("react-flow-container", "id")]
    )
```

**步骤 4：测试画布初始化**

运行：`python app.py`
访问可视化编辑器页面
预期：画布显示点状背景，有缩放/平移/小地图控件

**步骤 5：提交**

```bash
git add frontend/assets/react_flow_canvas.js app.py frontend/pages/visual_protocol_editor.py
git commit -m "feat: 集成 React Flow 画布（支持拖拽和连线）"
```

---

## 任务 5：实现节点配置弹窗

**文件:**
- 新建：`frontend/components/node_config_modal.py`

**步骤 1：创建配置弹窗组件**

新建 `frontend/components/node_config_modal.py`：

```python
from dash import html, dcc

def device_node_config():
    """设备节点配置"""
    return html.Div([
        html.H4("📦 配置设备节点"),

        html.Div([
            html.Label("协议类型", className="form-label"),
            dcc.Dropdown(
                id="config-device-protocol",
                options=[
                    {"label": "Modbus TCP", "value": "modbus_tcp"},
                    {"label": "Modbus RTU", "value": "modbus_rtu"},
                    {"label": "MQTT", "value": "mqtt"},
                    {"label": "Serial", "value": "serial"},
                    {"label": "TCP", "value": "tcp"},
                ],
                value="modbus_tcp",
                className="mb-3"
            ),
        ]),

        html.Div([
            html.Label("设备地址", className="form-label"),
            dcc.Input(
                id="config-device-address",
                type="text",
                placeholder="192.168.1.100",
                className="form-control mb-3"
            ),
        ]),

        html.Div([
            html.Label("端口", className="form-label"),
            dcc.Input(
                id="config-device-port",
                type="number",
                placeholder="502",
                value=502,
                className="form-control mb-3"
            ),
        ]),

        html.Div([
            html.Label("从站ID", className="form-label"),
            dcc.Input(
                id="config-device-slave-id",
                type="number",
                value=1,
                className="form-control mb-3"
            ),
        ]),
    ])

def data_source_config():
    """数据源节点配置"""
    return html.Div([
        html.H4("📨 配置数据源"),

        html.Div([
            html.Label("操作类型", className="form-label"),
            dcc.Dropdown(
                id="config-datasource-action",
                options=[
                    {"label": "读取输入寄存器", "value": "read_input_registers"},
                    {"label": "读取保持寄存器", "value": "read_holding_registers"},
                    {"label": "读取线圈", "value": "read_coils"},
                    {"label": "写入单个寄存器", "value": "write_single_register"},
                ],
                value="read_input_registers",
                className="mb-3"
            ),
        ]),

        html.Div([
            html.Label("起始地址", className="form-label"),
            dcc.Input(
                id="config-datasource-address",
                type="number",
                value=0,
                className="form-control mb-3"
            ),
        ]),

        html.Div([
            html.Label("读取数量", className="form-label"),
            dcc.Input(
                id="config-datasource-count",
                type="number",
                value=2,
                className="form-control mb-3"
            ),
        ]),

        html.Div([
            html.Label("数据类型", className="form-label"),
            dcc.RadioItems(
                id="config-datasource-data-type",
                options=[
                    {"label": "16位整数", "value": "int16"},
                    {"label": "32位整数", "value": "int32"},
                    {"label": "浮点数", "value": "float"},
                ],
                value="int16",
                className="mb-3"
            ),
        ]),
    ])

def transform_config():
    """转换节点配置"""
    return html.Div([
        html.H4("🔄 配置转换"),

        html.Div([
            html.Label("转换类型", className="form-label"),
            dcc.Dropdown(
                id="config-transform-type",
                options=[
                    {"label": "合并32位整数", "value": "combine_32bit"},
                    {"label": "四则运算", "value": "arithmetic"},
                    {"label": "正则提取", "value": "regex_extract"},
                    {"label": "JSON解析", "value": "json_parse"},
                    {"label": "单位转换", "value": "unit_convert"},
                ],
                value="combine_32bit",
                className="mb-3"
            ),
        ]),

        html.Div([
            html.Label("公式/模式", className="form-label"),
            dcc.Input(
                id="config-transform-formula",
                type="text",
                placeholder="A*65536+B 或 (?<=value)": (.*)",
                className="form-control mb-3"
            ),
        ]),

        html.Small([
            "💡 提示：",
            html.Code("A*65536+B", className="me-1"),
            "表示合并两个字节，",
            html.Code("(?<=value"): (.*)", className="me-1"),
            "表示提取 value 后的值"
        ], className="text-muted"),
    ])

def output_config():
    """输出节点配置"""
    return html.Div([
        html.H4("📤 配置输出"),

        html.Div([
            html.Label("字段名", className="form-label"),
            dcc.Input(
                id="config-output-field",
                type="text",
                placeholder="weight / temperature / humidity",
                className="form-control mb-3"
            ),
        ]),

        html.Div([
            html.Label("单位", className="form-label"),
            dcc.Input(
                id="config-output-unit",
                type="text",
                placeholder="kg / °C / %",
                className="form-control mb-3"
            ),
        ]),

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
        ]),
    ])

def get_config_modal(node_type):
    """根据节点类型返回对应配置"""
    modals = {
        "device": device_node_config(),
        "dataSource": data_source_config(),
        "transform": transform_config(),
        "output": output_config(),
    }
    return modals.get(node_type, html.Div("未知节点类型"))
```

**步骤 2：在页面中添加弹窗容器**

修改 `frontend/pages/visual_protocol_editor.py`，在操作按钮后添加：

```python
# 配置弹窗（默认隐藏）
html.Div(id="config-modal-container", style={
    "display": "none",
    "position": "fixed",
    "top": "50%",
    "left": "50%",
    "transform": "translate(-50%, -50%)",
    "backgroundColor": "white",
    "padding": "25px",
    "borderRadius": "10px",
    "boxShadow": "0 10px 25px rgba(0,0,0,0.2)",
    "zIndex": "9999",
    "maxWidth": "500px",
    "width": "90%",
    "maxHeight": "80vh",
    "overflowY": "auto"
}),

html.Div(id="config-modal-content"),

html.Div([
    html.Button("✖️ 关闭", id="close-modal-btn",
               className="btn btn-sm btn-secondary float-end"),
    html.Br(),
    html.Button("💾 保存配置", id="save-node-config-btn",
               className="btn btn-primary"),
], className="mt-3"),
```

**步骤 3：测试弹窗显示**

运行：`python app.py`
预期：弹窗容器已定义（通过回调显示）

**步骤 4：提交**

```bash
git add frontend/components/node_config_modal.py frontend/pages/visual_protocol_editor.py
git commit -m "feat: 添加节点配置弹窗"
```

---

## 任务 6：实现流程图转JSON转换器

**文件:**
- 新建：`backend/services/visual_flow_converter.py`

**步骤 1：创建转换服务**

新建 `backend/services/visual_flow_converter.py`：

```python
"""
可视化流程图转JSON转换服务

将用户在可视化编辑器中创建的节点和连线，
转换为协议模板JSON格式，复用现有 ProtocolExecutor
"""

from typing import Any

def flow_to_json(flow_data: dict[str, Any], protocol_name: str) -> dict[str, Any]:
    """
    将可视化流程图转换为协议模板JSON

    Args:
        flow_data: 流程图数据 {"nodes": [...], "edges": [...]}
        protocol_name: 协议模板名称

    Returns:
        协议模板JSON（与现有格式兼容）
    """
    nodes = flow_data.get("nodes", [])
    edges = flow_data.get("edges", [])

    if not nodes:
        raise ValueError("流程图为空，请先添加节点")

    # 查找设备节点（根节点）
    device_node = next((n for n in nodes if n["type"] == "device"), None)
    if not device_node:
        raise ValueError("必须先添加设备节点")

    # 获取协议类型
    protocol_type = device_node.get("data", {}).get("protocol", "modbus_tcp")

    # 构建步骤列表
    steps = []

    # 处理数据源节点
    for node in nodes:
        if node["type"] == "dataSource":
            step = _build_data_source_step(node, edges, protocol_type)
            steps.append(step)
        elif node["type"] == "transform":
            step = _build_transform_step(node)
            steps.append(step)

    # 构建输出映射
    output_mapping = _build_output_mapping(nodes, edges)

    # 构建完整模板
    template = {
        "name": protocol_name,
        "description": f"通过可视化编辑器创建（{len(nodes)}个节点）",
        "protocol_type": protocol_type,
        "variables": [],
        "output": output_mapping,
        "steps": steps
    }

    return template


def _build_data_source_step(node: dict, edges: list, protocol_type: str) -> dict[str, Any]:
    """构建数据源步骤"""
    data = node.get("data", {})
    node_id = node["id"]

    # 查找依赖的前置节点
    input_edge = next((e for e in edges if e["target"] == node_id), None)

    # 构建参数
    if protocol_type in ["modbus_tcp", "modbus_rtu"]:
        action = data.get("action", "read_input_registers")
        if action.startswith("read_"):
            action = f"modbus.{action}"

        return {
            "id": node_id,
            "name": data.get("name", "读取数据"),
            "action": action,
            "trigger": "poll",
            "params": {
                "address": data.get("address", 0),
                "count": data.get("count", 2),
                "slave_id": data.get("slave_id", 1)
            },
            "parse": {
                "type": data.get("dataType", "raw")
            }
        }

    elif protocol_type == "mqtt":
        return {
            "id": node_id,
            "name": "订阅消息",
            "action": "mqtt.subscribe",
            "trigger": "poll",
            "params": {
                "topic": data.get("topic", ""),
                "qos": 0
            }
        }

    else:  # Serial, TCP
        return {
            "id": node_id,
            "name": "发送命令",
            "action": f"{protocol_type}.send",
            "trigger": "poll",
            "params": {
                "command": data.get("command", "")
            }
        }


def _build_transform_step(node: dict) -> dict[str, Any]:
    """构建转换步骤"""
    data = node.get("data", {})
    node_id = node["id"]

    transform_type = data.get("transformType", "arithmetic")

    if transform_type == "combine_32bit":
        return {
            "id": node_id,
            "name": "合并32位整数",
            "action": "transform.parse",
            "trigger": "poll",
            "params": {
                "type": "expression",
                "expression": data.get("formula", "A*65536+B")
            }
        }

    elif transform_type == "arithmetic":
        return {
            "id": node_id,
            "name": "四则运算",
            "action": "transform.parse",
            "trigger": "poll",
            "params": {
                "type": "expression",
                "expression": data.get("formula", "A+B")
            }
        }

    elif transform_type == "regex_extract":
        return {
            "id": node_id,
            "name": "正则提取",
            "action": "transform.parse",
            "trigger": "poll",
            "params": {
                "type": "regex",
                "pattern": data.get("formula", ""),
                "output": "match"
            }
        }

    elif transform_type == "json_parse":
        return {
            "id": node_id,
            "name": "JSON解析",
            "action": "transform.parse",
            "trigger": "poll",
            "params": {
                "type": "json_path",
                "expression": data.get("formula", "$.value")
            }
        }

    else:  # 默认
        return {
            "id": node_id,
            "name": "数据转换",
            "action": "transform.parse",
            "trigger": "poll",
            "params": {
                "type": "expression",
                "expression": data.get("formula", "value")
            }
        }


def _build_output_mapping(nodes: list, edges: list) -> dict[str, Any]:
    """构建输出映射"""
    output = {}

    for node in nodes:
        if node["type"] == "output":
            field_name = node.get("data", {}).get("field", "output")
            unit = node.get("data", {}).get("unit", "")
            decimals = node.get("data", {}).get("decimals", 2)

            # 查找输入边
            input_edge = next((e for e in edges if e["target"] == node["id"]), None)

            if input_edge:
                source_node = next((n for n in nodes if n["id"] == input_edge["source"]), None)
                if source_node:
                    # 引用源节点的结果
                    reference = f"${{{{source_node['id']}.result}}}"

                    # 添加单位转换（如果有）
                    if unit:
                        if decimals == 0:
                            output[field_name] = f"int({reference})"
                        else:
                            output[field_name] = f"round({reference}, {decimals})"
                    else:
                        output[field_name] = reference

    return output
```

**步骤 2：创建单元测试**

新建 `tests/test_visual_flow_converter.py`：

```python
import pytest
from backend.services.visual_flow_converter import flow_to_json

def test_simple_modbus_flow():
    """测试简单的Modbus流程"""
    flow = {
        "nodes": [
            {
                "id": "device1",
                "type": "device",
                "data": {"protocol": "modbus_tcp", "address": "192.168.1.100"}
            },
            {
                "id": "read1",
                "type": "dataSource",
                "data": {"address": 0, "count": 2, "slave_id": 1}
            },
            {
                "id": "output1",
                "type": "output",
                "data": {"field": "weight", "unit": "kg"}
            }
        ],
        "edges": [
            {"source": "device1", "target": "read1"},
            {"source": "read1", "target": "output1"}
        ]
    }

    template = flow_to_json(flow, "测试模板")

    assert template["protocol_type"] == "modbus_tcp"
    assert len(template["steps"]) == 1
    assert "weight" in template["output"]

def test_complex_flow_with_transform():
    """测试带转换节点的复杂流程"""
    flow = {
        "nodes": [
            {"id": "device1", "type": "device", "data": {"protocol": "modbus_tcp"}},
            {"id": "read1", "type": "dataSource", "data": {"address": 0, "count": 2}},
            {"id": "combine", "type": "transform",
             "data": {"transformType": "combine_32bit", "formula": "A*65536+B"}},
            {"id": "output1", "type": "output", "data": {"field": "weight"}}
        ],
        "edges": [
            {"source": "device1", "target": "read1"},
            {"source": "read1", "target": "combine"},
            {"source": "combine", "target": "output1"}
        ]
    }

    template = flow_to_json(flow, "32位合并测试")

    assert len(template["steps"]) == 2  # read + transform
    assert template["steps"][1]["params"]["expression"] == "A*65536+B"

def test_empty_flow_raises_error():
    """测试空流程抛出异常"""
    with pytest.raises(ValueError, match="流程图为空"):
        flow_to_json({"nodes": [], "edges": []}, "测试")

def test_flow_without_device_raises_error():
    """测试缺少设备节点抛出异常"""
    with pytest.raises(ValueError, match="必须先添加设备节点"):
        flow = {
            "nodes": [{"id": "read1", "type": "dataSource"}],
            "edges": []
        }
        flow_to_json(flow, "测试")
```

**步骤 3：运行测试**

运行：`pytest tests/test_visual_flow_converter.py -v`
预期：所有测试通过

**步骤 4：提交**

```bash
git add backend/services/visual_flow_converter.py tests/test_visual_flow_converter.py
git commit -m "feat: 添加流程图转JSON转换器"
```

---

## 任务 7：实现实时JSON预览

**文件:**
- 修改：`frontend/pages/visual_protocol_editor.py`

**步骤 1：添加实时预览回调**

在 `frontend/pages/visual_protocol_editor.py` 中添加：

```python
from dash import callback
import json
from backend.services.visual_flow_converter import flow_to_json

@callback(
    Output("json-preview", "value"),
    Input("nodes-store", "data"),
    State("protocol-name-store", "data"),
    prevent_initial_call=False
)
def update_json_preview(flow_data, protocol_name):
    """流程图变化时实时更新JSON预览"""

    if not flow_data or not flow_data.get("nodes"):
        return json.dumps({
            "comment": "💡 拖拽节点到画布开始配置",
            "steps": []
        }, indent=2, ensure_ascii=False)

    try:
        # 转换流程图为JSON
        template = flow_to_json(flow_data, protocol_name or "新协议模板")

        # 美化输出
        return json.dumps(template, indent=2, ensure_ascii=False)

    except ValueError as e:
        return json.dumps({
            "error": f"⚠️ 配置错误: {str(e)}",
            "hint": "请检查：1. 是否已添加设备节点 2. 连线是否正确"
        }, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "error": f"❌ 生成失败: {str(e)}"
        }, indent=2, ensure_ascii=False)


@callback(
    Output("status-message", "children"),
    Input("json-preview", "value"),
    prevent_initial_call=True
)
def show_preview_status(json_value):
    """显示预览状态"""
    try:
        template = json.loads(json_value)
        if "error" in template:
            return html.Div(template["error"], className="alert alert-warning")
        elif "comment" in template:
            return html.Div(template["comment"], className="alert alert-info")
        else:
            return html.Div("✅ JSON生成成功", className="alert alert-success")
    except:
        return html.Div("⚠️ JSON格式错误", className="alert alert-danger")
```

**步骤 2：在画布脚本中添加Dash通知**

修改 `frontend/assets/react_flow_canvas.js`，添加更新逻辑：

```javascript
// 在文件末尾添加

// 监听流程图变化，通知Dash更新
function notifyDashUpdate(nodes, edges) {
    // 更新全局状态
    window.currentFlowData = { nodes, edges };

    // 触发Dash回调更新存储
    const storeElement = document.getElementById('nodes-store');
    if (storeElement && window.dash_clientside) {
        // 使用Dash的自定义事件机制
        const event = new CustomEvent('reactFlowChange', {
            detail: { nodes: nodes, edges: edges },
            bubbles: true
        });

        // 更新Dash Store
        // 注意：这里需要通过Dash的回调机制来更新
        // 实际更新在步骤3中实现
    }

    console.log('📊 流程图已更新:', nodes.length, '个节点,', edges.length, '条连线');
}

// 加载预设模板到画布
window.loadPresetToCanvas = function(presetData) {
    if (!window.reactFlowSetNodes) {
        console.error('画布未初始化');
        return;
    }

    const event = new CustomEvent('loadPreset', {
        detail: presetData
    });
    document.dispatchEvent(event);
};
```

**步骤 3：添加Dash客户端回调**

在 `frontend/pages/visual_protocol_editor.py` 中添加客户端回调：

```python
# 添加客户端回调脚本到页面
html.Script(id="react-flow-bridge", children="""

// 监听React Flow变化，更新Dash Store
document.addEventListener('reactFlowChange', function(event) {
    const data = event.detail;
    // 触发Dash回调更新存储
    if (window.dash_clientside) {
        window.dash_clientside.setCallback('nodes-store.data', data);
    }
});

// 监听预设加载事件
document.addEventListener('loadPreset', function(event) {
    const preset = event.detail;
    // 这里需要通过React Flow API设置节点和连线
    console.log('📦 加载预设模板:', preset.name);
});

""")
```

**步骤 4：测试实时预览**

运行：`python app.py`
访问可视化编辑器，拖拽一个节点
预期：右侧JSON预览实时更新

**步骤 5：提交**

```bash
git add frontend/pages/visual_protocol_editor.py frontend/assets/react_flow_canvas.js
git commit -m "feat: 添加实时JSON预览功能"
```

---

## 任务 8：实现预设模板功能

**文件:**
- 新建：`backend/services/preset_templates.py`

**步骤 1：创建预设模板服务**

新建 `backend/services/preset_templates.py`：

```python
"""
预设模板库

提供常见设备的预设流程图，帮助用户快速上手
"""

PRESET_TEMPLATES = {
    "ohaus_scale": {
        "name": "奥豪斯电子天平",
        "description": "Modbus TCP 电子天平，读取32位重量数据",
        "protocol_type": "modbus_tcp",
        "nodes": [
            {
                "id": "device",
                "type": "device",
                "position": {"x": 50, "y": 100},
                "data": {
                    "protocol": "modbus_tcp",
                    "address": "192.168.1.100",
                    "port": 502,
                    "slave_id": 1
                }
            },
            {
                "id": "read_weight",
                "type": "dataSource",
                "position": {"x": 350, "y": 100},
                "data": {
                    "name": "读取重量",
                    "action": "read_input_registers",
                    "address": 0,
                    "count": 2,
                    "slave_id": 1,
                    "dataType": "int16"
                }
            },
            {
                "id": "combine_32bit",
                "type": "transform",
                "position": {"x": 650, "y": 100},
                "data": {
                    "name": "合并32位",
                    "transformType": "combine_32bit",
                    "formula": "A*65536+B"
                }
            },
            {
                "id": "output_weight",
                "type": "output",
                "position": {"x": 950, "y": 100},
                "data": {
                    "field": "weight",
                    "unit": "kg",
                    "decimals": 2
                }
            }
        ],
        "edges": [
            {"source": "device", "target": "read_weight", "id": "e1"},
            {"source": "read_weight", "target": "combine_32bit", "id": "e2"},
            {"source": "combine_32bit", "target": "output_weight", "id": "e3"}
        ]
    },

    "mqtt_sensor": {
        "name": "MQTT温湿度传感器",
        "description": "订阅MQTT主题，解析JSON格式的温湿度数据",
        "protocol_type": "mqtt",
        "nodes": [
            {
                "id": "device",
                "type": "device",
                "position": {"x": 50, "y": 100},
                "data": {
                    "protocol": "mqtt",
                    "address": "localhost",
                    "port": 1883
                }
            },
            {
                "id": "subscribe",
                "type": "dataSource",
                "position": {"x": 350, "y": 100},
                "data": {
                    "name": "订阅消息",
                    "topic": "sensor/data"
                }
            },
            {
                "id": "parse_json",
                "type": "transform",
                "position": {"x": 650, "y": 100},
                "data": {
                    "name": "解析JSON",
                    "transformType": "json_parse",
                    "formula": "$.temperature"
                }
            },
            {
                "id": "output_temp",
                "type": "output",
                "position": {"x": 950, "y": 100},
                "data": {
                    "field": "temperature",
                    "unit": "°C",
                    "decimals": 1
                }
            }
        ],
        "edges": [
            {"source": "device", "target": "subscribe", "id": "e1"},
            {"source": "subscribe", "target": "parse_json", "id": "e2"},
            {"source": "parse_json", "target": "output_temp", "id": "e3"}
        ]
    }
}


def get_preset_template(preset_id: str) -> dict[str, object] | None:
    """根据ID获取预设模板"""
    return PRESET_TEMPLATES.get(preset_id)


def list_preset_templates() -> list[dict[str, Any]]:
    """列出所有可用的预设模板"""
    return [
        {
            "id": key,
            "name": value["name"],
            "description": value["description"],
            "protocol_type": value["protocol_type"],
            "complexity": "简单" if len(value["nodes"]) <= 4 else "复杂"
        }
        for key, value in PRESET_TEMPLATES.items()
    ]
```

**步骤 2：添加加载预设回调**

在 `frontend/pages/visual_protocol_editor.py` 中添加：

```python
from backend.services.preset_templates import get_preset_template

@callback(
    Output("nodes-store", "data"),
    Output("status-message", "children"),
    Input("load-preset-btn", "n_clicks"),
    State("preset-selector", "value"),
    prevent_initial_call=True
)
def load_preset(n_clicks, preset_id):
    """加载预设模板到画布"""

    if not preset_id:
        return dash.no_update, html.Div("请选择预设模板", className="alert alert-warning")

    try:
        preset = get_preset_template(preset_id)
        if not preset:
            return dash.no_update, html.Div("预设模板不存在", className="alert alert-danger")

        return {
            "nodes": preset["nodes"],
            "edges": preset["edges"]
        }, html.Div([
            f"✅ 已加载预设模板：{preset['name']}",
            html.Br(),
            html.Small(preset['description'], className="text-muted")
        ], className="alert alert-success")

    except Exception as e:
        return dash.no_update, html.Div(f"❌ 加载失败: {str(e)}", className="alert alert-danger")
```

**步骤 3：更新预设选择器选项**

修改页面中的预设选择器：

```python
from backend.services.preset_templates import list_preset_templates

# 在生成预设选择器时动态获取选项
html.Div([
    "选择预设模板：",
    dcc.Dropdown(
        id="preset-selector",
        options=[
            {"label": f"{t['name']} ({t['protocol_type']})", "value": t['id"]}
            for t in list_preset_templates()
        ],
        placeholder="选择预设模板...",
        className="mb-2"
    ),
    html.Button("加载模板", id="load-preset-btn",
               className="btn btn-sm btn-outline-secondary w-100"),
], className="mt-4"),
```

**步骤 4：测试预设加载**

运行：`python app.py`
选择"奥豪斯电子天平"预设，点击加载
预期：画布显示预设节点和连线，JSON预览更新

**步骤 5：提交**

```bash
git add backend/services/preset_templates.py frontend/pages/visual_protocol_editor.py
git commit -m "feat: 添加预设模板功能（奥豪斯电子天平、MQTT传感器）"
```

---

## 任务 9：实现模板保存功能

**文件:**
- 修改：`frontend/pages/visual_protocol_editor.py`

**步骤 1：添加保存回调**

在 `frontend/pages/visual_protocol_editor.py` 中添加：

```python
import requests
from config.settings import settings

@callback(
    Output("status-message", "children", allow_duplicate=True),
    Input("save-template-btn", "n_clicks"),
    State("nodes-store", "data"),
    State("protocol-name-store", "data"),
    prevent_initial_call=True
)
def save_template(n_clicks, flow_data, protocol_name):
    """保存可视化流程图为协议模板"""

    if not flow_data or not flow_data.get("nodes"):
        return html.Div("⚠️ 画布为空，请先配置协议模板", className="alert alert-warning")

    try:
        # 使用转换器生成JSON
        from backend.services.visual_flow_converter import flow_to_json
        template = flow_to_json(flow_data, protocol_name or "新协议模板")

        # 调用后端API保存
        response = requests.post(
            f"{settings.backend_base}/api/protocols",
            json=template,
            timeout=10
        )
        response.raise_for_status()

        result = response.json()

        return html.Div([
            f"✅ 模板保存成功！",
            html.Br(),
            html.Small(f"模板ID: {result.get('id', 'N/A')}", className="text-muted"),
        ], className="alert alert-success")

    except requests.exceptions.RequestException as e:
        return html.Div(f"❌ 保存失败: {str(e)}", className="alert alert-danger")

    except ValueError as e:
        return html.Div(f"⚠️ 配置错误: {str(e)}", className="alert alert-warning")

    except Exception as e:
        return html.Div(f"❌ 未知错误: {str(e)}", className="alert alert-danger")


@callback(
    Output("protocol-name-store", "data"),
    Input("protocol-name-input", "value"),
    prevent_initial_call=True
)
def update_protocol_name(name):
    """更新协议模板名称"""
    return name or "新协议模板"
```

**步骤 2：添加协议名称输入框**

在页面顶部添加输入框：

```python
html.Div([
    html.Label("模板名称", className="form-label"),
    dcc.Input(
        id="protocol-name-input",
        type="text",
        placeholder="例如：奥豪斯电子天平配置",
        className="form-control"
    ),
], className="mb-3"),
```

**步骤 3：测试保存功能**

运行：`python app.py`
创建简单流程（设备→数据源→输出），输入名称，点击保存
预期：显示"保存成功"提示

**步骤 4：提交**

```bash
git add frontend/pages/visual_protocol_editor.py
git commit -m "feat: 添加模板保存功能"
```

---

## 任务 10：添加清空画布功能

**文件:**
- 修改：`frontend/pages/visual_protocol_editor.py`

**步骤 1：添加清空回调**

添加回调函数：

```python
@callback(
    Output("nodes-store", "data", allow_duplicate=True),
    Output("status-message", "children", allow_duplicate=True),
    Input("clear-canvas-btn", "n_clicks"),
    prevent_initial_call=True
)
def clear_canvas(n_clicks):
    """清空画布"""
    empty_flow = {"nodes": [], "edges": []}

    return empty_flow, html.Div([
        "🔄 画布已清空",
        html.Br(),
        html.Small("可以重新开始配置", className="text-muted")
    ], className="alert alert-info")
```

**步骤 2：测试清空功能**

运行：`python app.py`
添加一些节点后点击"清空画布"
预期：画布清空，节点和连线消失

**步骤 3：提交**

```bash
git add frontend/pages/visual_protocol_editor.py
git commit -m "feat: 添加清空画布功能"
```

---

## 任务 11：编写用户文档

**文件:**
- 新建：`docs/visual-editor-user-guide.md`

**步骤 1：创建用户指南**

新建 `docs/visual-editor-user-guide.md`：

```markdown
# 可视化协议编辑器使用指南

## 快速上手（3步配置）

### 第1步：添加设备
1. 从左侧拖拽"📦 设备"节点到画布中央
2. 点击设备节点，在弹窗中配置：
   - 协议类型：选择 Modbus TCP / MQTT / Serial / TCP
   - 设备地址：如 192.168.1.100
   - 端口/从站ID：根据设备填写

### 第2步：添加数据源
1. 拖拽"📨 数据源"节点到画布
2. 连线：从设备节点 → 数据源节点（拖拽数据源右侧的点到设备）
3. 点击数据源节点，配置：
   - 操作类型：如"读取输入寄存器"
   - 起始地址：如 0
   - 读取数量：如 2

### 第3步：添加输出
1. 拖拽"📤 输出"节点到画布
2. 连线：从数据源/转换节点 → 输出节点
3. 点击输出节点，配置：
   - 字段名：如 weight、temperature
   - 单位：如 kg、°C
   - 小数位数：如 2

### 第4步：保存并测试
1. 在顶部输入模板名称
2. 查看右侧JSON预览（实时生成）
3. 点击"💾 保存模板"
4. 可选：点击"🧪 测试连接"验证设备通信

---

## 节点类型详解

### 📦 设备节点
**作用**：代表物理设备，配置通信参数

**必填配置**：
- 协议类型（Modbus TCP/RTU、MQTT、Serial、TCP）
- 设备地址（IP地址或主机名）
- 端口号（可选，有默认值）

**示例配置**：
- Modbus TCP：地址 `192.168.1.100`，端口 `502`，从站ID `1`
- MQTT：地址 `localhost`，端口 `1883`

---

### 📨 数据源节点
**作用**：从设备读取原始数据

**必填配置**：
- 操作类型（读取输入/保持寄存器、订阅主题等）
- 起始地址/主题
- 读取数量

**示例配置**：
- Modbus读取：地址 `0`，数量 `2`
- MQTT订阅：主题 `sensor/data`

---

### 🔄 转换节点（可选）
**作用**：处理原始数据，如合并32位、提取字段

**常用转换**：
- 合并32位整数：公式 `A*65536+B`（A是高位，B是低位）
- 四则运算：公式 `A*0.1`（缩放）
- 正则提取：模式 `(?<=value"): (.*)`
- JSON解析：表达式 `$.temperature`

**使用场景**：
- 设备返回两个字节，需要合并为一个32位整数
- 设备返回JSON，需要提取特定字段
- 数据需要单位转换（如从克转为千克）

---

### 📤 输出节点
**作用**：定义最终输出字段

**必填配置**：
- 字段名（如 weight、temperature、humidity）
- 单位（可选，如 kg、°C、%）
- 小数位数（可选，0-4位）

**注意**：
- 可以添加多个输出节点，每个代表一个输出字段
- 输出节点必须是流程的终点

---

## 常见使用场景

### 场景1：Modbus 电子天平
**节点配置**：
1. 📦 设备：Modbus TCP，地址 192.168.1.100
2. 📨 数据源：读取输入寄存器，地址 0，数量 2
3. 🔄 转换：合并32位，公式 A*65536+B
4. 📤 输出：字段 weight，单位 kg

**连线**：设备 → 数据源 → 转换 → 输出

---

### 场景2：MQTT 温湿度传感器
**节点配置**：
1. 📦 设备：MQTT，地址 localhost
2. 📨 数据源：订阅消息，主题 sensor/data
3. 🔄 转换：JSON解析，表达式 $.temperature
4. 📤 输出：字段 temperature，单位 °C

**连线**：设备 → 数据源 → 转换 → 输出

---

### 场景3：多个输出字段
如果设备同时返回温度和湿度：

**方案A：使用两个数据源**
1. 📦 设备
2. 📨 数据源1（读取温度地址）
3. 📨 数据源2（读取湿度地址）
4. 📤 输出1（temperature）
5. 📤 输出2（humidity）

**连线**：设备 → 数据源1 → 输出1，设备 → 数据源2 → 输出2

**方案B：使用转换节点**
1. 📦 设备
2. 📨 数据源（读取多个寄存器）
3. 🔄 转换（拆分数据）
4. 📤 输出1（temperature）
5. 📤 输出2（humidity）

---

## 快捷操作技巧

### 1. 使用预设模板
- 点击左侧"选择预设模板"下拉框
- 选择"奥豪斯电子天平"或"MQTT温湿度传感器"
- 点击"加载模板"自动填充画布
- 根据实际设备调整参数

### 2. 复制JSON到其他编辑器
- 右侧JSON预览可以手动编辑
- 点击"📋 复制JSON"按钮
- 粘贴到"协议编辑器"标签页进行微调

### 3. 调试流程图
- 查看右侧JSON预览是否正确
- 检查节点连线是否正确（数据应该从左流向右）
- 点击"🧪 测试连接"验证设备通信

### 4. 键盘快捷键（React Flow内置）
- Delete：删除选中的节点或连线
- Ctrl+Z：撤销操作
- Ctrl+Y：重做操作
- 方向键：平移画布
- 鼠标滚轮：缩放画布

---

## 故障排查

### 问题1：节点无法拖到画布
**可能原因**：
- 浏览器不支持拖拽API
- React Flow 未正确加载

**解决方案**：
- 刷新页面重试
- 检查浏览器控制台是否有JavaScript错误

### 问题2：连线无法连接
**可能原因**：
- 点击的是节点中心而非连接点
- 连接方向错误（应从源节点拖到目标节点）

**解决方案**：
- 鼠标悬停在节点上，查看出现的连接点（右侧圆点）
- 从源节点的连接点拖拽到目标节点

### 问题3：JSON预览显示错误
**可能原因**：
- 缺少设备节点
- 节点连线不完整
- 配置参数有误

**解决方案**：
- 确保已添加设备节点
- 检查所有节点都有连线
- 点击节点查看配置是否完整

### 问题4：保存失败
**可能原因**：
- 网络连接问题
- 后端服务未启动
- JSON格式有误

**解决方案**：
- 检查后端服务是否运行
- 查看浏览器控制台的网络请求
- 检查右侧JSON预览是否有红色错误提示

---

## 与其他编辑器的对比

| 特性 | 可视化编辑器 | JSON编辑器 | 表单编辑器 |
|-----|-----------|----------|----------|
| 上手难度 | ⭐ 最简单 | ⭐⭐⭐ 最复杂 | ⭐⭐ 中等 |
| 灵活性 | ⭐⭐ 中等 | ⭐⭐⭐ 最灵活 | ⭐⭐ 中等 |
| 适用场景 | 常见设备（80%） | 任何设备（100%） | 常见协议（60%） |
| 学习曲线 | 平缓 | 陡峭 | 平缓 |
| 调试友好 | ⭐⭐⭐ 可视化流程 | ⭐ 需理解JSON | ⭐⭐ 表单验证 |

**建议**：
- 初学者：从可视化编辑器开始，快速上手
- 进阶用户：结合三种编辑器，发挥各自优势
- 复杂协议：使用JSON编辑器，完全控制细节

---

## 下一步

- [ ] 尝试创建自己的第一个协议模板
- [ ] 探索预设模板，了解不同协议配置
- [ ] 在设备管理页面使用可视化创建的模板
- [ ] 遇到问题查看"协议模板JSON指南"文档
```

**步骤 2：测试文档**

运行：`python app.py`
预期：用户指南文档已创建

**步骤 3：提交**

```bash
git add docs/visual-editor-user-guide.md
git commit -m "docs: 添加可视化编辑器用户指南"
```

---

## 任务 12：最终集成测试

**文件:**
- 修改：`app.py`

**步骤 1：确保可视化编辑器标签页可见**

检查 `app.py` 中标签页注册：

```python
# 确保标签页按顺序排列
tabs = [
    dcc.Tab(label="设备管理", value="devices", children=device_management_layout()),
    dcc.Tab(label="协议编辑器", value="protocols", children=protocol_editor_layout()),
    dcc.Tab(label="可视化编辑器", value="visual-protocol", children=visual_protocol_editor.layout()),
    # ... 其他标签页
]
```

**步骤 2：端到端测试**

运行：`python app.py`

测试清单：
1. 访问 `http://localhost:8050?tab=visual-protocol`
   - 预期：页面正常显示，三栏布局清晰

2. 拖拽"📦 设备"节点到画布
   - 预期：节点成功添加到画布

3. 拖拽"📨 数据源"节点到画布
   - 预期：节点成功添加

4. 连接设备 → 数据源
   - 预期：连线成功创建

5. 拖拽"📤 输出"节点并连接
   - 预期：流程图完整，右侧JSON预览生成

6. 点击"💾 保存模板"
   - 预期：显示保存成功提示

7. 切换到"设备管理"标签页
   - 预期：可以看到刚创建的模板

8. 创建设备时选择该模板
   - 预期：设备创建成功，可以正常通信

**步骤 3：回归测试**

确保现有功能未受影响：
- JSON编辑器正常工作
- 表单编辑器正常工作
- 设备管理正常工作
- 手动控制正常工作

运行：`pytest tests/ -v`
预期：所有现有测试通过

**步骤 4：性能检查**

- 页面加载时间 < 3秒
- 拖拽节点响应流畅
- JSON预览实时更新无延迟

**步骤 5：最终提交**

```bash
git add app.py
git commit -m "feat: 完成可视化编辑器集成测试（可选功能，与现有编辑器并存）"
```

---

## 验证步骤

### 1. 启动应用

```bash
cd /Users/n/Code/Quantix-Cnnector
python app.py
```

### 2. 访问可视化编辑器

浏览器打开：`http://localhost:8050?tab=visual-protocol`

检查项：
- ✅ 三栏布局正确显示
- ✅ 左侧节点库显示4种节点
- ✅ 中间画布显示点状背景
- ✅ 右侧JSON预览区域空白

### 3. 创建第一个协议

**步骤**：
1. 拖拽"📦 设备"到画布中央
2. 点击设备节点，选择"Modbus TCP"
3. 填写地址：`192.168.1.100`，端口：`502`，从站ID：`1`
4. 拖拽"📨 数据源"到画布
5. 连线：设备 → 数据源（从数据源右侧的点拖到设备）
6. 点击数据源，选择"读取输入寄存器"，地址：`0`，数量：`2`
7. 拖拽"📤 输出"到画布
8. 连线：数据源 → 输出
9. 点击输出，填写字段名：`weight`，单位：`kg`
10. 查看右侧JSON预览

**预期结果**：
```json
{
  "name": "新协议模板",
  "description": "通过可视化编辑器创建（3个节点）",
  "protocol_type": "modbus_tcp",
  "variables": [],
  "output": {
    "weight": "${{read1.result}}"
  },
  "steps": [
    {
      "id": "read1",
      "name": "读取数据",
      "action": "modbus.read_input_registers",
      "trigger": "poll",
      "params": {
        "address": 0,
        "count": 2,
        "slave_id": 1
      },
      "parse": {
        "type": "raw"
      }
    }
  ]
}
```

### 4. 测试预设模板

**步骤**：
1. 点击左侧"选择预设模板"下拉框
2. 选择"奥豪斯电子天平"
3. 点击"加载模板"
4. 查看画布显示完整的预设流程
5. 查看右侧JSON预览

**预期结果**：
- 画布显示4个节点和3条连线
- JSON预览显示完整的协议模板

### 5. 测试保存功能

**步骤**：
1. 在顶部输入框填写模板名称：`测试电子天平`
2. 点击"💾 保存模板"
3. 查看状态提示

**预期结果**：
- 显示"✅ 模板保存成功！"
- 显示模板ID

### 6. 切换到设备管理验证

**步骤**：
1. 切换到"设备管理"标签页
2. 点击"新建设备"
3. 选择刚创建的"测试电子天平"模板
4. 填写设备信息并保存
5. 测试连接

**预期结果**：
- 设备创建成功
- 可以选择刚创建的协议模板
- 设备通信正常

### 7. 单元测试

```bash
# 测试转换器
pytest tests/test_visual_flow_converter.py -v

# 测试所有功能
pytest tests/ -k visual -v
```

**预期结果**：
- 所有测试通过

---

## 实施注意事项

### 可选功能的定位

**重要**：可视化编辑器是**可选功能**，不替代现有编辑器

- **保留**：JSON编辑器（完整控制）
- **保留**：表单编辑器（快速配置）
- **新增**：可视化编辑器（初学者友好）

用户可以：
- 在可视化编辑器中快速创建模板
- 切换到JSON编辑器进行微调
- 使用表单编辑器填充常用配置

### 与现有系统的兼容性

**完全兼容**：
- 生成的JSON格式与现有格式100%兼容
- 复用现有 ProtocolExecutor
- 复用现有API接口
- 不修改数据库结构

### 扩展性

**未来可以添加**：
- 更多节点类型（条件分支、循环等）
- 更多预设模板（覆盖主流设备）
- 节点模板库（用户自定义）
- AI辅助配置（根据设备型号推荐节点）

### 性能优化

**当前实现**：
- 使用CDN加载React Flow（无需npm构建）
- 实时JSON生成（无性能问题）
- 节点数量 < 20 时流畅

**未来优化**：
- 大型流程图分页渲染
- 虚拟滚动优化
- Web Worker处理复杂计算

---

**计划完成！已保存到 `docs/plans/2026-03-01-visual-protocol-editor.md`**

**执行选项**：

**1. 会话内逐步执行** - 我在这个会话中逐个任务执行，每步评审
**2. 新会话批量执行** - 开启新会话批量执行，定期检查点

您希望哪种方式？或者您想先看看某个具体任务的详细设计？
