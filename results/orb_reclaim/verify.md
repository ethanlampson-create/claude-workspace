# orb_reclaim - adversarial verification (2026-10-04)

Fixed params (`final.json`): `{"windows":"am_only","use_pd_levels":false,"max_stop_pts":60,"rr":3.5,"valid_minutes":60,"max_trades":4,"flat":"15:55","use_london":true}`,
contract MNQ. All numbers per ONE micro contract after costs ($1.30 RT + 1 tick slippage per side on stop fills), engine state of 2026-10-03.
Runs: `python3 -m backtest.run --strategy orb_reclaim --contract MNQ --start <s> --end <e> --params '<fixed>'` (driven through `backtest.run.run_strategy`,
same code path; raw outputs in the session scratchpad `v_reclaim/`). Walk-forward numbers are taken from `walkforward.json` (not re-run).

## 1. Look-ahead audit of `strategies/orb_reclaim.py` - none found

- Levels. London high/low (l.98-101) = high/low of bars with `tod` in [02:00, min(08:30, first window start)) of the same `day_id`; the session starts
  18:00 the evening before, so these bars are strictly before the 09:30 window. PDH/PDL (l.102-106, not used by the fixed params) come from
  `prior_day_stats`, i.e. `daily_bars(rth).shift(1)`: day d uses day d-1 only; `pd_mode='session'` also shifts by one day. No ATR, SMA or VIX is used.
- Sweep / extreme / swing (l.166-198). At bar i (closed) the level state is updated with `h[i]`/`l[i]`; the swing test at j = i uses
  `l[j-2], l[j-1], l[j], c[j]` and X (running extreme including bar j) - all closed bars. The result is stored in `arm` and the order is placed in
  step A of the NEXT iteration at index i+1 (l.139-147), i.e. live from the open of the bar after the confirming close. This is the correct
  `i_next` placement; the sweep bar cannot be the swing bar (`j-1 > sweep_i`), and `j-2 >= d0` guards the session start.
- Fill / exit mirror (l.149-164, `_simulate_exit` l.52-73). The module replays the engine's fills to know when a level is consumed and when the
  strategy is flat. `pos_exit` is derived from future bars, but it is only used in comparisons `i > pos_exit` ("flat at the open of bar i"), which
  is information available at bar i; it never feeds a price or a direction. Verified against the engine on MAIN: 340 engine trades, 340 mirror
  fills on allowed bars, 0 unmatched, 0 side mismatches, 0 exit-timestamp mismatches; every long fill >= the stop level, every short fill <= it.
- Order mechanics. Buy stop at X + 1 tick, protective stop at S - 1 tick, target = fill + rr x (order - stop) via `tgt_pts` (resolved by the engine
  at the fill). `valid_bars` = 60, pending orders die at the window end (engine cancels pending when `allow_entry` is false), `set_session`
  masks entries to the windows and forces flat at 15:55. No same-bar information in the entry decision; no session high/low/close used.
- Minor, not look-ahead: the mirror uses `contract.slip_ticks` (1 tick) for its own fill price (l.88), so under `--slip 2` the mirror's predicted
  target price differs from the engine's by 1 tick; this can shift when the mirror believes it is flat, but it does not use future information.
- Parameters. Nothing encodes dates or regime switches. `max_stop_pts=60` is outside the module GRID (30/45) and was chosen on MAIN (README attempt 6:
  MAIN PF 1.24 at 45 vs 1.33 at 60, PRIOR 1.17 vs 1.18) - selection on the test window, not look-ahead; the walk-forward used the grid (cap 45) and
  is the honest yardstick. `use_pd_levels=False` and `windows='am_only'` were also chosen because they hurt MAIN (same caveat).

`lookahead_found = false`.

## 2. Fixed-parameter re-runs

| run | trades | net $ | PF | Sharpe | maxDD intra | pos months | largest day share |
|---|---|---|---|---|---|---|---|
| MAIN 2025-01-01..2026-09-30 | 340 | +6,433 | 1.327 | 1.59 | -1,949 | 14/21 | 0.066 |
| PRIOR 2023-01-01..2024-12-31 | 324 | +2,814 | 1.182 | 0.84 | -1,268 | 12/24 | 0.146 |

Both reproduce `final.json` exactly (MAIN PF 1.3272, PRIOR 1.1818). Walk-forward OOS 2025-01..2026-09 (`walkforward.json`, grid-selected params,
cap 45 from Q2-2025): 309 trades, +2,669, PF 1.170, Sharpe 0.84, largest day 20% of net -> criterion PF >= 1.1 met, but it is the PRIOR-like half
of the MAIN story (avg trade $8.6 vs $18.9 in-sample), and the last fold (Jul-Sep 2026) is PF 0.51.

## 3. Plateau (MAIN, fixed params otherwise; numeric GRID keys are `rr` [2.0, 2.5, 3.5] and `max_stop_pts` [30, 45])

