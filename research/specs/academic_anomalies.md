# Specs: Academic / Quantpedia-style anomalies (equity-index and gold futures) for the Lucid 50K LucidFlex backtest

Source report: `/home/user/claude-workspace/research/families/academic_anomalies.md` (22 strategies, read in full).
Engine contract: `/home/user/claude-workspace/docs/STRATEGY_GUIDE.md`, `backtest/engine.py` (`Intents.place / exit_at / set_session`, `max_trades_day`, `daily_loss_stop`, `daily_profit_stop`; one position and one pending order at a time; fixed 1 contract per run, sizing in the Lucid simulator), helpers in `strategies/common.py` (`opening_range`, `daily_atr`, `daily_bars`, `prior_day_stats`, `session_vwap` (TWAP proxy), `sma`, `ema`, `atr`, `rsi`, `vix_lag1`, `session_info`), `backtest.data.resample(df1, N, rth_only=True)` (gives `i_next`).

Cross-family overlaps (do not run the same rule twice; the ids below are the *academic-replication* parameterisations and say what differs):
- `trend_momentum__noise_area` (14-day paper default) vs `academic_anomalies__noise_area_futures90` (Quantitativo ES/NQ replication: 90-day band, reversal on band crossover, gap-adjusted anchor, daily profit cap). Run both only if the module exposes `lookback`; otherwise fold.
- `calendar_seasonal_structural__pre_fomc_morning_drift` vs `academic_anomalies__pre_fomc_morning_vix` (adds the Lucca-Moench VIX gate and the flagged 18:00 Globex-entry leg). The FOMC date table lives in `calendar_seasonal_structural__calendar_flags_module`; reuse it.
- `calendar_seasonal_structural__turnaround_tuesday` vs `academic_anomalies__turnaround_tuesday_vixterm` (adds the Beyond Passive VIX-term-structure ensemble branch).
- `trend_momentum__last_half_hour` (Gao et al. first-half-hour sign rule; negative OOS) vs `academic_anomalies__last_half_hour_hedging` (Baltussen et al.: whole-day move with a sigma threshold). The Gao rule is the dead one; keep `trend_momentum__last_half_hour` as the control and run this family's version as the live candidate.
- `calendar_seasonal_structural__calendar_window_long` already generalises the payday test; `academic_anomalies__payday_16th_long` is just its 16th-of-month parameter set and is listed for completeness.

## 0. Conventions used by every spec below

Times: all **ET**. Data session 18:00 -> ~16:14 ET next day for `SPXUSD`/`NSXUSD` (CFD feed stops ~16:14), 18:00 -> 17:00 for `XAUUSD`. RTH equities 09:30-16:00; gold pit 08:20-13:30 (gold trades ~23h). A 1-minute bar with `tod = T` covers `[T, T+1)`. "Close at 10:00" means the close of the bar with `tod = 09:59`; the decision is taken with that information and the order is placed at the bar with `tod = 10:00` (`i_next`), i.e. **market at next open (+1 tick slippage)** unless the spec says `kind='stop'` or `kind='limit'`. On N-minute bars (`resample`) the decision uses the N-bar close and the order index is `i_next` (skip `-1`).

Forced flat: equities **15:55** (never later than 15:58); gold pit variants 13:25, gold full-session variants 16:30 (never later than 16:45). No overnight, no weekend. The two "within the CME session" variants (FOMC 18:00 evening entry, overnight drift 01:30-03:30) hold only inside one data session (18:00 -> 17:00) and never through a 17:00 close; they are still **flagged** because the guide's prop-safe convention is "flat by 15:58" and Lucid's definition of overnight must be verified before they go in a live portfolio.

Indicators (exact definitions):
- `ATR14d` = `daily_atr(df1, 14, rth_only=True, rth=(contract.rth_open, contract.rth_close))`: Wilder ATR of RTH daily bars, shifted one day (day d uses days < d). For gold full-session specs use `rth_only=False` (23-hour range). Rows with NaN ATR never trade.
- `D` = `daily_bars(df1, rth_only=True)`; `O930[d] = D.open`; `PC[d] = D.close.shift(1)` (prior RTH close, never the 16:14 bar); `ret[d] = D.close[d]/D.close[d-1] - 1`.
- `RV14[d]` = std of `ret[d-14..d-1]` (14 prior RTH close-to-close returns, `min_periods=14`); `RV14_pts[d] = RV14[d] * PC[d]`.
- `SMA_D(n)` = simple MA of RTH daily closes over the n sessions **before** d (`sma(close, n).shift(1)`).
- `TWAP[d,t]` = `session_vwap(rth_bars)` = cumulative mean of (H+L+C)/3 from 09:30. **Approximation of VWAP** (no volume); flagged wherever used.
- `VIX_lag[d]` = `vix_lag1(df1)` (prior-day VIX close). `VIX3M_lag[d]`: NOT in the repo (see data gap in spec 12); proxy defined there.
- `F = flags(df1)` = the calendar module of the calendar family (`fomc`, `press_conference`, `fomc_stmt_tod`, `payday`, `dow`, `early_close`).
- `R` = |entry - initial stop| in points; `$R = R x point_value` (MES $5/pt, MNQ $2/pt, MGC $10/pt).

Lucid risk block (default for every spec unless overridden; all values **per ONE micro contract**; the Lucid Monte Carlo scales 5-40 micros):
- `daily_loss_stop` (no new entries once realized day P&L <= -X): MES $60, MNQ $80, MGC $80. Grid multiplier `{1.0, 1.5}`. At 10 micros = $600-$1,200, i.e. <= 60% of the $2,000 MLL distance; one bad day cannot breach an EOD-trailing MLL that started the day >= $1,200 above the floor.
- `daily_profit_stop` (no new entries once realized day P&L >= Y): MES $120, MNQ $160, MGC $160. Grid multiplier `{1.0, 1.5, none}`. At 10 micros this caps a day at ~$1,200-$1,800 so no single day exceeds 50% of the $3,000 target (eval consistency rule) and a funded cycle collects many >= $150 days.
- Both stops only block NEW entries; an open position runs to its own stop/target/flat, so **a hard protective stop is mandatory on every entry**.
- One position at a time; `max_trades_day` as specified; always `set_session(entry_start, entry_end, flat)`.
- Volatility targeting (paper: 2-3% daily vol) cannot be done inside the engine (1 contract fixed). It is expressed as a per-session `size_mult[d]` from spec 12 that the portfolio / Lucid tools apply to the daily P&L stream (integer micros), plus a `skip_day[d]` rule for extreme-vol days. Flagged as an engine gap.

Evidence quality (EQ) is from the report (1-5). Priority 5 = best prior of working under Lucid constraints with evidence, 1 = long shot. Complexity 1 = a few lines on existing helpers, 5 = multi-state intraday machine.

