"""Risk manager: position limits, drawdown guard, cooldown.

Guards (all causal, from the account the harness reports):
  - max position: never more than 100% of equity in the symbol (the cap).
  - drawdown guard: if equity falls 5% below its peak, stop NEW entries
    (exits still allowed) until equity recovers to within 2% of the peak.
  - per-trade size: every order is a fraction (k/8) of cash/qty, so an
    order can never exceed what the account holds.
  - end-of-window: flatten in the last bars (the strategy's time stop).
"""

MAX_DD_GUARD_BPS = 500   # 5% below peak -> block new entries
RECOVER_BPS = 200        # recover to within 2% of peak -> re-arm entries


class RiskManager:
    def __init__(self, start_equity):
        self.start_equity = start_equity
        self.peak_equity = start_equity
        self.blocked = False

    def on_equity(self, equity):
        if equity > self.peak_equity:
            self.peak_equity = equity
        if not self.blocked:
            if equity * 10000 < self.peak_equity * (10000 - MAX_DD_GUARD_BPS):
                self.blocked = True
        else:
            if equity * 10000 >= self.peak_equity * (10000 - RECOVER_BPS):
                self.blocked = False
        return self.blocked

    def allow_entry(self):
        return not self.blocked
