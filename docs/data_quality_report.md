# Data Quality Report - Sales_Data_Quality_Scorecard

Factual profile of the raw `transactions` table (both yearly sheets combined),
computed directly from the loaded data.

## Dataset overview

| Metric | Value |
|--------|-------|
| Total rows | 1,067,371 |
| Date range | 2009-12-01 07:45:00 to 2011-12-09 12:50:00 |
| Distinct invoices | 53,628 |
| Distinct customers (non-null) | 5,942 |
| Distinct stock codes | 5,305 |
| Cancellation invoices (C-prefixed rows) | 19,494 |

## Column types

| Column | Type |
|--------|------|
| rowid | int64 |
| Invoice | object |
| StockCode | object |
| Description | object |
| Quantity | int64 |
| InvoiceDate | object |
| Price | float64 |
| Customer ID | float64 |
| Country | object |
| source_sheet | object |

## Missing values

| Column | Missing | Rate |
|--------|---------|------|
| rowid | 0 | 0.0000% |
| Invoice | 0 | 0.0000% |
| StockCode | 0 | 0.0000% |
| Description | 4,382 | 0.4105% |
| Quantity | 0 | 0.0000% |
| InvoiceDate | 0 | 0.0000% |
| Price | 0 | 0.0000% |
| Customer ID | 243,007 | 22.7669% |
| Country | 0 | 0.0000% |
| source_sheet | 0 | 0.0000% |

## Quantity and price ranges

| Metric | Value |
|--------|-------|
| Quantity min | -80,995 |
| Quantity max | 80,995 |
| Quantity non-positive (<= 0) | 22,950 |
| Price min | -53,594.36 |
| Price max | 38,970.00 |
| Price non-positive (<= 0) | 6,207 |
| Quantity 99.9th pct (abs) | 600.0 |
| Price 99.9th pct | 217.02 |

## Country distribution (top 15)

| Country | Rows |
|---------|------|
| United Kingdom | 981,330 |
| EIRE | 17,866 |
| Germany | 17,624 |
| France | 14,330 |
| Netherlands | 5,140 |
| Spain | 3,811 |
| Switzerland | 3,189 |
| Belgium | 3,123 |
| Portugal | 2,620 |
| Australia | 1,913 |
| Channel Islands | 1,664 |
| Italy | 1,534 |
| Norway | 1,455 |
| Sweden | 1,364 |
| Cyprus | 1,176 |

Rows with country `Unspecified`: 756.

## Rule results

| id | name | dimension | severity | handling | failures | rate |
|----|------|-----------|----------|----------|----------|------|
| R001 | missing_customer_id | completeness | critical | flag | 243,007 | 22.7669% |
| R002 | cancelled_order | validity | critical | exclude | 19,494 | 1.8264% |
| R003 | non_positive_quantity | validity | critical | exclude | 22,950 | 2.1501% |
| R004 | non_positive_price | validity | critical | exclude | 6,207 | 0.5815% |
| R005 | non_product_stock_code | validity | warning | flag | 6,093 | 0.5708% |
| R006 | duplicate_line_item | uniqueness | warning | flag | 67,250 | 6.3005% |
| R007 | country_blank_or_unspecified | consistency | warning | flag | 756 | 0.0708% |
| R008 | quantity_extreme_outlier | accuracy | warning | keep_with_note | 941 | 0.0882% |
| R009 | price_extreme_outlier | accuracy | warning | keep_with_note | 1,068 | 0.1001% |
