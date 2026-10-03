# Specs: Calendar, seasonal, time-of-day and structural-flow effects (index futures and gold) for the Lucid 50K LucidFlex backtest

Source report: `/home/user/claude-workspace/research/families/calendar_seasonal_structural.md` (read fully; section numbers below refer to it).
Engine contract: `/home/user/claude-workspace/docs/STRATEGY_GUIDE.md`, `backtest/engine.py` (`Intents.place / set_session / exit_at`, public arrays `allow_entry`, `force_flat`, `max_trades_day`, `daily_loss_stop`, `daily_profit_stop`), helpers in `strategies/common.py` (`daily_atr`, `daily_bars`, `prior_day_stats`, `session_info`, `vix_lag1`, `opening_range`), `backtest.data.resample`, `backtest.run.prepare` (skips thin sessions = holidays/early closes by default).

Family verdict (from the report, and it drives every priority below): **nothing here is a stand-alone Lucid-passing engine.** The calendar edges fire 4-50 days/yr; the clock edges are 2-3 bp/day. The value is (i) a **flags module** every base strategy can consume, (ii) three **overlays** with peer-reviewed evidence that are flat by close and uncorrelated with a morning ORB/mean-reversion leg (pre-FOMC morning long, macro-day last-half-hour momentum, witching-day short), and (iii) a set of **cheap one-line day-window tests** that tell the backtest loop which calendar flags still have an *intraday-only* edge in 2025-26 (most will not; the report expects the edge to be overnight).

## 0. Conventions used by every spec below

Times: all **ET**. Data session 18:00 -> 17:00 (equity CFD feed stops ~16:14; gold feed has bars to 23:59 but Lucid flat-by is 16:45). RTH equities 09:30-16:00; gold pit 08:20-13:30 (gold trades ~23h). A 1-minute bar with `tod = T` covers `[T, T+1)`. "Close at 10:00" = close of the bar with `tod = 09:59`; the decision is taken with that information and the order is placed at the bar with `tod = 10:00` = **market at next open** (+1 tick slippage) unless the spec says stop/limit. **Never execute at the 09:30 print**: every open-of-day entry in this family is at the 09:31 bar or later (report Section 1, Quantpedia GDX warning: 09:30 vs 09:31 cut a 30%/yr result to 8.6%/yr).

Forced flat: equities **15:55** (never later than 15:58); pre-event flats as specified (FOMC 13:55); gold daytime legs flat at the leg's clock exit, never later than 16:30. No overnight, no weekends. One position at a time.

Per-session windows: `Intents.set_session` is global (same window every day). Specs that trade **different windows on different days** (FOMC day vs FOMC-1, lunch reverse, gold legs) set the public arrays directly: `it.allow_entry[i] = True/False` and `it.force_flat[i] = True` for the bars of each session, replicating `set_session` semantics (entries only in `[start, end)`, flat from the first bar `>= flat_time` to session end).

Indicators (exact):
- `ATR14d` = `daily_atr(df1, 14, rth_only=True)` (equities) / `daily_atr(df1, 14, rth_only=False)` (gold): Wilder ATR of daily bars, shifted one day. NaN rows never trade.
- `prev_close[d]` = last 1-min close with `tod < 16:00` of session d-1 (never the 16:14 feed stop). `O930[d]` = open of the 09:30 bar. `pd_high/pd_low` from `prior_day_stats`.
- `D` = `daily_bars(df1, rth_only=True)`; `SMA_D(n)` = `sma(D.close, n).shift(1)`.
- `VIX_lag` = `vix_lag1(df1)`.
- `c(HH:MM)` = close of the 1-min bar whose `tod` = HH:MM minus 1 minute (i.e. the price "at HH:MM"); `i(HH:MM)` = 1-min index of the bar with `tod = HH:MM`.
- `pct_pts(p, px)` = `p/100 * px` = a percentage stop/target converted to points at reference price `px` (the close of the bar before entry).

Lucid risk block (default for every spec unless overridden; all values **per ONE micro contract**, the Lucid Monte Carlo scales 5-40 micros):
- `daily_loss_stop`: MES $60, MNQ $80, MGC $80 (grid multiplier `{1.0, 1.5}`); `daily_profit_stop`: MES $120, MNQ $160, MGC $160 (grid `{1.0, 1.5, none}`). At 10 micros a day is capped at ~$1,200-1,800 (< 50% of the $3,000 target: consistency rule) and a loss day at $600-1,200 (< 60% of the $2,000 MLL distance). Both stops only block NEW entries, so every entry carries a hard protective stop.
- Single-trade-per-day calendar overlays: the daily stops are moot; the hard stop is the risk control, sized so that `stop_pts x point_value x micros <= $600` at 10 micros (MES: 12 pts; MNQ: 30 pts; MGC: 6 pts). Where the published stop is wider (FOMC 0.6-0.8% = 35-45 ES pts) the Monte Carlo will settle at 3-5 micros for that leg; that is expected and acceptable because these are overlays.

Priority: 5 = best prior of working under Lucid constraints with evidence, 1 = long shot. Complexity: 1 = a few lines on existing helpers, 5 = multi-state machine. Evidence quality (EQ) is the report's 1-5 scale.

Controls: every day-window spec includes `window='all_days'` (unconditional long 09:31-15:55) and spec 3 includes `variant='always_long'` (unconditional long 15:30-15:58) as **negative controls**: the report (Sections 1 and 20) says these must come out ~0 / negative; if they come out strongly positive in 2025-26 that is the long-biased tape, not an edge, and every window result must be read relative to the control.

---

## 1. calendar_seasonal_structural__calendar_flags_module  (infrastructure: per-session calendar/event flags from the data + one FOMC table)

Priority **4** (prerequisite for specs 2-12 and consumed as filters by the ORB / mean-reversion / trend families), complexity **2**, instruments all, bar size: daily session list + 1-min bars for the two event detectors. Not a strategy; produces `flags(df1) -> DataFrame indexed by day_id`.

Data gap and the design answer: **the repo has no economic calendar** (`mr_gapfade.py`: "FOMC/CPI calendar is not available"). Everything below is computed from the session list and the 1-min bars, except the FOMC statement dates, which are a short hard-coded table (8/yr, published years ahead by the Fed). CPI/NFP/PPI/GDP days are detected from the 08:30 reaction itself (OHLC-only; measured on the S&P proxy Jun-2024..Sep-2025: 08:30 two-bar range median 3.4 pts, p95 24.6; CPI days 42-62 pts; 3x the rolling-60-session median flags 79/598 sessions = ~33/yr), FOMC-minutes days from the 14:00 reaction (median 3.5, FOMC statement days 15-27 pts). Both detectors are **known before any entry that uses them** (08:32 and 14:02 respectively) - the 14:00 detector may only gate entries at or after 14:02.

