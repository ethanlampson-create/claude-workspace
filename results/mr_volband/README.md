# mr_volband -- Implied-vol band fade (prior RTH close +/- VIX/16) with VIX regime gate (Seeck 2026)

Family: intraday_mean_reversion. Module: `strategies/mr_volband.py`. Source paper: SSRN 7364204 (NQ, VXN/16 bands,
30-minute hold, OOS 2023-2026 Sharpe 1.29).

## Rules as implemented

- Reference level `C_ref` = previous session's RTH close (last 1-min close with tod < 16:00 ET; MGC: < 13:30 ET),
  taken from `daily_bars(rth_only=True)` shifted by one session (strictly days < d).
- Vol input `V`: previous calendar session's VIX close (`strategies.common.vix_lag1`) x `vol_mult`
  (1.0 MES, 1.25 MNQ as a fixed VXN/VIX proxy; no VXN series exists in data/parquet). `vol_src='rv20'` (MGC default):
  V = stdev of the last 20 daily log RTH close-to-close returns of days < d x sqrt(252) x 100 (min_periods = 20).
- Band half-width `w = C_ref * (V / divisor) / 100`; Upper = C_ref + w, Lower = C_ref - w.
- Entry window 09:35-15:00 ET (MGC 08:25-13:00 ET). If the first 1-min close inside the window is already beyond a band,
  that band is pre-breached and not traded that day (`allow_open_outside=False`).
- Signal: first 1-min bar in the window whose close < Lower -> long at market at the open of the next bar;
  first close > Upper -> short. Each band fires at most once per session; `max_trades_day=2`; one position at a time
  (a signal arriving while a position is open is dropped by the engine, as the spec requires).
- Exits: time exit after `hold` minutes (`max_hold` bars; paper rule), protective stop `stop_mult * w` beyond the
  breached band, optional target (`tgt_mode` none / ref = C_ref / band), force flat 15:55 ET.
- Regime gate (`gate=True`): trade only when vix_lag1 < 20 or vix_lag1 >= 30 (the gate uses VIX even for MGC/rv20).
  NaN VIX / C_ref / RV -> no trade.
- Costs: engine defaults (1 tick slippage per side on market/stop fills, $1.30 RT commission on micros).

Defaults (= paper): divisor=16, hold=30, stop_mult=0.5, tgt_mode='none', gate=True, vix_low=20, vix_high=30,
sides='both', max_trades=2, flat 15:55.

Verification: for every MNQ MAIN trade the bar before entry closed beyond the band, the VIX gate held and the entry
bar belonged to the same session (88/88 checked, 0 violations). 384 of 479 sessions pass the gate (373 VIX<20, 14 VIX>=30).

## Metrics with default parameters (1 micro, after costs)

| contract | period | trades | net $ | PF | win | avg trade | max DD intraday | Sharpe | pos days | pos months |
|---|---|---|---|---|---|---|---|---|---|---|
| MNQ | MAIN 2025-01..2026-09 | 88 | +769 | 1.13 | 43% | 8.7 | -2092 | 0.23 | 43% | 43% |
| MNQ | PRIOR 2023-01..2024-12 | 126 | -785 | 0.83 | 41% | -6.2 | -1108 | -0.52 | 42% | 42% |
| MES | MAIN | 61 | +217 | 1.09 | 46% | 3.6 | -954 | 0.12 | 46% | 52% |
| MES | PRIOR | 99 | -820 | 0.59 | 40% | -8.3 | -882 | -1.34 | 40% | 42% |
| MGC (rv20) | MAIN | 104 | +1923 | 1.43 | 50% | 18.5 | -1792 | 0.87 | 50% | 48% |
| MGC (rv20) | PRIOR | 158 | -1088 | 0.71 | 43% | -6.9 | -1327 | -1.10 | 43% | 38% |

## Diagnostics (MAIN, defaults)

MNQ: 85 of 88 exits are the 30-min time exit; the 3 stops cost -1,183 (avg -394 vs +23 for time exits). Shorts
carry the net (+823 on 41) and longs are flat (-54 on 47). Entries in the 09:00-10:59 window make +2,468; everything
after 11:00 loses (-1,700). Monday +1,999, Tue/Wed -1,562. VIX>=30 bucket is a coin flip with huge sizes (4 trades
-1,234, 3 trades +1,250). Median MAE 58 pts vs MFE 32 pts: the typical trade goes against us more than for us, and the
30-min exit is what caps the damage. Monthly P&L is 43% positive; the best month (2026-06, +1,190) is 150% of the
total net.

