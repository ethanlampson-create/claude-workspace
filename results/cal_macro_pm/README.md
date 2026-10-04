# cal_macro_pm - Macro-day gated last-half-hour momentum (family calendar_seasonal_structural)

Module: `strategies/cal_macro_pm.py`; shared flags helper: `strategies/_cal_flags.py` (first use; unblocks the other
calendar candidates). Research: `research/families/calendar_seasonal_structural.md`, spec section 3 of
`research/specs/calendar_seasonal_structural.md` (Gao-Han-Li-Zhou, JFE 2018, conditional on CPI/NFP/FOMC days).
Periods: MAIN = 2025-01-01..2026-09-30, PRIOR = 2023-01-01..2024-12-31, long history 2015-01-01..2024-12-31.
All numbers per ONE micro contract after costs ($1.30 RT + 1 tick slippage per side on market/stop fills).

**Verdict: dead** (walk-forward OOS 2025-26 on MNQ: 234 trades, PF 0.95, net -$498). The macro-day *contrast* the paper
reports is real in this data (macro days beat non-macro days in every period on both contracts), but the gated leg alone
is a ~+$8/trade, ~35 trades/yr proposition that does not survive the honest yardstick, and the 2025-26 result is largely
the long-biased tape plus 14 FOMC afternoons.

## Rules as implemented (all ET; a 1-min bar with tod=T covers [T, T+1))
- `c(HH:MM)` = close of the last bar with `HH:MM-5 <= tod < HH:MM` (normally the HH:MM-1 bar; the CFD feed omits tick-less
  minutes, 1-2 minute gaps mostly 2013-2017). `i(HH:MM)` = first bar with `HH:MM <= tod < HH:MM+5` (normally the HH:MM bar).
- `prev_close` = last RTH close (tod < 16:00) of the prior session; `ATR14d = daily_atr(df1, 14, rth_only=True)` (Wilder, shifted).
- Flags (`_cal_flags.flags`): `r0830` = two-bar range of the 08:30/08:31 bars; `rel0830 = r0830 / rolling median of the prior
  60 sessions` (min_periods 48); `macro0830 = rel0830 >= k0830 (3.0)`, known at 08:32. `r1400/rel1400/macro1400` likewise on
  14:00/14:01 (known 14:02). `fomc` = hard-coded statement dates (every 2013-2026 date re-verified on federalreserve.gov on
  2026-10-04; 2025-08-22 notation vote excluded; March 2020 excluded). `macro_day = macro0830 | fomc`. `witching` = 3rd Friday
  (or the Thursday before when Friday is closed) of Mar/Jun/Sep/Dec. Calendar arithmetic runs on "market open" sessions
  (>= 60 RTH bars) because Feb-Jul 2023 the feed prints only ~180 RTH bars/session; thin sessions are skipped by the engine.
- Signal per session d: `ref_px` = prev_close (default) | 09:30 open | c(08:30) (pre-release); `r1 = c(10:00)/ref_px - 1`;
  `r12 = c(15:30)/c(15:00) - 1` (c(15:30) is the close of the **15:29** bar). `sig = sign(r1)` (thresh_atr 0 = sign only, as
  published); variant `r1_r12` requires sign(r12) == sign(r1); `always_long` = +1 (control). `day_ok`: `macro_only` ->
  macro_day; `all`; `non_macro`; `fomc_minutes_only` -> macro1400. Quad-witching skipped (`skip_witching`). ATR must be non-NaN.
- Entry: market at the open of `i(15:30)` (+1 tick) with `stop_pts = stop_atr x ATR14d` (0.4 default). No target, no re-entry,
  one trade per day. Exit: stop, or forced flat at the open of the first bar >= 15:58 (28-minute hold).
- Defaults (`PARAMS` = published rule restricted to macro days): ref prev_close, variant r1, days macro_only, entry 15:30,
  flat 15:58, thresh_atr 0, stop_atr 0.4, skip_witching True, skip_fomc False, k0830 3.0, k1400 3.0, median_lookback 60.
- GRID (16): ref {prev_close, pre0830} x days {macro_only, all} x variant {r1, r1_r12} x stop_atr {0.3, 0.6}.

Look-ahead audit (scratch script, every MAIN trade on MES and MNQ): entry bar tod == 15:30 and fill == that bar's open + 1
tick; side == sign(c(10:00) - prev_close) recomputed from raw bars; c(15:30) comes from a bar with tod < 15:30 (the 15:30
bar itself is never read by the signal); every exit <= 15:58. Flags self-check (scratch): 8 FOMC days per year 2013-2025
(7 in 2020), 4 witching and 12 opex per year, 23-57 macro mornings per year (36 in 2025, 28 in 2026-01..09); the four 2025
FOMC dates show rel1400 = 6.1 / 7.0 / 2.8 / 6.9 (so the 14:00 detector alone would miss some statements: the table is used).