Validation protocol: prime window 2025-01-01..2026-09-24; robustness 2018-01..2024-12 (the noise-area edge "appears from 2018"); control 2010-2017 (expected ~flat for the trend rules; a strongly positive 2010-2017 for a rule the sources call flat there is a look-ahead smell). Judge calendar overlays (FOMC, Tuesday, payday, gold Friday) on 2010-2026 trade counts, never on the prime window alone (8-50 trades). Every grid is <= 48 combos; report the plateau, not the best cell.

---

## 1. academic_anomalies__noise_area_futures90  (Zarattini-Aziz-Barbon noise-area momentum, Quantitativo ES/NQ parameterisation: 90-day band, half-hour decisions, band/TWAP trailing stop, reversal, gap-adjusted anchor)

Priority **5**, complexity **4**, instruments MNQ (NQ Sharpe 1.67 in the replication), MES (1.25); bar size 1-min data, decisions every 30 min. EQ 4 (full code-level paper spec with live-measured slippage + independent futures replication net of $2.25 + 0.25 tick per transaction; flat 2010-2017, works 2018-2025; Sharpe rises with VIX; NR4 prior day 22 bp/day t=5.1; Wed best).

Data gap: the VWAP trailing stop needs volume. `stop_mode='own_band_twap'` uses the TWAP proxy (flagged); `stop_mode='own_band'` (current band only) and `'opp_band'` (paper base) need no volume. Vol targeting (3% daily vol, 8x cap in the replication) is delegated to spec 12's `size_mult`.

```
PARAMS (defaults = futures replication): lookback=90, vm=1.0, step=30, first_decision='10:00', last_decision='15:30',
  stop_mode='own_band_twap' | 'own_band' | 'opp_band', hard_stop_atr=0.5, reverse=True, long_only=False,
  bias='none' | 'tsmom60' (spec 12), regime='none' | 'vix_ge' (vix_min=18) | 'nr4', flat='15:55', max_trades=4,
  daily_cap_mult=1.5 (daily_profit_stop multiplier), size_from_overlay=True
PRE (per session d, RTH 1-min bars only, tod 09:30..15:59):
  D, O930, PC, atr = ATR14d as in section 0
  move[d, t] = | close(d, t) / O930[d] - 1 |        for every RTH tod t (store the full 1-min grid; only decision tods are read)
  M = pivot(move) -> rows = day_id, cols = tod;  sigma = M.rolling(lookback, min_periods=lookback).mean().shift(1)   # days d-1..d-lookback
  anchor_hi[d] = max(O930[d], PC[d]);  anchor_lo[d] = min(O930[d], PC[d])                                        # gap-adjusted anchor (report section 16)
  U[d, t] = anchor_hi[d] * (1 + vm * sigma[d, t]);  L[d, t] = anchor_lo[d] * (1 - vm * sigma[d, t])
  twap[d, t] = session_vwap(rth bars)                                                                              # TWAP proxy, only for own_band_twap
  NR4[d] = RTH range of d-1 is the smallest of d-4..d-1
  allowed[d] = sigma[d,:] not NaN AND atr[d] not NaN AND not F.early_close[d]
               AND (regime=='none' OR (regime=='vix_ge' AND VIX_lag[d] >= vix_min) OR (regime=='nr4' AND NR4[d]))
  bias_dir[d] = 0 if bias=='none' else sign(D.close[d-1] / D.close[d-61] - 1)   # tsmom60 (spec 12); counter-bias entries are skipped
STATE MACHINE per allowed session d, pos in {0,+1,-1}, at decision times T = first_decision, +step, ..., last_decision:
  c = close of bar tod T-1;  i = index of bar tod T;  Ucur = U[d, T-1]; Lcur = L[d, T-1]; tw = twap[d, T-1]
  if pos == 0:
     if c > Ucur and (bias_dir[d] >= 0):                pos=+1; place(i, +1, stop_px = c - hard_stop_atr*atr[d])
     elif c < Lcur and not long_only and bias_dir[d] <= 0: pos=-1; place(i, -1, stop_px = c + hard_stop_atr*atr[d])
  elif pos == +1:
     stop_level = Lcur                    if stop_mode=='opp_band'
                = Ucur                    if stop_mode=='own_band'
                = max(Ucur, tw)           if stop_mode=='own_band_twap'
     if c < stop_level:
        exit_at(i); pos = 0                                                     # exit market at the open of bar T
        if reverse and c < Lcur and not long_only and bias_dir[d] <= 0:        # crossover to the opposite band -> reverse
           place(i+1, -1, stop_px = c + hard_stop_atr*atr[d]); pos = -1       # one bar later (one position at a time)
  elif pos == -1: mirror (stop_level = Ucur | Lcur | min(Lcur, tw); reverse to long when c > Ucur)
  The 1-min hard stop (hard_stop_atr x ATR from the decision close) is the disaster stop between decisions; if it fires the
  next decision sees pos == 0 and may re-enter (counts toward max_trades).
POST: set_session(first_decision, last_decision + 1 min, flat); max_trades_day = max_trades;
  daily_loss_stop = block x 1.0; daily_profit_stop = block x daily_cap_mult   # the cap is what satisfies the 50% rule at 10+ micros
```
Grid (<= 48): `lookback {14, 90}` x `vm {1.0, 1.5}` x `stop_mode {own_band_twap, own_band, opp_band}` x `regime {none, vix_ge}` x `hard_stop_atr {0.35, 0.6}`. Fixed: step 30, reverse True, bias none. Extra single runs: `long_only=True` (MNQ), `bias='tsmom60'`, `regime='nr4'` on the best cell.

Session rules: entries 10:00..15:30 at half-hour marks only; flat 15:55; no 09:30-10:00 entries (section 15: the opening hour is the one negative hour in ES).
Risk rules: hard stop 0.35-0.6 ATR (ES 2025: ~25-50 pts = $125-250/MES, NQ ~100-200 pts = $200-400/MNQ) -> expect the Lucid scan to settle at 4-8 micros; daily loss stop 1.0x block; daily profit stop 1.5x block; max 4 entries/day. Expected profile: ~40% winners, payoff 2-2.5, 1-2 entries per active day, worst month ~-6%.
Evidence to beat: ES 16.8%/yr Sharpe 1.25 (90-day), NQ 24.3%/yr Sharpe 1.67, combined 65% positive months, +4-6 bp/trade net. A prime-window result with PF < 1.2 on MNQ means the 2025-26 decay seen on SPY/ES applies to this spec too; then try `regime='vix_ge'` before giving up.

## 2. academic_anomalies__atr_band_open_stop  (Concretum/Kaufman ATR-band intraday breakout: open +/- 0.5 ATR14, 15-min checks, session open as the stop, flat at close)

Priority **4**, complexity **2**, instruments MES, MNQ, MGC (gold: band from the 08:20 pit open, 23h ATR); bar size 15-min (decision) on 1-min data. EQ 3 (SPY 5-min 2007-Jan 2026 net of fees: CAGR > 13%, Sharpe 0.87, in-sample through the prime window, no walk-forward).

