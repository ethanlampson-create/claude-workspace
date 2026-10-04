# orb_close30 - adversarial verification (2026-10-04)

Contract MNQ, fixed params from `final.json` (or_minutes 15, direction trend, trend_len 200, trend_fast 50, last_entry 10:30,
stop_mode opposite, max_stop_atr 0.6, tgt_frac 0.75, min_range_atr 0.1, max_range_atr 0.5, flat 15:55, max_trades 1, bar 5,
all improvement-round options off). All numbers per ONE micro after costs ($1.30 RT + 1 tick/side on market and stop fills).
Walk-forward numbers are taken from `walkforward.json` (not re-run). No file under `backtest/`, `tests/` or `strategies/` was modified.

## 1. Look-ahead audit of `strategies/orb_close30.py`  -> none found

Line-by-line:
- `daily_atr(df1, 14, rth_only=True)` (l.82): `atr(daily_bars).shift(1)` -> ATR for day_id d uses RTH days < d. Empirically checked
  (day 62: module ATR 329.01 == ATR computed on days <= d-1; the same-day value would be 315.2).
- `opening_range(df1, rth_open, or_minutes)` (l.81): [09:30, 09:45). Candidate bars are the RTH 5-min bars with `tod >= or_end`
  (l.101), i.e. the OR is complete before any candidate bar even starts.
- Signal (l.104-109): CLOSE of a 5-min bar vs or_high/or_low; order placed at `i_next` (l.137), the first 1-min bar after that
  5-min bar closes; the engine fills a market order at the OPEN of that bar + 1 tick. The decision uses only bars <= i_next-1.
  `i_next == -1` rows are excluded (l.101). Only the first confirming close counts (`groupby('day_id').head(1)`), so a
  disallowed first break blocks the day (no peeking at later bars).
- `daily_trend` (l.49-62): NDX cash daily close (`data/parquet/NDX_1d.parquet`, naive datetime64 index, sorted, no duplicates);
  `searchsorted(session_date, side='left') - 1` = last row strictly before the session date; SMA uses `min_periods=n` so NaN rows
  do not trade. `trend_fast` uses the same function. Checked for all 142 MAIN trades: the prior-close row date < session date in
  every case and sign(prior close - SMA200) == sign(prior close - SMA50) == trade side.
- Gap-through skip, stop/target distances (l.125-145) use the signal close, the OR levels and the shifted ATR only. The capped stop
  is expressed as `stop_pts` from the actual fill (unknown at decision time but resolved by the engine, not by the strategy).
- `set_session(or_end, last_entry + bar, flat)` (l.150): entries in [09:45, 10:35), consistent with signal bars starting < 10:30.
- `overnight_range` is only used when `min_on_range_atr > 0` (off) and would be complete before 09:30 anyway. No session_vwap.
- No date constants, regime switches or 2025-2026-specific logic in the module. The three non-GRID values trend_fast 50,
  max_range_atr 0.5, max_stop_atr 0.6 were chosen on MAIN (data snooping, documented in the README), not look-ahead in the code.
- Harness note (not a strategy bug): `backtest.run.thin_sessions` uses the median RTH bar count of the whole loaded window to flag
  holiday sessions; direction-agnostic data-quality filter, does not inform the signal.

Empirical re-check on the MAIN trades table (142 trades): entry minute in 09:50-10:30 and always on a 5-minute boundary (142/142);
entry_px == open of the entry 1-min bar + 0.25 (142/142); the 5-min close immediately before entry is beyond the OR level on the
trade side (142/142); no earlier 5-min close since 09:45 had broken either OR side (0 violations); OR width within
[0.1, 0.5] x shifted ATR (142/142).

## 2. Fixed-parameter re-runs (`python3 -m backtest.run ... --params <final.json>`)

| period | trades | net $ | win | PF | Sharpe | maxDD intra | largest_day_share | pos months |
|---|---|---|---|---|---|---|---|---|
| MAIN 2025-01-01..2026-09-30 | 142 | +6,217 | 72.5% | 1.717 | 2.12 | -1,212 | 0.057 | 13/21 |
| PRIOR 2023-01-01..2024-12-31 | 117 | +1,301 | 64.1% | 1.222 | 0.69 | -984 | 0.153 | 10/24 |

Both reproduce `final.json` exactly. Exit mix MAIN: 94 targets, 33 stops, 15 flat. By year: 2025 86 trades +3,682 PF 1.83;
2026 56 trades +2,535 PF 1.59; 2023 34 trades +378 PF 1.22; 2024 83 trades +923 PF 1.22.

Walk-forward (from `walkforward.json`, not re-run): OOS 2025-01..2026-09 = 140 trades, net +3,870, PF 1.452, Sharpe 1.42,
15/21 positive months, maxDD -1,076; last three OOS quarters PF 1.07 / 1.03 / 0.64.

