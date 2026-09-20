# FibEdge Premium — isolated website layer

This folder keeps Premium-specific dashboard logic separate from the existing
Classic/Clean Render app and from the scanner/backtest code.

## What is frozen

### Premium Clean
- Historical resolved win rate: 56.36%
- Exact website selection requires `Recovery Efficiency >= 0.94`
- If the live feed does not contain `Recovery Efficiency`, the UI must not
  claim that current cards are exact Premium Clean signals.

### Premium+ V1
Frozen website-facing rule metadata:
- Base tracking decline: 8%+
- Premium+ final decline: 15%+
- Swing duration: 15+ days
- Lower Wick % Range <= 10%
- Compression 3v10 <= 0.90
- 786 Close % >= 2.0%
- Signal only after completed daily candle
- Candidate entry next session

Historical resolved backtest:
- 304 resolved
- 234 wins
- 70 losses
- 76.97% historical win rate

## Separation rule

The files in this folder are presentation/selection helpers only.
They do not modify Fibonacci calculations, scanner state, backtests, SL/target
math, or the existing Classic/Clean production logic.

This folder can be wired into the future static Netlify dashboard after the
Render period ends.
