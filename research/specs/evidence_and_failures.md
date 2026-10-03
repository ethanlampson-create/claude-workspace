# Specs: Published backtests, forward-test results and documented failure modes (ES / NQ / MES / MNQ day-trading systems) for the Lucid 50K LucidFlex backtest

Source report: `/home/user/claude-workspace/research/families/evidence_and_failures.md` (read fully; sections 0-7).
Engine contract: `/home/user/claude-workspace/docs/STRATEGY_GUIDE.md`, `backtest/engine.py` (`Intents.place(idx, side, entry_px, valid_bars, stop_px, tgt_px, stop_pts, tgt_pts, trail_pts, trail_act_pts, max_hold, kind)`, `Intents.exit_at(idx, which)`, `Intents.set_session(entry_start, entry_end, flat_time)` (overnight windows supported), `max_trades_day`, `daily_loss_stop`, `daily_profit_stop`), helpers in `strategies/common.py` (`atr`, `ema`, `sma`, `rsi`, `adx`, `session_vwap` (TWAP proxy), `opening_range`, `overnight_range`, `daily_atr`, `prior_day_stats`, `vix_lag1`, `session_info`), `backtest.data.resample(df1, N, rth_only=...)` (adds `tod` = bar start, `i_first`, `i_last`, `i_next`; buckets are anchored at 18:00 so 15/30/60-minute bars sit on :00/:15/:30/:45 boundaries) and `backtest.data.daily_bars`.

What this family contributes that the other families do not: **the evidence on what fails and why**, plus the few things that survived a walk-forward with costs in 2023-2026. The headline (report section 0) is that every properly OOS-tested, OHLC-only, single-bar intraday ES/NQ rule is either inside costs or decayed to <= 0 in 2025-26; what survived uses (a) 60-120-minute holds or fixed targets instead of next-bar exits, (b) regime / day-type gates, (c) exact-bar entries, (d) long bias on NQ setups, (e) one-loss-per-session and small daily caps. The specs below are therefore of three kinds: **re-tests of the near-misses and positive controls** (Mesfin ORB-75, gap-velocity short, London regime long, RTH pullback mechanic, NQ nested FVG), **reusable gates and mechanics** (day-type gates, exit bake-off), and **cheap negative controls** (close momentum) that the backtest loop needs as calibration. A dropped list with reasons is in section 12, and the validation / cost protocol every spec must pass is in section 13.

## 0. Conventions used by every spec below

**Times**: all ET. Data session 18:00 -> 17:00 (equity CFD feed stops ~16:14). RTH equities 09:30-16:00; gold pit 08:20-13:30 (gold trades ~23h). A 1-minute bar with `tod = T` covers `[T, T+1)`. A decision taken on the close of the bar with `tod = T-1` is executed at the bar with `tod = T` (`i_next`): **market at next 1-minute open (+1 tick slippage)** unless the spec says `kind='stop'` or `kind='limit'`. On N-minute bars `B = resample(df1, N, ...)` the decision uses the N-bar close and the order index is `B.i_next[k]` (skip `-1`: the session ended). Rolling indicators use `min_periods` = full window; NaN rows never trade. `max_hold` is counted in **1-minute bars from the fill bar** (so "hold 75 minutes" = `max_hold=75`).

**Forced flat**: equities **15:55** (never later than 15:58) unless the published rule is earlier (spec 5 keeps 15:45). Pre-market spec (3) is flat by **08:30**. Gold pit specs 13:25. No overnight, no weekends.

**Exact-bar entry rule (mandatory for this family)**: the report documents two sign flips caused by entry delay (London Signal B: T +4.30 -> -2.78 with one 15-minute bar delay; Asia expansion bars: open-to-next-open +32 pts vs close-to-next-open -0.17). Every spec enters at `i_next` of the signal bar (the very first 1-minute bar after the signal bar closes) or with a resting order placed at that index. Never add a "confirmation" bar. Each spec also runs a `delay=1` sensitivity (shift the order index by one signal bar): a result that *survives* a delay is more trustworthy; one that flips is a bar-boundary artefact and gets a haircut.

**Costs per micro, per round trip, already in the engine** (`backtest/contracts.py`): MES $2.50 slippage + $1.30 commission = $3.80 (0.76 pt); MNQ $1.00 + $1.30 = $2.30 (1.15 pt); MGC $2.00 + $1.30 = $3.30 (0.33 pt). Lucid's published commission is $0.50/side on micros so the engine is slightly conservative. **Stress run**: `engine.run(..., slip_ticks=2)` (= MNQ 2.15 pts RT, the Mesfin 2.0-pt floor). Deployability (report section 4): mean gross P&L per trade >= 2x stress RT (>= 2.8 MES pts, >= 4 MNQ pts, >= 1.0 MGC pt) and **median initial stop >= 5x RT cost** (>= 4 MES pts, >= 6 MNQ pts, >= 2 MGC pts); any spec whose grid can produce smaller stops carries a `min_stop_pts` guard.

**Lucid risk block** (default for every spec unless overridden; values per ONE micro contract; the Lucid Monte Carlo scales 5-40 micros). This family's evidence (report section 0 item 5 and section 6 item 5) argues for a *smaller* daily loss cap than the sibling spec files so that a 5-6-day losing streak stays well under the $2,000 EOD-trailing floor:
- `daily_loss_stop`: MES $35, MNQ $40, MGC $40 (grid multiplier `dls_mult {1.0, 2.0}`). At 10 micros = $350-$800/day; six straight max-loss days at 1.0x = $2,100-$2,400 but the EOD trailing floor only moves up on winning days, so the realistic streak cost is < $1,500.
- `daily_profit_stop`: MES $50, MNQ $60, MGC $60 (grid multiplier `dps_mult {1.0, 2.0, none}`). At 10 micros ~$500-$1,200/day, keeping the best eval day near $600 so the 50% consistency rule is met by day 6-10 instead of fought, and so the funded phase collects many >= $150 days.
- Engine semantics: both stops look at **realized** P&L only and only block **new** entries; every entry therefore carries a hard protective stop (never a stop-less position in a prop account). `max_trades_day` as specified; `one_loss` = `max_trades_day` plus a daily loss stop at one R so a second trade after a full loss is blocked.
- One position at a time; always `set_session(entry_start, last_entry, flat)`.
- News blackout (08:30 / 10:00 / 14:00 +/-2 min) is NOT implemented (no calendar in the data). Pre-market spec 3 stops entering at 07:30 and is flat by 08:30 so the 08:30 prints are never held.

