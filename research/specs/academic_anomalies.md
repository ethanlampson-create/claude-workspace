# Specs: Academic / Quantpedia-style anomalies (equity-index and gold futures) for the Lucid 50K LucidFlex backtest

Source report: `/home/user/claude-workspace/research/families/academic_anomalies.md` (24 sections, 22 strategies, read in full; report date 2026-10-03 19:30, this spec file supersedes the 17:21 version written against the earlier draft).
Engine contract: `/home/user/claude-workspace/docs/STRATEGY_GUIDE.md`, `backtest/engine.py` (`Intents.place / exit_at / set_session`, `max_trades_day`, `daily_loss_stop`, `daily_profit_stop`; one position and one pending order at a time; one contract per run, sizing in the Lucid Monte Carlo), helpers in `strategies/common.py` (`opening_range`, `overnight_range`, `daily_atr`, `daily_bars`, `prior_day_stats`, `session_vwap` (TWAP proxy), `sma`, `ema`, `atr`, `rsi`, `vix_lag1`, `session_info`), `backtest.data.resample(df1, N, rth_only=True)` (gives `i_next`).

What this family contributes (report section 24): the index **last-30-minute momentum** (Baltussen-Da-Lammers-Martens, JFE 2021) is the best-documented futures intraday effect and the only one here with a 55-61% hit rate, one trade per day and a 25-minute hold, i.e. exactly the daily-P&L shape Lucid's consistency rule and 5-green-day payout gate reward. The **ES gap-fill** (Nova SBE thesis, 1-min ES 2000-2021, 73.6% win long side) is its natural low-VIX, morning, mean-reversion complement. Everything else is either a regime switch (VIX gate), a rare-event overlay (FOMC reversal, 8/yr), a gold leg (two of them), or a trend-day capture that already lives in another family (noise-area momentum, 5-min ORB) and is re-parameterised here with the academic defaults and the Lucid caps. Calendar anomalies (ToM, payday, OpEx week, Turnaround Tuesday, pre-FOMC drift) are overnight effects; they are folded into one `long_bias[d]` flag (spec 9) instead of being traded.

Cross-family overlaps (never run the same rule twice under two ids; where a module exists, add parameters to it instead of writing a new one):
- `academic_anomalies__rod_last30_momentum` (spec 1) is the canonical JFE rule: prior **close** -> 15:30 move, no threshold, optional first-half-hour sign agreement. `strategies/intraday_momentum.py` (`trend_momentum__last_half_hour`, ref='close', thresh=0) already computes the signal; add `agree_fh`, `regime`, `direction`. `evidence_and_failures__close_momentum_vixgate` (signal 'to1530', vix gate) is the same rule run as a negative control; run the batch once and report it under both ids. The previous version of this file called it `academic_anomalies__last_half_hour_hedging`; that id is retired.
- `academic_anomalies__noise_area_vixgate` (spec 4) is a parameter set for the `trend_momentum__noise_area` / `bot_popular_indicators__noise_area_1m_bands` module (paper defaults + band-only stop + VIX / realized-vol gate + long-only). Do not write a third band module.
- `academic_anomalies__gap_fill_thesis` (spec 3) is NOT `intraday_mean_reversion__gap_fade_small` (`mr_gapfade.py`): limit entry beyond the open, target at the prior-day high/low with a tight dollar cap, dollar stop, 5-day SMA trend filter, no Mon/Fri, 2-day-range gap filter, both setups A/B. Different enough to be its own module; reuse `mr_gapfade`'s PDC/O930 definitions.
- `academic_anomalies__orb5_capped_target` (spec 5) differs from every `orb_session__*` spec: the entry is the **direction of the first 5-minute bar at 09:35** (not a range breakout), stop floored at 0.1 ATR, R-multiple target.
- `academic_anomalies__fomc_post_reversal_1400` (spec 7) trades the sign of the **24-hour pre-announcement return**; `calendar_seasonal_structural__fomc_post_announcement_fade` fades the 14:00-14:10 print. Both need the FOMC table from `calendar_seasonal_structural__calendar_flags_module` (`F.fomc`, `F.fomc_stmt_tod`).
- `academic_anomalies__gold_western_short_conditional` (spec 8) extends `calendar_seasonal_structural__gold_clock_legs` leg `west_short` (03:00-10:00, unconditional) with the thesis window 02:00-11:00 and the overnight-rally condition the report recommends; the unconditional cell of the grid is the control and equals the calendar spec's leg.
- Overnight-return cross-sectional reversal: use `intraday_mean_reversion__onrev_cross_sectional` (`mr_onrev.py`) with `universe='eq'`; see the folded section for the hedged-pair note.
- Witching-day short, pre-FOMC morning long, day-only calendar windows: `calendar_seasonal_structural__witching_day_short`, `__pre_fomc_morning_drift`, `__calendar_window_long` already cover them; not duplicated.

## 0. Conventions used by every spec below

Times: all **ET**. Data session 18:00 -> ~16:14 ET next day for `SPXUSD`/`NSXUSD` (the CFD feed stops ~16:14), 18:00 -> 17:00 for `XAUUSD`. RTH equities 09:30-16:00; gold pit 08:20-13:30 (gold trades ~23h). A 1-minute bar with `tod = T` covers `[T, T+1)`. "Close at 15:30" means the close of the bar with `tod = 15:29`; the decision is taken with that information and the order is placed at the bar with `tod = 15:30`, i.e. **market at next open (+1 tick slippage)** unless the spec says `kind='stop'` or `kind='limit'`. On N-minute bars (`resample`) the decision uses the N-bar close and the order index is `i_next` (skip `-1`). `i(T)` below = index of the 1-min bar of session d with `tod = T`; `c(T)` = close of the bar with `tod = T-1` (i.e. the price known at T).

Forced flat: equities **15:55** (never later than 15:58); gold pit variants 13:25; gold full-session variants 16:30 (never later than 16:45). No overnight, no weekend. Early-close sessions (`session_info().early_close`, RTH last bar before 15:30) are skipped by every afternoon spec.

