# cal_window - adversarial verification (2026-10-04)

Contract MNQ, fixed params from final.json: `{"window":"totm","side":"auto","entry_time":"09:31","exit_time":"15:55","stop_atr":0.75,"target_atr":0.0,"trend_filter":false,"press_conf_only":true,"max_trades":1}`.
All numbers per ONE micro contract after costs ($1.30 RT + 1 tick slippage per side unless stated). final_select / walk-forward
were NOT re-run; the walk-forward numbers below are read from `walkforward.json`.

## 1. Look-ahead audit (`strategies/cal_window.py`, `strategies/_cal_flags.py`, `strategies/common.py`, `backtest/data.py`, `backtest/engine.py`)

| item | finding |
|---|---|
| Entry bar | `i_entry` = first bar with tod == 09:31; `place(i, side, stop_pts, tgt_pts)` with `entry_px` NaN = market at the open of bar i (+1 tick). Verified on all 80 MAIN trades: entry tod 09:31 on every trade. Nothing from bar i or later enters the decision. |
| Daily features | `daily_atr(df1, 14, rth_only=True)` = Wilder ATR of RTH daily bars `.shift(1)` (day d uses days < d), `min_periods=14` so NaN rows do not trade (`day_ok` requires ATR non-NaN). `sma(D.close, 200).shift(1)` and `prev_close = D.close.shift(1)` are shifted (only used with trend_filter=False here, i.e. unused). `open_0930` and `ref` (09:30 close) are computed but never used in `day_ok`/side/stop. No VIX. |
| Calendar flags | `totm`, `opex_week`, `payday`, `santa`, `pre_witch5`, `precash`, `dow` are exchange-calendar arithmetic (known the day before). FOMC dates are a hard-coded table (meeting dates are published a year ahead, so 2025-2026 entries are not look-ahead; irrelevant for window=totm anyway). |
| Exit | `exit_at(first bar >= exit_tod)` = market at that bar's open; per-session `force_flat` from exit_tod and global `set_session('09:31','09:32','15:55')`. Latest MAIN exit 15:55. Stops fill at level - slip. No session high/low/close used anywhere. |
| i_next / resample / opening_range / session_vwap / overnight_range | not used. |
| `early_close` exit (12:55) | uses the session's own last RTH bar (`rth_last_tod < 15:30`), i.e. same-session information - BUT every such session 2011-2026 is also a thin session (< 80% RTH bars) that `run.prepare` blocks for entry (0 early_close-and-not-thin sessions on NSXUSD 2011-01..2026-09). Dead code path under default settings; would only matter with `skip_thin_sessions=False`. |
| Data-boundary artifact (not a market look-ahead, but a mis-flag) | `totm` T-1 = `by_month[...][-1]`, the LAST calendar session of each month *in the loaded data*. The loaded data ends 2026-09-24/25, so 2026-09-24 (a Thursday, not the month end) is flagged T-1 and traded (+$528.3, 5.2% of MAIN net). The flag "knows" the dataset ends there. The real T-1 (2026-09-30) is outside the data. MAIN ex that trade: net +$9,551, PF 1.88 - conclusion unchanged. Suggested fix (not applied): in `_cal_flags.flags`, only assign `totm_pos = -1` to `lst[-1]` when a later calendar session exists in the data (`vidx[lst[-1]] + 1 < len(valid_dates)`) or when `lst[-1]` is the last exchange business day of its month by calendar (e.g. `pd.offsets.BMonthEnd` adjusted for holidays); same guard for the start of the warm-up window is unnecessary because `prepare` blocks entries before `start`. Also note the same mechanism would flag a feed-outage day's predecessor as T-1 (a day with < 60 RTH bars drops out of `cal_session`); none observed in the trade sample. |
| Parameters encoding 2025-26 | PARAMS are the published McConnell-Xu / Quantpedia TOTM window (T-1, T+1..T+3) forced intraday; stop 0.75 ATR is the family spec. The 16-cell GRID does not contain the fixed stop 0.75. Contract MNQ was chosen because it was positive on MAIN and PRIOR (MES PRIOR is 0.91): a mild selection on the test window, disclosed in the README. |

**lookahead_found = false.** One data-edge mis-flag (2026-09-24 traded as T-1) that is not a market-information leak and does not change any conclusion.

## 2. Fixed params re-run (MNQ)

| period | trades | net $ | win | PF | Sharpe | maxDD intra | largest_day_share |
|---|---|---|---|---|---|---|---|
| MAIN 2025-01-01..2026-09-30 | 80 | +10,079.8 | 65.0% | **1.932** | 1.80 | -2,368 | 0.111 |
| PRIOR 2023-01-01..2024-12-31 | 72 | +1,658.3 | 58.3% | **1.208** | 0.47 | -1,298 | 0.490 |

Both reproduce `final.json` (`fixed_main`, `fixed_prior`) to the dollar. MAIN exits: 67 flat at 15:55, 13 stops.
Walk-forward (from walkforward.json, not re-run): OOS 2025-01..2026-09 80 trades, net +5,890, **PF 1.493**, Sharpe 1.10, 10/21 positive months; whole OOS 2023-26 356 trades PF 1.11; Lucid 50K Flex on the OOS stream: best 5 micros, exp net +132 but bootstrap lower bound -146 = zero-edge control -> not recommended.

