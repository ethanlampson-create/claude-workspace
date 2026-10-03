# Specs: Volatility-based breakout and compression/expansion strategies for the Lucid 50K LucidFlex backtest

Source report: `/home/user/claude-workspace/research/families/volatility_breakout.md` (read fully; section numbers below refer to it) plus the structured findings supplied inline by the harness (22 catalogued items).
Engine contract: `/home/user/claude-workspace/docs/STRATEGY_GUIDE.md`, `backtest/engine.py` (`Intents.place(idx, side, entry_px, valid_bars, stop_px, tgt_px, stop_pts, tgt_pts, trail_pts, trail_act_pts, max_hold, kind)`, `Intents.exit_at`, `Intents.set_session`, public arrays `allow_entry` / `force_flat`, `max_trades_day`, `daily_loss_stop`, `daily_profit_stop`), helpers in `strategies/common.py` (`atr`, `sma`, `ema`, `daily_atr`, `prior_day_stats`, `opening_range`, `overnight_range`, `vix_lag1`, `session_info`), `backtest.data.daily_bars / resample / hm`, Lucid simulator `backtest.lucid.Rules / simulate_eval / monte_carlo`.

**Family verdict (report section 0 and 7), restated because it sets every priority below.** Three cost-aware studies that overlap our prime window say the *unconditioned* version of every strategy in this family is flat-to-negative after futures friction (Fetna 2026: 0/225 ORB cells net-positive at $25/RT over 16 years; Mesfin 2026: 11/14 OHLCV families on MNQ below the 2-pt floor, chasing a completed 5-min expansion bar T = -11.5 on N = 1,955; Oxford Strat 1980-2016: Crabel stretch ORB / NR7 / 2-bar-NR all "C", wide-range breakout "D"). What *is* robust is (a) **compression predicts expansion** (inside days broke the prior range next session 87.8% ES / 88.4% NQ in 2025), (b) **direction has to be imported** (open vs prior-day midpoint: 67% / 58% prior-extreme hits on NQ; momentum / trend filters improve Crabel's ORBP), (c) **entries must be resting stop orders at pre-computed levels filled from 1-minute data, 09:30-11:30 ET** (completed-bar entries are structurally late), (d) **volatility sets size, not permission** (continuation rates within 1.8 pp across ATR regimes on 6,142 ES/NQ sessions), and (e) **the median post-break extension is 36-43% of the prior bar's range**, so a 0.4x-range capped target is what turns the family's fat right tail into the many-$150-days profile the Lucid payout rule wants. The one peer-reviewed positive (Holmberg 2013, crude, 61-80% winners at 1.7-2.3-sigma thresholds, EOD exit, gross) had its whole edge in a high-volatility decade. The specs below therefore put the engine time on **conditioned, one-sided, capped-target breakouts** (specs 1-3), carry the two published ATR / quantile variants as cheaper siblings (4, 5), supply the sizing overlay (6), fold every squeeze / compression indicator into one resting-stop spec (7), and include the Mesfin expansion-bar rule as a **negative control** (8) that must lose or the engine is suspect. The family suits the **safe** configuration (steady $100-300 days) more than the fast one.

**Overlap with sibling spec files (implement once, do not re-run).** `orb_session__crabel_stretch_volbreak` (two-sided Crabel stretch / Williams k x range OCO with NR/ID filters, EOD or 2S target), `trend_momentum__crabel_stretch_nr`, `trend_momentum__williams_volbreak` (`bias=sma20`, rr target) and `trend_momentum__squeeze_breakout` (TTM squeeze as an *entry* on 5-min bars) already exist as specs. The specs here are the **family-specific additions** the report argues for: one-sided ORBP with the prior-midpoint bias and the opposite-level cancel, the wide-spread-day skip, the 0.4x capped target, the ATR-exhaustion cancel, the swing-range unit, the inside-day range-target trade, the Holmberg quantile threshold, the Kaufman ATR-from-close level, 2-bar-NR / ID-NR4 tiers, the sizing overlay and the late-entry controls. Spec 1 is designed so that the sibling two-sided cells are its `bias='none'` rows: register ONE module (`vb_orbp`) and point the sibling ids at it with their parameter cells rather than coding the machinery three times.

---

## 0. Conventions used by every spec below

**Times**: all ET. Data session 18:00 -> ~16:14 (equity CFD feed stops ~16:14), 18:00 -> 17:00 gold. RTH equities 09:30-16:00 (`contract.rth_open/rth_close`); gold pit 08:20-13:30 (MGC trades ~23h but every spec here uses the pit session as "the day"). A 1-minute bar with `tod = T` covers `[T, T+1)`. `i0[d]` = index of the first RTH bar of session d (09:30 equities, 08:20 gold); `O930[d]` = open of that bar; `i1[d] = i0[d] + 1` (**orders are placed on the 09:31 / 08:21 bar, never on the 09:30 bar** whose open is the only thing we know). A decision taken on the close of the bar with `tod = T-1` is executed at the bar with `tod = T`: **market at next open (+1 tick slippage)** unless the spec says `kind='stop'` or `kind='limit'`. On N-minute bars `B = resample(df1, N, rth_only=True, rth=(rth_open, rth_close))` the decision uses the N-bar close and the order index is `B.i_next[k]` (skip `-1`). Rolling indicators use `min_periods` = full window; NaN rows never trade. `max_hold` counts 1-minute bars from the fill bar.

**Forced flat**: equities **15:55** (never later than 15:58); gold pit specs **13:25** (MGC `flat='13:25'` everywhere a spec says `flat`). No overnight, no weekends. Early-close sessions (`session_info().early_close`) do not trade.

**Resting-order rule (mandatory for this family; report sections 4.1 and 7.2)**: every breakout entry is a `kind='stop'` order at a level known before the entry window opens (open +/- k x unit, prior-day high/low, prior close +/- k x ATR, open x (1 +/- rho), compression-window extreme). The engine fills stop entries at `max(open, level) + 1 tick`, so a gap through the level fills at the open of the placement bar (worse than the level, which is right). **Never add a confirmation bar** except in the explicitly labelled late-entry control cells (`entry_mode='close_confirm'` in spec 1, spec 8). Two-sided (OCO) cells are resolved on the 1-minute data before placement exactly as `strategies/orb.py` does: scan bars from `i1` while `tod < entry_cutoff`; the first level touched is the fill; both touched in one bar -> the side nearer that bar's open (the engine then stops it on the same bar: a conservative loss, never a skipped day). One-sided (ORBP) cells place only the allowed side; with `cancel_on_opposite=True` the order is cancelled (no trade that day) if the opposite level is touched first (Crabel's ORBP rule).

