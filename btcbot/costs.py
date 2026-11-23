"""Exact fill model for the bars-replay market.

Replicates the harness (sim/bars/engine.ts) integer-exactly for a single-hop
pool, which is what cbBTC/USDC is (one depth per bar). All divisions truncate
toward zero, as BigInt `/` does on non-negative values.

  buy:  spend = notional * (10000 - fee_bps) / 10000
        price = open * (10000 + slippage_bps) * (D + spend) / (10000 * D)
        qty   = spend * 10^(qty_scale + price_scale) / (price * 10^quote_scale)
  sell: price = max(1, open * (10000 - slippage_bps) * D / (10000 * (D + value)))
        gross = qty * price * 10^quote_scale / 10^(qty_scale + price_scale)
        proceeds = gross * (10000 - fee_bps) / 10000

where D is the bar's open depth and value = qty * open valued in quote units.
The factor (D + amount) / D is the constant-product impact M = 1 + a / D.
A fill's price move from the decision bar's close must stay inside the
order's max_slippage_bps or the harness rejects it (max_slippage).
"""

BPS = 10_000
FEE_BPS = 4
SLIP_BPS = 2
PRICE_SCALE = 5
QTY_SCALE = 8
QUOTE_SCALE = 6


def value_of(qty, price):
    """What qty is worth at price, in quote units (truncated)."""
    return qty * price * (10 ** QUOTE_SCALE) // (10 ** (QTY_SCALE + PRICE_SCALE))


def buy_fill(notional, open_price, depth):
    """(price, spend, fee, qty) for a buy of `notional` quote units."""
    spend = notional * (BPS - FEE_BPS) // BPS
    price = open_price * (BPS + SLIP_BPS) * (depth + spend) // (BPS * depth)
    qty = spend * (10 ** (QTY_SCALE + PRICE_SCALE)) // (price * (10 ** QUOTE_SCALE))
    return price, spend, notional - spend, qty


def sell_fill(qty, open_price, depth):
    """(price, gross, fee, proceeds) for a sell of `qty`."""
    v = value_of(qty, open_price)
    price = open_price * (BPS - SLIP_BPS) * depth // (BPS * (depth + v))
    if price < 1:
        price = 1
    gross = value_of(qty, price)
    proceeds = gross * (BPS - FEE_BPS) // BPS
    return price, gross, gross - proceeds, proceeds


def impact_bps(amount, depth):
    """Price impact in bps of a trade worth `amount` quote units on depth."""
    return amount * BPS // depth


def round_trip_bps(amount, depth):
    """Full round-trip cost in bps at this size and depth (fee + slip + impact)."""
    return 2 * (FEE_BPS + SLIP_BPS + impact_bps(amount, depth))
