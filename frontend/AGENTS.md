# Frontend working agreement

## Scope
The frontend is a Next.js + TypeScript research terminal. Build actual workflows first:
market overview, company research, screener, comparison, evidence review, jobs, and settings.
Avoid marketing-only pages.

## Data display rules
- Never render fabricated chart data. Use explicit empty states when the backend has no data.
- Every chart must show period/time range, unit/currency, source label, and stale or insufficient
  data warnings when supplied by the API.
- Important financial numbers should be clickable or visibly connected to their source metadata
  when the backend provides it.
- Do not show cookies, tokens, connector secrets, or platform account details in the UI.

## Interaction rules
- Long-running research, sync, market snapshot, and AI actions must display job/progress states.
- Connector statuses must distinguish disabled, not installed, not configured, requires login,
  available, unavailable, and circuit-open states.
- Use dense, professional terminal-style layouts suitable for repeated research work.
- Use ECharts for financial charts already supported by the project dependency set.

## Quality
- Run `npm run build` for production verification.
- `npx tsc --noEmit` must work from a clean checkout without relying on stale `.next/types`.
- Keep TypeScript types close to API payloads and preserve empty/error states in components.
