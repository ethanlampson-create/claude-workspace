# Specs: ICT, Smart Money Concepts and price-action methods as objective rules for the Lucid 50K LucidFlex backtest

Source report: `/home/user/claude-workspace/research/families/ict_smc_price_action.md` (20 strategies S1-S20, sections 0-4).
Engine contract: `/home/user/claude-workspace/docs/STRATEGY_GUIDE.md`, `backtest/engine.py` (`Intents.place / set_session /
exit_at`, `allow_entry`, `max_trades_day`, `daily_loss_stop`, `daily_profit_stop`), helpers in `strategies/common.py`
(`atr`, `ema`, `session_vwap`, `prior_day_stats`, `overnight_range`, `opening_range`, `daily_atr`, `session_info`, `vix_lag1`) and
`backtest.data.resample(df1, N, rth_only=True)` (`i_first`, `i_last`, `i_next`).

**State of play before anything in this family runs (read first).**

| existing module | relation to this family | result (per micro, MAIN 2025-01..2026-09 / PRIOR 2023-24) |
|---|---|---|
| `strategies/orb_reclaim.py` | sweep of London/PDH/PDL levels traded as **continuation** (stop entry beyond the sweep extreme after a 3-bar pullback, 3.5R) | marginal: MNQ am_only, London levels only: PF 1.33 / 1.18, 31% win, Sharpe 1.59 / 0.84; PD levels and MES/MGC dead |
| `strategies/mr_pdrange.py` | open outside PDH/PDL, fade back to the level (Williams "Oops" stop entry = a reclaim) | marginal: MNQ stop-entry variant PF 1.29-1.39 on 47 trades MAIN, 1.56 PRIOR, ~2 trades/month |
| `strategies/mr_ibfail.py` | IB failed-breakout fade (= Brooks FBO on the IB, S15) | dead: stop (1 tick beyond extreme) hit 56%, payoff 1.6, avg +$1.8 |
| `strategies/orb_close30.py` | 5-min close-confirmed OR continuation | marginal: PF 1.43 / 1.08 on MNQ |

Two consequences. (1) Spec 2 below (sweep **reversal** with a close-back-inside) is the opposite trade to `orb_reclaim` on the
same levels; `orb_reclaim`'s own ledger says sweeps of PDH/PDL continued often enough to make its PD-level cells negative in
MAIN, which is mildly *favourable* for the reversal rule on PD levels and *unfavourable* on London levels. Run spec 2 on PD and
ON levels first. (2) The mr_ibfail result is the base rate for every "stop 1 tick beyond the extreme" rule: it loses. Every
reversal spec here therefore places the stop `stop_k x ATR1` beyond the extreme (Osler 2003: stops cluster just beyond the
level; ours must sit beyond that cluster) and caps it in daily-ATR terms.

Family-level prior from the report: the two best-controlled coded tests of ICT entries on our instruments (MPM FVG, ~40k gaps,
2019-2026; hindsight Silver Bullet NQ 1-min, 78 trades, PF 0.87, 2025 PF 0.51) are negative, and the canonical ICT payoff shape
(20-35% win, 5-16R outliers, 15-17R drawdowns) is the worst possible shape for a $2,000 EOD-trailing, 50%-consistency account.
Every spec below is therefore re-cut to the Lucid shape (1R-1.5R targets, stops 1-2 x ATR1, 2-6 trades/day, daily caps) and the
canonical form is kept only as a negative control (spec 5). Only spec 1 (JJ Simon displacement model, 158 manual trades, 54%,
PF 1.76) has a positive in-family NQ 1-minute record, and it is manual, cost-free and in-sample-filtered.

---

## 0. Conventions used by every spec

**Times.** All ET. Data session 18:00 -> ~16:14 next day for the index proxies, 18:00 -> 17:00 for gold. RTH equities
09:30-16:00; gold pit 08:20-13:30. A 1-minute bar with `tod = T` covers `[T, T+1)`. A decision "at the close of bar i" places its
order at `i+1` (1-min) or at `i_next` (N-min bar; `i_next == -1` -> skip). "Market" = `place(i+1, side)` with `entry_px` NaN:
fills at the open of bar i+1 plus 1 tick slippage. "Stop entry" fills at `max(open, level) + slip`; "limit entry" fills at the
level only when the bar trades through it by `through_ticks` (1 tick), no slippage. Decisions never use the open of the bar the
order is placed on. Overnight windows (03:00-04:00, 02:00-05:00) are legal: the session runs from 18:00 and `set_session`
supports them; the forced flat for those specs is still 15:55 (equities) / 16:45 (gold) and they also carry a time stop.

**Forced flat.** Equities `flat = '15:55'` (never later than 15:58). Gold pit specs `13:25`; gold 23-hour specs `16:45`. No
overnight, no weekend. Early-close sessions (`session_info().early_close`): no entries after 12:00; the engine flattens at the last bar.

**Engine facts the state machines rely on** (verified in `backtest/engine.py`):
- Signals placed on bars while a position is open are **ignored** (the in-position branch never reads `sig`). A module may
  therefore emit every candidate signal; only the first one after the position closes is taken. Specs that need "one trade per
  level per day" or "one per structure" still need an internal mirror (as `orb_reclaim` does) to know which level was consumed.
- A new pending order **replaces** a live pending order; a market signal cancels a pending order.
- `it.allow_entry[i] = False` on bar i **drops a pending order** at that bar (the flat branch sets `pend = 0` on a blocked bar).
  This is the only cancellation mechanism; use it for "cancel if a bar closes through the far side of the zone" rules.
- Protective stops fill at level - slip and are assumed to hit before the target when both are inside one bar. Trailing:
  `trail_act_pts` (MFE needed to activate) and `trail_pts` (distance from the extreme); a break-even ratchet is
  `trail_act_pts = trail_pts = X`, giving stop = entry once MFE >= X. `max_hold` = bars. `exit_at(idx, which)` with `which`
  2 (any), 1 (longs), -1 (shorts) exits an open position at the open of `idx`.
- `daily_loss_stop` / `daily_profit_stop` ($ per contract, realized) block **new** entries only.