## 3. Plateau (MAIN, one grid step up/down for each numeric GRID parameter; `verify_plateau_MNQ.csv`)

Module GRID = {or_minutes [15, 30], direction [both, long, trend], stop_mode [opposite, mid], tgt_frac [0.5, 0.75]}.
Numeric parameters: or_minutes (fixed 15 -> only neighbour 30) and tgt_frac (fixed 0.75 -> only neighbour 0.5).

| neighbour | trades | net $ | PF | Sharpe | maxDD | pass (PF >= 1.05) |
|---|---|---|---|---|---|---|
| or_minutes 30 | 99 | +2,003 | 1.243 | 0.71 | -2,161 | yes |
| tgt_frac 0.5 | 135 | +4,629 | 1.723 | 2.01 | -1,076 | yes |

plateau_frac = 2/2 = 1.00. Categorical GRID neighbours for context: direction long PF 1.238, direction both PF 1.064,
stop_mode mid PF 1.295 (all >= 1.05, but `both` is near the floor and OR-30 halves the Sharpe).

Extended neighbours for the non-GRID numeric parameters chosen on MAIN (not part of plateau_frac): trend_fast 20 / 100 / off ->
PF 1.806 / 1.574 / 1.436; max_range_atr 0.4 / 0.8 -> 1.629 / 1.362; max_stop_atr 0.45 / 0.75 -> 1.668 / 1.717; min_range_atr
0.05 / 0.15 -> 1.717 / 1.720; last_entry 10:00 / 11:00 -> 1.567 / 1.752; trend_len 100 -> 1.793; tgt_frac 1.0 -> 1.689.
13/13 >= 1.05; the chosen cell is not a spike on MAIN (several neighbours are better in-sample, e.g. trend_len 100, last_entry 11:00).

## 4. History with the fixed parameters

| period | trades | net $ | win | PF | Sharpe | maxDD intra |
|---|---|---|---|---|---|---|
| 2015-01-01..2022-12-31 | 665 | +162 | 60.0% | 1.007 | 0.02 | -2,153 |
| 2020-01-01..2020-12-31 | 97 | -1,112 | 57.7% | 0.785 | -1.00 | -1,638 |
| 2015-2022 ex-2020 (from the trades table) | 568 | +1,273 | | 1.074 | | |

By year: 2015 PF 0.49 (-822), 2016 0.86 (-188), 2017 0.86 (-139), 2018 1.16 (+311), 2019 1.19 (+209), 2020 0.79 (-1,112),
2021 1.25 (+914), 2022 1.15 (+989). The ex-2020 criterion (PF >= 1.0) is met at 1.074, but the edge before 2018 is negative and the
average trade ex-2020 is +$2.2, i.e. about one round trip of costs. The rule is a 2018+ phenomenon in NDX, strongest in
2021-2022 and 2025-2026.

## 5. Slippage stress (MAIN, `--slip 2` = 2 ticks per side on market/stop fills)

142 trades, net +6,170, PF 1.708, Sharpe 2.10, maxDD -1,220 (vs 1.717 at 1 tick). Robust: the average trade (+$43) is ~30x the
extra tick, and 94/142 exits are limit targets (no slippage by engine convention).

## 6. Thin-session / concentration dependence (MAIN trades table)

- 10 best days contribute +2,874 of +6,217 = 46.2% of net (142 trading days). Ex-top-10: net +3,343, PF 1.385 -> still positive.
  Six of the ten are in Apr-2025 (tariff crash shorts: 04-03, 04-04, 04-10) and Jun-2026 (06-12, 06-18, 06-23, 06-26, 06-30).
- Largest single day 357 = 5.7% of net. No month > 40%: largest month Jun-2026 = 17.4% (+1,084), then Apr-2025 12.6%.
  2025 = 59% of net, 2026 = 41%.
- Shorts: 20 trades (only when NDX < SMA50 and SMA200: Mar-May 2025, part of 2026) vs 122 longs.

## Verdict: survivor (thin)

Criteria: look-ahead none (pass); WF OOS 2025 PF 1.45 >= 1.1 (pass); plateau_frac 1.00 >= 0.5 (pass); history 2015-2022 ex-2020
PF 1.074 >= 1.0 (pass, narrowly; total 1.007; 2015-2017 negative); slippage-2 MAIN PF 1.71 >= 1.0 (pass). All five pass ->
`survivor`. Honest reading: the in-sample MAIN story (PF 1.72) overstates a walk-forward edge of PF 1.45 whose last three OOS
quarters are 1.07 / 1.03 / 0.64; the long history is flat (PF ~1.0 over 2015-2022) and 46% of MAIN net sits in ten days.
Portfolio leg at most, not a stand-alone evaluation strategy, consistent with the README.

Files: `verify_plateau_MNQ.csv` (neighbour runs). Raw run outputs in the session scratchpad (`v_orb/*_trades.csv`).
