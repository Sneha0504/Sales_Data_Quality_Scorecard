# Memo: What Cleaning Did to the Sales Numbers

**To:** Data consumers and stakeholders
**From:** Data Quality and Governance
**Date:** 2026-11-09
**Re:** Online Retail II sales data, raw vs curated

## Summary

We ran a documented set of quality rules over the full Online Retail II
transaction dataset (1,067,371 raw rows, Dec 2009 to Dec 2011) and produced a
trustworthy curated sales layer. The headline finding is that cleaning moves the
numbers in ways that matter, and in one case in the opposite direction from what
most people expect. This memo explains the most impactful issues and how much
cleaning changed the top-line figures.

## The most impactful issue: cancellations and non-sale rows

The single biggest driver of change is the removal of rows that are not forward
sales: cancellations (invoices starting with C), zero or negative quantities, and
zero or negative prices. Together these account for 25,701 excluded rows.

The counter-intuitive part is the money. Those excluded rows carried a net of
negative £1,685,344 in value, because cancellations and returns are recorded with
negative quantities. Removing them therefore raises curated revenue rather than
lowering it:

- Revenue: £19,287,250.57 raw, rising to £20,972,594.57 curated, a gain of 8.74%.
- Distinct orders: 53,628 raw, falling to 40,077 curated, a drop of 25.27%.
- Line items: 1,067,371 raw, falling to 1,041,670 curated, a drop of 2.41%.
- Distinct customers: 5,942 raw, falling to 5,878 curated, a drop of 1.08%.

The takeaway is that anyone reporting revenue off the raw file is understating it,
while anyone counting orders off the raw file is overstating them, because a large
share of invoices are cancellations. The curated layer corrects both.

## The second issue: missing customer IDs

Nearly one in four raw rows, 243,007 of them or 22.77%, has no Customer ID. These
are mostly guest or business (B2B) checkouts. They still represent real revenue,
so we keep them, but we flag them so any customer-level analysis can see that a
large block of sales cannot be tied to a named customer. This is a completeness
limit to keep in mind for any per-customer metric.

## How much cleaning moved the headline numbers

In plain terms: revenue went up about 8.7%, order count went down about 25%, line
items went down about 2.4%, and the customer count barely moved (down about 1%).
The large order drop and the revenue rise both come from the same cause, the
cancellations, which is why we report them together.

## What we flagged but kept

Beyond exclusions, we flagged duplicate line items (67,250 raw rows, with a large
spike in December 2010), non-product stock codes such as postage and bank charges
(6,093 rows), blank or unspecified countries (756 rows), and extreme quantity and
price outliers (941 and 1,068 rows). We keep all of these so totals stay complete,
and we mark them so downstream users can include or exclude them deliberately.

## Limitations

- About 22.8% of rows cannot be attributed to a customer, so customer-level
  analysis covers only the attributable portion.
- Outlier thresholds use the 99.9th percentile (quantity above 600, price above
  217). They flag for review only and are tunable in the rule catalog.
- We do not impute or correct values. We exclude, flag, or note, and every action
  is documented in the rule catalog and issue log.
- The data covers December 2009 to December 2011 and is one UK wholesale
  retailer, so it is not representative of retail in general.

## Where to look next

The interactive dashboard shows the per-rule scorecard, the raw vs curated
reconciliation, and the monthly failure-rate trend. The issue log and data
dictionary document every rule and every curated field.
