# tm_gold_donch - Gold intraday Donchian 20/10, long-only, FULL ~23h session, SMA-200 gate (family trend_momentum)

Module: `strategies/tm_gold_donch.py`. Research: `research/families/trend_momentum.md` section 9 (Turtle / Donchian);
spec `research/specs/trend_momentum.md` 13. Periods: MAIN = 2025-01-01..2026-09-30, PRIOR = 2023-01-01..2024-12-31,
regime check 2021-01-01..2023-12-31 (sideways gold). All numbers per ONE micro contract, after costs (engine: $1.30 RT
commission + 1 tick slippage per side on market/stop fills; MGC $10/pt, tick 0.10). Instruments: MGC (primary; GC same
rules), MNQ / MES on RTH bars only as a sanity comparison.

The one candidate in the lab that changes BOTH instrument and session: every other MGC leg trades the 08:20-13:30 pit; this one
trades the whole 18:00 -> 17:00 gold session with entries from the London open (02:00 ET) through the US pit morning (13:00 ET).

## Rules as implemented (all times ET)
- Bars: `B = resample(df1, bar, rth_only=False)` for gold = N-minute bars over the whole session, CONTINUOUS across sessions
  (channel and ATR state carry over the 17:00-18:00 break and over weekends, TradingView "ETH chart" semantics). MES/MNQ:
  `resample(df1, bar, rth_only=True, rth=(09:30, 16:00))`.
- Indicators on B, windows exclude bar k, `min_periods` = full window, NaN = no trade: `hh[k] = max(high[k-n_entry..k-1])`,
  `ll[k] = min(low[k-n_exit..k-1])`, `ATRb[k]` = Wilder ATR(20) of the N-min bars (bar k is closed at decision time).
- Daily (gold: one bar per 18:00 -> 17:00 session via `daily_bars(rth_only=False)`; equities: RTH daily bars). The daily series is
  built on 420 calendar days of earlier 1-min history plus the window (`load_1m` is cached) so that SMA(200) and the 12-month
  lookback are warm on the first session; only sessions < d are used: `prev_close = close.shift(1)`,
  `SMA_D(200) = close.rolling(200).mean().shift(1)`, `ATR14d_full = ATR(14).shift(1)`. `bias_ok[d]`: `sma200` -> prev_close >
  SMA_D(200); `tsmom12` -> prev_close > close.shift(253); `none` -> True.
- Signal (long only by default): `close[k] > hh[k]` and `bias_ok[day_id[k]]` and `entry_start <= tod[k] < last_entry` and
  `i_next[k] != -1` and hh, ll, ATRb, ATR14d not NaN and the module is flat and entries today < `max_trades`.
- Entry: `place(i_next[k], +1, stop_px = sp)` = market at the open of the next 1-min bar (+1 tick slip). `entry_ref = close[k]`;
  `sp = max(close - 2.0*ATRb, close - 0.5*ATR14d)` (the NEARER stop), rounded down to the tick; skip if `close - sp < 2 ticks`.
  `tgt 'none'` = no target; `'rr2'` -> `tgt_px = entry_ref + 2*(entry_ref - sp)`.
