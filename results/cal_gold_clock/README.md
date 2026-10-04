# cal_gold_clock - Gold round-the-clock legs on MGC (family calendar_seasonal_structural)

Module: `strategies/cal_gold_clock.py` (shared flags: `strategies/_cal_flags.py`). Research: `research/families/calendar_seasonal_structural.md`
section 18 (CBS thesis "Gold Price Dynamics Around the Clock", GC 5-min 2001-2018; Caminschi-Heaney 2014); spec
`research/specs/calendar_seasonal_structural.md` section 9. Instrument: **MGC only** (XAUUSD 1-min proxy; MGC $10/pt, tick 0.10,
$1.30 RT + 1 tick slippage per side = ~$3.30 per round trip). Periods: MAIN = 2025-01-01..2026-09-30, PRIOR = 2023-01-01..2024-12-31,
sub-periods 2010-2014 / 2015-2019 / 2020-2024 for the thesis's regime dependence. All numbers per ONE micro contract after costs.

**Session traded is the London/COMEX daytime, not the 08:20-13:30 pit window**: west_short 03:00-10:00 ET, pmfix_fade fixPM-30 -> fixPM
(normally 09:30-10:00 ET), ny_long 10:05-16:30 ET. Every leg is flat by 16:30 ET (Lucid gold deadline 16:45). The thesis's strongest leg,
the Asian-hours long 18:00-02:00, is an overnight hold and is **not implemented** (project convention).

## Verdict: DEAD

Walk-forward OOS 2025-01..2026-09: 289 trades, net **-$76, PF 0.997**, Sharpe -0.02 (bar for 'marginal': PF >= 1.03 on >= 40 trades).
Whole OOS span 2023-01..2026-09: 497 trades, -$1,448, PF 0.96. Lucid Monte Carlo on the OOS stream: best size 5 micros, pass rate 0.21,
P(first payout) 0.06, expected net +$78 per evaluation but **bootstrap lower bound -$146** and the zero-edge control (+$95) beats the
strategy -> not recommended. All 24 grid cells (12 combos x MAIN/PRIOR) have exp_net_lb = -$146. The fixed default (west_short) is
+$5,062 / PF 1.11 on MAIN but that is one 2026 outlier day plus a 2026 gold crash tape (details below); PRIOR PF 0.83; 2015-2024 PF 0.91.

## Rules as implemented (all times ET)

Conventions: `c(HH:MM)` = close of the bar with tod HH:MM - 1 min; `i(HH:MM)` = index of the bar with tod HH:MM; an order placed at
`i(T)` is a market order at that bar's open (+1 tick), decided on bars up to T-1. The gold data session runs 18:00 -> 17:00 (bars to 16:59);
the 03:00 entry of session d is inside the session that opened at 18:00 the previous evening.

| leg | side | entry | exit | stop (% of ref) | status |
|---|---|---|---|---|---|
| `west_short` (default) | short | 03:00 | 10:00 | 0.6 | grid |
| `pmfix_fade` | short | fixPM - 30 min | fixPM | 0.4 | grid |
| `ny_long` | long | 10:05 | 16:30 | 0.5 | grid |
| `amfix_fade` | short | fixAM - 30 min | fixAM | 0.4 | implemented, reported by sub-period only |
| `pmfix_momo` | sign(close[fixPM+4] - close[fixPM]) | fixPM + 5 | fixPM + 30 | 0.3 | implemented, 2010-14 vs 2015-26 only |

- `fixAM[d]` / `fixPM[d]` = 10:30 / 15:00 **Europe/London** clock on the session date converted to ET via the two zones' UTC offsets
  (05:30 / 10:00 ET normally; 06:30 / 11:00 ET in the 35 sessions per 2025-26 when US DST is on and UK is not, 04:30 / 09:00 in the
  autumn mismatch). west_short's exit stays at 10:00 ET fixed (the thesis quotes the 10:00 ET minimum in NY time).
- `ref` = close of the bar before the entry bar; `stop_pts = stop_pct x stop_mult / 100 x ref`; `Intents.place(i(entry), side, stop_pts)`.
  stop_pct takes the **leg default** unless leg == west_short and params give stop_pct (so a grid over `leg` keeps each leg's own
  default even when the base params carry 0.6); `stop_mult` scales it.
- Exits: protective stop (level - slip) or `Intents.exit_at(i(exit))` = market at the exit bar's open; `force_flat` from the exit tod to
  session end; global guard: nothing open at or after 16:30. One entry per session (`max_trades_day = 1`), no re-entry after a stop.
