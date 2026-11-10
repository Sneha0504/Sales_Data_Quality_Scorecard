"""Build the self-contained Plotly data-quality dashboard.

Reads the precomputed curated CSVs (never the raw row-level data) and renders a
single standalone HTML file -- ``docs_site/index.html`` -- with the Plotly
library inlined, so it opens from the local filesystem with no server.

Sections:

1. **Scorecard** -- failure rate per rule, colored by severity.
2. **Reconciliation** -- raw vs curated headline metrics, with % change labeled.
3. **Trend** -- monthly failure rate per rule across the two-year range.

All numbers are read from the curated outputs, so the dashboard always reflects
the latest pipeline run.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

from config_util import configure_logging, load_config, resolve_path

logger = logging.getLogger("dashboard")

# Severity -> bar color (color-blind-friendly, distinct in grayscale).
SEVERITY_COLORS = {"critical": "#c0392b", "warning": "#e69f00"}
# Raw vs curated bar colors for the reconciliation panel.
RAW_COLOR = "#95a5a6"
CURATED_COLOR = "#2c7fb8"
# Human-readable labels for the reconciliation metrics.
METRIC_LABELS = {
    "total_revenue": "Revenue (£)",
    "distinct_orders": "Distinct orders",
    "line_items": "Line items",
    "distinct_customers": "Distinct customers",
}


def _read_csv(path: Path) -> pd.DataFrame:
    """Read a curated CSV, raising a clear error if it is missing."""
    if not path.exists():
        raise FileNotFoundError(f"Required curated input not found: {path}. Run `make all` first.")
    return pd.read_csv(path)


def build_scorecard(rule_results: pd.DataFrame, total_rows: int) -> go.Figure:
    """Build the per-rule failure-rate scorecard, colored by severity.

    Args:
        rule_results: The ``rule_results.csv`` contents.
        total_rows: Raw row count, used for pass/fail counts in the hover.

    Returns:
        A Plotly bar figure.
    """
    data = rule_results.sort_values("failure_rate", ascending=False)
    labels = [f"{row.id} {row.name}" for row in data.itertuples()]
    rates = data["failure_rate"] * 100
    colors = [SEVERITY_COLORS.get(sev, "#7f8c8d") for sev in data["severity"]]
    customdata = list(
        zip(
            data["severity"],
            data["handling"],
            data["failure_count"],
            total_rows - data["failure_count"],
            strict=True,
        )
    )

    fig = go.Figure(
        go.Bar(
            x=rates,
            y=labels,
            orientation="h",
            marker_color=colors,
            customdata=customdata,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Failure rate: %{x:.3f}%<br>"
                "Severity: %{customdata[0]}<br>"
                "Handling: %{customdata[1]}<br>"
                "Failing rows: %{customdata[2]:,}<br>"
                "Passing rows: %{customdata[3]:,}<extra></extra>"
            ),
        )
    )
    # Manual legend entries for the two severities.
    for severity, color in SEVERITY_COLORS.items():
        fig.add_trace(
            go.Bar(
                x=[None],
                y=[None],
                marker_color=color,
                name=severity,
                showlegend=True,
                hoverinfo="skip",
            )
        )
    fig.update_layout(
        title="Rule scorecard: failure rate per rule (colored by severity)",
        xaxis_title="Failure rate (% of raw rows)",
        yaxis=dict(autorange="reversed"),
        barmode="overlay",
        template="plotly_white",
        height=460,
        margin=dict(l=240, r=40, t=60, b=50),
        legend=dict(title="Severity", orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    return fig


def build_reconciliation(reconciliation: pd.DataFrame) -> go.Figure:
    """Build the raw-vs-curated before/after panel with % change labels.

    Each metric gets its own subplot (the metrics differ by orders of
    magnitude), with raw and curated bars and the percent change annotated.

    Args:
        reconciliation: The ``reconciliation.csv`` contents.

    Returns:
        A Plotly subplot figure.
    """
    metrics = list(reconciliation["metric"])
    titles = [METRIC_LABELS.get(m, m) for m in metrics]
    fig = make_subplots(rows=1, cols=len(metrics), subplot_titles=titles)

    for col, (_, row) in enumerate(reconciliation.iterrows(), start=1):
        pct = row["pct_diff"] * 100
        fig.add_trace(
            go.Bar(
                x=["Raw", "Curated"],
                y=[row["raw"], row["curated"]],
                marker_color=[RAW_COLOR, CURATED_COLOR],
                text=[f"{row['raw']:,.0f}", f"{row['curated']:,.0f}"],
                textposition="auto",
                hovertemplate="%{x}: %{y:,.2f}<extra></extra>",
                showlegend=False,
            ),
            row=1,
            col=col,
        )
        fig.add_annotation(
            text=f"{pct:+.2f}%",
            xref=f"x{col} domain" if col > 1 else "x domain",
            yref=f"y{col} domain" if col > 1 else "y domain",
            x=0.5,
            y=1.08,
            showarrow=False,
            font=dict(size=13, color="#2c3e50"),
        )

    fig.update_layout(
        title="Reconciliation: raw vs curated headline metrics (% change labeled)",
        template="plotly_white",
        height=420,
        margin=dict(l=50, r=40, t=90, b=50),
    )
    return fig


def build_trend(failure_trend: pd.DataFrame) -> go.Figure:
    """Build the monthly failure-rate-per-rule trend.

    Args:
        failure_trend: The ``failure_trend.csv`` contents.

    Returns:
        A Plotly line figure, one line per rule (toggle via the legend).
    """
    fig = go.Figure()
    for rule_id, group in failure_trend.groupby("rule_id"):
        group = group.sort_values("month")
        name = f"{rule_id} {group['rule_name'].iloc[0]}"
        fig.add_trace(
            go.Scatter(
                x=group["month"],
                y=group["failure_rate"] * 100,
                mode="lines+markers",
                name=name,
                hovertemplate=(
                    "%{x} - " + name + "<br>"
                    "Failure rate: %{y:.3f}%<extra></extra>"
                ),
            )
        )
    fig.update_layout(
        title="Monthly failure rate per rule (Dec 2009 to Dec 2011)",
        xaxis_title="Month",
        yaxis_title="Failure rate (% of that month's rows)",
        template="plotly_white",
        height=520,
        margin=dict(l=60, r=40, t=60, b=60),
        legend=dict(title="Rule (click to toggle)"),
    )
    return fig


def render_html(figures: list[go.Figure], output_path: Path) -> None:
    """Render the figures into one standalone HTML file with Plotly inlined.

    Only the first figure embeds the Plotly library; the rest reference the same
    inlined copy, keeping the file self-contained and reasonably small.

    Args:
        figures: Figures to render, in display order.
        output_path: Destination HTML file.
    """
    blocks: list[str] = []
    for index, fig in enumerate(figures):
        include = "inline" if index == 0 else False
        blocks.append(
            pio.to_html(fig, full_html=False, include_plotlyjs=include, config={"responsive": True})
        )

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sales Data Quality Scorecard</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
         margin: 0; padding: 0 16px 48px; color: #2c3e50; background: #ffffff; }}
  header {{ max-width: 1100px; margin: 0 auto; padding: 28px 0 8px; }}
  h1 {{ font-size: 1.6rem; margin: 0 0 6px; }}
  p.lead {{ color: #5d6d7e; margin: 0 0 8px; }}
  section {{ max-width: 1100px; margin: 0 auto 28px; }}
  footer {{ max-width: 1100px; margin: 24px auto 0; color: #85929e; font-size: 0.85rem;
           border-top: 1px solid #ececec; padding-top: 12px; }}
</style>
</head>
<body>
<header>
  <h1>Sales Data Quality Scorecard</h1>
  <p class="lead">Data-quality and governance view of the Online Retail II wholesale
  transaction dataset (UCI ML Repository), Dec 2009 to Dec 2011. All figures are
  precomputed from the curated data layer.</p>
</header>
<section>{blocks[0]}</section>
<section>{blocks[1]}</section>
<section>{blocks[2]}</section>
<footer>
  Scorecard shows the share of raw rows failing each rule. Reconciliation compares
  raw vs curated headline numbers. Trend shows monthly failure rates across the
  two-year window. Data source: Online Retail II, UCI Machine Learning Repository
  (CC BY 4.0).
</footer>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page, encoding="utf-8")
    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info("Wrote self-contained dashboard: %s (%.2f MB)", output_path, size_mb)


def main() -> None:
    """Build the dashboard from configuration."""
    config: dict[str, Any] = load_config()
    configure_logging(config)
    curated_dir = resolve_path(config["paths"]["curated_dir"])
    outputs = config["outputs"]
    output_path = resolve_path(config["paths"]["dashboard_html"])

    rule_results = _read_csv(curated_dir / outputs["rule_results_csv"])
    reconciliation = _read_csv(curated_dir / outputs["reconciliation_csv"])
    failure_trend = _read_csv(curated_dir / outputs["failure_trend_csv"])

    total_rows = int(reconciliation.loc[reconciliation["metric"] == "line_items", "raw"].iloc[0])
    logger.info("Loaded curated inputs; raw row count = %d", total_rows)

    figures = [
        build_scorecard(rule_results, total_rows),
        build_reconciliation(reconciliation),
        build_trend(failure_trend),
    ]
    render_html(figures, output_path)
    logger.info("Dashboard build complete.")


if __name__ == "__main__":
    main()
