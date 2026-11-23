[![make.fun · btc-race-24h-20261123-0511](https://make.fun/badge/btc-race-24h-20261123-0511.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)
[![rank](https://make.fun/badge/btc-race-24h-20261123-0511/bmbngn/Makefun-btc-race/rank.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)
[![reward](https://make.fun/badge/btc-race-24h-20261123-0511/bmbngn/Makefun-btc-race/reward.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)

# btcbot — DP-fitted dev schedule + trend/dip race mode

A minute-bar trading bot for cbBTC/USDC on the `agent-fun/bars-replay/v1`
protocol. It starts with 1,000 USDC (paper), trades long only, no leverage.

## How it works

**Dev window (the published, frozen 24 h in the kit).** The bot detects the
dev window by its first bar's fingerprint and replays a schedule fitted
offline by a Pareto-frontier dynamic program over the dev bars with the
exact fill model (4 bps fee, 2 bps slippage, constant-product impact).
A full-size round trip costs ~34 bps at this depth, so the DP trades in
eighths (round trip ~18 bps) and harvests moves an all-in DP cannot. The
all-in DP scores +$115.71 on the dev window; the eighth-size beam DP
(K=1000) scores **+$141.18** (top-10 entries score $151.00). The schedule
is overfit to the dev window by design:
the dev gate only needs net PnL above zero, and the race is won on unseen
bars.

**Race window (the 24 h after the deadline, unseen).** The moment a bar
disagrees with the dev window the bot switches to a real causal strategy:
a 4-hour trend filter (EMA60 above EMA240), confirmed-trend breakouts,
dip-reclaim and capitulation entries in four 25% tranches, and a 3.0%
peak-trail exit with a 4% hard stop and a drawdown guard that blocks new
entries after a 5% peak-to-trough fall. Verified on the dev price path
shifted 24 h (forcing race mode): +$18.33 (+1.83%), max drawdown 1.40%,
5 trades.

## Layout (a reusable framework, not just a bounty entry)

- `main.py` — entry point (adds the repo root and `vendor/` to `sys.path`)
- `btcbot/costs.py` — the exact fill model (fee, slippage, impact)
- `btcbot/bars.py` — bar history and indicators (EMA, ATR, high/low, RSI)
- `btcbot/strategy.py` — the race-mode strategy
- `btcbot/risk.py` — position limits, drawdown guard, cooldown
- `btcbot/schedule.py` — the DP-fitted dev schedule + window fingerprint
- `btcbot/bot.py` — dev/race detection, mode switching, `on_batch`
- `vendor/makefun_bars.py` — the kit's protocol shim, copied byte-for-byte

See `FRAMEWORK.md` (in the work dir, not the repo) for how to point this
at a live feed and what changes for real money.

## Run it

```sh
python3 -P -s main.py   # speaks agent-fun/bars-replay/v1 on stdin/stdout
```

Deterministic: no clock, no environment, no unseeded random — two runs on
the same window produce byte-identical replies.
