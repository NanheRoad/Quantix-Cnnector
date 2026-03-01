from __future__ import annotations

import json
import logging
import os
import re
import socket
import threading
import time
from copy import deepcopy
from typing import Any

import requests
import uvicorn
import dash
from dash import Dash, Input, Output, State, dcc, html, no_update, ALL
from dash.exceptions import PreventUpdate
from dash_extensions import WebSocket

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
LOGGER = logging.getLogger(__name__)
EMBED_BACKEND = os.getenv("EMBED_BACKEND", "true").lower() in {"1", "true", "yes", "on"}
EMBED_BACKEND_WAIT_SECONDS = float(os.getenv("EMBED_BACKEND_WAIT_SECONDS", "20"))
BACKEND_HEALTH_TIMEOUT_SECONDS = float(os.getenv("BACKEND_HEALTH_TIMEOUT_SECONDS", "1.2"))
API_RETRY_ATTEMPTS = int(os.getenv("API_RETRY_ATTEMPTS", "6"))
API_RETRY_BACKOFF_SECONDS = float(os.getenv("API_RETRY_BACKOFF_SECONDS", "0.3"))
RETRYABLE_STATUS_CODES = {502, 503, 504}
_BACKEND_THREAD: threading.Thread | None = None
API_SESSION = requests.Session()
API_SESSION.trust_env = False
DASHBOARD_MAX_REFRESH_HZ = 10.0
DASHBOARD_MIN_RENDER_INTERVAL = 1.0 / DASHBOARD_MAX_REFRESH_HZ

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

WRITE_ACTIONS = {"modbus.write_register", "modbus.write_coil", "mqtt.publish"}
PLACEHOLDER_PATTERN = re.compile(r"\$\{([^}]+)\}")
VALID_ACTIONS_BY_PROTOCOL: dict[str, set[str]] = {
    "modbus_tcp": {
        "modbus.read_input_registers",
        "modbus.read_holding_registers",
        "modbus.write_register",
        "modbus.write_coil",
        "delay",
    },
    "modbus_rtu": {
        "modbus.read_input_registers",
        "modbus.read_holding_registers",
        "modbus.write_register",
        "modbus.write_coil",
        "delay",
    },
    "mqtt": {"mqtt.subscribe", "mqtt.on_message", "mqtt.publish", "delay"},
    "serial": {"serial.send", "serial.receive", "delay"},
    "tcp": {"tcp.send", "tcp.receive", "delay"},
}

UI_ACTION_OPTIONS_BY_PROTOCOL: dict[str, list[dict[str, str]]] = {
    "modbus_tcp": [
        {"label": "modbus.read_input_registers", "value": "modbus.read_input_registers"},
        {"label": "modbus.read_holding_registers", "value": "modbus.read_holding_registers"},
        {"label": "modbus.write_register", "value": "modbus.write_register"},
        {"label": "modbus.write_coil", "value": "modbus.write_coil"},
        {"label": "delay", "value": "delay"},
    ],
    "modbus_rtu": [
        {"label": "modbus.read_input_registers", "value": "modbus.read_input_registers"},
        {"label": "modbus.read_holding_registers", "value": "modbus.read_holding_registers"},
        {"label": "modbus.write_register", "value": "modbus.write_register"},
        {"label": "modbus.write_coil", "value": "modbus.write_coil"},
        {"label": "delay", "value": "delay"},
    ],
    "mqtt": [
        {"label": "mqtt.publish", "value": "mqtt.publish"},
        {"label": "delay", "value": "delay"},
    ],
    "serial": [
        {"label": "serial.send", "value": "serial.send"},
        {"label": "serial.receive", "value": "serial.receive"},
        {"label": "delay", "value": "delay"},
    ],
    "tcp": [
        {"label": "tcp.send", "value": "tcp.send"},
        {"label": "tcp.receive", "value": "tcp.receive"},
        {"label": "delay", "value": "delay"},
    ],
}

SETUP_ACTION_OPTIONS = [
    {"label": "mqtt.subscribe", "value": "mqtt.subscribe"},
    {"label": "delay", "value": "delay"},
]

TRIGGER_OPTIONS_BY_PROTOCOL: dict[str, list[dict[str, str]]] = {
    "modbus_tcp": [{"label": "poll", "value": "poll"}, {"label": "manual", "value": "manual"}],
    "modbus_rtu": [{"label": "poll", "value": "poll"}, {"label": "manual", "value": "manual"}],
    "mqtt": [{"label": "manual", "value": "manual"}],
    "serial": [{"label": "poll", "value": "poll"}, {"label": "manual", "value": "manual"}],
    "tcp": [{"label": "poll", "value": "poll"}, {"label": "manual", "value": "manual"}],
}

PARSE_TYPE_UI_OPTIONS = [
    {"label": "none", "value": ""},
    {"label": "expression", "value": "expression"},
    {"label": "regex", "value": "regex"},
]


def pretty_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _safe_json_loads(text: Any, fallback: Any) -> Any:
    if text is None:
        return fallback
    raw = str(text).strip()
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except Exception:
        return fallback


def _is_write_action(action: str) -> bool:
    return action in WRITE_ACTIONS


def _extract_placeholders(value: str) -> list[str]:
    return PLACEHOLDER_PATTERN.findall(str(value))


def _is_valid_placeholder(path: str) -> bool:
    parts = [part.strip() for part in str(path).split(".")]
    if not parts:
        return False
    return all(bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part)) for part in parts)


def _validate_expression_syntax(expression: str) -> bool:
    try:
        compile(expression, "<protocol_expression>", "eval")
        return True
    except Exception:
        return False


def _validate_regex_syntax(pattern: str) -> bool:
    try:
        re.compile(pattern)
        return True
    except Exception:
        return False


def _step_to_row(step: dict[str, Any]) -> dict[str, Any]:
    parse = step.get("parse") if isinstance(step.get("parse"), dict) else {}
    parse_type = str(parse.get("type") or "")
    parse_rule = ""
    parse_group = ""
    if parse_type == "expression":
        parse_rule = str(parse.get("expression") or "")
    elif parse_type == "regex":
        parse_rule = str(parse.get("pattern") or "")
        parse_group = str(parse.get("group") or "1")
    return {
        "id": str(step.get("id") or ""),
        "name": str(step.get("name") or ""),
        "trigger": str(step.get("trigger") or "poll"),
        "action": str(step.get("action") or ""),
        "params_json": pretty_json(step.get("params", {})),
        "parse_type": parse_type,
        "parse_rule": parse_rule,
        "parse_group": parse_group,
    }


def _variable_to_row(variable: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(variable.get("name") or ""),
        "type": str(variable.get("type") or "string"),
        "default": variable.get("default"),
        "label": str(variable.get("label") or ""),
    }


def _handler_to_fields(handler: dict[str, Any]) -> dict[str, str]:
    parse = handler.get("parse") if isinstance(handler.get("parse"), dict) else {}
    parse_type = str(parse.get("type") or "regex")
    parse_rule = ""
    parse_group = "1"
    if parse_type == "expression":
        parse_rule = str(parse.get("expression") or "")
    elif parse_type == "regex":
        parse_rule = str(parse.get("pattern") or "")
        parse_group = str(parse.get("group") or "1")
    return {
        "id": str(handler.get("id") or "handle_message"),
        "name": str(handler.get("name") or "处理消息"),
        "action": str(handler.get("action") or "mqtt.on_message"),
        "parse_type": parse_type,
        "parse_rule": parse_rule,
        "parse_group": parse_group,
    }


def _default_step_row(protocol_type: str) -> dict[str, Any]:
    normalized = str(protocol_type or "modbus_tcp")
    options = UI_ACTION_OPTIONS_BY_PROTOCOL.get(normalized, UI_ACTION_OPTIONS_BY_PROTOCOL["modbus_tcp"])
    default_action = options[0]["value"] if options else ""
    default_trigger = "manual" if normalized == "mqtt" else "poll"
    return {
        "id": "",
        "name": "",
        "trigger": default_trigger,
        "action": default_action,
        "params_json": "{}",
        "parse_type": "",
        "parse_rule": "",
        "parse_group": "1",
    }


def _default_setup_step_row() -> dict[str, Any]:
    return {
        "id": "",
        "name": "",
        "trigger": "setup",
        "action": "mqtt.subscribe",
        "params_json": "{}",
        "parse_type": "",
        "parse_rule": "",
        "parse_group": "1",
    }


