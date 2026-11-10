"""Build the curated data layer by applying the catalog's handling rules.

Curation is driven entirely by the YAML ``handling`` field, so every change to
the curated data is traceable to a documented rule:

* ``exclude``        -> row dropped (attributed to one rule by precedence).
* ``flag``           -> row kept; its ``flag_column`` set to 1.
* ``keep_with_note`` -> row kept; its note ``flag_column`` set to 1 (never dropped).

Outputs (``data/curated/``): ``transactions.csv`` (curated line items + flags +
``revenue``), ``rule_results.csv``, ``reconciliation.csv`` and
``failure_trend.csv``. If the curated transactions CSV would exceed the
configured size it is written gzip-compressed with an aggregated monthly summary.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

import reconcile
from config_util import configure_logging, load_config, resolve_path
from rule_engine import RuleResult, attribute_exclusions, load_catalog, run_catalog

logger = logging.getLogger("curate")


def load_transactions(db_path: Path, table: str) -> pd.DataFrame:
    """Load the transactions table indexed by the stable ``rowid``."""
    with sqlite3.connect(db_path) as conn:
        frame = pd.read_sql_query(f'SELECT rowid AS rowid, * FROM "{table}"', conn)
    # SQLite stores datetimes as text; parse back for period/trend operations.
    frame["InvoiceDate"] = pd.to_datetime(frame["InvoiceDate"])
    return frame.set_index("rowid", drop=False)


def apply_handling(
    frame: pd.DataFrame, results: list[RuleResult], revenue_col: str, owner: dict[int, str]
) -> pd.DataFrame:
    """Apply flag/note columns and drop excluded rows; add the revenue column.

    Args:
        frame: Raw transactions indexed by rowid.
        results: All rule results.
        revenue_col: Name of the derived revenue column.
        owner: Mapping of excluded rowid to owning rule id.

    Returns:
        The curated DataFrame (excluded rows removed, flags set, revenue added).
    """
    curated = frame.copy()
    curated[revenue_col] = curated["Quantity"] * curated["Price"]

    for result in results:
        if result.handling in ("flag", "keep_with_note"):
            column = result.flag_column
            if not column:
                raise ValueError(
                    f"Rule {result.id} has handling {result.handling!r} but no flag_column"
                )
            curated[column] = curated.index.isin(result.failing_rowids).astype(int)

    excluded_rowids = list(owner.keys())
    curated = curated.drop(index=excluded_rowids)
    logger.info("Excluded %d rows; curated rows: %d", len(excluded_rowids), len(curated))
    return curated


def build_rule_results_frame(
    results: list[RuleResult], attributed: dict[str, int]
) -> pd.DataFrame:
    """Build the per-rule results table for ``rule_results.csv``."""
    records: list[dict[str, Any]] = []
    for result in results:
        records.append(
            {
                "id": result.id,
                "name": result.name,
                "dimension": result.dimension,
                "severity": result.severity,
                "handling": result.handling,
                "flag_column": result.flag_column or "",
                "failure_count": result.failure_count,
                "failure_rate": result.failure_rate,
                "attributed_exclusions": attributed.get(result.id, 0),
                "example_failing_rowids": ";".join(
                    str(rid) for rid in result.example_failing_rowids
                ),
            }
        )
    return pd.DataFrame.from_records(records)


def build_failure_trend_frame(
    frame: pd.DataFrame, results: list[RuleResult], period: str
) -> pd.DataFrame:
    """Build the monthly failure-rate-per-rule table for ``failure_trend.csv``.

    Args:
        frame: Raw transactions indexed by rowid (all rows, pre-curation).
        results: All rule results.
        period: Pandas period alias (e.g. ``M`` for month).

    Returns:
        A long-format DataFrame: month, rule_id, rule_name, failures, total, rate.
    """
    month = frame["InvoiceDate"].dt.to_period(period).astype(str)
    totals = month.value_counts().sort_index()
    records: list[dict[str, Any]] = []
    for result in results:
        is_fail = frame.index.isin(result.failing_rowids)
        fail_by_month = month[is_fail].value_counts()
        for period_label, total in totals.items():
            failures = int(fail_by_month.get(period_label, 0))
            records.append(
                {
                    "month": period_label,
                    "rule_id": result.id,
                    "rule_name": result.name,
                    "failures": failures,
                    "total": int(total),
                    "failure_rate": failures / total if total else 0.0,
                }
            )
    trend = pd.DataFrame.from_records(records)
    return trend.sort_values(["rule_id", "month"]).reset_index(drop=True)


def write_transactions(
    curated: pd.DataFrame,
    curated_dir: Path,
    filename: str,
    max_mb: float,
    period: str,
    summary_filename: str,
) -> None:
    """Write curated transactions, compressing and summarising if oversized.

    Drops the internal ``rowid`` index column from the committed output.

    Args:
        curated: The curated DataFrame.
        curated_dir: Output directory.
        filename: Base CSV filename from config.
        max_mb: Size threshold (MB) above which the CSV is gzip-compressed.
        period: Period alias for the aggregated monthly summary.
        summary_filename: Filename for the aggregated monthly summary (from config).
    """
    output = curated.drop(columns=["rowid"])
    csv_path = curated_dir / filename
    output.to_csv(csv_path, index=False)
    size_mb = csv_path.stat().st_size / (1024 * 1024)
    logger.info("Wrote %s (%.1f MB uncompressed)", csv_path, size_mb)

    if size_mb > max_mb:
        gz_path = csv_path.with_suffix(csv_path.suffix + ".gz")
        output.to_csv(gz_path, index=False, compression="gzip")
        csv_path.unlink()
        logger.info(
            "Curated CSV %.1f MB exceeds %.0f MB limit; wrote %s instead and removed plain CSV",
            size_mb,
            max_mb,
            gz_path,
        )
        summary = (
            output.assign(_month=output["InvoiceDate"].dt.to_period(period).astype(str))
            .groupby("_month")
            .agg(
                line_items=("Invoice", "size"),
                revenue=("revenue", "sum"),
                distinct_invoices=("Invoice", "nunique"),
                distinct_customers=("Customer ID", "nunique"),
            )
            .reset_index()
            .rename(columns={"_month": "month"})
        )
        summary_path = curated_dir / summary_filename
        summary.to_csv(summary_path, index=False)
        logger.info("Wrote aggregated monthly summary: %s", summary_path)


def main() -> None:
    """Run the full curation step from configuration."""
    config = load_config()
    configure_logging(config)
    db_path = resolve_path(config["paths"]["warehouse_db"])
    catalog_path = resolve_path(config["paths"]["rule_catalog"])
    curated_dir = resolve_path(config["paths"]["curated_dir"])
    curated_dir.mkdir(parents=True, exist_ok=True)

    table = config["load"]["table"]
    curate_cfg = config["curate"]
    outputs = config["outputs"]
    revenue_col = curate_cfg["revenue_column"]

    catalog = load_catalog(catalog_path)
    results = run_catalog(db_path, catalog, table)
    frame = load_transactions(db_path, table)

    owner, attributed = attribute_exclusions(results, curate_cfg["exclude_precedence"])
    curated = apply_handling(frame, results, revenue_col, owner)

    # Per-rule results.
    rule_results = build_rule_results_frame(results, attributed)
    rule_results.to_csv(curated_dir / outputs["rule_results_csv"], index=False)
    logger.info("Wrote %s", curated_dir / outputs["rule_results_csv"])

    # Monthly failure trend.
    trend = build_failure_trend_frame(frame, results, curate_cfg["trend_period"])
    trend.to_csv(curated_dir / outputs["failure_trend_csv"], index=False)
    logger.info("Wrote %s", curated_dir / outputs["failure_trend_csv"])

    # Curated transactions (compressed + summarised if oversized).
    write_transactions(
        curated,
        curated_dir,
        outputs["transactions_csv"],
        float(outputs["transactions_csv_max_mb"]),
        curate_cfg["trend_period"],
        outputs["transactions_monthly_summary_csv"],
    )

    # Reconciliation (also verifies the internal identity).
    reconcile.reconcile(config, raw_frame=frame, curated_frame=curated, owner=owner)
    logger.info("Curation complete.")


if __name__ == "__main__":
    main()
