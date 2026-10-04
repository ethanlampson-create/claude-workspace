# mr_gapfade - adversarial verification (2026-10-04)

Fixed params from `final.json`: contract MNQ, `{"gap_max": 0.35, "entry_delay": 1}` (all other params = module defaults).
All numbers per 1 micro contract, after engine costs ($1.30 RT commission, 1 tick slippage per side unless `--slip 2`).
`backtest.run` skips thin sessions (holiday / early close) by default; `final.json.period_main` (114 trades, PF 1.56) was
produced before that filter existed. The current CLI reproduces `walkforward.json.fixed_main` exactly (109 trades, PF 1.61).

## 1. Look-ahead review of `strategies/mr_gapfade.py` - none found

| item | where | finding |
|---|---|---|
| prior close / PDH / PDL | `prior_day_stats` (common.py:54) | RTH daily bars `.shift(1)` by session; day d uses session d-1 only. `pd_close` = last 1-min close with tod < 16:00 (never the 16:14 feed stop). |
| ATR | `daily_atr` (common.py:82) | Wilder ATR on RTH daily bars, `.shift(1)`; `min_periods=n` so warm-up rows are NaN and `q &= t['atr'].notna()` blocks them. |
| VIX gate | `vix_regime` (module:42-56) | `searchsorted(dates, side='left') - 1` = last VIX close strictly before the session date; rolling 100-day hi/lo evaluated at that same lagged position, so the range is also built from closes <= d-1. `min_periods=lb`; `hot.notna()` required. |
| trend SMA (off by default) | module:76-78 | `rolling(trend_len, min_periods=trend_len).mean().shift(1)` -> sessions < d. Inert here (`trend_filter='none'`). |
| open_0930 / gap | module:65-71 | Open of the 09:30 bar; known at 09:30:00. Nothing from the 09:30 bar's high/low/close enters qualification. |
| entry bar | module:113-139 | `k` = first bar with `tod == 09:30 + entry_delay`; `it.place(k)` -> live from the OPEN of bar k. Pre-entry checks use `l[i0:k]`, `h[i0:k]`, `c[k-1]`: bars 09:30..k-1 only, all closed before the fill. With entry_delay 1 this is exactly the 09:30 bar. |
| stop / target | module:123-137 | Built from open_0930, pd_close, lagged ATR only. The engine checks the protective stop on the entry bar against that bar's extreme (conservative). |
| exit | module:148-152 | `exit_at` at the first bar >= exit_time (open of that bar), `set_session` forces flat at 15:55; no session-own high/low/close used anywhere. |
| i_next / resample / opening_range / overnight_range / session_vwap | - | not used; the module works directly on the 1-minute index. |
| hard-coded dates / regime switches | - | none. No parameter encodes 2025-2026 knowledge; `gap_max 0.35` and `entry_delay 1` were tuned on MAIN by the author (disclosed in the README) but are not date-based. |

Minor, not look-ahead: (a) `entry_delay=0` would crash (`l[i0:i0].min()` on an empty slice) - the grid never uses it; (b) `backtest.run.thin_sessions` classifies holidays with the median RTH bar count over the whole loaded window - a liquidity filter, not a predictive feature.

## 2. Fixed params re-run

| period | trades | net $ | win | PF | maxDD intra | Sharpe | largest_day_share |
|---|---|---|---|---|---|---|---|
| MAIN 2025-01-01..2026-09-30 | 109 | +2051 | 0.578 | **1.610** | -585 | 1.58 | 0.108 |
| PRIOR 2023-01-01..2024-12-31 | 104 | +571 | 0.519 | **1.165** | -847 | 0.48 | 0.248 |

Exit reasons MAIN: 61 targets +$5396, 45 stops -$3307, 3 time exits -$39. PRIOR: 52 targets +$3956, 47 stops -$3400, 5 time exits +$15.

## 3. Plateau (MAIN, fixed params otherwise, one grid step up / down)

Numeric GRID parameters: `gap_max [0.35, 0.50]` (step 0.15), `stop_mult [0.75, 1.0]` (step 0.25). Fixed values sit at a grid edge
(gap_max 0.35 is the lowest, stop_mult 1.0 the highest), so the missing neighbour is extrapolated by one grid spacing.