**Costs per micro, per round trip, already in the engine** (`backtest/contracts.py`): MES $2.50 slippage + $1.30 commission = $3.80 (0.76 pt); MNQ $1.00 + $1.30 = $2.30 (1.15 pt); MGC $2.00 + $1.30 = $3.30 (0.33 pt). **Stress run** `engine.run(..., slip_ticks=2)`. **Fetna floor (report 4.4)**: a cell is noise unless its mean *gross* P&L per trade is >= 1.5-2 ES pts (6-8 NQ pts, 0.5 GC pt) = roughly 2x the stress round trip; and the median initial stop must be >= 5x RT cost (>= 4 MES pts, >= 6 MNQ pts, >= 2 MGC pts), enforced by a `min_stop_pts` guard in every spec (a stop narrower than that is widened to it).

**Indicator definitions (exact; daily quantities for session d use days < d only)**:
- `D` = `daily_bars(df1, rth_only=True, rth=(rth_open, rth_close))` (one RTH bar per session; for gold the pit session). `H[d-1], L[d-1], O[d-1], C[d-1]` = that bar's values shifted one day. **`C[d-1]` must be the close of the last 1-min bar with `tod < rth_close`**, never the 16:14 feed-stop print (`daily_bars(rth_only=True)` already does this).
- `rng[d] = H[d-1] - L[d-1]`; `pd_mid[d] = (H[d-1] + L[d-1]) / 2`; `PDH = H[d-1]`, `PDL = L[d-1]`, `PDC = C[d-1]`.
- `ATR14d` = `daily_atr(df1, 14, rth_only=True, rth=(rth_open, rth_close))` (Wilder ATR of RTH daily bars, shifted). 2025-26 medians: SPX ~76 pts, NDX ~398 pts, GC pit ~69 pts. Every stop and cap is expressed in ATR fractions or in units of `rng`, never in fixed points.
- `noise[d'] = min(H[d'] - O[d'], O[d'] - L[d'])` (Crabel); `stretch[d] = mean(noise[d-10..d-1])` (10 full days required).
- `swing[d] = max(H[d-3] - L[d-1], H[d-1] - L[d-3])` (mql5 Part 6 dominant 3-day swing; report 1.2).
- `NR4[d]` = `rng` of day d-1 is the smallest of days d-4..d-1; `NR7[d]` over d-7..d-1; `ID[d]` = `H[d-1] < H[d-2] and L[d-1] > L[d-2]`; `ID_NR4 = ID and NR4`; `R2[d'] = max(H[d'], H[d'-1]) - min(L[d'], L[d'-1])`, `XBNR2[d]` = `R2[d-1] == min(R2[d-20..d-1])` (Crabel 2-bar NR, lookback 20); `WS[d]` = `rng[d] > 1.5 * ATR14d[d]` (Crabel wide-spread day; Oxford Strat D-rated as a setup).
- `mom10[d] = sign(C[d-1] - C[d-11])`; `SMA20[d]` = mean of `C[d-20..d-1]`.
- `gap[d] = O930[d] - PDC[d]`; `gap_atr = gap / ATR14d`.
- `VIX_lag` = `vix_lag1(df1)`; `pct252(x)[d]` = share of the readings `x[d-252..d-1]` that are `<= x[d-1]` (luxalgo convention; diagnostic buckets, never a grid parameter unless a spec says so).
- `B5` = `resample(df1, 5, rth_only=True, rth=(rth_open, rth_close))`; `ATR5(n)` = Wilder ATR on `B5` continuous across sessions.
- `R` = |entry - initial stop| in points; `$R = R x point_value`.
- `early_close[d]` from `session_info`.

**Lucid risk block** (default for every spec unless overridden; values per ONE micro contract; the Lucid Monte Carlo scales 5-40 micros):
- `max_trades_day = 1` for specs 1-5 (one attempt per instrument per day, the family's published rule) -> `daily_loss_stop` = one full stop (`max_stop_atr x ATR14d_median x point_value`, i.e. the engine's realized-only stop is inert and the hard stop does the work) and `daily_profit_stop` inert. Multi-trade specs (7) use `daily_loss_stop` MES $60 / MNQ $80 / MGC $80 and `daily_profit_stop` MES $120 / MNQ $160 / MGC $160 (grid multipliers `{1.0, 1.5}`).
- **Consistency arithmetic**: at the moment of passing a $3,000 eval no single day may exceed $1,500. With a hard target of `tgt_cap_atr = 0.4` ATR the per-micro largest day is ~MES $150 / MNQ $320 / MGC $280, so the Lucid scan will land at <= 10 MES, <= 4 MNQ, <= 5 MGC micros for the fast configuration; the `tgt_frac {0.3, 0.4}` and `tgt_cap_atr {0.3, 0.4}` cells exist to let the scan trade size for frequency. EOD-exit cells (`tgt_mode='eod'`, the published Williams / Holmberg / Kaufman rule) always carry `tgt_cap_atr` as a hard target in the eval phase (default 0.6 ATR; `none` only in the funded phase where no consistency rule applies).
- **Payout arithmetic**: 5 EOD days >= $150 at the funded size. Capped-target cells with 50-60% hit rates produce the most such days; EOD cells the fewest.
- Both daily stops only block NEW entries; every entry carries a hard protective stop. One position at a time; always `set_session(entry_start, entry_cutoff, flat)`.
- No event calendar in the data: news blackouts are NOT implemented. The 08:30 prints are outside every entry window here; the 10:00 and 14:00 prints are covered by the hard stop. The `gap_skip_atr` and overlay flags (spec 6) are the OHLC-only stand-ins.

**Benchmarks every cell must beat on 2025-01..2026-09**: `trend_momentum__benchmark_long_0945`, `orb_session__orb_bracket_control`, and spec 8 below. If spec 8 or spec 1's `close_confirm` cell shows PF > 1.2 on both periods, suspect an engine or look-ahead bug before believing any winner.

**Priority**: 5 = best prior of working under Lucid constraints with evidence, 1 = long shot / control. **Complexity**: 1 = a parameter on an existing module, 5 = multi-state intraday machine. EQ = the report's evidence-quality scale (1-5).

---

## 1. volatility_breakout__orbp_midpoint_capped  (one-sided Williams / Crabel volatility breakout: open +/- k x unit, prior-midpoint bias, wide-spread skip, 0.4x capped target; module `vb_orbp`)

Priority **4**, complexity **3**, instruments MNQ, MES, MGC; bar size: daily unit + 1-min execution. EQ 2 for the Williams rule as published (TradeSearcher: "cannot be told apart from chance"), 3 for the Crabel/ORBP machinery (Oxford Strat 36 years: trend/price-channel preference "improves the base ORB"), 3 for the conditioning statistics (open-vs-midpoint 67%/58% on NQ 2025; 0.4x median extension on 12 years of ES/NQ). Report sections 1.1-1.3, 2.1, 5.2, 7.6 (VB-1). This is the family's flagship: the **defaults are the published NanoTrader / WH SelfInvest rule** (two-sided, k = 0.25 of yesterday's range, bracket 2 x k-range both ways, time exit), and the grid is the report's conditioned version.