```
INPUT df1 (1-min, columns ts, open, high, low, close, session, tod, dow, day_id); S = session dates (one per day_id)
HELPERS
  info = session_info(df1)                       # rth_bars, early_close, dow
  D    = daily_bars(df1, rth_only=True)          # per day_id OHLC of RTH
  nth_weekday(year, month, weekday, n) -> date   # e.g. 3rd Friday
  prev_session(date) / next_session(date): nearest session in S strictly before / after date
  is_session(date): date in S and not info.early_close and rth_bars >= 0.8 * median(rth_bars)
FLAGS (all boolean per day_id unless noted; all use only sessions <= d or fixed calendar arithmetic)
  dow[d]              = weekday of session date (0 = Mon)
  holiday_next[d]     = next weekday calendar date after S[d] is NOT in S (or is a thin session)   # pre-holiday day
  early_close[d]      = info.early_close
  totm[d]             = S[d] is the last session of its calendar month (T-1) OR one of the first 3 sessions of a month (T+1..T+3)
  totm_pos[d]         = -1 for T-1, +1/+2/+3, else 0;  precash[d] = S[d] is T-4, T-3 or T-2 of its month (sessions from the end)
  payday[d]           = S[d] is the first session with day-of-month >= 15, or the session after it
  opex[d]             = S[d] == 3rd Friday of the month, or the Thursday before it when that Friday is not a session (Good Friday)
  witching[d]         = opex[d] and month in {3, 6, 9, 12}
  pre_witch5[d]       = S[d] is one of the 5 sessions before a witching day
  opex_week[d]        = S[d] is Mon..Thu of the calendar week whose Friday (or Thursday) is opex
  vix_exp[d]          = S[d] == the Wednesday 30 calendar days before next month's 3rd Friday (if not a session: the session before);  vix_exp_eve[d] = next_session(S[d]) is vix_exp
  santa[d]            = S[d] is one of the last 5 sessions of December or the first 2 sessions of January
  qend[d]             = S[d] is T-3, T-2 or T-1 of March/June/September/December
  qtd_ret[d]          = D.close at session T-5 of that quarter / D.close at the last session of the prior quarter - 1   (float; NaN unless qend[d])
  weak_close[d]       = ((C-L)/(H-L) of RTH day d-1) < 0.2 AND (H-L)/C of day d-1 > 1.5%
  month_rank_long[d]  = calendar month of S[d] is in the top 6 of trailing-10-year same-month mean returns of the instrument's daily parquet (ES_1d/NQ_1d/GC_1d), computed with years < year(S[d]) only (Keloharju filter, Section 17)
  fomc[d]             = S[d] in FOMC_STATEMENT_DATES (table below);  fomc_minus1[d] = next_session(S[d]) is fomc
  fomc_stmt_tod[d]    = 14:00 for S[d] >= 2013-01-01; for 2011-2012: 12:30 on press-conference meetings (Apr/Jun/Nov 2011; Jan/Apr/Jun/Sep/Dec 2012), else 14:15; 2010: 14:15
  r0830[d]            = max(high of bars tod 08:30, 08:31) - min(low of those bars)      # NaN if either bar missing
  rel0830[d]          = r0830[d] / median(r0830[d-60..d-1])     (min_periods 60)
  macro0830[d]        = rel0830[d] >= k0830    (k0830 default 3.0)                       # known at 08:32
  r1400[d], rel1400[d] likewise on bars tod 14:00, 14:01;  macro1400[d] = rel1400[d] >= k1400 (default 3.0)   # known at 14:02 - afternoon use only
  fomc_minutes[d]     = macro1400[d] and not fomc[d]     (approximation: minutes are the dominant scheduled 14:00 release; also catches unscheduled 14:00 shocks)
  macro_day[d]        = macro0830[d] or fomc[d]                                            # usable from 09:30
  exp_range_mult[d]   = 1.15 if (opex[d] or witching[d]) else 1.0                          # Section 11 amplification; filter for other families
FOMC_STATEMENT_DATES (second day of each scheduled meeting; VERIFY against federalreserve.gov before the final run - from memory, 2010-2026):
  2010: 01-27 03-16 04-28 06-23 08-10 09-21 11-03 12-14
  2011: 01-26 03-15 04-27 06-22 08-09 09-21 11-02 12-13
  2012: 01-25 03-13 04-25 06-20 08-01 09-13 10-24 12-12
  2013: 01-30 03-20 05-01 06-19 07-31 09-18 10-30 12-18
  2014: 01-29 03-19 04-30 06-18 07-30 09-17 10-29 12-17
  2015: 01-28 03-18 04-29 06-17 07-29 09-17 10-28 12-16
  2016: 01-27 03-16 04-27 06-15 07-27 09-21 11-02 12-14
  2017: 02-01 03-15 05-03 06-14 07-26 09-20 11-01 12-13
  2018: 01-31 03-21 05-02 06-13 08-01 09-26 11-08 12-19
  2019: 01-30 03-20 05-01 06-19 07-31 09-18 10-30 12-11
  2020: 01-29 04-29 06-10 07-29 09-16 11-05 12-16   (March 2020: emergency cuts 03-03 and 03-15 replaced the scheduled 03-18 meeting - exclude March 2020)
  2021: 01-27 03-17 04-28 06-16 07-28 09-22 11-03 12-15
  2022: 01-26 03-16 05-04 06-15 07-27 09-21 11-02 12-14
  2023: 02-01 03-22 05-03 06-14 07-26 09-20 11-01 12-13
  2024: 01-31 03-20 05-01 06-12 07-31 09-18 11-07 12-18
  2025: 01-29 03-19 05-07 06-18 07-30 09-17 10-29 12-10
  2026: 01-28 03-18 04-29 06-17 07-29 09-16 10-28 12-09
  press_conference[d] = True for all meetings >= 2019 (every meeting), for 2011-2018 the Mar/Jun/Sep/Dec meetings only (+ Apr 2011, Nov 2011 as listed above); FOMC spec default trades press-conference meetings only.
SELF-CHECK (run once, assert): count(fomc) == 8 per full year (7 in 2020); count(witching) == 4/yr; count(opex) == 12/yr; count(macro0830) in [20, 45]/yr; count(holiday_next) in [7, 11]/yr; the four 2025 FOMC dates listed in the data check (01-29, 03-19, 06-18, 09-17) all have rel1400 > 3.
```
Grid: none (module). Tunables exposed to the consuming specs: `k0830 {3.0, 4.0}`, `k1400 {3.0}`, `median_lookback 60`.

