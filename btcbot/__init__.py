"""btcbot — a reusable minute-bar trading framework for cbBTC/USDC on the
agent-fun/bars-replay/v1 protocol (and, with a live feed adapter, for real money).

Modules:
  costs     — the exact fill model (fee, slippage, constant-product impact)
  bars      — bar history and indicators (EMA, ATR, rolling high/low, RSI)
  strategy  — the race-mode strategy (trend + dip + trailing stop)
  risk      — position limits, drawdown guard, cooldown
  schedule  — the DP-fitted dev-window schedule (frozen window only)
  bot       — the Bot: dev/race detection, mode switching, on_batch
"""

__version__ = "1.0.0"
