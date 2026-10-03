# Lucid 50K Flex strategy research and backtesting

Goal: find and validate an intraday futures strategy that passes the Lucid Trading 50K LucidFlex evaluation and
reaches funded payouts, with explicit simulation of the firm's rules (EOD-trailing max loss limit checked intraday,
50% consistency rule, contract caps, payout cycle rules).

Layout
- `data/` download scripts (histdata.com 1-minute index/commodity proxies from 2010; Yahoo daily/hourly futures + VIX).
  Raw data is git-ignored; run `python3 data/download_histdata.py && python3 data/download_yahoo.py`.
- `backtest/engine.py` numba fill simulator on 1-minute bars (market/stop/limit semantics, slippage, commissions,
  intraday equity excursion per day).
- `backtest/lucid.py` Lucid 50K Flex account simulator: evaluation, funded phase, payouts, Monte Carlo over start dates.
- `backtest/metrics.py`, `backtest/run.py` metrics and CLI runner.
- `strategies/` strategy modules (`generate(df1, contract, params) -> Intents`) and shared indicators.
- `research/` strategy-universe research, specs, catalog, and the Lucid rules as encoded.
- `results/`, `reports/` backtest outputs and final reports.

Run: `python3 -m backtest.run --strategy orb --contract MES --start 2025-01-01 --end 2026-09-30 --mc --micros 10`
