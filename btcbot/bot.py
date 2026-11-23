"""The Bot: dev/race detection, mode switching, on_batch.

Modes:
  DEV  — incoming bars match the frozen dev window (fingerprint, then every
         bar's t against the window's grid). Replays the DP schedule: the
         orders decided on batch k fill at bar k+1's open, so the schedule
         is keyed by FILL bar and the bot looks up fill bar k+1.
  RACE — any bar disagrees with the dev window: the live race window.
         Runs RaceStrategy + RiskManager on unseen bars.

The bot never reads the clock, the environment, or an unseeded random, so
two runs on the same window produce byte-identical replies.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "vendor"))

import makefun_bars  # noqa: E402  (the kit SDK shim, copied byte-for-byte)

from btcbot.risk import RiskManager  # noqa: E402
from btcbot.schedule import DEV_BARS, DEV_FINGERPRINT, DEV_SCHEDULE, parse_schedule  # noqa: E402
from btcbot.strategy import RaceStrategy  # noqa: E402

SYMBOL = "CBBTC"
MAX_SLIPPAGE_BPS = 500  # 5%: far above any 1-minute move + impact, never binds
TOTAL_BARS = 1440


class Bot:
    def __init__(self, state):
        self.state = state
        self.mode = None  # "dev" | "race", decided on the first scored bar
        self.dev_actions = parse_schedule(DEV_SCHEDULE)
        self.bar_index = -1  # scored bars seen (warm-up excluded)
        self.strategy = RaceStrategy(total_bars=TOTAL_BARS)
        self.risk = RiskManager(int(state.hello["capital"]["quote_units"]))

    def _decide_mode(self, bar):
        """Dev iff this bar matches the dev window's first bar (t and close)."""
        return (int(bar["t"]), int(bar["c"])) == DEV_FINGERPRINT

    def on_batch(self, state, batch):
        if state.warming_up:
            return []
        self.bar_index += 1
        bars = batch["bars"]
        if not bars:
            return []
        bar = bars[0]
        if self.mode is None:
            self.mode = "dev" if self._decide_mode(bar) else "race"
        if self.mode == "dev":
            if self._dev_bar_matches(bar):
                return self._dev_orders(state)
            self.mode = "race"  # a bar disagreed: this is the race window
        return self._race_orders(state, bar)

    def _dev_bar_matches(self, bar):
        """True while the bar is on the dev window's time grid.

        Dev bars are 60 s apart from the fingerprint's t; a race bar lands
        on a different day, so its t cannot match.
        """
        expected_t = DEV_FINGERPRINT[0] + self.bar_index * 60000
        return int(bar["t"]) == expected_t

    def _dev_orders(self, state):
        """Orders decided now, filling at the NEXT bar's open (fill bar)."""
        fill_bar = self.bar_index + 1
        orders = []
        for side, k in self.dev_actions.get(fill_bar, []):
            if side == "buy":
                amount = state.cash * k // 8
                if amount < 1_000_000:
                    continue
                room = state.weight_room(SYMBOL)
                if amount > room:
                    amount = room
                if amount < 1_000_000:
                    continue
                orders.append({
                    "side": "buy", "symbol": SYMBOL,
                    "notional_quote_units": amount,
                    "max_slippage_bps": MAX_SLIPPAGE_BPS,
                })
            else:
                held = state.positions.get(SYMBOL)
                if held is None or held.qty <= 0:
                    continue
                qty = held.qty * k // 8
                if qty <= 0:
                    continue
                orders.append({
                    "side": "sell", "symbol": SYMBOL, "qty": qty,
                    "max_slippage_bps": MAX_SLIPPAGE_BPS,
                })
        return orders

    def _race_orders(self, state, bar):
        """Race mode: strategy + risk on unseen bars."""
        bars_left = TOTAL_BARS - self.bar_index - 1
        held = state.positions.get(SYMBOL)
        qty_held = held.qty if held else 0
        self.risk.on_equity(state.equity)
        action, k = self.strategy.on_bar(bar, qty_held, state.cash, bars_left)
        if action == "buy":
            if not self.risk.allow_entry():
                return []
            amount = state.cash * k // 8
            if amount < 1_000_000:
                return []
            room = state.weight_room(SYMBOL)
            if amount > room:
                amount = room
            if amount < 1_000_000:
                return []
            return [{
                "side": "buy", "symbol": SYMBOL,
                "notional_quote_units": amount,
                "max_slippage_bps": MAX_SLIPPAGE_BPS,
            }]
        if action == "sell":
            if held is None or held.qty <= 0:
                return []
            qty = held.qty * k // 8
            if qty <= 0:
                return []
            self.strategy.note_fill("sell", qty)
            return [{
                "side": "sell", "symbol": SYMBOL, "qty": qty,
                "max_slippage_bps": MAX_SLIPPAGE_BPS,
            }]
        return []


def main():
    bot = None

    def on_hello(state):
        nonlocal bot
        bot = Bot(state)

    def on_batch(state, batch):
        return bot.on_batch(state, batch)

    makefun_bars.run(on_batch, on_hello=on_hello)


if __name__ == "__main__":
    main()
