# mr_gapfade - small opening-gap fade toward the prior RTH close

Family: intraday_mean_reversion (research: `research/families/intraday_mean_reversion.md`, item 7).
Module: `strategies/mr_gapfade.py`. Verdict: **marginal** (MNQ only; thin, infrequent, holds on PRIOR and in walk-forward OOS, but dead as a standalone Lucid vehicle; MES dead).

## Rules as implemented
- `prior_close` = last 1-min close with tod < 16:00 ET of the previous session (`prior_day_stats`, RTH 09:30-16:00).
  `open_0930` = open of the 09:30 bar. `gap = (open_0930 - prior_close) / prior_close`. PDH/PDL = prior RTH high/low.
  ATR = 14-day RTH daily ATR (`daily_atr`, lagged), compared as % of prior_close.
- Qualify (all known at the 09:30 open): `gap_min <= |gap| <= gap_max` (%), `|gap| <= atr_mult * ATR%`,
  open within `[PDL - outside_atr*ATR, PDH + outside_atr*ATR]` (else gap-and-go, skip), VIX gate: skip when the lagged VIX
  close is in the top quartile of its trailing 100-session high/low range (sessions < d only). FOMC/CPI calendar: not
  available, not implemented.
- Direction: gap down -> long, gap up -> short (`sides` = both | long | short). `skip_mon_gapup` optional.
- Entry: market at the open of the bar at 09:30 + `entry_delay` min. Skip if the gap already filled before entry (long:
  any high >= prior_close; short: any low <= prior_close). Skip if the stop level was already breached before entry
  (`skip_beyond_stop`, the bracket would be dead on arrival; this is my addition, affects a handful of days).
- Stop = open_0930 -/+ `stop_mult` * |gap|; target = open_0930 + `fill_frac` * (prior_close - open_0930).
- Exit: `Intents.exit_at` at the first bar >= `exit_time`; force flat 15:55; one trade/day.

Defaults (published): gap_min 0.10, gap_max 0.50, atr_mult 0.7, stop_mult 1.0, fill_frac 1.0, entry_delay 5,
exit_time 11:00, sides both, vix_gate True, outside_atr 0.5, skip_mon_gapup False.

## Metrics (per 1 micro, after costs)

| config | contract | period | trades | net $ | win | PF | maxDD intra | Sharpe | pos days |
|---|---|---|---|---|---|---|---|---|---|
| defaults | MES | MAIN 2025-01..2026-09 | 191 | -1300 | 0.435 | 0.79 | -1828 | -1.01 | 0.44 |
| defaults | MES | PRIOR 2023-24 | 215 | +743 | 0.535 | 1.17 | -680 | 0.66 | 0.54 |
| defaults | MNQ | MAIN | 114 | +1658 | 0.561 | 1.34 | -903 | 0.97 | 0.56 |
| defaults | MNQ | PRIOR | 162 | -100 | 0.500 | 0.98 | -923 | -0.06 | 0.50 |
| gap_max 0.35 | MNQ | MAIN | 72 | +1542 | 0.597 | 1.74 | -438 | 1.44 | 0.60 |
| gap_max 0.35 | MNQ | PRIOR | 101 | +430 | 0.515 | 1.16 | -525 | 0.42 | 0.51 |
| **gap_max 0.35, entry_delay 1 (best)** | **MNQ** | **MAIN** | **114** | **+1985** | **0.570** | **1.56** | **-633** | **1.51** | **0.57** |
| best | MNQ | PRIOR | 130 | +828 | 0.515 | 1.22 | -737 | 0.67 | 0.52 |
| best params | MES | MAIN | 158 | -1535 | - | 0.72 | - | -1.36 | - |

Best config, MAIN: avg trade $17.4 (avg win $85 / avg loss -$72), largest day share 11%, 57% positive months,
worst month -$414, 2 max consecutive losing days. Trades per month: ~5.4.

Lucid scan (best config, MAIN, constant micros): best = 10 micros -> pass rate 0.37, P(first payout | pass) 0.51,
P(first payout) 0.19, expected net per eval +$330, median 23 days to pass. 5 micros: pass 0.44 but never reaches a
payout (profit too slow). Monthly pass rate at 10 micros is bimodal: 0 in 2025-01..04 and 2025-09..11, 1.0 in
2025-06, 2026-01, 2026-06/07. Not a standalone eval vehicle.

