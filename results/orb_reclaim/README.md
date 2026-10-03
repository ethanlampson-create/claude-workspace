# orb_reclaim - London Reclaim: level sweep, 3-bar pullback swing, stop entry beyond the breakout extreme, 3.5R (family orb_session)

Module: `strategies/orb_reclaim.py`. Research: `research/families/orb_session.md` 5.3 (AskElira/london-reclaim, MNQ 2019-05..2026-08,
1,367 trades, PF 1.26, Sharpe 1.44, 32% win at $100 risk). Periods: MAIN = 2025-01-01..2026-09-30, PRIOR = 2023-01-01..2024-12-31.
All numbers per ONE micro contract after costs ($1.30 RT commission + 1 tick slippage per side on stop fills).

Engine note: all numbers in this file come from the engine state of 2026-10-03 16:44 UTC (`prepare()` now skips thin / holiday
sessions by default and pending orders are cancelled on any exit). A first grid run on the earlier engine is kept in `old_engine/`
for reference only; it is not comparable (e.g. the PRIOR default rule had 637 trades there vs 500 now).

## Rules as implemented
- 1-min bars, all times ET. Levels per session, all from bars strictly before the first entry window:
  - London high/low = high/low of bars with `tod` in [02:00, 08:30) of the same session (MGC: [02:00, 08:20), cut at the window start).
  - PDH/PDL = prior session's RTH high/low (`strategies.common.prior_day_stats`, 1-day lag; `pd_mode='session'` uses the prior full
    18:00-cut session high/low, which is what the original repo used).
- High-type levels (London high, PDH) give LONG setups when swept (bar high >= level); low-type levels (London low, PDL) give SHORT
  setups (bar low <= level). Direction = continuation of the sweep. Each level is tradable once per day; a level swept in the
  morning window is skipped in the afternoon window.
- Breakout extreme X = running max high (long) / min low (short) since and including the sweep bar.
- Pullback confirmation (3-bar swing, no look-ahead): at the close of bar j, a swing low is confirmed at bar j-1 if the swing bar is
  after the sweep bar, low[j-1] <= low[j-2], low[j-1] < low[j] and low[j-1] < X. S = low[j-1]. Mirror for shorts.
- Order at bar j+1 (live from its open): buy stop at X + 1 tick, protective stop at S - 1 tick, target = fill + rr x (order - stop),
  rr = 3.5. Skipped when (order - stop) > `max_stop_pts` (the level waits for the next swing). Live for `valid_minutes` (60) bars or
  until the window ends; an order that expires unfilled lets the level re-arm on its next confirmed swing.
- One pending order and one position at a time (engine semantics). A setup that confirms while another order is pending or a
  position is open is skipped (the level may re-arm later). Max 4 trades/day.
- Exits: stop, target, forced flat 15:55 (MGC 13:25). No trailing, no re-entry on a traded level.
- Windows: `am_only` = 09:30-11:00; `am_pm` = 09:30-11:00 and 13:30-15:30 (MGC: 08:20-11:00 / 12:00-13:00). Session set with
  `set_session(first window start, last window end, flat)` and `allow_entry` masked to the windows.
- The module runs an internal state machine that mirrors the engine's fill/exit logic to know when a level has been consumed and when
  the strategy is flat; it was verified against the engine on MAIN and PRIOR (every engine trade is predicted, 0 exit-index mismatches,
  and the engine never trades where the mirror did not predict a fill). `it.meta` holds one row per placed order for diagnostics.

Defaults (`PARAMS`, published rule): london ('02:00','08:30'), windows 'am_pm', rr 3.5, max_stop_pts {MNQ 45, MES 12, MGC 9},
valid_minutes 60, max_trades 4, flat '15:55', use_pd_levels True, pd_mode 'rth', use_london True. Gold overrides: london end 08:20, flat 13:25.

## Headline results (per micro, after costs)

Published rule (defaults):

| contract | period | trades | net $ | win | PF | Sharpe | maxDD intra | pos days |
|---|---|---|---|---|---|---|---|---|
| MNQ | MAIN | 468 | +412 | 25.4% | 1.02 | 0.12 | -2,626 | 33% |
| MNQ | PRIOR | 500 | +4,666 | 29.0% | 1.23 | 1.23 | -1,415 | 35% |
| MES | MAIN | 550 | -1,153 | 25.6% | 0.93 | -0.51 | -2,272 | 32% |
| MES | PRIOR | 501 | +312 | 27.1% | 1.03 | 0.16 | -940 | 35% |
| MGC | MAIN | 573 | -258 | 26.5% | 0.99 | -0.08 | -3,275 | 35% |
| MGC | PRIOR | 556 | -950 | 27.3% | 0.93 | -0.46 | -2,939 | 35% |

