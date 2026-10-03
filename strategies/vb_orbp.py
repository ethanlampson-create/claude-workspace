"""Williams volatility breakout, one-sided (ORBP): open +/- k x yesterday's range, prior-midpoint bias with cancel-on-opposite,
wide-spread-day skip, capped fraction target (family volatility_breakout, research/families/volatility_breakout.md VB-1,
research/specs/volatility_breakout.md spec 1).

CONVENTIONS: D = daily RTH bars (daily_bars(df1, rth_only=True, rth=(contract.rth_open, contract.rth_close))); every daily
quantity used for session d comes from sessions < d; ATR = daily_atr(14) (already shifted); early_close -> skip;
min_stop_pts per contract (MES 4 / MNQ 6 / MGC 2); tick = contract.tick.
DAILY (per session d): rng = high[d-1] - low[d-1]; mid = (high[d-1] + low[d-1]) / 2; C1 = close[d-1]; C2 = close[d-2];
  swing = max(high[d-3] - low[d-1], high[d-1] - low[d-3]). unit='range': B = rng; unit='swing': B = swing. U = k * B.
TRADEABLE: B, ATR, mid not NaN; min_unit_atr*ATR <= U <= max_unit_atr*ATR; (ws_skip == 0 or rng <= ws_skip*ATR) [Crabel: never
  after a wide-spread day]; (gap_skip_atr == 0 or |O - C1| <= gap_skip_atr*ATR); not early_close.
OPEN: i0 = first RTH bar of session d; O = open[i0]; i1 = i0 + 1 (orders go live at the open of bar i1, so the open print of
  bar i0 can never fill them). Levels: up = O + U + buffer_ticks*tick; dn = O - U - buffer_ticks*tick.
ALLOWED SIDES: bias='none': {+1,-1}; 'pd_mid': {+1} if O > mid, {-1} if O < mid, {} if equal; 'down_close_long': {+1} if
  C1 < C2 else {-1}. sides='long' / 'short' intersects with {+1} / {-1}.
ENTRY (resting stop orders resolved on the 1-min bars exactly as strategies/orb.py): scan k = i1, i1+1, ... while day[k] == d
  and tod[k] < entry_cutoff: hit_up = high[k] >= up; hit_dn = low[k] <= dn; both -> first = +1 if (up - open[k]) <=
  (open[k] - dn) else -1; elif hit_up: +1; elif hit_dn: -1; else continue. If first in allowed: trade side=first via
  place(i1, side, entry_px=level, kind='stop', valid_bars = bars from i1 to the cutoff) (the engine re-finds the same fill bar,
  fill = max(open, level) + 1 tick). Elif cancel_on_opposite: no trade today. Else keep waiting for the allowed level (if the
  allowed level is touched in the same bar as the opposite one, it is traded). One trade per day, never a reversal.
STOP: stop_mode='frac': R = stop_frac*B; 'open': R = U + buffer (stop at the open: the breakout failed).
  R = min(R, max_stop_atr*ATR); R = max(R, min_stop_pts); stop_pts = R from the fill.
TARGET: tgt_mode='frac': T = tgt_frac*B; 'eod': none. tgt_cap_atr > 0: T = min(T, tgt_cap_atr*ATR) (in 'eod' mode with a cap
  T = tgt_cap_atr*ATR = the hard cap). tgt_pts = T from the fill (NaN when none).
EXITS: stop, target, forced flat at `flat`. SESSION: set_session(tod(i1), entry_cutoff, flat); max_trades_day = 1;
  daily_loss_stop 0 (the single stop is the daily loss).
GOLD (MGC/GC): pit daily bars 08:20-13:30; O = the 08:20 open; i1 = 08:21; entry_cutoff default '13:25' (= published eod
  control; the grid uses '10:30'); flat 13:25. `entry_cutoff` / `flat` / `min_stop_pts` accept a per-contract dict.
DIAGNOSTICS: day_table(df1, contract, params) -> per-session B/ATR, allowed side, first level touched, fill minute, levels.
LOOK-AHEAD: rng/mid/closes/swing/ATR from sessions < d; O is the open print of bar i0; the orders go live at i1 and are stop
  orders beyond O, so the open print cannot fill them.
"""
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm, daily_bars
from strategies.common import daily_atr

