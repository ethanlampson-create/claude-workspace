# bot_rsi_dip - RSI(5) cross-back dip-buy, Chandelier(22,1) ratchet exit, SMA50>SMA200 regime (family bot_popular_indicators)

Module: `strategies/bot_rsi_dip.py`. Research: `research/families/bot_popular_indicators.md` 2.5 (StockCharts SystemTrader,
Arthur Hill 2016, daily SPY/QQQ/IJR 2000-2016) and `research/specs/bot_popular_indicators.md` section 5. Periods: MAIN =
2025-01-01..2026-09-30, PRIOR = 2023-01-01..2024-12-31. All numbers per ONE micro contract, after costs (engine: $1.30 RT
commission + 1 tick slippage per side on market/stop fills).

## Rules as implemented
- 5-min RTH bars from the 1-min feed (`resample(df1, 5, rth_only=True, rth=(rth_open, rth_close))`), continuous across sessions
  (TradingView "RTH chart" semantics: the first bar of a day continues the previous day's RSI / ATR / Chandelier state).
- Indicators on the 5-min closes: Wilder RSI(rsi_len), Wilder ATR(14) (hard stop) and ATR(ce_len) (Chandelier). Chandelier
  (everget, useClose): `ls_raw = highest(close, 22) - ce_mult*ATR(22)`, ratcheted up while `close[k-1] > ls[k-1]`; `ss` mirrored.
  The recursion was checked against a naive re-implementation (identical on 4,140 bars).
- Threshold `{2: 10, 5: 30, 14: 30}[rsi_len]`; short threshold `100 - thresh`.
- Regime per session (`sma50_200`): SMA(50) vs SMA(200) of the cash-index daily closes (`SPX_1d` for MES, `NDX_1d` for MNQ,
  `GC_1d` for MGC) at the row strictly before the session date (same lag as `orb_close30.daily_trend`). Longs only when
  SMA50 > SMA200; shorts (direction `both`) only when SMA50 < SMA200; NaN = no trade.
- Entry (variant B, default): 5-min bar k with `entry_start <= tod < last_entry` and `RSI[k-1] < 30 <= RSI[k]` (cross back
  above) -> market at the next 1-min open (+1 tick), hard stop `close[k] - stop_atr*ATR14[k]` rounded down to the tick (shorts
  mirrored). Variant A (cross below, the original's falling-knife entry) is available but not in the grid. No target.
- Exit: first confirmed 5-min bar k' with `k' - k >= min_hold` and `close[k'] < ls[k']` -> `exit_at(i_next[k'], +1)` (market at
  the next 1-min open). Plus the hard stop and forced flat at 15:55 (MGC 13:25).
- Module-side position state: one trade at a time; the state goes flat on the chandelier exit (from k'+1), when a 5-min bar's
  low touches the stop (mirror of the engine's stop), or at the session end. Up to `max_trades` = 3 entries per day.
- Session: `set_session(entry_start, last_entry + 5 min, flat)` (the engine window ends one bar after `last_entry` so the signal
  bar that starts just before 15:00 can fill at its `i_next`; this keeps the module state and the engine in step).
  `daily_loss_stop` / `daily_profit_stop` = Lucid risk block x `dls_mult` / `dps_mult`: MES 60/120, MNQ 80/160, MGC 80/160.
- Gold (MGC): pit mapping, entries 08:35-12:30, flat 13:25, regime from GC_1d closes.

Defaults (`PARAMS`, = the published SystemTrader rule translated to 5-min bars): bar 5, rsi_len 5, variant B, regime sma50_200,
direction long_only, ce_len 22, ce_mult 1.0, stop_atr 1.5, min_hold 1, entry_start 09:45, last_entry 15:00, flat 15:55,
max_trades 3, dls_mult 1.0, dps_mult 1.0. Optional diagnostic switch `exit_arm` (default False, see below).

Grid (16 combos, used by the walk-forward): rsi_len {2, 5} x ce_mult {1.0, 2.0} x direction {long_only, both} x stop_atr {1.5, 2.5}.

## Headline results, default rule (per micro, after costs)

| contract | period | trades | net $ | win | avg trade | PF | Sharpe | maxDD intra | pos days | pos months |
|---|---|---|---|---|---|---|---|---|---|---|
| MES | MAIN | 872 | -3,728 | 39.0% | -4.3 | 0.68 | -2.75 | -3,778 | 36% | 14% |
| MES | PRIOR | 887 | -4,081 | 36.4% | -4.6 | 0.50 | -4.75 | -4,361 | 29% | 8% |
| MNQ | MAIN | 805 | -1,710 | 47.3% | -2.1 | 0.91 | -0.66 | -2,398 | 46% | 33% |
| MNQ | PRIOR | 826 | -3,637 | 41.8% | -4.4 | 0.72 | -2.15 | -4,010 | 41% | 29% |
| MGC | MAIN | 725 | -3,367 | 44.8% | -4.6 | 0.76 | -1.91 | -3,668 | 48% | 38% |
| MGC | PRIOR | 747 | -2,443 | 41.6% | -3.3 | 0.60 | -3.33 | -2,497 | 39% | 8% |

Every instrument loses in both periods. MNQ MAIN is the "best" cell (PF 0.91) and is the contract used for the walk-forward.

Control cell (rsi_len 14, MES MAIN; independent 1-/5-min RSI(14) tests report 20-23% win): 289 trades, net -1,058, 41% win,
PF 0.75. The engine reproduces the known-bad result (fewer, still losing trades), so the losses above are not an artefact.

## Grid (MNQ, `results/bot_rsi_dip_MNQ.csv`)
0 of 16 combos profitable on MAIN and 0 of 16 on PRIOR. MAIN range: net -1,370 (rsi 5, ce 2.0, long, stop 1.5) to -4,156; PRIOR
range -3,331 to -5,453. Rank correlation of the combos between the two periods: -0.59 (the ordering flips: ce_mult 2.0 is the
least bad on MAIN and the worst on PRIOR). rsi_len 2 is worse than 5 everywhere on MAIN; adding shorts (`both`) costs
$900-1,100 on MAIN and $300-700 on PRIOR. Lucid scan on every cell: pass rate <= 0.3%, exp. net per eval = the fee (-$146).

## Diagnostics (MNQ, defaults, MAIN; `backtest.report`)
- **Exit mix is the whole story**: 766 of 805 trades (95%) leave on the chandelier signal, and the duration quartiles are 5 / 5 / 5
  minutes: the trade is closed on the very next 5-min bar. Reason: after an RSI(5) dip the deciding close is below
  `highest(22) - 1 ATR` in 97% of entries (measured), so with `min_hold = 1` the "close below ls" test is true immediately. The
  system degenerates into a 5-minute scalp that pays $2.30 of costs per round trip: signal exits net +$957 (avg +$1.25, 49% win),
  the 32 hard stops net -$3,784 (avg -$118), 7 forced-flat trades +$1,117. Median MAE/MFE +-15 pts; winners' MAE -7, losers' MFE +7.
- Hour: 09:45-10:00 entries +$705 (51% win), 10:xx -$538, 11:xx -$2,337 (40% win), 12:xx -$1,090, 13:xx-15:xx positive (+$1,550).
  Midday dips in an uptrend do not bounce within one bar. Weekday: Wed -$2,004, the others within +-$600.
- VIX (lag 1): all buckets negative except 20-25 (+$288, n=103) and >35 (n=6); 25-35 -$853 on 43 trades (the trend-day short-circuit
  the research warned about, despite the SMA50>SMA200 gate).
- Months: 7 of 21 positive; worst -$802 (2026-06, one -$300 day and a +$764 day in the same week), best +$873. Days: 165 up / 198
  down / 85 flat (the regime gate was off for ~4 months of 2025 after the April drawdown). Max 7 consecutive losing days and trades.
- The regime filter is nearly inert on MNQ MAIN: `regime none` gives 898 trades, net -1,539, PF 0.93 (vs -1,710 / 0.91 gated).
  Variant A + no regime on MES MAIN: 982 trades, net -4,080, PF 0.65 (the falling-knife variant is worse, as in the original).

## What was tried outside the grid (all in-sample, none adopted; `PARAMS` stay at the published rule)
| cell | MNQ MAIN | MNQ PRIOR | MES MAIN | MES PRIOR | MGC MAIN |
|---|---|---|---|---|---|
| min_hold 2 | 727 tr, -822, PF 0.96 | | | | |
| min_hold 3 | 686 tr, +4,269, PF 1.19, Sharpe 1.15 | 719 tr, -773, PF 0.95 | 792 tr, -2,539, PF 0.83 | 840 tr, -2,586, PF 0.76 | 640 tr, -4,264, PF 0.79 |
| min_hold 4 | 657 tr, +1,808, PF 1.07 | | | | |
| min_hold 6 | 629 tr, +1,870, PF 1.07 | | | | |
| exit_arm (exit only after a close above ls) | 540 tr, -478, PF 0.99 | 577 tr, +277, PF 1.01 | 634 tr, -3,430, PF 0.82 | | |
| exit_arm + ce_mult 2 | 575 tr, +183, PF 1.01 | | | | |

`min_hold = 3` on MNQ MAIN is the only profitable cell found, and it is a spike, not a plateau: min_hold 2 loses, 4 and 6 are
weaker, and the same setting loses on MNQ PRIOR, MES (both periods) and MGC. Arming the chandelier exit (so the exit is a cross of
the line rather than a level test) removes the one-bar scalp but turns the trades into long holds with a 1.5-ATR stop: ~PF 1.0 on
MNQ, worse on MES, with max intraday drawdown growing to -$4,200. Neither is a credible edge; they are reported only to document
that the literal spec's exit is the mechanism that fails, not the RSI entry alone (which is also negative: the entry hour and
regime splits show no bucket with an average trade above costs except the first 15 minutes).

## Walk-forward (honest yardstick; `backtest.final_select`, IS 12 months / OOS 3 months from 2022-01, 16-combo grid, selection by IS daily Sharpe, MNQ)

| span | trades | net $ | win | PF | Sharpe | maxDD intra | pos days | pos months |
|---|---|---|---|---|---|---|---|---|
| OOS 2022-01..2026-09 | 1768 | -8,667 | 40.7% | 0.78 | -1.68 | -8,693 | 39% | 27% |
| OOS 2025-01..2026-09 | 776 | -4,062 | 42.9% | 0.81 | -1.47 | -4,076 | 41% | 29% |

Parameters chosen per OOS window (IS metric = daily Sharpe):

| OOS window | params | IS Sharpe | IS net |
|---|---|---|---|
| 2023-01-01..2023-03-31 | `{"rsi_len": 5, "ce_mult": 2.0, "direction": "long_only", "stop_atr": 1.5}` | 0.95 | 1,210 |
| 2023-04-01..2023-06-30 | `{"rsi_len": 2, "ce_mult": 2.0, "direction": "both", "stop_atr": 1.5}` | -1.20 | -2,197 |
| 2023-07-01..2023-09-30 | `{"rsi_len": 2, "ce_mult": 1.0, "direction": "both", "stop_atr": 1.5}` | -0.97 | -733 |
| 2023-10-01..2023-12-31 | `{"rsi_len": 5, "ce_mult": 1.0, "direction": "long_only", "stop_atr": 2.5}` | -0.02 | -13 |
| 2024-01-01..2024-03-31 | `{"rsi_len": 2, "ce_mult": 1.0, "direction": "long_only", "stop_atr": 1.5}` | -0.43 | -337 |
| 2024-04-01..2024-06-30 | `{"rsi_len": 2, "ce_mult": 1.0, "direction": "long_only", "stop_atr": 1.5}` | -0.94 | -868 |
| 2024-07-01..2024-09-30 | `{"rsi_len": 2, "ce_mult": 2.0, "direction": "both", "stop_atr": 1.5}` | -0.44 | -663 |
| 2024-10-01..2024-12-31 | `{"rsi_len": 2, "ce_mult": 2.0, "direction": "both", "stop_atr": 1.5}` | -1.20 | -1,932 |
| 2025-01-01..2025-03-31 | `{"rsi_len": 2, "ce_mult": 2.0, "direction": "both", "stop_atr": 1.5}` | -1.55 | -2,606 |
| 2025-04-01..2025-06-30 | `{"rsi_len": 5, "ce_mult": 2.0, "direction": "long_only", "stop_atr": 1.5}` | -2.71 | -3,898 |
| 2025-07-01..2025-09-30 | `{"rsi_len": 5, "ce_mult": 1.0, "direction": "long_only", "stop_atr": 1.5}` | -2.48 | -2,800 |
| 2025-10-01..2025-12-31 | `{"rsi_len": 5, "ce_mult": 1.0, "direction": "long_only", "stop_atr": 1.5}` | -1.43 | -1,535 |
| 2026-01-01..2026-03-31 | `{"rsi_len": 5, "ce_mult": 1.0, "direction": "long_only", "stop_atr": 1.5}` | 0.08 | 103 |
| 2026-04-01..2026-06-30 | `{"rsi_len": 5, "ce_mult": 1.0, "direction": "long_only", "stop_atr": 1.5}` | 0.38 | 478 |
| 2026-07-01..2026-09-30 | `{"rsi_len": 5, "ce_mult": 2.0, "direction": "long_only", "stop_atr": 1.5}` | 0.93 | 2,389 |

Lucid scan on the OOS 2025-26 daily P&L: best size 5.0 micros, pass rate 0.32, pass within 21 sessions 0.05, expected net per evaluation 109 (bootstrap lower bound -146, zero-edge control 1,123), recommended = 0.0.

## Verdict

**dead**. Rule: `marginal` needs walk-forward OOS 2025 PF >= 1.03 with >= 40 trades; this has 776 trades at PF 0.81. The intraday translation of the SystemTrader RSI(5)/Chandelier system has no edge on MES, MNQ or MGC after costs: the published exit degenerates into a one-bar scalp on 5-minute bars, the regime gate barely changes anything, and no cell of the grid is profitable in either period. The only positive in-sample cell (min_hold 3 on MNQ MAIN) is not a plateau and fails everywhere else. Not a portfolio candidate; the reusable parts are the Chandelier ratchet helper and the regime/position-state scaffolding.