**Indicator definitions (exact)**:
- `ATR14d = daily_atr(df1, 14, rth_only=True)` (Wilder ATR of RTH daily bars, shifted one day: day d uses days < d). `ATR_N(n)` = `common.atr` on N-minute bars (Wilder, EWM alpha 1/n, min_periods n).
- `D = daily_bars(df1, rth_only=True)`; `O930[d] = D.open`; `prev_close[d] = D.close.shift(1)`; `pd_high / pd_low` = `prior_day_stats` (prior RTH high/low); `SMA200_D = sma(D.close, 200).shift(1)`.
- `gap[d] = O930[d] / prev_close[d] - 1`; `r30[d] = close(tod 09:59) / prev_close[d] - 1` (prev-close-anchored first-30-minute return, as in Gao et al.); `r_to1530[d] = close(tod 15:29) / prev_close[d] - 1`.
- `clpos` = `(close - low) / (high - low)` (0.5 when `high == low`). `ret_N` = `close / close.shift(1) - 1` on N-minute bars.
- `range_z(n)` on N-minute bars = `(range - rolling_mean(range, n)) / rolling_std(range, n)` with `range = high - low`, **the OHLC-only proxy for a volume z-score** (flagged wherever used; bar range and bar volume are positively correlated but not identical).
- `OLS_slope(x)` = least-squares slope of the series x against 0..len(x)-1.
- `expanding_q(x, q, min_n)` = q-quantile of x over all days strictly before d, NaN until min_n days exist.
- `VIX_lag = vix_lag1(df1)` (prior-day VIX close).
- `R` = |entry_ref - initial stop| in points; `entry_ref` = the deciding close (market orders) or the order level (stop/limit).
- Instrument point scalers used where the published rule is in NQ points: `PT = {MNQ: 1.0, MES: 0.28, MGC: 0.12}` (ES ~ 6,700 vs NQ ~ 24,500 in 2026 -> 0.27; gold ~ 3,000 but ~0.5x the daily % range of NQ -> 0.12). A rule "25 NQ pts" becomes `25 * PT[contract]`.

**Evidence quality (EQ)**: 1 anecdote/vendor claim; 2 single self-reported test, no costs or no OOS; 3 independent test with costs, one market/period; 4 multiple independent tests with costs; 5 peer-reviewed + OOS replications. **Priority** 5 = best prior under Lucid constraints with evidence, 1 = long shot. **Complexity** 1 = a few lines on existing helpers, 5 = multi-state intraday machine.

**Overlap with other spec files**: `trend_momentum__noise_area` and `bot_popular_indicators__noise_area_1m_bands` already specify the Zarattini noise-area system; spec 6 here is deliberately the *timed / vol-gated* variant the report recommends and keeps its own id. `strategies/orb_sma_rr.py` and `strategies/orb_reclaim.py` already exist (SMA200-filtered ORB with R exits; London reclaim); spec 1 is the Mesfin *time-exit* ORB and is different. Gap-fade (`mr_gapfade.py`) exists and is a documented failure in this family (not re-specified).

---

## 1. evidence_and_failures__orb_long_75min  (Mesfin ORB long, 25-minute OR, 75-minute time exit; near-miss, positive in every OOS year)

