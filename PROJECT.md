# Sales_Data_Quality_Scorecard — Project Spec

> Standing reference. This is the spec the project is built against.

Project name:   Sales_Data_Quality_Scorecard
Target role:    Data Analyst / Data Engineer (data governance, data quality roles)

## Goal
Build a data quality and governance framework for a real wholesale sales
transaction dataset: a YAML-defined rule catalog, a cleaned and curated data
layer, a data dictionary, a business glossary, and an issue log, so that anyone
using the curated data can trust it and understand exactly what was done to it.

## Key questions
1. What fraction of raw transaction records fail basic quality rules (missing
   customer IDs, cancelled/negative-quantity orders, invalid or test SKUs,
   duplicate invoices), and how should each type be handled (exclude, flag, or
   keep with a note)?
2. Can the rule catalog be defined once, in a readable format separate from the
   code, so rules can be added or changed without touching the pipeline logic?
3. Once cleaned, does the curated sales data reconcile with the raw data in ways
   that matter (total revenue, order counts) or does cleaning materially change
   the headline numbers, and by how much?
4. Is every field in the curated dataset documented clearly enough that a new
   analyst could use it correctly without asking what a column means?

## Required tools
Python (pandas), SQL (SQLite), YAML (rule catalog), Plotly (static dashboard),
Git, GitHub CLI.

## Deliverables
YAML-defined rule catalog with a SQLite-based runner, a curated data layer, a
data dictionary, a business glossary, an issue log, a precomputed interactive
dashboard published on GitHub Pages, clean public README.

## Data
Online Retail II dataset (UCI ML Repository), real transaction-level data from a
UK-based online wholesale retailer, December 2009 to December 2011.
https://archive.ics.uci.edu/dataset/502/online+retail+ii

See git history / docs/PLAN.md for the full build plan and the step-by-step
requirements this spec was delivered with.
