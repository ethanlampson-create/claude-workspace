# Specs: Opening range breakouts and session-structure strategies for the Lucid 50K LucidFlex backtest

Source report: `/home/user/claude-workspace/research/families/orb_session.md` (sections 1-8) and
`/home/user/claude-workspace/research/findings/orb_session.json` (24 catalogued strategies).
Engine contract: `/home/user/claude-workspace/docs/STRATEGY_GUIDE.md`, `backtest/engine.py` (`Intents.place / set_session /
exit_at`, `max_trades_day`, `daily_loss_stop`, `daily_profit_stop`), helpers in `strategies/common.py` (`opening_range`,
`overnight_range`, `daily_atr`, `prior_day_stats`, `session_info`, `sma`, `atr`, `vix_lag1`) and `backtest.data.resample(df1, N,
rth_only=True)` (gives `i_next`, the first 1-minute index after an N-minute bar closes).

**State of play in this family (read before running anything).** Five modules already exist and three have results:

| module | report section | status (per micro, MAIN 2025-01..2026-09 / PRIOR 2023-24) |
|---|---|---|
| `strategies/orb_close30.py` | 3.2 / 3.3 | **marginal**: MNQ, OR-15, 5-min close confirm, SMA200 trend bias, far stop capped 0.6 ATR, OR width 0.1-0.5 ATR, 0.75x target: PF 1.43 / 190 trades / Sharpe 1.64 / 69.5% positive days; PRIOR PF 1.08; 12-cell plateau. Lucid: 5 micros, pass 0.47, P(payout) 0.20, +$711/eval. MES, MGC, shorts, `direction=both` all dead. |
| `strategies/orb_sma_rr.py` | 3.1 | **marginal**: published 150-tick cap is dead now (0.09-0.11 ATR vs 0.14-0.16 when published); stop re-expressed as 0.15 x ATR14: MNQ PF 1.16 / 1.08, 312 trades, Sharpe 0.9, 40% positive days; in the neighbouring grid row (OR15 / 0.25 ATR / rr 2.0) 82 trades were flat-at-close carries (+$9.2k, 84% winners) -> a large part of the edge is trend-day carry, not the 2R target. Monthly pass rate 0.0-1.0 (not consistent). |
| `strategies/orb_onmid.py` | 5.1 / 5.2 | **dead**: the 70-75% first-break-direction statistic replicates on our NQ data, but the break is shallow (0.5x range reached only 40-48% of the time; midpoint revisited 53-57%). MNQ PF 0.84/0.83, MES 0.74/0.79 in all 32 cells; MGC positive only in 2025-26 (9 of 12 years negative). |
| `strategies/orb_reclaim.py` | 5.3 | grid in progress: MAIN 24 cells, median PF 0.97, best PF 1.08 (rr 2.0, 45 pts, am_pm, London only), 42% of cells profitable. |
| `strategies/orb_ib_c.py` | 4.1 | grid in progress (MES main/prior logs only). |

The specs below therefore (a) restate every codeable strategy in the family with complete rules so a fresh agent can implement
or re-implement it, (b) mark the existing module where one exists, and (c) put the untested, evidence-backed variants (not
re-runs of dead cells) in the grids. Priorities are posterior to those results, not just to the literature.

## 0. Conventions used by every spec below

Times: all **ET**. Data session 18:00 -> ~16:14 ET next day for the index CFD proxies (feed stops ~16:14), 18:00 -> 17:00 for
gold. RTH equities 09:30-16:00; gold pit 08:20-13:30 (gold trades ~23h). A 1-minute bar with `tod = T` covers `[T, T+1)`.
"5-min close at 10:00" means the close of the 5-min bar whose last 1-min bar has `tod = 09:59`; the decision uses that close and
the order is placed at `i_next` (the 1-min bar with `tod = 10:00`), i.e. **market at next open (+1 tick)** unless the spec says
stop/limit. `i_next == -1` (session ended) -> skip. Decisions never use the open of the bar the order is placed on, except where
a spec explicitly uses the 09:30 open `O930` and then places the order at the **09:31** bar (`i0 + 1`).

Forced flat: equities **15:55** (never later than 15:58); gold pit strategies **13:25**. No overnight, no weekends. Early-close
sessions (`session_info().early_close`) are skipped for entries after 12:00 and flattened by the engine at the last bar.

Instruments: MNQ (NSXUSD) first for every index spec (every result so far says MES is dead for ORB rules because the 0.5-1.0x
range targets in ES points are too small against fixed costs), MES second, MGC only where the spec says so.

Indicators (exact definitions):
- `ATR14d` = `daily_atr(df1, 14, rth_only=True, rth=(rth_open, rth_close))`: Wilder ATR of RTH daily bars, shifted one day
  (session d uses days < d). NaN -> no trade. 2025-26 medians: NDX ~398 pts, SPX ~76 pts, GC (pit) ~69 pts. Every stop and cap
  below is expressed in ATR fractions, never fixed points (the fixed 150-tick cap is what killed the published spec of 3.1).
- `OR(N)` = `opening_range(df1, rth_open, N)`: `or_high, or_low, or_open, or_close, i_end` over `[rth_open, rth_open+N)`;
  `rng = or_high - or_low`; `mid = (or_high + or_low)/2`. Valid only at indices > `i_end`.
- `B5` = `resample(df1, 5, rth_only=True, rth=(rth_open, rth_close))` 5-min bars; `B30` likewise with 30.
- `ON` = `overnight_range(df1, rth_open)`: 18:00 -> rth_open high/low; `LON` = high/low of bars with `tod in [02:00, 08:00)`
  (>= 200 bars required); both valid only after rth_open.
- `PDH / PDL / PDC` = prior RTH high/low/close (`prior_day_stats`, 1-day lag); `pd_rng = PDH - PDL`; `pd_mid = (PDH+PDL)/2`.
- `O930` = open of the first RTH bar; `gap = (O930 - PDC)/PDC`.
- `SMA_D(n)` = SMA of the cash-index daily closes (`data/parquet/{NDX,SPX,GC}_1d.parquet`) over the n rows strictly before the
  session (as `orb_close30.daily_trend`); `bias = +1 if close > SMA, -1 if below, NaN -> no trade`.
