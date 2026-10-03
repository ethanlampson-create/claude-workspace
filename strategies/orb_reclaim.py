"""London Reclaim: sweep of a London-session / prior-day level, confirmed 3-bar pullback swing, stop entry one tick beyond
the breakout extreme, stop one tick beyond the swing, fixed R-multiple target (AskElira open-source spec, MNQ).

Levels per session (all from bars strictly before the entry window): London high/low = high/low of bars with tod in
[london_start, london_end); PDH/PDL = prior session's RTH high/low (`strategies.common.prior_day_stats`, 1-day lag).
High-type levels (London high, PDH) give LONG setups when swept (bar high >= level); low-type levels give SHORT setups
(bar low <= level). Each level is tradable once per day; a level swept in the morning window is skipped in the afternoon.

Setup (long; shorts mirrored):
  sweep  : first bar of the window whose high >= level. X = running max high since (and including) the sweep bar.
  swing  : at the close of bar j, a pullback swing low is confirmed at bar j-1 when the swing bar is after the sweep bar,
           low[j-1] <= low[j-2], low[j-1] < low[j] and low[j-1] < X.  S = low[j-1].
  order  : at bar j+1 a buy stop at X + 1 tick, protective stop at S - 1 tick, target = fill + rr * (order - stop).
           Skipped when (order - stop) > max_stop_pts (wait for the next swing). Live for `valid_minutes` bars or until the
           window ends; an order that expires unfilled lets the level re-arm on the next confirmed swing.
  one at a time: one pending order and one position at a time (engine semantics); a setup that confirms while another
           order is pending or a position is open is skipped (the level may re-arm on a later swing).
Exits: stop, target, forced flat at `flat` (15:55 index / 13:25 gold). No trailing. Max `max_trades` trades per day.
`pd_mode`: 'rth' (prior RTH high/low, default) or 'session' (prior full 18:00-cut session high/low, the original repo's
definition).
Gold (MGC): windows 08:20-11:00 and 12:00-13:00, London levels 02:00-08:20 (the London range is cut at the first window
start so it never contains window bars), flat 13:25, PDH/PDL from the 08:20-13:30 pit session.
`windows` may be a list of (start, end) pairs or an alias: 'am_only' / 'am_pm'.
"""
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm
from strategies.common import prior_day_stats

NAME = 'London Reclaim (level sweep, pullback swing, stop entry beyond extreme, R-multiple target)'
DESCRIPTION = __doc__
CONTRACTS = ['MNQ', 'MES', 'MGC']
PARAMS = {'london': ('02:00', '08:30'), 'windows': 'am_pm', 'rr': 3.5, 'max_stop_pts': {'MNQ': 45.0, 'MES': 12.0, 'MGC': 9.0},
          'valid_minutes': 60, 'max_trades': 4, 'flat': '15:55', 'use_pd_levels': True, 'pd_mode': 'rth', 'use_london': True,
          # gold session overrides (applied for MGC/GC unless the key is passed explicitly)
          'gold': {'london': ('02:00', '08:20'), 'flat': '13:25'}}
GRID = {'rr': [2.0, 2.5, 3.5], 'max_stop_pts': [30, 45], 'windows': ['am_only', 'am_pm'], 'use_pd_levels': [True, False]}

WINDOW_ALIASES = {
    'index': {'am_only': [('09:30', '11:00')], 'am_pm': [('09:30', '11:00'), ('13:30', '15:30')]},
    'gold': {'am_only': [('08:20', '11:00')], 'am_pm': [('08:20', '11:00'), ('12:00', '13:00')]},
}


def _resolve_windows(w, gold):
    if isinstance(w, str):
        return WINDOW_ALIASES['gold' if gold else 'index'][w]
    return [tuple(x) for x in w]


