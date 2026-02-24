from __future__ import annotations

from dash import dcc, html


def layout() -> html.Div:
    return html.Div(
        [
            dcc.Interval(id="dashboard-interval", interval=2000, n_intervals=0),
            html.H2("实时数据大屏"),
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
