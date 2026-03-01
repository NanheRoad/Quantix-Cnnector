from __future__ import annotations

from dash import dash_table, dcc, html


PROTOCOL_OPTIONS = [
    {"label": "Modbus TCP", "value": "modbus_tcp"},
    {"label": "Modbus RTU（串口）", "value": "modbus_rtu"},
    {"label": "MQTT（推送）", "value": "mqtt"},
    {"label": "Serial（串口）", "value": "serial"},
    {"label": "TCP（原始）", "value": "tcp"},
]


TRIGGER_OPTIONS = [
    {"label": "poll", "value": "poll"},
    {"label": "manual", "value": "manual"},
    {"label": "setup", "value": "setup"},
    {"label": "event", "value": "event"},
]

PARSE_TYPE_OPTIONS = [
    {"label": "none", "value": ""},
    {"label": "expression", "value": "expression"},
    {"label": "regex", "value": "regex"},
]

ACTION_OPTIONS = [
    {"label": "modbus.read_input_registers", "value": "modbus.read_input_registers"},
    {"label": "modbus.read_holding_registers", "value": "modbus.read_holding_registers"},
    {"label": "modbus.write_register", "value": "modbus.write_register"},
    {"label": "modbus.write_coil", "value": "modbus.write_coil"},
    {"label": "mqtt.subscribe", "value": "mqtt.subscribe"},
    {"label": "mqtt.on_message", "value": "mqtt.on_message"},
    {"label": "mqtt.publish", "value": "mqtt.publish"},
    {"label": "serial.send", "value": "serial.send"},
    {"label": "serial.receive", "value": "serial.receive"},
    {"label": "tcp.send", "value": "tcp.send"},
    {"label": "tcp.receive", "value": "tcp.receive"},
    {"label": "delay", "value": "delay"},
]

MQTT_MESSAGE_ACTION_OPTIONS = [
    {"label": "mqtt.on_message", "value": "mqtt.on_message"},
]


def help_text(text: str) -> html.Div:
    return html.Div(text, className="protocol-help-text")


def _variables_table() -> dash_table.DataTable:
    return dash_table.DataTable(
        id="protocol-form-variables",
        columns=[
            {"name": "变量名", "id": "name"},
            {"name": "类型", "id": "type", "presentation": "dropdown"},
            {"name": "默认值", "id": "default"},
            {"name": "标签", "id": "label"},
        ],
        data=[],
        editable=True,
        row_deletable=True,
        css=[
            {
                "selector": ".Select-menu-outer",
                "rule": "z-index: 3200 !important;",
            },
        ],
        dropdown={"type": {"options": [{"label": t, "value": t} for t in ["string", "int", "float", "bool"]]}},
        style_table={
            "overflowX": "auto",
            "overflowY": "visible",
            "minHeight": "140px",
        },
        style_cell={"textAlign": "left", "padding": "8px", "fontSize": "13px", "whiteSpace": "nowrap", "height": "44px"},
        style_data={"height": "44px"},
        style_cell_conditional=[
            {"if": {"column_id": "name"}, "minWidth": "140px", "width": "140px", "maxWidth": "190px"},
            {"if": {"column_id": "type"}, "minWidth": "110px", "width": "110px", "maxWidth": "140px"},
            {"if": {"column_id": "default"}, "minWidth": "110px", "width": "110px", "maxWidth": "160px"},
            {"if": {"column_id": "label"}, "minWidth": "170px", "width": "170px", "maxWidth": "260px"},
        ],
        style_header={"backgroundColor": "#f4f8ff", "fontWeight": "700"},
    )


