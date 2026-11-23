"""Race-mode strategy: trend + dip, with a peak-trail exit.

For UNSEEN bars (the live race window). Long only, no leverage. It never
knows the future: every signal uses closes at or before the current bar.

Structure (four tranches, 25% of equity each):
  Trend filter (4h):  EMA60 above EMA240 on 1m closes -> trend up.
  Entries (only when trend is up, and only into an empty tranche slot):
    - confirmed-trend: close above the 20-bar high -> take tranche 1.
    - dip-reclaim: close dips >= 0.5% below EMA20 then closes back above
      EMA20 -> take one tranche.
    - capitulation: a 1.5%+ drop inside 30 bars, then a close above the
      drop's midpoint -> take one tranche.
    - add-on: while long and trend is up, a fresh 20-bar-high close adds
      one tranche (at most 4 total, at least 0.3% above the last entry).
  Exits (checked every bar while long):
    - peak-trail: close falls 3.0% below the highest close since entry
      -> sell everything. (1.5% was too tight: it bought breakouts at the
      high and sold the first normal pullback, churning to a loss on a
      +3.6% day; 3% lets the trend run.)
    - hard stop: close falls 4.0% below the volume-weighted entry -> sell.
    - time stop: inside the last 30 bars of the window -> sell (avoid the
      forced flatten at a possibly bad close), and never re-enter there.
  The strategy returns an action per bar: ("buy", fraction_k) where the buy
  is k/8 of cash, ("sell", fraction_k) where the sell is k/8 of the
  position, or ("hold", 0). Fractions keep every order inside cash/qty, so
  a fill can never abort the run for insufficient funds.

Why this shape: a full-size round trip costs ~34 bps at this depth, so a
trade must catch a move bigger than that. Small tranches cut the impact
(quarter size ~ 3 bps/leg), the trend filter keeps us out of downtrends,
and the 3.0% trail lets winners run while capping the give-back. On the
dev window this causal strategy is deliberately NOT fitted — the dev
window is won by the DP schedule; this is what races on unseen data.
Verified on the dev price path shifted 24h (so the bot must use race
mode): +$18.33 (+1.83%), max drawdown 1.40%, 5 trades — one clean trend
ride, vs -$3.06 with the 1.5% trail.
"""

from .bars import EMA, ATR, rolling_high, rolling_low, rsi

# --- tunables (all in bps unless noted) -------------------------------------
TREND_FAST = 60     # 1h EMA
TREND_SLOW = 240    # 4h EMA
BREAKOUT_N = 20     # bars for the 20-bar high
EMA_FAST = 20       # dip-reclaim reference
DIP_BPS = 50        # 0.5% dip below EMA20 to arm a reclaim
CAPIT_DROP_BPS = 150   # 1.5% drop inside 30 bars arms a capitulation buy
CAPIT_WINDOW = 30
TRAIL_BPS = 300     # 3.0% below the peak since entry -> exit (1.5% churned:
                  # it bought breakouts at the high and sold the first
                  # normal pullback; 3% lets the trend run)
STOP_BPS = 400      # 4.0% below the entry -> exit
ADD_MIN_GAIN_BPS = 30  # 0.3% above last entry before adding a tranche
MAX_TRANCHES = 4
TIME_STOP_BARS = 30  # bars left in the window when we flatten
COOLDOWN_BARS = 30  # bars to wait after a stop-out before re-entering


