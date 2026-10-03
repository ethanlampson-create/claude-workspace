# mr_bbfade -- Bollinger (20,2) rejection-wick fade, ADX<25 gate, trend-day kill switch

Family: intraday_mean_reversion (research/families/intraday_mean_reversion.md, item 3, evidence quality 2).
Module: `strategies/mr_bbfade.py`. Priority 7 ("consistency filler").

## Rules as implemented
- 5-min bars from ALL session bars (`resample(df1, 5, rth_only=False)`), so SMA/ATR/ADX are mature at the RTH open.
- Indicators on 5-min closes, `min_periods` = full window: mid = SMA(20); sd = rolling std(20); upper/lower = mid +/- 2.0 sd;
  ATR5 = Wilder ATR(14); ADX = ADX(14) (`strategies.common`). Daily ATR = 14-day RTH ATR, lagged. `rth_open_px` = open of the
  first 1-min bar at/after 09:30 (08:20 for MGC).
- Signal bar b (values at its close): LONG if low <= lower AND (close-low) >= 0.5*range AND range > 0 AND ADX < 25 AND
  |close - rth_open_px| <= 0.6 * dailyATR. SHORT mirror (high >= upper, (high-close) >= 0.5*range). Implementation guard: the
  SMA target must be >= 1 tick beyond the close in the trade direction (otherwise the target is a scratch at entry).
- Entry: market at the open of 1-min bar `i_next` (skipped if -1), only if that bar is inside the entry window
  (09:45-15:00 ET; MGC 08:30-13:00). Stop = low - 1.0*ATR5 (long) / high + 1.0*ATR5 (short). Target = mid (fixed SMA20 value of
  the signal bar). Time stop 15 bars x 5 = 75 min. Flat 15:55 (MGC 13:25). max_trades_day 4, daily_loss_stop = loss_cap (0 = off).
- Optional extra (added after diagnosis, default off): `max_rr` -- skip when |mid - close| > max_rr x (close-to-stop distance),
  i.e. when the bands are wide relative to ATR5 (expanding / trending volatility). Tested at 1.0.
- Look-ahead check: all signal inputs are at the 5-min bar close; entry is the next 1-min bar; daily ATR is lagged; rth_open_px is
  the session's own 09:30 open, known before any 09:45+ entry.

## Default-parameter results (per 1 micro, costs included)
| contract | period | trades | net $ | win | PF | avg trade | Sharpe | pos days | max DD intraday |
|---|---|---|---|---|---|---|---|---|---|
| MNQ | MAIN 2025-01..2026-09 | 812 | -3436 | 61.2% | 0.90 | -4.2 | -0.83 | 52.9% | -7347 |
| MNQ | PRIOR 2023-24 | 757 | -2470 | 61.2% | 0.89 | -3.3 | -0.94 | 45.6% | -3911 |
| MES | MAIN | 866 | -3758 | 57.6% | 0.81 | -4.3 | -1.81 | 48.6% | -4082 |
| MES | PRIOR | 790 | -3288 | 57.0% | 0.75 | -4.2 | -2.49 | 43.8% | -3525 |
| MGC | MAIN (08:30-13:00) | 950 | -5808 | 58.9% | 0.84 | -6.1 | -1.49 | 45.5% | -6308 |
| MGC | PRIOR | 802 | -3695 | 57.0% | 0.72 | -4.6 | -2.58 | 42.6% | -3781 |

Gross of costs MNQ MAIN is still negative (-1569): the loss is not a cost artefact.

## Diagnosis (MNQ MAIN, defaults; `report_MNQ_main.txt`)
- Win rate is 61% as advertised, but winners are only 0.57R (avg win $65 vs avg loss $113), not the 0.8R claimed. Reason: the
  target is the SMA20 at the signal bar while the stop is wick + 1 ATR beyond the extreme. A big rejection wick (which is what the
  pattern demands) leaves the close near the SMA: median reward 33 pts vs median risk 58 pts on MNQ.
- By reward/risk bucket: rr>1.0 (wide bands relative to ATR5, 197 trades) loses -3645 at a 40% win rate on MNQ and -3218 on MES
  at 34%; rr<0.25 loses -1709 on MNQ (78% win rate, but each winner is a scratch). The middle buckets are roughly flat.
- Shorts lose 4.5x more than longs (-2815 vs -621), consistent with the family finding "shorts are the weak side".
- By hour: 10:00 and 12:00 hours carry nearly all the loss (-1844, -1733); 09:45-10:00, 11:00 and 14:00 are ~flat/positive.
- Exit reasons: 451 targets (+29.6k), 263 stops (-33.2k), 94 time stops (-0.1k). Losers' median MFE is 10.8 pts, winners' median
  MAE -12.9 pts: there is no obvious better exit; the stop is simply too far relative to the target.
