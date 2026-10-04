# orb_dbl verification (adversarial verifier, 2026-10-04)

Contract MNQ, fixed params from `final.json`: or_minutes 30, require_fail true, stop_mode mid, max_stop_atr 0.6, tgt_frac 0.5,
skip_ext 0.5, last_entry 13:30, min_range_atr 0.1, max_range_atr 0.8, flat 15:55, max_trades 1, bar 5. All numbers per micro
contract after costs (1 tick slippage per side on market/stop fills, $1.30 round trip). Walk-forward numbers are taken from
`walkforward.json` (not re-run). Run artefacts: scratchpad `v_dbl/` (`main_variants.csv`, `*_trades.csv`, `*_metrics.json`).

## 1. Look-ahead review of `strategies/orb_dbl.py` -> none found

Code reading (line by line):
- Opening range: `opening_range(df1, 09:30, 30)` over [09:30, 10:00). Candidate 5-min bars are filtered with `tod >= or_end`
  (first candidate bar 10:00-10:05, closes 10:05), so the OR is complete before any state transition uses it.
- ATR: `daily_atr(df1, 14, rth_only=True)` = Wilder ATR(14) of daily RTH bars `.shift(1)`; day d uses days < d. Confirmed
  numerically (value at day d equals the ATR computed through d-1 and differs from the same-day ATR).
- State machine runs on *closed* 5-min bars (`resample` closes/highs/lows); the signal bar's close is `est`, the order is placed
  at `i_next` = `i_last + 1` of the signal bar (market at the open of that 1-min bar). Nothing from bar `i_next` or later is used.
  `E` (failed extreme) is the running high/low from the first-break bar through the failure bar inclusive (with require_fail
  False it includes the signal bar itself, which is already closed). Confirmed: `k_first_break < k_fail < k_signal` on all rows,
  `tod(i_next) - tod_signal == 5` on all 72 signal rows, `entry_ts == ts[i_next]` and `fill == open[i_next] + tick*side` on all
  71 engine trades, OR high/low == 1-min window extremes, `E` == extreme over the [first_break, fail] bars.
- Stop/target: `stop_px` is a fixed price (OR midpoint / E); the cap `max_stop_atr*ATR` is compared with `est` and applied as
  `stop_pts` from the actual fill; `tgt_pts` from the fill. Entry window [10:00, 13:35), flat 15:55: entries observed 10:15-13:30,
  last exit 15:55. No VIX, SMA or prior-day level features. No date- or regime-dependent parameters in the module.
- Engine-level note (not strategy-specific): `backtest.run.prepare` skips sessions with < 80% of the typical RTH bar count using
  the session's own bar count (a holiday/early-close calendar, known in advance in live trading). Applies to every strategy.
- Parameter provenance: `last_entry 13:30` is not in the GRID and was chosen (per the README) from MAIN diagnostics; `stop_mode
  mid` / `tgt_frac 0.5` were selected on the MAIN+PRIOR grid. These are in-sample choices, not look-ahead in the engine sense,
  but they mean the fixed-param MAIN/PRIOR numbers are partly selected (see section 7).

## 2. Fixed-param re-runs (match final.json exactly)

| period | trades | net $ | PF | Sharpe | DD intraday | largest_day_share | pos months |
|---|---|---|---|---|---|---|---|
| MAIN 2025-01-01..2026-09-30 | 71 | +2,620.8 | **1.674** | 1.40 | -728 | 0.146 | 11/21 |
| PRIOR 2023-01-01..2024-12-31 | 72 | +376.7 | **1.127** | 0.32 | -816 | 0.560 | 9/24 |

PRIOR by year: 2023 26 trades, -161, PF 0.9; 2024 46 trades, +538, PF 1.3.

## 3. Plateau (MAIN, one grid step up/down per numeric GRID parameter, everything else fixed)

Numeric GRID parameters: `or_minutes` [15, 30] and `tgt_frac` [0.5, 0.75, 1.0]. The fixed values (30, 0.5) sit on a grid edge, so
the missing neighbour was extrapolated one step (45 min, 0.25).

| variant | trades | net $ | PF | Sharpe | DD | >= 1.05 |
|---|---|---|---|---|---|---|
| or_minutes 15 (grid) | 117 | 2,176 | 1.365 | 1.13 | -1,069 | yes |
| or_minutes 45 (extrapolated) | 43 | 3,468 | 2.945 | 2.13 | -528 | yes |
| tgt_frac 0.75 (grid) | 71 | 3,026 | 1.655 | 1.37 | -819 | yes |
| tgt_frac 0.25 (extrapolated) | 71 | 1,724 | 1.746 | 1.34 | -696 | yes |