```
PARAMS: band_atr=0.5, check_minutes=15, stop_check='tick' | 'close15', stop_buffer_atr=0.0, disaster_stop_atr=1.0,
  first_check='09:45', last_entry='15:00', flat='15:55', max_trades=3, direction='both' | 'long_only', exec_mode='market' (spec 3 adds 'fast_alpha')
PRE: atr = ATR14d; O930[d] (gold: open of the 08:20 bar); U[d] = O930 + band_atr*atr; L[d] = O930 - band_atr*atr
  B = resample(df1, check_minutes, rth_only=True)        # bars 09:30-09:45, 09:45-10:00, ...; decision at each bar close
  allowed[d] = atr not NaN and not F.early_close[d]
LOOP per allowed session d over B bars b in order, pos in {0,+1,-1}:
  skip if b.i_next == -1 or (b.tod + check_minutes) > last_entry (for entries)
  if pos == 0 and b.tod + check_minutes >= first_check:
     if b.close > U[d] and direction allows long:  side=+1
     elif b.close < L[d] and direction=='both':     side=-1
     else continue
     stop_px = O930[d] - side * stop_buffer_atr*atr[d]                    if stop_check=='tick'    # "price returns to the session open"; engine checks every 1-min bar
             = b.close - side * disaster_stop_atr*atr[d]                  if stop_check=='close15' # disaster stop only; open-level test below
     place(b.i_next, side, stop_px=stop_px); pos = side; entries += 1
  elif pos != 0 and stop_check=='close15':
     if (pos==+1 and b.close < O930[d]) or (pos==-1 and b.close > O930[d]): exit_at(b.i_next); pos = 0    # open-level stop evaluated on 15-min closes (paper semantics)
  (any 1-min stop fill resets pos = 0 for the next bar; re-entry allowed while entries < max_trades)
POST: set_session(first_check, last_entry, flat); max_trades_day = max_trades; Lucid block (daily_loss_stop 1.0x, daily_profit_stop 1.0x)
```
Grid (<= 36): `band_atr {0.35, 0.5, 0.75}` x `stop_check {tick, close15}` x `direction {both, long_only}` x `max_trades {1, 3}` (+ `check_minutes {15, 30}` on the best cell). Fixed first_check 09:45, last_entry 15:00.

Session rules: first possible entry at the 09:45 check (band from the 09:30 open; no unconditional 09:30 entries); last entry 15:00; flat 15:55. Gold: checks from 08:35, last entry 12:30, flat 13:25 (pit) or 16:30 (full session run).
Risk rules: max loss per trade = band + buffer ~0.5-0.75 ATR (ES 2025 ATR14 ~60-80 pts -> $150-300/MES; MNQ ~$250-400) -> Lucid sizing 4-6 micros; `stop_check='tick'` is tighter than the paper (more whipsaw, smaller losses) and `close15` is the paper. daily_loss_stop 1.0x block (two full stops end the day), daily_profit_stop 1.0x block, 1-3 trades/day.
Evidence: Sharpe 0.87 net on SPY; the overlay (spec 3) improves it. Expect ~1 trade/day, 40-45% winners.

## 3. academic_anomalies__atr_band_fast_alpha  (spec 2 with the Concretum "fast alpha" execution overlay: limit entry after one opposite 5-min bar, stop exit delayed until one favourable 5-min bar)

Priority **3**, complexity **3**, instruments MES, MNQ; bar size 15-min signal + 5-min execution bars on 1-min data. EQ 3 (same paper: 1-bar 5-min reversal ~-1 bp next bar, standalone unprofitable after costs; as an overlay it raises the baseline Sharpe above 0.87). Implemented as `exec_mode='fast_alpha'` of the spec-2 module.

```
PARAMS (in addition to spec 2): pullback_bars=1, max_arm_attempts=3, limit_valid_bars=5, exit_delay_max_bars=3, disaster_stop_atr=1.0
PRE: as spec 2 plus B5 = resample(df1, 5, rth_only=True)
ENTRY (after a spec-2 signal bar b with side s at 15-min close):
  arm = 0; scan B5 bars q with q.i_first > b.i_last and q.tod + 5 <= last_entry:
     if the signal is cancelled (s==+1 and q.close < U[d], or s==-1 and q.close > L[d]): stop scanning (no trade from this signal)
     if sign(q.close - q.open) == -s  (one opposite-direction 5-min bar; 'pullback_bars' consecutive if > 1):
        limit_px = q.low if s==+1 else q.high                                  # limit at the prior bar's extreme
        place(q.i_next, s, entry_px=limit_px, kind='limit', valid_bars=limit_valid_bars,
              stop_px = b.close - s*disaster_stop_atr*atr[d])                  # disaster stop; the open-level stop is handled below
        arm += 1; if filled -> pos = s (engine); if not filled within valid_bars and arm < max_arm_attempts: keep scanning
        if arm == max_arm_attempts: stop scanning
EXIT (pos != 0): at each B5 close q:
  if the open-level stop condition holds (pos==+1 and q.close < O930[d], mirror short): pending_exit = True, delay = 0
  if pending_exit: if sign(q.close - q.open) == pos (one favourable bar) or delay >= exit_delay_max_bars: exit_at(q.i_next); pos = 0
                   else delay += 1
  (disaster stop and flat 15:55 are hard; the engine's limit fill rule requires price to trade through limit_px by one tick, so fills are conservative)
POST: as spec 2; max_trades_day = max_trades
```
Grid (<= 24): `band_atr {0.5, 0.75}` x `direction {both, long_only}` x `exit_delay_max_bars {0, 3}` x `limit_valid_bars {5, 10}` x `max_arm_attempts {1, 3}` (0 delay = immediate exit on the 15-min open-level test; isolates the entry half of the overlay). Fixed stop_check close15 semantics, disaster stop 1.0 ATR.

Session rules: as spec 2 (first arm after 09:45, last entry 15:00, flat 15:55).
Risk rules: as spec 2; the delayed exit widens the worst case to the disaster stop (1.0 ATR ~ $300-400/MES) on fast reversals -> the Monte Carlo will size 3-5 micros; if exit_delay 3 raises MDD without raising PF, keep delay 0 and only the limit entry (which alone saves ~1 tick/side = the whole gross edge of single-bar signals per Mesfin 2026).

## 4. academic_anomalies__orb5_atr_stop_eod  (Zarattini-Aziz 5-minute ORB: first-candle direction, ATR-fraction stop, no target, EOD exit; long-only on futures)

Priority **2**, complexity **2**, instruments MNQ (QQQ/TQQQ paper; MNQ falsification), MES; bar size 5-min OR on 1-min data. EQ 3 (QQQ 2016-23 Sharpe 1.12, win 24%; TQQQ 2016-25 CAGR 41.9%, Sharpe 1.07, MDD -37%; MNQ 2022-25 walk-forward: long bar+1 net -0.82 pts, long bar+15 +2.82 pts T=0.88 (improving 2023->2025), ALL shorts negative). Differs from `strategies/orb.py` (range-breakout stops): this is the *candle-direction* rule with a market entry at the OR close.

