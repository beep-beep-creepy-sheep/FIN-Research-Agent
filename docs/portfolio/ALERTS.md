# Portfolio Alerts

Alerts are local research reminders.

Supported rule families:

- Price threshold.
- Metric threshold.
- Data-quality issue.
- Report validation issue.
- Portfolio concentration threshold.
- Stale price.
- Missing filing.

Alert evaluation is manual through the API and may later run through ordinary database-backed jobs. It does not send email, SMS, external push notifications, or trading instructions.

Missing data produces skipped results with explicit reasons.