Session rules: n/a. Risk: n/a. Data gap: FOMC table is from memory (verify); CPI/NFP/GDP identity is approximated by the 08:30 reaction size (an event-agnostic "macro morning" flag - it also catches PPI/retail sales/big claims days, which is fine for the momentum use but means the flag is a *volatility* flag, not a calendar flag); holidays are inferred from missing/thin sessions (a feed gap looks like a holiday - acceptable); VIX expiration rule ignores the rare Thursday-settlement cases.

## 2. calendar_seasonal_structural__pre_fomc_morning_drift  (Lucca-Moench morning leg: long 09:31 -> 13:55 on scheduled FOMC statement days)

Priority **4**, complexity **1**, instruments MES (published on SPX/E-mini), MNQ secondary; bar size 1-min. EQ 4 (NY Fed SR 512 / JF 2015: +49 bp 2pm-2pm, 98/131 positive, Sharpe 1.14, drift concentrated in the announcement-day morning, zero after 14:00; Applied Economics 2025: survives for press-conference meetings; OOS 2011-15 +26 bp n.s.). Only 8 trades/yr (~14 in the prime window), so this is an overlay: it adds a well-defined +$150 day roughly half the time and is flat through the announcement.

```
PARAMS: entry_time='09:31', exit_time='13:55', stop_pct=0.7, stop_mode='pct' | 'atr', stop_atr=1.0, press_conf_only=True,
  prior_day_leg=False, prior_entry='13:00', prior_flat='15:55', vix_min=0 (0 = no gate), target_pct=0 (0 = none), max_trades=1
PRE: F = flags(df1); atr = ATR14d
  trade_day[d] = F.fomc[d] and (not press_conf_only or F.press_conference[d]) and (vix_min == 0 or VIX_lag[d] >= vix_min)
  exit_tod[d]  = min(exit_time, F.fomc_stmt_tod[d] - 5 min)          # 13:55 for 2013+, 12:25 / 14:10 for 2010-2012 meetings
ENTRY (announcement day): i = i(entry_time) of session d where trade_day[d]
  ref = close of bar i-1
  stop_pts = pct_pts(stop_pct, ref) if stop_mode=='pct' else stop_atr * atr[d]
  tgt_pts  = pct_pts(target_pct, ref) if target_pct > 0 else NaN
  place(i, +1, stop_pts=stop_pts, tgt_pts=tgt_pts)
  allow_entry: only bar i (entry window [entry_time, entry_time+1min)); force_flat from exit_tod[d] to session end  (no re-entry after the stop; nothing held into 14:00)
OPTIONAL prior-day leg (prior_day_leg=True): on sessions where F.fomc_minus1[d]: place(i(prior_entry), +1, stop_pts as above); force_flat from prior_flat.
  (Paper: "rises slightly on the afternoon before"; close-two-days-prior-to-2pm +54 bp vs +49 bp => the extra day adds ~5 bp; expect it to fail after costs.)
EXIT: hard stop; optional target; forced flat at exit_tod (market at the open of the first bar >= exit_tod).
SESSION/RISK: max_trades_day 1; per-session windows set via allow_entry/force_flat arrays (two different windows on d-1 and d); Lucid block (moot: one trade). Stop 0.7% ES = ~45 pts = $225/MES => Monte Carlo will size 3-5 micros; keep it, do not shrink the stop below 0.5% (the drift is noisy intraday).
```
Grid (<= 24): `stop_pct {0.5, 0.8}` x `stop_mode {pct, atr}` (atr: `stop_atr {0.7, 1.2}`) x `press_conf_only {True, False}` x `prior_day_leg {False, True}` x `exit_time {13:55, 12:30}` (12:30 tests whether the drift is front-loaded). Fixed: entry 09:31, vix_min 0 (one extra run with `vix_min=20`).

Evidence recap / expectation: a 20-35 bp morning capture at ES ~6,000 is 12-21 pts = $60-105 per MES per event; 14 events in the prime window; a 2025-26 result of +$600-1,200 per MES with 8-10 winners would confirm; anything with < 55% winners is noise at n=14 - report with the 2013-2024 count (96 events) as the real test.

## 3. calendar_seasonal_structural__macro_day_last_half_hour  (Gao-Han-Li-Zhou intraday momentum, gated or sized by the macro-day flags)

Priority **4**, complexity **2**, instruments MES, MNQ; bar size 1-min (30-min quantities computed from 1-min closes). EQ 4 for the base effect (JFE 2018: Sharpe 1.08, 54% success; r1+r12 agreement 77% success; weakened post-2020), EQ 3 for the macro-day amplification (R2 2.6% -> 5.5% on CPI/GDP days, 11% on FOMC-minutes days; gains ~3x on CPI, ~4x on minutes days). This spec **extends `trend_momentum__last_half_hour` / `strategies/intraday_momentum.py`** with the thing that spec called a data gap: the macro-day gate. Implement as new parameters on that module or as a thin wrapper; do not duplicate the mechanics.

```
PARAMS: ref='prev_close' | 'open' | 'pre0830', variant='r1' | 'r1_r12' | 'always_long' (control), entry_time='15:30', flat='15:58',
  days='all' | 'macro_only' | 'non_macro' | 'fomc_minutes_only', thresh_atr=0.0, stop_atr=0.4, skip_witching=True, max_trades=1
PRE: F = flags(df1); atr = ATR14d
  c1000 = c(10:00); c1500 = c(15:00); c1530 = c(15:30); c0830 = c(08:30) (close of bar tod 08:29, i.e. before the release)
  ref_px = prev_close[d] (paper) | O930[d] | c0830
  r1  = c1000 / ref_px - 1;   r12 = c1530 / c1500 - 1
  day_ok[d] = (days=='all') or (days=='macro_only' and F.macro_day[d]) or (days=='non_macro' and not F.macro_day[d])
              or (days=='fomc_minutes_only' and F.macro1400[d])            # macro1400 is known at 14:02 < 15:30: no look-ahead
  if skip_witching and F.witching[d]: day_ok = False
  sig = sign(r1) if |c1000 - ref_px| >= thresh_atr * atr[d] else 0
  if variant=='r1_r12': sig = sig if sign(r12) == sign(r1) else 0
  if variant=='always_long': sig = +1
ENTRY: if day_ok and sig != 0: place(i(entry_time), sig, stop_pts = stop_atr * atr[d])     # market at the 15:30 open
EXIT: forced flat at `flat` (15:58; 29-min hold); protective stop only, no target.
SESSION/RISK: set_session(entry_time, entry_time+1min, flat); max_trades_day 1; Lucid block moot.
SIZING-UP ON MACRO DAYS (the paper's "size 1.5-2x on release days") is done at the PORTFOLIO level, not inside the engine:
  leg A = this spec with days='all' at m micros; leg B = same with days='macro_only' at m micros  =>  macro days run 2m, other days m.
  (backtest.portfolio / portfolio_opt accept both legs on the same contract; entry windows coincide but the engine treats legs independently - this is the documented way to size by day type.)
```
Grid (<= 48): `ref {prev_close, open, pre0830}` x `variant {r1, r1_r12}` x `days {all, macro_only, non_macro}` x `stop_atr {0.3, 0.6}` + two control runs (`variant=always_long, days=all` and `days=fomc_minutes_only`). `thresh_atr` fixed 0 (the paper uses the sign only); one extra run with 0.2.