def _step_row_from_editor(
    protocol_type: str,
    step_id: str,
    name: str,
    trigger: str,
    action: str,
    params_json: str,
    parse_type: str,
    parse_rule: str,
    parse_group: str,
) -> dict[str, Any]:
    fallback = _default_step_row(protocol_type)
    row = {
        "id": str(step_id or "").strip(),
        "name": str(name or "").strip(),
        "trigger": str(trigger or fallback["trigger"]).strip() or fallback["trigger"],
        "action": str(action or fallback["action"]).strip() or fallback["action"],
        "params_json": str(params_json or "{}"),
        "parse_type": str(parse_type or "").strip(),
        "parse_rule": str(parse_rule or ""),
        "parse_group": str(parse_group or "1"),
    }
    return row


def _default_variable_row() -> dict[str, Any]:
    return {
        "name": "",
        "type": "string",
        "default": "",
        "label": "",
    }


def _normalize_variable_default(value: str, var_type: str) -> Any:
    raw = str(value or "").strip()
    if raw == "":
        return ""

    normalized_type = str(var_type or "string")
    try:
        if normalized_type == "int":
            return int(raw)
        if normalized_type == "float":
            return float(raw)
        if normalized_type == "bool":
            return raw.lower() in {"1", "true", "yes", "on"}
    except Exception:
        return raw
    return raw


def _template_to_form_fields(template: dict[str, Any]) -> dict[str, Any]:
    protocol_type = str(template.get("protocol_type") or "modbus_tcp")
    variables = template.get("variables", [])
    steps = template.get("steps", [])
    setup_steps = template.get("setup_steps", [])
    message_handler = template.get("message_handler", {}) if isinstance(template.get("message_handler"), dict) else {}
    output = template.get("output", {})

    return {
        "variables_data": [_variable_to_row(v) for v in variables if isinstance(v, dict)],
        "steps_data": [_step_to_row(s) for s in steps if isinstance(s, dict)],
        "setup_steps_data": [_step_to_row(s) for s in setup_steps if isinstance(s, dict)],
        "message_fields": _handler_to_fields(message_handler if protocol_type == "mqtt" else {}),
        "output_weight": str(output.get("weight") or ""),
        "output_unit": str(output.get("unit") or "kg"),
    }


def _parse_row_step(
    row: dict[str, Any],
    protocol_type: str,
    default_trigger: str,
) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    step_id = str(row.get("id") or "").strip()
    name = str(row.get("name") or "").strip() or step_id
    action = str(row.get("action") or "").strip()
    trigger = str(row.get("trigger") or default_trigger).strip() or default_trigger

    if not step_id:
        errors.append("步骤缺少 id")
    if not action:
        errors.append(f"步骤 {step_id or '<unknown>'} 缺少 action")

    valid_actions = VALID_ACTIONS_BY_PROTOCOL.get(protocol_type, set())
    if action and valid_actions and action not in valid_actions:
        errors.append(f"步骤 {step_id or '<unknown>'} 使用了不支持的 action: {action}")

    params_json = row.get("params_json")
    params: dict[str, Any] = {}
    if isinstance(params_json, str) and params_json.strip():
        try:
            parsed = json.loads(params_json)
        except Exception as exc:
            errors.append(f"步骤 {step_id or '<unknown>'} params JSON 错误: {exc}")
            parsed = {}
        if not isinstance(parsed, dict):
            errors.append(f"步骤 {step_id or '<unknown>'} params 必须是 JSON 对象")
            parsed = {}
        params = parsed

    for _, value in params.items():
        if isinstance(value, str):
            for placeholder in _extract_placeholders(value):
                if not _is_valid_placeholder(placeholder):
                    errors.append(f"步骤 {step_id or '<unknown>'} 存在无效占位符: {placeholder}")

    step: dict[str, Any] = {
        "id": step_id,
        "name": name or step_id,
        "trigger": trigger,
        "action": action,
    }
    if params:
        step["params"] = params

    parse_type = str(row.get("parse_type") or "").strip()
    parse_rule = str(row.get("parse_rule") or "")
    parse_group = str(row.get("parse_group") or "1")
    if parse_type:
        parse_cfg: dict[str, Any] = {"type": parse_type}
        if parse_type == "expression":
            parse_cfg["expression"] = parse_rule
            if parse_rule and not _validate_expression_syntax(parse_rule):
                errors.append(f"步骤 {step_id or '<unknown>'} expression 语法错误")
        elif parse_type == "regex":
            parse_cfg["pattern"] = parse_rule
            if parse_group.strip():
                try:
                    parse_cfg["group"] = int(parse_group)
                except Exception:
                    errors.append(f"步骤 {step_id or '<unknown>'} regex group 必须是整数")
            if parse_rule and not _validate_regex_syntax(parse_rule):
                errors.append(f"步骤 {step_id or '<unknown>'} regex 语法错误")
        step["parse"] = parse_cfg

    if _is_write_action(action) and trigger != "manual":
        errors.append(f"步骤 {step_id or '<unknown>'} 的写操作必须使用 trigger=manual")

    if not step_id or not action:
        return None, errors, warnings
    return step, errors, warnings


def _validate_template_structure(template: dict[str, Any], strict_name: bool = True) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    name_value = str(template.get("name") or "").strip()
    if not name_value:
        if strict_name:
            errors.append("缺少必填字段: name")
        else:
            warnings.append("建议填写字段: name")

    for field in ["protocol_type", "output"]:
        if not template.get(field):
            errors.append(f"缺少必填字段: {field}")

    protocol_type = str(template.get("protocol_type") or "")
    if protocol_type == "mqtt":
        if not template.get("setup_steps"):
            errors.append("MQTT 协议必须配置 setup_steps")
        if not isinstance(template.get("message_handler"), dict):
            errors.append("MQTT 协议必须配置 message_handler")
        for i, step in enumerate(template.get("steps", []), start=1):
            if step.get("trigger") != "manual":
                warnings.append(f"MQTT steps[{i}] 建议只保留 manual 步骤")
    else:
        if not template.get("steps"):
            errors.append(f"{protocol_type or '当前'} 协议必须配置 steps")

    return errors, warnings