```
PARAMS (defaults = published NanoTrader rule):
  unit='range' | 'stretch' | 'swing', k=0.25 (range: 0.25-0.5; stretch: 1.0-2.0; swing: 0.25-0.4),
  sides='both' | 'long' | 'short', bias='none' | 'pd_mid' | 'mom10' | 'sma20' | 'down_close_long',
  stop_mode='frac' | 'open', stop_frac=0.5 (x base unit B, published = 2 x k x range = 0.5 x range),
  tgt_mode='frac' | 'eod', tgt_frac=0.5 (published; report cap 0.4), tgt_cap_atr=0.6 (hard target also in 'eod' mode; 0 = none),
  max_stop_atr=0.5, min_stop_pts (MES 4 / MNQ 6 / MGC 2), min_unit_atr=0.05, max_unit_atr=1.0,
  ws_skip=0.0 (0 = off; 1.5 = Crabel wide-spread skip), gap_skip_atr=0.0 (0 = off), atr_exhaust=0.0 (0 = off),
  entry_mode='stop' | 'close_confirm', entry_cutoff='11:30' (published 15:59 = 'eod'), cancel_on_opposite=True,
  buffer_ticks=1, flat='15:55' (MGC '13:25'), max_trades=1
PRE (per session d; D = daily RTH bars; everything shifted so d uses days < d):
  B[d] = {range: rng[d], stretch: stretch[d], swing: swing[d]}[unit]      # the base unit; k scales it
  U[d] = k * B[d]                                                        # breakout distance from the open
  atr = ATR14d[d]; require B, atr, pd_mid, mom10, SMA20 not NaN
  tradeable[d] = min_unit_atr*atr <= U <= max_unit_atr*atr
                 and (ws_skip == 0 or rng[d] <= ws_skip*atr)             # never after a wide-spread day (Crabel; Oxford D)
                 and (gap_skip_atr == 0 or |gap[d]| <= gap_skip_atr*atr)  # top-tercile-gap days whipsaw (Mesfin VVG)
                 and not early_close[d]
  O = O930[d]; i1 = i0[d] + 1
  up = O + U + buffer_ticks*tick;  dn = O - U - buffer_ticks*tick
  allowed = {+1, -1}
    bias 'pd_mid':          {+1} if O > pd_mid else {-1} if O < pd_mid else {}
    bias 'mom10':           {mom10[d]} (0 -> {})
    bias 'sma20':           {+1} if O > SMA20[d] else {-1}
    bias 'down_close_long': {+1} if C[d-1] < C[d-2] else {-1}            # Williams: prefer longs after a down close
  allowed &= {+1} if sides=='long' else {-1} if sides=='short' else allowed
ENTRY (entry_mode='stop'):
  resolve on 1-min bars k = i1, i1+1, ... while day[k]==d and tod[k] < entry_cutoff:
    if atr_exhaust > 0 and (max(high[i0..k-1]) - min(low[i0..k-1])) >= atr_exhaust*atr: cancel (session already used its ATR)
    hit_up = high[k] >= up; hit_dn = low[k] <= dn
    if hit_up and hit_dn: first = +1 if (up - open[k]) <= (open[k] - dn) else -1
    elif hit_up: first = +1; elif hit_dn: first = -1; else continue
    if first in allowed: fill side = first at bar k; break
    elif cancel_on_opposite: no trade today; break
    else: continue (wait for the allowed level; the opposite level is ignored)
  place(i1, side, entry_px=level(side), kind='stop', valid_bars=minutes(i1 -> entry_cutoff), stop_px, tgt_px)
  (the engine re-finds the same fill bar; valid_bars keeps the order dead after the cutoff)
ENTRY (entry_mode='close_confirm', late-entry CONTROL): first B5 bar with tod >= 09:35 and close beyond level(side);
  place(B5.i_next[k], side) market; same stop/target distances from the fill.  Expected to be worse than 'stop'
  (Mesfin: the move is consumed inside the signal bar); if it is better, suspect the fill model.
STOP:  'frac': stop_px = entry - side*stop_frac*B[d];  'open': stop_px = O  (distance U + buffer; the breakout failed)
       R = min(|entry - stop_px|, max_stop_atr*atr); R = max(R, min_stop_pts); stop_px = entry - side*R
TARGET: 'frac': tgt = entry + side*tgt_frac*B[d];  'eod': none
        if tgt_cap_atr > 0: tgt = entry + side*min(tgt_dist, tgt_cap_atr*atr)   (hard cap in both modes)
SESSION: set_session(tod(i1), entry_cutoff, flat); max_trades_day = 1
RISK: daily_loss_stop = max_stop_atr*median(atr)*point_value (one full stop halts the day); daily_profit_stop inert
OUTPUT per day (for diagnostics): unit B, U/atr, bias side, first level touched, fill minute, exit reason
```
Grid (<= 48): `bias {none, pd_mid, mom10}` x `(unit, k) {(range, 0.3), (range, 0.5), (stretch, 1.0), (stretch, 2.0)}` x `stop_mode {open, frac(0.5)}` x `tgt {frac(0.4), eod}`. Fixed: `ws_skip 1.5`, `entry_cutoff 11:30`, `max_stop_atr 0.4`, `tgt_cap_atr 0.6`, `cancel_on_opposite True`, `gap_skip_atr 0`, `atr_exhaust 0`. Single extra runs on the best cell: published defaults (control; `bias none, k 0.25, bracket 0.5/0.5, cutoff eod`), `unit swing k 0.3`, `bias sma20`, `bias down_close_long`, `entry_mode close_confirm` (control), `gap_skip_atr 1.0`, `atr_exhaust 1.0`, `cancel_on_opposite False`, `tgt_frac 0.3`.

Risk / Lucid: with `k 0.3` and `stop_mode open` the stop is ~0.3 x range (~20 ES pts = $100/MES, ~120 NQ pts = $240/MNQ) before the 0.4-ATR cap; the capped 0.4 x range target is ~$135/MES, ~$320/MNQ, so the scan sizes 4-10 MES / 3-4 MNQ micros. Expected (report 7.6): 40-55% win rate, PF 1.1-1.4 after costs *if* the conditioning works, 8-15 trades/month/instrument. `bias none` rows are the sibling two-sided cells and the control for the bias; `ws_skip 0` on the best cell is the control for the wide-spread rule.

## 2. volatility_breakout__compression_orbp  (spec 1 traded only after NR7 / ID-NR4 / 2-bar-NR days, with setup-extreme or open-stretch levels and a size tier; parameter set on module `vb_orbp`)

