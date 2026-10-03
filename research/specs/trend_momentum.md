# Specs: Trend-following and momentum (intraday + daily bias) for the Lucid 50K LucidFlex backtest

Source report: `/home/user/claude-workspace/research/families/trend_momentum.md` (no `findings/trend_momentum.json` existed at spec time).
Engine contract: `/home/user/claude-workspace/docs/STRATEGY_GUIDE.md`, `backtest/engine.py` (`Intents.place / set_session / exit_at`, `max_trades_day`, `daily_loss_stop`, `daily_profit_stop`), helpers in `strategies/common.py` (`opening_range`, `daily_atr`, `daily_bars`, `prior_day_stats`, `session_vwap` (TWAP proxy), `adx`, `ema`, `sma`, `atr`, `vix_lag1`, `session_info`), `backtest.data.resample(df1, N, rth_only=True)`.

## 0. Conventions used by every spec below

Times: all **ET**. Data session 18:00 -> 17:00 (equity CFD feed stops ~16:14). RTH equities 09:30-16:00; gold pit 08:20-13:30 (gold trades ~23h). A 1-minute bar with `tod = T` covers `[T, T+1)`. "Close at 10:00" means the close of the bar with `tod = 09:59`; the decision is taken with that information and the order is placed at the bar with `tod = 10:00` (`i_next`), i.e. **market at next open** unless the spec says stop/limit. On N-minute bars (`resample`) decisions use the N-bar close and the order index is `i_next` (skip `-1`).

Forced flat: equities **15:55** (never later than 15:58); gold pit strategies 13:25, gold full-session strategies 16:30 (never later than 16:45). No overnight, no weekends (the data has no Saturday sessions).

Indicators (exact definitions):
- `ATR14d` = `daily_atr(df1, 14, rth_only=True)`: Wilder ATR of RTH daily bars, shifted one day (day d uses days < d). Rows with NaN ATR never trade.
- `prev_close` = prior session RTH close (`daily_bars(rth_only=True).close.shift(1)`); `pd_high / pd_low` = prior RTH high/low (`prior_day_stats`).
- `O930` = open of the first RTH bar of the session (`daily_bars(rth_only=True).open`).
- `SMA_D(n)` = simple MA of RTH daily closes over the n sessions **before** d (`sma(close, n).shift(1)`).
- `TWAP` = `session_vwap(df1_rth)` = cumulative mean of typical price (H+L+C)/3 from 09:30; it is an **approximation of VWAP** (equal-weighted, no volume) and is flagged as such wherever used.
- `NR4[d]` = RTH range of day d-1 is the smallest of days d-4..d-1; `NR7` likewise over 7; `ID[d]` = High(d-1) < High(d-2) and Low(d-1) > Low(d-2).
- `VIX_lag` = `vix_lag1(df1)` (prior-day VIX close).
- `R` = |entry - initial stop| in points; `$R = R x point_value`.

Lucid risk block (default for every spec unless overridden; all values are **per ONE micro contract**, the Lucid Monte Carlo scales 5-40 micros):
- `daily_loss_stop` (halts new entries once realized day P&L <= -X): MES $60, MNQ $80, MGC $80. Grid multiplier `{1.0, 1.5}`. At 10 micros this is a $600-$1,200 daily loss, <= 60% of the $2,000 MLL distance, so one bad day cannot breach an EOD-trailing MLL that started the day >= $1,200 above balance.
- `daily_profit_stop` (halts new entries once realized day P&L >= Y): MES $120, MNQ $160, MGC $160. Grid multiplier `{1.0, 1.5, none}`. At 10 micros this caps a day at ~$1,200-$1,800 so that no single day exceeds 50% of the $3,000 target (consistency rule) and so a funded cycle collects many >= $150 days rather than one big one.
- Engine semantics note: both stops only prevent NEW entries; an open position still runs to its own stop/target/flat. Hard protective stops are therefore mandatory on every entry (never a stop-less position in a prop account).
- One position at a time; `max_trades_day` as specified; always `set_session(entry_start, entry_end, flat)`.

Evidence-quality (EQ) and priority: priority 5 = best prior under Lucid constraints with evidence, 1 = long shot. Complexity 1 = a few lines on existing helpers, 5 = multi-state intraday machine.

Benchmark every spec must beat on 2025-01..2026-09: `trend_momentum__benchmark_long_0945` (buy 09:45, flat 15:55), because the prime window is a long-biased tape (ES study: +$2.3k..$22.7k/contract).

---

## 1. trend_momentum__noise_area  (Zarattini-Barbon-Aziz intraday momentum, semi-hourly bands)

Priority **4**, complexity **4**, instruments MNQ (best per Quantitativo), MES; bar size: 1-min data, decisions every 30 min. EQ 4 (peer-reviewed + 2 independent replications), but documented decay (Sharpe ~0 in 2025-26 on SPY/ES) -> regime filter is part of the grid.

Data gap: the paper's VWAP trailing stop needs volume. `stop_mode='twap'` uses the TWAP proxy (flagged approximation); `stop_mode='opp_band'` is the paper's base variant and needs no volume.