```
PARAMS: or_minutes=5, direction='long_only' | 'both', stop_mode='or_extreme' | 'atr', stop_atr=0.1, target_r=0 (0 = none, EOD),
  max_hold=0 (0 = EOD; 75 = bar+15 variant), min_body_ticks=2 (doji filter), flat='15:55', max_trades=1
PRE: OR = opening_range(df1, '09:30', or_minutes) -> or_open, or_close (first/last 1-min bars), or_high, or_low, i_end; atr = ATR14d
  dir[d] = +1 if or_close - or_open >= min_body_ticks*tick; -1 if <= -min_body_ticks*tick; else 0 (no trade)
  trade[d] = dir != 0 and (direction=='both' or dir == +1) and atr not NaN
ENTRY: i = OR.i_end + 1 (market at the open of the bar after the OR closes, i.e. 09:35 for or_minutes=5)
  stop_px = or_low (long) / or_high (short)                  if stop_mode=='or_extreme'   (paper base: R = OR range)
          = or_close - dir*stop_atr*atr[d]                   if stop_mode=='atr'          (paper best: 5% ATR; 0.1-0.25 ATR here for futures ticks)
  tgt_px  = or_close + dir*target_r*R if target_r > 0 else NaN
  place(i, dir, stop_px=stop_px, tgt_px=tgt_px, max_hold=max_hold)
EXIT: stop / optional 10R target / max_hold bars / flat 15:55
POST: set_session('09:30', '09:36' (or_minutes+1), flat); max_trades_day 1; daily_loss_stop = 1 x $R cap (one loss ends the day); daily_profit_stop block x 1.0
```
Grid (<= 24): `or_minutes {5, 15}` x `stop_mode/stop_atr {or_extreme, atr 0.1, atr 0.25}` x `direction {long_only, both}` x `max_hold {0, 75}`. Fixed target_r 0 (one extra run target_r=10 on the best cell).

Session rules: entry at exactly one bar (09:35 / 09:45); flat 15:55 (or max_hold 75 min -> ~10:50).
Risk rules: $R = 0.1-0.25 ATR (MNQ 2025 ATR ~400 pts -> 40-100 pts = $80-200/MNQ; or_extreme on a 5-min NQ candle ~50-120 pts); one trade/day; 24% win rate with EOD runners is lumpy -> the daily profit stop does nothing here (one trade) so the consistency rule must be checked by the Lucid MC with `micros` small (3-6). Shorts are expected to fail (report them as the control).

## 5. academic_anomalies__last_half_hour_hedging  (Baltussen-Da-Lammers-Martens hedging-demand momentum: direction of the prior-close -> 15:30 move when it exceeds k sigma; hold 15:30 -> 15:55)

Priority **3**, complexity **1**, instruments MES, MNQ; bar size 1-min. EQ 3 (JFE 2021, ~60 futures incl. ES, pooled t 3-6, strongest in equity indices; mechanism = gamma hedging / LETF rebalancing; not independently re-tested post-2020; competing evidence of slight *reversal* for the first-half-hour-conditioned rule). Distinct from `trend_momentum__last_half_hour` (that is the dead Gao r1 rule, the control).

```
PARAMS: entry_time='15:30', ref='prev_close' | 'open', k_sigma=0.75, sigma_mode='rv14' | 'atr14', stop_atr=0.3, flat='15:55',
  vix_min=0 (0 = no gate), direction='both' | 'long_only', max_trades=1
PRE: PC, O930, atr = ATR14d, RV14_pts as in section 0;  c1530[d] = close of bar tod 15:29
  ref_px = PC[d] if ref=='prev_close' else O930[d];  mv = c1530 - ref_px
  sig_pts = RV14_pts[d] if sigma_mode=='rv14' else atr[d]
  signal[d] = sign(mv) if |mv| >= k_sigma * sig_pts else 0;  if direction=='long_only' and signal < 0: signal = 0
  if vix_min > 0 and VIX_lag[d] < vix_min: signal = 0;  skip F.early_close days (no 15:30 bar)
ENTRY: place(i of bar tod 15:30, signal, stop_pts = stop_atr*atr[d])     # market at the 15:30 open
EXIT: hard stop or forced flat 15:55 (market at the open of the 15:55 bar); no target
POST: set_session('15:30', '15:31', flat); max_trades_day 1; Lucid block (moot: one trade)
```
Grid (<= 24): `ref {prev_close, open}` x `k_sigma {0.5, 0.75, 1.0}` x `stop_atr {0.25, 0.5}` x `vix_min {0, 18}`. Fixed sigma_mode rv14 (atr14 as one check), direction both (long_only one run).

Session rules: one entry at 15:30; flat 15:55 (the paper holds to 16:00; the last 5 minutes are given up for prop safety).
Risk rules: 25-minute hold; stop 0.25-0.5 ATR; typical move 5-12 ES pts -> needs 10-20 MES to matter; fat tails on FOMC days (the 14:00 statement move is inside the signal; optionally skip F.fomc). Fits the many-small-days profile; expected ~60-90 signals/yr at k=0.75.

## 6. academic_anomalies__eod_large_move_momentum  (QuantRocket / Cheng-Madhavan leveraged-ETF rebalancing momentum: |prior close -> 14:00| > threshold, trade the direction 14:00 -> 15:55)

Priority **2**, complexity **1**, instruments MNQ, MES; bar size 1-min. EQ 3 (14 LETFs 2008-2016 at +/-6%: CAGR 31%, Sharpe 1.95, decayed from 2017; the ES/NQ translation is an interpretation). Parameter set of the spec-5 module (`entry_time='14:00'`, percentage threshold).

```
PARAMS (spec-5 module): entry_time='14:00', ref='prev_close', thresh_mode='pct', thresh_pct=1.3 (MES) | 2.0 (MNQ), stop_atr=0.4, flat='15:55', max_trades=1
PRE: c1400[d] = close of bar tod 13:59; mv_pct = c1400 / PC[d] - 1; signal = sign(mv_pct) if |mv_pct| >= thresh_pct/100 else 0
ENTRY: place(i of bar tod 14:00, signal, stop_pts = stop_atr*atr[d]);  EXIT: stop or flat 15:55 (QuantRocket exits 15:45: grid)
POST: set_session('14:00', '14:01', flat); max_trades_day 1
```
Grid (<= 16): `thresh_pct {0.8, 1.3, 2.0}` (MES) / `{1.3, 2.0, 3.0}` (MNQ) x `exit {15:45, 15:55}` x `stop_atr {0.4, 0.8}`.
Session rules: single 14:00 entry; flat 15:45/15:55. Risk rules: rare (10-30 signals/yr, clustered in 2020/2022/Apr-2025) on high-vol days; stop 0.4-0.8 ATR of an already-large ATR -> the Lucid scan must cap micros by the worst-day loss (rule of thumb: max_dd_intraday x micros < $1,500). Report on 2018-2026 only; a prime-window count under 15 is not interpretable.

## 7. academic_anomalies__pre_fomc_morning_vix  (Lucca-Moench pre-FOMC drift, same-session morning leg with the VIX gate; flagged 18:00 Globex-entry leg)

