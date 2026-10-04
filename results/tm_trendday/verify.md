# tm_trendday - adversarial verification (MES, fixed params from final.json, per micro after costs)

Verifier run 2026-10-04. Fixed params = final.json (min_score 2, market_1030, stop_mode ib_mid, max_stop_atr 0.5, trail 0.3/0.3 tied,
gap_atr 0.7, narrow_ib_atr 0.5, max_ib_atr 1.5, skip_after_trend_day, last_entry 12:00, flat 15:55, dls $60, dps 1.5x$120).
Walk-forward numbers are taken from `walkforward.json` (not re-run). No files under backtest/, tests/ or strategies/ were modified.

## 1. Look-ahead review (`strategies/tm_trendday.py`, line by line) -> none found

| item | finding |
|---|---|
| daily_atr(14) | `atr(daily_bars).shift(1)` in `strategies/common.py`: day d uses days < d. OK |
| prev_close, pd_high, pd_low, range1, O1, C1 | all `D[...].shift(1)`; H2/L2 `shift(2)`. OK |
| NR4 / NR7 | `r1 == r1.rolling(4|7, min_periods=full).min()` on the already-shifted range: window is d-4..d-1 / d-7..d-1, NaN rows excluded. OK |
| ID (inside day) | pd_high < H2 and pd_low > L2: sessions d-1 vs d-2. OK |
| O930 | open of the `tod == 09:30` bar, known at 09:30. OK |
| IB = opening_range('09:30', 60) | bars with 570 <= tod < 630 (09:30..10:29); `i_end` = index of the 10:29 bar. Empirically `tod[ib_i_end] == 629` on every trade day. OK |
| OR30 = opening_range('09:30', 30) | bars 09:30..09:59; or_close = 09:59 close. OK |
| direction / flags / score / negative filters | use only c1029, O930, or_close, IB width and shifted daily data. OK |
| entry index | `i = ib_i_end + 1`, checked `day[i] == d and tod[i] == 10:30`; the signal is live from the OPEN of the 10:30 bar and uses data up to the 10:29 close. Empirically all 99 MAIN entries are at 10:30:00 ET. OK |
| entry_ref / stop | market mode: entry_ref = c1029 (last known close), fill = 10:30 open + 1 tick; stop_px = ib_mid (known); cap `max_stop_atr*atr` applied relative to the fill via stop_pts. OK |
| ib_break_stop mode | stop order at IB extreme +- 1 tick, live from 10:30 for `last_entry - 10:30` bars; engine fills at max(open, level)+slip. OK |
| session high/low/close | never used in the entry decision. OK |
| VIX / SMA / regime dates | not used. No parameter encodes 2025-2026 knowledge (dls/dps are fixed dollar blocks per contract). OK |
| `session_info().early_close` (minor) | computed from the session's own RTH bar count / last RTH bar (`rth_last_tod < 15:30 or rth_bars < 300`), i.e. same-session information in the day filter. Checked on MAIN: 16 sessions are excluded only by this flag; all 16 are US exchange holidays / half days (2025-01-20, 02-17, 05-26, 06-19, 07-03, 07-04, 09-01, 11-27, 11-28, 12-24, 2026-01-19, 02-16, 05-25, 06-19, 07-03, 09-07), all of which `backtest.run.prepare()` already removes through its engine-level thin-session filter. The flag is calendar knowledge (known in advance), direction-neutral, and redundant with the engine filter, so it is not an exploitable look-ahead. Not counted. |

Sanity check on 2025-01-06: ib_high / ib_low / c1029 in `day_table` equal max(high) / min(low) / last close of the 09:30-10:29 bars exactly.
Exit reasons MAIN: stop 62, flat 23, trail 14; last exit 15:55 ET (no overnight holds).

**lookahead_found = false.**

## 2. Fixed params re-run (`python3 -m backtest.run --strategy tm_trendday --contract MES --params <final.json params>`)

| period | trades | net $ | PF | win | avg trade | Sharpe | maxDD intra | largest day | largest_day_share | pos months |
|---|---|---|---|---|---|---|---|---|---|---|
| MAIN 2025-01-01..2026-09-30 | 99 | -46.7 | **0.985** | 0.364 | -0.47 | -0.04 | -722 | +303.8 | n/a (net < 0); 9.9% of gross profit ($3,065) | 11/21 |
| PRIOR 2023-01-01..2024-12-31 | 90 | +19.3 | **1.010** | 0.322 | +0.21 | 0.02 | -570 | +278.6 | 14.4 (= 1440% of a +$19 net) | 6/24 |

Matches final.json / README exactly (reproducible).

## 3. Plateau (MAIN, one grid step up/down per numeric GRID parameter; everything else fixed)

GRID numeric parameters: `min_score` [1, 2] (fixed 2) and `trail_atr` [0.25, 0.4] (fixed 0.3, between the grid values).