Priority **3**, complexity **2**, instruments MNQ (published), MES; bar size 5-minute signal bars on 1-minute data. EQ **4** (pre-registered walk-forward with 2.0-pt friction: OOS N=447, net +2.82 pts/trade, gross +4.82, by year +2.43 / +7.04 / +15.05, but T=0.88 so it failed the author's gate). Why re-test: positive every OOS year, the only ORB variant with a positive OOS mean, and the ORB family report found that an SMA200 daily trend filter plus a one-loss-per-session rule made a related variant survive; our 1-minute history 2010-2026 triples N. Shorts are NOT specified (OOS -2.16 / -3.45 pts, T -3.16).

Data gap: none (OHLC only).

```
PARAMS (defaults = Mesfin): or_start='09:30', or_minutes=25, hold_min=75, trend_filter='none' | 'sma200',
  stop_mode='or_low' | 'atr', stop_atr=0.5, last_entry='11:30', max_trades=1, skip_vvg=False, entry_bar=5
PRE:
  B5 = resample(df1, 5, rth_only=True)                    # continuous 5-minute RTH bars
  OR = opening_range(df1, or_start, or_minutes)           # or_high, or_low, i_end per day_id (valid only after i_end)
  atr = ATR14d; sma200 = SMA200_D; vvg = day_type_gates.vvg_big_day (spec 7) if skip_vvg
PER SESSION d:
  if atr[d] is NaN or (trend_filter=='sma200' and (sma200[d] is NaN or prev_close[d] <= sma200[d])): skip day
  if skip_vvg and vvg[d]: skip day
  for k in 5-min bars of day d with B5.tod[k] >= or_start + or_minutes and B5.tod[k] + 5 <= last_entry:
      if B5.close[k] > or_high[d]:                        # first 5-min CLOSE above the OR high (signal at bar close)
          i = B5.i_next[k]; if i == -1: break
          c = B5.close[k]
          stop = or_low[d]                                 if stop_mode == 'or_low'
               = c - stop_atr * atr[d]                     if stop_mode == 'atr'
          stop = min(stop, c - min_stop_pts)               # min_stop_pts: MNQ 6, MES 4, MGC 2 (5x RT cost)
          place(i, +1, stop_px=stop, max_hold=hold_min)   # market at next open, time exit after hold_min 1-min bars
          break                                           # one entry per day (Mesfin); max_trades grid allows a re-entry
SESSION: set_session(or_start + or_minutes, last_entry, '15:55'); max_trades_day = max_trades; Lucid risk block.
NOTE: no profit target (pure time exit as published). Entry at exact i_next; delay=1 sensitivity run as in section 0.
```
Grid (24 combos): `hold_min {60, 75, 120}`, `trend_filter {none, sma200}`, `stop_mode {or_low, atr(0.5)}`, `skip_vvg {False, True}`. Fixed: or 25 min, last_entry 11:30, max_trades 1 (one extra run with `max_trades=2`, `dls_mult=1.0`, i.e., one loss ends the day).

Risk: initial stop = OR range below the breakout close (MNQ typically 40-120 pts = $80-240 per micro at 2025-26 OR sizes; the ATR mode is ~0.5 x 300 = 150 pts): this is a wide-stop system, expect the Lucid scan to settle at 3-6 micros. Daily loss stop 1.0x block (one full stop ends the day anyway); daily profit stop 2.0x block (a 75-minute hold on a trend morning is where this system makes its year).

Evidence recap and what must be true: Mesfin OOS +2.82 net at 2.0-pt friction; year-by-year positive. On our data require positive net in each of 2023/2024/2025/2026 at base costs, >= 30 trades/year, and gross/trade >= 4 MNQ pts; expect the ORB report's SMA200 + one-loss variant to be the surviving corner of the grid.

## 2. evidence_and_failures__gap_velocity_short  (Mesfin gap-continuation short via first-30-minute velocity z-score; near-miss, rare)

Priority **2**, complexity **3**, instruments MNQ (published), MES; bar size 1-minute. EQ **3** (walk-forward OOS N=35: net +14.52 pts, gross +16.53, T 1.46, by year +14.53 / -11.87 / +10.27; fails year stability and N per fold; the author names it the best candidate for more data). Our 2010-2026 1-minute history exists precisely to fix the N problem.

Data gap: the paper uses a Kalman-filter velocity on 1-minute closes; this spec uses the standard approximation named in the report (**OLS slope of the 1-minute closes 09:30-09:59, standardised by its trailing 60-day distribution**), flagged. The approximation is faithful in spirit (both measure the signed speed of the first 30 minutes) but not numerically identical.

```
PARAMS (defaults = Mesfin where known): z_thr=2.5, z_lookback=60 (days), side='short' | 'both', hold_min=75,
  exit='time' | 'close', stop_atr=0.5, tgt_atr=None, require_gap=True, entry_time='10:00', max_trades=1
PRE (per session d):
  x[d] = closes of the 30 one-minute bars 09:30..09:59 (skip day if fewer than 28 bars)
  slope[d] = OLS_slope(x[d]) / O930[d]                   # fractional price change per minute, signed
  z[d] = (slope[d] - mean(slope[d-z_lookback .. d-1])) / std(slope[d-z_lookback .. d-1])   # strictly past days
  g[d] = gap[d]; atr = ATR14d[d]
SIGNAL at 10:00 (decision on the close of the 09:59 bar; i = index of the bar with tod 10:00):
  short if z[d] <= -z_thr and (not require_gap or g[d] < 0)
  long  if side=='both' and z[d] >= +z_thr and (not require_gap or g[d] > 0)
  c = close(09:59)
  stop_px = c + stop_atr*atr (short) / c - stop_atr*atr (long); stop distance >= min_stop_pts (MNQ 6 / MES 4)
  tgt_px  = c -/+ tgt_atr*atr if tgt_atr else NaN
  place(i, side, stop_px=stop_px, tgt_px=tgt_px, max_hold = hold_min if exit=='time' else 0)   # exit=='close' -> flat 15:55
SESSION: set_session('10:00', '10:01', '15:55'); max_trades_day = 1; Lucid risk block.
```
Grid (36 combos): `z_thr {1.5, 2.0, 2.5}`, `side {short, both}`, `hold_min {75, 180}` x `exit {time, close}` collapsed to `exit {time75, time180, close}`, `tgt_atr {None, 1.0}`. Fixed: lookback 60, require_gap True (one run with False), stop_atr 0.5.

Risk: single-trade SD in the paper is 59 MNQ pts ($118 per micro): at 10 micros one trade is +/- $1,180, which can breach the eval consistency cap on its own, so `daily_profit_stop` is irrelevant (one trade/day) and sizing must come from the Lucid scan (expect 3-5 micros). Daily loss stop 1.0x block. Stop 0.5 x ATR14d (~150 MNQ pts) is large; `stop_atr {0.35, 0.5}` may be added if the first pass has too few stop-outs to matter.

Evidence recap: ~10-12 trades/year at z 2.5; z 1.5-2.0 should give 30-60/year. Validation gate: positive net in >= 3 of 4 years 2023-2026 with >= 25 trades/year at z <= 2.0; if the only profitable corner is z 2.5 with N < 30 this is dropped exactly as the paper did.

## 3. evidence_and_failures__london_regime_long  (Mesfin London Session Signal B: regime-transition long, 03:00-08:30 ET, 60-minute hold; positive control)

Priority **3**, complexity **4**, instruments MNQ (published), MES; MGC optional (03:00-08:00, flat 08:15, no published evidence). Bar size 15-minute (non-RTH resample). EQ **3** (walk-forward OOS N=247, net +4.09 pts, T 4.30, p 0.000025, win 61.5%, T 3.87-4.83 across parameter variations, unconditional long benchmark -0.47 pts; single author, and a one-bar delay flips the sign to T -2.78).

Data gap (flagged): the paper's 5 GMM features include a **volume z-score**; we substitute `range_z(50)` on 15-minute bars. The paper's regimes come from a 3-component GMM refit per walk-forward fold. Two implementations are specified: **(A) deterministic regime proxy** (default, no ML dependency, reproducible) and **(B) GMM** (optional, `sklearn.mixture.GaussianMixture`, refit on data strictly before each calendar year). A is the primary spec because the loop needs something debuggable first; B is the faithful-structure version.

```
PARAMS: bar=15, win_start='03:00', win_end='08:30', last_entry='07:30', hold_min=60, stop_pts=20*PT (MNQ 20, MES 5.6, MGC 2.4),
  z_window=100 (bars), ret_z_thr=0.5, atr_z_r1=1.5, act_z_r1=2.0, clpos_min=0.6, dc_min=0.5, regime_impl='rule' | 'gmm'
PRE:
  B = resample(df1, 15, rth_only=False)                   # continuous 15-min bars across the whole 18:00-17:00 session, all days
  features per bar k (all use bars <= k only):
    atr_ratio[k] = ATR_15(5)[k] / ATR_15(20)[k]
    act[k]       = range_z(50)[k]                          # VOLUME PROXY (flagged)
    clpos[k]     = (close-low)/(high-low)
    ret[k]       = close[k]/close[k-1] - 1
    dc[k]        = mean(sign(ret[k-3..k]))                 # signed directional consistency in [-1, +1]
  z-scores: z_atr, z_act, z_ret = rolling z over z_window bars of atr_ratio, act, ret (min_periods z_window)
  REGIME (impl 'rule'):
    R1 (extreme vol)   if z_atr[k] > atr_z_r1 or z_act[k] > act_z_r1
    R2 (bullish drift) elif z_ret[k] > ret_z_thr and clpos[k] >= clpos_min and dc[k] >= dc_min
    R0 (bearish chop)  elif z_atr[k] <= 0.5 and (ret[k] <= 0 or dc[k] <= 0)
    N  (neutral)       otherwise
  REGIME (impl 'gmm'): for each calendar year Y, fit GaussianMixture(3, full cov, seed 0) on the StandardScaled 5-feature
    vectors of all London-window bars in years < Y (min 1 year); predict labels for year Y; map the component with the highest
    mean z_atr -> R1, of the other two the one with the higher mean dc -> R2, the remaining -> R0 (no N state).
SIGNAL on 15-min bar k with win_start <= B.tod[k] and B.tod[k] + 15 <= last_entry:
  if label[k] == R2 and label[k-1] == R0 and label[k-2] != R1:      # clean R0 -> R2 transition, no R1 in the prior two bars
      i = B.i_next[k]; if i == -1: skip
      place(i, +1, stop_px = B.close[k] - stop_pts, max_hold = hold_min)   # market at the exact next 1-min open; time exit
SESSION: set_session(win_start, last_entry, win_end)      # last entry 07:30 so a 60-min hold ends by 08:30; flat 08:30 (before the 08:30 prints)
  max_trades_day = 2 (paper allows multiple transitions per session); Lucid risk block.
  Gold: win 03:00-08:00, last_entry 07:00, flat 08:15.
DELAY TEST (mandatory): rerun with i = B.i_next[k+1]; the paper's edge flips sign. If ours does not flip, the proxy is not reproducing the paper's mechanism (report it either way).
```
Grid (24 combos, impl 'rule'): `z_window {50, 100}`, `ret_z_thr {0.5, 1.0}`, `stop_pts {20, 40} x PT`, `hold_min {45, 60, 90}`. Then one `impl='gmm'` run at defaults.

Risk: fixed 20 MNQ-pt stop = $40 per micro (median stop >= 5x RT cost: yes); daily loss stop 1.0x block = one loss ends the session; daily profit stop 1.0x block. ETH slippage: run the stress case `slip_ticks=2` as the headline number for this spec (the report recommends 2-3 ticks in ETH).

Evidence recap: +$8/contract/trade, ~80 trades/year, ~61% win. Target on our data: >= 50 trades/year, win >= 55%, net >= 3 MNQ pts/trade at base costs and >= 2 at stress costs, positive in each of 2023-2026.

## 4. evidence_and_failures__rth_pullback_limit  (Mesfin RTH Confluence mechanic stripped of the volume/Markov gates: ATR-scaled limit pullback after an up-bar, 65-minute hold)

Priority **2**, complexity **3**, instruments MNQ (published), MES; bar size 5-minute RTH bars on 1-minute data. EQ **3** for the published signal (OOS N=196, +11.82 pts, T 3.11, 2025 OOS +13.14) but **the published signal is NOT reproducible here**: two of its three gates (50-bar volume z > 0.5, GMM regime with a volume feature) and the Markov transition gate (P(1->2) > 0.15 over 200 bars of GMM labels) need volume. What is kept is the *mechanic* the author's own unconditional benchmark isolates (unconditional 09:30 long with a 13-bar hold: -2.60 pts): an ATR-scaled resting limit below an "active flow" bar, 65-minute hold, ATR-scaled stop. This spec tests whether that mechanic alone, with an OHLC activity gate, has any value. Treat as a long shot; the author also reports 53+ parameter combinations searched.

Data gap (flagged): volume z replaced by `range_z(50)` on 5-min bars; GMM regime 1 replaced by a rule; Markov gate dropped.

```
PARAMS: pull_pts=25*PT, stop_pts=80*PT, valid_min=30 (6 five-min bars), hold_min=65, act_z_min=0.5, clpos_min=0.6,
  atr_lo=0.8, atr_hi=2.0, entry_start='09:35', last_signal='14:30', max_trades=2
PRE:
  B5 = resample(df1, 5, rth_only=True)
  atr1 = ATR on 1-minute bars, n=20, evaluated at B5.i_last[k]            # paper: 20-bar ATR on 1-min bars
  base[d] = median over the 60 RTH sessions before d of atr1 at 10:00      # replaces the paper's fixed 10.34 baseline (look-ahead)
  atr_ratio[k] = clip(atr1[k] / base[d], 0.5, 2.0)
  act[k] = range_z(50) on B5 (VOLUME PROXY); clpos[k]; ret5[k]
SIGNAL on 5-min bar k (tod in [entry_start, last_signal)):
  active_flow = ret5[k] > 0 and clpos[k] >= clpos_min and atr_lo <= atr_ratio[k] <= atr_hi and act[k] > act_z_min
  if active_flow:
      i = B5.i_next[k]; if i == -1: skip
      px = B5.close[k] - pull_pts * atr_ratio[k]
      place(i, +1, entry_px=px, kind='limit', valid_bars=valid_min,
            stop_px = px - max(stop_pts * atr_ratio[k], min_stop_pts), max_hold = hold_min)
      (engine: limit fills only on a 1-tick trade-through; cancelled after valid_min bars; one pending order at a time)
SESSION: set_session(entry_start, last_signal, '15:55'); max_trades_day = max_trades; Lucid risk block.
NOTE: paper exits at bar 13 from the SIGNAL bar open; the engine counts max_hold from the FILL, so holds are up to 30 min longer than the paper's (flagged); grid hold {45, 65} brackets it.
```
Grid (24 combos): `pull_pts {15, 25} x PT`, `stop_pts {40, 80} x PT`, `hold_min {45, 65}`, `act_z_min {0.0 (gate off), 0.5}` (Swanson independent-filter test of the range gate), `clpos_min {0.6}` fixed, plus `max_trades {1, 2}` in a second pass only on the best corner.

Risk: 80 x ratio MNQ pts = $160 per micro per stop at ratio 1 (too large above ~6 micros); the 40-pt corner is the prop-sized one. Daily loss stop 1.0x; daily profit stop 2.0x (single-trade SD in the paper is $108 per micro).

Evidence recap: paper +$23.6/MNQ/trade, ~55 trades/year, 61% win. Pass bar here: positive net in 2025 and 2026 separately and in 2023-24 combined, >= 40 trades/year, and the `act_z_min=0.5` gate must improve PF over `0.0` (otherwise it is noise and the spec collapses to "buy pullbacks after up bars", which the author's benchmark says is negative).

## 5. evidence_and_failures__fvg_nested_long  (NQ "Strategy B": 5-minute bullish FVG nested inside a 15-minute bullish FVG, long only, 2R, 09:30-12:00, flat 15:45)

Priority **4**, complexity **4**, instruments MNQ (published), MES; bar size 5-minute + 15-minute RTH bars on 1-minute data. EQ **2** (single author, full-sample, fees included but slippage unstated, no walk-forward; rising win rate 46 -> 68% from 2023 to 2026 is a tuning red flag). It is nevertheless the **best-shaped candidate in the family** for Lucid: ~0.5 trades/day, 53-57% win, 2R, max DD < $800 per micro, 35/41 months profitable, 2025: +$6,623 per MNQ with DD $786. Must be re-derived on our data with the walk-forward in section 13 before any number is trusted.

Data gap: none (OHLC only; FVG = 3-bar gap pattern).

```
PARAMS (defaults = README): rr=2.0, buffer_pts=5*PT, stop_off_pts=2*PT, min_gap5=2*PT, min_gap15=5*PT, max_age5=36 (5-min bars),
  max_age15=24 (15-min bars), entry_start='09:30', last_entry='12:00', flat='15:45', max_trades=2, side='long',
  same_session_only=False, min_R=8*PT, max_R=60*PT
PRE:
  B5 = resample(df1, 5, rth_only=True); B15 = resample(df1, 15, rth_only=True)      # continuous across sessions (RTH chart)
  FVG definition on a bar series X (bullish): at bar j, if X.low[j] > X.high[j-2] + min_gap:
      zone = {bottom: X.high[j-2], top: X.low[j], born_i: X.i_last[j], age0: j}
    bearish (side 'both' only): X.high[j] < X.low[j-2] - min_gap: zone = {bottom: X.high[j], top: X.low[j-2]}
  ACTIVE rule (bullish): zone is active from bar j+1 until the first later bar with low <= bottom (fully filled -> dead),
      or age > max_age bars; if same_session_only, zones die at session end.
  F5 = all 5-min bullish FVGs; F15 = all 15-min bullish FVGs (same rule with min_gap15, max_age15)
SIGNAL on 5-min bar k with entry_start <= B5.tod[k] and B5.tod[k] + 5 <= last_entry (bars completing by 12:00):
  cands = { f in F5 active at k, f.born_i < B5.i_first[k],                                # formed before bar k opened
            exists F in F15 active at k with F.born_i < B5.i_first[k]                    # 15-min zone completed before bar k
                   and f.bottom >= F.bottom and f.top <= F.top + buffer_pts,            # 5-min FVG inside the 15-min FVG (5-pt buffer at top)
            B5.low[k] <= f.top and B5.low[k] > f.bottom,                                 # bar k dips INTO the 5-min FVG (not through it)
            B5.close[k] > f.top }                                                        # and closes back above it
  if cands: f = the candidate with the highest top (nearest zone)
      i = B5.i_next[k]; if i == -1: skip
      c = B5.close[k]; stop = f.bottom - stop_off_pts; R = c - stop
      if R < min_R or R > max_R: skip                                                     # cost-floor guard and sanity cap (flagged deviation from README)
      place(i, +1, stop_px=stop, tgt_px = c + rr*R)                                       # market at next open; 2R target; flat 15:45
  side=='both': mirror with bearish zones (README: shorts 42.5% win -> expect to reject).
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = max_trades; Lucid risk block.
```
Grid (36 combos): `rr {1.5, 2.0, 3.0}`, `buffer_pts {5, 10} x PT`, `max_age5 {24, 72}` (with max_age15 = max_age5 x 2/3), `max_trades {1, 2}`, `same_session_only {False, True}` collapsed into the age axis as `{24 same-session, 36 continuous, 72 continuous}` -> 3 x 2 x 3 x 2 = 36. One extra run `side='both'` at defaults.

Risk: R is typically 10-30 MNQ pts ($20-60 per micro) in 2025-26 -> prop-friendly at 10-20 micros; min_R 8 pts enforces median stop >= 5x RT. Daily loss stop 1.0x block (= roughly one full-R loss on 1-2 micros... at 10 micros a $400 cap allows one 20-pt loss, which is the intended one-loss rule); daily profit stop 1.0x block ($600 at 10 micros ~ one 2R winner on 15 micros). Flat 15:45 as published.

Evidence recap: 2023 +$1,974 / 2024 +$5,430 / 2025 +$6,623 / 2026 (4 mo) +$3,319 per MNQ, max DD $786. On our data require: positive in each of 2023/2024/2025/2026, PF >= 1.3 with >= 100 trades/year, win >= 50%, and parameter plateau across rr 1.5-3 and buffer 5-10. Apply the 1.5-2.5x haircut the author expects before sizing.

## 6. evidence_and_failures__noise_band_timed  (Zarattini noise-area breakout, VIX/ATR-gated, fixed ATR target or 90-120-minute time exit instead of EOD band-trailing)

Priority **2**, complexity **3**, instruments MNQ, MES; bar size 1-minute. EQ **4** for the in-sample effect and **4 for its decay** (two independent replications: OOS Sharpe 0.39 in 2024-26, ES 2025 Sharpe -0.27, 2026 YTD -1.91; the brusco VIX-regime tables show the edge lived in VIX > 20). This spec is the salvage the report proposes: keep the noise band as the breakout definition, add the vol gate, and replace the EOD/band-trailing exit (41-45% win, fat right tail) with the fixed-target / timed exits the Davey study and the Lucid payout shape favour. Sibling specs cover the paper's own exits; do not duplicate them.

Data gap: none (band variant; VWAP not used).

```
PARAMS: lookback=14 (days), vm=1.0, gate='vix' | 'atr' | 'none', vix_min=20, atrpct_min=0.9 (% of close, NQ; ES 0.6),
  first_entry='10:00', last_entry='14:30', exit='target' | 'time', tgt_atr=0.5, hold_min=90, hard_stop_atr=0.5, long_only=False, max_trades=2
PRE (per session d, RTH 1-min bars 09:30 <= tod < 16:00):
  move[d, t] = | close(bar tod t) / O930[d] - 1 |;   M = pivot(day_id x tod)
  sigma[d, t] = M.rolling(lookback, min_periods=lookback).mean().shift(1)[d, t]        # days < d only
  UB[d, t] = max(O930[d], prev_close[d]) * (1 + vm*sigma[d, t]);  LB[d, t] = min(O930[d], prev_close[d]) * (1 - vm*sigma[d, t])
  allowed[d] = sigma ok and ATR14d ok and (gate=='none' or (gate=='vix' and VIX_lag[d] >= vix_min)
               or (gate=='atr' and 100*ATR14d[d]/prev_close[d] >= atrpct_min))
SIGNAL on 1-min bar t (first_entry <= tod < last_entry), once per direction per day:
  if close[t] > UB[d, t] and close[t-1] <= UB[d, t-1] (first upward cross of the day):
      i = t+1; c = close[t]; place(i, +1, stop_px = c - hard_stop_atr*ATR14d[d],
            tgt_px = c + tgt_atr*ATR14d[d] if exit=='target' else NaN, max_hold = hold_min if exit=='time' else 0)
  if not long_only and close[t] < LB[d, t] and close[t-1] >= LB[d, t-1]: mirror short
SESSION: set_session(first_entry, last_entry, '15:55'); max_trades_day = max_trades; Lucid risk block.
```
Grid (36 combos): `gate {none, vix20, atr}`, `exit {target(0.5 ATR), target(1.0 ATR), time90}`, `hard_stop_atr {0.35, 0.5}`, `long_only {False, True}`. Fixed: lookback 14, vm 1.0, max_trades 2.

Risk: stop 0.35-0.5 x ATR14d (~100-150 MNQ pts, $200-300 per micro) -> 3-6 micros; daily loss stop 1.0x; daily profit stop 2.0x. The `gate='none'` corner is the control that must reproduce the published 2025-26 decay (if it does not, the implementation is wrong).

Evidence recap: expected to be flat-to-negative ungated in 2025-26; the question is whether `vix20` or `atr` gating with a fixed target gives >= 30 trades/year with PF >= 1.3 in 2025Q1-Q2 and 2026Q1 while staying flat in 2025Q3.

## 7. evidence_and_failures__day_type_gates  (reusable no-trade / mode gates: VVG big-day skip, range-regime persistence, volatility floor)

Priority **3**, complexity **2**, instruments all; bar size daily + first 30 minutes. EQ **3** (VVG: 77.6% of flagged days reverse from their intraday peak, arXiv 2605.11423; range persistence 58.9% and regime lens 65.2% walk-forward, Matswm86; vol floor is Hart's method, EQ 2; the local 2025Q3 RV 8.9% dead zone is computed from workspace data). Not a strategy: a module `strategies/common_gates.py`-style set of per-day boolean series that other specs import (`skip_vvg` in spec 1, `gate` in spec 6), validated the Swanson way (each gate alone against each baseline strategy; keep only gates that raise both PF and net/max-DD; never stack more than two).

Data gap: the VVG classifier's third condition (first-bar volume vs 20-day baseline) is dropped; the OHLC-only version uses |gap| and |first-30| terciles only (the report says this is acceptable for a risk filter).

```
PRE (daily, per session d; all inputs strictly before the gate's decision time):
  gap[d], r30[d] as in section 0; rng[d-1] = pd_high - pd_low (prior RTH range)
GATE 1 vvg_big_day[d]   (decision time 10:00; affects entries with tod >= 10:00 only):
  qg = expanding_q(|gap|, 2/3, min_n=120); qr = expanding_q(|r30|, 2/3, min_n=120)        # expanding-window top terciles (days < d)
  vvg_big_day[d] = |gap[d]| >= qg[d] and |r30[d]| >= qr[d]                                 # ~11% of days OHLC-only (4.4% with volume)
  usage: allow_entry[i] &= not (vvg_big_day[d] and tod[i] >= 10:00)   (breakout systems);  mean-reversion systems may invert it
GATE 2 range_regime[d]  (decision time pre-open):
  med[d] = median(rng[d-20 .. d-1]);  ratio = rng[d-1] / med[d]
  regime[d] = WIDE if ratio > 1.1, NARROW if ratio < 0.9, else NOCALL                      # persistence baseline (~59%)
  usage: breakout specs trade only on WIDE or NOCALL; mean-reversion specs only on NARROW or NOCALL (grid `regime_gate {off, on}`)
GATE 3 vol_floor[d]     (decision time pre-open):
  atrpct[d] = 100 * ATR14d[d] / prev_close[d]
  vol_floor[d] = atrpct[d] >= thr[contract]   (thr: MES 0.6, MNQ 0.9, MGC 0.8)  or  VIX_lag[d] >= 14
  usage: allow_entry &= vol_floor[d] for every breakout / momentum spec; expect the gate to switch systems off for most of 2025Q3.
VALIDATION: for each gate g and baseline s in {orb_long_75min, fvg_nested_long, noise_band_timed}: run s with and without g on
  2023-01..2026-09; keep g for s only if PF and net/maxDD both improve and trade count stays >= 70% of the ungated count.
```
Grid: `vvg_q {0.6, 0.667}`, `regime band {+/-10%, +/-20%}`, `vol thr {0.8x, 1.0x of the table}`; evaluated only through the validation loop above (no standalone P&L).

Risk: none directly; a gate that removes > 30% of trades without improving net/DD is rejected (Swanson: stacked filters hide effects).

## 8. evidence_and_failures__close_momentum_vixgate  (Gao-Han-Li-Zhou / Baltussen last-30-minute momentum, VIX-gated; negative control)

Priority **1**, complexity **1**, instruments MES, MNQ; bar size 1-minute. EQ **5** for the 1993-2020 papers, **1-2 for 2023-2026** (local check: first-30 -> last-30 same-sign 44.8-50.2%, to-15:30 -> last-30 correlation -0.08..+0.06 since 2024; mean last-30 move 17 bps). Included because it costs ten lines, gives one trade per day, and is the calibration case the backtest loop needs: if this shows an edge on 2025-26 at base costs, the cost model or the look-ahead guards are broken.

Data gap: none (dealer gamma is not available; the VIX gate stands in for "negative-gamma / high-vol days").

```
PARAMS: signal='to1530' | 'first30', vix_min=None | 25, min_abs_ret=0.003, stop_atr=0.25, entry_time='15:30', flat='15:55'
PRE (per session d): r = r_to1530[d] if signal=='to1530' else r30[d];  allowed = (vix_min is None or VIX_lag[d] >= vix_min) and |r| >= min_abs_ret
SIGNAL at 15:30 (i = index of the bar with tod 15:30; c = close(15:29)):
  if allowed: place(i, sign(r), stop_px = c - sign(r)*max(stop_atr*ATR14d[d], min_stop_pts))      # no target; flat 15:55
SESSION: set_session('15:30', '15:31', flat); max_trades_day = 1; Lucid risk block (daily stops irrelevant with one trade).
```
Grid (12 combos): `signal {to1530, first30}`, `vix_min {None, 20, 25}`, `min_abs_ret {0.0, 0.003}`.

Risk: 25-minute hold, 0.25-ATR stop (~75 MNQ pts); expect ~0 net; one trade/day.

Evidence recap: expected result on 2025-26 is PF ~1.0 ungated; a VIX >= 25 gate selects ~25 days/year (2025Q2, 2026Q1). Pass bar is the same as every spec; it is listed to be *failed* on purpose, which is informative.

## 9. evidence_and_failures__pdh_break_retest  (ICT previous-day-high break-and-retest, optional "Silver Bullet" hour windows)

Priority **2**, complexity **3**, instruments MNQ (published), MES; bar size 5-minute RTH bars on 1-minute data. EQ **1** (asiatrada README: 61% win, PF 1.89 on a 60-day sweep, no costs, no dates, no OOS; numbers are marketing until re-tested). Included because the rule is objective, overlaps the session-structure family's break-and-retest logic that did survive (London reclaim), and the retest entry gives a structurally defined stop.

Data gap: none.

```
PARAMS: level='pdh' (long) / 'pdl' (short mirror), side='long' | 'both', buf_atr=0.05, tol_atr=0.15, fail_atr=0.25, max_wait=12 (5-min bars),
  rr=2.0, window='all' (09:35-14:30) | 'sb' (10:00-11:00 and 14:00-15:00), max_trades=2, stop_mode='retest_low' | 'level'
PRE: B5 = resample(df1, 5, rth_only=True); L[d] = pd_high[d] (long) / pd_low[d] (short); a = ATR14d[d]
STATE MACHINE per session d (long side; short mirrors with signs flipped), state in {IDLE, BROKEN, DONE}:
  IDLE:   on 5-min bar k (tod >= 09:35) with close[k] > L + buf_atr*a and close[k-1] <= L + buf_atr*a   # first 5-min close through the level
          -> BROKEN, t_break = k
  BROKEN: on bar k (k - t_break <= max_wait):
          if close[k] < L - fail_atr*a: -> IDLE (false break; may re-arm once)
          elif low[k] <= L + tol_atr*a and low[k] >= L - fail_atr*a and close[k] > L:        # retest touches the level zone and holds
               if window=='sb' and B5.tod[k]+5 not in [10:00,11:00) U [14:00,15:00): continue
               i = B5.i_next[k]; if i == -1: -> DONE
               c = close[k]; stop = (low[k] - buf_atr*a) if stop_mode=='retest_low' else (L - fail_atr*a)
               R = c - stop; if R < min_stop_pts: stop = c - min_stop_pts; R = min_stop_pts
               place(i, +1, stop_px=stop, tgt_px = c + rr*R); -> DONE (re-arm to IDLE after the trade closes if max_trades allows)
          elif k - t_break > max_wait: -> IDLE
SESSION: set_session('09:35', '14:30', '15:55'); max_trades_day = max_trades; Lucid risk block.
```
Grid (32 combos): `rr {1.5, 2.0}`, `tol_atr {0.1, 0.2}`, `window {all, sb}`, `stop_mode {retest_low, level}`, `side {long, both}`. Fixed: buf 0.05, fail 0.25, max_wait 12.

Risk: R is typically 0.1-0.3 x ATR14d (30-90 MNQ pts, $60-180 per micro) -> 5-10 micros; daily loss stop 1.0x; daily profit stop 1.0x.

Evidence recap: none credible. Pass bar: positive net in 2025 and 2026 separately with >= 60 trades/year and PF >= 1.3, and the `sb` window must not be the only profitable corner (that would be a 2-hour curve fit).

## 10. evidence_and_failures__sr_3touch_breakout  (marcwong 3-touch support/resistance breakout with its execution model)

Priority **1**, complexity **3**, instruments MNQ, MGC (as in the repo), MES; bar size 5-minute RTH bars. EQ **1** (framework published, results tables empty, live log pending). Its value is the cost/fill model (already matched by the engine) and a level-based entry that is independent of the opening range. The repo's stop (1/4 of the breakout bar's wick) is below the friction floor on micros (report section 3: tiny stops donate slippage) and is replaced by `max(wick/4, 0.25*ATR14d)` (flagged deviation).

Data gap: none.

```
PARAMS: pivot_n=3 (bars each side), lookback_bars=234 (~3 RTH days of 5-min bars), tol_atr=0.10, min_touches=3, buf_atr=0.05,
  stop_floor_atr=0.25, exit='session' | 'rr2', side='both', max_trades=2, entry_start='09:45', last_entry='14:30'
PRE: B5 = resample(df1, 5, rth_only=True); a = ATR14d[d]
  swing_high[j] confirmed at bar j+pivot_n when high[j] == max(high[j-pivot_n .. j+pivot_n]); swing_low likewise
  at bar k: pivots = confirmed swing highs/lows within the last lookback_bars bars (confirmation index <= k)
  cluster pivots whose prices lie within tol_atr*a of each other (single-linkage); level price = mean; touches = cluster size
  resistance levels = clusters with touches >= min_touches and price > close[k]; support = ... price < close[k]
SIGNAL on bar k (entry_start <= tod < last_entry):
  nearest resistance Rv: if close[k] > Rv + buf_atr*a and close[k-1] <= Rv + buf_atr*a:
      i = B5.i_next[k]; wick = close[k] - low[k]; stop = close[k] - max(wick/4, stop_floor_atr*a, min_stop_pts)
      place(i, +1, stop_px=stop, tgt_px = close[k] + 2*(close[k]-stop) if exit=='rr2' else NaN)      # exit=='session': flat 15:55
  mirror for support (short) when side=='both'
SESSION: set_session(entry_start, last_entry, '15:55'); max_trades_day = max_trades; Lucid risk block.
```
Grid (16 combos): `min_touches {3, 4}`, `tol_atr {0.10, 0.15}`, `exit {session, rr2}`, `side {long, both}`.

Risk: stop ~0.25 x ATR14d (~75 MNQ pts, $150 per micro) -> 5-8 micros; daily loss stop 1.0x; daily profit stop 2.0x (session exits can be large).

Evidence recap: none. Pass bar as in section 13; if it fails, keep only the lesson (level breakouts after bar close capture the reversal, per Mesfin).

## 11. evidence_and_failures__exit_bakeoff_60m  (Kevin Davey exit study replicated day-trade-only: neutral 60-minute momentum entry, five exit types compared)

Priority **2**, complexity **3**, instruments MES, MNQ, MGC (Davey: metals and stock indices were the profitable sectors); bar size 60-minute RTH bars on 1-minute data. EQ **3** (567,000 backtests on 40 futures 2010-2020, real-money cost assumptions, ranking stop-and-reverse > dollar target > breakeven > trailing > parabolic; vendor-published without underlying numbers). The point of this spec is not the entry (Davey used it as a neutral baseline) but to **rank exits on our data under the Lucid constraints** so the other specs use the right exit family; the result feeds the `exit` grids of specs 1, 6, 9, 10.

Data gap: none. Engine gap: there is no parabolic (accelerating) trail; `parabolic` is approximated by a trail that tightens with hold time via two placements and is flagged; `breakeven` is approximated with `trail_act_pts` (stop ratchets to roughly entry when the activation profit is reached) and flagged.

```
PARAMS: len=15 (60-min bars; Davey 15/25/35), atr_n=14 (60-min ATR), exit_mode in {sar, dollar, breakeven, trail, parabolic},
  tgt_usd=60 (per micro: MNQ 30 pts, MES 12 pts, MGC 6 pts), stop_atr=1.0, trail_atr=1.0, be_act_atr=0.5, max_trades=3
PRE: B60 = resample(df1, 60, rth_only=True)       # bars 09:30-10:00 (30 min, bucket boundary), 10:00-11:00, ..., 15:00-16:00 (continuous across days)
  hh[k] = max(close[k-len .. k-1]); ll[k] = min(close[k-len .. k-1]); a60 = ATR_60(atr_n)
ENTRY on 60-min bar k with B60.tod[k] + 60 <= 14:00 (last entry 14:00):
  long if close[k] > hh[k]; short if close[k] < ll[k]      # Davey "momentum" entry: close above the highest close of the prior len bars
  i = B60.i_next[k]; c = close[k]; s = stop_atr*a60[k] (>= min_stop_pts)
EXIT by mode:
  sar:       place(i, side, stop_px = c -/+ 2*s)   (wide catastrophe stop); on the opposite signal at bar m: exit_at(B60.i_next[m]) and
             place(B60.i_next[m]+1, -side, ...) (flip-system pattern); flat 15:55
  dollar:    place(i, side, stop_px = c -/+ s, tgt_pts = tgt_usd / point_value)                  # fixed-dollar target
  breakeven: place(i, side, stop_px = c -/+ s, trail_pts = be_act_atr*a60, trail_act_pts = be_act_atr*a60)   # ratchets to ~entry at +0.5 ATR (approximation)
  trail:     place(i, side, stop_px = c -/+ s, trail_pts = trail_atr*a60, trail_act_pts = 0)
  parabolic: place(i, side, stop_px = c -/+ s, trail_pts = trail_atr*a60, trail_act_pts = 0, max_hold = 180) (approximation: trail + 3-hour time cap)
SESSION: set_session('10:00', '14:01', '15:55'); max_trades_day = max_trades; Lucid risk block.
```
Grid (30 combos): `exit_mode {sar, dollar, breakeven, trail, parabolic}`, `len {15, 25}`, `tgt_usd {40, 80}` (dollar mode only; others use 60) x `stop_atr {0.75, 1.0}`.

Risk: 60-minute ATR stops (ES ~15-25 pts, NQ ~60-100 pts) -> 4-8 micros; daily loss stop 2.0x (three trades/day possible); daily profit stop 2.0x.

Evidence recap: expected ranking on index futures: sar / dollar > breakeven > trail > parabolic. Output of this spec is the ranking table by instrument and year, not a tradable system (unless one corner passes section 13 outright).

---

## 12. Strategies from this family that were NOT specified, and why

| Candidate (report section) | Reason dropped |
|---|---|
| Zarattini noise-area momentum, paper exits (1.1) | Already specified in `trend_momentum__noise_area` and `bot_popular_indicators__noise_area_1m_bands`; this file adds only the timed/gated variant (spec 6). |
| Mesfin ORB short, ORB pullback-entry (1.4) | OOS negative (short -3.45 / -2.16 pts, T -3.16; pullback 80.7% stop-out, -4.44 pts). Nothing to re-test. |
| Mesfin gap-fill fades at 09:30/09:45/10:00 (1.4) | All three negative OOS (T -0.26..-0.44); `mr_gapfade.py` already exists in the mean-reversion family and should inherit this as a negative prior. |
| Asia-session expansion-bar continuation / reversal (1.4) | Continuation T -11.52 net, but gross is only -0.27 pts: fading is gross +0.27 and still inside friction. Both directions are inside costs. Lesson kept: never enter after a completed expansion bar. |
| Asia liquidity-grab fade / follow (1.4) | Gross 0.2-0.8 pts either way on 6,442 events; inside friction by construction. |
| Volume spike / volume dry-up (1.4) | Needs volume (not in our data) and fails anyway (T -2.2 to -5.3). |
| Event-day drift after spike bars (1.4) | T 0.14-0.69, 2025: 12 trades mean -9.56; also needs an event calendar we do not have. |
| MGC OU mean reversion on 5-min bars (1.4) | T -1.6 to -5.3; half-life ~8 h makes intraday MR structurally wrong on 5-min MGC. |
| ML direction classifiers on MNQ 5-min (1.7) | OOS accuracy = base rate, permutation p 0.14-0.52; needs volume; do not spend backtest cycles. |
| VVG reversal / continuation as entries (1.7) | N=35, T 1.26 / -1.64, year-unstable (+8.35 / -22.76). Kept only as the no-trade gate in spec 7. |
| Concretum bare VWAP cross on QQQ/TQQQ (1.8) | Needs volume (VWAP); fires dozens of times a day in chop; no stop/target/OOS published; replication of the sibling ORB paper shows the edge equals the spread. A TWAP-proxy version is a different strategy (covered by `twap_revert.py`-type specs). |
| ICT Asian-range break-retest, OTE, OR-FVG (2.2) | Asian-range retest = London reclaim (`orb_reclaim.py` exists); OTE (61.8-78.6% retracement) has no published entry/exit detail and EQ 1; OR-FVG is a subset of spec 5 with the OR as the HTF zone. Only the PDH version (spec 9) is new. |
| kjw616 strategies (2.3) | Rules not disclosed; the one documented result is a failure (EMA cross died with costs, median stop 2.34 pts). Lesson encoded as `min_stop_pts` everywhere. |
| Matswm86 range forecast as a model (2.5) | The 63.9% / 65.2% calls come from an undisclosed model; only the 58.9% persistence baseline is codeable and it is spec 7 gate 2. |
| Unger ES/NQ strategies (2.9) | Article bodies not retrievable; no rules. |
| Davey walk-forward / Monte Carlo articles, Build Alpha tests, Swanson method, Hart (2.6-2.8, 3) | Methods, not strategies; encoded in section 13 and in spec 7's validation loop. |
| Chague base rates, overnight-vs-intraday drift (3) | Evidence only; encoded as the prior "expect zero" and as the long-only benchmark comparison (`trend_momentum__benchmark_long_0945`). |

---

## 13. Validation and cost protocol every spec in this file must pass (from report sections 3, 4, 6)

1. **Costs**: base run with engine defaults (1 tick/side + $1.30 RT); headline numbers from the **stress run** (`slip_ticks=2`) for any spec that trades in ETH (spec 3) or enters within 2 minutes of 09:30 / 10:00 / 14:00 (specs 1, 2, 11 at 10:00; spec 6 at 10:00). Deployability: gross/trade >= 2x stress RT; median stop >= 5x RT (`min_stop_pts` MNQ 6 / MES 4 / MGC 2).
2. **Walk-forward the Mesfin way**: parameters chosen on data strictly before each test year; test 2023, 2024, 2025, 2026 (to 2026-09-24) separately; require positive net in **each** year, >= 30 trades per year (>= 100 for spec 5), and the same sign in 2025Q2 (VIX 52) and 2025Q3 (RV 9%) or an explicit gate that switches the system off in one of them (spec 7).
3. **Plateau, not spike**: every grid axis must show neighbours within +/-10% of the chosen value with Sharpe >= 70% of the best; a lone peak is rejected (Build Alpha).
4. **Permutation / deflated Sharpe**: permute daily returns 1,000x (and the engine's trade order for drawdown); real result must beat >= 95% of permutations; apply a deflated-Sharpe correction for the number of grid combos tried (24-36 per spec, ~300 across the file).
5. **Exact-bar sensitivity**: `delay=1` run for every spec (section 0). Flip => artefact; survive => robust.
6. **Independent-filter test** for every gate (spec 7; `act_z_min` in spec 4; `trend_filter` and `skip_vvg` in spec 1): gate alone vs no gate on the full baseline; keep only if PF and net/maxDD improve; max two gates stacked.
7. **Haircut**: multiply net by 0.5-0.67 (the 1.5-2.5x haircut the practitioner sources expect) before the Lucid Monte Carlo sizes micros; require P(pass eval) and P(first payout) to hold under the haircut.
8. **Report** `results/<id>/README.md` with the per-year table, the delay test, the stress-cost table, the plateau plot/table and the honest verdict; a spec that fails is recorded with its failure mode from the report's taxonomy (inside friction / consumed inside the bar / year instability / too few trades / tiny stops / overfit).
