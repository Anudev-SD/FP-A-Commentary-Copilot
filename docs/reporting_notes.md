# Accounting and Reporting Notes

> Simulated reporting notes for this capstone.

## Sign conventions
<!-- pin -->
- Gross Sales, Discounts, COGS and Gross Profit are all stored as positive amounts.
- Net Sales equals Gross Sales minus Discounts. Gross Profit equals Net Sales minus COGS.
- Variance is always Actual minus the comparison. Whether it is favourable depends on the account type, not on the sign.
- Margin and rate changes are shown in percentage points (pp).

## Source data and classification
The source is the Financial Sample workbook: 700 transaction rows from September 2013 to December 2014, aggregated to month by segment by country by product. Available accounts are Gross Sales, Discounts, COGS and Units Sold. No operating expenses exist, so EBITDA, operating profit and net income must not be discussed.

## Budget and forecast provenance
Budget and Forecast are produced by a seeded simulation script, not by a finance team. Any commentary using them must say in the Data Notes that they are simulated and are not approved plans. Commentary must not claim the plan reflects any business assumption beyond what the tool facts show.

## Currency and units
The source file does not state a currency. Amounts are presented with a dollar sign by convention and the assumption should be confirmed with the data owner. Units Sold can be fractional in some source rows; this is a quirk of the source file.

## Data coverage
Actuals cover September 2013 to December 2014. Prior-year comparisons exist only from September 2014. A comparison with fewer months than the actual period is not like-for-like and must be called out. Actual lines with no matching comparison line are unplanned; comparison lines with no Actual are planned business that did not occur.

## Review checklist
Before a draft is issued: every number traces to a tool fact; every material variance is explained or flagged as unexplained; favourable and unfavourable labels match the facts; no cause is asserted without evidence; data caveats are stated; open questions are listed for the analyst.

## Approval and distribution
Commentary produced by the copilot is a draft. It must be reviewed by an FP&A lead before inclusion in a management pack.
