# orb_dbl: ORB failed-breakout / double-break reversal (second break of the 30-min range)

Family: orb_session (research/families/orb_session.md section 3.8). Module: `strategies/orb_dbl.py`. Verdict: **marginal**.

## Rules as implemented (all times ET)
- 5-min RTH bars from the 1-min feed. Opening range (OR) = high/low of [09:30, 09:30 + or_minutes). rng = OR width.
  ATR = Wilder ATR(14) of daily RTH bars, shifted one day. Skip the day if ATR NaN, rng < 0.1 ATR or rng > 0.8 ATR.
- State machine on closed 5-min bars starting at the OR end and before `last_entry`:
  1. FIRST BREAK: first bar with close > or_high (up) or close < or_low (down). E = running max high / min low from that bar until the failure bar.
  2. FAILURE: a later bar closing back inside [or_low, or_high] (skipped when require_fail = False).
  3. SECOND BREAK: after the failure, the first bar closing beyond the OPPOSITE side. Signal bar; entry = market at the open of the
     next 1-min bar (i_next, +1 tick slippage). Strict reading: with require_fail = True a bar closing straight through from one side
     to the other is not a signal (an inside close is still required); this case is rare, so require_fail True/False differ by 0-1 trades.
  4. One trade per day; no second break before last_entry -> no trade.
- Chase filter: skip if the signal close is more than skip_ext (0.5) x rng beyond the broken side.
- Stop: 'extreme' = E (failed extreme) or 'mid' = OR midpoint, distance from the entry capped at max_stop_atr (0.6) x ATR (cap applied
  from the actual fill as stop_pts). Target = fill +/- tgt_frac x rng. Exits: stop, target, forced flat 15:55. No trailing.
- Session: entries in [09:30 + or_minutes, last_entry + 5 min); max_trades_day = 1. Look-ahead: all states update at 5-min bar closes,
  the order is placed at i_next; nothing from the entry bar or later is used.

Spec defaults (PARAMS): or_minutes 30, require_fail True, stop_mode 'extreme', max_stop_atr 0.6, tgt_frac 0.75, skip_ext 0.5, last_entry 12:30.
Final chosen config: **or_minutes 30, stop_mode 'mid', tgt_frac 0.5, last_entry 13:30** (everything else default), contract **MNQ**.

## Metrics per micro contract (after costs)

| period | contract | params | trades | net $ | win | PF | avg trade | max DD intraday | Sharpe | pos days | worst day |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MAIN 2025-01..2026-09 | MNQ | spec defaults | 50 | +1,703 | 68% | 1.41 | 34.1 | -947 | 0.74 | 68% | -704 |
| PRIOR 2023-01..2024-12 | MNQ | spec defaults | 57 | -1,106 | 56% | 0.77 | -19.4 | -2,288 | -0.62 | 56% | -367 |
| MAIN | MES | spec defaults | 68 | -951 | 56% | 0.76 | -14.0 | -1,971 | -0.68 | 56% | -486 |
| PRIOR | MES | spec defaults | 75 | -194 | 61% | 0.92 | -2.6 | -1,078 | -0.22 | 61% | -185 |
| **MAIN** | **MNQ** | **final (mid, 0.5, 13:30)** | **71** | **+2,621** | **66%** | **1.67** | **36.9** | **-728** | **1.40** | **66%** | **-428** |
| **PRIOR** | **MNQ** | **final** | **72** | **+377** | **57%** | **1.13** | **5.2** | **-816** | **0.32** | **57%** | **-203** |
| MAIN | MES | final | 94 | -187 | 53% | 0.94 | -2.0 | -930 | -0.18 | 53% | |
| PRIOR | MES | final | 97 | -373 | 51% | 0.83 | -3.8 | -767 | -0.60 | 51% | |

MAIN monthly (final, MNQ): 11 of 21 months positive; best 2026-06 +907 (35% of net), worst 2026-05 -433; largest day share 15%.
PRIOR: 2023 produced only 26 trades (26 signals in 12 months: the 2023 low-vol trend rarely double-broke the 30-min range by 13:30);
2024 46 trades. Sessions are complete in 2023 (20-23 per month), ranges are normal (median rng/ATR 0.3-0.55); it is a genuine signal drought.

## Lucid 50K Flex Monte Carlo (final config, MNQ, MAIN period; `results/orb_dbl/final_MNQ_lucid_scan.csv`)

| micros | pass rate | pass within 21 | P(first payout) uncond. | exp net / eval | bootstrap LB | zero-edge control | median days to pass |
|---|---|---|---|---|---|---|---|
| 5 | 45% | 9% | 18% | +174 | -146 | -146 | 43.5 |
| 10 | 44% | 17% | | +45 | -146 | -46 | 25 |
| 15-40 | 18-26% | 11-14% | | -84 | -146 | -146 | 18-21 |

Best by lower bound = 5 micros, **not recommended** (LB negative). P(breach before first payout | passed) = 61%. Monthly pass-within-21-sessions
rate is 0 for 14 of 19 start months (only 2025-03/04 and 2026-06 above 40%). The strategy makes ~3.4 trades/month x $37/micro: at 5 micros
that is ~$630/month expected, far too slow for a $3,000 target, and the eval clock (and the EOD trailing drawdown) eats it.

