# orb_close30 - ORB with 5-min close confirmation, capped range target (family orb_session)

Module: `strategies/orb_close30.py`. Research: `research/families/orb_session.md` 3.2 (tradingstats conservative setup) and 3.3
(Trade-That-Swing long-only ORB-15). Periods: MAIN = 2025-01-01..2026-09-30, PRIOR = 2023-01-01..2024-12-31. All numbers are
per ONE micro contract, after costs (engine: $1.30 RT commission + 1 tick slippage per side on market/stop fills).

## Rules as implemented
- 5-min RTH bars from the 1-min feed (`resample(df1, 5, rth_only=True, rth=(rth_open, rth_close))`).
- Opening range over `[rth_open, rth_open + or_minutes)`; `rng = or_high - or_low`; ATR = Wilder ATR(14) of daily RTH bars, shifted
  one day. Skip the day if `rng < min_range_atr*ATR`, `rng > max_range_atr*ATR` or ATR NaN.
- Direction: `both` | `long` | `trend` (prior cash-index daily close vs its SMA(trend_len); SPX for MES, NDX for MNQ, GC for MGC; the
  row strictly before the session; NaN = no trade). Optional `or_dir_filter` (OR candle must point the trade's way).
- Signal: from the first 5-min bar at/after the OR end whose start is before `last_entry`, the first bar whose CLOSE is above or_high
  (long) / below or_low (short). Only the first break of the day counts; a break in a disallowed direction = no trade that day.
  Skip if the signal close is already more than the target distance beyond the broken level.
- Entry: market at the open of the next 1-min bar (+1 tick). Stop: far side of the OR (`opposite`) or OR midpoint (`mid`), the
  distance capped at `max_stop_atr*ATR` from the fill. Target = fill +/- `tgt_frac*rng`. No trailing, no re-entry, 1 trade/day.
- Exits: stop, target, or flat at `flat` (15:55 MES/MNQ, 13:25 MGC). Session: entries in [OR end, last_entry + 5 min) so the bar
  that starts at 10:25 can fill at 10:30; gold OR anchored at 08:20 with last_entry 09:30.

Defaults (`PARAMS`, kept at the published rule): or_minutes 30, direction both, trend_len 200, or_dir_filter False, last_entry 10:30,
stop_mode opposite, max_stop_atr 0.6, tgt_frac 0.5, min_range_atr 0.1, max_range_atr 0.8, flat 15:55, max_trades 1.

## Headline results (per micro, after costs)

Default rule (ORB-30, both directions, far stop, 0.5x target):

| contract | period | trades | net $ | win | PF | Sharpe | maxDD intra | pos days |
|---|---|---|---|---|---|---|---|---|
| MES | MAIN | 301 | -1,760 | 64% | 0.87 | -0.75 | -2,799 | 64% |
| MES | PRIOR | 272 | -546 | 67% | 0.93 | -0.37 | -1,424 | 67% |
| MNQ | MAIN | 271 | -24 | 67% | 1.00 | -0.01 | -3,898 | 67% |
| MNQ | PRIOR | 276 | +1,906 | 69% | 1.13 | 0.60 | -1,911 | 69% |
| MGC | MAIN | 279 | -3,202 | 65% | 0.80 | -1.06 | -4,029 | 65% |
| MGC | PRIOR | 247 | +604 | 73% | 1.12 | 0.50 | -835 | 73% |

Best configuration found (MNQ; ORB-15, direction trend, far stop capped 0.6 ATR, OR width 0.1-0.5 ATR, 0.75x target):

| period | trades | net $ | win | avg trade | PF | Sharpe | maxDD intra | pos days | pos months | worst day | largest day share |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MAIN | 190 | +6,065 | 69.5% | +31.9 | 1.43 | 1.64 | -1,371 | 69.5% | 15/21 | -512 | 6.5% |
| PRIOR | 181 | +819 | 62.4% | +4.5 | 1.08 | 0.32 | -1,686 | 62.4% | 12/24 | -296 | 37% |

Lucid 50K Flex Monte Carlo (MAIN daily P&L, constant micros): best 5 micros -> pass rate 0.47, P(first payout | pass) 0.42,
P(first payout) unconditional 0.20, expected net +$711 per evaluation, median 17 trading days to pass. 10 micros: pass 0.26,
exp net +$330; 15+: ~0. The avg trade is ~10x costs, but single stops of up to ~$500/micro cap sizing at 5 micros under the $2k MLL.

## Diagnostics (MNQ, best config, MAIN)
- Exit mix: 119 targets (+$159 avg), 51 stops (-$255 avg), 18 flat-at-15:55 (+$10 avg, 67% win), 2 early-session ends. Break-even win
  rate for the 1:1.6 payoff is 62%; realised 69.5%. P&L is a thin surplus of many small target hits over fewer, 1.6x larger stops.
- Sides: 166 longs +$4,252 (68% win), 24 shorts (only when NDX < SMA200: Mar-May 2025) +$1,814 (79% win). With direction=both the
  shorts lose ~$1,400 on MAIN and more on PRIOR, exactly as Mesfin 2026 reports.
- Weekday: Mon +$1,987, Wed +$2,251, Thu +$882, Fri +$1,118, Tue -$173. No day-of-week filter applied (vendor DOW filters are in-sample).
- VIX (lag 1): <15 +$1,017 (84% win), 15-20 +$3,626, 20-25 -$222 (61% win), 25-35 +$1,002, >35 +$642 (n=2). The 20-25 bucket is
  the only losing regime; no filter applied (28 trades).
- Months: 15/21 positive; losers Jul-25 (-97), Nov-25 (-366), Dec-25 (-316), Feb-26 (-37), Mar-26 (-68), Jul-26 (-544). Best Jun-26
  +1,084, Feb-25 +1,036. No month > 18% of net. Max 3 consecutive losing days/trades.
- MAE/MFE: winners' median MAE 30 pts (stop 60-200 pts away): the far stop is rarely threatened by winners; losers' median MFE 25 pts
  (target 40-150): a 0.25x target would catch them, but that cell is negative on PRIOR (see pass 2).
- Days with a trade: 190 of 448 sessions (42%); the 0.1-0.5 ATR range filter plus trend filter skip the rest.

## Attempts log
1. Default rule, all instruments (both directions, OR-30, 0.5x): MNQ break-even (PF 1.00 MAIN / 1.13 PRIOR); MES PF 0.87/0.93; MGC
   PF 0.80/1.12. Diagnosis: 172 targets at +$143 vs 67 stops at -$333 on MNQ = break-even at 70% win; shorts negative.
2. Grid 1 (24 combos: or_minutes 15/30 x direction both/long/trend x stop opposite/mid x tgt 0.5/0.75), MNQ and MES, both periods
   (`grid_main_MNQ.csv`, `grid_main_MES.csv`):
   - MNQ: every `both` cell is <= break-even on MAIN. All 8 long/trend + opposite-stop cells are positive on BOTH periods (MAIN PF
     1.06-1.34, PRIOR 1.06-1.21) -> plateau. `mid` stop lowers the win rate to ~50-60% and is not better. OR-15 beats OR-30 on MAIN,
     OR-30 beats OR-15 on PRIOR; 0.75x >= 0.5x in most cells.
   - MES: only or15/trend/opposite is positive on MAIN (PF 1.16-1.19) and it is negative on PRIOR (0.77-0.90); all OR-30 cells
     negative on MAIN. The 0.5-0.75x range target in ES points is too small against fixed costs. MES = dead.
3. Grid 2 (plateau base or15/opposite; direction long/trend x or_dir_filter x last_entry 10:30/11:00 x tgt 0.25/0.5/0.75; 24
   combos, both periods; `grid_pass2_MNQ.csv`): `or_dir_filter=True` hurts on both periods (fewer trades, lower net) -> dropped.
   `last_entry 11:00` adds ~5% net on both periods -> not adopted (within noise, default kept). `tgt 0.25` is positive on MAIN
   (85% win) but negative on PRIOR -> confirmed as the negative control.
4. MGC grid (or 15/30 x long/trend x 0.5/0.75; `grid_MGC.csv`): all 8 cells PF 0.68-0.84 on MAIN even in the 2025 gold bull run;
   PRIOR ~1.0. MGC = dead for this rule.
5. Grid 3 (or15/trend-or-long/opposite/0.75; max_stop_atr 0.3/0.45/0.6 x max_range_atr 0.5/0.8; 12 combos, both periods;
   `grid_pass3_MNQ.csv`). Reason: the Lucid pass rate was ~25% because a far-side stop on a 0.8-ATR range is a $400-600 loss per
   micro. All 12 cells positive on both periods (MAIN PF 1.18-1.43, PRIOR 1.06-1.22). `max_range_atr 0.5` lifts trend from PF 1.34
   to 1.43 on MAIN and 1.056 to 1.078 on PRIOR, and the Lucid pass rate from 0.25 to 0.47. `max_stop_atr 0.3` is the most robust
   on PRIOR (PF 1.14-1.22) at slightly lower MAIN (1.31-1.38): an equally defensible choice. Chosen: trend / 0.6 / 0.5.

Not tried (would be new rules, not parameter choices): day-of-week or VIX filters, partial exits, time stop at noon, re-entry.

## Verdict: marginal
MNQ, ORB-15 close-confirmed with a daily SMA200 trend filter, far-side stop and 0.75x-range target is a real but thin edge:
PF 1.43 / 190 trades / Sharpe 1.64 / 69.5% positive days on MAIN, PF 1.08 on PRIOR with the same parameters, a 12-cell plateau.
It does not reach the guide's "good" bar (PF >= 1.3 with >= 150 trades: yes; Sharpe >= 1.5: yes; PRIOR PF >= 1.1: no, 1.08). For
Lucid: 5 micros, 47% pass rate, 20% unconditional first-payout probability, +$711 expected net per evaluation, 17 days median to
pass. The constraint is the loss size per trade (far-side stop), not the hit rate; the 50% consistency rule is comfortably met
(largest day 6.5% of net). Shorts (direction=both), MES and MGC are dead. Useful as a low-correlation portfolio leg (one trade at
~10:05-10:30, flat by target/stop usually within an hour) rather than a stand-alone account strategy.

Files: `final.json`, `final_MNQ_{main,prior}_{trades,daily}.csv`, `grid_main_MNQ.csv`, `grid_main_MES.csv`, `grid_pass2_MNQ.csv`,
`grid_pass3_MNQ.csv`, `grid_MGC.csv` (+ `.log` batch printouts).

## Walk-forward assessment (2026-10-03, honest yardstick)
`python3 -m backtest.final_select --ids orb_close30 --jobs 2 --wf_start 2022-01-01 --max_combos 16` -> `walkforward.json`, `wf_oos_2025_daily.csv`.
Parameters re-selected every quarter on the trailing 12 months from GRID (or_minutes 15/30 x direction both/long/trend x stop
opposite/mid x tgt 0.5/0.75) with the final.json params as base; tested on the next 3 months. No module change in this round.

| stream | trades | net $ | win | PF | Sharpe | maxDD intra | pos months |
|---|---|---|---|---|---|---|---|
| WF OOS 2025-01..2026-09 (`wf_2025`) | 140 | +3,870 | 71% | 1.45 | 1.42 | -1,076 | 15/21 |
| WF OOS 2023-01..2026-09 (`wf_all`) | 353 | +5,555 | 67% | 1.28 | 1.01 | -1,260 | 26/45 |
| fixed params MAIN (in-sample) | 142 | +6,217 | 73% | 1.72 | 2.12 | -1,212 | 13/21 |
| fixed params PRIOR | 117 | +1,301 | 64% | 1.22 | 0.69 | -984 | 10/24 |

Lucid 50K Flex on the OOS 2025 stream (`lucid_wf_2025`, bootstrap lower-bound sizing): 5 micros, pass rate 0.50, pass-within-21
0.13, median 43.5 days to pass, P(first payout) 0.20 unconditional, expected net +$445/eval, **exp_net_lb -146 = zero-edge control
-146 -> not recommended** at any size (10 micros: exp net +617, lb -146).

Diagnosis:
- The OOS edge is real but roughly 40% thinner than the in-sample story (PF 1.45 vs 1.72, net 3,870 vs 6,217). Since 2025 the WF
  settles on or15/trend/opposite with tgt alternating 0.5/0.75; before 2025 the chosen cell flips (OR30/both, mid stop), i.e. the
  selected parameters are not a stable optimum over the whole history.
- Concentration: 82% of OOS net comes from Jan-Jun 2026 (Jun-26 +1,084 = 28%); calendar 2025 OOS is +1,342 on 84 trades. The last
  three OOS quarters are PF 1.07 / 1.03 / 0.64 (2026Q3 -662). The 2023-2024 OOS folds total +1,684 but 5/8 are negative and the
  sum is -694 without the single 2024Q3 fold (+2,378).
- Partial contamination: `trend_fast=50`, `max_range_atr=0.5`, `max_stop_atr=0.6` were chosen on MAIN and are not in GRID, so the
  walk-forward only re-selects four parameters; the OOS numbers are optimistic to that extent.
- Structure: far-side OR stop gives avg loss -$214 vs avg win +$124 (break-even win rate 63%, realised 71%); 0.31 trades/day and
  +$28 avg trade are too slow for a 21-session pass, which is what kills the Lucid lower bound.

Gate: wf_2025 PF 1.45 >= 1.03 with 140 trades (and fixed MAIN 1.72 / PRIOR 1.22 with >= 60 trades) -> proceed = true. Verdict
stays `survivor`: a thin, slow portfolio leg; not a stand-alone evaluation strategy.
