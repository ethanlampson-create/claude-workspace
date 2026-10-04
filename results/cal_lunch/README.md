# cal_lunch - Lunch effect: short 11:00-12:00 / long 12:00-14:00 (family calendar_seasonal_structural)

Module: `strategies/cal_lunch.py` (shared flags: `strategies/_cal_flags.py`). Research: `research/families/calendar_seasonal_structural.md`
section 9; spec `research/specs/calendar_seasonal_structural.md` section 8. Source: Quantpedia "Lunch Effect in the U.S. Stock Market
Indices" (SPY 2010-05..2024-05; long-only 12:00-14:00 leg ~5.2%/yr at 8% vol; evidence quality 2: one vendor backtest, no OOS, ~2 bp/day).
Instruments: MES (primary per the SPY evidence) and MNQ, 1-min bars, equities RTH, trade window 11:00-14:00 ET only, flat by 14:00.
Periods: MAIN = 2025-01-01..2026-09-30, PRIOR = 2023-01-01..2024-12-31, long history 2015-01-01..2024-12-31 (profile 2010-2026).
All numbers per ONE micro contract after costs ($1.30 RT commission + 1 tick slippage per side on market/stop fills: MES $3.80, MNQ $2.30 per RT).

**Verdict: marginal (by the mechanical rule only).** Walk-forward OOS 2025-01..2026-09 on MNQ: 401 trades, net +$4,379, PF 1.185,
Sharpe 0.76, 14/21 positive months, so it clears the 'marginal' bar (PF >= 1.03 on >= 40 trades). Everything else says no edge:
2025-04-09 alone is +$3,089 of the OOS net (ex that day PF 1.055), 2026 OOS is -$38 (PF 0.997), the 2023-24 OOS folds are 7/8
negative, 2015-2024 is PF 0.91 on MNQ and 0.83 on MES (the paper's instrument, negative in every period and every grid cell), the
raw 12:00-14:00 return is 0.0 bp/day over 2010-2024, and the Lucid lower bound is -$146 = the zero-edge control at every size.

## Rules as implemented (all ET; a 1-min bar with tod=T covers [T, T+1))
- `i(HH:MM)` = first bar with `HH:MM <= tod < HH:MM+5` (normally the HH:MM bar; the CFD feed omits tick-less minutes). A market order
  placed at `i(T)` fills at that bar's open + 1 tick, decided on bars up to T-1. `ref` = close of the bar before the entry bar.
- `ATR14d = daily_atr(df1, 14, rth_only=True)` (Wilder, shifted one day). Flags from `_cal_flags.flags(df1)`: `macro_day` (08:30 two-bar
  range >= 3x the trailing-60-session median, known 08:32, or FOMC statement day from the verified table), `fomc`, `opex`.
- Day filter: `day_ok = not (skip_macro and (macro_day or fomc)) and not (skip_opex and opex) and ATR non-NaN and all clock bars exist`.
- Entries per session with `day_ok`:
  - `short_only` / `short_then_long`: `place(i(short_start)=11:00, -1, stop_pts)`; `exit_at(i(reverse_time)=12:00)` = market exit at the
    12:00 open unless the protective stop fired first.
  - `long_only` / `short_then_long`: `place(i_l, +1, stop_pts)` with `i_l = i(12:00)` (long_only) or `i(12:00) + 1` = the 12:01 bar
    (short_then_long: one position at a time, the engine exits the short at the 12:00 open and takes no entry on an exit bar);
    `exit_at(i(long_exit)=14:00)` = market exit at the 14:00 open. No targets, no re-entry after a stop (one entry index per leg).
- Stop: `stop_pts = stop_pct/100 x ref` (`stop_mode='pct'`, default 0.4% ~ 24 ES pts = $120/MES, ~90 NQ pts = $180/MNQ) or
  `stop_atr x ATR14d` (`stop_mode='atr'`).
- Session: `set_session(11:00, 12:02, long_exit)` for the short variants, `set_session(12:00, 12:02, long_exit)` for long_only; `force_flat`
  from `long_exit` to session end so nothing can be open after 14:00. `max_trades_day = min(max_trades, legs)` (2 / 1).
  `daily_loss_stop = dls_mult x Lucid block` (MES $60, MNQ $80 per micro). NOTE: the block is smaller than one 0.4% stop, so in
  `short_then_long` a stopped 11:00 short halts the day and the 12:01 long does **not** enter (281 of 358 MAIN sessions on MES got
  both legs; the 77 single-leg days are the stopped shorts). `dls_mult=0` restores the spec's "the long still enters" clause; it does not
  change the conclusion (MES MAIN PF 0.893 either way).
- Defaults (`PARAMS` = the published long-only midday leg): `variant long_only, short_start 11:00, reverse_time 12:00, long_exit 14:00,
  stop_mode pct, stop_pct 0.4, stop_atr 0.4, skip_macro True, skip_opex False, max_trades 2, dls_mult 1.0`.
- GRID (16): `variant {long_only, short_then_long} x stop_pct {0.3, 0.5} x long_exit {13:30, 14:00} x skip_macro {True, False}`; one extra
  single run `stop_mode='atr', stop_atr=0.4` for stop-definition sensitivity.

Look-ahead / mechanics audit (scratch script over every MAIN trade, both contracts): every long_only entry has tod 12:00, every reversal
short tod 11:00 and long tod 12:01; fill == bar open + side x tick on all 364 / 639 trades; stop exits at exactly entry -/+ 0.4% x ref - slip
(one MNQ exception is a gap-through fill at the bar's open, the engine's worst-case rule); latest exit tod 14:00; 0 of 64-72 macro days
traded; the 11:00 short's exit is the 12:00 bar and the long's entry the 12:01 bar on 100% of two-leg days.

## Headline results, default rule (long_only 12:00-14:00, skip_macro)

| contract | period | trades | net $ | win | avg net / gross per trade | PF | Sharpe | maxDD intra | pos days | pos months |
|---|---|---|---|---|---|---|---|---|---|---|
| MNQ | MAIN 2025-26 | 364 | **+6,868** | 52% | +18.9 / +21.2 | **1.315** | 1.17 | -1,516 | 52% | 15/21 |
| MNQ | MAIN ex 2025-04-09 | 363 | +3,778 | 52% | +10.4 | 1.173 | | | | |
| MNQ | PRIOR 2023-24 | 304 | +650 | 51% | +2.1 / +4.4 | 1.045 | 0.22 | -1,845 | 51% | 13/24 |
| MNQ | 2015-2024 | 1,972 | -4,891 | 49% | -2.5 / -0.2 | 0.910 | -0.45 | -5,589 | 49% | 44% |
| MES | MAIN 2025-26 | 358 | -518 | 53% | -1.4 / +2.4 | 0.960 | -0.23 | -2,020 | 53% | 11/21 |
| MES | PRIOR 2023-24 | 302 | -562 | 50% | -1.9 / +1.9 | 0.927 | -0.36 | -1,518 | 50% | 9/24 |
| MES | 2015-2024 | 1,912 | -5,974 | 47% | -3.1 / +0.7 | 0.832 | -0.91 | -6,184 | 47% | 36% |

Gross vs cost (the spec's first question): the mean gross move captured by the 12:00-14:00 long on non-macro days is **+$0.7/MES and
-$0.2/MNQ per trade over 2015-2024** against ~$3.80 / $2.30 round-trip costs; on 2025-26 it is +$0.9 (MES) and +$18.8 (MNQ). The
published ~2 bp/day is ~$6/MES at 6,000, so even the paper's own number is barely above cost; our 2015-2024 data shows ~0 bp.
The 2025-26 MNQ result is a different animal (see concentration below).

Reversal variant (`short_then_long`, the paper's second version): MES MAIN 639 trades, -$2,309, PF 0.893; PRIOR PF 0.842;
2015-2024 3,654 trades, -$17,190, PF 0.738. MNQ MAIN 605 trades, -$840, PF 0.978; PRIOR 0.898; 2015-2024 PF 0.841. The 11:00-12:00
short is wrong on our data in every period (the 11:00-12:00 hour is mildly **positive**, +1.2 to +1.7 bp/day, t ~2.3, on 2010-2024).
`short_only` MES MAIN: 358 trades, -$1,607, PF 0.864. Stop definition: `stop_mode='atr'` (0.4 ATR) on MNQ MAIN PF 1.181 (+$4,523, worst
day -$593 vs -$284), PRIOR 1.016; MES MAIN 0.903. The pct stop is the published one and slightly better; the sensitivity is not the story.

## The lunch profile on our data (`lunch_profile_summary.csv`, `lunch_profile_{MES,MNQ}.csv`; close-to-close, bp, no costs)

11:00->12:00 (`am`) and 12:00->14:00 (`pm`) mean return per session, full sessions only (thin sessions excluded):

| index | period | n | am mean bp (t) | am %pos | pm mean bp (t) | pm %pos | pm std bp |
|---|---|---|---|---|---|---|---|
| SPX | 2010-2024 | 3,276 | +1.2 (2.4) | 54% | **0.0 (0.0)** | 54% | 37 |
| SPX | 2015-2024 | 2,352 | +1.3 (2.1) | 54% | -0.3 (-0.4) | 54% | 38 |
| SPX | 2023-2024 | 386 | +1.9 (1.5) | 52% | +1.7 (1.2) | 56% | 29 |
| SPX | 2025-2026 | 429 | -0.7 (-0.5) | 52% | +2.4 (0.9) | 55% | 52 |
| NDX | 2010-2024 | 3,402 | +1.5 (2.4) | 55% | -0.2 (-0.2) | 55% | 44 |
| NDX | 2015-2024 | 2,376 | +1.7 (2.2) | 56% | -0.5 (-0.6) | 55% | 46 |
| NDX | 2023-2024 | 384 | +4.0 (2.4) | 55% | +2.8 (1.4) | 55% | 39 |
| NDX | 2025-2026 | 430 | +0.4 (0.2) | 54% | +3.3 (1.1) | 54% | 62 |

By year, pm mean bp (SPX / NDX): 2010 +7.5/+8.5 (21-31 sessions), 2011 -0.8/-0.9, 2012 +3.4/+2.0, 2013 +1.5/+1.4, 2014 -0.8/-0.9, 2015 +0.1/-0.3,
2016 -1.3/-2.6, 2017 +2.0/+2.6, 2018 -2.9/-3.4, 2019 +2.1/+2.0, 2020 -2.7/-2.5, 2021 +1.0/+0.4, 2022 -4.1/-5.4, 2023 +2.0/+4.7, 2024 +1.6/+1.8,
2025 +3.5/+3.9, 2026 +0.8/+2.5. Positive in bull years, negative in 2016/2018/2020/2022: the "lunch effect" is the market's drift
split across the day, not a clock anomaly. The only year-level t above 2 is 2010 (21 sessions). The 11:00-12:00 hour, which the paper
shorts, is the more reliably positive of the two (t 2.1-2.4 over 2010-2024 on both indices), i.e. the reversal variant is backwards here.
By flag (2010-2024 SPX): non-macro pm +0.2 bp, macro pm -0.9, FOMC pm +2.6 (107 days; 14:00 statement is outside the window),
opex pm **-4.4 bp (t -1.9)** (NDX -4.8, t -1.7): the opex midday is the one consistently negative slot (`skip_opex` is in PARAMS, off by default).
2025-26: SPX macro-day pm **+16.2 bp** (74 days, std 100: the April 2025 tariff days) vs non-macro -0.5; NDX macro +8.6 vs non-macro +2.3.

## P&L on macro vs non-macro days (`macro_vs_nonmacro.csv`; `skip_macro=False` run split by `macro_day | fomc`)

| contract / variant | period | non-macro: trades / net / PF / avg gross | macro: trades / net / PF / avg gross |
|---|---|---|---|
| MNQ long_only | 2015-2024 | 1,972 / -4,891 / 0.91 / -0.2 | 408 / +156 / 1.01 / +2.7 |
| MNQ long_only | 2025-2026 | 360 / +5,952 / 1.28 / +18.8 | 68 / -1,238 / 0.80 / -15.9 |
| MES long_only | 2015-2024 | 1,912 / -5,974 / 0.83 / +0.7 | 440 / -1,243 / 0.88 / +1.0 |
| MES long_only | 2025-2026 | 354 / -1,012 / 0.92 / +0.9 | 75 / +1,343 / 1.41 / +21.7 |
| MNQ short_then_long | 2015-2024 | 3,706 / -15,079 / 0.84 / -1.8 | 735 / -3,117 / 0.87 / -1.9 |
| MES short_then_long | 2015-2024 | 3,654 / -17,190 / 0.74 / -0.9 | 811 / -4,633 / 0.75 / -1.9 |

`skip_macro` is not a stable edge either way: it helps MNQ 2025-26 (-$1,238 removed) and hurts MES 2025-26 (+$1,343 removed), and is
neutral on 2015-2024 (macro-day PF 1.01 / 0.88 vs non-macro 0.91 / 0.83). The grid confirms it (below).

## Grid (16 combos x MAIN / PRIOR; `grid_MNQ.csv`, `grid_MES.csv`; Lucid `exp_net_lb` -$146 = the fee in 31 of 32 cells, -$141 in one)
- MNQ: rank correlation of cell PF MAIN vs PRIOR 0.72, but only **3/16 cells PF > 1 on both** and all three are `long_only / 14:00`
  with `skip_macro=False` or `stop_pct 0.5` (PRIOR PF 1.04-1.10, MAIN 1.11-1.24). Every `long_only` cell is PF 1.04-1.31 on MAIN; every
  `short_then_long` cell is PF < 1 on both periods (0.75-0.92 PRIOR, 0.94-0.99 MAIN). `long_exit 13:30` is worse than 14:00 everywhere
  (the 13:30-14:00 half hour carries the 2025-26 gain). Plateau on MAIN only.
- MES: rank correlation 0.35, **0/16 cells PF > 1 on both**; best MAIN cell `long_only / 0.3 / 14:00 / skip_macro=False` PF 1.03 (+$420)
  with PRIOR 0.91. MES, the paper's instrument, is dead in every cell.
- No cell is `recommended` by the Lucid lower-bound sizing in either period on either contract.

## Diagnostics (MNQ, defaults, MAIN; `report_MNQ_main.txt`)
- 364 trades, all 12:00 longs: 281 clock exits at 14:00 (+$81.5 avg, 68% win) and 83 stops (-$193 avg) = -$16,045 of stops against
  +$22,913 of flat exits. Median trade +$9.85; **top-10 trades = 110% of the net**; 2025-04-09 (the tariff-pause rally, 13:18 ET) alone is
  +$3,089 = 45% of MAIN net (`largest_day_share` 0.45). Ex that day: PF 1.17, +$10.4/trade. 2025 PF 1.42 / 2026 PF 1.19.
- Weekday: Tue +$3,028 and Wed +$2,816 carry it; Mon +$248, Thu +$46, Fri +$730. VIX: 15-20 bucket +$4,298 on 252 trades; 20-25
  -$624; 25-35 +$1,832 on 25 trades with 28% win (one trade). Months: 15/21 positive, 2025-04 +$3,017, worst 2026-02 -$673.
- Positive days 190 / negative 174 (52%), avg +$151 / -$125; 7 consecutive losing days max. Share of trading days >= $15/micro (= a $150
  day at 10 micros): 39.5%. At 10 micros the intraday maxDD is ~$15,200: far outside the $2,000 MLL; realistic size is 5 micros, where a
  stop day is -$900 and the 2025-26 average day is +$94.
- PRIOR (MNQ): +$650 on 304 trades is 13/24 positive months with -$652 (2024-08) and -$632 (2024-10) months; PF 1.045 = noise.

## Walk-forward (the yardstick)
`python3 -m backtest.final_select --ids cal_lunch --jobs 2 --wf_start 2022-01-01 --max_combos 16` (MNQ; IS 12 months / OOS 3 months,
parameters chosen from the 16-cell GRID by IS Sharpe with >= 30 IS trades; `walkforward.json`, `final_select.log`, `wf_oos_2025_daily.csv`).

| OOS span | trades | net $ | PF | Sharpe | pos months | maxDD intra |
|---|---|---|---|---|---|---|
| **2025-01..2026-09** | **401** | **+4,379** | **1.185** | 0.76 | 14/21 | -2,230 |
| 2025-01..2026-09 ex 2025-04-09 | 400 | +1,290 | 1.055 (daily) | | | |
| 2025-01..2026-09 ex April 2025 | 339 | +1,793 | 1.082 (daily) | | | |
| 2025 only | 207 | +4,418 | 1.351 | | | |
| 2026-01..2026-09 | 194 | -38 | 0.997 | | | |
| 2023-01..2024-12 (8 folds) | 366 | -1,339 | 7/8 folds negative | | | |
| whole OOS 2023-01..2026-09 | 767 | +3,040 | 1.072 | 0.32 | 53% | -2,878 |

Fold path: the 2023 folds picked `short_then_long` twice (both negative), then `long_only / 14:00` with `stop_pct` 0.5 -> 0.3 and
`skip_macro` flipping four times; the two 2026 Q1-Q2 folds picked `long_exit 13:30` (OOS -$1,197 / PF 0.67 and +$1,041). The OOS
2025-26 stream has 43% positive days (84 flat days with no trade), 40% of days >= $15/micro, and its top-10 days are 176% of the net.
Monthly: 2025-04 +$2,586, 2025-11 +$1,097, 2026-06 +$764 against 2026-02 -$986, 2025-06 -$949.

Lucid 50K Flex Monte Carlo on the OOS 2025-26 stream (`lucid_wf_2025`): best size **5 micros**, pass rate 0.178, pass-within-21 0.156,
P(first payout) 0.008, expected net **-$118** per evaluation, bootstrap lower bound **-$146** = the zero-edge control (-$146) ->
**not recommended** at any size (10-40 micros: pass 0.15 -> 0.07, expected net -$138 to -$146). The ~$10/trade OOS mean at 5 micros is
~$50/day: it cannot reach the $3,000 target inside the 21-session window and the 83 stop days at -$900 each breach the trailing MLL.

## What was tried and why it failed
1. Default long-only leg on MES and MNQ, MAIN / PRIOR / 2015-2024: MES negative in every period (the paper's own instrument); MNQ
   positive on 2025-26 (PF 1.31, 45% from one day), break-even on 2023-24 (1.05), negative 2015-2024 (0.91).
2. Reversal and short-only variants: negative everywhere (the 11:00-12:00 hour is positive on our data, not negative).
3. Raw lunch profile 2010-2026 by year and flag: 12:00-14:00 mean is 0.0 bp over 2010-2024 on SPX (-0.2 on NDX) with a sign that
   follows the year's drift; no t-stat above 2 in any multi-year window. The reusable facts: opex midday -4 to -5 bp (t ~ -1.8), FOMC-day
   midday +2.6 / +4.7 bp before the 14:00 statement, 11:00-12:00 +1.2 to +1.7 bp (t ~2.3).
4. Macro vs non-macro split and the 16-cell grid: `skip_macro` flips sign between contracts and periods; MES has no cell positive on
   both periods; MNQ's plateau exists on MAIN only. ATR stop: same conclusion.
5. Walk-forward OOS 2025-26 and the Lucid Monte Carlo (section above).
6. Not pursued (in-sample curve fitting on a single-day-dominated result): weekday filters, VIX gates, dropping the stop, trailing stops,
   skip_opex as default, entry at 13:00 or 13:30 only.

## Verdict
**marginal**, and only because the mechanical rule (walk-forward OOS 2025-26 PF >= 1.03 on >= 40 trades: here 1.185 on 401) says so.
The honest reading is that there is no lunch edge net of micro costs: the 12:00-14:00 return averages 0.0 bp/day over 2010-2024 on both
indices and its sign tracks the year's drift; the paper's instrument (MES) loses in every period and every grid cell; the reversal variant
is backwards on our data; MNQ's 2025-26 profit is one tariff-rally afternoon plus the 2025 long-biased tape (2026 OOS is flat), and the
Lucid lower bound equals the zero-edge control. It fails the spec's own acceptance test (PF >= 1.2 on 2015-2026: MNQ long_only 2015-2026
is PF 1.00 on 2,808 trades with skip_macro off, 0.91 on 2015-2024 with it on). Not a portfolio leg and not a funded-phase filler either
(40% of days >= $15/micro, but those days are the same trend days the morning legs already own).
Reusable by-products: `lunch_profile_summary.csv` (11:00-12:00 and 12:00-14:00 returns by year and by macro / FOMC / opex flag, 2010-2026,
SPX and NDX): the opex midday is -4 to -5 bp (t ~ -1.8) and the FOMC-day 12:00-14:00 is +2.6 / +4.7 bp (pre-statement drift), both
usable as time-of-day bias flags for the other families; the 11:00-12:00 hour is mildly positive (t ~2.3), so a midday short bias is wrong.