def _generate_template_from_form(
    name: str,
    description: str,
    protocol_type: str,
    variables_data: list[dict[str, Any]] | None,
    steps_data: list[dict[str, Any]] | None,
    setup_steps_data: list[dict[str, Any]] | None,
    message_id: str,
    message_name: str,
    message_action: str,
    message_parse_type: str,
    message_parse_rule: str,
    message_parse_group: str,
    output_weight: str,
    output_unit: str,
) -> tuple[dict[str, Any], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    variables: list[dict[str, Any]] = []
    for row in variables_data or []:
        if not isinstance(row, dict):
            continue
        var_name = str(row.get("name") or "").strip()
        if not var_name:
            continue
        var_item: dict[str, Any] = {"name": var_name, "type": str(row.get("type") or "string")}
        if str(row.get("label") or "").strip():
            var_item["label"] = str(row.get("label"))
        if row.get("default") is not None and str(row.get("default")) != "":
            var_item["default"] = row.get("default")
        variables.append(var_item)

    parsed_steps: list[dict[str, Any]] = []
    for row in steps_data or []:
        if not isinstance(row, dict):
            continue
        step, step_errors, step_warnings = _parse_row_step(row, protocol_type, "poll")
        errors.extend(step_errors)
        warnings.extend(step_warnings)
        if step:
            parsed_steps.append(step)

    parsed_setup_steps: list[dict[str, Any]] = []
    for row in setup_steps_data or []:
        if not isinstance(row, dict):
            continue
        row = dict(row)
        row["trigger"] = row.get("trigger") or "setup"
        step, step_errors, step_warnings = _parse_row_step(row, "mqtt", "setup")
        errors.extend(step_errors)
        warnings.extend(step_warnings)
        if step:
            step["trigger"] = "setup"
            parsed_setup_steps.append(step)

    template: dict[str, Any] = {
        "name": name or "",
        "description": description or "",
        "protocol_type": protocol_type,
        "variables": variables,
        "output": {
            "weight": output_weight or "",
            "unit": output_unit or "kg",
        },
    }

    if protocol_type == "mqtt":
        template["setup_steps"] = parsed_setup_steps
        template["steps"] = [step for step in parsed_steps if step.get("trigger") == "manual"]
        message_handler: dict[str, Any] = {
            "id": message_id or "handle_message",
            "name": message_name or "处理消息",
            "trigger": "event",
            "action": message_action or "mqtt.on_message",
        }
        if message_parse_type:
            if message_parse_type == "expression":
                message_handler["parse"] = {"type": "expression", "expression": message_parse_rule or ""}
                if message_parse_rule and not _validate_expression_syntax(message_parse_rule):
                    errors.append("message_handler expression 语法错误")
            elif message_parse_type == "regex":
                parse_item: dict[str, Any] = {"type": "regex", "pattern": message_parse_rule or ""}
                if message_parse_group.strip():
                    try:
                        parse_item["group"] = int(message_parse_group)
                    except Exception:
                        errors.append("message_handler group 必须是整数")
                if message_parse_rule and not _validate_regex_syntax(message_parse_rule):
                    errors.append("message_handler regex 语法错误")
                message_handler["parse"] = parse_item
        template["message_handler"] = message_handler
    else:
        template["steps"] = parsed_steps

    structure_errors, structure_warnings = _validate_template_structure(template, strict_name=False)
    errors.extend(structure_errors)
    warnings.extend(structure_warnings)
    return template, errors, warnings


def _format_validation(errors: list[str], warnings: list[str]) -> str:
    if not errors and not warnings:
        return "✅ 验证通过"
    lines: list[str] = []
    if errors:
        lines.append("❌ 错误:")
        lines.extend(f"- {item}" for item in errors)
    if warnings:
        lines.append("⚠️ 警告:")
        lines.extend(f"- {item}" for item in warnings)
    return "\n".join(lines)


def _backend_health_url() -> str:
    return f"{BACKEND_BASE}/health"


def _dashboard_ws_url() -> str:
    host = _backend_probe_host()
    return f"ws://{host}:{settings.backend_port}/ws?api_key={settings.api_key}"


def _backend_probe_host() -> str:
    host = str(settings.backend_host).strip()
    if host in {"", "0.0.0.0", "::"}:
        return "127.0.0.1"
    return host


def _backend_port_open(timeout_seconds: float = 1.0) -> bool:
    try:
        with socket.create_connection((_backend_probe_host(), int(settings.backend_port)), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def _backend_ready(timeout_seconds: float = BACKEND_HEALTH_TIMEOUT_SECONDS) -> bool:
    try:
        response = API_SESSION.get(_backend_health_url(), timeout=timeout_seconds)
        if response.status_code != 200:
            return _backend_port_open(timeout_seconds=min(timeout_seconds, 1.0))
        payload = response.json() if response.content else {}
        if not isinstance(payload, dict) or payload.get("status") == "ok":
            return True
        return _backend_port_open(timeout_seconds=min(timeout_seconds, 1.0))
    except Exception:
        return _backend_port_open(timeout_seconds=min(timeout_seconds, 1.0))


def _run_embedded_backend() -> None:
    uvicorn.run(
        "backend.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        log_level=settings.log_level.lower(),
    )


def _start_embedded_backend() -> None:
    global _BACKEND_THREAD
    if _BACKEND_THREAD and _BACKEND_THREAD.is_alive():
        return
    _BACKEND_THREAD = threading.Thread(target=_run_embedded_backend, name="quantix-backend", daemon=True)
    _BACKEND_THREAD.start()


def _wait_backend_ready(max_wait_seconds: float) -> bool:
    deadline = time.monotonic() + max_wait_seconds
    while time.monotonic() < deadline:
        if _backend_ready():
            return True
        time.sleep(0.2)
    return _backend_ready()


def api_request(method: str, path: str, **kwargs: Any) -> Any:
    method_upper = str(method).upper()
    retryable_method = method_upper in {"GET", "HEAD", "OPTIONS"}
    max_attempts = max(API_RETRY_ATTEMPTS, 1) if retryable_method else 1

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = API_SESSION.request(
                method_upper,
                f"{BACKEND_BASE}{path}",
                headers=HEADERS,
                timeout=5,
                **kwargs,
            )
        except requests.RequestException as exc:
            last_error = exc
            if retryable_method and attempt < max_attempts:
                time.sleep(API_RETRY_BACKOFF_SECONDS * attempt)
                continue
            raise

        if response.status_code >= 400:
            detail = response.text
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    detail = str(payload.get("detail") or payload)
            except Exception:
                pass

            http_error = requests.HTTPError(f"{response.status_code} {detail}", response=response)
            last_error = http_error
            if retryable_method and response.status_code in RETRYABLE_STATUS_CODES and attempt < max_attempts:
                time.sleep(API_RETRY_BACKOFF_SECONDS * attempt)
                continue
            raise http_error

        if response.content:
            return response.json()
        return None

    if last_error is not None:
        raise last_error
    raise RuntimeError("API request failed unexpectedly")


def _devices_to_dashboard_map(devices: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in devices:
        if not isinstance(item, dict):
            continue
        key = str(item.get("id"))
        if not key or key == "None":
            continue
        result[key] = deepcopy(item)
    return result


def _dashboard_cards_from_map(data: dict[str, dict[str, Any]]) -> list[html.Div]:
    def sort_key(item: dict[str, Any]) -> tuple[int, str]:
        raw_id = str(item.get("id", ""))
        try:
            return (0, f"{int(raw_id):08d}")
        except Exception:
            return (1, raw_id)

    ordered = sorted(data.values(), key=sort_key)
    return [device_card(item) for item in ordered]


def _parse_dashboard_ws_message(message: Any) -> dict[str, Any] | None:
    payload: Any = message
    if isinstance(payload, dict) and "data" in payload:
        payload = payload.get("data")

    if isinstance(payload, bytes):
        try:
            payload = payload.decode("utf-8")
        except Exception:
            return None

    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return None
        try:
            payload = json.loads(text)
        except Exception:
            return None

    if isinstance(payload, dict):
        return payload
    return None


def _merge_dashboard_weight_update(
    data: dict[str, dict[str, Any]],
    update: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    device_id = update.get("device_id")
    if device_id is None:
        return data

    key = str(device_id)
    base = deepcopy(data.get(key, {}))
    base["id"] = int(device_id) if str(device_id).isdigit() else device_id
    base["device_code"] = str(update.get("device_code") or base.get("device_code") or "")
    base["name"] = str(update.get("device_name") or base.get("name") or f"Device {device_id}")

    runtime = deepcopy(base.get("runtime") or {})
    runtime["status"] = update.get("status", runtime.get("status", "offline"))
    runtime["weight"] = update.get("weight", runtime.get("weight"))
    runtime["unit"] = update.get("unit", runtime.get("unit", "kg"))
    runtime["timestamp"] = update.get("timestamp", runtime.get("timestamp"))
    runtime["error"] = update.get("error", runtime.get("error"))
    base["runtime"] = runtime

    merged = dict(data)
    merged[key] = base
    return merged


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
        dcc.Store(id="devices-refresh-signal", data=0),
        dcc.Store(id="protocols-refresh-signal", data=0),
        WebSocket(id="dashboard-ws", url=_dashboard_ws_url()),
        html.Div(id="page-dashboard", children=dashboard_page.layout(), style={"display": "block", "marginTop": "12px"}),
        html.Div(id="page-devices", children=device_config_page.layout(), style={"display": "none", "marginTop": "12px"}),
        html.Div(id="page-control", children=manual_control_page.layout(), style={"display": "none", "marginTop": "12px"}),
        html.Div(id="page-protocols", children=protocol_editor_page.layout(), style={"display": "none", "marginTop": "12px"}),
        html.Div(id="page-serial-debug", children=serial_debug_page.layout(), style={"display": "none", "marginTop": "12px"}),
    ],
    style={"maxWidth": "1200px", "margin": "0 auto", "padding": "16px"},
)


@app.callback(
    Output("page-dashboard", "style"),
    Output("page-devices", "style"),
    Output("page-control", "style"),
    Output("page-protocols", "style"),
    Output("page-serial-debug", "style"),
    Output("dashboard-interval", "disabled"),
    Output("devices-interval", "disabled"),
    Output("control-interval", "disabled"),
    Output("protocols-interval", "disabled"),
    Output("serial-debug-interval", "disabled"),
    Output("dashboard-ws", "url"),
    Input("main-tabs", "value"),
)
def switch_active_tab(tab: str):
    active_tab = str(tab or "dashboard")
    return (
        {"display": "block" if active_tab == "dashboard" else "none", "marginTop": "12px"},
        {"display": "block" if active_tab == "devices" else "none", "marginTop": "12px"},
        {"display": "block" if active_tab == "control" else "none", "marginTop": "12px"},
        {"display": "block" if active_tab == "protocols" else "none", "marginTop": "12px"},
        {"display": "block" if active_tab == "serial_debug" else "none", "marginTop": "12px"},
        active_tab != "dashboard",
        active_tab != "devices",
        active_tab != "control",
        active_tab != "protocols",
        active_tab != "serial_debug",
        _dashboard_ws_url() if active_tab == "dashboard" else "",
    )


@app.callback(
    Output("dashboard-cards", "children"),
    Output("dashboard-error", "children"),
    Output("dashboard-live-store", "data"),
    Output("dashboard-ws-status", "children"),
    Output("dashboard-last-render-ts", "data"),
    Input("dashboard-ws", "message"),
    Input("dashboard-interval", "n_intervals"),
    Input("devices-refresh-signal", "data"),
    Input("main-tabs", "value"),
    State("dashboard-live-store", "data"),
    State("dashboard-last-render-ts", "data"),
)
def refresh_dashboard(
    ws_message: Any,
    _n: int,
    _devices_refresh: Any,
    active_tab: Any,
    live_store: Any,
    last_render_ts: Any,
):
    if str(active_tab or "") != "dashboard":
        raise PreventUpdate

    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else ""
    current_store = deepcopy(live_store) if isinstance(live_store, dict) else {}

    try:
        last_ts = float(last_render_ts or 0.0)
    except Exception:
        last_ts = 0.0

    if triggered_id in {"main-tabs", "dashboard-interval", "devices-refresh-signal"}:
        try:
            devices = api_request("GET", "/api/devices")
            current_store = _devices_to_dashboard_map(devices)
            cards = _dashboard_cards_from_map(current_store)
            return (
                cards,
                "",
                current_store,
                "WebSocket实时推送中，轮询10秒兜底同步",
                time.monotonic(),
            )
        except Exception as exc:
            cards = _dashboard_cards_from_map(current_store)
            return cards, f"加载失败: {exc}", current_store, "WebSocket重连中，已切到兜底数据", last_ts

    if triggered_id == "dashboard-ws":
        payload = _parse_dashboard_ws_message(ws_message)
        if payload is None:
            return no_update, no_update, no_update, no_update, last_ts

        msg_type = str(payload.get("type", "")).lower()
        if msg_type == "ping":
            return no_update, no_update, no_update, "WebSocket心跳正常", last_ts
        if msg_type != "weight_update":
            return no_update, no_update, no_update, no_update, last_ts

        current_store = _merge_dashboard_weight_update(current_store, payload)
        now_ts = time.monotonic()
        if now_ts - last_ts >= DASHBOARD_MIN_RENDER_INTERVAL:
            cards = _dashboard_cards_from_map(current_store)
            return cards, "", current_store, "WebSocket实时推送中（<=10次/秒）", now_ts
        return no_update, no_update, current_store, "WebSocket实时推送中（<=10次/秒）", last_ts

    return no_update, no_update, no_update, no_update, last_ts


@app.callback(
    Output("devices-table", "children"),
    Output("devices-error", "children"),
    Input("devices-interval", "n_intervals"),
    Input("devices-refresh-signal", "data"),
    Input("main-tabs", "value"),
)
def refresh_devices(_n: int, _devices_refresh: Any, active_tab: Any):
    if str(active_tab or "") != "devices":
        raise PreventUpdate
    try:
        devices = api_request("GET", "/api/devices")
    except Exception as exc:
        return html.Div(), f"加载失败: {exc}"

    columns = [
        ("ID", "6%"),
        ("设备编号", "12%"),
        ("名称", "12%"),
        ("模板ID", "10%"),
        ("状态", "10%"),
        ("重量", "10%"),
        ("更新时间", "24%"),
        ("启用", "8%"),
        ("操作", "8%"),
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
                    html.Td(item.get("device_code") or "-"),
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
                            className="qx-btn qx-btn-danger qx-btn-sm",
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
    Input("protocols-refresh-signal", "data"),
    Input("main-tabs", "value"),
    State("device-template-id", "value"),
)
def load_device_template_options(_n: int, _protocols_refresh: Any, active_tab: Any, current_value: Any):
    if str(active_tab or "") != "devices":
        raise PreventUpdate
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
    State("device-code", "value"),
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
    device_code: str,
    template_id: int,
    poll_rate_hz: float,
    enabled: str,
    connection_json: str,
    variables_json: str,
):
    try:
        if not str(device_code or "").strip():
            return "创建失败: 设备编号不能为空"

        rate = float(poll_rate_hz or 0)
        if rate <= 0:
            return "创建失败: 采集频率必须大于 0（单位：次/秒）"

        poll_interval = 1.0 / rate
        payload = {
            "device_code": str(device_code),
            "name": name,
            "protocol_template_id": int(template_id),
            "connection_params": json.loads(connection_json or "{}"),
            "template_variables": json.loads(variables_json or "{}"),
            "poll_interval": poll_interval,
            "enabled": str(enabled).lower() == "true",
        }
        created = api_request("POST", "/api/devices", json=payload)
        return f"创建成功: device_id={created['id']}, code={created.get('device_code', '-')}"
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
    Output("devices-refresh-signal", "data"),
    Input("create-device-result", "children"),
    Input("delete-device-result", "children"),
    prevent_initial_call=True,
)
def trigger_devices_refresh(create_result: Any, delete_result: Any):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise PreventUpdate

    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    text = str(create_result or "") if triggered_id == "create-device-result" else str(delete_result or "")
    if "device_id=" not in text:
        raise PreventUpdate
    return time.time()


