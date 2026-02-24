from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import requests
from dash import Dash, Input, Output, State, dcc, html, no_update

from config.settings import settings
from frontend.components.device_card import device_card
from frontend.pages import dashboard as dashboard_page
from frontend.pages import device_config as device_config_page
from frontend.pages import protocol_editor as protocol_editor_page

BACKEND_BASE = f"http://{settings.backend_host}:{settings.backend_port}"
HEADERS = {"X-API-Key": settings.api_key}

DEFAULT_CONNECTION_BY_PROTOCOL: dict[str, dict[str, Any]] = {
    "modbus_tcp": {"host": "127.0.0.1", "port": 502},
    "mqtt": {"host": "127.0.0.1", "port": 1883, "username": None, "password": None},
    "serial": {"port": "/dev/ttyUSB0", "baudrate": 9600, "bytesize": 8, "parity": "N", "stopbits": 1},
    "tcp": {"host": "127.0.0.1", "port": 8000},
}

PROTOCOL_TEMPLATE_PRESETS: dict[str, dict[str, Any]] = {
    "modbus_tcp": {
        "name": "Modbus 模板示例",
        "protocol_type": "modbus_tcp",
        "variables": [
            {"name": "slave_id", "type": "int", "default": 1, "label": "从站地址"},
            {"name": "address", "type": "int", "default": 0, "label": "寄存器地址"},
        ],
        "steps": [
            {
                "id": "read_weight",
                "name": "读取重量",
                "trigger": "poll",
                "action": "modbus.read_input_registers",
                "params": {"slave_id": "${slave_id}", "address": "${address}", "count": 2},
                "parse": {"type": "expression", "expression": "registers[0] * 65536 + registers[1]"},
            }
        ],
        "output": {"weight": "${steps.read_weight.result}", "unit": "kg"},
    },
    "mqtt": {
        "name": "MQTT 模板示例",
        "protocol_type": "mqtt",
        "variables": [{"name": "topic", "type": "string", "default": "sensor/weight", "label": "主题"}],
        "setup_steps": [
            {
                "id": "subscribe",
                "name": "订阅主题",
                "trigger": "setup",
                "action": "mqtt.subscribe",
                "params": {"topic": "${topic}", "qos": 1},
            }
        ],
        "message_handler": {
            "id": "handle_message",
            "name": "处理消息",
            "trigger": "event",
            "action": "mqtt.on_message",
            "parse": {"type": "expression", "expression": "float(payload)"},
        },
        "output": {"weight": "${message_handler.result}", "unit": "kg"},
    },
    "serial": {
        "name": "串口模板示例",
        "protocol_type": "serial",
        "variables": [],
        "steps": [
            {"id": "send_cmd", "name": "发送命令", "trigger": "poll", "action": "serial.send", "params": {"data": "W\\r\\n"}},
            {"id": "wait", "name": "等待", "trigger": "poll", "action": "delay", "params": {"milliseconds": 100}},
            {
                "id": "receive",
                "name": "接收响应",
                "trigger": "poll",
                "action": "serial.receive",
                "params": {"size": 32, "timeout": 1000},
                "parse": {"type": "regex", "pattern": "([0-9.]+)", "group": 1},
            },
        ],
        "output": {"weight": "${steps.receive.result}", "unit": "kg"},
    },
    "tcp": {
        "name": "TCP 模板示例",
        "protocol_type": "tcp",
        "variables": [],
        "steps": [
            {"id": "send", "name": "发送请求", "trigger": "poll", "action": "tcp.send", "params": {"data": "READ\\n"}},
            {
                "id": "receive",
                "name": "接收响应",
                "trigger": "poll",
                "action": "tcp.receive",
                "params": {"size": 64, "timeout": 1000},
                "parse": {"type": "regex", "pattern": "([0-9.]+)", "group": 1},
            },
        ],
        "output": {"weight": "${steps.receive.result}", "unit": "kg"},
    },
}


def pretty_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def api_request(method: str, path: str, **kwargs: Any) -> Any:
    response = requests.request(
        method,
        f"{BACKEND_BASE}{path}",
        headers=HEADERS,
        timeout=5,
        **kwargs,
    )
    response.raise_for_status()
    if response.content:
        return response.json()
    return None


