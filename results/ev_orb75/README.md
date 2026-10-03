# ev_orb75 - Mesfin ORB long, 25-min OR, close-confirmed entry, 75-min time exit (family evidence_and_failures)

Module: `strategies/ev_orb75.py`. Research: `research/families/evidence_and_failures.md` 1.4 (arXiv 2605.04004, "ORB long,
bar+15": OOS N=447, net +2.82 MNQ pts after 2.0-pt friction, +2.43 / +7.04 / +15.05 pts in 2023 / 2024 / 2025, T=0.88).
Periods: MAIN = 2025-01-01..2026-09-30, PRIOR = 2023-01-01..2024-12-31. All numbers per ONE micro contract, after costs
(engine: $1.30 RT commission + 1 tick slippage per side on market/stop fills).

## Rules as implemented (all times ET)
- 5-min RTH bars from the 1-min feed (`resample(df1, 5, rth_only=True)`, buckets anchored at 18:00 -> 09:30, 09:35, ...).
- Opening range = high/low of the 1-min bars in [09:30, 09:55) (five 5-min bars). Daily ATR14 of RTH bars, shifted one day;
  skip the day if NaN. Daily RTH closes for `prev_close` / SMA200 and the VVG gap / r30 quantiles are built on up to 420
  calendar days of 1-min history loaded BEFORE the first session of the run (so the SMA200 and the 120-session quantile
  warm-up do not eat the test window); every daily feature of day d uses sessions < d only.
- Scan 5-min bars starting 09:55 .. 11:25 in order; at the FIRST bar whose close > or_high: market long at the open of the
  next 1-min bar (`B5.i_next[k]`, +1 tick). Stop = `or_low` (default; the brief's spec) or `close - 0.5 x ATR14` (`atr`), both
  at least `min_stop_pts` (MNQ 6 / MES 4 pts) below the signal close; `none` = the published rule (no protective stop,
  added as a diagnostic). Exit after `hold_min` = 75 one-minute bars from the fill (time exit), at the stop, or flat 15:55.
  One trade per day (max_trades 1); `max_trades 2` places every qualifying bar (the engine re-arms after an exit) and the
  daily loss stop halts the day after a losing first trade.
- No shorts (published OOS shorts -2.16 / -3.45 pts). Session: entries in [09:55, 11:35) so the bar starting 11:25 can fill
  at 11:30; flat 15:55. Lucid risk block per micro: daily_loss_stop = {MNQ 40, MES 35} x dls_mult (1.0),
  daily_profit_stop = {MNQ 60, MES 50} x dps_mult (2.0); with one trade per day these never bind.
- Optional gates (independent-filter tests): `trend_filter='sma200'` = trade only when prev_close > SMA200 of daily RTH closes;
  `skip_vvg=True` = skip "big days" where |gap| and |first-30-min return| are both >= their expanding 2/3-quantile
  (OHLC-only VVG, arXiv 2605.11423). r30 is the 09:59 close, known at 10:00, which is when the first signal (09:55 bar) fires.
- Sensitivities: `delay=1` (order at `B5.i_next[k+1]`), `--slip 2` (two ticks per side).
- Gold (MGC): OR 08:20 for 25 min, signals from 08:45, last entry 10:30, flat 13:25, ATR on 08:20-13:30 daily bars.

Defaults (`PARAMS`): or_minutes 25, hold_min 75, trend_filter none, stop_mode or_low, stop_atr 0.5, last_entry 11:30,
max_trades 1, skip_vvg False, flat 15:55, dls_mult 1.0, dps_mult 2.0, delay 0.

## Replication check against the paper (MNQ, default spec)
Gross pts per trade (after slippage, before commission) by year: 2023 +2.0 (paper +2.43), 2024 +5.7 (paper +7.04),
2025 -2.9 (paper +15.05 for Jan-Aug 2025; our Jan-Aug 2025 is +$1,110 on 99 trades, i.e. about +4 pts, the losing stretch
is Sep-2025 onwards), 2026 -2.8. Trade frequency 233 / 448 sessions (52%; paper 447 / 947 = 47%). Exit mix 201 time exits
(+$42 avg) vs 32 OR-low stops (-$316 avg = -158 pts): the stop that the brief added to the published rule is wide enough to
fire only on crash mornings, and those 32 trades cost more than the 201 time exits make.

## Headline results (per micro, after costs)

Default spec (OR-low stop, hold 75, no gates):

| contract | period | trades | net $ | win | avg $ | PF | Sharpe | maxDD intra | pos days | pos months |
|---|---|---|---|---|---|---|---|---|---|---|
| MNQ | MAIN | 233 | -1,619 | 57.5% | -7.0 | 0.91 | -0.41 | -4,405 | 57% | 43% |
| MNQ | PRIOR | 213 | +1,567 | 52.6% | +7.4 | 1.16 | 0.59 | -1,670 | 53% | 42% |
| MES | MAIN | 250 | +654 | 55.6% | +2.6 | 1.08 | 0.35 | -1,115 | 56% | 38% |
| MES | PRIOR | 218 | +504 | 49.1% | +2.3 | 1.10 | 0.35 | -920 | 49% | 42% |
| MGC | MAIN | 294 | -5,300 | 46.6% | -18.0 | 0.75 | -1.33 | -7,191 | 47% | 43% |
| MGC | PRIOR | 235 | -1,266 | 43.8% | -5.4 | 0.82 | -0.91 | -1,782 | 44% | 25% |

Published rule exactly (stop_mode none = pure time exit; one reasoned change, applied to both contracts and both periods):

| contract | period | trades | net $ | win | avg $ | PF | Sharpe | maxDD intra | pos days | worst day | largest day share |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MES | MAIN | 250 | +1,092 | 56.8% | +4.4 | 1.14 | 0.58 | -1,030 | 57% | -347 | 26% |
| MES | PRIOR | 218 | +730 | 51.4% | +3.3 | 1.14 | 0.49 | -992 | 51% | -306 | 54% |
| MNQ | MAIN | 233 | -326 | 57.9% | -1.4 | 0.98 | -0.09 | -3,627 | 58% | -888 | n/a |
| MNQ | PRIOR | 213 | +2,250 | 53.5% | +10.6 | 1.25 | 0.85 | -1,490 | 54% | -277 | 29% |

Per year (net $ per micro): MES no-stop 2023 +336 / 2024 +393 / 2025 +562 / 2026 +531 (positive every year, gross 0.8-1.3
MES pts per trade, i.e. about 1.5-2x the 0.76-pt cost); MES spec 2023 -7 / 2024 +510 / 2025 +152 / 2026 +503; MNQ spec
2023 +219 / 2024 +1,348 / 2025 -902 / 2026 -717; MNQ no-stop 2023 +511 / 2024 +1,738 / 2025 -1,185 / 2026 +859.

Validation targets from the brief: positive in each of 2023/2024/2025/2026 -> MNQ fails (2025, 2026), MES passes only
without a stop; >= 30 trades/year -> pass (74-144); gross per trade >= 4 MNQ pts / 2.8 MES pts -> FAIL on both
(MNQ -2.8 on MAIN, MES +0.8 to +1.1); PRIOR PF >= 1.0 -> pass.

Sensitivities (PF MAIN / PRIOR): MNQ spec delay=1 0.93 / 1.16, slip=2 0.90 / 1.14, max_trades=2 0.99 / 1.25 (276 / 261
trades); MES spec delay=1 1.06 / 1.11, slip=2 1.00 / 0.99, max_trades=2 1.05 / 1.10; MES no-stop delay=1 1.12 / 1.14,
slip=2 1.06 / 1.03, hold 60 1.27 / 1.09, hold 120 1.06 / 1.14. The one-bar delay does not hurt (no bar-boundary artefact);
two ticks of slippage remove most of the MES edge, which says the edge is about one tick in size.

## Grid (24 combos: hold {60,75,120} x trend {none,sma200} x stop {or_low,atr} x skip_vvg {F,T}; `grid_MNQ.csv`, `grid_MES.csv`)
- MNQ MAIN: 1 / 24 combos profitable (hold 60 + atr stop, PF 1.01, +$122); median PF 0.95, best Sharpe 0.03. MNQ PRIOR:
  24 / 24 profitable, PF 1.13-1.36, best hold 120. Rank correlation MAIN vs PRIOR 0.15. No cell is Lucid-recommended.
- MES MAIN: 23 / 24 profitable, median PF 1.08, best hold 60 + atr stop (PF 1.24, +$1,730, Sharpe 0.90) which is PF 1.06 on
  PRIOR; MES PRIOR 24 / 24 profitable, median PF 1.11, best hold 120. Rank correlation -0.13: the hold length that wins on one
  period loses on the other, so the plateau is "any hold 60-120 is roughly PF 1.0-1.2 on MES", not a peak.
- Independent-filter tests: `sma200` lowers PF in 11 / 12 MNQ cells and 12 / 12 MES cells on MAIN (trade count 87%);
  `skip_vvg` keeps only 60-70% of trades and lowers MAIN PF in 11 / 12 MNQ cells and 12 / 12 MES cells while raising PRIOR PF
  in most cells. Neither gate passes the "PF and net/maxDD both improve on both periods with >= 70% of trades" rule; both off.
- `atr` stop (0.5 x ATR14 below the signal close) beats `or_low` in 10 / 12 MNQ and 12 / 12 MES MAIN cells; no stop beats
  both (see above). The stop converts what the time exit would have partially recovered into a full loss.

## Diagnostics (MES, published rule / no stop, MAIN)
- Hour: 10:00-10:59 entries 218 trades +$524 (avg +2.4), 11:00-11:30 entries 32 trades +$569 (avg +17.8, 62% win): the late
  breakouts (after a 10:00-11:00 consolidation) carry most of the per-trade edge; the 09:55-bar signal that fills at 10:00
  (a release minute) is the bulk of the sample and roughly break-even.
- Weekday: Mon +$362, Tue +$177, Wed -$69, Thu +$125, Fri +$497. Nothing to filter.
- VIX (lag 1): <15 +$42 (n 26), 15-20 +$1,158 (n 172), 20-25 +$386 (n 39), 25-35 -$174 (n 11), >35 -$320 (n 2). The rule
  loses on the crash mornings (2025-04-08/09, 2026-06-10, 2026-07-02 are four of the five worst days) and makes its money in
  the normal 15-25 VIX tape; too few high-VIX trades to justify a gate.
- Months: 13 / 21 positive; Sep-Dec 2025 all negative (-$785 in total), Jun-Aug 2026 -$783; best Feb-25 +$554, Mar-25 +$474,
  Apr-26 +$413. Max 3 consecutive losing days, 6 consecutive losing trades. Largest day 26% of net.
- MAE / MFE: median MAE -9.2 pts, median MFE +11.1 pts; winners' median MAE -5.1, losers' median MFE +5.9. The 75-minute
  hold rides a ~10-pt two-sided excursion for a ~1-pt net drift: this is a coin flip with a slight positive drift, not a
  breakout that runs.
- MNQ MAIN (spec): all of the loss is in the 32 OR-low stops (-$10.1k) vs +$8.5k from the 201 time exits; by VIX only the
  15-20 bucket is positive (+$894, n 159); worst days 2026-06-10 (-$888) and 2026-06-11 (-$743) are the June-2026 sell-off.

## Lucid 50K Flex Monte Carlo (MAIN daily P&L, constant micros, `lucid_scan_*.csv`)
- MES no-stop: best 5 micros -> pass rate 0.39, P(first payout) 0.05, expected net per evaluation -$50 (bootstrap lower bound
  -$146 = the fee; zero-edge control -$146); median 37 trading days to pass. Not recommended. At 10+ micros the pass rate falls
  further because the -$300 days x micros eat the $2,000 trailing floor before the $3,000 target is reached.
- MES spec: 5 micros, pass 0.37, P(first payout) 0.00, expected net -$146. MNQ spec: 5 micros, pass 0.28, expected net +$72
  vs zero-edge control +$154 (worse than noise). MNQ no-stop: 5 micros, pass 0.29, expected net +$172 vs control +$271.

## Attempts log
1. Spec defaults (OR-low stop, hold 75) on MNQ / MES / MGC, MAIN and PRIOR: MNQ replicates the paper's 2023-2024 numbers and
   its Jan-Aug 2025 sign, then loses from Sep-2025; MES marginally positive both periods; MGC dead both periods.
2. Sensitivities delay=1, slip=2, max_trades=2 (one-loss rule): no sign flips; MES dies at 2 ticks; max_trades=2 adds ~20%
   trades at the same PF on MES and improves MNQ PRIOR (1.25) but not MAIN (0.99).
3. 24-combo grid on MNQ and MES, MAIN and PRIOR: MNQ MAIN 1 / 24 profitable; MES plateau PF 1.0-1.24 with no stable optimum;
   both gates (SMA200, VVG skip) reduce PF on MAIN; rejected.
4. Reverted the brief's added stop to the published no-stop rule (one change, reason: the OR-low stop only fires on crash
   mornings and converts partial recoveries into full-sized losses, exit-reason table): improves both contracts on both periods
   (MES PF 1.08 -> 1.14 MAIN, 1.10 -> 1.14 PRIOR; MNQ 0.91 -> 0.98, 1.16 -> 1.25). Hold 60 / 120 around it: no plateau.
5. Lucid scan on all four (contract x stop) configurations: nothing recommended; MES expected net per evaluation is negative.

## Verdict: marginal (MES) / dead (MNQ, MGC)
The published MNQ result is real for 2023-2024 and Jan-Aug 2025 (the paper's window) and has not held since: MNQ is PF 0.91
on MAIN with every one of 24 grid cells at or below PF 1.01. MES carries a small, year-consistent drift (PF 1.14 on both
periods without a stop, positive in each of 2023-2026) but it is about one tick per trade (gross 0.8-1.3 MES pts vs 2.8
required), vanishes at two ticks of slippage, and cannot pass a Lucid evaluation at any size (expected net per evaluation
-$50, not distinguishable from the zero-edge control). Not a candidate for the account on its own; at most a low-weight
diversifier if a portfolio needs a long-only, time-exit leg on MES. The stop axis is the only "fixable flaw" and it has
already been fixed here; the gates do not help.
