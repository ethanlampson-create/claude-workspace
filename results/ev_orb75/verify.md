# ev_orb75 - adversarial verification (2026-10-04)

Fixed params (`final.json`): `{"or_start":"09:30","or_minutes":25,"hold_min":75,"trend_filter":"none","stop_mode":"none","stop_atr":0.5,
"last_entry":"11:30","max_trades":1,"skip_vvg":false,"flat":"15:55","dls_mult":1.0,"dps_mult":2.0,"delay":0}`, contract MES.
All numbers per ONE micro contract after costs ($1.30 RT commission + 1 tick slippage per side on market fills = 0.76 MES pts per round trip),
engine state of 2026-10-03. Runs driven through `backtest.run.run_strategy` (the `python3 -m backtest.run` code path, 2 processes at a time);
raw tables in the session scratchpad `runs/`. Walk-forward numbers are taken from `walkforward.json` (not re-run).

## 1. Look-ahead audit of `strategies/ev_orb75.py` - none found

- Bars and signal placement (l.110, 125-138). `resample(df1, 5, rth_only=True)` buckets by `(tod - 18:00) // 5`, so RTH bars start 09:30, 09:35, ...
  and `i_next` is the first 1-min bar after `i_last` in the same session (`backtest/data.py` l.69-72). A candidate bar needs `tod >= 09:55` (the OR
  end) and `tod + 5 <= 11:30`; the first bar of the day with `close > or_high` is kept (`groupby('day_id').head(1)`), and the market order is placed
  at `b['i_next'][k + delay]` (same-day check at l.137). Verified on 2025-Q1 (43 signals, 0 failures): every order index is `i_next` of a 5-min
  bar whose `i_last < i`, whose close exceeds the day's `or_high`, with no earlier qualifying bar of the day closing above `or_high`; entry
  `tod` runs 10:00 .. 11:20, inside the `set_session` window [09:55, 11:35), flat 15:55. This is the correct `i_next` placement: the decision
  uses the 5-min close, the fill is the next 1-min open + 1 tick.
- Opening range (l.111, `common.opening_range`). `or_high`/`or_low` = high/low of the 1-min bars with `tod` in [09:30, 09:55) of the same
  `day_id`; checked that the last OR bar index is below `i_first` of every signal bar and that `or_high` equals the max high of those bars.
  The signal bar starts at or after 09:55, so the OR window is complete before it. `n_bars >= 23` guards thin OR windows.
- Daily features (l.61-93, 112-115). `daily_atr(df1, 14, rth_only=True)` = Wilder ATR of RTH daily bars `.shift(1)` (day d uses days < d).
  `prev_close[d] = close.shift(1)`, `sma[d] = SMA200(close).shift(1)` on RTH daily closes built from `load_1m(symbol, first-420d, first-1d)`
  plus df1 (duplicates `keep='last'`, sorted); the history ends the day before df1's first session, so nothing from df1's window leaks
  backwards. Spot-checked three sessions: `prev_close` equals the previous RTH close and `sma` equals the mean of the 200 closes strictly
  before d, to the decimal. `qg`/`qr` (VVG quantiles) are expanding quantiles `.shift(1)` with `min_periods` 120 -> sessions < d only.
- VVG gate (off in the fixed params). `gap` and `r30` ARE the day's own 09:30 open and 09:59 close, by design; the module only uses them
  when `skip_vvg=True` and then restricts candidate bars to `tod + 5 >= 10:00` (l.126-127), i.e. the earliest signal bar is 09:55-09:59 whose
  order is placed at the 10:00 open, when the 09:59 close is known. Not a look-ahead; irrelevant here since `skip_vvg=False`.
- Exit (l.151, 145-148). `stop_mode='none'` -> `stop_px` NaN; the only exits are `max_hold = 75` 1-min bars from the fill (engine: exit at the
  open of the bar where `held >= 75`) or the 15:55 flat. MAIN trades: 250 / 250 `max_hold` exits. No session high/low/close, no VIX used.
