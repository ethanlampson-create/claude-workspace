# orb_sma_rr — adversarial verification (2026-10-04)

Verifier run on MNQ with the fixed params from `final.json`:
`{"or_minutes": 15, "sma_len": 200, "rr": 2.0, "stop_cap_pts": 1e9, "max_stop_atr": 0.15, "buffer_ticks": 1, "last_entry": "12:00",
"min_range_atr": 0.1, "max_trades": 1, "flat": "15:55", "reentry": false}`. All numbers per ONE micro contract after engine costs
($1.30 RT + 1 tick slippage per side unless `--slip 2`). Raw outputs (trades/daily/metrics per run) are in the verifier scratchpad
`.../scratchpad/v_sma/` (`main_*`, `prior_*`, `hist_*`, `y2020_*`, `slip2_*`, `msa_up_*`, `rr_dn_*`, `rr_up_*`, `or_up_*`, `msa_dn_x_*`, `or_dn_x_*`).
Nothing under `backtest/`, `tests/` or `strategies/` was modified; `final_select` was not re-run (walk-forward numbers are read from
`walkforward.json`).

## 1. Look-ahead review — none found

Read line by line: `strategies/orb_sma_rr.py`, `strategies/common.py` (`opening_range`, `daily_atr`, `atr`, `vix_lag1`),
`backtest/data.py` (`load_1m`, `daily_bars`), `backtest/engine.py` (entry/fill semantics, `Intents.place`, `set_session`), `backtest/run.py` (`prepare`).

| check | finding |
|---|---|
| Trend filter (`daily_trend_bias`) | Daily NDX closes from `data/parquet/NDX_1d.parquet` (date-indexed at midnight, no duplicates). `searchsorted(session_date, side='left') - 1` = last row strictly before the session date, so session d uses the close of d-1 (Monday uses Friday — checked: 2025-03-10 uses 2025-03-07). SMA(200) is `rolling(min_periods=200)` on those closes, NaN -> bias 0 -> no trade. Never built from the 1-minute feed. OK. |
| ATR14 | `daily_atr` = Wilder ATR on RTH daily bars `.shift(1)`; verified numerically equal to the unshifted ATR shifted by one row. Day d uses days < d. `min_periods=14`, NaN rows excluded by `orr['atr'].notna()`. OK. |
| Opening range | `opening_range` over `[09:30, 09:45)`; `i_end` = last 1-min index inside the window; order index `i0 = i_end + 1` = first bar at/after 09:45, so the order is live from the open of the bar after the range closes (engine: signal at i is live from the open of bar i). `n_bars >= or_minutes - 2` requires a complete range. `good` requires `i0` in the same day. `set_session('09:45', '12:00', '15:55')` additionally blocks any fill before 09:45. OK. |
| Entry decision inputs | level = or_high + 1 tick / or_low - 1 tick (completed range); stop distance = min(range, cap, 0.15 x ATR14) (completed range + prior-day ATR); target = rr x stop. No session high/low/close, no bar at or after the entry bar. OK. |
| i_next / resampling | Not used (works directly on the 1-minute index). OK. |
| session_vwap / overnight_range / VIX | Not used in the fixed config (`max_vix=None`); `vix_lag1` is correctly lagged anyway. OK. |
| Fill semantics | Stop entry fills at max(open, level) + 1 tick slippage on the first bar whose high >= level; on the entry bar the stop is checked before the target (conservative). Pending order lives `last_entry - tod[i0]` bars and `allow_entry` cancels it at 12:00. OK. |
| 2025-2026 knowledge in params | No dates, regime switches or calendar rules. `stop_cap_pts=1e9` / `max_stop_atr=0.15` were chosen after seeing MAIN and PRIOR grids (acknowledged in README) — in-sample selection, not look-ahead in the code sense; the walk-forward in `walkforward.json` is the control for it. |
| Engine-level note | `run.prepare` skips thin sessions using the median RTH bar count of the loaded window (uses future sessions only to define "typical"); negligible and engine-wide, not strategy-specific. |

Numeric spot-check on all 304 MAIN trades: side == sign(lagged NDX close - SMA200) recomputed independently from the parquet 304/304;
entry fill beyond range level + 1 tick 304/304; entry bar index > `i_end` and tod >= 09:45 304/304; entry tod range 09:45..11:54.
`lookahead_found = false`.

## 2. Fixed params re-run (current engine)

| period | trades | net | win | PF | Sharpe | max DD intraday | largest_day_share | pos months |
|---|---|---|---|---|---|---|---|---|
| MAIN 2025-01-01..2026-09-30 | 304 | +3,377 | 39.8% | **1.147** | 0.81 | -2,135 | 0.121 | 57% |
| PRIOR 2023-01-01..2024-12-31 | 274 | +1,961 | 38.3% | **1.151** | 0.75 | -1,689 | 0.141 | 46% |

Identical to `final.json` `fixed_main` / `fixed_prior` (reproducible). Walk-forward OOS 2025-01..2026-09 (`walkforward.json`, not re-run):
304 trades, net +4,684, **PF 1.173**, Sharpe 0.96; WF OOS 2023-01..2026-09: 578 trades, PF 1.127.

## 3. Plateau (module GRID = `{'max_stop_atr': [0.15, 0.25], 'rr': [1.4, 2.0, 3.0], 'or_minutes': [15, 30]}`), MAIN, fixed params otherwise

