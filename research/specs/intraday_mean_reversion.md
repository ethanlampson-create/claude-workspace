# Specs: Intraday mean-reversion strategies for the Lucid 50K LucidFlex backtest

Source report: `/home/user/claude-workspace/research/families/intraday_mean_reversion.md` (items 1-26) and
`/home/user/claude-workspace/research/findings/intraday_mean_reversion.json`. Engine contract:
`/home/user/claude-workspace/docs/STRATEGY_GUIDE.md`, `backtest/engine.py` (`Intents.place / set_session / exit_at`,
`max_trades_day`, `daily_loss_stop`, `daily_profit_stop`; one position and one pending order at a time; OHLC only, no volume),
helpers in `strategies/common.py` (`atr`, `ema`, `sma`, `rsi`, `adx`, `session_vwap` (= TWAP), `prior_day_stats`,
`overnight_range`, `opening_range`, `daily_atr`, `vix_lag1`, `session_info`) and `backtest.data.resample(df1, N, rth_only)`
(N-minute bars with `i_next`, the first 1-minute index after the N-minute bar closes; `-1` = session ended, skip).

**State of play in this family (read before running anything).** Seven modules already exist; five have results:

| module | report item | status (per micro, MAIN 2025-01..2026-09 / PRIOR 2023-24) |
|---|---|---|
| `strategies/mr_gapfade.py` | 7 | **marginal, best of the family**: MNQ, gap_max 0.35, 09:31 market entry, 1x-gap stop, full-fill target, 11:00 exit: PF 1.56 / 114 trades / Sharpe 1.51 / 57% pos days; PRIOR PF 1.22 / 130 trades. ~5 trades/month. Lucid 10 micros: pass 0.37, P(payout) 0.19, +$330/eval, monthly pass rate bimodal. MES dead (0/36 cells). |
| `strategies/mr_pdrange.py` | 9, 10 | **marginal**: only the Williams Oops STOP-entry re-cross holds (MNQ both sides, max_dist 0.50, tgt 0.5 ATR: PF 1.39 / 47 trades MAIN, 1.56 / 53 PRIOR, ~2 trades/month). 09:35 market fade (edgeful) is not an edge. Lucid: median 79 days to pass, exp. net lower bound negative. MES rejected. |
| `strategies/mr_wkopen.py` | 24 | **marginal / dead standalone**: touch rates reproduce (89% by 11:30 at < 0.25%) but only ~20% of weeks qualify and 39% of those touch WO inside the 09:30 bar. MES max_dist 0.50: PF 2.09 / 35 trades MAIN but 0.67 PRIOR; MNQ 1.27 / 21 MAIN, 1.59 / 43 PRIOR. <= 2 trades/month/instrument. Leg only. |
| `strategies/mr_volband.py` | 19 | **marginal, regime fit**: paper defaults MNQ PF 1.13 / 88 MAIN, 0.83 PRIOR; MGC (rv20) 1.43 MAIN / 0.71 PRIOR (gold bull artefact); 70 of 72 grid points negative on PRIOR. Only `band` target + long-only survives both periods (PF 1.41 / 1.38) at ~26 trades/yr, $5/trade. |
| `strategies/mr_ibfail.py` | 15 | **dead**: MNQ MAIN PF 1.04 / 253 trades, PRIOR 0.79; MES negative both; rank correlation between periods -0.70. The 1-tick-beyond-extreme stop (~0.10 ATR) is noise-sized and hit 56% of the time. |
| `strategies/mr_bbfade.py` | 3 | **dead at defaults**: MNQ MAIN 812 trades, 61% win, PF 0.90, net -$3,436, DD -$7,347 per micro, 38% positive months. Grid did not complete (`grid_main_MNQ.log` empty). |
| `strategies/mr_onrev.py` | 25 | module exists, **no results yet** (needs the three-leg portfolio run). |
| `strategies/twap_revert.py` | 1, 2 | baseline module from the engine build, **no results yet**; limit-entry TWAP band fade (VWAP proxy). |

The specs below (a) restate every codeable strategy in the family with complete rules so a fresh agent can implement or
re-implement it, (b) name the existing module where one exists and put ONLY the untested deltas in the grid (never a re-run
of a dead cell), (c) give priorities posterior to those results, not just to the literature. The family's two structural
lessons so far: **(i) stops expressed as "1x the setup distance" or "1 tick beyond the extreme" are noise-sized on 2025-26
NQ/ES and get hit before the (statistically likely) reversion; every spec below floors the stop in ATR terms; (ii) the
large-sample touch/fill statistics (60-93%) are base rates, not P&L: with a 1:1 bracket a 55% touch rate is break-even after
costs. A fade needs either a confirmation entry (stop order after the failure) or an asymmetric exit (band/level target that
is nearer than the stop but hit > 60% of the time).**

## 0. Conventions used by every spec below

Times: all **ET**. Data session 18:00 -> ~16:14 ET next day for the index CFD proxies, 18:00 -> 17:00 for gold. RTH equities
09:30-16:00; gold pit 08:20-13:30 (gold trades ~23h). A 1-minute bar with `tod = T` covers `[T, T+1)`. "5-min close at
10:00" means the close of the 5-min bar whose last 1-min bar has `tod = 09:59`; the decision uses that close and the order is
placed at `i_next` (the 1-min bar with `tod = 10:00`), i.e. **market at next open (+1 tick slippage)** unless the spec says
stop/limit. `i_next == -1` -> skip. Decisions never use the open of the bar the order is placed on, except where a spec
explicitly uses the 09:30 open `O930` and then places the order at the **09:31** bar (`i0 + 1`), exactly as `mr_gapfade`,
`mr_pdrange` and `mr_wkopen` do.

Forced flat: equities **15:55** (never later than 15:58); gold pit specs **13:25**; gold specs that use the 09:30 clock
(spec 7) flat 15:55 (within the 16:45 limit). No overnight, no weekends. Early-close sessions (`session_info().early_close`)
are skipped for entries after 12:00.

Instruments: **MNQ (NSXUSD) first** for every index spec (MES has been dead on gapfade, pdrange, ibfail and wkopen-PRIOR:
the targets in ES points are too small against the fixed $3.80 round trip), MES second, MGC only where the spec says so.

Indicators (exact definitions):
- `ATR14d` = `daily_atr(df1, 14, rth_only=True, rth=(rth_open, rth_close))`: Wilder ATR of RTH daily bars, shifted one day
  (session d uses days < d). NaN -> no trade. 2025-26 medians: NDX ~398 pts, SPX ~76 pts, GC (pit) ~69 pts. **Every stop,
  cap and distance filter is expressed in ATR fractions or % of price, never fixed points.**
- `PDH / PDL / PDC` = prior RTH high / low / close (`prior_day_stats`, 1-day lag; PDC = last 1-min close with tod < 16:00,
  never the 16:14 / 17:00 print). `pd_rng = PDH - PDL`; `pd_mid = (PDH+PDL)/2`; `in_value[d] = PDL <= O930 <= PDH`.
- `O930` = open of the first RTH 1-min bar (`tod == rth_open`); `gap = (O930 - PDC)/PDC` (fraction; `gap_pct` in %).
- `B1` = RTH 1-min bars; `B5` = `resample(df1, 5, rth_only=True, rth=(rth_open, rth_close))`; `B15` likewise with 15.
  `B5all` = `resample(df1, 5, rth_only=False)` (all session bars, used when an indicator needs > 1 session to mature, as
  `mr_bbfade` does); entries from `B5all` are still restricted to the RTH entry window.
- `OR(N)` = `opening_range(df1, rth_open, N)` -> `or_high, or_low, i_end`; `or_rng`, `or_mid`. Valid only at indices > `i_end`.
- `IB` = `OR(60)` (09:30-10:29). `ON` = `overnight_range(df1, rth_open)` -> `on_high, on_low` (18:00 -> rth_open); `on_rng`,
  `on_mid`; valid only after the RTH open.