Priority **4**, complexity **1**, instruments MES (confirmed in E-mini since 1997), MNQ secondary; bar size 1-min. EQ 5 (SR 512: +49 bp/meeting t>4.5, 98/131 positive, Sharpe 1.14-1.43; 2011-18 ~40 bp on press-conference meetings only; SPY 1993-2024 Sharpe 0.5-0.6, flat 2016-19, strong 2020-24; +31 bp per 1 sd VIX). Uses the FOMC table + `press_conference` + `fomc_stmt_tod` from `calendar_seasonal_structural__calendar_flags_module`.

```
PARAMS: entry_time='09:31' | '18:00' (flagged), exit_time='13:55', stop_pct=0.5, press_conf_only=True, vix_min=13 (0 = none), target_pct=0, max_trades=1
PRE: trade_day[d] = F.fomc[d] and (not press_conf_only or F.press_conference[d]) and (vix_min == 0 or VIX_lag[d] >= vix_min)
  exit_tod[d] = min(exit_time, F.fomc_stmt_tod[d] - 5 min)           # 13:55 for 2013+; never hold into the statement
ENTRY: i = i(entry_time) of session d where trade_day[d]           # 18:00 = first bar of the same data session (the prior calendar evening)
  ref = close of bar i-1; stop_pts = stop_pct/100 * ref; tgt_pts = target_pct/100 * ref if target_pct > 0 else NaN
  place(i, +1, stop_pts=stop_pts, tgt_pts=tgt_pts)
EXIT: hard stop; optional target; forced flat at exit_tod (market at the open of the first bar >= exit_tod); no re-entry after a stop
POST: set_session(entry_time, entry_time + 1 min, exit_tod)   # overnight window supported by set_session for the 18:00 leg; max_trades_day 1
```
Grid (<= 12): `entry_time {09:31, 18:00 (flag)}` x `vix_min {0, 13, 18}` x `stop_pct {0.5, 0.8}`. Fixed press_conf_only True (one run False), exit 13:55 (one run 12:30 to test front-loading).

Session rules: 8 days/yr (7 in 2020, March 2020 excluded); the 09:31 leg is prop-safe; the 18:00 leg holds ~20 hours inside one CME session (18:00 -> 13:55) and is **flagged: verify Lucid's overnight definition (positions must be flat before the 17:00 daily close; this never crosses it) before using it live**; both legs are flat 5 minutes before the statement.
Risk rules: stop 0.5-0.8% (ES ~30-50 pts = $150-250/MES) -> Monte Carlo sizes 3-5 micros; expected +15-35 bp per event in the morning slice (~10-20 ES pts = $50-100/MES; the slice is not reported separately in the papers: flag) -> at 10 micros a typical winning FOMC day is a $500-1,000 day, a payout-qualifying day about half the time.
Data gap: FOMC table is hard-coded from memory in the calendar module (verify against federalreserve.gov); VIX daily from Yahoo is available.

## 8. academic_anomalies__overnight_drift_eu_open  (Boyarchenko-Larsen-Whelan overnight drift at the European open: long ES 01:30 -> 03:30 ET after a prior-day sell-off, passive entry)

Priority **2**, complexity **2**, instruments MES (ES evidence only; MNQ as a check); bar size 1-min, Globex. EQ 4 (NY Fed SR 917: 02:00-03:00 +1.48 bp/day, positive 20 of 23 years, every weekday, 2020 best; OD+ 01:30-03:30 Sharpe 1.3 pre-cost / 0.3 post; buy-the-dip conditional Sharpe 1.8 pre / 1.1 post, positive skew). Data gap: the conditioning variable (closing order imbalance, RSV) needs volume -> proxied by the prior RTH day's return sign (flagged); the post-cost edge depends on passive fills.

```
PARAMS: entry_time='01:30', exit_time='03:30', condition='prev_rth_down' | 'last_hour_down' | 'none' (control), entry_kind='limit' | 'market',
  limit_offset_ticks=1, limit_valid_bars=10, stop_atr=0.3, vix_min=0, max_trades=1
PRE: session d contains the calendar-night bars 18:00(d-1 evening) .. 16:14(d); D = daily_bars(rth_only=True)
  ret_prev[d]  = D.close[d-1] / D.close[d-2] - 1                                  # both closes before the session started
  lasthr[d]    = close(d-1, 15:59) / close(d-1, 14:59) - 1
  cond[d] = (condition=='prev_rth_down' and ret_prev[d] < 0) or (condition=='last_hour_down' and lasthr[d] < 0) or condition=='none'
  trade[d] = cond[d] and atr[d] not NaN and (vix_min == 0 or VIX_lag[d] >= vix_min) and F.dow[d] in Mon..Fri
ENTRY: i = i(entry_time) of session d (bar tod 01:30); ref = close of bar i-1
  if entry_kind=='limit': place(i, +1, entry_px = ref - limit_offset_ticks*tick, kind='limit', valid_bars=limit_valid_bars, stop_pts = stop_atr*atr[d])   # fills only if price trades through by one tick; unfilled -> no trade
  else:                   place(i, +1, stop_pts = stop_atr*atr[d])
EXIT: hard stop or forced flat at exit_time (market at the open of the 03:30 bar)
POST: set_session(entry_time, entry_time + limit_valid_bars min, exit_time)   # flat window 03:30..18:00 also covers RTH: harmless, no entries there
  max_trades_day 1; Lucid block (moot)
```
Grid (<= 24): `condition {prev_rth_down, last_hour_down, none}` x `window {01:30-03:30, 02:00-03:00}` x `entry_kind {limit, market}` x `stop_atr {0.25, 0.5}`.

Session rules: entry 01:30 (or 02:00), flat 03:30 (03:00); Sunday-night sessions are Monday's `day_id` and qualify (the paper finds the effect on every weekday); skip if the 01:30 bar is missing (holiday session).
Risk rules: ~1.5-3 bp/day = $4-8 per MES -> needs 10-20 MES to matter, which raises the tail from 03:00-04:00 European data; stop 0.25-0.5 ATR; this leg rarely clears the $150 payout-day threshold alone and is a consistency filler at best. **Flagged**: inside one CME session (never crosses 17:00) but outside the guide's RTH convention; verify Lucid's overnight definition and the Lucid "no trading during maintenance" windows before live use.

## 9. academic_anomalies__turnaround_tuesday_vixterm  (Turnaround Tuesday ensemble: Monday down AND (Friday down OR VIX term structure in backwardation); long Tuesday 09:31 -> 15:55)

Priority **3**, complexity **1**, instruments MES (SPY/VTI evidence), MNQ; bar size 1-min with daily signals. EQ 3 (SPY 1993-2026: +0.10% after Monday down, +0.33% after Fri+Mon down, stable across eras; VTI 2007-2025 ensemble +0.469%/trade t=3.29, 176 trades; inside the backwardation decile t=3.04). Differs from `calendar_seasonal_structural__turnaround_tuesday` by the VIX-term-structure branch and the `mon_down_only` baseline.

