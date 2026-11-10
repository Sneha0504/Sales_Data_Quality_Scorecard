"""Profile the loaded ``transactions`` table and draft the data-quality report.

Computes factual profiling metrics (types, missing rates, distinct counts,
invoice/cancellation patterns, quantity/price ranges, country distribution)
straight from the SQLite table and writes a Markdown report built from those
real numbers. The rule-results section is filled from the curated
``rule_results.csv`` when it exists, otherwise a placeholder is written.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from config_util import configure_logging, load_config, resolve_path

logger = logging.getLogger("profile")


def load_table(db_path: Path, table: str) -> pd.DataFrame:
    """Load the transactions table (including ``rowid``) into a DataFrame."""
    with sqlite3.connect(db_path) as conn:
        frame = pd.read_sql_query(f'SELECT rowid AS rowid, * FROM "{table}"', conn)
    return frame


def profile(frame: pd.DataFrame) -> dict[str, Any]:
    """Compute profiling metrics from the transactions DataFrame.

    Args:
        frame: The loaded transactions table.

    Returns:
        A dictionary of profiling metrics suitable for reporting.
    """
    total = len(frame)
    invoice = frame["Invoice"].astype(str)
    stock = frame["StockCode"].astype(str)

    missing = {
        col: {
            "missing": int(frame[col].isna().sum()),
            "rate": float(frame[col].isna().mean()),
        }
        for col in frame.columns
    }

    metrics: dict[str, Any] = {
        "row_count": total,
        "column_types": {col: str(dtype) for col, dtype in frame.dtypes.items()},
        "missing": missing,
        "distinct_customers": int(frame["Customer ID"].nunique(dropna=True)),
        "distinct_stock_codes": int(stock.nunique()),
        "distinct_invoices": int(invoice.nunique()),
        "cancellation_invoices_rows": int(invoice.str.startswith("C").sum()),
        "quantity_min": int(frame["Quantity"].min()),
        "quantity_max": int(frame["Quantity"].max()),
        "quantity_non_positive": int((frame["Quantity"] <= 0).sum()),
        "price_min": float(frame["Price"].min()),
        "price_max": float(frame["Price"].max()),
        "price_non_positive": int((frame["Price"] <= 0).sum()),
        "date_min": str(frame["InvoiceDate"].min()),
        "date_max": str(frame["InvoiceDate"].max()),
        "country_counts": frame["Country"].value_counts().head(15).to_dict(),
        "country_unspecified": int((frame["Country"].astype(str) == "Unspecified").sum()),
        "quantity_abs_p999": float(frame["Quantity"].abs().quantile(0.999)),
        "price_p999": float(frame["Price"].quantile(0.999)),
    }
    return metrics


def log_profile(metrics: dict[str, Any]) -> None:
    """Log the profiling metrics as a readable summary."""
    logger.info("Row count: %d", metrics["row_count"])
    logger.info("Date range: %s -> %s", metrics["date_min"], metrics["date_max"])
    logger.info("Distinct customers: %d", metrics["distinct_customers"])
    logger.info("Distinct stock codes: %d", metrics["distinct_stock_codes"])
    logger.info("Distinct invoices: %d", metrics["distinct_invoices"])
    logger.info("Cancellation (C-prefixed) rows: %d", metrics["cancellation_invoices_rows"])
    logger.info(
        "Quantity range: %d..%d (%d non-positive)",
        metrics["quantity_min"],
        metrics["quantity_max"],
        metrics["quantity_non_positive"],
    )
    logger.info(
        "Price range: %.2f..%.2f (%d non-positive)",
        metrics["price_min"],
        metrics["price_max"],
        metrics["price_non_positive"],
    )
    for col, info in metrics["missing"].items():
        if info["missing"]:
            logger.info("Missing %s: %d (%.2f%%)", col, info["missing"], info["rate"] * 100)


def _rule_results_section(rule_results_csv: Path) -> str:
    """Build the rule-results section from the curated CSV, if present."""
    if not rule_results_csv.exists():
        return (
            "## Rule results\n\n"
            "_Placeholder — run `make rules` / `make curate` to populate this "
            "section from `data/curated/rule_results.csv`._\n"
        )
    results = pd.read_csv(rule_results_csv)
    lines = [
        "## Rule results\n",
        "| id | name | dimension | severity | handling | failures | rate |",
        "|----|------|-----------|----------|----------|----------|------|",
    ]
    for _, row in results.iterrows():
        lines.append(
            f"| {row['id']} | {row['name']} | {row['dimension']} | {row['severity']} | "
            f"{row['handling']} | {int(row['failure_count']):,} | {row['failure_rate']:.4%} |"
        )
    return "\n".join(lines) + "\n"


def write_report(metrics: dict[str, Any], report_path: Path, rule_results_csv: Path) -> None:
    """Write the Markdown data-quality report built from real numbers.

    Args:
        metrics: Profiling metrics from :func:`profile`.
        report_path: Destination Markdown file.
        rule_results_csv: Path to the curated rule-results CSV (optional source).
    """
    report_path.parent.mkdir(parents=True, exist_ok=True)
    types_rows = "\n".join(
        f"| {col} | {dtype} |" for col, dtype in metrics["column_types"].items()
    )
    missing_rows = "\n".join(
        f"| {col} | {info['missing']:,} | {info['rate']:.4%} |"
        for col, info in metrics["missing"].items()
    )
    country_rows = "\n".join(
        f"| {country} | {count:,} |" for country, count in metrics["country_counts"].items()
    )

    body = f"""# Data Quality Report — Sales_Data_Quality_Scorecard

