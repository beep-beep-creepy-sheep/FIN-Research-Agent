# Relative Valuation

Relative valuation compares local target metrics with a selected peer set.

Supported metrics:

- PE TTM
- EV/EBITDA
- FCF yield
- PB when available
- PS when available

Rules:

- Insufficient peer counts return `insufficient_peers`.
- Missing or not-applicable values are excluded from rank and percentile.
- Outliers are flagged using an IQR fence and modified z-score policy.
- Negative or missing earnings make PE not applicable.
- Negative or missing EBITDA makes EV/EBITDA not applicable.
- Relative position is a distribution label, not investment advice.

The output can show implied multiple ranges and scenario ranges, but it does not output target-price language.