```
PARAMS: rule='ensemble' | 'mon_down' | 'fri_mon_down', entry_time='09:31' | '10:00', exit_time='15:55', backwardation_mode='vix3m' | 'proxy',
  proxy_mult=1.15, decile_lookback=252, stop_atr=0.6, target_atr=0, max_trades=1
PRE: D (RTH closes); ret[d] = D.close[d]/D.close[d-1] - 1
  tue[d] = F.dow[d]==1 and F.dow[d-1]==0 (session d-1 is a Monday; skip Tuesdays after a Monday holiday)
  mon_down[d] = ret[d-1] < 0;   fri_down[d] = (F.dow[d-2]==4) and ret[d-2] < 0
  bw[d] (backwardation):
     'vix3m': (VIX_lag[d] / VIX3M_lag[d]) >= rolling 90th percentile of that ratio over the prior decile_lookback sessions   # DATA GAP: ^VIX3M not downloaded; add ('^VIX3M','VIX3M') to data/download_yahoo.py (Yahoo history from Dec 2007)
     'proxy': VIX_lag[d] >= proxy_mult * SMA20(VIX_lag)[d]   (spike vs its trailing mean; flagged approximation of the term-structure inversion)
  trade[d] = tue[d] and atr not NaN and
     (rule=='mon_down'     and mon_down[d]) or
     (rule=='fri_mon_down' and mon_down[d] and fri_down[d]) or
     (rule=='ensemble'     and mon_down[d] and (bw[d] or fri_down[d]))
ENTRY: place(i(entry_time), +1, stop_pts = stop_atr*atr[d], tgt_pts = target_atr*atr[d] if target_atr > 0 else NaN)
EXIT: stop / optional target / flat 15:55.   POST: set_session(entry_time, entry_time + 1 min, exit_time); max_trades_day 1
```
Grid (<= 24): `rule {mon_down, fri_mon_down, ensemble}` x `backwardation_mode {proxy, vix3m (once downloaded)}` x `entry_time {09:31, 10:00}` x `stop_atr {0.5, 1.0}`.

Session rules: Tuesdays only; one entry; flat 15:55 (the documented edge is Monday close -> Tuesday close; the overnight portion is not capturable and the RTH-only split is the thing being tested).
Risk rules: stop 0.5-1.0 ATR ($150-300/MES) -> 3-5 micros; ~10 trades/yr (ensemble), ~20-25 (mon_down); judge on 2010-2026 (150-350 trades); keep as a long-bias flag (`tt_day[d]`) for specs 1/2/13 if stand-alone PF < 1.4.

## 10. academic_anomalies__gold_friday_long  (Gold Friday effect, day-trade version: long MGC on Fridays from the 08:20 pit open (or 09:30) to 13:25 / 16:30; flagged Thursday-18:00 version)

Priority **2**, complexity **1**, instrument MGC (GLD evidence); bar size 1-min. EQ 2 (Beyond Passive GLD 2007-2025 Thu close -> Fri close Sharpe 0.93; Blose-Gondhalekar weekend effect; Caminschi-Heaney PM-fix pressure; single practitioner study, no RTH split).

```
PARAMS: entry_time='08:20' | '09:30' | '18:00' (Thu evening, flagged), exit_time='13:25' | '16:30', stop_atr=0.5, trend_gate='none' | 'sma50',
  target_atr=0, max_trades=1
PRE: atr = daily_atr(df1, 14, rth_only=False) (23h gold ATR); fri[d] = F.dow[d]==4 and not F.early_close[d]
  gate[d] = True if trend_gate=='none' else PC[d] > SMA_D(50)[d]  (daily full-session closes)
  trade[d] = fri[d] and gate[d] and atr not NaN
ENTRY: place(i(entry_time), +1, stop_pts = stop_atr*atr[d], tgt_pts = target_atr*atr[d] if > 0 else NaN)   # 18:00 entry = first bar of Friday's data session (Thursday evening), inside one CME session
EXIT: stop / target / flat at exit_time (13:25 = before the 13:30 pit close; 16:30 = before the 17:00 daily close; never later than 16:45)
POST: set_session(entry_time, entry_time + 1 min, exit_time); max_trades_day 1; Lucid block MGC
```
Grid (<= 16): `entry_time {08:20, 09:30}` x `exit_time {13:25, 16:30}` x `stop_atr {0.5, 1.0}` x `trend_gate {none, sma50}` (+ one flagged run entry 18:00).

Session rules: Fridays only; gold pit 08:20-13:30; flat 13:25 or 16:30. Risk rules: GC 2025-26 ATR ~1-1.5% ($40-60/MGC) vs a 0.1-0.2% drift: a tilt, not a stand-alone; stop 0.5-1.0 ATR; 52 trades/yr, judge on 2010-2026 (~800 Fridays). Prefer as a `friday_long_tilt` flag for gold trend rules (`trend_momentum__gold_donchian_intraday`).

## 11. academic_anomalies__payday_16th_long  (Ma-Pratt payday anomaly: long the index on the 16th calendar day, day-trade 09:31 -> 15:55; parameter set of calendar_window_long)

Priority **1**, complexity **1**, instruments MES, MNQ; bar size 1-min. EQ 3 (S&P 1980-2010 +0.214%/event, Sharpe 0.6; no post-2015 OOS; authors warn bi-weekly pay dilutes it). Listed for completeness; run through `calendar_seasonal_structural__calendar_window_long` with `window='payday16'`.

```
PARAMS: window='payday16' | 'first2' (control: 1st-2nd of month, the only days the paper says beat the 16th) | 'other' (control), entry_time='09:31', exit_time='15:55', stop_atr=0.8
PRE: payday16[d] = session date has day-of-month == 16, or is the first session after a 16th that is not a session (weekend/holiday)
ENTRY: place(i(entry_time), +1, stop_pts = stop_atr*atr[d]);  EXIT: stop or flat 15:55
POST: set_session(entry_time, entry_time + 1 min, exit_time); max_trades_day 1
```
Grid (<= 6): `window {payday16, first2, other}` x `stop_atr {0.6, 1.0}`.
Session rules / risk: 12 trades/yr; +20 bp expected (12 ES pts = $60/MES); judge on 2010-2026 (~200 events) against the `other` control; drop unless the 16th beats the all-days mean by > 10 bp with t > 2.

## 12. academic_anomalies__vix_term_vol_target_overlay  (infrastructure: VIX term-structure regime, realized-vol sizing multiplier, TSMOM daily bias, hour-of-day / day-of-week filters, NQ/ES relative-strength flag; consumed by specs 1, 2, 5, 9, 13)

Priority **3**, complexity **2**, instruments all; bar size daily (from the 1-min data + Yahoo VIX). Not a strategy; produces `overlay(df1, contract) -> DataFrame indexed by day_id`. Folds report items 12 (VIX vs VIX3M), 13 (vol scaling), 15 (seasonality filters), 18 (NQ/ES relative strength) and 20 (TSMOM bias).