MGC: longs +2,820 on 54, shorts -897 on 50; 84 time exits +4,519 vs 20 stops -2,596. Early-window entries (08:xx) are
flat, 09:00-11:59 profitable. Every month from 2025-02 to 2025-09 but one is negative; 2026 carries the net
(gold bull market: fading dips in a strong uptrend). 2025-09 alone lost -567.

## Grid (24 combos, MAIN and PRIOR, 1 micro)

MNQ (`grid_main_MNQ.csv`): MAIN 62% of combos profitable, median PF 1.06; PRIOR 8% profitable, median PF 0.91;
rank correlation between periods 0.40. The MAIN plateau is divisor 14 (widest band) with hold 30: PF 1.51-1.72 for
all four stop/gate combinations, net 2,871-3,512, 76-93 trades. On PRIOR those same combos are PF 0.94-0.99
(net -192..-54). Concentration: 2025-04-07 (two trades, +2,638) is 75-80% of the MAIN net of the plateau; ex April 2025
the plateau is PF 1.30 on 69-83 trades. Longer holds (60) and tighter bands (20) are worse on both periods. The gate
removes 15-20% of the trades and slightly lowers net; its benefit in the paper does not show up here.

MGC (`grid_main_MGC.csv`): 24/24 combos profitable on MAIN (median PF 1.18, best 1.51) and 0/24 profitable on PRIOR
(PF 0.59-0.87); rank correlation 0.15. This is the signature of a regime fit, not of a parameter plateau: gold trended
up strongly in 2025-26, so every "buy the lower band" trade benefited.

MES (`grid_main_MES.csv`): MAIN 71% of combos profitable (median PF 1.10, best 1.73 at divisor 14 / hold 30 /
stop 0.5 / gate off, 58 trades, net 1,199) but every MAIN winner has largest_day_share >= 1.0 (one session is bigger
than the whole net); PRIOR 0/24 profitable, PF 0.52-0.85, median 0.68. Divisor 20 (tight band) loses on both periods.

## Follow-up grid (tgt_mode x sides x gate at the plateau)

MNQ at divisor 14 / hold 30 / stop 0.5 (`followup_MNQ.csv`, 12 combos = tgt_mode x sides x gate):

| variant | n MAIN | net MAIN | PF MAIN | DD intraday | Sharpe | lds | n PRIOR | net PRIOR | PF PRIOR |
|---|---|---|---|---|---|---|---|---|---|
| none / both / gate | 76 | 3322 | 1.72 | -1341 | 0.80 | 0.79 | 100 | -192 | 0.94 |
| none / both / no gate | 93 | 3512 | 1.63 | -1419 | 0.83 | 0.75 | 115 | -79 | 0.98 |
| ref / both / gate | 76 | 3072 | 1.67 | -1341 | 0.79 | 0.78 | 100 | -192 | 0.94 |
| band / both / gate | 76 | 848 | 2.09 | -447 | 1.07 | 0.42 | 100 | -122 | 0.83 |
| band / both / no gate | 93 | 908 | 2.02 | -469 | 1.12 | 0.39 | 115 | -117 | 0.85 |
| none / long / gate | 46 | 1926 | 1.63 | -933 | 0.86 | 0.49 | 45 | -144 | 0.92 |
| band / long / no gate | 53 | 249 | 1.41 | -478 | 0.44 | 0.28 | 50 | +102 | 1.38 |
| band / long / gate | 46 | 219 | 1.37 | -466 | 0.39 | 0.32 | 45 | +38 | 1.14 |

The `ref` target (C_ref) is almost never reached inside 30 minutes, so it equals `none`. The `band` target (scalp back
to the breached band) makes the shape prop-friendly on MAIN (PF 2.0, DD -450, Sharpe 1.1, no single day > 42%) but
the net shrinks to ~$10/trade and PRIOR is still PF 0.83-0.85. The only variant positive on both periods is
band + long-only (PF 1.41 MAIN / 1.38 PRIOR), and it is too small to matter: ~$5/trade, 26 trades a year, Lucid pass
rate 5%, P(first payout) 0.

MGC at the defaults (`followup_MGC.csv`): long-only is the whole edge on MAIN (none/long/no gate: 59 trades, net
3,042, PF 2.28, Sharpe 1.47; band/long: PF 2.85, DD -351) but long-only is PF 0.43-0.68 on PRIOR, i.e. worse than
both sides (0.71). Gold 2025-26 rewarded every dip-buy; 2023-24 did not. Shorts lose on both periods.

