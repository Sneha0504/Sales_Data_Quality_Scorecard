"""Test 2 (PLAN section 8): a planted bad record is caught by the right rule.

A row with a negative unit price must be caught by R004 (non_positive_price),
and the zero/negative-quantity rows by R003 (non_positive_quantity) -- and by
*only* those rules, with the exact planted rowids.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from conftest import write_transactions_db

from rule_engine import load_catalog, run_catalog

REAL_CATALOG = Path(__file__).resolve().parent.parent / "rules" / "rule_catalog.yaml"


def test_negative_price_caught_by_r004(tmp_path: Path) -> None:
    """R004's SQL catches exactly the single planted negative-price row."""
    rows = [
        # rowid 1: clean
        {"Invoice": "900001", "StockCode": "85048", "Quantity": 5,
         "InvoiceDate": "2010-03-01 09:00:00", "Price": 4.0,
         "Customer ID": 20001.0, "Country": "United Kingdom"},
        # rowid 2: clean
        {"Invoice": "900002", "StockCode": "85048", "Quantity": 2,
         "InvoiceDate": "2010-03-01 09:00:00", "Price": 9.0,
         "Customer ID": 20002.0, "Country": "United Kingdom"},
        # rowid 3: PLANTED negative price
        {"Invoice": "900003", "StockCode": "85048", "Quantity": 1,
         "InvoiceDate": "2010-03-01 09:00:00", "Price": -7.5,
         "Customer ID": 20003.0, "Country": "United Kingdom"},
    ]
    db_path = tmp_path / "planted.db"
    write_transactions_db(rows, db_path)

    catalog = load_catalog(REAL_CATALOG)
    results = {r.id: r for r in run_catalog(db_path, catalog, table="transactions")}

    assert results["R004"].failing_rowids == [3], "R004 must catch exactly the planted row"
    # No clean row is mis-flagged by the quantity/price rules.
    assert results["R003"].failing_rowids == []


def test_zero_and_negative_quantity_caught_by_r003(synthetic_db: Path) -> None:
    """R003 catches exactly the cancellation's negative qty and the zero-qty row."""
    catalog = load_catalog(REAL_CATALOG)
    results = {r.id: r for r in run_catalog(synthetic_db, catalog, table="transactions")}

    # Row 3 has Quantity -4, row 4 has Quantity 0.
    assert results["R003"].failing_rowids == [3, 4]
    # Row 5 is the only negative-price row.
    assert results["R004"].failing_rowids == [5]


def test_synthetic_db_rowids_are_insertion_order(synthetic_db: Path) -> None:
    """Sanity check: SQLite rowids match insertion order, as the loader assumes."""
    with sqlite3.connect(synthetic_db) as conn:
        rowids = [r[0] for r in conn.execute("SELECT rowid FROM transactions").fetchall()]
    assert rowids == list(range(1, 12))