NAME = 'Williams volatility breakout, one-sided ORBP (open +/- k x range, pd-mid bias, wide-spread skip, capped target)'
DESCRIPTION = __doc__
CONTRACTS = ['MNQ', 'MES', 'MGC']
# Defaults = the published NanoTrader / WH SelfInvest rule: two-sided, k = 0.25 of yesterday's range, bracket 2 x k-range both
# ways (0.5 x range), time exit at the close (entry allowed until the flat).
PARAMS = {'unit': 'range', 'k': 0.25, 'sides': 'both', 'bias': 'none', 'stop_mode': 'frac', 'stop_frac': 0.5,
          'tgt_mode': 'frac', 'tgt_frac': 0.5, 'tgt_cap_atr': 0.0, 'max_stop_atr': 0.6,
          'min_stop_pts': {'MES': 4.0, 'MNQ': 6.0, 'MGC': 2.0}, 'min_unit_atr': 0.05, 'max_unit_atr': 1.0,
          'ws_skip': 0.0, 'gap_skip_atr': 0.0,
          'entry_cutoff': {'MES': '15:55', 'MNQ': '15:55', 'MGC': '13:25'}, 'cancel_on_opposite': True, 'buffer_ticks': 1,
          'flat': {'MES': '15:55', 'MNQ': '15:55', 'MGC': '13:25'}, 'max_trades': 1}
# Report's conditioned version: 16 combos; the single-valued keys are the fixed conditioning (ws_skip 1.5, cutoff 11:30 / gold
# 10:30, 0.6-ATR target cap, 0.4-ATR stop cap, target fraction 0.4).
GRID = {'bias': ['none', 'pd_mid'], 'k': [0.3, 0.5], 'stop_mode': ['open', 'frac'], 'tgt_mode': ['frac', 'eod'],
        'ws_skip': [1.5], 'entry_cutoff': [{'MES': '11:30', 'MNQ': '11:30', 'MGC': '10:30'}], 'tgt_cap_atr': [0.6],
        'max_stop_atr': [0.4], 'tgt_frac': [0.4], 'stop_frac': [0.5]}


def _pc(v, contract, default=None):
    """Per-contract parameter: a dict keyed by contract name, or a scalar."""
    if isinstance(v, dict):
        return v.get(contract.name, v.get(contract.name.lstrip('M'), default))
    return v


def _tod_str(minutes: int) -> str:
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def _early_close(df1: pd.DataFrame, rth) -> pd.Series:
    """Per day_id: True when the RTH session is short (last RTH bar more than 30 min before rth_close, or < 80% of the typical
    RTH bar count). Works for the 09:30-16:00 equity session and the 08:20-13:30 gold pit session alike."""
    o, c = hm(rth[0]), hm(rth[1])
    r = df1[(df1['tod'] >= o) & (df1['tod'] < c)].groupby('day_id')
    n = r.size(); last = r['tod'].last()
    typical = n.median() if len(n) else 0
    return (last < c - 30) | (n < 0.8 * typical)


