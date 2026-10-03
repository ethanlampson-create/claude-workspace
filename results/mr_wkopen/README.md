# mr_wkopen - Weekly-open reversion (day-2 fade toward the week's first RTH open)

Family: intraday_mean_reversion (research #24, tradingstats.net "565 weeks of NQ data"). Module: `strategies/mr_wkopen.py`.

## Rules as implemented
- **Week**: first session of a week = first session whose session-date weekday is lower than the previous session's
  (Monday normally; Tuesday after a Monday holiday). `WO` = open of that session's first RTH 1-min bar (09:30 ET for
  MES/MNQ, 08:20 ET for MGC). The WO bar must sit within 5 min of the RTH open, otherwise the week is skipped.
- **Trade day** = the next session of the same week (Tuesday). `allow_day3` (default False): if day 2 did not qualify,
  day 3 is tried with `max_dist` capped at 0.25%.
- **Setup** at the trade day's first RTH bar: `d = (open_rth - WO) / WO`; qualify `min_dist (0.05%) <= |d| <= max_dist`.
  Open below WO -> LONG, above -> SHORT (`sides` = both | long | short). `require_eth_touch`: the 18:00 -> RTH-open span
  must have traded through WO. Skip if the 09:30 bar already touched WO (its high/low is known at the 09:31 decision).
- **Entry**: market at the open of the bar at RTH open + `entry_delay` (1 min, i.e. 09:31 / 08:21).
- **Stop**: `open_rth -/+ max(stop_mult * |open_rth - WO|, min_stop_pct% * open_rth)`. **Target**: WO (fills 1 tick through).
- **Exits**: open of the first bar >= `exit_time` (11:30) via `Intents.exit_at`; forced flat at 15:55 (all contracts).
  `max_trades_day = 1`, one trade per week per instrument.
- Defaults: `max_dist=0.25, min_dist=0.05, stop_mult=1.0, min_stop_pct=0.15, entry_delay=1, exit_time='11:30', flat='15:55',
  sides='both', require_eth_touch=False, allow_day3=False, max_trades=1`.
- Look-ahead: the only information used at the 09:31 decision is the week-open bar, the overnight bars and the 09:30 bar
  (all closed). No daily indicators needed.

## Base-rate check of the study on our data (scratch script, not a backtest)
NQ 2025-01..2026-09 (91 weeks): WO touched on day 2 in RTH when |d| is 0.05-0.25%: 18/18 (89% by 11:30); 0.25-0.50%:
64%; 0.5-1%: 38%; >1%: <7%. NQ 2015-2024 (521 weeks): 0.05-0.25%: 84% (76% by 11:30); 0.25-0.50%: 52%. So the
study's touch rates reproduce. Two problems appear immediately:
1. **Frequency**: only ~20% of weeks open within 0.25% of WO (NQ median |d| in 2025-26 is 0.72%), and in 2025-26 39% of
   those weeks already touch WO inside the 09:30 bar (NQ 1-min opening bars are huge now), so they cannot be traded.
   Result: 10 MNQ trades in 21 months at the published 0.25% filter.
2. **Stop vs noise**: with distance ~0.15% the stop is 0.15-0.25% below the open; in 2025-26 the 09:30-11:30 NQ noise is
   larger than that, so the stop is hit before the (eventually ~90% certain) touch. MNQ median MAE on winners is -27 pts.

## Metrics (per 1 micro, after costs). MAIN = 2025-01-01..2026-09-30, PRIOR = 2023-01-01..2024-12-31

### Published defaults (max_dist 0.25)
| contract | period | trades | net $ | win | PF | maxDD intra | Sharpe |
|---|---|---|---|---|---|---|---|
| MNQ | MAIN | 10 | -19 | 0.50 | 0.93 | -217 | -0.07 |
| MNQ | PRIOR | 19 | -98 | 0.42 | 0.81 | -363 | -0.28 |
| MES | MAIN | 21 | 141 | 0.57 | 1.31 | -253 | 0.42 |
| MES | PRIOR | 27 | -200 | 0.56 | 0.68 | -427 | -0.48 |
| MGC | MAIN | 10 | 274 | 0.70 | 2.20 | -147 | 0.86 |
| MGC | PRIOR | 25 | -246 | 0.40 | 0.53 | -305 | -0.98 |

### Best cells from the 16-combo grid (max_dist x stop_mult x exit_time x sides), CSVs `grid_main_{MNQ,MES,MGC}.csv`
| contract | params | MAIN trades / net / PF / Sharpe / pos-months | PRIOR trades / net / PF | Lucid (best micros, pass, E[net/eval]) |
|---|---|---|---|---|
| **MES** | max_dist 0.50, stop 1.0, 11:30, both | 35 / +736 / 2.09 / 1.41 / 76% | 54 / -522 / 0.67 | 10, 37%, -146 (15 micros: 56% pass, 0 payout) |
| MES | max_dist 0.50, 13:00, long | 15 / +355 / 2.73 | 37 / -440 / 0.65 | 10, 36%, +244 |
| **MNQ** | max_dist 0.50, stop 1.0, 11:30, both | 21 / +260 / 1.27 / 0.34 / 48% | 43 / +803 / 1.59 | 10, 4%, -146 |
| MNQ | max_dist 0.50, stop 1.5, 11:30, both | 21 / -75 / 0.94 | 43 / +1256 / 1.98 | - |
| MGC | max_dist 0.25, stop 1.0, both | 10 / +274 / 2.20 | 25 / -246 / 0.53 | - |
| MGC | max_dist 0.50, stop 1.5, 11:30, long | 17 / +245 / 1.26 | 20 / +131 / 1.45 | 10, 2%, -146 |

