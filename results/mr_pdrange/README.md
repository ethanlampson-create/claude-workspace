# mr_pdrange - outside-open re-entry to the prior-day high/low (edgeful outside days / Williams "Oops")

Family: intraday_mean_reversion (research: `research/families/intraday_mean_reversion.md`, items 9 and 10).
Module: `strategies/mr_pdrange.py`. Verdict: **dead** after walk-forward (2026-10-03): the OOS 2025-26 stream has 12 trades; the stop-entry edge is too rare to be selected or sized. In-sample it was marginal (MNQ, stop-entry only; holds on PRIOR).

## Rules as implemented
- Definitions (all known at the 09:30 open): PDH/PDL = prior-session RTH 09:30-16:00 high/low and `prior_close` = last
  1-min close with tod < 16:00 (`strategies.common.prior_day_stats`); `open_0930` = open of the 09:30 bar; ATR = 14-day RTH
  daily ATR, lagged (`daily_atr`).
- Setup: LONG if `open_0930 < PDL`, SHORT if `open_0930 > PDH`; `level` = PDL/PDH; `dist = |open_0930 - level|`.
- Qualify: `min_dist` (0.05%) <= dist/open <= `max_dist` (0.30%); dist <= `dist_atr` (0.5) x ATR; |open - prior_close| /
  prior_close <= `gap_cap` (1.0%). `sides` = both | long | short.
- `entry='market'` (edgeful): market at the open of the 09:30 + `entry_delay` (5) bar; skip if the level was touched in the
  bars before entry (long: any high >= PDL); skip if the stop is already breached at the last pre-entry close
  (`skip_beyond_stop`, my addition, same as mr_gapfade). Stop = open -/+ max(`stop_mult` x dist, `min_stop_pct` 0.15% x open).
  Target = level + `tgt_ext` x (prior_close - level) (0 = the level).
- `entry='stop'` (Williams Oops): from the 09:31 bar a buy stop at PDL + 1 tick (sell stop at PDH - 1 tick), live until
  `stop_valid_until` (11:30; `valid_bars` = minutes). Stop = level -/+ max(stop_mult x dist, min_stop_pct x open). Target =
  level +/- min(|prior_close - level|, `tgt_atr` x ATR). Days whose target would be < `min_tgt_pct` (0.05%) from the level are
  skipped (prior close at the level: the target would sit at/below the fill; my addition, affects a handful of days).
- Exit: `Intents.exit_at` at the first bar >= `exit_time` (12:00); force flat 15:55; one trade per day.

Defaults = the published rule (market mode, max_dist 0.30, stop_mult 1.0, tgt_ext 0, entry_delay 5, both sides).

## Raw statistics (no engine; `results/mr_pdrange/funnel_study.py`)
- The 09:30 open is outside the prior RTH range on 40-45% of sessions (MNQ MAIN: 202/445; 75 below PDL, 127 above PDH).
  With dist >= 0.05%: 181; <= 0.30%: 78; <= 0.5 ATR: 78; gap <= 1%: 70. The 0.30% cap is the binding filter.
- Touch rates confirm the published numbers and their decay: MNQ MAIN touch-by-12:00 = 81% (0-0.1%), 88% (0.1-0.2%),
  84% (0.2-0.3%), 39% (0.3-0.5%), 39% (0.5-1%), 21% (>1%). PRIOR: 95/85/68/61/29/6%. MES MAIN: 82/77/56/44/21/21%.
- But 36-67% of those touches (MNQ, <= 0.3%) happen **before 09:35**, so the published 09:35 entry skips most of the
  fast reversions, and the stop (max(1x dist, 0.15%)) is hit before the touch on 33-47% of the remaining days: a 1:1
  bracket with a ~50% hit rate, i.e. no edge after costs. Shorts (open above PDH) outnumber longs 2:1.

## Metrics (per 1 micro, after costs; all numbers from the current engine, md5 a9d7a48d)

