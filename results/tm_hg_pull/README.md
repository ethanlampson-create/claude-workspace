# tm_hg_pull — Raschke-Connors "Holy Grail": ADX(14) > 30 and rising, first pullback to the 20-EMA, buy stop over the touch bar

Family: `trend_momentum` (research `research/families/trend_momentum.md` sections 10 and 14, spec 10 in
`research/specs/trend_momentum.md`). Module: `strategies/tm_hg_pull.py`. Instruments tested: MES, MNQ (RTH 5-min bars,
entries 10:00-15:00, flat 15:55) and MGC (pit 5-min bars 08:20-13:30, entries 08:35-12:30, flat 13:25).
Periods: MAIN 2025-01-01..2026-09-30, PRIOR 2023-01-01..2024-12-31. All numbers per ONE micro contract after engine costs
($1.30 RT commission + 1 tick slippage per side on stop fills; $2.30/trade on MNQ, $3.80 on MES, $3.30 on MGC).
Evidence quality going in: 1-2 (Street Smarts 1995 + anecdotes, no quantified ES/NQ test). The spec said to drop it fast if
PF < 1.2 on 2023-2026 with the default parameters. It is below that bar on every contract.

## Rules as implemented
- Bars: `resample(df1, bar, rth_only=True, rth=(contract.rth_open, contract.rth_close))`, continuous RTH series across sessions
  (indicator state carries over the overnight gap, same convention as `bot_squeeze_lb`).
- Indicators on the N-min bars, `min_periods` = full window: EMA(20) of close, Wilder ADX(14) (`strategies.common.adx`),
  Wilder ATR(14) of the bars (ATRb), plus the daily RTH ATR(14) shifted one day (ATR14d) for the stop cap.
- Trend state at bar k: `ADX[k] > adx_min` AND the ADX was "> adx_min and rising" (ADX[j] > ADX[j-1]) on at least one of the
  last `adx_rise_lb` bars (k included) AND `EMA[k] > EMA[k-3]` AND `close[k-1] > EMA[k-1]` (shorts mirror).
- Touch bar: long `low[k] <= EMA[k]` and `close[k] > EMA[k] - 0.5*ATRb[k]`; short mirror. Window `10:00 <= tod[k] < 15:00`,
  `i_next[k] != -1`, module flat (no position, no live pending order), < max_trades entries today, no NaN indicator.
- Entry: buy stop at `high[k] + 1 tick` (sell stop at `low[k] - 1 tick`), placed at `i_next[k]`, live for 30 one-minute bars
  (also cancelled at the end of the entry window). Fill = max(open, level) + 1 tick.
- Stop: `swing` = min(low[k-2..k]) - 1 tick (long) / max(high[k-2..k]) + 1 tick (short); `keltner` = EMA -/+ 2.0*ATRb.
  R = |level - stop|; skip if R < 2 ticks; if R > 0.5*ATR14d the stop is placed R = 0.5*ATR14d from the fill (`stop_pts`).
- Target: `swing` = max(high[k-20..k-1]) (long) / min(low[k-20..k-1]) (short), trade skipped if the room is < 1R;
  `rr` = level +/- 1.5R. Trail: once the bar extreme is >= 1R beyond the fill, stop = extreme -/+ R (engine ratchet; the
  stop is at breakeven on activation). Forced flat 15:55 (13:25 gold). Re-entry on the next touch after a stop-out, max 3/day.
- Risk block: `daily_loss_stop` MES $60 / MNQ $80 / MGC $80 per micro, `daily_profit_stop` off.
- Module state mirror: walked on the 1-minute bars (pending fill, stop/target/trail, session end) so the module never places
  an order while the engine is in a position. Verified on MNQ MAIN: 243 placements, 153 engine trades, 90 expired unfilled,
  0 placements inside an engine position. Five random placements re-derived by hand (level, swing stop, swing target, trend
  gate, armed state): all correct. Look-ahead: the touch bar is closed before `i_next`, the entry is a stop beyond its extreme,
  all windows are full-`min_periods` rolling, ATR14d shifted one day.

### One deviation from the spec text, and why (`adx_rise_lb`)
The spec writes the trend gate as `ADX[k] > ADX[k-1]` on the touch bar itself. That conjunction almost never happens: the ADX
falls while price retraces to the EMA. Literal implementation (`adx_rise_lb=1`) on 2025-26: **MES 5 trades, MNQ 4 trades**
(PRIOR MNQ: 6 trades, 0 winners) against the spec's own expectation of 100-300 trades per 21 months. The book's rule is
"ADX > 30 and rising" to identify the trend, then wait for the retracement. `adx_rise_lb = 6` (30 minutes on 5-min bars)
keeps that reading: the ADX must still be above 30 on the touch bar and must have been rising through 30 within the last six
bars. Candidate touches in the entry window, MNQ 2025-26: literal 25, lb=3 193, **lb=6 488**, lb=12 755, no rising condition 839.
Six bars is the smallest window that gives the trade count the spec expected; it was fixed before any P&L was looked at and is
not in the grid.

