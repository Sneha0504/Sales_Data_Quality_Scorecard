"""Test 3 (PLAN section 8): the YAML ``handling`` field is honored exactly.

Curation must: drop ``exclude`` rows, keep and flag ``flag`` rows, keep (never
drop) ``keep_with_note`` rows, and apply no undocumented action. An invalid
``handling`` value must raise a clear error (catalog validation, fix b).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from curate import apply_handling, load_transactions
from rule_engine import attribute_exclusions, load_catalog, run_catalog

REAL_CATALOG = Path(__file__).resolve().parent.parent / "rules" / "rule_catalog.yaml"
EXCLUDE_PRECEDENCE = ["R002", "R003", "R004"]


def _curate(synthetic_db: Path):
    """Run the real catalog + curation against the synthetic warehouse."""
    catalog = load_catalog(REAL_CATALOG)
    results = run_catalog(synthetic_db, catalog, table="transactions")
    frame = load_transactions(synthetic_db, "transactions")
    owner, _ = attribute_exclusions(results, EXCLUDE_PRECEDENCE)
    curated = apply_handling(frame, results, "revenue", owner)
    return frame, curated, results, owner


def test_exclude_rows_are_dropped(synthetic_db: Path) -> None:
    """Rows owned by an exclude rule are removed from the curated frame."""
    frame, curated, _, owner = _curate(synthetic_db)
    # Rows 3 (cancel/neg-qty), 4 (zero qty) and 5 (neg price) are excluded.
    assert set(owner.keys()) == {3, 4, 5}
    assert set(curated.index) == {1, 2, 6, 7, 8, 9, 10, 11}
    assert len(curated) == len(frame) - 3


def test_flag_rows_kept_and_flagged(synthetic_db: Path) -> None:
    """Flag rows stay in curated with their flag_column set to 1, others 0."""
    _, curated, _, _ = _curate(synthetic_db)
    assert curated.loc[2, "is_missing_customer_id"] == 1
    assert curated.loc[1, "is_missing_customer_id"] == 0
    assert curated.loc[6, "is_non_product_stock_code"] == 1
    assert set(curated.loc[[7, 8], "is_duplicate_line_item"]) == {1}
    assert curated.loc[9, "is_country_unspecified"] == 1


def test_keep_with_note_rows_never_dropped(synthetic_db: Path) -> None:
    """keep_with_note rows remain in curated and carry their note flag."""
    _, curated, _, _ = _curate(synthetic_db)
    assert 10 in curated.index  # quantity outlier
    assert 11 in curated.index  # price outlier
    assert curated.loc[10, "note_quantity_outlier"] == 1
    assert curated.loc[11, "note_price_outlier"] == 1


def test_no_undocumented_action(synthetic_db: Path) -> None:
    """Curated columns are exactly raw + revenue + documented flag/note columns."""
    frame, curated, results, _ = _curate(synthetic_db)
    flag_cols = {r.flag_column for r in results if r.flag_column}
    expected = set(frame.columns) | {"revenue"} | flag_cols
    assert set(curated.columns) == expected

    # Non-excluded rows keep their original field values untouched.
    for rowid in curated.index:
        assert curated.loc[rowid, "Invoice"] == frame.loc[rowid, "Invoice"]
        assert curated.loc[rowid, "Quantity"] == frame.loc[rowid, "Quantity"]
    # Revenue is the documented derived field, Quantity * Price.
    assert curated.loc[1, "revenue"] == frame.loc[1, "Quantity"] * frame.loc[1, "Price"]


def _write_catalog(tmp_path: Path, rule: dict) -> Path:
    """Write a minimal one-rule catalog to a temp file and return its path."""
    catalog = {"meta": {"table": "transactions"}, "rules": [rule]}
    path = tmp_path / "bad_catalog.yaml"
    path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    return path


def test_invalid_handling_raises(tmp_path: Path) -> None:
    """An unknown handling value is rejected with a clear error."""
    path = _write_catalog(
        tmp_path,
        {
            "id": "RX",
            "name": "bogus",
            "dimension": "validity",
            "severity": "warning",
            "handling": "delete_silently",
            "sql": "SELECT rowid FROM transactions",
        },
    )
    with pytest.raises(ValueError, match="invalid handling"):
        load_catalog(path)


def test_missing_required_key_raises(tmp_path: Path) -> None:
    """A rule missing a required key is rejected."""
    path = _write_catalog(
        tmp_path,
        {"id": "RY", "name": "no_sql", "severity": "warning", "handling": "flag"},
    )
    with pytest.raises(ValueError, match="missing required key"):
        load_catalog(path)


def test_flag_without_flag_column_raises(tmp_path: Path) -> None:
    """A flag rule with no flag_column is rejected."""
    path = _write_catalog(
        tmp_path,
        {
            "id": "RZ",
            "name": "flag_no_col",
            "dimension": "validity",
            "severity": "warning",
            "handling": "flag",
            "sql": "SELECT rowid FROM transactions",
        },
    )
    with pytest.raises(ValueError, match="no 'flag_column'"):
        load_catalog(path)


def test_keep_with_note_without_flag_column_raises(tmp_path: Path) -> None:
    """A keep_with_note rule with no flag_column is rejected."""
    path = _write_catalog(
        tmp_path,
        {
            "id": "RN",
            "name": "note_no_col",
            "dimension": "accuracy",
            "severity": "warning",
            "handling": "keep_with_note",
            "sql": "SELECT rowid FROM transactions",
        },
    )
    with pytest.raises(ValueError, match="no 'flag_column'"):
        load_catalog(path)


def test_non_string_handling_raises_valueerror(tmp_path: Path) -> None:
    """A non-string (unhashable) handling raises a clear ValueError, not TypeError."""
    path = _write_catalog(
        tmp_path,
        {
            "id": "RL",
            "name": "list_handling",
            "dimension": "validity",
            "severity": "warning",
            "handling": ["flag"],
            "sql": "SELECT rowid FROM transactions",
        },
    )
    with pytest.raises(ValueError, match="invalid handling"):
        load_catalog(path)
