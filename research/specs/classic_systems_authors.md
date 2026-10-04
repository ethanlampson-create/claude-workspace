# Specs: Classic published trading systems and author methods, for the Lucid 50K LucidFlex backtest

Source report: `/home/user/claude-workspace/research/families/classic_systems_authors.md` (sections 1-30; section 30 lists the
F1-F7 first parameter sets that the specs below formalise). Engine contract: `/home/user/claude-workspace/docs/STRATEGY_GUIDE.md`,
`backtest/engine.py` (`Intents.place / set_session / exit_at`, `max_trades_day`, `daily_loss_stop`, `daily_profit_stop`), helpers
in `strategies/common.py` (`atr, ema, sma, rsi, adx, opening_range, overnight_range, daily_atr, prior_day_stats, session_info,
vix_lag1`) and `backtest.data` (`load_1m, resample(df1, N, rth_only=True) -> i_next, daily_bars(df1, rth_only=True) -> i_first`).

**State of play before running anything.** Four modules from other families already implement rules that belong to this
family; their results set the prior for the specs below and are NOT re-run here:

| module (family) | classic rule it implements | status (per micro, MAIN 2025-01..2026-09 / PRIOR 2023-24) |
|---|---|---|
| `strategies/orb_crabel.py` (orb_session) | Crabel stretch ORB, NR7/ID setups, 2T reverse stop | published spec MNQ PF 1.19 / 1.32 but intraday DD $5k per micro (unusable); best cell (mult 1.5, cutoff 10:30, stop min(2T, 0.25 ATR), rr 1.5) PF 1.25 / 1.39, 323 trades, Lucid 5 micros +$807/eval point estimate, lower bound -$98 -> **not recommended**; setup filters nr7 / nr4_or_id did not beat `none`. MES, MGC dead. |
| `strategies/mr_pdrange.py` (intraday_mean_reversion) | Williams Oops (`entry='stop'`, buy stop at PDL after an open below it) | **dead after walk-forward**: OOS 2025-26 stream has 12 trades; in-sample MNQ PF 1.39 / 1.56 on 47 / 53 trades; MES dead. The edge is real but too rare to carry an evaluation. |
| `strategies/mr_gapfade.py` (intraday_mean_reversion) | Capstone-style ES gap fill toward the prior close (09:35 entry) | MES **dead** (PF 0.79 MAIN); MNQ marginal (PF 1.56 / 1.22, 114 trades, 10 micros +$330/eval, monthly pass rate bimodal). Confirms the Capstone ES GAPF decay. |
| `strategies/vb_orbp.py` (volatility_breakout) | Williams volatility breakout, one-sided (open +/- k x prior range), `bias='down_close_long'` already available | grid run; see `results/vb_orbp/final.json`. |

Sibling specs that already formalise members of this family (not duplicated here; this file only adds what they lack):
`trend_momentum__holy_grail_pullback` (Street Smarts Holy Grail), `trend_momentum__williams_volbreak` and
`volatility_breakout__orbp_midpoint_capped / compression_orbp` (Williams VB, Crabel NR setups), `orb_session__orb_close_confirm_capped`
(Bernstein 30-min breakout), `intraday_mean_reversion__turtle_soup_pd_recross` (Unger Strategy 1 / prior-day Turtle Soup),
`intraday_mean_reversion__session_low_limit_dip` (Unger Strategy 2), `intraday_mean_reversion__eighty_twenty_filter` (80-20 setup),
`calendar_seasonal_structural__gold_clock_legs` (Unger gold time-of-day bias), `bot_popular_indicators__chandelier_ema200_flip`
(LeBeau chandelier), `bot_popular_indicators__supertrend_session` / `psar_ma_squeeze_confluence` (Wilder PSAR).

What this family adds that no sibling has: (1) the **author setup filters** (Williams down-close / TDW, ADX Gapper, 80-20, Meander
band) as one switchable module on the prior-day-extreme stop re-entry; (2) **daily reversal-bar patterns** (Smash Day naked /
hidden, Whiplash, Penfold key reversal) as next-day stop entries; (3) the book **Turtle Soup at the 20-day extreme** with the 4-day
age rule and Plus One; (4) **Momentum Pinball** (LBR/RSI(3) + first-hour ORB); (5) **ACD** time-confirmation + failed-A reversal;
(6) **Ehlers' anticipatory roofing-filter oscillator** with the adverse-excursion reversal, plus the "confirmation" control that
Ehlers says loses, and Williams %R / generic RSI as oscillator variants; (7) **Capstone NQ gap continuation** with Bean's dollar
stop/target shape (the only strategy in the family with published 2024-2026 year-by-year numbers); (8) Crabel's **intraday NR7 /
ID pattern-bar** breakout; (9) **The Anti**; (10) **Collins' combined open-to-close biases** as a trade and as a filter; (11) Davey's
count/pullback pattern with his **dollar-exit** finding; (12) a **regime/filter overlay** (Kaufman ER, Wilder ADX, Turtle
skip-after-a-winner, TD-9 no-chase); (13) the ES 09:32 gap-fill as a **decay control**.

## 0. Conventions used by every spec below

Times are **ET**. Data sessions run 18:00 -> ~16:14 ET next day for the index CFD proxies (the feed stops ~16:14), 18:00 -> 17:00
for gold. RTH equities 09:30-16:00; gold pit 08:20-13:30. A 1-minute bar with `tod = T` covers `[T, T+1)`. A decision taken "on
the close of bar k" places the order at `k+1` (1-min) or at `B.i_next[k]` (N-min bars): **market at the next open (+1 tick slip)**
unless the spec says stop/limit. `i_next == -1` (session ended) -> skip. The 09:30 open `O930` = open of the first RTH bar `i0`
(`daily_bars(...).i_first`); any order that uses it goes live at `i1 = i0 + 1` (the 09:31 bar), so the open print itself can
never fill it. Forced flat: equities **15:55** (engine limit 15:58); gold pit specs **13:25**. No overnight, no weekends.
Early-close sessions (`session_info().early_close`) take no entries after 12:00.

Instruments: **MNQ** first for every index spec (every family so far finds MES dead on breakout rules because ES-point targets are
too small against fixed costs; the Capstone 2024-26 numbers point the same way), MES second as the cross-market acceptance test
(Collins / Penfold: a pattern that only works on one index is suspect), MGC only where stated (pit hours 08:20-13:30, flat 13:25).

Indicators (exact definitions; every daily quantity used on session d comes from sessions < d; NaN -> no trade):
- `D` = `daily_bars(df1, rth_only=True, rth=(rth_open, rth_close))`: one RTH bar per session: `open, high, low, close, i_first,
  i_last`. `PDH, PDL, PDC, PDO` = high/low/close/open of `D[d-1]`; `R1 = PDH - PDL`; `C2 = close[d-2]`; `oc[k] = close[k] - open[k]`.
- `ATR14d` = `daily_atr(df1, 14, rth_only=True, rth=...)` (Wilder, shifted one day). 2025-26 medians: NDX ~398 pts, SPX ~76 pts,
  XAU pit ~69 pts. `ATR10d` likewise with 10. Stops and caps are expressed in ATR fractions, not fixed points, except where an
  author's **dollar** stop is the thing under test (specs 9, 12, 13, 15; Davey's finding is that dollar exits beat ATR exits).
- `B5 / B15 / B30` = `resample(df1, N, rth_only=True, rth=...)`; indicators on these are computed on the **continuous RTH series**
  (bars from prior sessions count toward lookbacks; `min_periods` = full window; the first full-window rows of the dataset never
  trade). `OR(N)` = `opening_range(df1, rth_open, N)` -> `or_high, or_low, or_open, or_close, i_end`, valid only at indices > `i_end`.
- `rsi(s, n)` = Wilder RSI (`common.rsi`, ewm alpha 1/n). `adx(bars, 14)` = `common.adx`; specs that need +DI/-DI (spec 1 ADX
  Gapper) need a small helper `dmi(bars, n) -> (pdi, mdi, adx)` factored out of `common.adx` (same arithmetic).
- `SMA_D(n)` = SMA of the cash-index daily closes (`data/parquet/{NDX,SPX,GC}_1d.parquet`) over the n rows strictly before the
  session (as `orb_close30.daily_trend`); `bias_d = +1 / -1 / NaN`.
- `tick` = contract tick (0.25 index, 0.10 gold); `pv` = point value (MNQ $2, MES $5, MGC $10). Costs in the engine: $1.30 RT +
  1 tick slippage per side on market/stop fills (MNQ $2.30, MES $3.80, MGC $3.30 per round trip). Limit fills: no slippage.
- `R` = |entry - initial stop| in points; `$R = R x pv`. Every stop below has a floor `min_stop_atr x ATR14d` (never a noise-sized
  stop: the mr_ibfail result showed a 0.10-ATR stop is hit 56% of the time before a 0.15-ATR target).

Lucid risk block (default for every spec unless overridden; $ per ONE micro; the Lucid Monte Carlo scales 5-40 micros):
- `max_trades_day` as stated per spec (1 for the daily-setup specs, 2-4 for the intraday engines).
- `daily_loss_stop` (no NEW entries once realised day P&L <= -X): for one-trade specs it is set to one full stop (a stop-out ends
  the day); for multi-trade specs MNQ $80 / MES $60 / MGC $80 unless the spec's stop is larger, in which case `1.5 x $R_median`.
- `daily_profit_stop` (no new entries once realised day P&L >= Y): MNQ $160 / MES $120 / MGC $160 on the multi-trade specs;
  inert when `max_trades_day = 1`. Both only block new entries; an open position runs to its own exit.
- Consistency arithmetic: at the moment of passing a $3,000 eval no single day may exceed $1,500 -> with 5-10 micros the per-micro
  largest day must stay <= $150-300. Capped targets (`tgt_cap_atr` <= 0.6 ATR = $480 MNQ worst case) and the profit stop do this;
  every "no target / EOD" mode below therefore also carries `tgt_cap_atr` (default 0.6) as a hard cap, and the eval run of any
  spec whose largest day exceeds $300/micro at the chosen size must drop the cap to 0.35 ATR or size down.
- Payout arithmetic: 5 days >= $150 at the funded size (20 micros max at funded start -> >= $7.50/micro/day): high-win-rate
  capped-target specs (4, 9, 15-type fades) produce the most such days; R-multiple and EOD-carry specs the fewest.
- One position at a time, one pending order at a time; `set_session(entry_start, entry_end, flat)` on every spec; stop-and-reverse
  logic (specs 7, 8, 12) is emulated by a module-side pre-walk of the 1-min bars exactly as `strategies/orb.py` resolves OCO
  entries: the module computes the market fill (next open + slip), walks forward to the first bar that touches the stop level,
  and places the reverse order at that bar + 1; the engine's own stop fires on the same bar, so the two agree.

