# Finance Glossary and Narrative Rules

> Simulated policy document for this capstone. Replace it with your organisation's real definitions.
> Chunks are split on `## ` headings. A `<!-- pin -->` marker means the chunk is always given to the model.

## Narrative rules
<!-- pin -->
- Open with a one-sentence headline covering Net Sales and Gross Profit versus the chosen comparison (Budget, Forecast or Prior Year).
- State every variance as an amount and a percentage, always Actual minus comparison.
- Describe results as "favourable" or "unfavourable". Do not use emotive words such as strong, disappointing or alarming.
- Explain what moved and where (segment, product, country) before speculating on why.
- Never assert a cause unless a data fact or a reporting note supports it. Otherwise write "cause not evidenced in the data provided" and raise a follow-up question.
- Do not include forecasts, guidance or recommendations that are not present in the facts.
- Amount format: $12.4M for millions, $850K for thousands, percentages to one decimal place, margin changes in percentage points (pp).
- Close with the data caveats a reader needs to interpret the numbers.

## Materiality
<!-- pin -->
A line variance is material when it is at least 5% of the comparison AND at least $250K in absolute terms for a single month ($750K for year to date). Material variances must be explained in the commentary. Immaterial variances may be summarised in one sentence or omitted. Name a driver member when it is among the top three by absolute variance for the metric.

## Gross Sales
Total invoiced value of units sold before any discounts. Equal to Units Sold multiplied by Sale Price in the source data. Reported as a positive amount.

## Discounts
Price reductions granted to customers. Reported as a positive amount and treated as contra-revenue: it reduces Gross Sales to give Net Sales. A discount amount below the comparison is favourable.

## Discount Rate
Discounts divided by Gross Sales, expressed as a percentage. A lower discount rate than the comparison is favourable. Changes are reported in percentage points (pp).

## Net Sales
Gross Sales minus Discounts. This is the top-line revenue measure used in this pack. In the source file it is the column named Sales.

## COGS
Cost of goods sold: the direct cost of the units sold, as recorded in the source file. Reported as a positive amount. COGS below the comparison is favourable. COGS rising with volume is not by itself a problem; compare it with COGS as a percentage of Net Sales.

## COGS Percent of Net Sales
COGS divided by Net Sales, expressed as a percentage. Lower is better. It is the mirror image of Gross Margin Percent.

## Gross Profit
Net Sales minus COGS. In the source file it is the column named Profit. No operating expenses exist in the data, so there is no EBITDA or operating profit.

## Gross Margin Percent
Gross Profit divided by Net Sales, expressed as a percentage. Margin changes are reported in percentage points (pp), never as a percentage of a percentage.

## Variance
Actual minus the comparison scenario, for every line, regardless of whether the line is revenue or cost. The sign alone does not say good or bad: see Favourable and Unfavourable.

## Variance Percent
Variance divided by the absolute value of the comparison. It is undefined (n/a) when the comparison is zero, and must not be quoted in that case.

## Favourable and Unfavourable
Revenue, profit and volume lines are favourable when Actual is above the comparison. Cost lines (COGS, Discounts) are favourable when Actual is below the comparison. The tool output carries this as the label field and it must be used as given.

## Budget
The approved plan for the period. In this project Budget is simulated and must be disclosed as simulated in the Data Notes.

## Forecast
The latest management estimate for the period. In this project Forecast is simulated and sits closer to Actual than Budget does.

## Prior Year
The same period twelve months earlier, taken from Actual. Source data starts in September 2013, so prior-year comparisons only exist from September 2014 onward. Year-to-date prior-year comparisons are therefore partial.

## Year to Date
January through the reporting month of the same calendar year. Year-to-date results must be compared with year-to-date comparison figures covering the same months.

## Share of Total Variance
A member's variance divided by the total variance across all members of the dimension. It can exceed 100% or be negative when other members offset it, so describe it with care.

## Trend and Run Rate
Recent monthly actuals shown for context. A trend is not a forecast and must not be extrapolated in the commentary.

## Segment
Customer group: Government, Midmarket, Channel Partners, Enterprise and Small Business. Segment is one of three drill-down dimensions with Country and Product.

## Discount Band
A source classification of discount level (None, Low, Medium, High). Blank values in the source file mean None.

## Price Volume Mix
Not computed in this prototype. Do not attribute a variance to price, volume or mix unless a tool fact says so.