@app.callback(
    Output("control-device-id", "options"),
    Output("control-device-id", "value"),
    Output("control-error", "children"),
    Input("control-interval", "n_intervals"),
    Input("devices-refresh-signal", "data"),
    Input("main-tabs", "value"),
    State("control-device-id", "value"),
)
def refresh_control_devices(_n: int, _devices_refresh: Any, active_tab: Any, current_value: Any):
    if str(active_tab or "") != "control":
        raise PreventUpdate
    try:
        devices = api_request("GET", "/api/devices")
    except Exception as exc:
        return [], no_update, f"加载设备失败: {exc}"

    enabled_devices = [item for item in devices if item.get("enabled")]
    options = [
        {
            "label": (
                f"#{item['id']} [{item.get('device_code') or '-'}] "
                f"{item['name']} ({item.get('runtime', {}).get('status', 'offline')})"
            ),
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
            html.Div(f"设备：#{device['id']} [{device.get('device_code') or '-'}] {device['name']}"),
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
        return "执行失败: 参数必须是 JSON 对象，例如 {\"value\":1}", ""

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
            return "执行失败: 未匹配到去皮手动步骤，请在模板中配置 trigger=manual 的去皮步骤。", ""
    elif triggered_id == "control-zero-btn":
        command_name = "清零"
        target_step_id = find_quick_step_id(manual_steps, "zero")
        if not target_step_id:
            return "执行失败: 未匹配到清零手动步骤，请在模板中配置 trigger=manual 的清零步骤。", ""
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
    Input("protocols-refresh-signal", "data"),
    Input("devices-refresh-signal", "data"),
    Input("main-tabs", "value"),
    State("protocol-edit-id", "value"),
)
def refresh_protocols(
    _n: int,
    _protocols_refresh: Any,
    _devices_refresh: Any,
    active_tab: Any,
    current_edit_id: Any,
):
    if str(active_tab or "") != "protocols":
        raise PreventUpdate
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
    Output("protocol-json-input-panel", "style"),
    Output("protocol-form-input-panel", "style"),
    Output("protocol-editor-preview", "style"),
    Output("protocol-editor-grid", "style"),
    Input("protocol-mode", "value"),
)
def switch_protocol_editor_mode(mode: str):
    current_mode = str(mode or "form")
    if current_mode == "json":
        return {"display": "block"}, {"display": "none"}, {"display": "none"}, {"display": "block"}
    return {"display": "none"}, {"display": "block"}, {"display": "block"}, {}


