# orb_sma_rr — ORB with daily SMA(200) trend filter, R-multiple exit, one loss per session

Family: `orb_session` (research: `research/families/orb_session.md`, section 3.1, "Backtests, Not Signals" MNQ walk-forward).
Module: `strategies/orb_sma_rr.py`. Instruments tested: MNQ (published), MES. Periods: MAIN 2025-01-01..2026-09-30,
PRIOR 2023-01-01..2024-12-31. All numbers per ONE micro contract, after engine costs ($1.30 RT + 1 tick slip per side).

## Rules as implemented
- Trend filter: daily closes from `data/parquet/NDX_1d.parquet` (MNQ) / `SPX_1d.parquet` (MES). For session d the close of
  the last daily row strictly before d is compared with the SMA(sma_len) of those lagged closes: above -> long bias only,
  below -> short bias only, SMA undefined -> no trade. The SMA is never built from the 1-minute feed.
- Opening range over [09:30, 09:30 + or_minutes). Day skipped if range < min_range_atr x ATR14 (daily RTH ATR, shifted).
- Entry: one stop order (bias side only) at or_high + 1 tick / or_low - 1 tick, placed on the first 1-min bar after the
  range, live until last_entry (12:00). Wick fill = max(open, level) + 1 tick slippage.
- Stop: opposite side of the range, distance = min(range, stop_cap_pts[contract], max_stop_atr x ATR14).
- Target: rr x stop distance. No trailing. Forced flat 15:55 ET. Early-close sessions exit at the last bar.
- One-loss rule: max_trades = 1 (published runs are effectively one trade per day). `reentry=True` re-places the same
  order after an exit while tod < last_entry (max 2 trades/day) with daily_loss_stop = cap $ per contract.
- Look-ahead: verified by hand on sampled trades (lagged close vs SMA, range, ATR, stop/target levels, fills).

Defaults (`PARAMS`, kept equal to the published rule): or_minutes 30, sma_len 200, rr 2.0, stop_cap_pts MNQ 37.5 / MES 10.0,
max_stop_atr 0.5, buffer 1 tick, last_entry 12:00, min_range_atr 0.1, max_trades 1, flat 15:55.

## Metrics per period and contract

### Published spec (defaults), MNQ
| period | trades | net | win | PF | Sharpe | max DD intraday | pos days | pos months |
|---|---|---|---|---|---|---|---|---|
| MAIN 2025-01..2026-09 | 273 | -960 | 34.4% | 0.93 | -0.42 | -1,781 | 34% | 43% |
| PRIOR 2023-01..2024-12 | 265 | -330 | 36.2% | 0.98 | -0.14 | -1,718 | 36% | 38% |

### Published spec (defaults), MES
| period | trades | net | win | PF | Sharpe | max DD intraday |
|---|---|---|---|---|---|---|
| MAIN | 284 | -1,584 | 34.5% | 0.84 | -1.04 | -2,004 |
| PRIOR | 271 | +661 | 40.2% | 1.08 | 0.41 | -795 |

### Best configuration found (MNQ): OR 15 min, SMA 200, rr 2.0, stop = min(range, 0.15 x ATR14), no point cap
`{"or_minutes": 15, "sma_len": 200, "rr": 2.0, "stop_cap_pts": 1e9, "max_stop_atr": 0.15, "last_entry": "12:00"}`

| period | trades | net | win | avg trade | PF | Sharpe | max DD intraday | pos days | pos months | worst day | largest day share |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MAIN | 312 | +3,750 | 40.4% | +12.0 | 1.16 | 0.90 | -2,135 | 40% | 62% | -246 | 11% |
| PRIOR | 315 | +1,249 | 37.1% | +4.0 | 1.08 | 0.45 | -2,875 | 37% | 50% | -288 | 22% |

Lucid 50K Flex (`lucid_scan`, MAIN): best 5 micros -> pass rate 0.49, P(first payout, unconditional) 0.20, expected net
per evaluation +$858, median 14 days to pass. 10 micros: pass 0.27, expected net -$41. PRIOR at 5 micros: pass 0.28,
expected net +$76. Monthly pass rate (5 micros, MAIN) ranges from 0.0 (2025-04) and 0.05 (2026-08) to 1.0
(2025-08..10): NOT monthly consistent.

Same configuration on MES: MAIN PF 0.905 (325 trades, net -1,236), PRIOR PF 0.95 -> MES is dead for this family.