Defaults (`PARAMS`): bar 5, adx_len 14, adx_min 30, adx_rise_lb 6, ema_len 20, stop_mode swing, kc_mult 2.0, atr_len 14,
tgt_mode swing, rr 1.5, swing_len 20, valid_minutes 30, trail_after_1r True, entry 10:00-15:00, flat 15:55, max_trades 3,
max_stop_atr 0.5 (spec 10 prop cap), dls_block {MES 60, MNQ 80, MGC 80}. Gold: entries 08:35-12:30, flat 13:25.

## Metrics per period and contract (defaults)
| contract | period | trades | net | win | avg trade | PF | Sharpe | max DD intraday | pos days | pos months |
|---|---|---|---|---|---|---|---|---|---|---|
| MNQ | MAIN | 153 | +756 | 47.7% | +4.9 | 1.12 | 0.39 | -1,447 | 47% | 48% |
| MNQ | PRIOR | 116 | -939 | 43.1% | -8.1 | 0.73 | -1.02 | -1,058 | 41% | 29% |
| MES | MAIN | 139 | +267 | 52.5% | +1.9 | 1.10 | 0.28 | -437 | 51% | 52% |
| MES | PRIOR | 96 | -128 | 40.6% | -1.3 | 0.92 | -0.28 | -715 | 42% | 38% |
| MGC | MAIN | 141 | -1,832 | 44.7% | -13.0 | 0.70 | -1.11 | -2,151 | 42% | 29% |
| MGC | PRIOR | 109 | -662 | 43.1% | -6.1 | 0.65 | -1.26 | -669 | 45% | 21% |

Literal spec (`adx_rise_lb=1`): MES MAIN 5 trades +133; MNQ MAIN 4 trades -53; MNQ PRIOR 6 trades -281. Not a strategy.
Optional `max_trades=1` on MNQ: MAIN 126 trades PF 1.14 (+743), PRIOR 97 trades PF 0.74 (-746): same picture.

## Diagnostics (MNQ MAIN, defaults, `backtest.report` + custom funnel)
- Exit mix: 75 stops (-6,143), 32 targets (+5,198), 44 trail exits (+1,707), 2 flat (-6). WR 47.7% x payoff 1.23 =
  PF 1.12. Avg win $95, avg loss $78: the stop is tight as designed (median |entry-exit| 32 NQ pts).
- Costs: $2.30/trade, $352 total = 4.9% of gross wins; avg trade +$4.9 is ~2x costs, i.e. at the floor of "acceptable".
- By ADX at the setup bar: 30-40 bucket 94 trades -427; 40+ bucket 38 trades +1,689; the (armed-but-fallen) < 30 bucket
  21 trades -506. The whole net comes from the strongest-trend minority; the nominal "ADX > 30" zone loses.
- By side: longs 61 trades +1,528 (avg +25), shorts 92 trades -772 (avg -8). By hour: 10:00 +662 (52), 11:00 +503 (43),
  12:00 -116, 13:00 -411 (19), 14:00 +182, 15:00 -64. Monday -497 on 21 trades; Thursday +837 on 36.
- Months: 10/21 positive; largest month 2026-07 +642 (85% of net), 2025-10 -259 on 17 trades. Noise-shaped.
- 37% of placed stop orders expire unfilled within 30 minutes (the pullback keeps going), which is the mechanism by which
  the entry avoids some failed pullbacks but also why 300+ setups become 150 trades.

## Grids (module GRID, 16 combos: adx_min {25,30} x stop_mode {swing,keltner} x tgt_mode {swing,rr} x bar {5,15})
Files: `grid_MNQ.csv`, `grid_MES.csv`, `grid_MGC.csv` (both periods each).
- MNQ: MAIN 8/16 profitable, median PF 0.99, best PF 1.31 (adx25/keltner/swing, 54 trades) and best net +3,200
  (adx25/keltner/rr, 211 trades, PF 1.17, DD -3,025). PRIOR 5/16 profitable, median PF 0.80; every bar-5 row with > 100
  trades loses (PF 0.55-0.90). Rank correlation of the 16 combos between periods **-0.42**: what wins in 2025-26 lost in
  2023-24. Bar 15 loses on both periods in 7 of 8 rows.
