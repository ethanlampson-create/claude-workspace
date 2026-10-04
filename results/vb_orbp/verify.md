# vb_orbp — adversarial verification (MNQ, fixed params from final.json)

Verifier run 2026-10-04. All numbers per ONE micro contract (MNQ, $2/pt), after the engine's costs (1 tick slippage per
side on stop/market fills, $1.30 round trip). Fixed parameters = the `PARAMS` defaults recorded in `final.json`
(published two-sided rule: k = 0.25 x yesterday's RTH range, bias none, stop 0.5 x range capped at 0.6 ATR, target
0.5 x range uncapped, entries until 15:55, flat 15:55, 1 trade/day). Nothing under `backtest/`, `tests/` or
`strategies/` was modified. `final_select` was not re-run; the walk-forward numbers are taken from `walkforward.json`.

## 1. Look-ahead review of `strategies/vb_orbp.py` — none found

| Item | Finding |
|---|---|
| Daily features (`rng`, `mid`, `C1`, `C2`, `swing`) | Built from `daily_bars(rth_only=True)` then `.shift(1)`, `.shift(2)`, `.shift(3)` on the day_id-indexed table: session d only sees sessions < d. |
| ATR | `strategies.common.daily_atr` = Wilder ATR with `min_periods = n` then `.shift(1)`; the first 14 sessions are NaN and the `ok` mask (`atr.notna() & atr > 0`) excludes them. `run.prepare` loads 45 calendar days of warm-up before `--start`. |
| VIX / SMA | Not used. |
| Open `O` | `D['open']` of the first RTH bar `i0` (09:30 print). The resting stop orders are placed at `i1 = i0 + 1`, i.e. live from the open of the 09:31 bar; the level is `O +/- k*B + 1 tick`, so the 09:30 print itself can never be the fill. |
| Session's own high/low/close | Never used in the entry decision. The `kb` scan over bars >= i1 only resolves which stop level is touched first (the OCO resolution that the guide explicitly allows and that `orb.py` uses); the engine then re-finds the same bar with its own stop-fill rule `max(open, level) + slip`. Stop and target are fixed distances from the fill, computed from prior-day quantities. |
| Same-bar double touch | Side = the level nearer the bar's open. A heuristic (symmetric, applied to 1-minute bars), not an information leak. |
| `_early_close` | Uses the session's OWN RTH bar count/last bar. In the MAIN window it flags 18 of 448 sessions: 16 CME 13:00/13:15 ET holiday early closes (MLK, Presidents, Memorial, Juneteenth, Jul 3/4, Labor, Thanksgiving + day after, Dec 24) plus 2025-01-09 (Carter day of mourning, no RTH) and the truncated last session 2026-09-25. All are exchange-calendar facts known in advance. `run.prepare` applies the same thin-session filter harness-wide, so this is not strategy-specific. Not a look-ahead in practice. |
| `i_next` | Not applicable (no resampling); orders placed at `i1`, `valid_bars` counted from `i1` to the cutoff. |
| 2025-2026 knowledge in parameters | None: no dates, regime switches or calendar filters. Defaults are the published rule; the GRID conditioning (ws_skip 1.5, 11:30 cutoff, 0.6-ATR cap) is NOT used by the fixed params. |

Modelling caveat (not a leak): because the order goes live only at 09:31, a touch of a level inside the 09:30 bar
itself is ignored (30 of 426 tradeable MAIN sessions: 16 up, 14 down). A live trader entering orders ~09:30:30 could
be filled in that minute. The direction of this bias is unknown; it is conservative on fill timing, not information.

## 2. Fixed-parameter re-runs (reproduce final.json exactly)

| Period | Trades | Net $ | PF | Win | Avg trade $ | Max DD intraday $ | Sharpe (daily, ann.) | Largest-day share |
|---|---|---|---|---|---|---|---|---|
| MAIN 2025-01-01..2026-09-30 | 419 | 7,629 | **1.148** | 0.542 | 18.2 | -8,113 | 0.91 | **0.181** |
| PRIOR 2023-01-01..2024-12-31 | 374 | 4,715 | **1.169** | 0.559 | 12.6 | -3,725 | 0.93 | 0.109 |

Exit mix MAIN: 148 target / 147 stop / 124 flat. Side split MAIN: shorts 196 trades +$8,791, longs 223 trades
-$1,162 — the whole net is on the short side.

## 3. Plateau (MAIN, one parameter moved, others fixed)

The fixed params are the defaults, not a GRID cell, so "one grid step" is defined as: the GRID spacing where the GRID
has two values (k: 0.2 -> tested 0.45 up; 0.05 down is below `min_unit_atr`, so the fine step +/-0.05 is reported
too), +/-0.1 for the fractions/ATR caps, and for the two filters that are OFF (0) in the fixed params the GRID's own
value (ws_skip 1.5, tgt_cap_atr 0.6) as the only neighbour.