def day_table(df1: pd.DataFrame, contract, params: dict) -> pd.DataFrame:
    """Per-session features, qualification, allowed side, first level touched and the resolved order (diagnostics + engine input).
    Everything daily is from sessions < d; O is the open print of the first RTH bar."""
    p = {**PARAMS, **params}
    rth = (contract.rth_open, contract.rth_close)
    tick = float(contract.tick)
    cutoff = hm(_pc(p['entry_cutoff'], contract))
    min_stop = float(_pc(p['min_stop_pts'], contract, 0.0))
    buf = float(p['buffer_ticks']) * tick
    k = float(p['k'])

    D = daily_bars(df1, rth_only=True, rth=rth)
    h1, l1 = D['high'].shift(1), D['low'].shift(1)
    t = pd.DataFrame(index=D.index)
    t['session'] = D['session']
    t['i0'] = D['i_first'].astype(int)
    t['O'] = D['open']
    t['rng'] = h1 - l1
    t['mid'] = 0.5 * (h1 + l1)
    t['C1'] = D['close'].shift(1); t['C2'] = D['close'].shift(2)
    t['swing'] = np.maximum(D['high'].shift(3) - l1, h1 - D['low'].shift(3))
    t['atr'] = daily_atr(df1, 14, rth_only=True, rth=rth).reindex(t.index)
    t['early_close'] = _early_close(df1, rth).reindex(t.index).fillna(True)
    if p['unit'] == 'range':
        t['B'] = t['rng']
    elif p['unit'] == 'swing':
        t['B'] = t['swing']
    else:
        raise ValueError(f"unknown unit {p['unit']!r}")
    t['U'] = k * t['B']
    t['B_atr'] = t['B'] / t['atr']
    t['gap'] = t['O'] - t['C1']
    ok = t['B'].notna() & t['atr'].notna() & t['mid'].notna() & (t['B'] > 0) & (t['atr'] > 0)
    ok &= (t['U'] >= float(p['min_unit_atr']) * t['atr']) & (t['U'] <= float(p['max_unit_atr']) * t['atr'])
    if float(p['ws_skip']) > 0:
        ok &= t['rng'] <= float(p['ws_skip']) * t['atr']
    if float(p['gap_skip_atr']) > 0:
        ok &= t['gap'].abs() <= float(p['gap_skip_atr']) * t['atr']
    ok &= ~t['early_close'].astype(bool)
    t['tradeable'] = ok
    # allowed sides as a bitmask: 1 = long, 2 = short
    if p['bias'] == 'none':
        allowed = np.full(len(t), 3)
    elif p['bias'] == 'pd_mid':
        allowed = np.where(t['O'] > t['mid'], 1, np.where(t['O'] < t['mid'], 2, 0))
    elif p['bias'] == 'down_close_long':
        allowed = np.where(t['C1'] < t['C2'], 1, 2)
        allowed = np.where(t['C1'].isna() | t['C2'].isna(), 0, allowed)
    else:
        raise ValueError(f"unknown bias {p['bias']!r}")
    if p['sides'] == 'long':
        allowed = allowed & 1
    elif p['sides'] == 'short':
        allowed = allowed & 2
    elif p['sides'] != 'both':
        raise ValueError(f"unknown sides {p['sides']!r}")
    t['allowed'] = allowed
    t['up'] = t['O'] + t['U'] + buf
    t['dn'] = t['O'] - t['U'] - buf

    # resolve the first touch on the 1-minute bars
    h = df1['high'].values; l = df1['low'].values; op = df1['open'].values
    day = df1['day_id'].values; tod = df1['tod'].values
    n = len(df1)
    first_hit = np.zeros(len(t), np.int8); side = np.zeros(len(t), np.int8)
    fill_tod = np.full(len(t), -1, np.int32); i1_arr = np.full(len(t), -1, np.int64); valid = np.zeros(len(t), np.int32)
    cancel = bool(p['cancel_on_opposite'])
    rows = list(zip(t.index.values, t['i0'].values, t['tradeable'].values, t['allowed'].values, t['up'].values, t['dn'].values))
    for j, (d, i0, trd, al, up, dn) in enumerate(rows):
        i1 = int(i0) + 1
        if i1 >= n or day[i1] != d or tod[i1] >= cutoff:
            continue
        i1_arr[j] = i1
        # bars the order can be live for: from i1 up to (not including) the cutoff within the session
        kk = i1
        while kk < n and day[kk] == d and tod[kk] < cutoff:
            kk += 1
        valid[j] = max(1, kk - i1)
        if not trd or al == 0:
            continue
        kb = i1
        while kb < kk:
            hit_up = h[kb] >= up; hit_dn = l[kb] <= dn
            if hit_up and hit_dn:
                first = 1 if (up - op[kb]) <= (op[kb] - dn) else -1
            elif hit_up:
                first = 1
            elif hit_dn:
                first = -1
            else:
                kb += 1; continue
            if first_hit[j] == 0:
                first_hit[j] = first
            bit = 1 if first > 0 else 2
            if al & bit:
                side[j] = first; fill_tod[j] = tod[kb]; break
            if cancel:
                break
            # waiting for the allowed level: if it is touched in this same bar take it, else keep scanning
            other = -first
            if (other > 0 and hit_up) or (other < 0 and hit_dn):
                side[j] = other; fill_tod[j] = tod[kb]; break
            kb += 1
    t['i1'] = i1_arr; t['valid_bars'] = valid; t['first_hit'] = first_hit; t['side'] = side; t['fill_tod'] = fill_tod
    # stop / target distances from the fill
    if p['stop_mode'] == 'frac':
        R = float(p['stop_frac']) * t['B']
    elif p['stop_mode'] == 'open':
        R = t['U'] + buf
    else:
        raise ValueError(f"unknown stop_mode {p['stop_mode']!r}")
    R = np.minimum(R, float(p['max_stop_atr']) * t['atr'])
    R = np.maximum(R, min_stop)
    t['stop_pts'] = R
    cap = float(p['tgt_cap_atr'])
    if p['tgt_mode'] == 'frac':
        T = float(p['tgt_frac']) * t['B']
        if cap > 0:
            T = np.minimum(T, cap * t['atr'])
    elif p['tgt_mode'] == 'eod':
        T = cap * t['atr'] if cap > 0 else pd.Series(np.nan, index=t.index)
    else:
        raise ValueError(f"unknown tgt_mode {p['tgt_mode']!r}")
    t['tgt_pts'] = T
    t['level'] = np.where(t['side'] > 0, t['up'], np.where(t['side'] < 0, t['dn'], np.nan))
    return t


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS, **params}
    it = Intents(df1)
    t = day_table(df1, contract, p)
    o = t[(t['side'] != 0) & (t['i1'] >= 0) & (t['stop_pts'] > 0)]
    if len(o):
        it.place(o['i1'].values.astype(int), o['side'].values.astype(np.int8), entry_px=o['level'].values.astype(float),
                 kind='stop', valid_bars=o['valid_bars'].values.astype(int), stop_pts=o['stop_pts'].values.astype(float),
                 tgt_pts=o['tgt_pts'].values.astype(float))
    cutoff = _pc(p['entry_cutoff'], contract); flat = _pc(p['flat'], contract)
    it.set_session(_tod_str(hm(contract.rth_open) + 1), cutoff, flat)
    it.max_trades_day = int(p['max_trades'])
    it.daily_loss_stop = 0.0
    return it