## Lucid 50K Flex (lucid_scan, best micros by expected net per evaluation)

Defaults, MNQ MAIN: best 5 micros, pass rate 10%, P(first payout) 0, expected net per eval -146 (the fee). The best
MNQ grid point (div 14 / hold 30 / stop 0.5 / gate off) reaches pass rate 21% at 5 micros with P(first payout) 0.3%
and expected net -136 per evaluation. MGC default: 18% pass, expected net +24..+41 per eval (10-15 micros), but that
sizing is built on the MAIN-only edge that reverses on PRIOR.

## Attempts log

1. Paper defaults on MNQ/MES/MGC, MAIN and PRIOR (table above). MNQ/MES marginally positive on MAIN, all three
   negative on PRIOR.
2. 24-combo grid MNQ: wider band (divisor 14) is the only region with PF > 1.3 on MAIN; it is break-even on PRIOR
   and its MAIN net is dominated by the 2025-04-07 tariff-crash session.
3. 24-combo grid MGC: everything wins on MAIN, everything loses on PRIOR (regime fit).
4. 24-combo grid MES: wide band (divisor 14) is the MAIN plateau again (PF 1.3-1.7) but single-day-driven
   (largest_day_share >= 1) and 0/24 combos profitable on PRIOR.
5. Follow-up (tgt_mode x sides x gate) on MNQ and MGC: `band` target cuts drawdown by 3x and doubles PF on MAIN but
   not on PRIOR; long-only is a gold-bull artefact; nothing but the tiny MNQ band/long variant survives both periods.
6. Not tried (no stated reason to expect PRIOR to improve, and it would be test-window tuning): hour-of-day filters
   (MNQ 09-11 only), weekday filters, VIX>=30 exclusion. The diagnostics show these would lift MAIN, but the paper
   gives no basis for them and the PRIOR failure is broad (all 24 combos on MES/MGC, 22/24 on MNQ), not a filter
   issue.

## Lucid detail for the reported configuration (MGC, defaults, rv20 band)

| micros | pass rate | P(first payout) | expected net / eval | median days to pass |
|---|---|---|---|---|
| 5 | 22% | 2.3% | -19 | 90 |
| 10 | 30% | 1.9% | +21 | 60 |
| 15 | 18% | 1.9% | +24 | 70 |
| 20+ | 10-14% | 0 | -146 | 21-26 |

MNQ defaults: pass rate 10% at 5-10 micros, P(first payout) 0, expected net -146 at every size. MNQ divisor-14 band
target: best 40 micros, pass 8%, P(first payout) 3%, expected net -91.

## Verdict: marginal (promising by the PF>=0.95 / >=40 trades screen, not by robustness)

- The rule is implemented faithfully and verified; it trades ~50-60 times a year per instrument.
- MAIN: positive on all three instruments with the paper defaults (MNQ PF 1.13 / 88 trades, MES 1.09 / 61,
  MGC 1.43 / 104). The MAIN edge is concentrated in a handful of high-vol sessions (2025-04-07 on MNQ, the 2026 gold
  rally on MGC) and in the 09:35-11:00 window.
- PRIOR: negative on all three instruments and on 70 of the 72 grid points. Profit factor on 2023-24 is 0.59-0.98 for
  every combination that is profitable on 2025-26. The paper's OOS Sharpe 1.29 (2023-2026) is not reproduced on our
  VIX-proxied, 1-minute-executed version with costs; our 2023-24 sample is what the paper calls its OOS and it loses.
- Lucid: no configuration has a positive expected net per evaluation with a meaningful first-payout probability on a
  rule that also holds on PRIOR. MGC defaults are the only +EV (+$24/eval at 15 micros) and that EV comes entirely
  from the MAIN-only edge.
- Fixable flaw? The one structural finding is that the `band` target (scalp back to the band) halves drawdown and
  doubles the profit factor at the same trades on MAIN, and that MNQ band/long-only is the single two-period-positive
  variant. A combined "band target + long-only + first 90 minutes" rule could be worth one more pass as a filler leg
  in a portfolio, but with 25-50 trades a year and ~$5-10 a trade it cannot carry an evaluation by itself.
- Recommendation: do not promote as a standalone leg. Keep the module; revisit only as a small long-only band-target
  filler if a portfolio needs uncorrelated, low-drawdown trades.