- `NR4[d]` = RTH range of day d-1 is the smallest of days d-4..d-1; `NR7` over 7; `ID[d]` = High(d-1) < High(d-2) and
  Low(d-1) > Low(d-2); `ID_NR4 = ID and NR4`.
- `noise[d] = min(High-Open, Open-Low)` of RTH day d; `stretch[d] = SMA(noise, 10) over days d-10..d-1` (Crabel).
- `VIX_lag` = `vix_lag1(df1)` (prior-day close); used only as a diagnostic bucket, never as a grid parameter, unless stated.
- `R` = |entry - initial stop| in points; `$R = R x point_value` (MNQ $2/pt, MES $5/pt, MGC $10/pt). Costs in the engine: $1.30
  RT + 1 tick slippage per side on market/stop fills (MNQ $2.30, MES $3.80, MGC $3.30 per round trip).

Lucid risk block (default for every spec unless overridden; values **per ONE micro contract**; the Lucid Monte Carlo scales 5-40):
- `daily_loss_stop` (no new entries once realized day P&L <= -X): MES $60, MNQ $80, MGC $80; for one-trade-per-day specs it is
  set to the maximum single stop so a full stop-out halts the day.
- `daily_profit_stop` (no new entries once realized day P&L >= Y): MES $120, MNQ $160, MGC $160. With `max_trades_day = 1` it is
  inert; it matters for the multi-trade specs (4, 7, 9).
- Both stops only block NEW entries; an open position runs to its own stop/target/flat. Every entry has a hard protective stop.
- Consistency arithmetic: at the moment of passing a $3,000 eval no single day may exceed $1,500. With 5-10 micros the per-micro
  largest day must stay <= $150-300: capped targets (0.5-1.0x range or <= 0.6 ATR) do this by construction; EOD-carry exits do
  not, so every EOD/trail exit mode below also carries an optional hard target `tgt_cap_atr` (default 0.6 ATR).
- Payout arithmetic: 5 days >= $150 at the funded size. High-win-rate capped-target specs (1, 6) produce the most such days;
  R-multiple specs (2, 9) the fewest.
- One position at a time, one pending order at a time; `set_session(entry_start, entry_end, flat)` on every spec.

Priority: 5 = best prior of working under Lucid constraints with evidence **and** our results, 1 = long shot / control.
Complexity: 1 = a parameter on an existing module, 5 = multi-state intraday machine.

Benchmarks every spec must beat on 2025-01..2026-09: `trend_momentum__benchmark_long_0945` (buy 09:45, flat 15:55) and the
family control spec 13 (`orb_session__orb_bracket_control`), which should lose after costs; if a control shows PF > 1.2 on both
periods, suspect an engine or look-ahead bug before believing any winner.

---

## 1. orb_session__orb_close_confirm_capped  (ORB-15/30, 5-min close confirmation, capped range target; existing module `orb_close30`)

Priority **4**, complexity **1** (module exists; the grid adds one new exit mode), instruments **MNQ** (MES/MGC dead on this
rule), bar size: N-min OR on 1-min data + 5-min confirmation bars. EQ 3 (tradingstats 2014-2026 continuation statistics; TTS /
edgeful vendor backtests) and our own MAIN PF 1.43 / PRIOR 1.08 on MNQ.

What is new versus the existing module: a break-even ratchet exit (`be_trail`), a noon time stop, and `last_entry 11:00`, the
three things the results README lists as "not tried"; everything else is the module as it stands.

```
PARAMS (defaults = published rule 3.2): or_minutes=30, confirm_bar=5, direction='both'|'long'|'trend', trend_len=200,
  stop_mode='opposite'|'mid', max_stop_atr=0.6, tgt_frac=0.5, min_range_atr=0.10, max_range_atr=0.8, last_entry='10:30',
  be_trail=False, time_stop=None|'12:00', flat='15:55', max_trades=1
  (best cell so far: or_minutes 15, direction trend, opposite, 0.6, tgt 0.75, max_range_atr 0.5)
PRE (per session d): OR = OR(or_minutes); atr = ATR14d[d]; rng, mid as in 0.
  tradeable[d] = atr notna AND min_range_atr*atr <= rng <= max_range_atr*atr
  allowed_side[d] = {+1,-1} if direction=='both'; {+1} if 'long'; {bias[d]} if 'trend' (SMA_D(trend_len); NaN -> none)
SIGNAL: scan B5 bars of day d with tod >= rth_open+or_minutes and tod < last_entry, in order:
  if bar.close > or_high: side=+1; break
  if bar.close < or_low:  side=-1; break
  (only the FIRST break of the day counts; if side not in allowed_side -> no trade today)
  skip if |bar.close - broken_level| > tgt_frac*rng   (already past the target distance)
  i = bar.i_next; if i == -1: skip
ENTRY: place(i, side)                                   # market at next 1-min open, +1 tick
STOP:  ref = bar.close
  opposite: stop_px = or_low (long) / or_high (short);  mid: stop_px = mid
  stop_px = clamp so that |ref - stop_px| <= max_stop_atr*atr
TARGET: tgt_px = ref + side*tgt_frac*rng
BE_TRAIL (new): trail_act_pts = 0.5*rng, trail_pts = 0.5*rng  -> once MFE >= 0.5 rng the stop ratchets to (extreme - 0.5 rng),
  i.e. never worse than break-even; the engine's trailing ratchet handles it (exit reason 3).
TIME_STOP (new): if time_stop: it.exit_at(index of first bar with tod >= time_stop, which=side)  (only acts if still open)
SESSION: set_session(rth_open + or_minutes, last_entry + 5 min, flat); max_trades_day = 1
RISK: daily_loss_stop = max_stop_atr*atr_median*point_value (= one full stop); daily_profit_stop inert (1 trade/day)
```
Grid (<= 48): `or_minutes {15, 30}`, `direction {long, trend}`, `tgt_frac {0.5, 0.75, 1.0}`, `max_range_atr {0.5, 0.8}`,
`be_trail {False, True}`. Fixed: stop_mode opposite, max_stop_atr 0.6, last_entry 10:30 (run one extra pair with 11:00 and
one with time_stop 12:00 on the best cell). Do NOT grid weekday or VIX (the vendor DOW filters are in-sample; our VIX 20-25
bucket is n=28).

