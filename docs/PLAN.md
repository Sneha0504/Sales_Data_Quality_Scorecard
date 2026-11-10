# PLAN - Sales_Data_Quality_Scorecard

Internal planning document. Not linked from the public README.

## 1. Goal and key questions

**Goal:** Build a data quality and governance framework over a real wholesale
sales transaction dataset. The output is a trustworthy *curated* data layer plus
the governance artifacts (YAML rule catalog, data dictionary, business glossary,
issue log) that let any downstream analyst trust the data and see exactly what
was changed and why.

**Key questions** (restated):
1. What fraction of raw records fail basic quality rules, and how is each failure
   type handled (exclude / flag / keep-with-note)?
2. Can the rule catalog live entirely in a readable file (YAML), separate from
   the pipeline code, so rules can be added/changed without editing Python?
3. After cleaning, how much do the headline numbers (revenue, orders, customers)
   move between raw and curated - stated in pounds and percent, not hidden?
4. Is every curated field documented well enough to use without asking anyone?

## 2. The data and why it fits

**Online Retail II** - UCI Machine Learning Repository (ID 502).
- URL: https://archive.ics.uci.edu/dataset/502/online+retail+ii
- Download (verified reachable, HTTP 200):
  `https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip`
- Real transaction-level data from a UK-based online **wholesale** retailer,
  **Dec 2009 - Dec 2011**. Delivered as one `.xlsx` with two sheets
  (`Year 2009-2010`, `Year 2010-2011`), ~1.07M rows combined.
- Columns: `Invoice`, `StockCode`, `Description`, `Quantity`, `InvoiceDate`,
  `Price`, `Customer ID`, `Country`.

**Why it fits:** it is genuinely messy in exactly the ways a governance project
should surface - cancellation invoices (`C` prefix) with negative quantities,
missing `Customer ID`s, non-product stock codes (POST, BANK CHARGES, M, D,
samples, test codes), zero/negative prices, duplicate line items, and price/qty
outliers. It has a two-year date range, so failure-rate trends are meaningful.

## 3. Rule catalog - YAML schema design

`rules/rule_catalog.yaml`. One list of rule entries; each entry is fully
self-describing so the engine never hard-codes rule logic.

```yaml
meta:
  dataset: online_retail_ii
  table: transactions          # table the SQL runs against
  version: 1
rules:
  - id: R001
    name: missing_customer_id
    description: Customer ID is null/blank; order cannot be attributed to a customer.
    dimension: completeness     # completeness | validity | uniqueness | consistency | accuracy
    severity: critical          # critical | warning
    handling: flag              # exclude | flag | keep_with_note
    rationale: Kept for revenue totals but flagged; many are valid guest/B2B sales.
    flag_column: is_missing_customer_id   # required when handling == flag
    sql: |                      # SELECT that returns the FAILING rows (must expose rowid)
      SELECT rowid FROM transactions
      WHERE "Customer ID" IS NULL OR TRIM(CAST("Customer ID" AS TEXT)) = ''
```

Contract the engine relies on (so YAML is the single source of truth):
- Every rule's `sql` is a `SELECT` returning at least `rowid` for failing rows.
- `handling` ∈ {`exclude`, `flag`, `keep_with_note`}; `flag` requires a
  `flag_column` name. The engine reads these - it does not decide them.
- Adding a rule = appending one YAML entry. No Python change. (Proven by a test.)

**Rules to implement (minimum set from the spec):**
| id | rule | dimension | severity | handling |
|----|------|-----------|----------|----------|
| R001 | Missing / null Customer ID | completeness | critical | flag |
| R002 | Cancelled orders (`Invoice` starts `C`) | validity | critical | exclude |
| R003 | Negative or zero quantity | validity | critical | exclude |
| R004 | Negative or zero unit price | validity | critical | exclude |
| R005 | Non-product stock codes (POST, DOT, M, BANK CHARGES, samples, test, etc.) | validity | warning | flag |
| R006 | Duplicate line items (same Invoice+StockCode+Quantity+Price) | uniqueness | warning | flag |
| R007 | Country blank / inconsistent (e.g. `Unspecified`) | consistency | warning | flag |
| R008 | Quantity extreme outlier | accuracy | warning | keep_with_note |
| R009 | Price extreme outlier | accuracy | warning | keep_with_note |

Exact thresholds (e.g. outlier cutoffs) are set from the **profiling** step and
written into the YAML, so they are documented and tunable without code changes.
Cancellations (R002) and negative quantity (R003) overlap intentionally; the
issue log and reconciliation report the relationship between them (question 1).

## 4. Curation logic