- `VIX_lag` = `vix_lag1(df1)` (prior session's VIX close). `VIX_hot[d]` = the quartile gate of `mr_gapfade.vix_regime(df1,
  lb=100, q=0.75)`: True when VIX_lag >= low + 0.75 x (high - low) of the trailing 100 VIX closes ending at VIX_lag.
  `VIX_gate_seeck[d]` = VIX_lag < 20 or VIX_lag >= 30 (Seeck). NaN VIX -> no trade when a gate is on.
- `ATR5(n)` = Wilder ATR on 5-min bars; `ADX5(n)` = `adx(B5all, n)`; `RSI(n)` = Wilder RSI (`common.rsi`); `SMA/EMA` as in
  `common`. `min_periods` = full window; NaN rows never trade.
- `TWAP_t` = `session_vwap(bars)` = cumulative mean of typical price `(H+L+C)/3` from the session anchor (**VWAP proxy, no
  volume: flagged in every spec that uses it**). `TWAPsd_t` = cumulative stdev of typical price from the same anchor.
- `R` = |entry - initial stop| in points; `$R = R x point_value` (MNQ $2/pt, MES $5/pt, MGC $10/pt). Costs in the engine:
  $1.30 RT + 1 tick slippage per side on market/stop fills (MNQ $2.30, MES $3.80, MGC $3.30 per round trip); limit fills
  carry no slippage but need a 1-tick trade-through.

Lucid risk block (default for every spec unless the spec overrides it):
- `daily_loss_stop` (no new entries once realized day P&L <= -X per micro): MES $60, MNQ $80, MGC $80; for one-trade-per-day
  specs it is set to the maximum single stop so a full stop-out halts the day.
- `daily_profit_stop` (no new entries once realized day P&L >= Y per micro): MES $120, MNQ $160, MGC $160. Inert with
  `max_trades_day = 1`; it matters for the multi-trade specs (10-16).
- Both only block NEW entries; an open position runs to its own stop/target/time/flat. Every entry has a hard protective stop.
- Consistency arithmetic: at the moment of passing a $3,000 eval no single day may exceed $1,500. With 10 micros the
  per-micro largest day must stay <= $150: level targets (prior close, band, OR edge) do this by construction; open-to-close
  holds (spec 7) and ATR targets >= 0.75 ATR (spec 4) do not, so those specs carry a `tgt_cap_atr` (default 0.6 ATR).
- Payout arithmetic: 5 days >= $150 at the funded size. High-frequency capped specs (10-13) produce the most such days;
  the 1-2 trades/month specs (5, 18) the fewest and cannot carry an evaluation alone (their Lucid results say so).
- One position at a time, one pending order at a time; `set_session(entry_start, entry_end, flat)` on every spec.

Priority: 5 = best prior of working under Lucid constraints with evidence **and** our results, 1 = long shot / control.
Complexity: 1 = a parameter on an existing module, 5 = multi-state intraday machine.

Benchmarks every spec must beat on 2025-01..2026-09: `mr_gapfade` MNQ (PF 1.56 / 114 trades, +$330/eval at 10 micros) as the
family's best, and the time-of-day control spec 20 (`lunch_drift`), which should be ~flat after costs; if a control shows
PF > 1.2 on both periods, suspect an engine or look-ahead bug before believing any winner.

Dropped from this family (not specified below) and why:
- **Mean reversion into the close (item 22)**: the index-futures evidence is the opposite sign (intraday momentum from
  hedging demand; late extremes are trend legs). Not codeable as a *reversion* spec with any positive prior; the
  continuation version belongs to the trend family.
- **Full-gap fade (item 8)**: a sub-case of the outside-open re-entry (spec 2, `open beyond PDH/PDL`); the TradingView rule
  (long at the first 5-min close, target 0.7-1.0 x gap, stop 1.0 x gap) is the `entry='market'` mode of `mr_pdrange`, which
  is already tested and not an edge.
- **Connors RSI(2) intraday (item 5)**: negative intraday evidence; it is the `rsi_len=2, rsi_in=10` cell of spec 11.
- **VWAP +/- K x ATR (item 2, StockSharp)**: the `band='atr'` mode of spec 13.
- **Vendor "Phoenix" (item 26)**: rules undisclosed; benchmark only (PF 1.3 / 70% win M5 passes ~70% of $50k evals at 2 MNQ).

---

## 1. intraday_mean_reversion__gap_fade_small  (small opening-gap fade to the prior close; existing module `mr_gapfade`)

Priority **4**, complexity **1** (module exists; the grid adds an ATR-floored stop and a limit entry), instruments **MNQ**
(MES dead in all 36 cells), bar size: 1-min, one decision at 09:30/09:31. EQ 3 (S&P same-day fill 78% at 0.10-0.25%, 60%
at 0.25-0.5%, 46% at 0.5-1%; edgeful NQ 56-60%) and our own MNQ result (PF 1.56 / 1.22 on 114 / 130 trades).

What the results say: the published 1x-gap stop on a 0.10-0.25% gap is 6-15 MES / 25-60 NQ points and is hit by opening
noise (stop first on 47-51% of MES days); the 5-minute entry delay throws away the 26-36% of gaps that fill before 09:35.
The 09:31 entry fixed the second flaw. The untested deltas are (a) an ATR floor under the stop, (b) a non-chasing limit
entry, (c) `gap_max 0.25` (the highest-fill bucket) now that frequency is less of a problem on MNQ.

```
PARAMS (defaults = published rule): gap_min=0.10, gap_max=0.50, atr_mult=0.7, stop_mult=1.0, stop_floor_atr=0.0 (new),
  entry='market' (new: 'market' | 'limit'), limit_frac=0.25 (new), limit_valid=15 (new), entry_delay=5, fill_frac=1.0,
  exit_time='11:00', flat='15:55', sides='both', vix_gate=True, outside_atr=0.5, skip_beyond_stop=True, max_trades=1
  (chosen fix so far: gap_max 0.35, entry_delay 1)
PRE (per session d, at the 09:30 open): PDC, PDH, PDL, ATR14d, O930; gap_pts = O930 - PDC; gap_pct = 100*gap_pts/PDC
  qualify[d] = ATR notna AND gap_min <= |gap_pct| <= gap_max AND |gap_pct| <= atr_mult * 100*ATR/PDC
               AND PDL - outside_atr*ATR <= O930 <= PDH + outside_atr*ATR          (else gap-and-go: skip)
               AND (not vix_gate OR not VIX_hot[d])
  side = +1 if gap_pts < 0 (gap down -> long) else -1;  apply `sides`
ENTRY (at i_e = index of the bar with tod = 09:30 + entry_delay; decision uses bars < i_e only):
  skip if the gap already filled in bars [09:30, i_e): long: any high >= PDC; short: any low <= PDC
  skip if the stop level is already breached at the close of bar i_e - 1 (skip_beyond_stop)
  stop_dist = max(stop_mult * |gap_pts|, stop_floor_atr * ATR)                       (stop_floor_atr 0 = published)
  stop_px = O930 - side*stop_dist;  tgt_px = O930 + fill_frac * (PDC - O930)
  entry='market': place(i_e, side, stop_px=stop_px, tgt_px=tgt_px)                     # market at the open of i_e
  entry='limit' : place(i_e, side, entry_px = O930 - side*limit_frac*|gap_pts|, kind='limit', valid_bars=limit_valid,
                        stop_px, tgt_px)                                               # buy the dip deeper than the open
TIME EXIT: it.exit_at(first bar with tod >= exit_time); SESSION: set_session('09:30', '09:40', flat); max_trades_day = 1
RISK: daily_loss_stop = stop_dist_median * point_value (one full stop halts the day); daily_profit_stop inert
```
Grid (<= 24): `gap_max {0.25, 0.35}`, `stop_floor_atr {0, 0.10, 0.15}`, `entry {market, limit}`, `sides {both, long}`.
Fixed: stop_mult 1.0, fill_frac 1.0 (0.75 already tested worse on both periods), entry_delay 1, exit 11:00 (12:00 tested
worse), vix_gate True (nearly inert: ~10 hot days). Do NOT grid weekday, VIX bucket or per-side stops (the README lists
them as untried for lack of a reason; nothing has changed).

Risk/Lucid: $R per micro at the published stop is ~$40-120 on MNQ; with the 0.15 ATR floor it is ~60 NQ pts = $120. Expect
10 micros as before; the floor should raise the hit rate (fewer noise stop-outs) at the price of a larger average loss, so
the comparison is on Sharpe and `exp_net_lb`, not on PF alone. Flat on ~75% of days -> stackable with spec 2 (requires the
open OUTSIDE the prior range, this one inside) and with an afternoon leg.

Evidence recap: thetrading.tools S&P fill rates; shareplanner SPY/QQQ; edgeful NQ 56-60%; Fung-Mok-Lam and Grant-Wolf-Yu
(index-futures opening reversals significant but cost-sensitive). Our result: the only two-period-positive rule in the family
with > 100 trades.

Data gap: FOMC/CPI calendar not available (published filter not implemented). None otherwise.

## 2. intraday_mean_reversion__pdrange_oops_stop  (open outside the prior-day range, STOP-order re-entry at PDH/PDL; existing module `mr_pdrange`, `entry='stop'`)

Priority **3**, complexity **1** (module exists; grid adds an ATR-scaled stop and a break-even ratchet), instruments **MNQ**
(MES rejected), bar size: 1-min, order placed at 09:31. EQ 3 (edgeful NQ: 75% touch PDH after opening above, 64% touch PDL;
tradethatswing SPY 71/71%; Oxfordstrat Williams Oops 42 markets 1980-2011 "C" grade) and our result (stop mode, both sides,
max_dist 0.50, tgt 0.5 ATR: PF 1.39 / 47 MAIN, 1.56 / 53 PRIOR; the 09:35 market fade is not an edge).

```
PARAMS (defaults = published Oops): entry='stop', max_dist=0.30, min_dist=0.05, dist_atr=0.5, stop_mode='dist' (new:
  'dist' | 'atr'), stop_mult=1.0, min_stop_pct=0.15, stop_atr=0.20 (new), tgt_atr=1.0, min_tgt_pct=0.05, be_trail=False (new),
  stop_valid_until='11:30', exit_time='12:00', flat='15:55', gap_cap=1.0, sides='both', max_trades=1
  (chosen fix so far: max_dist 0.50, tgt_atr 0.5)
PRE (at the 09:30 open): PDH, PDL, PDC, ATR14d, O930
  setup: LONG if O930 < PDL (level = PDL); SHORT if O930 > PDH (level = PDH); dist = |O930 - level|
  qualify = ATR notna AND min_dist% <= 100*dist/O930 <= max_dist% AND dist <= dist_atr*ATR AND 100*|O930-PDC|/PDC <= gap_cap