```
INPUT: df1 (traded symbol), VIX_1d.parquet, (VIX3M_1d.parquet when downloaded), SPXUSD/NSXUSD 1-min for the ratio
PER day_id d (all series use information from sessions < d only):
  vix[d]        = VIX_lag[d];  vix3m[d] = VIX3M_lag[d] (NaN until downloaded)
  contango[d]   = vix[d] < vix3m[d]            if vix3m available
                = vix[d] < proxy_mult*SMA20(vix)[d]   otherwise (proxy_mult 1.15; FLAGGED approximation; also flag the decile version for spec 9)
  backwardation[d] = not contango[d]
  vix_bucket[d] = 'low' if vix < 15, 'mid' if 15..25, 'high' if 25..35, 'extreme' if > 35
  rv14[d]       = RV14[d] (std of 14 prior RTH close-to-close returns);  rv_med[d] = median of rv14 over the prior 252 sessions
  size_mult[d]  = clip(vol_target / rv14[d], 0.5, 2.0)  with vol_target = rv_med[d]   # unit size at median vol; half at 2x vol; double at 0.5x vol
  skip_day[d]   = rv14[d] > 3 * rv_med[d]  (extreme regime: no new entries; Lucid DD protection) or vix[d] > 45
  regime_size[d]= size_mult[d] * (0.5 if vix_bucket=='extreme' else 1.0)            # report item 12(c): halve all sizes when VIX > 35
  tsmom_k[d]    = sign(D.close[d-1] / D.close[d-1-k] - 1) for k in {20, 60, 120}; tsmom_bias[d] = sign(sum of the three signs) (0 = mixed)
  no_long_0930[d] = True (constant filter: no unconditional longs 09:30-10:00; ES 09:00-10:00 is -1.2 bp/day)
  dow_weight[d] = {Mon: 0.5, Tue: 0.5, Wed: 1.0, Thu: 1.0, Fri: 1.0}[F.dow[d]]   # Beat-the-Market weekday table; use ONLY as a reporting split, never as a grid dimension (overfit risk)
  nq_es_rs[d]   = (NSX close[d-1] / SPX close[d-1]) > SMA20 of that ratio (daily RTH closes from the two 1-min feeds)   # EQ 1; optional long-side gate
  dd_room_cap: NOT computable here (needs account state) - the Lucid MC applies "max daily loss <= 30% of remaining trailing-DD room" when it scales micros
OUTPUT columns: vix, vix3m, contango, backwardation, vix_bucket, rv14, size_mult, regime_size, skip_day, tsmom_20/60/120, tsmom_bias, dow_weight, nq_es_rs
SELF-CHECK: size_mult has median ~1.0 over 2018-2026; skip_day fires on < 3% of sessions (Mar 2020, Aug 2024, Apr 2025); tsmom_bias == +1 on > 60% of 2025-26 sessions (bull tape)
```
Grid: none (module). Tunables: `proxy_mult {1.15, 1.3}`, `vol_target` = rolling median (alternative fixed 1.0%/day), `size caps {0.5-2.0}`.
Session rules: n/a. Risk rules: `size_mult` and `skip_day` are applied by `backtest.portfolio` / the Lucid MC to the per-micro daily P&L stream (round to integer micros; never exceed the Lucid contract cap 40 micros eval / 20 micros funded); the engine itself stays 1 contract. Data gap: ^VIX3M is not in `data/parquet` (add `('^VIX3M','VIX3M')` to `data/download_yahoo.py`; until then the SMA20 proxy is used and every result that depends on `contango` is labelled approximate); VX futures curve not needed; dealer gamma (options) not available -> `rv14`/`vix_bucket` are the proxies.

## 13. academic_anomalies__vix_dip_buy_1000  (VIX-gated short-term mean reversion, index version of the Connors RSI(2) family: 2+ down closes, VIX >= 20, weak first half hour -> long at 10:00, flat 15:55)

Priority **2**, complexity **1**, instruments MES, MNQ; bar size 1-min with daily signals. EQ 2 (S&P constituents 2006-25: VIX >= 20 gate 5.1% CAGR Sharpe 0.47 vs 0.30 ungated, best 2020-22, zero trades 2017; the index/day-trade version is an interpretation; OU mean reversion on MGC 5-min is negative -> not applied to gold).

```
PARAMS: n_down=2, vix_min=20, entry_time='10:00', require_morning_down=True, rsi2_max=0 (0 = off; else RSI(2) of daily closes <= rsi2_max),
  stop_atr=0.6, target_atr=0, exit_time='15:55', max_trades=1
PRE: D; ret[d]; down_streak[d] = number of consecutive sessions ending at d-1 with ret < 0
  morning[d] = close(d, 09:59) / O930[d] - 1                              # known at 10:00
  trade[d] = down_streak[d] >= n_down and VIX_lag[d] >= vix_min and (not require_morning_down or morning[d] <= 0)
             and (rsi2_max == 0 or RSI(2)(D.close)[d-1] <= rsi2_max) and atr not NaN
ENTRY: place(i of bar tod 10:00, +1, stop_pts = stop_atr*atr[d], tgt_pts = target_atr*atr[d] if > 0 else NaN)
EXIT: stop / target / flat 15:55.   POST: set_session('10:00', '10:01', exit_time); max_trades_day 1; Lucid block
```
Grid (<= 16): `n_down {1, 2}` x `vix_min {18, 22}` x `stop_atr {0.4, 0.8}` x `require_morning_down {True, False}` (+ one run `rsi2_max=10`).
Session rules: one 10:00 entry (no 09:30 longs); flat 15:55. Risk rules: stop 0.4-0.8 ATR in a high-vol regime (ES ATR 80-120 pts when VIX > 20 -> $160-480/MES) -> 2-4 micros; zero trades in calm years is expected (2017-like); report by VIX bucket; combine with `backwardation[d]` from spec 12 as the extra run.

## 14. academic_anomalies__gold_safe_haven_1000  (Baur-Lucey safe-haven day effect, intraday interpretation: when ES is down > 1% by 10:00 ET, long MGC 10:00 -> 15:55)

