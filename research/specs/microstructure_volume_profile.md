# Specs: Market profile, volume profile, VWAP and order-flow methods for the Lucid 50K LucidFlex backtest

Source report: `/home/user/claude-workspace/research/families/microstructure_volume_profile.md` (read fully; section numbers below refer to it).
Engine contract: `/home/user/claude-workspace/docs/STRATEGY_GUIDE.md`, `backtest/engine.py` (`Intents.place(idx, side, entry_px, valid_bars, stop_px, tgt_px, stop_pts, tgt_pts, trail_pts, trail_act_pts, max_hold, kind='stop'|'limit')`, `Intents.exit_at(idx, which=+1|-1|2)`, `Intents.set_session(entry_start, entry_end, flat_time)`, public arrays `allow_entry` / `force_flat`, `max_trades_day`, `daily_loss_stop`, `daily_profit_stop`), helpers in `strategies/common.py` (`atr`, `adx`, `sma`, `ema`, `session_vwap` (= session TWAP of typical price, the volume-free VWAP proxy), `opening_range`, `daily_atr`, `prior_day_stats`, `session_info`, `vix_lag1`), `backtest.data.resample(df1, N, rth_only=True, rth=(open, close))` (adds `tod` = bar start, `i_first`, `i_last`, `i_next`; buckets anchored at 18:00 so 5/30-minute RTH bars start 09:30, 09:35, ... / 09:30, 10:00, ...) and `backtest.data.daily_bars`.

**Family verdict that drives the priorities (report sections 0, 23, 24).** Volume-profile *geometry* (POC, value area, 80% rule, day types) has no cost-adjusted standalone edge in the only adversarial test found (pedrobraiti: bootstrap PF CIs include 1.0, 80% rule traverses 27-67%); the edge that study did find needed a volume filter we cannot compute. What has large-sample, OHLC-codeable support is **time structure**: the initial balance (tradingstats ES 2,686 / NQ 2,833 days 2015-2025 plus a 12-year retest study to May 2026). Session VWAP has one paper-grade result (Zarattini-Aziz QQQ, Sharpe 2.1) whose mechanics (always-in, 17% hit, ~15 flips/day) are friction-hostile on micros; only its two-window, close-confirmed variant is worth engine time. Order-flow methods (delta, absorption, footprint, NYSE TICK) cannot be reproduced from OHLC and are dropped (section 17 below). Two modules from this family's IB corner already exist and have results: `orb_ib_c` (C-period confirmation: default rule **dead** on 2025-26, MES `narrow_break` PF 1.25 MAIN / 1.11 PRIOR but `recommended=False` in the Lucid scan) and `mr_ibfail` (failed-break fade, **dead**). Those results are the prior for every IB spec here: the IB has structure, but a 1:1-ish payoff at ~45% after costs is not enough; the specs below go after the **70-77% continuation** retest entry and the **86-90% directional** ending-zone filter, which are the only base rates in the family high enough to clear costs with a tight stop.

## 0. Conventions used by every spec below