def default_variables_from_template(template: dict[str, Any]) -> dict[str, Any]:
    variables = template.get("variables", [])
    if not isinstance(variables, list):
        return {}

    result: dict[str, Any] = {}
    for item in variables:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not name:
            continue
        result[str(name)] = item.get("default")
    return result


app: Dash = Dash(__name__, suppress_callback_exceptions=True)
app.title = "Quantix Connector"

app.layout = html.Div(
    [
        html.H1("Quantix 设备管理系统", style={"marginBottom": "10px"}),
        html.Div(f"Backend: {BACKEND_BASE}", style={"fontSize": "12px", "color": "#666", "marginBottom": "12px"}),
        dcc.Tabs(
            id="main-tabs",
            value="dashboard",
            children=[
                dcc.Tab(label="实时大屏", value="dashboard"),
                dcc.Tab(label="设备配置", value="devices"),
                dcc.Tab(label="协议模板", value="protocols"),
            ],
        ),
        html.Div(id="tab-content", style={"marginTop": "12px"}),
    ],
    style={"maxWidth": "1200px", "margin": "0 auto", "padding": "16px"},
)


@app.callback(Output("tab-content", "children"), Input("main-tabs", "value"))
def render_tab_content(tab: str):
    if tab == "devices":
        return device_config_page.layout()
    if tab == "protocols":
        return protocol_editor_page.layout()
    return dashboard_page.layout()


@app.callback(
    Output("dashboard-cards", "children"),
    Output("dashboard-error", "children"),
    Input("dashboard-interval", "n_intervals"),
)
def refresh_dashboard(_n: int):
    try:
        devices = api_request("GET", "/api/devices")
        cards = [device_card(item) for item in devices]
        return cards, ""
    except Exception as exc:
        return [], f"加载失败: {exc}"


@app.callback(
    Output("devices-table", "children"),
    Output("devices-error", "children"),
    Input("devices-interval", "n_intervals"),
)
def refresh_devices(_n: int):
    try:
        devices = api_request("GET", "/api/devices")
    except Exception as exc:
        return html.Div(), f"加载失败: {exc}"

    columns = [
        ("ID", "6%"),
        ("名称", "16%"),
        ("模板ID", "10%"),
        ("状态", "10%"),
        ("重量", "10%"),
        ("更新时间", "38%"),
        ("启用", "10%"),
    ]
    header = html.Tr([html.Th(title, style={"width": width}) for title, width in columns])

    rows = []
    for item in devices:
        runtime = item.get("runtime", {})
        rows.append(
            html.Tr(
                [
                    html.Td(item.get("id")),
                    html.Td(item.get("name")),
                    html.Td(item.get("protocol_template_id")),
                    html.Td(runtime.get("status", "offline")),
                    html.Td(runtime.get("weight")),
                    html.Td(runtime.get("timestamp") or "-"),
                    html.Td("是" if item.get("enabled") else "否"),
                ]
            )
        )

    table = html.Table(
        [html.Thead(header), html.Tbody(rows)],
        className="qx-table",
    )
    return table, ""


@app.callback(
    Output("device-template-id", "options"),
    Output("device-template-id", "value"),
    Input("devices-interval", "n_intervals"),
    State("device-template-id", "value"),
)
def load_device_template_options(_n: int, current_value: Any):
    try:
        protocols = api_request("GET", "/api/protocols")
    except Exception:
        return [], no_update

    options = [
        {
            "label": f"#{item['id']} {item['name']} ({item['protocol_type']})",
            "value": item["id"],
        }
        for item in protocols
    ]

    valid_values = {item["value"] for item in options}
    if current_value in valid_values:
        return options, no_update

    first = options[0]["value"] if options else None
    return options, first


