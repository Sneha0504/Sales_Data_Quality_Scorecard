"""Load the raw Online Retail II workbook into a SQLite ``transactions`` table.

Both yearly sheets are concatenated into a single table. The load is
idempotent: the table is dropped and recreated on every run. SQLite's implicit
``rowid`` provides a stable per-row identifier that the rule catalog references.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd

from config_util import configure_logging, load_config, resolve_path

logger = logging.getLogger("load")


def read_sheets(xlsx_path: Path, sheet_names: list[str], sheet_column: str) -> pd.DataFrame:
    """Read and concatenate the configured workbook sheets.

    Args:
        xlsx_path: Path to the source ``.xlsx`` workbook.
        sheet_names: Sheet names to read and combine.
        sheet_column: Name of the column that records the originating sheet.

    Returns:
        A single DataFrame combining all sheets, with a source-sheet column.
    """
    logger.info("Reading workbook: %s", xlsx_path)
    frames: list[pd.DataFrame] = []
    with pd.ExcelFile(xlsx_path) as workbook:
        for sheet in sheet_names:
            frame = pd.read_excel(workbook, sheet_name=sheet)
            frame[sheet_column] = sheet
            logger.info("Read sheet %r: %d rows", sheet, len(frame))
            frames.append(frame)
    combined = pd.concat(frames, ignore_index=True)
    logger.info("Combined shape: %d rows x %d columns", combined.shape[0], combined.shape[1])
    return combined


def write_table(frame: pd.DataFrame, db_path: Path, table: str) -> int:
    """Write the DataFrame to SQLite, dropping any existing table first.

    Args:
        frame: The combined transactions DataFrame.
        db_path: Path to the SQLite database file.
        table: Target table name.

    Returns:
        The number of rows written.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Writing %d rows to %s::%s (idempotent drop/recreate)", len(frame), db_path, table)
    with sqlite3.connect(db_path) as conn:
        conn.execute(f'DROP TABLE IF EXISTS "{table}"')
        frame.to_sql(table, conn, if_exists="replace", index=False)
        conn.commit()
        (count,) = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
        # Confirm the implicit rowid is usable for downstream rule SQL.
        conn.execute(f'SELECT rowid FROM "{table}" LIMIT 1').fetchone()
    logger.info("Verified %d rows and usable rowid in %s", count, table)
    return int(count)


def main() -> None:
    """Run the full load step from configuration."""
    config = load_config()
    configure_logging(config)
    xlsx_path = resolve_path(config["paths"]["raw_xlsx"])
    db_path = resolve_path(config["paths"]["warehouse_db"])
    load_cfg = config["load"]
    frame = read_sheets(xlsx_path, load_cfg["sheet_names"], load_cfg["source_sheet_column"])
    rows = write_table(frame, db_path, load_cfg["table"])
    logger.info("Load complete: %d rows in table %r", rows, load_cfg["table"])


if __name__ == "__main__":
    main()
