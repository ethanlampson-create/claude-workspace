# vb_idtarget - inside-day range target (open vs prior-day midpoint, target the prior extreme, stop at the midpoint)

Family: volatility_breakout (research `research/families/volatility_breakout.md` 2.4-2.5; spec
`research/specs/volatility_breakout.md` section 3; edgeful 2025 / Connors-Raschke inside-day setup).
Module: `strategies/vb_idtarget.py`. Verdict: **dead** (see the walk-forward section and the honest verdict).

## Rules as implemented (all times ET)
- Daily bars `D` = one RTH bar per session (`daily_bars(df1, rth_only=True, rth=(contract.rth_open, contract.rth_close))`:
  equities 09:30-16:00, gold pit 08:20-13:30). Every daily quantity for session d uses sessions < d only (`shift(1)`).
  ATR = `daily_atr(df1, 14)` (RTH daily bars, already shifted). Early-close / thin RTH sessions (< 90% of the nominal RTH
  minutes or last RTH bar > 30 min before the close) are skipped; `backtest.run` additionally skips thin sessions.
- Setup: PDH/PDL = high/low of d-1, `rng` = PDH-PDL, `mid` = (PDH+PDL)/2. ID = d-1 was an inside day of d-2.
  NR4 = rng[d-1] <= min(rng[d-4..d-1]). `setup` in {id, nr4_or_id, id_nr4, any}.
- Open: `O` = open of the first RTH 1-min bar (09:30 / 08:20); order bar `i1` = the next bar (09:31 / 08:21). Nothing after
  the open print is used for qualification. `side` = +1 if O > mid, -1 if O < mid, 0 = skip. `level` = PDH (long) / PDL
  (short); `dist` = |level - O|.
- Tradeable: setup_ok, side != 0, (require_inside_open: PDL < O < PDH), `min_dist_atr*ATR <= dist <= max_dist_atr*ATR`,
  ATR / rng not NaN, not early close, and (sanity check I added) the level lies ahead of the open in the trade direction.
  Without the last condition an open outside the prior range trades toward a level BEHIND the fill, which is what the
  spec's `require_inside_open=False` extra run produced (-$5.7k MNQ / -$7.2k MGC on MAIN: the target is already passed at
  the fill). With the check in place `require_inside_open=False` admits no additional days.
- Entry `market_0931`: market at the open of bar i1 (+1 tick). Entry `close_above_open`: first 1-min bar k >= i1 with
  tod < last_entry whose close is beyond O in the trade direction, inside the prior range and still >= min_dist_atr*ATR from
  the level -> market at the open of bar k+1 (same session only).
- Stop: `mid` -> R = |ref - mid| (ref = O or the signal close); `frac` -> R = stop_frac*rng. R = min(R, max_stop_atr*ATR),
  R = max(R, min_stop_pts) (MES 4 / MNQ 6 / MGC 2 pts). Passed as `stop_pts` (applied from the actual fill).
- Target: absolute `level + side*tgt_ext*rng` (needs a 1-tick trade-through in the engine).
- Time stop (`time_stop` != none): exit at the open of the first bar >= time_stop (`13:00` on equities maps to `11:30` on
  gold). Forced flat at `flat` (15:55 equities, 13:25 gold). One trade per day; no daily loss/profit stop.

PARAMS (published): setup id, entry market_0931, stop_mode mid, stop_frac 0.5, tgt_ext 0.0, require_inside_open True,
min_dist_atr 0.08, max_dist_atr 0.6, max_stop_atr 0.4, last_entry 10:30 (MGC 09:30), time_stop none, flat 15:55 (MGC 13:25).
GRID (16): setup {id, nr4_or_id} x stop_mode {mid, frac} x tgt_ext {0.0, 0.25} x time_stop {none, 13:00}.

## Mandatory diagnostic: hit rate of `level` (files `hit_rate_diag.txt`, `funnel.txt`)
Share of qualifying sessions on which the prior extreme was touched after the open (session high >= PDH for longs, low <= PDL
for shorts), and the share on which the prior midpoint (the published stop) was touched:

| contract | period | setup | long n / hit / mid-touch | short n / hit / mid-touch |
|---|---|---|---|---|
| MNQ | MAIN 2025-01..2026-09 | id | 6 / 1.00 / 1.00 | 4 / 0.75 / 1.00 |
| MNQ | MAIN | nr4_or_id | 29 / 0.66 / 0.86 | 16 / 0.69 / 0.81 |
| MNQ | MAIN | any | 105 / 0.65 / 0.71 | 71 / 0.65 / 0.72 |
| MNQ | PRIOR 2023-24 | id | 12 / 0.50 / 0.75 | 7 / 0.71 / 0.71 |
| MNQ | PRIOR | any | 110 / 0.59 / 0.65 | 77 / 0.58 / 0.71 |
| MES | MAIN | id | 7 / 0.86 / 0.86 | 5 / 0.80 / 0.60 |
| MES | MAIN | any | 112 / 0.65 / 0.70 | 81 / 0.59 / 0.75 |
| MGC | MAIN | id | 11 / 0.36 / 0.82 | 5 / 0.60 / 0.80 |
| MGC | MAIN | any | 79 / 0.53 / 0.72 | 85 / 0.59 / 0.73 |