```
PARAMS (defaults = paper): lookback=14 days, vm=1.0, step=30 min, first_decision='10:00', last_decision='15:30',
  stop_mode='opp_band' | 'own_band_twap', hard_stop_atr=0.5, regime='none' | 'vix' | 'nr4', vix_min=18,
  long_only=False, flat='15:55', max_trades=6
PRE (per session d, RTH 1-min bars only):
  D = daily_bars(df1, rth_only=True); O930[d] = D.open; prev_close[d] = D.close.shift(1); atr[d] = ATR14d
  move[d, t] = | close(bar tod t) / O930[d] - 1 |          for every RTH tod t in 09:30..15:59
  M = pivot(move) -> rows = day_id, cols = tod
  sigma[d, t] = M.rolling(lookback, min_periods=lookback).mean().shift(1)   # days d-1..d-lookback only
  upper[d, t] = max(O930[d], prev_close[d]) * (1 + vm * sigma[d, t])
  lower[d, t] = min(O930[d], prev_close[d]) * (1 - vm * sigma[d, t])
  twap[d, t]  = session_vwap(rth bars)  (TWAP proxy)                          # only for stop_mode='own_band_twap'
  allowed[d]  = sigma not NaN AND atr not NaN AND
                (regime=='none' OR (regime=='vix' AND VIX_lag[d] >= vix_min) OR (regime=='nr4' AND NR4[d]))
STATE MACHINE per session d, pos in {0,+1,-1}, evaluated at decision times T = 10:00, 10:30, ..., 15:30:
  c = close of bar tod T-1;  i = index of bar tod T (market at its open); U = upper[d, T-1]; L = lower[d, T-1]
  if pos == 0:
     if c > U:             pos=+1; place(i, +1, stop_px = c - hard_stop_atr*atr[d])    # hard $ stop checked every 1-min bar
     elif c < L and not long_only: pos=-1; place(i, -1, stop_px = c + hard_stop_atr*atr[d])
  elif pos == +1:
     stop_level = L                              if stop_mode=='opp_band'
                = max(U, twap[d, T-1])           if stop_mode=='own_band_twap'
     if c < stop_level: exit_at(i); pos = 0
        if stop_mode=='opp_band' and c < L and not long_only: place(i+1, -1, stop_px = c + hard_stop_atr*atr[d]); pos=-1   # reverse one bar later (engine: one position at a time)
  elif pos == -1: mirror (stop_level = U for opp_band; min(L, twap) for own_band_twap; reverse to long if c > U)
  if the 1-min hard stop fires between decisions the engine flattens; the next decision sees pos==0 again (re-entry allowed).
SESSION: set_session('10:00', '15:31', flat); max_trades_day = max_trades; Lucid risk block.
```
Grid (<= 48 combos): `lookback {14, 90}`, `vm {1.0, 1.5}`, `stop_mode {opp_band, own_band_twap}`, `regime {none, vix, nr4}`, `hard_stop_atr {0.35, 0.6}`. Fixed: step 30, long_only False (add a `long_only=True` run on MNQ only).