Priority **4**, complexity **2** (adds `setup_filter`, `level_mode`, `tier` to spec 1's module), instruments MNQ, MES, MGC; bar size daily setup + 1-min. EQ 3 for "compression precedes expansion" (edgeful 2025: inside day -> prior range broken 87.8% ES / 88.4% NQ; Oxford Strat NR7 / 2-bar-NR C-rated positive gross over 33-36 years; Crabel: ID-NR4 the highest-probability ORB setup), 2 for any day-trade P&L (rusty_trader intraday note: NR7 87% win but PF < 1 until a stop at the NR7 low is added). Report sections 2.2-2.4, 7.3, 7.6 (VB-2). Differs from `orb_session__nr_inside_day_orb` (filter on the close-confirmed ORB) and `trend_momentum__crabel_stretch_nr` (two-sided stretch) by the one-sided bias, the Connors-Raschke setup-extreme level, the 2-bar-NR and ID-NR4 setups, the WS negative control and the tier output.

```
PARAMS: everything in spec 1 plus
  setup_filter='nr7' | 'id_nr4' | 'xbnr2' | 'nr4_or_id' | 'id' | 'ws' (negative control) | 'none',
  level_mode='open_unit' (spec 1 levels) | 'pd_extreme' (Connors-Raschke: PDH + tick / PDL - tick),
  tgt_unit='rng' | 'atr', tgt_frac=0.4, stop_mode='frac' | 'open' | 'opposite' ('opposite' only with pd_extreme: the other
  setup-bar extreme, i.e. R = rng + 2 ticks), tier_setups=('id_nr4', 'xbnr2')
PRE: as spec 1, plus setup_ok[d] = {nr7: NR7[d], id_nr4: ID_NR4[d], xbnr2: XBNR2[d], nr4_or_id: NR4[d] or ID[d], id: ID[d],
     ws: WS[d], none: True}[setup_filter];  tradeable[d] &= setup_ok[d]
     if level_mode == 'pd_extreme': up = PDH + buffer; dn = PDL - buffer; and require PDL < O930 < PDH (open inside the
       setup bar; an open already outside = the expansion happened overnight -> skip, the orb_session 'outside open' finding)
     tier[d] = 2 if setup_filter in tier_setups and setup_ok[d] else 1          # written to the daily output, see RISK
ENTRY / resolution: as spec 1 (one-sided by bias, cancel_on_opposite, cutoff 11:30)
STOP:  'frac' / 'open' as spec 1;  'opposite': stop_px = PDL - buffer (long) / PDH + buffer (short); cap max_stop_atr; min_stop_pts
TARGET: tgt_unit 'rng': entry + side*tgt_frac*rng[d] (0.4 x a compressed range is small: ~0.2 ATR; cost share ~3-5%);
        'atr':  entry + side*tgt_frac*atr;  tgt_cap_atr applies
SESSION / RISK: as spec 1. The tier is NOT applied inside the engine (it runs one contract): the daily output carries
  tier[d] and the campaign tests 'tier' sizing by running the module twice (tier-1 days, tier-2 days) as two portfolio legs
  with micros 1x and 2x, or by extending backtest.lucid.simulate_eval's micros_schedule to take a per-day array (engine gap,
  see Notes). Until then tier is a diagnostic column.
```
Grid (<= 36): `setup_filter {nr7, id_nr4, xbnr2}` x `level_mode {open_unit(stretch 1.0), pd_extreme}` x `bias {pd_mid, none}` x `(tgt_unit, tgt_frac) {(rng, 0.4), (atr, 0.4)}` x `stop_mode {open|opposite (matched to level_mode), frac(0.5)}`... capped by fixing `stop_mode` = `open` for open_unit and `opposite` for pd_extreme -> 3 x 2 x 2 x 2 = 24, plus `setup_filter nr4_or_id` and `id` on the best cell, plus the `ws` control cell (must lose: Oxford Strat PF 0.74) and `none` (= spec 1 best cell, the frequency control).

Risk / Lucid: NR7 ~15-20% of days, ID ~12%, ID-NR4 ~5%, 2-bar-NR ~5-8% -> 3-5 setups/month/instrument; across MNQ + MES + MGC ~1 setup every 1-2 days. Both target and stop are small on compressed days ($75-200 per micro): the "many small green days" shape. A pure-compression leg is too slow for a fast eval; it is the safe leg and the overlay for spec 1.

## 3. volatility_breakout__inside_day_range_target  (inside day, open vs prior-day midpoint, trade from the open toward the prior extreme, stop at the midpoint; edgeful 2025)

Priority **4**, complexity **2**, instruments MNQ (published), MES, MGC; bar size daily setup + 1-min. EQ 2 (edgeful, NY session, 6 months to mid-2025, N 69-74: open above midpoint -> prior high reached 67%, below -> prior low 58%, range broken 87.8% ES / 88.4% NQ; no P&L, no costs) but consistent with the 11-year session-midpoint statistics in the ORB family. Report sections 2.4-2.5, 7.6 (VB-3). This is the family's best **shape** for Lucid: target and stop are both inside a compressed range ($100-300 per micro), the hit rate is high, and it is flat by close. It is NOT a breakout (the entry is at the open, before the expansion), so it is uncorrelated in timing with specs 1-2 and with the ORB family's 10:00-10:30 fills. Note: `orb_session__session_mid_bias_break` (overnight / London range + midpoint bias, `orb_onmid`) is DEAD on our data; this spec uses the **prior RTH day's** range and an inside-day setup, which is a different level set, and the `setup='any'` cell below is the test of whether that difference matters.

```
PARAMS: setup='id' | 'id_nr4' | 'nr4_or_id' | 'any' (control: every day), entry='market_0931' | 'close_above_open',
  stop_mode='mid' | 'frac', stop_frac=0.5 (x rng), tgt_ext=0.0 (target = prior extreme + tgt_ext*rng beyond it),
  require_inside_open=True, min_dist_atr=0.08, max_dist_atr=0.6, max_stop_atr=0.4, min_stop_pts,
  last_entry='10:30' (only for 'close_above_open'), time_stop='none' | '13:00', flat='15:55' (MGC '13:25'), max_trades=1
PRE (per session d): ID[d], NR4[d]; PDH, PDL, pd_mid, rng; atr; O = O930[d]; i1 = i0 + 1
  side = +1 if O > pd_mid else -1 if O < pd_mid else 0 (skip)
  level = PDH if side > 0 else PDL;  dist = |level - O|
  tradeable[d] = setup_ok[d] and side != 0 and (not require_inside_open or PDL < O < PDH)
                 and min_dist_atr*atr <= dist <= max_dist_atr*atr and atr, rng not NaN and not early_close[d]
ENTRY 'market_0931':      place(i1, side)   (market at the open of the 09:31 bar, +1 tick)
      'close_above_open': first 1-min bar k in [i1, last_entry) with close[k] > O (long) / < O (short) and
                          PDL < close[k] < PDH and |level - close[k]| >= min_dist_atr*atr: place(k+1, side) market
STOP:  'mid':  stop_px = pd_mid (R = |O - pd_mid| for the 09:31 entry, typically 0.1-0.3 x rng)
       'frac': stop_px = entry - side*stop_frac*rng
       R = min(R, max_stop_atr*atr); R = max(R, min_stop_pts)      # a 1-tick-from-mid open gets a floor stop, not no stop
TARGET: tgt_px = level + side*tgt_ext*rng   (tgt_ext 0 = the prior extreme; the engine needs a 1-tick trade-through, so
        our hit rate is slightly below the published 67/58% "touch" rate by construction)
TIME:  if time_stop != 'none': exit_at(index of the first bar >= time_stop, which=side);  flat at `flat`
SESSION: set_session(tod(i1), last_entry or tod(i1)+1 min, flat); max_trades_day = 1
RISK: daily_loss_stop = max_stop_atr*median(atr)*point_value; daily_profit_stop inert
DIAGNOSTIC: hit rate of `level` by side and by setup (must reproduce ~65%/55% on NQ 2025 for 'id'; if the raw
  statistic does not replicate on our data, stop here)
```
Grid (<= 32): `setup {id, nr4_or_id}` x `entry {market_0931, close_above_open}` x `stop_mode {mid, frac(0.5)}` x `tgt_ext {0.0, 0.25}` x `time_stop {none, 13:00}`. Fixed `require_inside_open True`, `max_stop_atr 0.4`. Extra runs on the best cell: `setup any` (control: the pure open-vs-midpoint statistic on every day), `setup id_nr4`, `require_inside_open False`, `sides long only` on MNQ.

Risk / Lucid: on an inside day `rng` is ~0.5-0.7 ATR, so a 'mid' stop is ~0.1-0.2 ATR (MNQ $80-160, MES $40-75) and the target 0.3-0.5 x rng (MNQ $120-280, MES $60-130): per-micro days of $100-300 with a ~60% hit rate is exactly the 5 x $150 payout profile. The scan should land at 6-12 micros. ~12% of days trade (ID) or ~30% (`nr4_or_id`): pair with spec 1 on the same contract is impossible in one module (one position per run), so run as separate legs in `backtest.portfolio` (different contracts) or merge later.

## 4. volatility_breakout__atr_close_breakout  (Kaufman-style ATR-unit breakout from the prior close, 0.33-ATR stop, one attempt, momentum direction; crackingmarkets blueprint)

Priority **3**, complexity **2**, instruments MES, MNQ, MGC; bar size daily ATR unit + 1-min. EQ 1-2 (Kaufman's textbook form is daily; the 2025 blog claims 3x expectancy with the narrow-day + trend filter and publishes no tables; StockSharp vendor number ignored). Report sections 1.5, 7.6 (VB-4). Worth running because it is the cheapest bounded-loss member (0.33 x ATR14 ~ 25 ES pts = $125/MES, ~130 NQ pts = $260/MNQ before the floor/cap) and because the level is anchored at the **prior close**, not the open, so it is the family's one test of whether the gap belongs inside or outside the breakout distance.

```
PARAMS (defaults = blueprint): k=0.33, stop_atr=0.33, tgt_mode='eod' (published) | 'atr', tgt_atr=0.5, tgt_cap_atr=0.6,
  direction='both' | 'mom10' | 'sma20', gap_mode='skip' | 'take', gap_tol_atr=0.25, nr_filter='none' | 'nr4' | 'nr4_or_id',
  ws_skip=1.5, entry_cutoff='11:30', cancel_on_opposite=True, min_stop_pts, buffer_ticks=1, flat='15:55' (MGC '13:25'), max_trades=1
PRE (per session d): PDC[d] (RTH close of d-1, never the feed-stop print); atr = ATR14d; O = O930; i1 = i0 + 1
  up = PDC + k*atr + buffer; dn = PDC - k*atr - buffer
  allowed = {+1,-1} ('both') | {mom10[d]} | {sign(O - SMA20[d])}
  tradeable[d] = atr not NaN and (ws_skip == 0 or rng[d] <= ws_skip*atr) and (nr_filter satisfied) and not early_close[d]
  GAP HANDLING (the open can already be beyond a close-anchored level):
    for each allowed side s with O beyond level(s):  gap_mode 'skip' -> drop side s today;
      'take' -> if |O - level(s)| <= gap_tol_atr*atr: place(i1, s) MARKET at the 09:31 open (the stop order would fill
      there anyway at max(open, level)); else drop side s (the move already happened: Mesfin VVG days)
ENTRY: one-sided / two-sided stop orders at up / dn from i1 until entry_cutoff, resolved as spec 1 (cancel_on_opposite)
STOP:  stop_px = entry - side*stop_atr*atr; R = max(stop_atr*atr, min_stop_pts)
TARGET: 'eod': none (published; flat at `flat`) + tgt_cap_atr hard cap in eval; 'atr': entry + side*tgt_atr*atr
SESSION: set_session(tod(i1), entry_cutoff, flat); max_trades_day = 1
RISK: daily_loss_stop = stop_atr*median(atr)*point_value
```
Grid (<= 32): `k {0.33, 0.5}` x `stop_atr {0.25, 0.33}` x `tgt {eod, atr(0.4), atr(0.5)}` x `direction {both, mom10}` = 24, plus `nr_filter nr4_or_id` and `gap_mode take` on the best cell, plus `direction sma20`. Fixed `ws_skip 1.5`, `cutoff 11:30`.

Risk / Lucid: the 0.33-ATR stop is the family's smallest fixed-fraction stop; with `tgt_atr 0.4-0.5` the reward:risk is 1.2-1.5 and the per-micro day is <= $200 MES / $400 MNQ (hence <= 7 MES / 3 MNQ micros under the consistency rule unless `tgt_cap_atr` is lowered). The `direction both` rows are the control for the momentum filter.

## 5. volatility_breakout__holmberg_quantile_threshold  (Holmberg-Lonnbark-Lundstrom 2013: open x (1 +/- rho), rho from the normal quantile of close/open log returns; rolling, with a stop and a 15:55 exit)

Priority **3**, complexity **2**, instruments MES, MNQ, MGC; bar size daily threshold + 1-min. EQ 4 for the published result (peer-reviewed, bootstrap-significant, 28 years of crude: 1% tail 61% winners +0.26%/trade; 0.1% tail 71%; 2001-2011 80% winners +0.52%) but **gross of costs, no stop, ex-post full-sample rho, crude only** (crude is unavailable 2024-26 so it cannot be replicated on its own market). Report section 1.4. The transfer: a rolling 250-day estimate (no look-ahead), the 2.5-10% tails for trade count, a capped stop, and the family's capped target as an alternative to the EOD exit. The paper's own finding that the edge lives in high-volatility regimes makes the VIX-percentile diagnostic mandatory.

```
PARAMS (defaults = paper where possible): alpha=0.01 (paper; grid 0.10/0.05/0.025), window=250, sides='both',
  tail_mode='directional' (paper: rho_up = mu + sd*q, rho_dn = -(mu - sd*q)) | 'symmetric' (rho = |mu| + sd*q both sides),
  stop_mode='open' (paper has none; our minimum) | 'atr', max_stop_atr=0.35, stop_atr=0.25, min_stop_pts,
  tgt_mode='eod' (paper) | 'atr', tgt_atr=0.4, tgt_cap_atr=0.6, entry_cutoff='15:00' (paper: any time) | '11:30',
  bias='none' | 'pd_mid', cancel_on_opposite=False (paper: both sides independent; we take the first touched), buffer_ticks=1,
  flat='15:55' (MGC '13:25'), max_trades=1
PRE (per session d): D = daily RTH bars; r[d'] = ln(C[d'] / O[d'])
  mu[d] = mean(r[d-window..d-1]); sd[d] = std(r[d-window..d-1]) (min_periods = window; NaN -> no trade)
  q = norm.ppf(1 - alpha)   (alpha 0.10 -> 1.2816; 0.05 -> 1.6449; 0.025 -> 1.9600; 0.01 -> 2.3263)
  rho_up = mu + sd*q;  rho_dn = sd*q - mu  (directional) | both = |mu| + sd*q (symmetric)
  O = O930[d]; up = O*(1 + rho_up) + buffer; dn = O*(1 - rho_dn) - buffer; i1 = i0 + 1
  tradeable[d] = rho not NaN and rho_up*O >= 0.15*atr (the threshold must clear noise) and not early_close[d]
ENTRY: stop orders at up / dn from i1 while tod < entry_cutoff; first touched wins (resolution as spec 1); bias as spec 1
STOP:  'open': stop_px = O, R = min(rho*O, max_stop_atr*atr)  (on ES a 1% threshold is ~60 pts, so the cap binds: R = 0.35 ATR);
       'atr': R = stop_atr*atr;  R = max(R, min_stop_pts)
TARGET: 'eod': none (paper) + tgt_cap_atr in eval;  'atr': entry + side*tgt_atr*atr
SESSION: set_session(tod(i1), entry_cutoff, flat); max_trades_day = 1
RISK: daily_loss_stop = max_stop_atr*median(atr)*point_value
DIAGNOSTIC (mandatory): P&L and hit rate by pct252(VIX_lag) bucket (<20, 20-80, >80) and by pct252(ATR14d/close);
  the paper predicts the edge sits in the top bucket. Also report the realised trigger frequency per alpha
  (ES: alpha 0.10 -> ~1.0% threshold -> expect 15-25% of days to touch it intraday).
```
Grid (<= 36): `alpha {0.10, 0.05, 0.025}` x `tgt {eod, atr(0.4)}` x `entry_cutoff {11:30, 15:00}` x `stop {open(cap 0.35), atr(0.25)}` = 24, plus the paper cell `alpha 0.01, eod, cutoff 15:00, stop open` (control, few trades), `tail_mode symmetric`, `bias pd_mid` on the best cell. Fixed `window 250`.

Risk / Lucid: the threshold is wide (0.8-1.3 ATR on ES at the 10-5% tails), so fills come late in the morning or in the afternoon (hence the 15:00 cutoff cell) and the EOD exit gives the family's fat-tailed day distribution: a strict `tgt_cap_atr` is needed in eval. Trade count 40-80/yr/instrument at alpha 0.10 and falls fast with the tail; this is a portfolio leg, not a stand-alone passer.

## 6. volatility_breakout__vol_regime_sizing_overlay  (infrastructure: per-session volatility flags for skip rules and contract sizing; consumed by every spec above and by the ORB / mean-reversion families)

Priority **3** (not a strategy; a prerequisite for the "volatility sets size, not permission" finding), complexity **2**, instruments all; bar size daily. EQ 3 (tradingstats 6,142 ES/NQ sessions: continuation and double-break rates within 1.8 pp across ATR regimes; Holmberg: edge scales with volatility against fixed costs; Zarattini replication: 76% of filtered P&L from 2022; Mesfin VVG: top-tercile gap / first-30-min days are distinct but sign-unstable). Report sections 4.2, 5.1, 5.3, 7.4.

```
vol_flags(df1, contract) -> DataFrame indexed by day_id (every column uses days < d; VIX via vix_lag1):
  atr        = ATR14d[d];  atr_pct = pct252(ATR14d / C)        # realised-vol percentile
  vix_lag, vix_pct = pct252(VIX_lag)
  range_ratio = rng[d] / atr;  ws = range_ratio > 1.5 (Crabel wide-spread);  nr_like = range_ratio < 0.7
  gap_atr = (O930 - PDC) / atr; gap_top = |gap_atr| >= rolling 252-day 66.7th percentile of |gap_atr| (shifted)
             (PRICE-ONLY approximation of Mesfin's VVG: the volume-deviation condition is dropped; FLAGGED)
  nr4, nr7, id, id_nr4, xbnr2 (definitions in 0);  wr7nr7_long = WR7-down on d-2 and NR7 on d-1 (Quantifiable Edges:
             next-day long bias; rare, diagnostic only)
  stop_atr_units(spec) -> size_mult[d] = clip(risk_budget / (stop_atr * atr * point_value), 1, cap)
             with risk_budget = $300-400 per day at the account level (so micros = floor(size_mult))
  skip[d] = ws[d] or (policy.gap_skip and gap_top[d]) or early_close[d]
apply(intents, flags, policy): intents.allow_entry[bars of day d] &= not skip[d]   (filter use works today)
  SIZING use: the engine runs one contract, so size_mult cannot be applied inside engine.run; it is applied in the Lucid
  layer. backtest.lucid.simulate_eval(micros_schedule=callable(day_in_eval, balance, mll, largest_day, total_profit))
  does not receive a per-day flag -> ENGINE GAP: extend it to accept an optional per-day multiplier array (micros[d] =
  base_micros * size_mult[d], capped by eval_max_micros / funded_scaling). Until then test sizing as two legs (high-vol
  days, normal days) in backtest.portfolio, or report the flat-size result and the bucketed diagnostic only.
Validation of the overlay itself (cheap, must run before it is trusted): bucket every base spec's per-trade P&L by
  atr_pct / vix_pct / range_ratio / gap_top; the family claim is that hit rates are FLAT across atr_pct buckets while
  $-per-trade rises with atr, and that ws days and gap_top days have lower PF. If hit rates move > 5 pp across buckets
  on 2015-2026 the "size not permission" rule is wrong for that spec and the bucket becomes an entry filter instead.
```
Grid (as a policy on the best cell of specs 1-4): `ws_skip {off, 1.5}` x `gap_skip {off, top-tercile, 1.0 ATR}` x `size_mode {flat, atr_budget}`. No parameters of its own are tuned.

Risk / Lucid: a daily risk budget of $300-400 is 15-20% of the $2,000 EOD-trailing distance; `atr_budget` sizing keeps the $-loss per day roughly constant across regimes, which is what the trailing drawdown needs. The percentile thresholds (<20 compression, >80 stress) are diagnostic buckets, not grid parameters.

## 7. volatility_breakout__intraday_compression_break  (intraday ATR-compression / Bollinger-inside-Keltner window, resting stops at the window extremes; folds TTM squeeze, BB-vs-ATR squeeze, ATR-channel compression and VCP)

Priority **2**, complexity **3**, instruments MNQ, MES; bar size 5-min RTH (grid 5 / 15). EQ 1 (no credible intraday futures evidence for any squeeze indicator; QS: Bollinger squeeze "doesn't do particularly well for any asset"; the NQ 60-min ATR-compression and FMZ pages were unreachable). Report sections 3.1-3.5, 7. Included once, as a single module with `compress_mode`, because the formulas are exact and cheap, and because it tests the family's structural claim on intraday bars: the compression window is real but the entry must be a **resting stop at the window extreme**, not a close outside a band (the Keltner 2-ATR close breakout is dropped for exactly that reason; `trend_momentum__squeeze_breakout` tests the close-fire version and is the comparison).

```
PARAMS: bar=5, compress_mode='atr_ratio' | 'bb_kc', atr_fast=14, atr_slow=100, ratio_max=0.7, bb_len=20, bb_k=2.0, kc_len=20,
  kc_mult=1.5, min_bars=6 (consecutive compressed bars), win=6 (window bars for the extremes), valid_minutes=60,
  stop_mode='window' | 'atr', stop_atr5=1.0, max_stop_atr=0.4, tgt_mode='window' | 'atr5', tgt_mult=1.0, tgt_atr5=1.5,
  tgt_cap_atr=0.6, min_stop_pts, entry_start='09:35', last_entry='14:00', flat='15:55', max_trades=2, direction='both' | 'sma20'
PRE on B = resample(df1, bar, rth_only=True, rth=(rth_open, rth_close)), continuous across sessions, min_periods full:
  'atr_ratio': comp[k] = atr(B, atr_fast)[k] / atr(B, atr_slow)[k] < ratio_max
  'bb_kc':     mid = sma(close, bb_len); sd = rolling std(close, bb_len); kc = ema(close, kc_len) +/- kc_mult*atr(B, kc_len)
               comp[k] = (mid + bb_k*sd < kc_up) and (mid - bb_k*sd > kc_dn)       # TTM squeeze ON
  run[k] = consecutive comp bars ending at k (reset at session start)
  setup[k] = comp[k] and run[k] >= min_bars and tod[k] in [entry_start, last_entry) and run[k-1] < min_bars  (first qualifying
             bar of each compression episode only; later bars extend the window silently)
  wh = max(high[k-win+1..k]); wl = min(low[k-win+1..k]); atr_d = ATR14d[d]; atr5 = atr(B, atr_fast)[k]
  skip if (wh - wl) < 0.05*atr_d or (wh - wl) > 0.5*atr_d
ENTRY: i = B.i_next[k]; up = wh + tick; dn = wl - tick; allowed by direction (sma20: sign(close[k] - SMA20[d]))
  OCO resolved on 1-min bars from i for valid_minutes (as spec 1); place(i, side, entry_px=level, kind='stop',
  valid_bars=valid_minutes, stop_px, tgt_px). An unfilled window expires; the next episode may set a new one.
STOP:  'window': the opposite window extreme (R = wh - wl + 2 ticks); 'atr': stop_atr5*atr5; cap max_stop_atr*atr_d; min_stop_pts
TARGET: 'window': entry + side*tgt_mult*(wh - wl); 'atr5': entry + side*tgt_atr5*atr5; tgt_cap_atr applies
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = 2; Lucid multi-trade risk block
```
Grid (<= 32): `compress_mode {atr_ratio, bb_kc}` x `bar {5, 15}` x `min_bars {4, 8}` x `(tgt_mode, mult) {(window, 1.0), (atr5, 1.5)}` x `stop_mode {window, atr(1.0)}`. Fixed `ratio_max 0.7`, `kc_mult 1.5`, `win 6`, `direction both` (one `sma20` run on the best cell).

Risk / Lucid: unknown edge; the report expects it to be no better than the daily NR/ID conditioning. Drop the module if PF < 1.1 on 2023-2026 in every cell; keep the compression flag as a diagnostic column for spec 1 (`squeeze_on_at_open`: was B5 compressed at 09:55?) which costs nothing.

## 8. volatility_breakout__expansion_bar_control  (NEGATIVE CONTROL: enter after a completed 5-min range-expansion bar in its direction; Mesfin 2026 falsified rule, RTH version)

Priority **1**, complexity **1**, instruments MNQ (published), MES; bar size 5-min RTH. EQ 4 as a negative (walk-forward, net of 2 pts, N 1,955: T = -11.52 at 1.5x / b+1; T = -4.86 at 1.5x / b+6; 2.5x / b+6 gross +1.06 net -0.94). Report section 4.1. The published test is the Asia session; we run the RTH analogue because that is where our other entries live. Purpose: calibrate the engine and the family's central claim. **It must lose after costs** (and the `b+1` cell must be the worst); a PF > 1.1 on both periods means the fill model, the bar alignment or the cost model is wrong, and every positive result in specs 1-7 is suspect until that is resolved.

```
PARAMS: bar=5, thresh=1.5 (x rolling mean range), avg_len=20, hold_bars=1 (b+1) | 6 (b+6), stop_atr5=1.0 (hard stop only;
  the paper has none), entry_start='09:35', last_entry='15:00', flat='15:55', max_trades=4
PRE on B5: range[k] = high - low; avg[k] = mean(range[k-avg_len..k-1]) (prior bars only; min_periods full)
  signal[k] = range[k] > thresh*avg[k] and close[k] != open[k]; side = sign(close[k] - open[k])
ENTRY: place(B5.i_next[k], side) market at the next 1-min open; max_hold = hold_bars*bar (1-min bars); stop_pts = stop_atr5*atr(B5,14)[k]
EXIT: max_hold (time) or the hard stop; flat 15:55. No target.
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = 4; no daily stops (control)
REPORT: gross and net pts/trade, T-stat, by year; also the paper's decomposition: mean (open[k] -> open[k+1]) vs
  (close[k] -> open[k+1]) move in the bar's direction, to confirm "the move is consumed inside the signal bar" on our data
```
Grid (<= 6): `thresh {1.5, 2.5}` x `hold_bars {1, 6}` plus `bar 15, thresh 1.5, hold 1`. No tuning.

---

## Dropped or folded (and why)

| Report item | Decision |
|---|---|
| 1.1 NanoTrader Williams defaults (k 0.25, 2x k-range bracket, 15:59 exit) | Folded as spec 1's **PARAMS defaults** (the published-rule control cell); 15:59 -> 15:55 for prop safety. |
| 1.2 mql5 Williams Parts 5/6/8 (gold daily, multi-day holds) | Multi-day holds violate no-overnight; the **swing-range unit** (Part 6) is spec 1 `unit='swing'`; the swing-low structure filter (Part 8) is dropped (long-only 2025 gold = beta; no day-trade evidence); 1-min crossover detection = our stop fill. |
| 1.3 rusty_trader VBO (SMA20 trend, 11:30 cutoff) / freqtrade LWBreakout | `bias='sma20'`, `entry_cutoff 11:30` in spec 1 (and `trend_momentum__williams_volbreak` `bias=sma20`); freqtrade's close-cross entry with 0.66/0.15 ATR(60) levels is a hyper-optimised crypto rule: dropped. |
| 1.4 Holmberg crude ORB | Spec 5 (rolling rho, ES/NQ/GC). Crude 2024-26 not in the data: the published market cannot be replicated. |
| 1.5 Kaufman / crackingmarkets ATR breakout | Spec 4. |
| 2.1 Crabel stretch ORB / ORBP | ORBP (one-sided, cancel on opposite, price-channel / momentum preference) is spec 1 `bias` + `cancel_on_opposite`; the two-sided base is `orb_session__crabel_stretch_volbreak` (same module, `bias none`). Crabel's "cancel if unfilled within 5-10 min" S&P ORB II rule is a cheap `valid_minutes` cell left to the loop. |
| 2.2 NR7 + stretch / NR7 + prior-range breakout | Spec 2 (`setup nr7`, `level_mode open_unit` / `pd_extreme`). |
| 2.3 2-bar NR | Spec 2 `setup xbnr2` + tier. |
| 2.4 ID/NR4 Connors-Raschke | Spec 2 `setup id_nr4`, `level_mode pd_extreme`, one-sided; the **stop-and-reverse clause is dropped** (two losses in one day on a trailing-drawdown account). |
| 2.5 Inside-day range target | Spec 3. |
| 2.6 WR7-down -> NR7 | Multi-day hold; kept only as the `wr7nr7_long` flag in spec 6 (diagnostic). |
| 3.1 TTM squeeze, 3.2 BB-vs-ATR squeeze, 3.4 ATR-channel compression, 3.5 VCP | One module, spec 7 (`compress_mode`), resting-stop entries. The close-fire TTM entry is `trend_momentum__squeeze_breakout`. |
| 3.3 Keltner 2-ATR close breakout | **Dropped**: a close 2 ATR from the mean is the late-entry pattern the family's own evidence rejects (Mesfin), no ES/NQ evidence, vendor only. Keltner 1.5-ATR survives as the squeeze reference in spec 7. |
| 3.6 HunterBreakOut NQ session bands | **Dropped**: undisclosed stop/target/period; as far as it is specified it is an opening range with volatility bands, which is the ORB family's spec 1 with an ATR-scaled buffer. |
| 4.1 Expansion-bar continuation | Spec 8 (negative control). |
| 4.2 VVG volatility-regime classifier | **Needs volume** (first-bar volume deviation). The two price conditions (|gap|, |first-30-min return| top tercile) are not a faithful classifier of the published 4.4%-of-days set, so it is NOT specced as a strategy; the |gap| tercile alone is the `gap_top` skip flag in spec 6 (flagged approximation), used for sizing/skipping only, which is also the report's recommendation. |
| 4.3 Mesfin RTH Confluence / London B | Volume features + fitted GMM; catalogued in the ml_statistical and evidence_and_failures spec files, not here. |
| 4.4 Fetna 225-cell cost study | Not a strategy; its floor is the validation criterion in section 0. |
| 5.1 ATR / VIX percentile regime | Spec 6 overlay (sizing and skip), never direction. |
| 5.2 Expansion-targeting statistics | Not a strategy; the 0.4x-range target default in specs 1-3 and the `tgt_cap_atr` convention. |
| 5.3 ATR exhaustion rule | Spec 1 `atr_exhaust` cancel (one extra run). |
| 6 QS Williams volatility channel (daily SPY, MR version) | Daily, multi-day, not intraday: dropped. |
| Williams trade-day-of-week filters, "first profitable open" exit | TDW filters are in-sample vendor filters (weekday P&L is reported in diagnostics only); the first-profitable-open exit holds overnight: dropped. |

## Validation protocol and notes for the backtest agents

- **Order of work**: spec 3 first (cheapest, best Lucid shape, and its raw hit-rate diagnostic tells us in one run whether the 2025 edgeful statistic exists on our data); then spec 1's grid on MNQ (the `bias none` rows double as the sibling two-sided cells, so run it once and share the CSV), then spec 2 on the best spec-1 cell; spec 8 in parallel as the control; specs 4 and 5 after; spec 6 is applied to whatever survives; spec 7 last.
- **Every cell**: MAIN 2025-01-01..2026-09-30 and PRIOR 2023-01-01..2024-12-31 with the same parameters; a cell counts only if PF >= 1.1 on PRIOR and its grid neighbours agree (plateau, not a spike); then `slip_ticks=2` stress, a `delay=1` sensitivity (place the resting order one 1-min bar later; a resting-stop strategy should be nearly indifferent, a market-entry cell that flips sign is a bar-boundary artefact), `backtest.walkforward` from 2019, and the Lucid Monte Carlo (`lucid_scan`, 5-40 micros) with `monthly_pass_rate` printed. The user's acceptance criterion is a **valid monthly pass rate**, not a positive point estimate.
- **Fetna floor**: discard any cell whose gross edge per trade is below ~1.5-2 ES pts / 6-8 NQ pts / 0.5 GC pt however good its net PF looks on a small N.
- **Family-specific checks**: (i) spec 8 and spec 1 `close_confirm` must lose; (ii) spec 2 `setup ws` must lose; (iii) spec 1 `bias none` vs `pd_mid` vs `mom10` on the same days is the test of "direction must be imported"; (iv) the overlay buckets must show flat hit rates and rising $/trade across ATR percentiles, or the sizing rule is replaced by a filter; (v) spec 5's VIX-bucket diagnostic must show the edge in the high-vol bucket as the paper predicts, or the transfer failed.
- **Engine gap to log**: per-day contract multipliers (spec 2 `tier`, spec 6 `size_mult`) cannot be applied inside `engine.run`; `backtest.lucid.simulate_eval.micros_schedule` needs an optional per-day array argument. Test via two portfolio legs until it exists.
- **Stacking**: specs 1/2 (fills ~09:35-11:30), 3 (09:31 entry) and 5 (fills to 15:00) collide on the same contract (one position per run); combine across contracts (MNQ spec 3 + MES spec 1 + MGC spec 2) in `backtest.portfolio` / `portfolio_opt`, or merge into one module with a priority order (spec 3's open entry first, spec 1's stop order only on non-ID days) once the single-leg results are known.
- **Two target configurations** (user request): "safe" = spec 3 and/or spec 2 at 5-8 micros with `daily_loss_stop` = one stop and the PRIOR PF >= 1.1 constraint (steady $100-300 days, 5 x $150 payout days in ~2-3 weeks); "fast" = spec 1 best cell at the consistency-limited size (<= 4 MNQ / <= 10 MES micros with `tgt_cap_atr 0.4-0.6`), which this family is NOT expected to win on its own: the report's own expectation is PF 1.1-1.4 and steady days, so the fast configuration should come from pairing with the ORB / mean-reversion legs. Report P(funded), days to funded, P(first payout) and expected net per evaluation for both from `backtest.campaign`.