**Instruments.** MNQ (NSXUSD) first for every index spec (every ICT source trades NQ; ES targets in points are too small
against fixed costs in this family's R-sized brackets), MES second, MGC where stated. Tick: 0.25 (MNQ/MES), 0.10 (MGC).
Point value: MNQ $2, MES $5, MGC $10. Costs in the engine: $1.30 RT + 1 tick slippage per side on market/stop fills (MNQ
$2.30, MES $3.80, MGC $3.30 per round trip), none on limit fills.

**Indicators (exact).**
- `ATR14d` = `daily_atr(df1, 14, rth_only=True, rth=(rth_open, rth_close))`: Wilder ATR of RTH daily bars, lagged one day. NaN
  -> no trade. 2025-26 medians: NDX ~398 pts, SPX ~76 pts, GC ~69 pts.
- `ATR1(n)` = Wilder ATR of the **continuous** 1-minute series (overnight bars included, sessions concatenated), `min_periods=n`,
  value used at bar i is the value at the close of bar i-1 (`shift(1)`). Default n=20 for displacement thresholds, n=14 for
  stop distances and regime bands. Expressed in ticks where a spec says "ticks" (`ATR1_ticks = ATR1 / tick`). 2025-26 RTH
  medians (approx.): NQ ~10-16 ticks (2.5-4 pts), ES ~5-8 ticks, GC ~8-12 ticks. Note: in the first RTH minutes the window is
  mostly overnight bars, so thresholds are lower there; specs that mind this start after 09:45 or use `ATR1_rth` (same but on
  RTH bars only, `min_periods=n`, which forbids the first n RTH minutes).
- `ATR5(n)` = Wilder ATR on `B5 = resample(df1, 5, rth_only=True, rth=(rth_open, rth_close))`, shifted one bar.
- `EMA20_5` = EMA(20) of B5 closes, shifted one bar; `EMA200_1` = EMA(200) of 1-min closes on the continuous series.
- `VWAP` = `session_vwap(df1, anchor_tod=hm('09:30'))`: **time-weighted** average of typical price from 09:30 (no volume; flagged
  as an approximation in every spec that uses it). Value at the close of bar i.
- `SH(N)` / `SL(N)` = swing high/low: bar k is a swing high if `high[k] > max(high[k-N..k-1])` and `high[k] >= max(high[k+1..k+N])`;
  it is **confirmed at the close of bar k+N** and usable from bar k+N+1. Mirror for swing lows. Defaults N=3 (internal, 1-min
  and 5-min), N=5 (swing structure). Never use an unconfirmed swing.
- `FVG` at the close of bar i: bullish if `low[i] > high[i-2]`; zone `[high[i-2], low[i]]`, `CE` = midpoint, `gap = low[i] -
  high[i-2]`. Bearish if `high[i] < low[i-2]`; zone `[high[i], low[i-2]]`. Size filter `gap >= min_gap_atr x ATR1(20)`.
  Mitigated (wick) when a later bar trades through the far edge; mitigated (close) when it closes beyond it; **inverted** when a
  later bar closes through the whole gap.
- `DISP` (ICT displacement bar, hindsight definition): `body = |close - open| > disp_mult x ATR1(20)` and `body / (high - low) >= 0.70`.
- `JJDISP` (JJ Simon displacement bar): bullish if `close > open` and `(open - low) <= wick_frac x (high - open)`; bearish if
  `close < open` and `(high - open) <= wick_frac x (open - low)`; plus a size floor `(extreme - open) >= min_size_atr x ATR1(14)`.
- `SWEEP(L)` of a high-type level L (reference for shorts): bar i with `high[i] >= L + 1 tick` and `close[i] < L`. The sweep
  **extreme** X = max high over the consecutive bars with `high > L` from the first poke until the first close back below L. If
  `n_beyond` consecutive closes occur above L before a close back inside, the level is a **breakout**, not a sweep, and is dead
  for reversal that day (edgeful: PDH break -> 81% green close). Mirror for low-type levels (longs).
- Levels (per session d, all from bars strictly before the entry window): `PDH/PDL/PDC` = prior RTH high/low/close
  (`prior_day_stats`, 1-day lag); `ONH/ONL` = 18:00 -> 09:30 high/low (`overnight_range`); `LONH/LONL` = high/low of bars with
  `tod in [02:00, 08:30)`; `H9/L9` = high/low of the 09:00-09:59 bars (valid from 10:00); `IBH/IBL` = 09:30-10:29 (valid from
  10:30); `ORH/ORL(N)` = `opening_range(df1, '09:30', N)`; `RN(step)` = round numbers (ES 25 pts, NQ 100 pts, GC $10) within
  `[PDL - 0.5 ATR14d, PDH + 0.5 ATR14d]`; `EQH/EQL` = two confirmed swing highs (N=3) within `eq_tol x ATR1(14)` of each
  other, >= 10 bars apart, both within the last 120 bars.
- Daily bias `S19`: `lh[d] = close(d-1) < high(d-2)` (lower-high day: PDL more likely visited), `hl[d] = close(d-1) > low(d-2)`.
  `SMA_D(n)` bias as in the ORB specs (`close > SMA -> +1`). `VIX_lag` only as a diagnostic bucket.

**Lucid risk block (default for every spec unless overridden; values per ONE micro; the Lucid Monte Carlo scales 5-40).**
- `$R` = |entry - initial stop| x point value for the trade; every spec states its typical `$R`.
- `daily_loss_stop = L_R x median $R` with `L_R = 3` (three full losses halt new entries for the day).
- `daily_profit_stop = P_R x median $R` with `P_R = 6` (default), so that the realized day is capped near 6R per micro; the Lucid
  sizing step must keep `micros x P_R x $R <= $1,400` so the largest day stays below 50% of the $3,000 target at the moment of
  passing (consistency rule). With fixed-tick brackets (spec 1) this is a hard cap; with ATR-sized stops use the median `$R`.
- `max_trades_day` as stated (2-6). One position and one pending order at a time. Every entry has a hard protective stop. Never
  hold through 15:55 (equities).
- Consistency/payout arithmetic reminder: many small green days (>= $150 at funded size) beat few large ones; a 50-60% win,
  1R-1.5R, 3-6 trade/day shape produces the most qualifying days.

**Controls every spec must beat** (same period 2025-01..2026-09, same contract, after costs):
1. `trend_momentum__benchmark_long_0945` (buy 09:45, flat 15:55).
2. **Random-time control** for entry-timing specs (1, 2, 13, 14, 18): the same bracket (stop/target/max_hold/session) entered at
   uniformly random bars inside the same window, 20 seeds; the real rule must beat the 90th percentile of the seeds on PF and
   on average trade.
3. **Random-zone control** for zone specs (3, 4, 9, 10, 12): zones of the same width distribution placed at random bars, identical
   entry/stop/target/cancel logic, 20 seeds (puravidaedge design).
4. **Spec 5 (Silver Bullet) is the negative control.** Expected PF < 1.0 on both periods; if it shows PF > 1.3 on both, audit the
   engine for look-ahead (unconfirmed swings, same-bar FVG fills, hourly exit resolution) before believing any winner.
5. The MPM FVG baseline (spec 3 with C1, 1R, no filters) is expected at PF ~1.0 after costs; a filtered variant must beat it by
   >= 0.15 PF on both periods, not just on MAIN.

Priority: 5 = best prior of working under Lucid constraints with evidence and our results; 1 = long shot / control.
Complexity: 1 = a parameter on an existing module; 5 = multi-state intraday machine with cross-instrument alignment.

Recommended run order: 1, 2, 3 (as baseline), 4 (+ control), 5 (control), 18, 13, 7, 6, 14, 15, 11, 8, 12, 10, 16, 9, 17.

---

## 1. ict_smc_price_action__displacement_from_open  (JJ Simon "Fair Value Theory": 1-min displacement bar away from / back to the 09:30 open, fixed-tick bracket; S10)

Priority **4**, complexity **3**, instruments **MNQ** (then MES at ES-scaled ticks), bar size 1-min. EQ 2 (158 manual trades,
54% win, PF 1.76, max loss streak 5, no costs, in-sample window filter). Best Lucid shape in the family: 25-tick NQ stop = $12.50
per MNQ, 1.5R target, several trades per day, no outlier dependence.

```
PARAMS (defaults = published rule): anchor='09:30', pm_anchor=None|'14:00', skip_min=3, mr_window=30, last_entry='15:00',
  wick_frac=0.20, min_size_atr=1.0, triggers='both'|'cont'|'mr', mss_lookback=5,
  bracket_mode='fixed'|'atr', stop_ticks=25, rr=1.5, regime_lo=7, regime_hi=20 (ATR1 in ticks),
  bracket_table={lo:(16,24), mid:(25,37.5), hi:(50,75)}  # (stop ticks, target ticks); mid = published 25/38.5
  atr_k=2.5 (bracket_mode atr: stop = atr_k x ATR1(14), target = rr x stop),
  entry_mode='market'|'limit_close', limit_valid=3, max_hold=0|45, max_trades=4, flat='15:55'
  MES scaling: ticks x 0.4 (ES ATR1 is ~0.4x NQ's in ticks): mid bracket 10/15 ticks; MGC: 10/15 ticks (not published; test only)
PRE per session d:
  A[d] = open of the first RTH bar (tod 09:30). If pm_anchor: A = open of the 14:00 bar for bars with tod >= 14:00.
  a_ticks[i] = ATR1(14)[i] / tick  (value at close of i-1)
  regime[i] = 'lo' if a_ticks < regime_lo; 'hi' if a_ticks > regime_hi; else 'mid'
  (stop_t, tgt_t) = bracket_table[regime] if bracket_mode=='fixed' else (atr_k*a_ticks, rr*atr_k*a_ticks)
SIGNAL at the close of 1-min bar i, tod in [09:30+skip_min, last_entry), ATR1 not NaN:
  bull = close>open and (open-low) <= wick_frac*(high-open) and (high-open) >= min_size_atr*ATR1(14)
  bear = close<open and (high-open) <= wick_frac*(open-low) and (open-low) >= min_size_atr*ATR1(14)
  CONTINUATION (triggers in {'both','cont'}):
     bull and close > A  -> side=+1      # displacement closing AWAY from the anchor, above it
     bear and close < A  -> side=-1
  MEAN REVERSION (triggers in {'both','mr'}; only tod < 09:30 + mr_window):
     bull and close < A and close > max(high[i-mss_lookback..i-1]) -> side=+1   # 1-min structure break back toward A
     bear and close > A and close < min(low[i-mss_lookback..i-1])  -> side=-1
  (if both continuation and MR fire on one bar they point the same way; one signal)
ENTRY: entry_mode 'market': place(i+1, side, stop_pts=stop_t*tick, tgt_pts=tgt_t*tick, max_hold=max_hold)
       entry_mode 'limit_close': place(i+1, side, entry_px=close[i], kind='limit', valid_bars=limit_valid, stop_pts=..., tgt_pts=...)
         (fills only on a 1-tick pullback through the displacement close; removes the +1 tick slip but misses runners)
STOP/TARGET: fixed ticks from the fill (stop_pts / tgt_pts). No trailing (published). max_hold optional.
SESSION: set_session('09:33', last_entry, flat); max_trades_day = max_trades. Signals while in a position are ignored by the engine.
  Published avoid-15:00-16:00 -> last_entry 15:00. Optional window filter (grid): entries only in 09:33-11:30 and 13:30-15:00.
RISK: $R = 25 ticks x $0.50 = $12.50/MNQ (mid regime). daily_loss_stop = 3 x $R ($37.50); daily_profit_stop = 6 x $R ($75).
  At 20 micros: $250 risk/trade, day loss cap $750, day profit cap $1,500 (= consistency ceiling; use 18 micros to stay under).
```
Grid (<= 48): `triggers {both, cont}`, `wick_frac {0.20, 0.30}`, `rr {1.0, 1.5}`, `bracket_mode {fixed, atr}`,
`max_trades {4, 8}`, plus one `entry_mode limit_close` run and one `window_filter` run on the best cell. Fixed: stop_ticks 25,
skip_min 3, mr_window 30, min_size_atr 1.0 (not published; it only removes doji "displacements" smaller than one ATR, and is
listed here because the published rule is silent on size).

Evidence recap: 158 trades 54% / PF 1.76; MR subset 49-59% / PF 1.46; Feb 2026 43 trades 58% +19R; Apr 2023 chop underperformed.
Expect the costed, mechanical version to land well below PF 1.76; the question is whether it clears PF 1.3 with >= 150 trades on
MAIN and >= 1.1 on PRIOR. Diagnostics to keep: P&L by regime, by trigger type, by hour; the random-time control is essential
because a 25/37.5-tick bracket on NQ in 2025 is close to the 1-min noise scale.

Data gap: none (OHLC only).

## 2. ict_smc_price_action__level_sweep_reclaim  (liquidity sweep of PDH/PDL/ONH/ONL (+ H9/IB/London/round numbers) with close-back-inside, ATR stop beyond the extreme, VWAP/midpoint target; S5 + S13 levels + S19 bias + S20 windows + S6 NY Power-of-Three)

Priority **4**, complexity **4**, instruments **MNQ, MES** (MGC with pit levels), bar size 1-min (5-min MSS variant). EQ 3
(Osler 2000: levels halt moves +4-6 pp over arbitrary levels; Osler 2003: stops cluster just beyond them; edgeful: PD-level breaks
continue 63-81% of the time, hence the mandatory close-back-inside; our `orb_reclaim` continuation ledger). This is the family's
most Lucid-compatible reversal: stops 1-2 x ATR1 (NQ 5-25 pts), VWAP/midpoint targets, 1-3 trades/day in 09:30-11:30.

```
PARAMS: levels=['PDH','PDL','ONH','ONL'] (grid adds ['H9','L9'], ['IBH','IBL'], ['LONH','LONL'], RN(step)),
  window=('09:30','11:30') (grid ('09:30','12:00'), ('13:30','15:30') add-on), confirm='close_inside'|'next_bar'|'mss1',
  n_beyond=2 (closes beyond the level before a close back inside -> breakout, level dead), max_exc_atr=1.5 (sweep extreme more
  than this x ATR1(14) beyond the level -> breakout, dead), min_exc_ticks=1,
  entry_mode='market'|'limit_level', limit_valid=5, stop_k=1.0 (x ATR1(14) beyond X), stop_cap_atrd=0.25, min_stop_ticks=6,
  target='vwap'|'mid'|'rr', rr=1.0, min_tgt_r=0.8 (skip if the vwap/mid target is closer than this x risk),
  be_frac=None|0.5 (break-even ratchet at this fraction of the target distance), time_stop=None|'12:00', max_hold=0|90,
  bias='none'|'s19'|'sma200', ema_filter='none'|'with', one_per_level=True, max_trades=3, flat='15:55'
PRE per session d: levels dict {name: (price, type)} with type 'high' (short setup) or 'low' (long setup); PDH/PDL, ONH/ONL known
  at 09:30; H9/L9 from 10:00; IBH/IBL from 10:30; LONH/LONL from 08:30; RN(step) list. ATR1(14), ATR14d, VWAP (time-weighted
  typical price from 09:30, approximation), EMA200_1, mids: pd_mid=(PDH+PDL)/2, on_mid=(ONH+ONL)/2, h9_mid, ib_mid.
  bias 's19': longs at PDL/ONL only on lh[d] days; shorts at PDH/ONH only on hl[d] days (MPM: a lower-high day makes a PDL
    visit more likely; we trade the reclaim after the visit, never the tag itself).
  bias 'sma200': longs only if SMA_D(200) bias +1, shorts only if -1.
STATE per level L (type 'high'; mirror for 'low'): armed -> swept -> (confirmed) -> traded | dead
  at the close of each 1-min bar i inside the window:
    armed:  if high[i] >= L + min_exc_ticks*tick: state=swept; X=high[i]; beyond = 1 if close[i] > L else 0
            (a bar that pokes AND closes back inside in the same bar is a one-bar sweep: evaluate the confirm rule now)
    swept:  X = max(X, high[i]); if close[i] > L: beyond += 1; if beyond >= n_beyond or X - L > max_exc_atr*ATR1: dead
            if close[i] < L (close back inside):
               confirm 'close_inside': fire at i
               confirm 'next_bar':     fire at i+1 if close[i+1] < L as well (else keep waiting while still swept)
               confirm 'mss1':         fire at the first bar j >= i with close[j] < min(low[s..j-1]) where s = first poke bar
                                        (1-min structure shift below the sweep leg's lowest low)
    fire at bar f: ref = close[f]; stop_px = X + stop_k*ATR1[f] (at least X + 1 tick); risk = stop_px - ref
       skip if risk > stop_cap_atrd*ATR14d or risk < min_stop_ticks*tick (then state stays swept; may fire again on a later close)
       target: 'vwap': tgt_px = VWAP[f]; 'mid': tgt_px = the level's own range midpoint (pd_mid for PDH/PDL, on_mid, h9_mid,
               ib_mid; RN -> rr); 'rr': tgt_px = ref - rr*risk. Skip (stay swept) if (ref - tgt_px) < min_tgt_r*risk.
       ema_filter 'with': short only if close[f] < EMA200_1[f]  (long only if above)
       bias checks as above
       ENTRY 'market': place(f+1, -1, stop_px=stop_px, tgt_px=tgt_px, trail_act_pts=be, trail_pts=be, max_hold=max_hold)
             'limit_level': place(f+1, -1, entry_px=L, kind='limit', valid_bars=limit_valid, stop_px=..., tgt_px=...)
             (sell limit at the level: fills only if price trades back up through L + 1 tick; a cleaner fill, lower fill rate)
       be = be_frac*(ref - tgt_px) if be_frac else NaN
       state=traded (one_per_level); if the engine ignores the signal because a position is open, the mirror marks it traded anyway
    dead/traded: nothing more today
  time_stop: it.exit_at(index of the first bar with tod >= time_stop, which=2)
SESSION: set_session(window[0], window[1], flat); max_trades_day = max_trades; allow_entry masked to the window(s).
RISK: $R typical MNQ 8-20 pts = $16-40, MES 2-5 pts = $10-25. daily_loss_stop = 3 x median $R; daily_profit_stop = 6 x median $R.
```
Grid (<= 48): `levels {PD+ON, PD+ON+H9+IB}`, `confirm {close_inside, mss1}`, `target {vwap, mid, rr}`, `stop_k {1.0, 1.5}`,
`bias {none, s19}`; then on the best cell: `entry_mode limit_level`, `be_frac 0.5`, `ema_filter with`, `window 13:30-15:30 add-on`,
`levels + RN(100 NQ / 25 ES)`, `levels + LON`. Fixed: n_beyond 2, max_exc_atr 1.5, stop_cap_atrd 0.25, max_trades 3, rr 1.0.

Notes. (a) `orb_reclaim`'s continuation entries on PD levels were negative in MAIN; if this reversal rule is also negative on PD
levels, the level simply carries no directional information after a sweep and both should be retired. (b) The NY Power-of-Three
(S6) is this spec with `levels=['ONL','ONH','ORL(5)','ORH(5)']`, window 09:30-10:00, bias sma200 and target PDH/ONH (`target
'opp'`: the opposite-type level; add as an extra target option only if 'mid'/'vwap' work). (c) test-max's 5-min version (reference
range 09:00-09:25, signal 09:30-10:25, confirm on a close above the sweep candle's high, exit 11:00) is `levels=['H9','L9']` with
`confirm='next_bar'` on B5 and `time_stop='11:00'`; run it as one extra cell. (d) VWAP is time-weighted (data gap: no volume).

Evidence recap: level effect +4-6 pp (Osler); reversal-vs-continuation unknown on ES/NQ 2022-26 with numbers; the report found no
coded sweep-and-reverse futures backtest. Expect 45-60% win at 1R, and the whole edge, if any, to sit in 09:30-11:30.

Data gap: VWAP is a time-weighted proxy; volume-spike / delta sweep filters from the TradingView scripts are dropped.

## 3. ict_smc_price_action__fvg_midpoint_bracket  (fair value gap limit entry at the midpoint / near edge with ATR stop and 1R-2R target; the MPM baseline; S2 constructions C1, C3, C5)

Priority **2**, complexity **3**, instruments **MNQ, MES, MGC**, bar size 1-min base; FVGs on 1-min and 5-min. EQ 4 (MPM
2019-2026, ~40k FVGs, 1-min exit resolution: no tradeable edge at any entry/timeframe; reaction +5 pp over random). This spec is
run mainly to establish the baseline that spec 4 and spec 5's re-cut must beat, and because the C1-1R construction is the
lowest-variance FVG form if a filter (session, displacement, premium/discount) turns out to matter.

```
PARAMS: bar=1|5, min_gap_atr=0.3 (x ATR1(20); 0 = MPM unfiltered), disp_filter=False|True (middle-bar range > 1.5 x median range
  of the prior 20 bars of the same size), construction='C1'|'C3'|'C5', stop_mode='atr'|'far_edge', stop_k=1.0 (x ATR of the bar
  size, period 14), rr=1.0|2.0|3.0, window=('09:30','11:30') (grid ('09:30','15:30')), expiry=60 (1-min bars the limit stays
  live), cancel_on_mitigation=True (a close through the far edge before the fill cancels the order via allow_entry),
  pd_filter='none'|'vwap' (buy only if CE < VWAP, sell only if CE > VWAP), dir_filter='none'|'ema' (bullish only if close >
  EMA200_1), max_trades=3, flat='15:55'
SIGNAL at the close of bar i (bar size `bar`): bullish FVG: low[i] > high[i-2], gap >= min_gap_atr*ATR; (disp_filter) range[i-1] >
  1.5 x median(range[i-21..i-2]). zone=[lo=high[i-2], hi=low[i]], CE=(lo+hi)/2. Mirror bearish.
  C1: buy limit at CE.  C3: buy limit at hi (near edge).  C5: no order yet; wait for a rejection bar j > i with low[j] <= CE,
      close[j] >= CE and (min(open[j],close[j]) - low[j]) >= 0.5*(high[j]-low[j]) -> market at j+1.
ENTRY: C1/C3: place(i_next, +1, entry_px=CE or hi, kind='limit', valid_bars=expiry, stop_px, tgt_px)
       (a newer FVG in the same direction replaces the pending order: engine semantics; an opposite-direction FVG also replaces it)
STOP: 'atr': stop_px = entry_px - stop_k*ATR(14) of the bar size; 'far_edge': stop_px = lo - 1 tick (C5: lo - 1 tick)
TARGET: tgt_px = entry_px + rr*(entry_px - stop_px)
CANCEL: at the close of any bar j before the fill with close[j] < lo: it.allow_entry[j+1] = False (drops the pending order)
SESSION: set_session(window[0], window[1], flat); max_trades_day = max_trades
RISK: $R: MNQ 1-min C1 ~3-4 pts = $6-8 (too small vs $2.30 costs at rr 1: C1 on 1-min only at rr >= 2), 5-min ~10-15 pts = $20-30.
  daily_loss_stop = 3 x median $R; daily_profit_stop = 6 x median $R.
```
Grid (<= 48): `bar {1, 5}`, `construction {C1, C5}`, `rr {1.0, 2.0}`, `min_gap_atr {0, 0.3}`, `pd_filter {none, vwap}`, `disp_filter
{False, True}`; C3 and `window 09:30-15:30` as two extra runs on the best cell. Run the random-zone control (20 seeds) on the
best cell; MPM's baseline says expect PF ~1.0 everywhere and 5-15-minute bars worst.

Evidence recap: MPM C1 PF ~1.0, C3 breakeven at every RR, C5 3-6 pp win-rate edge on 1h erased by costs, 1 of 18 configs positive
(GC 1h 3R, ~$6/trade); edgeful: 61-63% of FVGs unmitigated by close same session; QTD EURUSD filtered 66.5% win at 2.3RR with
paywalled filters.

Data gap: none; the "premium/discount" filter uses the time-weighted VWAP proxy.

## 4. ict_smc_price_action__order_block_midpoint  (ICT/SMC order block: last opposite bar before a >= 2 x ATR impulse; limit at zone midpoint, stop beyond the far edge, 1R-2R, random-zone control; S7)

Priority **2**, complexity **3**, instruments **MNQ, MES**, bar size 1-min (grid 5-min). EQ 2 (hindsight OB sub-sample +0.18R, n=15,
inside a losing ledger; Reddit multi-asset test negative; vendor 55-62% uncited). Tightest stops in the family (NQ 5-12 pts on
1-min), which is the Lucid attraction; fill modelling is the risk.

```
PARAMS: bar=1|5, imp_mult=2.0 (x ATR(14) of the bar size; grid 1.5, 3.0), imp_window=3 (bars), imp_confirm='none'|'fvg'|'bos'
  (the impulse must also create an FVG / close above the last confirmed SH(3)), zone='full'|'body', entry='mid'|'proximal',
  stop_buf_atr=0.0|0.25 (stop = far edge - 1 tick - buf x ATR), rr=2.0 (grid 1.0), window=('09:30','11:30') (grid ('09:30','15:30')),
  expiry=120 (1-min bars; "5 sessions" in the source is cut to same-session because we are flat by 15:55), require_leave=True
  (price must be above the zone top at placement), cancel_on_close_through=True, max_trades=3, flat='15:55'
SIGNAL at the close of bar i (bar size): bullish OB candidate: let m = first bar of the impulse = i - imp_window + 1 .. i;
  impulse if max(high[m..i]) - close[k] >= imp_mult*ATR(14) where k = the last bar < m with close[k] < open[k] (bearish bar) and
  m - k <= 2 (the impulse must start right after the OB bar). imp_confirm 'fvg': some bar in [m..i] forms a bullish FVG;
  'bos': close[i] > last confirmed SH(3). zone=[lo=low[k], hi=high[k]] ('full') or [min(o,c), max(o,c)] ('body'); mid=(lo+hi)/2.
  Skip if close[i] <= hi (price has not left the zone). One OB per impulse (the first qualifying i).
ENTRY: place(i_next, +1, entry_px = mid ('mid') or hi ('proximal'), kind='limit', valid_bars=expiry, stop_px, tgt_px)
  A newer OB in either direction replaces the pending order (engine); keep an internal list to re-arm nothing (first return only).
STOP: stop_px = lo - 1 tick - stop_buf_atr*ATR(14).  TARGET: tgt_px = entry_px + rr*(entry_px - stop_px). Skip if risk < 4 ticks.
CANCEL: bar j before fill closes below lo -> allow_entry[j+1] = False.
SESSION: set_session(window...); max_trades_day = max_trades.
RISK: $R MNQ 1-min 5-12 pts = $10-24, 5-min 15-35 pts = $30-70. daily_loss_stop = 3 x median $R; daily_profit_stop = 6 x median $R.
CONTROL (mandatory): random-zone: for each real OB, a zone of the same width at a uniformly random bar in the same window of the
  same session, identical entry/stop/target/cancel; 20 seeds; report the seed distribution of PF and avg trade next to the real run.
```
Grid (<= 48): `bar {1, 5}`, `imp_mult {1.5, 2.0, 3.0}`, `imp_confirm {none, bos}`, `rr {1.0, 2.0}`, `entry {mid, proximal}`;
extras on the best cell: `zone body`, `stop_buf_atr 0.25`, `window 09:30-15:30`.

Evidence recap: see above; FvgGold adds +20 quality points for OB+FVG overlap (imp_confirm 'fvg').

Data gap: OBVolume / volume-weighted OB selection (library, LuxAlgo) dropped; the OHLC definition above is the puravidaedge spec.

## 5. ict_smc_price_action__silver_bullet_control  (canonical ICT Silver Bullet / 9 AM-candle range: level sweep -> displacement FVG in the 10:00-11:00 (14:00-15:00, 03:00-04:00) window, limit at the gap, stop beyond the sweep, opposite-liquidity target; NEGATIVE CONTROL, with a 1R re-cut; S1 + S18 9AM-range + S4 wording)

Priority **1** (control), complexity **4**, instruments **MNQ** (MES second), bar size 1-min (15-min for level marking is replaced by
the explicit level list). EQ 3 (two independent coded NQ tests negative: hindsight 78 trades PF 0.87 / 2025 PF 0.51; cjosh PF 0.67).
Purpose: (a) verify the engine reproduces a losing result on a model the literature says loses; (b) test the one re-cut
(OB/CE entry, 1R, no outlier targets) that could fit Lucid.

```
PARAMS: windows=[('10:00','11:00')] (grid + ('14:00','15:00'), + ('03:00','04:00')), pre_window=30 (minutes before the window in
  which the sweep may occur), levels=['PDH','PDL','ONH','ONL','H9','L9'] (grid + EQH/EQL), min_range_pts={MNQ:10, MES:3} (reference
  range H9-L9 must exceed this), disp_mult=1.5 (DISP body > disp_mult x ATR1(20), body ratio >= 0.70), min_gap_atr=0.3,
  entry='near_edge'|'ce', stop='sweep'|'fvg_bar' (1 tick beyond the sweep extreme | beyond the FVG-creating bar's extreme),
  max_risk_pts={MNQ:60, MES:15}, target='opposite'|'rr', rr=2.0 (re-cut 1.0), min_rr=2.0 (skip if the opposite-liquidity target
  is < min_rr x risk; hindsight used 2.5; re-cut 0.8), be_r=None|3.0, max_hold=120, one_per_window=True, flat='15:55'
STATE per window w and session d:
  1. sweep search over bars with tod in [w.start - pre_window, w.end): SWEEP(L) of any listed level (poke >= 1 tick, close back
     inside; X tracked). Record (L, type, X, s=first poke bar).
  2. displacement search after the close back inside: bar i with DISP in the reversal direction AND close[i] back through L
     (long after a low-type sweep: close[i] > L) AND the bar forms an FVG in that direction (bullish: low[i] > high[i-2],
     gap >= min_gap_atr x ATR1(20)). zone=[high[i-2], low[i]]; near edge = low[i]; CE = midpoint.
  3. order: buy limit at near edge ('near_edge') or CE ('ce'), placed at i+1, valid until the window end (valid_bars = bars to
     w.end); the fill must occur inside the window (allow_entry masked to the window). One trade per window.
  4. stop: 'sweep': X - 1 tick; 'fvg_bar': low[i] - 1 tick. risk = entry_px - stop_px; skip if risk > max_risk_pts or risk < 4 ticks.
  5. target: 'opposite': the nearest opposite-type level above the entry among the listed levels (for an H9/L9 sweep: the other
     side of the 09:00-10:00 range); skip if (tgt - entry) < min_rr x risk. 'rr': entry + rr x risk.
  6. be_r: trail_act_pts = trail_pts = be_r x risk (break-even once MFE >= be_r x risk). max_hold = 120 bars (cjosh 2-hour exit).
SESSION: set_session(earliest window start, latest window end, flat); allow_entry masked to the windows; max_trades_day = len(windows).
RISK: $R median NQ ~22 pts = $44/MNQ (hindsight median 21.9 pts). daily_loss_stop = 1 x $R per window traded (the control runs
  1 trade/window); daily_profit_stop inert.
```
Grid (<= 32): `entry {near_edge, ce}`, `stop {sweep, fvg_bar}`, `target {opposite, rr}`, `rr {1.0, 2.0}`, `min_rr {0.8, 2.0}`,
`windows {AM only, AM+PM}`. Expected: canonical cells (opposite target, min_rr 2.0) PF < 1.0 with ~25-35% win on both periods.
If a re-cut cell (ce, 1R, min_rr 0.8) shows PF >= 1.2 on both periods, it is a candidate; verify against the random-time control
and inspect for same-bar fills (an FVG whose near edge is touched on the bar after formation must not fill at that bar's open
unless the open is through the level: engine rule).

Evidence recap: hindsight by entry type: FVG +0.04R (n=46), OB +0.18R (n=15), breaker -0.68R (n=17); cjosh PM window consistent
loser; 5-year manual Reddit test 34% win on Thursdays, "1:2 creates huge drawdowns".

Data gap: none. The 03:00-04:00 window runs on the overnight CFD feed (wider effective spread; run with `slip_ticks=2` as a sensitivity).

## 6. ict_smc_price_action__ifvg_reclaim_smt  (inverse FVG at the NY open: swing sweep -> FVG closed through -> limit at the inverted gap, first target internal liquidity, optional ES/NQ SMT divergence; S3)

Priority **2**, complexity **4** (cross-instrument alignment), instruments **MNQ** (SMT needs SPXUSD aligned on `ts`), bar size 1-min
(grid 3-min via `resample(df1, 3)`). EQ 1 (no statistics anywhere). Included because the structure (reclaim entry, nearby stop,
first target at the last swing) is drawdown-friendly and SMT is codeable with our synchronous ES/NQ data.

```
PARAMS: bar=1|3, swing_n=3, window=('09:30','11:30') (Kane: ('10:00','13:00')), fvg_lookback=30 (bars before the sweep leg in
  which the FVG must have formed), inv_mode='close_through' (a bar closes beyond the whole gap), entry='limit_mid'|'market_inv'
  (market at the inversion close only if that bar is DISP with disp_mult 1.0), expiry=30, stop='x'|'gap_far' (sweep extreme X |
  far edge of the IFVG) + 1 tick, cap_atrd=0.25, tgt1='internal' (last confirmed opposite swing, N=3), min_rr=1.0, tgt_final_rr=None|2.0
  (if set, tgt = max(internal, rr)), be_frac=0.5 (Kane: BE at halfway), smt='off'|'on', max_trades=2, flat='15:55'
PRE: swings SH(3)/SL(3) on the chosen bar size for NSXUSD; if smt: same for SPXUSD aligned by ts (inner join; a bar missing on
  either side disables SMT on that bar). ATR1(20), ATR14d.
STATE (bearish case; mirror bullish):
  1. sweep: bar i with high[i] > SHlast (most recent confirmed swing high) and close[i] < SHlast; X = high[i] (extend over
     consecutive bars above SHlast until the first close below). smt 'on': require SPX high over the same bars <= its own SHlast
     (NQ made the new high, ES did not: divergence) - else skip the setup.
  2. IFVG: among bullish FVGs that formed in bars [s - fvg_lookback, s] (s = sweep bar), the most recent unmitigated one Z=[lo,hi];
     inversion at bar j >= s with close[j] < lo. Z now acts as resistance; zone mid = (lo+hi)/2.
  3. entry: 'limit_mid': sell limit at mid placed j+1, valid expiry bars; cancel if a bar closes above hi (allow_entry mask).
     'market_inv': if bar j is DISP(1.0): place(j+1, -1) market.
  4. stop: 'x': X + 1 tick; 'gap_far': hi + 1 tick; cap at cap_atrd x ATR14d (skip if larger).
  5. target: tgt1 = the last confirmed SL(3) below the entry (internal liquidity); skip if (entry - tgt1) < min_rr x risk;
     tgt_final_rr: tgt = min(tgt1, entry - rr x risk) i.e. the farther one only if tgt_final_rr set (grid).
  6. be_frac: trail_act_pts = trail_pts = be_frac x (entry - tgt).
SESSION: set_session(window...); max_trades_day = max_trades.
RISK: $R NQ 8-20 pts = $16-40/MNQ. daily_loss_stop = 3 x median $R; daily_profit_stop = 6 x median $R.
```
Grid (<= 32): `bar {1, 3}`, `entry {limit_mid, market_inv}`, `stop {x, gap_far}`, `smt {off, on}`, `tgt_final_rr {None, 2.0}`;
`window 10:00-13:00` as one extra run. Random-zone control on the best cell.

Data gap: SMT needs both symbols loaded and aligned (`load_1m('SPXUSD')` + `load_1m('NSXUSD')`, merge on `ts`); the engine runs
one contract, so the SPX series is a feature only.

## 7. ict_smc_price_action__pdh_pdl_mss_fvg  (ICT 2022 model in TradeZella's wording: PDH/PDL sweep -> 5-min market structure shift with displacement -> limit in the MSS FVG -> stop at the sweep, 2R or draw on liquidity; S4)

Priority **2**, complexity **4**, instruments **MNQ, MES**, bar size 5-min structure, 1-min fills. EQ 2 (vendor 55-70% uncited; Reddit
33% at 1:2; components S1/S2/S5 negative). It is spec 2 with a 5-min MSS confirmation and an FVG limit entry; kept separate
because the entry (limit in the gap) and target (2R / draw) differ and because the ICT 2022 model is the most-taught form.

```
PARAMS: levels=['PDH','PDL'] (grid + ONH/ONL), window=('08:30','11:00') (ICT killzone; grid ('09:30','11:30')), mss_bar=5, disp_mult=1.0
  (MSS bar body > disp_mult x ATR5(14)), fvg_source='5m'|'1m' (gap formed by the MSS bar on B5, or any 1-min FVG inside the MSS bar),
  entry='ce'|'near_edge', expiry=60 (1-min bars), stop='sweep' (X + 1 tick; cap 0.30 x ATR14d), target='rr'|'draw', rr=2.0 (grid 1.0, 1.5),
  draw = the opposite listed level (PDL after a PDH sweep); min_rr=1.0 for 'draw', max_trades=2, flat='15:55'
STATE (short after PDH sweep; mirror long):
  1. sweep on B5: 5-min bar with high > PDH and close < PDH inside the window (or a close above PDH followed within 3 bars by a close
     below: beyond count <= 2). X = max high of the sweep bars. s5 = sweep bar.
  2. counter-swing: pl = min(low) of the B5 bars from s5 to the current bar - 1 (the pullback low formed after the sweep);
     require at least one completed bar after s5 so that pl is a formed low, not the sweep bar itself.
  3. MSS: 5-min bar m with close[m] < pl and body > disp_mult x ATR5(14) (displacement) within 12 bars (60 min) of s5.
  4. FVG: '5m': bearish FVG on B5 at m (high[m] < low[m-2]); '1m': the last bearish 1-min FVG formed inside bar m's 1-min range.
     If none: no trade (the model requires it).
  5. order: sell limit at CE ('ce') or near edge (the gap's lower edge for a bearish gap), placed at m.i_next, valid expiry bars;
     cancel if a 1-min bar closes above X (allow_entry mask).
  6. stop: X + 1 tick (skip if risk > 0.30 x ATR14d). target: entry - rr x risk, or PDL ('draw'; skip if < min_rr x risk).
SESSION: set_session(window...); max_trades_day = max_trades (one per level per day).
RISK: $R NQ 15-40 pts = $30-80/MNQ (wider than spec 2 because the stop sits at the sweep high and the entry is a retrace).
  daily_loss_stop = 2 x median $R; daily_profit_stop = 4 x median $R (one or two trades/day).
```
Grid (<= 24): `fvg_source {5m, 1m}`, `entry {ce, near_edge}`, `rr {1.0, 1.5, 2.0}`, `window {08:30-11:00, 09:30-11:30}`; `target draw`
as an extra run. Compare directly with spec 2 cell (levels PD, confirm mss1, target rr 1.0) to measure what the 5-min MSS + FVG
retrace add or subtract.

Data gap: none.

## 8. ict_smc_price_action__judas_asian_range  (London-open Judas swing: sweep of the Asian range then CHoCH close back through, entry at the CHoCH close or FVG, stop beyond the sweep, target the other side of the range; S6)

Priority **1**, complexity **3**, instruments **MNQ, MES, MGC** (gold trades the window with real liquidity), bar size 1-min (5-min
CHoCH variant). EQ 1 (one Reddit 9-trade snippet; FX Replay session with no results). Allowed by Lucid (flat by 16:59) but the
CFD feed in 02:00-05:00 ET is thin: run with `slip_ticks=2` as the base case.

```
PARAMS: asia=('20:00','00:00') (grid ('20:00','02:00')), window=('02:00','05:00'), confirm='choch_close' (a 1-min close back through the
  swept Asian level after the poke; 'choch_5m' = a 5-min close), entry='market'|'fvg_limit' (limit at the near edge of the FVG left
  by the reclaim bar, if any; else market), half_filter=True (longs only if the sweep low is below the Asian midpoint, i.e. the
  entry is in the lower half), stop='sweep_atr' (X -/+ stop_k x ATR1(14), stop_k 1.0), cap_atrd=0.25, target='opposite'|'rr',
  rr=1.5, min_rr=1.0, time_stop='09:25' (never carry into the NY open), max_trades=1, flat='15:55' (MGC '16:45')
PRE per session: AH/AL = high/low of bars with tod in asia (wrapping midnight inside the same 18:00 session), amid=(AH+AL)/2.
STATE (long after AL sweep; mirror short):
  swept: bar i in window with low[i] <= AL - 1 tick; X = min low over consecutive bars below AL; dead if 2 closes below AL before a
  close back above (breakout) or X < AL - 1.5 x ATR1(14).
  confirm: 'choch_close': first bar f with close[f] > AL after the poke -> ref=close[f].
  entry: 'market': place(f+1, +1, ...); 'fvg_limit': if bar f or f+1 forms a bullish FVG: buy limit at its near edge (low[f]) valid 30 bars.
  stop_px = X - stop_k x ATR1[f] (skip if risk > cap_atrd x ATR14d). target: 'opposite': AH (skip if < min_rr x risk); 'rr': ref + rr x risk.
  time_stop: exit_at(first bar tod >= 09:25, which=2).
SESSION: set_session('02:00','05:00', flat); max_trades_day = 1.
RISK: $R NQ 10-30 pts = $20-60/MNQ. daily_loss_stop = 1 x $R; daily_profit_stop inert (1 trade/day).
```
Grid (<= 16): `asia {20:00-00:00, 20:00-02:00}`, `entry {market, fvg_limit}`, `target {opposite, rr}`, `half_filter {True, False}`.
Also run on MGC with `flat 16:45` and `time_stop 08:15`.

Data gap: none. Overnight CFD spread is wider than the CME book in this window; results must survive `slip_ticks=2`.

## 9. ict_smc_price_action__breaker_unicorn  (breaker block: swing low -> swing high -> sweep below the low -> displacement close above the high; limit at the breaker top on the first retest; Unicorn = breaker overlapping the displacement FVG; S8)

Priority **1**, complexity **4**, instruments **MNQ**, bar size 1-min (grid 5-min). EQ 2, negative (hindsight breaker entries 6% win,
-0.68R; definition sensitivity high). Included because it is codeable and the Unicorn (overlap) variant has never been tested; expect
it to lose. Treat as a second control for zone-entry specs.

```
PARAMS: bar=1|5, swing_n=3, max_struct_bars=60 (L1 -> BOS within this many bars), disp_mult=1.5 (BOS bar DISP), zone='full'|'body',
  unicorn=False|True (require the BOS displacement FVG to overlap the breaker; entry at the overlap midpoint), entry='top'|'mid',
  expiry=60, stop='sweep' (X - 1 tick; cap 0.25 x ATR14d), target='projection'|'rr' (H1 + (H1 - L1) | rr 2.0; grid 1.0),
  window=('09:30','11:30'), max_trades=2, flat='15:55'
STATE (bullish breaker; mirror bearish):
  1. L1 = confirmed SL(3); H1 = the next confirmed SH(3) after L1 (H1 > L1).
  2. sweep: bar s after H1's confirmation with low[s] < L1 (X = running min low while below L1).
  3. BOS: bar b > s with close[b] > H1, DISP(disp_mult), b - L1.bar <= max_struct_bars.
  4. breaker zone = the last down-closing bar k with H1.bar <= k <= s (full range or body). If unicorn: the bullish FVG formed by
     the BOS leg (bars b-2..b, or any bullish FVG in [s, b]) must overlap [low[k], high[k]]; zone = the overlap.
  5. order: buy limit at the zone top ('top') or mid, placed b+1, valid expiry bars; cancel if a bar closes below the zone bottom.
  6. stop: X - 1 tick (cap). target: H1 + (H1 - L1) ('projection'; skip if < 1.0 x risk) or rr.
SESSION: set_session(window...); max_trades_day = max_trades; one trade per structure.
RISK: $R NQ 15-40 pts = $30-80/MNQ. daily_loss_stop = 2 x median $R; daily_profit_stop = 4 x median $R.
```
Grid (<= 16): `unicorn {False, True}`, `entry {top, mid}`, `target {projection, rr(1.0)}`, `bar {1, 5}`. Random-zone control mandatory.

Data gap: none.

## 10. ict_smc_price_action__ote_retrace  (Optimal Trade Entry: after a 1-min/5-min MSS with displacement, limit at the 0.705 retracement of the leg, stop below the leg origin, -0.27 extension target; S9)

Priority **1**, complexity **3**, instruments **MNQ, MES, MGC**, bar size 5-min legs (grid 1-min), 1-min fills. EQ 2 (MPM: 38.2/50%
pullbacks no edge beyond drift on GC/SI/NQ/ES 2019-2026; 61.8-79% untested). Low fill rate expected.

```
PARAMS: bar=5|1, swing_n=3, disp_mult=1.0 (MSS bar body > disp_mult x ATR of the bar size), fib=0.705 (grid 0.62, 0.79 as band edges:
  'band' = limit at 0.62 with cancel at 0.79), require_pda=False|True (an FVG or OB of the leg must lie inside [0.62, 0.79]),
  stop_buf_atr=0.25 (stop = leg low - buf x ATR), target='ext27'|'rr' (leg high + 0.27 x leg | rr 1.0), max_leg_age=60 (minutes),
  expiry=60, window=('09:30','11:30'), max_trades=2, flat='15:55'
STATE (bullish; mirror bearish):
  1. MSS: bar m closes above the most recent confirmed SH(3) that is lower than the previous SH(3) (a lower high), with DISP.
  2. leg: low0 = min(low) from the SL(3) preceding the lower high to bar m (the leg origin); high1 = the next confirmed SH(3) after
     m (confirmed at bar h = high1.bar + swing_n). leg = high1 - low0; require leg >= 1.0 x ATR(14) of the bar size.
  3. order at h.i_next: buy limit at high1 - fib x leg, valid min(expiry, max_leg_age) bars; cancel if a bar closes below low0 or
     (band mode) trades below high1 - 0.79 x leg before the fill (allow_entry mask).
  4. stop_px = low0 - stop_buf_atr x ATR; skip if risk > 0.30 x ATR14d. target: high1 + 0.27 x leg ('ext27') or entry + rr x risk.
SESSION: set_session(window...); max_trades_day = max_trades.
RISK: $R NQ 20-45 pts = $40-90/MNQ on 5-min legs (10-20 pts on 1-min). daily_loss_stop = 2 x median $R; daily_profit_stop = 4 x median $R.
```
Grid (<= 16): `bar {5, 1}`, `fib {0.705, 0.62}`, `require_pda {False, True}`, `target {ext27, rr}`. Random-zone control (random
retracement levels of random legs) on the best cell. MPM's drift baseline: compare each cell with "buy at the same time, hold the
same bars" over the same sessions.

Data gap: none.

## 11. ict_smc_price_action__choch_pullback  (SMC change of character on 5-min internal structure with displacement, limit at the OB/FVG left by the CHoCH leg, stop beyond the leg origin, next-swing or 2R target; S11)

Priority **2**, complexity **4**, instruments **MNQ, MES, MGC**, bar size 5-min structure, 1-min fills. EQ 1 (library definition only;
structurally a swing-breakout pullback system). Trend-dependent; the Lucid concern is long flat stretches on range days.

```
PARAMS: swing_n=3 (internal; grid 5), disp_mult=1.5 (CHoCH bar body > disp_mult x ATR5(14)), zone='fvg'|'ob' (the FVG created by the
  CHoCH leg | the last opposite bar before it, full range), entry='mid', expiry=90 (1-min bars), stop='origin' (the swing the leg
  started from -/+ 1 tick; cap 0.30 x ATR14d), target='next_swing'|'rr', rr=2.0 (grid 1.0, 1.5), min_rr=1.0,
  window=('09:30','15:00'), max_trades=3, flat='15:55'
PRE on B5: confirmed SH(n)/SL(n); trend state updated on each confirmed swing: 'down' if the last two swing highs are lower
  highs and the last two lows are lower lows; 'up' mirror; else 'none'.
STATE (bullish CHoCH; mirror bearish): trend == 'down'; bar c closes above the most recent confirmed SH(n) (the last lower high)
  with DISP(disp_mult). leg origin = the lowest low between the previous SH(n) and bar c (an SL(n) if confirmed, else the raw min).
  zone 'fvg': bullish 5-min FVG in bars [c-2 .. c+1] (the leg); 'ob': the last bearish 5-min bar before the leg's first up bar.
  order: buy limit at zone mid placed at the zone bar's i_next, valid expiry; cancel on a 5-min close below the zone bottom.
  stop: origin - 1 tick. target: the next confirmed SH(n) above the entry that is >= min_rr x risk away ('next_swing'), else rr.
SESSION: set_session(window...); max_trades_day = max_trades; one trade per CHoCH.
RISK: $R NQ 20-50 pts = $40-100/MNQ. daily_loss_stop = 2 x median $R; daily_profit_stop = 4 x median $R.
```
Grid (<= 24): `swing_n {3, 5}`, `zone {fvg, ob}`, `rr {1.0, 2.0}`, `target {next_swing, rr}`, `disp_mult {1.0, 1.5}` (drop disp 1.0 if
the count explodes). Compare with `trend_momentum__holy_grail_pullback` / `ema_cross_pullback` results (same family shape).

Data gap: none.

## 12. ict_smc_price_action__supply_demand_fresh_zone  (rally-base-rally / drop-base-drop: 1-3 narrow base bars then a >= 2 x ATR departure; limit at the proximal edge of a fresh zone, stop beyond the distal edge; S12)

Priority **1**, complexity **3** (shares spec 4's machinery: `zone_mode='base'`), instruments **MNQ, MES**, bar size 5-min (grid
15-min via `resample(df1, 15)`). EQ 1 (forex manual ~55% / 1.8RR, no PF/DD; Quantified Strategies declined to test).

```
PARAMS: bar=5|15, base_max_bars=3, base_range_atr=0.5 (each base bar range <= this x ATR(14) of the bar size), dep_mult=2.0 (departure
  >= dep_mult x ATR within 3 bars after the base), zone='full'|'body_high' (base low .. base high | base low .. highest body),
  fresh_only=True (first retest only), entry='proximal' (limit at the zone top), stop_buf_atr=0.25 (stop = zone bottom - 1 tick -
  buf x ATR), rr=2.0 (grid 1.0), htf_filter='none'|'ema' (zone direction = sign(close - EMA(50) of 1-hour closes, lagged)),
  expiry=120, window=('09:30','11:30') (grid ('09:30','15:30')), max_trades=2, flat='15:55'
SIGNAL at the close of bar i: base = the last 1..base_max_bars consecutive bars ending at i-d (d in 1..3) each with range <=
  base_range_atr x ATR; departure: max(high[i-d+1..i]) - base_high >= dep_mult x ATR with close[i] > base_high (bullish). Zone =
  [base_low, base_high]. Fresh: no prior bar since formation has traded below base_high.
ENTRY: buy limit at base_high placed i_next, valid expiry; cancel on a close below base_low.  STOP: base_low - 1 tick - buf x ATR.
TARGET: entry + rr x risk (or the nearest opposing fresh supply zone if >= 1.0 x risk, 'opposing').
SESSION/RISK: as spec 4; $R NQ 10-30 pts on 5-min.
```
Grid (<= 16): `bar {5, 15}`, `rr {1.0, 2.0}`, `htf_filter {none, ema}`, `zone {full, body_high}`. Random-zone control.

Data gap: none.

## 13. ict_smc_price_action__round_number_sr_bounce  (first-touch fade of round numbers and prior swing / prior-day levels with a close back above, stop beyond the stop cluster (1-1.5 x ATR), 1R target; S13)

Priority **2**, complexity **2**, instruments **MES (25-pt), MNQ (100-pt; grid 50), MGC ($10)**, bar size 1-min. EQ 3 (Osler 2000: +4-6 pp
bounce at published levels incl. round numbers; Osler 2003 stop clustering). Thin edge; it is here because its stop placement
rule (beyond the cluster) is the one that mr_ibfail lacked, and because round numbers are the one level set no other spec uses.

```
PARAMS: level_set='rn'|'rn_pd'|'swing' (round numbers | + PDH/PDL/ONH/ONL | 5-min SH/SL(5) touched >= 2 times within tol),
  rn_step={MES:25, MNQ:100, MGC:10} (grid MNQ 50), tol_atr=0.25 (x ATR1(14): the bar's low must come within tol of the level),
  close_rule='upper_half' (close > level and close in the upper half of the bar's range), first_touch_only=True (the level was not
  touched earlier in the session, including the overnight for RN), stop_k=1.0 (grid 1.5; stop = level - stop_k x ATR1(14)),
  target='rr'|'next_level_mid', rr=1.0, window=('09:30','15:30') (grid ('09:30','11:30')), trend_filter='none'|'ema200'
  (no fades against a 1-min EMA200 slope: long only if EMA200_1[i] >= EMA200_1[i-30]), max_trades=4, flat='15:55'
SIGNAL at the close of bar i: for the nearest level L below the close with first_touch: low[i] <= L + tol_atr x ATR1 and low[i] >= L -
  tol_atr x ATR1 (a touch, not a sweep: a bar that pokes through L by more than tol is handed to spec 2) and close[i] > L and
  close[i] >= (high[i] + low[i]) / 2 -> long. Mirror short at the nearest level above.
ENTRY: place(i+1, +1, stop_px = L - stop_k x ATR1[i], tgt_px = close[i] + rr x (close[i] - stop_px)) ('rr') or the midpoint between L
  and the next level above ('next_level_mid'; skip if < 0.8 x risk).
SESSION: set_session(window...); max_trades_day = max_trades; one trade per level per day.
RISK: $R MES 2-3 pts = $10-15; MNQ 6-12 pts = $12-24; MGC 1-2 $ = $10-20. daily_loss_stop = 3 x median $R; daily_profit_stop = 6 x median $R.
```
Grid (<= 32): `level_set {rn, rn_pd}`, `stop_k {1.0, 1.5}`, `rr {1.0, 1.5}`, `window {09:30-15:30, 09:30-11:30}`, `trend_filter {none, ema200}`.
Random-time control is decisive here (the edge is a few pp over a ~56% base).

Data gap: none.

## 14. ict_smc_price_action__brooks_second_entry  (Al Brooks H2/L2: with-trend second pullback entry on 5-min bars, buy stop above the signal bar, stop below the signal bar, 2R / measured move; S14)

Priority **2**, complexity **3**, instruments **MNQ, MES**, bar size 5-min (`B5`). EQ 1 (Brooks' ~60% statements; no backtest). The
objective thinkScript/TradingView definitions are used verbatim.

```
PARAMS: ema_n=20, trend='above_rising' (close > EMA20_5 and EMA20_5[i] > EMA20_5[i-3]), signal_close_pct=0.30 (signal bar closes in its
  top 30%), entry='stop_above' (buy stop 1 tick above the H2 signal bar high, valid 2 bars), stop='signal_low'|'pullback_low'
  (1 tick below the signal bar low | below the lowest low of the pullback), cap_atrd=0.30, target='rr'|'mm' (rr 2.0 (grid 1.0,
  1.5) | measured move = height of the prior leg (last SL(3) to last SH(3)) projected from the signal bar high), skip_first_bar=True,
  window=('09:35','15:00'), max_trades=3, flat='15:55'
STATE on B5 (bull; mirror bear): require trend at the close of bar i.
  pullback leg: a bar with low < prior low starts leg 1. H1 = the first subsequent bar whose high > prior bar high (its close
  reclaims). After H1, if a bar again prints low < prior low (leg 2) and then a bar j has high > high[j-1]: bar j is the H2 signal
  bar; require close[j] >= low[j] + (1 - signal_close_pct) x (high[j] - low[j]).
  order at j.i_next: buy stop at high[j] + 1 tick, valid_bars = 10 (two 5-min bars); stop_px per `stop`; skip if risk > cap_atrd x ATR14d.
  target: entry + rr x risk, or entry + measured move ('mm'; skip if < 1.0 x risk).
  reset the H-count when the EMA condition fails or after an entry.
SESSION: set_session(window...); max_trades_day = max_trades.
RISK: $R NQ 15-40 pts = $30-80/MNQ (5-min signal bars). daily_loss_stop = 2 x median $R; daily_profit_stop = 4 x median $R.
```
Grid (<= 24): `rr {1.0, 1.5, 2.0}`, `stop {signal_low, pullback_low}`, `target {rr, mm}`, `signal_close_pct {0.30, 0.50}`. Diagnostics:
P&L split by `ATR14d` tercile and by trend-day flag (close-open > 0.5 x ATR14d) to confirm the trend-day dependence.

Data gap: none.

## 15. ict_smc_price_action__brooks_breakout_pullback_fbo  (Al Brooks breakout pullback with measured move, and failed-breakout fade on a >= 10-bar 5-min range; S15)

Priority **2**, complexity **3**, instruments **MNQ, MES**, bar size 5-min. EQ 2 (Bulkowski daily-stock flag statistics; Brooks 50%
breakout success in ranges). The failed-breakout fade on the IB is already dead (`mr_ibfail`); this spec tests (a) the BP
continuation, which is new, and (b) the FBO on generic >= 10-bar ranges with an ATR stop rather than a 1-tick stop.

```
PARAMS: mode='bp'|'fbo', range_bars=10 (the range = high/low of the prior >= range_bars 5-min bars, none of which closed outside it),
  disp_mult=1.5 (breakout bar body > disp_mult x ATR5(14)), fail_bars=5, window=('09:35','15:00'),
  BP: pullback must hold (low >= range_high - 0.5 x ATR5) within 6 bars of the breakout; entry buy stop 1 tick above the first bar
      whose high > prior high after the pullback low; stop = range_high - 0.5 x ATR5 (cap 0.30 x ATR14d); target 'mm' (range
      height from the breakout) or rr 1.5
  FBO: a bar within fail_bars after the breakout closes back inside the range; entry market at i_next against the breakout;
      stop = breakout extreme + stop_k x ATR5 (stop_k 0.5; cap 0.30 x ATR14d); target = range midpoint ('mid') or opposite side ('far')
  max_trades=2, flat='15:55'
SESSION: set_session(window...); max_trades_day = max_trades; one BP or FBO per range.
RISK: $R NQ 15-40 pts. daily_loss_stop = 2 x median $R; daily_profit_stop = 4 x median $R.
```
Grid (<= 16): `mode {bp, fbo}`, `range_bars {10, 20}`, BP `target {mm, rr1.5}` / FBO `target {mid, far}`, `disp_mult {1.0, 1.5}`.
Compare FBO with `mr_ibfail` (dead) and BP with `orb_close30` (marginal) before investing further.

Data gap: none.

## 16. ict_smc_price_action__candle_reversal_at_level  (5-min engulfing / hammer / evening-morning star / three-line strike only at a spec-2 level touch, stop beyond the pattern + 0.25 ATR, 1R-2R; S16)

Priority **1**, complexity **2**, instruments **MNQ, MES, MGC**, bar size 5-min. EQ 3 but mostly negative and on daily stocks
(Marshall-Young-Rose 2006: no value; Bulkowski: engulfing/hammer among the worst). Confirmation filter only; the standalone run exists
to quantify what the filter adds to spec 2.

```
PARAMS: patterns=['engulf','hammer','star','tls'] (subsets in the grid), level_set=['PDH','PDL','ONH','ONL'] (+ RN), tol_atr=0.5 (the
  pattern's extreme must be within tol x ATR5(14) of a level, on the correct side), stop_buf_atr=0.25, rr=1.0 (grid 2.0),
  window=('09:30','15:00'), max_trades=3, flat='15:55'
PATTERNS at the close of 5-min bar i (bullish; mirror bearish):
  engulf: close[i]>open[i], close[i-1]<open[i-1], open[i]<=close[i-1], close[i]>=open[i-1]
  hammer: lower wick >= 2 x body, upper wick <= 0.25 x body, close in the top third, after >= 3 declining closes
  star (morning): body[i-2] bearish and >= 1.0 x ATR5; |body[i-1]| < 0.3 x |body[i-2]| with its body below close[i-2]; close[i] bull
        and close[i] > midpoint of bar i-2's body
  tls (bullish three-line strike): three bull bars with higher closes then a bear bar opening above the third close and closing
        below the first open (Bulkowski: bullish continuation after the strike; take it long)
LEVEL: min(low[i-2..i]) within tol x ATR5 of a low-type level (long).  ENTRY: place(i_next, +1).
STOP: pattern low - 1 tick - stop_buf_atr x ATR5; cap 0.30 x ATR14d.  TARGET: close[i] + rr x risk.
SESSION: set_session(window...); max_trades_day = max_trades.
RISK: $R NQ 15-30 pts. daily_loss_stop = 3 x median $R; daily_profit_stop = 6 x median $R.
```
Grid (<= 12): `patterns {all, engulf+hammer, star+tls}`, `rr {1.0, 2.0}`, `tol_atr {0.5, 1.0}`. Then, if spec 2 is alive, add
`candle_confirm` to spec 2's grid as a confirm option.

Data gap: none.

## 17. ict_smc_price_action__double_bottom_hs_neckline  (intraday double bottom / top and head-and-shoulders with neckline-close entry and measured-move target; S17)

Priority **1**, complexity **4**, instruments **MNQ, MES, MGC**, bar size 5-min. EQ 3, negative for futures (MPM 13,704 hourly double
bottoms 2019-2026: no edge beyond drift; neckline-break significance "mechanical"). Included for completeness as a pattern control.

```
PARAMS: pattern='db'|'hs', swing_n=4, match_atr=0.25 (the two lows within this x ATR5(14)), min_sep=8, max_sep=120 (bars), peak_atr=0.5
  (intervening peak >= this x ATR above the higher low), entry='neckline' (market at i_next after a 5-min close above the peak) |
  'second_low' (buy limit at low1 + 0.1 x ATR, stop 0.5 x ATR below), stop='below_second_low', target='mm'|'rr' (pattern height from
  the neckline | rr 2.0, grid 1.0), window=('09:30','15:00'), max_trades=2, flat='15:55'
DB: confirmed SL(4) at k1 and k2 (k2 - k1 in [min_sep, max_sep]), |low[k1] - low[k2]| <= match_atr x ATR, peak = max(high[k1..k2]) >=
  max(low[k1], low[k2]) + peak_atr x ATR; neckline = peak. Entry on the first 5-min close > neckline after k2's confirmation.
HS (top): three confirmed SH(4) h1 < h2 > h3 with |h1 - h3| <= 0.5 x ATR; neckline = line through the two intervening lows (use the
  lower one as a flat level for simplicity); entry on the first close below it; stop above h3; target = h2 - neckline from the break.
SESSION/RISK: as spec 11.
```
Grid (<= 8): `pattern {db, hs}`, `entry {neckline, second_low}` (db only), `target {mm, rr}`. Drift baseline: same-time long/short
holds over the same bars (MPM method).

Data gap: none.

## 18. ict_smc_price_action__equal_highs_sweep  (run on equal highs / lows: two confirmed 1-min swings within 0.1 x ATR, sweep through both with a close back below the lower one, stop beyond the sweep + ATR buffer, 1.5R or last-swing target; S18 equal-highs version)

Priority **2**, complexity **3**, instruments **MNQ, MES**, bar size 1-min. EQ 2 (untested; Osler 2003 stop-clustering mechanism; the
hindsight 9 AM-range version is the negative control in spec 5). It is spec 2 with intraday swing-pair levels instead of session
levels; worth its own run because equal highs are formed many times a day (frequency) and the stop sits just beyond a known cluster.

```
PARAMS: swing_n=3, eq_tol_atr=0.10 (x ATR1(14); grid 0.20), min_sep=10, max_age=120 (bars), window=('09:30','15:00') (grid ('09:30','11:30')),
  sweep_rule='close_below_lower' (high > max(h1,h2) + 1 tick and close < min(h1,h2)), stop_k=0.5 (stop = sweep high + stop_k x ATR1(14),
  at least + 1 tick; grid 1.0), cap_atrd=0.20, target='rr'|'last_swing' (rr 1.5 (grid 1.0) | the last confirmed SL(3) below, skip if
  < 0.8 x risk), be_frac=None|0.5, max_trades=4, flat='15:55'
PRE: confirmed SH(3) list; EQH = the most recent pair (h1 at k1, h2 at k2) with |h1 - h2| <= eq_tol_atr x ATR1, k2 - k1 >= min_sep,
  i - k1 <= max_age, and no bar between k1 and i closed above max(h1,h2).
SIGNAL at the close of bar i: high[i] > max(h1,h2) + 1 tick and close[i] < min(h1,h2) -> short; X = high[i] (a two-bar sweep: the
  first bar closes above, the next closes below min(h1,h2) also qualifies with X = max of both; more than 2 closes above -> dead).
ENTRY: place(i+1, -1, stop_px = X + stop_k x ATR1[i], tgt_px per target, trail = be). Skip if risk > cap_atrd x ATR14d or < 4 ticks.
SESSION: set_session(window...); max_trades_day = max_trades; a pair is used once.
RISK: $R NQ 6-15 pts = $12-30/MNQ. daily_loss_stop = 3 x median $R; daily_profit_stop = 6 x median $R.
```
Grid (<= 32): `eq_tol_atr {0.10, 0.20}`, `stop_k {0.5, 1.0}`, `rr {1.0, 1.5}`, `target {rr, last_swing}`, `window {09:30-15:00, 09:30-11:30}`.
Random-time control mandatory.

Data gap: none.

---

## Not separate specs (folded into parameters)

- **S19 lower-high / higher-low bias** -> `bias='s19'` in spec 2 and (optionally) spec 7. Evidence is for the *visit* probability, and
  MPM showed buying the tag loses; only the reclaim is traded.
- **S20 killzones / macro windows** -> every spec carries a `window` parameter; the PM window 14:00-15:00 is excluded by default
  (cjosh: consistent loser) and appears only as an add-on cell in specs 2 and 5. The ICT macros (09:50-10:10, 10:50-11:10) are not
  gridded: with 2-4 trades/day the sub-windows would have < 40 trades per cell.
- **S6 NY Power-of-Three** -> spec 2 with ON/OR(5) levels, window 09:30-10:00 and `bias='sma200'` (note (b) in spec 2).
- **S18 9 AM-range version** and **S4 full ICT sequence** -> spec 5 (control) and spec 7.
- **S15 FBO on the IB** -> already run as `mr_ibfail` (dead); spec 15 keeps only the generic-range FBO and the breakout pullback.

## Dropped components (need data we do not have)

- Volume-spike / delta confirmation of sweeps (TradingView Sweep&Reverse, NinjaTrader liquidity traps): no volume. Not approximated;
  range expansion is not a faithful proxy for volume at a level.
- Volume-weighted order-block selection (`OBVolume`, LuxAlgo) and session POC / value-area targets (steady-turtle): no volume. The
  POC target is replaced by the range midpoint / time-weighted VWAP (flagged).
- True VWAP: replaced everywhere by `session_vwap` (time-weighted typical price). Every spec that uses it says so; results that hinge
  on a VWAP target (spec 2 `target='vwap'`) must also be shown with `target='mid'`.
- SMT divergence with CL or YM: only ES/NQ are available (spec 6 uses them).
- Daily Turtle Soup (20-day low break with next-day exit): needs holding overnight; not allowed. The intraday reclaim is spec 2.

## Walk-forward and reporting requirements (all specs)

- Periods: MAIN 2025-01-01..2026-09-30, PRIOR 2023-01-01..2024-12-31; then `backtest.walkforward` 12/3 from 2019 for any cell
  with MAIN PF >= 1.3 and PRIOR PF >= 1.1.
- Report by exit reason, hour, regime (`ATR1` tercile, `VIX_lag` bucket), and the control distributions (random-time or random-zone,
  20 seeds). A cell that does not sit outside the 90th percentile of its control is reported as "noise-compatible".
- Lucid: `lucid_scan` on the daily per-micro stream; sizing such that `micros x daily_profit_stop <= $1,400`; report `monthly_pass_rate`
  and `P(first payout)`. Only `recommended` cells go to `results/final_selection.csv`.
