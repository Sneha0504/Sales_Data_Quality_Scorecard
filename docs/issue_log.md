# Issue Log

One entry per data-quality issue surfaced by the rule catalog, built directly
from `data/curated/rule_results.csv`. All rates are shares of the 1,067,371 raw
rows. Date found: 2026-11-09 for every issue (the profiling/rule run date).

### How to read the "rows affected" counts

The counts below are **raw failure counts**: how many raw rows each rule matched,
independent of any other rule. For `flag` and `keep_with_note` rules, some of
those rows are **not present in the curated table** because an `exclude` rule
(R002/R003/R004) also matched them and removed the row. For example, R008
(quantity outlier) matches 941 raw rows, but only **640** remain in curated; the
other 301 were also cancellations or non-positive-quantity rows and were
excluded. The curated-present counts are listed in `data_dictionary.md`.

---

## R001 - missing_customer_id

- **Issue:** `Customer ID` is null or blank, so the line cannot be attributed to
  a specific customer.
- **Severity:** critical
- **Dimension:** completeness
- **Rows affected:** 243,007 (22.77% of raw rows)
- **Handling / resolution:** Flag (`is_missing_customer_id`). Rows are kept so
  revenue stays complete, but marked. Many are legitimate guest/B2B checkouts.
  236,121 flagged rows remain in curated (the rest were also excluded by R002-R004).
- **Date found:** 2026-11-09

## R002 - cancelled_order

- **Issue:** `Invoice` starts with `C`, marking a cancellation/return that
  reverses a prior sale.
- **Severity:** critical
- **Dimension:** validity
- **Rows affected:** 19,494 (1.83% of raw rows)
- **Handling / resolution:** Exclude. Not real forward sales; removed so curated
  revenue reflects net kept sales. Owns 19,494 attributed exclusions (first in
  the exclude precedence R002 > R003 > R004).
- **Date found:** 2026-11-09

## R003 - non_positive_quantity

- **Issue:** `Quantity` is zero or negative (returns, write-offs, adjustments).
- **Severity:** critical
- **Dimension:** validity
- **Rows affected:** 22,950 (2.15% of raw rows)
- **Handling / resolution:** Exclude. A sold line must have positive quantity.
  Overlaps heavily with R002 (cancellations are also negative-quantity): after
  precedence, R003 **uniquely owns 3,457** exclusions; the rest were already
  owned by R002.
- **Date found:** 2026-11-09

## R004 - non_positive_price

- **Issue:** `Price` is zero or negative (adjustments, bad debt, manual
  corrections).
- **Severity:** critical
- **Dimension:** validity
- **Rows affected:** 6,207 (0.58% of raw rows)
- **Handling / resolution:** Exclude. A valid sale must carry a positive unit
  price. After precedence, R004 **uniquely owns 2,750** exclusions; the rest were
  already owned by R002/R003.
- **Date found:** 2026-11-09

## R005 - non_product_stock_code

- **Issue:** `StockCode` is not a standard product code (postage, bank charges,
  manual, discount, samples, gift, carriage, test, etc.).
- **Severity:** warning
- **Dimension:** validity
- **Rows affected:** 6,093 (0.57% of raw rows)
- **Handling / resolution:** Flag (`is_non_product_stock_code`). Legitimate
  administrative lines, kept but made excludable from product analysis. 4,793
  flagged rows remain in curated.
- **Date found:** 2026-11-09

## R006 - duplicate_line_item

- **Issue:** Exact duplicate line item (same Invoice, StockCode, Quantity and
  Price as another row).
- **Severity:** warning
- **Dimension:** uniqueness
- **Rows affected:** 67,250 (6.30% of raw rows)
- **Handling / resolution:** Flag (`is_duplicate_line_item`). Possible
  double-entry, but some repeats are genuine re-scans, so flagged rather than
  dropped. 66,102 flagged rows remain in curated. Note the Dec-2010 spike
  (about 70% of that month's rows) visible in the trend chart.
- **Date found:** 2026-11-09

## R007 - country_blank_or_unspecified

- **Issue:** `Country` is null, blank, or the catch-all `Unspecified`.
- **Severity:** warning
- **Dimension:** consistency
- **Rows affected:** 756 (0.07% of raw rows)
- **Handling / resolution:** Flag (`is_country_unspecified`). Geography is used
  for segmentation; unknown origin is flagged, not dropped. 752 flagged rows
  remain in curated.
- **Date found:** 2026-11-09

## R008 - quantity_extreme_outlier

- **Issue:** `ABS(Quantity)` exceeds the extreme-outlier threshold.
- **Severity:** warning
- **Dimension:** accuracy
- **Rows affected:** 941 (0.09% of raw rows)
- **Handling / resolution:** Keep with note (`note_quantity_outlier`). Extreme
  quantities may be data-entry errors or genuine bulk B2B orders; surfaced, never
  dropped. Only **640 of the 941** remain in curated (301 were also
  cancellations or non-positive-quantity rows removed by R002/R003).
- **Threshold:** `|Quantity| > 600`, the 99.9th percentile of raw `|Quantity|`
  from profiling (set in `rules/rule_catalog.yaml` `params`).
- **Date found:** 2026-11-09

## R009 - price_extreme_outlier

- **Issue:** `Price` exceeds the extreme-outlier threshold.
- **Severity:** warning
- **Dimension:** accuracy
- **Rows affected:** 1,068 (0.10% of raw rows)
- **Handling / resolution:** Keep with note (`note_price_outlier`). Extreme
  prices may be errors or genuine high-value items; surfaced, never dropped. 695
  of the 1,068 remain in curated (the rest were removed by an exclude rule).
- **Threshold:** `Price > 217`. The profiled 99.9th percentile is **217.02**;
  it is rounded to **217** in `rules/rule_catalog.yaml` `params` for a clean,
  documented, tunable cutoff.
- **Date found:** 2026-11-09

---

## Why an IQR fence was not used for outliers (R008/R009)

The data is heavily right-skewed wholesale data. A standard IQR fence flags more
than 5% of rows, which is not "extreme" for this domain. The 99.9th percentile
isolates genuinely extreme magnitudes while keeping the ordinary bulk orders that
are normal in wholesale. The thresholds live in the YAML `params` block so they
are documented and tunable without any code change.

## Reconciliation impact summary

Excluding the 25,701 rows owned by R002/R003/R004 removed a **net -£1,685,344**
of value (cancellations and negatives carried negative revenue), so curated
revenue is **higher** than raw: £19,287,250.57 raw to £20,972,594.57 curated
(+8.74%). Distinct orders fell 53,628 to 40,077 (-25.27%), line items 1,067,371
to 1,041,670 (-2.41%), and distinct customers 5,942 to 5,878 (-1.08%).
