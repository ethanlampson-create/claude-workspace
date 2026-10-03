# ev_fvg_nested - 5-min bullish FVG nested inside a 15-min bullish FVG, long only, 2R, 09:30-12:00 ("NQ Strategy B")

Module: `strategies/ev_fvg_nested.py`. Family: evidence_and_failures (`research/families/evidence_and_failures.md` 2.1, GitHub
prashanthaitha24/nq-strategy-b-bot: 1 MNQ, Jan 2023-May 2026, 432 trades, 53.5% win, PF ~2.3, +$17,187, max DD $786; evidence quality 2).
Periods: MAIN = 2025-01-01..2026-09-30, PRIOR = 2023-01-01..2024-12-31. All numbers per ONE micro contract after costs
($1.30 RT commission + 1 tick slippage per side on market/stop fills). `prepare()` skips thin/holiday sessions (< 80% of the typical
RTH bar count) by default.

## Rules as implemented
- Bars: `B5 = resample(df1, 5, rth_only=True)`, `B15 = resample(df1, 15, rth_only=True)` (09:30-16:00 ET). Both series are
  continuous across sessions (an RTH chart), so zones persist into later days unless `same_session_only`.
- Bullish FVG on a series X at bar j: `X.low[j] > X.high[j-2] + min_gap` -> zone {bottom = X.high[j-2], top = X.low[j],
  born_i = X.i_last[j]}. min_gap = `min_gap5` (2 NQ pts) for B5, `min_gap15` (5) for B15. Bearish mirror only with `side='both'`.
- Active: from bar j+1 until the first later bar whose low <= bottom (filled, dead for good) or until age (current bar - j) >
  `max_age` bars (36 x 5-min, 24 x 15-min by default); with `same_session_only` also at the session end. "Active at k" uses bars
  strictly before 5-min bar k; for B15 the bars that COMPLETED before bar k opened (`i_last < B5.i_first[k]`), and the "current"
  15-min bar for the age test is the one containing k.
- Signal on 5-min bar k with tod in [09:30, 11:55] (bar closes by 12:00): among the active 5-min zones f born before k for which an
  active 15-min zone F (completed before k opened) exists with `f.bottom >= F.bottom` and `f.top <= F.top + buffer_pts` (5 NQ pts),
  require `B5.low[k] <= f.top`, `B5.low[k] > f.bottom` (dips INTO the 5-min FVG, not through it) and `B5.close[k] > f.top`
  (closes back above). f = the candidate with the highest top.
- Order: market long at the open of `B5.i_next[k]` (skipped when -1). c = B5.close[k]; stop = f.bottom - `stop_off_pts` (2);
  R = c - stop; skipped when R < `min_R` (8 NQ pts) or R > `max_R` (60) or R < min_stop_pts (MNQ 6, MES 4); target = c + rr x R
  (rr 2.0). No trailing, no time exit; forced flat at 15:45.
- Every "NQ point" parameter is scaled by PT = {MNQ 1.0, MES 0.28}. Session: `set_session('09:30', '12:01', '15:45')` (the +1 minute
  lets the 11:55 signal bar fill at the 12:00 open, as the published "signal time 09:30-12:00" implies). `max_trades_day` = 2;
  Lucid risk block per micro: daily loss stop {MNQ 40, MES 35} x `dls_mult` (1.0), daily profit stop {MNQ 60, MES 50} x `dps_mult`
  (1.0). One position at a time (engine); a signal that fires while a position is open is dropped.
- `delay=1` places every order at `B5.i_next[k+1]` (sensitivity run). `age_preset` A/B/C overrides max_age5/max_age15/same_session_only
  (A: 24/16/True, B: 36/24/False = published-like, C: 72/48/False).
- Defaults (`PARAMS`) = the published README except the flagged deviations (min_R/max_R, min_stop_pts, Lucid risk block).

## Headline results (per micro, after costs, defaults)

