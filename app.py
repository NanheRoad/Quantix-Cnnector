from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import requests
import dash
from dash import Dash, Input, Output, State, dcc, html, no_update, ALL

from config.settings import settings
from frontend.components.device_card import device_card
from frontend.pages import dashboard as dashboard_page
from frontend.pages import device_config as device_config_page
from frontend.pages import manual_control as manual_control_page
from frontend.pages import protocol_editor as protocol_editor_page
from frontend.pages import serial_debug as serial_debug_page
from frontend.time_utils import format_timestamp

BACKEND_BASE = f"http://{settings.backend_host}:{settings.backend_port}"
HEADERS = {"X-API-Key": settings.api_key}

DEFAULT_CONNECTION_BY_PROTOCOL: dict[str, dict[str, Any]] = {
    "modbus_tcp": {"host": "127.0.0.1", "port": 502},
    "modbus_rtu": {"port": "/dev/ttyUSB0", "baudrate": 9600, "bytesize": 8, "parity": "N", "stopbits": 1},
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
    "modbus_rtu": {
        "name": "Modbus RTU 模板示例",
        "protocol_type": "modbus_rtu",
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
        "variables": [
            {"name": "data_topic", "type": "string", "default": "sensor/weight", "label": "数据主题"},
            {"name": "cmd_topic", "type": "string", "default": "sensor/weight/cmd", "label": "控制主题"},
            {"name": "qos", "type": "int", "default": 1, "label": "QoS"},
        ],
        "setup_steps": [
            {
                "id": "subscribe",
                "name": "订阅主题",
                "trigger": "setup",
                "action": "mqtt.subscribe",
                "params": {"topic": "${data_topic}", "qos": "${qos}"},
            }
        ],
        "steps": [
            {
                "id": "tare",
                "name": "去皮",
                "trigger": "manual",
                "action": "mqtt.publish",
                "params": {"topic": "${cmd_topic}", "payload": "{\"cmd\":\"tare\"}", "qos": "${qos}"},
            },
            {
                "id": "zero",
                "name": "清零",
                "trigger": "manual",
                "action": "mqtt.publish",
                "params": {"topic": "${cmd_topic}", "payload": "{\"cmd\":\"zero\"}", "qos": "${qos}"},
            },
        ],
        "message_handler": {
            "id": "handle_message",
            "name": "处理消息",
            "trigger": "event",
            "action": "mqtt.on_message",
            "parse": {
                "type": "regex",
                "pattern": "\"weight\"\\s*:\\s*([-+]?[0-9]*\\.?[0-9]+)",
                "group": 1,
            },
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
    if response.status_code >= 400:
        detail = response.text
        try:
            payload = response.json()
            if isinstance(payload, dict):
                detail = str(payload.get("detail") or payload)
        except Exception:
            pass
        raise requests.HTTPError(f"{response.status_code} {detail}", response=response)
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


def extract_manual_steps(template: dict[str, Any]) -> list[dict[str, str]]:
    steps = template.get("steps", [])
    if not isinstance(steps, list):
        return []

    result: list[dict[str, str]] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        if step.get("trigger", "poll") != "manual":
            continue
        step_id = str(step.get("id", "")).strip()
        if not step_id:
            continue
        result.append(
            {
                "id": step_id,
                "name": str(step.get("name", step_id)),
                "action": str(step.get("action", "")),
            }
        )
    return result


def find_quick_step_id(manual_steps: list[dict[str, str]], command: str) -> str | None:
    if command == "tare":
        keywords = ["tare", "去皮"]
    elif command == "zero":
        keywords = ["zero", "清零", "归零", "置零"]
    else:
        return None

    for step in manual_steps:
        text = f"{step.get('id', '')} {step.get('name', '')} {step.get('action', '')}".lower()
        if any(keyword in text for keyword in keywords):
            return step.get("id")
    return None


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
                dcc.Tab(label="手动控制", value="control"),
                dcc.Tab(label="协议模板", value="protocols"),
                dcc.Tab(label="串口调试", value="serial_debug"),
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
    if tab == "control":
        return manual_control_page.layout()
    if tab == "protocols":
        return protocol_editor_page.layout()
    if tab == "serial_debug":
        return serial_debug_page.layout()
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
        ("名称", "14%"),
        ("模板ID", "10%"),
        ("状态", "10%"),
        ("重量", "10%"),
        ("更新时间", "28%"),
        ("启用", "8%"),
        ("操作", "14%"),
    ]
    header = html.Tr([html.Th(title, style={"width": width}) for title, width in columns])

    rows = []
    for item in devices:
        device_id = item.get("id")
        runtime = item.get("runtime", {})
        rows.append(
            html.Tr(
                [
                    html.Td(device_id),
                    html.Td(item.get("name")),
                    html.Td(item.get("protocol_template_id")),
                    html.Td(runtime.get("status", "offline")),
                    html.Td(runtime.get("weight")),
                    html.Td(format_timestamp(runtime.get("timestamp"))),
                    html.Td("是" if item.get("enabled") else "否"),
                    html.Td(
                        html.Button(
                            "删除",
                            id={"type": "delete-device-btn", "index": device_id},
                            n_clicks=0,
                            style={
                                "padding": "4px 12px",
                                "backgroundColor": "#dc2626",
                                "color": "white",
                                "border": "none",
                                "borderRadius": "4px",
                                "cursor": "pointer",
                                "fontSize": "12px",
                            },
                        ),
                        style={"textAlign": "center"},
                    ),
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
            html.Div(
                "连接参数和变量已按模板默认值自动填充，你可以继续手动调整。",
                style={"fontSize": "12px", "color": "#666", "marginTop": "6px"},
            ),
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
    Output("delete-device-result", "children"),
    Input({"type": "delete-device-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def delete_device(clicks: list[int]):
    """删除设备。"""
    ctx = dash.callback_context
    if not ctx.triggered:
        return ""

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    # 解析设备ID (格式: {"type":"delete-device-btn","index":123})
    import ast
    try:
        button_info = ast.literal_eval(button_id)
        device_id = button_info.get("index")
        if device_id is None:
            return "删除失败: 无效的设备ID"
    except Exception:
        return "删除失败: 无法解析设备ID"

    # 检查是否真的点击了（n_clicks > 0）
    triggered_index = ctx.triggered[0]["value"]
    if triggered_index is None or triggered_index == 0:
        return ""

    try:
        api_request("DELETE", f"/api/devices/{device_id}")
        return f"删除成功: device_id={device_id}"
    except Exception as exc:
        return f"删除失败: {exc}"


@app.callback(
    Output("control-device-id", "options"),
    Output("control-device-id", "value"),
    Output("control-error", "children"),
    Input("control-interval", "n_intervals"),
    State("control-device-id", "value"),
)
def refresh_control_devices(_n: int, current_value: Any):
    try:
        devices = api_request("GET", "/api/devices")
    except Exception as exc:
        return [], no_update, f"加载设备失败: {exc}"

    enabled_devices = [item for item in devices if item.get("enabled")]
    options = [
        {
            "label": f"#{item['id']} {item['name']} ({item.get('runtime', {}).get('status', 'offline')})",
            "value": item["id"],
        }
        for item in enabled_devices
    ]

    if not options:
        return [], None, "暂无已启用设备。"

    valid_values = {item["value"] for item in options}
    if current_value in valid_values:
        return options, no_update, ""
    return options, options[0]["value"], ""


@app.callback(
    Output("control-step-id", "options"),
    Output("control-step-id", "value"),
    Output("control-device-help", "children"),
    Output("control-manual-steps-store", "data"),
    Input("control-device-id", "value"),
)
def load_control_manual_steps(device_id: Any):
    if device_id is None:
        return [], None, "请选择设备。", []

    try:
        device = api_request("GET", f"/api/devices/{int(device_id)}")
        protocol_id = int(device.get("protocol_template_id"))
        protocol = api_request("GET", f"/api/protocols/{protocol_id}")
    except Exception as exc:
        return [], None, f"加载手动步骤失败: {exc}", []

    manual_steps = extract_manual_steps(protocol.get("template", {}))
    step_options = [
        {
            "label": f"{step['name']} ({step['id']}) [{step['action']}]",
            "value": step["id"],
        }
        for step in manual_steps
    ]

    tare_step_id = find_quick_step_id(manual_steps, "tare")
    zero_step_id = find_quick_step_id(manual_steps, "zero")

    info = html.Div(
        [
            html.Div(f"设备：#{device['id']} {device['name']}"),
            html.Div(f"手动步骤数量：{len(step_options)}"),
            html.Div(f"快捷去皮：{tare_step_id or '未匹配'}"),
            html.Div(f"快捷清零：{zero_step_id or '未匹配'}"),
        ]
    )

    first_step = step_options[0]["value"] if step_options else None
    return step_options, first_step, info, manual_steps


@app.callback(
    Output("control-result", "children"),
    Output("control-result-detail", "children"),
    Input("control-tare-btn", "n_clicks"),
    Input("control-zero-btn", "n_clicks"),
    Input("control-execute-btn", "n_clicks"),
    State("control-device-id", "value"),
    State("control-step-id", "value"),
    State("control-params-json", "value"),
    State("control-manual-steps-store", "data"),
    prevent_initial_call=True,
)
def execute_manual_command(
    _tare_clicks: int,
    _zero_clicks: int,
    _execute_clicks: int,
    device_id: Any,
    selected_step_id: Any,
    params_json: str,
    manual_steps_data: Any,
):
    ctx = dash.callback_context
    if not ctx.triggered:
        return no_update, no_update

    if device_id is None:
        return "执行失败: 请先选择设备。", ""

    try:
        params = json.loads(params_json or "{}")
    except json.JSONDecodeError as exc:
        return f"执行失败: 参数 JSON 格式错误: {exc}", ""

    if not isinstance(params, dict):
        return "执行失败: 参数必须是 JSON 对象，例如 {\"value\":1}。", ""

    manual_steps: list[dict[str, str]] = []
    if isinstance(manual_steps_data, list):
        for item in manual_steps_data:
            if not isinstance(item, dict):
                continue
            manual_steps.append(
                {
                    "id": str(item.get("id", "")),
                    "name": str(item.get("name", "")),
                    "action": str(item.get("action", "")),
                }
            )

    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    target_step_id: str | None = None
    command_name = "自定义命令"

    if triggered_id == "control-tare-btn":
        command_name = "去皮"
        target_step_id = find_quick_step_id(manual_steps, "tare")
        if not target_step_id:
            return "执行失败: 未匹配到“去皮”手动步骤，请在模板中配置 trigger=manual 的去皮步骤。", ""
    elif triggered_id == "control-zero-btn":
        command_name = "清零"
        target_step_id = find_quick_step_id(manual_steps, "zero")
        if not target_step_id:
            return "执行失败: 未匹配到“清零”手动步骤，请在模板中配置 trigger=manual 的清零步骤。", ""
    elif triggered_id == "control-execute-btn":
        if not selected_step_id:
            return "执行失败: 请先选择手动步骤。", ""
        target_step_id = str(selected_step_id)
    else:
        return no_update, no_update

    try:
        result = api_request(
            "POST",
            f"/api/devices/{int(device_id)}/execute",
            json={"step_id": target_step_id, "params": params},
        )
        return f"执行成功: {command_name} ({target_step_id})", pretty_json(result)
    except Exception as exc:
        return f"执行失败: {exc}", ""


@app.callback(
    Output("protocols-list", "children"),
    Output("protocols-error", "children"),
    Output("protocol-edit-id", "options"),
    Output("protocol-edit-id", "value"),
    Input("protocols-interval", "n_intervals"),
    State("protocol-edit-id", "value"),
)
def refresh_protocols(_n: int, current_edit_id: Any):
    try:
        protocols = api_request("GET", "/api/protocols")
        devices = api_request("GET", "/api/devices")
    except Exception as exc:
        return html.Div(), f"加载失败: {exc}", [], no_update

    usage_count: dict[int, int] = {}
    for item in devices:
        try:
            template_id = int(item.get("protocol_template_id"))
        except Exception:
            continue
        usage_count[template_id] = usage_count.get(template_id, 0) + 1

    rows = []
    for item in protocols:
        template_id = int(item.get("id", 0))
        rows.append(
            html.Tr(
                [
                    html.Td(template_id),
                    html.Td(item.get("name")),
                    html.Td(item.get("protocol_type")),
                    html.Td(item.get("description") or "-"),
                    html.Td(usage_count.get(template_id, 0)),
                    html.Td("是" if item.get("is_system") else "否"),
                ]
            )
        )

    table = html.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("ID"),
                        html.Th("名称"),
                        html.Th("协议类型"),
                        html.Th("描述"),
                        html.Th("绑定设备数"),
                        html.Th("系统模板"),
                    ]
                )
            ),
            html.Tbody(rows),
        ],
        className="qx-table",
    )

    options = [
        {
            "label": f"#{item['id']} {item['name']} ({item['protocol_type']})",
            "value": item["id"],
        }
        for item in protocols
    ]
    valid_ids = {item["value"] for item in options}
    if current_edit_id in valid_ids:
        return table, "", options, no_update
    return table, "", options, None


@app.callback(
    Output("protocol-template-json", "value"),
    Output("protocol-template-help", "children"),
    Output("protocol-preset-last-type", "data"),
    Input("protocol-type", "value"),
    State("protocol-template-json", "value"),
    State("protocol-preset-last-type", "data"),
)
def load_protocol_preset(protocol_type: str, current_json: str | None, last_type: str | None):
    normalized = str(protocol_type or "modbus_tcp")
    preset = deepcopy(PROTOCOL_TEMPLATE_PRESETS.get(normalized, PROTOCOL_TEMPLATE_PRESETS["modbus_tcp"]))

    if normalized == "mqtt":
        text = "MQTT 模板建议使用 setup_steps + message_handler。setup 负责订阅，message_handler 负责解析消息。"
    else:
        text = "轮询协议模板建议使用 steps + trigger=poll；写操作步骤建议设置 trigger=manual。"

    # Keep user-edited JSON when returning to same tab/type.
    # Reset to preset only when protocol type actually changes.
    current_text = str(current_json or "").strip()
    previous_type = str(last_type or "").strip()

    if previous_type and previous_type == normalized:
        return no_update, text, normalized

    if (not previous_type) and current_text and current_text != "{}":
        return no_update, text, normalized

    return pretty_json(preset), text, normalized


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


@app.callback(
    Output("protocol-edit-name", "value"),
    Output("protocol-edit-desc", "value"),
    Output("protocol-edit-type", "value"),
    Output("protocol-edit-template-json", "value"),
    Input("protocol-edit-id", "value"),
)
def load_protocol_for_edit(protocol_id: Any):
    if not protocol_id:
        return "", "", "modbus_tcp", "{}"

    try:
        protocol = api_request("GET", f"/api/protocols/{int(protocol_id)}")
    except Exception:
        return "", "", "modbus_tcp", "{}"

    template = protocol.get("template", {})
    return (
        str(protocol.get("name") or ""),
        str(protocol.get("description") or ""),
        str(protocol.get("protocol_type") or "modbus_tcp"),
        pretty_json(template),
    )


@app.callback(
    Output("protocol-edit-result", "children"),
    Input("protocol-update-btn", "n_clicks"),
    Input("protocol-delete-btn", "n_clicks"),
    State("protocol-edit-id", "value"),
    State("protocol-edit-name", "value"),
    State("protocol-edit-desc", "value"),
    State("protocol-edit-type", "value"),
    State("protocol-edit-template-json", "value"),
    prevent_initial_call=True,
)
def update_or_delete_protocol(
    _update_clicks: int,
    _delete_clicks: int,
    protocol_id: Any,
    name: str,
    description: str,
    protocol_type: str,
    template_json: str,
):
    if not protocol_id:
        return "请先选择模板"

    ctx = dash.callback_context
    if not ctx.triggered:
        return no_update

    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

    try:
        if triggered_id == "protocol-delete-btn":
            api_request("DELETE", f"/api/protocols/{int(protocol_id)}")
            return f"删除成功: protocol_id={int(protocol_id)}"

        template = json.loads(template_json or "{}")
        template["name"] = template.get("name") or (name or "")
        template["protocol_type"] = protocol_type

        payload = {
            "name": name,
            "description": description,
            "protocol_type": protocol_type,
            "template": template,
        }
        updated = api_request("PUT", f"/api/protocols/{int(protocol_id)}", json=payload)
        return f"更新成功: protocol_id={updated['id']}"
    except Exception as exc:
        if triggered_id == "protocol-delete-btn":
            return f"删除失败: {exc}"
        return f"更新失败: {exc}"


def _normalize_serial_log_text(text: str) -> str:
    return text.replace("\r", "\\r").replace("\n", "\\n")


def _build_serial_status_view(status: dict[str, Any]) -> html.Div:
    settings_data = status.get("settings", {})
    connected = bool(status.get("connected"))
    badge_text = "已连接" if connected else "未连接"
    badge_class = "serial-debug-status-badge connected" if connected else "serial-debug-status-badge disconnected"

    info = [
        f"串口: {settings_data.get('port', '-')}",
        (
            f"波特率/数据位/校验位/停止位: "
            f"{settings_data.get('baudrate', '-')}/{settings_data.get('bytesize', '-')}/"
            f"{settings_data.get('parity', '-')}/{settings_data.get('stopbits', '-')}"
        ),
        f"超时: {settings_data.get('timeout_ms', '-')} ms",
    ]

    last_error = status.get("last_error")
    if last_error:
        info.append(f"最近错误: {last_error}")

    return html.Div(
        [
            html.Div(html.Span(badge_text, className=badge_class), style={"marginBottom": "8px"}),
            html.Div([html.Div(line, style={"fontSize": "13px", "lineHeight": "1.5"}) for line in info]),
        ]
    )


def _format_serial_log_entry(entry: dict[str, Any]) -> str:
    ts = format_timestamp(entry.get("timestamp"))
    direction = str(entry.get("direction") or "?")
    bytes_count = int(entry.get("bytes", 0))
    text = _normalize_serial_log_text(str(entry.get("text") or ""))
    payload_hex = str(entry.get("hex") or "")
    if text:
        return f"[{ts}] {direction} {bytes_count}B: {text} | HEX: {payload_hex}"
    return f"[{ts}] {direction} {bytes_count}B | HEX: {payload_hex}"


@app.callback(
    Output("serial-debug-port", "options"),
    Output("serial-debug-port", "value"),
    Output("serial-debug-ports-error", "children"),
    Input("serial-debug-refresh-btn", "n_clicks"),
    State("serial-debug-port", "value"),
)
def refresh_serial_ports(_refresh_clicks: int, current_value: Any):
    try:
        result = api_request("GET", "/api/serial-debug/ports")
        ports = result.get("ports", [])
    except Exception as exc:
        return [], no_update, f"扫描串口失败: {exc}"

    options = [
        {
            "label": f"{item.get('device')} - {item.get('description') or item.get('name') or ''}",
            "value": item.get("device"),
        }
        for item in ports
        if item.get("device")
    ]
    valid_values = {item["value"] for item in options}
    if current_value in valid_values:
        return options, no_update, ""
    first = options[0]["value"] if options else None
    return options, first, ""


@app.callback(
    Output("serial-debug-action-result", "children"),
    Input("serial-debug-open-btn", "n_clicks"),
    Input("serial-debug-close-btn", "n_clicks"),
    State("serial-debug-port", "value"),
    State("serial-debug-baudrate", "value"),
    State("serial-debug-bytesize", "value"),
    State("serial-debug-parity", "value"),
    State("serial-debug-stopbits", "value"),
    State("serial-debug-timeout", "value"),
    prevent_initial_call=True,
)
def serial_debug_connect_action(
    _open_clicks: int,
    _close_clicks: int,
    port: Any,
    baudrate: Any,
    bytesize: Any,
    parity: Any,
    stopbits: Any,
    timeout_ms: Any,
):
    ctx = dash.callback_context
    if not ctx.triggered:
        return ""

    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    try:
        if triggered_id == "serial-debug-open-btn":
            if not port:
                return "连接失败: 请先选择串口。"

            payload = {
                "port": str(port),
                "baudrate": int(baudrate or 9600),
                "bytesize": int(bytesize or 8),
                "parity": str(parity or "N"),
                "stopbits": float(stopbits or 1),
                "timeout_ms": int(timeout_ms or 300),
            }
            result = api_request("POST", "/api/serial-debug/open", json=payload)
            settings_data = result.get("settings", {})
            return (
                "连接成功: "
                f"{settings_data.get('port')} "
                f"{settings_data.get('baudrate')}/{settings_data.get('bytesize')}/"
                f"{settings_data.get('parity')}/{settings_data.get('stopbits')}"
            )

        if triggered_id == "serial-debug-close-btn":
            api_request("POST", "/api/serial-debug/close")
            return "已断开串口连接。"
    except Exception as exc:
        return f"操作失败: {exc}"

    return ""


@app.callback(
    Output("serial-debug-send-result", "children"),
    Input("serial-debug-send-btn", "n_clicks"),
    State("serial-debug-send-data", "value"),
    State("serial-debug-data-format", "value"),
    State("serial-debug-encoding", "value"),
    State("serial-debug-line-ending", "value"),
    prevent_initial_call=True,
)
def send_serial_debug_data(
    _send_clicks: int,
    send_data: Any,
    data_format: Any,
    encoding: Any,
    line_ending: Any,
):
    payload_text = str(send_data or "")
    if not payload_text:
        return "发送失败: 数据为空。"

    try:
        result = api_request(
            "POST",
            "/api/serial-debug/send",
            json={
                "data": payload_text,
                "data_format": str(data_format or "text"),
                "encoding": str(encoding or "utf-8"),
                "line_ending": str(line_ending or "none"),
            },
        )
        return f"发送成功: {result.get('bytes_sent', 0)} 字节，HEX={result.get('payload_hex', '')}"
    except Exception as exc:
        return f"发送失败: {exc}"


@app.callback(
    Output("serial-debug-status", "children"),
    Output("serial-debug-log-store", "data"),
    Output("serial-debug-log", "children"),
    Output("serial-debug-recv-error", "children"),
    Output("serial-debug-log-seq-store", "data"),
    Input("serial-debug-interval", "n_intervals"),
    Input("serial-debug-clear-log-btn", "n_clicks"),
    State("serial-debug-log-store", "data"),
    State("serial-debug-log-seq-store", "data"),
)
def refresh_serial_debug_runtime(_n: int, _clear_clicks: int, stored_logs: Any, log_seq: Any):
    logs: list[str] = []
    if isinstance(stored_logs, list):
        logs = [str(item) for item in stored_logs]

    try:
        seq = int(log_seq or 0)
    except Exception:
        seq = 0

    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else ""
    clear_requested = triggered_id == "serial-debug-clear-log-btn"
    if clear_requested:
        logs = []

    try:
        status = api_request("GET", "/api/serial-debug/status")
    except Exception as exc:
        log_text = "\n".join(logs) if logs else "暂无串口日志"
        return f"状态查询失败: {exc}", logs, log_text, "", seq

    recv_error = ""
    connected = bool(status.get("connected"))
    if connected and not clear_requested:
        try:
            api_request(
                "GET",
                "/api/serial-debug/read",
                params={"max_bytes": 2048, "timeout_ms": 30, "encoding": "utf-8"},
            )
        except Exception as exc:
            recv_error = f"读取失败: {exc}"

    try:
        logs_payload = api_request("GET", "/api/serial-debug/logs", params={"last_seq": max(seq, 0), "limit": 400})
        entries = logs_payload.get("entries", [])
        next_seq = int(logs_payload.get("next_seq", seq))

        if not clear_requested:
            for entry in entries:
                if isinstance(entry, dict):
                    logs.append(_format_serial_log_entry(entry))
            if len(logs) > 300:
                logs = logs[-300:]
        seq = next_seq
    except Exception as exc:
        if recv_error:
            recv_error = f"{recv_error}; 日志拉取失败: {exc}"
        else:
            recv_error = f"日志拉取失败: {exc}"

    status_view = _build_serial_status_view(status)
    log_text = "\n".join(logs) if logs else "暂无串口日志"
    return status_view, logs, log_text, recv_error, seq

if __name__ == "__main__":
    app.run(host=settings.frontend_host, port=settings.frontend_port, debug=True)
