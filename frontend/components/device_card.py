from __future__ import annotations

from dash import html

from frontend.time_utils import format_timestamp


def device_card(device: dict) -> html.Div:
    runtime = device.get("runtime", {})
    status = runtime.get("status", "offline")
    color = {"online": "#2e7d32", "offline": "#616161", "error": "#c62828"}.get(status, "#616161")
    weight = runtime.get("weight")
    unit = runtime.get("unit", "kg")
    ts = format_timestamp(runtime.get("timestamp"))

    return html.Div(
        [
            html.Div(device.get("name", "Unnamed"), style={"fontWeight": "700", "fontSize": "18px"}),
            html.Div(f"编号: {device.get('device_code') or '-'}", style={"fontSize": "12px", "color": "#666", "marginTop": "4px"}),
            html.Div(f"{weight if weight is not None else '--'} {unit}", style={"fontSize": "32px", "margin": "12px 0"}),
            html.Div(
                [
                    html.Span("●", style={"color": color, "marginRight": "8px"}),
                    html.Span(status),
                ]
            ),
            html.Div(f"更新时间: {ts}", style={"marginTop": "8px", "fontSize": "12px", "color": "#666"}),
        ],
        style={
            "border": "1px solid #e5e7eb",
            "borderRadius": "12px",
            "padding": "16px",
            "background": "#fff",
            "boxShadow": "0 4px 12px rgba(0,0,0,0.06)",
        },
    )