Factual profile of the raw `transactions` table (both yearly sheets combined),
computed directly from the loaded data.

## Dataset overview

| Metric | Value |
|--------|-------|
| Total rows | {metrics['row_count']:,} |
| Date range | {metrics['date_min']} to {metrics['date_max']} |
| Distinct invoices | {metrics['distinct_invoices']:,} |
| Distinct customers (non-null) | {metrics['distinct_customers']:,} |
| Distinct stock codes | {metrics['distinct_stock_codes']:,} |
| Cancellation invoices (C-prefixed rows) | {metrics['cancellation_invoices_rows']:,} |

## Column types

| Column | Type |
|--------|------|
{types_rows}

## Missing values

| Column | Missing | Rate |
|--------|---------|------|
{missing_rows}

## Quantity and price ranges

| Metric | Value |
|--------|-------|
| Quantity min | {metrics['quantity_min']:,} |
| Quantity max | {metrics['quantity_max']:,} |
| Quantity non-positive (<= 0) | {metrics['quantity_non_positive']:,} |
| Price min | {metrics['price_min']:,.2f} |
| Price max | {metrics['price_max']:,.2f} |
| Price non-positive (<= 0) | {metrics['price_non_positive']:,} |
| Quantity 99.9th pct (abs) | {metrics['quantity_abs_p999']:,.1f} |
| Price 99.9th pct | {metrics['price_p999']:,.2f} |

## Country distribution (top 15)

| Country | Rows |
|---------|------|
{country_rows}

Rows with country `Unspecified`: {metrics['country_unspecified']:,}.

{_rule_results_section(rule_results_csv)}"""

    report_path.write_text(body, encoding="utf-8")
    logger.info("Wrote data-quality report: %s", report_path)


def main() -> None:
    """Run profiling and write the data-quality report."""
    config = load_config()
    configure_logging(config)
    db_path = resolve_path(config["paths"]["warehouse_db"])
    table = config["load"]["table"]
    report_path = resolve_path(config["paths"]["data_quality_report"])
    curated_dir = resolve_path(config["paths"]["curated_dir"])
    rule_results_csv = curated_dir / config["outputs"]["rule_results_csv"]

    frame = load_table(db_path, table)
    metrics = profile(frame)
    log_profile(metrics)
    write_report(metrics, report_path, rule_results_csv)


if __name__ == "__main__":
    main()