Final configuration (MNQ): windows `am_only`, London levels only (`use_pd_levels=False`), rr 3.5, `max_stop_pts` 60, valid 60 min, max 4 trades/day, flat 15:55.

| period | trades | net $ | win | avg trade | PF | Sharpe | maxDD intra | pos days | pos months | worst day | largest day share |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MAIN | 340 | +6,433 | 30.9% | +18.9 | 1.33 | 1.59 | -1,949 | 32% | 14/21 | -229 | 6.6% |
| PRIOR | 324 | +2,814 | 27.2% | +8.7 | 1.18 | 0.84 | -1,268 | 29% | 12/24 | -162 | 14.6% |

Same configuration with the published 45-pt cap: MAIN 297 trades, +3,485, PF 1.24, Sharpe 1.13; PRIOR 324 trades, +2,432, PF 1.17.
Same configuration on MES (cap 12): MAIN PF 1.11 (+1,049) but PRIOR 0.91 (-726). MGC (cap 9): MAIN 0.84, PRIOR 0.92. MES and MGC are dead.

Lucid 50K Flex Monte Carlo (MAIN daily P&L, constant micros, `lucid_scan` with 60 block-bootstrap reps; `final_MNQ_lucid_scan.csv`):

| micros | pass rate | pass within 21 d | P(payout given pass) | P(first payout) | exp net / eval | bootstrap p05 | P(lose fee) | median days to pass | zero-edge exp net |
|---|---|---|---|---|---|---|---|---|---|
| 5 | 0.41 | 0.34 | 0.37 | 0.15 | +655 | -99 | 0.59 | 13 | -130 |
| 10 | 0.25 | 0.22 | 0.14 | 0.03 | +13 | -134 | 0.75 | 10 | -113 |
| 15 | 0.19 | 0.16 | 0.10 | 0.02 | -56 | -134 | 0.81 | 10 | -113 |
| 20+ | <= 0.16 | | | <= 0.02 | < 0 | -146 | >= 0.84 | 9-10 | |

Best 5 micros: expected net +$655 per evaluation but the bootstrap 5th percentile is negative (-$99), so the harness does not flag it as
`recommended`. The max intraday DD per micro (~$1,950 on MAIN) is the binding constraint: 2+ micros already exceed the $2,000 EOD-trailing
MLL over the full period, so every size is a race between +$3,000 and the drawdown; the pass rate is driven by a 3-4 good-day run
rather than by a stable edge. 32% win / 3.5R means the funded phase needs 5 qualifying days (>= $150) out of ~30% positive days.

## Diagnostics (MNQ, final configuration)
MAIN:
- Exit mix: 79 targets (+$277 avg), 232 stops (-$84 avg), 29 flat at 15:55 (+$139 avg, 90% win). The forced-flat trades are the
  slow trend days that never reach 3.5R; they contribute $4,029 of the $6,433 net, so the 15:55 exit is load-bearing.
- Hour: 09:xx entries +$6,124 (208 trades, 34% win); 10:xx +$309 (132 trades, 27%). On PRIOR both hours are positive (09:xx +$1,944,
  10:xx +$870), so no time-of-day filter is applied.
- Sides: shorts +$4,230 (150 trades, 31% win), longs +$2,203 (190, 31%). PRIOR: shorts +$1,673, longs +$1,141. Both sides work.
- Levels: London high +$1,342 / London low +$2,143 at cap 45 on MAIN (both positive on PRIOR too). PDH/PDL (dropped): on MAIN with
  the default rule PDH -$1,576 (82 trades, 22% win) and PDL +$146; on PRIOR PDH +$1,932 and PDL +$291. Not stable across periods.
- Weekday: Mon +$1,202, Tue +$1,400, Wed +$3,194, Thu -$96, Fri +$733. PRIOR: Mon -$716, Wed -$525, Thu +$1,827, Fri +$1,486. The
  losing weekday flips between periods; no filter.
