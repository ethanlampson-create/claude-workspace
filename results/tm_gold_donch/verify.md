# tm_gold_donch - adversarial verification (2026-10-04)

Verifier re-ran the fixed parameters from `final.json` (bar 15, n_entry 20, n_exit 10, bias sma200, long_only, stop 2.0xATR20(bar) /
0.5xATR14d nearer, no target, entries 02:00-13:00 ET, flat 16:30, max 2 trades, dls $80) on MGC with `backtest.run.run_strategy`
(`--jobs 2`, same engine, costs = $1.30 RT + 1 tick slip per side; `--slip 2` for check 5). All numbers per ONE micro, after costs.
`final_select` / the walk-forward were NOT re-run; the OOS numbers below are read from `walkforward.json`.

## 1. Look-ahead review of `strategies/tm_gold_donch.py` (line by line) - NONE FOUND

- Bars: `resample(df1, bar, rth_only=False)` buckets 1-min bars by floor((tod-18:00) mod 1440 / bar) within a session; `tod` is the bar
  START, `i_next` the first 1-min bar after the bar closes (same session, else -1). The signal uses `close[k]` (the N-bar is closed) and the
  order goes to `it.place(i_next[k], ...)` with `entry_px` NaN = market at the OPEN of that next 1-min bar (+1 tick). Engine `_simulate`
  fills a market signal at `o[i] + slip`; decision info ends at the close of bar `i-1`. Correct.
- Channels: `hi_prev = high.shift(1)`, `hh_in = hi_prev.rolling(n, min_periods=n).max()` -> `hh[k] = max(high[k-n..k-1])`, bar k excluded;
  same for `ll_out`. `atr(b, 20)` (Wilder ewm, min_periods=20) includes bar k, which is closed at decision time. NaN rows cannot trade
  (explicit `isnan` checks on atrb, atr_d, ll_out, hh_out, hh_in).
- Daily features (`daily_features`): the daily series D is built from `daily_bars(rth_only=False)` on 420 calendar days of earlier 1-min
  history plus df1 (which itself carries the 45-day engine warm-up). `prev_close = close.shift(1)`, `sma200 = rolling(200, min_periods=200)
  .mean().shift(1)`, `close_12m = close.shift(253)`, `atr14 = atr(D,14).shift(1)`; reindexed to the sessions of df1 by `day_id`. Day d
  therefore only sees sessions < d. The gold session close (17:00 of session d) is used from 18:00 onwards (session d+1). Correct.
  Duplicate sessions between `hist` and `df1` are impossible (hist ends the day before `first`) and are deduplicated anyway.
- Session own high/low/close: never referenced in the entry decision (only `close[k]` of a closed N-bar and prior-bar windows).
- Time window: `entry_start <= tod[k] < last_entry` on the bar START; `set_session(entry_start, last_entry + bar, flat)` lets the signal bar
  starting at 12:45 fill at 13:00. Forced flat at the first 1-min bar >= 16:30 (gold session ends 17:00, data has no 17:00-18:00 bars).
- Module state mirror (`pos`): reset on new session, on `low[k] <= sp` for N-bars AFTER the signal bar, on channel-exit close, on flat time.
  It can diverge from the engine only in the direction of emitting an entry the engine ignores (e.g. after the $80 daily-loss halt, or when the
  engine's 1-min stop fires inside the bar but the mirror exit is the channel close on the same bar - both reset `pos` at bar k'). Diverging
  emissions never create fills the engine would not itself allow, and `exit_at` on a flat engine is a no-op (line 68 checks `pos`). Not look-ahead.
- `exit_at(i_next[k'], which=+1)` exits at the OPEN of the bar after bar k' closes (engine line 68, `at_open`). Correct.
- No hard-coded dates, regime switches or 2025-2026 knowledge in PARAMS / GRID / code. Defaults are the published Turtle 20/10, 2N stop.
- Harness note (not strategy-specific): `backtest.run.prepare` skips "thin" sessions using the session's OWN RTH bar count, i.e. holiday
  knowledge the trader has ex ante but the harness derives ex post. It applies to every strategy in the lab; on gold it affects few sessions.

`lookahead_found = false`.

## 2. Fixed parameters, re-run (per micro, after costs)

| run | trades | net $ | PF | Sharpe | maxDD intra | largest day | largest_day_share | pos months |
|---|---|---|---|---|---|---|---|---|
| MAIN 2025-01-01..2026-09-30 | 327 | -1,046 | **0.960** | -0.20 | -6,309 | 940 | n/a (net < 0) | 7/21 |
| PRIOR 2023-01-01..2024-12-31 | 377 | -452 | **0.963** | -0.18 | -1,484 | 450 | n/a (net < 0) | 9/24 |

Both match `final.json` exactly (327 / -1,046.36 / 0.9603; 377 / -452.07 / 0.9631). `largest_day_share` is NaN by the metrics definition
because the net is negative; the largest day (2026-03-31, +940) is 3.7% of the gross winning P&L (25,284) and 90% of |net|.