Indicators (exact definitions):
- `D = daily_bars(df1, rth_only=True, rth=(contract.rth_open, contract.rth_close))`; `O930[d] = D.open` (open of the 09:30 bar); `PC[d] = D.close.shift(1)` = **prior RTH close = last 1-min close with tod < 16:00 of the previous session** (never the 16:14 bar); `PDH/PDL = prior_day_stats()` prior RTH high/low; `PDO[d]` = prior RTH open.
- `ATR14d = daily_atr(df1, 14, rth_only=True, rth=...)`: Wilder ATR of RTH daily bars, shifted one day (day d uses days < d). Gold full-session specs use `rth_only=False`. NaN rows never trade.
- `RV14[d]` = std of the 14 prior RTH close-to-close returns (`min_periods=14`); `RV14_pts = RV14 * PC`. `RV_med252[d]` = rolling 252-session median of RV14, shifted.
- `SMA_D(n)[d]` = `sma(D.close, n).shift(1)` (uses closes of sessions < d). `R5[d]` = `max(D.high[d-5..d-1]) - min(D.low[d-5..d-1])`; `R2[d]` likewise over 2 sessions.
- `TWAP` = `session_vwap(rth_bars)` = cumulative mean of (H+L+C)/3 from 09:30. **Approximation of VWAP** (no volume); flagged wherever used.
- `VIX_lag[d] = vix_lag1(df1)` (prior-day VIX close). `F = flags(df1)` = the calendar module of the calendar family (`fomc`, `fomc_stmt_tod`, `press_conference`, `witching`, `opex`, `early_close`, `dow`).
- `REG = regime(df1)` = spec 9's per-session table (`vix_q`, `mom_size`, `meanrev_on`, `trend100`, `long_bias`).
- `R` = |entry - initial stop| in points; `$R = R x point_value` (MES $5/pt, MNQ $2/pt, MGC $10/pt). Reference levels for sizing arithmetic: ES ~6,800 (ATR14d ~55-70 pts), NQ ~25,000 (ATR ~300-400), gold ~4,250 (full-session ATR ~55-70 $/oz; pit-hours ATR ~30-40).