**plateau_frac = 4/4 = 1.00** (2/2 counting only in-grid neighbours). Categorical GRID neighbours: stop_mode extreme PF 1.47
(DD -1,251), require_fail False PF 1.674 (identical trades). Non-GRID numeric parameters (informational): max_stop_atr 0.45/0.75
PF 1.69/1.67; skip_ext 0.35/0.75 1.63/1.67; max_range_atr 0.6/1.0 1.90/1.67; min_range_atr 0.05/0.2 1.67/1.63; last_entry 12:30/14:30
1.79/1.88. Every neighbour on MAIN is above 1.3: MAIN is a broad plateau. (The README shows the same plateau does not exist on PRIOR:
all 24 primary-grid combos lose on 2023-24 and only last_entry 13:30 lifts PRIOR above 1.0.)

## 4. History

| period | trades | net $ | PF |
|---|---|---|---|
| 2015-01-01..2022-12-31 (one run) | 336 | +735 | 1.081 |
| same, ex-2020 (trades of 2020 removed) | 292 | +719 | **1.103** |
| 2020-01-01..2020-12-31 (separate run) | 44 | +16 | **1.008** |

By year: 2015 PF 0.7 (-197), 2016 0.7 (-137), 2017 0.9 (-53), 2018 1.4 (+406), 2019 0.7 (-199), 2020 1.0 (+16), 2021 1.3 (+440),
2022 1.2 (+458). Four of seven ex-2020 years lose; 2015-2019 cumulative is -$179 on 212 trades (PF ~0.9). The history criterion is
met only because of 2021-2022 (both high-volatility years, consistent with the README's VIX > 20 dependence).

## 5. Slippage: MAIN with `--slip 2`

71 trades, net +2,592.8, **PF 1.663**, Sharpe 1.38, DD -733. On MNQ one tick is $0.50, so doubling slippage costs ~$28 over the
window; this test cannot hurt an MNQ strategy with a $37 average trade (break-even would need ~50 ticks of slippage).

## 6. Thin-session dependence (MAIN trades table)

- Net +2,620.8 on 71 trading days. The 10 best days sum to +2,439 = **93.1% of net**; ex-top-10 net is +182 with PF 1.047 on 61
  trades. Top 5 days = 55.7%; largest day (2026-06-10, +383) = 14.6%.
- Best month 2026-06 +907 = 34.6% of net; **no month > 40%**. 11 of 20 active months positive. 2025 +1,858 (43 trades), 2026 +762 (28).
- Exits: 43 targets (+146 avg), 20 stops (-184 avg), 8 flats (~0). With avg win $138 vs avg loss $162, a 93% top-10-day share on 71
  trades is high but not pathological (10 days = 14% of trades, each roughly 1.5 average wins); it does say the remaining 61 trades
  are break-even.

## 7. Criteria and verdict

| criterion | value | threshold | result |
|---|---|---|---|
| look-ahead | none found | none | pass |
| walk-forward OOS 2025 PF (`walkforward.json` wf_2025) | 1.464 (75 trades, +2,282) | >= 1.1 | pass |
| plateau_frac | 1.00 | >= 0.5 | pass |
| history 2015-2022 PF ex-2020 | 1.103 | >= 1.0 | pass (narrow) |
| slippage-2 MAIN PF | 1.663 | >= 1.0 | pass |

All five criteria pass -> **verdict: survivor** (formal rule). Honest reading of the caveats, which the rule does not score:
1. The WF OOS 2025 stream is only partly out-of-sample: the WF re-selected the fixed combo for 5 of 7 quarters, and `last_entry 13:30`
   (chosen from MAIN diagnostics, outside the GRID) is inside every WF window. The two quarters with a different selection net -$192.
2. PRIOR 1.13 is a selected number: 12:30 and 14:30 give PRIOR 0.99 / 0.96 (README) while every MAIN cutoff is >= 1.55. PRIOR and
   the 2015-2019 history (PF ~0.9) say the calm-regime edge is ~0; the positive years (2018, 2021, 2022, 2025, 2026-06) are
   high-volatility years.
3. Economics: ~3.4 trades/month at $37/micro; Lucid 5-micro bootstrap LB -$146 = zero-edge control, not recommended (README/final.json).
   Survivor as a strategy with a real but regime-dependent edge; not a stand-alone evaluation vehicle.