Expectation: ~2.6 bp/day = ~$8/MES/day on all days (not a passer); on macro days 3-4x that with ~33 + 8 days/yr. The informative output is the contrast `macro_only` vs `non_macro`: if the macro-only leg has PF >= 1.3 on 2025-26 AND 2015-2024, it becomes the afternoon leg B of the portfolio. Note for the Lucid MC: a 29-minute 10-MES position has intraday sigma ~$300, so leg B at 10 micros cannot breach the MLL on its own.

## 4. calendar_seasonal_structural__witching_day_short  (short NQ/ES open-to-close on quad-witching Fridays; monthly-OPEX variant for sample size)

Priority **2**, complexity **1**, instruments MNQ (Nasdaq 67% negative, strongest), MES (57%); bar size 1-min. EQ 3 (Caporale-Plastun 2000-2021 significant in 7/7 tests for d(0); Seasonax; Schaeffer's: triple-witching weeks <30% positive since 2021) but **n = 4/yr** (7 in the prime window): statistically this spec can only be judged on 2010-2026 (~66 events) and used at small size; it is in the file because it is the family's best-evidenced *short* and the only reason to ever short the 2025-26 tape on a calendar.

```
PARAMS: days='witching' | 'opex' (all 12 monthly expirations) | 'opex_week_fri_control' (the Friday after OPEX, control), entry_time='09:31' | '14:00',
  stop_pct=1.0 (MNQ) / 0.7 (MES), target_pct=0 (none) | 0.5, flat='15:55', max_trades=1
PRE: F = flags(df1)
  trade_day[d] = F.witching[d] if days=='witching' else F.opex[d] if days=='opex' else (dow==4 and F.opex_week[prev week])
ENTRY: i = i(entry_time); ref = close of bar i-1
  place(i, -1, stop_pts = pct_pts(stop_pct, ref), tgt_pts = pct_pts(target_pct, ref) if target_pct > 0 else NaN)
  entry_time='14:00' variant: SpotGamma "sharp moves after 2 PM as ITM contracts are exercised" - tests whether the weakness is an afternoon phenomenon
EXIT: stop / target / forced flat 15:55.
SESSION/RISK: set_session(entry_time, entry_time+1min, flat); max_trades_day 1. Hard stop 1.0% NQ ~ 200 pts = $400/MNQ => MC sizes 1-3 micros; that is the point - this is a 1-2 micro overlay.
```
Grid (<= 16): `days {witching, opex}` x `entry_time {09:31, 14:00}` x `stop_pct {0.7, 1.2}` x `target_pct {0, 0.5}`. Plus one control run `days=opex_week_fri_control`.

Expectation: the daily-close statistic includes the overnight gap; the intraday-only capture is unknown. Accept only if 2010-2026 win rate >= 58% with PF >= 1.3 AND 2025-26 is not negative; otherwise demote to a *filter* (`no_longs_on_witching=True` for the ORB family), which is the report's minimum recommendation.

## 5. calendar_seasonal_structural__expiration_afternoon_break  (expiration-day range amplification: break of the 13:00-14:00 range after 14:00, stop entries)

Priority **2**, complexity **2**, instruments MES, MNQ; bar size 1-min (range built from 1-min bars). EQ 3 for the amplification (Elms 2016-2025: ~16% wider ranges on high near-expiry-OI days; no pinning), EQ 1-2 for this specific trade (report Section 10d/11: "prefer breakout logic after 14:00 on expiration days"). The `days='all'` control is essential: if the breakout works on every day it is a generic afternoon-breakout strategy, not a calendar effect.

```
PARAMS: days='expiration' (opex or witching) | 'witching' | 'all' (control), range_start='13:00', range_end='14:00', buffer_ticks=2,
  valid_minutes=90, stop_mode='opposite' | 'half', target_rr=0 (none; run to flat) | 1.5, flat='15:55', max_trades=2 (one per side)
PRE: F = flags(df1); for each session d with day_ok[d]:
  RH = max(high), RL = min(low) over bars with range_start <= tod < range_end;  W = RH - RL;  i0 = i(range_end)
  skip if W < 0.15 * ATR14d[d] (too tight to be a range) or W > 1.0 * ATR14d[d] (already trending)
ENTRY (bracket, resolved on 1-min data as strategies/orb.py does): at i0 place
  long  stop order at RH + buffer_ticks*tick, valid_bars = valid_minutes
  short stop order at RL - buffer_ticks*tick, valid_bars = valid_minutes
  one position at a time: whichever side triggers first on the 1-min path cancels the other (orb.py pattern)
STOP: 'opposite' = other side of the range (RL for long, RH for short); 'half' = range midpoint
TARGET: target_rr * (entry - stop) if target_rr > 0, else none (ride to 15:55 - the amplification thesis is a range-extension thesis)
RE-ENTRY: after a stop-out, the opposite-side stop order may be re-placed once (max_trades 2); no re-entry on the same side.
EXIT: forced flat 15:55.
SESSION/RISK: set_session('14:00', '15:30', flat); max_trades_day 2; Lucid block 1.0x (two possible losses of ~W each; W ~ 0.3-0.5 ATR ~ 15-25 ES pts).
```
Grid (<= 36): `days {expiration, witching, all}` x `stop_mode {opposite, half}` x `target_rr {0, 1.5}` x `buffer_ticks {1, 4}` + `range_start {12:30, 13:00}` on the best combo only.

Expectation: 16 expiration days/yr; the test is `expiration` vs `all` PF and average range extension after 14:00. Keep only if expiration PF exceeds the all-days PF by >= 0.3 on 2016-2026 (the Elms sample); otherwise the only surviving output is the `exp_range_mult = 1.15` filter for other families.

## 6. calendar_seasonal_structural__turnaround_tuesday  (long Tuesday 09:31 -> 15:55 after Friday-down AND Monday-down)

Priority **2**, complexity **1**, instruments MES (SPY evidence), MNQ; bar size 1-min with daily signals. EQ 2 (TradeQuantix SPY 1993-2026: +0.33% on qualifying Tuesdays vs -0.03% otherwise; FRL 2024 says the Monday reversal is an afternoon phenomenon; part of the +0.33% accrues Mon->Tue overnight and is not capturable).

```
PARAMS: entry_time='09:31' | '12:00', exit_time='15:55', mon_thresh=0.0 (Monday return <= -mon_thresh %, 0 = any down day), require_fri_down=True,
  stop_mode='atr', stop_atr=1.0, target_atr=0 (none), flat='15:55', max_trades=1
PRE: D = daily_bars(rth_only=True) with RTH closes; F = flags(df1)
  ret[d] = D.close[d] / D.close[d-1] - 1   (RTH close to RTH close; never the 16:14 bar)
  Tuesday session d (dow==1) qualifies if: session d-1 is a Monday (dow==0; skip Tuesdays after a Monday holiday) AND ret[d-1] <= -mon_thresh/100
       AND (not require_fri_down or (session d-2 is a Friday and ret[d-2] < 0))
  (all of ret[d-1], ret[d-2] use closes of sessions < d: no look-ahead)
ENTRY: i = i(entry_time); place(i, +1, stop_pts = stop_atr * ATR14d[d], tgt_pts = target_atr * ATR14d[d] if target_atr > 0 else NaN)
EXIT: stop / target / forced flat at exit_time.
SESSION/RISK: set_session(entry_time, entry_time+1min, flat); max_trades_day 1; stop 1.0 ATR (~60 ES pts in 2025 = $300/MES) => MC sizes 2-4 micros; alternatively stop_atr 0.5.
```
Grid (<= 24): `entry_time {09:31, 12:00}` x `mon_thresh {0.0, 0.5}` x `require_fri_down {True, False}` x `stop_atr {0.5, 1.0}` + `target_atr {0, 1.0}` on the best combo.

Expectation: ~8-12 trades/yr (`require_fri_down=True`), ~20 with it off. Judge on 2010-2026 (150-300 trades); a 2025-26 result alone is ~15 trades. Keep as a *long-bias filter* (`tt_day[d]`) for the mean-reversion family unless stand-alone PF >= 1.4 on 2010-2026.

## 7. calendar_seasonal_structural__calendar_window_long  (one module, one day-window parameter: intraday-only test of every "long this day" calendar effect, with controls)

Priority **2**, complexity **2**, instruments MES (all published evidence is S&P), MNQ; bar size 1-min. EQ 4 for the close-to-close effects (TOTM, OPEX week), 2-3 for the rest, **1-2 for any intraday-only version** (report Section 21: "effects that are real close-to-close but die when forced into a flat-by-close implementation"; Atlanta Fed: TOTM in S&P futures dead after 1990). The purpose of this spec is to settle, in one batch run, which calendar flags have an intraday-only edge in 2025-26 and in 2010-2024, so that the base-strategy families can use them as filters with evidence rather than lore.

```
PARAMS: window (see table), side='auto' (per window default) | +1 | -1, entry_time='09:31', exit_time='15:55' | '12:00',
  stop_atr=0.75, target_atr=0 (none), trend_filter=False (SMA_D(200) > close[d-1] required for longs), flat='15:55', max_trades=1
WINDOW TABLE (flag from flags(df1); default side):
  'totm'          F.totm           +1     (T-1, T+1..T+3; ~48 days/yr)
  'payday'        F.payday         +1     (15th/16th; 24/yr)
  'precash'       F.precash        -1     (T-4..T-2 dash-for-cash short bias; 36/yr; unverified)
  'pre_witch5'    F.pre_witch5     +1     (5 days before quad witching; 20/yr)
  'opex_week'     F.opex_week      +1     (Mon-Thu of monthly expiration week; 48/yr)
  'pre_holiday'   F.holiday_next   +1     (~9/yr; early-close eves are skipped by run.prepare's thin-session filter unless skip_thin_sessions=False; on those use entry 09:31, exit 12:55)
  'santa'         F.santa          +1     (7/yr; failed 2024-25)
  'vix_exp_eve'   F.vix_exp_eve    +1     (12/yr; indirect)
  'qtr_rebal'     F.qend           sign = -1 if F.qtd_ret[d] > +0.05, +1 if < -0.05, else no trade; entry_time forced to '13:00' (afternoon pension flow lore)
  'dow_tuewed'    dow in {1, 2}    +1     (weekday tilt; 100/yr; control-like)
  'month_rank'    F.month_rank_long +1    (Keloharju filter; ~125/yr; control-like)
  'all_days'      True             +1     (CONTROL: unconditional long 09:31-15:55; the report says ~0)
PRE: F = flags(df1); atr = ATR14d
  day_ok[d] = window flag[d] and (not trend_filter or D.close[d-1] > SMA_D(200)[d])
  side[d] = per table unless overridden
ENTRY: i = i(entry_time) (or 13:00 for qtr_rebal); place(i, side[d], stop_pts = stop_atr*atr[d], tgt_pts = target_atr*atr[d] or NaN)
EXIT: stop / target / forced flat at exit_time (exit_at the first bar >= exit_time; force_flat at 15:55 regardless).
SESSION/RISK: set_session(entry_time, entry_time+1min, flat); max_trades_day 1; Lucid block moot (one trade); stop 0.75 ATR => MC 3-5 micros.
REPORT: for each window, the table must show (a) the window's per-day mean and t-stat vs the 'all_days' control's on the same period, 2025-26 and 2010-2024, (b) the overnight component (prev_close -> O930 on the same days) so the "edge is overnight" hypothesis is tested directly.
```
Grid (<= 48): `window {12 values}` x `exit_time {12:00, 15:55}` x `stop_atr {0.5, 1.0}`; `trend_filter` on for `totm` and `all_days` only (4 extra runs). `side` fixed per table.

Expectation: most windows will not beat the control intraday; the report's prediction is that `totm`, `opex_week`, `santa`, `pre_holiday` edges are overnight. Any window with mean-minus-control >= +8 bp/day (t >= 2 on 2010-2024) and positive in 2025-26 becomes a `+1` bias flag for the ORB / mean-reversion legs; `precash` and `qtr_rebal` likewise on the short side.

## 8. calendar_seasonal_structural__lunch_effect  (short 11:00-12:00, long 12:00-14:00; or long-only 12:00-14:00)

Priority **2**, complexity **1**, instruments MES (SPY evidence 2010-2024), MNQ; bar size 1-min. EQ 2 (single Quantpedia vendor backtest, long-only 12:00-14:00 leg ~5.17%/yr at 8.03% vol, no OOS, period-dependent). Structurally ideal (daily, flat by 14:00, never overlaps the 15:30 leg, overlaps a morning ORB only if the ORB is still holding at 11:00) but ~2 bp/day.

```
PARAMS: variant='long_only' | 'short_then_long' | 'short_only', short_start='11:00', reverse_time='12:00', long_exit='14:00', stop_pct=0.4,
  stop_mode='pct' | 'atr', stop_atr=0.4, skip_macro=True (skip F.macro_day and F.fomc sessions), skip_opex=False, max_trades=2
PRE: F = flags(df1); atr = ATR14d; day_ok[d] = not (skip_macro and (F.macro_day[d] or F.fomc[d])) and not (skip_opex and F.opex[d])
ENTRY per session d with day_ok:
  variant 'short_only' / 'short_then_long': i_s = i(short_start); place(i_s, -1, stop_pts = pct_pts(stop_pct, c(short_start)) or stop_atr*atr[d])
       exit_at(i(reverse_time))                                            # market exit at the 12:00 open
  variant 'long_only' / 'short_then_long': i_l = i(reverse_time) + (1 if variant=='short_then_long' else 0)   # one position at a time: the long goes in one bar after the short exits
       place(i_l, +1, stop_pts as above);  exit_at(i(long_exit))
  (if the short's protective stop fired before 12:00 the long still enters at 12:00/12:01)
EXIT: stop or clock exit; force_flat from long_exit (14:00) to session end so nothing can remain after 14:00; set_session(short_start, reverse_time + 2min, long_exit).
SESSION/RISK: max_trades_day 2; daily_loss_stop 1.0x block (two clock trades/day can both lose on a trend day); daily_profit_stop none (small edge, no monster days).
```
Grid (<= 24): `variant {long_only, short_then_long}` x `stop_mode {pct, atr}` (`stop_pct {0.3, 0.5}` / `stop_atr {0.3, 0.6}`) x `long_exit {13:30, 14:00}` x `skip_macro {True, False}`.

Expectation: average ~$5-10/MES/day gross; costs are $1.30 + 2 ticks ($2.50) per round trip = ~$4, so the net is marginal. Accept only with PF >= 1.2 on 2015-2026 and positive 2025-26; its realistic role is a midday consistency filler at 10-20 micros in the funded phase (where many >= $150 days matter), never an eval passer.

## 9. calendar_seasonal_structural__gold_clock_legs  (gold round-the-clock "hat shape": western-hours short, pre-fix fades, post-PM-fix momentum, NY-hours long)

Priority **2**, complexity **2**, instruments MGC (GC proxy XAUUSD, 1-min, 18:00 -> 23:59 bars available); bar size 1-min. EQ 3 for the shape (CBS thesis GC 5-min 2001-2018), 2 for post-2015 persistence (2017-18 negative for every leg net of spreads; net-of-spread profitable only 2013-2018), 1 for the fix-leak leg (electronic auction since March 2015). All daytime legs are Lucid-compatible (flat long before 16:45). MGC costs ($1.30 + 2 x $1 slippage = $3.30/RT on a $10/pt contract) are large relative to a few-bp edge: this family on gold is marginal by construction and the grid is deliberately tiny.

```
PARAMS: leg (one of the table below), stop_pct per leg, gap_skip_pct=1.0 (skip the day if |open 18:00 of the session vs prior 16:59 close| > 1%),
  winter_only=False (trade only when US standard time is in force: Nov..Mar, the thesis's strong half), skip_macro=True (skip F.macro0830 days for legs that straddle 08:30), max_trades=1
LEG TABLE (ET clock; entry = market at the open of the entry bar; exit = exit_at the open of the exit bar; stop = pct of entry price):
  'west_short'     side -1  entry 03:00  exit 10:00   stop 0.6    (London open to PM fix; thesis "Short 02:00-11:00" simplified to the 03:00-10:00 core)
  'amfix_fade'     side -1  entry 05:00  exit 05:30   stop 0.4    (30 min before the 10:30 London AM auction; -3.7 pp cumulative)
  'pmfix_fade'     side -1  entry 09:30  exit 10:00   stop 0.4    (30 min before the 15:00 London PM auction; -4.2 pp)
  'pmfix_momo'     side = sign(c(10:04) - c(10:00))  entry 10:04  exit 10:30  stop 0.3   (Caminschi-Heaney leak; expected dead post-2015: run 2010-2014 vs 2015-2026 separately)
  'ny_long'        side +1  entry 10:05  exit 16:30   stop 0.5    (rising leg of the U; GLD: gold's drift is in NY hours)
  'asia_long'      side +1  entry 18:00  exit 02:00   stop 0.5    *** DECISION FLAG: this is the strongest leg in the thesis (12.3%/yr gross to 02:30) but it is an evening/overnight Globex hold. Lucid permits it (flat only by 16:45 next day) and the engine supports it (set_session handles start > end) but it violates this project's no-overnight convention. Implement behind leg='asia_long' and do NOT run it unless the orchestrator explicitly enables overnight gold. ***
PRE: F = flags(df1) (gold session calendar; macro0830 computed on XAUUSD's own 08:30 bars); px_ref = close of the bar before entry
  dst[d] = America/New_York is on daylight time on session date d (from ts.utcoffset()); day_ok[d] = (not winter_only or not dst[d]) and gap filter and macro filter
  NOTE the London fixes are at 10:30/15:00 London time: 05:30/10:00 ET except during the 2-3 weeks per year when UK and US DST differ (then 04:30/09:00 or 06:30/11:00 ET). Compute fix_tod[d] from Europe/London vs America/New_York offsets on date d and shift the amfix/pmfix windows accordingly.
ENTRY: place(i(entry_tod), side, stop_pts = pct_pts(stop_pct, px_ref)); for 'pmfix_momo' side needs c(10:04) so the order goes at i(10:04) using closes of bars <= 10:03.
EXIT: exit_at(i(exit_tod)); force_flat from exit_tod; set_session(entry_tod, entry_tod+1min, exit_tod).
SESSION/RISK: max_trades_day 1; gold ATR for context: daily_atr(rth_only=False). Stop 0.6% of $3,700 = $22 = $220/MGC => MC sizes 2-4 micros for west_short; the fix fades at 0.4% likewise.
```
Grid (<= 20): `leg {west_short, amfix_fade, pmfix_fade, ny_long, pmfix_momo}` x `winter_only {False, True}` x `stop_pct {leg default, 1.5x default}`. Periods: 2010-2014, 2015-2019, 2020-2024, 2025-26 reported separately (the thesis shows strong sub-period dependence).

Expectation: the honest prior is that `amfix_fade`/`pmfix_fade`/`pmfix_momo` are pre-2015 phenomena and `west_short` was net-positive only 2013-18; `ny_long` is the only leg with a plausible 2025-26 tailwind (gold's bull run) and even that is a long-bias statement, not an edge. Keep any leg only with PF >= 1.3 on 2020-2026 after costs; otherwise record the clock profile (mean return by 30-min slot, 2020-2026) as a filter input for the gold ORB/mean-reversion legs (e.g. "no gold longs 03:00-10:00 ET").

## 10. calendar_seasonal_structural__large_gap_fade  (fade >= 0.7% ES / >= 1% NQ opening gaps toward a 50% fill; weekday and weak-close filters)

Priority **2**, complexity **1**, instruments MNQ (stronger: QQQ gap-up open-to-close -0.5%), MES; bar size 1-min. EQ 2 (Shareplanner 5-yr SPY/QQQ: gap-up >= 1% -> -0.2%/-0.5% open-to-close; gap-down +0.21%/+0.1%; Monday gap-ups fade ~60%; 1-2% gaps fill same day 45-47%). **This is a parameterisation of the existing `strategies/mr_gapfade.py`** (which tests 0.10-0.50% gaps toward a full fill): implement by extending that module's parameters, not a new module, so the two gap regimes are compared in one report.

```
PARAMS (mr_gapfade extension): gap_min=0.7 (MES) / 1.0 (MNQ), gap_max=3.0, fill_frac=0.5, stop_mult=0.5, entry_delay=1 (09:31 bar), sides='both' | 'short' (gap-ups only; the stronger side),
  exit_time='15:55', dow_filter='none' | 'mon_gapup_only' | 'skip_wedthu', weak_close_bias=False, vix_gate=False, outside_atr=99 (no gap-and-go skip: large gaps are the point), max_trades=1
PRE: gap = (O930 - prev_close)/prev_close; F = flags(df1); as in mr_gapfade (prior_close = last close with tod < 16:00; never 16:14)
  qualify[d] = gap_min <= |gap| <= gap_max and side allowed and dow filter:
     'mon_gapup_only': only gap-ups on Monday (dow 0) (and gap-downs any day if sides=='both'); 'skip_wedthu': no trades on dow 2,3 (gaps continue mid-week per the source)
  weak_close_bias: if F.weak_close[d] (prior day closed in the bottom 20% of a > 1.5% range) allow longs only (gap-down fades), skip gap-up shorts
ENTRY: market at the open of the 09:30 + entry_delay bar (09:31); skip if the gap already filled to fill_frac in the bars before entry
STOP: O930 -/+ stop_mult * |gap_pts| (beyond the open, away from the fill); TARGET: O930 + fill_frac * (prev_close - O930)
EXIT: target / stop / exit_at(exit_time) / force_flat 15:55.
SESSION/RISK: set_session('09:31', '09:32', '15:55'); max_trades_day 1; stop 0.5 x gap = 0.35-0.5% ES ~ 20-30 pts = $100-150/MES => MC sizes 4-6 micros; Lucid block 1.0x.
```
Grid (<= 32): `gap_min {0.7, 1.0}` x `fill_frac {0.5, 0.75}` x `stop_mult {0.5, 1.0}` x `sides {both, short}` x `dow_filter {none, skip_wedthu}`; `weak_close_bias` one extra run.

Expectation: ~15-20% of sessions have >= 1% gaps on NQ (more in 2025's April tariff shock); 2025-26 provides ~50-80 trades on MNQ. The shock days (April 2025) dominate: report with and without the top-3 days (consistency rule: one $1,500 day at 10 micros is 50% of the target).

## 11. calendar_seasonal_structural__fomc_post_announcement_fade  (fade the 14:00-14:10 statement move on FOMC days; 14:30 press-conference variant)

Priority **1**, complexity **2**, instruments MES, MNQ; bar size 1-min. EQ 1 (practitioner lore; the only hard number is Lucca-Moench: average 14:00-to-close return on FOMC days = 0, i.e. no drift either way). Included because it is cheap, codeable and the engine's big-bar handling on 14:00 prints is real (guide: "big single bars exist on FOMC prints; they are real"), but it is micro-size only: one wrong trade at 4 minis can breach the MLL.

```
PARAMS: window='stmt' (measure 13:59 -> 14:10, enter 14:10) | 'presser' (measure 14:29 -> 14:45, enter 14:45), min_move_pct=0.35 (MES) / 0.5 (MNQ),
  min_move_mode='pct' | 'rel' (|M| >= rel_k x median 10-min range of the prior 10 sessions at 14:00-14:10, rel_k=1.5), retrace=0.5, stop_mult=1.25,
  time_exit='14:29' (stmt) | '15:55' (presser), max_trades=1
PRE: F = flags(df1); only sessions with F.fomc[d] and F.fomc_stmt_tod[d] == 14:00 (2013+; the 2010-2012 12:30/14:15 statements use the same offsets from fomc_stmt_tod)
  'stmt':    M = c(14:10) - c(13:59)... precisely: M = close of bar tod 14:09 - close of bar tod 13:59;  ext = max high (M>0) / min low (M<0) over bars tod 14:00..14:09
  'presser': M = close of bar tod 14:44 - close of bar tod 14:29;  ext over 14:30..14:44
  trigger = |M| / c(13:59) >= min_move_pct/100  (or the 'rel' rule)
ENTRY: i = i(14:10) (or i(14:45)); side = -sign(M); place(i, side, tgt_px = c(13:59) + 0.5*M  [i.e. 50% retrace of M], stop_px = ext +/- (stop_mult - 1) * |M| beyond the extreme)
   (limit-style target: engine fills targets only when traded through by one tick; stop is a protective stop filled at level - slip)
EXIT: target / stop / exit_at(time_exit) (stmt variant is flat before the 14:30 presser; presser variant flat 15:55).
SESSION/RISK: entries allowed only at the single entry bar (allow_entry array); force_flat from time_exit; max_trades_day 1; stop = 1.25 x M ~ 0.45% ES ~ 27 pts = $135/MES => MC sizes <= 4 micros; the Lucid MC should additionally cap this leg at 4 micros (hard rule in the portfolio config, not a grid value).
```
Grid (<= 16): `window {stmt, presser}` x `min_move_pct {0.25, 0.4}` x `retrace {0.5, 0.75}` x `stop_mult {1.25, 1.75}`.

Expectation: 8/yr, ~14 in the prime window, ~110 on 2013-2026. A coin flip is the base case; keep only if 2013-2026 PF >= 1.5 with >= 60% winners (n ~ 60 triggered events); otherwise drop and keep the filter "no entries 13:55-14:35 on FOMC days" (already implied by spec 2's exit and recommended for every other family).

## 12. calendar_seasonal_structural__macro_0830_spike_fade  (pre-RTH fade of an outsized 08:30 release spike, 50% retrace, flat by 09:25)

Priority **1**, complexity **2**, instruments MES, MNQ; bar size 1-min, **pre-RTH (08:33-09:25)**. EQ 1 (Bookmap/FundedFast "wait 15 minutes, fade the retail spike": anecdote). Lucid allows pre-RTH trading; the engine allows entries at any `tod`. Pre-market liquidity on MES/MNQ at 08:30 is thin and the data is a CFD proxy, so the backtest must run with **2 ticks slippage** (`engine.run(..., slip_ticks=2)`) and the result discounted further.

```
PARAMS: measure_minutes=3 (08:30..08:32 bars), min_move_pct=0.4 (MES) / 0.6 (MNQ), retrace=0.5, stop_mult=0.5 (protective stop placed stop_mult x |M| beyond the spike extreme), entry_time='08:33',
  time_exit='09:25', require_macro_flag=True (F.macro0830[d], known at 08:32), max_trades=1
PRE: F = flags(df1); c0829 = close of bar tod 08:29; M = close of bar tod (08:30 + measure_minutes - 1) - c0829; ext = max high / min low over the measure bars
  trigger[d] = require_macro_flag -> F.macro0830[d]; and |M| / c0829 >= min_move_pct/100
ENTRY: i = i(entry_time); side = -sign(M); place(i, side, tgt_px = c0829 + (1 - retrace) * M, stop_px = ext + sign(M) * stop_mult * |M|)
EXIT: target / stop / exit_at(time_exit) (always flat before the 09:30 open so this leg never collides with a morning ORB leg on the same contract).
SESSION/RISK: set_session('08:33', '08:34', '09:25'); max_trades_day 1; stop ~0.6% ES ~ 36 pts = $180/MES => MC sizes 2-3 micros; cap this leg at 4 micros in the portfolio config.
```
Grid (<= 16): `min_move_pct {0.3, 0.5}` x `retrace {0.5, 0.75}` x `stop_mult {0.5, 1.0}` x `measure_minutes {3, 5}`.

Expectation: ~20-35 triggers/yr. The honest prior is negative after 2-tick slippage; this spec exists to close the question. The informative by-product is the distribution of (08:30-08:33 move) vs (08:33-09:25 move) on macro days, which also validates the `macro0830` detector for spec 3.

---

## Dropped or folded (and why)

| Report section / strategy | Decision |
|---|---|
| 1. Overnight-only index drift (close -> next open) | Not codeable under the rules (overnight hold). Recorded as the family's **prior**: unconditional intraday long holds have ~zero expectation (SPY 90.6% of 1993-2024 gain overnight). Enforced via the `all_days` and `always_long` controls in specs 7 and 3. |
| 2. Weekday overnight seasonality | Overnight legs dropped. The intraday weekday tilt is `window='dow_tuewed'` in spec 7 and the `dow` flag in spec 1. |
| 4. TOTM / payday, 10b/c. pre-witching long and OPEX-week tilt, 12. VIX-expiration eve, 14. pre-holiday, 15. Santa, 16. month-end / quarter-end flows, 17. Keloharju month filter | All folded into spec 7 (`window` parameter) so that twelve weak "long this day" claims are tested by one module against one control, and into spec 1 as flags. None gets a stand-alone module: 7-48 days/yr each, evidence is close-to-close, intraday-only persistence unproven (Atlanta Fed: TOTM in S&P futures dead after 1990; Santa failed 2024-25). |
| 7a. Macro-day momentum carry-over | Spec 3 (`days='macro_only'`); 7c spike fade is spec 12; 7b large-gap fade is spec 10 (extension of `mr_gapfade`). |
| 8. Intraday momentum (base) | Already specced as `trend_momentum__last_half_hour`; spec 3 adds only the macro-day gate/sizing and the `pre0830` reference. Do not implement twice. |
| 11. 0DTE / expiration amplification | No directional edge; it is the `exp_range_mult = 1.15` flag in spec 1 (filter for other families: widen stops/targets, prefer breakouts, no fades after 14:00 on expiration days) and the trade test in spec 5. A true gamma filter needs options OI / dealer gamma - **data gap, not available**. |
| 13. MOC imbalance / closing-auction drift | **Dropped**: needs the NYSE/Nasdaq imbalance feed (published 15:50), which we do not have; the only OHLC proxy ("15:30-15:50 direction continues") is the r12 signal already inside `trend_momentum__last_half_hour` (Sharpe 0.29 in the paper, i.e. weak). Not faithful enough to approximate. The calendar part (larger closing moves on month/quarter-end, Russell reconstitution, witching) survives as the `qend`/`witching` flags = "wider stops or flat into the close" for other families. |
| 18e. Gold Asian-hours long (18:00-02:00 ET) | Implemented behind `leg='asia_long'` in spec 9 but **not run by default**: it is an evening/overnight Globex hold; Lucid permits it (flat by 16:45 next day) but the project convention forbids overnight. Decision flag for the orchestrator. |
| 18c. Gold post-PM-fix leak | Kept as `leg='pmfix_momo'` in spec 9 for a 2010-2014 vs 2015-2026 split only; the LBMA electronic auction (March 2015) is expected to have killed it. |
| 20. Unconditional last-30-minutes long | Negative result; coded only as the `always_long` control in spec 3 (expected ~0 / negative; validates the engine against a published number). |

## Portfolio notes for the backtest agents

- Build spec 1 first; it unblocks the "FOMC/CPI calendar not available" gaps in `mr_gapfade.py` and `trend_momentum__last_half_hour`. Run its self-check (8 FOMC days/yr, 4 witching, 12 OPEX, 20-45 macro mornings/yr) before anything else and verify the FOMC table against federalreserve.gov.
- Overlay order of merit from the evidence: spec 3 (`macro_only` leg) > spec 2 > spec 4 > spec 10 > everything else. Specs 5-9 and 11-12 are one-batch-run questions: run the grid once on 2010-2024 and 2025-26, keep what beats its control, demote the rest to flags.
- Stacking: spec 2 (09:31-13:55 on 8 days) collides with a morning ORB leg on the same contract on FOMC days - run spec 2 on MES and the ORB on MNQ, or give the ORB a `skip_fomc` flag. Spec 3 (15:30-15:58), spec 8 (11:00-14:00), spec 12 (08:33-09:25) never overlap a 09:30-11:30 morning leg. Spec 11 (14:10-15:55 on FOMC days) overlaps spec 3 on 8 days: give spec 3 `skip_fomc=True` if both are kept.
- Consistency rule arithmetic for calendar overlays: a single FOMC-day or gap-fade winner at 10 micros can be $800-1,500 = up to 50% of the target. Keep the overlay legs at 3-5 micros in the eval configuration and let the daily base strategy supply the target; in the funded phase (no consistency rule) they can be sized up to feed the "5 days >= $150" requirement.
- Never report a spec on 2025-26 alone when it fires < 50 times there; the 2010-2024 count is the test and 2025-26 is the sign check.
