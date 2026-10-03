# mr_ibfail - Initial-balance failed-breakout fade (Market Profile / tradingstats ES-NQ statistics)

Family: intraday_mean_reversion (research: `research/families/intraday_mean_reversion.md`, item 15, priority 5).
Module: `strategies/mr_ibfail.py`. Verdict: **dead** (MNQ MAIN PF 1.04 at best with defaults, does not hold on PRIOR;
MES negative on both periods; no plateau anywhere in the grid).

## Rules as implemented
- IB = high/low of the 1-min bars 09:30..10:29 ET (`opening_range(df1, '09:30', ib_minutes=60)`, used only after `i_end`).
  ATR = 14-day RTH daily ATR, lagged (`daily_atr`). Skip the day if ATR is NaN or IB range > `max_ib_atr` (1.5) x ATR.
- Decision bars: 5-min RTH bars (`resample(df1, 5, rth_only=True)`) from 10:30. All orders go at the bar's `i_next`.
- BREAK: first 5-min bar at/after 10:30 and before `break_deadline` (11:30) with high > IB_high (up) or low < IB_low
  (down); both in one bar -> the side farther from the bar's open. Only the first break of the day is eligible.
  `break_mode='close'` (follow-up option, not default) additionally requires the break bar to close outside the IB.
- Extreme = running max high / min low from the break bar through the failure bar.
- FAILURE: one of the next `fail_window`/5 bars (default 6 bars = 30 min) starting before `fail_deadline` (12:00) that
  closes back inside the IB (up: close < IB_high; down: close > IB_low). `min_break_atr` (follow-up option, default 0)
  requires the extreme to be at least that many ATR beyond the edge.
- ENTRY: market at the open of the 1-min bar after the failure bar; failed up-break -> short, failed down-break -> long.
  `sides` = both | long | short.
- STOP: 1 tick beyond the extreme (absolute `stop_px`); if that is farther than `stop_cap_atr` (0.25) x ATR from the
  failure bar's close (entry proxy), the stop is instead `stop_pts` = cap relative to the fill. ~7-10% of trades are capped.
- TARGET: `tgt='mid'` IB midpoint, `tgt='far'` the opposite IB edge (absolute `tgt_px`).
- TIME EXIT: `Intents.exit_at` at the first bar >= `exit_time` (13:00); `set_session(09:30, exit_time, flat=15:55)`;
  `max_trades_day = 1`.

Defaults (published): ib_minutes 60, break_deadline 11:30, fail_window 30, fail_deadline 12:00, stop_cap_atr 0.25,
tgt mid, exit_time 13:00, flat 15:55, max_ib_atr 1.5, sides both, max_trades 1, break_mode touch, min_break_atr 0.

Sanity checks (`day_signals()` dump): ~250 signals per period per contract, 45-50% longs, median stop distance 0.10 ATR,
median target distance 0.14-0.17 ATR, 62-68% of failures occur on the very next 5-min bar after the break, 40-45% of
breaks happen on the 10:30 bar. Trade samples checked by hand (entry 1 min after the failure bar, stop at extreme +/- 1 tick).

## Metrics (per 1 micro, after costs, default params)

| contract | period | trades | net $ | win | PF | avg trade | maxDD intra | Sharpe | pos days | pos months |
|---|---|---|---|---|---|---|---|---|---|---|
| MES | MAIN 2025-01..2026-09 | 250 | -2085 | 0.364 | 0.70 | -8.3 | -2274 | -1.72 | 0.36 | 0.24 |
| MES | PRIOR 2023-24 | 281 | -955 | 0.406 | 0.79 | -3.4 | -1034 | -1.14 | 0.41 | 0.38 |
| **MNQ** | **MAIN** | **253** | **+459** | **0.383** | **1.04** | **+1.8** | **-1941** | **0.17** | **0.38** | **0.48** |
| MNQ | PRIOR | 207 | -1430 | 0.362 | 0.79 | -6.9 | -1484 | -0.99 | 0.36 | 0.21 |

MNQ MAIN: avg win $131 / avg loss -$79, worst month -$702, best month +$938 (2026-08), largest-day share 89% of a tiny net.
Lucid scan (MNQ defaults, MAIN): best 5 micros -> pass rate 0.22, P(first payout) 0.04, expected net per eval -$79;
10 micros pass 0.18 / exp. net -$1. Not an evaluation vehicle at any size.

## Diagnostics (MNQ MAIN, `report_MNQ_main_defaults.json`; MES in `report_MES_main_defaults.json`)
- Exit reasons: stop 142 (56%, avg -$81), target 89 (35%, avg +$133), time exit 22 (avg +$7). Median hold 16 min.
  The published stop (1 tick beyond a 1-bar poke) is only ~0.10 ATR; it is noise-sized and is hit before the midpoint
  target 56% of the time. Winners' median MAE is 15 pts vs losers' median MFE 14 pts: the two cohorts are not separable.
