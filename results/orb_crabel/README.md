# orb_crabel — Crabel stretch ORB (open +/- SMA10 of daily noise), NR7 / inside-day setups, entry cutoff

Family: `orb_session` (research: `research/families/orb_session.md`, section 2.1, Toby Crabel 1990). Priority 3.
Module: `strategies/orb_crabel.py`. Instruments: MNQ, MES, MGC. Periods: MAIN 2025-01-01..2026-09-30,
PRIOR 2023-01-01..2024-12-31. All numbers per ONE micro contract, after engine costs ($1.30 RT + 1 tick slip per side).

## Rules as implemented
- Daily RTH bars (`daily_bars(df1, rth_only=True, rth=(rth_open, rth_close))`): equities 09:30-16:00, gold 08:20-13:30.
- noise_d = min(high_d - open_d, open_d - low_d); stretch = SMA(stretch_len=10)(noise) shifted one day (days < d only;
  NaN -> no trade). Trigger distance T = mult x stretch.
- Setup filter (`setup`): `none` (every day), `nr7` (prior day's RTH range <= min of the last 7 daily ranges),
  `nr4`, `id` (prior day high < day-before high and low > day-before low), `nr4_or_id`. All flags use days < d.
- Entry: at the first RTH bar (open price o0) a buy stop at o0 + T and a sell stop at o0 - T. OCO emulated by scanning the
  1-minute bars for the first touch (as `strategies/orb.py`); if both are touched in the same bar the side nearer that
  bar's open is taken (conservative: it is stopped on the same bar). Valid until `cutoff` (11:00 default; gold 10:30).
  One trade per day (`max_trades_day = 1`), no reversal. Fill = level + 1 tick slippage (verified by hand).
- Stop: the other trigger level, i.e. 2T from entry, capped at max_stop_atr (0.6) x ATR14 (daily RTH ATR, shifted).
  The cap almost never binds at 0.6 (2T is ~0.4 x ATR on MNQ in 2025-26).
- Target: `tgt_mode='eod'` none (Crabel original, exit at flat); `'rr'` entry +/- rr (1.5) x stop distance.
- Exits: stop, target (rr mode), forced flat 15:55 ET (MGC 13:25). Session `set_session(rth_open, cutoff, flat)`.
- Look-ahead: stretch, setup flags and ATR use prior days only; o0 is the open of the bar at which the orders go live
  (the orders are stop orders above/below that open, so the open print itself cannot fill them).
- Verified on sampled MNQ trades: module stretch == manual SMA10 of noise over the previous 10 RTH days; entry price ==
  o0 +/- T + 1 tick; stop exit == level -/+ 2T -/+ 1 tick.

Defaults (`PARAMS`, equal to the Crabel rule): stretch_len 10, mult 1.0, setup none, cutoff 11:00, max_stop_atr 0.6,
tgt_mode eod, rr 1.5, flat 15:55 (gold: cutoff 10:30, flat 13:25 unless passed explicitly).
Module `GRID`: mult [1.0, 1.5, 2.0] x setup [none, nr7, nr4_or_id] x tgt_mode [eod, rr] x cutoff [10:30, 11:30] = 36.

## Metrics per period and contract (one micro, after costs)

### Published spec (defaults: mult 1.0, setup none, cutoff 11:00, 2T stop, EOD exit)
| contract | period | trades | net | win | avg trade | PF | Sharpe | max DD intraday | pos days | largest day share |
|---|---|---|---|---|---|---|---|---|---|---|
| MNQ | MAIN | 415 | +9,967 | 46.0% | +24.0 | 1.19 | 0.95 | -5,053 | 46% | 0.40 (2025-04-09 = +3,961) |
| MNQ | PRIOR | 366 | +9,942 | 44.5% | +27.2 | 1.32 | 1.48 | -1,898 | 45% | 0.09 |
| MES | MAIN | 393 | +1,980 | 43.0% | +5.0 | 1.08 | 0.37 | -2,374 | 43% | 1.2 |
| MES | PRIOR | 341 | -529 | 42.2% | -1.6 | 0.97 | -0.17 | -2,513 | 42% | n/a |
| MGC | MAIN | 437 | +979 | 42.1% | +2.2 | 1.02 | 0.13 | -4,217 | 42% | 1.3 |
| MGC | PRIOR | 386 | -194 | 38.9% | -0.5 | 0.99 | -0.06 | -2,265 | 39% | n/a |

MNQ MAIN without the 2025-04-09 day: 414 trades, net +6,007, PF 1.11, Sharpe 0.67. Lucid (defaults, MNQ MAIN, 5 micros):
pass rate 0.16, P(first payout) 0.02, expected net -$39 per eval; PRIOR: pass 0.25, exp net +$137, lower bound -$136.
Not usable as published: the per-micro intraday DD ($5k) and worst days (-$560) already breach the $2k MLL at 5 micros.

### Best configuration (MNQ): setup none, mult 1.5, cutoff 10:30, stop = min(2T, 0.25 x ATR14), target rr 1.5
`{"setup": "none", "mult": 1.5, "cutoff": "10:30", "max_stop_atr": 0.25, "tgt_mode": "rr", "rr": 1.5}`

| period | trades | net | win | avg trade | PF | Sharpe | max DD intraday | pos days | worst day | largest day share | pos months |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MAIN | 323 | +7,810 | 48.9% | +24.2 | 1.25 | 1.36 | -4,124 | 49% | -408 | 0.08 | 57% |
| PRIOR | 277 | +6,708 | 48.4% | +24.2 | 1.39 | 1.81 | -1,005 | 48% | -234 | 0.05 | 67% |

Exit mix MAIN: 151 stops / 122 targets / 50 flat; shorts +4,663 (172) and longs +3,147 (151). PRIOR: 135 / 126 / 16.
Lucid 50K Flex (`lucid_scan`, 60 bootstrap reps): MAIN best 5 micros -> pass rate 0.375 (within 21 sessions 0.357),
P(first payout, unconditional) 0.143, expected net +$807 per eval, bootstrap lower bound -$98, zero-edge control -$104,
median 8 days to pass -> NOT recommended. PRIOR at 5 micros: pass 0.589, P(first payout) 0.157, expected net +$809,
lower bound +$129 -> recommended. Monthly pass rate on MAIN (5 micros) ranges 0.00 (2025-01, 2026-05, 2026-06) to 0.83
(2025-07): not monthly consistent. Files: `best_MNQ_{main,prior}_{trades,daily}.csv`, `best_MNQ_summary.json`.

Same cell with EOD exit (Crabel original exit): MAIN PF 1.39 / 323 trades / Sharpe 1.47 / DD -3,345 / pos days 43%,
PRIOR PF 1.37 / Sharpe 1.44; Lucid MAIN exp net -$32 (pass 0.25). Higher PF, worse account shape (fewer positive days).

Same cell on MES: MAIN PF 1.38 (270 trades, +7,173, Sharpe 1.33, DD -2,053) but PRIOR PF 0.88 (-1,567) -> fails the
PRIOR >= 1.0 rule. MGC: MAIN PF 0.96 (eod) / 1.00 (rr), PRIOR 0.92 / 0.86 -> dead.

## Diagnostics (MNQ, defaults, MAIN; `backtest.report`)
- Edge is EOD carry: 230 flat exits avg +$254 (83% winners) vs 185 stops avg -$263 (stop = 2T ~ 120 NQ pts). Winners'
  median MAE -39 pts vs losers' median MFE +52 pts: the 2T stop is far wider than the adverse excursion of winners,
  which is what motivated the stop-cap pass.
- Hour: 09:30 hour 364 trades +$9,241; 10:00 hour 51 trades +$726 (61% win). Nothing after 11:00 (cutoff).
- Weekday: Mon +4,343, Wed +6,083, Thu +1,199; Tue -1,113, Fri -545. Both sides positive (long +5,450 / short +4,517).
- VIX (lag 1): 15-20 +7,261 (278 trades), 25-35 +5,424 (28), 20-25 -1,931 (65), >35 -1,189 (5).
- Month: 14/21 positive; worst 2026-07 (-2,637), 2025-06 (-1,929); best 2025-04 (+4,004, one day), 2026-02 (+3,082).
- Max consecutive losing trades/days: 9. Positive days 46%.

## Grids (MNQ)
1. Module GRID (36 combos), MAIN `grid_main.csv` (36 runs, ~5 min with --jobs 2): 24/36 profitable. `setup=none` block
   12/12 profitable, PF 1.16-1.38 (mult 1.5 > 2.0 > 1.0; cutoff 10:30 >= 11:30; eod ~ rr). NR7 cells: mult 1.0/rr PF 1.41
   on 59-69 trades, mult 1.5/2.0 PF 0.70-0.87 (spike). nr4_or_id: PF 0.91-1.21. No cell Lucid-recommended (best MAIN
   expected net +$1,168 at nr7/rr/1.0/11:30 on 69 trades with lower bound -$146).
2. Module GRID, PRIOR `grid_prior.csv`: 36/36 profitable; NR7 / ID cells lead (PF 1.45-2.22 on 27-113 trades),
   `setup=none` PF 1.18-1.41. Rank correlation of PF between periods: -0.68, driven entirely by the setup filters.
   -> NR7 / inside-day filters rejected (the research hypothesis does not hold on 2025-26); `setup=none` is the plateau
   that holds on both periods, with mult 1.5 at or near the top in both.
3. Stop-cap pass `grid_stopcap.csv` (base setup none / cutoff 10:30; mult [1.0, 1.5] x max_stop_atr [0.15, 0.25, 0.4]
   x tgt_mode [eod, rr]; both periods). Reason: at 0.6 x ATR the cap never binds, so the stop is 2T (mult 1.0) to 3T
   (mult 1.5), i.e. 0.4-0.6 x ATR, giving $4-5k per-micro DD. Result: mult 1.5 is a plateau across caps on both periods
   (MAIN PF 1.15-1.39, PRIOR 1.14-1.56); mult 1.0 breaks under tight caps on MAIN (0.15: PF 0.92-0.98). Two PRIOR cells
   are Lucid-recommended (1.5/0.4/rr lb +$220, 1.5/0.25/rr lb +$205); no MAIN cell is (best lb -$98 at 1.5/0.25/rr).
   Chosen cell: mult 1.5 (grid middle, best on both periods), cap 0.25 x ATR (middle of the cap plateau; the same stop
   geometry the family's orb_sma_rr survivor found), rr 1.5 (better account shape than eod: 49% vs 43% positive days,
   largest-day share 0.08 vs 0.24), cutoff 10:30 (Crabel: early fills are the profitable ones; better than 11:30 on both
   periods in the module grid).

## Attempts log
1. Faithful implementation; smoke tests MES/MNQ/MGC x MAIN/PRIOR: 341-437 trades per period, no session/index bugs.
2. Hand verification on sampled MNQ trades: stretch == manual SMA10 of noise; fills == o0 +/- T + 1 tick; stops == 2T + slip.
3. Report on MNQ MAIN: EOD-carry edge, one day = 40% of net, wide stops vs winners' MAE.
4. Module grid MAIN + PRIOR: setup filters unstable (rank corr -0.68); setup=none plateau; mult 1.5 best on both.
5. Stop-cap pass (reasoned flaw): mult 1.5 plateau across 0.15-0.4 x ATR; Lucid recommended on PRIOR, not on MAIN.
6. MES / MGC at the chosen cell: MES MAIN 1.38 but PRIOR 0.88; MGC dead.

## Verdict: marginal
On MNQ the unfiltered Crabel stretch ORB with mult 1.5, a 0.25 x ATR stop cap and a 1.5R target is profitable on both
periods (PF 1.25 / 1.39, Sharpe 1.4 / 1.8, 277-323 trades, avg trade +$24 = ~9x costs) and the parameter surface is a
plateau, but the Lucid 50K simulation on 2025-26 is not recommended at any size (pass 0.375 at 5 micros, P(first payout)
0.14, bootstrap lower bound of expected net negative, monthly pass rate 0.0-0.83). Per-micro intraday DD ($4.1k on MAIN)
and worst days (-$408) hold sizing to 5 micros, at which the $3k target needs ~25 average days. The research hypothesis
(NR7 / inside-day setups raise the edge) is falsified on 2025-26. Possible portfolio leg (shorts and longs both work,
low correlation with range-extreme ORBs expected), not a standalone candidate. No engine bugs found.

## Walk-forward (honest yardstick; `final_select --wf_start 2022-01-01 --max_combos 16`, MNQ)
IS 12 months / OOS 3 months, parameters chosen on trailing data only by daily Sharpe, base = final.json params (cap 0.25 x ATR
fixed), search grid coarsened to mult [1.0, 2.0] x setup [none, nr4_or_id] x tgt_mode [eod, rr] x cutoff [10:30, 11:30].
Files: `walkforward.json`, `wf_oos_2025_daily.csv`, `wf_oos_2025_bars.parquet`.

| span | trades | net | PF | Sharpe | pos days | pos months | max DD intraday | worst month | largest day share |
|---|---|---|---|---|---|---|---|---|---|
| OOS 2025-01..2026-09 | 225 | +777 | 1.031 | 0.15 | 43% | 48% | -3,793 | -1,608 (2026-07) | 1.13 |
| OOS 2023-01..2026-09 | 415 | +7,773 | 1.21 | 0.85 | 46% | 60% | -3,793 | -1,608 | 0.11 |
| fixed params MAIN (in-sample) | 323 | +7,810 | 1.25 | 1.36 | 49% | 71% | -4,124 | -1,065 | 0.08 |
| fixed params PRIOR | 277 | +6,708 | 1.39 | 1.81 | 48% | 54% | -1,005 | -583 | 0.05 |

Lucid on the OOS 2025 stream (`lucid_wf_2025`): 5 micros, pass rate 0.117, pass within 21 sessions 0.11, P(first payout) 0.036,
expected net +$31 per eval vs zero-edge control +$19, bootstrap lower bound -$146 -> not recommended at any size (10+ micros
exp net -$126 to -$142).

Reading: the in-sample story (PF 1.25 / 1.39, Sharpe 1.4 / 1.8) does not survive walk-forward. On 2025-26 the OOS average
trade is +$3.5 (about the round-trip cost), net excluding 2026-01, 2026-02 and 2026-09 is -$3,079, and the 2023-24 folds
carry the whole-span result. Per-fold picks oscillate between setup none / nr4_or_id and mult 1.0 / 2.0 (the folds with
the highest IS Sharpe, 1.8-2.4, produced the worst OOS: 2025Q2 -506, 2025Q3 -395, 2026Q2 -1,590), i.e. the parameter
surface is not a plateau the selector can lock onto. WF 2025 PF 1.031 clears the 1.03 proceed threshold by 0.001 on 225
trades, so the strategy is kept as a *marginal* portfolio candidate only; as a standalone it is noise-compatible.