ENTRY: at i0 = index of the 09:31 bar, one STOP order: long: entry_px = PDL + 1 tick; short: entry_px = PDH - 1 tick;
  valid_bars = minutes from 09:31 to stop_valid_until.  Fills only when price re-crosses INTO the prior range (failure of
  the outside open confirmed first).  (`entry='market'`: 09:35 market fade toward the level, published edgeful rule, tested
  and rejected; keep as the control cell only.)
STOP: stop_mode 'dist': level - side*max(stop_mult*dist, min_stop_pct%*O930)   (published)
      stop_mode 'atr' : level - side*stop_atr*ATR                                 (new: noise-proof floor)
TARGET: level + side*min(|PDC - level|, tgt_atr*ATR); skip the day if that is < min_tgt_pct% of O930 from the level
BE_TRAIL (new): trail_act_pts = R, trail_pts = R  (once MFE >= 1R the stop ratchets to never worse than break-even)
TIME EXIT: it.exit_at(first bar >= exit_time); SESSION: set_session('09:31', stop_valid_until, flat); max_trades_day = 1
RISK: daily_loss_stop = one full stop; daily_profit_stop inert
```
Grid (<= 16): `max_dist {0.50, 0.80}`, `stop_mode {dist, atr}`, `tgt_atr {0.5, 0.75}`, `be_trail {False, True}`. Fixed:
sides both (long-only is 15-19 trades and 0.8-1.0 on PRIOR), stop_valid_until 11:30 (10:30 worse on both periods), exit
12:00 (13:00 a wash), stop_atr 0.20. One extra run with `max_dist 0.80` on MES only (its 0.20-cap cell held on both
periods with 25-37 trades; 0.80 is the untested side).

Risk/Lucid: $R ~ 0.15-0.2 ATR = 60-80 NQ pts = $120-160 per micro; 47-53 trades per 21 months is the problem (median 79
days to pass). Only a portfolio leg; its days are disjoint from spec 1 by construction.

Evidence recap: edgeful outside days; tradethatswing (effect decays beyond 0.2%); our funnel study (touch-by-12:00 81-88% at
0-0.3%, 39% at 0.3-0.5% on MNQ MAIN; 36-67% of touches before 09:35).

Data gap: none.

## 3. intraday_mean_reversion__turtle_soup_pd_recross  (intraday Turtle Soup: PDL/PDH break during RTH, close back inside, stop entry; also covers Unger "Strategy 1" 15-min re-cross)

Priority **3**, complexity **3**, instruments **MNQ, MES**, bar size: 5-min (grid 15) on 1-min execution. EQ 2-3 (Connors &
Raschke "Street Smarts" Turtle Soup, no numbers; Unger Academy Strategy 1: ~750 trades / 6-7 yrs, avg ~$300 per ES, 2022
+$15k, 2023 +$18k with undisclosed filters; LuxAlgo: works in rotational markets, fails in persistent trends). This is spec 2
moved off the open: the break of the prior-day extreme happens DURING the session (the open was inside the range), which is
the common case (55-60% of sessions open inside the prior range and ~45% of those later trade through PDH or PDL).

```
PARAMS: bar=5, pen_ticks=2, fail_bars=6 (30 min on 5-min bars), entry='stop' ('stop' | 'market'), stop_cap_atr=0.25,
  tgt_mode='pdc_capped' ('pdc_capped' | 'atr'), tgt_atr=0.5, min_tgt_atr=0.10, be_trail=False, first_entry='09:35',
  last_entry='14:00', exit_time='15:00', flat='15:55', sides='both', max_trades=2, max_dist_atr=0.6
PRE: PDH, PDL, PDC, ATR14d, O930; require in_value[d] (O930 inside [PDL, PDH]; outside opens belong to spec 2)
STATE per level L in {PDL (long side), PDH (short side)}: armed -> broken -> entered/expired; each level once per day.
Scan B(bar) RTH bars b of day d in order (values at the bar close; order at b.i_next; skip if i_next == -1 or
  tod(i_next) not in [first_entry, last_entry)):
  LONG side (level PDL): broken when low_b < PDL - pen_ticks*tick; ext = running min low since the break bar.
    skip the level if PDL - ext > max_dist_atr*ATR (a real breakdown, not a sweep).
    failure: within fail_bars bars after the break bar, a bar closes > PDL  ->  at b.i_next:
      entry='stop'  : place(i_next, +1, entry_px = PDL + 1 tick, kind='stop', valid_bars = 30, ...)   # Turtle Soup
      entry='market': place(i_next, +1, ...)                                                           # Unger re-cross
    stop_px = ext - 1 tick, but never farther than stop_cap_atr*ATR from the entry level (then stop = level - cap)
    tgt_px = 'pdc_capped': PDL + min(|PDC - PDL|, tgt_atr*ATR) (skip if < min_tgt_atr*ATR above PDL);  'atr': PDL + tgt_atr*ATR
  SHORT side (level PDH): mirror (broken when high_b > PDH + pen_ticks*tick; failure = close < PDH; sell stop PDH - 1 tick)
  be_trail: trail_act_pts = R, trail_pts = R
TIME EXIT: it.exit_at(first bar >= exit_time); SESSION: set_session(first_entry, last_entry, flat); max_trades_day = 2
RISK: daily_loss_stop = MNQ $80 / MES $60 (two stop-outs end the day); daily_profit_stop MNQ $160 / MES $120
Unger S1 cell = bar 15, entry market, sides both, tgt 'atr' (his 80-pt ES target ~ 1 ATR; we cap at tgt_atr <= 1.0).
```
Grid (<= 32): `bar {5, 15}`, `entry {stop, market}`, `stop_cap_atr {0.25, 0.40}`, `tgt_atr {0.5, 1.0}`, `sides {both, long}`.
Fixed: pen_ticks 2, fail_bars 6 (15-min: 2), be_trail False (one follow-up pair on the best cell), exit 15:00.

Risk/Lucid: $R <= 0.25-0.4 ATR = 100-160 NQ pts = $200-320 per micro worst case -> expect 5 micros; `stop_cap_atr 0.25` is
the lever. 0-2 trades/day, mid-session, resolves within 1-2 hours. Shorts (failed upside breaks) are the weak side in
2023-26 per the research; if `long` wins the grid, that is consistent with the family's evidence, not a fit.

Evidence recap: Street Smarts (no stats); Unger blog (vendor backtest, OOS included, win rate undisclosed); LuxAlgo regime
note; tradingstats IB double-break statistics (46.8% of failed breaks become double breaks: the stop must be beyond the sweep
extreme, hence the cap not a 1-tick stop).

Data gap: none.

## 4. intraday_mean_reversion__session_low_limit_dip  (Unger "Strategy 2": limit buy below the running session low minus an ATR offset)

Priority **2**, complexity **2**, instruments **MES (published), MNQ**, bar size: 1-min running extremes, order refreshed every
5 min. EQ 2 (Unger Academy: ~1,800 trades, avg ~$140 per ES, 2020 +$40k, 2023 +$33k; stop $800 ~ 16 ES pts ~ 0.2 ATR, target
$3,000 ~ 60 pts ~ 0.75 ATR; offset undisclosed, standard reading 0.25-0.5 ATR).

```
PARAMS: offset_atr=0.25, stop_atr=0.20, tgt_atr=0.75, tgt_cap_atr=0.6, refresh=5, first_entry='10:00', last_entry='14:30',
  flat='15:55', sides='long', max_trades=2, max_fall_atr=0.8
PRE: ATR14d; B5 RTH bars for the refresh clock; running session low L_t / high H_t over RTH 1-min bars [09:30, t]
LOOP over B5 bars b with tod(b.i_next) in [first_entry, last_entry), i_next != -1:
  L = min(low) of 1-min bars from 09:30 through b.i_last (all closed);  H likewise
  skip day-side if O930 - L > max_fall_atr*ATR (already a trend day; the "dip" is a crash)
  LONG : place(b.i_next, +1, entry_px = L - offset_atr*ATR, kind='limit', valid_bars = refresh,
               stop_pts = stop_atr*ATR, tgt_pts = min(tgt_atr, tgt_cap_atr)*ATR)
  SHORT (sides both): place(..., -1, entry_px = H + offset_atr*ATR, kind='limit', ...)
  (one pending order at a time: valid_bars = refresh means each order expires exactly when the next is placed; when both
   sides are active, alternate: the side whose level is nearer the last close gets the order)