- Exits: (1) channel exit, first bar k' > k with `close[k'] < ll[k']` -> `exit_at(i_next[k'], which=+1)` (market at the next
  1-min open); (2) the fixed hard stop `sp`, checked by the engine on every 1-min bar; (3) forced flat at 16:30 (gold) / 15:55 (equities).
- Module state mirrors the engine (no second entry while in a position): flat again after the channel exit (from k'+1), a
  stop-touch on an N-bar after the signal bar (`low <= sp`), a target touch in `rr2` mode, or the forced flat / session end.
  Re-entry on a later breakout the same session up to `max_trades` = 2.
- Session / risk: `set_session(entry_start, last_entry + bar, flat)` (the signal bar starting just before 13:00 can still fill);
  `max_trades_day` 2; `daily_loss_stop` $80 (MGC Lucid block; MES 60 / MNQ 80); `daily_profit_stop` off.
- Look-ahead: channel windows end at k-1, the decision uses close[k], the order is at i_next[k], daily bias / ATR are shifted one
  session. Verified by hand on the first three MAIN trades (e.g. 2025-01-02 04:00 bar close 2638.048 > hh 2637.558 = max high of
  bars k-20..k-1; stop = min(2 x 2.509, 0.5 x 34.56) below the close = 2633.03 -> 2633.0; fill = next 1-min open 2638.004 + 0.10).

Defaults (`PARAMS` = Turtle System 1 lengths and 2N stop, long-only as in the Algomatic gold 2000-2025 test): bar 15, n_entry 20,
n_exit 10, bias sma200, direction long_only, stop_atr_bars 2.0, max_stop_atr 0.5, tgt none, entry_start 02:00, last_entry 13:00,
flat 16:30, max_trades 2, dls_block 80. Equity override: 09:35 / 15:00 / 15:55, dls 60 (MES) / 80 (MNQ).
GRID (16 combos): n_entry {20, 55} x n_exit {10, 20} x bias {sma200, none} x bar {15, 60}. Extra single runs: bias tsmom12, tgt rr2,
direction both (diagnostic only).

## Headline results (fixed defaults, per micro, after costs)

| contract | period | trades | net $ | win | PF | Sharpe | maxDD intra | pos months |
|---|---|---|---|---|---|---|---|---|
| MGC | MAIN 2025-01..2026-09 | 327 | -1,046 | 35% | 0.96 | -0.20 | -6,309 | 7/21 |
| MGC | PRIOR 2023-2024 | 377 | -452 | 32% | 0.96 | -0.18 | -1,484 | 9/24 |
| MGC | 2021-2023 (sideways gold) | 295 | -2,545 | 28% | 0.70 | -1.34 | -2,832 | 8/36 |
| MNQ | MAIN | 186 | -260 | 50% | 0.98 | -0.06 | -2,524 | 9/21 |
| MNQ | PRIOR | 179 | +1,369 | 47% | 1.11 | 0.40 | -1,745 | 13/24 (one day = 48% of net) |
| MES | MAIN | 197 | -418 | 48% | 0.95 | -0.20 | -1,583 | 7/21 |
| MES | PRIOR | 186 | -224 | 47% | 0.97 | -0.13 | -1,504 | 11/24 |

Extra single runs, MGC MAIN: bias tsmom12 387 trades PF 0.93 (net -2,372); tgt rr2 371 trades PF 0.92 (net -2,407); direction both
with no bias 552 trades PF 0.97 (shorts add nothing). The published rule loses in every period on every instrument.

## Walk-forward (the honest yardstick; `walkforward.json`, `wf_oos_2025_daily.csv`, `final_select.log`)
`final_select --wf_start 2022-01-01 --max_combos 16`, IS 12 months / OOS 3 months, metric Sharpe, grid = module GRID (16 combos).
- OOS 2025-01..2026-09: **171 trades, net +2,043, PF 1.15, Sharpe 0.53**, 43% win, 9/21 positive months, maxDD -2,825,
  largest day = 36% of net. Quarterly OOS nets: Q1-25 -800, Q2-25 +2,085, Q3-25 +1,873, Q4-25 -434, Q1-26 -964, Q2-26 -214,
  Q3-26 +497 (1 trade). Two quarters (Apr-Sep 2025, the steepest leg of the gold bull run) earn +3,958; the other five lose -1,915.
- Full OOS 2023-01..2026-09 (15 folds): 604 trades, net -650, PF 0.98, Sharpe -0.10. Every 2023-2024 fold lost (PF 0.52-1.01).
- Parameter path: 2023-2024 folds pick 15-min / 20-in / bias none (the IS Sharpe was mostly negative); from Q2-2025 the selector
  switches to 60-min bars, 55-in / 20-out, sma200 - the slowest cells, i.e. "buy the breakout and hold to 16:30 in a bull market".
- Q3-2026 has one trade: gold fell below its 200-day SMA (bias_ok share of sessions 100% through Q1-26, 73% Q2-26, 11% Q3-26), so
  the gate switched the system off - the intended regime behaviour, and also why there is no evidence about a post-bull regime.
- Lucid 50K Flex on the OOS stream: best 5 micros, pass rate 0.28 (zero-edge control 0.22), pass-within-21 0.20, P(first payout)
  0.18, expected net per evaluation +370 but bootstrap lower bound -146 (= the fee floor; P(exp net > 0) = 0.44), zero-edge
  control +16 -> `recommended` False.

## Grid (`grid_MGC.csv`; 16 combos x 2 periods)
- PRIOR 2023-2024: 0/16 cells profitable (PF 0.66-0.98). MAIN: 12/16 profitable; the best cells are the slowest ones (60-min /
  55-in / sma200: PF 1.40, 101 trades, net +3,502; 15-min / 55-in / 20-out / sma200: PF 1.19, 225 trades), the published 15-min
  20/10 cells are the worst (PF 0.93-0.98).
- Rank correlation of the 16 cells between periods: **-0.83** - what works on MAIN is what loses most on PRIOR (the slow cells
  are PF 0.66-0.74 on 2023-2024). No plateau; the MAIN ranking is the gold bull run, not a parameter edge. 0 cells with PF > 1 in
  both periods.

## Diagnostics (MGC, defaults; `report_MGC_main.txt` + scratch scripts)
- Exit mix MAIN: 149 stops at -140 avg (-20,926 total), 67 forced flats at 16:30 at +279 avg (+18,709, 96% win), 108 channel
  exits at +8 avg (+817), 3 session ends. The whole P&L is "the days gold trended into the close"; the 10-bar channel exit
  neither protects nor earns. PRIOR: 199 stops -10,830, 65 flats +7,913, 109 channel exits +2,426.
- Entry hour (MAIN): 02:00 bar +1,338 (64 trades, 42% win), 03-04 -1,170, 05:00 -2,252 (23 trades, 4% win), 06:00 +803,
  07:00 -1,654, 08-10 (pit open) +2,651 (96 trades, 34-58% win), 11-13 -762. Blocks: 02-05 London +168 (140 trades), 05-08
  pre-pit -3,103 (65), 08-13 pit +1,889 (122). The London block is the thesis of this spec and it is flat; the pre-pit block is
  where the London breakouts fail into the US open.
- Year split: 2025 236 trades +3,357; 2026 91 trades -4,403. The 2025 gain is Apr-Oct (+5,272 in 7 months); Dec-25 to Jun-26 lost
  in 7 consecutive months (-5,365). Stop size grew with gold volatility: median stop $98 (2025) -> $208 (2026); average stop loss
  -107 -> -246 per micro, worst day -844 (2026-03-23, two stops). 121 of 289 traded MAIN sessions end at or below the -$80 daily
  loss block after a single trade.
- Hold time quartiles 80 / 210 / 375 minutes; 0.73 trades per session; 38 sessions with the second entry.
- MAE/MFE: median MAE -8.4 pts vs median MFE +11.0; losers' median MFE +4.7 pts (= $47, the trades reach 0.5 stop distances in
  profit before failing). Max 12 consecutive losing trades, 7 consecutive losing days.
- VIX (lagged): 15-20 215 trades +1,132; 20-25 60 trades -1,906; others ~0.
- Control: buy gold at the 02:00 open and sell at the 16:30 flat on every bias-ok session, no costs: MAIN +3,059 (375 sessions,
  54% win), PRIOR +1,295 (489, 50%), 2021-2023 -3,920 (419, 44%). The strategy underperforms its own buy-and-hold-the-day control
  in every period: the breakout timing plus the 2N stop subtract value from a plain long-gold bet.
- Regime check demanded by the spec (PF >= 1.1 on 2021-2023 sideways gold): FAILED, PF 0.70.

## What was tried and why it failed
- Published 15-min 20/10 rule: PF 0.96 on MAIN and PRIOR, 0.70 on 2021-2023. Stops outnumber good flats 2:1 and the channel
  exit adds nothing.
- Daily gate: sma200 vs none changes little (bias_ok is on for 84-100% of sessions in 2024-2026); tsmom12 is worse (PF 0.93).
- 2R target: worse (PF 0.92) - the only winners are the hold-to-16:30 trend days, which a target caps.
- Shorts (direction both): PF 0.97 with twice the trades - confirms the research note that short gold Donchian loses.
- Slower channels / 60-min bars: PF 1.2-1.4 on MAIN, 0.66-0.74 on PRIOR, rank correlation -0.83 -> a bull-market fit, not an edge.
- Equity sanity run (MNQ/MES RTH): PF 0.95-0.98 on MAIN; the MNQ PRIOR PF 1.11 rests on one day worth 48% of the net.

## Verdict: marginal (by the lab rule), dead in substance
Rule: 'marginal' if walk-forward OOS 2025 PF >= 1.03 with >= 40 trades -> 171 trades, PF 1.15, so the rule says **marginal**.
Honest reading: the OOS stream is two quarters of the 2025 gold bull run (+3,958) against five losing quarters (-1,915); the full
OOS 2023-2026 is PF 0.98; the fixed rule loses in MAIN, PRIOR and 2021-2023; the grid is anti-correlated across periods; the
strategy underperforms a costless buy-02:00 / sell-16:30 control in every period; the Lucid lower bound is the fee floor and the
scan does not recommend any size. The regime dependence is total: with gold below its 200-day SMA since mid-2026 the gate shuts the
system off, and nothing in the record says what it does in the next sideways or bear phase except the 2021-2023 PF 0.70.
Do not allocate; the only residual value is as a low-correlation diagnostic leg for `portfolio_opt`, and the 5-micro Lucid sizing
with a negative lower bound does not justify even that.
