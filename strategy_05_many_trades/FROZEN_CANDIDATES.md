# Strategy 05 — Frozen Candidate Features

Research branch only. **Do not deploy to production yet.**

## Primary feature — Fib 1.260 continuation

Geometry:
- Fib structure anchor: 0.786
- Stop: 0.500
- Target: 1.260
- Confirmation is evaluated after the daily candle closes
- Outcome evaluation begins from the next trading session

Confirmation:
- Signal candle closes at least **4.0% above the 0.786 level**
- Absolute candle body is at least **60% of the candle high-low range**

V6 historical result:
- Resolved trades: **1,060**
- Overall historical win rate: **87.92%**
- DEV: **88.35%**
- Validation: **86.14%**
- Test: **87.82%**
- Unique stocks: **707**
- Yearly win rates:
  - 2021: 92.55%
  - 2022: 83.26%
  - 2023: 89.96%
  - 2024: 90.15%
  - 2025: 86.67%
  - 2026: 82.14%

## Secondary feature — Fib 1.500 extension

This **replaces / supersedes** the earlier 1.50 experiment based on
Close>=3% + 4-of-5 up closes (~52% overall). Do not use that old V5
candidate as the preferred 1.50 feature.

Geometry:
- Fib structure anchor: 0.786
- Stop: 0.500
- Target: 1.500
- Same completed-daily-candle confirmation
- Outcome evaluation begins from the next trading session

Confirmation:
- Signal candle closes at least **4.0% above the 0.786 level**
- Absolute candle body is at least **60% of the candle high-low range**

V7 historical result:
- Resolved trades: **1,023**
- Overall historical win rate: **77.13%**
- DEV: **78.20%**
- Validation: **75.32%**
- Test: **74.03%**
- Unique stocks: **691**
- Yearly win rates:
  - 2021: 81.72%
  - 2022: 71.37%
  - 2023: 81.90%
  - 2024: 77.47%
  - 2025: 75.36%
  - 2026: 74.36%

## Important execution caveat

These are **confirmation-after-close** setups, not literal fills at 0.786.
The next production-readiness audit must use the actual executable
next-session entry price and recalculate:
- true stop %
- true target %
- true reward/risk
- true expectancy
- gap risk
- max losing streak
- monthly/yearly stability

Do not quote the theoretical 0.786-based reward/risk as executable until that
audit is complete.