EXIT: stop / target / forced flat at `flat` (Unger exits at session end; no time stop otherwise)
SESSION: set_session(first_entry, last_entry, flat); max_trades_day = max_trades
RISK: daily_loss_stop = 2 x stop ($R = 0.2 ATR = 15 ES pts = $75/MES, 80 NQ pts = $160/MNQ); daily_profit_stop block default
```
Grid (<= 24): `offset_atr {0.15, 0.25, 0.40}`, `stop_atr {0.20, 0.35}`, `tgt_atr {0.5, 0.75}`, `sides {long, both}`.
Fixed: refresh 5, max_fall_atr 0.8, window 10:00-14:30.

Risk/Lucid: low win rate (target 2.5-3.75x stop -> expect 30-40% winners); streaky; the capped 0.6 ATR target keeps the largest
day <= ~$150/micro on MNQ. Because it buys a NEW session low, fills cluster on down days; the max_fall gate is the trend-day
kill switch. Limit fills in the engine need a 1-tick trade-through (conservative).

Evidence recap: Unger blog only (403-blocked; numbers from snippets). Family evidence that dip-buys beat short fades (StatOasis
970/971 short variants lost) supports `sides='long'` as the default.

Data gap: none.

## 5. intraday_mean_reversion__wkopen_tuesday_fade  (day-2 fade toward the week's first RTH open; existing module `mr_wkopen`)

Priority **2**, complexity **1** (module exists), instruments **MNQ, MES, MGC** (one trade per week each, as a three-leg
filler), bar size: 1-min, order at 09:31. EQ 3 (tradingstats NQ 565 weeks: 92.9% touch at < 0.25%, 75.5% at 0.25-0.50%; our
replication: 89% by 11:30 at < 0.25% on 2025-26) but our P&L: MES 2.09 MAIN / 0.67 PRIOR, MNQ 1.27 / 1.59, 21-35 trades.

```
PARAMS (defaults = published): max_dist=0.25, min_dist=0.05, stop_mode='dist' (new: 'dist' | 'atr'), stop_mult=1.0,
  min_stop_pct=0.15, stop_atr=0.20 (new), entry_delay=1, exit_time='11:30', flat='15:55', sides='both',
  require_eth_touch=False, allow_day3=False, max_trades=1   (chosen fix so far: max_dist 0.50)
PRE: week_id from session weekdays (first session whose dow < previous dow starts a week); WO = open of the week's first
  RTH bar (must be within 5 min of rth_open); trade day = day_in_week == 2 (day 3 only if allow_day3 and day 2 skipped)
SETUP at the trade day's RTH open: d = 100*(open_rth - WO)/WO; qualify min_dist <= |d| <= max_dist; side = +1 if d < 0 else -1
  skip if the 09:30 bar already touched WO (long: high_0930 >= WO)
ENTRY: place(i_open + entry_delay, side) market
STOP: 'dist': open_rth - side*max(stop_mult*|open_rth - WO|, min_stop_pct%*open_rth);  'atr': open_rth - side*stop_atr*ATR14d
TARGET: WO (fills 1 tick through).  TIME EXIT: exit_at(first bar >= exit_time).  SESSION: set_session(rth_open, rth_open+5, flat)
max_trades_day = 1; one trade per week per instrument
```
Grid (<= 8 per contract): `max_dist {0.50}`, `min_dist {0.05, 0.15}`, `stop_mode {dist, atr}`, `sides {both}` x
`exit_time {11:30, 13:00}` -> 8 cells x 3 contracts. Fixed: entry_delay 1, require_eth_touch False (worse everywhere),
allow_day3 False. The ATR stop is the only untested lever with a stated reason (stops are hit by 09:30-11:30 noise; median MAE
of winners -27 NQ pts, i.e. ~0.07 ATR, so a 0.2 ATR stop clears it).

Risk/Lucid: <= 2 trades/month/instrument: can never carry an evaluation (Lucid exp. net negative in every cell); only a
three-instrument leg whose value is low correlation. Evaluate only in `backtest.portfolio` next to specs 1-3.

Evidence recap: tradingstats NQ 2015-2025 (touch rates reproduce on our data); not-touched weeks are gap-and-go 66.7%.

Data gap: none.

## 6. intraday_mean_reversion__volband_band_target_long  (prior-close +/- VIX/16 band breach, scalp back to the band, long-only; existing module `mr_volband`)

Priority **2**, complexity **1** (module exists; one untested combination), instruments **MNQ, MES, MGC (rv20 band)**, bar
size: 1-min. EQ 3 (Seeck SSRN 7364204: 860 breaches 2018-2026, 85.2% same-session reversion, OOS 2023-26 Sharpe 1.29) but our
replication with VIX-proxied bands and costs is PF 0.83 on PRIOR for the paper rule; the single two-period-positive variant is
`tgt_mode='band'` + `sides='long'` (PF 1.41 / 1.38, ~26 trades/yr, ~$5/trade).

```
PARAMS (defaults = paper): divisor=16, hold=30, stop_mult=0.5, tgt_mode='none', gate=True, vix_low=20, vix_high=30,
  vol_mult (MES 1.0, MNQ 1.25 VXN proxy), vol_src ('vix'; MGC 'rv20'), entry_start (09:35; MGC 08:25), entry_end (15:00;
  MGC 13:00), flat='15:55', sides='both', max_trades=2, allow_open_outside=False
PRE per session: C_ref = prior RTH close; V = VIX_lag*vol_mult (or rv20 = stdev of last 20 daily log RTH returns x sqrt(252) x 100);
  w = C_ref*(V/divisor)/100; Upper = C_ref + w; Lower = C_ref - w; ok = C_ref, V, VIX notna and (not gate or VIX_gate_seeck)
SIGNAL (1-min): the first bar in [entry_start, entry_end) is checked first: a band already breached at that close is dead
  for the day. Then the first bar whose close < Lower -> place(i+1, +1); first close > Upper -> place(i+1, -1); each band once.
EXITS: max_hold = hold minutes; stop_px = band - side*stop_mult*w (beyond the breached band); tgt_mode 'none' (paper) |
  'ref' (C_ref) | 'band' (the breached band: Lower for longs); flat 15:55.  max_trades_day = 2