@app.callback(
    Output("device-template-help", "children"),
    Output("device-conn", "value"),
    Output("device-vars", "value"),
    Input("device-template-id", "value"),
)
def update_device_template_info(template_id: Any):
    if template_id is None:
        conn = pretty_json(DEFAULT_CONNECTION_BY_PROTOCOL["modbus_tcp"])
        return "请选择协议模板后自动填充说明。", conn, "{}"

    try:
        protocol = api_request("GET", f"/api/protocols/{int(template_id)}")
    except Exception as exc:
        return f"模板加载失败: {exc}", "{}", "{}"

    protocol_type = str(protocol.get("protocol_type", "modbus_tcp"))
    template = protocol.get("template", {})
    defaults = default_variables_from_template(template)
    conn_example = DEFAULT_CONNECTION_BY_PROTOCOL.get(protocol_type, {"host": "127.0.0.1", "port": 0})

    info = html.Div(
        [
            html.Div(f"模板名称：{protocol.get('name', '-')}", style={"fontWeight": "600"}),
            html.Div(f"协议类型：{protocol_type}"),
            html.Div(f"说明：{protocol.get('description') or '无'}"),
            html.Div("提示：连接参数和变量已按模板自动填充，你可以继续手动调整。", style={"fontSize": "12px", "color": "#666", "marginTop": "6px"}),
        ]
    )
    return info, pretty_json(conn_example), pretty_json(defaults)


@app.callback(
    Output("create-device-result", "children"),
    Input("create-device-btn", "n_clicks"),
    State("device-name", "value"),
    State("device-template-id", "value"),
    State("device-poll", "value"),
    State("device-enabled", "value"),
    State("device-conn", "value"),
    State("device-vars", "value"),
    prevent_initial_call=True,
)
def create_device(
    _n: int,
    name: str,
    template_id: int,
    poll_rate_hz: float,
    enabled: str,
    connection_json: str,
    variables_json: str,
):
    try:
        rate = float(poll_rate_hz or 0)
        if rate <= 0:
            return "创建失败: 采集频率必须大于 0（单位：次/秒）"

        poll_interval = 1.0 / rate
        payload = {
            "name": name,
            "protocol_template_id": int(template_id),
            "connection_params": json.loads(connection_json or "{}"),
            "template_variables": json.loads(variables_json or "{}"),
            "poll_interval": poll_interval,
            "enabled": str(enabled).lower() == "true",
        }
        created = api_request("POST", "/api/devices", json=payload)
        return f"创建成功: device_id={created['id']}"
    except Exception as exc:
        return f"创建失败: {exc}"


@app.callback(
    Output("protocols-list", "children"),
    Output("protocols-error", "children"),
    Input("protocols-interval", "n_intervals"),
)
def refresh_protocols(_n: int):
    try:
        protocols = api_request("GET", "/api/protocols")
    except Exception as exc:
        return html.Div(), f"加载失败: {exc}"

    rows = [html.Li(f"#{item['id']} {item['name']} ({item['protocol_type']})") for item in protocols]
    return html.Ul(rows), ""


@app.callback(
    Output("protocol-template-json", "value"),
    Output("protocol-template-help", "children"),
    Input("protocol-type", "value"),
)
def load_protocol_preset(protocol_type: str):
    normalized = str(protocol_type or "modbus_tcp")
    preset = deepcopy(PROTOCOL_TEMPLATE_PRESETS.get(normalized, PROTOCOL_TEMPLATE_PRESETS["modbus_tcp"]))

    if normalized == "mqtt":
        text = "MQTT 模板采用 setup_steps + message_handler。setup 负责订阅，message_handler 负责解析消息。"
    else:
        text = "轮询协议模板建议使用 steps + trigger=poll；写操作步骤建议设置 trigger=manual。"

    return pretty_json(preset), text


@app.callback(
    Output("create-protocol-result", "children"),
    Input("create-protocol-btn", "n_clicks"),
    State("protocol-name", "value"),
    State("protocol-desc", "value"),
    State("protocol-type", "value"),
    State("protocol-template-json", "value"),
    prevent_initial_call=True,
)
def create_protocol(_n: int, name: str, description: str, protocol_type: str, template_json: str):
    try:
        template = json.loads(template_json or "{}")
        template["name"] = template.get("name") or name
        template["protocol_type"] = protocol_type

        payload = {
            "name": name,
            "description": description,
            "protocol_type": protocol_type,
            "template": template,
            "is_system": False,
        }
        created = api_request("POST", "/api/protocols", json=payload)
        return f"创建成功: protocol_id={created['id']}"
    except Exception as exc:
        return f"创建失败: {exc}"


if __name__ == "__main__":
    app.run(host=settings.frontend_host, port=settings.frontend_port, debug=True)