- VIX (lag 1): <15 -$420 (38 trades), 15-20 +$6,217 (227), 20-25 +$845 (53), 25-35 -$130 (21). PRIOR: <15 +$1,776 (165 trades) is the
  best bucket. No regime filter is justified.
- Months: 14/21 positive; losers Jan-25 (-438), Jun-25 (-486), Jul-25 (-198), Dec-25 (-194), Mar-26 (-449), Aug-26 (-819), Sep-26
  (-255). Best Feb-26 +1,699 (26% of net), Jan-26 +1,231, May-26 +1,155. The last two months (Aug-Sep 2026) are both negative.
- MAE/MFE (pts): winners' median MAE 17 vs stops of 30-60; losers' median MFE 22 vs targets of 100-200. Max 20 consecutive losing
  trades, 7 consecutive losing days.
- Stop-distance buckets (cap 45 on MAIN): 10-15 pts n=4, 15-20 +$145 (32% win), 20-30 +$513 (28%), 30-45 +$2,808 (30%). PRIOR: 10-15
  -$222 (12 trades, 8% win), 15-20 +$201, 20-30 +$1,335, 30-45 +$1,080. Larger stops win at least as often as small ones; the cap only
  removes trades. A stop floor was NOT added (the < 15-pt bucket is 4-12 trades).
PRIOR: 74 targets (+$220), 231 stops (-$66), 19 flat (+$95, 74% win); 12/24 positive months; max 14 consecutive losing trades.

## Grid (module `GRID`, MNQ, both periods; `grid_main.csv`, `grid_prior.csv`; Lucid columns are the best constant size on MAIN)

| rr | cap | windows | PD levels | MAIN trades | MAIN net | MAIN PF | MAIN Sharpe | Lucid pass | Lucid exp net | PRIOR trades | PRIOR net | PRIOR PF |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3.5 | 45 | am_only | True | 392 | +1676 | 1.08 | 0.50 | 0.34 | +120 | 401 | +4581 | 1.25 |
| 3.5 | 45 | am_only | False | 297 | +3485 | 1.24 | 1.13 | 0.45 | +70 | 324 | +2432 | 1.17 |
| 3.5 | 45 | am_pm | True | 468 | +412 | 1.02 | 0.12 | 0.21 | -28 | 500 | +4666 | 1.23 |
| 3.5 | 45 | am_pm | False | 346 | +2971 | 1.18 | 0.93 | 0.38 | -2 | 386 | +2255 | 1.14 |
| 3.5 | 30 | am_only | True | 276 | -787 | 0.93 | -0.40 | 0.19 | -146 | 363 | +444 | 1.03 |
| 3.5 | 30 | am_only | False | 213 | +167 | 1.02 | 0.09 | 0.24 | -146 | 280 | +49 | 1.00 |
| 3.5 | 30 | am_pm | True | 341 | -805 | 0.94 | -0.39 | 0.15 | -70 | 464 | +518 | 1.03 |
| 3.5 | 30 | am_pm | False | 256 | -270 | 0.97 | -0.14 | 0.22 | -29 | 341 | +131 | 1.01 |
| 2.5 | 45 | am_only | True | 407 | -790 | 0.96 | -0.28 | 0.19 | -146 | 422 | +1338 | 1.07 |
| 2.5 | 45 | am_only | False | 297 | +1240 | 1.09 | 0.48 | 0.36 | -113 | 324 | +467 | 1.03 |
| 2.5 | 45 | am_pm | True | 485 | -1372 | 0.94 | -0.46 | 0.16 | -146 | 523 | +1122 | 1.05 |
| 2.5 | 45 | am_pm | False | 346 | +753 | 1.05 | 0.28 | 0.28 | -44 | 386 | +111 | 1.01 |
| 2.5 | 30 | am_only | True | 284 | -1887 | 0.82 | -1.19 | 0.00 | n/a | 381 | -329 | 0.98 |
| 2.5 | 30 | am_only | False | 213 | -427 | 0.94 | -0.29 | 0.10 | -146 | 280 | -471 | 0.95 |
| 2.5 | 30 | am_pm | True | 349 | -1670 | 0.86 | -0.99 | 0.12 | -146 | 484 | -349 | 0.98 |
| 2.5 | 30 | am_pm | False | 256 | -699 | 0.92 | -0.44 | 0.16 | -146 | 341 | -401 | 0.96 |
| 2.0 | 45 | am_only | True | 413 | +141 | 1.01 | 0.05 | 0.18 | -138 | 435 | +738 | 1.04 |
| 2.0 | 45 | am_only | False | 297 | +1509 | 1.11 | 0.65 | 0.29 | +5 | 324 | -482 | 0.96 |
| 2.0 | 45 | am_pm | True | 492 | -143 | 0.99 | -0.05 | 0.21 | -60 | 538 | +858 | 1.04 |
| 2.0 | 45 | am_pm | False | 346 | +1164 | 1.08 | 0.49 | 0.29 | +66 | 386 | -505 | 0.97 |
| 2.0 | 30 | am_only | True | 288 | -1550 | 0.84 | -1.03 | 0.01 | -146 | 391 | -981 | 0.92 |
| 2.0 | 30 | am_only | False | 213 | -809 | 0.89 | -0.61 | 0.06 | -146 | 280 | -697 | 0.92 |
| 2.0 | 30 | am_pm | True | 355 | -1206 | 0.90 | -0.76 | 0.17 | -146 | 494 | -630 | 0.96 |
| 2.0 | 30 | am_pm | False | 256 | -871 | 0.90 | -0.61 | 0.24 | +41 | 341 | -238 | 0.98 |