The published statistic replicates on the index proxies: on MNQ 2025-26 the prior extreme is reached on ~65% of qualifying
days for both sides (published 67% / 58%); the pure inside-day cell is tiny (n = 10 on MNQ) but 90% there. So the
diagnostic passes and the module was run. The same table, however, already contains the verdict: the **midpoint is touched
more often than the extreme** on every row (71-100% vs 50-65%), i.e. the published stop sits inside the day's noise band.
Funnel (MNQ MAIN, 428 sessions): 40 inside days -> 14 whose open is inside the (narrow) prior range -> 10 with
0.08 ATR <= dist <= 0.6 ATR. The spec expects ~12% of days to trade with `setup='id'`; on our data it is 2.3%, because
after an inside day the next open gaps outside the compressed range ~65% of the time.

## Metrics (per 1 micro, after costs; `grid_*.csv`, `smoke.txt`, `extra_runs.txt`)

Published defaults (setup id, stop mid, tgt_ext 0):

| contract | period | trades | net $ | win | PF | maxDD intra | Sharpe |
|---|---|---|---|---|---|---|---|
| MNQ | MAIN | 10 | -366 | 0.30 | 0.47 | -510 | -0.60 |
| MNQ | PRIOR | 19 | -96 | 0.42 | 0.89 | -544 | -0.15 |
| MES | MAIN | 12 | -131 | 0.42 | 0.73 | -460 | -0.34 |
| MES | PRIOR | 18 | -17 | 0.44 | 0.95 | -180 | -0.06 |
| MGC | MAIN | 16 | -421 | 0.31 | 0.45 | -473 | -0.91 |
| MGC | PRIOR | 23 | -285 | 0.30 | 0.48 | -334 | -1.04 |

Grid (16 cells per contract and period): MAIN profitable cells MNQ 7/16 (median net -$309), MES 3/16 (-$197), MGC 6/16
(-$172); PRIOR profitable cells MNQ 0/16, MES 1/16 (+$31), MGC 0/16. Rank correlation MAIN vs PRIOR on MNQ: -0.42.
Best cells and the spec's extra runs on them:

| contract | config | MAIN trades / net / PF / Sharpe | PRIOR trades / net / PF / Sharpe |
|---|---|---|---|
| MGC | nr4_or_id, frac, tgt_ext 0.25 (best MAIN cell) | 35 / +882 / 1.40 / 0.65 | 47 / -545 / 0.72 / -0.72 |
| MGC | same, setup any (control) | 164 / +2394 / 1.16 / 0.56 | 190 / -434 / 0.94 / -0.25 |
| MGC | same, setup id_nr4 | 10 / -85 / 0.88 | 9 / -207 / 0.47 |
| MGC | same, entry close_above_open | 30 / +399 / 1.20 / 0.34 | 42 / -730 / 0.61 / -1.03 |
| MGC | any, stop mid, tgt_ext 0 (published stop, every day) | 164 / -255 / 0.97 | 190 / -1158 / 0.74 |
| MNQ | nr4_or_id, frac, tgt_ext 0.25 (best MNQ cell with >= 40 trades) | 45 / +606 / 1.12 / 0.24 | 53 / -974 / 0.78 / -0.57 |
| MNQ | same, setup any (control) | 176 / +2972 / 1.13 / 0.52 | 187 / -1485 / 0.91 / -0.40 |
| MNQ | same, setup id_nr4 | 5 / +326 / 1.73 | 6 / +578 / 3.91 |
| MNQ | same, entry close_above_open | 38 / +774 / 1.18 / 0.32 | 43 / -776 / 0.78 / -0.51 |
| MNQ | any, stop mid, tgt_ext 0 | 176 / -70 / 0.99 | 187 / +798 / 1.10 / 0.38 |
| MES | id, frac, tgt_ext 0 (best MES cell) | 12 / +221 / 1.33 | 18 / -200 / 0.69 |

## Diagnostics (MGC MAIN, best cell nr4_or_id / frac / 0.25; `report_MGC_bestcell.txt`)
- Exits: 17 targets avg +$177, 12 stops avg -$175, 6 time/flat exits avg -$4. A 1:1 payoff that needs > 50% hits and
  gets 51%. Median hold 87 min (IQR 49-132), so it is a mid-morning trade, not a scalp.
- Sides: shorts +$1,516 on 18 trades (67% win), longs -$634 on 17 (35%). The whole net is one side.
- Weekday: Monday +$600 and Thursday +$658 carry it; Wednesday and Friday negative. VIX 15-20 bucket (25 of 35 trades) is
  net negative; the +$888 sits in 4 trades at VIX 25-35.