Risk/Lucid: $R up to 0.6 ATR = ~240 NQ pts = $480/micro worst case (this is what pins sizing at 5 micros); `max_range_atr 0.5`
and `be_trail` are the two levers that shrink it. 1 trade/day at ~10:05-10:30, usually resolved within the hour -> stackable with
an afternoon leg on the same contract.

Evidence recap: 30-min OR close-confirmed continuation 70.7% ES / 71.5% NQ (2014-2026, stable by year); TTS NQ-15 long-only
74.6% win PF 2.51 (in-sample); our MNQ result above.

## 2. orb_session__orb_sma_bias_rmultiple  (ORB with daily SMA bias, ATR-scaled stop, R-multiple exit, one loss per session; existing module `orb_sma_rr`)

Priority **3**, complexity **1** (module exists), instruments **MNQ** (MES dead), bar size: 15/30-min OR on 1-min data. EQ 3
(Backtests-Not-Signals OOS 2023-02..2026-02 Sharpe 1.10 PF 1.32 on MNQ) but our replication of the published rule is dead
(PF 0.93) and only the ATR-scaled stop variant is positive (PF 1.16 / 1.08).

```
PARAMS (defaults = published rule 3.1): or_minutes=30, sma_len=200, rr=2.0, stop_cap_pts={MNQ:37.5, MES:10}, max_stop_atr=0.5,
  buffer_ticks=1, last_entry='12:00', min_range_atr=0.10, max_trades=1, reentry=False, flat='15:55'
  (chosen fix: or_minutes 15, stop_cap_pts=inf, max_stop_atr 0.15)
PRE: bias[d] = SMA_D(sma_len) sign (lagged cash-index close vs its SMA); OR = OR(or_minutes); atr = ATR14d; rng
  tradeable[d] = bias notna AND atr notna AND rng >= min_range_atr*atr
ENTRY: i0 = OR.i_end + 1; one stop order on the bias side only:
  long bias:  place(i0, +1, entry_px = or_high + buffer, kind='stop', valid_bars = minutes until last_entry)
  short bias: place(i0, -1, entry_px = or_low - buffer, kind='stop', valid_bars = ...)
  fill = max(open, level) + slip (engine)
STOP:  dist = min(rng, stop_cap_pts[contract], max_stop_atr*atr); stop_px = level - side*dist
TARGET: tgt_px = level + side*rr*dist
ONE-LOSS: max_trades_day = 1 (published). reentry=True: after any exit while tod < last_entry re-place the same order once
  (max_trades_day = 2) with daily_loss_stop = dist*point_value.
SESSION: set_session(rth_open + or_minutes, last_entry, flat)
```
Grid (<= 24): `or_minutes {15, 30}`, `max_stop_atr {0.15, 0.25}`, `rr {1.4, 2.0, 3.0}`, `sma_len {150, 200}`. Fixed:
stop_cap_pts = inf (the published cap is the identified flaw), last_entry 12:00, reentry False (tested: worse).

Risk/Lucid: $R = 0.15-0.25 ATR = 60-100 NQ pts = $120-200/micro; 25-40% win rate -> 5-8 consecutive losing trades are
routine; the monthly pass rate swung 0.0-1.0 at 5 micros. Only a portfolio leg; its distinct feature is trend-day carry
(flat-at-close winners), which spec 3 isolates.

## 3. orb_session__orb_long_carry  (ORB long, close-confirmed, timed / trailing / EOD carry; Mesfin 2026 + our carry diagnostic)

Priority **3**, complexity **2**, instruments **MNQ** (then MES), bar size: 15- or 25-min OR, 5-min confirmation. EQ 3-4 for the
direction of the effect (Mesfin walk-forward: ORB long hold-15-bars +2.4 / +7.0 / +15.1 pts net per trade in 2023/24/25, T=0.88,
shorts negative every year; our orb_sma_rr diagnostic on the OR15 / 0.25 ATR / rr 2.0 row: 82 flat-at-close carries +$9.2k, 84% winners), 2 for a tradable rule.

Why it is its own spec: specs 1 and 2 cap the winner (range target / 2R). This one keeps the capped-loss, close-confirmed entry
and lets the winner run by time, trail or EOD, with a hard `tgt_cap_atr` so one day cannot breach the consistency rule.

```
PARAMS: or_minutes=25, confirm_bar=5, direction='long'|'trend', trend_len=200, stop_atr=0.20, exit_mode='hold75'|'trail'|'eod',
  hold_minutes=75, trail_act_atr=0.20, trail_atr=0.30, tgt_cap_atr=0.6, last_entry='11:30', min_range_atr=0.10,
  max_range_atr=0.8, flat='15:55', max_trades=1
PRE: OR = OR(or_minutes); atr = ATR14d; rng; tradeable as spec 1; allowed_side = {+1} ('long') or {bias[d]} ('trend')
SIGNAL: first B5 bar after the OR with close > or_high (long) [close < or_low only if 'trend' and bias == -1]; tod < last_entry;
  the first break decides (a first break against allowed_side = no trade); i = bar.i_next
ENTRY: place(i, side, stop_pts = stop_atr*atr, tgt_pts = tgt_cap_atr*atr,
             max_hold = hold_minutes if exit_mode=='hold75' else 0,
             trail_pts = trail_atr*atr if exit_mode=='trail' else NaN, trail_act_pts = trail_act_atr*atr)
  (exit_mode 'eod': stop + cap target + flat only)
SESSION: set_session(rth_open + or_minutes, last_entry, flat); max_trades_day = 1
RISK: daily_loss_stop = stop_atr*atr_median*point_value
```
Grid (<= 24): `or_minutes {15, 25}`, `stop_atr {0.15, 0.25}`, `exit_mode {hold75, trail, eod}`, `direction {long, trend}`.
Fixed: tgt_cap_atr 0.6, trail 0.3/0.2, last_entry 11:30. Run a `tgt_cap_atr = none` cell on the best config funded-only
(no consistency rule there).

Risk/Lucid: $R 60-100 NQ pts ($120-200/micro); largest day capped at 0.6 ATR = ~$480/micro -> at 5 micros $2,400 > $1,500, so
the eval run needs `tgt_cap_atr 0.35` or 3 micros; the funded run can lift it. Expect 40-50% win, PF driven by a few trend
days -> count positive days and months, not just PF.