Grid reading: 10/24 cells profitable on MAIN, 14/24 on PRIOR; rank correlation of net between periods 0.45. The four rr 3.5 / cap 45
cells are all positive on both periods (the only such block): the published target and stop cap are the plateau, rr 2.0-2.5 and a
30-pt cap are not. PDH/PDL help PRIOR (+$2,100) and hurt MAIN (-$1,800 to -$2,600); the afternoon window adds trades and drawdown but no
net on either period (MAIN -$514, PRIOR -$177 vs am_only at cap 45). London-only + am_only is the one cell that is >= 1.15 on both.

## Attempts log
1. Faithful implementation of the spec (defaults). MNQ MAIN PF 1.02 / 468 trades, PRIOR 1.23; MES/MGC <= 1.03. Win rate 25-29% vs the
   published 32%, i.e. the retest edge is thinner here (CFD proxy, 1-tick slippage both sides, thin-session skip).
2. Mirror verification: the module's internal fill/exit mirror matches the engine on every trade in both periods (0 mismatches).
3. `pd_mode='session'` (prior full-session high/low, the original repo's definition): with PD levels and am_only, MAIN PF 1.11 vs 1.08
   (rth), PRIOR 1.27 vs 1.26 - slightly better, but PD levels of either kind are below London-only on MAIN. Kept as an option only.
4. Afternoon window: MAIN -$1,264 on 76 trades (default rule), PRIOR -$8 on 135. Dropped (`am_only`). Reason: no net contribution on
   either period and the research note places the edge in the 09:30-11:00 window.
5. PDH/PDL: MAIN -$1,431 (135 trades), PRIOR +$2,223. Dropped. Reason: unstable sign, and the note's PDH statistic ("almost 100%
   re-entry into the prior range") makes a plain PDH break a poor continuation level.
6. Stop cap sweep (am_only, London only): MAIN PF 1.24 (45) / 1.33 (60) / 1.26 (80) / 1.31 (100) / 1.29 (150) / 1.32 (none); PRIOR 1.17 /
   1.18 / 1.15 / 1.13 / 1.16 / 1.15. maxDD MAIN -1,948 / -1,949 / -2,253 / -2,848 / -3,130 / -3,306. 60 adopted: best on both periods,
   DD unchanged vs 45, plateau above it. Reason: the published 45 NQ pts was set on 2019-2024 prices (NQ ~7k-18k); NQ now trades at
   ~2x, so a fixed 45-pt cap is tighter in relative terms and rejects normal-depth pullbacks whose win rate is the same or better.
7. valid_minutes 30/60/90: MAIN PF 1.22 / 1.24 / 1.23, PRIOR 1.14 / 1.17 / 1.17 (cap 45). Flat; default kept.
8. rr 3.0 / 4.0 (cap 45): MAIN 1.15 / 1.23, PRIOR 1.11 / 1.12 - both below 3.5 on both periods. Default kept.
9. Not tried on purpose: time-of-day, weekday and VIX filters (each losing bucket on MAIN is a winning bucket on PRIOR), a stop floor
   (< 15-pt bucket has 4-12 trades).

## Verdict: marginal
The strategy reproduces the published shape (31% win, 3.5R, ~190 trades/yr, PF 1.2-1.3) on MNQ and holds on 2023-2024 with the same
parameters, so it is real but thin. As a stand-alone Lucid 50K candidate it is a lottery: $1,950 max DD per micro caps the size at 5
micros, which gives a 41% pass rate, a 15% unconditional first-payout probability and +$655 expected net per evaluation with a negative
bootstrap lower bound; 32% positive days fight the payout rule (5 days >= $150). It is a reasonable diversifying leg for the "safe"
portfolio (short-biased profits, morning-only exposure, no outsized days: largest day 6.6% of net) rather than a core engine.
Files: `final.json`, `final_MNQ_{main,prior}_{trades,daily}.csv`, `final_MNQ_lucid_scan.csv`, `grid_{main,prior}.csv/.log`.

## Walk-forward assessment (honest yardstick, 2026-10-03; `walkforward.json`, `wf_oos_2025_daily.csv`)
`python3 -m backtest.final_select --ids orb_reclaim --jobs 2 --wf_start 2022-01-01 --max_combos 16` on MNQ: IS 12 months / OOS 3 months, parameters
chosen on trailing data only from the module `GRID` (rr 2.0/2.5/3.5, cap 30/45, am_only/am_pm, PD levels on/off), 15 folds 2023-01..2026-09.

| stream | trades | net $ | PF | Sharpe | win | pos days | pos months | maxDD intra | largest day share |
|---|---|---|---|---|---|---|---|---|---|
| WF OOS 2023-01..2026-09 (all) | 784 | +6,421 | 1.19 | 0.96 | 28.1% | 31% | 25/45 | -1,948 | 8.8% |
| WF OOS 2025-01..2026-09 (`wf_2025`) | 309 | +2,669 | 1.17 | 0.84 | 28.2% | 29% | 13/21 | -1,948 | 20.0% |
| fixed final params, MAIN (in-sample) | 340 | +6,433 | 1.33 | 1.59 | 30.9% | 32% | 14/21 | -1,949 | 6.6% |
| fixed final params, PRIOR | 324 | +2,814 | 1.18 | 0.84 | 27.2% | 29% | 12/24 | -1,268 | 14.6% |

Fold path: 2023 folds picked `am_pm` / cap 30 (OOS PF 2.07, 1.21, 0.73, 0.84); 2024 folds `am_only` + PD levels / cap 45 (1.27, 0.80, 1.63, 1.38);
Q1-2025 still with PD levels (0.96); from Q2-2025 `am_only`, London only, cap 45, rr 3.5 (1.28, 1.15, 1.29, 1.41, 1.73, then 0.51 for Jul-Sep 2026).
The final cap 60 is not in the grid, so the walk-forward validates the cap-45 version (MAIN in-sample PF 1.24).

OOS 2025 monthly: 5 months (Nov-25 +1,042, Jan-26 +649, Feb-26 +1,158, Apr-26 +779, May-26 +1,068 = +4,697) exceed the whole net; the other 16 sum to
-2,028; Mar-26 -988; Jul/Aug/Sep-26 all negative (-980 in total, fold PF 0.51). Largest OOS day = 20% of the net.

Lucid 50K Flex on the OOS 2025 stream (`lucid_wf_2025`, bootstrap lower-bound sizing): 5 micros, pass rate 0.38, pass within 21 d 0.26, P(first payout)
0.044, P(breach before payout) 0.67, expected net +29/eval, lower bound -146 = zero-edge control -146, **not recommended** (10 micros: +73 point estimate,
same -146 lower bound). The in-sample MAIN scan (+655/eval at 5 micros) was the optimistic half of the story.

Reading: the OOS 2025 stream reproduces PRIOR (PF 1.17-1.18, Sharpe 0.84, avg trade ~$8.6/micro), not MAIN; the edge is real but thin, lumpy (five
months carry it, 29% positive days vs 3.5R targets), and currently in a 3-month losing run. Max DD -1,948/micro ties the size at 5 micros, where the
expected net per evaluation is indistinguishable from a demeaned stream. Gate: OOS PF 1.17 >= 1.03 on 309 trades, so the strategy formally proceeds as a
diversifying portfolio leg; verdict stays **marginal**, not a stand-alone Lucid candidate. No parameter change attempted (nothing in the grid beats the
current cell on both periods, see the attempts log above). `final.json` now carries `wf_2025` and the `lucid` block from `lucid_wf_2025`.
