# cal_window - Calendar day-window long with controls (family calendar_seasonal_structural)

Module: `strategies/cal_window.py` (uses the shared flags helper `strategies/_cal_flags.py` written with cal_macro_pm; the
two extra flags `precash` and `pre_witch5` are computed inside this module on the helper's calendar sessions).
Research: `research/families/calendar_seasonal_structural.md`; spec sections 7 (day-window test) and 2 (Lucca-Moench FOMC
morning leg) of `research/specs/calendar_seasonal_structural.md`.
Periods: MAIN = 2025-01-01..2026-09-30, PRIOR = 2023-01-01..2024-12-31, long history 2011-01-01..2024-12-31 (the 1-min
feed starts 2010-11-15, so "2010-2024" is 2011-2024 here; Feb-Jul 2023 the feed prints ~180 RTH bars/session and those
sessions are skipped by the engine's thin-session filter, hence 2023 has 140 full sessions). All numbers per ONE micro
contract after costs ($1.30 RT + 1 tick slippage per side on market/stop fills).

**Verdict: marginal by the letter of the yardstick (walk-forward OOS 2025-01..2026-09 on MNQ: 80 trades, PF 1.49, net
+$5,890), dead by the evidence.** The walk-forward picked `totm` in every 2025-26 fold, and TOTM 09:31->15:55 is +18/+22 bp
per day over the all-days control in 2025-26 (t ~ 2.1-2.3 on 80 days) - but on 2011-2024 (605-620 days) it is -0.6/-0.2 bp
vs the control (t ~ 0), negative in 8 of 14 years, and the Lucid Monte Carlo on the OOS stream is not recommended at any
size (lower bound -$146 = the zero-edge control). The honest reading is a two-year hot streak in a long-biased tape, the
precise failure mode the family report predicted. **No window meets the flag criterion** (mean-minus-control >= +8 bp/day
with t >= 2 on 2011-2024 AND positive in 2025-26): `payday` passes the historical test (+11/+14 bp, t 3.0-3.4, PF 1.33) but
is the worst window of all in 2025-26 (-19/-27 bp, t -2.5). The Lucca-Moench FOMC drift is confirmed in this data but it
lives in the overnight leg (prev close -> 09:30: +22/+32 bp, t 3.7-3.9 on 67 press-conference meetings 2013-2024), not in
the 09:31->13:55 intraday leg (+2 bp vs control, t 0.5; -7/-10 bp on the 14 events of 2025-26).

## Rules as implemented (all ET; a 1-min bar with tod=T covers [T, T+1))
- `i(HH:MM)` = the bar with tod = HH:MM (a missing 09:31 bar = no trade; never the 09:30 print). Market orders fill at that
  bar's open + 1 tick. `ATR14d = daily_atr(df1, 14, rth_only=True)` (Wilder, shifted one day); `SMA_D(200) = sma(D.close, 200).shift(1)`
  on RTH daily bars; `prev_close` = last RTH close of the prior session; `open_0930` = open of the 09:30 bar.
- Flags (`_cal_flags.flags`, calendar arithmetic on sessions with >= 60 RTH bars): `totm` = last session of a month (T-1) or
  the first three (T+1..T+3); `opex_week` = Mon-Thu of the monthly-expiration week (excluding the expiration day); `fomc` =
  hard-coded statement days verified on federalreserve.gov 2013-2026; `press_conference`; `payday` = first session with
  day >= 15 and the next one; `holiday_next` = next weekday closed or a half-day; `santa` = last 5 sessions of December +
  first 2 of January; `dow`. Computed here: `precash` = T-4, T-3, T-2 of the month; `pre_witch5` = the 5 sessions before a
  quad-witching day.
- Window table (window -> flag, default side, exit): `totm` +1 exit_time; `opex_week` +1 exit_time; `fomc` (press-conference
  meetings only when press_conf_only) +1 exit = min(exit_time, statement time - 5 min) = 13:55; `fomc_all` (every statement
  day) +1 same exit; `all_days` +1 exit_time (negative control); `payday` +1; `pre_witch5` +1; `pre_holiday` +1 (12:55 exit on
  half-days, which the engine skips by default); `santa` +1; `precash` -1; `dow_tuewed` (Tue, Wed) +1. `side` param +1/-1 overrides.
- `day_ok[d]` = window flag and ATR non-NaN and (not trend_filter or prev_close > SMA_D(200)). Entry: market at the open of
  i(09:31) with `stop_pts = stop_atr x ATR14d` (0.75), optional target `target_atr x ATR` (0 = none). Exit: stop / target /
  `exit_at(i(exit_tod))` = market at the open of the first bar >= exit_tod (15:55 default; 13:55 on FOMC days for the fomc
  windows), plus per-session `force_flat` / `allow_entry=False` from exit_tod to the session end and the global
  `set_session('09:31', '09:32', '15:55')`. One trade per day, no re-entry after a stop. Daily stops moot.
- Defaults (`PARAMS` = McConnell-Xu / Quantpedia TOTM window forced into the intraday-only form): {"window": "totm", "side": "auto", "entry_time": "09:31", "exit_time": "15:55", "stop_atr": 0.75, "target_atr": 0.0, "trend_filter": false, "press_conf_only": true, "max_trades": 1}.
- GRID (16): window {totm, opex_week, fomc, all_days} x exit_time {12:00, 15:55} x stop_atr {0.5, 1.0}.

Look-ahead / mechanics audit (scratch script on every MAIN trade, MES): entry bar tod == 09:31 on all 80 TOTM / 430 all-days /
14 FOMC / 62 precash trades, fill == that bar's open + side x 1 tick, FOMC exits all at 13:55 (one stop), exit_time=12:00
exits at 12:00, latest exit 15:58 (a missing 15:55-15:57 bar). Window counts per year: totm 41-47, opex_week 40-47, fomc 4-8
(press-conference), payday 19-23, pre_witch5 18-20, pre_holiday 5-11, santa 2-7, precash 29-35, dow_tuewed 90-104, all 219-251.

## Headline results, default rule (window = totm, 09:31 -> 15:55, stop 0.75 ATR)

| contract | period | trades | net $ | win | avg $/trade | PF | Sharpe | maxDD intra | pos months |
|---|---|---|---|---|---|---|---|---|---|
| MNQ | MAIN 2025-26 | 80 | +10,080 | 65% | +126 | 1.93 | 1.80 | -2,368 | 13/21 |
| MNQ | PRIOR 2023-24 | 72 | +1,658 | 58% | +23 | 1.21 | 0.47 | -1,298 | 11/24 |
| MNQ | 2011-2024 | 620 | +2,202 | 52% | +3.6 | 1.06 | 0.12 | - | 8/14 years negative |
| MES | MAIN 2025-26 | 80 | +4,116 | 59% | +51 | 1.71 | 1.48 | -1,186 | 13/21 |
| MES | PRIOR 2023-24 | 71 | -361 | 52% | -5 | 0.91 | -0.21 | -1,189 | 8/24 |
| MES | 2011-2024 | 605 | -1,572 | 51% | -2.6 | 0.94 | -0.15 | - | - |

Walk-forward (`python3 -m backtest.final_select --ids cal_window --jobs 2 --wf_start 2022-01-01 --max_combos 16`, MNQ, IS 12m /
OOS 3m, selection by IS Sharpe over the 16-cell grid, min 30 IS trades): **OOS 2025-01..2026-09 = 80 trades, net
+5,890, PF 1.49, Sharpe 1.10, 59% positive days, 10/21 positive months, maxDD intra -3,217.**
Whole OOS span 2023-01..2026-09: 356 trades, PF 1.11, net +4,405, Sharpe 0.39. Parameter path: 2023 and
2024 folds alternated totm / all_days / opex_week (2023-07..2024-09 the IS Sharpe preferred `all_days`, OOS PF 0.68-1.52,
net -$1,949 over those 5 folds); every fold from 2024-10 on chose `totm` (exit 15:55 / stop 0.5 in 6 of 8, exit 12:00 / stop 1.0
in 2, those two were the losing folds: -$1,261, -$197). Lucid 50K Flex on the OOS 2025-26 stream: best size 5 micros, pass rate
0.24, pass-within-21 0.15, P(first payout) 0.05, expected net +132 per evaluation, **bootstrap lower bound
-146 = the zero-edge control (-146) -> not recommended** (p(lose the fee) 0.76). One trade per day at 09:31 with a
~0.75-ATR stop puts 80 trades in 21 months; a 5-micro evaluation needs ~$3,000 of a stream that nets $73/trade/micro.

## The window table (the deliverable): every window vs the all-days control, intraday and overnight (`windows.csv`)

Columns: days = sessions in the window (full sessions with ATR); trades/net/PF/avg/stops = engine, net of costs, with the
0.75-ATR stop; "intraday mean bp" = side x (open of the first bar >= exit_tod / open of the 09:31 bar - 1) on the window
days, gross, no stop (so stops do not confound the comparison); t = one-sample t of that mean; "control bp" = the same
quantity on all sessions of the period (long, same exit); "minus control"; "t vs rest" = Welch t of window days vs
non-window days; "overnight bp" = side x (09:30 open / prev RTH close - 1) on the same days, with its t and the all-days
control; "close-to-close bp" = side x (exit / prev close - 1). For `precash` (side -1) every bp figure is already signed for
the short, so a positive number means the short worked.

#### MES, 2025-01..2026-09

| window | side | days | trades | net $ | PF | avg $/trade | stops | intraday mean bp | t | control bp | minus control bp | t vs rest | overnight bp (same days) | t | control ON bp | close-to-close bp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| totm | +1 | 80 | 80 | +4108 | 1.71 | +51.3 | 18 | +21.4 | 2.6 | +3.4 | +18.0 | 2.3 | -9.7 | -1.2 | +3.6 | +12.8 |
| opex_week | +1 | 80 | 80 | -1543 | 0.78 | -19.3 | 15 | -3.5 | -0.5 | +3.4 | -6.9 | -1.0 | +14.7 | 2.0 | +3.6 | +10.6 |
| fomc | +1 | 14 | 14 | -519 | 0.27 | -37.1 | 1 | -6.6 | -1.1 | +4.0 | -10.6 | -1.5 | +5.9 | 1.1 | +3.6 | -4.1 |
| fomc_all | +1 | 14 | 14 | -519 | 0.27 | -37.1 | 1 | -6.6 | -1.1 | +4.0 | -10.6 | -1.5 | +5.9 | 1.1 | +3.6 | -4.1 |
| all_days | +1 | 430 | 430 | +2697 | 1.07 | +6.3 | 92 | +3.4 | 0.8 | +3.4 | +0.0 | - | +3.6 | 1.1 | +3.6 | +7.0 |
| payday | +1 | 40 | 40 | -3206 | 0.29 | -80.2 | 9 | -15.9 | -2.2 | +3.4 | -19.3 | -2.5 | +10.6 | 1.3 | +3.6 | -5.1 |
| pre_witch5 | +1 | 34 | 34 | -1614 | 0.51 | -47.5 | 7 | -13.4 | -1.3 | +3.4 | -16.8 | -1.6 | +20.6 | 2.1 | +3.6 | +6.8 |
| pre_holiday | +1 | 19 | 19 | +164 | 1.15 | +8.7 | 3 | +7.3 | 0.7 | +3.4 | +3.9 | 0.3 | +1.0 | 0.1 | +3.6 | +11.3 |
| santa | +1 | 8 | 8 | -581 | 0.23 | -72.6 | 3 | -20.2 | -1.2 | +3.4 | -23.7 | -1.4 | +21.5 | 1.7 | +3.6 | +4.4 |
| precash | -1 | 62 | 62 | +637 | 1.14 | +10.3 | 5 | +5.1 | 0.6 | +3.4 | +1.7 | 1.1 | -7.6 | -1.6 | +3.6 | -1.6 |
| dow_tuewed | +1 | 179 | 179 | +1265 | 1.08 | +7.1 | 37 | +6.9 | 0.9 | +3.4 | +3.5 | 0.7 | +4.9 | 1.1 | +3.6 | +11.3 |
| totm+trend | +1 | 68 | 68 | +1652 | 1.30 | +24.3 | 17 | +13.0 | 1.6 | +3.4 | +9.6 | 1.2 | -3.6 | -0.6 | +3.6 | +10.3 |
| all_days+trend | +1 | 372 | 372 | -559 | 0.98 | -1.5 | 80 | +0.7 | 0.2 | +3.4 | -2.8 | -0.8 | +4.2 | 1.6 | +3.6 | +4.7 |

#### MES, 2011-01..2024-12

| window | side | days | trades | net $ | PF | avg $/trade | stops | intraday mean bp | t | control bp | minus control bp | t vs rest | overnight bp (same days) | t | control ON bp | close-to-close bp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| totm | +1 | 605 | 605 | -1572 | 0.94 | -2.6 | 155 | +0.9 | 0.3 | +1.6 | -0.6 | -0.2 | +2.5 | 0.9 | +3.5 | +3.9 |
| opex_week | +1 | 617 | 617 | -2984 | 0.88 | -4.8 | 118 | +1.6 | 0.6 | +1.6 | +0.1 | 0.0 | -0.3 | -0.1 | +3.5 | +1.8 |
| fomc | +1 | 77 | 77 | +117 | 1.08 | +1.5 | 4 | +4.9 | 1.3 | +1.6 | +3.3 | 0.8 | +19.7 | 3.2 | +3.5 | +23.6 |
| fomc_all | +1 | 107 | 107 | -340 | 0.84 | -3.2 | 7 | +0.7 | 0.2 | +1.6 | -0.9 | -0.3 | +18.7 | 3.7 | +3.5 | +18.8 |
| all_days | +1 | 3242 | 3242 | -7914 | 0.94 | -2.4 | 681 | +1.6 | 1.1 | +1.6 | +0.0 | - | +3.5 | 2.9 | +3.5 | +5.3 |
| payday | +1 | 298 | 298 | +2910 | 1.33 | +9.8 | 41 | +13.0 | 3.4 | +1.6 | +11.4 | 3.1 | +4.0 | 1.1 | +3.5 | +17.4 |
| pre_witch5 | +1 | 266 | 266 | -2521 | 0.78 | -9.5 | 57 | +1.7 | 0.3 | +1.6 | +0.1 | 0.0 | +4.7 | 0.9 | +3.5 | +7.0 |
| pre_holiday | +1 | 112 | 112 | +1230 | 1.38 | +11.0 | 15 | +8.3 | 1.3 | +1.6 | +6.7 | 1.1 | +0.5 | 0.1 | +3.5 | +9.7 |
| santa | +1 | 76 | 76 | -836 | 0.76 | -11.0 | 20 | -2.5 | -0.3 | +1.6 | -4.1 | -0.5 | +1.6 | 0.2 | +3.5 | +0.0 |
| precash | -1 | 446 | 446 | -950 | 0.95 | -2.1 | 70 | -1.3 | -0.3 | +1.6 | -2.9 | 0.1 | -9.0 | -3.2 | +3.5 | -11.3 |
| dow_tuewed | +1 | 1348 | 1348 | -4285 | 0.92 | -3.2 | 288 | +1.3 | 0.6 | +1.6 | -0.3 | -0.2 | +6.3 | 3.6 | +3.5 | +7.3 |
| totm+trend | +1 | 472 | 472 | -4103 | 0.78 | -8.7 | 131 | -4.5 | -1.4 | +1.6 | -6.1 | -2.0 | +4.6 | 2.0 | +3.5 | +0.5 |
| all_days+trend | +1 | 2509 | 2509 | -7294 | 0.91 | -2.9 | 526 | +0.2 | 0.2 | +1.6 | -1.4 | -1.3 | +3.0 | 3.1 | +3.5 | +3.3 |

#### MES, 2023-01..2024-12

| window | side | days | trades | net $ | PF | avg $/trade | stops | intraday mean bp | t | control bp | minus control bp | t vs rest | overnight bp (same days) | t | control ON bp | close-to-close bp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| totm | +1 | 71 | 71 | -373 | 0.91 | -5.3 | 18 | -0.1 | -0.0 | +1.7 | -1.7 | -0.3 | -0.8 | -0.1 | +6.0 | -0.6 |
| opex_week | +1 | 73 | 73 | -1011 | 0.78 | -13.8 | 16 | -8.0 | -1.0 | +1.7 | -9.6 | -1.4 | +9.3 | 1.5 | +6.0 | +1.8 |
| fomc | +1 | 12 | 12 | +171 | 1.82 | +14.2 | 0 | +5.6 | 0.8 | +1.8 | +3.8 | 0.5 | +18.6 | 1.3 | +6.0 | +22.1 |
| fomc_all | +1 | 12 | 12 | +171 | 1.82 | +14.2 | 0 | +5.6 | 0.8 | +1.8 | +3.8 | 0.5 | +18.6 | 1.3 | +6.0 | +22.1 |
| all_days | +1 | 386 | 386 | +318 | 1.01 | +0.8 | 81 | +1.7 | 0.5 | +1.7 | +0.0 | - | +6.0 | 2.5 | +6.0 | +7.4 |
| payday | +1 | 36 | 36 | +66 | 1.04 | +1.8 | 5 | -2.0 | -0.2 | +1.7 | -3.6 | -0.4 | -1.1 | -0.1 | +6.0 | -1.7 |
| pre_witch5 | +1 | 29 | 29 | -99 | 0.94 | -3.4 | 7 | -1.2 | -0.1 | +1.7 | -2.9 | -0.3 | +15.4 | 2.0 | +6.0 | +14.0 |
| pre_holiday | +1 | 17 | 17 | +258 | 1.32 | +15.1 | 3 | +12.2 | 1.0 | +1.7 | +10.5 | 0.9 | +0.6 | 0.1 | +6.0 | +14.7 |
| santa | +1 | 13 | 13 | -806 | 0.26 | -62.0 | 4 | -16.3 | -1.5 | +1.7 | -18.0 | -1.6 | -14.3 | -1.0 | +6.0 | -29.6 |
| precash | -1 | 53 | 53 | -157 | 0.93 | -3.0 | 5 | +0.4 | 0.1 | +1.7 | -1.3 | 0.3 | +0.2 | 0.0 | +6.0 | +0.7 |
| dow_tuewed | +1 | 159 | 159 | +529 | 1.06 | +3.3 | 34 | +2.5 | 0.5 | +1.7 | +0.8 | 0.2 | -1.0 | -0.3 | +6.0 | +1.1 |
| totm+trend | +1 | 65 | 65 | -474 | 0.88 | -7.3 | 17 | -1.5 | -0.2 | +1.7 | -3.2 | -0.5 | -3.7 | -0.6 | +6.0 | -4.5 |
| all_days+trend | +1 | 368 | 368 | -220 | 0.99 | -0.6 | 78 | +0.8 | 0.2 | +1.7 | -0.9 | -1.0 | +5.1 | 2.1 | +6.0 | +5.6 |

#### MNQ, 2025-01..2026-09

| window | side | days | trades | net $ | PF | avg $/trade | stops | intraday mean bp | t | control bp | minus control bp | t vs rest | overnight bp (same days) | t | control ON bp | close-to-close bp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| totm | +1 | 80 | 80 | +10069 | 1.93 | +125.9 | 13 | +25.9 | 2.3 | +4.1 | +21.7 | 2.1 | -9.9 | -0.9 | +5.8 | +17.4 |
| opex_week | +1 | 80 | 80 | -4642 | 0.71 | -58.0 | 15 | -7.2 | -0.7 | +4.1 | -11.3 | -1.2 | +20.8 | 2.0 | +5.8 | +12.1 |
| fomc | +1 | 14 | 14 | -1301 | 0.27 | -92.9 | 1 | -10.3 | -1.4 | +4.7 | -15.0 | -1.6 | +21.3 | 2.6 | +5.8 | +6.3 |
| fomc_all | +1 | 14 | 14 | -1301 | 0.27 | -92.9 | 1 | -10.3 | -1.4 | +4.7 | -15.0 | -1.6 | +21.3 | 2.6 | +5.8 | +6.3 |
| all_days | +1 | 429 | 429 | +10050 | 1.14 | +23.4 | 78 | +4.1 | 0.8 | +4.1 | +0.0 | - | +5.8 | 1.3 | +5.8 | +9.7 |
| payday | +1 | 40 | 40 | -7113 | 0.31 | -177.8 | 10 | -23.0 | -2.3 | +4.1 | -27.2 | -2.5 | +13.4 | 1.1 | +5.8 | -9.8 |
| pre_witch5 | +1 | 34 | 34 | -2053 | 0.70 | -60.4 | 7 | -10.2 | -0.7 | +4.1 | -14.4 | -1.0 | +27.6 | 1.8 | +5.8 | +17.2 |
| pre_holiday | +1 | 19 | 19 | +432 | 1.17 | +22.7 | 3 | +5.8 | 0.3 | +4.1 | +1.7 | 0.1 | +9.2 | 0.4 | +5.8 | +15.5 |
| santa | +1 | 8 | 8 | -1165 | 0.28 | -145.6 | 2 | -29.6 | -1.2 | +4.1 | -33.8 | -1.4 | +32.2 | 1.6 | +5.8 | +5.0 |
| precash | -1 | 61 | 61 | +1270 | 1.13 | +20.8 | 3 | +6.0 | 0.5 | +4.1 | +1.8 | 0.9 | -14.7 | -1.9 | +5.8 | -7.4 |
| dow_tuewed | +1 | 178 | 178 | +5160 | 1.18 | +29.0 | 29 | +10.0 | 1.0 | +4.1 | +5.9 | 0.9 | +6.3 | 1.1 | +5.8 | +16.0 |
| totm+trend | +1 | 68 | 68 | +5480 | 1.53 | +80.6 | 13 | +14.2 | 1.2 | +4.1 | +10.1 | 0.9 | -1.2 | -0.1 | +5.8 | +14.1 |
| all_days+trend | +1 | 370 | 370 | +4993 | 1.08 | +13.5 | 67 | +1.7 | 0.4 | +4.1 | -2.4 | -0.6 | +7.2 | 1.8 | +5.8 | +8.5 |

#### MNQ, 2011-01..2024-12

| window | side | days | trades | net $ | PF | avg $/trade | stops | intraday mean bp | t | control bp | minus control bp | t vs rest | overnight bp (same days) | t | control ON bp | close-to-close bp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| totm | +1 | 620 | 620 | +2202 | 1.06 | +3.5 | 158 | +2.2 | 0.5 | +2.3 | -0.2 | -0.0 | +3.1 | 1.0 | +4.6 | +6.0 |
| opex_week | +1 | 634 | 634 | -741 | 0.98 | -1.2 | 114 | +3.6 | 1.0 | +2.3 | +1.3 | 0.4 | +1.6 | 0.5 | +4.6 | +5.8 |
| fomc | +1 | 77 | 77 | +611 | 1.25 | +7.9 | 4 | +4.8 | 0.9 | +2.2 | +2.6 | 0.5 | +28.0 | 3.5 | +4.6 | +32.6 |
| fomc_all | +1 | 107 | 107 | -31 | 0.99 | -0.3 | 6 | -1.3 | -0.3 | +2.2 | -3.5 | -0.8 | +28.6 | 4.3 | +4.6 | +27.4 |
| all_days | +1 | 3359 | 3359 | +2163 | 1.01 | +0.6 | 699 | +2.3 | 1.4 | +2.3 | +0.0 | - | +4.6 | 3.6 | +4.6 | +7.5 |
| payday | +1 | 308 | 308 | +4488 | 1.32 | +14.6 | 47 | +16.2 | 3.4 | +2.3 | +13.8 | 3.0 | +6.0 | 1.5 | +4.6 | +21.8 |
| pre_witch5 | +1 | 268 | 268 | -1814 | 0.89 | -6.8 | 56 | +2.0 | 0.3 | +2.3 | -0.4 | -0.1 | +4.4 | 0.8 | +4.6 | +7.8 |
| pre_holiday | +1 | 130 | 130 | -54 | 0.99 | -0.4 | 19 | +5.1 | 0.7 | +2.3 | +2.8 | 0.4 | +3.7 | 0.7 | +4.6 | +9.2 |
| santa | +1 | 90 | 90 | -2182 | 0.65 | -24.2 | 22 | -5.3 | -0.6 | +2.3 | -7.6 | -0.8 | +2.5 | 0.3 | +4.6 | -0.4 |
| precash | -1 | 467 | 467 | +3073 | 1.12 | +6.6 | 79 | +0.1 | 0.0 | +2.3 | -2.2 | 0.5 | -9.5 | -2.9 | +4.6 | -11.3 |
| dow_tuewed | +1 | 1389 | 1389 | -1761 | 0.98 | -1.3 | 292 | +3.0 | 1.1 | +2.3 | +0.6 | 0.3 | +8.1 | 4.1 | +4.6 | +11.0 |
| totm+trend | +1 | 486 | 486 | -1100 | 0.96 | -2.3 | 134 | -1.6 | -0.4 | +2.3 | -3.9 | -1.1 | +4.7 | 1.4 | +4.6 | +3.7 |
| all_days+trend | +1 | 2641 | 2641 | +2059 | 1.01 | +0.8 | 547 | +1.6 | 0.9 | +2.3 | -0.8 | -0.7 | +5.0 | 4.2 | +4.6 | +6.9 |

#### MNQ, 2023-01..2024-12

| window | side | days | trades | net $ | PF | avg $/trade | stops | intraday mean bp | t | control bp | minus control bp | t vs rest | overnight bp (same days) | t | control ON bp | close-to-close bp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| totm | +1 | 72 | 72 | +1645 | 1.21 | +22.8 | 19 | +7.0 | 0.6 | +4.0 | +3.0 | 0.3 | -9.3 | -0.8 | +5.1 | -1.8 |
| opex_week | +1 | 72 | 72 | -1354 | 0.83 | -18.8 | 13 | -9.0 | -0.9 | +4.0 | -13.0 | -1.4 | +10.8 | 1.4 | +5.1 | +2.4 |
| fomc | +1 | 12 | 12 | +513 | 2.23 | +42.8 | 0 | +10.8 | 1.0 | +3.9 | +6.9 | 0.6 | +26.9 | 1.2 | +5.1 | +38.4 |
| fomc_all | +1 | 12 | 12 | +513 | 2.23 | +42.8 | 0 | +10.8 | 1.0 | +3.9 | +6.9 | 0.6 | +26.9 | 1.2 | +5.1 | +38.4 |
| all_days | +1 | 386 | 386 | +4097 | 1.10 | +10.6 | 77 | +4.0 | 0.9 | +4.0 | +0.0 | - | +5.1 | 1.4 | +5.1 | +9.6 |
| payday | +1 | 36 | 36 | +252 | 1.08 | +7.0 | 5 | -3.9 | -0.3 | +4.0 | -7.9 | -0.6 | -1.7 | -0.2 | +5.1 | -5.4 |
| pre_witch5 | +1 | 29 | 29 | -72 | 0.98 | -2.5 | 6 | -4.2 | -0.3 | +4.0 | -8.2 | -0.6 | +17.3 | 1.6 | +5.1 | +14.8 |
| pre_holiday | +1 | 20 | 20 | -940 | 0.64 | -47.0 | 6 | -3.8 | -0.2 | +4.0 | -7.8 | -0.5 | +4.2 | 0.4 | +5.1 | +3.0 |
| santa | +1 | 13 | 13 | -2021 | 0.16 | -155.4 | 5 | -42.9 | -2.8 | +4.0 | -46.9 | -3.0 | -11.5 | -0.6 | +5.1 | -52.7 |
| precash | -1 | 52 | 52 | +774 | 1.18 | +14.9 | 6 | +1.4 | 0.1 | +4.0 | -2.6 | 0.6 | -0.3 | -0.0 | +5.1 | +0.2 |
| dow_tuewed | +1 | 159 | 159 | +645 | 1.03 | +4.1 | 37 | +3.1 | 0.4 | +4.0 | -0.9 | -0.2 | -2.9 | -0.6 | +5.1 | +0.8 |
| totm+trend | +1 | 68 | 68 | +2062 | 1.28 | +30.3 | 18 | +9.6 | 0.8 | +4.0 | +5.6 | 0.6 | -11.3 | -0.9 | +5.1 | -0.7 |
| all_days+trend | +1 | 368 | 368 | +2601 | 1.06 | +7.1 | 74 | +1.9 | 0.4 | +4.0 | -2.1 | -1.5 | +5.0 | 1.3 | +5.1 | +7.3 |

#### FOMC windows, 2013-01..2024-12 (the real test: 91 statement days with a full session; 67 press-conference meetings)

| contract | window | events | trades | net $ | PF | win | intraday 09:31->13:55 mean bp | t | control bp | minus control | overnight bp (prev close -> 09:30) | t | control ON bp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MES | fomc | 67 | 67 | +88 | 1.06 | 0.39 | +4.1 | 1.08 | +1.9 | +2.2 | +22.5 | 3.74 | +3.8 |
| MES | fomc_all | 91 | 91 | -296 | 0.85 | 0.35 | +0.5 | 0.16 | +1.9 | -1.4 | +17.9 | 3.70 | +3.8 |
| MNQ | fomc | 67 | 67 | +612 | 1.26 | 0.45 | +4.7 | 0.86 | +2.2 | +2.5 | +31.6 | 3.86 | +4.8 |
| MNQ | fomc_all | 91 | 91 | +47 | 1.02 | 0.37 | -1.4 | -0.32 | +2.2 | -3.6 | +26.9 | 3.95 | +4.8 |

### Reading the table
1. **Control**: unconditional long 09:31->15:55 is +3.4 bp/day on MES and +4.1 on MNQ in 2025-26 (PF 1.07 / 1.14, +$2,697 /
   +$10,051 on 430 trades), +1.6 / +2.3 bp over 2011-2024 (PF 0.94 / 1.01). 2025-26 is a long-biased tape; the report's
   "the control must come out ~0" holds for 2011-2024 and for 2023-24 but not for the prime window. Every window result
   below is read relative to it.
2. **totm**: 2025-26 +18 / +22 bp over the control (t vs rest 2.3 / 2.1; 62-65% positive days). 2011-2024: -0.6 / -0.2 bp
   vs control (t -0.2 / 0.0), PF 0.94 / 1.06. 2023-24: -1.7 / +3.0 bp. The 2011-2024 overnight leg on TOTM days is +2.5 /
   +3.1 bp - *below* the all-days overnight mean (+3.5 / +4.6), so in this feed the Atlanta Fed result (TOTM dead in S&P
   futures after 1990) holds for both legs; the 2025-26 edge is intraday but has no historical counterpart. Breakdown of
   the 2025-26 MNQ result: Mon/Tue/Wed +$12,235 on 55 trades vs Thu/Fri -$2,166 on 25; T+2 +$4,328 of the +$10,069; 2023-24
   the same cuts flip (Tue -$1,081, T-1 -$1,893, T+3 +$3,003) and 2011-2024 all four positions are within +/- $26/trade.
   Year by year on MNQ 2011-2024: 2018 +$940, 2020 +$2,870, 2022 +$1,599, 2021 -$2,298, the rest within +/- $706.
   The trend filter (close > SMA200) removes 12 days and *lowers* 2025-26 (+9.6 / +10.1 bp over control) and 2011-2024
   (-6.1 / -3.9 bp, PF 0.78 / 0.96): no help.
3. **opex_week**: intraday negative or zero everywhere (-6.9 / -11.3 bp vs control in 2025-26, PF 0.78 / 0.71; +0.1 / +1.3 bp
   on 2011-2024); the overnight on those days is +14.7 / +20.8 bp in 2025-26 (t 2.0) and +9 / +11 in 2023-24 - the edge,
   where there is one, is overnight, as the report said.
4. **fomc (Lucca-Moench morning leg)**: 2025-26, 14 press-conference events: -$519 / -$1,301, 6/14 winners, -6.6 / -10.3 bp
   intraday (-10.6 / -15.0 vs control). The real test 2013-2024 (67 press-conference meetings): +4.1 / +4.7 bp intraday,
   +2.2 / +2.5 bp over control, t vs rest 0.55 / 0.44, PF 1.06 / 1.27, 40-45% positive days, net +$88 / +$612. On the same
   days the overnight leg is **+22.5 / +31.6 bp (t 3.7 / 3.9; +19 / +27 bp over the all-days overnight, t 3.1 / 3.3)**, and
   close-to-close +25.6 / +36.1 bp, i.e. the published pre-FOMC drift is in this data at the published size, but it accrues
   before 09:30 (the paper's own finding is a 2pm-to-2pm window with the drift concentrated in the morning; here it is the
   overnight part of that morning). All 91 statement days (fomc_all): intraday +0.5 / -1.4 bp (PF 0.85 / 1.02), overnight
   +17.9 / +26.9 bp (t 3.7 / 4.0). The press-conference restriction does nothing intraday. Grid: fomc with exit 12:00 is
   worse than 13:55 in 2025-26 and the same in 2023-24. The morning leg is not an overlay candidate; the overnight leg cannot
   be traded under Lucid (no overnight).
5. **payday**: the only window that clears +8 bp with t >= 2 on 2011-2024 (+11.4 / +13.8 bp over control, t vs rest 3.1 /
   3.0, PF 1.33 / 1.32 on 298-308 trades, 59% positive days) - and the single worst window in 2025-26 (-19.3 / -27.2 bp vs
   control, t -2.5 / -2.6, PF 0.29 / 0.31 on 40 trades, 33-38% positive) and flat in 2023-24. Fails the "positive in 2025-26"
   clause. Documented as a historical-only effect; not a flag.
6. **pre_witch5**: intraday zero on 2011-2024 (+0.1 / -0.4 bp), negative in 2025-26 (-17 / -14 bp); overnight +20.6 / +27.6 bp
   in 2025-26 (t ~2) and +15 / +17 in 2023-24: again overnight.
7. **pre_holiday**: the one window with a consistent intraday sign on MES: +6.7 bp over control on 2011-2024 (t 1.1, PF 1.38,
   60% positive on 112 trades), +10.5 in 2023-24, +3.9 in 2025-26 - but below the +8 bp / t >= 2 bar and only 9 days/yr;
   on MNQ +2.8 / -7.8 / +1.7. The overnight on those days is ~0. Suggestive, not a flag (and most of those days precede a
   half-day the engine skips anyway).
8. **santa**: negative intraday in every period on both contracts (-24 / -34 bp vs control in 2025-26 on 8 days, -18 / -47 in
   2023-24, -4 / -8 on 2011-2024); the report's "failed 2024-25" is confirmed and extended.
9. **precash (short T-4..T-2)**: intraday ~0 vs control everywhere (+1.7 / +1.8 bp in 2025-26, -2.9 / -2.2 on 2011-2024; PF
   0.95 / 1.12 long-run); the overnight on those days is *against* the short (-9 bp, t -3.2 / -2.9 on 2011-2024, i.e. those
   mornings gap up). Not a short-side flag.
10. **dow_tuewed**: +3.5 / +5.9 bp over control in 2025-26 (t 0.7 / 0.9), -0.3 / +0.6 on 2011-2024: control-like, as
    expected. The overnight leg on Tue/Wed is +6.3 / +8.1 bp (t 3.6 / 4.1 on 2011-2024).

**Flag outcome for the other families: none.** No calendar window has an intraday-only edge that is both historically
significant and positive in 2025-26; `payday` is historically significant and negative now, `totm` is strong now and zero
historically. The overnight component carries the TOTM-adjacent, OPEX-week, pre-witching and FOMC effects, consistent with
the report (SPY 90.6% of 1993-2024 gains overnight).

## Grid (16 combos x MAIN/PRIOR, `grid_MES.csv`, `grid_MNQ.csv`)
- MES: rank correlation of cell PF between MAIN and PRIOR -0.15. MAIN is ordered totm (PF 1.71-2.08) > all_days 15:55
  (1.08-1.11) > all_days 12:00 (0.97-0.99) > opex_week (0.72-0.99) > fomc (0.25-0.66); PRIOR: fomc (1.62-1.82 on 12 trades) >
  all_days (0.96-0.98) > totm (0.58-0.85) > opex_week (0.73-0.98). Nothing is positive on both periods except the 12-trade
  fomc cells and no totm cell. exit 15:55 beats 12:00 for totm in both periods (the afternoon carries the 2025-26 move).
- MNQ: rank correlation 0.66. MAIN: totm 1.65-1.87, all_days 1.01-1.12, opex_week 0.73-1.00, fomc 0.28-0.54. PRIOR: totm
  15:55 1.12-1.32, totm 12:00 0.92-1.04, all_days 1.06-1.14, fomc 1.24-2.23 (12 trades), opex_week 0.73-0.92. The MNQ totm x
  15:55 cells are positive on both periods (the reason the walk-forward keeps picking them), but the 2011-2024 run of the
  same cell is PF 1.06 / +$3.6 per trade. stop_atr 0.5 vs 1.0 is immaterial (13-19 stops per period at 0.75).

## Diagnostics (MNQ, defaults, MAIN; `backtest.report`)
- 80 trades: 67 flat at 15:55, 13 stops. By weekday: Mon 18 / +$3,808, Tue 19 / +$5,185, Wed 18 / +$3,242, Thu 10 / -$267,
  Fri 15 / -$1,889. By month: 13 of 21 positive; best 2026-08 +$2,194 (2 days +$1,123 / +$1,071), 2025-02 +$1,957; worst
  2026-07 -$1,501, 2026-01 -$816. Largest day 11% of net; 5 consecutive losing trades max.
- VIX (lagged): < 15: 6 trades -$145; 15-20: 55 / +$4,489; 20-25: 17 / +$5,277 (82% win); > 25: 2 / +$458 - half the net
  comes from the 17 elevated-VIX month-turns, i.e. the 2025-04 and 2026 Q2-Q3 rebounds.
- Positive days 52 / negative 28, avg +$402 / -$386: a 65% win rate on a symmetric payoff is the whole result; 2011-2024 the
  win rate is 52% with the same symmetry.

## What was tried and why it failed
1. Default rule (totm) on MES and MNQ, MAIN / PRIOR / 2011-2024: strong 2025-26, flat-to-negative before. MNQ chosen as the
   contract (positive on MAIN and PRIOR; MES PRIOR negative).
2. Full 11-window table vs the all-days control with the overnight leg, 3 periods x 2 contracts (`windows.csv`): no window
   clears the flag criterion; the historically significant one (payday) is the worst now; FOMC drift is overnight.
3. 16-cell grid: no plateau across periods on MES (rank corr -0.15); MNQ totm x 15:55 positive on both periods but
   zero over 2011-2024.
4. Trend filter on totm / all_days: hurts in every period.
5. Walk-forward OOS 2025-26 PF 1.49 on 80 trades (marginal by the letter); Lucid lower bound = zero-edge control.
6. Not pursued (in-sample curve fitting on <= 80 trades): dropping Thu/Fri, keeping T+2 only, VIX gates, per-position sides.

## Verdict
**marginal** per the yardstick definition (walk-forward OOS 2025-01..2026-09 PF 1.49 >= 1.03 on 80 >= 40 trades), recorded
with the explicit caveat that the same rule is PF 1.06 (MNQ) / 0.94 (MES) over 620 / 605 trades 2011-2024 with a mean-minus-
control of ~0 bp, that the 2025-26 result is 55 Mon-Wed trades in a long-biased tape, and that the Lucid Monte Carlo rejects
it at every size. It should not be given a portfolio slot; a later verification should expect it to fail. The reusable
output is the control-adjusted window table: no `+1` calendar bias flag is justified for the ORB / mean-reversion families,
the pre-FOMC drift is an overnight effect (+22-32 bp, t ~3.8, 2013-2024) with no 09:31-13:55 counterpart, and `payday`
(+11-14 bp over control, t ~3, 2011-2024) is the only historically significant intraday window and it has inverted since 2025.
