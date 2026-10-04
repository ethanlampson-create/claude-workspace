# tm_trendday - trend-day runner (composite 10:30 flag, direction of the open, trailing runner)

Family: trend_momentum (research `research/families/trend_momentum.md` section 19; spec `research/specs/trend_momentum.md` spec 8).
Module: `strategies/tm_trendday.py`. Instruments: MES, MNQ (equity RTH 09:30-16:00 ET; MGC not in this round).
Verdict: **marginal** (walk-forward OOS 2025-01..2026-09 on MES: PF 1.15, 186 trades, Sharpe 0.57; but the published
defaults are flat on both periods, the OOS edge is concentrated in one quarter, and the Lucid scan equals the zero-edge
control at every size).

## Rules as implemented (all times ET; decisions at 10:30 use only bars with tod <= 10:29 plus shifted daily data)
- Daily (sessions < d): `D = daily_bars(rth_only)`, `atr = daily_atr(14)` (shifted), prev_close / pd_high / pd_low / range1 /
  O1 / C1 = session d-1, H2 / L2 = session d-2. `NR4[d]` = range1 is the smallest of the 4 prior sessions (needs 4), `NR7`
  analog, `ID[d]` = H1 < H2 and L1 > L2. `O930` = open of the tod == 09:30 bar.
- Intraday (known at 10:30): IB = `opening_range('09:30', 60)` -> ib_high, ib_low, c1029 (close of the 10:29 bar), width, ib_mid.
  OR30 = `opening_range('09:30', 30)` -> or_high, or_low, or_close. Skip the day if IB < 55 bars, OR30 < 28 bars, atr NaN,
  early close (`session_info`), width == 0 or the 09:30 bar is missing.
- `direction = sign(c1029 - O930)` (0 -> no trade). Flags (0/1): (a) gap_out: |O930 - prev_close| >= gap_atr*atr AND the open is
  outside the prior RTH range AND the gap points in `direction`; (b) narrow_ib: width < narrow_ib_atr*atr; (c) open_drive:
  OR30 closes in the top 25% of its range and above pd_high (long) / bottom 25% and below pd_low (short), same side as
  `direction`; (d) nr_prior: NR4 or NR7 or ID. `score = a+b+c+d`.
- Negative filters: width > max_ib_atr*atr (extreme IB) -> skip; `skip_after_trend_day` and |C1 - O1| >= 0.7*range1 -> skip.
- trade_day = score >= min_score and direction != 0 and no negative filter. One trade per day, the direction's side only.
- Entry at i1030 (the tod == 10:30 bar = IB i_end + 1, same session): `market_1030` = market at the 10:30 open (+1 tick slip),
  entry_ref = c1029; `ib_break_stop` = stop order at ib_high + 1 tick / ib_low - 1 tick, live for the 90 minutes to last_entry
  (fills at the 10:30 open if price is already through), entry_ref = level.
- Stop: `ib_mid` -> ib_mid; `ib_opp` -> opposite IB extreme. dist = (entry_ref - raw_stop)*direction; dist <= 2 ticks -> skip the
  day; dist > max_stop_atr*atr -> stop_pts = max_stop_atr*atr relative to the fill, else stop_px = raw_stop.
- Exit: trailing runner, trail_pts = trail_atr*atr, trail_act_pts = trail_act_atr*atr (engine ratchet off the bar extreme once MFE >=
  act, exit when the close is through the trailed stop). tgt_atr > 0 adds a fixed target (default none). Forced flat 15:55.
- Session/risk: `set_session('10:30', last_entry, flat)`, `max_trades_day = 1`, daily_loss_stop = MES $60 / MNQ $80,
  daily_profit_stop = 1.5 x (MES $120 / MNQ $160).
- Implementation note: `tie_trail_act=True` (default) makes trail_act_atr follow trail_atr so the GRID over trail_atr moves both
  (spec: "trail_act_atr tied to trail_atr"); with the defaults both are 0.3 either way. `direction='long'` is the optional
  longs-only run.