| contract | period | trades | net $ | win | avg trade | PF | Sharpe | maxDD intra | pos days | pos months |
|---|---|---|---|---|---|---|---|---|---|---|
| MNQ | MAIN | 68 | -133 | 33.8% | -2.0 | 0.96 | -0.12 | -1,009 | 35% | 8/21 |
| MNQ | PRIOR | 81 | -939 | 30.9% | -11.6 | 0.74 | -0.83 | -1,623 | 31% | 6/24 |
| MES | MAIN | 76 | -8 | 39.5% | -0.1 | 1.00 | -0.01 | -771 | 40% | 12/21 |
| MES | PRIOR | 74 | -19 | 36.5% | -0.3 | 0.99 | -0.02 | -663 | 38% | 10/24 |

Per year (defaults; the specs' section-13 validation asks for positive net in each year, >= 100 trades/yr, win >= 50%, PF >= 1.3):

| contract | year | trades | net $ | win | PF | maxDD intra |
|---|---|---|---|---|---|---|
| MNQ | 2023 | 32 | +123 | 37.5% | 1.10 | -401 |
| MNQ | 2024 | 49 | -1,062 | 26.5% | 0.54 | -1,336 |
| MNQ | 2025 | 41 | -870 | 26.8% | 0.57 | -870 |
| MNQ | 2026 (9 mo) | 27 | +738 | 44.4% | 1.80 | -335 |
| MES | 2023 | 29 | -265 | 34.5% | 0.73 | -481 |
| MES | 2024 | 45 | +246 | 37.8% | 1.20 | -321 |
| MES | 2025 | 49 | -634 | 30.6% | 0.59 | -771 |
| MES | 2026 (9 mo) | 27 | +626 | 55.6% | 2.42 | -115 |

Without the R caps (published rule: `min_R=0, max_R=inf`): MNQ 2023 -349 (34 trades, PF 0.79), 2024 -1,792 (68, 0.64), 2025 -1,634
(54, 0.62), 2026 +2,173 (39, 1.88); MES 2023 -68 (0.93), 2024 +118 (1.06), 2025 -741 (0.77), 2026 +1,225 (2.29). Every validation
criterion fails: 2 of 4 years negative on both instruments, 30-50 trades/yr (published ~140), win 27-44% (published 53%), PF < 1.3 in
3 of 4 years. Only 2026 looks like the published numbers - which is also the published sample's best year (68% win), i.e. the
2026 regime (5-min NQ bar range 30-48 pts vs 17-25 in 2025) suits the rule, not a stable edge.

Data note: the proxy feed has only ~180 RTH bars per session in Mar-Jul 2023 (vs 390), so `prepare()` skips most of those sessions
(zero trades Mar-Jul 2023 on both instruments); PRIOR has ~19 effective months. Zones are still computed on those bars.

## Mandatory sensitivity runs (defaults; `sensitivity.csv`)

| run | MNQ MAIN | MNQ PRIOR | MES MAIN | MES PRIOR |
|---|---|---|---|---|
| default | 68 tr, -133, PF 0.96 | 81, -939, 0.74 | 76, -8, 1.00 | 74, -19, 0.99 |
| delay = 1 (order at `i_next[k+1]`) | 70, +258, 1.11 | 80, -1,410, 0.59 | 82, -396, 0.81 | 73, -96, 0.96 |
| slip_ticks = 2 | 68, -191, 0.94 | 81, -1,010, 0.72 | 76, -174, 0.92 | 73, -137, 0.94 |
| side = 'both' (extra run) | 105, -333, 0.93 | 126, -1,102, 0.80 | 128, +422, 1.12 | 107, +35, 1.01 |

The one-bar delay flips MNQ MAIN from -133 to +258 and MES MAIN from -8 to -396: the result is fill-timing noise, not edge. Doubling
slippage costs $60-170 per period (~$1-2 per trade), so costs are not the problem - the gross edge is ~0. Shorts on MNQ lose (0.80-0.93,
consistent with the published 42.5% short win rate); on MES `side='both'` is +422 / PF 1.12 on MAIN and +35 / 1.01 on PRIOR (avg trade
+$3.3 = the cost of a round trip, Sharpe 0.43) - a one-off extra run on the second instrument, not a reason to change the rule.

## Diagnostics (MNQ MAIN, defaults; `report_MNQ_main.txt`)
- Signal funnel: 228 raw signals (0.51/day, matching the published "~0.5 trades/day"); the R caps remove 117 (115 above 60 pts,
  2 below 8) -> 111 orders; one-position-at-a-time, max 2 trades/day and the $40 daily loss stop leave 68 fills. Median R without caps
  is 61 NQ pts in 2025-26 (42 in 2023-24): close - low[k] median 20 pts plus low[k] - bottom median 27 pts. The published "median R
  10-30 pts" does not hold at 20k+ NQ prices, so the 60-pt cap (a flagged deviation) halves the sample and does not help (no-cap MAIN
  PF 1.10 on 104 trades, PRIOR 0.69 on 111).