@app.callback(
    Output("protocol-setup-section", "style"),
    Output("protocol-message-section", "style"),
    Input("protocol-type", "value"),
)
def switch_protocol_mqtt_sections(protocol_type: str):
    is_mqtt = str(protocol_type or "") == "mqtt"
    visible = {"display": "block"}
    hidden = {"display": "none"}
    return (visible if is_mqtt else hidden, visible if is_mqtt else hidden)


@app.callback(
    Output("protocol-step-edit-trigger", "options"),
    Output("protocol-step-edit-action", "options"),
    Output("protocol-setup-edit-action", "options"),
    Input("protocol-type", "value"),
)
def update_protocol_step_dropdowns(protocol_type: str):
    normalized = str(protocol_type or "modbus_tcp")
    main_actions = UI_ACTION_OPTIONS_BY_PROTOCOL.get(normalized, UI_ACTION_OPTIONS_BY_PROTOCOL["modbus_tcp"])
    main_triggers = TRIGGER_OPTIONS_BY_PROTOCOL.get(normalized, TRIGGER_OPTIONS_BY_PROTOCOL["modbus_tcp"])
    return main_triggers, main_actions, SETUP_ACTION_OPTIONS


@app.callback(
    Output("protocol-form-message-id", "value"),
    Output("protocol-form-message-name", "value"),
    Output("protocol-form-message-action", "value"),
    Output("protocol-form-message-parse-type", "value"),
    Output("protocol-form-message-parse-rule", "value"),
    Output("protocol-form-message-parse-group", "value"),
    Output("protocol-form-output-weight", "value"),
    Output("protocol-form-output-unit", "value"),
    Input("protocol-type", "value"),
    State("protocol-form-message-id", "value"),
    State("protocol-form-message-name", "value"),
    State("protocol-form-message-action", "value"),
    State("protocol-form-message-parse-type", "value"),
    State("protocol-form-message-parse-rule", "value"),
    State("protocol-form-message-parse-group", "value"),
    State("protocol-form-output-weight", "value"),
    State("protocol-form-output-unit", "value"),
    prevent_initial_call=False,
)
def manage_protocol_form_inputs(
    protocol_type: str,
    message_id: str,
    message_name: str,
    message_action: str,
    message_parse_type: str,
    message_parse_rule: str,
    message_parse_group: str,
    output_weight: str,
    output_unit: str,
):
    normalized = str(protocol_type or "modbus_tcp")
    preset = deepcopy(PROTOCOL_TEMPLATE_PRESETS.get(normalized, PROTOCOL_TEMPLATE_PRESETS["modbus_tcp"]))
    fields = _template_to_form_fields(preset)
    message_fields = fields["message_fields"]
    return (
        message_fields["id"],
        message_fields["name"],
        message_fields["action"],
        message_fields["parse_type"],
        message_fields["parse_rule"],
        message_fields["parse_group"],
        fields["output_weight"],
        fields["output_unit"],
    )


@app.callback(
    Output("protocol-form-variables-store", "data"),
    Output("protocol-variables-selected-index", "data"),
    Input("protocol-type", "value"),
    Input("protocol-add-variable-btn", "n_clicks"),
    Input("protocol-variable-save-btn", "n_clicks"),
    Input("protocol-variable-delete-btn", "n_clicks"),
    Input("protocol-variable-up-btn", "n_clicks"),
    Input("protocol-variable-down-btn", "n_clicks"),
    Input({"type": "protocol-variable-select-btn", "index": ALL}, "n_clicks"),
    State("protocol-form-variables-store", "data"),
    State("protocol-variables-selected-index", "data"),
    State("protocol-variable-edit-name", "value"),
    State("protocol-variable-edit-type", "value"),
    State("protocol-variable-edit-default", "value"),
    State("protocol-variable-edit-label", "value"),
    prevent_initial_call=False,
)
def manage_protocol_variables_workspace(
    protocol_type: str,
    _add_variable_clicks: int,
    _save_clicks: int,
    _delete_clicks: int,
    _up_clicks: int,
    _down_clicks: int,
    _select_clicks: list[int],
    variables_data: Any,
    selected_index: Any,
    var_name: str,
    var_type: str,
    var_default: str,
    var_label: str,
):
    variables = list(variables_data or [])
    try:
        selected = int(selected_index) if selected_index is not None else None
    except Exception:
        selected = None

    ctx = dash.callback_context
    triggered_raw = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else "protocol-type"

    if triggered_raw == "protocol-type" or not ctx.triggered:
        normalized = str(protocol_type or "modbus_tcp")
        preset = deepcopy(PROTOCOL_TEMPLATE_PRESETS.get(normalized, PROTOCOL_TEMPLATE_PRESETS["modbus_tcp"]))
        fields = _template_to_form_fields(preset)
        preset_vars = fields["variables_data"]
        first = 0 if preset_vars else None
        return preset_vars, first

    if triggered_raw == "protocol-add-variable-btn":
        variables.append(_default_variable_row())
        return variables, len(variables) - 1

    if triggered_raw.startswith("{"):
        try:
            trigger_dict = json.loads(triggered_raw)
            if trigger_dict.get("type") == "protocol-variable-select-btn":
                index = int(trigger_dict.get("index"))
                if 0 <= index < len(variables):
                    return variables, index
        except Exception:
            pass
        raise PreventUpdate

    if triggered_raw == "protocol-variable-save-btn":
        row = {
            "name": str(var_name or "").strip(),
            "type": str(var_type or "string"),
            "default": _normalize_variable_default(str(var_default or ""), str(var_type or "string")),
            "label": str(var_label or "").strip(),
        }
        if selected is None or selected < 0 or selected >= len(variables):
            variables.append(row)
            return variables, len(variables) - 1
        variables[selected] = row
        return variables, selected

    if triggered_raw == "protocol-variable-delete-btn":
        if selected is None or selected < 0 or selected >= len(variables):
            raise PreventUpdate
        variables.pop(selected)
        if not variables:
            return [], None
        return variables, min(selected, len(variables) - 1)

    if triggered_raw == "protocol-variable-up-btn":
        if selected is None or selected <= 0 or selected >= len(variables):
            raise PreventUpdate
        variables[selected - 1], variables[selected] = variables[selected], variables[selected - 1]
        return variables, selected - 1

    if triggered_raw == "protocol-variable-down-btn":
        if selected is None or selected < 0 or selected >= len(variables) - 1:
            raise PreventUpdate
        variables[selected + 1], variables[selected] = variables[selected], variables[selected + 1]
        return variables, selected + 1

    raise PreventUpdate


@app.callback(
    Output("protocol-variable-edit-name", "value"),
    Output("protocol-variable-edit-type", "value"),
    Output("protocol-variable-edit-default", "value"),
    Output("protocol-variable-edit-label", "value"),
    Input("protocol-form-variables-store", "data"),
    Input("protocol-variables-selected-index", "data"),
)
def load_selected_variable_editor(variables_data: Any, selected_index: Any):
    variables = list(variables_data or [])
    try:
        selected = int(selected_index) if selected_index is not None else None
    except Exception:
        selected = None

    if selected is not None and 0 <= selected < len(variables):
        row = variables[selected]
        return (
            str(row.get("name") or ""),
            str(row.get("type") or "string"),
            str(row.get("default") or ""),
            str(row.get("label") or ""),
        )
    return "", "string", "", ""


@app.callback(
    Output("protocol-variables-list", "children"),
    Input("protocol-form-variables-store", "data"),
    Input("protocol-variables-selected-index", "data"),
)
def render_protocol_variables_list(variables_data: Any, selected_index: Any):
    variables = list(variables_data or [])
    try:
        selected = int(selected_index) if selected_index is not None else None
    except Exception:
        selected = None

    if not variables:
        return html.Div("暂无变量，点击“+ 添加变量”后在下方编辑。", className="protocol-help-text")

    cards: list[html.Button] = []
    for index, row in enumerate(variables):
        is_active = index == selected
        cards.append(
            html.Button(
                [
                    html.Span(
                        [
                            html.Span(str(row.get("name") or f"var_{index+1}"), className="protocol-step-item-id"),
                            html.Span(
                                f"{row.get('type') or 'string'} | default={row.get('default') if row.get('default') is not None else ''}",
                                className="protocol-step-item-meta",
                            ),
                        ],
                        className="protocol-step-item-main",
                    ),
                    html.Span(str(row.get("label") or "-"), className="protocol-step-item-trigger"),
                ],
                id={"type": "protocol-variable-select-btn", "index": index},
                n_clicks=0,
                className="protocol-step-item active" if is_active else "protocol-step-item",
            )
        )
    return cards