Priority: 5 = best prior of working under Lucid constraints given published evidence AND our results so far; 1 = long shot or
control. Complexity: 1 = a parameter set on an existing module, 5 = multi-state intraday machine with pre-walk.

Benchmarks every spec must beat on 2025-01..2026-09: `trend_momentum__benchmark_long_0945` (buy 09:45, flat 15:55), spec 15 below
(the decayed ES gap-fill control) and `orb_session__orb_bracket_control`. If a control shows PF > 1.2 on both periods, suspect an
engine or look-ahead bug before believing any winner.

Data gaps that apply to the whole family: no T-bond daily series in `data/parquet` (Williams' bond filter, Ruggiero intermarket:
approximable only if `ZB=F` daily closes are added from Yahoo; flagged in spec 13); no economic-release calendar (Ruggiero
report-day rule dropped; Williams TDW tested as a plain weekday parameter); no volume (nothing in this family needs it).

---

## 1. classic_systems_authors__pd_extreme_stop_reentry_setups  (Williams Oops / ADX Gapper / 80-20 / Stridsman Meander: prior-day-extreme stop re-entry with the authors' setup filters; `setup` mode on `mr_pdrange`)

Priority **2**, complexity **2** (adds a `setup` switch, a `dmi` helper and the Meander band to the existing `mr_pdrange` stop
mode), instruments **MNQ**, MES. Bar size: daily setup, 1-min execution. EQ 2 (oxfordstrat Bull Oops 42 futures 1980-2011 rated C,
gross-positive; Street Smarts ch. 3 / 7 and Stridsman have no numbers). Our unconditional Oops stop entry is dead after
walk-forward (12 OOS trades): this spec tests whether the authors' filters raise the per-trade edge, knowing they lower frequency
further. Expected use: a filter subset / portfolio leg, never an evaluation vehicle on its own.

