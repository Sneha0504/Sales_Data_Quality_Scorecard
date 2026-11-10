"""Test 4 (PLAN section 8): the reconciliation identity holds.

For exclude rules, ``curated + excluded == raw`` must hold for both row count
and revenue, within float tolerance. Verified on a small synthetic dataset so
the test is fast and deterministic.
"""

from __future__ import annotations

from pathlib import Path

from curate import apply_handling, load_transactions
from reconcile import _revenue, build_reconciliation, verify_identity
from rule_engine import attribute_exclusions, load_catalog, run_catalog

REAL_CATALOG = Path(__file__).resolve().parent.parent / "rules" / "rule_catalog.yaml"
EXCLUDE_PRECEDENCE = ["R002", "R003", "R004"]
TOLERANCE = 0.01


def test_reconciliation_identity_holds(synthetic_db: Path) -> None:
    """Row count and revenue both reconcile: curated + excluded == raw."""
    catalog = load_catalog(REAL_CATALOG)
    results = run_catalog(synthetic_db, catalog, table="transactions")
    raw = load_transactions(synthetic_db, "transactions")
    owner, _ = attribute_exclusions(results, EXCLUDE_PRECEDENCE)
    curated = apply_handling(raw, results, "revenue", owner)

    excluded = raw.loc[list(owner.keys())]

    # Count identity.
    assert len(curated) + len(excluded) == len(raw)

    # Revenue identity (within tolerance).
    assert abs((_revenue(curated) + _revenue(excluded)) - _revenue(raw)) <= TOLERANCE

    # The engine's own identity check agrees.
    assert verify_identity(raw, curated, owner, TOLERANCE) is True


def test_reconciliation_table_values(synthetic_db: Path) -> None:
    """The reconciliation table reports the expected raw/curated headline values."""
    catalog = load_catalog(REAL_CATALOG)
    results = run_catalog(synthetic_db, catalog, table="transactions")
    raw = load_transactions(synthetic_db, "transactions")
    owner, _ = attribute_exclusions(results, EXCLUDE_PRECEDENCE)
    curated = apply_handling(raw, results, "revenue", owner)

    recon = build_reconciliation(raw, curated).set_index("metric")

    assert recon.loc["line_items", "raw"] == 11
    assert recon.loc["line_items", "curated"] == 8
    # Hand-computed from the synthetic dataset.
    assert abs(recon.loc["total_revenue", "raw"] - 1244.0) <= TOLERANCE
    assert abs(recon.loc["total_revenue", "curated"] - 1270.0) <= TOLERANCE