## Diagnostics (MNQ)
Published spec, MAIN (report): the 37.5-pt stop cap binds on 100% of orders (NQ 30-min range is 50-270 pts at 2025-26
price levels), so every trade is a fixed 37.5-pt stop / 75-pt target. 34% win at 2R = breakeven before costs. Losses
concentrate in the 10:00 hour (-1,839 on 237 trades) while 11:00-12:00 entries are positive (+879 on 36); shorts lose
(-763 on 39 trades, 26% win) vs longs -197 on 234; Wed/Thu lose (-786 / -462); VIX 20-35 loses (-1,420 on 65 trades).
Exit mix: 176 stops (-13,684), 84 targets (+12,381), 9 flat (+334). Worst month 2026-03 (-786, 12% win).

Why the cap fails now: 37.5 pts was 0.157 x NDX ATR14 during the published in-sample (2020-02..2022-12) and 0.142 in
the published OOS (2023-01..2026-02), but 0.111 in 2025 and 0.086 in 2026 (NDX ATR14 ~408 in MAIN). The same 150 ticks
are now a noise-level stop. Expressing the cap as 0.15 x ATR14 restores the published risk geometry.

ATR-stop variant, MAIN (report run on OR15 / 0.25 ATR / rr 2.0, the neighbouring grid row; shape is the same at 0.15):
by entry hour 09:45-09:59 +3,705 (223 trades) / 10:00 +1,742 (70) / 11:00 +1,225 (19); both sides positive; Friday the
only losing weekday (-776); VIX 20-25 still negative (-1,329 on 50). Exit mix: 155 stops (-28,720), 70 targets (+26,029), 82 flat-at-close (+9,216,
84% winners) -> a large part of the edge is trend-day carry to the close rather than the 2R target, consistent with the
family note that MNQ ORB longs with long holds were positive in 2025. Max consecutive losing trades 8, losing days 5.
Months: 13/21 positive; losing stretch 2026-07..09 (-1,706 over three months).

## Grids
1. Module GRID (published spec), MNQ, MAIN: `grid_main.csv` (48 combos, 24 s). 8/48 profitable, best PF 1.04
   (sma150 / rr2.0 / OR15 / 11:00, 291 trades, net +543). Surface is a monotone slope, not a plateau: sma 150 > 200 > 250,
   rr 1.4-2.0 > 2.4-3.0, OR15 > OR30 everywhere. PRIOR (`grid_prior.csv`): 40/48 profitable, best PF 1.22
   (sma150 / rr3.0 / OR15), OR30+rr2 (the published default) ~1.0. The published OOS (PF 1.32) is only approximately
   reproduced on 2023-24 and not at all on 2025-26 -> rejected under the plateau criterion.
2. Second pass (reasoned, not tuned): single-run variants on MNQ, both periods (`pass2.py`):
   - rr 4.0 (implied by published OOS win rate 24.9% / PF 1.32): MAIN PF 0.87, PRIOR 1.10 -> worse.
   - reentry=True (second attempt after a stop-out, daily loss stop at cap $): MAIN 0.91, PRIOR 0.96 -> worse.
   - cap 75 pts: MAIN 0.99 / PRIOR 1.21; cap 150: 1.08 / 1.21; no cap + 0.5 ATR: 1.06 / 1.16; no cap + 0.25 ATR: 1.08 / 1.27.
     Loosening the cap monotonically helps on both periods -> the cap is the identified flaw.
3. ATR-stop grid (`grid_atrstop.csv`, base stop_cap_pts=1e9, sma 200, 12:00; max_stop_atr [0.15, 0.25, 0.35] x rr
   [1.4, 2.0, 2.4, 3.0] x OR [15, 30], both periods, 52 s): MAIN 22/24 profitable (median PF 1.08, best 1.27 at
   OR15 / 0.25 / 1.4), PRIOR 23/24 profitable (median PF 1.09, best 1.30 at OR30 / 0.25 / 2.4). A broad, shallow plateau,
   but the rank correlation between periods is -0.33: OR15 wins on MAIN, OR30 on PRIOR. Lucid-optimal size is 5 micros
   for every row because worst days are $250-460 per micro and intraday DD $2.1-4.5k per micro; best MAIN expected net
   per eval +$858 (OR15 / 0.15 / 2.0) and +$686 (OR15 / 0.15 / 1.4).
   Chosen configuration: OR15, rr 2.0 (published default), max_stop_atr 0.15 (= the published cap's ATR fraction in its
   own in-sample), no point cap. It is not the best row on either period; it is the row whose every parameter has a
   stated reason.

## Attempts log
1. Faithful implementation, smoke tests MNQ/MES x MAIN/PRIOR: runs, ~155 trades/yr (published ~154/yr), MAIN PF 0.93 / 0.84.
2. Manual verification of bias, range, ATR, stop/target, fills on sampled trades: correct.
3. Report on MNQ MAIN: cap binds 100%, 2R target rarely reached, shorts and 10:00 hour lose.
4. Module grid MAIN + PRIOR: no plateau, published spec rejected.
5. Second-pass hypotheses: rr 4 (no), reentry (no), cap scaling (yes, both periods).
6. ATR-stop grid both periods: broad shallow plateau; Lucid at 5 micros only.
7. MES with the fix: dead on MAIN under all variants.