```
PARAMS: setup='oops' | 'oops_downclose' | 'adx_gapper' | 'eighty_twenty' | 'meander' | 'any_outside',
  entry='stop' | 'market_0931' (forced for 'meander'), pen_ticks=5 (80-20 only: today must trade >= pen_ticks beyond PDL/PDH
  before the stop is armed), order_until='11:30', min_dist_atr=0.03, max_dist_atr=0.5 (open-to-level distance), gap_cap_atr=1.0,
  stop_mode='today_ext' | 'dist', stop_cap_atr=0.3, min_stop_atr=0.08, tgt='pdc_capped' | 'atr', tgt_atr=0.5, tgt_cap_atr=0.6,
  min_tgt_atr=0.08, exit_time='13:00', flat='15:55', sides='both', adx_len=14, adx_min=30, tdw=None (None | tuple of weekdays
  allowed for LONGS, e.g. (0,1); shorts mirror on the other days), max_trades=1
PRE (per session d; D daily RTH, sessions < d): PDH, PDL, PDC, PDO, R1, C2; atr = ATR14d[d]
  (pdi, mdi, adxd) = dmi(D, adx_len) evaluated at d-1
  meander band (Stridsman): obs = { X[k]/close[k-1] - 1 : X in (open, high, low, close), k in d-5..d-1 }  (20 numbers)
     m = mean(obs); s = std(obs, ddof=1); band_lo = PDC*(1 + m - s); band_hi = PDC*(1 + m + s)
  O930 = open[i0]; i1 = i0 + 1
  LONG setup (short = mirror with PDH / top-of-range / open above / mdi > pdi / band_hi):
    any_outside:    O930 < PDL
    oops:           O930 < PDL                                             (Williams; identical to any_outside, kept for naming)
    oops_downclose: O930 < PDL and PDC < C2                                (Williams [book]: "buys after a down close")
    adx_gapper:     O930 < PDL and adxd > adx_min and pdi > mdi            (Street Smarts ch. 7: gap against an established uptrend)
    eighty_twenty:  (PDO - PDL)/R1 >= 0.80 and (PDC - PDL)/R1 <= 0.20      (yesterday: opened in the top 20%, closed in the bottom 20%)
                    and the FIRST RTH 1-min bar t (tod < order_until) with low[t] <= PDL - pen_ticks*tick  (open below PDL counts)
    meander:        O930 < band_lo and PDL - 0.5*atr <= O930              (unusually weak open; need not be outside the prior range)
  level = PDL (long) / PDH (short); dist = |O930 - level|  (eighty_twenty: dist = PDL - min low through bar t)
  tradeable = setup and min_dist_atr*atr <= dist <= max_dist_atr*atr and |O930 - PDC| <= gap_cap_atr*atr and atr notna
              and (tdw is None or weekday(d) in tdw for longs / not in tdw for shorts) and not early_close
ENTRY entry='stop':  arm bar a = i1 (eighty_twenty: a = t + 1); place(a, +1, entry_px = PDL + tick, kind='stop',
      valid_bars = minutes from a to order_until, stop_px, tgt_px)                   # fill = max(open, level) + 1 tick
      entry='market_0931' (meander; also allowed for the other setups as a cell): place(i1, +1) market, target PDC
STOP:  'today_ext': stop_px = (lowest low from 09:30 through bar a-1) - tick; if level - stop_px > stop_cap_atr*atr then
       stop_px = level - stop_cap_atr*atr; if level - stop_px < min_stop_atr*atr then stop_px = level - min_stop_atr*atr
       'dist': stop_px = level - clamp(dist, min_stop_atr*atr, stop_cap_atr*atr)
TARGET: 'pdc_capped': tgt_px = level + min(PDC - level, tgt_cap_atr*atr); skip the day if PDC - level < min_tgt_atr*atr
        'atr': tgt_px = level + tgt_atr*atr
EXIT: it.exit_at(first bar >= exit_time); set_session('09:31', order_until, flat); max_trades_day = 1
RISK: daily_loss_stop = stop_cap_atr*atr_median*pv (one full stop); daily_profit_stop inert
```
Grid (<= 32): `setup {oops_downclose, adx_gapper, eighty_twenty, meander}`, `sides {both, long}`, `stop_cap_atr {0.2, 0.3}`,
`tgt {pdc_capped, atr}`. Fixed: entry stop (meander market), order_until 11:30, exit 13:00, tdw None. Run `tdw` only as a
diagnostic split of the best cell (Williams' TDW tables are 1980s in-sample).

Risk/Lucid: $R <= 0.3 ATR = ~120 NQ pts = $240/micro; 51-60% win in the unconditional version, ~2 setups/month per filter ->
a filter leg only. Compare each cell against the same days traded unconditionally (`mr_pdrange` stop mode): the filter earns its
place only if PF rises on MAIN and PRIOR with >= 60% of the unconditional trade count.

Evidence recap: oxfordstrat Bull Oops C; Moore 80-20 statistic (80-90% follow-through next morning, ~50% close beyond); Street
Smarts ADX Gapper book-only; Stridsman 1990s book tests. Data gap: none (TDW is a plain weekday).

## 2. classic_systems_authors__daily_reversal_bar_stop_entry  (Williams Smash Day naked / hidden, Street Smarts Whiplash, Penfold key reversal: daily pattern, next-day stop entry beyond the pattern bar)

Priority **2**, complexity **2**, instruments **MNQ**, MES, MGC. Bar size: daily pattern, 1-min execution. EQ 1 (book tables only;
oxfordstrat "Reversal Patterns part 2" on the related outside-reversal family: PF 0.97, win 34.5%, rated C, positive only with
8:1 exits). Objective and cheap; the Lucid translation caps the stop and adds a target, which is exactly what the oxfordstrat
result says such patterns lack.

```
PARAMS: pattern='smash_naked' | 'smash_hidden' | 'whiplash' | 'key_reversal', hidden_pct=0.25, lookback=20 (whiplash),
  n_filter=0 (ProRealCode: 0 = off; n > 0 requires the smash to occur below/above the recent n-day range), order_start='09:31',
  order_until='12:00', gap_through_atr=0.10, stop_mode='pattern_ext' | 'cap', stop_cap_atr=0.4, min_stop_atr=0.10,
  tgt_mode='rr' | 'atr', rr=1.0, tgt_atr=0.5, tgt_cap_atr=0.6, be_trail=False, exit_time='15:00', flat='15:55',
  sides='both', max_trades=1
PRE (D daily RTH; d uses d-1, d-2, ...; atr = ATR14d[d]):
  H1,L1,O1,C1 = D[d-1]; H2,L2,C2 = D[d-2]; R1 = H1 - L1
  LONG pattern (short = exact mirror):
    smash_naked:   C1 < L2                                  entry_level = H1;  stop_level = L1     (Williams [book])
    smash_hidden:  (C1 - L1)/R1 <= hidden_pct and L1 >= L2  entry_level = H1;  stop_level = L1     (weak close, no new low)
    whiplash:      L2 <= min(low[d-2-lookback+1 .. d-2])     (day d-2 made a new 20-day low)
                   and L1 < L2 and C1 > H2                   entry_level = H1;  stop_level = L1     ([interp] outside reversal)
    key_reversal:  O1 > C2 and L1 < L2 and C1 > C2           entry_level = H1;  stop_level = L1     (Penfold: lower low, close above prior close)
    n_filter > 0 (smash only): require H1 < max(high[d-1-n .. d-2])  (the smash happened inside/below the recent range)
  O930 = open[i0]; skip if O930 > entry_level + gap_through_atr*atr (gapped through the trigger; a stop would be a chase)
  tradeable = pattern and atr notna and not early_close and entry_level - stop_level <= 1.5*atr
ENTRY: i1 = i0 + 1; place(i1, +1, entry_px = entry_level + tick, kind='stop', valid_bars = minutes from 09:31 to order_until,
       stop_px / stop_pts, tgt_px)        # if O930 >= entry_level the engine fills at the 09:31 open + slip (Williams: still a buy)
STOP:  'pattern_ext': stop_px = stop_level - tick; if entry_level - stop_px > stop_cap_atr*atr -> use stop_pts = stop_cap_atr*atr
       'cap': stop_pts = min(entry_level - stop_level + 2*tick, stop_cap_atr*atr); floor min_stop_atr*atr in both modes
TARGET: R = effective stop distance; 'rr': tgt_pts = rr*R; 'atr': tgt_pts = tgt_atr*atr; both <= tgt_cap_atr*atr
  be_trail: trail_act_pts = R, trail_pts = R (break-even ratchet, Davey's third-best exit)
EXIT: it.exit_at(first bar >= exit_time); set_session(order_start, order_until, flat); max_trades_day = 1
RISK: daily_loss_stop = stop_cap_atr*atr_median*pv; daily_profit_stop inert
```
Grid (<= 32): `pattern {smash_naked, smash_hidden, key_reversal, whiplash}`, `stop_cap_atr {0.3, 0.5}`, `(tgt_mode, value)
{(rr, 1.0), (atr, 0.5)}`, `sides {both, long}`. Fixed: hidden_pct 0.25, n_filter 0 (one follow-up cell with n = 10 on the best
smash cell), order_until 12:00, be_trail False (one follow-up pair).

Risk/Lucid: smash-day ranges are often > 1 ATR on NQ, so the cap binds on most trades ($R = 0.3-0.5 ATR = $240-400/micro) ->
3-5 micros. Frequency per instrument: naked smash ~5-8% of sessions, hidden ~15%, key reversal ~8%, whiplash < 2% (whiplash is
in the grid for completeness only; expect < 30 trades on MAIN, judge it on 2010-2024 pooled across MNQ/MES/MGC, Penfold-style).

Evidence recap: Williams 1999 [book]; ProRealCode code without statistics; oxfordstrat reversal-pattern family PF 0.97 (daily
holds); Penfold's P24 acceptance test (must work across markets) is the acceptance rule here. Data gap: none.

## 3. classic_systems_authors__turtle_soup_20day  (Street Smarts Turtle Soup and Turtle Soup Plus One at the 20-day extreme, 4-day age rule, 5-10 tick offset)

Priority **2**, complexity **3**, instruments **MNQ**, MES, MGC. Bar size: daily levels, 1-min execution. EQ 2 (book, no numbers;
ProRealCode M30 forex: positive but "bad profit factor"; luxalgo: regime-dependent). Distinct from
`intraday_mean_reversion__turtle_soup_pd_recross` (prior-DAY level, close-back-inside trigger): this is the book rule at the
**20-day** low/high, which fires on fewer, more extreme days and uses a stop order a fixed number of ticks above the old low
without waiting for a close back inside.

```
PARAMS: lookback=20, min_age=4, offset_ticks=8 (book 5-10), variant='soup' | 'plus_one', order_until='14:00',
  stop_mode='today_ext' | 'cap', stop_cap_atr=0.30, min_stop_atr=0.08, max_dist_atr=0.6, tgt='atr' | 'pdc', tgt_atr=0.5,
  tgt_cap_atr=0.6, min_tgt_atr=0.08, reenter=True (book: re-enter once at the original price), exit_time='15:00', flat='15:55',
  sides='both', max_trades=2
PRE (D daily RTH; for session d use sessions < d; atr = ATR14d[d]):
  LONG side (short = mirror on highs):
   soup:     LL = min(low[d-lookback .. d-1]); j = argmin (most recent if tied); age = (d-1) - j
             require age >= min_age            (the previous 20-day low is at least 4 sessions old; a fresh low yesterday is NOT a setup)
             TRIGGER during day d: the first 1-min bar t (tod < order_until) with low[t] < LL - tick   (today makes a new 20-day low)
             arm bar a = t + 1; entry_px = LL + offset_ticks*tick
   plus_one: LLp = min(low[d-lookback-1 .. d-2]); age computed on LLp as above, require age >= min_age
             require low[d-1] < LLp and close[d-1] <= LLp     (yesterday made the new 20-day low and closed at/below the old one)
             arm bar a = i1 (09:31); entry_px = LLp + offset_ticks*tick
  dist = entry level - (lowest low so far at bar a-1, soup) / - min(low[d-1], O930) (plus_one); skip if dist > max_dist_atr*atr
  (a real breakdown, not a sweep); skip if O930 > entry_px + 0.10*atr (gapped back through the level: no re-entry to catch)
ENTRY: place(a, +1, entry_px, kind='stop', valid_bars = minutes from a to order_until, stop_px, tgt_px)
STOP:  'today_ext': stop_px = min(lowest low 09:30..a-1 [soup] or min(low[d-1], lowest low 09:30..a-1) [plus_one]) - tick,
       then clamp so that entry_px - stop_px in [min_stop_atr*atr, stop_cap_atr*atr]
       'cap': stop_pts = stop_cap_atr*atr
TARGET: 'atr': tgt_px = entry_px + tgt_atr*atr; 'pdc': tgt_px = entry_px + min(PDC - entry_px, tgt_cap_atr*atr) if
        PDC - entry_px >= min_tgt_atr*atr else fall back to 'atr'
RE-ENTRY: if reenter and the first attempt is stopped out before order_until (module pre-walk: fill = max(open, entry_px) + slip
       at the first bar touching entry_px, then the first later bar touching the stop), re-place the same stop order at
       stop_bar + 1 with the same stop/target (book: "re-enter at the original entry price on day 1 or 2"); max_trades_day = 2
EXIT: it.exit_at(first bar >= exit_time); set_session('09:31', order_until, flat)
RISK: daily_loss_stop = 2 x stop_cap_atr*atr_median*pv when reenter else 1 x; daily_profit_stop inert
```
Grid (<= 32): `variant {soup, plus_one}`, `offset_ticks {4, 8}`, `stop_cap_atr {0.20, 0.35}`, `tgt {atr, pdc}`, `sides {both,
long}`. Fixed: lookback 20, min_age 4, reenter True (one follow-up pair with False), exit 15:00.

Risk/Lucid: $R <= 0.2-0.35 ATR = $160-280/micro -> 5 micros; new-20-day-extreme days with the age rule are ~8% of sessions per
side -> 2-4 setups/month/instrument; across MNQ + MES + MGC ~1 every 2 days. Shorts (failed upside breaks) are the weak side in
2023-26 per the family and sibling results; if only `long` survives, that is consistent, not a fit.

Evidence recap: Street Smarts ch. 1-2 (rules, no stats); ProRealCode (positive, low PF); luxalgo regime note. Data gap: none.

## 4. classic_systems_authors__momentum_pinball  (Street Smarts Momentum Pinball: LBR/RSI(3) of the 1-day ROC as the day filter, first-hour range breakout after 10:30)

Priority **3**, complexity **2**, instruments **MNQ**, MES, MGC (pit: first hour 08:20-09:20, entries 09:20-11:30, flat 13:25).
Bar size: daily filter + 60-min opening range, 1-min execution. EQ 1-2 for the book rule; 3 for the first-hour ORB component
(sibling orb_session: IB/first-hour continuation 60-72% with context filters; our own `orb_close30` 15/30-min close-confirmed
ORB is the one marginal-positive ORB on MNQ). Report item F2. Structurally the best-shaped entry in the family: one trade a day,
after the opening noise, risk = first-hour range (capped), direction from a two-day mean-reversion filter.

```
PARAMS: rsi_len=3, lo=30, hi=70, fh_minutes=60, order_until='12:00', stop_cap_atr=0.5, min_stop_atr=0.10, max_fh_atr=0.8,
  tgt_mode='fh_range' | 'atr' | 'none', tgt_mult=1.0, tgt_atr=0.5, tgt_cap_atr=0.6, reenter=True (book: once), be_trail=False,
  flat='15:55', sides='both', max_trades=2
PRE: D daily RTH closes; roc1 = close - close.shift(1); LBR = rsi(roc1, rsi_len)   (3-period Wilder RSI of the 1-day change)
  signal day: LBR[d-1] < lo -> buy day; LBR[d-1] > hi -> sell day; else no trade  (yesterday's close value; strictly lagged)
  FH = opening_range(df1, rth_open, fh_minutes) -> fh_high, fh_low, i_end (10:29 bar); fh_rng = fh_high - fh_low; atr = ATR14d
  tradeable = signal and atr notna and 0 < fh_rng <= max_fh_atr*atr and not early_close
ENTRY: i_e = FH.i_end + 1 (the 10:30 bar). buy day: place(i_e, +1, entry_px = fh_high + tick, kind='stop',
       valid_bars = minutes from 10:30 to order_until, stop_px / stop_pts, tgt_px / tgt_pts); sell day: mirror at fh_low - tick
STOP:  stop_px = fh_low - tick (long); if fh_rng + 2*tick > stop_cap_atr*atr -> stop_pts = stop_cap_atr*atr; floor min_stop_atr*atr
TARGET: 'fh_range': tgt_pts = min(tgt_mult*fh_rng, tgt_cap_atr*atr); 'atr': tgt_pts = tgt_atr*atr; 'none': no target
        (book: hold overnight if profitable -> replaced by flat 15:55; tgt_cap_atr still applies as a hard cap)
  be_trail: trail_act_pts = R, trail_pts = R
RE-ENTRY: if reenter and the first trade is stopped before order_until (module pre-walk as spec 3), re-place the same stop order
       at stop_bar + 1 (book: "re-enter once if the first-hour extreme is re-broken"); max_trades_day = 2
EXIT: set_session(rth_open + fh_minutes, order_until, flat); no time exit other than flat (the book holds to the close)
RISK: daily_loss_stop = (2 if reenter else 1) x stop_cap_atr*atr_median*pv; daily_profit_stop inert
```
Grid (<= 24): `(tgt_mode, value) {(fh_range, 1.0), (atr, 0.5), (none, cap 0.6)}`, `stop_cap_atr {0.3, 0.5}`, `sides {both, long}`,
`reenter {False, True}`. Fixed: rsi_len 3, lo/hi 30/70 (one follow-up pair with 25/75 on the best cell), fh 60 min, order_until
12:00. Also run the **control** `lo=hi=50` (every day is a signal day, direction = LBR side) to measure what the filter adds.

Risk/Lucid: NQ first-hour range 80-200 pts -> the 0.5-ATR cap (~200 pts = $400/micro) binds on wide days; 0.3 ATR ($240) is the
sizing lever. Frequency: LBR(3) < 30 or > 70 on ~35-45% of sessions; the first-hour extreme is broken on ~60% of those ->
~1 trade every 2 days per instrument. Win rate target 50-55% with ~1R targets; the `fh_range` cells produce the $150-day shape.

Evidence recap: Street Smarts ch. 4 [book] (rule only); ProRealCode indicator (different parameterisation 14 / 40-60, not used);
first-hour continuation statistics in orb_session.md. Data gap: none.

## 5. classic_systems_authors__crabel_stretch_close_confirm  (Crabel stretch ORB with 1-min / 5-min close confirmation, stop at the open instead of the full reverse, ATR target; parameter extension of `orb_crabel`)

Priority **3**, complexity **1** (three new modes on the existing module), instruments **MNQ** (MES, MGC dead on the touch version;
re-run MES once on the best MNQ cell only). Bar size: daily stretch + 1-min. EQ 3 for the setup statistics (Crabel 1982-89 tables
60-71% after NR4/ID), 2 for net profitability (oxfordstrat C). Report item F1. Our touch-entry version is marginal (MNQ PF 1.25 /
1.39, Lucid lower bound -$98); the two untested levers are the close-confirmed trigger (kills the wick-break fills that made the
published cell's intraday DD $5k/micro) and the stop at the open (R = T instead of 2T).

```
PARAMS (orb_crabel + new): stretch_len=10, mult=1.0, setup='none' | 'nr7' | 'nr4' | 'id' | 'nr4_or_id' | 'id_nr4' (new),
  cutoff='10:30', max_stop_atr=0.25, entry_mode='touch' (existing stop order) | 'close1' (new) | 'close5' (new),
  stop_mode='reverse' (existing: the other level, R = 2T) | 'open' (new: stop_px = O930, R ~ T), tgt_mode='eod' | 'rr' | 'atr'
  (new), rr=1.5, tgt_atr=0.5, tgt_cap_atr=0.6, flat='15:55', max_trades=1
PRE (as orb_crabel): noise_k = min(high_k - open_k, open_k - low_k) on D; stretch[d] = SMA(noise, stretch_len) over d-10..d-1;
  T = mult*stretch; setup flags on days < d (id_nr4 = id and nr4); atr = ATR14d; O930 = open[i0]; up = O930 + T; dn = O930 - T
ENTRY 'touch': as the module today (OCO stop orders from i1, resolved on 1-min bars, valid to cutoff)
      'close1': scan 1-min bars k >= i1 with tod < cutoff: first k with close[k] > up -> side +1, i = k + 1;
                first k with close[k] < dn -> side -1 (whichever comes first); place(i, side) market (+1 tick)
      'close5': same on B5 bars (close of the 5-min bar beyond the level), i = B5.i_next[k]
STOP:  'reverse': stop_px = dn (long) / up (short); 'open': stop_px = O930 - tick (long) / O930 + tick (short);
       in both modes clamp |ref - stop_px| <= max_stop_atr*atr where ref = level (touch) or close[k] (close modes);
       floor 0.08*atr
TARGET: 'eod': none but tgt_pts = tgt_cap_atr*atr (hard cap); 'rr': tgt_pts = rr*R; 'atr': tgt_pts = tgt_atr*atr (<= cap)
SESSION: set_session(rth_open, cutoff, flat); max_trades_day = 1
RISK: daily_loss_stop = max_stop_atr*atr_median*pv (one full stop)
```
Grid (<= 48): `entry_mode {touch, close1}`, `stop_mode {reverse, open}`, `(tgt_mode, value) {(rr, 1.5), (atr, 0.5)}`,
`setup {none, nr4_or_id, nr7}`, `mult {1.0, 1.5}`. Fixed: cutoff 10:30, max_stop_atr 0.25 (the best existing cell), stretch_len
10. One follow-up cell `close5` and one `id_nr4` on the best configuration.

Risk/Lucid: with `stop_mode='open'` and mult 1.0, $R ~ T ~ 25-60 NQ pts = $50-120/micro: the cheapest risk in the family, so
10-15 micros are feasible and the payout-day arithmetic ($150/day at 20 micros) is easy if the win rate holds. Expect the close
confirmation to cut trades by 30-40% and to remove most same-bar stop-outs.

Evidence recap: Crabel tables; oxfordstrat NR C / WR D; our `results/orb_crabel/README.md`. Data gap: none.

## 6. classic_systems_authors__nr_pattern_bar_intraday  (Crabel NR4 / NR7 / inside-bar pattern on 15- or 30-min RTH bars, stop beyond the pattern bar, EMA(20) trend filter; mql5 NR7 EA / tradingsetupsreview codification)

Priority **2**, complexity **2**, instruments **MNQ**, MES, MGC. Bar size: 15 or 30 min on 1-min execution. EQ 2 (Crabel's daily
tables; oxfordstrat NR7 C; no net intraday test). Related sibling: `volatility_breakout__intraday_compression_break` (ATR
compression / BB-inside-KC window) - this is the discrete narrow-bar version with the one-bar validity rule, kept separate because
the bar-count definition and the "cancel if the next bar does not trigger" rule are the published ones.

```
PARAMS: bar=30, nr_len=7, require_id=False, trend_filter='ema7' | 'none', ema_len=20, skip_consecutive=True, first_bar_tod='10:00',
  last_entry='14:30', valid_mult=1 (the stop lives for valid_mult x bar minutes: 1 = next bar only, published),
  stop_cap_atr=0.30, min_stop_atr=0.05, tgt_mode='rr' | 'atr', rr=1.5, tgt_atr=0.4, tgt_cap_atr=0.6, flat='15:55', sides='both',
  max_trades=2
PRE: B = resample(df1, bar, rth_only=True) continuous RTH series (lookbacks may include the prior session's RTH bars, as the
  mql5 EA does); rng = high - low; atr = ATR14d of the bar's session
  NR[k] = rng[k] <= min(rng[k-nr_len+1 .. k])  (narrowest of the last nr_len, ties count)
  ID[k] = high[k] < high[k-1] and low[k] > low[k-1];  pattern[k] = NR[k] and (ID[k] if require_id)
  if skip_consecutive: pattern[k] = pattern[k] and not pattern[k-1]   (congestion warning in tradingsetupsreview)
  EMA = ema(close, ema_len); long_ok[k] = all(low[k-6..k] > EMA[k-6..k]); short_ok[k] = all(high[k-6..k] < EMA[k-6..k])
  ('ema7': the last 7 bars entirely above/below the 20-EMA; 'none': both sides allowed)
  eligible[k] = pattern[k] and tod[k] + bar >= first_bar_tod and tod[k] + bar < last_entry and not early_close
ENTRY at i = B.i_next[k]: long_ok -> buy stop at high[k] + tick; short_ok -> sell stop at low[k] - tick; both allowed -> OCO
  resolved on the 1-min bars (as orb.py; both touched in one 1-min bar -> the side nearer that bar's open);
  place(i, side, entry_px, kind='stop', valid_bars = valid_mult*bar, stop_px, tgt_pts)
STOP:  stop_px = low[k] - tick (long) / high[k] + tick (short); if |entry_px - stop_px| > stop_cap_atr*atr -> stop_pts = cap;
       floor min_stop_atr*atr (a 30-min NR7 bar on NQ is ~0.1-0.2 ATR, so the floor rarely binds, the cap rarely either)
TARGET: 'rr': tgt_pts = rr*R; 'atr': tgt_pts = tgt_atr*atr; both <= tgt_cap_atr*atr
SESSION: set_session(first_bar_tod, last_entry, flat); max_trades_day = 2 (one pending order at a time: a new pattern bar while
  an order is pending replaces it only after the old one expires)
RISK: daily_loss_stop MNQ $80 / MES $60 / MGC $80; daily_profit_stop MNQ $160 / MES $120 / MGC $160
```
Grid (<= 32): `bar {15, 30}`, `nr_len {4, 7}`, `trend_filter {ema7, none}`, `(tgt_mode, value) {(rr, 1.5), (atr, 0.4)}`,
`stop_cap_atr {0.2, 0.3}`. Fixed: require_id False (one follow-up cell True on the best), skip_consecutive True, valid_mult 1.

Risk/Lucid: $R = pattern-bar range ~0.1-0.2 ATR = $80-160/micro; 1-3 signals/day, ~45% win expected at 1.5R. Many small trades:
the profit stop matters here. Pair with spec 4 or 5 (morning) since most NR bars form after 11:00.

Evidence recap: Crabel; tradingsetupsreview NR7 / ID-NR4; mql5 NR7 EA (no stats); oxfordstrat NR7 C. Data gap: none.

## 7. classic_systems_authors__acd_time_confirm_failed_a  (Fisher ACD: opening range, A-up/A-down = 0.2 x ATR(10) beyond the OR, confirmation by TIME, stop at the confirmation low or the OR edge, failed-A reversal at the C level, first A only)

Priority **3**, complexity **4** (state machine with a pre-walk to detect the failed A), instruments **MNQ**, MES, MGC (OR
08:20-08:35, A/C windows shifted, flat 13:25). Bar size: 15-min OR, 1-min state machine. EQ 1-2 (anecdotal; Fisher's own framing is
that ACD is risk management, not an edge). Report item F5. Why it is here despite the evidence grade: the two failure modes of
every ORB in our results (wick-break fills, re-trigger churn) are exactly what the time confirmation and the first-A-only rule
remove, and the failed-A reversal is the only published rule that trades the 40-60% of days on which the first break fails from
the *other* side of the range (cf. `orb_session__orb_second_break`).

```
PARAMS: or_minutes=15, a_atr=0.20, c_atr=0.30, atr_len=10, confirm_minutes=8 (~ half the OR), stop_mode='confirm_low' | 'or_edge',
  stop_cap_atr=0.40, min_stop_atr=0.08, tgt_mode='atr' | 'none', tgt_atr=0.5, tgt_cap_atr=0.6, failed_a=True, first_a_only=True,
  a_until='11:30', c_until='13:00', exit_time='15:30', flat='15:55', sides='both', max_trades=2
PRE: OR = opening_range(df1, rth_open, or_minutes): orh, orl, i_end; atr10 = ATR10d[d]; atr = ATR14d[d] (caps)
  A = a_atr*atr10; C = c_atr*atr10; A_up = orh + A; A_dn = orl - A; C_up = orh + C; C_dn = orl - C
  tradeable = atr10 notna and orh - orl <= 0.8*atr and not early_close
STATE per day on 1-min bars k > i_end (closes only), state in {WAIT, CONF_UP(n), CONF_DN(n), IN_LONG, IN_SHORT, FAILED_UP,
  FAILED_DN, DONE}; start WAIT:
  WAIT (tod < a_until):  close[k] > A_up -> CONF_UP(1);  close[k] < A_dn -> CONF_DN(1)
  CONF_UP(n): close[k] > A_up -> n += 1; if n >= confirm_minutes: ENTER LONG at k+1 (market), conf_low = min(low over the n bars)
              close[k] <= A_up -> (first_a_only ? FAILED_UP : WAIT)      # the A-up did not hold for the required time
  IN_LONG: stop_px = conf_low - tick ('confirm_low') or orh - tick ('or_edge', back inside the OR, Fisher's default);
           clamp so that close[k_entry-1] - stop_px <= stop_cap_atr*atr, floor min_stop_atr*atr;
           tgt_pts = tgt_atr*atr ('atr') or none (cap tgt_cap_atr*atr); exit_at(first bar >= exit_time)
           MODULE PRE-WALK: fill = open[k+1] + slip; walk bars until the stop level is touched (stop exit, bar s), the target is
           reached, or exit_time -> if stop exit and failed_a: FAILED_UP from s+1; else DONE
  FAILED_UP (tod < c_until, only if failed_a): close[k] < C_dn -> ENTER SHORT at k+1 (market), stop_px = orh + tick (clamp to
           stop_cap_atr*atr from close[k], floor), tgt_pts = tgt_atr*atr, exit_at(exit_time) -> DONE
           (Fisher: an A-up that fails and trades through C-down is the reversal; "only the first fade at the A has edge")
  CONF_DN / IN_SHORT / FAILED_DN: exact mirror (A_dn, C_up)
  sides='long': the CONF_DN branch is disabled but FAILED_DN -> long at C_up stays enabled; 'both' = all branches
SESSION: set_session(rth_open + or_minutes, c_until, flat); max_trades_day = 2
RISK: daily_loss_stop = 1.5 x stop_cap_atr*atr_median*pv (an A loss plus a C loss ends the day); daily_profit_stop inert
```
Grid (<= 32): `or_minutes {15, 30}`, `a_atr {0.15, 0.25}`, `confirm_minutes {5, 10}`, `stop_mode {confirm_low, or_edge}`,
`failed_a {False, True}`. Fixed: c_atr 0.30, tgt_atr 0.5, a_until 11:30, sides both (one `long` run on the best cell).
Report the A-trades and the C-trades as separate exit cohorts (the C reversal may carry or kill the whole thing).

Risk/Lucid: $R: 'confirm_low' ~0.1-0.2 ATR ($80-160/micro); 'or_edge' = A + OR width ~0.3-0.4 ATR ($240-320): the cap binds ->
5 micros for or_edge, 10 for confirm_low. Expect ~0.6 A-trades/day and ~0.2 C-trades/day.

Evidence recap: elitetrader ACD thread excerpts (A/C = 20-25% of a 5-10 day ATR; "risk by time, not by price"); TradingView
Session OR A-Lines; no backtest. Data gap: none.

## 8. classic_systems_authors__ehlers_anticipatory_oscillator  (Ehlers roofing filter (48/10) + SuperSmoothed stochastic on 5-min bars, ANTICIPATORY entries at 0.2 / 0.8, adverse-excursion stop-and-reverse; `confirm` mode as the control; generic RSI and Williams %R as oscillator variants)

Priority **3**, complexity **4** (recursive filters, signal exits, pre-walk reversal), instruments **MES**, MNQ (Ehlers' tests are
S&P daily and T-bonds; ES is the natural first instrument for a mean-reversion engine, and this is the one family spec where MES
goes first). Bar size: 5-min RTH. EQ 2-3 (author's own tests: bonds 2002-07 PF 1.7-2.1 at 53-57% wins, no costs; S&P daily
anticipatory curve "consistent winners", confirmation "loses consistently"; nothing on ES intraday). Report item F6.
Williams %R (s.5) is folded in as `osc='wpr'` because the only thing Williams adds to a stochastic is the lookback and the
-80/-20 zones; Ehlers' point (confirmation loses, anticipation wins) is the test.

```
PARAMS: bar=5, osc='roof_stoch' | 'rsi' | 'wpr', hp_len=48, ss_len=10, stoch_len=20, rsi_len=10, wpr_len=14, lo=0.2, hi=0.8
  (rsi: 0.3 / 0.7), mode='anticipate' | 'confirm' (control), adverse_atr=0.4 (stop = adverse excursion, x ATR14d),
  reverse_on_adverse=True, max_reversals=1, tgt_mode='opposite' | 'atr', tgt_atr=0.4, tgt_cap_atr=0.6, first_entry='09:45',
  last_entry='15:00', flat='15:55', sides='both', max_trades=4
PRE: B = resample(df1, bar, rth_only=True), continuous RTH series; C = close. Warm-up: no signals in the first 200 bars of the
  loaded range (the recursive filters need ~4 x hp_len bars to converge).
  Roofing filter (Ehlers, Predictive Indicators listing 2):
    w = 0.707 * 2*pi / hp_len;  alpha1 = (cos(w) + sin(w) - 1) / cos(w)
    HP[k] = (1 - alpha1/2)^2 * (C[k] - 2*C[k-1] + C[k-2]) + 2*(1 - alpha1)*HP[k-1] - (1 - alpha1)^2 * HP[k-2]
    a1 = exp(-1.414*pi / ss_len);  b1 = 2*a1*cos(1.414*pi / ss_len);  c2 = b1;  c3 = -a1^2;  c1 = 1 - c2 - c3
    Filt[k] = c1*(HP[k] + HP[k-1])/2 + c2*Filt[k-1] + c3*Filt[k-2]
    HighestC = max(Filt[k-stoch_len+1 .. k]);  LowestC = min(...);  Stoc[k] = (Filt[k] - LowestC) / (HighestC - LowestC)
    Osc[k] = c1*(Stoc[k] + Stoc[k-1])/2 + c2*Osc[k-1] + c3*Osc[k-2]          # SuperSmoothed stochastic in [0, 1]
  osc='rsi':  raw = rsi(C, rsi_len)/100;  Osc = SuperSmoother(raw) (same c1..c3)   # Ehlers "generic RSI" strategy; lo/hi 0.3/0.7
  osc='wpr':  raw = 1 + WilliamsR(wpr_len)/100 where WilliamsR = (HH(wpr_len) - C)/(HH - LL) x -100  (so -80 -> 0.2, -20 -> 0.8);
              Osc = SuperSmoother(raw); lo/hi 0.2/0.8
SIGNAL on bar k (values at its close; order at B.i_next[k]; require first_entry <= tod(i_next) < last_entry):
  anticipate: long_sig  = Osc[k] <  lo and Osc[k-1] >= lo        (crosses BELOW the lower threshold: anticipating the trough)
              short_sig = Osc[k] >  hi and Osc[k-1] <= hi        (crosses ABOVE the upper threshold)
  confirm (control; Ehlers: "loses consistently"):
              long_sig  = Osc[k] >  lo and Osc[k-1] <= lo        (turns up through the lower threshold)
              short_sig = Osc[k] <  hi and Osc[k-1] >= hi
  sides='long': short_sig only EXITS a long, never opens a short
POSITION LOGIC (module-side, one position at a time):
  flat and long_sig  -> place(i_next, +1, stop_pts = adverse_atr*atr, tgt_pts = tgt_atr*atr if tgt_mode=='atr' else tgt_cap_atr*atr)
  in long and short_sig -> it.exit_at(i_next, +1) and, if sides=='both', place(i_next + 1, -1, ...)   (exit on the opposite signal)
  REVERSAL (reverse_on_adverse): after each market entry the module pre-walks the 1-min bars: fill = open[i_next] + slip; s = the
    first bar with low[s] <= fill - adverse_atr*atr (long). If s comes before the next opposite signal, the target and flat:
    place(s + 1, -side, stop_pts = adverse_atr*atr, tgt_pts as above) as the reversal (Ehlers: "reverse the position if the trade
    moves against entry by a set percentage"); the reversal itself does not reverse again (max_reversals 1) and exits on the next
    opposite signal / target / flat. The engine's own stop fires at bar s on the same level, so trade accounting is consistent.
SESSION: set_session(first_entry, last_entry, flat); max_trades_day = 4
RISK: daily_loss_stop = 1.5 x adverse_atr*atr_median*pv (an entry loss plus its reversal loss ends the day);
      daily_profit_stop MES $120 / MNQ $160
```
Grid (<= 48): `osc {roof_stoch, rsi, wpr}`, `mode {anticipate, confirm}`, `adverse_atr {0.3, 0.5}`, `tgt_mode {opposite, atr}`,
`reverse_on_adverse {True, False}`. Fixed: bar 5, hp 48, ss 10, stoch 20, thresholds as above, sides both (one `long` run on the
best anticipate cell). The `confirm` cells are the control: if they beat the `anticipate` cells on MAIN and PRIOR, Ehlers'
central claim does not transfer to 5-min ES and the spec is dead.

Risk/Lucid: $R = 0.3-0.5 ATR ($115-190/MES, $240-400/MNQ) -> MES 5-10 micros; 2-4 trades/day, mean-reversion shape (many small
winners, occasional reversal pair). Largest-day cap via `tgt_cap_atr`; the profit stop keeps a trend day from stacking losses.

Evidence recap: mesasoftware PredictiveIndicators.pdf (roofing filter code, S&P daily anticipatory vs confirmation curves);
InferringTradingStrategies.pdf (RSI/Fisher anticipatory strategies with adverse-excursion reversal: PF 2.05 / 2.10, 57% wins,
bonds, no costs). Data gap: none.

## 9. classic_systems_authors__capstone_gap_continuation_dollar_exits  (David Bean / Capstone NQ gap continuation: four gap types, early-momentum alignment in the first 15 minutes, DOLLAR stop and PT/SL ratio, exits by 15:30)

Priority **4**, complexity **2**, instruments **MNQ** (Bean's product is NQ-only and long-only in the 2020 version), MES as the
cross-check. Bar size: daily gap + 15-min momentum window, 1-min execution. EQ 2 (vendor hypotheticals without slippage, but
the only strategy in this family with year-by-year 2024/2025/2026 numbers, all positive: Gap Continuation 2020 NQ 2024 +$28,190,
2025 +$6,090, 2026 +$6,645, PF 1.87, 59.5% wins, stop $1,225 = $122/MNQ; GC 2026 NQ PF 1.83, avg $164). Report item F7. Shape
(57-60% wins, avg win ~1.3 x avg loss, fixed dollar risk) is exactly the Lucid payout-day shape. Sibling
`trend_momentum__gap_and_go` trades only >= 0.7-ATR gaps outside the prior range with a stop-order break of the first range; this
spec covers Bean's smaller and inside-range gaps, the momentum-close alignment and his dollar exits.

```
PARAMS: gap_set='outside' | 'all' | 'above_only', min_gap_atr=0.15, max_gap_atr=1.5, mom_minutes=15, entry_mode='market_0946' |
  'close_break', stop_mode='dollar' | 'atr', stop_usd={'MNQ': 122, 'MES': 52, 'MGC': 100} (Bean: $1,225 NQ, $525 ES, scaled to
  micros), stop_atr=0.3, tgt_mode='ratio' | 'atr', tgt_ratio=1.3, tgt_atr=0.4, tgt_cap_atr=0.6, last_entry='10:30',
  exit_time='15:30', flat='15:55', sides='long' | 'both', max_trades=1
PRE: PDH, PDL, PDC (prior RTH; PDC = last 1-min close before 16:00, the settlement proxy); O930; atr = ATR14d; gap = O930 - PDC
  gap type: above_high if O930 > PDH; below_low if O930 < PDL; inside_above_close if PDC < O930 <= PDH;
            inside_below_close if PDL <= O930 < PDC;  dir = sign(gap)
  gap_set: 'outside' = {above_high, below_low}; 'all' = all four; 'above_only' = {above_high}
  tradeable = type in gap_set and min_gap_atr*atr <= |gap| <= max_gap_atr*atr and dir in allowed(sides) and not early_close
  MW = opening_range(df1, rth_open, mom_minutes): mw_high, mw_low, mw_close, i_end (the 09:44 bar)
  momentum aligned (Bean's undisclosed "early momentum aligns with the initial move", objective reading [interp]):
     dir = +1: mw_close > O930 and mw_close > (mw_high + mw_low)/2;  dir = -1: mirror
ENTRY 'market_0946': if aligned: place(i_end + 1, dir) market
      'close_break': if aligned: scan 1-min k > i_end with tod < last_entry: first close[k] > mw_high (dir +1) -> place(k+1, +1);
                     mirror for dir -1
STOP:  'dollar': stop_pts = stop_usd[contract] / pv (MNQ 61 pts, MES 10.4 pts, MGC 10 pts); 'atr': stop_pts = stop_atr*atr
TARGET: 'ratio': tgt_pts = tgt_ratio*stop_pts (Bean's PT/SL ratio; Davey: dollar targets beat ATR targets);
        'atr': tgt_pts = min(tgt_atr*atr, tgt_cap_atr*atr)
EXIT: it.exit_at(first bar >= exit_time) (Bean: "exits by 15:30"); set_session(rth_open + mom_minutes, last_entry, flat);
      max_trades_day = 1
RISK: daily_loss_stop = stop_usd[contract] (one full stop); daily_profit_stop inert
```
Grid (<= 48): `gap_set {outside, all}`, `entry_mode {market_0946, close_break}`, `stop_mode {dollar, atr}`, `tgt_ratio {1.0, 1.3,
2.0}` (tgt_mode ratio; one follow-up cell tgt_mode atr 0.4), `sides {long, both}`. Fixed: min_gap_atr 0.15, mom 15 min,
exit 15:30. Also run the best cell year by year 2019-2026 to compare the sign pattern with Capstone's published years (2019 was
their only losing year on the open-range product; GC 2020 NQ positive every year).

Risk/Lucid: $R fixed at $122/MNQ -> 10-12 micros fit the $1,500 rule-of-thumb; 57-60% wins x 1.3 payoff = +$15-20/trade gross
per micro before our $2.30 costs; ~40-60% of sessions qualify under 'all', ~25% under 'outside'. One trade, resolved by 15:30.

Evidence recap: Capstone product pages (hypothetical, no slippage, periodically re-released = survivorship); Bean 2010 book gap
taxonomy. Data gap: Bean's exact momentum filter and the 16:00 vs 16:15 close convention are undisclosed; PDC = last close before
16:00 is our settlement proxy.

## 10. classic_systems_authors__anti_stochastic_hook  (Street Smarts "The Anti": slow stochastic 7/10/3, %K hooks against a rising/falling %D for 3-4 bars then hooks back, stop beyond the hook bar, one-day hold, trend filter)

Priority **2**, complexity **3**, instruments **MNQ**, MES. Bar size: 5-min RTH. EQ 1 (book examples only). A pullback-continuation
engine with small stops and frequent signals; the report's warning is that it fades badly on rotational days, hence the trend
filter is in the grid, not optional.

```
PARAMS: bar=5, k_len=7, k_smooth=10, d_smooth=3, hook_min=3, hook_max=4, trend_filter='sma_d200' | 'adx5' | 'none', adx_min=25,
  near_d=5 (points of stochastic; the hook must still be at/below %D + near_d), stop_cap_atr=0.30, min_stop_atr=0.05,
  tgt_mode='rr' | 'atr', rr=1.5, tgt_atr=0.4, tgt_cap_atr=0.6, valid_bars=10 (1-min bars = 2 x 5-min bars), first_entry='10:00',
  last_entry='15:00', flat='15:55', sides='both', max_trades=3
PRE: B5 continuous RTH. rawK = 100*(C - LL(k_len))/(HH(k_len) - LL(k_len)); slowK = SMA(rawK, k_smooth); slowD = SMA(slowK, d_smooth)
  ([interp] of "7, 10, 3": fast %K 7, slow %K 10, %D 3; the book's slow stochastic)
  dD[k] = slowD[k] - slowD[k-1]; dK[k] = slowK[k] - slowK[k-1]
  LONG hook at bar k: dD[k] > 0 (trend up by %D) and dK[k] > 0 (hooks back) and n in [hook_min, hook_max] where n = number of
    consecutive bars j = k-1, k-2, ... with dK[j] < 0 (the pullback) and slowK[k] <= slowD[k] + near_d (not already resolved)
  SHORT hook: mirror (dD < 0, dK < 0, n up-bars, slowK >= slowD - near_d)
  trend_filter 'sma_d200': longs only if the lagged cash-index close > SMA_D(200), shorts only if below;
               'adx5': adx(B5, 14)[k] > adx_min (either side); 'none'
ENTRY at i = B5.i_next[k]: place(i, +1, entry_px = high[k] + tick, kind='stop', valid_bars, stop_px, tgt_pts)  (short mirror)
STOP:  stop_px = low[k] - tick (hook bar low); if entry_px - stop_px > stop_cap_atr*ATR14d -> stop_pts = cap; floor min_stop
TARGET: 'rr': tgt_pts = rr*R; 'atr': tgt_pts = tgt_atr*atr; both <= tgt_cap_atr*atr
SESSION: set_session(first_entry, last_entry, flat); max_trades_day = 3 (book: "held strictly one day")
RISK: daily_loss_stop MNQ $80 / MES $60; daily_profit_stop MNQ $160 / MES $120
```
Grid (<= 48): `trend_filter {sma_d200, adx5, none}`, `(tgt_mode, value) {(rr, 1.5), (atr, 0.4)}`, `stop_cap_atr {0.2, 0.3}`,
`hook_min {2, 3}`, `sides {both, long}`. Fixed: 7/10/3, hook_max 4, near_d 5, valid 10 min.

Risk/Lucid: hook-bar stops are 0.05-0.15 ATR ($40-120/micro): 10+ micros feasible but the win rate on noise-sized stops is the
risk (cf. mr_ibfail). Expect 1-3 trades/day; the profit stop and `max_trades 3` cap the day.

Evidence recap: Street Smarts ch. 8; roboforex parameter summary. Data gap: none.

## 11. classic_systems_authors__collins_bias_open_to_close  (Art Collins: combined small biases scored +1/-1, open-to-close trade at 09:31 with a disaster stop and a consistency cap; also the per-day score for the overlay in spec 14)

Priority **2**, complexity **2**, instruments **MNQ**, MES (Collins' acceptance rule: must work on both). Bar size: daily, 1-min
execution. EQ 2 (book tables 1990s-2005, not retrievable; Better System Trader interview). Collins' trades carry no stop and hold
open-to-close; the Lucid translation adds a 0.4-0.6 ATR stop and a 0.8 ATR cap, which turns it into a capped daily-bias trade.
Its main value is `mode='filter'`: the daily score becomes a gate for the ORB/pinball specs.

```
PARAMS: biases=('two_same_way', 'hl15', 'dow') | + 'open_vs_close', threshold=2, mode='trade' | 'filter', stop_atr=0.6,
  tgt_cap_atr=0.8, entry_tod='09:31', flat='15:55', sides='both', max_trades=1
PRE (D daily RTH, sessions < d, except open_vs_close which uses O930):
  two_same_way: +1 if oc[d-1] < 0 and oc[d-2] < 0 (two down open-to-closes -> buy the open); -1 if both > 0; else 0   [book]
  hl15:         +1 if close[d-1] > mean((high + low)/2 over d-15 .. d-1) else -1                                      [book]
  dow:          +1 if weekday(d) in {Mon, Tue}; 0 otherwise                      (Collins: long bias early in the week [interview])
  open_vs_close: +1 if O930 < PDC, -1 if O930 > PDC, 0 if equal   (fade the open vs the prior close [interp]; grid in/out)
  score[d] = sum over the selected biases; side = +1 if score >= threshold, -1 if score <= -threshold (and in sides), else none
  tradeable = side and ATR14d notna and not early_close
ENTRY mode='trade': place(index of the bar with tod == entry_tod, side) market
STOP:  stop_pts = stop_atr*atr (disaster stop; Collins has none - his book P&L is the stop-less open-to-close)
TARGET: tgt_pts = tgt_cap_atr*atr (consistency cap; `inf` for the funded-only run)
EXIT: flat at `flat`; set_session(entry_tod, entry_tod + 1 min, flat); max_trades_day = 1
mode='filter': no orders; write score[d] to the daily output (consumed by spec 14 as `gate='collins'`)
RISK: daily_loss_stop inert; $R = 0.6 ATR = $480/MNQ -> 2-3 micros only
```
Grid (<= 24): `biases {two_same_way only, two_same_way + hl15, all four}`, `threshold {1, 2}`, `stop_atr {0.4, 0.6}`, `sides {both,
long}`. Fixed: tgt_cap_atr 0.8 (one uncapped funded-only run on the best cell).

Risk/Lucid: wrong shape for the eval on its own (one big daily range per trade; the $2,000 intraday floor is one bad day away
at 5 micros); the capped version in 2-3 micros is a low-variance "many small days" leg if the biases hold; otherwise filter only.

Evidence recap: Collins 2006 [book] TOC and interview; no modern OOS. Data gap: none.

## 12. classic_systems_authors__davey_count_pullback_dollar_target  (Kevin Davey published pattern 1: up/down-close count over BCount bars with a pullback entry, exits per his 567k-backtest study: fixed DOLLAR target / stop or stop-and-reverse)

Priority **1**, complexity **2**, instruments **MNQ**, MES, MGC (Davey: only indices and metals had positive average returns).
Bar size: 15 or 30 min RTH (Davey's samples are 60-min to daily; 60-min bars give < 1 signal/day inside RTH). EQ 2 (sample
equity curves only for the pattern; the exit study is large but vendor-run). Included mainly to test the exit finding on a
neutral entry: dollar target vs stop-and-reverse.

```
PARAMS: bar=15, bcount=10, pullback=3, exit_mode='dollar' | 'sar', tgt_usd={'MNQ': 150, 'MES': 75, 'MGC': 150},
  stop_usd={'MNQ': 150, 'MES': 75, 'MGC': 150}, first_entry='10:00', last_entry='14:30', flat='15:55', sides='both', max_trades=2
PRE: B = resample(df1, bar, rth_only=True) continuous RTH; up[j] = close[j] > close[j-1]
  ups[k] = sum(up[k-bcount+1 .. k]); dns = bcount - ups
  long_pat[k]  = ups > dns and close[k] < close[k-pullback]     (Davey pattern 1: majority up closes, short-term pullback)
  short_pat[k] = dns > ups and close[k] > close[k-pullback]
ENTRY at i = B.i_next[k] when flat and the pattern is true and first_entry <= tod(i) < last_entry:
  'dollar': place(i, side, stop_pts = stop_usd/pv, tgt_pts = tgt_usd/pv)
  'sar':    place(i, side, stop_pts = stop_usd/pv (disaster), no target); on the first later bar k' with the opposite pattern:
            it.exit_at(B.i_next[k'], side) and place(B.i_next[k'] + 1, -side, ...) (stop-and-reverse, Davey's best exit);
            flat at 15:55 (no overnight)
SESSION: set_session(first_entry, last_entry, flat); max_trades_day = 2 ('dollar') / 4 ('sar')
RISK: daily_loss_stop = stop_usd[contract]; daily_profit_stop = 2 x tgt_usd
```
Grid (<= 32): `bar {15, 30}`, `bcount {8, 12}`, `pullback {2, 4}`, `exit_mode {dollar, sar}`, `tgt_usd {100, 200}` (MNQ; MES
half, MGC same; stop_usd = tgt_usd). Fixed: sides both.

Risk/Lucid: $R fixed $100-200/micro, 1-2 trades/day; the dollar-target cells produce the capped-day shape by construction.
Expect PF near 1 (the entry has no evidence); the information is in the exit comparison.

Evidence recap: kjtradingsystems.com 15 patterns article and exits article (stop-and-reverse > dollar target > breakeven;
dollar > ATR; targets > stops; trailing/parabolic/chandelier worst; indices and metals positive). Data gap: none.

## 13. classic_systems_authors__williams_volbreak_filters  (Larry Williams volatility breakout with HIS filters: buys after a down close / sells after an up close, trade-day-of-week, DOLLAR stop instead of the full reverse, bond filter flagged; parameter set on `vb_orbp`)

Priority **2**, complexity **1** (adds `stop_mode='dollar'`, `tdw` and the optional bond gate to `vb_orbp`), instruments **MNQ**,
MES, MGC. Bar size: daily + 1-min. EQ 2 (book in-sample S&P 1982-98 tables "80%+ profitable with the bond filter" [book]; modern
ORB literature: gross edge within slippage unless filtered). `trend_momentum__williams_volbreak` and `vb_orbp` already test the
bare rule with ATR-fraction stops; what is untested is Williams' own package: the down-close direction filter (already `bias=
'down_close_long'` in the module), his TDW and a fixed dollar stop ($150-250 per micro) with the EOD exit.

```
PARAMS (vb_orbp conventions): k=0.6, unit='range' (yesterday's RTH range) | 'swing', bias='down_close_long' | 'pd_mid' | 'none',
  tdw=None | 'mon_tue_long' (longs only Mon/Tue, shorts only Wed-Fri [book TDW tables, S&P]), stop_mode='dollar' (NEW) | 'frac' |
  'open', stop_usd={'MNQ': 150, 'MES': 100, 'MGC': 150}, stop_frac=0.5, max_stop_atr=0.5, tgt_mode='eod' (Williams: exit at the
  close) with tgt_cap_atr=0.8 | 'frac' 0.5, entry_cutoff='12:00', ws_skip=1.5, bond_filter=False (DATA GAP, see below),
  flat='15:55', max_trades=1
PRE: rng = high[d-1] - low[d-1]; U = k*rng; O = open[i0]; up = O + U + tick; dn = O - U - tick; C1 = close[d-1]; C2 = close[d-2]
  allowed sides: 'down_close_long': {+1} if C1 < C2 else {-1} (Williams: buy breakouts after a down close, sell after an up close);
  'pd_mid' / 'none' as the module; tdw intersects: 'mon_tue_long' -> longs only if weekday in {0,1}, shorts only otherwise
  bond_filter (if True and a ZB daily series exists): longs only if ZB_close[d-1] > ZB_close[d-6]; shorts only if below
  tradeable = U <= max_stop_atr*ATR14d*2 and (ws_skip == 0 or rng <= ws_skip*ATR14d) and not early_close
ENTRY: resting stop order(s) from i1 at up / dn on the allowed side(s), valid to entry_cutoff, resolved on 1-min bars as the module
STOP:  'dollar': stop_pts = stop_usd[contract]/pv (MNQ 75 pts, MES 20 pts, MGC 15 pts); 'frac': stop_frac*U; 'open': back to O;
       all capped at max_stop_atr*ATR14d
TARGET: 'eod': none, flat 15:55, hard cap tgt_cap_atr*ATR14d; 'frac': tgt_pts = 0.5*U
SESSION: set_session(rth_open, entry_cutoff, flat); max_trades_day = 1; daily_loss_stop = stop_usd (one stop)
```
Grid (<= 24): `k {0.5, 0.6, 0.8}`, `bias {down_close_long, pd_mid}`, `stop_mode {dollar, frac}`, `tdw {None, mon_tue_long}`.
Fixed: unit range, tgt eod (cap 0.8), cutoff 12:00, ws_skip 1.5.

Risk/Lucid: $R = $150/MNQ fixed; k = 0.6 on NQ triggers 150-240 pts from the open so many days never trigger (~40% trigger rate):
one trade on ~2 days a week, EOD exits with a 0.8-ATR cap -> largest-day share must be checked (the EOD carry is the edge and the
consistency risk at once).

Data gap: **T-bond daily closes are not in `data/parquet`** (no ZB/ZN parquet). The bond filter is the filter Williams credits
for most of his S&P improvement; it can only be tested if `ZB=F` (or `^TNX` inverted) daily closes are downloaded from Yahoo into
`data/parquet/ZB_1d.parquet` with a one-day lag. Until then `bond_filter=False` and the spec tests the down-close and TDW filters
only.

## 14. classic_systems_authors__regime_filter_overlay  (infrastructure: per-session gates from Kaufman's efficiency ratio, Wilder's daily ADX, the Turtle "skip after a winner" rule, DeMark's TD-9 no-chase count and the Collins score; consumed as a `gate` parameter by the breakout specs and inverted by the fade specs)

Priority **2**, complexity **2** (one helper module `strategies/common_gates.py` + a `gate` parameter in the consuming modules),
instruments all. EQ 2 (Kaufman's ER and Wilder's ADX are standard regime measures with daily evidence; the Turtle skip rule is
historical; TD-9 has no ES test). Not a strategy: it is the family's answer to "Filters to test on all of them" in report s.30.

```
GATES (per session d; all computed on D daily RTH bars or the cash-index daily closes, strictly lagged):
  er_trend[d]:    ER10 = |close[d-1] - close[d-11]| / sum_{j=d-10..d-1} |close[j] - close[j-1]|;  er_trend = ER10 >= 0.30
                  (Kaufman: ER > ~0.3 trending -> allow breakouts; < 0.3 noisy -> allow fades / stand aside)
  adx_trend[d]:   ADX14 = adx(D, 14)[d-1] > 25;  adx_rising[d] = ADX14[d-1] > ADX14[d-2]   (Wilder / LeBeau: trend systems only
                  when ADX > 20-25 and rising; counter-trend when falling from above 30)
  prev_trend_day[d]: |oc[d-1]| >= 0.5*ATR14d[d]   (proxy for the Turtle "last breakout was a winner" rule: a breakout that worked
                  yesterday -> skip today's; the exact rule needs the strategy's own prior-trade outcome, available in the
                  stop-order modules via their pre-walk as `prev_trade_won[d]`; implement both, report both)
  td9_nochase (intraday, B5): count_up[k] = consecutive bars with close[k] > close[k-4] (reset otherwise); when count_up reaches 9
                  set no_chase_long for the next 12 B5 bars (and mirror for shorts). DeMark: exhaustion after a 9-count; used only
                  to BLOCK breakout entries in that direction, never to enter.
  collins[d]:     score from spec 11 (`mode='filter'`); gate = sign(score) must agree with the trade side (|score| >= 1)
CONSUMERS: breakout specs 4, 5, 6, 7, 9, 13 and orb_crabel / vb_orbp / orb_close30 take `gate in {none, er_trend, adx_trend,
  adx_rising, not_prev_trend_day, td9_nochase, collins}`; the fade specs 1, 3 and spec 8 take the inverse (`er_noise` = ER10 < 0.3,
  `adx_rotation` = ADX14 < 25).
VALIDATION PROTOCOL: for each consumer's best ungated cell, run every gate on the same days; adopt a gate only if PF improves on
  BOTH MAIN and PRIOR, the trade count stays >= 60% of the ungated count, and the improvement is not carried by one month.
  Also report the gate's hit rate (share of sessions allowed) so a gate that simply halves trading is not mistaken for an edge.
```
Grid: the gate values above (7 per consumer); no numeric grid (ER 0.30 and ADX 25 are the published thresholds; do not tune them).

Risk/Lucid: gates lower frequency; the Lucid Monte Carlo pass-within-21-sessions rate is the metric that decides whether a gate
is worth its trade count, not PF alone. Data gap: none.

## 15. classic_systems_authors__gapfill_0932_control  (Capstone ES GAPF-style 09:32 gap fade with a fixed dollar PT/SL: DECAYED-REGIME CONTROL, expected to lose on 2025-26)

Priority **1**, complexity **1**, instruments **MES**, MNQ. Bar size: daily gap, 1-min. EQ 2 for the decay itself (Capstone ES GAPF
I: 2023 +$15,925, 2024 -$100, 2025 +$475, 2026 YTD -$3,675; ES Mirror 2020 negative 2024-26; our `mr_gapfade` MES PF 0.79 on
MAIN). Purpose: a cheap control that the backtest reproduces the published sign flip, and a year-by-year regime series for the
family. Not a candidate.

```
PARAMS: entry_tod='09:32', min_gap_atr=0.10, max_gap_atr=0.70, require_inside=True (open inside the prior RTH range; outside opens
  are gap-and-go days per Bean's taxonomy), stop_usd={'MES': 50, 'MNQ': 100}, tgt_usd={'MES': 70, 'MNQ': 140} (Bean: 700 PT /
  500 SL per ES, scaled to micros; MNQ doubled for its larger $ gaps), tgt_mode='min_pdc_dollar', exit_time='11:00', flat='15:55',
  sides='both', max_trades=1
PRE: PDC, PDH, PDL, O930, atr = ATR14d; gap = O930 - PDC; dir = sign(gap)
  tradeable = min_gap_atr*atr <= |gap| <= max_gap_atr*atr and (not require_inside or PDL <= O930 <= PDH) and not early_close
  skip if the gap already filled in the 09:30-09:31 bars (long fade: any low <= PDC; short fade: any high >= PDC)
ENTRY: place(index of the bar with tod == 09:32, -dir) market  (fade toward the prior close)
STOP:  stop_pts = stop_usd[contract]/pv (MES 10 pts, MNQ 50 pts)
TARGET: tgt_px = PDC but never farther than tgt_usd/pv from the fill (tgt_pts = min(|PDC - open[i]|, tgt_usd/pv))
EXIT: it.exit_at(first bar >= exit_time); set_session('09:32', '09:33', flat); max_trades_day = 1
RISK: daily_loss_stop inert (one trade)
```
Grid (<= 8): `require_inside {True, False}`, `exit_time {11:00, 15:30}`, `sides {both, long}`. Run by calendar year 2019-2026 on
MES and MNQ; the expected pattern is PF > 1 through 2023 and <= 1 in 2024-26 on MES. If MES MAIN shows PF > 1.2, check the engine
(settlement proxy, slippage on the 09:32 market fill) before anything else.

Risk/Lucid: n/a (control). Data gap: Bean's gap definition uses the 16:00 settlement; PDC = last 1-min close before 16:00.

---

## Dropped or folded (and why)

- **Turtle System 1 / 2** (s.1): multi-week holds; forbidden overnight. N-based sizing is already what `lucid_scan` does with
  the intraday DD; the "skip after a winner" filter -> spec 14; a 55/20-bar intraday Donchian has no evidence and the gold
  Donchian is `trend_momentum__gold_donchian_intraday`.
- **Williams %R** (s.5): folded into spec 8 (`osc='wpr'`); the only open question is Ehlers' anticipatory vs confirmation entry.
- **Holy Grail** (s.9): `trend_momentum__holy_grail_pullback` already specifies it (ADX 25/30, 5/15-min, swing vs Keltner stop).
- **Williams volatility breakout** bare rule (s.4): `vb_orbp` module + `trend_momentum__williams_volbreak`; spec 13 adds only the
  author's filters and the dollar stop.
- **Crabel stretch ORB** bare rule (s.13): `orb_crabel` module (results in `results/orb_crabel/README.md`); spec 5 adds the
  untested entry/stop/target modes. Crabel ORB II (wide first-5-min bar as the entry) is the `volatility_breakout__
  expansion_bar_control` negative control (Mesfin 2026 falsified it); not re-specified.
- **Bernstein 30-min breakout** (s.27): `orb_close30` module / `orb_session__orb_close_confirm_capped`. Bernstein's gap method is
  the 09:32-type fade (spec 15 / `mr_gapfade`).
- **Unger Strategy 1 / 2** (s.19): `intraday_mean_reversion__turtle_soup_pd_recross` and `__session_low_limit_dip`; the gold
  time-of-day bias is `calendar_seasonal_structural__gold_clock_legs`.
- **Capstone ES GAPF / ES Mirror** (s.24): decayed by the vendor's own numbers and by `mr_gapfade`; kept only as the control
  (spec 15). **NQ Open Range 2026** (37% wins, $2,213 avg winner): the wrong shape for the 50% consistency rule; its mechanics are
  `orb_session__orb_long_carry` (EOD / trailing carry with a cap), not re-specified.
- **80-20s as a stand-alone** (s.7): `intraday_mean_reversion__eighty_twenty_filter` and spec 1 (`setup='eighty_twenty'`).
- **Kaufman KAMA crossover** (s.16): lagging trend follower, whipsaws intraday; the efficiency ratio -> spec 14.
- **DeMark TD Sequential** (s.17): 0-2 signals/day, discretionary perfection / cancellation rules, counter-trend on trend days;
  TD-9 -> the no-chase gate in spec 14.
- **Wilder DMI crossover / Parabolic SAR / Volatility System** (s.22): always-in stop-and-reverse systems whipsaw on 5-min bars
  and Davey ranks parabolic exits below dollar targets; PSAR / Supertrend flips are in bot_popular_indicators; ADX -> spec 14.
- **LeBeau** (s.23): exits only. Chandelier is `bot_popular_indicators__chandelier_ema200_flip`; the Yo-Yo stop (close - 2 x
  ATR(14, 5-min), re-anchored each bar) is a reasonable disaster stop but the engine's `trail_pts` ratchet already covers the
  use case; not specified separately.
- **Bandy** (s.25): a sizing/evaluation framework (CAR25 / safe-f), already embodied in `backtest.lucid` Monte Carlo and the
  `exp_net_lb` sizing rule; multi-day equity reversion is not tradable here.
- **Penfold** (s.26): the key-reversal bar -> spec 2; the P24 cross-market acceptance test is the acceptance rule for specs 2, 3,
  11 (MNQ and MES must both be >= PF 1.1 before a cell counts).
- **Ruggiero** (s.28): report-day fade needs an economic calendar (not available; fixed 08:30 / 14:00 times are covered by
  `calendar_seasonal_structural__macro_0830_spike_fade` and `__fomc_post_announcement_fade`); the intermarket bond / S&P filter
  needs a T-bond daily series that is not in `data/parquet` (same gap as spec 13); adaptive channel length needs a cycle
  measurement with no published intraday evidence. Dropped.
- **Stridsman Meander** (s.29): spec 1 (`setup='meander'`). Harris 3L-R, Dynamic Breakout, Hybrid No. 1: no rules retrievable.
- **Davey's other 14 patterns** (s.18): sample curves only; pattern 1 (spec 12) carries the exit-study test; the rest add
  parameters without evidence.
- **Collins open-to-close as published (no stop)** (s.20): one bad NQ day ($2,500-4,000 per mini) can breach the $2,000 intraday
  floor; only the stopped, capped version (spec 11) is specified.

Nothing in this family needs volume, order flow, DOM or options data; no approximation was required.

## Summary table

| # | id | priority | complexity | instruments | bar | one-line |
|---|---|---|---|---|---|---|
| 9 | classic_systems_authors__capstone_gap_continuation_dollar_exits | 4 | 2 | MNQ, MES | daily gap + 15-min window | Bean's NQ gap continuation, dollar stop/PT ratio, flat 15:30 |
| 4 | classic_systems_authors__momentum_pinball | 3 | 2 | MNQ, MES, MGC | daily LBR/RSI + 60-min OR | Street Smarts pinball: filtered first-hour ORB after 10:30 |
| 5 | classic_systems_authors__crabel_stretch_close_confirm | 3 | 1 | MNQ (MES check) | daily stretch + 1/5-min | orb_crabel with close confirmation, stop at the open, ATR target |
| 7 | classic_systems_authors__acd_time_confirm_failed_a | 3 | 4 | MNQ, MES, MGC | 15-min OR + 1-min state machine | Fisher ACD: A by time, C reversal after a failed A |
| 8 | classic_systems_authors__ehlers_anticipatory_oscillator | 3 | 4 | MES, MNQ | 5-min | roofing-filter stochastic, anticipatory entries, adverse-excursion reversal; confirm control |
| 1 | classic_systems_authors__pd_extreme_stop_reentry_setups | 2 | 2 | MNQ, MES | daily + 1-min | Oops / ADX Gapper / 80-20 / Meander filters on the PDH-PDL stop re-entry |
| 2 | classic_systems_authors__daily_reversal_bar_stop_entry | 2 | 2 | MNQ, MES, MGC | daily + 1-min | Smash Day, Whiplash, key reversal: next-day stop beyond the pattern bar |
| 3 | classic_systems_authors__turtle_soup_20day | 2 | 3 | MNQ, MES, MGC | daily 20-day level + 1-min | book Turtle Soup / Plus One with the 4-day age rule |
| 6 | classic_systems_authors__nr_pattern_bar_intraday | 2 | 2 | MNQ, MES, MGC | 15/30-min | intraday NR4/NR7/ID bar breakout, next-bar validity, EMA20 filter |
| 10 | classic_systems_authors__anti_stochastic_hook | 2 | 3 | MNQ, MES | 5-min | The Anti: stochastic 7/10/3 hook, trend-filtered |
| 11 | classic_systems_authors__collins_bias_open_to_close | 2 | 2 | MNQ, MES | daily + 1-min | combined biases score, capped open-to-close trade / filter |
| 13 | classic_systems_authors__williams_volbreak_filters | 2 | 1 | MNQ, MES, MGC | daily + 1-min | vb_orbp with Williams' down-close, TDW, dollar stop; bond filter flagged |
| 14 | classic_systems_authors__regime_filter_overlay | 2 | 2 | all | daily / 5-min | ER, ADX, skip-after-winner, TD-9, Collins gates with a validation protocol |
| 12 | classic_systems_authors__davey_count_pullback_dollar_target | 1 | 2 | MNQ, MES, MGC | 15/30-min | Davey pattern 1 with dollar target vs stop-and-reverse exits |
| 15 | classic_systems_authors__gapfill_0932_control | 1 | 1 | MES, MNQ | daily + 1-min | decayed ES gap-fill control, year-by-year |

## Validation protocol and notes for the backtest agents

1. Order of work: spec 9 (the only 2024-26 evidence), then 4 and 5 (cheapest, one trade/day, capped risk), then 7 and 8 (the two
   intraday engines), then the rest as portfolio candidates. Spec 15 runs once as a control before any of them.
2. Every spec: run the published defaults first (`PARAMS` = the book rule), then the grid, on MAIN 2025-01..2026-09 and PRIOR
   2023-01..2024-12; a cell counts only if PF >= 1.1 on both, the grid is a plateau and no month carries > 40% of the net.
   Then `lucid_scan`; only a `recommended` size (positive bootstrap lower bound, beats the zero-edge control by >= $100) counts.
3. Cross-market acceptance (Collins / Penfold): for the daily-pattern specs (1, 2, 3, 11) a cell that is positive on MNQ but
   negative on MES with the same parameters is reported as "single-market", not adopted.
4. Controls built into the grids: spec 8 `mode='confirm'`, spec 4 `lo=hi=50`, spec 15 as a whole, and the ungated cell of every
   spec 14 consumer. If a control wins, look for a bug before looking for an edge.
5. Pre-walk modules (3, 4, 7, 8, 12 re-entries / reversals): verify on sampled days that the module's computed stop bar equals the
   engine's recorded exit bar; any disagreement is a look-ahead or fill-convention bug.
6. Report per `results/<id>/README.md` as the guide requires: rules as implemented, metrics per period, exit-reason cohorts,
   the consistency and payout-day arithmetic at the chosen size, and the honest verdict.
