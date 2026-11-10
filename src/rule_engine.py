"""Generic, data-driven rule engine for the YAML rule catalog.

The engine loads ``rules/rule_catalog.yaml`` and executes each rule's ``sql``
against the SQLite warehouse. It is fully data-driven: adding a rule to the YAML
requires no change here. No rule id or rule-specific logic is hard-coded.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from config_util import configure_logging, load_config, resolve_path

logger = logging.getLogger("rule_engine")

# Number of failing rowids retained as examples in the result summary.
EXAMPLE_LIMIT = 10


@dataclass
class RuleResult:
    """Outcome of running one catalog rule."""

    id: str
    name: str
    dimension: str
    severity: str
    handling: str
    flag_column: str | None
    failure_count: int
    failure_rate: float
    failing_rowids: list[int] = field(default_factory=list)

    @property
    def example_failing_rowids(self) -> list[int]:
        """First few failing rowids, for human-readable summaries."""
        return self.failing_rowids[:EXAMPLE_LIMIT]


def load_catalog(catalog_path: Path) -> dict[str, Any]:
    """Load and parse the YAML rule catalog.

    Args:
        catalog_path: Path to the rule catalog YAML.

    Returns:
        The parsed catalog dictionary (``meta`` and ``rules``).
    """
    with catalog_path.open("r", encoding="utf-8") as handle:
        catalog: dict[str, Any] = yaml.safe_load(handle)
    return catalog


def _render_sql(rule: dict[str, Any]) -> str:
    """Substitute any ``params`` into the rule SQL via named placeholders.

    This is a generic mechanism: thresholds live in the YAML ``params`` block,
    keeping the engine free of rule-specific numbers.
    """
    sql: str = rule["sql"]
    params = rule.get("params")
    if params:
        sql = sql.format(**params)
    return sql


def run_rule(conn: sqlite3.Connection, rule: dict[str, Any], total_rows: int) -> RuleResult:
    """Execute a single rule and summarise its failing rows.

    Args:
        conn: Open SQLite connection.
        rule: One rule entry from the catalog.
        total_rows: Total rows in the table, for the failure rate.

    Returns:
        A :class:`RuleResult` with counts and failing rowids.
    """
    sql = _render_sql(rule)
    rows = conn.execute(sql).fetchall()
    failing_rowids = [int(r[0]) for r in rows]
    count = len(failing_rowids)
    rate = count / total_rows if total_rows else 0.0
    logger.info("Rule %s (%s): %d failures (%.4f%%)", rule["id"], rule["name"], count, rate * 100)
    return RuleResult(
        id=rule["id"],
        name=rule["name"],
        dimension=rule["dimension"],
        severity=rule["severity"],
        handling=rule["handling"],
        flag_column=rule.get("flag_column"),
        failure_count=count,
        failure_rate=rate,
        failing_rowids=failing_rowids,
    )


def run_catalog(
    db_path: Path, catalog: dict[str, Any], table: str | None = None
) -> list[RuleResult]:
    """Run every rule in the catalog against the warehouse table.

    Args:
        db_path: Path to the SQLite database.
        catalog: Parsed rule catalog.
        table: Optional table override; defaults to ``catalog['meta']['table']``.

    Returns:
        A list of :class:`RuleResult`, one per rule, in catalog order.
    """
    table_name = table or catalog["meta"]["table"]
    results: list[RuleResult] = []
    with sqlite3.connect(db_path) as conn:
        (total_rows,) = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()
        for rule in catalog["rules"]:
            results.append(run_rule(conn, rule, int(total_rows)))
    return results


def attribute_exclusions(
    results: list[RuleResult], precedence: list[str]
) -> tuple[dict[int, str], dict[str, int]]:
    """Attribute each excluded row to exactly one rule, by precedence.

    Rows failing more than one ``exclude`` rule are counted once, owned by the
    first rule in ``precedence`` (then any remaining exclude rules), so the
    reconciliation identity holds.

    Args:
        results: All rule results.
        precedence: Ordered list of exclude-rule ids defining ownership.

    Returns:
        A tuple of (rowid -> owning rule id) and (rule id -> attributed count).
    """
    by_id = {r.id: r for r in results}
    exclude_ids = [r.id for r in results if r.handling == "exclude"]
    ordered = [rid for rid in precedence if rid in exclude_ids]
    ordered += [rid for rid in exclude_ids if rid not in ordered]

    owner: dict[int, str] = {}
    attributed: dict[str, int] = {rid: 0 for rid in exclude_ids}
    for rid in ordered:
        for rowid in by_id[rid].failing_rowids:
            if rowid not in owner:
                owner[rowid] = rid
                attributed[rid] += 1
    return owner, attributed


def main() -> None:
    """Run the full catalog and log a summary table."""
    config = load_config()
    configure_logging(config)
    db_path = resolve_path(config["paths"]["warehouse_db"])
    catalog_path = resolve_path(config["paths"]["rule_catalog"])
    catalog = load_catalog(catalog_path)
    results = run_catalog(db_path, catalog)
    logger.info("=== Rule summary ===")
    for result in results:
        logger.info(
            "%s %-28s %-11s %-8s %-14s count=%7d rate=%.4f%%",
            result.id,
            result.name,
            result.dimension,
            result.severity,
            result.handling,
            result.failure_count,
            result.failure_rate * 100,
        )


if __name__ == "__main__":
    main()
