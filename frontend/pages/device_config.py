from __future__ import annotations

from dash import dcc, html

ENABLE_OPTIONS = [
    {"label": "启用", "value": "true"},
    {"label": "禁用", "value": "false"},
]


def help_text(text: str) -> html.Div:
    return html.Div(text, style={"fontSize": "12px", "color": "#666", "marginTop": "4px"})


def field_block(children: list) -> html.Div:
    return html.Div(children, style={"display": "flex", "flexDirection": "column", "minHeight": "94px"})


def layout() -> html.Div:
    return html.Div(
        [
            dcc.Interval(id="devices-interval", interval=3000, n_intervals=0),
            html.H2("设备配置"),
            html.Div("说明：设备创建时先选择协议模板，系统会自动填充连接参数与模板变量。", style={"fontSize": "13px", "color": "#444", "marginBottom": "10px"}),
            html.Div(id="devices-error", style={"color": "#c62828", "marginBottom": "8px"}),
            html.Div(id="devices-table", style={"marginBottom": "20px"}),
            html.H3("新建设备"),
            html.Div(
                [
                    field_block(
                        [
                            html.Label("设备名称"),
                            dcc.Input(id="device-name", type="text", className="qx-input", style={"width": "100%"}),
                            help_text("示例：电子台秤-01，用于大屏和日志标识。"),
                        ]
                    ),
                    field_block(
                        [
                            html.Label("协议模板"),
                            dcc.Dropdown(
                                id="device-template-id",
                                options=[],
                                placeholder="请选择协议模板",
                                clearable=False,
                                className="qx-dropdown",
                            ),
                            help_text("下拉仅显示系统内可用模板。"),
                        ]
                    ),
                    field_block(
                        [
                            html.Label("采集频率（次/秒）"),
                            dcc.Input(
                                id="device-poll",
                                type="number",
                                value=1.0,
                                min=0.1,
                                step=0.1,
                                className="qx-input",
                                style={"width": "100%"},
                            ),
                            help_text("请输入每秒采集次数。系统内部会转换为采集间隔：间隔(秒)=1/频率。"),
                        ]
                    ),
                    field_block(
                        [
                            html.Label("启用状态"),
                            dcc.Dropdown(
                                id="device-enabled",
                                options=ENABLE_OPTIONS,
                                value="true",
                                clearable=False,
                                className="qx-dropdown",
                            ),
                            help_text("禁用后设备不会启动采集任务。"),
                        ]
                    ),
                ],
                style={"display": "grid", "gridTemplateColumns": "repeat(2, 1fr)", "gap": "12px"},
            ),
            html.Div(id="device-template-help", style={"marginTop": "10px", "padding": "10px", "background": "#f8fafc", "border": "1px solid #e2e8f0", "borderRadius": "8px"}),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("连接参数（JSON）"),
                            dcc.Textarea(id="device-conn", value='{"host":"127.0.0.1","port":502}', style={"width": "100%", "height": "140px"}),
                            help_text("系统会根据模板自动填充示例，可按现场网络/串口参数调整。"),
                        ]
                    ),
                    html.Div(
                        [
                            html.Label("模板变量（JSON）"),
                            dcc.Textarea(id="device-vars", value='{"slave_id":1,"address":0}', style={"width": "100%", "height": "140px"}),
                            help_text("变量来源于模板定义，例如 slave_id、寄存器地址、topic。"),
                        ]
                    ),
                ],
                style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "12px", "marginTop": "12px"},
            ),
            html.Button("创建", id="create-device-btn", n_clicks=0, style={"marginTop": "12px"}),
            html.Div(id="create-device-result", style={"marginTop": "8px"}),
        ]
    )
