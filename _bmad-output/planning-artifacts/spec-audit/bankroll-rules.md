# Bankroll rules (CAP-9)

One account, no deposits, gains and losses compound. The browser and the second calculator implement these same rules and must agree to the cent.

## Ledger (published in results/, new key, contract change first)
- Every priced trade at every delay in `[1,3,5,10,15,30,60]`, all portfolios.
- Per trade: id, portfolio, ticker, side, status, and its legs: `{ts, action: open|add|trim|close, frac_of_position, px}`; costs per side as in contracts.md.
- Unpriced statuses (`not_triggered`, `too_late`, `no_bars`, options) are listed with no legs; the simulator skips and counts them.

## Sizing
- Each new trade's first leg = `share` × account, where account = cash + open positions at cost, at that moment. `share` is the user's setting: default 10%, adjustable (Luis, 2026-10-20).
- Adds and trims keep his stated ratios; where he gave no size, an add is another `share`-sized slice capped at cash, and a trim sells half (as today).
- Shorts are cash-secured: entry notional is reserved from cash. No margin, no borrowing.
- Fractional shares allowed. A slice under $100, or no cash left, is skipped and counted; if the account can't fund a $100 slice, copying stops and the app shows the date.

## Window
- Start and stop dates are clamped to the course window; start < stop, else an empty state.
- A trade counts only if it opens on or after the start and closes on or before the stop. Trades still open at the stop are left out and counted.
- Same timestamp: exits and trims before entries, then by trade id.
- The delay slider snaps to the ledger delays.

## Result
- Ending balance, path, return, trades copied, skipped (by reason), and the same money held in the benchmark from the first to last trading day in the window (SPY total return for stocks, BTC for crypto; daily series published in results/).
- The Yes / Barely / No word applies at 30+ copied trades; under 30 reads "Not enough trades".