**Times**: all ET. Data session 18:00 -> ~16:14 (equity CFD feed), 18:00 -> 17:00 gold. RTH equities 09:30-16:00; gold pit 08:20-13:30 (gold trades ~23h; the GC IB specs anchor at 09:30 like their sources and say so). A 1-minute bar with `tod = T` covers `[T, T+1)`. "Close at 10:30" = close of the bar with `tod = 10:29`; the decision uses that close and the order is placed at the bar with `tod = 10:30` (`i_next` on resampled frames; skip `-1` = session ended). **Market at next open (+1 tick slippage)** unless the spec says `kind='stop'` or `kind='limit'`. Limit entries fill at the level **only when price trades through it by one tick** and carry no slippage, so a resting limit meant to fill "on touch of level L" is placed at `L + side*tick` (long: one tick above L; it fills when the bar's low <= L). Protective stops fill at level - 1 tick (worst case: stop before target when both are touched in one bar). Targets fill only when traded through by one tick. One position at a time, one pending order at a time; a signal placed while a position is open (or on the bar a position was just closed) is ignored. `max_hold` counts 1-minute bars from the fill bar.

**Forced flat**: equities **15:55** (never later than 15:58). Gold: 13:25 for pit-anchored variants, 15:55 for the 09:30-anchored GC IB variants (Lucid allows 16:45; the sources flatten at the equity close). No overnight, no weekends. Early-close sessions (`session_info().early_close`) take no entries after 12:00.

**Costs per micro per round trip, already in the engine** (`backtest/contracts.py`): MES $2.50 slippage + $1.30 commission = $3.80 (0.76 pt); MNQ $1.00 + $1.30 = $2.30 (1.15 pt); MGC $2.00 + $1.30 = $3.30 (0.33 pt). Limit fills save the slippage half. Stress run: `--slip 2`. Deployability floor (report section 23 item 6): mean gross per trade >= 1.5 ES / 6 NQ / 1.0 GC points, and **median initial stop >= `min_stop_pts` = {MES 4, MNQ 10, MGC 1.5}**; every spec that derives its stop from a range fraction carries this guard (`stop = min(stop_level, ref - side*min_stop_pts)` for longs, i.e. the stop is never closer than the guard).

**Indicator and level definitions (exact)**:
- `ATR14d` = `daily_atr(df1, 14, rth_only=True, rth=(rth_open, rth_close))`: Wilder ATR of RTH daily bars shifted one day (session d uses days < d). NaN -> no trade. 2025-26 medians: SPX ~76 pts, NDX ~398 pts, GC (pit) ~69.
- `IB` = `opening_range(df1, ib_start, 60)`: `ib_high, ib_low, ib_open, ib_close, i_end` over `[ib_start, ib_start+60)` (09:30-10:30 equities; GC specs say which anchor). `ib_rng = ib_high - ib_low`, `ib_mid = (ib_high+ib_low)/2`. Require >= 48 of 60 bars. Valid only at indices > `i_end`. IB tier (section 8): narrow `ib_rng < 0.5 ATR14d`, normal 0.5-1.0, wide 1.0-1.5, extreme > 1.5 (never traded).
- `i_hi(IB)` / `i_lo(IB)` = 1-minute index of the first bar whose high == `ib_high` / low == `ib_low`. `low_first = i_lo < i_hi`; `bias = +1 if low_first else -1` (section 9: the first-formed extreme is expected to hold and the other to break). `ez` (ending zone) = distance of the 10:29 close from the expected-break edge as a fraction of `ib_rng`: `ez = (ib_high - c1029)/ib_rng` if `low_first` else `(c1029 - ib_low)/ib_rng`. `ez <= 0.25` = "confirmed" zone (86-90% directional in the vendor samples).
- `B5` / `B30` = `resample(df1, 5 / 30, rth_only=True, rth=(rth_open, rth_close))`; `ATR5m14` = Wilder `atr(B5, 14)` on the continuous 5-minute RTH series (across sessions, `min_periods=14`); `ADX5m14` = `adx(B5, 14)`.
- `TWAP` = `session_vwap(df_rth)` on the 1-minute RTH bars (cumulative mean of typical price (H+L+C)/3 from 09:30; the VWAP proxy, **flagged** everywhere it is used). `TWAP_k` for a 5-minute bar `k` = the 1-minute TWAP value at `B5.i_last[k]`. `SIG_k` = cumulative population std-dev of 1-minute typical price from 09:30 through `B5.i_last[k]` (the sigma-band proxy); needs >= 10 bars. Alternative bands: `k_atr * ATR5m14`.
- `PROFILE[d]` = the time-at-price profile of session d-1's RTH bars (spec 1 defines it): `poc, vah, val, vaw = vah - val, ph` (poor-high flag), `pl`, `tails`, `sp_zones` (single-print zones), `npoc` (naked POCs list). Day d uses it from 09:30. `pd_high / pd_low / pd_close` from `prior_day_stats` (1-day lag). `O930` = open of the 09:30 bar; `gap = (O930 - pd_close)/pd_close`.
- `fh_dir[d]` = sign(close(10:29) - O930): the first-hour candle colour (edgeful: green first hour -> green close 73.9% NQ).
- `R` in the IB specs = `ib_rng` (the tradingstats extension unit). `$R` = points x point value (MNQ $2, MES $5, MGC $10).

**Lucid risk block** (default for every spec unless overridden; all values per ONE micro contract; the Lucid Monte Carlo scales 5-40 micros):
- `daily_loss_stop`: MES $60, MNQ $80, MGC $80 (grid multiplier `dls_mult {1.0, 1.5}`); for one-trade-per-day specs it is the single max stop in $ so a full stop-out ends the day. At 10 micros = $600-$1,200, under 60% of the $2,000 EOD-trailing distance.
- `daily_profit_stop`: MES $120, MNQ $160, MGC $160 (grid `dps_mult {1.0, 1.5}`; inert on one-trade specs). At 10 micros ~$1,200-$1,800/day so no day exceeds 50% of the $3,000 target (consistency rule) and the funded phase collects many >= $150 days.
- Both stops look at **realized** P&L only and only block new entries, so every entry carries a hard protective stop. `max_trades_day` as specified; always `set_session(entry_start, last_entry, flat)`.
- Consistency arithmetic: at the moment of passing, the largest day must be <= $1,500 -> per-micro largest day <= $150-300 at 5-10 micros. Capped targets (<= 1.0 x VA width, <= 0.6 x IB range + stop) give this by construction; the VWAP trend spec (11) does not and therefore carries a daily profit stop and a hard target cap `tgt_cap_atr`.
- Payout arithmetic: 5 funded days >= $150. High-hit-rate capped-target specs (2, 3, 4) produce those days; the VWAP flip spec the fewest.
- News blackout (CPI/NFP 08:30, FOMC 14:00): NOT implemented (no event calendar in the data). All entry windows here start >= 10:00; the FOMC 14:00 bar is covered by the hard stop plus the daily loss stop, and spec 12's second window closes at 14:30. Document, do not fake.

Priority: 5 = best prior of working under Lucid constraints with evidence and the existing results, 1 = long shot / control. Complexity: 1 = a parameter on an existing module, 5 = multi-state intraday machine with a profile builder. EQ = the report's evidence quality (1-3 in this family).

Benchmarks every spec must beat on 2025-01..2026-09: `trend_momentum__benchmark_long_0945` (buy 09:45, flat 15:55), and this family's own ungated controls (the `twap_revert` module cells for spec 12, `confirm_bar=1, windows='all'` for spec 11, `zone_filter=False, bias_filter=False` for specs 2-3). Every spec runs MAIN 2025-01-01..2026-09-30 and PRIOR 2023-01-01..2024-12-31 with identical parameters; a cell counts only if PF >= 1.1 on PRIOR and its grid neighbours agree (plateau); then `backtest.walkforward` from 2015 (the IB base rates are stable 2015-2025, so a spec that does not survive 2015-2024 is not trading the base rate) and `lucid_scan`.

---

## 1. microstructure_volume_profile__profile_module  (infrastructure: time-at-price / TPO profile builder: POC, value area, poor highs/lows, single prints, naked POCs)

Priority **4** (prerequisite for specs 4-8, 15, 16 and the POC targets in 13, 17), complexity **3**, instruments all, bar size 1-min (time-at-price) and 30-min (TPO). Not a strategy: `profile(df1, contract, params) -> DataFrame indexed by day_id` with the columns below, every row computed from sessions **strictly before** that day_id (shift by one session). Report section 1 (data reality table) and section 11 (poor high / single print definitions).

Data gap and the design answer: the volume profile needs volume at price; we have none. The time-at-price profile from 1-minute bars (each bar adds 1 to every price row in `[low, high]`) correlates strongly with the volume POC/VA on index futures (minutes are far more uniform in volume than in price range) but **cannot see volume spikes or LVNs** -> fidelity medium-high for POC/VA, low for LVN/HVN. The 30-minute TPO profile is exact (Market Profile never used volume). Both are built; the strategies default to `mode='tpm'` (time-at-price, 1-min) with `mode='tpo'` in the grid.

```
PARAMS: mode='tpm'|'tpo', va_pct=0.70, row_mult={MES:1, MNQ:4, MGC:1} (row height = row_mult x tick: 0.25 ES, 1.0 NQ, 0.10 GC),
        src='rth' (09:30-16:00 equities; gold uses 08:20-13:30 for pit profiles or 09:30-16:00 when the strategy anchors at 09:30),
        npoc_lookback=10, poor_min_tpo=2, tail_rows=2
PER SESSION s (RTH bars only):
  rows = arange(floor(min(low)/row)*row, ceil(max(high)/row)*row + row, row)
  tpm:  count[r] = number of 1-min bars with low <= r <= high            (exact per-row minutes-at-price)
  tpo:  count[r] = number of 30-min bars (B30 of session s) with low <= r <= high
  POC   = argmax(count); ties -> the row closest to (max(high)+min(low))/2 (CBOT convention)
  VA    = Steidlmayer: acc = count[POC]; up = POC+row, dn = POC-row;
          while acc < va_pct * sum(count): a = count[up]+count[up+row]; b = count[dn]+count[dn-row];
            if a >= b: acc += a; vah = up+row; up += 2*row  else: acc += b; val = dn-row; dn -= 2*row
          (rows outside the session range count 0; VAH/VAL clipped to the session high/low)
  poor_high = count_tpo[session_high_row] >= poor_min_tpo and no tail above       (tpo counts, 30-min)
  tail_high = the top `tail_rows` rows all have count_tpo == 1 (single-print excess); poor_low / tail_low mirror
  sp_zones  = maximal runs of interior rows (strictly between the top and bottom tail) with count_tpo == 1 and length >= 2 rows;
              stored as (zone_low, zone_high)
OUTPUT for day d (= session index of the trading day): poc, vah, val, vaw, s_high, s_low, poor_high, poor_low, tail_high, tail_low,
  sp_zones (list), all taken from session d-1 (the last COMPLETED RTH session before d; holidays: the previous available session).
  npoc[d] = list of (session, poc) for sessions d-npoc_lookback-1 .. d-2 whose POC row was NOT inside any later completed session's
  [low, high] (sessions <= d-1 only). Retiring a naked POC on day d's own touch is done inside the consuming strategy's bar scan.
LOOK-AHEAD: nothing from session d enters profile[d]; a strategy that uses today's developing profile must build it bar-by-bar
  (none of the specs here do; today's levels are the IB and TWAP, which are causal).
VALIDATION: on 10 random sessions compare tpm vs tpo POC/VAH/VAL (expect |diff| < 0.15 x vaw on balance days); print the share of
  days with O930 inside [val, vah] (expect ~55-65% on ES) and the vaw/ATR14d distribution (median ~0.4-0.5).
```
Grid: none (infrastructure); the consuming specs carry `mode {tpm, tpo}` and `va_pct {0.65, 0.70}`.

Risk/Lucid: n/a.

## 2. microstructure_volume_profile__ib_retest_continue  (IB break, 1.1x-1.2x extension, limit entry at the broken IB level on the first return, 10:30-12:00 only; tradingstats 12-year retest study)

Priority **5**, complexity **3**, instruments MES, MNQ (ES continuation slightly stronger), MGC as a cheap third run, bar size 1-min. EQ **3** (NQ/ES Feb 2014-May 2026, ~3,000 break-days each: at the 1.1x extension 91% reached, first return to the level 87-90%, retest -> continue **71% NQ / 77% ES**, reverse 16%; fast moves at 1.2x continue 62% vs slow 42%; 10:30-12:00 continue 58% vs 23% after 14:00; narrow IB 73% vs wide 54%; 90% of first returns hold within 10% of R; median second leg +0.45R NQ / +0.56R ES). Report section 7, ranked 1 in section 24. No P&L was modelled in the study: this spec is the first cost-adjusted test. New module `mp_ibretest`.

```
PARAMS: ib_minutes=60, ext_mult=0.1 (1.1x), speed_max=30 (min from break to extension; 0 = off), retest_deadline='12:00',
        confirm='limit'|'wick', entry_off_ticks=1, stop_mode='frac'|'mid', stop_frac=0.25, tgt_r=0.45, tgt_mode='ext_plus'|'fixed',
        tgt_fixed=0.5, ib_min_atr=0.2, ib_max_atr=1.5, sides='both'|'long', rebreak=False, max_hold=0 (0 = none), flat='15:55',
        max_trades=1, min_stop_pts={MES:4, MNQ:10, MGC:1.5}
PRE (per session d): IB = OR(ib_start, 60); atr = ATR14d[d]; skip if atr NaN, ib_rng < ib_min_atr*atr, ib_rng > ib_max_atr*atr, < 48 IB bars,
  early_close[d]. R = ib_rng. dl = hm(retest_deadline).
SCAN 1-min bars i from IB.i_end+1 (10:30) while tod[i] < dl, state machine:
  phase BREAK: first bar k with high[k] > ib_high (up) or low[k] < ib_low (down); both in one bar -> the side nearer open[k].
    side = +1 (up) / -1 (down); level = ib_high (up) / ib_low (down). If sides=='long' and side == -1: day done.
    ext_level = level + side*ext_mult*R. t_break = k.
  phase EXTEND: scan j = k..: if side*(close[j] - level) < 0 (a 1-min CLOSE back inside the IB before the extension is reached):
      the break failed before extending -> day done (rebreak=True: return to phase BREAK for the SAME side only, once).
    if (side==+1 and high[j] >= ext_level) or (side==-1 and low[j] <= ext_level): t_ext = j; break.
    if tod[j] >= dl: day done.
  SPEED: if speed_max > 0 and (t_ext - t_break) > speed_max: day done (slow grind; continuation 42%).
  ORDER at i0 = t_ext + 1 (must satisfy tod[i0] < dl and same session):
    confirm='limit' (published, section 7: "limit order at the broken IB level, entry on the first touch"):
      entry_px = level + side*entry_off_ticks*tick, kind='limit', valid_bars = dl - tod[i0]  (expires at 12:00 unfilled)
      hi_ext = side*max(side*high/low over t_break..t_ext) = the extension extreme known at placement
      stop:  'frac' -> stop_px = level - side*stop_frac*R ; 'mid' -> stop_px = ib_mid        (failed retests reach ib_mid 69-81%)
             guard: stop no closer than min_stop_pts to entry_px
      tgt:   'ext_plus' -> tgt_px = hi_ext + side*tgt_r*R  (prior extension extreme + 0.4-0.5R: the median second leg)
             'fixed'    -> tgt_px = level + side*tgt_fixed*R
      place(i0, side, entry_px, kind='limit', valid_bars, stop_px, tgt_px, max_hold)
    confirm='wick' (+5 pp continuation in the study): no resting order; scan i >= i0 while tod[i] < dl for the first bar with
      side*(level - low[i]) >= 0 (long: low[i] <= level) and side*(close[i] - level) > 0 (closes back on the break side):
      place(i+1, side, market, stop_px/tgt_px as above measured from level, max_hold). If a bar closes through the level
      (side*(close - level) < 0) before any rejection bar: day done (deep retest, continuation 24%).
EXITS: stop, target, max_hold (grid), forced flat. One setup per day (max_trades_day = 1).
SESSION: set_session('10:30', retest_deadline, flat).  RISK: daily_loss_stop = stop_frac*R_median*point_value (one trade/day).
LOOK-AHEAD: the order is placed at t_ext+1 using bars <= t_ext only; hi_ext uses bars <= t_ext; the limit fill is simulated by the
  engine on later bars. Never use the retest bar itself to size the order.
```
Grid (3 x 2 x 2 x 2 x 2 = 48): `ext_mult {0.1, 0.2, 0.3}`, `confirm {limit, wick}`, `stop_mode {frac, mid}`, `tgt_r {0.3, 0.5}`, `sides {both, long}`. Fixed at defaults: `speed_max 30`, `ib_max_atr 1.5`, `retest_deadline 12:00`. Follow-up (best cell only): `speed_max {0, 30, 60}`, `ib_max_atr {1.0, 1.5}`, `max_hold {0, 120}`, `tgt_mode fixed`, `retest_deadline {12:00, 13:30}` (expected to degrade: the afternoon continuation rate halves).

Risk/Lucid: stop 0.25R: ES IB median ~45 pts -> ~11 pts ($56/MES); NQ ~240 pts -> ~60 pts ($120/MNQ); target ~0.55R from entry -> ~1.1:1 at a claimed 71-77% hit (before the 13% that never return and the expiries). Expect ~0.5-0.6 fills/day (break 97% x reach 1.1x 91% x return 87% x window share). Largest day = one target (~$65 MES / ~$130 MNQ): consistency-safe at 10 micros. The `mid` stop doubles the risk ($110 / $240); the Lucid scan will size it at 3-5 micros. The failure mode to watch is the 16% reversal cohort on wide IBs: if PRIOR PF < 1.1, cut `ib_max_atr` to 1.0 before anything else. Cross-check against `mr_ibfail` (the same first-break event traded the other way, dead): if both are negative the IB break event itself is not tradable after costs in 2025-26 and the family's IB corner is closed.

## 3. microstructure_volume_profile__ib_rejection_zone_limit  (IB-by-rejection bias with the ending-zone filter: 25%/50%-retracement limit entries toward the expected break, plus the IB75 contrarian cell; edgeful)

Priority **4**, complexity **3**, instruments MNQ first (NQ low-first 78.5%), MES, MGC low-first only, bar size 1-min (IB) + 5-min. EQ **2** (vendor, 6-12 month 2025-26 samples: low-first -> high breaks 78.5% NQ / 60-63% ES / 70.5% GC; ending zone 0-25% -> 86.6% NQ / 86.4% ES; IB75 18/22; the high-first leg unstable 77% vs 51%; no costs). Report section 9, ranked 3 in section 24. Must be re-validated on 2015-2026 because the samples are tiny. New module `mp_ibzone`.

```
PARAMS: mode='retrace'|'ib75', entry_frac=0.25 (limit depth into the IB from the expected-break edge; 0.5 = ib_mid),
        stop_mode='mid'|'far' (retrace mode: 'mid' = ib_mid for entry_frac 0.25, 'far' = opposite IB edge for entry_frac 0.5),
        tgt_ext=0.2 (target = expected edge + tgt_ext*R), zone_max=0.25, zone_filter=True, bias_filter=True, sides='both'|'long'
        (long = only low_first setups; the unstable leg off), last_entry='13:00', valid_until='13:00', flat='15:55', max_trades=1,
        ib_min_atr=0.2, ib_max_atr=1.5, min_stop_pts, require_touch_before=False
PRE (known at the 10:30 bar): IB, atr, tier filter as spec 2; low_first, bias, ez (section 0); c1029 = close of the 10:29 bar.
  skip: atr NaN, extreme IB, early_close, fewer than 48 IB bars, i_hi == i_lo (one bar made both extremes).
  if sides=='long' and bias == -1: skip.
mode 'retrace' (main variant):
  if zone_filter and ez > zone_max: skip (the 10:30 close is not within 25% of the expected-break edge).
  edge = ib_high if bias==+1 else ib_low; far = ib_low if bias==+1 else ib_high
  entry_px = edge - bias*entry_frac*R  (+ bias*tick so the fill happens on a touch; see section 0 limit semantics)
  stop_px  = ib_mid - bias*tick (stop_mode 'mid'; only sensible when entry_frac < 0.5) | far - bias*tick ('far')
  tgt_px   = edge + bias*tgt_ext*R
  i0 = IB.i_end + 1 (10:30). If bias*(c1029 - entry_px) < 0 (the 10:29 close is already beyond the limit level, i.e. price is
    deeper in the IB than the entry): place a MARKET order at i0 instead (entry_px NaN) with the same stop/tgt (grid flag
    market_if_through {True, False}; False = skip the day).
  place(i0, bias, entry_px, kind='limit', valid_bars = hm(valid_until) - tod[i0], stop_px, tgt_px)
  The engine cancels the resting limit if the expected edge breaks first and price never retraces (no fill: the 0.2x extension was
  reached without us; this is the cost of the limit entry and is the number to report: fill rate).
mode 'ib75' (contrarian; edgeful IB75): condition ez >= 0.75 (the 10:30 close pulled back to within 25% of the FIRST-formed level).
  Trade TOWARD the first-formed level (expect it to break): side = -bias.
  level_first = ib_low if low_first else ib_high
  entry_px = level_first + bias*0.25*R  (the 75% level; price must come back up (down) to it) kind='limit', valid until valid_until
  stop_px  = ib_mid + bias*tick   (just beyond the midpoint; risk 0.25R)
  tgt_px   = level_first - bias*tgt_ext75*R  (tgt_ext75 default 0.0 = the level itself (published), grid 0.1)
EXITS: stop, target, forced flat (no time stop in the published rule; grid max_hold {0, 180}). max_trades_day = 1.
SESSION: set_session('10:30', last_entry, flat). RISK: daily_loss_stop = 0.25*R_median*point_value (one trade/day).
LOOK-AHEAD: bias, ez and the levels use bars <= 10:29 only; i_hi/i_lo are computed inside the IB window.
```
Grid (2 x 2 x 2 x 2 x 2 = 32): `mode {retrace, ib75}`, `entry_frac/stop_mode {(0.25, mid), (0.5, far)}` (paired, retrace only; ib75 ignores), `tgt_ext {0.1, 0.2}`, `zone_filter {True, False}` (False = the raw 78% bias, the control), `sides {both, long}`. Follow-up: `zone_max {0.25, 0.35}`, `valid_until {12:00, 13:00, 14:00}`, `max_hold {0, 180}`.

Risk/Lucid: risk 0.25R (~$56 MES / $120 MNQ) for a target 0.45R from entry (0.25 to the edge + 0.2 extension): 1.8:1 at a vendor-claimed ~70-85% x 71% (0.2x touched 71% of breakout days) -> the honest expectation is ~55-60% hit at 1.8:1 before costs, which clears costs if the limit fill rate is > 50%. Largest day = one target (~$100 MES / $220 MNQ per micro): at 10 micros $2,200 -> **exceeds the $1,500 consistency cap on MNQ**; the Lucid scan will stop at 6-7 micros or the backtest agent sets `tgt_ext 0.1`. ~0.3-0.4 trades/day with the zone filter (the 0-25% zone is ~50% of sessions). Shares the 10:30 placement with spec 2 on the same contract: run them on different contracts or as a combined module that prefers spec 2 when a break has already happened.

## 4. microstructure_volume_profile__ib_cperiod_bias_ext  (extensions to the existing `orb_ib_c` module: first-formed bias, ending-zone gate, fractional stop, time stop)

Priority **3**, complexity **1** (parameters on an existing module), instruments MES, MNQ, bar size 60-min IB + 30-min C. EQ **3** for the base rates (section 6: C-period close beyond the IB lifts the 100%-extension rate to 45.5-50% ES vs 19-20%; low-first -> single-up 52.5% vs single-down 17.0%; shallow < 25% retrace -> 93.8% close in break direction). Existing results: default rule PF 0.78-0.87 MAIN on all three contracts (dead); MES `narrow_break` PF 1.25/1.11, not recommended. Overlaps `orb_session__ib_c_confirm` (spec 8 there): this spec adds only the family's conditioning statistics; same module, one set of runs.

```
NEW PARAMS on strategies/orb_ib_c.py: bias_filter=False (True: c_confirm long only if low_first, short only if high_first;
  narrow_break: place only the bias side's stop order), zone_filter=False (True: additionally require ez <= zone_max, zone_max=0.25),
  stop_mode='frac' (new: stop = broken edge - side*stop_frac*ib_rng, stop_frac=0.25; the published 'mid' = 0.5), max_hold=0,
  retrace_exit with retrace_frac=0.25 (the 25% shallow/deep boundary; with stop_mode 'frac' 0.25 it is no longer a no-op as the
  README notes for 'mid' 0.5), fh_filter=False (True: trade only if fh_dir agrees with the break side).
PSEUDOCODE: unchanged from orb_ib_c (C = [10:30, 11:00) built from 1-min bars; long if C.close > ib_high and (C.close - ib_high) <=
  max_ext_entry*ib_rng; entry market at 11:00; target ib_high + tgt_ext*ib_rng); add before placement:
  if bias_filter and side != bias: skip ; if zone_filter and ez > zone_max: skip ; if fh_filter and side != fh_dir: skip
  stop: 'frac' -> stop_px = edge - side*stop_frac*ib_rng (guard min_stop_pts; clamp max_stop_atr*atr)
SESSION / RISK: as the module (entries [11:00, 11:01) c_confirm, [10:30, 12:00) narrow_break; flat 15:55; max_trades 1).
```
Grid (2 x 2 x 2 x 2 x 2 = 32): `mode {c_confirm, narrow_break}`, `bias_filter {False, True}`, `zone_filter {False, True}`, `stop_mode {frac(0.25), mid}`, `tgt_ext {0.5, 1.0}`; fixed `ib_max_atr 1.0` (the module's best cell). Follow-up: `retrace_exit True + retrace_frac 0.25`, `max_hold {0, 150}`, `fh_filter True`.

Risk/Lucid: as the module README (5-8 micros, ~0.3-0.4 trades/day c_confirm). Decision rule: if `bias_filter + zone_filter` does not lift MAIN PF above 1.2 **and** PRIOR above 1.1 on at least one contract, the C-period entry is retired in favour of spec 2 (same event, better entry).

## 5. microstructure_volume_profile__va_edge_rotation  (time-based value-area edge-to-edge fade on balance days: open inside value, narrow/normal IB, 5-min close rejection at VAL/VAH, POC / far-edge target, trend-day kill switch)

Priority **3**, complexity **4**, instruments MES, MNQ (long side first), MGC last, bar size 5-min on 1-min profile. EQ **2** (pedrobraiti E2E OOS PF 1.41 SPY / 2.06 QQQ on daily bars but bootstrap CI includes 1.0 and the edge needed a volume filter; matiasjuarezau QQQ 5-min: raw 58% WR -8.6%, with trend filter +0.75%, with R:R >= 2 +4.7%; tradealgo 55-65% unsourced). Report section 2, ranked 4 in section 24. Needs spec 1. New module `mp_vafade`.

```
PARAMS: mode='tpm'|'tpo', va_pct=0.70, touch_ticks=2, confirm_bar=5, stop_frac=0.25, tgt_mode='poc'|'far', ib_max_atr=1.0,
        min_vaw_atr=0.15, first_entry='10:30', last_entry='14:30', exit_time='15:30', flat='15:55', max_trades=2, sides='both'|'long',
        kill_frac=0.25, open_filter=True, min_stop_pts, open_type_gate=False (spec 9)
PRE (day d): P = PROFILE[d] (poc, vah, val, vaw); pd_high/pd_low; O930; atr; IB at 10:30.
  skip if any NaN; if open_filter: require val <= O930 <= vah and pd_low <= O930 <= pd_high; require vaw >= min_vaw_atr*atr
  (the POC target must be > 2x costs away: ES vaw ~30-40 pts -> POC ~15-20 pts from the edge); at 10:30 require ib_rng <= ib_max_atr*atr
  (else no trades: trend-day presumption). open_type_gate: require open_type in {auction, rejection} (spec 9).
SIGNALS on B5 bars k with tod[k] >= first_entry, tod[k] + 5 <= last_entry, i_next >= 0, in time order; dead = False:
  kill switch: if close[k] > vah + kill_frac*vaw or close[k] < val - kill_frac*vaw: dead = True (price left value: no more entries today).
  if dead: continue
  LONG: low[k] <= val + touch_ticks*tick and close[k] > val and close[k] < poc           (tested VAL, closed back inside, room to POC)
    stop_px = max(val - stop_frac*vaw, low[k] - tick) [the tighter]; guard: stop_px <= close[k] - min_stop_pts
    tgt_px  = poc (tgt_mode 'poc') | vah ('far')
    place(i_next[k], +1, market, stop_px, tgt_px)
  SHORT mirror at vah (sides=='long' -> skip); one signal per bar; the engine ignores signals while a position is open.
  confirm_bar: 5 (default) | 1 | 15 (resample accordingly; 1 = 1-min close confirmation).
EXITS: stop, target, exit_at(first bar >= exit_time, which=2), forced flat. max_trades_day = max_trades (the published "2 per side"
  cannot be expressed per side; 2 total is the stricter reading).
SESSION: set_session(first_entry, last_entry, flat). RISK: standard block (multi-trade spec).
```
Grid (2 x 2 x 2 x 2 x 2 = 32): `stop_frac {0.25, 0.4}`, `tgt_mode {poc, far}`, `ib_max_atr {0.8, 1.0}`, `sides {both, long}`, `va_pct {0.65, 0.70}`. Follow-up: `mode {tpm, tpo}`, `confirm_bar {1, 5, 15}`, `open_filter False` (control: without the balance filter the report expects losses), `open_type_gate True`.

Risk/Lucid: stop 0.25 x vaw: ES ~8-10 pts ($45), NQ ~40-50 pts ($90); target POC ~0.4-0.5 x vaw (~1:1.5 against) at an expected ~55% -> thin; the `far` target (~1 x vaw, 1:4 reward:risk) at ~35% is the matiasjuarezau v5 shape (+4.7%, MDD 1.7%). 0-2 trades/day on ~55% of days. Day shape is consistency-friendly; the loss cluster is the trend day that opens inside value: the IB gate + kill switch are mandatory and the control cell (`open_filter False`) must lose. If MAIN PF < 1.1 on both contracts with the gates on, the whole VA corner (specs 5-8) is closed, matching the pedrobraiti conclusion.

## 6. microstructure_volume_profile__va_80pct_rule  (Market Profile 80% rule: open outside value, re-entry held for one/two 30-min periods, trade to the far edge or POC)

Priority **2**, complexity **3**, instruments MES first (the published tests are ES), MNQ, bar size 30-min TPO periods. EQ **2** (mypivots: "should be called the 60% rule" on ES; nexusfi ~62%; pedrobraiti 27-67% full traversal; no cost-adjusted P&L). Report section 3, ranked 8. Needs spec 1. Same module as spec 5 (`mp_vafade`, `strategy='rule80'`) or `mp_va80`.

```
PARAMS: mode='tpm'|'tpo', va_pct=0.70, setup='open_outside'|'move_outside', confirm='one_close'|'two_close', confirm_deadline='12:00',
        stop_mode='frac'|'ticks', stop_frac=0.1, stop_ticks=4, tgt_mode='far'|'poc', flat='15:55', max_trades=1, min_vaw_atr=0.15
PRE: P = PROFILE[d]; O930; atr; vaw >= min_vaw_atr*atr.
  setup 'open_outside': O930 > vah -> from_above (short setup); O930 < val -> from_below (long setup); inside -> no trade.
  setup 'move_outside': the first 30-min period A (09:30) closes outside the VA (close_A > vah / < val); then as above.
B30 periods j = A(09:30), B(10:00), C(10:30), D(11:00), E(11:30) while tod[j] + 30 <= confirm_deadline:
  inside_j = val <= close[j] <= vah
  'one_close' (mypivots: first period enters and closes inside, the next opens inside = continuity): first j with inside_j and
     NOT inside_{j-1} (or j == A for open_outside) -> entry at i_next[j] (the open of period j+1).
  'two_close': first j with inside_j and inside_{j+1} -> entry at i_next[j+1].
  side = -1 if from_above else +1.  edge = vah (from_above) | val (from_below); far = val | vah.
  stop_px = edge + (-side)*stop_frac*vaw ('frac') | edge + (-side)*stop_ticks*tick ('ticks'; the "just outside the VA" rule);
    guard min_stop_pts from the entry reference (close of the confirming period).
  tgt_px  = far ('far', the full fill) | poc ('poc').
  place(i_entry, side, market, stop_px, tgt_px). One trade per day.
EXITS: stop, target, forced flat 15:55 (published: no time stop). SESSION: set_session('10:00', confirm_deadline, flat); max_trades_day = 1.
RISK: daily_loss_stop = the single stop in $.
```
Grid (2 x 2 x 2 x 2 = 16): `confirm {one_close, two_close}`, `stop_frac {0.1, 0.25}` (stop_mode frac), `tgt_mode {far, poc}`, `setup {open_outside, move_outside}`. Follow-up: `stop_mode ticks (4)`, `mode tpo`, `confirm_deadline {11:00, 12:00}`.

Risk/Lucid: one trade on ~25-35% of days, stop 0.1-0.25 x vaw ($15-45 MES), target 0.4-1.0 x vaw: 2:1 to 4:1 at the realistic ~40-60% (POC / far). Shape is good; the expectancy per the report is near zero before costs unless the stop is tight, so the `stop_frac 0.1` cells are the ones that matter and they are the ones most exposed to the 1-tick stop-slippage model. Largest day = one far-edge target (~$150-200 MES per micro): consistency-safe at <= 7 micros.

## 7. microstructure_volume_profile__va_acceptance_breakout  (open outside value, acceptance through 10:30, initiative continuation at market or on the first VAH/VAL pullback)

Priority **2**, complexity **3**, instruments MNQ, MES, bar size 1-min (acceptance) + 5-min (pullback). EQ **2** (pedrobraiti BRK OOS PF 1.38 SPY / 1.58 QQQ on daily bars; opening-candle continuation 73.9% NQ (edgeful, 6 months); tradingstats open-above-range single-up 40.7% vs down 33.2%, weak). Report section 4. Mutually exclusive with spec 5 by the open-location filter (same module `mp_vafade`, `strategy='accept'`, or `mp_vabreak`).

```
PARAMS: mode='tpm', va_pct=0.70, accept='no_reentry'|'two_closes', entry='market'|'pullback', pullback_until='12:00', touch_ticks=2,
        stop_frac=0.25, tgt_mult=1.0, trail=False, gap_max_atr=1.2, flat='15:55', max_trades=1, min_stop_pts, fh_filter=False
PRE: P = PROFILE[d]; O930; pd_close; atr. side = +1 if O930 > vah, -1 if O930 < val, else no trade. edge = vah (long) | val (short).
  skip if |O930 - pd_close| > gap_max_atr*atr (large gaps extend less), atr NaN, vaw < 0.15*atr, early_close.
ACCEPTANCE (known at the 10:30 bar):
  'no_reentry': no 1-min bar in [09:30, 10:30) with side*(edge - low/high) >= 0 (long: no low <= vah).
  'two_closes': the 09:30 and 10:00 30-min periods both close on the outside (long: close_A > vah and close_B > vah).
  fh_filter: additionally require fh_dir == side.
ENTRY:
  'market': place(IB.i_end+1 (10:30), side, market, stop_px, tgt_px).
  'pullback': scan B5 bars k with 10:30 <= tod[k], tod[k]+5 <= pullback_until: first bar with side*(edge + side*touch_ticks*tick - low/high)
     >= 0 (long: low[k] <= vah + 2 ticks) and side*(close[k] - edge) > 0 (closed back outside) -> place(i_next[k], side, market, ...).
     If a 5-min bar CLOSES inside the VA before the pullback entry (side*(close - edge) < 0): day done (acceptance failed).
  ref = close of the decision bar. stop_px = edge - side*stop_frac*vaw (guard min_stop_pts; tradealgo's fixed 8 ES / 30 NQ pts is
  ~0.25 x vaw). tgt_px = edge + side*tgt_mult*vaw. trail=True: trail_pts = 0.5*vaw, trail_act_pts = 0.5*vaw (the "runner" after 2/3
  off; the engine cannot scale so the grid runs tgt_mult 0.5 and 1.0 as separate cells instead).
EXITS: stop, target, trail, forced flat. SESSION: set_session('10:30', pullback_until, flat); max_trades_day = 1. RISK: single stop.
```
Grid (2 x 2 x 2 x 2 = 16): `accept {no_reentry, two_closes}`, `entry {market, pullback}`, `tgt_mult {0.5, 1.0}`, `fh_filter {False, True}`. Follow-up: `stop_frac {0.25, 0.4}`, `trail True`, `gap_max_atr {0.8, 1.2}`.

Risk/Lucid: ~20-30% of days qualify; stop 0.25 x vaw, target 0.5-1.0 x vaw (2:1 to 4:1); the day shape is a trend-day participation trade with a defined stop. Largest day = one 1.0 x vaw target (~$150-200 MES / $300-400 MNQ per micro): cap at `tgt_mult 0.5` or <= 5 micros for the consistency rule.

## 8. microstructure_volume_profile__poc_reversion  (prior-session POC reversion after a 0.5 x VA-width excursion on non-trend days; naked POC as an optional target)

Priority **2**, complexity **2** (given spec 1), instruments MES, MNQ, MGC, bar size 5-min. EQ **1** (pedrobraiti REV OOS PF 1.13 SPY / 1.63 QQQ daily; permutation p 0.002 SPY but 0.08 QQQ; LuxAlgo: no dependable naked-POC fill rate). Report section 5. The naked-POC magnet is NOT a standalone entry (open-ended timing); it survives only as `tgt_mode='naked'`. Module `mp_pocrev`.

```
PARAMS: mode='tpm', trig_frac=0.5, stop_frac=0.25, tgt_mode='poc'|'naked', npoc_max_atr=1.0, ib_max_atr=1.0, first_entry='10:30',
        last_entry='14:30', exit_time='15:30', flat='15:55', max_trades=2, sides='both'|'long', min_stop_pts
PRE: P = PROFILE[d] (poc, vaw, npoc list); atr; IB at 10:30: skip the day if ib_rng > ib_max_atr*atr (trend day) or vaw < 0.15*atr.
SIGNALS on B5 bars k, first_entry <= tod[k], tod[k]+5 <= last_entry:
  dist = close[k] - poc
  LONG: dist < -trig_frac*vaw and close[k] > open[k] and close[k] > close[k-1] (a 5-min reversal bar toward the POC)
    stop_px = low[k] - stop_frac*vaw (guard min_stop_pts); tgt_px = poc ('poc')
    'naked': candidates = npoc[d] with poc_j > close[k] and poc_j - close[k] <= npoc_max_atr*atr and not yet touched today
      (touched = any 1-min bar of session d before i_next[k] with low <= poc_j <= high); tgt_px = the nearest; if none -> poc.
    place(i_next[k], +1, market, stop_px, tgt_px)
  SHORT mirror (dist > +trig_frac*vaw, close < open, close < close[k-1]; naked POCs below).
EXITS: stop, target, exit_at(exit_time), forced flat. max_trades_day = max_trades.
SESSION: set_session(first_entry, last_entry, flat). RISK: standard block.
```
Grid (3 x 2 x 2 x 2 = 24): `trig_frac {0.35, 0.5, 0.75}`, `stop_frac {0.25, 0.4}`, `tgt_mode {poc, naked}`, `sides {both, long}`.

Risk/Lucid: stop ~0.25-0.4 x vaw beyond the signal bar (ES $50-80/micro), target 0.5+ x vaw: ~1.5:1 at an unknown hit rate; the report expects "nothing special". Run it once with spec 5's gates; keep it only as a POC-target library test.

## 9. microstructure_volume_profile__ib_open_type_gates  (reusable day-type gates: IB width tiers, first-formed bias, ending zone, first-hour colour, Dalton open types)

Priority **3** (gate consumed by specs 2-8, 12, 13), complexity **2**, instruments all, bar size 1-min / 5-min / 30-min. EQ **3** for the IB-width tiers (steady-turtle NQ 1,586 sessions: narrow tercile 41.1% reach 1x extension vs 15.5% wide; tradingstats smallest-20% IB 99.3% break / 84.5% median extension), **1-2** for the open types (no published stats; pedrobraiti "day-types do not predict continuation"). Report sections 8 and 12. Not a strategy: `gates(df1, contract) -> DataFrame indexed by day_id`, all columns known by 10:30 (open types by 10:00).

```
COLUMNS (day d):
  ib_tier = 'narrow' (ib_rng < 0.5 atr) | 'normal' (< 1.0) | 'wide' (< 1.5) | 'extreme' ; ib_pct60 = percentile of ib_rng among the
    trailing 60 sessions' IB ranges (sessions < d) ; low_first, bias, ez (section 0) ; fh_dir
  OPEN TYPE (Dalton, 09:30-10:00; ATR = ATR14d; VA from PROFILE[d]; thresholds exc=0.25, auc=0.20, cl=0.25):
    bars 09:30-09:59; o = O930; A = the 30-min bar [09:30, 10:00); up_exc = max(high) - o; dn_exc = o - min(low)
    recross = any bar with tod >= 09:35 whose [low, high] contains o
    open_drive      = not recross and (A.close - A.low)/(A.high - A.low) >= 1 - cl (if A.close > o; mirror for down) and
                      (A.close > vah or A.close < val)
    open_test_drive = (min(low) over 09:30-09:59 <= val or max(high) >= vah or touches pd_high/pd_low within the first 30 min)
                      and the bar closes through o on the other side with |A.close - o| >= exc*atr
    open_rej_rev    = max(up_exc, dn_exc) >= exc*atr and recross and |A.close - o| < exc*atr
    open_auction    = max(up_exc, dn_exc) < auc*atr and recross
    open_type = first match in [drive, test_drive, rej_rev, auction] else 'other'
USAGE: specs 2, 3, 4, 7 accept `tier_allow` (default {narrow, normal, wide}) and `open_type_allow` (default all; test {drive, test_drive});
  specs 5, 6, 8 accept `open_type_allow` {rej_rev, auction} and `tier_allow` {narrow, normal}. Each spec's follow-up grid turns one gate
  on at a time and reports the change in positive-day share and worst day, not just PF: a gate that raises PF by removing 60% of trades
  is not a gate, it is a sample.
VALIDATION: print the open-type mix (expect drive ~15%, auction ~35%) and, per type, the share of sessions whose close is beyond
  the IB (the only objective check of Dalton's claim available to us).
```
Grid: none (consumed as a flag by other specs).

Risk/Lucid: n/a; its value is in the daily P&L distribution of the gated specs.

## 10. microstructure_volume_profile__gc_ib_pullback  (gold IB breakout with a 25%-of-IB pullback limit entry, 60% stop, 50% target; trailing single-break-rate regime gate; tradethatswing / edgeful)

Priority **2**, complexity **3**, instruments MGC only (full GC stops are $1,800-2,400/contract: impossible under a $2,000 EOD trail), bar size 1-min. EQ **2** (vendor: 142 trades/250 days, WR ~50%, avg win $1,100 / loss $600, +411% on $10k, MDD 25%; edgeful WR 65.8% PF 1.94 over 12 months; **author withdrew it in July 2026** as the single-break rate fell to 50/50). Report section 10, ranked 9. Existing `orb_ib_c` on MGC (pit-anchored 08:20 IB) is dead (PF 0.80 MAIN): this spec is the 09:30-anchored pullback version with the regime gate, which is what the sources traded. Module `mp_gcib`.

```
PARAMS: ib_start='09:30'|'08:20', ib_minutes=60, entry_frac=0.25 (edgeful: 0.01), stop_frac=0.60, stop_ref='entry'|'level'
        (tradethatswing: 60% of IB from the ENTRY; edgeful: 60% retrace back into the IB from the LEVEL), tgt_frac=0.5 (from the broken
        level), last_entry='12:30' (pit: '11:30'), flat='15:55' (pit: '13:25'), gate_rate=0.70, gate_n=40, atr_rising=False,
        max_trades=1, sides='both', ib_min_atr=0.15, ib_max_atr=1.5
ATR14d for the 09:30 anchor = daily_atr on 09:30-16:00 XAUUSD bars (rth=('09:30','16:00')); for 08:20 the pit ATR.
REGIME GATE (sessions < d): single_break[s] = exactly one of {max(high) > ib_high, min(low) < ib_low} over [ib_end, rth_close) of session s.
  rate = mean(single_break over the last gate_n sessions); trade only if rate >= gate_rate (0 = gate off). atr_rising: ATR14d[d] > ATR14d[d-20].
PRE: IB; skip if atr NaN, tier extreme, ib_rng < ib_min_atr*atr, gate fails, early_close.
SCAN 1-min bars from IB.i_end+1 while tod < last_entry: first bar k with high > ib_high (up) or low < ib_low (down) (both -> nearer open).
  side, level as spec 2. i0 = k+1.
  entry_px = level - side*entry_frac*R + side*tick?  NO: the limit must be touched from above (long), so entry_px = level - side*entry_frac*R
    (fills when low <= entry_px - tick; a 1-tick-deeper fill is the conservative reading of "limit at 25% inside").
  stop_px = entry_px - side*stop_frac*R ('entry') | level - side*stop_frac*R ('level'); guard min_stop_pts (1.5 GC pts)
  tgt_px  = level + side*tgt_frac*R
  place(i0, side, entry_px, kind='limit', valid_bars = hm(last_entry) - tod[i0], stop_px, tgt_px)
  If price closes back through the opposite IB edge before a fill: the resting order simply expires or fills into a reversal (as published).
EXITS: stop, target, forced flat (published: hold to the close; grid max_hold {0, 240}). max_trades_day = 1.
SESSION: set_session(ib_end, last_entry, flat). RISK: daily_loss_stop = 0.6*R_median*$10 (single stop).
```
Grid (2 x 2 x 2 x 3 = 24): `ib_start {09:30, 08:20}`, `entry_frac {0.25, 0.01}` (paired with `stop_ref {entry, level}`), `tgt_frac {0.25, 0.5}`, `gate_rate {0, 0.6, 0.7}`. Follow-up: `atr_rising True`, `max_hold 240`, `sides long` (2025 gold trend).

Risk/Lucid: GC 09:30 IB median ~$25-35 in 2025-26 -> stop 0.6R ~$15-20 = $150-200 per MGC micro, target 0.75R from entry ~1.25:1 at a claimed ~50-65%. At 5 micros a stop is ~$900 (45% of the MLL distance): the Lucid scan will land at 3-5 micros. The 2025 numbers were the gold trend; the gate must be on and the PRIOR period (2023-24) must be >= 1.1 or this is a regime bet, not a strategy. Expect MAIN to look good through 2025 and decay in 2026 (the author's own OOS).

## 11. microstructure_volume_profile__vwap_two_window_trend  (Zarattini-Aziz session-VWAP trend flip restricted to 09:35-12:00 and 15:00-15:55, 5-min close confirmation, disaster stop, daily caps; TWAP proxy)

Priority **3**, complexity **3**, instruments MNQ (QQQ proxy), MES, bar size 5-min on a 1-min TWAP. EQ **3** for QQQ (SSRN 4631351: 2018-2023 +671%, Sharpe 2.1, MDD 9.4%, 21,967 trades, 17% hit, gain:loss 5.67; P&L concentrated 09:30-12:00 and 15:00-16:00; no OOS, no slippage), **1** for net futures tradability (Mesfin 2026: a 2-pt NQ friction floor kills most sub-2-pt 5-min signals). Report section 13, ranked 5. **Data gap**: true VWAP needs volume; `session_vwap` = equal-weighted typical price (TWAP). Zarattini-Barbon-Aziz report the VWAP stop doubling Sharpe, so proxy error matters: run the second proxy `twap_w` (1-min bars weighted by 1/range, which up-weights quiet minutes less) as a grid cell. Module `mp_vwaptrend`.

```
PARAMS: confirm_bar=5 (paper: 1), windows='two'|'all' (two: [09:35, 12:00) and [15:00, 15:55); all: [09:31/09:35, 15:55)), lunch_flat=True
        (exit at 12:00 when windows='two'), dead_band=0.0 (x ATR5m14; a close must be beyond TWAP by this to count), hard_stop_atr=0.5
        (x ATR14d disaster stop; paper none), tgt_cap_atr=0.0 (0 = none; 0.8 = hard target cap for the consistency rule), proxy='twap'|'twap_w',
        cooldown=10 (min; see note), flat='15:55', max_trades=0 (unlimited; the daily stops govern), dls_mult=1.0, dps_mult=1.0
TWAP on 1-min RTH bars from 09:30 (proxy 'twap_w': cumsum(tp*w)/cumsum(w), w = 1/max(high-low, tick)). B = resample(confirm_bar).
PER SESSION, pos = 0; for each bar k of B in time order with i = B.i_next[k] >= 0, tod[k]+confirm_bar <= 15:55:
  in_window = (windows=='all') or tod[k]+confirm_bar in [09:35, 12:00) or in [15:00, 15:55)
  tw = TWAP at B.i_last[k]; dev = close[k] - tw; desired = +1 if dev > dead_band*ATR5m14[k] else -1 if dev < -dead_band*ATR5m14[k] else pos
  if not in_window:
    if pos != 0 and lunch_flat: exit_at(i, which=2); pos = 0        (12:00 flat; re-enters at the first 15:00-window close)
    continue
  if desired != pos:
    if pos != 0: exit_at(i, which=pos)                                 (close the opposite position at the open of bar i)
    stop_px = tw - desired*hard_stop_atr*ATR14d  (NaN if hard_stop_atr == 0); tgt_pts = tgt_cap_atr*ATR14d or NaN
    place(i, desired, market, stop_px, tgt_pts)                        (fills at bar i if flat, e.g. after a stop-out)
    if i+1 in the same session and tod[i+1] < 15:55: place(i+1, desired, market, same stop/tgt)
      (the engine ignores a signal on the bar where a position was just closed, so the reversal fills one bar later: the flip-system
       pattern from the bot_popular_indicators specs)
    pos = desired
  The exit rule IS the flip (a confirm_bar close on the other side of TWAP); there is no other target in the paper.
cooldown: the engine does not expose fills to generate(); the 10-minute no-re-entry-after-stop rule is approximated by dead_band
  (grid) and is otherwise NOT implemented. Document.
SESSION: set_session('09:35' (confirm_bar 5) / '09:31' (1), '15:55', '15:55'); daily_loss_stop / daily_profit_stop per the Lucid block
  (mandatory here: this is the only spec with an uncapped day); max_trades_day 0.
```
Grid (3 x 2 x 2 x 2 = 24): `confirm_bar {1, 5, 15}`, `windows {two, all}`, `dead_band {0, 0.1}`, `hard_stop_atr {0.3, 0.6}`. `confirm_bar=1, windows='all', dead_band=0` is the paper (the control: expected to lose on micros after costs). Follow-up: `proxy twap_w`, `tgt_cap_atr {0, 0.8}`, `dps_mult {1.0, 1.5}`, `lunch_flat False`.

Risk/Lucid: the raw version makes ~15 flips/day with a 17% hit ratio: at $2.30/RT on MNQ that is ~$35/day of friction per micro before any edge, so `confirm_bar 1` must lose and `confirm_bar 5/15` with `windows two` (~2-4 flips/day) is the only live cell. The profit comes from trend days (QQQ best day +6.5% of equity): the `daily_profit_stop` and `tgt_cap_atr` are what make it consistency-legal, and they also remove part of the edge; report both. Positive-day share is the metric to watch (the paper's distribution is ~45% positive days with a fat right tail, the opposite of what the payout rule wants).

## 12. microstructure_volume_profile__vwap_band_fade_gated  (session-VWAP +/-2 sigma rejection fade, long-biased, ADX < 25 / opening-range / distance-from-open gates, two windows; crosstrade rule sheet + extremes base rates)

Priority **3**, complexity **3**, instruments MES, MNQ (long first), MGC (pit) last, bar size 5-min on a 1-min TWAP. EQ **2** (crosstrade: 55-65% WR / PF 1.2-1.6 with the gates, 45% without, no sample; nullh0 Micro WTI long-only: 505 trades, WR 62%, Sharpe 4.9, 13/15 walk-forward windows positive, author declined to deploy; tradingstats extremes: < 0.3 ATR from the open revert 85%, > 1.0 ATR ~20%). Report section 14, ranked 6; companion rules in intraday_mean_reversion.md sections 1-2. **Data gap**: VWAP and sigma need volume -> TWAP + cumulative std of typical price (`band_mode 'sigma'`) or `k_atr x ATR5m14` (`'atr'`); both flagged. The existing `twap_revert` module (limit entries at a rolling-std band, no gates, untested) is the ungated control cell. Module `mp_vwapfade`.

```
PARAMS: band_mode='sigma'|'atr', k_sig=2.0, k_atr=2.0, rej='pin'|'any', stop_atr=1.0 (x ATR5m14 beyond the signal-bar extreme),
        tgt_mode='vwap'|'half', max_hold=90, adx_max=25, or_mult=2.0, dist_max_atr=1.0, windows=[('10:00','11:30'), ('13:30','14:30')],
        sides='long'|'both', max_trades=3, flat='15:55', min_stop_pts
TWAP, SIG on 1-min RTH bars (section 0). B5; ADX5m14 (continuous series; NaN -> no trade); ATR5m14.
PER DAY GATES: or_rng[d] = high-low of 09:30-10:29; base[d] = mean(or_rng over the 20 sessions < d); skip the day if or_rng > or_mult*base.
SIGNALS on B5 bars k with tod[k]+5 inside a window, i_next >= 0, B5.tod >= 10:00:
  tw = TWAP_k; band = k_sig*SIG_k ('sigma') | k_atr*ATR5m14[k] ('atr'); require band >= 2*cost_pts (ES 1.5, NQ 2.3, GC 0.7) so the
    target pays costs.
  gates per bar: ADX5m14[k] <= adx_max ; |close[k] - O930| <= dist_max_atr*ATR14d (extremes study: deep excursions do not revert).
  LONG: low[k] <= tw - band (the bar traded >= 2 sigma below) and rejection: 'any' -> close[k] > open[k] ; 'pin' -> close[k] > open[k]
    and (close[k] - low[k]) >= 0.6*(high[k] - low[k]) (pin / engulfing proxy) and close[k] > tw - band (closed back inside the band).
    stop_px = low[k] - stop_atr*ATR5m14[k] (guard min_stop_pts); tgt_px = tw ('vwap') | close[k] + 0.5*(tw - close[k]) ('half')
    place(i_next[k], +1, market, stop_px, tgt_px, max_hold)
  SHORT mirror (sides=='both'); Friday 14:30+ is outside the windows by construction; FOMC 14:00 is inside the second window on 8 days/yr
    (no calendar; accept).
EXITS: stop, target, max_hold, forced flat. max_trades_day = max_trades. SESSION: allow_entry only inside the two windows (set the array
  directly: set_session('10:00', '14:30', flat) then allow_entry &= ~((tod >= 11:30) & (tod < 13:30))). RISK: standard block.
```
Grid (2 x 2 x 2 x 2 x 2 = 32): `k_sig {1.5, 2.0, 2.5}` (sigma) or `k_atr {1.5, 2.0}` (atr) via `band_mode {sigma, atr}`, `rej {any, pin}`, `tgt_mode {vwap, half}`, `sides {long, both}`, `adx_max {25, 99(off)}`. Follow-up: `stop_atr {0.75, 1.0, 1.5}`, `max_hold {60, 120}`, `dist_max_atr {0.6, 1.0}`, `or_mult {1.5, 2.0}`.

Risk/Lucid: 1-3 trades/day, stop ~1 x ATR5m (ES ~6-8 pts $35, NQ ~35-45 pts $80), target to VWAP (~0.6-1.2 x the stop) at a claimed 55-65%: thin but consistent if true; the loss tail is the trend day, which is why `adx_max 99` must be worse than 25 for the spec to be believed. Largest day ~3 targets ($100-150/micro): consistency-safe at 10 micros.

## 13. microstructure_volume_profile__vwap_pullback_continuation  (VWAP bounce on qualified trend days: first pullback to VWAP after 10:30 with a 5-min close back above, stop under VWAP, target session high / sigma band, optional VWAP-close trail)

Priority **3**, complexity **3**, instruments MNQ, MES, bar size 5-min on a 1-min TWAP. EQ **2** (SPY hourly RSI(2)-at-VWAP variant: 254 trades, WR 45.7%, PF 1.69, MDD 0.53%; VWAP-as-trailing-stop doubled Sharpe 0.61 -> 1.24 on SPY 2007-2024 (Zarattini-Barbon-Aziz); vendor WR ranges unsourced). Report section 15, ranked 7. Trend-day complement of spec 12; shares the IB gate. **Data gap**: TWAP proxy (the slope test is robust to it). Module `mp_vwappull`.

```
PARAMS: qual='vwap'|'ib', touch_atr=1.0 (x ATR5m14 tolerance for "touches VWAP"), stop_mode='atr'|'sigma', stop_atr=1.0, stop_sig=0.5,
        tgt_mode='hod'|'sigma'|'rr', rr=1.5, min_tgt_atr=0.3 (x ATR5m14: skip if the session high is closer than this),
        vwap_exit=True (exit on a 5-min close through TWAP), first_entry='10:30' (qual 'ib': '11:00'), last_entry='14:30', flat='15:55',
        max_trades=2, sides='both'|'long', min_stop_pts
TWAP, SIG on 1-min bars; B5; ATR5m14; IB; low_first; C-period close (10:30-10:59 bar).
QUALIFY (up-trend; mirror for down):
  'vwap': every B5 close with tod in [10:00, 10:30) > TWAP_k and TWAP(10:29 bar end) > TWAP(09:59 bar end) ; qualifies at 10:30.
  'ib':   low_first and C-period close > ib_high ; qualifies at 11:00.
ENTRY: scan B5 bars k with first_entry <= tod[k], tod[k]+5 <= last_entry, after qualification:
  if close[k] < TWAP_k (a 5-min close through VWAP): trend invalidated -> no more entries today (and vwap_exit fires if in a position).
  LONG: low[k] <= TWAP_k + touch_atr*ATR5m14[k] and close[k] > TWAP_k and close[k] > open[k]
    stop_px = TWAP_k - stop_atr*ATR5m14[k] ('atr') | TWAP_k - stop_sig*SIG_k ('sigma'); guard min_stop_pts
    hod = max(high) over session d bars up to B5.i_last[k]; tgt_px = hod ('hod'; skip if hod - close[k] < min_tgt_atr*ATR5m14)
          | TWAP_k + 1.0*SIG_k ('sigma'; skip if below close) | close[k] + rr*(close[k] - stop_px) ('rr')
    place(i_next[k], +1, market, stop_px, tgt_px)
  vwap_exit: at every later bar j with close[j] < TWAP_j: exit_at(i_next[j], which=+1) (side-specific, harmless when flat).
  One pullback per trend leg: after an entry no new signal until a bar closes above the entry bar's high (new leg) -> approximated by
  max_trades_day = 2 and the engine's one-position rule.
EXITS: stop, target, vwap_exit, forced flat. SESSION: set_session(first_entry, last_entry, flat). RISK: standard block.
```
Grid (2 x 2 x 3 x 2 = 24): `qual {vwap, ib}`, `stop_mode {atr(1.0), sigma(0.5)}`, `tgt_mode {hod, sigma, rr(1.5)}`, `sides {both, long}`. Follow-up: `touch_atr {0.5, 1.0}`, `vwap_exit False`, `rr 2.0`.

Risk/Lucid: stop ~1 x ATR5m below VWAP (ES $35-50, NQ $70-100 per micro); target at the session high (~1-2 x the stop): expected ~50-55% at 1.3-1.8R if the vendor numbers hold. 0-2 trades/day on the ~35-40% of days that qualify. Largest day ~2 targets: consistency-safe.

## 14. microstructure_volume_profile__avwap_prior_extremes  (anchored TWAP from the prior day's high and low bars: dual-AVWAP breakout, and the AVWAP level defence trade)

Priority **1**, complexity **3**, instruments MES, MNQ, bar size 5-min on 1-min anchored TWAP. EQ **1** (no published statistics for (a)/(b); the CPI-anchor test (c) is 11 trades and is dropped: needs a CPI calendar and fires ~1/month). Report section 16. **Data gap**: anchored TWAP of typical price for anchored VWAP (flagged). Test only if spec 13 works (it is spec 13 with a free anchor). Module `mp_avwap`.

```
PARAMS: variant='dual'|'level', confirm_bar=5, stop_atr=1.0, tgt_mode='pd_extreme'|'rr', rr=1.5, first_entry='10:00', last_entry='14:30',
        flat='15:55', max_trades=2, sides='both', min_stop_pts, swing_atr=1.0, gap_atr=0.5
ANCHORS (known at 09:30): i_pdh / i_pdl = 1-min index of session d-1's RTH high / low bar (prior_day_stats + a scan of d-1).
  AVWAP_H[i] = cumulative mean of typical price from i_pdh through i (crossing the session boundary; evening bars included: the
  anchored VWAP is continuous); AVWAP_L likewise from i_pdl. Both are causal.
'dual' (forextester): on B5 bars k in [first_entry, last_entry): long on the first close > AVWAP_H_k when the previous close <= it;
  short on the first close < AVWAP_L_k; reverse on the opposite signal (flip pattern of spec 11); stop = the other AVWAP (stop_px) or
  stop_atr*ATR5m14 (the tighter, guard min_stop_pts); tgt 'pd_extreme' = pd_high (long) / pd_low (short), skip if < 0.3 ATR5m away; 'rr'.
'level' (Shannon): anchor = the latest swing extreme of >= swing_atr*ATR14d (from the 5-min series, sessions <= d-1 plus today's bars
  <= k) or the 09:30 bar when |gap| >= gap_atr*ATR14d; direction = sign(close_k - anchor_price); entry = a B5 bar whose low (long)
  touches the AVWAP within 1 tick and closes above it; invalidation = a B5 close through the line (exit_at); stop_atr beyond the line;
  target pd_high / pd_low in the anchor's direction.
EXITS: stop, target, line-close exit, forced flat. SESSION: set_session(first_entry, last_entry, flat). RISK: standard block.
```
Grid (2 x 2 x 2 = 8): `variant {dual, level}`, `tgt_mode {pd_extreme, rr}`, `stop_atr {0.75, 1.25}`.

Risk/Lucid: as spec 13. Expect nothing beyond spec 13; it exists so the "anchored" claim is tested once and closed.

## 15. microstructure_volume_profile__poor_high_single_print  (prior-day structure as entry/target rules: poor-high repair, tail fade, single-print traversal; extreme-distance base-rate gates)

Priority **1**, complexity **3** (given spec 1), instruments MES, MNQ, bar size 5-min + 30-min TPO. EQ **1** for the Dalton rules (no backtest anywhere), **3** for the extreme base rates (tradingstats 2019-2026: extremes < 0.3 ATR from the open revert 85%, > 1.0 ATR ~20%; lows fade 61% vs highs 55%). Report section 11. Three rules in one module `mp_structure`, `rule {repair, tail, single}`; the useful output is whether `poor_high` / `sp_zones` improve the targets of specs 2, 7, 13 (`tgt_mode='structure'`), not the standalone P&L.

```
PRE: P = PROFILE[d] (s_high, s_low, poor_high, poor_low, tail_high, tail_low, sp_zones, poc, vaw); atr; O930; TWAP.
rule 'repair' (poor high is a magnet): require poor_high (prior session high touched in >= 2 TPO periods, no tail) and O930 < s_high and
  s_high - O930 <= 1.0*atr. Trend qualification = spec 13 'vwap' at 10:30 (up). Entry = spec 13's pullback entry; tgt_px = s_high + 2 ticks;
  stop_px = entry_ref - 0.25*vaw (guard). Mirror for poor_low with a down-trend. Flat 15:55, 1 trade/day.
rule 'tail' (excess fades): require tail_high; on B5 bars k >= 10:00: high[k] >= s_high - 2 ticks and close[k] < s_high (rejection at the
  tail) -> short at i_next, stop_px = s_high + 2 ticks (guard min_stop_pts -> stop = max(s_high + 2 ticks, close + min_stop)), tgt_px = poc.
  Distance gate: skip if s_high - O930 > 1.0*atr (deep extremes do not revert) ; prefer s_high - O930 <= 0.3*atr (grid dist_max_atr {0.3, 1.0}).
rule 'single' (single-print traversal): for each zone (zl, zh) in sp_zones with zh - zl >= 0.1*atr: on the first B5 close inside the zone
  after 10:00 entering from below (prev close < zl, close in [zl, zh]): long, tgt_px = zh, stop_px = zl - 0.1*vaw (guard); from above mirror.
EXITS: stop, target, exit_at 15:30, forced flat. max_trades_day = 2. SESSION: set_session('10:00', '14:30', '15:55'). RISK: standard block.
```
Grid (3 x 2 x 2 = 12): `rule {repair, tail, single}`, `dist_max_atr {0.3, 1.0}`, `sides {both, long}`.

Risk/Lucid: as spec 5. Run once; promote only `tgt_mode='structure'` into the other specs if the targets are hit more often than POC.

## 16. microstructure_volume_profile__gc_poc_signal_candle  (prior-session POC break with a >= 70%-body signal candle, fixed 1R stop / 2R target, one trade per window; XAUUSD V7/V8 transferred to MGC)

Priority **1**, complexity **2** (given spec 1), instruments MGC, bar size 5-min. EQ **2** (honest, tiny: V7 59 trades PF 1.19, OOS PF 1.00; V8 31 trades PF 1.88 with a filter chosen in-sample; medium costs turned -18.7R into -33.5R). Report section 22. Only the signal-candle-through-POC rule is transferable. Module `mp_gcpoc`.

```
PARAMS: body_min=0.70, poc_dist_max=0.20 (V8: |entry - poc| / |entry - stop| <= 0.20; 0 = off), stop_mode='atr'|'bar', stop_atr=0.5 (x ATR5m14),
        rr=2.0, windows=[('08:25','09:25')] (the source's US-open window in ET; grid adds ('10:00','11:30')), flat='13:25', max_trades=1
PRE: P = PROFILE[d] built from the prior completed GC session (src 08:20-13:30 pit by default; grid 'full' = the 18:00-17:00 session).
SIGNAL on B5 bars k inside a window: body = |close - open| / max(high - low, tick) >= body_min ; the bar closes through the POC
  (open[k] < poc <= close[k] -> long; mirror short). entry ref = close[k]. stop = ref - stop_atr*ATR5m14 ('atr') | low[k] - tick ('bar');
  guard min_stop_pts 1.5. R = ref - stop. V8 filter: skip if |ref - poc| / R > poc_dist_max (entry too far past the POC).
  tgt_px = ref + rr*R. place(i_next[k], side, market, stop_px, tgt_px). One trade per window.
EXITS: stop, target, forced flat. SESSION: allow_entry inside the windows only; flat 13:25 (pit) / 15:55 (full). RISK: single stop.
```
Grid (2 x 2 x 2 x 2 = 16): `poc_dist_max {0, 0.2}`, `stop_mode {atr, bar}`, `rr {1.5, 2.0}`, `windows {us_open, us_open+mid}`.

Risk/Lucid: ~0.3 trades/day, 1R ~0.5 ATR5m (~$30-50/MGC micro), 2R target at a claimed ~40-50%: positive only if the hit rate holds; the source's own OOS is flat. Run once.

## 17. microstructure_volume_profile__gapfade_poc_target  (parameter on the existing `mr_gapfade` module: prior-session POC as the second target when the open is outside the prior value area)

Priority **2**, complexity **1**, instruments MNQ (the module's only live contract), MES, bar size 1-min. EQ **2** (edgeful NQ gaps < 0.4%: full fill 92.9%; gaps >= 0.4% full fill 26.7% but 25%-fill 77.3%; the prior close sits inside the prior VA within ~0.3 x vaw of the POC). Report section 21; the gap trade itself is intraday_mean_reversion's and `results/mr_gapfade` is marginal on MNQ.

```
NEW PARAMS on strategies/mr_gapfade.py: tgt_mode='close' (published) | 'poc' | 'nearer' ; profile from spec 1 (tpm).
  'poc':    target = PROFILE[d].poc instead of prior_close (a return-to-value target; farther on gap-ups above value, nearer when the
            prior close sits beyond the POC).
  'nearer': target = whichever of {prior_close, poc} is nearer to the open (a 25%-fill-style partial for large gaps).
  Only when the open is OUTSIDE [val, vah] (tgt_gate=True); inside -> the published rule.
Everything else (gap size filter, 09:35 entry, stop, 11:00 exit) unchanged.
```
Grid: the module's grid x `tgt_mode {close, poc, nearer}`.

Risk/Lucid: as `results/mr_gapfade/README.md`.

---

## 18. Dropped or folded (and why)

| Report section | Decision |
|---|---|
| 17 Cumulative delta (CVD) divergence at a level | **Dropped.** Needs bid/ask-classified volume; the price-only "CVD" (sum of close-location x range) is a momentum oscillator, not delta, and the academic ES evidence puts flow predictability at the one-second horizon. Not faithful; not approximated. |
| 18 Absorption / exhaustion (footprint) | **Dropped as a strategy.** Per-price bid x ask volume required. The candle-shape proxies (1-min range >= 1.5 x ATR closing within 20% of its open at a level; 5-min range >= 2 x ATR closing in the back 30% at a new extreme) do not measure absorption; they survive only as the `rej='pin'` confirmation cell in spec 12 and the `confirm='wick'` cell in spec 2. |
| 19 Footprint stacked imbalances | **Dropped.** No OHLC approximation exists. |
| 20 NYSE TICK extremes | **Dropped.** Breadth data not in the data set; no OHLC proxy (a 1-min z-score is a different signal already covered by the mean-reversion family). |
| 5(b) Naked POC magnet as an entry | Folded into spec 8 as `tgt_mode='naked'`; open-ended timing makes it unusable as a day-trade entry. |
| 16(c) CPI-anchored AVWAP | Dropped: needs a CPI calendar (none in the data), 11 trades in 14 months, ~1/month is below the payout cadence. |
| 11 Dalton rules as standalone | Spec 15 exists only to test them as target logic; EQ 1. |
| 13 Raw always-in VWAP flip (1-min, all day) | Kept only as the control cell of spec 11 (`confirm_bar 1, windows all`); expected to lose after micro-futures friction. |
| 10 Full-size GC | Dropped; MGC only (spec 10): a 60%-of-IB stop on GC is $1,800-2,400 per contract. |
| 8 IB width gate as a strategy | Infrastructure only (spec 9). |
| Day-of-week filters (Wednesday double-break, Wed/Thu VWAP) | Not specced: in-sample vendor cuts; `mr_ibfail` found Wednesday worst on all four contract/period combinations but declined to adopt a one-weekday filter. Diagnostics only. |
| News-day skips (FOMC/CPI/NFP/ISM) | Not implemented anywhere (no calendar); documented in each spec. |

## 19. Notes for the backtest agents

- **Order of work**: spec 1 (profile builder, with the validation printouts) and spec 9 (gates) first because specs 5-8, 15-17 need them; then spec 2 (the family's one priority-5 idea: a resting limit at the broken IB level, 10:30-12:00, 0.25R stop) and spec 3 (ending-zone limit entries), which share the IB machinery with the existing `orb_ib_c`; spec 4 is a parameter pass on that module and runs in minutes. Specs 11-13 (VWAP corner) next, as one module family with a shared TWAP/sigma helper. Specs 5-8 after; 10, 14-17 last.
- **Base-rate replication before P&L**: for spec 2 print, on 2015-2026 ES/NQ, the reach / return / continue rates at 1.1x and 1.2x and compare with the tradingstats numbers (91% / 87-90% / 71-77%). For spec 3 print the low-first -> high-breaks rate and the ending-zone 0-25% rate over 2015-2026 (vendor: 78% / 86%). If our data does not reproduce the base rates within ~5 pp, the problem is the implementation, not the market; if it reproduces them and the P&L is still negative, the edge is inside costs and the spec is closed.
- **Cost stress**: every live cell must survive `--slip 2` with PF >= 1.1 on MAIN and keep its sign on PRIOR; limit-entry specs (2, 3, 10) are tested with `through_ticks 2` as well (the fill assumption is the whole edge of a resting-limit entry).
- **Consistency and payout checks**: report `largest_day_share`, positive-day share and the count of days >= $150 at the `lucid_scan` size; the family's preferred cells are the ones with the highest positive-day share, not the highest PF (spec 2 `tgt_r 0.3`, spec 3 `tgt_ext 0.1`, spec 12 `tgt_mode half`).
- **Stacking**: specs 2/3/4 occupy 10:30-13:00 on the same contract, spec 12 and 13 10:00-14:30, spec 11 the open and the close; combine across contracts (MNQ spec 2 + MES spec 3 + MGC spec 10) through `backtest.portfolio_opt`, never two IB specs on one contract in one run (one position at a time).
- **Walk-forward**: `backtest.walkforward --is_months 12 --oos_months 3 --start 2015-01-01` for specs 2, 3, 4 (the base rates exist from 2015); 2019 for the VWAP specs; the VA specs from 2019 (profile fidelity on thinner early data is untested).