RISK: $R = 0.5 w; with VIX 18 on NQ w ~ 1.4% ~ 330 pts -> stop 165 pts = $330/micro: TOO BIG for 10 micros. The new combination
  caps it: stop_mult 0.25 (new grid value) and entry_end 11:00 (the paper's and our edge is in the first 90 minutes).
```
Grid (<= 8 per contract): `divisor {14, 16}`, `stop_mult {0.25, 0.5}`, `hold {30, 60}`; fixed tgt_mode band, sides long,
gate False (the gate removed 15-20% of trades and lowered net; it is a diagnostic bucket only), entry_end 11:00. MGC with
vol_src rv20 and the pit clock (entry 08:25-10:00, flat 13:25).

Risk/Lucid: at best a low-drawdown filler (DD -$470/micro at the band target); expect <= 30 trades/yr per instrument. If the
MAIN PF < 1.2 or PRIOR < 1.0 on the first pass, stop; the README already recommends not promoting it.

Evidence recap: Seeck 2026; our grid (MAIN 62% of MNQ cells profitable, PRIOR 8%; MGC 24/24 MAIN, 0/24 PRIOR; MES largest-day
share >= 1.0 on every MAIN winner).

Data gap: VXN not in `data/parquet` (fixed 1.25 x VIX proxy for NQ); VIX is one-day lagged.

## 7. intraday_mean_reversion__onrev_cross_sectional  (overnight-return reversal across MES / MNQ / MGC, open-to-close; existing module `mr_onrev`, no results yet)

Priority **3**, complexity **2** (module exists; needs a three-leg portfolio run), instruments **MES + MNQ + MGC as one
portfolio**, bar size: daily signal, 1-min execution at 09:31. EQ 4 (Akbas-Boehmer-Jiang-Koch 2022; quantreturns 2007-2025
equity-futures basket ~0.09%/day gross Sharpe 3.2 on 6 index futures; robust across asset classes 1982-2014) but our universe
is 3 instruments, so expect a fraction of that.

```
PARAMS: thresh=0.30 (% spread), universe='all3' ('all3' | 'eq'), stop_atr=1.0, entry_time='09:31', exit_time='15:55' (new:
  '12:00' | '15:55'), flat='15:55', sides='both', max_trades=1, tgt_cap_atr=0.6 (new, consistency cap)
PRE (same clock for every instrument, gold included): prior_close_k = last 1-min close with tod < 16:00 of the previous
  session; open_k = open of the 09:30 bar; r_k = 100*(open_k - prior_close_k)/prior_close_k for every k in the universe.
  Sessions missing any member, or whose prior sessions differ in date across members, are skipped. x_k = r_k - mean_k(r);
  spread = max(r) - min(r).
SIGNAL for the contract X being run: LONG X if r_X is the minimum AND spread >= thresh AND x_X <= -thresh/2;
  SHORT X if r_X is the maximum AND spread >= thresh AND x_X >= +thresh/2; else flat. Apply `sides`.
ENTRY: place(index of the 09:31 bar, side, stop_pts = stop_atr*ATR14d, tgt_pts = tgt_cap_atr*ATR14d)
EXIT: exit_at(first bar >= exit_time); flat at `flat`.  SESSION: set_session('09:31', '09:32', flat); max_trades_day = 1
PORTFOLIO: run each contract separately, combine with backtest.portfolio (1 micro per leg); legs are NOT hedged against each
  other (ES vs GC), so intraday equity is the sum of legs.
RISK: $R = 1 ATR per leg is a disaster stop only (MNQ ~$800/micro!): size by the campaign tool, not by $R; the 0.6 ATR target
  cap bounds the largest day. daily_loss_stop/profit_stop inert (1 trade).
```
Grid (<= 24): `thresh {0.20, 0.30, 0.50}`, `universe {eq, all3}`, `exit_time {12:00, 15:55}`, `sides {both, long}`. Fixed:
stop_atr 1.0 (the module's 0.75/1.5 cells are a follow-up only if the base is alive).

Risk/Lucid: open-to-close holds produce fat daily P&L (consistency risk, hence the cap); 1 micro per leg at most until the
intraday-equity portfolio optimizer says otherwise. Gold's overnight return is a different animal (its range is mostly
overnight) -> `universe='eq'` is the clean test; `all3` is the cross-asset test.

Evidence recap: Quantpedia "Overnight-Intraday Daily Reversal"; quantreturns replication; CXO.

Data gap: only 3 of the 4 published instruments (crude 1-min is missing for 2024-26); equal-weight dollar-neutral replaced by
1 micro per leg.

## 8. intraday_mean_reversion__or_whipsaw_invalue  (30-min opening-range failed break, fade to the opposite edge, "in value" open filter)

Priority **3**, complexity **3**, instruments **MNQ, MES**, bar size: 30-min OR, 5-min confirmation on 1-min execution. EQ 3
(tradingstats 2014-2026: on whipsaw days the first OR break was the fake-out 73-78% of the time; whipsaw rate highest for
in-value opens: 41.5% NQ / 47.0% ES; base rate 70-73% of days close outside the 30-min OR). Caution: `mr_ibfail` (same
structure on the 60-min IB, midpoint target, 1-tick stop) is dead; this spec differs in the four ways the research says
matter: 30-min range, in-value filter, far-edge target and an ATR-capped stop. If the default cell is PF < 1.0 on both
contracts on MAIN, stop; do not grid.

```
PARAMS: or_minutes=30, break_deadline='10:30', fail_deadline='11:00', require_in_value=True, tgt='far' ('far' | 'mid'),
  stop_cap_or=0.5 (x or_rng), stop_cap_atr=0.3, min_or_atr=0.15, max_or_atr=0.8, exit_time='11:30', flat='15:55',
  sides='both', max_trades=1
PRE: OR(or_minutes) -> or_high, or_low, or_rng, or_mid, i_end; ATR14d; in_value[d]
  tradeable[d] = ATR notna AND min_or_atr*ATR <= or_rng <= max_or_atr*ATR AND (not require_in_value OR in_value[d])
BREAK: first B5 bar b with tod >= 10:00 and tod < break_deadline whose high > or_high (up) or low < or_low (down); both in
  one bar -> the side of the bar's close relative to its open. ext = running extreme since the break bar.
FAILURE: a B5 bar f after b, with tod < fail_deadline, whose close is back inside [or_low, or_high]
ENTRY at f.i_next (skip if -1): failed up-break -> place(i_next, -1); failed down-break -> place(i_next, +1)  (market)
STOP: ext +/- 1 tick, capped: |stop - close_f| <= min(stop_cap_or*or_rng, stop_cap_atr*ATR) (then stop = close_f -/+ cap)
TARGET: 'far' = opposite OR edge (or_low for shorts); 'mid' = or_mid.  Skip if the target is < 1 tick beyond close_f.
TIME EXIT: exit_at(first bar >= exit_time).  SESSION: set_session('10:00', fail_deadline, flat); max_trades_day = 1
RISK: daily_loss_stop = one full stop; daily_profit_stop inert
```
Grid (<= 16): `require_in_value {True, False}`, `tgt {far, mid}`, `stop_cap_or {0.25, 0.5}`, `sides {both, long}`. Fixed:
or_minutes 30, deadlines 10:30 / 11:00, exit 11:30 (one follow-up pair with 13:00 on the best cell, as ibfail's 15:00 exit
helped a little on both periods).

Risk/Lucid: $R <= 0.5 x or_rng ~ 0.15-0.3 ATR = 60-120 NQ pts = $120-240/micro -> 5-10 micros. One early trade, resolved by
11:30. The `require_in_value` cell is the whole hypothesis: if it does not beat `False` on both periods, the tradingstats
whipsaw conditioning does not translate into P&L.

Evidence recap: tradingstats OR close-outside statistics; SMB opening drive study; tradethatswing (71% of days break both
sides of the 5-min OR).

Data gap: the published "value area" needs volume; the prior-day RTH range is the proxy (flagged).

## 9. intraday_mean_reversion__opening_drive_fade  (fade a directional drive off the 09:30 open back to the opening print)

Priority **2**, complexity **2**, instruments **MNQ, MES**, bar size: 1-min, decisions 09:33-09:40. EQ 2-3 (SMB "First Ticks -
Wrong Ticks": after an opening drive price trades back through the opening print within 30 min 84.3% of the time, median 2
min; fade 57.9% winners, avg win 0.75 ES pts on pre-2015 data: thin). The 2025-26 version must express the drive in ATR, not
points.

```
PARAMS: drive_min_atr=0.12, drive_max_atr=0.5, t_first='09:33', t_last='09:40', stop_frac=0.5, stop_cap_atr=0.3, tgt='open'
  ('open' | 'half'), max_hold=30, require_in_value=False, gap_cap=0.75 (%), sides='both', max_trades=1, flat='15:55'
PRE: O930, ATR14d, PDH/PDL/PDC, gap_pct; skip day if |gap_pct| > gap_cap or ATR NaN or (require_in_value and not in_value)
LOOP 1-min bars i with tod in [t_first, t_last] (values at the close of bar i; order at i+1):
  drive = close_i - O930;  if |drive| >= drive_min_atr*ATR and |drive| <= drive_max_atr*ATR and no order yet today:
    side = -sign(drive);  ext = max high (drive up) / min low (drive down) over [09:30, i]
    stop_px = ext - side*stop_frac*|drive|   (beyond the drive extreme; if |stop_px - close_i| > stop_cap_atr*ATR then
             stop_px = close_i - side*stop_cap_atr*ATR)
    tgt_px = O930 ('open') or O930 + 0.5*drive ('half');  skip if |tgt_px - close_i| < 2 ticks
    place(i+1, side, stop_px=stop_px, tgt_px=tgt_px, max_hold=max_hold)
SESSION: set_session('09:33', '09:42', flat); max_trades_day = 1
RISK: daily_loss_stop = one full stop ($R ~ 0.1-0.3 ATR); daily_profit_stop inert
```
Grid (<= 16): `drive_min_atr {0.12, 0.20}`, `stop_frac {0.5, 1.0}`, `max_hold {15, 30}`, `sides {both, long}`. Fixed: tgt
'open', t_last 09:40, gap_cap 0.75, require_in_value False (one follow-up with True).

Risk/Lucid: tiny, fast trades (median hold minutes); costs ($2.30 MNQ) are a large share of the 0.75-pt-equivalent edge; it
lives or dies on MNQ's larger point range. Early resolution makes it stackable with everything after 10:00.

Evidence recap: SMB (ES, old); tradingstats (first OR break is the fake-out on whipsaw days).

Data gap: none.

## 10. intraday_mean_reversion__on_range_fail_fade  (overnight-range failed break, fade to the ON midpoint / opposite edge)

Priority **2**, complexity **3**, instruments **MNQ, MES**, bar size: ON range on 1-min data, 5-min confirmation. EQ 1-2
(practitioner scripts only; OR studies suggest failure fades beat level fades). Structural sibling of spec 8 with the Globex
range as reference; the breakout version (`on_range_break.py`) already exists, so this is its mirror.

```
PARAMS: mode='fail' ('fail' | 'touch'), fail_bars=3 (15 min), first_entry='09:35', last_entry='11:30', tgt='mid' ('mid' |
  'far'), stop_cap_on=0.25 (x on_rng), stop_cap_atr=0.3, min_on_atr=0.3, max_on_atr=1.2, exit_time='12:00', flat='15:55',
  sides='both', max_trades=2
PRE: ON -> on_high, on_low, on_rng, on_mid; ATR14d; require on_low < O930 < on_high (open inside the ON range) and
  min_on_atr*ATR <= on_rng <= max_on_atr*ATR
STATE per edge (on_high -> short setups; on_low -> long setups), each once per day; scan B5 RTH bars b with tod >= 09:35:
  mode 'fail' : break when high_b > on_high (up) [low_b < on_low (down)]; ext = running extreme since the break;
                failure = within fail_bars bars a close back inside (close < on_high) -> place(f.i_next, -1) [+1]
  mode 'touch': the first bar whose high >= on_high AND close < on_high (touch and reject) -> place(b.i_next, -1); mirror
STOP: ext (or the touch bar's extreme) +/- 1 tick, capped at min(stop_cap_on*on_rng, stop_cap_atr*ATR) from the signal close
TARGET: 'mid' = on_mid; 'far' = opposite ON edge.  TIME EXIT: exit_at(first bar >= exit_time)
SESSION: set_session(first_entry, last_entry, flat); max_trades_day = 2
RISK: daily_loss_stop MNQ $80 / MES $60; daily_profit_stop MNQ $160 / MES $120
```
Grid (<= 16): `fail_bars {2, 3}`, `tgt {mid, far}`, `stop_cap_on {0.25, 0.5}`, `sides {both, long}`; fixed mode 'fail'. One
extra run with `mode='touch'` at the defaults (the level-fade control, expected worse).

Risk/Lucid: $R <= 0.25 x on_rng ~ 0.1-0.3 ATR; 0-2 trades/day before noon. Skip 08:30-data days is not implementable (no
calendar); the 1.2 ATR cap removes most of them anyway.

Evidence recap: futures.io / TradingView scripts (no P&L); edgeful overnight-range reports (descriptive).

Data gap: no FOMC/CPI/NFP calendar.

## 11. intraday_mean_reversion__rsi3_dip_vixgate  (RSI(3) < 20 dip-buy above the 190-bar MA on 5-min bars, VIX top-quartile excluded)

Priority **2**, complexity **2**, instruments **MNQ, MES**, bar size: 5-min (all-session bars so the 190-bar MA is mature at the
open). EQ 2 (algotr Substack 2025: ~34% better return/drawdown with the VIX quartile gate on ES/NQ/RTY; absolute numbers not
given; Connors RSI(2) daily is robust but intraday ports are reported as losers). The transferable idea is the regime gate;
the base rule is re-parameterised to day-trade only.

```
PARAMS: bar=5, rsi_len=3, rsi_in=20, rsi_out=80, ma_len=190, stop_datr=0.3, max_bars=39, vix_gate=True, max_trend_atr=0.6,
  entry_start='09:35', entry_end='14:30', flat='15:55', sides='long', max_trades=2
PRE: B5all bars; RSI = rsi(close, rsi_len); MA = sma(close, ma_len); ATR14d; O930; VIX_hot[d]
SIGNAL bar b (values at its close; entry at b.i_next with tod in [entry_start, entry_end), i_next != -1):
  LONG  if RSI_b < rsi_in AND close_b > MA_b AND (not vix_gate or not VIX_hot[d]) AND |close_b - O930| <= max_trend_atr*ATR
  SHORT (sides both) if RSI_b > rsi_out AND close_b < MA_b AND same gates
ENTRY: place(b.i_next, side, stop_pts = stop_datr*ATR14d, max_hold = max_bars*bar)
EXIT SIGNAL: at the close of any later B5 bar e with RSI_e > rsi_out (long) [< rsi_in (short)]: exit_at(e.i_next, which=side)
  (the engine's exit_flag; only acts if a position is open); max_hold; flat 15:55
SESSION: set_session(entry_start, entry_end, flat); max_trades_day = 2
RISK: $R = 0.3 ATR = 120 NQ pts = $240/micro (large: this rule holds through noise); daily_loss_stop MNQ $80 / MES $60 (one
  stop-out halts the day); daily_profit_stop MNQ $160 / MES $120; tgt_cap: none published; add tgt_pts = 0.6 ATR as the
  consistency cap.
```
Grid (<= 32): `rsi_len {2, 3}`, `rsi_in {10, 20}` (rsi_out = 100 - rsi_in), `stop_datr {0.3, 0.5}`, `vix_gate {True, False}`,
`sides {long, both}`. Fixed: ma_len 190, max_bars 39, bar 5.

Risk/Lucid: holds up to 195 min with a 0.3-0.5 ATR stop: the worst daily P&L shape in this family for the EOD trail; only
viable at 3-5 micros. The `vix_gate True vs False` pair on both periods is the only thing this spec is really testing.

Evidence recap: algotr (EasyLanguage, unverified); Connors & Alvarez (daily); ProRealCode intraday failures.

Data gap: none (VIX daily from Yahoo, lagged).

## 12. intraday_mean_reversion__zscore_1m_long  (1-min rolling z-score dip-buy, 09:35-11:30, minutes-horizon exit)

Priority **2**, complexity **2**, instruments **MNQ, MES**, bar size: 1-min (all-session bars for the rolling window). EQ 3-4
for the existence of 2-30 minute reversion (arXiv 2501.16772: t = 13.6 at 2-16 min horizons, persistence beyond ~1 h;
StatOasis daily: long-only z-fades positive in 99-100% of variants, 970/971 short variants lost), EQ 2 for any specific
intraday rule. The edge is basis points per trade: the test is whether MNQ's point range beats $2.30 round trips.

```
PARAMS: N=30, z_in=2.0, z_out=0.0, confirm='cross_back' ('cross_back' | 'raw'), max_hold=10, stop_datr=0.25, vix_min=0,
  max_trend_atr=0.6, entry_start='09:35', entry_end='11:30', flat='15:55', sides='long', max_trades=4, rearm=0.5
PRE: 1-min all-session bars; m = sma(close, N); s = rolling stdev(close, N) (min_periods N); z = (close - m)/s; ATR14d; O930
STATE: armed=True at the session start. For bar i (values at its close; order at i+1 inside the entry window):
  'raw'       : LONG when armed and z_i < -z_in
  'cross_back': LONG when armed and z_{i-1} < -z_in and z_i >= -z_in  (first close back above the -2 sigma line)
  gates: VIX_lag >= vix_min (0 = off); |close_i - O930| <= max_trend_atr*ATR (not a trend day); s_i > 0
  after a signal: armed=False until z >= -rearm (prevents re-entering the same excursion)
  SHORT (sides both, control only): mirror at +z_in
ENTRY: place(i+1, +1, stop_pts = stop_datr*ATR, max_hold = max_hold)
EXIT SIGNAL: first later bar e with z_e >= z_out -> exit_at(e+1, which=+1); max_hold minutes; flat 15:55
SESSION: set_session(entry_start, entry_end, flat); max_trades_day = 4
RISK: $R = 0.25 ATR = 100 NQ pts = $200/micro disaster stop (rarely hit inside 10-20 min); daily_loss_stop MNQ $80 / MES
  $60; daily_profit_stop MNQ $160 / MES $120
```
Grid (<= 16): `N {30, 60}`, `z_in {2.0, 2.5}`, `max_hold {10, 20}`, `vix_min {0, 18}`. Fixed: confirm 'cross_back' (one
follow-up with 'raw'), z_out 0, stop_datr 0.25, sides long (one control run with 'both').

Risk/Lucid: 2-4 trades/day, each a few minutes: the most consistency-friendly shape in the family if it clears costs; avg
trade must be >= 2x costs (>= $5 on MNQ) to count.

Evidence recap: arXiv 2025 tick study; StatOasis; the report's note that VIX > 20 raises the per-trade magnitude.

Data gap: none.

## 13. intraday_mean_reversion__twap_band_revert  (session TWAP +/- band fade: VWAP-SD / VWAP +/- K x ATR with a volume-free proxy; existing module `twap_revert`, untested)

Priority **2**, complexity **2** (module exists; add band modes and a confirmation entry), instruments **MNQ, MES**, bar size:
5-min on 1-min execution. EQ 2 (LuxAlgo / NexusFi descriptive: +/-2 sigma is where reversion "plays out most consistently";
StockSharp #0235 vendor PF 1.37, win 37-48%, unverified). **Data flag: true VWAP needs volume; `session_vwap` is a cumulative
TWAP of typical price and the SD band is the cumulative stdev of typical price. On trend days the TWAP lags VWAP more than
VWAP lags price, so the proxy is biased toward MORE band touches; treat results as an upper bound on the VWAP version.**

```
PARAMS: bar=5, band='sd' ('sd' | 'cumsd' | 'atr'), lb=24, k=2.0, atr_len=14, entry='limit' ('limit' | 'confirm'), valid=10,
  stop_mult=1.5, tgt_frac=1.0, max_hold=60, first_entry='10:00', last_entry='15:00', flat='15:55', max_trades=3,
  max_trend_atr=0.6, adx_max=99, sides='both'
PRE: B5 RTH bars; twap_t = session_vwap(B5) (anchor 09:30); dev_t = close_t - twap_t; ATR14d; O930
  band_t: 'sd'   = k * rolling stdev(dev, lb) within the session (min_periods max(6, lb//2))   (module as built)
          'cumsd'= k * cumulative stdev of typical price since 09:30 (VWAP-SD bands)            (needs >= 3 bars)
          'atr'  = k * ATR5(atr_len) on B5all                                                   (StockSharp #0235)
  ok_t = tod in [first_entry, last_entry) AND band notna AND |close_t - O930| < max_trend_atr*ATR AND ADX5(14) < adx_max
SIGNAL bar t: LONG if ok and dev_t < -band_t; SHORT if ok and dev_t > +band_t (apply sides)
ENTRY: 'limit'  : place(t.i_next, side, entry_px = close_t, kind='limit', valid_bars = valid, stop_pts = stop_mult*band_t,
                  tgt_pts = tgt_frac*band_t, max_hold = max_hold)              (module as built: fade at the signal close)
       'confirm': wait for the next bar u whose close is back inside the band (dev_u > -band_u) -> place(u.i_next, side) market,
                  stop_px = extreme of bars t..u -/+ 0.5*band_u, tgt_px = twap_u (fixed at entry), max_hold
SESSION: set_session(first_entry, last_entry, flat); max_trades_day = 3
RISK: $R = stop_mult*band ~ 0.1-0.25 ATR; daily_loss_stop MNQ $80 / MES $60; daily_profit_stop MNQ $160 / MES $120
```
Grid (<= 32): `band {sd, atr}`, `k {2.0, 2.5}`, `stop_mult {1.0, 1.5}`, `tgt_frac {0.5, 1.0}`, `sides {both, long}`. Fixed:
entry 'limit', max_hold 60, lb 24, adx_max 99 (one follow-up with 25 and with entry 'confirm' on the best cell).

Risk/Lucid: 1-3 trades/day, 0.8R winners, fat left tail on trend days (the `max_trend_atr` kill switch is mandatory); daily
loss cap does the rest. Being the proxy of a volume indicator it is the least faithful spec here.

Evidence recap: LuxAlgo/NexusFi/TradingView (no audited numbers); StockSharp (vendor).

Data gap: **VWAP requires volume -> TWAP proxy (flagged)**; the hourly Yahoo volume (`ES_1h.parquet`) could weight the TWAP
within the hour as a second-order improvement; not required for the first pass.

## 14. intraday_mean_reversion__bb_wick_fade_confirm  (Bollinger(20,2) rejection-wick fade with ADX gate; existing module `mr_bbfade`, dead at defaults)

Priority **1**, complexity **1** (module exists; two untested deltas), instruments **MNQ**, bar size: 5-min (all-session bars).
EQ 2 (crosstrade ES range regimes: 58-65% win, 0.8R/1R, PF 1.3-1.6; no audited backtest). Our defaults: 812 trades, 61% win,
PF 0.90, -$3,436, DD -$7,347 per micro: the published shape reproduces (high win rate) and loses after costs; 10:xx and
12:xx entries are the worst hours.

```
PARAMS (defaults = published): bb_len=20, bb_sd=2.0, wick_frac=0.5, adx_len=14, adx_max=25, atr_len=14, stop_atr=1.0 (x ATR5),
  time_bars=15, max_trend_atr=0.6, entry 09:45-15:00, flat 15:55, sides='both', max_trades=4, loss_cap=0,
  confirm=False (new), band='bb' (new: 'bb' | 'kc', spec 15)
INDICATORS on B5all closes: mid = sma(close, bb_len); sd = rolling std(bb_len); upper/lower = mid +/- bb_sd*sd;
  ATR5 = atr(B5all, atr_len); ADX = adx(B5all, adx_len); ATR14d; O930
SIGNAL bar b: LONG if low_b <= lower_b AND (close_b - low_b) >= wick_frac*(high_b - low_b) AND ADX_b < adx_max AND
  |close_b - O930| <= max_trend_atr*ATR14d AND mid_b >= close_b + 1 tick.  SHORT mirror.
  confirm=True (new): additionally require close_b > lower_b (the bar closed back INSIDE the band; the VWAP-SD2 script's
  re-entry confirmation) and that bar b-1 closed below lower_{b-1} (the excursion was real).
ENTRY: place(b.i_next, side, stop_px = low_b - stop_atr*ATR5_b, tgt_px = mid_b, max_hold = time_bars*5)
SESSION: set_session(entry_start, entry_end, flat); max_trades_day = 4; daily_loss_stop = loss_cap
```
Grid (<= 8): `confirm {True}`, `adx_max {20, 25}`, `sides {long}`, `loss_cap {60, 80}` x `stop_atr {1.0, 1.5}`. Do not re-run the
dead defaults; do not add hour filters (the 10:xx / 12:xx losses are in-sample).

Risk/Lucid: $R ~ 1-1.5 x ATR5 ~ 0.05-0.1 ATR14d; 2-4 trades/day; the daily loss cap is what protects the EOD trail. Expected
verdict: dead; it is here so a fresh agent does not rebuild it from the literature.

Evidence recap: crosstrade.io (ES, range regimes only); Unger BB article unreachable.

Data gap: none.

## 15. intraday_mean_reversion__keltner_revert  (EMA(20) +/- 2 x ATR(14) channel reversion; `band='kc'` mode of the `mr_bbfade` module)

Priority **1**, complexity **1**, instruments **MNQ**, bar size: 5-min (all-session). EQ 1 (StockSharp #0031/#0073 vendor claims,
no independent ES test). Identical machinery to spec 14 with an ATR-width channel and the vendor's close-through exit.

```
PARAMS: ema_len=20, atr_len=14, mult=2.0, stop_atr=2.0 (x ATR5, vendor), exit='mid_cross' ('mid_cross' | 'mid_target'),
  adx_max=25, max_trend_atr=0.6, entry 09:45-15:00, flat 15:55, sides='long', max_trades=3, loss_cap=80
INDICATORS on B5all: mid = ema(close, ema_len); ATR5 = atr(B5all, atr_len); upper/lower = mid +/- mult*ATR5; ADX; ATR14d; O930
SIGNAL bar b: LONG if close_b < lower_b AND ADX_b < adx_max AND |close_b - O930| <= max_trend_atr*ATR14d (vendor: no wick
  rule, raw close beyond the channel). SHORT mirror (sides both).
ENTRY: place(b.i_next, side, stop_pts = stop_atr*ATR5_b, tgt_px = mid_b if exit == 'mid_target' else NaN, max_hold = 120)
EXIT 'mid_cross': first later bar e with close_e > mid_e -> exit_at(e.i_next, which=side)
SESSION: set_session(09:45, 15:00, flat); max_trades_day = 3; daily_loss_stop = loss_cap
```
Grid (<= 8): `mult {2.0, 2.5}`, `stop_atr {1.0, 2.0}`, `exit {mid_cross, mid_target}`; fixed sides long, adx_max 25.

Risk/Lucid: as spec 14. Long shot; run only after specs 12-13 (the better-evidenced indicator fades) have a verdict.

Data gap: none.

## 16. intraday_mean_reversion__hod_lod_shallow_fade  (fade a shallow new session extreme, 50% retrace target; depth-gated)

Priority **1**, complexity **3**, instruments **MNQ, MES**, bar size: 5-min on 1-min execution, mornings. EQ 3 for the base
rates (tradingstats 2019-2026, 14,300 extremes per market: shallow < 0.3 ATR extremes retrace 50%+ ~85% of the time; deep > 1
ATR ~20%) but the study's own stop sweep says the mechanical expectancy is ~0 at every stop width. Specified as the control
that tests the depth gate; the gate itself is reused by specs 12-15 via `max_trend_atr`.

```
PARAMS: min_depth_atr=0.10, max_depth_atr=0.30, stop_atr=0.10, tgt_frac=0.5, max_hold=120, first_entry='09:40',
  last_entry='12:00', flat='15:55', sides='both', max_trades=2
PRE: ATR14d; O930; running session high H / low L over RTH 1-min bars
LOOP B5 RTH bars b (values at close; order at (b+1).i_next after the confirmation bar):
  LOW event at b: low_b < L_{b-1} (new session low) AND min_depth_atr*ATR <= O930 - low_b <= max_depth_atr*ATR
  confirmation bar c = b+1: close_c > low_b AND close_c > close_b (closed back from the extreme)
  -> place(c.i_next, +1, stop_px = low_b - stop_atr*ATR, tgt_px = low_b + tgt_frac*(O930 - low_b), max_hold)
  HIGH event mirror (sides both). Each side at most once per day; no new event while a position is open.
SESSION: set_session(first_entry, last_entry, flat); max_trades_day = 2
RISK: $R = 0.10-0.25 ATR; daily_loss_stop MNQ $80 / MES $60; daily_profit_stop MNQ $160 / MES $120
```
Grid (<= 16): `max_depth_atr {0.3, 0.5}`, `stop_atr {0.10, 0.25}`, `tgt_frac {0.5, 1.0}`, `sides {both, long}`.

Risk/Lucid: expected ~break-even before costs; a positive two-period result would be a surprise worth a look-ahead audit first.

Data gap: none.

## 17. intraday_mean_reversion__ib_overextension_fade  (fade the first failure at >= 1.5x IB extension, afternoon, slow grinds only)

Priority **1**, complexity **4**, instruments **MNQ, MES**, bar size: IB 60 min, 5-min confirmation, 12:00-15:30. EQ 3
(tradingstats NQ/ES 2014-2026: at 1.5x extension continuation 18-25%, reversal 27%, runaway 55%; afternoon 1.2x retests
continue only 23%; fast moves continue 62% vs slow grinds 42%). Counter-trend into the afternoon with a runaway tail: the
family report itself calls it marginal standalone.

```
PARAMS: ext_mult=0.5 (extension level = IB edge + ext_mult*ib_rng, i.e. 1.5x IB), slow_min=45, t_first='12:00', t_last='15:15',
  tgt='edge' ('edge' | 'mid'), stop_cap_ib=0.25, stop_cap_atr=0.3, exit_time='15:30', flat='15:55', sides='both', max_trades=1,
  max_ib_atr=1.5
PRE: IB -> ib_high, ib_low, ib_rng, ib_mid; ATR14d; skip if ib_rng > max_ib_atr*ATR
STATE (long side mirrored): t_break = first 1-min bar after 10:30 with high > ib_high; ext_up = ib_high + ext_mult*ib_rng;
  t_ext = first 1-min bar with high >= ext_up; require t_ext - t_break >= slow_min minutes AND tod(t_ext) >= t_first
  failure = first B5 bar f after t_ext with close_f < ext_up and tod(f.i_next) in [t_first, t_last]; X = max high since t_ext
ENTRY: place(f.i_next, -1, stop_px = X + 1 tick capped at min(stop_cap_ib*ib_rng, stop_cap_atr*ATR) from close_f,
  tgt_px = ib_high ('edge') or ib_mid ('mid'))
TIME EXIT: exit_at(first bar >= exit_time); SESSION: set_session(t_first, t_last, flat); max_trades_day = 1
RISK: daily_loss_stop = one full stop; daily_profit_stop inert
```
Grid (<= 16): `ext_mult {0.4, 0.5}`, `tgt {edge, mid}`, `slow_min {0, 45}`, `sides {both, long}`.

Risk/Lucid: one afternoon trade on maybe 15-20% of days; the `slow_min` pair is the hypothesis. Last-hour fades of index
futures are contra-indicated by the literature (intraday momentum), hence priority 1 and the 15:30 exit.

Data gap: none.

## 18. intraday_mean_reversion__eighty_twenty_filter  (Taylor / Raschke 80-20s setup day as a filter on the Oops stop entry; `setup='8020'` mode of `mr_pdrange`)

Priority **1**, complexity **2**, instruments **MNQ, MES**, bar size: daily setup, 1-min execution 09:30-13:00. EQ 2-3 (Street
Smarts: after a close in the top/bottom 10-20% of the range, 80-90% follow-through next morning but only 50% close beyond;
MQL5 17-yr FX test positive on daily bars, "needs serious upgrade"). Rare (a few per month); objective.

```
PARAMS: pct=0.20, range_filter=True, range_len=10, pen_ticks=5, order_until='13:00', stop_mode='today_ext', stop_cap_atr=0.3,
  tgt='pdc' ('pdc' | 'atr'), tgt_atr=1.0, tgt_cap_atr=0.6, be_trail=True, exit_time='15:00', flat='15:55', sides='both'
PRE (daily, 1-day lag): yesterday's RTH open O1, high H1, low L1, close C1, range R1 = H1 - L1; avg_rng = SMA(R, range_len)
  over days d-1-range_len..d-1
  bullish setup = (O1 - L1)/R1 >= 1 - pct AND (C1 - L1)/R1 <= pct AND (not range_filter or R1 > avg_rng)
  bearish setup = (O1 - L1)/R1 <= pct AND (C1 - L1)/R1 >= 1 - pct AND same range filter
TRIGGER (bullish): the first RTH 1-min bar t with low_t <= PDL - pen_ticks*tick, tod < order_until  ->  at t+1 a BUY STOP at
  PDL (valid_bars = minutes to order_until); stop_px = min low since 09:30 at the fill decision (today's extreme), capped at
  stop_cap_atr*ATR below PDL; tgt_px = PDC ('pdc', capped at tgt_cap_atr*ATR above PDL) or PDL + tgt_atr*ATR ('atr')
  bearish mirror. be_trail: trail_act_pts = R, trail_pts = R.
TIME EXIT: exit_at(first bar >= exit_time); SESSION: set_session('09:31', order_until, flat); max_trades_day = 1
RISK: daily_loss_stop = one full stop; daily_profit_stop inert
```
Grid (<= 16): `pct {0.20, 0.25}`, `range_filter {True, False}`, `tgt {pdc, atr}`, `sides {both, long}`.

Risk/Lucid: too rare to carry an evaluation (expect 1-3 setups/month/instrument); value only as a higher-prior subset of spec 2;
compare its cells against spec 2's unconditional stop-entry on the same days.

Data gap: none.

## 19. intraday_mean_reversion__ib_fail_fade  (initial-balance failed-breakout fade; existing module `mr_ibfail`: DEAD, control only)

Priority **1**, complexity **1** (module exists), instruments **MNQ, MES**, bar size: 60-min IB, 5-min confirmation. EQ 3 for the
base rates (tradingstats: 34% of first IB breaks fail; 55.7% of breakouts retrace 50% into the IB) and our verdict: dead
(MNQ MAIN PF 1.04 / 253 trades, PRIOR 0.79; MES negative both; no plateau; MAIN/PRIOR rank correlation -0.70).

```
RULES AS IMPLEMENTED (for the record): IB = OR(60); skip if ib_rng > 1.5 ATR. First B5 bar after 10:30 and before 11:30 that
  trades beyond the IB (break_mode 'touch'; 'close' requires a close outside); failure = a B5 bar within fail_window (30 min)
  that closes back inside, before 12:00 -> market at the failure bar's i_next, opposite the break; stop 1 tick beyond the
  extreme, capped at stop_cap_atr (0.25) x ATR from entry; target 'mid' (IB midpoint) | 'far' (opposite edge); exit 13:00;
  flat 15:55; 1 trade/day.
WHY IT FAILS: the stop is ~0.10 ATR and is hit 56% of the time before the ~0.15 ATR target; winners' MAE and losers' MFE are
  not separable; the best MAIN cells (fail_window 15) are the worst on PRIOR.
```
Grid: **none**. The only principled variant (ATR-floored stop + far target + in-value filter + 30-min range) is spec 8. Keep the
module as a negative control: if an engine change makes it PF > 1.2 on both periods, audit the engine.

Data gap: none.

## 20. intraday_mean_reversion__lunch_drift_control  (time-of-day control: short 11:00-12:00, long 12:00/13:00-14:00)

Priority **1**, complexity **1**, instruments **MES, MNQ**, bar size: 1-min, pure time entries. EQ 2-3 (Quantpedia "Lunch Effect"
SPY 2010-2024: equity curve positive, a few bp per hour; R_Omega stock-level 12:30 losers). Not a candidate (the per-day drift
is far too small for a $3k target); it is the family's **zero-edge control** for time-of-day effects and a sanity check on the
engine (should be ~flat after costs on both periods).

```
PARAMS: short_leg=True, short_start='11:00', short_end='12:00', long_start='12:00' ('12:00' | '13:00'), long_end='14:00',
  stop_datr=0.5, flat='15:55'
ENTRY: if short_leg: place(index of the short_start bar, -1, stop_pts = stop_datr*ATR14d); exit_at(index of the short_end bar)
       place(index of the long_start bar, +1, stop_pts = stop_datr*ATR14d); exit_at(index of the long_end bar)
       (the engine is one position at a time: the long is placed only after the short's time exit, same bar is fine because
        exits are processed before entries at the open; verify with a trade list)
SESSION: set_session('11:00', '13:05', flat); max_trades_day = 2; daily stops inert
```
Grid (4): `short_leg {True, False}` x `long_start {12:00, 13:00}`.

Use: report it next to every spec above; a reversion spec that does not beat this control on both periods has no edge beyond
the time of day it happens to trade in.

Data gap: none.

---

## Summary table

| # | id | module | priority | complexity | instruments | trades/mo (est.) | key risk |
|---|---|---|---|---|---|---|---|
| 1 | gap_fade_small | mr_gapfade (exists) | 4 | 1 | MNQ | 5-6 | noise-sized stop; ~75% flat days |
| 2 | pdrange_oops_stop | mr_pdrange (exists) | 3 | 1 | MNQ (MES 0.80 cell) | 2-3 | too rare alone |
| 3 | turtle_soup_pd_recross | new | 3 | 3 | MNQ, MES | 6-12 | double-break tail; shorts weak |
| 4 | session_low_limit_dip | new | 2 | 2 | MES, MNQ | 8-15 | low win rate, streaky |
| 5 | wkopen_tuesday_fade | mr_wkopen (exists) | 2 | 1 | MNQ, MES, MGC | 1-2 each | leg only |
| 6 | volband_band_target_long | mr_volband (exists) | 2 | 1 | MNQ, MES, MGC | 2-3 | regime fit on PRIOR |
| 7 | onrev_cross_sectional | mr_onrev (exists, untested) | 3 | 2 | MES+MNQ+MGC | 4-8 per leg | open-to-close P&L fatness |
| 8 | or_whipsaw_invalue | new | 3 | 3 | MNQ, MES | 4-8 | sibling of dead ibfail |
| 9 | opening_drive_fade | new | 2 | 2 | MNQ, MES | 6-10 | costs vs tiny edge |
| 10 | on_range_fail_fade | new | 2 | 3 | MNQ, MES | 4-8 | EQ 1-2 |
| 11 | rsi3_dip_vixgate | new | 2 | 2 | MNQ, MES | 8-15 | long holds, wide stop |
| 12 | zscore_1m_long | new | 2 | 2 | MNQ, MES | 20-40 | bp-sized edge vs costs |
| 13 | twap_band_revert | twap_revert (exists, untested) | 2 | 2 | MNQ, MES | 15-30 | VWAP proxy (flag); trend days |
| 14 | bb_wick_fade_confirm | mr_bbfade (exists, dead) | 1 | 1 | MNQ | 30-40 | dead at defaults |
| 15 | keltner_revert | mr_bbfade band='kc' | 1 | 1 | MNQ | 20-30 | EQ 1 |
| 16 | hod_lod_shallow_fade | new | 1 | 3 | MNQ, MES | 15-25 | expectancy ~0 by the source |
| 17 | ib_overextension_fade | new | 1 | 4 | MNQ, MES | 2-4 | afternoon counter-trend tail |
| 18 | eighty_twenty_filter | mr_pdrange setup='8020' | 1 | 2 | MNQ, MES | 1-3 | rare |
| 19 | ib_fail_fade | mr_ibfail (exists, dead) | 1 | 1 | MNQ, MES | 12 | control only |
| 20 | lunch_drift_control | new | 1 | 1 | MES, MNQ | 20-40 | control only |

Run order for a fresh agent: 1 (grid deltas) -> 3 -> 8 -> 7 (portfolio) -> 2 (deltas) -> 12 -> 13 -> 9 -> 10 -> 11 -> 4 -> 6 -> 5
-> the rest only if time allows. Every run: MAIN 2025-01-01:2026-09-30 and PRIOR 2023-01-01:2024-12-31, both contracts where
listed, `--mc` Lucid scan on any cell with PF >= 1.2 on both periods, and the zero-edge control reported alongside.
