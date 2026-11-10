# Data Sources

The project uses one external dataset. It is downloaded once into the
git-ignored `data/raw/` directory and is never modified in place.

## Online Retail II

| Field | Value |
|-------|-------|
| Dataset | Online Retail II |
| Creator | Daqing Chen |
| Publisher | UCI Machine Learning Repository |
| Dataset page | https://archive.ics.uci.edu/dataset/502/online+retail+ii |
| Direct download | https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip |
| License | Creative Commons Attribution 4.0 International (CC BY 4.0) |
| Date accessed | 2026-11-09 |
| File name | `online_retail_II.xlsx` |
| Row count | 1,067,371 |
| Date range | December 2009 to December 2011 |
| Format | One `.xlsx` workbook with two sheets: `Year 2009-2010` and `Year 2010-2011` |

### Description

Real transaction-level sales records from a UK-based online **wholesale**
retailer that mainly sells all-occasion giftware, much of it to business
(B2B) customers. Each row is one line item on an invoice.

### Columns in the source file

| Column | Meaning |
|--------|---------|
| `Invoice` | Invoice number. A `C` prefix marks a cancellation/return. |
| `StockCode` | Product (or administrative) code. |
| `Description` | Free-text product description. |
| `Quantity` | Units on the line (negative on cancellations/returns). |
| `InvoiceDate` | Timestamp of the transaction. |
| `Price` | Unit price in GBP. |
| `Customer ID` | Customer identifier (often missing for guest/anonymous sales). |
| `Country` | Customer country. |

### License and attribution

The Online Retail II dataset was created by **Daqing Chen** and is published by
the UCI Machine Learning Repository under the Creative Commons Attribution 4.0
International (CC BY 4.0) license, which permits sharing and adaptation with
attribution. As required by CC BY 4.0, the creator is credited here by name.

Citation: Chen, Daqing. (2019). *Online Retail II* [Dataset]. UCI Machine
Learning Repository. https://doi.org/10.24432/C5CG6D

Dataset facts: 1,067,371 instances; time span 01/12/2009 to 09/12/2011.

### Reproducing the download

1. Download the ZIP from the direct-download link above.
2. Extract `online_retail_II.xlsx` into `data/raw/`.
3. Run `make all` to load, profile, run the rule catalog, and curate.

The raw file is intentionally git-ignored (see `.gitignore`): it is large and
freely re-downloadable, and the repository commits only the curated outputs and
governance artifacts derived from it.
