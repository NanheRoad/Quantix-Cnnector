from __future__ import annotations

from dash import dcc, html


PROTOCOL_OPTIONS = [
    {"label": "Modbus TCP", "value": "modbus_tcp"},
    {"label": "Modbus RTU（串口）", "value": "modbus_rtu"},
    {"label": "MQTT（推送）", "value": "mqtt"},
    {"label": "Serial（串口）", "value": "serial"},
    {"label": "TCP（原始）", "value": "tcp"},
]


def help_text(text: str) -> html.Div:
    return html.Div(text, style={"fontSize": "12px", "color": "#666", "marginTop": "4px"})


def layout() -> html.Div:
    return html.Div(
        [
            dcc.Interval(id="protocols-interval", interval=5000, n_intervals=0),
            html.H2("协议模板管理"),
            html.Div("说明：先选择协议类型，下方会自动加载对应模板示例，再按设备协议细节调整。", style={"fontSize": "13px", "color": "#444", "marginBottom": "10px"}),
            html.Div(id="protocols-error", style={"color": "#c62828", "marginBottom": "8px"}),
            html.Div(id="protocols-list", style={"marginBottom": "20px"}),
            html.H3("创建协议模板"),
            html.Div(
                [
                    html.Label("模板名称"),
                    dcc.Input(id="protocol-name", type="text", className="qx-input", style={"width": "100%"}),
                    help_text("建议包含设备品牌或型号，便于复用。"),
                ]
            ),
            html.Div(
                [
                    html.Label("模板描述"),
                    dcc.Input(id="protocol-desc", type="text", className="qx-input", style={"width": "100%"}),
                    help_text("用于说明适用设备、采集方式和注意事项。"),
                ],
                style={"marginTop": "8px"},
            ),
            html.Div(
                [
                    html.Label("协议类型"),
                    dcc.Dropdown(
                        id="protocol-type",
                        options=PROTOCOL_OPTIONS,
                        value="modbus_tcp",
                        clearable=False,
                        className="qx-dropdown",
                    ),
                    help_text("可选协议使用下拉固定值，避免手写拼写错误。"),
                ],
                style={"marginTop": "8px"},
            ),
            html.Div(id="protocol-template-help", style={"marginTop": "8px", "padding": "10px", "background": "#f8fafc", "border": "1px solid #e2e8f0", "borderRadius": "8px"}),
            html.Div(
                [
                    html.Label("模板 JSON"),
                    dcc.Textarea(id="protocol-template-json", value="{}", style={"width": "100%", "height": "220px"}),
                    help_text("可在示例基础上修改 action、params、parse、trigger。"),
                ],
                style={"marginTop": "8px"},
            ),
            html.Button("创建模板", id="create-protocol-btn", n_clicks=0, style={"marginTop": "12px"}),
            html.Div(id="create-protocol-result", style={"marginTop": "8px"}),
        ]
    )