- Exit mix: 20 targets (+$120 avg), 45 stops (-$65), 3 flat at 15:45 (+$133, all winners). Without caps: 27 targets, 54 stops,
  23 flat (+$86, all winners) - the trades that survive to 15:45 are trend days that never reached 2R.
- Hour of entry: 09:xx +$131 (8 trades), 10:xx +$133 (25), 11:xx -$345 (31, 29% win), 12:00 fills -$52 (4). Signals cluster late
  because a 15-min FVG cannot complete before 10:15 within the session.
- Weekday: Thu +$493 (20 trades, 45% win), Wed +$128, Mon -$111, Tue -$52, Fri -$590 (12 trades, 17% win). Too few trades to filter.
- VIX (lag 1): 15-20 +$477 (53 trades), <15 +$125 (5), 20-25 -$608 (8, 12% win), >25 -$128 (2).
- Months: 8/21 positive; best Jul-26 +$431, Sep-26 +$258; worst Oct-25 -$304, Dec-25 -$252. No trades in Jan-Feb 2025 (all signals
  cut by the R cap or blocked by the loss stop).
- MAE/MFE: median MAE -24 pts, median MFE +24; winners' median MAE -15; losers' median MFE +8 (losers go nowhere). Median hold 15.5
  minutes (quartiles 3 / 41): most stops hit within minutes of the fill, i.e. the "close back above the FVG" is not a reliable
  rejection on this feed. Max 7 consecutive losing trades.
- Stop-distance buckets (no caps, MNQ): 15-30 pts +$206 (26 trades, 42% win) on MAIN but -$620 (33, 21%) on PRIOR; 30-60 pts -$369
  / -$1,418; 60-100 +$703 / -$115; > 100 pts -$1,765 / -$2,035 (0-33% win, 7 + 7 trades). No bucket is positive on both periods.

## Grid (module `GRID`: rr {1.5, 2, 3} x buffer {5, 10} x age preset {A, B, C} x max_trades {1, 2} = 36 combos; Lucid columns on MAIN)
MNQ (`grid_main.csv`, `grid_prior.csv`, joined in `grid_both_MNQ.csv`): MAIN 13/36 cells profitable (median PF 0.96, best 1.15 at
rr 3 / buffer 5 / preset B / 1 trade, 66 trades, Sharpe 0.34); PRIOR 0/36 profitable (median PF 0.78, best 0.91 - the same rr 3 / B cell).
Rank correlation of net between the periods 0.23. Medians by factor (MAIN / PRIOR PF): rr 1.5 0.93 / 0.78, rr 2 0.91 / 0.75, rr 3 1.06 /
0.85; preset A 0.96 / 0.75, B 0.99 / 0.78, C 0.84 / 0.85; buffer 5 0.99 / 0.84, 10 0.93 / 0.83; 1 trade 0.97 / 0.84, 2 trades 0.95 / 0.83.
rr 3 is the best target on both periods but still < 1.0 on PRIOR; long-lived zones (C) add trades and lose more. No Lucid cell is
`recommended` (bootstrap lower bound -146 = the evaluation fee everywhere; pass rates 0.06-0.28 at 5 micros).