Defaults (PARAMS = the spec's published composite): min_score 2, entry_mode market_1030, stop_mode ib_mid, max_stop_atr 0.5,
trail_atr 0.3 / trail_act_atr 0.3, tgt_atr 0, gap_atr 0.7, narrow_ib_atr 0.5, max_ib_atr 1.5, skip_after_trend_day True,
last_entry 12:00, flat 15:55, max_trades 1, dps_mult 1.5.
GRID (16 combos): min_score {1, 2} x entry_mode {market_1030, ib_break_stop} x stop_mode {ib_mid, ib_opp} x trail_atr {0.25, 0.4}.

## Metrics, defaults (per 1 micro, after costs)

| contract | period | trades | net $ | win | PF | avg trade | Sharpe | maxDD intra | pos months |
|---|---|---|---|---|---|---|---|---|---|
| MES | MAIN 2025-01..2026-09 | 99 | -47 | 0.364 | 0.985 | -0.5 | -0.04 | -722 | 0.52 |
| MES | PRIOR 2023-01..2024-12 | 90 | +19 | 0.322 | 1.010 | +0.2 | 0.02 | -570 | 0.25 |
| MNQ | MAIN | 100 | -1849 | 0.300 | 0.728 | -18.5 | -0.88 | -2650 | 0.33 |
| MNQ | PRIOR | 82 | +507 | 0.329 | 1.136 | +6.2 | 0.29 | -988 | 0.33 |
| MES longs only | MAIN / PRIOR | 60 / 56 | +42 / -348 | | 1.02 / 0.74 | | | | |
| MES longs only, ib_opp | MAIN / PRIOR | 73 / 62 | +30 / +188 | | 1.01 / 1.09 | | | | |

Frequency ~1.1 trades/week (99-100 trades in 21 months; 121 flagged days on MES MAIN, the rest skipped because the ib_mid
stop was within 2 ticks of c1029 or the session was thin). The published composite is a coin flip on both instruments on
both periods: the day classification does not produce a tradable edge with a market entry and an IB-midpoint stop.

## Diagnostics (MES MAIN, defaults; `python3 -m backtest.report`, plus a score/flag breakdown)
- Flag base rates on valid days: narrow_ib 62% (the 0.5-ATR cut-off is loose on this feed: a 60-min IB under half the daily ATR is
  the norm, not the exception), nr_prior 31%, open_drive 21%, gap_out 5%. Score distribution: 0: 91, 1: 194, 2: 121, 3: 21, 4: 2 days.
  So "score >= 2" is mostly narrow_ib + nr_prior (both weak flags), and the two strong flags (gap_out, open_drive) rarely fire.
- P&L by score: score 2: 82 trades, PF 0.83, -$485; score 3: 15 trades, PF 3.1, +$500 (MES PRIOR score 3: 14 trades PF 3.5; but MNQ
  MAIN score 3: 14 trades PF 0.17, -$706). Score 3+ is 15% of trades and the sign flips across instruments: not a usable filter.
- By flag fired (MES MAIN): narrow_ib PF 1.06 vs 0.64 without; open_drive 1.10 vs 0.91; nr_prior 1.03 vs 0.80; gap_out 0.79 (11 trades).
  On MNQ MAIN every flag subgroup is below 1 except nr_prior = 0 (PF 1.21, 22 trades). No flag is robust across instruments.
- Exit split: stop 62% of trades (avg -$50), flat 23% (avg +$99, 100% winners), trail 14% (avg +$56). Winners hold a median 325
  bars (to the close), losers 25 bars. MFE quantiles (ATR units) 0.05 / 0.15 / 0.31 / 0.41 (p25/50/75/90): only 26% of trades ever
  reach the 0.3-ATR trail activation, so the "runner" is a 15:55 flat exit on a quarter of the days and a stop on the rest.
- The ib_mid stop is the problem: median MAE -0.09 ATR, stop distance from c1029 to ib_mid is typically 0.1-0.2 ATR, i.e. inside
  the noise of the next hour; 62% stop rate at ~3 ES points.
- Sides (MES MAIN): longs 60 trades PF 1.02, shorts 39 PF 0.93; MNQ MAIN longs PF 0.61 (-$1823), shorts 0.99. Weekday: Monday
  +$545 (24 trades), Friday -$420 (16); noise-level with these counts.
- Concentration: top-5 trades sum +$1128 against a net of -$47; best month +$324, worst -$368; 52% positive months.
- Validity filter: 2023 has 117 invalid sessions (the CFD feed is sparse in Feb-Mar 2023: 30 bars per 60-min IB, flagged as early
  close / IB < 55 bars), 2024 has 14, 2025-26 have 17 (holidays). Those days are skipped, which is the intended behaviour.

## Grid (`grid_MES.csv`, `grid_MNQ.csv`; 16 combos x MAIN + PRIOR)
- MES MAIN: 9/16 positive. Plateau = market_1030 + ib_opp: min_score 2 PF 1.20-1.29 (121 trades, net +$976..+$1508, Sharpe
  0.6-0.8, DD -$690), min_score 1 PF 1.04-1.12 (264 trades). ib_mid variants PF 0.93-1.13; every ib_break_stop + min_score 1 combo
  loses (PF 0.83-0.88, DD up to -$2.7k). MES PRIOR: 15/16 positive, best = ib_break_stop + ib_opp (PF 1.39-1.45, 166 trades) and
  market_1030 + ib_opp + trail 0.4 (PF 1.32, 239 trades). Rank correlation MAIN vs PRIOR = -0.39: the ranking does not persist.
- MNQ MAIN: 1/16 positive (market_1030 / ib_opp / trail 0.25 / score 2: PF 1.06, net +$547, DD -$3.3k). MNQ PRIOR: 16/16 positive
  (PF 1.03-1.39). Rank correlation -0.29. MNQ 2025-26 kills the composite regardless of parameters.
- Consistent message: the wider ib_opp stop beats ib_mid everywhere (fewer noise stop-outs); market at 10:30 beats the IB-break
  stop entry on MAIN but not on PRIOR; trail 0.25 vs 0.4 is a wash.

## Walk-forward out-of-sample (the honest yardstick)
`python3 -m backtest.final_select --ids tm_trendday --jobs 2 --wf_start 2022-01-01 --max_combos 16` -> `walkforward.json`,
`wf_oos_2025_daily.csv`, `wf_oos_2025_bars.parquet`. IS 12 months / OOS 3 months, parameters chosen on trailing IS by daily
Sharpe, base = final.json params (the defaults), search space = module GRID (16 combos). Contract MES.

| stream (MES, 1 micro) | trades | net $ | PF | win | avg trade | Sharpe | pos months | maxDD intra | largest day share |
|---|---|---|---|---|---|---|---|---|---|
| OOS 2025-01..2026-09 | 186 | +1230 | 1.149 | 0.495 | +6.6 | 0.57 | 0.62 | -889 | 0.33 |
| OOS 2023-01..2026-09 (all) | 341 | +2641 | 1.198 | 0.525 | +7.7 | 0.68 | 0.58 | -889 | 0.15 |
| fixed defaults MAIN | 99 | -47 | 0.985 | 0.364 | -0.5 | -0.04 | 0.52 | -722 | - |
| fixed defaults PRIOR | 90 | +19 | 1.010 | 0.322 | +0.2 | 0.02 | 0.25 | -570 | - |

- Parameter path: stop_mode = ib_opp in all 15 windows (ib_mid, the published default, was never selected); entry_mode
  market_1030 from 2024-10 on; min_score alternates 1/2; trail_atr 0.4 in 12 of 15 windows. So the OOS stream is effectively
  "market at 10:30 on flagged days, stop at the opposite IB extreme (capped 0.5 ATR), 0.4-ATR trail".
- OOS quarters 2025-26: +474, -538, -44, +988, -63, +508, -96. The 2025-10..12 quarter is 80% of the OOS net; the three
  score-2 quarters with market entry (2025-Q1, 2026-Q2) are strong, the min_score 1 quarters (2025-Q2/Q3) lose. Largest single
  day = 33% of the OOS net (consistency rule risk).
- OOS monthly: 13/21 positive; worst -$331 (2025-05), best +$599 (2025-03).
- Lucid scan on the OOS 2025-26 daily stream: best size 5 micros, pass_rate 0.30, median 51 sessions to pass, pass_within_21 =
  0.016, P(first payout) = 0.00 (every funded path breaches before a payout), expected net per eval -$146 = exp_net_lb = zero-edge
  control (-$146) at 5, 10, 20, 30, 40 micros; `recommended = False`. The strategy is indistinguishable from no edge at the
  account level.

## What I tried, what failed
- Published composite (ib_mid stop, market 10:30, score >= 2): flat on MES both periods, -$1.8k on MNQ MAIN. Cause: the midpoint
  stop is 0.1-0.2 ATR from the entry and is hit on 62% of days before the runner can develop; only 26% of trades reach the trail.
- Longs only: no improvement (MES PF 1.02 MAIN / 0.74 PRIOR; with ib_opp 1.01 / 1.09).
- Score >= 3 (the two strong flags): 15-20 trades per period, PF 3.1-3.5 on MES but 0.17 on MNQ MAIN; too few and not robust.
- ib_opp stop: the only consistent improvement (MES MAIN PF 1.2-1.3, PRIOR 1.1-1.4) and what the walk-forward selected; still
  avg trade +$7-12/micro (about 2-3x the $1.30 commission plus 2 ticks slippage = ~$3.80, borderline on the 2x-costs rule).

## Honest verdict
**marginal** by the stated gate (walk-forward OOS 2025 PF 1.15 >= 1.03 with 186 >= 40 trades), but weak: the published
defaults have no edge (PF 0.99 / 1.01), the OOS stream relies on one parameter (ib_opp) that the published rule does not use, the
OOS net is 80% one quarter and 33% one day, Sharpe 0.57 is below the 1.5 bar, and the Lucid Monte Carlo equals the zero-edge
control at every size. The day-type classification itself (narrow IB + NR prior day dominating the score) does not separate
trend days from rotation days well enough on 2025-26 ES/NQ. Not a standalone evaluation vehicle; at most a low-weight
diversifier (trades at 10:30, holds to the close, flat 80% of days) if a later verification confirms the ib_opp variant.