Lucid risk block (default for every spec unless overridden; all values **per ONE micro contract**; the Lucid Monte Carlo scales 5-40 micros):
- `daily_loss_stop` (no new entries once realized day P&L <= -X): MES $60, MNQ $80, MGC $80. Grid multiplier `{1.0, 1.5}`. At 10 micros = $600-$1,200 = <= 60% of the $2,000 MLL distance; one bad day cannot breach an EOD-trailing MLL that started the day >= $1,200 above the floor.
- `daily_profit_stop` (no new entries once realized day P&L >= Y): MES $120, MNQ $160, MGC $160. Grid multiplier `{1.0, 1.5, none}`. At 10 micros this caps a day at ~$1,200-$1,800 so no single day exceeds 50% of the $3,000 target (eval consistency rule) and a funded cycle collects many >= $150 days.
- Both stops only block NEW entries; an open position runs to its own stop/target/flat, so **a hard protective stop is mandatory on every entry**. For one-trade-per-day specs the daily stops are inert and the per-trade stop IS the daily loss cap: size it so `stop_pts x point_value x micros <= $600` at the Monte Carlo's chosen size.
- One position at a time; `max_trades_day` as specified; always `set_session(entry_start, entry_end, flat)`. Specs with different windows on different days set `it.allow_entry[i]` / `it.force_flat[i]` directly (the calendar family's convention).

Priority 5 = best prior of working under Lucid constraints with evidence, 1 = long shot. Complexity 1 = a few lines on existing helpers, 5 = multi-state intraday machine. EQ = the report's evidence quality (1-5).

Benchmark every equity spec must beat on 2025-01..2026-09: `trend_momentum__benchmark_long_0945` (buy 09:45, flat 15:55). Gold specs: buy 08:20, flat 13:25 (and buy 18:00, flat 16:30 as the bull-market reference, reported only).

---

## 1. academic_anomalies__rod_last30_momentum  (Baltussen-Da-Lammers-Martens JFE 2021: rest-of-day sign -> last 30 minutes; eta(rROD) and eta(rONFH, rROD))

Priority **5**, complexity **1**, instruments MES, MNQ (run both; the paper's equity-index panel includes ES and NQ), bar size 1-min (signals from 1-min closes). EQ **5** (JFE 2021, 60+ futures 1974-2020, equity 1/N Sharpe 1.73 gross, success 55%; with sign agreement Sharpe 1.60, success 61%; beta_ROD larger in 2000-2020 than 1974-1999; positive net Sharpe on ES at 1-tick cost; mechanism = gamma hedging). Caveats the backtest must settle: no published 2022-2026 ES test; the weaker Gao first-half-hour-only variant is negative OOS (this spec uses it only as the agreement filter, never as the signal); the local check in `evidence_and_failures` found ~0 correlation to-15:30 -> last-30 since 2024.

Data gap: none for the base rule. Net-gamma conditioning (options data) is not available; `regime='vix'` stands in for high-vol / negative-gamma days. FOMC-minutes days (4x profit in Gao et al.) can only be flagged after 14:02 via `F.fomc_minutes` (14:00 reaction size); that is before the 15:30 entry, so `days='minutes_only'` is a legal diagnostic.

```
PARAMS (defaults = paper): entry_time='15:30', ref='prev_close', agree_fh=False, min_abs_ret=0.0, stop_atr=0.3,
  flat='15:55', regime='none' ('none' | 'vix' | 'rv' | 'mom_size'), vix_min=18, direction='both' ('both' | 'long_only' | 'bias'),
  days='all' ('all' | 'minutes_only' | 'no_fomc'), max_trades=1
PRE (per session d; skip if F.early_close[d], ATR14d NaN, or PC NaN):
  ref_px[d] = PC[d] if ref=='prev_close' else O930[d]                      # paper: prior close (overnight + RTH to 15:30)
  c1530[d]  = c(15:30) = close of the bar with tod 15:29
  c1000[d]  = c(10:00) = close of the bar with tod 09:59
  rROD[d]   = c1530 / ref_px - 1;   rONFH[d] = c1000 / PC[d] - 1            # rONFH always vs prior close (paper)
  sig[d]    = sign(rROD) if |rROD| >= min_abs_ret else 0
  if agree_fh and sign(rONFH) != sig: sig = 0                               # eta(rONFH, rROD): trade only on agreement
  if regime=='vix'      and VIX_lag[d] < vix_min: sig = 0
  if regime=='rv'       and RV14[d] <= RV_med252[d]: sig = 0
  if regime=='mom_size' and REG.mom_size[d] == 0: sig = 0                   # spec 9 table (0 / 0.5 / 1; 0.5 is applied by the portfolio tool, not here)
  if direction=='long_only' and sig < 0: sig = 0
  if direction=='bias': sig = 0 if (sig < 0 and REG.long_bias[d]) else sig  # calendar long-bias days: no shorts
  if days=='minutes_only' and not F.fomc_minutes[d]: sig = 0;  if days=='no_fomc' and F.fomc[d]: sig = 0
ENTRY: if sig != 0: place(i(entry_time), sig, stop_pts = stop_atr * ATR14d[d])      # market at the open of the 15:30 bar
EXIT: hard stop (checked every 1-min bar) or forced flat at the open of the first bar >= flat. No target (the paper holds to 16:00;
  the last 5 minutes are given up for prop safety; one diagnostic run with flat='15:58' shows what the MOC print is worth).
SESSION: set_session(entry_time, entry_time + 1 min, flat); max_trades_day = 1; Lucid block inert (one trade); the hard stop is the daily cap.
```
Grid (32 combos): `ref {prev_close, open}` x `agree_fh {False, True}` x `min_abs_ret {0.0, 0.002}` x `stop_atr {0.25, 0.5}` x `regime {none, vix}` (vix_min fixed 18). Fixed direction both, days all. Extra single runs (not gridded): `direction=long_only`, `direction=bias`, `regime=rv`, `days=minutes_only`, `flat='15:58'`, `vix_min=25`.

Session rules: one entry at 15:30, flat 15:55, skip early-close days (no 15:30 bar) and sessions with a missing prior RTH close.
Risk rules: 25-minute hold; stop 0.25-0.5 ATR (ES 15-30 pts = $75-150/MES; NQ 90-180 pts = $180-360/MNQ) is a disaster stop, rarely hit in 25 minutes; typical last-30 move 0.15-0.25% (ES 10-17 pts = $50-85/MES). Expected gross edge 2.7 bp/day on notional (~$9/day/MES, ~$13/day/MNQ) with daily SD ~25 bp (~$85/MES): at 10 micros, mean ~$90/day, SD ~$850/day, 55% green days. It needs 15-20 micros or a second leg (spec 3) to reach $3,000 inside a typical 2-3-month eval, and the Monte Carlo must confirm that a 20-micro $1,700 daily SD does not breach the $2,000 EOD trail (expect the scan to settle at 10-15). Cost sensitivity is the main risk: $1.30 + 2 x $1.25 slippage = $3.80/RT on MES vs ~$9 gross/day.

Evidence recap: Table 6 of the JFE paper (equity eta(rROD) 6.86%/yr, SD 3.96%, Sharpe 1.73, 55%; eta(rONFH,rROD) 5.47%, Sharpe 1.60, 61%; always-long last 30 min 0.44%, Sharpe 0.11 -> the sign is the edge, not the window); Gao et al. SPY 1993-2013 Sharpe 1.08 and 4x on FOMC-minutes days; negative OOS only for the first-half-hour-only rule (QuantConnect 2015-2020 Sharpe -0.63, Marwood 2010-2018 -1.37%/yr).

Acceptance: PF >= 1.3 and positive-day share >= 52% on 2025-26 at base costs AND PF >= 1.1 on 2023-24 AND the `min_abs_ret` / `stop_atr` cells form a plateau. If the ungated paper rule fails but `regime=vix` passes, report the gate as the result (it is what the mechanism predicts), not as a tuned parameter.

## 2. academic_anomalies__rod_last30_momentum_gold  (commodity leg of the JFE rule on MGC: pit-session rest-of-day sign -> 13:00-13:25; flagged Globex-close variant)

Priority **3**, complexity **1**, instruments MGC; bar size 1-min. EQ **4** (same JFE paper, commodity 1/N eta(rROD) 4.34%/yr, Sharpe 1.42, success 56%; 2000-2020 commodity beta_ROD 1.04, t 2.86, i.e. weaker than equities; gold-specific coefficient not extracted; the pit-close hedging deadline is weaker in the electronic era, so the modern-session variant is a standard interpretation, untested).

Data gap: none. The paper's gold "day" is pit hours 08:20-13:30, which the contract spec (`rth_open='08:20', rth_close='13:30'`) already encodes.

```
PARAMS: session='pit' ('pit' | 'globex'), agree_fh=False, min_abs_ret=0.0, stop_atr=0.2, direction='both', max_trades=1
WINDOWS: 'pit':    ref_px = close of the bar tod 13:29 of the prior session (pit close); entry 13:00; flat 13:25; FH window 08:20-08:50 (c(08:50) vs ref)
         'globex': ref_px = close of the bar tod 16:59 of the prior session (Globex close); entry 16:15; flat 16:45;
                   FH window = first 30 min of the session (18:00-18:30 of the same data session, c(18:30) vs ref)      # flagged: untested interpretation
PRE (per session d; ATR_g = daily_atr(rth_only=(session=='pit'), rth=('08:20','13:30'))):
  rROD = c(entry) / ref_px - 1;  rONFH = c(FH end) / ref_px - 1
  sig = sign(rROD) if |rROD| >= min_abs_ret else 0;  if agree_fh and sign(rONFH) != sig: sig = 0
  if direction=='long_only' and sig < 0: sig = 0
ENTRY: place(i(entry), sig, stop_pts = stop_atr * ATR_g[d])            # market at the open of the entry bar
EXIT: hard stop or forced flat (13:25 pit / 16:45 globex). No target.
SESSION: set_session(entry, entry + 1 min, flat); max_trades_day = 1; skip F.fomc days for 'pit' only if the 14:00 statement is outside the window (it is), so no skip needed; skip sessions where the ref bar is missing.
```
Grid (16): `session {pit, globex}` x `agree_fh {False, True}` x `min_abs_ret {0.0, 0.0015}` x `stop_atr {0.15, 0.3}`. Fixed direction both (one `long_only` run: the 2019-2026 bull market makes a long-only cell look good for the wrong reason, so report it but do not select it).

Session rules: one entry at 13:00 (pit) or 16:15 (globex); flat 13:25 / 16:45.
Risk rules: 25-minute hold; stop 0.15-0.3 x pit ATR (~5-12 $/oz = $50-120/MGC); the typical 25-minute gold move is 0.1-0.2% (~4-8 $/oz = $40-80/MGC). Daily stops inert. Independent of the ES/NQ leg by construction (different hours): a diversifier in the portfolio optimizer, not an eval engine on its own.

Evidence recap: commodity panel Sharpe 1.42 gross 1974-2020; the "always long last 30 min" commodity control is negative (-0.68%/yr), so the gold bull drift does not explain a positive result in the pit variant.

Acceptance: as spec 1; additionally the `pit` and `globex` cells should agree in sign on 2015-2026, otherwise the pit-close mechanism is dead and only the untested variant "works" (reject).

## 3. academic_anomalies__gap_fill_thesis  (Trequattrini / Nova SBE 2022 ES gap fill: limit entry beyond the open, prior-day high/low target with dollar cap, dollar stop, 5-day SMA filter, no Mon/Fri)

Priority **4**, complexity **3**, instruments MES (published on ES), MNQ (fill statistics also reported for NQ); bar size 1-min. EQ **2** (single student thesis, parameters optimised in-sample with a comb-shaped OOS validation; long side 73.6% win, Sharpe 1.05 on $50k, Calmar 3.12, max DD -$3,400/contract combined; underlying fill statistics 62-65% same-day agree with independent sources). The dollar parameters were set on 2000-2021 ES levels (1,000-4,500); at ES 6,800 a $250 target is 0.07%, so the default parameterisation is **ATR-scaled** with the literal dollar rule kept as a check run.

Data gap: none. The thesis used the cash session: gap = `O930 - PC` with PC the 16:00 close (not the 16:14 CFD bar, not the 17:00 futures settle).

```
PARAMS: mode='atr' ('atr' | 'dollar'), enter_off_atr=0.03 (0 = at the open), tgt_atr=0.2, stop_atr=0.4, range_stop_mult=0.5,
  gap_max_r2=0.2, sma_len=5, skip_dow={0, 4} (Mon, Fri), body_min=0.0 (optional prior-day |body|/range >= 0.2),
  last_entry='11:00', flat='15:55', sides='long' ('long' | 'short' | 'both'), max_trades=1
  'dollar' mode (literal thesis, ES points): enter_off 2 pts; long: target cap 5 pts ($250/ES), stop cap 10 pts ($500/ES); short: 13 / 13 pts ($650/$650)
PRE (per session d; uses only sessions < d plus O930[d]):
  gap = O930 - PC;  up_prev = D.close[d-1] > PDO[d]  (prior day closed up)
  long_setup  = gap < 0 and ((up_prev and O930 > PDL) or (not up_prev))            # setup A needs the open inside the prior range; setup B any gap down
  short_setup = gap > 0 and (((not up_prev) and O930 < PDH) or up_prev)
  common = ATR14d notna and |gap| < gap_max_r2 * R2[d] and dow[d] not in skip_dow and (body_min == 0 or |D.close[d-1]-PDO| >= body_min*(PDH-PDL))
  long_ok  = long_setup  and common and O930 > SMA_D(sma_len)[d]              # "price above the 5-day SMA" taken at the open (known at 09:30)
  short_ok = short_setup and common and O930 < SMA_D(sma_len)[d]
  side = +1 if long_ok and sides in {long, both} else -1 if short_ok and sides in {short, both} else 0
LEVELS (long; short mirrored):
  entry_px = O930 - enter_off_atr * ATR14d                              # buy limit below the open (thesis: Open - 2 pts); 0 -> limit at the open
  stop_dist = min(range_stop_mult * R5[d], stop_atr * ATR14d)           # thesis: 0.5 x 5-day range, capped by the $500 monetary stop
  tgt_px    = min(PDH, entry_px + tgt_atr * ATR14d)                     # thesis: prior-day high, capped by the $250 monetary target
  skip if tgt_px <= entry_px + 2 ticks (prior high already too close) or stop_dist < 2 ticks
ENTRY: place(i(09:30), side, entry_px, kind='limit', valid_bars = minutes from 09:30 to last_entry, stop_px = entry_px - side*stop_dist, tgt_px)
  (engine: limit fills only when price trades through the level by one tick, no slippage; a day where the dip never prints = no trade)
EXIT: target / protective stop / forced flat 15:55 (thesis: session end).
SESSION: set_session('09:30', last_entry, flat); max_trades_day = 1; daily_loss_stop = stop_dist_median x point_value (one stop-out ends the day; inert with one trade).
```
Grid (32): `sides {long, both}` x `tgt_atr {0.15, 0.25}` x `stop_atr {0.3, 0.5}` x `last_entry {11:00, 15:00}` x `enter_off_atr {0, 0.05}`. Fixed: mode atr, range_stop_mult 0.5, gap_max_r2 0.2, sma_len 5, skip Mon/Fri. Check runs: `mode=dollar` (literal), `skip_dow={}` (is the Mon/Fri exclusion real?), `body_min=0.2`.

Session rules: limit order live 09:30 -> last_entry; flat 15:55; no Monday/Friday (thesis); skip sessions with NaN ATR / SMA.
Risk rules: the thesis shape is **win-rate heavy with a stop 2x the target** (73.6% / $250 vs $500): with tgt 0.2 ATR (~12 ES pts = $60/MES) and stop 0.4 ATR (~24 pts = $120/MES) a 20-micro day loses at most ~$2,400 -> the Monte Carlo will size 5-10 micros; a 10-micro winner (~$600) clears the $150 payout-day bar and stays under 50% of the target. Expected per trade at 1 MES: 0.74 x 60 - 0.26 x 120 - 1.30 ~ +$12 (ATR mode) vs the thesis's $73/ES = $7.3/MES. Trades on ~30-40% of sessions (gap down, Tue-Thu, above SMA, small gap) -> ~80-100 trades/yr on the long side; stackable with spec 1 (afternoon) and spec 4 (which only trades after 10:00 and in high VIX).

Evidence recap: fill 62.5% (gap up) / 65.3% (gap down) same day, 84% for 0.25-0.5% gaps; long system Sharpe 1.05, win 73.6%, avg $73; short Sharpe 1.01, PF 1.5, max open DD -$3,550; combined Sharpe 2.0, Calmar 2.47; profits rising 2017-2021; August the only negative month.

Acceptance: win rate >= 65% with PF >= 1.3 on 2025-26 (n >= 60 long trades) and PF >= 1.1 on 2023-24; the `tgt_atr x stop_atr` block must be a plateau. The `dollar` check run is expected to fail at 2025 price levels (targets inside the noise) - that is informative, not a reason to retune.

## 4. academic_anomalies__noise_area_vixgate  (Zarattini-Aziz-Barbon noise-area momentum, paper defaults, band-only stop, VIX / realized-vol gate; parameter set for the existing band module)

Priority **3**, complexity **3** (1 if the `trend_momentum__noise_area` module exposes `regime`, `stop_mode`, `long_only`), instruments MES, MNQ; bar size 1-min with decisions every 30 min. EQ **4** (SSRN 4824172: SPY 2007-2024 Sharpe 1.33 with VWAP stop + vol targeting, 0.61 band-only; codecat-ops replication on SPY and ES 2020-2026 Sharpe 1.11 / +2 bp per ES trade; **Sharpe ~0 in 2025-26 on both**; walk-forward reselection makes it worse). The test this id exists for: does the published VIX-at-open conditioning (Sharpe ~1.5 baseline -> ~3.5 at VIX > 40, in-sample) rescue 2025-26, or does the codecat finding ("no relation between daily PnL and VIX in 2020-2026") hold?

Data gap: the paper's VWAP trailing stop needs volume. `stop_mode='opp_band'` is the paper's volume-free base variant (Sharpe 0.61 vs 1.24; this is the honest cost of no volume). `stop_mode='own_band_twap'` substitutes the TWAP of (H+L+C)/3 - flagged approximation; report both. Vol targeting (2% daily, 4x cap) cannot run inside the engine (1 contract); spec 9's `size_mult` applies it in the portfolio tool.

```
PARAMS (defaults = paper): lookback=14, vm=1.0, step=30, first_decision='10:00', last_decision='15:30', stop_mode='opp_band',
  hard_stop_atr=0.5, regime='vix' ('none' | 'vix' | 'rv' | 'vix_q4'), vix_min=20, long_only=False, flat='15:55', max_trades=6,
  daily_profit_mult=1.5
PRE (per session d, RTH 1-min bars): move[d,t] = |close(t) / O930[d] - 1| for every RTH tod t
  sigma[d,t] = mean over sessions d-1..d-lookback of move[., t] (min_periods = lookback; NaN -> no trade)
  upper[d,t] = max(O930[d], PC[d]) * (1 + vm*sigma[d,t]);  lower[d,t] = min(O930[d], PC[d]) * (1 - vm*sigma[d,t])     # gap-anchored bands
  gate[d] = regime=='none' or (regime=='vix' and VIX_lag[d] >= vix_min) or (regime=='rv' and RV14[d] > RV_med252[d]) or (regime=='vix_q4' and REG.vix_q[d] == 4)
STATE MACHINE at T in {10:00, 10:30, ..., 15:30}, pos in {0, +1, -1}; c = c(T); U = upper[d, T-1]; L = lower[d, T-1]; i = i(T):
  if not gate[d]: no entries today
  pos == 0: if c > U: place(i, +1, stop_px = c - hard_stop_atr*ATR14d); pos = +1
            elif c < L and not long_only: place(i, -1, stop_px = c + hard_stop_atr*ATR14d); pos = -1
  pos == +1: stop_level = L (opp_band) | max(U, TWAP[d, T-1]) (own_band_twap)
            if c < stop_level: exit_at(i); pos = 0; if stop_mode=='opp_band' and c < L and not long_only: place(i+1, -1, stop_px = c + hard_stop_atr*ATR14d); pos = -1
  pos == -1: mirror (stop_level = U | min(L, TWAP); reverse to long if c > U)
  a 1-min hard stop between decisions flattens; the next decision sees pos == 0 (re-entry allowed up to max_trades).
SESSION: set_session('10:00', '15:31', flat); max_trades_day = max_trades; Lucid block with daily_profit_stop x daily_profit_mult (trend days are the whole edge; do not cap them at 1.0x), daily_loss_stop x 1.0.
```
Grid (32): `regime {none, vix, rv, vix_q4}` x `stop_mode {opp_band, own_band_twap}` x `hard_stop_atr {0.35, 0.6}` x `long_only {False, True}`. Fixed: lookback 14, vm 1.0, step 30 (the 90-day / vm 1.5 cells belong to `trend_momentum__noise_area`). One extra run `vix_min=25`.

Session rules: first decision 10:00, last 15:30, flat 15:55.
Risk rules: 36-43% win rate with payoff ~2: lumpy. Worst published day -4.8% of notional with the VWAP stop (-10.3% without) = $1,600 / $3,500 on one MES-equivalent of notional at 4x leverage; at 1x leverage (what the engine runs) -1.2% / -2.6% = $400 / $880 per MES. The hard stop 0.35-0.6 ATR (ES 20-40 pts = $100-200/MES) bounds a single trade; the daily loss block bounds the day. Expect the Monte Carlo to settle at 3-6 micros and a consistency-rule failure risk in short evals; this is a VIX-regime satellite, never the core leg.

Evidence recap: paper Sharpe 0.61 (opp band) / 1.24 (band+VWAP) / 1.33 (+vol target), hit 43%, MDD 12-25%, 12 bp/day; replication 2020-26 Sharpe 1.11, 2022 +25.8%, 2025-26 ~0; Wednesday best (18 bp), Mon/Tue 9 bp - do NOT grid weekdays.

Acceptance: the gated cell must beat the `regime=none` control on `exp_net_lb` in BOTH 2023-24 and 2025-26 and have >= 60 trades in 2025-26; if the gate only removes trades without raising PF, record "VIX gate does not rescue noise-area momentum in 2025-26" and stop.

## 5. academic_anomalies__orb5_capped_target  (Zarattini-Aziz 5-minute ORB: first-bar direction at 09:35, stop at the first bar's extreme floored at 0.1 ATR, R-multiple target capped for the consistency rule)

Priority **2**, complexity **2**, instruments MNQ (published on QQQ/TQQQ), MES; bar size 5-min opening bar on 1-min data. EQ **3** (two SSRN papers by the same group, QQQ 2016-2023 alpha 33% net, no peer review, no futures OOS; hit ratio ~25-30% at 10R, i.e. the profile most likely to break the 50% consistency rule). The spec exists to test whether a **capped** target (2-3R) keeps enough of the edge to be a trend-day satellite; the 10R cell is the paper's literal rule and is a check, not a candidate.

Data gap: none (volume-based "stocks in play" filter does not apply to a single index future).

```
PARAMS: or_minutes=5, rr=3.0, stop_floor_atr=0.1, max_stop_atr=0.5, doji_frac=0.1, direction='both', flat='15:55', max_trades=1
PRE: OR = opening_range(df1, '09:30', or_minutes) -> or_open, or_close, or_high, or_low, i_end; ATR14d
  body = or_close - or_open; rng = or_high - or_low
  side = sign(body) if |body| >= doji_frac * rng and rng > 0 else 0;  if direction=='long_only' and side < 0: side = 0
  stop_dist = max(or_close - or_low if side > 0 else or_high - or_close, stop_floor_atr * ATR14d)      # measured from the 09:35 reference price
  if stop_dist > max_stop_atr * ATR14d: side = 0                        # wide first bar = oversized risk: skip (added for Lucid; paper risks 1% equity instead)
ENTRY: place(i_end + 1, side, stop_px = or_close - side*stop_dist, tgt_px = or_close + side*rr*stop_dist)     # market at the 09:35 open
EXIT: target / stop / forced flat 15:55 (paper: 16:00). No trail.
SESSION: set_session('09:35', '09:36', flat); max_trades_day = 1; daily_loss_stop = stop $ (one trade; inert); daily_profit_stop = Lucid block x 1.5 (inert with one trade; the rr cap is the consistency control).
```
Grid (24): `rr {2, 3, 10}` x `stop_floor_atr {0.1, 0.2}` x `max_stop_atr {0.35, 0.6}` x `direction {both, long_only}`. Fixed: or_minutes 5, doji_frac 0.1. Diagnostic (not grid): P&L by weekday (the paper says Mondays best; do not select on it).

Session rules: single entry at 09:35; flat 15:55.
Risk rules: $R = 0.1-0.5 ATR = NQ 35-175 pts = $70-350/MNQ -> 3-8 micros; win rate 25-45% depending on rr; a 3R winner at 5 micros is ~$500-1,000, which at the moment of passing can be > 50% of cumulative profit if the eval has been short - the Lucid MC must check the consistency rule explicitly for this spec.

Evidence recap: QQQ 2016-2023 alpha 33% net at 10R; TQQQ +1,484%; stocks-in-play Sharpe 2.81; retail NQ claims anecdotal; `orb_session` family's own results on ES/NQ ORBs apply as a prior (modest).

Acceptance: PF >= 1.3 with >= 100 trades on 2025-26 at rr in {2, 3} AND positive-day share >= 40% AND the MC pass rate is not driven by one month. Otherwise drop (the `orb_session` family already covers range breakouts).

## 6. academic_anomalies__opening_fade_upgap  (Boyarchenko-Larsen-Whelan overnight-drift reversal: fade an up-gap >= 0.3% from 09:31 to 12:00; down-gaps faded only after a weak prior last hour)

Priority **2**, complexity **2**, instruments MES, MNQ; bar size 1-min. EQ **4** for the return pattern (NY Fed SR 917: overnight +2.6%/yr of 4.3%, 09:30-12:00 ~-3.9%/yr annualised, 12:00-15:00 flat), **2** for the derived rule (the paper does not trade it; standard interpretation). Distinct from `intraday_mean_reversion__gap_fade_small` (0.10-0.50% gaps, target = prior close, exit 11:00) and `calendar_seasonal_structural__large_gap_fade`: this one keys on the **morning-session negative drift**, not on the fill, so it has a time exit and no fill target by default.

Data gap: the paper's conditioning variable is end-of-day order imbalance (MOC data, not available). Proxy: prior session's 15:00 -> 16:00 return (`r_last_hour`), flagged.

```
PARAMS: gap_min=0.30 (%), gap_max=1.50 (%), entry_time='09:31', exit_time='12:00', stop_atr=0.5, tgt_mode='none' ('none' | 'gap_fill'),
  sides='short_only' ('short_only' | 'both'), last_hour_min=-0.30 (%), flat='15:55', max_trades=1
PRE (per session d): gap_pct = 100*(O930 - PC)/PC;  r_last_hour[d] = 100*(PC - c_{d-1}(15:00))/c_{d-1}(15:00)   (prior session's 15:00 -> 16:00 move)
  short_ok = gap_pct >= gap_min and gap_pct <= gap_max
  long_ok  = sides=='both' and gap_pct <= -gap_min and gap_pct >= -gap_max and r_last_hour <= last_hour_min      # asymmetric: fade down-gaps only after a sell-off into the prior close
  side = -1 if short_ok else +1 if long_ok else 0;  skip if ATR NaN, F.fomc[d] (14:00 is after the exit, harmless, but the morning is positioning), or F.witching[d]
  ref = c(entry_time);  skip if the gap already closed before entry (short: any low of bars [09:30, entry) <= PC)
ENTRY: place(i(entry_time), side, stop_pts = stop_atr*ATR14d, tgt_px = PC if tgt_mode=='gap_fill' else NaN)        # market at the 09:31 open
EXIT: exit_at(i(exit_time)) (market at the open of the 12:00 bar) / stop / target / forced flat 15:55.
SESSION: set_session(entry_time, entry_time + 1 min, flat); max_trades_day = 1; Lucid block inert (one trade).
```
Grid (32): `gap_min {0.3, 0.5}` x `exit_time {11:00, 12:00}` x `stop_atr {0.4, 0.7}` x `tgt_mode {none, gap_fill}` x `sides {short_only, both}`. Fixed gap_max 1.5, last_hour_min -0.3.

Session rules: entry 09:31, time exit 11:00/12:00, flat 15:55; no entries on FOMC / witching days.
Risk rules: 0.4-0.7 ATR stop (ES 25-45 pts = $125-225/MES) on a 2.5-hour hold against the 2025-26 long-biased tape: the benchmark (buy 09:45) is the thing to beat and the report's prior is that it will not be beaten unconditionally; ~40-60 trades/yr at gap_min 0.3. Size 3-6 micros.

Evidence recap: morning negative drift is peer-reviewed and 20+ years long, but it is an average over all days and the 2025-26 window is a strong up-tape; the conditional (bottom-tercile imbalance -> overnight +12.4% European hours) is not capturable day-only.

Acceptance: PF >= 1.3, >= 60 trades on 2025-26 AND positive on 2023-24; otherwise reduce to the design rule "no momentum longs initiated 09:30-10:00 after an up-gap" (a filter the ORB/momentum families can consume).

## 7. academic_anomalies__fomc_post_reversal_1400  (Insper / Quantpedia post-FOMC reversal: trade against the sign of the 24-hour pre-announcement return from 14:00/14:05 to 15:55 on statement days)

Priority **2**, complexity **2**, instruments MES, MNQ; bar size 1-min. EQ **3** (PhD thesis, ES 1997-2020, 180 announcements, negative pre/post relation "independent of uncertainty level and sample period", Sharpe ~2.5x the pre-FOMC drift strategy; no post-2020 OOS; 8 events/yr -> ~14 in the prime window, ~130 on 2010-2026). An overlay, never an eval engine; it is in the file because the 2022-2024 hiking cycle produced several violent 14:00-16:00 reversals that make a 2022-2026 test worthwhile.

Data gap: FOMC statement dates come from the hard-coded table in `calendar_seasonal_structural__calendar_flags_module` (verify against federalreserve.gov); statement time 14:00 for 2013+, `F.fomc_stmt_tod` for 2011-2012 (12:30 / 14:15).

```
PARAMS: entry_delay=5 (minutes after the statement; 0 = at the statement bar), stop_atr=0.5, tgt_atr=0 (0 = none), min_pre=0.0 (%), flat='15:55', max_trades=1
PRE (statement sessions only: F.fomc[d]): T0 = F.fomc_stmt_tod[d]
  pre_ret = c_d(T0) / c_{d-1}(T0) - 1               # 24h pre-announcement return: close of bar tod T0-1 today vs the same bar of the prior session (Lucca-Moench window)
  side = -sign(pre_ret) if |pre_ret| >= min_pre/100 else 0
ENTRY: place(i(T0 + entry_delay), side, stop_pts = stop_atr*ATR14d, tgt_pts = tgt_atr*ATR14d if tgt_atr > 0 else NaN)   # market at the open of the 14:05 bar (bars 14:00-14:04 absorb the print)
EXIT: stop / target / forced flat 15:55 (thesis: 16:00).
SESSION: allow_entry only at the single entry bar on F.fomc sessions (set allow_entry[i] directly); force_flat from 15:55; max_trades_day 1.
```
Grid (16): `entry_delay {0, 5}` x `stop_atr {0.5, 1.0}` x `min_pre {0, 0.2}` x `tgt_atr {0, 0.75}`. Fixed flat 15:55. Press-conference-only diagnostic via `F.press_conference` (report, do not grid).

Session rules: FOMC statement days only; single entry 14:00 or 14:05; flat 15:55.
Risk rules: the 14:00-14:05 bars can be 1% on NQ; stop 0.5-1.0 ATR (ES 30-65 pts = $150-325/MES; NQ 150-350 pts = $300-700/MNQ) means **this leg is capped at 2-4 micros** in the portfolio config (hard rule, as the calendar family does for its FOMC fade). The engine's stop-before-target worst case on the big print is real: with entry_delay 0 the fill is at the 14:00 open + slip and the stop can be hit within the same bar. Prefer entry_delay 5 unless the 0 cell is clearly better on 2013-2026.

Evidence recap: Insper thesis (Sharpe ~2.5-2.8 on event days 1997-2020); Boguth-Gregoire-Martineau post-announcement noise and multi-day fade; Lucca-Moench: average 14:00-close return on FOMC days ~0 unconditionally (so the sign conditioning is the whole edge).

Acceptance: on 2013-2026 (~100 events) win rate >= 58% and PF >= 1.5; 2025-26 (14 events) must not be negative. Otherwise keep only as the filter "no new entries 13:55-14:35 on FOMC days" that other families already use.

## 8. academic_anomalies__gold_western_short_conditional  (CBS-thesis gold "hat": short 02:00 -> 11:00 ET, conditioned on an overnight (Asia) rally, ATR stop; unconditional cell = thesis rule = control)

Priority **2**, complexity **2**, instruments MGC; bar size 1-min (full 18:00-17:00 session). EQ **3** for the periodicity (CBS thesis 5-min 2001-2018: Short 02:00-11:00 +10.0%/yr gross, +13.5% 2013-18, 2017 -3.7%, 2018 -1.1%; Batten et al. 2017), **1-2** post-2019 (untested in the $1,300 -> $4,000+ bull market; the fixing-window shorts are tied to the pre-2015 fix process and are left to `calendar_seasonal_structural__gold_clock_legs`). The conditioning on the overnight rally is the report's prop adaptation (untested).

Data gap: CPI/NFP dates are not available before 08:30 (the 08:30-reaction detector fires after the entry); only `F.fomc` is skipped. London-fix clock shifts (UK/US DST mismatch weeks) are inside the 02:00-11:00 window and ignored.

```
PARAMS: entry_time='02:00', exit_time='11:00', asia_min=0.15 (%; 0 = unconditional thesis rule), stop_atr=0.5, tgt_atr=0 (0 = none),
  trend_filter='none' ('none' | 'sma100'), skip_fomc=True, max_trades=1
PRE (per data session d, 18:00 -> 17:00): ATR_g = daily_atr(rth_only=False) (23-hour range, lagged); PC_g = close of bar tod 16:59 of the prior session
  asia_ret[d] = 100 * (c(entry_time) / open(18:00 bar of session d) - 1)        # Asia-hours move, known at 02:00
  ok = ATR_g notna and asia_ret >= asia_min and (not skip_fomc or not F.fomc[d]) and (trend_filter=='none' or PC_g < SMA_D(100)[d] (full-session closes))
ENTRY: if ok: place(i(entry_time), -1, stop_pts = stop_atr*ATR_g, tgt_pts = tgt_atr*ATR_g if tgt_atr > 0 else NaN)      # market at the 02:00 open
EXIT: exit_at(i(exit_time)) / stop / target; force_flat from exit_time (never later than 16:30).
SESSION: set_session(entry_time, entry_time + 1 min, exit_time); max_trades_day = 1; Lucid block inert (one trade).
```
Grid (24): `asia_min {0, 0.15, 0.30}` x `exit_time {10:00, 11:00}` x `stop_atr {0.3, 0.5}` x `trend_filter {none, sma100}`. Fixed entry 02:00, tgt none (one `tgt_atr=0.4` check run as the consistency cap). Periods reported separately: 2010-2014, 2015-2019, 2020-2024, 2025-26.

Session rules: one short at 02:00, time exit 10:00/11:00; skip FOMC days.
Risk rules: 8-9-hour hold on gold with a 0.3-0.5 x full-session ATR stop (~17-35 $/oz = $170-350/MGC) -> 2-4 micros; gold's 02:00-11:00 window carries most of its daily range, so even at 3 micros a bad day is ~$600-1,000. This is a short against a secular bull: the `asia_min` conditioning is the only reason to expect a positive 2025-26 cell.

Evidence recap: Short strategy +10%/yr gross 2001-2018 with two negative years at the end; Caminschi-Heaney fix leakage (dead post-2015); `gold_clock_legs` west_short 03:00-10:00 is the unconditional control at a narrower window.

Acceptance: PF >= 1.3 on 2020-2026 after costs with >= 100 trades in the conditional cell AND the unconditional control not strongly negative in 2025-26; otherwise record the 30-minute-slot return profile 2020-26 as a filter ("no gold longs 02:00-10:00") and drop.

## 9. academic_anomalies__vix_regime_gate_module  (infrastructure: VIX level / 100-day-quartile regime, realized-vol switch, trend sign, calendar long-bias flag, size multiplier; consumed by specs 1, 3, 4 and the portfolio tool)

Priority **4** (as a filter: costless, and the report's single most likely switch for passing in a given 2-3-month window), complexity **1**, instruments all (per-session table keyed by day_id), bar size daily. EQ **3** (Gao et al.: momentum stronger on high-vol days; Zarattini Sec. 4.3: Sharpe ~1.5 -> ~3.5 at VIX > 40, in-sample; practitioner: excluding the top VIX quartile improved mean-reversion return/DD ~34%; codecat: no VIX-PnL relation 2020-26). Produces no trades.

Data gap: VIX3M / VIX9D (term structure, Johnson 2017) are not in the repo -> `vix_stress` below is a **flagged proxy** (VIX vs its own 20-day mean), not the VIX/VIX3M ratio; if `data/download_yahoo.py` is later extended with ^VIX3M, replace the proxy with `VIX/VIX3M > 1.0` (backwardation) / `< 0.9` (steep contango). Carry (Koijen et al.) needs the term structure of each future -> not available; only the trend half of "trend + carry" is implemented. Net gamma exposure not available.

```
PARAMS: vix_full=20, vix_half=15, q_window=100, rv_len=14, rv_med_len=252, trend_len=100, vix_mr_max=25, vol_target_pct=2.0 (daily), size_cap=2.0
PER SESSION d (all inputs lagged: VIX_lag = prior-day close; daily bars of sessions < d):
  vix_q[d]      = quartile (1..4) of VIX_lag[d] within [min, max] of VIX closes over the prior q_window sessions (NaN until q_window sessions exist)
  mom_size[d]   = 1.0 if VIX_lag >= vix_full or vix_q == 4 else 0.5 if VIX_lag >= vix_half else 0.0        # momentum sizing (specs 1, 4)
  rv_hi[d]      = RV14[d] > RV_med252[d]                                                                   # realized-vol alternative to the VIX level
  meanrev_on[d] = vix_q != 4 and VIX_lag < vix_mr_max                                                       # gap-fill / RSI mean reversion allowed (spec 3; intraday_mean_reversion__rsi3_dip_vixgate)
  vix_stress[d] = VIX_lag > sma(VIX, 20).shift(1)        # FLAGGED proxy for VIX/VIX3M backwardation
  trend100[d]   = sign(PC[d] - SMA_D(trend_len)[d])                                                         # Koijen trend sign; momentum entries only with the trend when a spec sets direction='trend'
  long_bias[d]  = tom[d] or payday[d] or opex_week[d] or turnaround_tue[d]
      tom           = session index within month in {last} or {1st, 2nd, 3rd}  (Xu-McConnell -1..+3)
      payday        = first session with calendar day >= 16
      opex_week     = Mon..Thu of the week containing the 3rd Friday (Quantpedia OpEx-week window)
      turnaround_tue= dow == Tuesday and D.close[d-1] < D.open[d-1]  (Monday closed down)
  size_mult[d]  = min(size_cap, vol_target_pct/100 / RV14[d])   # paper-style vol targeting for the portfolio tool (applied to daily P&L streams as integer micros)
  skip_day[d]   = RV14[d] > 2.5 * RV_med252[d]                   # extreme-vol circuit breaker for every spec (crash regimes blow through EOD-trailing limits)
OUTPUT: DataFrame indexed by day_id with the columns above; strategies read it via REG = regime(df1).
```
Grid (4 combos, each consuming spec runs it as its `regime` cell): `(vix_full, vix_half) {(20, 15), (25, 18)}` x `vix_mr_max {25, 30}`. Fixed q_window 100, rv 14/252, trend 100.

Session/risk rules: n/a (no trades). Usage contract: a spec that takes `regime='mom_size'` skips days with `mom_size == 0`; the 0.5 cells are applied by `backtest.portfolio` as half the micro count (round down, minimum 1). `skip_day` is a hard filter in the portfolio config. The calendar flags are **long-bias only** (no shorts on those days), never a reason to enter: every published number for them is close-to-close and the report expects the intraday share to be ~0.

Evidence recap: Zarattini VIX bar chart, Gao vol terciles (both in-sample); algotr RSI/VIX quartile test (34% better return/DD, undisclosed period); codecat 2025-26 Sharpe collapse coincided with a low grinding VIX (consistent with the gate); Johnson 2017 (term structure predicts variance assets, not ES direction).

Acceptance: a gate is kept only if it raises `exp_net_lb` of the consuming spec on 2023-24 AND 2025-26 (two periods, same threshold); a gate that helps one and hurts the other is reported as "regime-dependent, not predictive".

---

## Dropped or folded (and why)

- **Pre-FOMC announcement drift** (Lucca-Moench): needs the 14:00 -> 14:00 overnight hold; effect 49 bp -> 9 bp after 2015 (Kurov et al.). Day-only morning leg already specified as `calendar_seasonal_structural__pre_fomc_morning_drift`; nothing to add.
- **End-of-day reversal** (Soebhag-Baltussen-Da): cross-section of single stocks; at the index level the last 30 minutes are momentum (spec 1). Lesson recorded: never fade the index into the close.
- **VIX term-structure signals** (Johnson 2017): predicts variance assets, not ES direction; VIX3M not in the data set. Folded as the flagged `vix_stress` proxy in spec 9.
- **Turn-of-the-month, payday (16th), options-expiration week, Turnaround Tuesday**: all documented close-to-close (overnight), tiny and weakening; day-only versions have no published numbers and the calendar family's `calendar_window_long` / `turnaround_tuesday` already run the cheap one-line tests. Folded into `long_bias[d]` (spec 9) as a no-shorts flag.
- **Witching-day short**: `calendar_seasonal_structural__witching_day_short` is exactly the Caporale-Plastun rule; not duplicated.
- **Overnight-return reversal across ES/NQ/GC**: `intraday_mean_reversion__onrev_cross_sectional` (`mr_onrev.py`) is the module; run `universe='eq'` (ES vs NQ) and combine the two legs with opposite signs in `backtest.portfolio` (that is the market-neutral NQ-vs-ES spread the report describes; equal notional ~ 3 MNQ : 2 MES at NQ 25,000 / ES 6,800). Per-day edge on a 1-lot spread is tens of dollars; a diversifier only.
- **Short-term (weekly) reversal in futures** (Wang / Quantpedia): weekly Wednesday-to-Wednesday holds (not allowed) and needs volume and open interest (not available). Dropped.
- **NQ/ES intraday lead-lag**: EQ 1, no published exploitable 1-minute lead; sub-minute data would be needed; costs on 1-min signals dominate. Dropped.
- **Gold-equity cross-asset ratios** (Huang-Kilic, S&P/gold): monthly horizon; platinum not available. Dropped (regime context only).
- **Trend-following + carry**: carry needs the term structure (not available); the trend half is `trend100` in spec 9. No intraday evidence; not a strategy.
- **Gold fixing-window shorts (05:05-05:35, 09:35-10:05)**: tied to the pre-2015 fix process, authors expect it unprofitable going forward, 30-minute round trips on MGC at $3.30/RT; `gold_clock_legs` already has `amfix_fade` / `pmfix_fade`. Not duplicated.
- **Intraday seasonality of returns and volatility**: descriptive; its content is already in the design of specs 1 (15:30 entry), 4 (minute-of-day sigma), 6 (morning drift) and the Lucid stop sizing. Not a strategy.
- **Gao et al. first-half-hour-only sign rule**: negative OOS (QuantConnect, Marwood); kept only as the agreement filter in spec 1 and as the control `trend_momentum__last_half_hour`.
- **Vol targeting at 4x leverage / 1% equity risk per trade (papers' sizing)**: not representable inside a one-contract engine; expressed as `size_mult` / `skip_day` in spec 9 for the portfolio and Lucid tools (engine gap, flagged).

## Portfolio notes for the backtest agents (Lucid 50K Flex: $3,000 target, $2,000 EOD-trailing MLL, 50% consistency in eval)

1. Core candidates: spec 1 (afternoon momentum, MES + MNQ) and spec 3 (morning gap fill, MES long side). They trade different hours, different directions of causation (hedging-demand momentum vs overnight-gap mean reversion) and partly different days (spec 3 only on Tue-Thu gap-downs); run `backtest.portfolio_opt` on the pair first, then add spec 2 (gold 13:00) as the uncorrelated third leg.
2. Satellites gated by spec 9: spec 4 only when `mom_size == 1`, spec 3 only when `meanrev_on`; spec 7 at <= 4 micros on 8 days a year; spec 5, 6, 8 only if they clear their own acceptance bars (the report's prior is that 5 and 6 fail the consistency simulation and 8 fails the bull-market test).
3. The pass bar for every spec is the guide's: PF >= 1.3 with >= 150 trades (or >= 1.5 with >= 60), daily Sharpe >= 1.5, positive-day share >= 50%, no month > 40% of net, PF >= 1.1 on 2023-24 with the same parameters, grid a plateau; then `lucid_scan` must mark a size `recommended` (lower bound of expected net positive and >= $100 above the zero-edge control). One-trade-per-day specs with a 55%+ hit rate (1, 2, 3) are the ones that can satisfy the 5 x >= $150 payout days; the trend captures (4, 5) cannot without a profit stop, which removes their edge - that trade-off is the main thing the Monte Carlo must report for this family.
4. Report every FOMC/CPI-dependent spec (7, and the `days` cells of 1) with the calendar table's verification status; a wrong FOMC date silently turns spec 7 into noise.
