# Industry Packs

Industry packs add domain-specific interpretation while preserving deterministic evidence rules.

## Selection

- `auto`: `general` plus a supported industry pack when industry text clearly matches.
- `general`: only the common financial analysis pack.
- `bank`: `general` plus bank-specific sections.
- `consumer_manufacturing`: `general` plus consumer/manufacturing sections.

If industry is unknown, the system uses only `general`. It does not infer industry from ticker
patterns.

## Bank Pack

The bank pack focuses on ROE, ROA, net interest margin, cost-income ratio, asset quality,
capital adequacy, loan/deposit structure, and missing regulatory ratio flags. Industrial metrics
such as gross-margin conclusions, inventory turnover, and current-ratio conclusions are not
applied as bank-specific conclusions.

## Consumer / Manufacturing Pack

The consumer/manufacturing pack covers revenue demand proxies, margin structure, working capital,
pricing-power proxy, capex/cash-flow profile, and risk flags. It reports proxy language only; it
does not claim brand strength without direct evidence.
