# mr_onrev - cross-sectional overnight-return reversal across MES / MNQ / MGC (open-to-close)

Family: intraday_mean_reversion (research item 25, evidence grade 4 in the literature, but our universe is 3 instruments).
Module: `strategies/mr_onrev.py`. Verdict: **dead** (no edge on PRIOR, MAIN edge is noise-level and tail-driven; gold leg is a continuation, not a reversal).

## Rules as implemented
- Same clock for all instruments: prior_close = last 1-min close with tod < 16:00 ET of the previous session; open_0930 = open of the 09:30 bar (XAU included). r_k = 100*(open_0930 - prior_close)/prior_close.
- Universe loaded inside generate() via load_1m for the df1 session span: all3 = SPX+NSX+XAU (default), eq = SPX+NSX (MGC with eq -> no trades by construction).
- A session is skipped if any member lacks a 09:30 bar / prior close, or if the members' prior sessions are not the same date (keeps overnight windows aligned; feeds were fully aligned, 0 sessions dropped).
- x_k = r_k - mean(r); spread = max(r) - min(r). LONG X if x_X is the min, spread >= thresh (0.30%), x_X <= -thresh/2. SHORT mirror. sides both|long|short.
- Entry: market at open of the 09:31 bar. Stop: stop_atr (1.0) x 14-day RTH ATR (lagged, contract RTH spec; gold 08:20-13:30). No target. Flat at first bar >= 15:55. One trade/day. ATR-not-warm days do not trade.
- Defaults = published rule (thresh 0.30, all3, stop_atr 1.0, both). Grid: thresh [0.2,0.3,0.5] x universe [eq,all3] x stop_atr [0.75,1,1.5] x sides [both,long] (MGC: all3 only).

## Metrics (defaults, per 1 micro, after costs)
| contract | period | trades | net $ | win | PF | maxDD intra | Sharpe | pos days | worst month |
|---|---|---|---|---|---|---|---|---|---|
| MES | MAIN | 136 | +885 | 0.456 | 1.075 | -4280 | 0.18 | 0.456 | -611 |
| MES | PRIOR | 78 | -232 | 0.474 | 0.951 | -1900 | -0.12 | 0.474 | -510 |
| MNQ | MAIN | 221 | +2509 | 0.534 | 1.061 | -5181 | 0.25 | 0.534 | -4204 |
| MNQ | PRIOR | 206 | -2055 | 0.476 | 0.918 | -6337 | -0.34 | 0.476 | -1575 |
| MGC | MAIN | 347 | -7667 | 0.447 | 0.837 | -10572 | -0.85 | 0.447 | -5468 |
| MGC | PRIOR | 281 | -5506 | 0.456 | 0.629 | -5729 | -2.03 | 0.456 | -899 |

MES MAIN: largest_day_share 2.8 -> the whole net is 2025-04-09 (+2487, tariff-pause day) plus 04-08 (+1306); ex those two days MES is negative.
MNQ MAIN: 19 disaster stops cost -16044 vs +18553 from 202 time exits; March 2025 alone -4204; shorts +2351, longs +158.
Lucid scan MNQ MAIN: see final.json (not recommended).

## Diagnostics (MAIN)
- Hour: single entry 09:31. Weekday MNQ: Mon +3025, Wed +4179, Tue -2407, Thu -1954, Fri -335 (sign flips by weekday = noise).
- VIX (MNQ): positive 15-25, negative <15 and >25. MES: positive only in the >25 buckets (7 trades, April 2025).
- Raw edge check, corr(demeaned overnight return, 09:31->15:55 return): MAIN SPX -0.07, NSX -0.06, XAU +0.11; PRIOR SPX +0.01, NSX +0.03, XAU +0.10. Equity-only demeaning: ~0 in both periods. Signal-conditional mean intraday return: MAIN SPX +0.06%/trade (t 0.6), NSX +0.05% (t 0.7), XAU -0.04% (t -0.9); PRIOR SPX +0.02% (t 0.2), NSX -0.04% (t -0.7), XAU -0.07% (t -2.3).
- Gold overnight returns continue intraday (positive corr both periods): gold should not be a reversal leg; because XAU has the largest dispersion it is the extreme on ~50% of days, so it also dominates signal selection for the others.

## Attempts log
1. Defaults on all 3 contracts, both periods (above). 2. Raw-edge check (above): no PRIOR edge for any leg. 3. 36-combo grids per contract on MAIN launched in the background (grid_main_MNQ/MES/MGC.csv); the 2015-22 long-history check was killed by memory contention with the grid. No parameter change can be justified: the edge is absent on PRIOR, so no "improvement holds on PRIOR".

## Verdict
Dead. The academic effect needs a wide cross-section; with 3 instruments the demeaned overnight return has corr ~0 with the intraday return, P&L is a few tail days, intraday DD per micro (-4k to -10k) is incompatible with the $2,000 trailing limit, and the gold leg is a continuation. Not promising; a portfolio combination of three dead legs was not run.