| neighbour | trades | net $ | PF | PF >= 1.05 |
|---|---|---|---|---|
| min_score 1 (down) | 214 | +618.7 | 1.089 | yes |
| min_score 3 (up, extrapolated one step) | 17 | +438.5 | 2.473 | yes (17 trades only) |
| trail_atr 0.25 (down) | 99 | -226.4 | 0.925 | no |
| trail_atr 0.40 (up) | 99 | +409.0 | 1.130 | yes |
| (categorical, for information) stop_mode ib_opp | 121 | +1411.3 | 1.284 | yes |
| (categorical, for information) entry_mode ib_break_stop | 88 | -252.8 | 0.933 | no |

**plateau_frac = 3/4 = 0.75** (numeric neighbours; 4/6 = 0.67 including the categorical ones). Caveat: the fixed point itself (PF 0.985) is the
local trough, so this is not a plateau around a working centre; the neighbours "pass" because the centre is below water. The min_score 3 neighbour
has 17 trades and is noise.

## 4. History (fixed params)

| period | trades | net $ | PF | Sharpe | maxDD intra |
|---|---|---|---|---|---|
| 2015-01-01..2022-12-31 | 447 | +376.0 | **1.050** | 0.11 | -1134 |
| 2015-2022 ex-2020 (from the same run's trades) | 382 | +557.3 | **1.099** | | |
| 2020-01-01..2020-12-31 (separate run) | 66 | -192.6 | **0.895** | -0.31 | -639 |

By year (2015-2022 run): 2015 PF 0.39 (-444), 2016 1.58 (+282), 2017 1.47 (+128), 2018 0.61 (-335), 2019 0.89 (-98), 2020 0.90 (-181),
2021 0.93 (-68), 2022 1.74 (+1091). Only 3 of 8 years positive; the whole 2015-2022 net is 2022 (+$1,091 against +$376 total). The
">= 1.0 ex-2020" bar is met numerically but the edge is one year.

## 5. Slippage (MAIN, `--slip 2`)

| run | trades | net $ | PF |
|---|---|---|---|
| MAIN, 1 tick (base) | 99 | -46.7 | 0.985 |
| MAIN, 2 ticks | 99 | -294.2 | **0.910** |
| (information) ib_opp variant, 1 tick / 2 ticks | 121 / 121 | +1411.3 / +1112.6 | 1.284 / 1.218 |

One extra tick per side costs $2.50 per trade on an average trade of -$0.47: the fixed rule has no cushion against costs.

## 6. Thin-session / concentration (MAIN trades table)

- Net -$46.7, gross profit $3,064.7, gross loss $3,111.5. The 10 best days sum to +$1,766 = 57.6% of gross profit; net excluding the 10 best
  days = -$1,813. "Share of net" is undefined because net is negative.
- Monthly: best 2025-10 +$323.7, worst 2026-03 -$368.1, 11/21 months positive. With a negative net, any positive month is > 40% of |net|; the
  "no single month > 40%" rule cannot be satisfied in a meaningful way.
- Largest single day +$303.8 (9.9% of gross profit); no single-day dependence, the problem is the absence of edge, not concentration.

## Verdict

| criterion | value | pass |
|---|---|---|
| no look-ahead | none found (early_close flag = calendar, redundant with engine filter) | yes |
| walk-forward OOS 2025 PF >= 1.1 (walkforward.json) | 1.149 (186 trades, Sharpe 0.57) | yes |
| plateau_frac >= 0.5 | 0.75 (centre is the trough) | yes |
| history 2015-2022 PF >= 1.0 ex-2020 | 1.099 (all 1.050; 2020 0.895) | yes |
| slippage-2 MAIN PF >= 1.0 | **0.910** (net -$294) | **no** |

**verdict: dead.** One criterion is missed, and not narrowly: PF 0.91 at 2-tick slippage is 9% under the bar, and the fixed rule is already below
water at base costs (MAIN PF 0.985, PRIOR 1.010, avg trade -$0.47 vs ~$3.80 of costs). The criteria that pass do so on weak ground: the walk-forward
OOS stream (PF 1.149) uses `stop_mode = ib_opp` in all 15 windows, a value the fixed params never take; the plateau passes only because the fixed
point is the local minimum; the 2015-2022 edge is a single year (2022). The published composite trend-day rule with the IB-midpoint stop has no
tradable edge on MES at micro costs.

What would need a separate, honest study (not done here, numbers for information only): the `ib_opp` stop variant - MAIN PF 1.284 (121 trades,
+$1,411), PF 1.218 at 2-tick slippage, README reports PRIOR PF 1.1-1.4 for it and the walk-forward chose it in every window. That is a different
rule from the published default and would need its own plateau / history / Lucid verification before it could be called a survivor.

Files: runs and trade tables in the session scratchpad (`tm/<tag>_trades.csv`, `<tag>_daily.csv`, `<tag>_metrics.json` for main, prior,
main_slip2, ms1, ms3, tr025, tr040, ibopp, ibbreak, ibopp_slip2, hist, y2020).