## Diagnostics (final config, MNQ MAIN; `report_MNQ_main_final.txt`)
- Exit reasons: 43 targets (+$146 avg), 20 stops (-$184 avg), 8 flats (~0). Mid stop makes the stop ~1.25x the target; with 66% wins
  that is +0.23 R expectancy. With the spec 'extreme' stop the geometry is inverted: median target only 0.5x the stop distance (MNQ
  median risk 195 pts vs target 98 pts; 24% of stops capped at 0.6 ATR), stops average -$415 and the 68% win rate barely covers them.
- Hour of entry: 10:xx +640 (10 trades), 11:xx +264 (29, 55% win), 12:xx +1,100 (15, 80%), 13:xx +617 (17). The 12:00-13:30 signals that the
  spec's 12:30 cutoff discards are the best hour, consistent with the research note that 30-min double breaks have a median 88-96 min
  between breaks.
- Weekday: Monday +1,118 (10 trades, 80%); Friday weakest +157 (11, 55%). With the spec defaults Fridays were -1,028: not stable, not used.
- Side: longs +1,641 (39), shorts +980 (32); both positive in the final config (shorts were negative with the spec stop).
- VIX regime (prior-day close): 15-20 +191 on 45 trades (56% win, essentially flat); 20-25 +1,037 (15, 80%); >25 +1,101 (6, 100%). The
  edge is concentrated in VIX > 20 (April 2025, June 2026). In the calm regime that dominates the sample the strategy is break-even.
- MAE/MFE median -35 / +52 pts; winners' MAE -20; losers' MFE +26 (losers do go 26 pts in favour first, i.e. ~half the target).
- Duration: median 29 min, 75th pct 112 min. Max 2 consecutive losing days, 3 consecutive losing trades.

## Grid (`grid_main_MNQ.csv`, `grid_main_MES.csv`: or_minutes x stop_mode x tgt_frac x require_fail = 24 combos, MAIN and PRIOR)
- MNQ MAIN: all 24 combos profitable, PF 1.36-1.78 (15-min range gives ~98 trades, PF 1.36-1.69; 30-min gives 50 trades, PF 1.38-1.78).
  MNQ PRIOR: **all 24 combos lose**, PF 0.66-0.99; the best is or30/mid/0.5 (PF 0.99). Rank correlation MAIN vs PRIOR ~0.
- MES: all 24 combos lose on PRIOR (PF 0.63-0.95); MAIN mixed (best 15-min/mid/1.0 PF 1.27, 123 trades; 30-min combos all <= 1.0). MES dead.
- require_fail True vs False: identical to within 1 trade (direct through-closes are rare and mostly caught by the chase filter).
- Second pass (`grid_pass2_MNQ.csv`, base or30/mid, tgt_frac x last_entry [12:00, 13:30]): last_entry 13:30 improves both periods
  (tgt 0.5: MAIN PF 1.67 / 71 trades, PRIOR PF 1.13 / 72 trades; tgt 0.75: MAIN 1.66, PRIOR 0.98). 12:00 cuts trades to 41-46.
  Extra check at 14:30 (tgt 0.5): MAIN PF 1.88 / 87 trades but PRIOR PF 0.96 / 90 trades. So MAIN is a broad plateau in the cutoff
  (12:00-14:30 all PF 1.55-1.88) while PRIOR hovers around 1.0 +/- noise; 13:30 is the one that holds the "PRIOR PF >= 1.0" rule.

## Attempts log
1. Spec defaults, MES and MNQ, MAIN and PRIOR: MNQ MAIN PF 1.41 (50 trades), everything else < 1.0. Low trade counts because close-based
   double breaks within 12:30 occur on only ~12% (30m) / ~24% (15m) of days, far below the wick-based 48-61% in the research.
2. Diagnosis: the 'extreme' stop is ~2 ranges away so target/stop ~0.5; the 0.6 ATR cap means single losses of -$400 to -$700 per micro.
   Grid: 'mid' stop with 0.5x target has the best PF and the smallest drawdown on MNQ in both periods -> adopted.
3. last_entry 13:30 (reason: median time between breaks on the 30-min range is 88-96 min, many second breaks land 12:30-13:30; the
   12:xx hour is the most profitable in the diagnostics) -> adopted. 14:30 tested once: better MAIN, worse PRIOR, not adopted.
4. Not tried (would be test-window tuning without a prior reason): weekday filter, VIX > 20 filter, long-only.

## Verdict: marginal
MNQ with mid stop / 0.5x target / 13:30 cutoff reaches the "PF >= 1.5 with >= 60 trades" bar on MAIN (1.67, 71 trades, Sharpe 1.4,
DD -$728 per micro) and just holds on PRIOR (1.13), but (a) every combo of the primary grid loses on 2023-24 and PRIOR is ~1.0 at best,
(b) ~3.4 trades per month is too slow for the $3k eval (median 43 sessions to pass, 9% pass within 21 sessions), (c) the Lucid bootstrap
lower bound is negative at every size and the edge is concentrated in VIX > 20 months. Possible use: a small, negatively-correlated
satellite leg next to a breakout strategy (it trades the days orb_close30 loses), not a stand-alone eval strategy.