@app.callback(
    Output("protocol-form-steps-store", "data"),
    Output("protocol-steps-selected-index", "data"),
    Input("protocol-type", "value"),
    Input("protocol-add-step-btn", "n_clicks"),
    Input("protocol-step-save-btn", "n_clicks"),
    Input("protocol-step-delete-btn", "n_clicks"),
    Input("protocol-step-up-btn", "n_clicks"),
    Input("protocol-step-down-btn", "n_clicks"),
    Input({"type": "protocol-step-select-btn", "index": ALL}, "n_clicks"),
    State("protocol-form-steps-store", "data"),
    State("protocol-steps-selected-index", "data"),
    State("protocol-step-edit-id", "value"),
    State("protocol-step-edit-name", "value"),
    State("protocol-step-edit-trigger", "value"),
    State("protocol-step-edit-action", "value"),
    State("protocol-step-edit-params-json", "value"),
    State("protocol-step-edit-parse-type", "value"),
    State("protocol-step-edit-parse-rule", "value"),
    State("protocol-step-edit-parse-group", "value"),
    prevent_initial_call=False,
)
def manage_protocol_steps_workspace(
    protocol_type: str,
    _add_step_clicks: int,
    _save_clicks: int,
    _delete_clicks: int,
    _up_clicks: int,
    _down_clicks: int,
    _select_clicks: list[int],
    steps_data: Any,
    selected_index: Any,
    step_id: str,
    step_name: str,
    trigger: str,
    action: str,
    params_json: str,
    parse_type: str,
    parse_rule: str,
    parse_group: str,
):
    steps = list(steps_data or [])
    try:
        selected = int(selected_index) if selected_index is not None else None
    except Exception:
        selected = None

    ctx = dash.callback_context
    triggered_raw = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else "protocol-type"

    if triggered_raw == "protocol-type" or not ctx.triggered:
        normalized = str(protocol_type or "modbus_tcp")
        preset = deepcopy(PROTOCOL_TEMPLATE_PRESETS.get(normalized, PROTOCOL_TEMPLATE_PRESETS["modbus_tcp"]))
        fields = _template_to_form_fields(preset)
        preset_steps = fields["steps_data"]
        first = 0 if preset_steps else None
        return preset_steps, first

    if triggered_raw == "protocol-add-step-btn":
        steps.append(_default_step_row(protocol_type))
        return steps, len(steps) - 1

    if triggered_raw.startswith("{"):
        try:
            trigger_dict = json.loads(triggered_raw)
            if trigger_dict.get("type") == "protocol-step-select-btn":
                index = int(trigger_dict.get("index"))
                if 0 <= index < len(steps):
                    return steps, index
        except Exception:
            pass
        raise PreventUpdate

    if triggered_raw == "protocol-step-save-btn":
        row = _step_row_from_editor(
            protocol_type=protocol_type,
            step_id=step_id,
            name=step_name,
            trigger=trigger,
            action=action,
            params_json=params_json,
            parse_type=parse_type,
            parse_rule=parse_rule,
            parse_group=parse_group,
        )
        if selected is None or selected < 0 or selected >= len(steps):
            steps.append(row)
            return steps, len(steps) - 1
        steps[selected] = row
        return steps, selected

    if triggered_raw == "protocol-step-delete-btn":
        if selected is None or selected < 0 or selected >= len(steps):
            raise PreventUpdate
        steps.pop(selected)
        if not steps:
            return [], None
        return steps, min(selected, len(steps) - 1)

    if triggered_raw == "protocol-step-up-btn":
        if selected is None or selected <= 0 or selected >= len(steps):
            raise PreventUpdate
        steps[selected - 1], steps[selected] = steps[selected], steps[selected - 1]
        return steps, selected - 1

    if triggered_raw == "protocol-step-down-btn":
        if selected is None or selected < 0 or selected >= len(steps) - 1:
            raise PreventUpdate
        steps[selected + 1], steps[selected] = steps[selected], steps[selected + 1]
        return steps, selected + 1

    raise PreventUpdate


@app.callback(
    Output("protocol-step-edit-id", "value"),
    Output("protocol-step-edit-name", "value"),
    Output("protocol-step-edit-trigger", "value"),
    Output("protocol-step-edit-action", "value"),
    Output("protocol-step-edit-params-json", "value"),
    Output("protocol-step-edit-parse-type", "value"),
    Output("protocol-step-edit-parse-rule", "value"),
    Output("protocol-step-edit-parse-group", "value"),
    Input("protocol-form-steps-store", "data"),
    Input("protocol-steps-selected-index", "data"),
    State("protocol-type", "value"),
)
def load_selected_step_editor(steps_data: Any, selected_index: Any, protocol_type: str):
    steps = list(steps_data or [])
    try:
        selected = int(selected_index) if selected_index is not None else None
    except Exception:
        selected = None

    if selected is not None and 0 <= selected < len(steps):
        row = steps[selected]
        return (
            str(row.get("id") or ""),
            str(row.get("name") or ""),
            str(row.get("trigger") or _default_step_row(protocol_type)["trigger"]),
            str(row.get("action") or _default_step_row(protocol_type)["action"]),
            str(row.get("params_json") or "{}"),
            str(row.get("parse_type") or ""),
            str(row.get("parse_rule") or ""),
            str(row.get("parse_group") or "1"),
        )

    default = _default_step_row(protocol_type)
    return (
        default["id"],
        default["name"],
        default["trigger"],
        default["action"],
        default["params_json"],
        default["parse_type"],
        default["parse_rule"],
        default["parse_group"],
    )


@app.callback(
    Output("protocol-steps-list", "children"),
    Input("protocol-form-steps-store", "data"),
    Input("protocol-steps-selected-index", "data"),
)
def render_protocol_steps_list(steps_data: Any, selected_index: Any):
    steps = list(steps_data or [])
    try:
        selected = int(selected_index) if selected_index is not None else None
    except Exception:
        selected = None

    if not steps:
        return html.Div("暂无步骤，点击“+ 添加步骤”后在下方编辑。", className="protocol-help-text")

    cards: list[html.Button] = []
    for index, row in enumerate(steps):
        is_active = index == selected
        cards.append(
            html.Button(
                [
                    html.Span(
                        [
                            html.Span(str(row.get("id") or f"step_{index+1}"), className="protocol-step-item-id"),
                            html.Span(
                                f"{row.get('name') or '-'} | {row.get('action') or '-'}",
                                className="protocol-step-item-meta",
                            ),
                        ],
                        className="protocol-step-item-main",
                    ),
                    html.Span(str(row.get("trigger") or "poll"), className="protocol-step-item-trigger"),
                ],
                id={"type": "protocol-step-select-btn", "index": index},
                n_clicks=0,
                className="protocol-step-item active" if is_active else "protocol-step-item",
            )
        )
    return cards