## 3. Plateau (MAIN, one grid step up / down per numeric GRID parameter, everything else fixed)

The module GRID has only two cells per numeric parameter ({20,55}, {10,20}, {15,60}) and the fixed value is the LOWER cell in all three,
so the "down" neighbour does not exist in the grid; I used the nearest round value below (n_entry 10, n_exit 5, bar 5) and flag it.

| parameter | value | in GRID | trades | net $ | PF | >= 1.05 |
|---|---|---|---|---|---|---|
| n_entry | 10 | no | 401 | +3,029 | 1.098 | yes |
| n_entry | 55 | yes | 231 | +910 | 1.055 | yes |
| n_exit | 5 | no | 353 | -1,951 | 0.922 | no |
| n_exit | 20 | yes | 315 | +458 | 1.016 | no |
| bar | 5 | no | 606 | -4,146 | 0.861 | no |
| bar | 60 | yes | 159 | +1,918 | 1.119 | yes |

`plateau_frac = 3/6 = 0.50` (GRID-only neighbours: 2/3). The centre itself is PF 0.96, so this is not a plateau around a working rule:
the neighbours scatter between 0.86 and 1.12 and the two best ones (n_entry 10 and bar 60) move in opposite directions (faster vs
slower), which is noise, not structure. The existing `grid_MGC.csv` shows the same cells at PF 0.66-0.98 on PRIOR (rank correlation -0.83).

## 4. History (fixed params)

| period | trades | net $ | PF | Sharpe | maxDD intra | pos months |
|---|---|---|---|---|---|---|
| 2015-01-01..2022-12-31 | 1,155 | -1,693 | **0.937** | -0.26 | -3,051 | 32% |
| 2020-01-01..2020-12-31 | 260 | +663 | **1.080** | 0.41 | -1,283 | 58% |
| 2015-2022 ex-2020 (from the trades table) | 895 | -2,356 | **0.872** | | | |

By year: 2015 +212 (19 tr), 2016 -443, 2017 -112, 2018 +304, 2019 -459, 2020 +663, 2021 -1,049, 2022 -809. Only 2020 (the gold bull
year) and the small 2015/2018 samples are positive. Criterion "history 2015-2022 PF >= 1.0 ex-2020": FAILED by a wide margin (0.87).

## 5. Slippage

MAIN with `--slip 2` (2 ticks per side on market/stop fills): 326 trades, net -1,623, **PF 0.939**, Sharpe -0.31, maxDD -6,494.
Criterion "slippage-2 MAIN PF >= 1.0": FAILED (it already fails at 1 tick).

## 6. Thin-session dependence (MAIN trades table)

- Net is -1,046, so "share of net" is undefined. The 10 best days sum to +7,228 = 28.6% of gross wins; without them the net is -8,274.
  Best days: 2026-03-31 +940, 2025-05-15 +796, 2026-01-27 +780, 2025-10-16 +761, 2025-10-20 +750, 2025-11-12 +693, 2025-05-20 +680,
  2025-11-24 +680, 2026-02-06 +628, 2025-12-11 +520.
- Months: best 2025-05 +2,062 (alone larger than |net|); 2025-04..2025-10 earn +5,272, then 7 consecutive losing months
  2025-12..2026-06 total -5,365; worst 2026-03 -1,799. 7 of 19 traded months positive. No month exceeds 40% of a positive net because there is
  no positive net; in absolute terms May-2025 is 2x |net|.
- Exit mix: 149 stops -20,926; 67 forced flats at 16:30 +18,709; 108 channel exits +817; 3 session ends +354. All of the gross profit
  is "gold trended into the close"; the Donchian exit contributes nothing.

## Walk-forward (from `walkforward.json`, not re-run)

OOS 2025-01..2026-09: 171 trades, net +2,043, PF 1.145, Sharpe 0.53, largest day 36% of net, 9/21 positive months; Q2+Q3 2025 earn +3,958,
the other five quarters -1,915. Full OOS 2023-2026: 604 trades, PF 0.978. The 2025 OOS figure clears the 1.1 bar narrowly and rests on two
quarters of the gold bull run with the selector on the slowest cells (60-min / 55 / sma200).

## Criteria and verdict

| criterion | value | pass |
|---|---|---|
| no look-ahead | none found | yes |
| walk-forward OOS 2025 PF >= 1.1 | 1.145 | yes (narrow) |
| plateau_frac >= 0.5 | 0.50 (3/6; centre PF 0.96) | yes (at the boundary) |
| history 2015-2022 PF >= 1.0 ex-2020 | 0.872 (0.937 incl. 2020) | NO |
| slippage-2 MAIN PF >= 1.0 | 0.939 | NO |

Two criteria fail, the history one by a wide margin, and the fixed rule loses on MAIN (0.96), PRIOR (0.96), 2015-2022 (0.94) and 2021-2023
(0.70, README). Verdict: **dead**. The code is clean; the edge is not there outside the 2025 gold bull run. Do not allocate.

Raw run outputs: scratchpad `tgd/*_metrics.json`, `main_trades.csv`, `hist_trades.csv` (session-specific temp dir).