| neighbour | trades | net $ | PF | Sharpe | maxDD | >= 1.05 |
|---|---|---|---|---|---|---|
| rr 2.5 (one grid step down) | 340 | +4,902 | 1.264 | 1.41 | -2,189 | yes |
| rr 4.5 (one step up, extrapolated: 3.5 is the grid top) | 340 | +7,127 | 1.351 | 1.57 | -1,857 | yes |
| max_stop_pts 45 (one grid step down) | 297 | +3,485 | 1.237 | 1.13 | -1,948 | yes |
| max_stop_pts 75 (one step up, extrapolated: 60 is above the grid) | 352 | +6,688 | 1.297 | 1.47 | -2,035 | yes |

`plateau_frac = 4/4 = 1.00` (in-grid-only neighbours: 2/2). Context: two steps down is where it breaks - rr 2.0 PF 1.198, cap 30 PF 1.02 (213 trades,
largest-day share 1.24 of a +167 net). Non-numeric / non-grid variants for information: windows am_pm PF 1.314 (393 trades), use_pd_levels True
PF 1.142 (450 trades, DD -2,969), valid_minutes 30 / 90 PF 1.308 / 1.293, max_trades 3 / 5 identical to 4 (never binding). The cell is a plateau
on MAIN; the PRIOR grid in the README shows the same cap-45 / rr-3.5 block as the only one positive on both periods.

## 4. History (fixed params)

| period | trades | net $ | PF | Sharpe | maxDD intra | pos months |
|---|---|---|---|---|---|---|
| 2015-01-01..2022-12-31 | 1,579 | -2,255 | 0.951 | -0.25 | -4,911 | 42/96 |
| 2020-01-01..2020-12-31 | 183 | -772 | 0.901 | -0.55 | -1,693 | 5/12 |
| 2015-2022 ex-2020 | 1,396 | -1,482 | 0.961 | | | |

By year (PF): 2015 0.84, 2016 0.79, 2017 1.00, 2018 0.75, 2019 1.20, 2020 0.90, 2021 0.92, 2022 1.07. Sub-periods: 2015-2018 PF 0.82 (-2,231 on 771
trades); 2019-2022 PF 0.999 (-24 on 808 trades); 2021-2022 PF 1.001. The published study starts 2019-05 (MNQ launch); on 2015-2018 NQ traded at
4,000-7,500, so the fixed 60-pt cap and 1-tick-beyond-swing stops are 2-3x larger in relative terms than today and the rule is effectively a
different one there. Even so, the criterion is PF >= 1.0 on 2015-2022 ex-2020 and the result is 0.961: MISSED, by 4%. The 2019-2022 window, where
the rule is comparable, is exactly break-even (0.999), not positive.

## 5. Slippage

MAIN with `--slip 2` (2 ticks per side on stop fills): 340 trades, +6,170, PF 1.310, Sharpe 1.52, maxDD -1,973, top-10-day share 0.645. Criterion met
with room (each extra tick costs ~$1 per side on MNQ, $263 over 340 trades). Average trade $18.9 is ~5x the $3.30 round-trip cost at 1-tick slippage.

## 6. Thin-session dependence (MAIN trades / daily table)

- 323 trading days; the 10 best days contribute +3,983 = 61.9% of the +6,433 net (5 best: 31.8%). Without the 10 best days the remaining 313 days
  still net +2,450 at PF 1.13, so the edge is not a handful of days, but the P&L is lumpy (31% win, 3.5R).
- Months: no month > 40% of net; best Feb-26 26.4%, then Jan-26 19.1%, Feb-25 18.8%, May-26 18.0%, Nov-25 17.6%. The 5 best months (+6,390) are
  99% of the net, the other 16 sum to +43. Last two months (Aug-Sep 2026) both negative.
- Largest single day 6.6% of net (MAIN), 14.6% (PRIOR), 20.0% (WF OOS 2025).
- Slip-2 top-10 share 0.645. PRIOR: the 10 best days (+3,551) exceed the whole PRIOR net (+2,814), share 1.26.

## Verdict: marginal

| criterion | value | threshold | met |
|---|---|---|---|
| look-ahead | none (mirror = engine 340/340) | none | yes |
| walk-forward OOS 2025 PF | 1.170 | >= 1.1 | yes |
| plateau_frac | 1.00 (4/4; in-grid 2/2) | >= 0.5 | yes |
| history 2015-2022 PF ex-2020 | 0.961 (full 0.951; 2019-2022 0.999) | >= 1.0 | no |
| slippage-2 MAIN PF | 1.310 | >= 1.0 | yes |

One criterion missed, by 4% (0.96 vs 1.0), with the comparable 2019-2022 sub-period at break-even and the failure concentrated in 2015-2018 where
the fixed point cap makes the rule a different one: `marginal`, not `dead`. Not `survivor`: the strategy has no history before 2019, the
in-sample cap-60 choice adds ~0.1 PF over the walk-forward-validated cap 45, 62% of MAIN net sits in 10 days and the walk-forward stream is
PRIOR-like (PF 1.17, Sharpe 0.84) with a 3-month losing tail. Consistent with the module README and the walk-forward assessment: a
diversifying portfolio leg at small size, not a stand-alone Lucid candidate.