Priority **1**, complexity **2**, instrument MGC (signal from SPXUSD); bar size 1-min, cross-instrument. EQ 2 (gold's positive return on extreme equity down days is documented contemporaneously, not as an intraday rule; the 2025-26 gold uptrend makes any long-gold rule look good -> compare with an unconditional MGC 10:00-15:55 long control). Monthly gold/oil and gold/platinum predictors are dropped (oil not available 2024-2026, platinum not in the data, monthly horizon).

```
PARAMS: es_thresh_pct=1.0, signal_time='10:00', exit_time='15:55' | '13:25', stop_atr=0.5, control=False (True = trade every day: the benchmark), max_trades=1
PRE: ES = load_1m('SPXUSD', start, end); align by ts: es_ret[d] = ES close(09:59) / ES open(09:30) - 1 for the gold session d containing that timestamp
  atr = daily_atr(gold df1, 14, rth_only=False); trade[d] = (control or es_ret[d] <= -es_thresh_pct/100) and atr not NaN
ENTRY: place(i of the gold bar tod 10:00, +1, stop_pts = stop_atr*atr[d]);  EXIT: stop or flat at exit_time
POST: set_session('10:00', '10:01', exit_time); max_trades_day 1; Lucid block MGC
```
Grid (<= 8): `es_thresh_pct {0.7, 1.0}` x `stop_atr {0.5, 1.0}` x `exit_time {13:25, 15:55}` + the control run.
Session rules: entry 10:00, flat 13:25/15:55 (gold session allows later; keep equities-correlated hours). Risk rules: 10-25 signals/yr, stop 0.5-1.0 ATR ($40-120/MGC); only interesting if it beats the control by > 0.2%/trade on 2010-2026.

## 15. academic_anomalies__twap_trend_halfhour  (Zarattini-Aziz VWAP trend day-trading, OHLC-only approximation: TWAP of (H+L+C)/3 anchored 09:30, half-hour decision points, stop-and-reverse, flat 15:55) - FLAGGED approximation

Priority **1**, complexity **2**, instruments MNQ (QQQ evidence), MES; bar size 30-min decisions on 1-min data. EQ 3 for the volume-weighted original (QQQ 2018-23 +671%, MDD 9.4%); **the TWAP proxy is untested in the paper and is an approximation** (equal-weighted; the paper's VWAP leans on opening volume). The 1-min reversal version of the paper is not run (whipsaw/friction); half-hour decisions only, as the report recommends.

```
PARAMS: step=30, first_decision='10:00', last_decision='15:00', eps=0.0 (band around TWAP, fraction), hard_stop_atr=0.5, direction='both' | 'long_only', reverse=True, flat='15:55', max_trades=6
PRE: twap[d, t] = session_vwap(rth bars) (TWAP proxy); atr = ATR14d
LOOP at T = first_decision .. last_decision step 30: c = close(bar T-1); tw = twap[d, T-1]; i = i(bar T)
  if pos == 0:   if c > tw*(1+eps): place(i, +1, stop_px = c - hard_stop_atr*atr); pos=+1
                 elif c < tw*(1-eps) and direction=='both': place(i, -1, stop_px = c + hard_stop_atr*atr); pos=-1
  elif pos == +1 and c < tw*(1-eps): exit_at(i); pos = 0; if reverse and direction=='both': place(i+1, -1, stop_px = c + hard_stop_atr*atr); pos=-1
  elif pos == -1 and c > tw*(1+eps): mirror
POST: set_session(first_decision, last_decision + 1 min, flat); max_trades_day = max_trades; Lucid block (daily_loss_stop 1.0x, daily_profit_stop 1.0x)
```
Grid (<= 8): `eps {0.0, 0.001}` x `step {30, 60}` x `direction {both, long_only}`. Fixed hard stop 0.5 ATR.
Session rules: decisions 10:00-15:00; flat 15:55. Risk rules: expect 2-4 reversals/day = heavy friction; this is a *control for spec 1* (same decision clock, no noise band): if it matches spec 1, the band adds nothing; if spec 1 beats it clearly, the band is the edge.

---

## Dropped or folded (and why)

- **Market intraday momentum, first-half-hour sign rule (report #1):** dead OOS on SPY/QQQ/DIA (net -2.3 bp/day, t=-5.2, 2014-2026; QuantConnect 2015-20 Sharpe -0.63). Already implemented as `strategies/intraday_momentum.py` / `trend_momentum__last_half_hour`; keep that as the control for spec 5, do not re-spec.
- **Overnight (close-to-open) premium (report #8):** holding through the 17:00 daily close is prohibited; the 18:00 -> 09:30 slice is inside one CME session but the per-night edge (~2-3 bp) is below ES friction unless conditioned, which is spec 8. Dropped; the only lesson used is that unconditional intraday long bias has ~0 expected return (so every spec above has a control).
- **Overnight-gap fade / continuation (report #16):** gap-fill fade fails on MNQ 2022-25 (net -1.9 pts, T=-0.44) and `strategies/mr_gapfade.py` already exists; gap-continuation short needs a Kalman velocity filter and 35 trades (T=1.46) - not spec-worthy. The gap is used only as the anchor `max(O930, PC)/min(O930, PC)` inside spec 1.
- **NQ-ES lead-lag (report #18):** EQ 1, intraday lead-lag arbitraged to seconds; kept only as the optional `nq_es_rs` flag in spec 12.
- **Gold-oil / gold-platinum monthly ratios (report #19):** monthly horizon, oil missing 2024-2026, platinum not in the data. Only the intraday safe-haven interpretation (spec 14) is codeable.
- **Carry (report #20):** needs the futures curve (front/next) - not in the data; equity carry is ~0 in 2023-26 anyway. TSMOM bias is kept (spec 12).
- **Morning order-flow reversal (report #22):** signed order flow cannot be computed from OHLC; no faithful approximation exists. Dropped. The VWAP trend rule survives only as the flagged TWAP approximation (spec 15).
- **OU / 5-min mean reversion on MGC (report #14):** negative in every configuration (T -1.6 to -5.3, half-life ~8 h). Not specced.
- **Fast-alpha 5-minute reversal as a stand-alone (report #21):** gross ~1 bp per bar, negative after commissions; kept only as the execution overlay (spec 3).
- **Day-of-week / hour-of-day as a stand-alone (report #15):** filters only (spec 12 `dow_weight`, `no_long_0930`); never a grid dimension.

## Portfolio notes for the backtest agents (Lucid 50K Flex: $3,000 target, $2,000 EOD-trailing MLL, 50% consistency in eval)

- Backbone: spec 1 on MNQ (and/or MES) at 4-8 micros, spec 2 as the simpler fallback; both only enter from 09:45/10:00, hold hours, and are capped by the daily profit stop (~$1,200 at 10 micros) so no day is > 50% of the $3,000 target. Their losses are 0.35-0.6 ATR per trade, so the per-day loss floor ($600-900) is the sizing constraint, not the win rate.
- Independent small positive days for the payout rule (5 days >= $150): spec 7 (8/yr, half of them > $500 at 10 micros), spec 9 (10-25/yr), spec 5 (60-90/yr, small), spec 13 (high-vol regimes only). Their daily P&L is nearly uncorrelated with the trend backbone (different hours or different days); use `backtest.portfolio_opt` to size them jointly.
- Two account policies to simulate once a backbone is confirmed: (a) "fast eval" = backbone at the largest `recommended` size from `lucid_scan` plus all overlays, profit cap 1.5x, aim to pass in ~10-15 sessions, then drop to the funded contract cap (20 micros) with the 1.0x cap to lock the first payout; (b) "safe" = backbone at ~half that size, overlays at full size, profit cap 1.0x, daily loss stop 1.0x, aim for P(funded) maximised at any speed. Report P(pass), monthly pass rate, P(first payout), expected net per evaluation for both.
- Regime: do not switch the trend rules off in high VIX (their Sharpe rises with VIX); instead apply `regime_size`/`skip_day` from spec 12 and let the Lucid MC cap micros by the worst day. Every spec's 2010-2017 result should be ~flat for the trend rules (the sources say so); if it is strongly positive, suspect look-ahead.
