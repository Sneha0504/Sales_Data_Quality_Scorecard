"""Test 1 (PLAN section 8): the rule catalog is data-driven.

Adding a brand-new rule to a *temp copy* of the catalog must be picked up and
executed by the engine with no change to any Python code. This proves the YAML
is the single source of truth for rule logic.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from rule_engine import load_catalog, run_catalog


def test_new_rule_runs_without_code_change(synthetic_db: Path, temp_catalog: Path) -> None:
    """A synthetic rule appended to the YAML is executed and returns a result."""
    catalog = yaml.safe_load(temp_catalog.read_text(encoding="utf-8"))
    original_rule_ids = {rule["id"] for rule in catalog["rules"]}

    # Append a never-before-seen rule. The engine has no knowledge of "R900".
    catalog["rules"].append(
        {
            "id": "R900",
            "name": "synthetic_high_price",
            "description": "Synthetic test rule: unit price above an arbitrary cutoff.",
            "dimension": "accuracy",
            "severity": "warning",
            "handling": "flag",
            "flag_column": "is_synthetic_high_price",
            "sql": "SELECT rowid FROM transactions WHERE Price > {cutoff}",
            "params": {"cutoff": 100},
        }
    )
    temp_catalog.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")

    loaded = load_catalog(temp_catalog)
    results = run_catalog(synthetic_db, loaded, table="transactions")

    by_id = {result.id: result for result in results}
    assert "R900" not in original_rule_ids, "synthetic id must be genuinely new"
    assert "R900" in by_id, "engine must run the newly added rule with no code change"

    synthetic = by_id["R900"]
    assert synthetic.name == "synthetic_high_price"
    assert synthetic.handling == "flag"
    # Only row 11 (price 250.0) exceeds the cutoff of 100.
    assert synthetic.failure_count == 1
    assert synthetic.failing_rowids == [11]
