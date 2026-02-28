from __future__ import annotations

from dash import dcc, html


def layout() -> html.Div:
    return html.Div(
        [
            # WebSocket is primary data path; keep low-frequency polling as fallback sync.
            dcc.Interval(id="dashboard-interval", interval=10000, n_intervals=0),
            dcc.Store(id="dashboard-live-store", data={}),
            dcc.Store(id="dashboard-last-render-ts", data=0.0),
            html.H2("实时数据大屏"),
            html.Div(
                id="dashboard-ws-status",
                style={"fontSize": "12px", "color": "#475569", "marginBottom": "6px"},
            ),
            html.Div(id="dashboard-error", style={"color": "#c62828", "marginBottom": "8px"}),
            html.Div(
                id="dashboard-cards",
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(auto-fill, minmax(240px, 1fr))",
                    "gap": "12px",
                },
            ),
        ]
    )