`src/curate.py` builds `data/curated/` **only** from rule results + the YAML
`handling` field. Fully traceable to the catalog, never an undocumented action.
- `exclude` → row dropped from curated `transactions` (recorded in an exclusions
  tally with the rule id that removed it; a row removed by multiple exclude rules
  is attributed once, with precedence recorded, so the reconciliation identity
  still holds).
- `flag` → row kept; a boolean `flag_column` is added/set to 1.
- `keep_with_note` → row kept and flagged, but never dropped; documented as a
  note only (used for outliers, which we surface but do not silently delete).

Curated outputs (committed, small):
- `data/curated/transactions.csv` - cleaned line items + flag columns + a derived
  `revenue = Quantity * Price` column.
- `data/curated/rule_results.csv` - per-rule id, name, severity, handling,
  failure count, failure rate, example failing rowids.
- `data/curated/reconciliation.csv` - raw vs curated headline numbers.
- `data/curated/failure_trend.csv` - monthly failure rate per rule (for the
  dashboard trend).

## 5. Reconciliation approach

`src/reconcile.py` compares raw vs curated and reports, for each metric, the raw
value, curated value, absolute diff, and percent diff:
- Total revenue (Σ Quantity×Price)
- Total orders (distinct `Invoice`)
- Total line items (row count)
- Total distinct customers

Internal-consistency identity that a test enforces: for exclude rules,
`curated_rowcount + excluded_rowcount == raw_rowcount`, and
`curated_revenue + excluded_revenue == raw_revenue` (within float tolerance).

## 6. Dashboard design (precomputed, static)

`src/build_dashboard.py` → `docs_site/index.html`, one self-contained Plotly HTML
file, all data precomputed and embedded, opens as a local file with no server.
Sections:
1. **Scorecard** - bar of failure rate per rule, colored by severity
   (critical vs warning), with pass/fail counts in hover.
2. **Reconciliation** - before/after grouped bars (revenue, orders, customers,
   line items) with the % change labeled.
3. **Trend** - monthly failure rate per rule over the 2-year range.
Embedded data is summarized (per-rule totals, monthly aggregates), not raw rows.
Published via GitHub Pages: `main` branch, `/docs_site` folder.

## 7. Code standards

Python 3.11+, pinned `requirements.txt`, `.venv`, type hints, docstrings,
`logging` (not print), all paths/settings in `config/config.yaml`, no hard-coded
paths. Lint with `ruff`. Makefile targets: `setup load rules curate reconcile
test dashboard all`.

## 8. Tests (pytest)

1. **Catalog is data-driven:** add a synthetic rule to a temp catalog (no change
   to `rule_engine.py`) → engine picks it up and runs it.
2. **Planted bad record:** inject a row with a negative price → caught by R004.
3. **Handling honored:** exclude rows are dropped, flag rows kept+flagged,
   keep_with_note rows never dropped; no undocumented action applied.
4. **Reconciliation identity:** curated + excluded == raw for count and revenue.

## 9. Risks and fallbacks

| Risk | Fallback |
|------|----------|
| UCI `.xlsx` download blocked/slow in CI env | Download once to git-ignored `data/raw/`; document; `load.py` reads whatever `.xlsx`/`.csv` is in `data/raw/`. URL already verified reachable (200). |
| `.xlsx` read needs `openpyxl` | Pin `openpyxl` in requirements. |
| Full 1.07M rows slow for dashboard | Dashboard uses precomputed aggregates only; SQLite handles the row-level rules fine. |
| Overlapping exclude rules double-count | Attribute each excluded row once with recorded precedence; test enforces the reconciliation identity. |
| Outlier cutoff arbitrary | Derive from profiling (e.g. IQR / high percentile), write threshold into YAML, document in issue log. |

## 10. Out of scope

- Predictive modeling / forecasting (this is governance + quality, not ML).
- Master-data management or writing back to any source system.
- Real-time / streaming quality checks (batch only).
- Imputing or "fixing" values beyond the documented exclude/flag/note actions.

## 11. Build order

1. Data: download → `data/raw/` ; `docs/data_sources.md`.
2. `load.py` → SQLite ; profiling → feeds `docs/data_quality_report.md`.
3. `rules/rule_catalog.yaml` + `rule_engine.py`.
4. `curate.py` + `reconcile.py`.
5. Docs: data_dictionary, business_glossary, issue_log (from real results).
6. Tests + ruff + Makefile.
7. `build_dashboard.py` → `docs_site/index.html` ; GitHub Pages.
8. `memo.md`, README, AI_USE.md.
9. `make all` + tests from clean state; verify every number; hand off push.