- MES: MAIN 7/16 profitable, median PF 0.85; the two keltner/swing rows (24-31 trades) show PF 3.3-4.0 on 2025-26 but
  PF 1.0-2.0 on 6-32 trades in PRIOR: small-sample spikes. adx25/keltner/rr: MAIN PF 1.33 (216 trades), PRIOR 0.98 (192).
  Rank correlation between periods -0.11.
- MGC: 7/16 profitable in each period, median PF 0.94 / 0.87, best net +558 / +966 on thin rows; defaults PF 0.65 / 0.70.
  Rank correlation 0.79 but around a losing centre: gold pit hours do not trend-pullback on 5-min bars with this gate.
- No plateau anywhere: the only PRIOR-positive rows have 6-45 trades, the only dense rows are negative in PRIOR.

## Walk-forward out-of-sample (`final_select`, 2026-10-04)
`python3 -m backtest.final_select --ids tm_hg_pull --jobs 2 --wf_start 2022-01-01 --max_combos 16` on MNQ (IS 12 months,
OOS 3 months, selection by IS daily Sharpe over the 16-combo GRID, 15 windows 2023-01..2026-09). Selected parameters flip
between swing/keltner, rr/swing and bar 5/15 almost every window; 8/15 OOS windows negative; OOS window PF 0.07..3.7.

| stream | trades | net | win | avg trade | PF | Sharpe | max DD intraday | pos days | pos months | worst day | worst month |
|---|---|---|---|---|---|---|---|---|---|---|---|
| WF OOS 2025-01..2026-09 | 167 | -1,036 | 45.5% | -6.2 | **0.91** | -0.34 | -2,710 | 46% | 43% (9/21) | -430 | -711 (2026-04) |
| WF OOS 2023-01..2026-09 | 324 | -2,372 | 46.3% | -7.3 | 0.89 | -0.42 | -4,373 | 47% | 42% | -430 | -727 |
| fixed defaults MAIN | 153 | +756 | 47.7% | +4.9 | 1.12 | 0.39 | -1,447 | 47% | 48% | -349 | -259 |
| fixed defaults PRIOR | 116 | -939 | 43.1% | -8.1 | 0.73 | -1.02 | -1,058 | 41% | 29% | -161 | -204 |

Lucid 50K Flex on the WF OOS 2025 stream (`lucid_wf_2025`): best lower-bound size 5 micros, pass rate 0.07, pass within
21 sessions 0.045, P(first payout) 0.05, expected net per evaluation -$63 (lower bound -$146 = the fee; zero-edge control
-$43), `recommended = 0`. At 10+ micros the pass rate is 0.03-0.07 and the expected net is the lost fee.

## Attempts log
1. Faithful implementation of the spec text: 4-5 trades per 21 months on MES/MNQ (ADX rising on the touch bar is nearly
   impossible). Funnel analysis of alternative "rising" definitions; `adx_rise_lb=6` adopted before looking at P&L.
2. Smoke tests MES/MNQ/MGC x MAIN/PRIOR: 96-153 trades per period, PF 1.10-1.12 on MES/MNQ MAIN, < 1 everywhere else.
3. Engine-mirror audit: 0 placements inside engine positions; 5 random trades re-derived by hand; the first check that
   flagged 33 "mismatches" was counting first-bar fills (placement index == entry index) and was corrected.
4. Report on MNQ MAIN: edge only in the ADX 40+ bucket and in longs; costs 5% of gross; months noise-shaped.
5. Module grid on all three contracts, both periods: no plateau, negative rank correlation MNQ/MES.
6. Optional max_trades 1 and literal adx_rise_lb 1 runs: no change in the picture.
7. Walk-forward OOS 2025: PF 0.91 on 167 trades, Lucid not recommended at any size.

## Verdict: dead
The Holy Grail pullback as written has no usable edge on MES/MNQ/MGC intraday in 2023-2026: default-parameter PF 1.12/1.10
on 2025-26 (below the family's own 1.2 drop threshold), 0.73/0.92 on 2023-24, 0.65-0.70 on gold, a 16-combo grid with
negative cross-period rank correlation, and a walk-forward OOS 2025 PF of 0.91 with negative Sharpe. The only positive pocket
(ADX > 40 longs, ~40 trades) is too small to build on and would be a post-hoc filter. No engine bugs found; the module is
correct and can serve as the pullback-entry template if a trend-day gate (spec 8) ever justifies revisiting it.
