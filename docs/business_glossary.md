# Business Glossary

Plain-language definitions of the retail and e-commerce terms a new analyst
needs to use this dataset correctly. Each term is cross-referenced to the
curated fields (in `transactions.csv.gz`) and rules that depend on it.

### Line item

A single product entry on an invoice: one `StockCode` with its `Quantity` and
unit `Price`. The dataset is at line-item grain, so one order (invoice) can span
many rows. **Fields:** every row of `transactions.csv.gz` is one line item.
**Rules:** R006 (`duplicate_line_item`) checks for exact repeats of a line item.

### Order / invoice

A single customer transaction, identified by `Invoice`. One invoice groups many
line items. "Distinct orders" in reconciliation counts distinct `Invoice`
values. **Fields:** `Invoice`. **Rules:** R002 (`cancelled_order`).

### Cancelled order (C-prefix invoice)

An invoice whose number starts with the letter `C`. It records a cancellation or
return that reverses a prior sale, and it carries negative quantities. These are
not new sales, so they are excluded from the curated sales layer. **Fields:**
`Invoice`. **Rules:** R002 (`cancelled_order`, exclude); overlaps with R003
(negative quantity).

### Stock code

The product identifier, `StockCode`. Standard products use a 5-digit code
(sometimes with a letter suffix, e.g. `79323P`). **Fields:** `StockCode`.
**Rules:** R005 (`non_product_stock_code`).

### Non-product stock code

A `StockCode` that is not a real product but an administrative entry: postage
(`POST`), bank charges (`BANK CHARGES`), manual adjustments (`M`), discounts
(`D`), samples, gifts, carriage (`DOT`), and test codes. These lines are
legitimate but should be separable from true product analysis, so they are
flagged rather than dropped. **Fields:** `StockCode`, `is_non_product_stock_code`.
**Rules:** R005 (flag).

### Revenue

The monetary value of a line item, derived as `Quantity * Price`. Total revenue
is the sum across kept line items. Because cancellations carry negative
quantities, removing them *raises* curated revenue versus raw. **Fields:**
`revenue` (derived), `Quantity`, `Price`. **Rules:** R002, R003, R004 all change
total revenue by excluding non-sale rows.

### Wholesale

Selling goods in bulk, typically to business (B2B) resellers rather than
individual consumers. It explains the large order quantities and the many sales
with no `Customer ID` (guest/B2B checkouts), and why extreme quantities are kept
with a note rather than deleted. **Fields:** `Quantity`, `Customer ID`.
**Rules:** R001 (missing customer id), R008 (quantity outlier).

### Active customer

A customer that can be attributed to a sale, i.e. has a non-null `Customer ID`.
Roughly 22.8% of raw rows have no customer id and cannot be tied to a specific
customer, though they still represent real revenue. "Distinct customers" counts
non-null `Customer ID` values. **Fields:** `Customer ID`,
`is_missing_customer_id`. **Rules:** R001 (flag).

### Unit price

The per-unit price of a product in GBP, `Price`. A valid sale must have a
positive unit price; zero or negative prices usually mark adjustments, bad debt,
or manual corrections. **Fields:** `Price`. **Rules:** R004
(`non_positive_price`, exclude), R009 (`price_extreme_outlier`).

### Data-quality dimension

The category a quality rule tests. This project uses: **completeness** (is a
required value present?), **validity** (is the value a legal/sensible value?),
**uniqueness** (are there unintended duplicates?), **consistency** (do values
agree with expected categories?), and **accuracy** (is the value plausible, not
an extreme error?). **Fields:** recorded per rule in `rule_results.csv`
(`dimension`).

### Handling (exclude / flag / keep-with-note)

What the pipeline does with a failing row, set per rule in the YAML catalog:
**exclude** drops the row from curated data, **flag** keeps the row and sets a
boolean column to 1, **keep_with_note** keeps the row and sets a note column to 1
but never drops it. **Fields:** all `is_*` and `note_*` columns.
**Rules:** every rule declares its handling in `rule_results.csv`.
