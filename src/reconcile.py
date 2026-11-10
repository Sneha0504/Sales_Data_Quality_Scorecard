"""Reconcile raw vs curated headline numbers and verify the curation identity.

Compares the raw ``transactions`` table against the curated data layer on four
headline metrics (total revenue, distinct orders, line items, distinct
customers), reporting raw value, curated value, absolute diff and percent diff.
It also verifies the internal identity that the excluded rows plus the curated
rows account for the full raw dataset, in both row count and revenue.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from config_util import configure_logging, load_config, resolve_path
from rule_engine import attribute_exclusions, load_catalog, run_catalog

logger = logging.getLogger("reconcile")


def _revenue(frame: pd.DataFrame) -> float:
    """Total revenue (Quantity * Price) for a frame."""
    return float((frame["Quantity"] * frame["Price"]).sum())


def compute_metrics(frame: pd.DataFrame) -> dict[str, float]:
    """Compute the four headline metrics for a transactions frame."""
    return {
        "total_revenue": _revenue(frame),
        "distinct_orders": float(frame["Invoice"].astype(str).nunique()),
        "line_items": float(len(frame)),
        "distinct_customers": float(frame["Customer ID"].nunique(dropna=True)),
    }


def _load_raw(db_path: Path, table: str) -> pd.DataFrame:
    """Load the raw transactions table indexed by rowid."""
    with sqlite3.connect(db_path) as conn:
        frame = pd.read_sql_query(f'SELECT rowid AS rowid, * FROM "{table}"', conn)
    return frame.set_index("rowid", drop=False)


def _load_curated(curated_dir: Path, filename: str) -> pd.DataFrame:
    """Load the curated transactions CSV, preferring a gzip variant if present."""
    csv_path = curated_dir / filename
    gz_path = csv_path.with_suffix(csv_path.suffix + ".gz")
    if csv_path.exists():
        return pd.read_csv(csv_path)
    if gz_path.exists():
        return pd.read_csv(gz_path, compression="gzip")
    raise FileNotFoundError(f"No curated transactions file at {csv_path} or {gz_path}")


def build_reconciliation(raw: pd.DataFrame, curated: pd.DataFrame) -> pd.DataFrame:
    """Build the raw-vs-curated reconciliation table with diffs.

    Args:
        raw: Raw transactions frame.
        curated: Curated transactions frame.

    Returns:
        A DataFrame with metric, raw, curated, abs_diff and pct_diff columns.
    """
    raw_metrics = compute_metrics(raw)
    curated_metrics = compute_metrics(curated)
    records: list[dict[str, Any]] = []
    for metric, raw_value in raw_metrics.items():
        curated_value = curated_metrics[metric]
        abs_diff = curated_value - raw_value
        pct_diff = (abs_diff / raw_value) if raw_value else 0.0
        records.append(
            {
                "metric": metric,
                "raw": raw_value,
                "curated": curated_value,
                "abs_diff": abs_diff,
                "pct_diff": pct_diff,
            }
        )
    return pd.DataFrame.from_records(records)


def verify_identity(
    raw: pd.DataFrame, curated: pd.DataFrame, owner: dict[int, str], tolerance: float
) -> bool:
    """Verify curated + excluded == raw for row count and revenue.

    Args:
        raw: Raw transactions indexed by rowid.
        curated: Curated transactions frame.
        owner: Mapping of excluded rowid to owning rule id.
        tolerance: Absolute float tolerance for the revenue check.

    Returns:
        True if both identities hold within tolerance.
    """
    excluded = raw.loc[list(owner.keys())]
    count_ok = (len(curated) + len(excluded)) == len(raw)
    revenue_ok = abs((_revenue(curated) + _revenue(excluded)) - _revenue(raw)) <= tolerance
    logger.info(
        "Identity check: rows %d + %d == %d -> %s; revenue %.2f + %.2f == %.2f -> %s",
        len(curated),
        len(excluded),
        len(raw),
        count_ok,
        _revenue(curated),
        _revenue(excluded),
        _revenue(raw),
        revenue_ok,
    )
    return bool(count_ok and revenue_ok)


def log_table(recon: pd.DataFrame) -> None:
    """Log the reconciliation table in a readable form."""
    logger.info("=== Reconciliation (raw vs curated) ===")
    for _, row in recon.iterrows():
        logger.info(
            "%-18s raw=%15.2f curated=%15.2f abs_diff=%15.2f pct_diff=%+.4f%%",
            row["metric"],
            row["raw"],
            row["curated"],
            row["abs_diff"],
            row["pct_diff"] * 100,
        )


def reconcile(
    config: dict[str, Any],
    raw_frame: pd.DataFrame | None = None,
    curated_frame: pd.DataFrame | None = None,
    owner: dict[int, str] | None = None,
) -> pd.DataFrame:
    """Run reconciliation, verify the identity, and write ``reconciliation.csv``.

    When called from curation, ``raw_frame``, ``curated_frame`` and ``owner`` are
    passed in. When run standalone, raw is read from the warehouse, curated from
    the curated CSV, and the exclusion ownership is recomputed from the catalog.

    Args:
        config: Parsed configuration.
        raw_frame: Optional raw transactions (indexed by rowid).
        curated_frame: Optional curated transactions.
        owner: Optional mapping of excluded rowid to owning rule id.

    Returns:
        The reconciliation DataFrame.
    """
    db_path = resolve_path(config["paths"]["warehouse_db"])
    curated_dir = resolve_path(config["paths"]["curated_dir"])
    table = config["load"]["table"]
    outputs = config["outputs"]
    tolerance = float(config["reconcile"]["float_tolerance"])

    raw = raw_frame if raw_frame is not None else _load_raw(db_path, table)
    curated = (
        curated_frame
        if curated_frame is not None
        else _load_curated(curated_dir, outputs["transactions_csv"])
    )
    if owner is None:
        catalog = load_catalog(resolve_path(config["paths"]["rule_catalog"]))
        results = run_catalog(db_path, catalog, table)
        owner, _ = attribute_exclusions(results, config["curate"]["exclude_precedence"])

    recon = build_reconciliation(raw, curated)
    log_table(recon)

    identity_ok = verify_identity(raw, curated, owner, tolerance)
    if not identity_ok:
        raise AssertionError("Reconciliation identity failed: curated + excluded != raw")

    curated_dir.mkdir(parents=True, exist_ok=True)
    recon_path = curated_dir / outputs["reconciliation_csv"]
    recon.to_csv(recon_path, index=False)
    logger.info("Wrote %s (identity holds: %s)", recon_path, identity_ok)
    return recon


def main() -> None:
    """Run reconciliation standalone from configuration."""
    config = load_config()
    configure_logging(config)
    reconcile(config)


if __name__ == "__main__":
    main()