- Months: 12 of 21 months have <= 2 trades; 2026-05 is -$495 (2 trades), largest-day share 35%. maxDD intraday -$755
  per micro at 35 trades.
- `any` control on MNQ MAIN (176 trades): longs +$3,739 (105), shorts -$767 (71); 65 targets avg +$350, 75 stops avg
  -$283, 36 flat exits avg +$41; 11/21 months positive, worst month -$1,499, best +$1,285 (43% of net). On PRIOR the same
  rule is -$1,485 (PF 0.91) with both sides negative or flat.

## Walk-forward (honest yardstick; `walkforward.json`, `final_select_MGC.log`, `wf_MNQ.log`, `wf_anygrid_*.log`)
`final_select --wf_start 2022-01-01 --max_combos 16` on MGC (IS 12 months / OOS 3 months, module GRID, 30-trade IS
minimum): **only one** IS window (2024-04..2025-03) ever contained a grid cell with >= 30 trades, and that cell
(nr4_or_id, mid, 0.25) was selected with a NEGATIVE in-sample Sharpe (-0.58, IS net -$178). Its single OOS quarter
(2025-04..06) made +$512 on 5 trades. Concatenated OOS 2025: 5 trades, 64 days; the Lucid scan cannot resolve a single
evaluation (62/62 starts censored), `exp_net_lb` = -$146 (fees only), `recommended` = 0. Every other quarter has no
trade because no grid cell is selectable: the inside-day setup does not generate enough trades per year to be
walk-forward tested at all.
Secondary walk-forwards (same IS/OOS scheme, `backtest.walkforward`, `wf_secondary_summary.txt`):
- MNQ, module GRID: 5 selectable quarters in 2025-26 (all `nr4_or_id`/`frac`), concatenated OOS 2025+: 36 trades, net
  +$483, day PF 1.18, Sharpe 0.32, 2 of 5 quarters positive (one quarter, 2025-07..09, is +$724 of it); whole OOS span
  2024-07..2026-03: 53 trades, net -$49, PF 0.99. Below the 40-trade bar and sign-unstable quarter to quarter.
- Control grid with `setup='any'` (the only configuration with enough trades to be selected every quarter): MGC OOS 2025+
  163 trades, net +$1,267, day PF 1.11, Sharpe 0.38, 4/7 quarters positive, but whole span 2023-2026 353 trades, net -$622,
  PF 0.97; MNQ OOS 2025+ 114 trades, net -$2,295, PF 0.81, whole span 301 trades, net -$2,840, PF 0.87. The raw
  open-vs-midpoint statistic is not tradeable out of sample on the published instrument and is a coin flip on gold.

## What I tried, what failed and why
1. Published rule (id / mid stop / prior extreme): loses on all 3 instruments in both periods (PF 0.45-0.95, 10-23
   trades). The midpoint stop is touched on 70-100% of qualifying days while the extreme is touched on 50-65%: the
   geometry is inverted relative to the thesis (stop inside the noise, target at the edge of the range).
2. `frac` stop (0.5 x rng) and `tgt_ext` 0.25 are the only cells that are positive in MAIN; they are positive because they
   turn the trade into a wider-stop, 1:1-payoff coin flip that happened to pay on gold shorts and Nasdaq longs in 2025-26.
   Every one of those cells loses on 2023-24 (0/16 MNQ, 0/16 MGC), so the plateau is a period effect, not a parameter one.
3. The `setup='any'` control shows the inside-day / NR4 conditioning adds nothing: the every-day version has the same
   PF (1.13 vs 1.12 on MNQ, 1.16 vs 1.40 on MGC with 4-5x the trades) and the same sign flip on PRIOR. The edge, where it
   exists, is "open above the prior midpoint in a trending index year reaches the prior high"; it is a 2025-26
   directional-drift artefact, not a compression effect.
4. `close_above_open` entry: slightly better average trade on MNQ MAIN (+$20 vs +$13) at fewer trades, worse on gold;
   same PRIOR failure. `id_nr4`: 5-10 trades per period, uninterpretable.
5. `require_inside_open=False`: degenerate as specified (target behind the fill); with the level-ahead sanity check it
   adds no days. Not pursued further.
6. Time stop 13:00 (11:30 gold): most trades resolve before it (identical rows in the grid), small negative where it binds.

## Honest verdict: dead
- Walk-forward OOS 2025: 5 trades (needs >= 40 with PF >= 1.03 for 'marginal'). The setup is too rare to be selectable
  in-sample and the published parameters lose outright.
- The raw statistic the spec is built on (prior extreme hit ~65% after an open on that side of the midpoint) does
  replicate, but the companion statistic the spec did not check (midpoint touched 70%+) kills the stop-at-mid design,
  and the inside-day filter removes the trades without improving them.
- Not a portfolio-leg candidate either: the only positive cells are a 2025-26-specific, one-sided, 1:1 coin flip with
  negative PRIOR and no OOS record. Nothing here to carry forward except the hit-rate tables.