- Day filters (entry-time information only): `gap_skip`: skip when |open18[d] - prev_close17[d]| / prev_close17 > 1% (open18 = first bar
  with tod >= 18:00 of the session, prev_close17 = last close with tod < 17:00 of the previous session; 9 of 448 MAIN sessions skipped).
  `winter_only`: trade only when America/New_York is on standard time on the session date (30% of sessions). `skip_macro`: for legs whose
  window contains 08:30 (west_short) the position is **forced flat at the 08:32 open** when `macro0830[d]` fires (08:30-08:31 range >= 3x
  the trailing-60-session median, known at 08:32; 40 MAIN sessions, 29 of them reached 08:32 with an open position). The entry is
  never skipped on it (that would be look-ahead). Missing entry / exit / reference bar -> no trade that day.
- Session: fixed-clock legs `set_session(entry, entry + 1 min, exit)`; fix-anchored legs set `allow_entry` (entry bar only) and
  `force_flat` (from the exit bar) per session. Daily stops moot with one trade per day. ATRg = `daily_atr(df1, 14, rth_only=False)` is
  computed for context only.
- Verified on the trade list: every entry at exactly the leg clock, stop exits at exactly 0.60 / 0.40 / 0.50 / 0.30 % of entry, 08:32
  macro flats present, fix-anchored legs shift by one hour in the DST-mismatch weeks.

Parameters (PARAMS, the published rule): `leg=west_short, stop_pct=0.6, stop_mult=1.0, gap_skip_pct=1.0, winter_only=False, skip_macro=True, max_trades=1`.
GRID (12 combos, used by the walk-forward): `leg {west_short, ny_long, pmfix_fade} x winter_only {False, True} x stop_mult {1.0, 1.5}`.

## Metrics: default (west_short) on MGC

| period | trades | net $ | PF | win | avg trade | Sharpe | max DD intraday | pos months | largest-day share |
|---|---|---|---|---|---|---|---|---|---|
| MAIN 2025-01..2026-09 | 437 | +5,062 | 1.114 | 41.6% | +11.6 | 0.57 | -5,274 | 61.9% | **0.571** (2026-03-03, +$2,889) |
| MAIN ex 2026-03-03 | 436 | +2,173 | 1.049 | | +5.0 | | | | |
| MAIN, 2025 only | 253 | -2,798 | 0.87 | | | | | | |
| MAIN, 2026 only | 184 | +7,937 | 1.35 | | | | | | |
| PRIOR 2023-01..2024-12 | 402 | -3,199 | 0.828 | 45.5% | -8.0 | -1.02 | -5,287 | 29.2% | n/a |
| WF OOS 2023-01..2026-09 | 497 | -1,448 | 0.956 | | | -0.19 | -6,454 | 31.1% | n/a |
| **WF OOS 2025-01..2026-09** | **289** | **-76** | **0.997** | 47.1% | | -0.02 | -6,454 | 42.9% | n/a |

MAIN composition: 283 time exits average +$149, 154 stops average -$241; median trade -$42; top-10 trades = 269% of the net; 16 consecutive
losing trades / 16 consecutive losing days; worst months 2025-01 (-$1,661) and 2025-09 (-$1,803). By weekday: Mon -$2,123, Fri -$705,
Tue-Thu +$2,300-2,800 each (the thesis reports West returns negative Mon/Tue/Thu, positive Fri - our 2025-26 pattern does not match it).
By VIX: all of the profit is in the 15-25 VIX buckets; >25 is negative. Yearly PF 2010-2026 (default): 1.04 1.02 1.19 1.63 0.96 | 1.30 0.91
0.74 0.81 0.74 | 0.76 1.19 0.98 0.98 0.79 | 0.87 1.35 - positive in 2012-2013 and 2015 (the thesis's "2013-2018 net-profitable" window is
really 2012-2015 on our data), losing in 8 of the 10 years 2016-2025. File: `west_short_by_year.csv`.

Lucid Monte Carlo (walk-forward OOS 2025-26 stream, `walkforward.json: lucid_wf_2025`): 5 micros, pass_rate 0.207, pass_within_21 0.195,
p_first_payout_unconditional 0.061, expected_net_per_eval +$78, exp_net_lb **-$146**, zero_edge_exp_net +$95, recommended False.

## Metrics by leg and sub-period (`legs_by_period.csv`; PF / net $ / trades, winter_only=False unless stated)