| neighbour | in GRID? | trades | net | PF | Sharpe | >= 1.05 |
|---|---|---|---|---|---|---|
| max_stop_atr 0.25 (up) | yes | 304 | +6,219 | 1.209 | 1.08 | yes |
| max_stop_atr 0.05 (down, extrapolated; 0.15 is the grid floor) | no | 304 | -4,125 | 0.592 | -3.15 | no |
| rr 1.4 (down) | yes | 304 | +3,027 | 1.148 | 0.86 | yes |
| rr 3.0 (up) | yes | 304 | +1,186 | 1.047 | 0.25 | no (misses by 0.003) |
| or_minutes 30 (up) | yes | 265 | -187 | 0.991 | -0.05 | no |
| or_minutes 10 (down, extrapolated; 15 is the grid floor) | no | 315 | +5,862 | 1.252 | 1.36 | yes |

`plateau_frac` over the four neighbours that exist in GRID = **2/4 = 0.50** (3/6 = 0.50 including the two extrapolated steps).
Reading: the stop-width axis is a one-sided cliff (tighter = dead, wider = better, consistent with the README's cap story), rr is flat to
slightly falling, and OR30 — the *published* opening-range length — is breakeven on MAIN with this stop. The surface is a ridge along
or_minutes=15, not a plateau in or_minutes.

## 4. History

| period | trades | net | win | PF | Sharpe | max DD intraday |
|---|---|---|---|---|---|---|
| 2015-01-01..2022-12-31 (one run) | 1,358 | -2,000 | 34.8% | **0.951** | -0.25 | -4,189 |
| 2015-2022 **ex-2020** (trades of 2020 removed from that run) | 1,183 | -1,225 | — | **0.963** | — | — |
| 2020-01-01..2020-12-31 (separate run) | 175 | -775 | 35.4% | **0.905** | -0.59 | -1,553 |

By year (trades / net / PF): 2015 159 / -769 / 0.66; 2016 175 / -428 / 0.81; 2017 156 / +32 / 1.02; 2018 178 / -263 / 0.94;
2019 161 / -136 / 0.96; 2020 175 / -775 / 0.90; 2021 178 / -475 / 0.94; 2022 176 / +813 / 1.07. Only 2 of 8 years positive; the
2017-2022 ex-2020 stretch is breakeven (net -29 on 849 trades) and the shortfall comes from 2015-2016. The ex-2020 miss is -3.7% on
PF, i.e. about -$1.0 per trade, statistically indistinguishable from breakeven but the criterion (>= 1.0) is **not met**.

## 5. Slippage

MAIN with `--slip 2` (2 ticks per side on market/stop fills): 304 trades, net +3,127, **PF 1.135**, Sharpe 0.75, max DD intraday -2,150.
Robust to doubled slippage (-$250 over 304 trades), because risk per trade is ~60 pts and 1 extra tick is 0.25 pt.

## 6. Thin-session / concentration dependence (MAIN trades table, one trade per day)

- Ten best days: 2025-04-21 +410, 2025-04-28 +399, 2026-06-30 +389, 2026-06-26 +386, 2026-08-06 +380, 2026-08-04 +369, 2026-08-03 +368,
  2025-04-08 +364, 2026-06-23 +353, 2026-07-30 +350 = **+3,768 = 112% of net (+3,377)**. Without them the strategy nets -391 (PF 0.983) on
  294 trades. The 10 best days are 14% of gross profit, so this is the normal profile of a PF 1.15 / 40%-win 2R system rather than a
  few outliers, but it means the whole edge is carried by ~3% of the sessions.
- Months: max single month 2025-03 +877 = 26% of net; **no month > 40%**. 12/21 months positive; 2026-01..06 contributed 51% of net
  (`wf_2025_monthly` shows 113% for the walk-forward stream); 2026-07..08 lost -741.
- Exit mix: 107 targets +25,082, 181 stops -22,992, 16 flat-at-close +1,287. Longs 261 trades +4,208; shorts 43 trades -831 (shorts lose).
- `largest_day_share` MAIN 0.121 (single best day 12% of net).

## Verdict: marginal

| criterion | value | threshold | result |
|---|---|---|---|
| look-ahead | none found (code + 304/304 numeric) | none | pass |
| walk-forward OOS 2025 PF (`walkforward.json`) | 1.173 | >= 1.1 | pass |
| plateau_frac | 0.50 (2/4; rr 3.0 misses by 0.003, OR30 fails clearly) | >= 0.5 | pass (on the boundary) |
| history 2015-2022 ex-2020 PF | 0.963 (full 0.951; 2020 alone 0.905) | >= 1.0 | **fail, narrow** |
| slippage-2 MAIN PF | 1.135 | >= 1.0 | pass |

Exactly one criterion is missed and the miss is narrow (PF 0.963 vs 1.0, -$1/trade over 1,183 trades), so by the rule the verdict is
**marginal**, not survivor. It is a weak marginal: the plateau sits exactly on the 0.5 line with the published OR30 dead, the edge is
carried by 10 sessions (112% of net), 6 of 8 history years are negative, and the author's own Lucid simulation already reports
`recommended = 0` at every size (per-micro DD $2.1-2.4k against the $2k trailing MLL). No engine or strategy bug found; nothing to fix
in the module.