| rr | buffer | preset | trades/day | MAIN trades | MAIN net | MAIN PF | PRIOR trades | PRIOR net | PRIOR PF |
|---|---|---|---|---|---|---|---|---|---|
| 3.0 | 10 | B | 1 | 78 | +516 | 1.14 | 88 | -547 | 0.87 |
| 3.0 | 5 | B | 1 | 66 | +452 | 1.15 | 80 | -347 | 0.91 |
| 3.0 | 10 | B | 2 | 80 | +437 | 1.12 | 90 | -615 | 0.85 |
| 3.0 | 5 | B | 2 | 68 | +373 | 1.12 | 81 | -393 | 0.89 |
| 3.0 | 10 | A | 1 | 75 | +245 | 1.07 | 74 | -513 | 0.85 |
| 2.0 | 5 | B | 1 | 66 | -53 | 0.98 | 80 | -894 | 0.75 |
| 2.0 | 5 | B | 2 (default) | 68 | -133 | 0.96 | 81 | -939 | 0.74 |
| 1.5 | 5 | B | 1 | 66 | +103 | 1.04 | 80 | -751 | 0.77 |
| 2.0 | 10 | C | 2 | 95 | -818 | 0.81 | 101 | -746 | 0.83 |
| 1.5 | 10 | C | 2 | 98 | -971 | 0.77 | 101 | -532 | 0.87 |

MES MAIN (`grid_main_MES.csv`): 1/36 cells profitable (rr 2 / buffer 5 / B / 1 trade: +$21, PF 1.01, 75 trades); median PF 0.79; the
published defaults are the best region, and every neighbour (buffer 10, preset A or C, rr 1.5 or 3) is 0.6-0.96. A spike at the
published cell, not a plateau; PRIOR at defaults is 0.99.

## Lucid 50K Flex (MAIN daily P&L, `final_{MES,MNQ}_lucid_scan.csv`)
MES defaults: expected net per evaluation equals the zero-edge control at every size (e.g. 15 micros: pass rate 0.37, +$846 point
estimate, zero-edge control +$846, bootstrap p05 -$146); MNQ: pass rate <= 0.20, expected net -$146 (the fee) at every size. Nothing
is `recommended`. A 1.5-2.5x haircut (the published author's own expectation) is moot: there is nothing to haircut.

## Attempts log
1. Faithful implementation of the spec on MNQ and MES (defaults). MNQ MAIN PF 0.96 / 68 trades, PRIOR 0.74; MES 1.00 / 0.99. Verified
   the funnel: FVG counts (8 x 5-min and 2.9 x 15-min bullish FVGs per day on MNQ), 228 raw signals on MAIN (0.51/day as published).
2. Removed the flagged R caps (published rule): MNQ MAIN 104 trades, PF 1.10, but PRIOR 0.69 (111 trades); MES 1.0 / 0.95. The caps
   are not the problem and are kept at the spec defaults.
3. Mandatory sensitivity (delay 1, slip 2 ticks) and the extra `side='both'` run: see table above. Fill timing changes the sign of
   MAIN on both instruments -> no edge to be sensitive about.
4. Module grid on MNQ (MAIN + PRIOR) and MES (MAIN): no cell is profitable on PRIOR for MNQ; one break-even cell on MES MAIN.
5. Not tried on purpose: hour / weekday / VIX filters (each losing bucket has 8-31 trades and flips between periods), a limit entry at
   the FVG top or a tighter stop at the signal-bar low (a different strategy, and losers' median MFE of 8 pts says the rejection itself
   fails, not the stop placement), re-tuning min gaps.

## Verdict: dead
The rule is objective and the implementation reproduces the published trade frequency (0.5 signals/day), but on this data the win rate
at 2R is 27-44% (published 53%), 2 of 4 years lose on both instruments, PRIOR is negative in all 36 MNQ grid cells, a one-bar entry
delay flips the sign of MAIN, and the Lucid scan cannot distinguish it from its zero-edge control. The published 46 -> 68% win-rate
drift was the warning sign; only 2026 (a high-range regime) resembles the published numbers. Not a portfolio component.
Files: `final.json` (MES defaults, the break-even instrument), `final_{MES,MNQ}_{main,prior}_{trades,daily}.csv`,
`final_{MES,MNQ}_lucid_scan.csv`, `grid_main.csv/.log`, `grid_prior.csv/.log`, `grid_both_MNQ.csv`, `grid_main_MES.csv/.log`,
`sensitivity.csv`, `report_MNQ_main.txt`.