- VIX: loses in the 15-20 bucket (553 trades, -3091) which is most of the sample; small positive elsewhere.
- Month: 8/21 positive months; best month 2026-06 (+1283), worst 2025-06 (-1453); the 2025 Q2 chop/trend period is the killer.

## Grids (results/mr_bbfade/*.csv, MAIN and PRIOR, Lucid scan per cell)
Module GRID = bb_sd [2.0, 2.5] x adx_max [20, 25, 99] x stop_atr [1.0, 1.5] x sides [both, long] (24 cells).
- MNQ: 4/24 cells profitable on MAIN, 9/24 on PRIOR, rank correlation between periods 0.37. Best MAIN cell bb_sd 2.0 / adx 20 / stop 1.0 /
  both: PF 1.07, net +1196, 509 trades -- but PF 0.86 on PRIOR. The cells that work on PRIOR (bb_sd 2.5, PF 1.1-1.25) lose on MAIN.
  No cell has a positive bootstrap lower bound; none is Lucid `recommended`.
- ADX gate (99 vs 25 vs 20): on MAIN the gate helps (PF 0.89 -> 0.90 -> 1.07 for both-sides, bb 2.0) but on PRIOR it does
  nothing (0.88 -> 0.89 -> 0.86). The gate removes trades but does not create an edge.
- Long-only: better than both-sides in every pairing on both instruments (shorts confirmed as the weak side), but long-only
  with defaults is only PF 1.005 / 0.96 (MAIN / PRIOR) on MNQ.
- MES: 0/24 cells profitable on either period; rank correlation 0.93 (it loses the same way everywhere). Best cell PF 0.98.
- Follow-up 1 (MNQ, time_bars [10,15,24] x loss_cap [0,60]): loss_cap 60 improves PF 0.90 -> 0.93-0.95 on MAIN but cuts positive
  days to 47%; PRIOR unchanged at 0.86-0.88. time_bars 24 marginally better than 15; 10 worse. Nothing goes positive.
- Follow-up 2 (MNQ, max_rr [0, 1.0] x sides): max_rr=1.0 improves both periods (both: 0.90 -> 0.94 MAIN, 0.89 -> 0.93 PRIOR;
  long: 1.005 -> 1.045 MAIN, 0.96 -> 0.98 PRIOR). This is the only change that holds on PRIOR. Best overall cell:
  **MNQ, sides=long, max_rr=1.0**: MAIN 395 trades, net +664, PF 1.045, avg trade +$1.7, Sharpe 0.25, 62% positive days,
  max DD intraday -2590; PRIOR 334 trades, net -167, PF 0.98.

## Lucid (50K Flex) for the best cell (MNQ long, max_rr 1.0), MAIN
- lucid_scan best size 5 micros: pass rate 31.5% (9% within 21 sessions), median 29 days to pass, P(first payout) 2.9%,
  expected net per eval -$93 (zero-edge control -$110, bootstrap lower bound -$146 = lose the fee). Not recommended at any size.
- Monthly pass rate (within 21 sessions): 0 in 14 of 20 start months; 0.57 (2025-03), 0.38 (2025-04), 0.70 (2026-02) are the
  only months above 0.3. Nothing like "consistent".

## Attempts log
1. Defaults on MES/MNQ/MGC, MAIN+PRIOR: all six runs lose (PF 0.72-0.90). Verified the signal construction on sample trades.
2. Diagnosis: reward/risk geometry is the structural flaw (0.57R winners); shorts and 10:00/12:00 hours carry the losses.
3. Module grid on MNQ and MES (MAIN+PRIOR): no robust cell; MES uniformly dead.
4. Follow-up time_bars x loss_cap: no cell positive.
5. Added `max_rr` (reason: rr>1 bucket = wide bands vs ATR = trending tape, loses on both instruments). Holds on PRIOR but only
   lifts MNQ long-only to PF 1.045 / 0.98 -- breakeven.
Not tried (would be curve-fitting on this evidence): hour-of-day exclusions, VIX bucket gating, per-side parameters.

## Verdict: dead (reported as marginal only because the literal "PF >= 0.95 with >= 40 trades" screen is met)
The pattern's win rate is real (58-68%) but the fixed SMA20 target cannot pay for a wick + ATR stop; after costs it is a
PF 0.9-1.05 plateau on MNQ and 0.75-0.98 on MES, with negative expected net per evaluation under every sizing and no
monthly consistency. The ADX gate and the trend-day kill switch do not turn it into an edge. Not usable as a consistency
filler either: at its best it has Sharpe 0.25 and 62% positive days with -$2.6k intraday drawdown per micro.
