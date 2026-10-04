# tm_gapgo - Gap-and-go: large opening gap outside the prior range, first-range breakout (family trend_momentum)

Module: `strategies/tm_gapgo.py`. Research: `research/families/trend_momentum.md`; spec `research/specs/trend_momentum.md` 6.
Periods: MAIN = 2025-01-01..2026-09-30, PRIOR = 2023-01-01..2024-12-31. All numbers per ONE micro contract, after costs
(engine: $1.30 RT commission + 1 tick slippage per side on stop fills). Instruments: MNQ (primary), MES. Not run on MGC
(a 08:20 pit "gap" after 19h of trading is not the same object).

## Rules as implemented (all times ET)
- Daily features, every one from sessions < d: `prev_close` = prior RTH close (last 1-min close with tod < 16:00, never the
  16:14 print), `pd_high / pd_low` = prior RTH high/low, `atr` = Wilder ATR(14) of RTH daily bars shifted one day
  (`daily_atr`), `O930` = open of the 09:30 bar. Skip the day if any is NaN or the session is an early close (`session_info`).
- Gap qualification: `gap = O930 - prev_close`. up_day = `gap >= gap_atr*atr` and (`outside_prior_range` off or `O930 > pd_high`);
  dn_day = `gap <= -gap_atr*atr` and (`outside_prior_range` off or `O930 < pd_low`) and `direction == 'both'`. No trade otherwise.
- First range FR = `opening_range('09:30', range_minutes)`; skip if fewer than `range_minutes` bars or zero width. `i0 = i_end + 1`.
- Entry: one resting stop order at `i0` on the gap side only: buy stop at `fr_high + 1 tick` / sell stop at `fr_low - 1 tick`,
  live for `min(valid_minutes, bars until last_entry)` bars (dies at 10:30). Fill = max(open, level) + 1 tick slippage.
- Stop: `range_low` = far side of FR +/- 1 tick; `gap_mid` = (O930 + prev_close)/2. Skip if the distance <= 2 ticks. If the
  distance > `max_stop_atr*atr`, a `stop_pts = max_stop_atr*atr` from the fill replaces the price stop.
- Target: `level + side*tgt_mult*(fr_high - fr_low)`; with `trail_atr > 0` no target, trail_pts = trail_act_pts = `trail_atr*atr`.
- Exits: stop, target (or trail), forced flat at 15:55. One trade per day, no re-entry, no reversal. `daily_loss_stop` = $80 MNQ
  / $60 MES (one full stop ends the day), `daily_profit_stop` off. Session: entries in [09:30 + range_minutes, 10:30).
- Look-ahead: all daily levels are shifted; O930 is the open print; FR is used only after `i_end`; the order goes live at `i0 > i_end`.
  Verified by hand on 2025-01-15 (fill 21149.39 + 0.25 + 0.25 = 21149.889; target = level + 1.0 x 119.58 = 21269.22) and
  2025-02-03 (short: stop at fr_high + tick + slip).

Defaults (`PARAMS`, the published rule): gap_atr 0.7, outside_prior_range True, range_minutes 15, direction both, stop_mode
range_low, max_stop_atr 0.5, tgt_mult 1.0, trail_atr 0, last_entry 10:30, valid_minutes 60, flat 15:55, max_trades 1,
dls_block {MES 60, MNQ 80}. GRID (16 combos): gap_atr {0.5, 0.7} x range_minutes {5, 15} x stop_mode {range_low, gap_mid} x
direction {both, long_only}. Extra single run: trail_atr 0.3.

## Headline results (fixed defaults, per micro, after costs)

| contract | period | trades | net $ | win | PF | Sharpe | maxDD intra | pos months |
|---|---|---|---|---|---|---|---|---|
| MNQ | MAIN | 27 | -680 | 48% | 0.81 | -0.38 | -2,514 | 4/14 traded |
| MNQ | PRIOR | 23 | +554 | 61% | 1.41 | 0.53 | -580 | 10/17 traded (one day = 45% of net) |
| MES | MAIN | 26 | -1,563 | 31% | 0.38 | -1.57 | -2,245 | 4/21 |
| MES | PRIOR | 24 | +36 | 50% | 1.05 | 0.07 | -589 | 7/24 |

Trade frequency: 55 of 446 MAIN sessions qualify (12%, as expected from the base rates), but only 27 (6%) fill: on half of the
qualified days price never breaks the first-15-min range in the gap direction before 10:30.

## Walk-forward (the honest yardstick; `walkforward.json`, `wf_oos_2025_daily.csv`)
`final_select --wf_start 2022-01-01 --max_combos 16`, IS 12 months / OOS 3 months, metric Sharpe, grid = module GRID.
- Caveat: at ~1 trade/month the IS windows had fewer than 30 trades until mid-2024, so no parameters could be selected and the
  OOS stream only starts 2024-07 (9 folds). Every fold picked gap_atr 0.5 / 5-min range / both (stop_mode flips once).