def _steps_table(table_id: str) -> dash_table.DataTable:
    return dash_table.DataTable(
        id=table_id,
        columns=[
            {"name": "id", "id": "id"},
            {"name": "名称", "id": "name"},
            {"name": "trigger", "id": "trigger", "presentation": "dropdown"},
            {"name": "action", "id": "action", "presentation": "dropdown"},
            {"name": "params(JSON)", "id": "params_json"},
            {"name": "parse.type", "id": "parse_type", "presentation": "dropdown"},
            {"name": "parse.rule", "id": "parse_rule"},
            {"name": "group", "id": "parse_group"},
        ],
        data=[],
        editable=True,
        row_deletable=True,
        css=[
            {
                "selector": ".Select-menu-outer",
                "rule": "z-index: 3200 !important;",
            },
        ],
        dropdown={
            "trigger": {"options": TRIGGER_OPTIONS},
            "action": {"options": ACTION_OPTIONS},
            "parse_type": {"options": PARSE_TYPE_OPTIONS},
        },
        style_table={
            "overflowX": "auto",
            "overflowY": "visible",
            "minHeight": "190px",
        },
        style_cell={"textAlign": "left", "padding": "8px", "fontSize": "13px", "whiteSpace": "nowrap", "height": "44px"},
        style_data={"height": "44px"},
        style_cell_conditional=[
            {"if": {"column_id": "id"}, "minWidth": "120px", "width": "120px", "maxWidth": "180px"},
            {"if": {"column_id": "name"}, "minWidth": "120px", "width": "120px", "maxWidth": "180px"},
            {"if": {"column_id": "trigger"}, "minWidth": "110px", "width": "110px", "maxWidth": "130px"},
            {"if": {"column_id": "action"}, "minWidth": "220px", "width": "220px", "maxWidth": "300px"},
            {"if": {"column_id": "params_json"}, "minWidth": "240px", "width": "240px", "maxWidth": "340px"},
            {"if": {"column_id": "parse_type"}, "minWidth": "120px", "width": "120px", "maxWidth": "140px"},
            {"if": {"column_id": "parse_rule"}, "minWidth": "180px", "width": "180px", "maxWidth": "280px"},
            {"if": {"column_id": "parse_group"}, "minWidth": "90px", "width": "90px", "maxWidth": "110px"},
        ],
        style_header={"backgroundColor": "#f4f8ff", "fontWeight": "700"},
    )


