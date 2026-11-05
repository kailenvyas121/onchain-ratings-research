"""
House chart style -- Coinbase institutional parity.

Mirrors the team's create_default_figure() spec: Coinbase Display type, white canvas,
y-gridlines only, black axis lines, horizontal legend below the plot, single grey
source footnote bottom-left. Minimal text -- the chart carries the message, not prose.
"""
from __future__ import annotations

import plotly.graph_objects as go

# "Coinbase Display" is the house face; "Coinbase Sans" is the locally installed
# fallback so exports render in-family on this machine too.
FONT = "Coinbase Display, Coinbase Sans, Helvetica, Arial"

BLUE = "#1414E8"    # primary series
GREY = "#8A8A8A"    # comparison series
LGREY = "#C4C4C4"   # tertiary series
NAVY = "#3D5588"
PURPLE = "#6B5B95"
BLACK = "#000000"

# Backtest exhibits (growth of $1, drawdown, metrics table)
GREEN = "#12A150"       # strategy line
DGREY = "#4A4A4A"       # buy & hold benchmark line
SHADE = "#E3E3E3"       # benchmark drawdown fill
TABLE_BLUE = "#0052FF"  # strategy column header
TABLE_GREEN = "#E6F4EA" # strategy column cells
TABLE_ROW = "#F7F7F7"   # alternating benchmark cells


def create_default_figure(title: str = "",
                          xlabel: str = "",
                          ylabel: str = "",
                          source_text: str = "",
                          ysource_text_offset: float = 0.3,
                          ylegend_offset: float = 0.17,
                          width: int = 900,
                          height: int = 500) -> go.Figure:
    fig = go.Figure()

    fig.update_layout(
        xaxis=dict(
            title=xlabel,
            title_font=dict(family=FONT, size=18),
            tickfont=dict(family=FONT, size=16, color="black"),
            linecolor="black",
            linewidth=0.75,
            showgrid=False,
            gridcolor="lightgray",
            color="black",
        ),
        yaxis=dict(
            title=ylabel,
            title_font=dict(family=FONT, size=18),
            title_standoff=15,
            tickfont=dict(family=FONT, size=16),
            color="black",
            linecolor="black",
            linewidth=0.75,
            showgrid=True,
            gridcolor="lightgray",
            zerolinecolor="black",
        ),
        legend=dict(
            title_text="",
            font=dict(family=FONT, size=16, color="black"),
            orientation="h",
            yanchor="bottom",
            y=-ylegend_offset,
            xanchor="center",
            x=0.49,
        ),
        autosize=False,
        width=width,
        height=height,
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=80, r=50, t=20, b=120),
        barmode="relative",
        bargap=0.1,
        bargroupgap=0.05,
    )

    fig.layout.annotations = ()

    fig.add_annotation(
        text="Sources: " + source_text,
        xref="paper", yref="paper",
        x=-0.08, y=-ysource_text_offset,
        showarrow=False,
        xanchor="left",
        align="left",
        font=dict(family=FONT, size=14, color="grey"),
    )

    return fig