## 4. orb_session__orb_second_break  (failed first breakout, then opposite-side break; "double-break" reversal)

Priority **3**, complexity **3**, instruments **MNQ**, MES, bar size 15/30-min OR, 5-min decision bars. EQ 2-3 (tradingstats: on
double-break days the second break closes in its direction 63.9% (15m) / 67.9% ES, 72.2% NQ (30m); edgeful NQ 15-min second
break 57% win, +0.43R/trade; no independent P&L). Not yet implemented; the mirror image of spec 1 on the 40-60% of days where
the first break fails. Note `strategies/mr_ibfail.py` (mean-reversion family) fades a failed IB break back to the midpoint;
this spec waits for the opposite edge to break and trades continuation of the second break.

```
PARAMS: or_minutes=30, confirm_bar=5, stop_mode='extreme'|'mid', max_stop_atr=0.5, tgt_frac=0.5, deadline='12:00',
  direction='both'|'long' (long = second break UP only), min_range_atr=0.10, max_range_atr=0.8, flat='15:55', max_trades=1
PRE: OR, atr, rng, mid, tradeable as spec 1
STATE per day (B5 bars with tod >= rth_open+or_minutes, tod < deadline), state in {WAIT1, BROKEN, FAILED}:
  WAIT1:  if close > or_high: first=+1; E = high; state=BROKEN
          elif close < or_low: first=-1; E = low; state=BROKEN
  BROKEN: E = max(E, high) if first>0 else min(E, low)
          if (first>0 and close < or_high) or (first<0 and close > or_low): state=FAILED     # closed back inside
          elif (first>0 and close < or_low) or (first<0 and close > or_high): treat as FAILED+SECOND in one bar (fall through)
  FAILED: E is frozen (the failed extreme); second break:
          if first>0 and close < or_low: side=-1; fire
          if first<0 and close > or_high: side=+1; fire
          (a re-break of the FIRST side after failure is ignored: one setup per day)
  fire: if side not allowed by direction -> no trade; i = bar.i_next; ref = bar.close
        stop_px = E + side*(-1)*tick  ('extreme': one tick beyond the failed extreme)  |  mid  ('mid')
        clamp |ref - stop_px| <= max_stop_atr*atr;  tgt_px = ref + side*tgt_frac*rng
        place(i, side, stop_px, tgt_px)
SESSION: set_session(rth_open + or_minutes, deadline, flat); max_trades_day = 1
RISK: daily_loss_stop = max_stop_atr*atr_median*point_value
```
Grid (<= 32): `or_minutes {15, 30}`, `stop_mode {extreme, mid}`, `tgt_frac {0.5, 1.0}`, `deadline {12:00, 13:30}`,
`direction {both, long}`. Fixed max_stop_atr 0.5.

Risk/Lucid: 'extreme' stops are wide on 30-min ranges (E is often 0.3-0.5 rng beyond the edge) -> expect the 0.5 ATR clamp to
bind; 'mid' stops give ~1:1 at 0.5x target. Entries 10:30-12:30, so this leg can be stacked after spec 1 only if spec 1's
trade has closed (engine: one position per contract; implement as a combined module if both are kept).

## 5. orb_session__crabel_stretch_volbreak  (Crabel stretch ORB and Williams k x prior-range breakout, NR/ID setup filters)

Priority **3**, complexity **2**, instruments MNQ, MES, MGC, bar size: daily setup + 1-min execution. EQ 3 (Crabel 1990 tables
60-70% profitable-at-close after NR4/ID; OxfordStrat 42 futures 1980-2013 positive before costs, "deteriorated" with $50 RT;
no modern ES day-trade test). **Overlaps `trend_momentum__crabel_stretch_nr` and `trend_momentum__williams_volbreak`: implement
ONCE (this spec folds both into `stretch_mode`), register under one id, and do not re-run the other.**

```
PARAMS: stretch_mode='crabel'|'williams', mult=1.0 (crabel: 1.0 or 2.0; williams k: 0.25 or 0.5), lookback=10,
  setup_filter='none'|'nr4'|'nr7'|'id'|'id_nr4', entry_cutoff='10:30', exit_mode='eod'|'target', tgt_mult=2.0 (x S),
  max_stop_atr=0.5, buffer_ticks=1, flat='15:55', max_trades=1
PRE (per session d, all from days < d): S[d] = mult*stretch[d] ('crabel') or mult*(High[d-1]-Low[d-1]) ('williams');
  atr = ATR14d; setup_ok[d] = setup_filter condition (NR4/NR7/ID/ID_NR4 as in 0; 'none' = True)
  O = O930[d] (open of the 09:30 bar); i1 = index of the 09:31 bar (orders are placed here, never on the 09:30 bar)
  skip if S < 0.05*atr or S > 1.0*atr
ENTRY: two levels: up = O + S + buffer, dn = O - S - buffer. Resolve OCO on 1-min bars from i1 while tod < entry_cutoff (as
  strategies/orb.py: first level touched wins; both in one bar -> the side nearer that bar's open; that trade is then stopped
  on the same bar by the engine, conservative). place(i1, side, entry_px=level, kind='stop', valid_bars=minutes to cutoff)
STOP:  stop_px = the other level (dn for longs, up for shorts) = 2S away; clamp |level - stop_px| <= max_stop_atr*atr
TARGET: exit_mode 'eod': tgt_px = NaN (flat 15:55); 'target': tgt_px = level + side*tgt_mult*S
SESSION: set_session('09:31', entry_cutoff, flat); max_trades_day = 1
RISK: daily_loss_stop = min(2*S_median, max_stop_atr*atr_median)*point_value; for 'eod' add tgt_cap_atr 0.6 (hard target) in eval
```
Grid (<= 48): `stretch_mode x mult {crabel 1.0, crabel 2.0, williams 0.25, williams 0.5}`, `setup_filter {none, nr4, id}`,
`exit_mode {eod, target(2S)}`, `entry_cutoff {10:30, 11:30}`. Fixed lookback 10, max_stop_atr 0.5.

Risk/Lucid: stop = 2S (~0.4-0.6x daily range = $300-700 per ES) -> MNQ/MES micros only, clamp at 0.5 ATR; NR/ID filters cut
frequency to 15-25% of days (slow eval, consistency-friendly). `setup_filter none` cells are the control for the filter.

