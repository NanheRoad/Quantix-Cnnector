from __future__ import annotations

from dash import dcc, html


def help_text(text: str) -> html.Div:
    return html.Div(text, style={"fontSize": "12px", "color": "#666", "marginTop": "4px"})


def layout() -> html.Div:
    return html.Div(
        [
            dcc.Interval(id="control-interval", interval=4000, n_intervals=0),
            dcc.Store(id="control-manual-steps-store", data=[]),
            html.H2("设备手动控制"),
            html.Div(
                "说明：本页面仅执行模板中 trigger=manual 的步骤。建议先在协议模板中配置去皮/清零步骤，再使用快捷按钮。",
                style={"fontSize": "13px", "color": "#444", "marginBottom": "10px"},
            ),
            html.Div(id="control-error", style={"color": "#c62828", "marginBottom": "8px"}),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("设备"),
                            dcc.Dropdown(
                                id="control-device-id",
                                options=[],
                                placeholder="请选择设备",
                                clearable=False,
                                className="qx-dropdown",
                            ),
                            help_text("仅显示已启用设备。"),
                        ]
                    ),
                    html.Div(
                        [
                            html.Label("可执行步骤（manual）"),
                            dcc.Dropdown(
                                id="control-step-id",
                                options=[],
                                placeholder="请选择手动步骤",
                                clearable=False,
                                className="qx-dropdown",
                            ),
                            help_text("自定义命令会执行这里选择的步骤。"),
                        ]
                    ),
                ],
                style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "12px"},
            ),
            html.Div(id="control-device-help", style={"marginTop": "8px", "color": "#555"}),
            html.H3("快捷命令"),
            html.Div(
                [
                    html.Button("去皮", id="control-tare-btn", n_clicks=0, className="qx-btn qx-btn-primary"),
                    html.Button("清零", id="control-zero-btn", n_clicks=0, className="qx-btn qx-btn-secondary"),
                ],
                style={"display": "flex", "gap": "10px", "marginBottom": "14px"},
            ),
            html.H3("自定义命令"),
            html.Div(
                [
                    html.Label("参数覆盖（JSON，可选）"),
                    dcc.Textarea(
                        id="control-params-json",
                        value="{}",
                        style={"width": "100%", "height": "120px"},
                    ),
                    help_text("将覆盖模板步骤 params。示例：{\"value\":1}"),
                ]
            ),
            html.Button(
                "执行自定义命令",
                id="control-execute-btn",
                n_clicks=0,
                className="qx-btn qx-btn-neutral",
                style={"marginTop": "12px"},
            ),
            html.Div(id="control-result", style={"marginTop": "10px", "fontWeight": "600"}),
            html.Pre(
                id="control-result-detail",
                style={
                    "marginTop": "8px",
                    "padding": "10px",
                    "background": "#f8fafc",
                    "border": "1px solid #e2e8f0",
                    "borderRadius": "8px",
                    "whiteSpace": "pre-wrap",
                    "wordBreak": "break-all",
                },
            ),
        ]
    )
