# Portfolio Calendar

The calendar is local and database-backed. It does not connect to Google Calendar, Outlook, email, or external reminder services.

Event types include:

- filing
- report
- valuation
- alert
- manual
- data_quality
- reminder

The API supports date range, portfolio, symbol, and severity filters. Future filing dates are never guessed; if no event is known, the API returns `no_known_events`.