## 6. orb_session__nr_inside_day_orb  (spec 1 traded only after NR4 / NR7 / inside days; Crabel pattern filter on the close-confirmed ORB)

Priority **3**, complexity **1** (a `setup_filter` parameter on `orb_close30`), instruments **MNQ**, MES. EQ 2 (Crabel: NR7 /
ID/NR4 precede range expansion; edgeful: inside-day range breaks next day 87.8% ES / 88.4% NQ, 6-month sample; Zarattini:
intraday momentum after NR4 earns 22 bps/day t=5.1 vs 12 unconditional).

```
PARAMS: everything in spec 1 (best cell: or 15, trend, opposite, 0.6, 0.75, max_range_atr 0.5) plus
  setup_filter='nr4'|'nr7'|'id'|'id_nr4'|'any' ('any' = nr4 OR id), direction='long'|'trend'
PRE: setup_ok[d] from the daily RTH bars (definitions in 0, all lagged); tradeable[d] &= setup_ok[d]
Everything else identical to spec 1 (signal, entry, stop, target, session, risk).
```
Grid (<= 12): `setup_filter {nr4, nr7, id}`, `or_minutes {15, 30}`, `tgt_frac {0.75, 1.0}`. Compare each cell with the
unfiltered spec-1 cell on the same days' complement: the filter earns its place only if PF rises on BOTH periods AND the
expected net per evaluation does not fall (fewer trades = slower eval).

## 7. orb_session__fisher_acd  (Mark Fisher ACD: A-up/A-down with time confirmation, C-level failure reversal)

Priority **2**, complexity **3**, instruments MNQ, MES, (MGC with OR 08:20-08:50), bar size: 15-min OR, 1-min confirmation.
EQ 2 (book + practitioner; no public backtest). Distinct from spec 1 in two ways that are testable: the ATR-scaled buffer A
beyond the OR, and the TIME rule (price must hold beyond A for half the OR length) instead of a single 5-min close; plus the
C-reversal after a failed A.

```
PARAMS: or_minutes=15, a_frac=0.20 (A = a_frac*ATR14d), c_frac=0.35 (C = c_frac*ATR14d), confirm_minutes=8 (= ceil(or/2)),
  stop_mode='or_edge'|'a_level', max_stop_atr=0.5, exit_mode='eod'|'atr_target', tgt_atr=0.5, c_reversal=True,
  last_entry='12:00', flat='15:55', max_trades=2
PRE: OR = OR(or_minutes); atr; A_up = or_high + A; A_dn = or_low - A; C_up = or_high + C; C_dn = or_low - C
  skip day if rng > 0.8*atr or atr NaN
A-CONFIRM (1-min bars k from OR.i_end+1 while tod < last_entry, no position/pending):
  cnt_up = number of consecutive closes > A_up ending at k (reset to 0 on a close <= A_up); cnt_dn mirror
  if cnt_up >= confirm_minutes: side=+1; i = k+1; ref = close[k]
  elif cnt_dn >= confirm_minutes: side=-1; i = k+1; ref = close[k]
  ENTRY: place(i, side)                        # market next open
  STOP:  'or_edge': or_low (long) / or_high (short);  'a_level': A_up - 1 tick (long) / A_dn + 1 tick (short)
         clamp |ref - stop| <= max_stop_atr*atr
  TARGET: 'eod': none (+ tgt_cap_atr 0.6 in eval);  'atr_target': ref + side*tgt_atr*atr
C-REVERSAL (only if c_reversal and the day's A trade was long and exited on its stop, or an A-up confirmation was reached and
  then a close <= A_up occurred before entry): afterwards if a 1-min close <= C_dn while tod < last_entry: side=-1, market next
  open, stop = or_high + 1 tick (clamped), same exit_mode. Mirror for a failed A-down -> C-up long. One A trade and one C trade
  max per day (max_trades_day = 2).
SESSION: set_session(rth_open + or_minutes, last_entry, flat)
RISK: daily_loss_stop = max_stop_atr*atr_median*point_value (the C trade is only allowed if the day is not halted)
```
Grid (<= 16): `a_frac {0.2, 0.3}`, `stop_mode {or_edge, a_level}`, `exit_mode {eod, atr_target(0.5)}`, `c_reversal {on, off}`.
Fixed or 15, confirm 8 min, C = 0.35 ATR.

Risk/Lucid: 'a_level' stops are tight (A - small) -> many 1R losses but $R ~ 0.2 ATR = $160/micro; 'or_edge' stops ~0.4-0.6 ATR.
Few signals/day; EOD exits need the cap in eval.

## 8. orb_session__ib_c_confirm  (Initial Balance C-period confirmation / narrow-IB breakout; existing module `orb_ib_c`)

Priority **3**, complexity **1** (module exists; grid in progress), instruments MES, MNQ, bar size 60-min IB + 30-min C period.
EQ 3 for the base rates (tradingstats ES 2,686 / NQ 2,833 days 2015-2025: C-period close above IB high -> 100% extension 45.5%
ES vs 18.8% unconditional; narrow IB < 0.5 ATR: 98.7% break, 74.8% median extension; shallow < 25% retrace -> 93.8% continue),
no net P&L. Overlaps `trend_momentum__ib_cperiod_breakout` (same rule): one module, one set of runs.