## Headline results, default rule (days = macro_only)

| contract | period | trades | net $ | win | avg trade | PF | Sharpe | maxDD intra | pos months |
|---|---|---|---|---|---|---|---|---|---|
| MNQ | MAIN 2025-26 | 64 | +566 | 53% | +8.8 | 1.16 | 0.30 | -1,254 | 11/21 |
| MNQ | PRIOR 2023-24 | 81 | +573 | 54% | +7.1 | 1.19 | 0.37 | -830 | 10/24 |
| MNQ | 2015-2024 | 403 | +549 | 48% | +1.4 | 1.05 | 0.09 | -2,521 | - |
| MES | MAIN 2025-26 | 71 | +75 | 47% | +1.1 | 1.03 | 0.07 | -931 | 9/21 |
| MES | PRIOR 2023-24 | 84 | +603 | 51% | +7.2 | 1.33 | 0.66 | -373 | 10/24 |
| MES | 2015-2024 | 433 | -530 | 44% | -1.2 | 0.94 | -0.13 | -2,043 | - |

Walk-forward (the yardstick; `python3 -m backtest.final_select --ids cal_macro_pm --jobs 2 --wf_start 2022-01-01 --max_combos 16`,
MNQ, IS 12m / OOS 3m, selection by IS Sharpe, min 30 IS trades): **OOS 2025-01..2026-09 = 234 trades, net -$498, PF 0.946,
Sharpe -0.22, 45% positive days, 11/21 positive months, maxDD intra -$1,686.** Whole OOS span 2023-2026: 400 trades, PF 0.935,
net -$936. Lucid 50K Flex on the OOS stream: best size 5 micros, pass rate 0.033, pass-within-21 0.033, P(first payout) 0,
expected net -$146 per evaluation = the fee, lower bound -$146, zero-edge control -$146 -> **not recommended** at any size.
Caveat on the WF mechanics: the 30-trade IS minimum eliminates the `macro_only` cells in many folds (35-45 trades/yr; the
`r1_r12 x macro_only` cells have ~20/yr), so 6 of 15 folds were forced onto `days='all'` (OOS PF 0.63-1.00 there) and the
folds that did pick `macro_only` were +$568 / -$121 / +$283 / +$368 / -$19 / -$335 (net +$744 on 50 trades). Even on the
fixed defaults the MAIN PF 1.16 on 64 trades is well inside noise (one trade, 2026-07-29, is +$731 = 129% of MAIN net).

## The contrast (the finding): PF / trades / mean per trade by day set (`contrast.csv`)

| contract | period | macro_only | all | non_macro | always_long (days=all, control) |
|---|---|---|---|---|---|
| MNQ | 2025-01..2026-09 | 1.16 / 64 / +8.8 | 0.97 / 424 / -1.2 | 0.93 / 360 / -3.0 | **1.18 / 424 / +7.1** |
| MNQ | 2015-2024 | 1.05 / 403 / +1.4 | 0.82 / 2336 / -3.9 | 0.75 / 1933 / -4.9 | 0.83 / 2342 / -3.5 |
| MES | 2025-01..2026-09 | 1.03 / 71 / +1.1 | 0.83 / 424 / -4.2 | 0.78 / 353 / -5.2 | 0.98 / 424 / -0.4 |
| MES | 2015-2024 | 0.94 / 433 / -1.2 | 0.68 / 2303 / -5.3 | 0.60 / 1870 / -6.2 | 0.69 / 2317 / -5.0 |

Reading: (1) the published unconditional effect (`all`) is dead net of micro costs in every period on both contracts (the
paper's ~2.6 bp/day is ~$5-8 per micro, below the ~$4 costs plus slippage on a 28-minute hold, and the sign rule is only
40-49% right here). (2) Macro days beat non-macro days everywhere: MNQ 2015-24 +1.4 vs -4.9 per trade, 2025-26 +8.8 vs -3.0;
MES likewise. The amplification direction the paper documents is in the data. (3) But the gated leg is not an edge of the
size needed: PF 1.05 over ten years on MNQ, 0.94 on MES. (4) **The always_long control is +$2,998 / PF 1.18 on MNQ 2025-26**
(the long-biased tape): the MNQ 2025-26 macro_only result (+$566) is *smaller* than simply buying every 15:30 and must be
read against it; the 40 macro-day longs made +$728 and the 24 shorts -$162. always_long on macro days only is PF 1.28 (MNQ)
and 1.62 (MES) in 2025-26 but 0.72 / 0.67 on 2023-24 and 0.86 / 0.78 on 2015-24: the tape, not a day effect.
(5) The 2025-26 macro_only P&L is the FOMC table: 14 FOMC-day trades +$1,696 (11 winners) vs 50 08:30-macro trades -$1,130
on MNQ (MES: +$952 vs -$877). `fomc_only` (k0830 = inf) is PF 6.7 / 14.9 on 14 trades in 2025-26 but PF 0.79 / 0.74 on
75 trades 2015-24 and 0.55-0.60 in 2015-19: a 14-trade hot streak, not a rule. `skip_fomc=True` turns 2025-26 macro_only
negative (MNQ PF 0.65, MES 0.58). (6) `fomc_minutes_only` (14:00 detector): MNQ 2015-24 PF 1.18 / 168 trades, 2023-24 1.72,
but 2025-26 0.74; MES mixed. (7) `r1_r12` on macro days is the most stable cell historically (MNQ 2015-24 PF 1.24 / 215
trades, MES 1.10 / 232; 2023-24 1.35 / 1.69) yet 0.98 / 0.82 in 2025-26 on 33-39 trades - consistent with the paper's note
that the effect weakened after 2020, and too few trades to pass anything.