| Neighbour | Trades | Net $ | PF | >= 1.05 |
|---|---|---|---|---|
| k 0.20 | 419 | 7,456 | 1.138 | yes |
| k 0.30 | 412 | 5,620 | 1.114 | yes |
| k 0.45 (grid step) | 350 | 15,143 | 1.521 | yes |
| stop_frac 0.4 | 419 | 6,676 | 1.136 | yes |
| stop_frac 0.6 | 419 | 10,604 | 1.209 | yes |
| tgt_frac 0.4 | 419 | 5,466 | 1.111 | yes |
| tgt_frac 0.6 | 419 | 9,356 | 1.178 | yes |
| max_stop_atr 0.5 | 419 | 7,547 | 1.148 | yes |
| max_stop_atr 0.7 | 419 | 8,117 | 1.157 | yes |
| tgt_cap_atr 0.6 (on) | 419 | 6,651 | 1.129 | yes |
| ws_skip 1.5 (on) | 397 | 8,323 | 1.180 | yes |

**plateau_frac = 11/11 = 1.00.** It is a genuine plateau, but a low one: every neighbour sits in 1.11-1.21 (the k 0.45
outlier aside), i.e. the parameters are not spiked, the edge is simply thin everywhere.

## 4. History

| Period | Trades | Net $ | PF |
|---|---|---|---|
| 2015-01-01..2022-12-31 (one run) | 1,924 | 4,853 | **1.053** |
| 2020-01-01..2020-12-31 | 245 | -2,510 | **0.876** |
| 2015-2022 ex-2020 (2015-19 + 2021-22 trade tables) | 1,679 | 7,383 | **1.102** |
| 2015-01-01..2019-12-31 | 1,195 | 990 | 1.034 |
| 2021-01-01..2022-12-31 | 484 | 6,394 | 1.148 |

Per year: 2015 -169, 2016 +117, 2017 -328, 2018 +644, 2019 +726, 2021 +1,007, 2022 +5,387. The ex-2020 criterion
(pf >= 1.0) passes, but 2015-2019 is flat (avg trade $0.83) and the historical pass is carried by 2022.

## 5. Slippage

MAIN with `--slip 2` (2 ticks per side on stop/market fills): 419 trades, net $7,354, **PF 1.143** (vs 1.148). The
entry level sits one tick beyond the breakout and most exits are target/flat, so slippage sensitivity is low.

## 6. Thin-session dependence (MAIN trades table)

- Top 10 days (of 419 trading days) sum to $7,653 = **100.3% of net**; net excluding them is -$24. Top 5 days = 59.8%.
- Largest day 2025-04-09 (+$1,378, 18.1%); 2025-04-08 (+$1,138). The two tariff-pause days alone are 33% of net.
- Largest month 2025-04 = $3,379 = **44.3% of net (> 40%)**. 12 of 21 months positive; 2026-03..2026-07 all negative
  (-$6,820 over five months), worst month 2026-06 -$2,850.
- All net from shorts (+$8,791); longs -$1,162.

## 7. Walk-forward (from walkforward.json, not re-run)

WF OOS 2025-01..2026-09: 270 trades, net $4,100, **PF 1.162**, Sharpe 0.81, largest-day share 0.158, worst month
-$2,472. Full concatenated OOS 2023-2026: 518 trades, PF 1.268, Sharpe 1.20. Lucid MC on the WF 2025 stream: best
size 5 micros, pass rate 0.33, expected net per eval +$193 but `exp_net_lb` = -$81 and `recommended` = 0.

## Verdict

| Criterion | Value | Threshold | Pass |
|---|---|---|---|
| No look-ahead | none found | — | yes |
| WF OOS 2025 PF | 1.162 | >= 1.1 | yes (narrow) |
| plateau_frac | 1.00 | >= 0.5 | yes |
| History 2015-2022 ex-2020 PF | 1.102 | >= 1.0 | yes |
| Slip-2 MAIN PF | 1.143 | >= 1.0 | yes |

**survivor** by the stated criteria — but a weak one. It fails the guide's quality bar on every count (MAIN PF 1.15
< 1.3, Sharpe 0.91 < 1.5, single month 44% > 40%, max intraday DD $8.1k per micro), the entire net sits in 10 of 419
days and on the short side only, 2015-2019 is flat, and the Lucid simulator does not recommend any size on the
walk-forward stream. It should not be sized as a stand-alone leg; at most a small diversifying component.

Files: this verification used `results/vb_orbp/final.json`, `walkforward.json`; run outputs are in the session
scratchpad (`runs.json`, `main_trades.csv`).