- OOS 2025-01..2026-09: **68 trades, net -1,322, PF 0.81, Sharpe -0.56**, 53% win, 8/21 positive months, maxDD -2,419.
  Quarterly OOS nets: -329, +256, +244, +427, -1,161, +124, -884.
- Full OOS 2024-07..2026-09: 84 trades, net -798, PF 0.90.
- Lucid 50K Flex on the OOS stream: best 5 micros, pass rate 0.21 = zero-edge control 0.21, pass-within-21 0.01, P(first payout)
  0.00, expected net per evaluation -146 = lower bound = zero-edge control -> `recommended` False.

## Grid (`grid_MNQ.csv`, `grid_MES.csv`; 16 combos x 2 periods each)
- MNQ MAIN: every `direction=both` cell is negative (PF 0.68-0.88, 27-68 trades). `long_only` cells are PF 1.01-1.09 on MAIN
  (16-38 trades, net +31..+318) but the gap_atr 0.5 long_only cells are PF 0.75-0.82 on PRIOR; best MAIN cell (0.5 / 5-min /
  gap_mid / long_only, PF 1.09) is PF 0.83 on PRIOR. PRIOR: 14/16 cells profitable (median PF 1.41) - on a 23-52 trade sample
  with a single day worth up to 70% of a cell's net. Rank correlation of the 16 cells between periods: -0.22 -> no plateau.
- MES: 0/16 cells profitable on MAIN (PF 0.29-0.99), 5/16 on PRIOR (median PF 0.95). Dead.
- trail_atr 0.3 (MNQ): MAIN PF 0.97 (27 trades, net -80), PRIOR PF 1.37. Trailing removes the target hits that pay for the
  stops; it does not change the sign.

## Diagnostics (MNQ, defaults, MAIN; `backtest.report` + scratch script)
- Exit mix: 14 stops at -259 avg, 9 targets at +256 avg, 4 flat-at-15:55 at +159 avg. A 1:1 payoff needs > 50% win; realised 48%.
  Hit rate by stop_mode: range_low 48% (MAIN) / 61% (PRIOR); gap_mid 52% / 70% (gap_mid stops are tighter and lose more per
  stop; its MAIN PF is 0.68).
- Gap size: 0.7-1.2 ATR 24 trades net -749 (46% win); > 1.2 ATR 3 trades +69. With gap_atr 0.5 the 0.5-0.7 bucket adds 25
  trades at -676 (48% win). The TradingStats fill-rate base rates (large gaps rarely fill) do not translate into
  continuation after the first range.
- Sides: longs 16 trades +47 (56% win); shorts 11 trades -727 (36% win). Fills before 10:00 (21) -1,382; after 10:00 (6) +702.
- VIX (lag 1): 15-20 14 trades -52; 20-25 6 trades -612; 25-35 4 trades -523; the single > 35 trade +476 (2025-04-04).
- MAE/MFE: median MAE -96 pts vs median MFE 81 pts; winners' median MAE -39, losers' median MFE 61 (losers travel half a range
  in favour, then reverse). Max 8 consecutive losing trades; worst day -386 (2025-04-23).
- Benchmark (gap-side buy at the 09:45 open, hold to the 15:55 open, no costs): on the 27 traded days +728 (56% win), on all
  55 qualified days -4,855 (45% win). In 2025-26 big outside-range gaps mean-revert intraday (the mirror image of
  `mr_gapfade` working on the same feed); the breakout filter only rescues part of that.
- Months: 4 of the 14 traded months positive; Jun-26 +538 and Apr-25 +413 vs Mar-26 -583, Nov-25 -424, Jan-26 -386.
- Data note: the NQ feed's RTH ends at 14:59 ET from Feb to Jul 2023, so `session_info` flags those ~130 sessions as early
  closes and the module skips them (per spec); the PRIOR sample is therefore ~390 sessions, not 515.

## What was tried and why it failed
1. Published rule on MNQ and MES, both periods: negative on MAIN for both instruments; PRIOR positive on MNQ only on a 23-trade
   sample dominated by one day.
2. 16-combo grid on both instruments: no cell is positive on both periods on MES; on MNQ the only MAIN-positive cells
   (long_only) are PRIOR-negative when gap_atr 0.5 and have 16 trades when gap_atr 0.7. Negative rank correlation = noise.
3. trail_atr 0.3: PF 0.97 on MAIN; no sign change.
4. Walk-forward: OOS 2025-26 PF 0.81 on 68 trades; Lucid indistinguishable from the zero-edge control.

## Verdict
**Dead.** Walk-forward OOS 2025 PF 0.81 (< 1.03) on 68 trades; fixed MAIN PF 0.81; MES dead on every cell. The day selection
(large gap outside the prior range) does identify a distinct 12% subset of days, but in 2025-26 those days fade rather than
continue, and the first-range breakout at ~6% of days is too infrequent to carry an evaluation anyway (walk-forward could not
even select parameters before mid-2024). Not usable as a stand-alone Lucid vehicle or as a portfolio leg.