```
PARAMS (module): mode='c_confirm'|'narrow_break', ib_minutes=60, c_minutes=30, ib_min_atr=0.2, ib_max_atr=1.5, narrow_only=False,
  narrow_atr=0.5, max_ext_entry=0.5, stop_mode='mid'|'atr', stop_atr=0.25, max_stop_atr=0.5, tgt_ext=0.5, retrace_exit=False,
  retrace_frac=0.5, buffer_ticks=1, last_entry=None, flat='15:55' (MGC 13:25), max_trades=1
PRE: IB = OR(ib_minutes) -> ib_high, ib_low, ib_rng, ib_mid; atr; skip if ib_rng < ib_min_atr*atr or > ib_max_atr*atr;
  if narrow_only: require ib_rng < narrow_atr*atr
c_confirm: C = the 30-min bar [10:30, 11:00). At its close (i_next = 11:00 bar):
  if C.close > ib_high and (C.close - ib_high) <= max_ext_entry*ib_rng: long; if C.close < ib_low mirror short; else no trade
  ENTRY market at i_next. STOP 'mid': ib_mid; 'atr': ref - side*stop_atr*atr; clamp max_stop_atr. TARGET ref + side*tgt_ext*ib_rng
narrow_break: from 10:30 (i = IB.i_end+1) stop orders at ib_high + buffer / ib_low - buffer (OCO resolved on 1-min bars as
  orb.py), valid until last_entry (12:00); stop/target as above measured from the level.
retrace_exit: after entry, if a 1-min close retraces more than retrace_frac*ib_rng back from the broken edge
  (long: close < ib_high - retrace_frac*ib_rng) -> exit_at(next bar, which=side).
SESSION: set_session('11:00' (c_confirm) / '10:30' (narrow_break), last_entry or '13:30', flat); max_trades_day = 1
RISK: daily_loss_stop = max_stop_atr*atr_median*point_value
```
Grid (module GRID, 32): `mode {c_confirm, narrow_break}`, `stop_mode {mid, atr}`, `tgt_ext {0.5, 1.0}`, `ib_max_atr {1.0, 1.5}`,
`narrow_only {False, True}`. Add `retrace_exit True` on the best cell only.

Risk/Lucid: ES IB width 0.5-1.0 ATR -> 'mid' stop = 0.25-0.5 ATR ($100-190/MES, $200-400/MNQ): 5-8 micros. Entry 11:00,
exposure to 15:55; ~0.3-0.4 trades/day (C closes inside the IB ~66% of days). Good "safe" leg candidate if PF > 1.2 holds.

## 9. orb_session__london_reclaim  (session-level sweep, 3-bar pullback swing, stop entry beyond the extreme, R-multiple target; existing module `orb_reclaim`)

Priority **2** (was 4 from the literature; our MAIN grid median PF 0.97, best 1.08), complexity **1** (module exists) / 4 to
re-implement, instruments MNQ (MES, MGC in module), bar size 1-min. EQ 3 (open-source repo 2019-2026, PF 1.26, Sharpe 1.44, DD
$2.1k at $100 risk, 1-tick slippage + commissions; single author).

```
PARAMS (module): london=('02:00','08:30'), windows='am_pm' ([09:30,11:00) and [13:30,15:30)), rr=3.5,
  max_stop_pts={MNQ:45, MES:12, MGC:9}, valid_minutes=60, max_trades=4, flat='15:55', use_pd_levels=True, pd_mode='rth',
  use_london=True
  NEW: max_stop_atr=None (when set, replaces max_stop_pts with max_stop_atr*ATR14d; 45 NQ pts was ~0.14 ATR in 2019-24 and is
  ~0.11 ATR in 2025-26, the same decay that killed the published cap in spec 2)
LEVELS per session: London high/low over [02:00, 08:30); PDH/PDL (prior RTH). High-type levels -> long setups, low-type -> short.
SETUP (long; short mirrored), 1-min bars inside a window:
  sweep: first bar with high >= level. X = running max high since the sweep bar.
  swing: at the close of bar j, swing low confirmed at j-1 if j-1 > sweep bar, low[j-1] <= low[j-2], low[j-1] < low[j], low[j-1] < X. S = low[j-1]
  order: at j+1 buy stop at X + 1 tick, stop_px = S - 1 tick, tgt_px = fill + rr*(X + tick - S + tick); skip if (X - S) > cap
         (cap = max_stop_pts or max_stop_atr*atr); valid_bars = valid_minutes or until window end; expired -> level re-arms on
         the next confirmed swing. One pending order / one position at a time; a level is traded once per day; a level swept in
         the AM window is skipped in the PM window.
SESSION: allow_entry only inside the windows; flat 15:55; max_trades_day = 4
RISK: daily_loss_stop = 2 x cap$ (two full losses halt the day); daily_profit_stop = Lucid block x1.5 (3.5R winners are the point)
```
Grid (<= 24): `rr {2.0, 3.5}`, `max_stop_atr {0.10, 0.15}` (replacing the point caps), `windows {am_only, am_pm}`,
`levels {london_only, london+pd}`, plus `rr 2.5` on the best two cells. Published cell (rr 3.5, 45 pts, am_pm, london+pd)
stays as PARAMS default.

Risk/Lucid: 32% win, avg win ~2.7x avg loss, up to 4 trades/day -> worst day ~4 x $R; at $R = 0.1 ATR (~$80/micro) that is
$320/micro. Slow eval (~190 trades/yr published); a portfolio leg at best unless the ATR-scaled cap restores PF >= 1.2.

## 10. orb_session__session_mid_bias_break  (overnight / London range breakout with midpoint bias; existing module `orb_onmid`, DEAD as published)

Priority **1**, complexity **2** (new entry/target modes on the module), instruments MGC (only instrument with any positive
cell), MNQ. EQ 3 for the directional statistic (76% / 83%) which replicates on our data (70-75%), 0 for the published breakout
rule (dead in all 32 cells on MNQ and MES both periods). Re-run ONLY with the untested variants below; every published cell is
already in `results/orb_onmid/`.

```
PARAMS (module defaults = published): levels='on'|'london', last_entry='11:00', exit_time='12:00', stop_mode='mid'|'frac(0.5)',
  max_stop_atr=0.4, tgt_frac=0.5, buffer_ticks=2, min_atr=0.25, max_atr=1.2, exhaust_frac=1.0, outside_mode='skip', gap_min=0,
  max_trades=1
  NEW: entry_mode='stop'|'close5' (close5 = first 5-min bar closing beyond the biased level, market at i_next, as spec 1),
       tgt_mode='frac'|'pd_level' (pd_level: target = PDH for longs / PDL for shorts if it lies 0.2-1.5x rng beyond the level,
       else skip), gap_min in {0, 0.0069} (large-gap days: 82-84% direction, 12.9% sweep), aln_filter=False|True
       (nqstats 'partial engulf': require the London range to partially engulf the Asia 20:00-02:00 range on the biased side)
PRE at rth_open: ON/LON high, low, mid, rng (bars strictly before rth_open); atr; bias = sign(O930 - mid); skip if none, if the
  biased level was already broken pre-session (london), if |O930 - level| > exhaust_frac*rng when O930 is beyond the level,
  or if |gap| < gap_min
ENTRY: 'stop': stop order at level +/- buffer at the 09:31 bar (i0+1), valid until last_entry;
       'close5': first B5 bar with close beyond the level (tod < last_entry) -> market at i_next
STOP: mid or frac(0.5)*rng from the level, clamp max_stop_atr. TARGET: tgt_frac*rng or pd_level. Exit at exit_time; flat 15:55.
SESSION: set_session(rth_open(+1), last_entry, exit_time); max_trades_day = 1
```
Grid (<= 16): `entry_mode {stop, close5}`, `gap_min {0, 0.0069}`, `tgt_mode {frac(0.5), pd_level}`, `levels {on, london}`.
Fixed stop mid, exit 12:00 for MGC / 15:55 for MNQ (the noon stop hurt every MNQ cell and helped MGC).