Exit 11:30 vs 13:00 is identical on MNQ MAIN (every trade resolves before 11:30; median hold 2.5 min, Q3 9.5 min).
Longs vs shorts: on MAIN shorts are slightly better on MES/MNQ (0.64-0.70 win) - the opposite of the study's long bias.

### Follow-up grid (base max_dist 0.50; require_eth_touch x allow_day3 x min_stop_pct {0.15, 0.30}), `followup_{MNQ,MES}.csv`
- `require_eth_touch=True` is worse everywhere (MNQ MAIN PF 0.88-0.91 vs 1.27; MES 1.59-1.80 vs 2.05-2.09; PRIOR also
  worse on MNQ). The study's "ETH touch raises RTH touch to 82.7%" does not translate into P&L here: a WO already
  traded overnight means the open is usually right on it and the 09:30 bar touches it (skipped) or the move is noise.
- `allow_day3=True`: MNQ MAIN 29 trades PF 1.00 (adds 8 losing day-3 trades); MES MAIN 41 trades PF 1.98 (+6 trades,
  net unchanged); PRIOR MES still 0.70.
- `min_stop_pct=0.30`: +$20-40 on MAIN, no change in sign anywhere; the stop width is not the lever.

## Diagnostics (MES max_dist 0.50, MAIN)
- Exit reasons: target 18 (+1,076), stop 9 (-561), time exit 8 (+222). Stops are ~1x the winners in size (-62 vs +60).
- VIX: 15-20 bucket 25 trades +367 (60% win); 20-35 buckets 7 trades +448 (100% win); <15: 3 trades -78.
- Months: 16/21 positive; worst May-2025 -139, May-2026 -108; largest day share 15%. Looks healthy but n=35.
- PRIOR (2023-24) is the problem: 54 trades, 46% win, PF 0.67, max DD -934: in the 2023-24 grind the Tuesday open was
  frequently 0.25-0.5% away and did not come back by 11:30 (touch rate 52% in that bucket historically, only 44% by 11:30).

Diagnostics (MNQ max_dist 0.50, MAIN): target 12 (+1,232) vs stop 9 (-971); May-2026 alone -393 (3 straight stops);
pos-days 57%; Sharpe 0.34. PRIOR 43 trades PF 1.59, Sharpe 0.92: the same rules were much better in 2023-24 on NQ than
in 2025-26, the reverse of MES. With n ~ 20-50 per period, the two instruments disagreeing in sign across periods says
the per-instrument cells are noise around a small true edge.

## Attempts log
1. Published rules, max_dist 0.25, all three micros: too few trades (10/21/10), negative on PRIOR for all three.
2. Module grid (16) on MAIN+PRIOR x 3 contracts: max_dist 0.50 is better than 0.25 on every instrument (more trades, PF
   up), stop_mult 1.5 is not better than 1.0 on MAIN, exit 13:00 adds nothing, long-only halves the sample without
   improving PF on MAIN.
3. Follow-up (ETH touch, day 3, stop floor): no cell improves MAIN and PRIOR together.
4. Not tried (would be curve fitting with n<50): VIX gates, ATR-scaled stops, scaling into the 09:30-bar-touch weeks.

## Verdict: **marginal** (dead as a standalone evaluation strategy)
- No instrument reaches PF >= 0.95 with >= 40 trades *and* holds on PRIOR. MES (35-41 trades, PF 2.0-2.1 on MAIN) fails
  PRIOR (0.67-0.70); MNQ holds on PRIOR (1.59) but has 21 MAIN trades, Sharpe 0.34 and a 4% Lucid pass rate.
- At <= 2 trades per month per instrument, even a true PF 1.3-1.5 edge cannot pass a $50K LucidFlex evaluation in
  reasonable time: Lucid expected net per evaluation is negative in every cell on every instrument (best: MES long-only
  13:00, +$244, 15 trades).
- Usable only as a small portfolio leg (MES + MNQ at max_dist 0.50, 1 trade per week each, both sides) where its low
  correlation with other legs matters more than its own P&L; it should not be sized to carry an evaluation.
- Engine notes: none. The `exit_at` time exit and the first-bar touch skip behave as intended (checked trade lists).

Files: `grid_main_{MNQ,MES,MGC}.csv/.log`, `followup_{MNQ,MES}.csv/.log`, `best_MNQ_main_{trades,daily}.csv`, `final.json`.
