# Strategy implementation guide (read fully before writing a strategy)

## Objective
Find a strategy (or small portfolio) that, traded on a Lucid Trading 50K LucidFlex account, (1) passes the evaluation
with a high and *monthly consistent* probability, (2) survives the funded phase to the first payout, and (3) has
positive expected net per evaluation after fees. The prime evaluation window is **2025-01-01 .. 2026-09-24**
(the data end). 2010-2024 is for robustness only. Costs are already in the engine (commission + slippage).

## Data facts
- `backtest.data.load_1m(symbol, start, end)` -> 1-minute bars, columns `ts` (tz-aware America/New_York), `open,
  high, low, close, session (date), tod (minutes since midnight ET of bar start), dow, day_id (0..N-1 contiguous)`.
- Symbols: `SPXUSD` (S&P 500, trade as MES/ES), `NSXUSD` (Nasdaq 100, MNQ/NQ), `XAUUSD` (gold, MGC/GC). No volume.
- A session runs 18:00 ET -> ~16:14 ET next day for the equity proxies (the CFD feed stops around 16:14), 18:00 ->
  17:00 for gold. RTH is 09:30-16:00 ET (equities), 08:20-13:30 (gold pit hours; gold trades nearly 23h).
- Daily futures/VIX from Yahoo in `data/parquet/{ES,NQ,GC,VIX,SPX,NDX}_1d.parquet` (index = date). Use VIX only with
  a one-day lag (yesterday's close) to avoid look-ahead.
- Big single bars exist on CPI/FOMC/NFP prints (08:30/14:00) and on crash days; they are real.

## Engine semantics (`backtest/engine.py`)
- You produce an `Intents(df1)` object: arrays on the 1-minute index. A signal placed at 1-minute index `i` is live
  from the OPEN of bar `i`. Decisions must only use information up to the close of bar `i-1`. When you work on
  resampled N-minute bars (`backtest.data.resample(df1, N, rth_only=True)`), place the order at `i_next` (the first
  1-minute bar after the N-minute bar closes). `i_next == -1` means the session ended; skip it.
- `Intents.place(idx, side, entry_px=NaN, kind='stop'|'limit', valid_bars=K, stop_px / stop_pts, tgt_px / tgt_pts,
  trail_pts, trail_act_pts, max_hold)`; `entry_px` NaN = market at the open (+1 tick slippage).
  Stop entries fill at max(open, level)+slip; limit entries fill at the level only when price trades through it by one
  tick (no slippage). Protective stops fill at level-slip (worst case: stop before target when both touched in a bar).
  Targets fill only when price trades through by one tick. One position at a time; one pending order at a time (for
  bracket/OCO entries resolve which side triggers first on the 1-minute data, as `strategies/orb.py` does).
- `Intents.set_session(entry_start, entry_end, flat_time)` restricts entries and forces flat (at the open of the first
  bar >= flat_time). Equities: flat no later than 15:58 ET. Gold: no later than 16:45 ET. Never hold overnight.
- `it.max_trades_day`, `it.daily_loss_stop` ($ per contract), `it.daily_profit_stop` ($ per contract).
- `engine.run(intents, contract)` -> (trades, daily). `daily` has per-session `pnl`, `min_eq` (intraday minimum of
  realized+unrealized equity, used for the Lucid intraday breach check), `max_eq`, `trades`. All per ONE contract.
- Contract specs and costs: `backtest/contracts.py` (MES $5/pt, MNQ $2/pt, MGC $10/pt, 1 tick slippage per side on
  market/stop fills, $1.30 round-trip commission on micros).

## Look-ahead rules (violations invalidate everything)
- Daily features (ATR, prior-day levels, VIX) must be shifted so day `d` only uses days `< d` (`daily_atr` already
  shifts). Intraday features may use bars up to the signal bar's close only.
- Never use the session's own high/low/close, or any bar at or after the entry bar, in the entry decision.
- `opening_range()` is only valid after its `i_end`; `overnight_range()` only after RTH open.
- Rolling indicators: `min_periods` = full window; NaN rows must not trade.

## Tools
- Quick run: `python3 -m backtest.run --strategy <id> --contract MES --start 2025-01-01 --end 2026-09-30 --mc --micros 10`
- Diagnostics: `python3 -m backtest.report --strategy <id> --contract MES ...` (P&L by hour, weekday, month, exit reason,
  VIX regime, MAE/MFE, streaks).
- Grid + robustness: `python3 -m backtest.batch --strategy <id> --contract MES --periods 2025-01-01:2026-09-30
  2023-01-01:2024-12-31 --jobs 4 --out results/<id>_MES` (uses the module `GRID`; override with `--grid '{...}'`).
- Portfolio: `python3 -m backtest.portfolio --legs '[{"strategy":"a","contract":"MES","micros":10}, ...]' --mc --mult 1`
- Lucid simulator: `backtest.lucid.monte_carlo(daily_micro, eval_micros, funded_policy, Rules())`; the batch runner's
  `lucid_scan` tries 5..40 micros and reports the best expected net per evaluation.

## Strategy module contract
```python
NAME = '...'; CONTRACTS = ['MES', 'MNQ']           # default instruments
PARAMS = {...}                                       # defaults
GRID = {...}                                         # SMALL grid (2-4 values per parameter, <= ~50 combos)
def generate(df1, contract, params) -> Intents: ...
```
Register in `strategies/__init__.py` (`REGISTRY[id] = 'strategies.<module>'`). One module per strategy id. Keep the
`PARAMS` defaults equal to the published/original rule; do not tune defaults to the test window.

## What "good" looks like (per micro contract, 2025-01..2026-09, after costs)
- Profit factor >= 1.3 with >= 150 trades, or >= 1.5 with >= 60 trades; average trade >= 2x costs.
- Daily Sharpe (annualised) >= 1.5; positive-day share >= 50%; no single month contributing > 40% of net.
- Intraday max drawdown per micro small enough that 10-20 micros stay under the $2,000 EOD-trailing MLL
  (rule of thumb: max_dd_intraday * micros < $1,500).
- Holds up (profit factor >= 1.1) on 2023-2024 with the same parameters, and the parameter grid is a plateau, not a spike.
- Then the Lucid Monte Carlo decides: pass rate, time to pass, first-payout probability, expected net per evaluation.

## Reporting
Write `results/<id>/README.md`: rules as implemented, parameters tested, metrics table per period, diagnostics summary,
what you tried, what failed and why, and the honest verdict. Keep `results/<id>/*.csv` from the batch runs.

## Account-level tools (used after strategies exist)
- `python3 -m backtest.campaign --strategy <id> --contract MNQ` (or `--legs '[...]'`): sequential evaluation attempts
  (1 or 3) with sizing policies constant / room / cushion; reports P(funded), days to funded, P(first payout), fees,
  expected net, and the minimum monthly P(funded).
- `python3 -m backtest.portfolio_opt --legs '[{"strategy":"a","contract":"MNQ"},{"strategy":"b","contract":"MGC"}]'
  --grid 0,5,10,15,20`: daily P&L correlation between legs and an exhaustive integer search of micros per leg with
  EXACT combined intraday equity, ranked by campaign expected net.
- `python3 -m backtest.scoreboard`: ranks every `results/<id>/final.json`.
- `python3 -m backtest.walkforward --strategy <id> --contract MES --is_months 12 --oos_months 3 --start 2019-01-01`:
  rolling in-sample parameter selection, concatenated out-of-sample result.