## Verdict: marginal
Published spec is dead on 2025-26 (and ~breakeven on 2023-24) because its fixed 150-tick stop no longer matches NQ
volatility. With the stop re-expressed as 0.15 x ATR14 the MNQ strategy is positive on both periods (PF 1.16 / 1.08) with
312 trades in MAIN, but the edge is thin (avg trade +$12 = ~5x costs, Sharpe 0.9, 40% positive days), the per-micro
drawdown ($2.1k) forces 5-micro sizing, the evaluation pass rate is 0.49 with a monthly pass rate between 0 and 1, and
P(first payout) is only 0.20. Not a standalone Lucid candidate; possibly a portfolio leg (trend-day carry is its
distinct feature) if a lower-correlation partner exists. No engine bugs found.

## Walk-forward out-of-sample (final_select, 2026-10-03)
`python3 -m backtest.final_select --ids orb_sma_rr --jobs 2 --wf_start 2022-01-01 --max_combos 16` -> `walkforward.json`,
`wf_oos_2025_daily.csv`. Base = final.json params (OR15, SMA200, stop = min(range, 0.15 x ATR14), rr 2, no point cap).
Module GRID replaced for this run (attempt 8): the old 48-combo grid coarsened to 16 dropped sma 200 and rr 2.0 (the
published values), so it is now `{'max_stop_atr': [0.15, 0.25], 'rr': [1.4, 2.0, 3.0], 'or_minutes': [15, 30]}` (12 combos,
the identified levers; sma_len stays 200 via the base). IS 12 months / OOS 3 months, selection by IS daily Sharpe, 15 windows
2023-01..2026-09.

| stream | trades | net | win | avg trade | PF | Sharpe | max DD intraday | pos days | pos months | worst day | worst month |
|---|---|---|---|---|---|---|---|---|---|---|---|
| WF OOS 2025-01..2026-09 | 304 | +4,684 | 47.0% | +15.4 | 1.17 | 0.96 | -2,422 | 47% | 71% (15/21) | -323 | -1,107 (2026-07) |
| WF OOS 2023-01..2026-09 | 578 | +5,472 | 43.3% | +9.5 | 1.13 | 0.65 | -2,422 | 43% | 56% | -323 | -1,107 |
| fixed params MAIN (current engine) | 304 | +3,377 | 39.8% | +11.1 | 1.15 | 0.81 | -2,135 | 40% | 57% | -246 | -849 |
| fixed params PRIOR (current engine) | 274 | +1,961 | 38.3% | +7.2 | 1.15 | 0.75 | -1,689 | 38% | 46% | -144 | -567 |

Parameter path: 2025-01..06 picked OR15 / 0.15 ATR / rr 2 (= the fixed config); from 2025-07 every window picked OR15 /
0.25 ATR / rr 1.4 (wider stop, nearer target). 2023-24 windows alternated OR30/OR15, rr 1.4..3.0. 7 of 15 OOS windows
are negative; window PF ranges 0.54 .. 3.17. OOS monthly: 2025 +1,245; 2026-01..06 +5,324 (113% of the 2025-26 net);
2026-07..09 -1,884 (two consecutive -800/-1,100 months).

Lucid on the 2025-26 OOS stream (`lucid_wf_2025`, bootstrap lower-bound sizing):

| micros | pass | pass<=21d | P(first payout) | exp net / eval | exp net LB | zero-edge control |
|---|---|---|---|---|---|---|
| 5 | 0.40 | 0.31 | 0.10 | +224 | -146 | -138 |
| 10 (selected by LB) | 0.22 | 0.22 | 0.01 | -89 | -135 | -134 |
| 15 | 0.15 | 0.15 | 0.01 | -121 | -146 | -146 |

`recommended = 0` at every size: the lower bound never clears zero and the strategy does not beat its demeaned control
by $100. Per-micro intraday DD of $2.1-2.4k and $300+ worst days against the $2,000 trailing MLL mean even 5 micros breach
before payout 94% of the time at 10 micros.

Verdict after walk-forward: still **marginal**. The OOS stream confirms the in-sample story (thin, real-looking PF 1.15-1.17
on both the fixed and the walk-forward params; no overfit signature) but the edge is too small and too drawdown-heavy for a
50K evaluation; the money is one bull-trend half-year (2026 H1), and the most recent quarter is the worst in the sample.
Attempt 8 (GRID narrowed to the identified levers for the walk-forward): kept — it is the search space, not a tuning.
