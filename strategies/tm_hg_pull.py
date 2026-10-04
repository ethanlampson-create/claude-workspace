"""Raschke-Connors 'Holy Grail' (Street Smarts, 1995): ADX(14) > 30 and rising, first pullback to the 20-EMA, buy stop over
the touch bar, stop under the pullback swing low, target the recent swing high, trail after a 1R move. Keltner-stop variant
(research/families/trend_momentum.md section 14) folded in as stop_mode='keltner'.

Family trend_momentum, spec 10 (research/specs/trend_momentum.md). EQ 1-2: book + anecdotes, no quantified ES/NQ test.

RULES AS IMPLEMENTED (all times ET; RTH = (contract.rth_open, contract.rth_close): 09:30-16:00 MES/MNQ, 08:20-13:30 MGC pit):
BARS: B = resample(df1, bar, rth_only=True, rth=rth), a continuous RTH series across sessions (the first bar of a day continues
  the previous day's indicator state, TradingView "RTH chart" semantics, same convention as bot_squeeze_lb). Rows carry tod
  (bar start), day_id, i_first/i_last (1-min index range) and i_next (first 1-min bar after the bar closes; -1 = session over).
INDICATORS on B (min_periods = full window; NaN -> no trade):
  EMA = ema(close, ema_len); ADX = adx(B, adx_len) (strategies.common.adx, Wilder-smoothed DI/DX); ATRb = atr(B, atr_len);
  ATR14d[day] = daily_atr(df1, 14, rth_only=True, rth) (Wilder ATR(14) of daily RTH bars, shifted one day).
TREND STATE at bar k:
  adx_up[k] = ADX[k] > adx_min and ADX[k] > ADX[k-1]  ("ADX > 30 and rising" on bar k)
  armed[k]  = any(adx_up[k-adx_rise_lb+1 .. k])         (the trend was identified within the last adx_rise_lb bars)
  up_trend[k] = ADX[k] > adx_min and armed[k] and EMA[k] > EMA[k-3] and close[k-1] > EMA[k-1]
  dn_trend[k] = ADX[k] > adx_min and armed[k] and EMA[k] < EMA[k-3] and close[k-1] < EMA[k-1]
  adx_rise_lb = 1 is the literal spec text (ADX must tick up on the touch bar itself). That conjunction almost never happens:
  ADX falls while price retraces to the EMA, so the literal rule produced 4-5 trades per 21 months on MES/MNQ (2025-26) against
  the spec's own expectation of 100-300. The book identifies the trend with "ADX > 30 and rising" and THEN waits for the
  retracement; adx_rise_lb = 6 (30 minutes on 5-min bars) keeps that reading: the ADX must still be above adx_min on the touch
  bar and must have been rising through adx_min within the last six bars.
TOUCH (setup bar k):
  touch_long[k]  = up_trend[k] and low[k] <= EMA[k]  and close[k] > EMA[k] - 0.5*ATRb[k]
  touch_short[k] = dn_trend[k] and high[k] >= EMA[k] and close[k] < EMA[k] + 0.5*ATRb[k]
  plus: entry_start <= tod[k] < last_entry, i_next[k] != -1, module state flat (no position, no live pending order),
  entries today < max_trades, all indicators and ATR14d not NaN. Both touches on one bar (impossible, guarded) -> no trade.
ENTRY: long: level = high[k] + 1 tick; it.place(i_next[k], +1, entry_px=level, kind='stop', valid_bars=valid_minutes, ...).
  short: level = low[k] - 1 tick, mirror. The stop order is live from the open of 1-min bar i_next[k] for valid_minutes bars,
  then cancels (the engine also cancels it at the end of the entry window). Engine fill = max(open, level) + 1 tick.
STOP: stop_mode 'swing': raw_stop = min(low[k-2..k]) - 1 tick (long) / max(high[k-2..k]) + 1 tick (short).
  stop_mode 'keltner': raw_stop = EMA[k] - kc_mult*ATRb[k] (long) / EMA[k] + kc_mult*ATRb[k] (short), rounded away to the tick.
  R = (level - raw_stop)*side. R < 2 ticks -> skip. R > max_stop_atr*ATR14d -> R = max_stop_atr*ATR14d and stop_pts = R
  (relative to the fill); otherwise stop_px = raw_stop.
TARGET: tgt_mode 'swing': tgt_px = max(high[k-swing_len..k-1]) (long; the most recent swing high before the touch bar) /
  min(low[k-swing_len..k-1]) (short); skip if (tgt_px - level)*side < 1.0*R (not enough room). tgt_mode 'rr': level + side*rr*R.
TRAIL: trail_after_1r: trail_pts = R, trail_act_pts = R (engine ratchet: once the bar extreme is >= 1R beyond the fill the stop
  moves to extreme -/+ R, i.e. to breakeven at activation; approximates "trail to the EMA").
MODULE STATE (mirror of the engine, walked on the 1-MINUTE bars of each N-bar; the spec's N-bar mirror made exact):
  'pending' after a placement -> 'in_position' on the first 1-min bar j in [i_next[k], i_next[k] + valid_minutes - 1] inside the
  entry window with high[j] >= level (long) / low[j] <= level (short); fill = max(open[j], level) + tick (mirror);
  -> 'flat' if the window expires untouched. in_position -> flat on (a) the fill bar itself if its low <= stop / high >= target+tick
  (engine: stop first, then target, on a stop-entry fill), (b) a later 1-min bar: open through stop/target, then low <= stop,
  then high >= target + tick, (c) the trail ratchet (mirrored exactly: extreme >= fill + R -> stop = max(stop, extreme - R);
  close <= stop -> out), (d) the session end. NOT mirrored: the engine daily_loss_stop halt and the thin-session / warm-up
  entry bans applied by backtest.run.prepare; both only make the engine IGNORE placements the module makes while it believes it
  is in a position, which can at most suppress a re-entry the module would otherwise have allowed -> state stays safe.
  After a stop-out, the next touch while the trend condition holds may re-enter (max_trades per day).
SESSION/RISK: it.set_session(entry_start, last_entry + bar minutes, flat): the window ends one bar after last_entry so that
  the setup bar starting just before last_entry can place at its i_next. it.max_trades_day = max_trades;
  it.daily_loss_stop = dls_block[contract] ($ per micro: MES 60, MNQ 80, MGC 80); it.daily_profit_stop = 0 (off).
GOLD (GOLD_DEFAULTS when contract.name in ('MGC', 'GC')): pit mapping 08:20-13:30, entries 08:35-12:30, flat 13:25.
LOOK-AHEAD: the touch bar k is fully closed before i_next[k]; the entry is a stop beyond its high/low, so the setup bar cannot
  fill the order; indicators are rolling with full min_periods; ATR14d is shifted one day.
"""
import math
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm, resample
from strategies.common import adx, atr, ema, daily_atr