def _simulate_exit(k, fill, base, sp, tp, side, o, h, l, c, tod, flat_m, day_last, tick):
    """Index of the bar on which the engine would close a position filled at bar k (stop before target, flat at open
    of the first bar >= flat_m, session end otherwise). Mirrors backtest.engine semantics for a stop-entry fill."""
    thr = tick
    if side > 0:
        if sp >= base or l[k] <= sp or h[k] >= tp + thr:
            return k
    else:
        if sp <= base or h[k] >= sp or l[k] <= tp - thr:
            return k
    k += 1
    while k <= day_last:
        if tod[k] >= flat_m:
            return k
        if side > 0:
            if l[k] <= sp or h[k] >= tp + thr:
                return k
        else:
            if h[k] >= sp or l[k] <= tp - thr:
                return k
        k += 1
    return day_last


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS, **params}
    gold = contract.name in ('MGC', 'GC')
    if gold:
        for k, v in PARAMS['gold'].items():
            if k not in params:
                p[k] = v
    windows = _resolve_windows(p['windows'], gold)
    mx = p['max_stop_pts']
    if isinstance(mx, dict):
        mx = mx.get(contract.name, mx.get(contract.name.replace('M', '', 1), 45.0))
    mx = float(mx)
    tick = float(contract.tick); slip = contract.slip_ticks * tick
    rr = float(p['rr']); vmin = int(p['valid_minutes']); flat_m = hm(p['flat'])
    it = Intents(df1)

    o = df1['open'].values.astype(np.float64); h = df1['high'].values.astype(np.float64)
    l = df1['low'].values.astype(np.float64); c = df1['close'].values.astype(np.float64)
    tod = df1['tod'].values.astype(np.int64); day = df1['day_id'].values.astype(np.int64)
    n = len(df1)

    # ---- levels (all computed from bars strictly before the first entry window)
    ls, le = hm(p['london'][0]), hm(p['london'][1])
    le = min(le, hm(windows[0][0]))
    lon = df1[(tod >= ls) & (tod < le)].groupby('day_id')
    lon_hi = lon['high'].max(); lon_lo = lon['low'].min()
    pds = prior_day_stats(df1, rth=(contract.rth_open, contract.rth_close))
    if p.get('pd_mode', 'rth') == 'session':   # prior FULL session (18:00 cut) high/low, as in the original repo
        pd_hi = pds['on_high'].shift(1); pd_lo = pds['on_low'].shift(1)
    else:                                       # prior RTH high/low (task spec)
        pd_hi = pds['pd_high']; pd_lo = pds['pd_low']

    # day index ranges
    first_idx = pd.Series(np.arange(n)).groupby(day).first(); last_idx = pd.Series(np.arange(n)).groupby(day).last()
    win_m = [(hm(a), hm(b)) for a, b in windows]

    idx_l, side_l, px_l, sp_l, tp_l, vb_l = [], [], [], [], [], []
    meta = []  # debug: one row per placed order (level, predicted fill / exit index)
    max_trades = int(p['max_trades'])

    for d in first_idx.index:
        d0, d1 = int(first_idx[d]), int(last_idx[d])
        levels = []  # (name, price, side)
        if p['use_london'] and d in lon_hi.index and np.isfinite(lon_hi[d]):
            levels += [('LH', float(lon_hi[d]), 1), ('LL', float(lon_lo[d]), -1)]
        if p['use_pd_levels'] and d in pd_hi.index and np.isfinite(pd_hi[d]) and np.isfinite(pd_lo[d]):
            levels += [('PDH', float(pd_hi[d]), 1), ('PDL', float(pd_lo[d]), -1)]
        if not levels:
            continue
        swept_today = set(); trades_today = 0
        pos_exit = -1          # index of the bar on which the current position closes (-1 = flat)
        pending = None         # dict(level, px, sp, tp_pts, side, exp)
        for (ws, we) in win_m:
            bars = np.nonzero((tod[d0:d1 + 1] >= ws) & (tod[d0:d1 + 1] < we))[0] + d0
            if len(bars) == 0:
                continue
            st = {}
            for li, (name, px, side) in enumerate(levels):
                st[li] = {'s': 'done' if name in swept_today else 'idle', 'X': np.nan, 'sweep_i': -1}
            pending = None; arm = None
            for i in bars:
                if trades_today >= max_trades:
                    break
                # ---- A) placement at bar i of a setup confirmed on bar i-1 (engine: order live from the open of bar i)
                if arm is not None:
                    li, px, sp, side, tp_pts = arm; arm = None
                    if i > pos_exit and pending is None:
                        vb = max(1, vmin)
                        idx_l.append(i); side_l.append(side); px_l.append(px); sp_l.append(sp); tp_l.append(tp_pts); vb_l.append(vb)
                        pending = {'level': li, 'px': px, 'sp': sp, 'tp_pts': tp_pts, 'side': side, 'exp': i + vb - 1}
                        meta.append({'i': i, 'level': levels[li][0], 'side': side, 'px': px, 'sp': sp, 'fill_i': -1, 'exit_i': -1, 'window': ws})
                        st[li]['s'] = 'pending'
                    # else: skipped (position open or another order pending); level stays 'swept' and may re-arm later
                # ---- B) bar i: pending fill -> position (engine order: position management, then pending, then signal)
                if i > pos_exit and pending is not None:
                    if i > pending['exp']:
                        st[pending['level']]['s'] = 'swept'; pending = None
                    else:
                        side = pending['side']; px = pending['px']; filled = False
                        if side > 0 and h[i] >= px:
                            base = o[i] if o[i] >= px else px; fill = base + slip; filled = True
                        elif side < 0 and l[i] <= px:
                            base = o[i] if o[i] <= px else px; fill = base - slip; filled = True
                        if filled:
                            sp = pending['sp']; tp = fill + pending['tp_pts'] * side
                            pos_exit = _simulate_exit(i, fill, base, sp, tp, side, o, h, l, c, tod, flat_m, d1, tick)
                            trades_today += 1
                            meta[-1]['fill_i'] = i; meta[-1]['exit_i'] = pos_exit
                            st[pending['level']]['s'] = 'done'; pending = None
                # ---- C) level state updates using bar i (closed)
                for li, (name, lpx, side) in enumerate(levels):
                    s = st[li]
                    if s['s'] == 'done':
                        continue
                    if s['s'] == 'idle':
                        swept = (h[i] >= lpx) if side > 0 else (l[i] <= lpx)
                        if swept:
                            s['s'] = 'swept'; s['X'] = h[i] if side > 0 else l[i]; s['sweep_i'] = i; swept_today.add(name)
                        continue
                    # swept or pending: track the breakout extreme
                    if side > 0:
                        s['X'] = max(s['X'], h[i])
                    else:
                        s['X'] = min(s['X'], l[i])
                    if s['s'] != 'swept' or arm is not None:
                        continue
                    j = i
                    if j - 1 <= s['sweep_i'] or j - 2 < d0:
                        continue
                    if side > 0:
                        ok = l[j - 1] <= l[j - 2] and l[j - 1] < l[j] and l[j - 1] < s['X']
                        if not ok:
                            continue
                        S = l[j - 1]; px = s['X'] + tick; sp = S - tick; dist = px - sp
                        if dist <= 0 or dist > mx or px <= c[j]:
                            continue
                    else:
                        ok = h[j - 1] >= h[j - 2] and h[j - 1] > h[j] and h[j - 1] > s['X']
                        if not ok:
                            continue
                        S = h[j - 1]; px = s['X'] - tick; sp = S + tick; dist = sp - px
                        if dist <= 0 or dist > mx or px >= c[j]:
                            continue
                    # the order is placed at bar j+1 only if flat and nothing pending at that time (checked in step A)
                    if pending is None and (j + 1) > pos_exit:
                        arm = (li, px, sp, side, rr * dist)
            # window end: the engine cancels pending orders outside the entry windows
            pending = None

    if idx_l:
        it.place(np.array(idx_l, dtype=int), np.array(side_l, dtype=np.int8), entry_px=np.array(px_l),
                 valid_bars=np.array(vb_l, dtype=int), stop_px=np.array(sp_l), tgt_pts=np.array(tp_l))
    # entries only inside the windows; flat at `flat`
    it.set_session(windows[0][0], windows[-1][1], p['flat'])
    allow = np.zeros(n, bool)
    for (ws, we) in win_m:
        allow |= (tod >= ws) & (tod < we)
    it.allow_entry &= allow
    it.max_trades_day = max_trades
    it.meta = pd.DataFrame(meta)
    return it