## 3. Plateau (MAIN, one grid step from the fixed value, everything else fixed)

GRID = window {totm, opex_week, fomc, all_days} x exit_time {12:00, 15:55} x stop_atr {0.5, 1.0}. The only numeric parameter is `stop_atr` (fixed 0.75, grid neighbours 0.5 below and 1.0 above).

| neighbour | trades | net $ | PF | >= 1.05 |
|---|---|---|---|---|
| stop_atr 0.5 | 80 | +8,690 | 1.794 | yes |
| stop_atr 1.0 | 80 | +9,746 | 1.875 | yes |
| (supplementary) exit_time 12:00 | 80 | +6,797 | 1.834 | yes |

**plateau_frac = 2/2 = 1.00** (3/3 including the exit_time neighbour). The stop is nearly irrelevant (13-19 stops per period); the plateau is flat because the rule has one real degree of freedom (which days to be long) and the PF comes from the 2025-26 day selection, not from the risk parameters. The window axis itself is NOT a plateau: all_days 1.01-1.14, opex_week 0.71-1.00, fomc 0.27-0.54 on MAIN (README grid).

## 4. History (MNQ, fixed params)

| period | trades | net $ | win | PF | Sharpe |
|---|---|---|---|---|---|
| 2015-01-01..2022-12-31 | 367 | +1,220.3 | 47.7% | **1.048** | 0.11 |
| 2015-2022 ex-2020 (from the same trades) | 321 | -1,649.4 | - | **0.926** | - |
| 2020-01-01..2020-12-31 | 46 | +2,870.2 | 65.2% | **1.916** | 1.82 |

Year by year 2015-2022 (net / PF): 2015 -700 / 0.59, 2016 -473 / 0.68, 2017 -257 / 0.77, 2018 +940 / 1.43, 2019 -460 / 0.81, 2020 +2,870 / 1.92, 2021 -2,298 / 0.63, 2022 +1,599 / 1.22. Six of eight years negative; the whole 2015-2022 result is 2020 (+$2,870 on 46 trades). Ex-2020 the rule loses $5/trade on 321 trades (t ~ -0.4 vs zero: statistically indistinguishable from both PF 1.0 and from no edge). The criterion "2015-2022 PF >= 1.0 ex-2020" is **missed** (0.926).

## 5. Slippage

MAIN with `--slip 2`: 80 trades, net +10,006.3, **PF 1.924**, Sharpe 1.79. One market entry and one market/stop exit per day, so two extra ticks cost $1/trade on MNQ ($73.5 total); passes trivially.

## 6. Thin-session / concentration dependence (MAIN trades table)

- Gross wins +$20,889 vs gross losses -$10,810 on 80 trades: a 65% win rate on a symmetric payoff (avg win +$402, avg loss -$386).
- **Top 10 days = +$8,632 = 85.6% of net** (top 5: 2026-08-04 +1,123, 2026-08-03 +1,071, 2026-03-31 +987, 2026-06-30 +980, 2025-04-02 +868). With a mean of $126/trade on a $390-sigma payoff this is expected arithmetic rather than outlier dependence (largest single day 11.1% of net), but it says the edge is a thin margin of win rate, not a fat right tail.
- Months: best 2026-03 = 23.8% of net, then 2025-02 19.4%, 2026-08 17.5%, 2025-04 16.9%, 2026-06 16.1%. **No month > 40%.** 13/21 months positive.
- Weekday: Mon +3,807 (18), Tue +5,185 (19), Wed +3,242 (18), Thu -267 (10), Fri -1,889 (15): the whole result is 55 Mon-Wed trades.
- Boundary: 2026-09-24 (+$528) is a mis-flagged T-1 (see section 1).

## Verdict

| criterion | value | pass |
|---|---|---|
| no look-ahead | none (one data-edge mis-flag, +$528, documented) | yes |
| walk-forward OOS 2025 PF >= 1.1 | 1.493 | yes |
| plateau_frac >= 0.5 | 1.00 | yes |
| history 2015-2022 PF >= 1.0 ex-2020 | 0.926 (1.048 incl. 2020) | **no** |
| slippage-2 MAIN PF >= 1.0 | 1.924 | yes |

One criterion missed, by 0.07 of PF on 321 trades (t ~ -0.4, i.e. within noise of 1.0) -> **marginal** by the letter of the rule.
Adversarial reading: the only criterion that tests whether the edge existed before the test window fails, 6 of 8 history years
are negative, the 2011-2024 TOTM-minus-control is ~0 bp (README), 86% of MAIN net sits in 10 days and all of it in Mon-Wed, and
the Lucid Monte Carlo on the walk-forward stream is not recommended at any size (lower bound = zero-edge control). The MAIN
PF 1.93 is a two-year streak in a long-biased tape with no historical counterpart. Treat as marginal-not-allocatable: do not
give it a portfolio slot; the reusable output is the control-adjusted window table in the README.