def layout() -> html.Div:
    return html.Div(
        [
            dcc.Interval(id="protocols-interval", interval=5000, n_intervals=0),
            dcc.Store(id="protocol-preset-last-type", data=None, storage_type="session"),
            dcc.Store(id="protocol-form-store", data={}, storage_type="session"),
            dcc.Store(id="protocol-generated-template-store", data={}, storage_type="session"),
            dcc.Store(id="protocol-form-variables-store", data=[], storage_type="session"),
            dcc.Store(id="protocol-variables-selected-index", data=None, storage_type="session"),
            dcc.Store(id="protocol-form-steps-store", data=[], storage_type="session"),
            dcc.Store(id="protocol-steps-selected-index", data=None, storage_type="session"),
            dcc.Store(id="protocol-form-setup-steps-store", data=[], storage_type="session"),
            dcc.Store(id="protocol-setup-selected-index", data=None, storage_type="session"),
            html.H2("协议模板管理"),
            html.Div(
                "支持 JSON 与无代码表单双模式，配置实时生成并验证模板 JSON。",
                className="protocol-subtitle",
            ),
            html.Div(id="protocols-error", style={"color": "#c62828", "marginBottom": "8px"}),
            html.Div(id="protocols-list", style={"marginBottom": "20px"}),
            html.Div(
                [
                    html.H3("创建模板"),
                    html.Div(
                        [
                            html.Label("编辑模式"),
                            dcc.RadioItems(
                                id="protocol-mode",
                                options=[
                                    {"label": "JSON 编辑", "value": "json"},
                                    {"label": "表单配置", "value": "form"},
                                ],
                                value="form",
                                className="protocol-mode-switch",
                                labelClassName="protocol-mode-item",
                                inputClassName="protocol-mode-input",
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
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
                                            help_text("切换协议类型会刷新默认步骤模板。"),
                                        ],
                                        style={"marginTop": "8px"},
                                    ),
                                    html.Div(
                                        id="protocol-template-help",
                                        className="protocol-help-panel",
                                    ),
                                    html.Div(
                                        [
                                            html.Div(
                                                [
                                                    html.Label("模板 JSON"),
                                                    dcc.Textarea(
                                                        id="protocol-template-json",
                                                        value="{}",
                                                        className="protocol-json-editor",
                                                        persistence=True,
                                                        persistence_type="session",
                                                    ),
                                                    help_text("JSON 模式直接编辑完整模板。"),
                                                ],
                                                id="protocol-json-input-panel",
                                            ),
                                            html.Div(
                                                [
                                                    html.Details(
                                                        [
                                                            html.Summary("变量定义", className="protocol-details-summary"),
                                                            html.Div(
                                                                [
                                                                    html.Div(
                                                                        [
                                                                            html.Button(
                                                                                "+ 添加变量",
                                                                                id="protocol-add-variable-btn",
                                                                                n_clicks=0,
                                                                                className="qx-btn qx-btn-soft qx-btn-sm",
                                                                            ),
                                                                        ],
                                                                        className="protocol-panel-header",
                                                                    ),
                                                                    html.Div(
                                                                        id="protocol-variables-list",
                                                                        className="protocol-variables-list",
                                                                    ),
                                                                    html.Div(
                                                                        [
                                                                            html.Div("变量详情编辑", className="protocol-step-editor-title"),
                                                                            html.Div(
                                                                                [
                                                                                    html.Div(
                                                                                        [
                                                                                            html.Label("变量名", className="protocol-field-label"),
                                                                                            dcc.Input(
                                                                                                id="protocol-variable-edit-name",
                                                                                                className="qx-input",
                                                                                                placeholder="如 slave_id",
                                                                                                style={"width": "100%"},
                                                                                            ),
                                                                                        ],
                                                                                        className="protocol-field",
                                                                                    ),
                                                                                    html.Div(
                                                                                        [
                                                                                            html.Label("变量类型", className="protocol-field-label"),
                                                                                            dcc.Dropdown(
                                                                                                id="protocol-variable-edit-type",
                                                                                                options=[
                                                                                                    {"label": "string", "value": "string"},
                                                                                                    {"label": "int", "value": "int"},
                                                                                                    {"label": "float", "value": "float"},
                                                                                                    {"label": "bool", "value": "bool"},
                                                                                                ],
                                                                                                value="string",
                                                                                                clearable=False,
                                                                                                className="qx-dropdown",
                                                                                            ),
                                                                                        ],
                                                                                        className="protocol-field",
                                                                                    ),
                                                                                    html.Div(
                                                                                        [
                                                                                            html.Label("默认值", className="protocol-field-label"),
                                                                                            dcc.Input(
                                                                                                id="protocol-variable-edit-default",
                                                                                                className="qx-input",
                                                                                                placeholder="如 1 / sensor/weight",
                                                                                                style={"width": "100%"},
                                                                                            ),
                                                                                        ],
                                                                                        className="protocol-field",
                                                                                    ),
                                                                                ],
                                                                                className="protocol-inline-grid",
                                                                            ),
                                                                            html.Div(
                                                                                [
                                                                                    html.Label("显示标签", className="protocol-field-label"),
                                                                                    dcc.Input(
                                                                                        id="protocol-variable-edit-label",
                                                                                        className="qx-input",
                                                                                        placeholder="如 从站地址",
                                                                                        style={"width": "100%"},
                                                                                    ),
                                                                                ],
                                                                                className="protocol-field",
                                                                                style={"marginTop": "8px"},
                                                                            ),
                                                                            html.Div(
                                                                                [
                                                                                    html.Button(
                                                                                        "保存当前变量",
                                                                                        id="protocol-variable-save-btn",
                                                                                        n_clicks=0,
                                                                                        className="qx-btn qx-btn-secondary qx-btn-sm",
                                                                                    ),
                                                                                    html.Button(
                                                                                        "删除当前变量",
                                                                                        id="protocol-variable-delete-btn",
                                                                                        n_clicks=0,
                                                                                        className="qx-btn qx-btn-danger qx-btn-sm",
                                                                                    ),
                                                                                    html.Button(
                                                                                        "上移",
                                                                                        id="protocol-variable-up-btn",
                                                                                        n_clicks=0,
                                                                                        className="qx-btn qx-btn-soft qx-btn-sm",
                                                                                    ),
                                                                                    html.Button(
                                                                                        "下移",
                                                                                        id="protocol-variable-down-btn",
                                                                                        n_clicks=0,
                                                                                        className="qx-btn qx-btn-soft qx-btn-sm",
                                                                                    ),
                                                                                ],
                                                                                className="protocol-step-editor-actions",
                                                                            ),
                                                                        ],
                                                                        className="protocol-step-editor",
                                                                    ),
                                                                ],
                                                                className="protocol-details-body",
                                                            ),
                                                        ],
                                                        className="protocol-details",
                                                        open=True,
                                                    ),
                                                    html.Details(
                                                        [
                                                            html.Summary("轮询/手动步骤", className="protocol-details-summary"),
                                                            html.Div(
                                                                [
                                                                    html.Div(
                                                                        [
                                                                            html.Button(
                                                                                "+ 添加步骤",
                                                                                id="protocol-add-step-btn",
                                                                                n_clicks=0,
                                                                                className="qx-btn qx-btn-soft qx-btn-sm",
                                                                            ),
                                                                        ],
                                                                        className="protocol-panel-header",
                                                                    ),
                                                                    html.Div(
                                                                        id="protocol-steps-list",
                                                                        className="protocol-steps-list",
                                                                    ),
                                                                    html.Div(
                                                                        [
                                                                            html.Div("步骤详情编辑", className="protocol-step-editor-title"),
                                                                            html.Div(
                                                                                [
                                                                                    html.Div(
                                                                                        [
                                                                                            html.Label("步骤 ID", className="protocol-field-label"),
                                                                                            dcc.Input(
                                                                                                id="protocol-step-edit-id",
                                                                                                className="qx-input",
                                                                                                placeholder="如 read_weight",
                                                                                                style={"width": "100%"},
                                                                                            ),
                                                                                        ],
                                                                                        className="protocol-field",
                                                                                    ),
                                                                                    html.Div(
                                                                                        [
                                                                                            html.Label("步骤名称", className="protocol-field-label"),
                                                                                            dcc.Input(
                                                                                                id="protocol-step-edit-name",
                                                                                                className="qx-input",
                                                                                                placeholder="如 读取重量",
                                                                                                style={"width": "100%"},
                                                                                            ),
                                                                                        ],
                                                                                        className="protocol-field",
                                                                                    ),
                                                                                ],
                                                                                className="protocol-inline-grid protocol-inline-grid-2",
                                                                            ),
                                                                            html.Div(
                                                                                [
                                                                                    html.Div(
                                                                                        [
                                                                                            html.Label("触发方式", className="protocol-field-label"),
                                                                                            dcc.Dropdown(
                                                                                                id="protocol-step-edit-trigger",
                                                                                                options=TRIGGER_OPTIONS,
                                                                                                clearable=False,
                                                                                                className="qx-dropdown",
                                                                                            ),
                                                                                        ],
                                                                                        className="protocol-field",
                                                                                    ),
                                                                                    html.Div(
                                                                                        [
                                                                                            html.Label("动作", className="protocol-field-label"),
                                                                                            dcc.Dropdown(
                                                                                                id="protocol-step-edit-action",
                                                                                                options=ACTION_OPTIONS,
                                                                                                clearable=False,
                                                                                                className="qx-dropdown",
                                                                                            ),
                                                                                        ],
                                                                                        className="protocol-field",
                                                                                    ),
                                                                                    html.Div(
                                                                                        [
                                                                                            html.Label("解析类型", className="protocol-field-label"),
                                                                                            dcc.Dropdown(
                                                                                                id="protocol-step-edit-parse-type",
                                                                                                options=PARSE_TYPE_OPTIONS,
                                                                                                clearable=False,
                                                                                                className="qx-dropdown",
                                                                                                value="",
                                                                                            ),
                                                                                        ],
                                                                                        className="protocol-field",
                                                                                    ),
                                                                                ],
                                                                                className="protocol-inline-grid",
                                                                                style={"marginTop": "8px"},
                                                                            ),
                                                                            html.Div(
                                                                                [
                                                                                    html.Div(
                                                                                        [
                                                                                            html.Label("解析规则", className="protocol-field-label"),
                                                                                            dcc.Input(
                                                                                                id="protocol-step-edit-parse-rule",
                                                                                                className="qx-input",
                                                                                                placeholder="regex 或 expression",
                                                                                                style={"width": "100%"},
                                                                                            ),
                                                                                        ],
                                                                                        className="protocol-field",
                                                                                    ),
                                                                                    html.Div(
                                                                                        [
                                                                                            html.Label("Regex Group", className="protocol-field-label"),
                                                                                            dcc.Input(
                                                                                                id="protocol-step-edit-parse-group",
                                                                                                className="qx-input",
                                                                                                placeholder="1",
                                                                                                value="1",
                                                                                                style={"width": "100%"},
                                                                                            ),
                                                                                        ],
                                                                                        className="protocol-field",
                                                                                    ),
                                                                                    html.Div(),
                                                                                ],
                                                                                className="protocol-inline-grid",
                                                                                style={"marginTop": "8px"},
                                                                            ),
                                                                            html.Label("参数 JSON", className="protocol-field-label"),
                                                                            dcc.Textarea(
                                                                                id="protocol-step-edit-params-json",
                                                                                className="protocol-json-editor protocol-json-editor-sm",
                                                                                value="{}",
                                                                            ),
                                                                            html.Div(
                                                                                [
                                                                                    html.Button(
                                                                                        "保存当前步骤",
                                                                                        id="protocol-step-save-btn",
                                                                                        n_clicks=0,
                                                                                        className="qx-btn qx-btn-secondary qx-btn-sm",
                                                                                    ),
                                                                                    html.Button(
                                                                                        "删除当前步骤",
                                                                                        id="protocol-step-delete-btn",
                                                                                        n_clicks=0,
                                                                                        className="qx-btn qx-btn-danger qx-btn-sm",
                                                                                    ),
                                                                                    html.Button(
                                                                                        "上移",
                                                                                        id="protocol-step-up-btn",
                                                                                        n_clicks=0,
                                                                                        className="qx-btn qx-btn-soft qx-btn-sm",
                                                                                    ),
                                                                                    html.Button(
                                                                                        "下移",
                                                                                        id="protocol-step-down-btn",
                                                                                        n_clicks=0,
                                                                                        className="qx-btn qx-btn-soft qx-btn-sm",
                                                                                    ),
                                                                                ],
                                                                                className="protocol-step-editor-actions",
                                                                            ),
                                                                        ],
                                                                        className="protocol-step-editor",
                                                                    ),
                                                                ],
                                                                className="protocol-details-body",
                                                            ),
                                                        ],
                                                        className="protocol-details",
                                                        open=True,
                                                    ),
                                                    html.Details(
                                                        [
                                                            html.Summary("MQTT setup 步骤", className="protocol-details-summary"),
                                                            html.Div(
                                                                [
                                                                    html.Div(
                                                                        [
                                                                            html.Button(
                                                                                "+ 添加 setup",
                                                                                id="protocol-add-setup-step-btn",
                                                                                n_clicks=0,
                                                                                className="qx-btn qx-btn-soft qx-btn-sm",
                                                                            ),
                                                                        ],
                                                                        className="protocol-panel-header",
                                                                    ),
                                                                    html.Div(
                                                                        id="protocol-setup-steps-list",
                                                                        className="protocol-steps-list",
                                                                    ),
                                                                    html.Div(
                                                                        [
                                                                            html.Div("setup 详情编辑", className="protocol-step-editor-title"),
                                                                            html.Div(
                                                                                [
                                                                                    html.Div(
                                                                                        [
                                                                                            html.Label("步骤 ID", className="protocol-field-label"),
                                                                                            dcc.Input(
                                                                                                id="protocol-setup-edit-id",
                                                                                                className="qx-input",
                                                                                                placeholder="如 subscribe",
                                                                                                style={"width": "100%"},
                                                                                            ),
                                                                                        ],
                                                                                        className="protocol-field",
                                                                                    ),
                                                                                    html.Div(
                                                                                        [
                                                                                            html.Label("步骤名称", className="protocol-field-label"),
                                                                                            dcc.Input(
                                                                                                id="protocol-setup-edit-name",
                                                                                                className="qx-input",
                                                                                                placeholder="如 订阅主题",
                                                                                                style={"width": "100%"},
                                                                                            ),
                                                                                        ],
                                                                                        className="protocol-field",
                                                                                    ),
                                                                                ],
                                                                                className="protocol-inline-grid protocol-inline-grid-2",
                                                                            ),
                                                                            html.Div(
                                                                                [
                                                                                    html.Div(
                                                                                        [
                                                                                            html.Label("触发方式", className="protocol-field-label"),
                                                                                            dcc.Input(
                                                                                                className="qx-input",
                                                                                                value="setup",
                                                                                                disabled=True,
                                                                                                style={"width": "100%"},
                                                                                            ),
                                                                                        ],
                                                                                        className="protocol-field",
                                                                                    ),
                                                                                    html.Div(
                                                                                        [
                                                                                            html.Label("动作", className="protocol-field-label"),
                                                                                            dcc.Dropdown(
                                                                                                id="protocol-setup-edit-action",
                                                                                                options=[
                                                                                                    {"label": "mqtt.subscribe", "value": "mqtt.subscribe"},
                                                                                                    {"label": "delay", "value": "delay"},
                                                                                                ],
                                                                                                value="mqtt.subscribe",
                                                                                                clearable=False,
                                                                                                className="qx-dropdown",
                                                                                            ),
                                                                                        ],
                                                                                        className="protocol-field",
                                                                                    ),
                                                                                    html.Div(
                                                                                        [
                                                                                            html.Label("解析类型", className="protocol-field-label"),
                                                                                            dcc.Dropdown(
                                                                                                id="protocol-setup-edit-parse-type",
                                                                                                options=PARSE_TYPE_OPTIONS,
                                                                                                value="",
                                                                                                clearable=False,
                                                                                                className="qx-dropdown",
                                                                                            ),
                                                                                        ],
                                                                                        className="protocol-field",
                                                                                    ),
                                                                                ],
                                                                                className="protocol-inline-grid",
                                                                                style={"marginTop": "8px"},
                                                                            ),
                                                                            html.Div(
                                                                                [
                                                                                    html.Div(
                                                                                        [
                                                                                            html.Label("解析规则", className="protocol-field-label"),
                                                                                            dcc.Input(
                                                                                                id="protocol-setup-edit-parse-rule",
                                                                                                className="qx-input",
                                                                                                placeholder="regex 或 expression",
                                                                                                style={"width": "100%"},
                                                                                            ),
                                                                                        ],
                                                                                        className="protocol-field",
                                                                                    ),
                                                                                    html.Div(
                                                                                        [
                                                                                            html.Label("Regex Group", className="protocol-field-label"),
                                                                                            dcc.Input(
                                                                                                id="protocol-setup-edit-parse-group",
                                                                                                className="qx-input",
                                                                                                placeholder="1",
                                                                                                value="1",
                                                                                                style={"width": "100%"},
                                                                                            ),
                                                                                        ],
                                                                                        className="protocol-field",
                                                                                    ),
                                                                                    html.Div(),
                                                                                ],
                                                                                className="protocol-inline-grid",
                                                                                style={"marginTop": "8px"},
                                                                            ),
                                                                            html.Label("参数 JSON", className="protocol-field-label"),
                                                                            dcc.Textarea(
                                                                                id="protocol-setup-edit-params-json",
                                                                                className="protocol-json-editor protocol-json-editor-sm",
                                                                                value="{}",
                                                                            ),
                                                                            html.Div(
                                                                                [
                                                                                    html.Button(
                                                                                        "保存当前 setup",
                                                                                        id="protocol-setup-save-btn",
                                                                                        n_clicks=0,
                                                                                        className="qx-btn qx-btn-secondary qx-btn-sm",
                                                                                    ),
                                                                                    html.Button(
                                                                                        "删除当前 setup",
                                                                                        id="protocol-setup-delete-btn",
                                                                                        n_clicks=0,
                                                                                        className="qx-btn qx-btn-danger qx-btn-sm",
                                                                                    ),
                                                                                    html.Button(
                                                                                        "上移",
                                                                                        id="protocol-setup-up-btn",
                                                                                        n_clicks=0,
                                                                                        className="qx-btn qx-btn-soft qx-btn-sm",
                                                                                    ),
                                                                                    html.Button(
                                                                                        "下移",
                                                                                        id="protocol-setup-down-btn",
                                                                                        n_clicks=0,
                                                                                        className="qx-btn qx-btn-soft qx-btn-sm",
                                                                                    ),
                                                                                ],
                                                                                className="protocol-step-editor-actions",
                                                                            ),
                                                                        ],
                                                                        className="protocol-step-editor",
                                                                    ),
                                                                ],
                                                                className="protocol-details-body",
                                                            ),
                                                        ],
                                                        id="protocol-setup-section",
                                                        className="protocol-details",
                                                        open=True,
                                                    ),
                                                    html.Details(
                                                        [
                                                            html.Summary("MQTT message_handler", className="protocol-details-summary"),
                                                            html.Div(
                                                                [
                                                                    html.Div(
                                                                        [
                                                                            dcc.Input(
                                                                                id="protocol-form-message-id",
                                                                                className="qx-input",
                                                                                placeholder="id",
                                                                                style={"width": "100%"},
                                                                            ),
                                                                            dcc.Input(
                                                                                id="protocol-form-message-name",
                                                                                className="qx-input",
                                                                                placeholder="name",
                                                                                style={"width": "100%"},
                                                                            ),
                                                                            dcc.Dropdown(
                                                                                id="protocol-form-message-action",
                                                                                options=MQTT_MESSAGE_ACTION_OPTIONS,
                                                                                value="mqtt.on_message",
                                                                                clearable=False,
                                                                                className="qx-dropdown",
                                                                            ),
                                                                        ],
                                                                        className="protocol-inline-grid",
                                                                    ),
                                                                    html.Div(
                                                                        [
                                                                            dcc.Dropdown(
                                                                                id="protocol-form-message-parse-type",
                                                                                options=PARSE_TYPE_OPTIONS,
                                                                                value="regex",
                                                                                clearable=False,
                                                                                className="qx-dropdown",
                                                                            ),
                                                                            dcc.Input(
                                                                                id="protocol-form-message-parse-rule",
                                                                                className="qx-input",
                                                                                placeholder="正则 pattern 或 expression",
                                                                                style={"width": "100%"},
                                                                            ),
                                                                            dcc.Input(
                                                                                id="protocol-form-message-parse-group",
                                                                                className="qx-input",
                                                                                placeholder="group (regex 用)",
                                                                                value="1",
                                                                                style={"width": "100%"},
                                                                            ),
                                                                        ],
                                                                        className="protocol-inline-grid",
                                                                        style={"marginTop": "8px"},
                                                                    ),
                                                                ],
                                                                className="protocol-sub-panel",
                                                            ),
                                                        ],
                                                        id="protocol-message-section",
                                                        className="protocol-details",
                                                        open=True,
                                                    ),
                                                    html.Details(
                                                        [
                                                            html.Summary("输出映射", className="protocol-details-summary"),
                                                            html.Div(
                                                                [
                                                                    html.Div(
                                                                        [
                                                                            dcc.Input(
                                                                                id="protocol-form-output-weight",
                                                                                className="qx-input",
                                                                                placeholder="weight 映射，如 ${steps.read_weight.result}",
                                                                                style={"width": "100%"},
                                                                            ),
                                                                            dcc.Input(
                                                                                id="protocol-form-output-unit",
                                                                                className="qx-input",
                                                                                placeholder="unit",
                                                                                value="kg",
                                                                                style={"width": "100%"},
                                                                            ),
                                                                        ],
                                                                        className="protocol-inline-grid",
                                                                    ),
                                                                ],
                                                                className="protocol-sub-panel",
                                                            ),
                                                        ],
                                                        className="protocol-details",
                                                        open=True,
                                                    ),
                                                    html.Div(id="protocol-form-validation", className="protocol-validation-box"),
                                                ],
                                                id="protocol-form-input-panel",
                                                className="protocol-form-stack",
                                            ),
                                        ],
                                        style={"marginTop": "10px"},
                                    ),
                                    html.Button(
                                        "创建模板",
                                        id="create-protocol-btn",
                                        n_clicks=0,
                                        className="qx-btn qx-btn-primary",
                                        style={"marginTop": "12px"},
                                    ),
                                    html.Div(id="create-protocol-result", style={"marginTop": "8px"}),
                                ],
                                className="protocol-editor-main",
                            ),
                            html.Div(
                                [
                                    html.Div("实时 JSON 预览", className="protocol-preview-title"),
                                    dcc.Textarea(
                                        id="protocol-json-preview",
                                        className="protocol-json-preview",
                                        readOnly=True,
                                        value="{}",
                                    ),
                                    html.Div(id="protocol-json-validation-status", className="protocol-validation-box"),
                                ],
                                id="protocol-editor-preview",
                                className="protocol-editor-preview",
                            ),
                        ],
                        id="protocol-editor-grid",
                        className="protocol-editor-grid",
                    ),
                ],
                className="protocol-card",
            ),
            html.Hr(style={"margin": "20px 0"}),
            html.Div(
                [
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
                                className="protocol-json-editor",
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
                ],
                className="protocol-card",
            ),
            html.Div(
                [
                    html.H3("单步测试（test-step）"),
                    html.Div(
                        [
                            dcc.Dropdown(
                                id="protocol-step-test-context",
                                options=[
                                    {"label": "setup", "value": "setup"},
                                    {"label": "poll", "value": "poll"},
                                    {"label": "event", "value": "event"},
                                ],
                                value="poll",
                                clearable=False,
                                className="qx-dropdown",
                            ),
                            dcc.Dropdown(
                                id="protocol-step-test-id",
                                options=[],
                                placeholder="选择步骤 id",
                                className="qx-dropdown",
                            ),
                            dcc.Checklist(
                                id="protocol-step-test-allow-write",
                                options=[{"label": "允许写操作", "value": "allow"}],
                                value=[],
                                style={"paddingTop": "8px"},
                            ),
                        ],
                        className="protocol-inline-grid",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Label("连接参数 JSON"),
                                    dcc.Textarea(
                                        id="protocol-step-test-conn-json",
                                        className="protocol-json-editor",
                                        value="{}",
                                    ),
                                ]
                            ),
                            html.Div(
                                [
                                    html.Label("变量 JSON"),
                                    dcc.Textarea(
                                        id="protocol-step-test-vars-json",
                                        className="protocol-json-editor",
                                        value="{}",
                                    ),
                                ]
                            ),
                        ],
                        className="protocol-inline-grid",
                        style={"marginTop": "8px"},
                    ),
                    html.Div(
                        [
                            html.Label("event 测试 payload"),
                            dcc.Textarea(
                                id="protocol-step-test-payload",
                                className="protocol-json-editor",
                                value="",
                            ),
                        ],
                        style={"marginTop": "8px"},
                    ),
                    html.Button(
                        "执行单步测试",
                        id="protocol-step-test-btn",
                        n_clicks=0,
                        className="qx-btn qx-btn-secondary",
                        style={"marginTop": "10px"},
                    ),
                    html.Div(id="protocol-step-test-result", style={"marginTop": "8px"}),
                ],
                className="protocol-card",
                style={"marginTop": "20px"},
            ),
        ]
    )
