# Scoring Rules

Scores are research-quality and risk-flag summaries. They are not recommendations, valuation
outputs, or trading signals.

## Outputs

- `growth_score`
- `profitability_score`
- `cash_flow_quality_score`
- `balance_sheet_score`
- `efficiency_score`
- `earnings_quality_score`
- `market_risk_score`
- `data_quality_score`
- `overall_research_quality_score`

## Rule Shape

Each score contains transparent components. Missing findings reduce section scores. Open
data-quality issues reduce data-quality score. Absence of official filing evidence reduces
data-quality score.

## Missing Data

Missing inputs never default to a high score. If no deterministic finding exists for a section,
the score status is `insufficient_data`.