- Risk block: `daily_loss_stop = 35`, `daily_profit_stop = 100` per micro, `max_trades_day = 1`; with one trade per day these never bind.
- Parameters. Nothing encodes dates or regime switches. Caveat (selection, not look-ahead): `stop_mode='none'` is not in the module `GRID`
  (`or_low`/`atr`) and was adopted after reading the MAIN and PRIOR exit-reason tables (README attempt 4); the walk-forward used the grid
  (always with a stop) and is the honest yardstick. The fixed `hold_min=75` is the published value.

`lookahead_found = false`.

## 2. Fixed-parameter re-runs

| run | trades | net $ | PF | Sharpe | maxDD intra | pos months | largest day share |
|---|---|---|---|---|---|---|---|
| MAIN 2025-01-01..2026-09-30 | 250 | +1,092 | 1.140 | 0.58 | -1,030 | 12/21 | 0.260 |
| PRIOR 2023-01-01..2024-12-31 | 218 | +730 | 1.141 | 0.49 | -992 | 12/24 | 0.544 |

Both reproduce `final.json` exactly (MAIN PF 1.1396, PRIOR 1.1415). MAIN by year: 2025 143 trades PF 1.136 (+562), 2026 107 trades PF 1.144
(+531). Average trade $4.37 = 0.87 MES pts gross per trade vs 0.76 pts of cost: the edge is about one tick.
Walk-forward OOS 2025-01..2026-09 (`walkforward.json`, 15 folds, grid-selected params, always with a stop): 221 trades, +840, PF 1.118,
Sharpe 0.44, maxDD -875, largest day 61% of net, 12/21 months positive, 7 / 15 folds negative. Criterion PF >= 1.1 met by 0.018.

## 3. Plateau (MAIN, fixed params otherwise; the only numeric GRID key is `hold_min` [60, 75, 120])

| neighbour | trades | net $ | PF | Sharpe | maxDD | >= 1.05 |
|---|---|---|---|---|---|---|
| hold_min 60 (one grid step down) | 250 | +1,902 | 1.274 | 1.01 | -913 | yes |
| hold_min 120 (one grid step up) | 250 | +604 | 1.058 | 0.24 | -1,416 | yes |

`plateau_frac = 2/2 = 1.00`, though hold 120 clears the bar by 0.008 and the ordering is reversed on PRIOR (README: hold 120 best there, hold 60
PF 1.09). Categorical GRID neighbours for information (MAIN): stop_mode `or_low` PF 1.080 (+654), `atr` 1.128 (+1,010); trend_filter `sma200`
1.041 (219 trades, +272); skip_vvg True 1.063 (172 trades, +337). Every neighbour is positive but every one is below the fixed cell: the
fixed cell is the best of its neighbourhood on MAIN, a mild peak on a low plateau (PF 1.04-1.27).

## 4. History (fixed params)

| period | trades | net $ | PF | Sharpe | maxDD intra | pos months |
|---|---|---|---|---|---|---|
| 2015-01-01..2022-12-31 | 1,068 | -6,861 | 0.701 | -1.29 | -7,062 | 29/96 |
| 2020-01-01..2020-12-31 | 152 | -1,732 | 0.626 | -1.74 | -1,952 | 3/12 |
| 2015-2022 ex-2020 | 916 | -5,129 | 0.720 | | | |

