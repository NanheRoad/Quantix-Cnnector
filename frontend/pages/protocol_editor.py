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
            dcc.Store(id="protocol-preset-last-type", data=None, storage_type="session"),
            html.H2("协议模板管理"),
            html.Div(
                "可创建、编辑、删除协议模板。若模板已被设备绑定，后端会拒绝修改和删除。",
                style={"fontSize": "13px", "color": "#444", "marginBottom": "10px"},
            ),
            html.Div(id="protocols-error", style={"color": "#c62828", "marginBottom": "8px"}),
            html.Div(id="protocols-list", style={"marginBottom": "20px"}),
            html.H3("创建模板"),
            html.Div(
                [
                    html.Label("模板名称"),
                    dcc.Input(
                        id="protocol-name",
                        type="text",
                        className="qx-input",
                        style={"width": "100%"},
                        persistence=True,
                        persistence_type="session",
                    ),
                    help_text("建议包含设备品牌/型号，便于复用。"),
                ]
            ),
            html.Div(
                [
                    html.Label("模板描述"),
                    dcc.Input(
                        id="protocol-desc",
                        type="text",
                        className="qx-input",
                        style={"width": "100%"},
                        persistence=True,
                        persistence_type="session",
                    ),
                    help_text("描述适配设备、采集方式和注意事项。"),
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
                        persistence=True,
                        persistence_type="session",
                    ),
                    help_text("优先使用下拉枚举值，避免手写拼写错误。"),
                ],
                style={"marginTop": "8px"},
            ),
            html.Div(
                id="protocol-template-help",
                style={
                    "marginTop": "8px",
                    "padding": "10px",
                    "background": "#f8fafc",
                    "border": "1px solid #e2e8f0",
                    "borderRadius": "8px",
                },
            ),
            html.Div(
                [
                    html.Label("模板 JSON"),
                    dcc.Textarea(
                        id="protocol-template-json",
                        value="{}",
                        style={"width": "100%", "height": "220px"},
                        persistence=True,
                        persistence_type="session",
                    ),
                    help_text("可按需修改 steps/setup_steps/message_handler/output。"),
                ],
                style={"marginTop": "8px"},
            ),
            html.Button(
                "创建模板",
                id="create-protocol-btn",
                n_clicks=0,
                className="qx-btn qx-btn-primary",
                style={"marginTop": "12px"},
            ),
            html.Div(id="create-protocol-result", style={"marginTop": "8px"}),
            html.Hr(style={"margin": "20px 0"}),
            html.H3("编辑或删除模板"),
            html.Div(
                [
                    html.Label("选择已有模板"),
                    dcc.Dropdown(
                        id="protocol-edit-id",
                        options=[],
                        placeholder="请选择要编辑的模板",
                        clearable=True,
                        className="qx-dropdown",
                        persistence=True,
                        persistence_type="session",
                    ),
                    help_text("仅未被设备绑定的模板允许修改/删除。"),
                ]
            ),
            html.Div(
                [
                    html.Label("模板名称"),
                    dcc.Input(
                        id="protocol-edit-name",
                        type="text",
                        className="qx-input",
                        style={"width": "100%"},
                        persistence=True,
                        persistence_type="session",
                    ),
                ],
                style={"marginTop": "8px"},
            ),
            html.Div(
                [
                    html.Label("模板描述"),
                    dcc.Input(
                        id="protocol-edit-desc",
                        type="text",
                        className="qx-input",
                        style={"width": "100%"},
                        persistence=True,
                        persistence_type="session",
                    ),
                ],
                style={"marginTop": "8px"},
            ),
            html.Div(
                [
                    html.Label("协议类型"),
                    dcc.Dropdown(
                        id="protocol-edit-type",
                        options=PROTOCOL_OPTIONS,
                        value="modbus_tcp",
                        clearable=False,
                        className="qx-dropdown",
                        persistence=True,
                        persistence_type="session",
                    ),
                ],
                style={"marginTop": "8px"},
            ),
            html.Div(
                [
                    html.Label("模板 JSON"),
                    dcc.Textarea(
                        id="protocol-edit-template-json",
                        value="{}",
                        style={"width": "100%", "height": "220px"},
                        persistence=True,
                        persistence_type="session",
                    ),
                ],
                style={"marginTop": "8px"},
            ),
            html.Div(
                [
                    html.Button("更新模板", id="protocol-update-btn", n_clicks=0, className="qx-btn qx-btn-secondary"),
                    html.Button("删除模板", id="protocol-delete-btn", n_clicks=0, className="qx-btn qx-btn-danger"),
                ],
                style={"display": "flex", "gap": "10px", "marginTop": "10px"},
            ),
            html.Div(id="protocol-edit-result", style={"marginTop": "8px"}),
        ]
    )