## Diagnostics (best config, MNQ MAIN)
- Exit reasons: target 42-57 wins avg +$85, stop 24-40 avg -$77, time exit small net negative (6/114 with delay 1).
  Median hold 12 min; 75% of trades resolve within 25 min: a 1:1 bracket that needs > 50% hits.
- Sides: longs (gap-downs) avg +$37/trade (25 tr), shorts +$13 (47 tr); both positive on MNQ, unlike MES.
- Weekday: Wednesday flat, all others positive. VIX: all buckets positive except 25-35 (2 trades, both losses).
- Months: 2025-11, 2026-03, 2026-05 are the losing months (2-3 trades each, all stops); no month > 40% of net.
- Raw fill statistics (unconditional, 2023-2026, long bucket 0.10-0.25%): on MES MAIN the stop was hit first on 47-51%
  of days vs the fill on 27-30%, with 15-16% filling inside the first 5 minutes. On MNQ 26-36% of small gaps filled
  before 09:35. That is the structural flaw of the published rule: a 1x-gap stop on a 0.1-0.25% gap is 6-15 MES
  points and gets hit by noise, and the 5-minute delay throws away the fastest (best) fills.

## Grid (MAIN, 36 combos each, `grid_main_MES.csv`, `grid_main_MNQ.csv`)
- MES: 0/36 profitable. Best PF 0.93 (gap_max 0.70, both, 11:00, 227 trades). stop_mult 1.5 worst everywhere,
  12:00 exit worse than 11:00. Dead on 2025-26 regardless of parameters.
- MNQ: 28/36 profitable. Plateau: gap_max 0.35-0.50 x stop_mult 0.75-1.0 x both sides (PF 1.3-1.7); gap_max 0.70 and
  stop_mult 1.5 break it (PF ~0.9-1.0, DD -2k..-4k). Long-only cuts trades to 25-45 (PF 1.3-2.1 but too few).
- MNQ PRIOR plateau check (`grid_prior_MNQ.csv`): gap_max 0.35 holds (PF 1.06-1.18, 92-101 trades); gap_max 0.50 does
  not (PF 0.92-0.98). So gap_max 0.35 is the robust cap, consistent with the published statistic (fill rate collapses
  as the gap grows).
- Follow-up (`followup_MNQ.csv`, `followup2_MNQ.csv`): fill_frac 0.75 worse on both periods; vix_gate on/off changes
  < 10 trades and < $100 (nearly inert, only ~10 top-quartile VIX days qualify); entry_delay 1 vs 5: +40 trades,
  higher net and Sharpe on both periods (MAIN PF 1.74 -> 1.56 but net +$440 and DD similar; PRIOR PF 1.16 -> 1.22).
- MES follow-up (`followup_MES.csv`): entry_delay 1 / long-only lifts MAIN to PF 0.95 (77 trades, net -$134), still
  negative; MES rejected.

## Walk-forward out-of-sample (the honest yardstick) - 2026-10-03
`python3 -m backtest.final_select --ids mr_gapfade --jobs 2 --wf_start 2022-01-01 --max_combos 16` -> `walkforward.json`,
`wf_oos_2025_daily.csv`. IS 12 months / OOS 3 months, parameters chosen on trailing IS by daily Sharpe, base = final.json
params (gap_max 0.35, entry_delay 1), search space = module GRID (trimmed this round from 36 to 16 combos:
gap_max {0.35, 0.50} x stop_mult {0.75, 1.0} x sides {both, long} x exit_time {11:00, 12:00}; the automatic coarsening of
the old 36-combo grid would have kept only gap_max {0.35, 0.70} and stop_mult {0.75, 1.5}, i.e. the two values shown
above to break the strategy on both periods, and dropped the published default stop_mult 1.0).