NAME = "Raschke-Connors Holy Grail: ADX>30 rising, 20-EMA pullback, buy stop over the touch bar"
DESCRIPTION = __doc__
CONTRACTS = ['MES', 'MNQ', 'MGC']
PARAMS = {'bar': 5, 'adx_len': 14, 'adx_min': 30, 'adx_rise_lb': 6, 'ema_len': 20, 'stop_mode': 'swing', 'kc_mult': 2.0, 'atr_len': 14,
          'tgt_mode': 'swing', 'rr': 1.5, 'swing_len': 20, 'valid_minutes': 30, 'trail_after_1r': True,
          'entry_start': '10:00', 'last_entry': '15:00', 'flat': '15:55', 'max_trades': 3,
          'max_stop_atr': 0.5,                       # prop-account cap on the stop distance (spec 10: 0.5 x ATR14d)
          'dls_block': {'MES': 60, 'MNQ': 80, 'MGC': 80}}
GOLD_DEFAULTS = {'entry_start': '08:35', 'last_entry': '12:30', 'flat': '13:25'}
GRID = {'adx_min': [25, 30], 'stop_mode': ['swing', 'keltner'], 'tgt_mode': ['swing', 'rr'], 'bar': [5, 15]}   # 16 combos
_MICRO_OF = {'ES': 'MES', 'NQ': 'MNQ', 'GC': 'MGC'}


