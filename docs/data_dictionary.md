# Data Dictionary

Every field in the curated data layer (`data/curated/`), with its type, meaning,
and the rule(s) that affect it. "Affected by" lists rules whose handling sets or
changes that field; exclude rules affect which rows are present rather than a
single column.

## Note on the curated main table (deviation from PLAN)

The plan specified a single `transactions.csv`. The curated line-item table is
1,041,670 rows with flag columns, which serialises to roughly **122 MB**
uncompressed, too large to commit comfortably. The pipeline therefore writes:

- **`transactions.csv.gz`** - the full curated line-item table, gzip-compressed
  (about 18 MB on disk). This is the authoritative curated dataset.
- **`transactions_monthly_summary.csv`** - a small aggregated monthly rollup,
  committed uncompressed for quick inspection and for the dashboard.

The switch to gzip plus a summary happens automatically when the uncompressed
CSV would exceed the `outputs.transactions_csv_max_mb` threshold in
`config/config.yaml` (default 50 MB). This is the only deviation from the plan's
file layout; the column contract is unchanged.

---

## `transactions.csv.gz` - curated line items

One row per kept line item. Rows removed by an `exclude` rule (R002, R003, R004)
are absent. Flag and note columns are 0/1 integers.

| Column | Type | Meaning | Affected by |
|--------|------|---------|-------------|
| `Invoice` | string | Invoice number (order id). A `C` prefix marks a cancellation, but all C-rows are excluded, so curated `Invoice` values never start with `C`. | R002 (exclude) |
| `StockCode` | string | Product or administrative code. | R005 |
| `Description` | string | Free-text product description (may be blank; 0.41% missing in raw). | none |
| `Quantity` | integer | Units sold on the line. Always positive in curated data. | R003 (exclude), R008 |
| `InvoiceDate` | datetime | Transaction timestamp (`YYYY-MM-DD HH:MM:SS`). | none |
| `Price` | float | Unit price in GBP. Always positive in curated data. | R004 (exclude), R009 |
| `Customer ID` | float (nullable) | Customer identifier; blank for guest/B2B sales. Kept even when missing. | R001 |
| `Country` | string | Customer country. | R007 |
| `source_sheet` | string | Which workbook sheet the row came from (`Year 2009-2010` or `Year 2010-2011`). | none |
| `revenue` | float | Derived: `Quantity * Price`, in GBP. | derived; indirectly R002/R003/R004 via row removal |
| `is_missing_customer_id` | int (0/1) | 1 if `Customer ID` was null/blank. Flag only; row kept. | R001 (flag) |
| `is_non_product_stock_code` | int (0/1) | 1 if `StockCode` is a non-product/administrative code. | R005 (flag) |
| `is_duplicate_line_item` | int (0/1) | 1 if the row is an exact duplicate (same Invoice+StockCode+Quantity+Price as another). | R006 (flag) |
| `is_country_unspecified` | int (0/1) | 1 if `Country` is null, blank, or `Unspecified`. | R007 (flag) |
| `note_quantity_outlier` | int (0/1) | 1 if `ABS(Quantity)` exceeds the 99.9th-percentile threshold (600). Note only; row kept. | R008 (keep_with_note) |
| `note_price_outlier` | int (0/1) | 1 if `Price` exceeds the 99.9th-percentile threshold (217). Note only; row kept. | R009 (keep_with_note) |

Curated flag/note totals (rows present in curated that carry the flag):
`is_missing_customer_id` 236,121 · `is_non_product_stock_code` 4,793 ·
`is_duplicate_line_item` 66,102 · `is_country_unspecified` 752 ·
`note_quantity_outlier` 640 · `note_price_outlier` 695. These are lower than the
raw failure counts in `rule_results.csv` because some flagged rows were also
removed by an exclude rule (see `issue_log.md`).

---

## `transactions_monthly_summary.csv` - curated monthly rollup

One row per calendar month over the curated data.

| Column | Type | Meaning |
|--------|------|---------|
| `month` | string (`YYYY-MM`) | Calendar month. |
| `line_items` | integer | Count of curated line items in the month. |
| `revenue` | float | Sum of `revenue` for the month (GBP). |
| `distinct_invoices` | integer | Distinct `Invoice` values (orders) in the month. |
| `distinct_customers` | integer | Distinct non-null `Customer ID` values in the month. |

---

## `rule_results.csv` - per-rule results

One row per catalog rule.

| Column | Type | Meaning |
|--------|------|---------|
| `id` | string | Rule id (e.g. `R001`). |
| `name` | string | Rule name (e.g. `missing_customer_id`). |
| `dimension` | string | Quality dimension: completeness, validity, uniqueness, consistency, accuracy. |
| `severity` | string | `critical` or `warning`. |
| `handling` | string | `exclude`, `flag`, or `keep_with_note`. |
| `flag_column` | string | Column set by this rule (blank for exclude rules). |
| `failure_count` | integer | Raw rows failing the rule (before any exclusion). |
| `failure_rate` | float | `failure_count / total raw rows` (1,067,371). |
| `attributed_exclusions` | integer | For exclude rules, rows this rule uniquely owns after precedence (0 for non-exclude rules). |
| `example_failing_rowids` | string | Up to 10 example failing rowids, `;`-separated. |

---

## `reconciliation.csv` - raw vs curated headline metrics

One row per headline metric.

| Column | Type | Meaning |
|--------|------|---------|
| `metric` | string | `total_revenue`, `distinct_orders`, `line_items`, or `distinct_customers`. |
| `raw` | float | Metric computed on the raw table. |
| `curated` | float | Metric computed on the curated table. |
| `abs_diff` | float | `curated - raw`. |
| `pct_diff` | float | `abs_diff / raw` (fraction; multiply by 100 for percent). |

---

## `failure_trend.csv` - monthly failure rate per rule

One row per (month, rule).

| Column | Type | Meaning |
|--------|------|---------|
| `month` | string (`YYYY-MM`) | Calendar month. |
| `rule_id` | string | Rule id. |
| `rule_name` | string | Rule name. |
| `failures` | integer | Rows failing the rule in that month. |
| `total` | integer | Total raw rows in that month. |
| `failure_rate` | float | `failures / total` for the month. |