- By entry hour: 10:xx entries (66% of trades) -$1,109, 11:xx +$1,568 on MAIN; on PRIOR the 11:00-11:30 bucket is
  -$958, so the "late failures are better" pattern is noise, not a filter.
- By weekday: Wednesday is the worst day on all four contract/period combinations (MNQ MAIN -$1,187, 26% win), in line
  with the research note that Wednesday has the highest double-break rate; Thursday best. The other days flip sign
  between periods. Excluding Wednesday alone would be a single-weekday filter on ~50 trades: not adopted.
- By side: longs avg +$2.4, shorts +$1.3 on MAIN; both negative on PRIOR (shorts -$1,123, longs -$307). The long
  bias from the research (downside breaks fail more) shows up as "less bad", not as an edge.
- VIX: 15-20 bucket (64% of trades) loses on both contracts; 20-35 wins on MNQ MAIN only. >35: 4 trades, -$654.
- Months: 10 of 21 months positive on MNQ MAIN; 2026-07/08 (+$1,733) carry the whole net; 2025-04 and 2026-01 -$500/-$700.
- Max 10 consecutive losing trades, 6 consecutive losing days.

## Grid (prescribed, 24 combos, MAIN + PRIOR; `grid_main_MNQ.csv`, `grid_main_MES.csv`)
- MNQ MAIN: 22/24 profitable but all PF 0.96-1.22; best fail_window 15 / mid / 0.25 / long (99 trades, PF 1.22, Sharpe
  0.59, pass rate 0.52 at the Lucid scan but expected net per eval -$146). MNQ PRIOR: 2/24 profitable; the top-ranked
  MAIN combos have PRIOR PF 0.69-0.95. Rank correlation between the periods -0.70: whatever moves the MAIN ranking is
  anti-persistent. fail_window 15 > 30 > 45 on MAIN but the opposite on PRIOR; tgt 'far' > 'mid' for both-sides on MAIN,
  reversed on PRIOR. stop_cap 0.25 vs 0.40 is nearly inert (the cap binds on < 10% of trades).
- MES MAIN: 2/24 profitable (both long/far/fail_window 15, PF 1.06-1.10, ~106 trades); MES PRIOR 7/24, all PF <= 1.10.
- The only points positive on both periods: MES long/far/fw15/cap0.25 (MAIN PF 1.10, +$351, 106 tr; PRIOR PF 1.08,
  +$173, 102 tr; Sharpe 0.28/0.21) and MNQ long/far/fw45 (MAIN 1.04 / PRIOR 1.05, Sharpe 0.11/0.14). Both are isolated
  spikes with negative neighbours (fw30 of the same family is negative on both contracts) and an avg trade of $2-3
  (< costs): not a plateau, not tradeable.

## Follow-ups (MNQ, both periods)
1. Prescribed ib_minutes x exit_time (`followup_MNQ.csv`): IB 30 min is far worse (PF 0.80 both periods, DD -$5k);
   exit 15:00 instead of 13:00 helps a little on both periods (MAIN PF 1.04 -> 1.09, PRIOR 0.79 -> 0.92) but PRIOR stays
   negative. Reason it helps: time-exits at 13:00 cut 22 trades that on average still drift toward the target.
2. Hypothesis "a 1-tick poke is not a breakout" (`followup2_MNQ.csv`): break_mode 'close' (break bar must close outside
   the IB) lifts MAIN to PF 1.14 (184 trades) but PRIOR stays 0.78; min_break_atr 0.1 cuts trades to ~50 and loses on
   both periods (the deeper the break, the more often it is a real trend day, exactly the double-breakout risk the
   research warns about); 0.2 leaves 11 trades. No fix.
3. Not tried (would be window-fitting without a stated reason): weekday or VIX-bucket filters, per-side stop sizes,
   hour-of-entry filters (the hour pattern already failed on PRIOR).

## Attempts log
1. Faithful implementation; first run produced trades on both contracts immediately. Verified the signal table by hand
   (break/failure bars, extreme, capped stops, target levels) and that the engine fills 1 min after the failure bar.
2. Prescribed grid on MES and MNQ, MAIN and PRIOR (48 runs each).
3. Prescribed follow-up (ib_minutes x exit_time) and one reasoned hypothesis (confirmed-close breaks, minimum break
   depth) on MNQ, both periods. Added `break_mode` and `min_break_atr` params with defaults equal to the published rule.

## Verdict
**Dead.** The tradingstats statistics (34% of first IB breaks fail, 56% of breakouts retrace half the IB) are
descriptive base rates; once the fade is traded with the published tiny stop (1 tick beyond the extreme, ~0.10 ATR) and
a midpoint target, the stop is hit 56% of the time and the payoff ratio (~1.6) is not enough: avg trade +$1.8 on MNQ
MAIN, negative everywhere else. Nothing in the 24-combo grid or the follow-ups holds on 2023-24 with a plateau. The
best-looking MAIN configs (MNQ fail_window 15) are the worst on PRIOR. Not a portfolio leg either (Sharpe 0.17, DD
-$1,941 per micro, 38% positive days). Engine notes: none found.