| leg | 2010-2014 | 2015-2019 | 2020-2024 | 2025-01..2026-09 |
|---|---|---|---|---|
| west_short | 1.16 / +6,187 / 1,279 | 0.90 / -2,833 / 1,285 | 0.91 / -4,488 / 1,170 | 1.11 / +5,062 / 437 |
| west_short winter_only | 1.25 / +3,085 / 441 | 1.03 / +273 / 443 | 1.11 / +1,918 / 428 | 1.32 / +3,876 / 131 |
| pmfix_fade | 1.01 / +216 / 1,283 | 0.83 / -2,106 / 1,285 | 0.91 / -1,921 / 1,170 | 1.03 / +709 / 437 |
| pmfix_fade winter_only | 1.15 / +760 / 441 | 0.85 / -661 / 443 | 1.08 / +570 / 428 | 1.11 / +727 / 131 |
| ny_long | 1.01 / +249 / 1,189 | 0.82 / -4,630 / 1,160 | 0.96 / -1,744 / 1,134 | 0.95 / -1,822 / 422 |
| ny_long winter_only | 1.08 / +842 / 393 | 0.80 / -1,728 / 394 | 0.96 / -559 / 406 | 0.94 / -669 / 124 |
| amfix_fade | 0.96 / -372 / 1,282 | 0.51 / -3,411 / 1,285 | 0.78 / -2,276 / 1,170 | 1.13 / +1,118 / 437 |
| pmfix_momo | 0.72 / -4,846 / 1,275 | 0.57 / -5,035 / 1,277 | 0.82 / -3,393 / 1,168 | 1.05 / +739 / 437 |

- The **fix legs are dead after 2015** exactly as the research predicted (LBMA electronic auction March 2015): amfix_fade PF 0.51 and
  pmfix_momo PF 0.57 in 2015-2019, both still < 0.85 in 2020-2024. pmfix_momo was already negative in 2010-2014 on our 1-min data (the
  Caminschi-Heaney leak is a 4-minute effect inside the bid-ask spread; a $3.30 round trip eats it). Their 2025-26 positives are noise:
  pmfix_fade's largest day is 151% of its net, pmfix_momo's 364% (one day, 2026-01-29, +$2,691).
- **winter_only** is the only switch positive in every sub-period for west_short (PF 1.03-1.32), but with 88 trades/yr, 2015-2019 PF 1.03
  and largest-day shares of 49-99% it is not an edge either; in the quarterly walk-forward it also produces zero-trade OOS quarters whenever
  the trailing IS window picks it before a summer quarter (6 of 15 OOS quarters traded nothing).
- **ny_long on the gold bull tape is a long-bias statement, and in 2025-26 even that fails**: 2025 +$5,629 (244 trades), 2026 -$7,451
  (178 trades), MAIN PF 0.95. Comparison on the same 422 traded sessions (`ny_long_vs_overnight.csv`): buy-and-hold 10:05 -> 16:30 gross
  **-$2,059 (0.16 bp/day)**, the window 03:00 -> 10:05 -$1,613 (-0.2 bp/day), while the **overnight 17:00 -> 03:00 return of the same
  days was +$18,471 (11.6 bp/day)** out of +$12,201 close-to-close. In 2020-2024 the picture is the same (hold 1.4 bp/day vs overnight
  4.9 bp/day). Gold's drift accrues in the Asian hours, not in NY hours (GLD's "5.7% overnight" statistic in the research refers to the US
  cash close-to-open, which includes the whole Asian session - the opposite reading from what the ny_long rationale assumed).

## The clock profile 2020-01..2026-09 (`clock_profile_30min.csv`, `clock_windows_bp.csv`) - the documented filter

Mean XAUUSD close-to-close return per 30-min ET slot (bp), 2020-2026, 1,625-1,736 sessions per slot. The 18:00 slot is the first bar of the
session vs the previous session's 16:59 close (it absorbs the 17:00-18:00 break and the weekend).

| window | 2010-2014 | 2015-2019 | **2020-2026** | 2025-26 |
|---|---|---|---|---|
| Asia 18:00-02:00 | +4.7 bp/day | +5.6 | **+5.7** | +9.1 |
| 02:00-03:00 | -1.0 | -1.4 | +1.4 | +3.0 |
| West 03:00-10:00 (west_short window) | -6.9 | -1.0 | **-0.4** | +0.4 |
| NY 10:00-16:30 (ny_long window) | +3.7 | +0.8 | **+0.7** | +1.1 |
| 16:30-17:00 | +0.7 | -1.5 | **-0.6** | -1.5 |
| overnight 17:00 -> 03:00 | +4.0 | +1.6 | **+7.1** | +12.0 |
| close-to-close | +1.5 | -0.1 | +6.7 | +12.0 |