| stream (MNQ, 1 micro) | trades | net $ | PF | Sharpe | pos months | maxDD intra |
|---|---|---|---|---|---|---|
| WF OOS 2025-01..2026-09 (**wf_2025**) | 65 | +1367 | 1.51 | 1.07 | 0.67 | -587 |
| WF OOS 2023-01..2026-09 (all) | 203 | +1066 | 1.14 | 0.41 | 0.53 | -1012 |
| fixed params MAIN 2025-01..2026-09 | 109 | +2051 | 1.61 | 1.58 | 0.57 | -585 |
| fixed params PRIOR 2023-24 | 104 | +571 | 1.17 | 0.48 | 0.42 | -847 |

Parameter path (OOS quarter -> chosen): 2023: gap_max 0.35/0.50, stop 0.75/1.0, both, 11:00 (OOS net -333 on 66 trades);
2024: gap_max 0.35, stop 1.0, both, 12:00 (OOS +32 on 72 trades, of which Q3 +829 and Q4 -670); 2025-Q1..2026-Q1:
gap_max 0.50, stop 0.75, **long only**, 11:00/12:00 (OOS +690 on 38 trades); 2026-Q2/Q3: gap_max 0.35, stop 0.75/1.0,
both, 11:00 (OOS +678 on 27 trades). OOS 2025 monthly: 14 of 21 months positive, worst -325 (2025-03), best +374
(2025-04); 2026-07..09 alone = +888 (65% of the OOS 2025 net); without that last window: +479 on 50 trades.

Lucid on the OOS 2025 stream (bootstrap lower-bound sizing, `lucid_wf_2025`): best size 5 micros, pass rate 0.34 but
median 85 sessions to pass, **pass_within_21 = 0.00, P(first payout) = 0.00, expected net per eval -$146 = exp_net_lb =
zero-edge control (-$146)** at every size 5..40; recommended = False. ~3 trades/month at +$21/trade/micro is $100/month
per micro: an evaluation needs $3,000 in a reasonable window and the strategy cannot get there before the fee clock does.

Reading: the in-sample story (PF 1.56-1.61 on MAIN) does survive out of sample in direction and magnitude (PF 1.51 on
65 OOS trades), which is more than most candidates manage. What does not survive is the account-level case: too few
trades, P&L concentrated in two or three quarters (2024-Q3, 2026-Q3), 2023-24 OOS negative, and a parameter path that
flips between sides=long/both and 11:00/12:00 exits, i.e. the selection is choosing among noise-level alternatives.
Gate: proceed = True (wf_2025 PF 1.51 >= 1.03 on 65 >= 40 trades; fixed MAIN 1.61 / PRIOR 1.17 on 109 trades), as a
portfolio-leg candidate only. Standalone verdict unchanged: marginal, not an eval vehicle.

## Attempts log
1. Faithful implementation; first run had the pre-fill check inverted (0 trades) - fixed.
2. Added `skip_beyond_stop` (do not enter when the stop is already breached by the 09:34 close): a trader would not
   place that bracket. Minor effect.
3. Prescribed grid on MES and MNQ (MAIN); PRIOR check of the MNQ plateau; prescribed fill_frac x vix_gate follow-up;
   entry_delay hypothesis (from the raw fill statistics) on both contracts and periods.
4. Not tried (would be curve-fitting without a new reason): weekday filters, VIX bucket filters, per-side stop sizes.
5. 2026-10-03 walk-forward round: trimmed GRID 36 -> 16 combos (dropped gap_max 0.70 and stop_mult 1.5, both shown to
   break the strategy on MAIN and PRIOR) so the walk-forward searches a meaningful space; no rule or default changed.
   Result kept as the reference OOS evidence (wf_2025 PF 1.51 / Sharpe 1.07 / 65 trades; lucid not recommended).

## Verdict
MNQ gap fade with gap_max 0.35 and 09:31 entry is a real but thin edge (PF 1.56 on 114 trades MAIN, 1.22 on 130
trades PRIOR, Sharpe 1.5 / 0.7, DD -$633 per micro). Frequency (~5/month) and the 1:1 payoff make it a poor standalone
Lucid vehicle (pass rate 0.37, P(first payout) 0.19 at 10 micros) with a bimodal monthly pass rate. Suitable as a
low-correlation portfolio leg (flat on ~75% of days, resolves by 10:00 most days). MES: dead in 2025-26.
Engine notes: none found. FOMC/CPI calendar is unavailable and was not implemented.