| config | contract | period | trades | net $ | win | PF | maxDD intra | Sharpe | pos days |
|---|---|---|---|---|---|---|---|---|---|
| defaults (market, 0.30, both) | MNQ | MAIN 2025-01..2026-09 | 27 | +430 | 0.52 | 1.62 | -319 | 0.73 | 0.52 |
| defaults | MNQ | PRIOR 2023-24 | 24 | +276 | - | 1.60 | -227 | 0.70 | - |
| defaults | MES | MAIN | 56 | +95 | 0.48 | 1.07 | -362 | 0.16 | 0.48 |
| defaults | MES | PRIOR | 53 | +219 | - | 1.28 | -235 | 0.53 | - |
| defaults + entry_delay 1 (old engine) | MNQ | MAIN | 54 | +364 | 0.52 | 1.22 | -313 | 0.46 | 0.52 |
| stop, 0.50, 1.0, both (tgt_atr 1.0) | MNQ | MAIN | 47 | +582 | 0.51 | 1.29 | -551 | 0.58 | 0.51 |
| stop, 0.50, 1.0, both (tgt_atr 1.0) | MNQ | PRIOR | 53 | +793 | 0.60 | 1.56 | -299 | 0.98 | 0.60 |
| **stop, 0.50, 1.0, both, tgt_atr 0.5 (best)** | **MNQ** | **MAIN** | **47** | **+774** | **0.51** | **1.39** | **-551** | **0.71** | **0.51** |
| best | MNQ | PRIOR | 53 | +793 | 0.60 | 1.56 | -299 | 0.98 | 0.60 |
| stop, 0.20, 1.0, both | MES | MAIN | 37 | +476 | 0.60 | 1.58 | -176 | 0.77 | 0.60 |
| stop, 0.20, 1.0, both | MES | PRIOR | 25 | +90 | - | 1.19 | -128 | 0.25 | - |
| best params | MES | MAIN / PRIOR | 55 / 47 | +79 / -161 | - | 1.05 / 0.85 | - | - | - |

Best config, MNQ MAIN: avg trade $16.5 (avg win $115 / avg loss -$86), ~2.2 trades/month, 57% positive months,
worst month -$436 (2026-08, 4 trades), largest day 44% of net (2025-11-03, +$343), max 2 consecutive losing days,
5 consecutive losing trades. Monthly: 12 of 21 months positive; 2026-03 (-$276) and 2026-08 (-$436) are the losers.

Lucid (MAIN, constant micros, current `lucid.py`): 10 micros -> pass rate 0.30, median 79 days to pass, P(first payout |
pass) 0.51, P(first payout) 0.15, expected net per eval +$129 point estimate but lower bound -$146 (the fee) at every
size; 21-day monthly pass rate is 0 in every month (eventual pass rate 0.55-1.0 only for starts in 2025-05..09). 5 micros
pass 0.22 and never reach a payout; 15+ micros pass less often (DD breaches). PRIOR: 10 micros pass 0.45, no payouts.
Not a standalone evaluation vehicle: it simply trades too rarely.

## Diagnostics (best config, MNQ MAIN; `report_MNQ_main_best.json`)
- Exit reasons: target 21 (avg +$115), stop 21 (avg -$88), 12:00 time exit 5 (avg +$42). Fills: 40 in the 09:xx hour,
  7 in the 10:xx hour (the later fills win 71%). Median MAE 33 pts / MFE 38 pts; losers' MFE 18 pts.
- Sides: longs (open below PDL) 19 trades avg +$29, shorts 28 trades avg +$8; both positive on MNQ.
- Weekday: Mon +$590 (8), Wed +$469 (10), Fri +$122; Tue -$253 (9), Thu -$155 (12). Small samples, no action taken.
- VIX (lag 1): 15-20 bucket carries everything (+$1,101 on 34 trades); <15 and 20-25 flat; 25-35 three losses (-$276).
- The 09:35 market entry (defaults) has 27 trades: 14 targets, 14 stops in the old engine run; the edge is in the
  stop-entry confirmation, not the raw touch rate.