Slots with |t| >= 2 in 2020-2026: 18:00 (+4.2 bp, t 5.5 - the overnight gap), 02:30 (+0.75, t 2.4), **05:00-05:30 (-0.66, t -2.1; the
pre-AM-fix half-hour)**, **16:30-17:00 (-0.60, t -2.5)**. The 09:30 pre-PM-fix slot is -0.92 bp but t -1.3; 08:30 is +0.98 (macro prints).
The thesis's hat shape survives in the *sign* pattern (Asia up, London/COMEX flat-to-down, NY slightly up) but the daytime amplitude is
0.4-0.7 bp/day against a $3.30 round trip on a ~$4,000 contract (= 0.8 bp): **no daytime window has a drift larger than the cost of
trading it**, which is why every leg is dead regardless of stop or season.

Filter statements for the existing MGC strategies (orb_onmid, tm_gold_donch, mr/orb gold legs):
1. No positive drift exists between 03:00 and 10:00 ET in 2020-2026 (-0.4 bp/day); a long entered in London hours relies entirely on
   its own signal, never on tape drift. The one slot that is reliably negative is 05:00-05:30 ET (pre-AM-fix).
2. Do not hold gold longs into 16:30-17:00 ET (-0.6 bp/day, t -2.5, 45% positive); the 16:30 flat used here is the right one.
3. Gold's 2025-26 bull drift (12 bp/day) accrued 17:00 -> 03:00; a daytime-only gold strategy cannot be "long gold" by holding, only by trading.

## Grid (`grid_MGC.csv`, 12 combos x MAIN / PRIOR, Lucid scan per cell)

MAIN: 8/12 cells positive, median PF 1.04, best net +$5,251 (west_short, stop_mult 1.5); PRIOR: 5/12 positive, median PF 0.98, best +$979
(west_short winter_only, stop_mult 1.5). Rank correlation of cells between the two periods: **-0.12** (no plateau). ny_long: negative in 7 of 8
cells. Every cell: best_micros 5, exp_net_lb -$146, recommended False. stop_mult 1.5 vs 1.0 changes PF by <= 0.07 in every pair (the stop
is rarely the binding exit for the 30-min legs; west_short stops out on 35% of trades at 1.0x and 16% at 1.5x with the same PF).

## Walk-forward (`walkforward.json`, IS 12 months / OOS 3 months from 2022-01, max 16 combos, selection by IS daily Sharpe)

Parameter path: ny_long winter_only (2023 Q1-Q3), west_short (2023 Q4-2024 Q3), ny_long (2024 Q4), pmfix_fade winter (2025 Q1), ny_long
(2025 Q2-2026 Q1), west_short winter (2026 Q2-Q3, zero trades). OOS quarters: +429, 0, 0, -831, -278, 0, 0, -692, -395, **+3,155, +1,451**,
-427, **-3,859**, 0, 0. The two good quarters are the 2025 gold rally captured by ny_long; the same leg then lost -$3,859 in 2026 Q1 when
gold reversed. The walk-forward never finds a stable leg, and the winter_only switch is structurally mis-specified for quarterly OOS blocks.

## What was tried and what failed

- All five thesis legs implemented and run over 2010-2026; the Asian long was deliberately not run (overnight).
- gap_skip (1%) removes 2% of sessions and changes nothing material. skip_macro force-flattens 29 west_short trades at 08:32 in MAIN and
  those 29 trades net +$4,881 (they are the big-print selloff mornings cut before the 08:30 reversal); with skip_macro=False the default is
  +$2,815 / PF 1.06 on the same 437 trades, so the macro flat is worth about +$2.2k on MAIN - a volatility-day artefact, not a thesis effect.
- winter_only improves every leg's PF in every sub-period but on a third of the trades and with single-day concentration; it does not
  rescue the walk-forward. No other filters were added: the clock profile shows there is no drift to filter towards.
- MES/MNQ not run: the rule is a gold-specific clock (London fixes, Asian demand); the family's index windows belong to other modules.

## Files

`final.json` (verdict dead), `walkforward.json`, `wf_oos_2025_daily.csv`, `wf_oos_2025_bars.parquet`, `grid_MGC.csv/.log`, `legs_by_period.csv`,
`west_short_by_year.csv`, `clock_profile_30min.csv`, `clock_windows_bp.csv`, `ny_long_vs_overnight.csv`, `report_MGC_main_west_short.txt`,
`final_MGC_main_*.csv`, `final_MGC_prior_*.csv`, `final_select.log`.
