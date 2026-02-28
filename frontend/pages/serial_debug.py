from __future__ import annotations

from dash import dcc, html

BAUDRATE_OPTIONS = [
    {"label": "1200", "value": 1200},
    {"label": "2400", "value": 2400},
    {"label": "4800", "value": 4800},
    {"label": "9600", "value": 9600},
    {"label": "19200", "value": 19200},
    {"label": "38400", "value": 38400},
    {"label": "57600", "value": 57600},
    {"label": "115200", "value": 115200},
]

BYTESIZE_OPTIONS = [
    {"label": "5", "value": 5},
    {"label": "6", "value": 6},
    {"label": "7", "value": 7},
    {"label": "8", "value": 8},
]

PARITY_OPTIONS = [
    {"label": "None (N)", "value": "N"},
    {"label": "Even (E)", "value": "E"},
    {"label": "Odd (O)", "value": "O"},
]

STOPBITS_OPTIONS = [
    {"label": "1", "value": 1},
    {"label": "1.5", "value": 1.5},
    {"label": "2", "value": 2},
]

DATA_FORMAT_OPTIONS = [
    {"label": "文本", "value": "text"},
    {"label": "HEX", "value": "hex"},
]

ENCODING_OPTIONS = [
    {"label": "UTF-8", "value": "utf-8"},
    {"label": "ASCII", "value": "ascii"},
]

LINE_ENDING_OPTIONS = [
    {"label": "无", "value": "none"},
    {"label": "CR (\\r)", "value": "cr"},
    {"label": "LF (\\n)", "value": "lf"},
    {"label": "CRLF (\\r\\n)", "value": "crlf"},
]


def help_text(text: str) -> html.Div:
    return html.Div(text, style={"fontSize": "12px", "color": "#666", "marginTop": "4px"})


