"""Bar history and indicators. Prices are ints at price_scale 5 ($1 = 100_000).
All indicators are causal: they use only closes at or before the current bar.
"""

from collections import deque


class BarHistory:
    """Rolling window of closes (and highs/lows) with O(1) append."""

    def __init__(self, capacity=1440):
        self.capacity = capacity
        self.t = deque(maxlen=capacity)
        self.o = deque(maxlen=capacity)
        self.h = deque(maxlen=capacity)
        self.l = deque(maxlen=capacity)
        self.c = deque(maxlen=capacity)

    def add(self, bar):
        self.t.append(int(bar["t"]))
        self.o.append(int(bar["o"]))
        self.h.append(int(bar["h"]))
        self.l.append(int(bar["l"]))
        self.c.append(int(bar["c"]))

    def __len__(self):
        return len(self.c)

    def closes(self):
        return list(self.c)


class EMA:
    """Exponential moving average over closes (alpha = 2 / (n + 1))."""

    def __init__(self, n):
        self.alpha_num = 2
        self.alpha_den = n + 1
        self.value = None

    def update(self, close):
        if self.value is None:
            self.value = close
        else:
            # value += (close - value) * 2 / (n + 1), integer-exact
            self.value += (close - self.value) * self.alpha_num // self.alpha_den
        return self.value


class ATR:
    """Average true range (Wilder smoothing) over closes."""

    def __init__(self, n=14):
        self.n = n
        self.value = None
        self.prev_close = None

    def update(self, high, low, close):
        if self.prev_close is None:
            tr = high - low
        else:
            tr = max(high - low, abs(high - self.prev_close), abs(low - self.prev_close))
        if self.value is None:
            self.value = tr
        else:
            self.value += (tr - self.value) // self.n
        self.prev_close = close
        return self.value


def rolling_high(values, n):
    """Highest of the last n values (None when fewer than n)."""
    if len(values) < n:
        return None
    return max(values[-n:])


def rolling_low(values, n):
    """Lowest of the last n values (None when fewer than n)."""
    if len(values) < n:
        return None
    return min(values[-n:])


def rsi(closes, n=14):
    """RSI over closes (None when fewer than n + 1 closes)."""
    if len(closes) < n + 1:
        return None
    gains = 0
    losses = 0
    for i in range(len(closes) - n, len(closes)):
        d = closes[i] - closes[i - 1]
        if d > 0:
            gains += d
        else:
            losses -= d
    if losses == 0:
        return 100
    rs = gains / losses
    return int(100 - 100 / (1 + rs))