Risk/Lucid: as module. Kill it for good if no cell is PF >= 1.1 on both periods.

## 11. orb_session__pdh_pdl_break  (previous-day high/low breakout with close confirmation or retest entry; inside-day setup filter)

Priority **2**, complexity **3**, instruments MNQ, MES, MGC, bar size 1-min levels + 5-min confirmation. EQ 2 (edgeful: open
inside yesterday's range -> 75% test of PDH or PDL, above pd_mid -> PDH touched 67%; inside-day range breaks next day ~88%;
tradezella ES/NQ H1: retest entry lower win rate but higher expectancy than fading; both degrade on FOMC/NFP/CPI days).
Data gap: no event calendar in the repo -> `event_proxy` below approximates it from the 08:30 bar.

```
PARAMS: entry_mode='break_close'|'retest', open_filter='inside'|'any', bias_mode='pd_mid'|'none', setup_filter='none'|'inside_day',
  stop_atr=0.20, max_stop_atr=0.4, tgt_mode='pd_frac'|'atr', tgt_frac=0.5 (x pd_rng), tgt_atr=0.5, retest_valid=60,
  first_signal='09:35', last_entry='11:30', time_stop='13:00', flat='15:55', max_trades=1, event_proxy_atr=0.0 (0 = off)
PRE: PDH, PDL, PDC, pd_rng, pd_mid (lag 1); atr; O930
  open_ok = (open_filter=='any') or (PDL < O930 < PDH)            # outside opens revert into the range ~100% (ES): skip
  allowed = {+1,-1}; if bias_mode=='pd_mid': allowed = {+1} if O930 > pd_mid else {-1}
  if setup_filter=='inside_day': require ID[d]
  event_proxy: if event_proxy_atr > 0 and (high-low of the 08:30 1-min bar) > event_proxy_atr*atr: skip the day (8:30 prints)
SIGNAL: first B5 bar with tod in [first_signal, last_entry) whose close > PDH (long) / < PDL (short); first break only;
  side must be in allowed; ref = bar.close; i = bar.i_next; skip if |ref - level| > 0.5*tgt distance
ENTRY: 'break_close': place(i, side)  (market)
       'retest':     place(i, side, entry_px = level + side*tick, kind='limit', valid_bars = retest_valid)  (fills only if
                      price trades back through the level by one tick; unfilled -> no trade)
STOP:  stop_px = entry_ref - side*stop_atr*atr (entry_ref = ref for market, level for retest); clamp max_stop_atr
TARGET: 'pd_frac': level + side*tgt_frac*pd_rng; 'atr': entry_ref + side*tgt_atr*atr
TIME_STOP: exit_at(first bar >= time_stop, which=side); flat 15:55
SESSION: set_session(first_signal, last_entry + retest_valid for 'retest', flat); max_trades_day = 1
RISK: daily_loss_stop = stop_atr*atr_median*point_value
```
Grid (<= 32): `entry_mode {break_close, retest}`, `stop_atr {0.15, 0.25}`, `tgt_frac {0.25, 0.5}`, `bias_mode {pd_mid, none}`,
`setup_filter {none, inside_day}`. Fixed open_filter inside, time_stop 13:00, event_proxy off (one extra run with 0.3 on the
best cell).

Risk/Lucid: $R 60-100 NQ pts; 'retest' cuts trade count ~40% but enters at the level (no slippage on limit fills in the engine:
do not over-trust the retest cell by more than ~1 tick/side).

## 12. orb_session__gold_pit_orb_newhigh  (gold 08:20 opening range, long-only new-session-high breakout, day-only adaptation of the relaxedtrader rule)

Priority **1**, complexity **2**, instrument **MGC**, bar size 30-min OR from 08:20 + 1-min. EQ 2 for the vendor's overnight
version (2001-2026, PF 1.69, 57% win, but avg hold 1.5 days: not allowed), 0 for a day-only version; `orb_close30` on MGC was
dead in all 8 cells (PF 0.68-0.84 MAIN) and `orb_onmid` MGC made all its MAIN money in 08:20-09:00 entries and lost in 9 of
12 years. Overlaps `trend_momentum__gold_donchian_intraday` (long-only Donchian on 15-min gold): run this one only if that spec
is positive, as its session-anchored variant.

```
PARAMS: or_minutes=30 (08:20-08:50), level_mode='session_high'|'or_high', thr_atr=0.05, stop_atr=0.25, exit_mode='flat'|'trail',
  trail_atr=0.30, trail_act_atr=0.20, tgt_cap_atr=0.6, last_entry='11:00', flat='13:25', max_trades=1, trend_len=50
PRE: OR = OR(30) from 08:20; H_sess = max(ON high (18:00->08:20), or_high) ('session_high') or or_high ('or_high'); atr (pit ATR);
  bias: GC daily close > SMA_D(trend_len) required (long only)
ENTRY: at i = OR.i_end+1 place(i, +1, entry_px = H_sess + thr_atr*atr, kind='stop', valid_bars = minutes to last_entry)
STOP: stop_pts = stop_atr*atr. EXIT: 'flat': tgt_pts = tgt_cap_atr*atr, flat 13:25; 'trail': trail_pts/act as params + cap
SESSION: set_session('08:50', last_entry, '13:25'); max_trades_day = 1; daily_loss_stop = stop_atr*atr_median*10
```
Grid (<= 16): `level_mode {session_high, or_high}`, `stop_atr {0.2, 0.3}`, `exit_mode {flat, trail}`, `trend_len {50, 200}`.

## 13. orb_session__orb_bracket_control  (negative controls: Zarattini first-candle 10R/EOD, TORB no-stop, symmetric 1:1 bracket, insigtrade 1.5x/0.75x)