## Grid (16 combos x MAIN/PRIOR, `grid_MNQ.csv`, `grid_MES.csv`)
- MNQ: rank correlation of cell PF between MAIN and PRIOR 0.61; 7/16 cells positive on both, all seven `macro_only`. The
  best MAIN cell is `pre0830 / macro_only / r1 / 0.3` (PF 1.66, +$1,791, Sharpe 1.02) with PRIOR PF 1.20; the default
  `prev_close / macro_only / r1` is PF 1.23-1.30 MAIN, 1.14-1.24 PRIOR. Every `days=all` cell is PF <= 1.00 on PRIOR.
  `pre0830` reference helps MAIN (ref before the release so r1 includes the release jump) but adds nothing on 2015-24
  (PF 1.07 vs 1.05) and hurts MES MAIN (0.82-1.01). stop_atr 0.3 vs 0.6 is immaterial (4-6 stops per period).
- MES: rank correlation -0.11; 2/16 cells positive on both (`prev_close / macro_only / r1 / 0.6` PF 1.11 / 1.30 and
  `pre0830 / macro_only / r1 / 0.6` 1.01 / 1.01). MES is noise.

## Diagnostics (MNQ, defaults, MAIN; `backtest.report`)
- 64 trades: 60 flat-at-15:58 (+$32 avg, 57% win) and 4 stops (-$335 avg): the hard 0.4-ATR stop (~$400/micro) is hit only
  on the 08:30 crash-type days (2025-04-07, 2025-01-30, 2025-02-28, 2025-11-20) and costs 70% of the gross.
- Longs 40 / +$728 (57% win), shorts 24 / -$162 (46%). Wednesdays (FOMC day) 25 trades / +$1,349; Thursdays 13 / -$524.
- Positive days 34 / negative 30; avg +$121 / -$118: a coin flip with a slightly positive mean. Largest day +$731 (2026-07-29,
  FOMC short) = 129% of MAIN net; 2026-07 alone is +$1,164 vs +$566 total. 2025 calendar year: 40 trades, -$314.
- VIX: all buckets flat except 20-25 (+$717 on 12 trades); >25: 6 trades, -$612 (the stops).
- Daily P&L lives 15:30-15:58 when every current survivor is flat, so the correlation argument from the spec holds, but a
  leg with expected +$8/trade on 35 trades/yr contributes ~$300/yr per micro: not worth a portfolio slot.

## What was tried and why it failed
1. Default rule on MES and MNQ, MAIN/PRIOR (table above): positive but thin; MNQ chosen as primary (positive on both periods).
2. Day-set contrast with controls (`contrast.csv`, 11 configs x 5 periods x 2 contracts): macro > non-macro everywhere,
   `all` dead everywhere, always_long control positive in 2025-26 on MNQ -> the 2025-26 macro_only result is tape + FOMC streak.
3. 16-combo grid: MNQ plateau exists only inside `macro_only`; the best cell (`pre0830`) is period-specific; MES has no plateau.
4. Walk-forward OOS 2025-26 PF 0.95 on 234 trades, Lucid -$146 at all sizes = the zero-edge control. Gate failed.
5. Not pursued (would be in-sample curve fitting on <= 64 trades): dropping shorts, dropping Thursdays, VIX gates, keeping
   only FOMC days (14 trades), stop tuning.

## Verdict
**dead.** Walk-forward OOS 2025-26 PF 0.946 < 1.03 (234 trades). The honest finding for the family is the contrast itself:
the macro-day gate roughly moves last-half-hour momentum from clearly negative to break-even per micro, which is useful as a
*filter* on other afternoon ideas (or as a reason not to fade the 15:30 move on macro days) but is not a leg. The flags module
(`strategies/_cal_flags.py`, verified FOMC table 2013-2026, 08:30/14:00 event detectors, opex/witching/totm/payday/santa/
holiday_next) is the reusable output for the other calendar candidates.
