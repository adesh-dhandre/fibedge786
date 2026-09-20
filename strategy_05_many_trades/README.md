# Strategy 05 — Many Trades 0.786 Research

## Goal

Build a new 0.786 Fibonacci strategy with a **much larger number of trades**
than Premium+ V1 while trying to preserve **70%+ out-of-sample historical
win rate**.

This research is isolated on the `strategy-05-many-trades` branch. It does not change
Netlify production, Render production, scanner outputs, or the existing
Classic / Clean / Premium / Premium+ logic.

## Locked base structure

- Entry: Fib 0.786
- Stop: Fib 0.500
- Target: Fib 1.260
- Broad NSE universe
- Conservative same-candle ambiguity: stop/loss takes priority
- 60 calendar-day maximum hold

## Stage 1: baseline from the existing historical quality dataset

Source: `FIBEDGE_QUALITY_ALL_STOCKS.csv`

Existing base history:
- 2,065 stocks
- 15,394 total trades
- 14,516 resolved trades
- 4,418 wins
- 10,098 losses
- 878 timeouts
- Weighted resolved win rate: **30.44%**

Diagnostic only (NOT a valid strategy because these thresholds select stocks
using their own historical outcomes):

| Same-history stock filter | Resolved trades | Weighted win rate |
|---|---:|---:|
| Historical WR >= 40% | 4,115 | 52.42% |
| Historical WR >= 45% | 2,781 | 57.46% |
| Historical WR >= 50% | 2,423 | 59.14% |
| Historical WR >= 55% | 1,154 | 68.20% |
| Historical WR >= 60% | 866 | 72.06% |
| Historical WR >= 65% | 585 | 77.26% |
| Historical WR >= 70% | 344 | 84.59% |

This shows the trade-count / hit-rate tension clearly: getting above ~70%
while keeping 1,000+ trades will be difficult and needs **trade-level setup
features**, not stock-selection hindsight.

## Stage 2

`trade_level_search_v1.py` generates every broad 0.786 trade and records
lightweight setup features. The grid search is fit on the development period
only, then the best development rules are evaluated on the untouched test
period.

Primary target:
- Prefer >= 1,000 total resolved trades
- Aim for >= 70% test win rate
- Broad unique-stock coverage
- No rule accepted from test-period tuning