Priority **1**, complexity **1**, instruments MNQ, MES (MGC optional), bar size 5/30-min OR on 1-min. EQ 4 that these LOSE after
costs on index futures (mql5 2015-2026 five indices net ~0; TradingView 18-yr NQ PF 0.87, last year 0.63; Mesfin ORB shorts
negative every year). Purpose: calibrate the engine and the agents. If any control is PF > 1.2 on both periods, look for a
look-ahead or fill bug before trusting specs 1-12.

```
PARAMS: variant='zarattini'|'zarattini_atr'|'torb'|'bracket11'|'insig', flat='15:55', max_trades=1 (bracket11: 2)
zarattini:     OR(5). At i = OR.i_end+1 (09:35): side = sign(or_close - or_open) (0 -> no trade); place(i, side,
               stop_px = or_low (long)/or_high (short), tgt_px = ref + side*10*R); flat 15:55.
zarattini_atr: same entry; stop_pts = 0.05*ATR14d; no target (flat 15:55).
torb:          OR(5); stop orders at or_high + tick / or_low - tick from 09:35, OCO as orb.py, valid to 12:00; NO protective
               stop in the published rule -> for the engine use stop_pts = 1.0*ATR14d (effectively none intraday); flat 15:55.
bracket11:     OR(30) on 15-min bars; first 15-min bar closing beyond the range in 10:00-15:00 -> market at i_next;
               stop_pts = tgt_pts = 0.5*rng (symmetric); one long and one short attempt per day (max_trades_day 2); flat 15:55.
insig:         OR(30); stop orders at or_high/or_low (OCO), stop = 0.75*rng, target = 1.5*rng, exit 15:45.
SESSION: set_session('09:35' or '10:00', '12:00' or '15:00', flat)
```
Grid: `variant {5 values}` x `direction {both, long}` = 10 runs, each on MAIN and PRIOR. No tuning. Also run spec 1 with
`or_minutes=5, tgt_frac 0.5, stop opposite` once (the edgeful ORB-5 cell) and report it here.

---

## Dropped or folded (and why)

| Report section | Decision |
|---|---|
| 1.2 Zarattini-Barbon-Aziz 2024 stocks-in-play ORB | Needs **volume** (relative volume) and single-stock data; the unfiltered base case is Sharpe 0.48. Not reproducible; the "in play" proxy (OR width vs ATR, gap size) is already a parameter in specs 1, 10. |
| 1.1 / 1.3 Zarattini 2023 and TORB | Not candidates (20-24% win, 10R/EOD tails, net ~0 after futures costs); kept only as `variant` cells of control spec 13. |
| 3.4 edgeful ORB-5 ES, 3.5 insigtrade, 3.6 Winning-Day ORB, 3.10 orbsetups | Parameter cells of specs 1 / 13 (`or_minutes=5`, `insig`, `bracket11`); orbsetups is equities-only cross-check. |
| 3.7 Capstone NQ Open Range | Proprietary rules, DD $4.5k per MNQ; not codeable. |
| 3.9 ORB break-and-retest INTO the opening range | EQ 1; Mesfin: pullback entries 80.7% stop-out; `orb_onmid` `outside_mode=pullback` was worse in every cell. Retest entries survive only on levels OUTSIDE the OR (spec 9 swing-retest, spec 11 `entry_mode=retest`). |
| 4.2 thinkorswim FirstHourBreakout | Overnight-**volume** filter unavailable; with the filter off it is spec 8 `narrow_break` without the narrow filter (a spec-8 cell). |
| 5.4 Asia session range | EQ 1-2, Mesfin: Asia range-expansion negative; folded as the `aln_filter` flag in spec 10. |
| 5.5 Mesfin London Session Signal B | Needs **volume** z-score + fitted GMM and trades 03:00-08:30 (before our 09:30 session). Catalogued only. |
| 6.3 CL pit-open ORB | `WTIUSD_1m` has no bars for 2024-2025 (prime window): untestable. Gold version is spec 12. |
| 2.3 Larry Williams volatility breakout | Folded into spec 5 as `stretch_mode='williams'` (same machinery as Crabel). |
| Day-of-week filters (TTS Mon/Thu, edgeful Tue, tradingstats Mon/Fri) | Not specced anywhere: in-sample vendor filters; our weekday P&L is noise-level. Report by weekday in diagnostics only. |

## Notes for the backtest agents

- Order of work given the results so far: spec 1 grid extension (be_trail / time stop) and spec 6 (NR/ID filter on the same
  module) first, because they are one-parameter changes to the only positive module; then spec 3 (isolates the carry effect that
  showed up in spec 2's flat-at-close trades) and spec 4 (trades the days spec 1 fails); spec 8 when its grid finishes; spec 9
  only with the ATR-scaled cap; specs 5, 7, 11 as new modules; specs 10, 12, 13 last.
- Every spec: MAIN 2025-01-01..2026-09-30 and PRIOR 2023-01-01..2024-12-31 with the same parameters; a cell counts only if PF >= 1.1
  on PRIOR and the neighbours in the grid agree (plateau). Then `backtest.walkforward` from 2019 and the Lucid Monte Carlo
  (`lucid_scan`, 5-40 micros) with the `monthly_pass_rate` printed: the user's acceptance criterion is a valid MONTHLY pass rate,
  which spec 2 failed (0.0-1.0) even with a positive PF.
- Stacking: specs 1/6 (one trade ~10:05-10:30), 4 (10:30-12:30), 8 (11:00) and 9 PM window (13:30-15:30) are time-disjoint on
  the same contract only if the earlier trade has closed; the engine holds one position per run, so a combined module or the
  portfolio runner on different contracts (MNQ + MES + MGC legs) is the way to add them.
- Sizing arithmetic for the two target configurations: "fast eval" = 8-10 micros of the spec-1 cell with `max_range_atr 0.5`
  (largest day ~$400/micro -> under $1,500 at <= 3 micros only if `be_trail` lowers the worst day; otherwise cap at 5);
  "safe" = 5 micros with `daily_loss_stop` at one stop and the 2023-24 PF >= 1.1 constraint. Report P(funded), days to funded,
  P(first payout) and expected net per evaluation for both from `backtest.campaign`.