## Grid (prescribed 24 combos, MAIN and PRIOR, both contracts: `grid_main_*.csv`, `grid_prior_*.csv`)
- MNQ: 13/24 profitable on MAIN (median PF 1.09), 16/24 on PRIOR (median 1.34); 8 cells >= 1.0 on both; MAIN/PRIOR rank
  correlation -0.21: the grid is not a plateau as a whole. Market-mode cells with PF 4-5 on PRIOR (0.20 cap) are < 0.9 on
  MAIN; market 0.50 is -$640..-$840 on MAIN. Long-only stop mode (PF 1.4-1.7 MAIN, 15-19 trades) is 0.8-1.0 on PRIOR.
  The stop-entry both-sides family is the only consistent region: 0.2/0.3/0.5 x 1.0/1.5 -> MAIN PF 1.01/1.19/1.29 and
  0.93/1.04/1.14, PRIOR 1.26/1.37/1.56 and 1.30/1.44/1.46. Wider cap = more trades and better on both periods.
- MES: 12/24 and 11/24 profitable, medians 1.00/1.03, rank corr 0.13. stop/0.20 both holds (1.58/1.19, 1.33/1.30) with
  25-37 trades; stop/0.30 ~1.05 on PRIOR; stop/0.50 < 1.0 on PRIOR; market mode inconsistent. MES rejected.
- Follow-up, stop mode (`followup_stop_MNQ.csv`, base stop/0.50/1.0/both, 16 runs = tgt_atr x exit_time x
  stop_valid_until, both periods): tgt_atr 0.5 raises MAIN PF 1.29 -> 1.39 and leaves PRIOR byte-identical (no PRIOR
  trade had a prior-close target beyond 0.5 ATR, so PRIOR is no evidence either way); exit 13:00 is a wash (MAIN slightly
  worse, PRIOR slightly better); stop_valid_until 10:30 is worse on both periods (fewer fills, lower PF). Same follow-up on
  MES: every cell < 1.0 on PRIOR.
- Follow-up, market mode on MES (`followup_market_MES.csv`, prescribed tgt_ext x exit_time): PF 1.14-1.36 MAIN but
  0.93-1.20 PRIOR with no ordering that agrees across periods; noise.

## Attempts log
1. Faithful implementation of both entry modes; smoke tests fine on first run (29 trades MNQ MAIN at the defaults).
2. Funnel/touch-rate study to explain the low count: the 0.30% cap and the pre-09:35 touches. Hypothesis `entry_delay 1`
   (as in mr_gapfade): doubles trades but the added trades are break-even (PF 1.37 -> 1.22), MES negative. Rejected.
3. Prescribed grid on both contracts and both periods; stop-entry both-sides identified as the only robust region.
4. Stop-mode follow-up (tgt_atr, exit_time, stop_valid_until) and prescribed market-mode follow-up on MES.
5. Mid-run the engine was modified by another session (engine.py/run.py/lucid.py/batch.py at 16:43-16:44, lucid.py again
   ~16:55); the first grid pass (old engine) gave 49 trades / PF 1.21 for the chosen cell vs 47 / 1.29 now. All seven
   batches were re-run on the current engine and verified identical across `backtest.run`, `--jobs 1` and `--jobs 2`.
6. Not tried (no stated reason beyond the test window): weekday or VIX-bucket filters, per-side stops, long-only on MAIN.

## Engine notes
- `backtest.run --mc` crashes at the JSON dump: `monthly_pass_rate` is keyed by pandas `Period`; `json.dumps(default=float)`
  does not convert keys. (Trades/metrics are printed before the crash; `--save` is not reached.)
- `lucid_scan`'s "best" row is now chosen on a lower-bound column that equals -146 (the fee) for every size here, so it
  returns 5 micros with expected net -146 while the 10-micro row has +$129 point estimate. `final.json` reports the
  10-micro row and states the selection.