Risk: per-trade hard stop 0.35-0.6 ATR (ES ~25-50 pts = $125-250/MES, too big for >10 micros -> expect the Lucid scan to settle at 5-8 micros); daily loss stop 1.0x block; daily profit stop 1.5x block (this strategy's good days are the trend days the target needs, so give it room). Flat 15:55.

Evidence recap: SPY 2007-24 Sharpe 0.61 (opp-band) / 1.24 (band+VWAP); NQ 2010-24 (90-day, scaled) 24%/yr Sharpe 1.67, WR 38%, payoff 2.25; 2025-26 ~0 on ES/SPY; Sharpe 1.5 when VIX > 20, NR4 prior day 22 bps/day (t=5.1).

## 2. trend_momentum__orb_sma200_oneloss  (filtered ORB: daily SMA bias, R-target, one-loss cap; the only OOS-validated ORB)

Priority **4**, complexity **2**, instruments MNQ (published), MES; bar size 15-min OR on 1-min data. EQ 3 (OOS Jan-2023..Feb-2026: Sharpe 1.10, PF 1.32, MDD 12.8%, WR 25%, 474 trades on 1 MNQ).

```
PARAMS: or_minutes=15, bias_len=200 (daily SMA), rr=2.0, stop_cap_usd=75 (MNQ 150 ticks; MES use 100), buffer_ticks=1,
  last_entry='11:30', valid_minutes=120, flat='15:55', max_trades=1, min_range_atr=0.05, max_range_atr=1.0
PRE: OR = opening_range(df1, '09:30', or_minutes) -> or_high, or_low, i_end; atr = ATR14d; bias = SMA_D(bias_len)
  long_ok[d]  = O930[d] > bias[d];  short_ok[d] = O930[d] < bias[d]        # bias known before the open (uses prev closes)
  rng = or_high - or_low; trade day only if min_range_atr*atr <= rng <= max_range_atr*atr
ENTRY (as strategies/orb.py): from i0 = i_end+1 scan 1-min bars until last_entry or valid_minutes:
  buy stop at or_high + buffer (only if long_ok); sell stop at or_low - buffer (only if short_ok);
  first touched side is the position (both in one bar -> side nearer that bar's open).
  place(i0, side, entry_px=level, kind='stop', valid_bars=valid_minutes, stop_px, tgt_px)
STOP: opposite OR side, capped: stop_px = max(or_low - buffer, entry - stop_cap_usd/point_value) for longs (mirror shorts)
TARGET: tgt_px = entry + rr * (entry - stop_px)   (4c's forced exit at next open is replaced by flat 15:55)
ONE-LOSS CAP: daily_loss_stop = 0.9 * stop_cap_usd (a single full stop-out halts the day); max_trades_day = max_trades
SESSION: set_session('09:30', last_entry, flat)
```
Grid (<= 48): `or_minutes {15, 30}`, `bias_len {100, 200}`, `rr {1.5, 2.5, 4.0}`, `stop_cap_usd {75, 150}`, `direction {both, long_only}`. Fixed buffer 1 tick, last_entry 11:30.

Risk: $R <= $75-150 per micro; daily loss = one R; daily profit stop = Lucid block x1.0 (rr 4 days will be capped by it only via no re-entry, fine). Note the 25% WR / PF 1.3 profile clusters profits -> the consistency rule is the main Lucid risk; the Lucid MC must verify the pass rate with `daily_profit_stop`.

## 3. trend_momentum__orb_close_confirm_halfrange  (15/30-min ORB, 5-min close confirmation, 0.5x-range target, high WR)

Priority **4**, complexity **2**, instruments MES, MNQ; bar size: 15/30-min OR + 5-min confirmation bars. EQ 3 (edgeful ES 6 months: 72% WR PF 1.62; TradeThatSwing NQ 12 months: 75% WR PF 2.51, MDD $2.7k on 1 NQ; both flattened mid-2026; base rate: 30-min OR with 5-min-close confirmation continues 71-77%, 0.5x extension hit 68-72%).

```
PARAMS: or_minutes=15, confirm_minutes=5, tgt_frac=0.5, stop_cap_usd=100, max_or_pct=0.0055, min_range_atr=0.10,
  direction='long_only' | 'both', last_entry='11:30', flat='15:55', max_trades=1, bias_len=0 (0 = no SMA filter)
PRE: OR = opening_range('09:30', or_minutes); rng = or_high - or_low; atr = ATR14d; price = or_close
  trade day only if rng/price <= max_or_pct AND rng >= min_range_atr*atr
  B5 = resample(df1, confirm_minutes, rth_only=True) restricted to bars with tod >= 09:30 + or_minutes
ENTRY: scan B5 bars of day d in order while bar.tod < last_entry:
  if bar.close > or_high: side=+1; i = bar.i_next; break
  if bar.close < or_low:  side=-1 if direction=='both' else STOP SCANNING (no trade today: first close is below); break
  (first confirming close only; the 4b rule "no trade if the first close is below the OR low" is the long_only branch)
  if bias_len > 0: require O930 > SMA_D(bias_len) for longs (mirror shorts)
  place(i, side)                                  # market at next 1-min open after the confirming 5-min close
STOP: opposite OR side, capped at stop_cap_usd: long stop_px = max(or_low, entry_ref - stop_cap_usd/point_value) where entry_ref = confirming bar close
TARGET: tgt_px = entry_ref + tgt_frac * rng  (long); mirror short.    No trail. max_hold = 0 (flat rule handles time).
SESSION: set_session('09:30', last_entry, flat); max_trades_day = max_trades; Lucid risk block (daily_loss_stop = 1 x stop_cap_usd)
```
Grid (<= 48): `or_minutes {15, 30}`, `tgt_frac {0.5, 0.75, 1.0}`, `stop_cap_usd {100, 150}`, `max_or_pct {0.0055, 0.008}`, `direction {long_only, both}`. Fixed confirm 5 min, last_entry 11:30. Do NOT grid weekdays (the published Tuesday/Mon/Thu exclusions are overfit).

Risk: payoff ~1:1 with 65-75% WR is the profile the "many small green days" requirement wants; $R <= $100-150/micro; one trade per day. ES 15-min OR median 8.5 pts -> target ~4 pts = $21/MES: at 10-20 micros a typical win is $200-400 and reaches the $150 payout-day threshold.

## 4. trend_momentum__ib_cperiod_breakout  (Initial Balance breakout with C-period close confirmation, narrow-IB filter)

Priority **3**, complexity **3**, instruments MES, MNQ; bar size: 60-min IB, 30-min (or 5-min) confirmation. EQ 2 (base rates only: 100%-IB extension 45.5% ES / 33% NQ after a C-period close above IB high vs 19% unconditional; narrow IB median extension 75% of IB vs 22% for extreme IB; shallow retrace -> 94% continuation close).

```
PARAMS: ib_minutes=60, confirm_minutes=30, confirm_windows=1 (how many confirmation bars after 10:30 may trigger),
  max_ib_atr=0.5, min_ib_atr=0.15, stop_mode='mid' | 'opp', tgt_ib=1.0, trail=False, last_entry='12:00', flat='15:55',
  max_trades=1, direction='both'
PRE: IB = opening_range('09:30', ib_minutes) -> ib_high, ib_low, ib_mid=(ib_high+ib_low)/2, width; atr = ATR14d
  trade day only if min_ib_atr*atr <= width <= max_ib_atr*atr
  C = resample(df1, confirm_minutes, rth_only=True) bars with tod >= 10:30, first `confirm_windows` bars only
ENTRY: first C bar with close > ib_high -> long at bar.i_next (market); close < ib_low -> short (if direction allows).
  Optional retrace guard (grid): require close - ib_high >= 0 (already true) and (bar.high - close) <= 0.25*width (shallow)
STOP: stop_mode 'mid': stop_px = ib_mid; 'opp': stop_px = ib_low (long). Cap: never farther than 0.5*atr from entry_ref (= confirming close).
TARGET: tgt_px = ib_high + tgt_ib * width (long). If trail: trail_pts = 0.5*width, trail_act_pts = 0.5*width and tgt_ib = 1.5.
RE-ENTRY: if max_trades=2 the opposite side may trigger after a stop-out (double-break days); default 1.
SESSION: set_session('10:30', last_entry, flat); Lucid risk block.
```
Grid (<= 48): `confirm_minutes {5, 30}`, `max_ib_atr {0.5, 0.8}`, `stop_mode {mid, opp}`, `tgt_ib {0.5, 1.0}`, `direction {both, long_only}`. Fixed ib 60 min, last_entry 12:00, max_trades 1 (then one run with 2).

Risk: stop 'mid' ~0.25 ATR (ES 8-10 pts = $40-50/MES); payoff ~1:1-2:1 with ~45% hit expected; entry after 10:30/11:00 avoids the open. Must be validated: no published P&L.

## 5. trend_momentum__crabel_stretch_nr  (Crabel ORB after NR4 / NR7 / inside day, open +/- Stretch stop entries)

Priority **3**, complexity **2**, instruments MES, MNQ, MGC; bar size: daily setup + 1-min execution. EQ 3 (Crabel 1990 S&P tables 59-71% WR; OxfordStrat 42 markets 1980-2013 positive; Zarattini: intraday momentum after NR4 earns 22 bps/day t=5.1 vs 12 bps unconditional). Frequency: NR4 ~25% of days, NR7 ~14%, ID ~12%.

```
PARAMS: setup='nr4' | 'nr7' | 'id' | 'nr4_or_id', stretch_len=10, stretch_mult=1.0, max_stop_atr=0.4, tgt_mode='close' | 'rr',
  rr=1.5, last_entry='11:00', valid_minutes=90, flat='15:55', max_trades=1
PRE (daily RTH bars, all shifted so day d uses days < d):
  range[d'] = H - L; noise[d'] = min(H - O, O - L); stretch[d] = SMA(noise over d-stretch_len..d-1) * stretch_mult
  NR4[d] = range[d-1] == min(range[d-4..d-1]); NR7 analog; ID[d] = H[d-1] < H[d-2] and L[d-1] > L[d-2]
  setup_ok[d] per `setup`; atr = ATR14d; require stretch, atr not NaN
ENTRY at the first RTH bar i0 (tod 09:30): O = open of bar i0 (known at the open; the order is live from that open)
  buy stop at O + stretch[d]; sell stop at O - stretch[d]; first touched side wins (resolve on 1-min as orb.py; both in a
  bar -> side nearer that bar's open). valid until min(last_entry, i0 + valid_minutes).
  place(i0, side, entry_px=level, kind='stop', valid_bars=valid_minutes, stop_px, tgt_px)
STOP: the opposite level (O - stretch for a long) => R = 2*stretch; capped at max_stop_atr*atr from the entry level.
TARGET: tgt_mode 'close' -> no target, flat 15:55 (Crabel); 'rr' -> tgt_px = entry + rr*R.
SESSION: set_session('09:30', last_entry, flat); max_trades_day = 1; Lucid risk block.
```
Grid (<= 48): `setup {nr4, nr7, nr4_or_id}`, `stretch_mult {1.0, 1.5, 2.0}`, `tgt_mode {close, rr}` with `rr {1.5, 3.0}` (rr only when tgt_mode='rr'), `max_stop_atr {0.3, 0.5}`.

Risk: ES 10-day noise ~5-10 pts -> R ~10-20 pts ($50-100/MES) before the ATR cap; one trade/day on ~15-25% of days (low frequency: pair with another spec in the portfolio). Gold: stretch on XAUUSD in $ (MGC $10/pt), use RTH 08:20-13:30 and flat 13:25.

## 6. trend_momentum__gap_and_go  (large opening gap outside the prior day's range, continuation)

Priority **3**, complexity **2**, instruments MNQ, MES; bar size: daily gap + first 5/15-min range. EQ 2 (NQ 2015-25: gaps > 1.2x ATR fill only 8.2% same day, 0.7-1.2x fill 25.6%; open above prior range fills 47%; gap-and-go WR quoted 50-55%, no P&L curve).

```
PARAMS: gap_atr=0.7, outside_prior_range=True, range_minutes=15, direction='both' | 'long_only', stop_mode='range_low' | 'gap_mid',
  max_stop_atr=0.5, tgt_mult=1.0, trail_atr=0 (0 = none), last_entry='10:30', valid_minutes=60, flat='15:55', max_trades=1
PRE: gap[d] = O930[d] - prev_close[d]; atr = ATR14d; pd_high, pd_low = prior RTH extremes
  up_day = gap >= gap_atr*atr and (not outside_prior_range or O930 > pd_high)
  dn_day = gap <= -gap_atr*atr and (not outside_prior_range or O930 < pd_low) and direction=='both'
  FR = opening_range('09:30', range_minutes) -> fr_high, fr_low, i_end
ENTRY: i0 = fr_i_end + 1. up_day: buy stop at fr_high + 1 tick; dn_day: sell stop at fr_low - 1 tick;
  valid until last_entry / valid_minutes. place(i0, side, entry_px, kind='stop', valid_bars, stop_px, tgt_px, trail_pts, trail_act_pts)
STOP: 'range_low': fr_low - 1 tick (long); 'gap_mid': (O930 + prev_close)/2; whichever selected, capped at max_stop_atr*atr from entry.
TARGET: tgt_px = entry + tgt_mult*(fr_high - fr_low).  If trail_atr > 0: no target; trail_pts = trail_atr*atr, trail_act_pts = trail_atr*atr.
SESSION: set_session('09:30', last_entry, flat); max_trades_day = 1; Lucid risk block.
```
Grid (<= 48): `gap_atr {0.5, 0.7, 1.0}`, `range_minutes {5, 15}`, `stop_mode {range_low, gap_mid}`, `tgt_mult {1.0, 1.5}` plus one `trail_atr=0.3` run, `direction {both, long_only}`.

Risk: large-gap days are high-ATR days (NQ MAE P90 ~200 pts = $400/MNQ) -> the ATR cap on the stop is essential; expect the Lucid scan to size 3-6 micros on MNQ. ~10-15% of days trade: a day-selection filter, pair with spec 3 or 11.

## 7. trend_momentum__williams_volbreak  (Larry Williams volatility breakout: open +/- k x prior range)

Priority **2**, complexity **1**, instruments MES, MNQ, MGC; bar size: daily + 1-min. EQ 2 (no credible 2020s ES/NQ test; equivalent to a wide ATR-scaled ORB). Cheap to test with the ORB machinery.

```
PARAMS: k_buy=0.5, k_sell=0.5, range_src='rth' | 'session', bias='none' | 'sma20', stop_k=0.5, max_stop_atr=0.5,
  tgt_mode='close' | 'rr', rr=2.0, last_entry='12:00', valid_minutes=150, flat='15:55', max_trades=1
PRE: prange[d] = High(d-1) - Low(d-1) of RTH ('rth') or full 18:00-17:00 session ('session') bars; atr = ATR14d
  if bias=='sma20': longs only when prev_close > SMA_D(20), shorts only when below
ENTRY at i0 (tod 09:30): O = open of i0; buy stop at O + k_buy*prange; sell stop at O - k_sell*prange; first touched wins;
  place(i0, side, entry_px, kind='stop', valid_bars=valid_minutes, stop_px, tgt_px)
STOP: entry - stop_k*prange (long), capped at max_stop_atr*atr.  TARGET: 'close' none (flat 15:55) or rr*R.
SESSION: set_session('09:30', last_entry, flat); max_trades_day 1; Lucid risk block.
```
Grid (<= 36): `k_buy=k_sell {0.3, 0.5}`, `range_src {rth, session}`, `bias {none, sma20}`, `tgt_mode {close, rr(2.0)}`, `stop_k {0.3, 0.5}` (with the ATR cap). Gold: same, pit hours 08:20-13:30, flat 13:25.

Risk: wide gate on ES (0.5 x 60-pt range = 30 pts) -> stop 15-30 pts = $75-150/MES; 1-4 micros of headroom only.

## 8. trend_momentum__trend_day_runner  (composite trend-day flag at 10:30, direction of the open, trailing runner)

Priority **3**, complexity **3**, instruments MES, MNQ; bar size: daily flags + 30-min IB + 1-min. EQ 2-3 (our synthesis of robust 2014-2026 base rates: narrow IB extends 3.4x further than extreme IB; large outside gaps fill 8%; NR4 prior day doubles intraday momentum P&L; wide 30-min OR continues 77%; only ~10% of ES sessions are trend days).

```
PARAMS: min_score=2, entry_mode='market_1030' | 'ib_break_stop', stop_mode='ib_mid' | 'ib_opp', max_stop_atr=0.5,
  trail_atr=0.3, trail_act_atr=0.3, tgt_atr=0 (0 = runner, no target), last_entry='12:00', flat='15:55', max_trades=1,
  skip_after_trend_day=True, max_ib_atr=1.5
PRE: atr = ATR14d; pd_high/pd_low/prev_close; IB = opening_range('09:30', 60); OR30 = opening_range('09:30', 30)
  flags at 10:30 (all computable from bars <= 10:29 close):
   a) gap_out  = |O930 - prev_close| >= 0.7*atr and (O930 > pd_high or O930 < pd_low)
   b) narrow_ib = (ib_high - ib_low) < 0.5*atr
   c) open_drive = OR30 closes in top 25% of its range and or30_close > pd_high  (or bottom 25% and < pd_low)
   d) nr_prior = NR4[d] or NR7[d] or ID[d]
  score = a + b + c + d; direction = sign(close_1029 - O930) (0 -> no trade)
  negative filters: (ib_high - ib_low) > max_ib_atr*atr -> skip; skip_after_trend_day and |C(d-1)-O(d-1)| >= 0.7*range(d-1) -> skip
  trade_day = score >= min_score and direction != 0
ENTRY: 'market_1030': place(i of bar tod 10:30, direction) (market at open)
       'ib_break_stop': buy stop at ib_high + 1 tick (direction>0) valid until last_entry (sell stop at ib_low - 1 tick if direction<0)
STOP: 'ib_mid' -> ib_mid; 'ib_opp' -> opposite IB extreme; both capped at max_stop_atr*atr from entry_ref.
EXIT: runner: trail_pts = trail_atr*atr, trail_act_pts = trail_act_atr*atr (engine ratchets off the bar extreme once MFE >= act);
      if tgt_atr > 0: tgt_px = entry + tgt_atr*atr. Flat 15:55.
SESSION: set_session('10:30', last_entry, flat); max_trades_day = max_trades; Lucid risk block with daily_profit_stop multiplier 1.5 (trend days are where the target is earned; still capped for consistency).
```
Grid (<= 48): `min_score {1, 2}`, `entry_mode {market_1030, ib_break_stop}`, `stop_mode {ib_mid, ib_opp}`, `trail_atr {0.25, 0.4}`, `tgt_atr {0, 1.0}`, direction both (longs-only as a second run).

Risk: ~1-3 trades per week; stop 0.25-0.5 ATR; large winners on real trend days -> watch the consistency rule (the Lucid MC with the profit stop decides).

## 9. trend_momentum__last_half_hour  (Gao-Han-Li-Zhou: first half-hour predicts last half-hour, with r12 agreement and VIX gate)

Priority **3**, complexity **1**, instruments MES, MNQ (MGC: use 08:20-08:50 -> 13:00-13:30 pit analog). EQ 5 for existence (JFE 2018), 2-3 for 2022-26 tradability (edge shrank ~75%; QuantConnect 2015-20 Sharpe -0.63 overall, 1.45 in the 2020 crash). Extends the existing `strategies/intraday_momentum.py` with the eta(r1, r12) agreement variant and a VIX gate.

```
PARAMS: ref='prev_close' | 'open', entry_time='15:30', flat='15:58', variant='r1' | 'r1_r12', thresh_atr=0.0,
  stop_atr=0.4, vix_min=0 (0 = no gate), max_trades=1
PRE: c1000 = close of bar tod 09:59; c1500 = close of bar tod 14:59; c1530 = close of bar tod 15:29; atr = ATR14d
  r1 = c1000/ref_px - 1  with ref_px = prev_close[d] (paper) or O930[d];   r12 = c1530/c1500 - 1
  signal = sign(r1) if |c1000 - ref_px| >= thresh_atr*atr else 0
  if variant=='r1_r12': signal = signal if sign(r12) == sign(r1) else 0
  if vix_min > 0 and VIX_lag[d] < vix_min: signal = 0
ENTRY: place(i of bar tod 15:30, signal, stop_pts = stop_atr*atr)   # market at the 15:30 open
EXIT: flat at 15:58 (set_session('15:30', '15:31', '15:58')); protective stop only; no target.
SESSION/RISK: max_trades_day 1; daily stops irrelevant (one trade) but keep the hard stop; Lucid risk block.
```
Grid (<= 32): `ref {prev_close, open}`, `variant {r1, r1_r12}`, `thresh_atr {0.0, 0.2}`, `stop_atr {0.3, 0.6}`, `vix_min {0, 18}`.

Risk: tiny edge (~2-3 bps = 1.5 ES pts); at 10-20 MES an average day is ~+$75-150, so it is a consistency filler / afternoon leg for the funded-phase "5 days >= $150" requirement, not a stand-alone eval passer. Macro-release-day gating is not available (no event calendar in the data); note as a data gap.

## 10. trend_momentum__holy_grail_pullback  (Raschke-Connors ADX > 30 + 20-EMA pullback, with Keltner-stop variant)

Priority **2**, complexity **3**, instruments MES, MNQ; bar size 5-min RTH. EQ 1-2 (book + anecdotes; no quantified ES/NQ test). Folds Keltner-channel pullback (Section 14) in as `stop_mode='keltner'`.

```
PARAMS: bar=5, adx_len=14, adx_min=30, ema_len=20, stop_mode='swing' | 'keltner', kc_mult=2.0, atr_len=14 (5-min ATR),
  tgt_mode='swing' | 'rr', rr=1.5, swing_len=20, valid_minutes=30, entry_start='10:00', last_entry='15:00', flat='15:55',
  max_trades=3, trail_after_1r=True
PRE on B = resample(df1, bar, rth_only=True), indicators computed on the continuous RTH 5-min series (min_periods = full window):
  EMA = ema(close, ema_len); ADX = adx(B, adx_len); ATR5 = atr(B, atr_len)
  up_trend[k]  = ADX[k] > adx_min and ADX[k] > ADX[k-1] and EMA[k] > EMA[k-3] and close[k-1] > EMA[k-1]   # rising ADX, rising EMA
  touch_long[k] = up_trend[k] and low[k] <= EMA[k] and close[k] > EMA[k] - 0.5*ATR5[k]                     # first touch of the EMA
  (shorts mirror: falling EMA, high >= EMA)
ENTRY: on touch bar k: buy stop at high[k] + 1 tick, placed at B.i_next[k], valid_bars = valid_minutes (1-min bars);
  place(i_next, +1, entry_px, kind='stop', valid_bars, stop_px, tgt_px, trail_pts, trail_act_pts)
STOP: 'swing': min(low[k-2..k]) - 1 tick; 'keltner': EMA[k] - kc_mult*ATR5[k]; cap at 0.5*ATR14d from entry.
TARGET: 'swing': max(high[k-swing_len..k]) (skip the trade if target < entry + 1*R); 'rr': entry + rr*R.
TRAIL: if trail_after_1r: trail_pts = R, trail_act_pts = R (engine ratchet approximates "trail to the EMA").
RE-ENTRY: after a stop-out, the next EMA touch while up_trend holds may re-enter (max_trades 3).
SESSION: set_session(entry_start, last_entry, flat); Lucid risk block.
```
Grid (<= 48): `adx_min {25, 30}`, `stop_mode {swing, keltner}`, `tgt_mode {swing, rr(1.5)}`, `bar {5, 15}`, `max_trades {1, 3}`. Fixed ema 20, kc_mult 2.0.

Risk: tight stops (ES 4-8 pts on 5-min = $20-40/MES) suit micros; expect ~50% WR x 1.2-1.5 payoff if anything. Natural pairing: only on days flagged by spec 8 (`trend_day_filter=True` as an optional boolean).

## 11. trend_momentum__ema_cross_pullback  (9/21 EMA cross then first pullback, trend-day and SMA-200 gated)

Priority **1**, complexity **2**, instruments MES, MNQ; bar size 5-min RTH. EQ 1 (raw cross PF ~1.2, 60-65% losers in one test; filtered WR claims unsourced). Included because it is the entry mechanism most practitioners pair with trend-day filters; low prior.

```
PARAMS: bar=5, fast=9, slow=21, require_pullback=True, bias_len=200 (daily), trend_day_only=False, stop_atr5=1.5,
  rr=2.0, half_at_1r=False (engine: single contract -> ignore), max_trades=3, entry_start='09:45', last_entry='15:00', flat='15:55'
PRE on B = resample(df1, bar, rth_only=True): EF = ema(close, fast); ES_ = ema(close, slow); ATR5 = atr(B, 14)
  cross_up[k] = EF[k] > ES_[k] and EF[k-1] <= ES_[k-1];  state 'armed_long' from cross_up until cross_down
  if bias_len > 0: longs only if O930 > SMA_D(bias_len) (mirror shorts); if trend_day_only: require spec-8 score >= 2 at 10:30
  pullback_long[k] = armed_long and low[k] <= ES_[k] and close[k] > ES_[k]   (first such bar after the cross; one per cross)
ENTRY: require_pullback: buy stop at high[k] + 1 tick at B.i_next[k], valid 20 1-min bars;  else: market at i_next of the cross bar.
STOP: min(low[k], ES_[k] - 0.5*ATR5[k]) - 1 tick; cap 0.5*ATR14d. TARGET: entry + rr*R. EXIT also on cross_down: exit_at(i_next of cross-down bar).
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = max_trades; Lucid risk block.
```
Grid (<= 32): `require_pullback {True, False}`, `bias_len {0, 200}`, `trend_day_only {False, True}`, `rr {1.5, 2.5}`, `bar {5, 15}`.

Risk: many signals -> commissions; raw PF ~1.2 is below what a $2k MLL needs; keep only if the gated version clears PF 1.3 with >= 150 trades.

## 12. trend_momentum__supertrend_flip  (Supertrend 10/3 (or PSAR) stop-and-flip, long-biased, intraday-flat; gold first)

Priority **2**, complexity **2**, instruments MGC (primary), MNQ, MES; bar size 15-min (grid 15/60). EQ 2 (gold H4 PF 3.2 in 2024-Sep-2026 on a one-way bull market, M15 PF 1.03, NZDUSD < 1; shorts lost on gold). Folds Parabolic SAR (Section 13) in as `trail_type='psar'`.

```
PARAMS: bar=15, trail_type='supertrend' | 'psar', st_len=10, st_mult=3.0, psar=(0.02, 0.02, 0.20), direction='long_only' | 'both',
  bias_len=200 (daily SMA; 0 = none), entry_start, last_entry, flat (gold: '03:00','15:00','16:30'; equities: '09:35','15:00','15:55'),
  hard_stop_atr=0.6, max_trades=2
PRE on B = resample(df1, bar, rth_only=False) (gold trades ~23h; for MES/MNQ use rth_only=True):
  supertrend: hl2 = (H+L)/2; up = hl2 + st_mult*ATR(st_len); dn = hl2 - st_mult*ATR(st_len); bands ratchet (dn[k] = max(dn[k], dn[k-1]) while close[k-1] > dn[k-1]; up mirrors); trend[k] = +1 if close[k] > up[k-1] (flip up) / -1 if close[k] < dn[k-1], else trend[k-1]; line = dn when trend +1, up when trend -1.
  psar: Wilder SAR with AF start/step/max; trend = +1 while close > SAR.
  flip_up[k] = trend[k] == +1 and trend[k-1] == -1 (flip_dn mirror); bias: longs only if prev_close > SMA_D(bias_len)
ENTRY: flip_up within [entry_start, last_entry): place(B.i_next[k], +1, stop_px = line[k] (supertrend) or SAR[k], capped at hard_stop_atr*ATR14d)
EXIT: flip_dn -> exit_at(B.i_next[k]) (and reverse to short at i_next+1 if direction=='both'); hard stop; flat at `flat`.
  (The ratcheting line itself is not re-sent to the engine each bar; the 15-min flip exit plus the fixed hard stop approximate it.)
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = max_trades; Lucid risk block (MGC $80/$160).
```
Grid (<= 48): `bar {15, 60}`, `trail_type {supertrend, psar}`, `st_mult {2.0, 3.0}` (supertrend only), `direction {long_only, both}`, `bias_len {0, 200}`.

Risk: 33-37% WR with occasional large winners (the opposite of what the consistency rule wants); intraday-flat truncates the H4-style winners that produced PF 3.2, so expect PF ~1.0-1.2. Regime risk: gold's 2024-26 trend. Test it, but treat as a filter/exit tool unless it clears the bar.

## 13. trend_momentum__gold_donchian_intraday  (long-only Donchian breakout on 15-min gold, daily trend gate, flat by 16:30)

Priority **2**, complexity **2**, instruments MGC (primary), MNQ/MES secondary; bar size 15-min. EQ 4 for the daily system's long-run behaviour (Gold 2000-25 long-only CAGR 6%, MDD 17%; NQ 1990-2025 CAGR 4%), 2 for intraday use (no credible intraday ES/NQ test; the SPY post-breakout drift decayed to ~0 in the 2020s). Day-trade adaptation of Section 9; the daily Turtle system itself is NOT specced (overnight holds are not allowed).

```
PARAMS: bar=15, n_entry=20, n_exit=10, bias='sma200' | 'tsmom12' | 'none', direction='long_only', stop_atr_bars=2.0 (ATR(20) on 15-min),
  max_stop_atr=0.5 (of ATR14d), entry_start='02:00', last_entry='13:00', flat='16:30' (equities: '09:35','15:00','15:55'), max_trades=2
PRE on B = resample(df1, bar, rth_only=False for gold / True for equities):
  hh[k] = max(high[k-n_entry..k-1]); ll[k] = min(low[k-n_exit..k-1]); ATRb = atr(B, 20)   (windows exclude bar k)
  bias_ok[d]: 'sma200' -> prev_close > SMA_D(200); 'tsmom12' -> prev_close > close 252 sessions earlier; 'none' -> True
  breakout[k] = close[k] > hh[k] and bias_ok and bar k start tod in [entry_start, last_entry)
ENTRY: place(B.i_next[k], +1, stop_px = max(close[k] - stop_atr_bars*ATRb[k], close[k] - max_stop_atr*ATR14d))
EXIT: close[k] < ll[k] -> exit_at(B.i_next[k]); hard stop; flat at `flat`. No fixed target (grid adds tgt rr 2.0 as an option).
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = max_trades; Lucid risk block.
```
Grid (<= 36): `n_entry {20, 55}`, `n_exit {10, 20}`, `bias {sma200, tsmom12, none}`, `tgt {none, rr2.0}`, `bar {15, 60}`.

Risk: gold 15-min ATR ~$3-6 -> stop $6-12 = $60-120/MGC; a one-way regime (2024-26) will flatter it: require PF >= 1.1 on 2021-2023 (sideways gold) before trusting it.

## 14. trend_momentum__squeeze_breakout  (Bollinger-inside-Keltner squeeze release, momentum direction)

Priority **1**, complexity **3**, instruments MNQ, MES; bar size 5-min RTH. EQ 1 (no quantified ES/NQ test). Included as a cheap compression-then-expansion test that overlaps NR-day ORB (spec 5, which has better evidence).

```
PARAMS: bar=5, bb_len=20, bb_k=2.0, kc_len=20, kc_mult=1.5, min_squeeze_bars=6, rr=1.5, trail=False, entry_start='10:00',
  last_entry='15:00', flat='15:55', max_trades=2, max_stop_atr=0.5
PRE on B = resample(df1, bar, rth_only=True):
  mid = sma(close, bb_len); sd = rolling std(close, bb_len); bb_up = mid + bb_k*sd; bb_dn = mid - bb_k*sd
  kc_up = ema(close, kc_len) + kc_mult*atr(B, kc_len); kc_dn = ema(close, kc_len) - kc_mult*atr(B, kc_len)
  squeeze[k] = bb_up[k] < kc_up[k] and bb_dn[k] > kc_dn[k]; run[k] = consecutive squeeze bars ending at k
  fire[k] = not squeeze[k] and squeeze[k-1] and run[k-1] >= min_squeeze_bars
  mom[k] = close[k] - ((max(high[k-19..k]) + min(low[k-19..k]))/2 + mid[k])/2;  side = sign(mom[k])
ENTRY: place(B.i_next[k], side) (market at next open) when fire[k] and side != 0 and bar start tod within window
STOP: opposite KC band at k (kc_dn for longs), capped at max_stop_atr*ATR14d. TARGET: entry + rr*R; if trail: trail_pts = R, act = R, no target.
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = max_trades; Lucid risk block.
```
Grid (<= 32): `kc_mult {1.5, 2.0}`, `min_squeeze_bars {4, 8}`, `rr {1.5, 2.5}`, `trail {False, True}`, `bar {5, 15}`.

Risk: unknown edge; drop if PF < 1.2 on 2023-2026.

## 15. trend_momentum__benchmark_long_0945  (control: buy 09:45, exit 11:00 or 15:55; not a strategy)

Priority **1**, complexity **1**, instruments MES, MNQ; bar size 1-min. EQ 2 (control in the ES 516-session study: +$2.3k to +$22.7k/contract 2024-26, beat all 12 ORB configurations).

```
PARAMS: entry_time='09:45', exit_time='15:55' | '11:00', stop_atr=1.0, bias_len=0
place(i of bar tod entry_time, +1, stop_pts = stop_atr*ATR14d); set_session(entry_time, '09:46', exit_time); max_trades_day 1.
if bias_len > 0: only when O930 > SMA_D(bias_len).
```
Grid: `exit_time {11:00, 15:55}`, `stop_atr {1.0, 3.0}`, `bias_len {0, 200}`. Purpose: every spec above must beat its per-trade and per-day metrics in 2025-01..2026-09 on the same instrument; it is not sized or submitted to the Lucid MC as a candidate (index drift risk, no edge).

---

## Dropped or folded (and why)

| Report section | Decision |
|---|---|
| 3. Zarattini-Aziz 5-min ORB, 10R / EOD exit | Not specced stand-alone: 20-23% WR, MDD 37%, net ~0 after futures costs, incompatible with the 50% consistency rule and a $2k MLL. Its only information (first-candle direction) is covered by `or_minutes=5` in specs 2/3 and `range_minutes=5` in spec 6. |
| 9. Turtle / Donchian daily, 16. 12-month TSMOM / CTA trend | Multi-week overnight holds are not allowed. Used only as `bias` parameters (`sma200`, `tsmom12`) in specs 2, 3, 11, 12, 13. Intraday Donchian adaptation is spec 13. |
| 14. Keltner pullback | Same mechanics as Holy Grail; folded into spec 10 as `stop_mode='keltner'`. |
| 13. Parabolic SAR | Folded into spec 12 as `trail_type='psar'`. |
| 15. Multi-timeframe bias | Not a strategy; it is the `bias_len` / `direction` parameter in specs 2, 3, 4, 6, 11, 12, 13. |
| 17. VWAP trend-following (entry) | Needs volume; a TWAP proxy is not faithful enough for pullback *entries* (equal-weighted). VWAP-as-trailing-stop is approximated inside spec 1 (`stop_mode='own_band_twap'`, flagged). No stand-alone spec. |
| 18. Crude-oil intraday momentum | Data gap: `WTIUSD_1m` has no bars for 2024-2025 and only ~88k bars in 2026 (checked), so it cannot be tested in the prime window. Spec 9 covers the same mechanic on ES/NQ/GC; re-enable for CL only if crude data for 2024-26 is obtained. |
| 19. Trend-day identification | Specced as spec 8 (runner) and as the optional `trend_day_only` gate in specs 10/11. |
| 20. TTM squeeze | Spec 14 (volume confirmation dropped; OHLC-only release rule). |
| 21. Fisher ACD | Equivalent to ORB with an ATR buffer and time confirmation; covered by `buffer_ticks` and the 5-min-close confirmation in spec 3. No separate spec. |
| 22. Buy 09:45 benchmark | Spec 15, benchmark only. |

## Portfolio notes for the backtest agents

- Lucid-fit ranking from the evidence: spec 3 (high WR, 1:1, one trade/day) and spec 2 (OOS-validated) first; spec 1 only with the `regime` gate on; spec 8/6 as the trend-day catchers that supply the $3k; spec 9 as the funded-phase consistency filler. Specs 10-14 are long shots to be dropped fast if PF < 1.2 on 2023-2026.
- Combining legs: all specs are one-position-at-a-time per instrument; the portfolio runner can stack a morning leg (2/3/5/6) with the afternoon leg (9) on the same contract only if their entry windows do not overlap (they do not: 09:30-11:30 vs 15:30).
- Consistency rule arithmetic: with `daily_profit_stop` at 1.0x the block and 10 micros, the largest day is ~$1,200-1,600 < 50% of $3,000; with 20 micros the block must be halved or the MC will show consistency failures.
- Never report a spec without the 2023-2024 hold-out and the 2010-2024 plateau check from `backtest.batch`.