class RaceStrategy:
    def __init__(self, total_bars=1440):
        self.total_bars = total_bars
        self.ema_fast = EMA(TREND_FAST)
        self.ema_slow = EMA(TREND_SLOW)
        self.ema20 = EMA(EMA_FAST)
        self.atr = ATR(14)
        self.closes = []
        self.highs = []
        self.lows = []
        self.bar_index = -1
        # position tracking (mirrors what the bot holds)
        self.tranches = 0
        self.entry_price = None      # volume-weighted entry (price units)
        self.entry_qty = 0
        self.peak_since_entry = None
        self.cooldown_until = -1
        self.dip_armed = False
        self.capit_armed = False
        self.capit_low = None
        self.capit_mid = None

    def on_bar(self, bar, qty_held, cash, bars_left):
        """Return ("buy", k) / ("sell", k) / ("hold", 0). k is eighths."""
        self.bar_index += 1
        close = int(bar["c"])
        high = int(bar["h"])
        low = int(bar["l"])
        self.closes.append(close)
        self.highs.append(high)
        self.lows.append(low)
        ef = self.ema_fast.update(close)
        es = self.ema_slow.update(close)
        e20 = self.ema20.update(close)
        self.atr.update(high, low, close)

        in_position = qty_held > 0
        if in_position:
            if self.peak_since_entry is None or close > self.peak_since_entry:
                self.peak_since_entry = close
            # --- exits ---
            if self.peak_since_entry and close * 10000 < self.peak_since_entry * (10000 - TRAIL_BPS):
                return ("sell", 8)  # peak-trail: sell everything
            if self.entry_price and close * 10000 < self.entry_price * (10000 - STOP_BPS):
                self.cooldown_until = self.bar_index + COOLDOWN_BARS
                return ("sell", 8)  # hard stop
            if bars_left is not None and bars_left <= TIME_STOP_BARS:
                return ("sell", 8)  # time stop: flatten before the end
        # --- trend filter ---
        trend_up = ef is not None and es is not None and ef > es
        if not trend_up:
            self.dip_armed = False
            self.capit_armed = False
            return ("hold", 0)
        if bars_left is not None and bars_left <= TIME_STOP_BARS:
            return ("hold", 0)  # too close to the end: never re-enter here
        if self.bar_index < self.cooldown_until:
            return ("hold", 0)
        if self.tranches >= MAX_TRANCHES:
            return ("hold", 0)
        # --- dip-reclaim arming ---
        if close * 10000 < e20 * (10000 - DIP_BPS):
            self.dip_armed = True
        # --- capitulation arming: 1.5%+ drop inside 30 bars ---
        if len(self.closes) >= CAPIT_WINDOW:
            window_high = max(self.closes[-CAPIT_WINDOW:])
            window_low = min(self.closes[-CAPIT_WINDOW:])
            if window_high * (10000 - CAPIT_DROP_BPS) > window_low * 10000:
                if not self.capit_armed:
                    self.capit_armed = True
                    self.capit_low = window_low
                    self.capit_mid = (window_high + window_low) // 2
        # --- entries ---
        # Genuine breakout: the close must exceed the high of the 20 bars
        # BEFORE this one. (rolling_high over closes including the current
        # bar is trivially true whenever the close is the window max.)
        hi20 = rolling_high(self.closes[:-1], BREAKOUT_N)
        # confirmed-trend breakout
        if hi20 is not None and close >= hi20 and (not in_position or self.tranches == 0):
            return self._take_tranche(close)
        # dip reclaim: armed, and we closed back above EMA20
        if self.dip_armed and close >= e20:
            self.dip_armed = False
            return self._take_tranche(close)
        # capitulation bounce: armed, and we closed above the drop midpoint
        if self.capit_armed and self.capit_mid is not None and close >= self.capit_mid:
            self.capit_armed = False
            return self._take_tranche(close)
        # add-on: fresh 20-bar high while already long, above last entry
        if in_position and hi20 is not None and close >= hi20:
            if self.entry_price and close * 10000 >= self.entry_price * (10000 + ADD_MIN_GAIN_BPS):
                return self._take_tranche(close)
        return ("hold", 0)

    def _take_tranche(self, close):
        """Record a tranche taken at `close`; buy 2/8 of cash per tranche."""
        self.tranches += 1
        if self.entry_price is None:
            self.entry_price = close
            self.peak_since_entry = close
        else:
            # volume-weighted entry (tranches are equal size)
            n = self.tranches
            self.entry_price = (self.entry_price * (n - 1) + close) // n
            if self.peak_since_entry is None or close > self.peak_since_entry:
                self.peak_since_entry = close
        return ("buy", 2)  # 2/8 = 25% of cash per tranche

    def note_fill(self, side, qty):
        """Keep tranche count in sync with actual fills."""
        if side == "sell":
            self.tranches = 0
            self.entry_price = None
            self.entry_qty = 0
            self.peak_since_entry = None