## Verdict
**Marginal.** The published 09:35 market fade is not an edge on 2025-26 (nor a plateau). The Williams stop-entry
re-cross on MNQ, both sides, 0.5% cap, is a real but thin and rare edge: PF 1.29-1.39 on 47 trades MAIN, 1.56 on 53
trades PRIOR, ~$15/trade/micro, ~2 trades a month. Far below the guide's "good" bar (PF >= 1.5 with >= 60 trades) and
useless as a standalone Lucid evaluation vehicle (median 79 days to pass). Possible portfolio leg next to mr_gapfade
(different days: gapfade requires the open inside the prior range, this requires it outside).

## Walk-forward assessment (2026-10-03; `python3 -m backtest.final_select --ids mr_pdrange --jobs 2 --wf_start 2022-01-01 --max_combos 16`)
Honest yardstick: IS 12 months -> OOS 3 months, parameters chosen on trailing data only, base = final.json params (stop, 0.5, 1.0, both,
tgt_atr 0.5), grid coarsened to 16 = entry {market, stop} x max_dist {0.2, 0.5} x stop_mult {1.0, 1.5} x sides {both, long}
(`subgrid` drops max_dist 0.30). Output: `walkforward.json`, `wf_oos_2025_daily.csv`, `wf_oos_2025_bars.parquet`.

| stream | trades | net $/micro | PF | Sharpe | pos months | maxDD intra |
|---|---|---|---|---|---|---|
| WF OOS 2025-01..2026-09 (`wf_2025`) | 12 | +141 | 1.31 | 0.58 | 0.14 (3/21) | -273 |
| WF OOS 2023-01..2026-09 (`wf_all`) | 34 | +320 | 1.24 | 0.49 | 0.20 | -517 |
| fixed final params, MAIN (`fixed_main`) | 47 | +774 | 1.39 | 0.71 | 0.57 | -551 |
| fixed final params, PRIOR (`fixed_prior`) | 53 | +793 | 1.56 | 0.98 | 0.54 | -299 |

- The selector requires >= 30 in-sample trades per 12-month window. The stop-entry cells trade ~25-27 times a year, so they
  rarely qualify; only 5 of 15 windows selected any cell at all and only 2 of the 7 OOS quarters in 2025-26 traded
  (2025Q1: stop/0.5/1.5 -> -$136 on 7 trades; 2026Q3: market/0.5/1.5 -> +$277 on 5 trades, PF 32, chosen with an IS Sharpe
  of -1.37, i.e. the least-bad of a negative set). 15 consecutive months of zero. The +$141 OOS net is one five-trade run.
- lucid_wf_2025 (bootstrap lower-bound sizing on the OOS stream): pass rate 0 at 5-10 micros, 0.16 at 15-20 micros,
  pass_within_21 = 0 at every size, p_first_payout / expected_net undefined (no evaluation ever reaches a funded resolution),
  exp_net_lb = -146 = zero_edge_exp_net (the fee) at every size, recommended = False.
- Proceed gates: wf_2025 PF 1.31 >= 1.03 but 12 trades < 40 (fail); fixed MAIN PF 1.39 >= 1.3 and PRIOR 1.56 >= 1.1 but
  47 MAIN trades < 60 (fail). No parameter change was attempted: the failure is trade frequency, which no cell in the grid
  fixes without moving into the market-mode cells that were -$640..-$840 on MAIN in the in-sample grid.
- Diagnosis: the in-sample story (stop re-cross PF 1.39/1.56) is neither refuted nor confirmed OOS; it is simply too rare
  (~2 trades/month, $12-16/trade/micro) to be selected by a trailing-12-month optimiser or to carry a Lucid evaluation.
  The P&L is a few 1:1 bracket trades per quarter with ~50% hit rate and a modest payoff asymmetry (avg win $98 / loss $75);
  one day equals 136% of the OOS net. Verdict: **dead** as a standalone candidate (documented, not pursued further).
