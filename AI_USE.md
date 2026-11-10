# AI Use (internal)

This file is the single, honest record of how AI assistance was used to build this
project. It is intentionally not linked from the public README.

## Tools genuinely used

- **AI coding assistant (Claude / Claude Code)** to write and revise the pipeline
  code, the YAML rule catalog, the test suite, the dashboard script, and the docs,
  and to run the pipeline and tests locally and check the outputs.
- **Python 3.12** in a local `.venv`, with `pandas`, `openpyxl`, `PyYAML`,
  `plotly`, `pytest`, `ruff` (versions pinned in `requirements.txt`).
- **SQLite** via the Python standard library as the rule-engine warehouse.
- **Make** for the pipeline targets.
- Git and GitHub CLI are used by the maintainer for version control and Pages
  publishing (not run as part of this build).

All numbers in the docs, README, and dashboard are read from real script output
(`data/curated/*.csv`), not estimated or invented.

## Bugs found during the build and how they were caught

### Unit A (core pipeline, fixed before Unit B)

- **InvoiceDate stored as TEXT broke the `.dt` accessor.** SQLite stores datetimes
  as text, so `frame["InvoiceDate"].dt.to_period(...)` failed on load. Caught when
  the curation/trend step raised an accessor error. Fixed by parsing
  `InvoiceDate` with `pd.to_datetime(...)` right after loading from SQLite (see
  `load_transactions` in `src/curate.py`).
- **Curated `transactions.csv` was about 122 MB uncompressed, too large to commit.**
  Caught when the written CSV exceeded a sane repo size. Fixed by writing
  `transactions.csv.gz` (about 18 MB) plus a small `transactions_monthly_summary.csv`
  whenever the uncompressed size would exceed `outputs.transactions_csv_max_mb`
  (default 50 MB) in `config/config.yaml`. Documented as a deviation from the plan
  in `docs/data_dictionary.md`.

### Unit B (this build)

The following three came from a code-review pass (verifier notes), not from a
crash, and were applied here:

- **Monthly-summary filename was hard-coded** in `src/curate.py`. Moved into the
  `outputs` section of `config/config.yaml`
  (`transactions_monthly_summary_csv`) and read via the config, so no output path
  is hard-coded.
- **No catalog validation.** `src/rule_engine.py` now validates each rule on load:
  it raises a clear `ValueError` if `handling` is not one of
  `{exclude, flag, keep_with_note}`, if any required key
  (`id, name, severity, handling, sql`) is missing, or if a `flag` rule has no
  `flag_column`. Covered by tests in `tests/test_handling.py`.
- **DtypeWarning on the standalone reconcile read.** `src/reconcile.py` read the
  curated `.gz` without dtypes, raising a pandas `DtypeWarning` on the mixed
  `Invoice`/`StockCode` columns. Fixed by passing
  `dtype={"Invoice": str, "StockCode": str}`. Confirmed gone by running
  `src/reconcile.py` standalone and grepping for warnings.

No further bugs surfaced while writing the tests: the 13 tests passed on the first
run, and the hand-computed synthetic expectations (for example the reconciliation
identity totals) matched the code output. The claim that only 640 of 941 R008
rows survive into curated was verified by reading `transactions.csv.gz` directly
before it was written into the docs.

## Anything unverified or deferred

- **GitHub Pages URL** in the README is a placeholder
  (`https://sneha0504.github.io/Sales_Data_Quality_Scorecard/`, marked with
  `<!-- PAGES_URL -->`). The exact Pages URL is confirmed by the maintainer after
  publishing.
- **Dashboard screenshot** (`docs/dashboard_screenshot.png`, marked with
  `<!-- SCREENSHOT -->`) is referenced but not yet captured; the maintainer
  captures it from the built `docs_site/index.html`.
- **Dataset license (CC BY 4.0)** is stated per the project brief and the UCI
  dataset page; it was not independently re-fetched from the web during this
  build.
- The dashboard is self-contained: the Plotly library is inlined into
  `docs_site/index.html` (no external script tags). The strings `cdn.plot.ly` and
  `src="https` appear only inside the minified Plotly bundle as internal literals,
  not as real external references.