def layout() -> html.Div:
    return html.Div(
        [
            dcc.Interval(id="serial-debug-interval", interval=1000, n_intervals=0),
            dcc.Store(id="serial-debug-log-store", data=[]),
            dcc.Store(id="serial-debug-log-seq-store", data=0),
            html.H2("串口调试助手"),
            html.Div(
                "可扫描本地串口，配置参数后连接，支持文本/HEX 发送和 RX/TX 实时日志。",
                style={"fontSize": "13px", "color": "#444", "marginBottom": "10px"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("串口"),
                            dcc.Dropdown(
                                id="serial-debug-port",
                                options=[],
                                placeholder="请选择串口",
                                clearable=False,
                                className="qx-dropdown",
                                persistence=True,
                                persistence_type="session",
                            ),
                            help_text("点击“刷新串口”可重新扫描本机串口列表。"),
                        ]
                    ),
                    html.Div(
                        [
                            html.Label("波特率"),
                            dcc.Dropdown(
                                id="serial-debug-baudrate",
                                options=BAUDRATE_OPTIONS,
                                value=9600,
                                clearable=False,
                                className="qx-dropdown",
                                persistence=True,
                                persistence_type="session",
                            ),
                            help_text("与设备串口参数保持一致。"),
                        ]
                    ),
                    html.Div(
                        [
                            html.Label("数据位"),
                            dcc.Dropdown(
                                id="serial-debug-bytesize",
                                options=BYTESIZE_OPTIONS,
                                value=8,
                                clearable=False,
                                className="qx-dropdown",
                                persistence=True,
                                persistence_type="session",
                            ),
                            help_text("常见设备为 8 位。"),
                        ]
                    ),
                    html.Div(
                        [
                            html.Label("校验位"),
                            dcc.Dropdown(
                                id="serial-debug-parity",
                                options=PARITY_OPTIONS,
                                value="N",
                                clearable=False,
                                className="qx-dropdown",
                                persistence=True,
                                persistence_type="session",
                            ),
                            help_text("None / Even / Odd。"),
                        ]
                    ),
                    html.Div(
                        [
                            html.Label("停止位"),
                            dcc.Dropdown(
                                id="serial-debug-stopbits",
                                options=STOPBITS_OPTIONS,
                                value=1,
                                clearable=False,
                                className="qx-dropdown",
                                persistence=True,
                                persistence_type="session",
                            ),
                            help_text("通常为 1。"),
                        ]
                    ),
                    html.Div(
                        [
                            html.Label("读超时（毫秒）"),
                            dcc.Input(
                                id="serial-debug-timeout",
                                type="number",
                                value=300,
                                min=0,
                                step=10,
                                className="qx-input",
                                style={"width": "100%"},
                                persistence=True,
                                persistence_type="session",
                            ),
                            help_text("连接后读取串口的默认超时时间。"),
                        ]
                    ),
                ],
                style={"display": "grid", "gridTemplateColumns": "repeat(3, 1fr)", "gap": "12px"},
            ),
            html.Div(
                [
                    html.Button("刷新串口", id="serial-debug-refresh-btn", n_clicks=0, style={"padding": "8px 14px"}),
                    html.Button("连接", id="serial-debug-open-btn", n_clicks=0, style={"padding": "8px 14px"}),
                    html.Button("断开", id="serial-debug-close-btn", n_clicks=0, style={"padding": "8px 14px"}),
                ],
                style={"display": "flex", "gap": "10px", "marginTop": "10px"},
            ),
            html.Div(id="serial-debug-status", className="serial-debug-status-card"),
            html.Div(id="serial-debug-action-result", style={"marginTop": "6px", "color": "#0f766e"}),
            html.Div(id="serial-debug-ports-error", style={"marginTop": "4px", "color": "#c62828"}),
            html.H3("发送"),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("数据格式"),
                            dcc.Dropdown(
                                id="serial-debug-data-format",
                                options=DATA_FORMAT_OPTIONS,
                                value="text",
                                clearable=False,
                                className="qx-dropdown",
                                persistence=True,
                                persistence_type="session",
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.Label("编码"),
                            dcc.Dropdown(
                                id="serial-debug-encoding",
                                options=ENCODING_OPTIONS,
                                value="utf-8",
                                clearable=False,
                                className="qx-dropdown",
                                persistence=True,
                                persistence_type="session",
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.Label("行结束符"),
                            dcc.Dropdown(
                                id="serial-debug-line-ending",
                                options=LINE_ENDING_OPTIONS,
                                value="none",
                                clearable=False,
                                className="qx-dropdown",
                                persistence=True,
                                persistence_type="session",
                            ),
                        ]
                    ),
                ],
                style={"display": "grid", "gridTemplateColumns": "repeat(3, 1fr)", "gap": "12px"},
            ),
            dcc.Textarea(
                id="serial-debug-send-data",
                value="",
                placeholder="输入要发送的数据（文本或HEX）",
                style={"width": "100%", "height": "110px", "marginTop": "8px"},
                persistence=True,
                persistence_type="session",
            ),
            html.Div(
                [
                    html.Button("发送", id="serial-debug-send-btn", n_clicks=0, style={"padding": "8px 14px"}),
                    html.Div(id="serial-debug-send-result", style={"color": "#0f766e"}),
                ],
                style={"display": "flex", "alignItems": "center", "gap": "12px", "marginTop": "8px"},
            ),
            html.H3("接收日志"),
            html.Div(id="serial-debug-recv-error", style={"color": "#c62828", "marginBottom": "6px"}),
            html.Button("清空日志", id="serial-debug-clear-log-btn", n_clicks=0, style={"padding": "6px 12px", "marginBottom": "8px"}),
            html.Pre(
                id="serial-debug-log",
                children="暂无串口日志",
                className="serial-debug-log-box",
                style={
                    "padding": "10px",
                    "minHeight": "220px",
                    "maxHeight": "360px",
                    "overflowY": "auto",
                    "background": "#0f172a",
                    "color": "#e2e8f0",
                    "borderRadius": "8px",
                    "whiteSpace": "pre-wrap",
                    "wordBreak": "break-word",
                    "fontSize": "13px",
                },
            ),
        ]
    )
