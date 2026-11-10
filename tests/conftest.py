"""Shared pytest fixtures for the data-quality test suite.

The tests exercise the rule engine, curation and reconciliation against small,
in-memory/temp SQLite datasets so they are fast and deterministic and never
depend on the full ~1M-row warehouse build.
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

# The pipeline modules use flat imports (``import reconcile`` etc.), so ``src``
# must be importable. Add it to the path once, here, for the whole suite.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# The real catalog, used as the basis for temp copies (never modified in place).
REAL_CATALOG = PROJECT_ROOT / "rules" / "rule_catalog.yaml"

# Columns of the raw transactions table the rule SQL references.
TABLE_COLUMNS = [
    "Invoice",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "Price",
    "Customer ID",
    "Country",
    "source_sheet",
]


def write_transactions_db(rows: list[dict], db_path: Path, table: str = "transactions") -> None:
    """Write a list of row dicts to a SQLite ``transactions`` table.

    Rows are inserted in order, so SQLite assigns ``rowid`` 1..N matching the
    list order, exactly as the real loader does.

    Args:
        rows: Row dictionaries (missing columns default to None).
        db_path: Destination SQLite file.
        table: Table name to create.
    """
    frame = pd.DataFrame([{col: row.get(col) for col in TABLE_COLUMNS} for row in rows])
    with sqlite3.connect(db_path) as conn:
        conn.execute(f'DROP TABLE IF EXISTS "{table}"')
        frame.to_sql(table, conn, if_exists="replace", index=False)
        conn.commit()


@pytest.fixture
def synthetic_rows() -> list[dict]:
    """A tiny, hand-built dataset with a known failure for each rule.

    Row order (1-based rowid) and what each row triggers:

    1. clean sale                          -> no rule
    2. missing Customer ID                 -> R001
    3. cancellation invoice (C-prefix)     -> R002 (+ negative qty R003)
    4. zero quantity                       -> R003
    5. negative unit price                 -> R004
    6. non-product stock code (POST)       -> R005
    7. duplicate of row 8                  -> R006
    8. duplicate of row 7                  -> R006
    9. country 'Unspecified'               -> R007
    10. extreme quantity (> 600)           -> R008
    11. extreme price (> 217)              -> R009
    """
    base_date = "2010-06-15 10:00:00"
    return [
        {"Invoice": "500001", "StockCode": "85048", "Description": "GLASS BALL",
         "Quantity": 10, "InvoiceDate": base_date, "Price": 5.0,
         "Customer ID": 10001.0, "Country": "United Kingdom", "source_sheet": "t"},
        {"Invoice": "500002", "StockCode": "85048", "Description": "GLASS BALL",
         "Quantity": 4, "InvoiceDate": base_date, "Price": 5.0,
         "Customer ID": None, "Country": "United Kingdom", "source_sheet": "t"},
        {"Invoice": "C500003", "StockCode": "85048", "Description": "GLASS BALL",
         "Quantity": -4, "InvoiceDate": base_date, "Price": 5.0,
         "Customer ID": 10001.0, "Country": "United Kingdom", "source_sheet": "t"},
        {"Invoice": "500004", "StockCode": "85048", "Description": "GLASS BALL",
         "Quantity": 0, "InvoiceDate": base_date, "Price": 5.0,
         "Customer ID": 10002.0, "Country": "United Kingdom", "source_sheet": "t"},
        {"Invoice": "500005", "StockCode": "85048", "Description": "GLASS BALL",
         "Quantity": 3, "InvoiceDate": base_date, "Price": -2.0,
         "Customer ID": 10002.0, "Country": "United Kingdom", "source_sheet": "t"},
        {"Invoice": "500006", "StockCode": "POST", "Description": "POSTAGE",
         "Quantity": 1, "InvoiceDate": base_date, "Price": 18.0,
         "Customer ID": 10003.0, "Country": "United Kingdom", "source_sheet": "t"},
        {"Invoice": "500007", "StockCode": "22423", "Description": "MUG",
         "Quantity": 2, "InvoiceDate": base_date, "Price": 7.5,
         "Customer ID": 10003.0, "Country": "United Kingdom", "source_sheet": "t"},
        {"Invoice": "500007", "StockCode": "22423", "Description": "MUG",
         "Quantity": 2, "InvoiceDate": base_date, "Price": 7.5,
         "Customer ID": 10003.0, "Country": "United Kingdom", "source_sheet": "t"},
        {"Invoice": "500008", "StockCode": "85048", "Description": "GLASS BALL",
         "Quantity": 1, "InvoiceDate": base_date, "Price": 2.0,
         "Customer ID": 10004.0, "Country": "Unspecified", "source_sheet": "t"},
        {"Invoice": "500009", "StockCode": "85048", "Description": "GLASS BALL",
         "Quantity": 900, "InvoiceDate": base_date, "Price": 1.0,
         "Customer ID": 10004.0, "Country": "United Kingdom", "source_sheet": "t"},
        {"Invoice": "500010", "StockCode": "85048", "Description": "GLASS BALL",
         "Quantity": 1, "InvoiceDate": base_date, "Price": 250.0,
         "Customer ID": 10005.0, "Country": "United Kingdom", "source_sheet": "t"},
    ]


@pytest.fixture
def synthetic_db(tmp_path: Path, synthetic_rows: list[dict]) -> Path:
    """A temp SQLite warehouse holding the :func:`synthetic_rows` dataset."""
    db_path = tmp_path / "warehouse_test.db"
    write_transactions_db(synthetic_rows, db_path)
    return db_path


@pytest.fixture
def temp_catalog(tmp_path: Path) -> Path:
    """A writable copy of the real rule catalog (the real file is untouched)."""
    dest = tmp_path / "rule_catalog.yaml"
    shutil.copyfile(REAL_CATALOG, dest)
    return dest