@app.callback(
    Output("protocol-form-setup-steps-store", "data"),
    Output("protocol-setup-selected-index", "data"),
    Input("protocol-type", "value"),
    Input("protocol-add-setup-step-btn", "n_clicks"),
    Input("protocol-setup-save-btn", "n_clicks"),
    Input("protocol-setup-delete-btn", "n_clicks"),
    Input("protocol-setup-up-btn", "n_clicks"),
    Input("protocol-setup-down-btn", "n_clicks"),
    Input({"type": "protocol-setup-select-btn", "index": ALL}, "n_clicks"),
    State("protocol-form-setup-steps-store", "data"),
    State("protocol-setup-selected-index", "data"),
    State("protocol-setup-edit-id", "value"),
    State("protocol-setup-edit-name", "value"),
    State("protocol-setup-edit-action", "value"),
    State("protocol-setup-edit-params-json", "value"),
    State("protocol-setup-edit-parse-type", "value"),
    State("protocol-setup-edit-parse-rule", "value"),
    State("protocol-setup-edit-parse-group", "value"),
    prevent_initial_call=False,
)
def manage_protocol_setup_steps_workspace(
    protocol_type: str,
    _add_setup_clicks: int,
    _save_clicks: int,
    _delete_clicks: int,
    _up_clicks: int,
    _down_clicks: int,
    _select_clicks: list[int],
    setup_steps_data: Any,
    selected_index: Any,
    step_id: str,
    step_name: str,
    action: str,
    params_json: str,
    parse_type: str,
    parse_rule: str,
    parse_group: str,
):
    steps = list(setup_steps_data or [])
    try:
        selected = int(selected_index) if selected_index is not None else None
    except Exception:
        selected = None

    ctx = dash.callback_context
    triggered_raw = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else "protocol-type"

    if triggered_raw == "protocol-type" or not ctx.triggered:
        normalized = str(protocol_type or "modbus_tcp")
        preset = deepcopy(PROTOCOL_TEMPLATE_PRESETS.get(normalized, PROTOCOL_TEMPLATE_PRESETS["modbus_tcp"]))
        fields = _template_to_form_fields(preset)
        preset_steps = fields["setup_steps_data"]
        first = 0 if preset_steps else None
        return preset_steps, first

    if triggered_raw == "protocol-add-setup-step-btn":
        steps.append(_default_setup_step_row())
        return steps, len(steps) - 1

    if triggered_raw.startswith("{"):
        try:
            trigger_dict = json.loads(triggered_raw)
            if trigger_dict.get("type") == "protocol-setup-select-btn":
                index = int(trigger_dict.get("index"))
                if 0 <= index < len(steps):
                    return steps, index
        except Exception:
            pass
        raise PreventUpdate

    if triggered_raw == "protocol-setup-save-btn":
        row = _step_row_from_editor(
            protocol_type="mqtt",
            step_id=step_id,
            name=step_name,
            trigger="setup",
            action=action,
            params_json=params_json,
            parse_type=parse_type,
            parse_rule=parse_rule,
            parse_group=parse_group,
        )
        row["trigger"] = "setup"
        if selected is None or selected < 0 or selected >= len(steps):
            steps.append(row)
            return steps, len(steps) - 1
        steps[selected] = row
        return steps, selected

    if triggered_raw == "protocol-setup-delete-btn":
        if selected is None or selected < 0 or selected >= len(steps):
            raise PreventUpdate
        steps.pop(selected)
        if not steps:
            return [], None
        return steps, min(selected, len(steps) - 1)

    if triggered_raw == "protocol-setup-up-btn":
        if selected is None or selected <= 0 or selected >= len(steps):
            raise PreventUpdate
        steps[selected - 1], steps[selected] = steps[selected], steps[selected - 1]
        return steps, selected - 1

    if triggered_raw == "protocol-setup-down-btn":
        if selected is None or selected < 0 or selected >= len(steps) - 1:
            raise PreventUpdate
        steps[selected + 1], steps[selected] = steps[selected], steps[selected + 1]
        return steps, selected + 1

    raise PreventUpdate


@app.callback(
    Output("protocol-setup-edit-id", "value"),
    Output("protocol-setup-edit-name", "value"),
    Output("protocol-setup-edit-action", "value"),
    Output("protocol-setup-edit-params-json", "value"),
    Output("protocol-setup-edit-parse-type", "value"),
    Output("protocol-setup-edit-parse-rule", "value"),
    Output("protocol-setup-edit-parse-group", "value"),
    Input("protocol-form-setup-steps-store", "data"),
    Input("protocol-setup-selected-index", "data"),
)
def load_selected_setup_editor(setup_steps_data: Any, selected_index: Any):
    steps = list(setup_steps_data or [])
    try:
        selected = int(selected_index) if selected_index is not None else None
    except Exception:
        selected = None

    if selected is not None and 0 <= selected < len(steps):
        row = steps[selected]
        return (
            str(row.get("id") or ""),
            str(row.get("name") or ""),
            str(row.get("action") or "mqtt.subscribe"),
            str(row.get("params_json") or "{}"),
            str(row.get("parse_type") or ""),
            str(row.get("parse_rule") or ""),
            str(row.get("parse_group") or "1"),
        )
    default = _default_setup_step_row()
    return (
        default["id"],
        default["name"],
        default["action"],
        default["params_json"],
        default["parse_type"],
        default["parse_rule"],
        default["parse_group"],
    )


@app.callback(
    Output("protocol-setup-steps-list", "children"),
    Input("protocol-form-setup-steps-store", "data"),
    Input("protocol-setup-selected-index", "data"),
)
def render_protocol_setup_steps_list(setup_steps_data: Any, selected_index: Any):
    steps = list(setup_steps_data or [])
    try:
        selected = int(selected_index) if selected_index is not None else None
    except Exception:
        selected = None

    if not steps:
        return html.Div("暂无 setup 步骤，点击“+ 添加 setup”后在下方编辑。", className="protocol-help-text")

    cards: list[html.Button] = []
    for index, row in enumerate(steps):
        is_active = index == selected
        cards.append(
            html.Button(
                [
                    html.Span(
                        [
                            html.Span(str(row.get("id") or f"setup_{index+1}"), className="protocol-step-item-id"),
                            html.Span(
                                f"{row.get('name') or '-'} | {row.get('action') or '-'}",
                                className="protocol-step-item-meta",
                            ),
                        ],
                        className="protocol-step-item-main",
                    ),
                    html.Span("setup", className="protocol-step-item-trigger"),
                ],
                id={"type": "protocol-setup-select-btn", "index": index},
                n_clicks=0,
                className="protocol-step-item active" if is_active else "protocol-step-item",
            )
        )
    return cards


@app.callback(
    Output("protocol-generated-template-store", "data"),
    Output("protocol-json-preview", "value"),
    Output("protocol-json-validation-status", "children"),
    Output("protocol-form-validation", "children"),
    Input("protocol-name", "value"),
    Input("protocol-desc", "value"),
    Input("protocol-type", "value"),
    Input("protocol-form-variables-store", "data"),
    Input("protocol-form-steps-store", "data"),
    Input("protocol-form-setup-steps-store", "data"),
    Input("protocol-form-message-id", "value"),
    Input("protocol-form-message-name", "value"),
    Input("protocol-form-message-action", "value"),
    Input("protocol-form-message-parse-type", "value"),
    Input("protocol-form-message-parse-rule", "value"),
    Input("protocol-form-message-parse-group", "value"),
    Input("protocol-form-output-weight", "value"),
    Input("protocol-form-output-unit", "value"),
)
def generate_protocol_preview(
    name: str,
    description: str,
    protocol_type: str,
    variables_data: Any,
    steps_data: Any,
    setup_steps_data: Any,
    message_id: str,
    message_name: str,
    message_action: str,
    message_parse_type: str,
    message_parse_rule: str,
    message_parse_group: str,
    output_weight: str,
    output_unit: str,
):
    template, errors, warnings = _generate_template_from_form(
        name=str(name or ""),
        description=str(description or ""),
        protocol_type=str(protocol_type or "modbus_tcp"),
        variables_data=variables_data if isinstance(variables_data, list) else [],
        steps_data=steps_data if isinstance(steps_data, list) else [],
        setup_steps_data=setup_steps_data if isinstance(setup_steps_data, list) else [],
        message_id=str(message_id or ""),
        message_name=str(message_name or ""),
        message_action=str(message_action or ""),
        message_parse_type=str(message_parse_type or ""),
        message_parse_rule=str(message_parse_rule or ""),
        message_parse_group=str(message_parse_group or ""),
        output_weight=str(output_weight or ""),
        output_unit=str(output_unit or "kg"),
    )
    validation_text = _format_validation(errors, warnings)
    return template, pretty_json(template), validation_text, validation_text