| neighbour | trades | net $ | PF | Sharpe | maxDD intra | PF >= 1.05 |
|---|---|---|---|---|---|---|
| gap_max 0.20 | 51 | +414 | 1.295 | 0.60 | -313 | yes |
| gap_max 0.50 | 152 | +2218 | 1.331 | 1.12 | -1075 | yes |
| stop_mult 0.75 | 102 | +1560 | 1.508 | 1.31 | -458 | yes |
| stop_mult 1.25 | 111 | +2393 | 1.615 | 1.60 | -737 | yes |

**plateau_frac = 4/4 = 1.00.** Extra (not counted): entry_delay 2 -> 93 tr, PF 1.715; exit_time 12:00 -> 109 tr, PF 1.577;
sides long -> 36 tr, PF 1.629. The MAIN surface is a plateau, not a spike.

## 4. History

| period | trades | net $ | win | PF | Sharpe |
|---|---|---|---|---|---|
| 2015-01-01..2022-12-31 (all) | 549 | -40 | 0.503 | **0.995** | -0.02 |
| 2015-2022 ex-2020 | 496 | +76 | - | **1.011** | - |
| 2020 alone | 53 | -116 | 0.491 | **0.903** | -0.32 |

By year (trades / net / PF): 2015 76 / +57 / 1.09; 2016 77 / -258 / 0.65; 2017 100 / +442 / 1.58; 2018 59 / -452 / 0.54;
2019 75 / -288 / 0.76; 2020 53 / -116 / 0.90; 2021 79 / +230 / 1.11; 2022 30 / +345 / 1.58.
The ex-2020 figure clears the >= 1.0 bar by 0.011 on 496 trades: that is zero edge, not a weak edge. Four of eight years
are losing. The edge the MAIN/PRIOR numbers show is a 2021+ phenomenon (2021-2026 all positive), not a property of the rule.

## 5. Slippage

| period | slip | trades | net $ | PF | maxDD intra |
|---|---|---|---|---|---|
| MAIN | 2 ticks | 109 | +1973 | **1.579** | -601 |
| PRIOR | 2 ticks | 104 | +493 | 1.141 | -862 |

MNQ tick = 0.25 pt = $0.50, so doubling slippage costs ~$0.75/trade; the strategy is insensitive to it (avg trade $18).

## 6. Thin-session dependence (MAIN trades table, one trade per day)

- 10 best days = +$1641 of +$2051 net = **80%**. Ex-top-10: 99 trades, net +$410, PF 1.12. With a 1:1 bracket and a 58%
  hit rate this is partly mechanical (the best 10 of 61 winning days), but it means ~9% of trading days carry the result.
- Largest single day $221 = 10.8% of net. Largest month 2026-02 = +$677 = 33% of net; **no month > 40%**.
- PRIOR: 10 best days = +$1286 vs net +$571 (225%); ex-top-10 PF 0.79; 5 months > 40% of the small net. The PRIOR edge is
  entirely in a handful of days.
- Walk-forward (from `walkforward.json`, not re-run): wf_2025 PF 1.51 on 65 trades, 2026-07..09 = 65% of OOS net.

## Verdict against the criteria

| criterion | threshold | value | pass |
|---|---|---|---|
| no look-ahead | - | none found | yes |
| walk-forward OOS 2025 PF (walkforward.json wf_2025) | >= 1.1 | 1.511 | yes |
| plateau_frac | >= 0.5 | 1.00 | yes |
| history 2015-2022 PF ex-2020 | >= 1.0 | 1.011 (all-in 0.995) | yes, at the floor |
| slippage-2 MAIN PF | >= 1.0 | 1.579 | yes |

**Verdict: survivor** (on the letter of the five criteria). Caveats that belong next to that label: the 2015-2022 edge is
nil (PF 1.01 ex-2020, 0.995 all-in, 4/8 losing years), so the 2021-2026 profitability is regime-dependent; 80% of MAIN net
comes from 10 days; ~5 trades/month at $18/trade is too slow to be a standalone Lucid vehicle (README Lucid scan:
`recommended = False`). Fit for a low-correlation portfolio leg only, as the README already concludes.

Runs: `python3 -m backtest.run --strategy mr_gapfade --contract MNQ --params '{"gap_max":0.35,"entry_delay":1}' ...` with the
periods / `--slip 2` / neighbour params above. Trades tables used for section 6 and the per-year table were saved to the
session scratchpad (`main_trades.csv`, `prior_trades.csv`, `hist_trades.csv`); `final_select` was not re-run.
