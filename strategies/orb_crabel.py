"""Crabel stretch ORB (Toby Crabel 1990): open +/- SMA10 of daily "noise", NR7 / inside-day setup filter, entry cutoff.

DATA: 1-minute bars; daily RTH bars via backtest.data.daily_bars(df1, rth_only=True, rth=contract session).
STRETCH: noise_d = min(high_d - open_d, open_d - low_d) on daily RTH bars; stretch = SMA(stretch_len)(noise) shifted
    one day (days < d only; NaN -> no trade). Trigger distance T = mult * stretch.
SETUP (param `setup`): 'none' = every day; 'nr7' = prior day's RTH range is the smallest of the last 7 daily ranges;
    'id' = prior day is an inside day (high < day-before high and low > day-before low); 'nr4_or_id' = NR4 or inside
    day; 'nr4' = NR4 only. All flags computed on days strictly before d.
ENTRY: at the first RTH bar (open price o0) a buy stop at o0 + T and a sell stop at o0 - T, OCO emulated by scanning
    the 1-minute data for the first touch (as strategies/orb.py), valid until `cutoff`. If both levels are touched in
    the same 1-minute bar the side nearer that bar's open is taken (conservative: a loss, never a skipped day).
    One trade per day, no reversal after a stop.
STOP: the other trigger level (stop distance 2T), capped at max_stop_atr x ATR14 (daily RTH, shifted).
TARGET (param `tgt_mode`): 'eod' = none (Crabel original, exit at flat); 'rr' = entry +/- rr x stop distance.
EXITS: stop, target (if any), forced flat at `flat` (15:55 ET equities; 13:25 ET gold).
SESSION: entries in [rth_open, cutoff); max_trades_day = 1. Gold (MGC/GC) uses rth_open 08:20, cutoff 10:30 and
    flat 13:25 unless `cutoff` / `flat` are passed explicitly.
LOOK-AHEAD: stretch, setup flags and ATR use prior days only; o0 is the open of the bar at which the orders go live.
"""
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm, daily_bars
from strategies.common import daily_atr, sma

NAME = 'Crabel stretch ORB (open +/- stretch, NR7/ID setups, entry cutoff)'
DESCRIPTION = __doc__
CONTRACTS = ['MES', 'MNQ', 'MGC']
PARAMS = {'stretch_len': 10, 'mult': 1.0, 'setup': 'none', 'cutoff': '11:00', 'max_stop_atr': 0.6, 'tgt_mode': 'eod',
          'rr': 1.5, 'flat': '15:55', 'max_trades': 1}
GRID = {'mult': [1.0, 1.5, 2.0], 'setup': ['none', 'nr7', 'nr4_or_id'], 'tgt_mode': ['eod', 'rr'], 'cutoff': ['10:30', '11:30']}

GOLD_DEFAULTS = {'cutoff': '10:30', 'flat': '13:25'}


def setup_flags(d: pd.DataFrame) -> pd.DataFrame:
    """Per day_id setup flags using days strictly before d. `d` = daily RTH bars (open/high/low/close)."""
    rng = d['high'] - d['low']
    r1 = rng.shift(1)                       # prior day's range
    out = pd.DataFrame(index=d.index)
    out['nr7'] = (r1 <= r1.rolling(7, min_periods=7).min()) & r1.notna()
    out['nr4'] = (r1 <= r1.rolling(4, min_periods=4).min()) & r1.notna()
    out['id'] = (d['high'].shift(1) < d['high'].shift(2)) & (d['low'].shift(1) > d['low'].shift(2))
    out['nr4_or_id'] = out['nr4'] | out['id']
    out['none'] = True
    return out


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS, **params}
    is_gold = contract.name in ('MGC', 'GC')
    if is_gold:
        for k, v in GOLD_DEFAULTS.items():
            if k not in params:
                p[k] = v
    it = Intents(df1)
    rth = (contract.rth_open, contract.rth_close)
    d = daily_bars(df1, rth_only=True, rth=rth)
    noise = np.minimum(d['high'] - d['open'], d['open'] - d['low'])
    stretch = sma(noise, p['stretch_len']).shift(1)          # days < d only
    datr = daily_atr(df1, 14, rth_only=True, rth=rth)        # already shifted
    flags = setup_flags(d)
    if p['setup'] not in flags:
        raise ValueError(f"unknown setup {p['setup']!r}")
    ok = stretch.notna() & (stretch > 0) & datr.notna() & flags[p['setup']].fillna(False)
    d = d[ok]
    T = p['mult'] * stretch[ok].values
    cap = p['max_stop_atr'] * datr[ok].values
    i0 = d['i_first'].values.astype(int)
    o0 = d['open'].values                                    # open of the first RTH bar = bar at which orders go live

    h = df1['high'].values; l = df1['low'].values; op = df1['open'].values
    day = df1['day_id'].values; tod = df1['tod'].values
    cutoff = hm(p['cutoff'])
    n = len(df1)
    idx_list = []; side_list = []; px_list = []; sp_list = []; tp_list = []
    for j in range(len(i0)):
        i_start = i0[j]
        if i_start >= n:
            break
        hi = o0[j] + T[j]; lo = o0[j] - T[j]
        k = i_start; first = 0
        while k < n and day[k] == day[i_start] and tod[k] < cutoff:
            up = h[k] >= hi; dn = l[k] <= lo
            if up and dn:
                first = 1 if (hi - op[k]) <= (op[k] - lo) else -1
                break
            if up:
                first = 1; break
            if dn:
                first = -1; break
            k += 1
        if first == 0:
            continue
        stop_dist = min(2.0 * T[j], cap[j])
        if stop_dist <= 0:
            continue
        idx_list.append(i_start); side_list.append(first)
        if first > 0:
            px_list.append(hi); sp_list.append(hi - stop_dist)
            tp_list.append(hi + p['rr'] * stop_dist if p['tgt_mode'] == 'rr' else np.nan)
        else:
            px_list.append(lo); sp_list.append(lo + stop_dist)
            tp_list.append(lo - p['rr'] * stop_dist if p['tgt_mode'] == 'rr' else np.nan)
    valid = max(1, cutoff - hm(contract.rth_open))
    if idx_list:
        it.place(np.array(idx_list, dtype=int), np.array(side_list, dtype=np.int8), entry_px=np.array(px_list),
                 valid_bars=valid, stop_px=np.array(sp_list), tgt_px=np.array(tp_list))
    it.set_session(contract.rth_open, p['cutoff'], p['flat'])
    it.max_trades_day = p['max_trades']
    return it