@app.callback(
    Output("protocol-template-json", "value"),
    Output("protocol-template-help", "children"),
    Output("protocol-preset-last-type", "data"),
    Input("protocol-type", "value"),
    Input("protocol-mode", "value"),
    Input("protocol-generated-template-store", "data"),
    State("protocol-template-json", "value"),
    State("protocol-preset-last-type", "data"),
)
def load_protocol_preset(
    protocol_type: str,
    mode: str,
    generated_template: Any,
    current_json: str | None,
    last_type: str | None,
):
    normalized = str(protocol_type or "modbus_tcp")
    preset = deepcopy(PROTOCOL_TEMPLATE_PRESETS.get(normalized, PROTOCOL_TEMPLATE_PRESETS["modbus_tcp"]))

    if normalized == "mqtt":
        text = "MQTT 模板建议使用 setup_steps + message_handler。setup 负责订阅，message_handler 负责解析消息。"
    else:
        text = "轮询协议模板建议使用 steps + trigger=poll；写操作步骤建议设置 trigger=manual。"

    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else "protocol-type"
    current_text = str(current_json or "").strip()
    previous_type = str(last_type or "").strip()

    # When switching back to JSON mode, sync the latest generated form template.
    if triggered_id == "protocol-mode" and str(mode or "form") == "json":
        if isinstance(generated_template, dict) and generated_template:
            return pretty_json(generated_template), text, normalized
        return no_update, text, normalized

    # In form mode, do not overwrite user JSON text.
    if str(mode or "form") == "form":
        return no_update, text, normalized

    # Keep user-edited JSON when type unchanged.
    if previous_type and previous_type == normalized:
        return no_update, text, normalized

    # Keep existing JSON on first load if user already pasted content.
    if (not previous_type) and current_text and current_text != "{}":
        return no_update, text, normalized

    return pretty_json(preset), text, normalized


@app.callback(
    Output("create-protocol-result", "children"),
    Input("create-protocol-btn", "n_clicks"),
    State("protocol-name", "value"),
    State("protocol-desc", "value"),
    State("protocol-type", "value"),
    State("protocol-mode", "value"),
    State("protocol-generated-template-store", "data"),
    State("protocol-template-json", "value"),
    prevent_initial_call=True,
)
def create_protocol(
    _n: int,
    name: str,
    description: str,
    protocol_type: str,
    mode: str,
    generated_template: Any,
    template_json: str,
):
    try:
        if not str(name or "").strip():
            return "创建失败: 模板名称不能为空"

        normalized_mode = str(mode or "form")
        if normalized_mode == "form":
            template = generated_template if isinstance(generated_template, dict) else {}
            if not template:
                return "创建失败: 表单尚未生成有效模板"
        else:
            template = json.loads(template_json or "{}")

        template["name"] = template.get("name") or name
        template["protocol_type"] = protocol_type

        errors, _warnings = _validate_template_structure(template, strict_name=True)
        if errors:
            return "创建失败: 模板校验未通过\n" + "\n".join(f"- {item}" for item in errors)

        payload = {
            "name": str(name),
            "description": str(description or ""),
            "protocol_type": str(protocol_type),
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
    Output("protocol-step-test-id", "options"),
    Output("protocol-step-test-id", "value"),
    Input("protocol-edit-id", "value"),
    Input("protocol-step-test-context", "value"),
)
def load_step_test_options(protocol_id: Any, step_context: str):
    if not protocol_id:
        return [], None

    try:
        protocol = api_request("GET", f"/api/protocols/{int(protocol_id)}")
    except Exception:
        return [], None

    template = protocol.get("template", {})
    context = str(step_context or "poll")
    options: list[dict[str, Any]] = []
    if context == "setup":
        for step in template.get("setup_steps", []):
            if not isinstance(step, dict):
                continue
            step_id = str(step.get("id") or "")
            if not step_id:
                continue
            options.append(
                {
                    "label": f"{step_id} ({step.get('action', '-')})",
                    "value": step_id,
                }
            )
    elif context == "event":
        handler = template.get("message_handler", {})
        if isinstance(handler, dict):
            step_id = str(handler.get("id") or "")
            if step_id:
                options.append(
                    {
                        "label": f"{step_id} ({handler.get('action', '-')})",
                        "value": step_id,
                    }
                )
    else:
        for step in template.get("steps", []):
            if not isinstance(step, dict):
                continue
            if step.get("trigger", "poll") != "poll":
                continue
            step_id = str(step.get("id") or "")
            if not step_id:
                continue
            options.append(
                {
                    "label": f"{step_id} ({step.get('action', '-')})",
                    "value": step_id,
                }
            )

    first = options[0]["value"] if options else None
    return options, first


@app.callback(
    Output("protocol-step-test-result", "children"),
    Input("protocol-step-test-btn", "n_clicks"),
    State("protocol-edit-id", "value"),
    State("protocol-step-test-context", "value"),
    State("protocol-step-test-id", "value"),
    State("protocol-step-test-conn-json", "value"),
    State("protocol-step-test-vars-json", "value"),
    State("protocol-step-test-payload", "value"),
    State("protocol-step-test-allow-write", "value"),
    prevent_initial_call=True,
)
def run_protocol_step_test(
    _n_clicks: int,
    protocol_id: Any,
    step_context: str,
    step_id: str,
    conn_json: str,
    vars_json: str,
    test_payload: str,
    allow_write_flags: list[str] | None,
):
    if not protocol_id:
        return "请先在“编辑或删除模板”中选择模板。"
    if not step_id:
        return "请选择要测试的步骤。"

    try:
        connection_params = _safe_json_loads(conn_json, {})
        template_variables = _safe_json_loads(vars_json, {})
        if not isinstance(connection_params, dict):
            return "连接参数必须是 JSON 对象。"
        if not isinstance(template_variables, dict):
            return "变量参数必须是 JSON 对象。"

        payload: dict[str, Any] = {
            "connection_params": connection_params,
            "template_variables": template_variables,
            "step_id": str(step_id),
            "step_context": str(step_context or "poll"),
            "allow_write": "allow" in (allow_write_flags or []),
        }
        if str(step_context or "") == "event":
            payload["test_payload"] = str(test_payload or "")

        result = api_request("POST", f"/api/protocols/{int(protocol_id)}/test-step", json=payload)
        return pretty_json(result)
    except Exception as exc:
        return f"单步测试失败: {exc}"


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


@app.callback(
    Output("protocols-refresh-signal", "data"),
    Input("create-protocol-result", "children"),
    Input("protocol-edit-result", "children"),
    prevent_initial_call=True,
)
def trigger_protocols_refresh(create_result: Any, edit_result: Any):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise PreventUpdate

    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    text = str(create_result or "") if triggered_id == "create-protocol-result" else str(edit_result or "")
    if "protocol_id=" not in text:
        raise PreventUpdate
    return time.time()


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
    Input("main-tabs", "value"),
    State("serial-debug-log-store", "data"),
    State("serial-debug-log-seq-store", "data"),
)
def refresh_serial_debug_runtime(_n: int, _clear_clicks: int, active_tab: Any, stored_logs: Any, log_seq: Any):
    if str(active_tab or "") != "serial_debug":
        raise PreventUpdate
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
    # When EMBED_BACKEND=true, `python app.py` starts backend and frontend together.
    # This keeps local debug as a one-command startup and avoids opening two terminals.
    if EMBED_BACKEND:
        # Probe backend health first.
        # If backend is already running, reuse it instead of starting a duplicate process.
        if _backend_ready():
            LOGGER.info("Backend already reachable at %s", BACKEND_BASE)
        else:
            # Backend is not ready; start Uvicorn in a background thread.
            LOGGER.info("Starting embedded backend on %s", BACKEND_BASE)
            _start_embedded_backend()
            # Wait for readiness to avoid frontend requests failing on first load.
            if _wait_backend_ready(EMBED_BACKEND_WAIT_SECONDS):
                LOGGER.info("Embedded backend is ready")
            else:
                # If thread exited, backend startup failed; raise immediately.
                backend_thread_alive = bool(_BACKEND_THREAD and _BACKEND_THREAD.is_alive())
                if not backend_thread_alive:
                    raise RuntimeError(
                        "Embedded backend exited before becoming ready at "
                        f"{BACKEND_BASE}. Please check backend startup logs."
                    )
                # Thread is alive but health probe timed out; continue frontend startup with warning.
                LOGGER.warning(
                    "Embedded backend health probe timed out after %.1fs, but backend thread is alive; "
                    "frontend will continue to start.",
                    EMBED_BACKEND_WAIT_SECONDS,
                )
        # In embedded mode, disable reloader to avoid duplicate backend starts in Dash debug.
        app.run(
            host=settings.frontend_host,
            port=settings.frontend_port,
            debug=True,
            use_reloader=False,
        )
    else:
        # In non-embedded mode, frontend only checks connectivity and does not start backend.
        if not _backend_ready():
            LOGGER.warning("Backend is not reachable at %s", BACKEND_BASE)
        app.run(host=settings.frontend_host, port=settings.frontend_port, debug=True)