By year (PF, net): 2015 0.32 (-1,285), 2016 0.64 (-573), 2017 0.66 (-371), 2018 0.59 (-1,135), 2019 0.94 (-117), 2020 0.63 (-1,732),
2021 1.02 (+62), 2022 0.71 (-1,710). Sub-periods: 2015-2018 PF 0.54, 2019-2022 PF 0.78, 2021-2022 PF 0.82. Gross MES pts per trade by year:
-1.9 / -0.6 / -0.4 / -1.3 / +0.1 / -2.0 / +0.4 / -2.3 (vs +0.9 to +1.3 on 2023-2026). Median MAE/MFE -4.6 / +4.1 pts on 2015-2022 vs
-9.2 / +11.1 on MAIN: with the S&P at 2,000-4,300 the 75-minute excursion is half the size, the fixed 0.76-pt cost eats it, and the drift after
the breakout is negative in 7 of 8 years, not just small. Criterion PF >= 1.0 ex-2020: MISSED by 28% (0.72). This is not a cost artefact alone:
2021-2022 (S&P 4,100-4,300, comparable to 2023) is PF 0.82. The published study starts Dec 2021; before that the rule simply did not work.

## 5. Slippage

MAIN with `--slip 2` (2 ticks per side on market fills): 250 trades, +467, PF 1.058, Sharpe 0.25, maxDD -1,199, 11/21 months positive,
top-10-day share 3.73 (the 10 best days are 3.7x the whole net). Criterion PF >= 1.0 met, but one extra tick per side removes 57% of the net
($625 over 250 trades), confirming that the whole edge is about one tick.

## 6. Thin-session dependence (MAIN trades / daily tables)

- 250 trading days (one trade each). The 10 best days contribute +1,766 = 161.7% of the +1,092 net (5 best: 90.7%). Without the 10 best days
  the remaining 240 days net -674 at PF 0.914: the positive result is carried by ten sessions.
- Months: TWO months exceed 40% of net: Feb-25 +554 = 50.7%, Mar-25 +474 = 43.4%; then Apr-26 37.8%, May-25 36.8%, Feb-26 32.4%. The five best
  months sum to +2,170, twice the net; Sep-Dec 2025 are all negative (-785) and Jun-Aug 2026 -783.
- Best days: 2026-04-02 +284, 2025-04-24 +203, 2025-11-14 +170, 2025-05-08 +167, 2026-08-04 +167. Worst: 2025-04-08 -347, 2026-07-02 -311,
  2026-06-22 -277, 2026-03-05 -272, 2026-06-10 -269 (crash / sell-off mornings, no stop by construction).
- Largest single day 26.0% of net (MAIN), 54.4% (PRIOR), 60.9% (WF OOS 2025). PRIOR top-10-day share 2.25.

## Verdict: dead

| criterion | value | threshold | met |
|---|---|---|---|
| look-ahead | none | none | yes |
| walk-forward OOS 2025 PF | 1.118 | >= 1.1 | yes (by 0.018) |
| plateau_frac | 1.00 (2/2; hold 120 at 1.058) | >= 0.5 | yes |
| history 2015-2022 PF ex-2020 | 0.720 (full 0.701; 2020 0.626; 2021-2022 0.82) | >= 1.0 | no |
| slippage-2 MAIN PF | 1.058 | >= 1.0 | yes |

One criterion is missed and the miss is not narrow: PF 0.72 on 916 trades, negative in 7 of 8 years, -$6,861 over 2015-2022, Sharpe -1.3.
The rule has no edge before the published study's own window (Dec 2021 onwards), so the 2023-2026 PF 1.14 is best read as the recent regime
(large 75-minute excursions at S&P 4,000-6,500) plus a one-tick drift, not a structural effect. Supporting evidence from the passes that
are technically met: the walk-forward clears 1.1 by 0.018 with 7 / 15 folds negative and 61% of net in one day; two MAIN months exceed 40% of
net; the 10 best days exceed the whole MAIN net (ex-top-10 PF 0.91); two ticks of slippage remove 57% of the net; and `stop_mode='none'` is an
in-sample choice outside the GRID. `dead`, consistent with the module README's own Lucid result (expected net per evaluation -$50, bootstrap
lower bound equal to the zero-edge control, nothing recommended at any size). Not a candidate for the account; at most a low-weight MES
time-exit diversifier if a portfolio needs one, and the history says even that is a 2023+ phenomenon.