def _tod_str(minutes: int) -> str:
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def signal_table(B: pd.DataFrame, p: dict) -> pd.DataFrame:
    """Indicator and setup columns on the N-minute bars: ema, adx, atrb, up_trend, dn_trend, touch_long, touch_short,
    sw_lo3/sw_hi3 (min low / max high of bars k-2..k), sw_hi/sw_lo (max high / min low of bars k-swing_len..k-1)."""
    c = B['close']; h = B['high']; l = B['low']
    e = ema(c, int(p['ema_len'])); a = adx(B, int(p['adx_len'])); ab = atr(B, int(p['atr_len']))
    adx_min = float(p['adx_min'])
    lb = max(1, int(p['adx_rise_lb']))
    adx_up = (a > adx_min) & (a > a.shift(1))                                   # "ADX > adx_min and rising" on this bar
    armed = adx_up.astype(float).rolling(lb, min_periods=1).max() > 0           # ... on any of the last lb bars (incl. k)
    up = (a > adx_min) & armed & (e > e.shift(3)) & (c.shift(1) > e.shift(1))
    dn = (a > adx_min) & armed & (e < e.shift(3)) & (c.shift(1) < e.shift(1))
    ok = e.notna() & a.notna() & a.shift(1).notna() & e.shift(3).notna() & ab.notna()
    tl = ok & up & (l <= e) & (c > e - 0.5 * ab)
    ts_ = ok & dn & (h >= e) & (c < e + 0.5 * ab)
    sl = int(p['swing_len'])
    out = B.copy()
    out['ema'] = e.values; out['adx'] = a.values; out['atrb'] = ab.values
    out['up_trend'] = up.values; out['dn_trend'] = dn.values
    out['touch_long'] = (tl & ~ts_).values; out['touch_short'] = (ts_ & ~tl).values
    out['sw_lo3'] = l.rolling(3, min_periods=3).min().values; out['sw_hi3'] = h.rolling(3, min_periods=3).max().values
    out['sw_hi'] = h.shift(1).rolling(sl, min_periods=sl).max().values; out['sw_lo'] = l.shift(1).rolling(sl, min_periods=sl).min().values
    return out


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS}
    if contract.name in ('MGC', 'GC'):
        p.update(GOLD_DEFAULTS)
    p.update(params)
    it = Intents(df1)
    rth = (contract.rth_open, contract.rth_close)
    tick = float(contract.tick)
    bar = int(p['bar'])
    e_start = hm(p['entry_start']); e_last = hm(p['last_entry']); e_end = e_last + bar
    max_trades = int(p['max_trades']); valid = max(1, int(p['valid_minutes']))
    max_stop_atr = float(p['max_stop_atr']); rr = float(p['rr']); kc_mult = float(p['kc_mult'])
    keltner = str(p['stop_mode']) == 'keltner'; tgt_rr = str(p['tgt_mode']) == 'rr'
    trail_on = bool(p['trail_after_1r'])

    B = resample(df1, bar, rth_only=True, rth=rth)
    T = signal_table(B, p)
    datr = daily_atr(df1, 14, rth_only=True, rth=rth)
    atr_d = T['day_id'].map(datr).values

    day = T['day_id'].values; tod = T['tod'].values; i_next = T['i_next'].values
    i_first = T['i_first'].values; i_last = T['i_last'].values
    hB = T['high'].values; lB = T['low'].values
    emaB = T['ema'].values; atrb = T['atrb'].values
    tl = T['touch_long'].values; tsh = T['touch_short'].values
    sw_lo3 = T['sw_lo3'].values; sw_hi3 = T['sw_hi3'].values; sw_hi = T['sw_hi'].values; sw_lo = T['sw_lo'].values
    nB = len(T)

    # 1-minute arrays for the state mirror
    o1 = df1['open'].values.astype(float); h1 = df1['high'].values.astype(float)
    l1 = df1['low'].values.astype(float); c1 = df1['close'].values.astype(float)
    tod1 = df1['tod'].values
    thr = tick                                                   # engine through_ticks = 1 for target fills

    e_idx, e_side, e_px, e_sp, e_spts, e_tp, e_trl, e_trla = [], [], [], [], [], [], [], []
    # module state: 0 flat, 1 pending, 2 in position
    state = 0; side = 0; level = np.nan; pexp = -1
    p_sp = np.nan; p_spts = np.nan; p_tp = np.nan; p_R = np.nan
    pos_sp = np.nan; pos_tp = np.nan; fill = np.nan; trl = np.nan; trla = 0.0
    ntr = 0; cur_day = -1

    def mirror_bar(j: int, is_fill_bar: bool) -> bool:
        """Engine exit mirror for the open position on 1-min bar j. Returns True when the position is closed."""
        nonlocal pos_sp
        sp = pos_sp; tp = pos_tp
        if not is_fill_bar:
            if side > 0:
                if (sp == sp and o1[j] <= sp) or (tp == tp and o1[j] >= tp + thr):
                    return True
            else:
                if (sp == sp and o1[j] >= sp) or (tp == tp and o1[j] <= tp - thr):
                    return True
        if side > 0:
            if sp == sp and l1[j] <= sp:
                return True
            if tp == tp and h1[j] >= tp + thr:
                return True
        else:
            if sp == sp and h1[j] >= sp:
                return True
            if tp == tp and l1[j] <= tp - thr:
                return True
        if trl == trl:                                           # trailing ratchet, exactly as the engine
            if side > 0 and (h1[j] - fill) >= trla:
                ns = h1[j] - trl
                if sp != sp or ns > sp:
                    pos_sp = ns
                if c1[j] <= pos_sp:
                    return True
            elif side < 0 and (fill - l1[j]) >= trla:
                ns = l1[j] + trl
                if sp != sp or ns < sp:
                    pos_sp = ns
                if c1[j] >= pos_sp:
                    return True
        return False

    for k in range(nB):
        if day[k] != cur_day:                                    # session boundary: flat, reset the per-day trade count
            cur_day = day[k]; state = 0; ntr = 0
        if state != 0:
            # walk the 1-minute bars of this N-bar, mirroring pending fill and position exits
            j = int(i_first[k]); jl = int(i_last[k])
            while j <= jl and state != 0:
                if state == 1:
                    if j > pexp or tod1[j] >= e_end or tod1[j] < e_start:
                        state = 0                                # order expired / cancelled by the entry window
                        break
                    touched = (h1[j] >= level) if side > 0 else (l1[j] <= level)
                    if touched:
                        fill = (max(o1[j], level) + tick) if side > 0 else (min(o1[j], level) - tick)
                        pos_sp = p_sp if p_sp == p_sp else fill - p_spts * side
                        pos_tp = p_tp
                        trl = p_R if trail_on else np.nan; trla = p_R if trail_on else 0.0
                        state = 2
                        if mirror_bar(j, True):
                            state = 0
                else:
                    if mirror_bar(j, False):
                        state = 0
                j += 1
        if state != 0:
            continue
        # flat after this bar's 1-min bars: is bar k a setup bar?
        if ntr >= max_trades or tod[k] < e_start or tod[k] >= e_last or i_next[k] < 0:
            continue
        if tl[k]:
            s = 1
        elif tsh[k]:
            s = -1
        else:
            continue
        if np.isnan(atr_d[k]) or np.isnan(emaB[k]) or np.isnan(atrb[k]) or np.isnan(sw_lo3[k]) or np.isnan(sw_hi[k]):
            continue
        lvl = hB[k] + tick if s > 0 else lB[k] - tick
        if keltner:
            raw = emaB[k] - kc_mult * atrb[k] if s > 0 else emaB[k] + kc_mult * atrb[k]
            raw = math.floor(raw / tick + 1e-9) * tick if s > 0 else math.ceil(raw / tick - 1e-9) * tick
        else:
            raw = sw_lo3[k] - tick if s > 0 else sw_hi3[k] + tick
        R = (lvl - raw) * s
        if R < 2.0 * tick:
            continue
        cap = max_stop_atr * float(atr_d[k])
        if R > cap:
            R = cap; spx = np.nan; spts = R
        else:
            spx = raw; spts = np.nan
        if tgt_rr:
            tpx = lvl + s * rr * R
        else:
            tpx = sw_hi[k] if s > 0 else sw_lo[k]
            if (tpx - lvl) * s < R:
                continue
        e_idx.append(int(i_next[k])); e_side.append(s); e_px.append(lvl); e_sp.append(spx); e_spts.append(spts); e_tp.append(tpx)
        e_trl.append(R if trail_on else np.nan); e_trla.append(R if trail_on else 0.0)
        state = 1; side = s; level = lvl; pexp = int(i_next[k]) + valid - 1
        p_sp = spx; p_spts = spts; p_tp = tpx; p_R = R
        ntr += 1
    if e_idx:
        it.place(np.array(e_idx, dtype=int), np.array(e_side, dtype=np.int8), entry_px=np.array(e_px), kind='stop',
                 valid_bars=valid, stop_px=np.array(e_sp), stop_pts=np.array(e_spts), tgt_px=np.array(e_tp),
                 trail_pts=np.array(e_trl), trail_act_pts=np.array(e_trla))
    it.set_session(p['entry_start'], _tod_str(e_end), p['flat'])
    it.max_trades_day = max_trades
    dls = p['dls_block'] if isinstance(p['dls_block'], dict) else {}
    it.daily_loss_stop = float(dls.get(contract.name, dls.get(_MICRO_OF.get(contract.name, ''), 0.0)) or 0.0)
    it.daily_profit_stop = 0.0
    return it
