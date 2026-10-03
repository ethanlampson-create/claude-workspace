"""Session-range (overnight or London) breakout with midpoint bias and a noon time stop.

Levels (`levels`): 'on' = overnight range 18:00 -> rth_open (strategies.common.overnight_range); 'london' = high/low of the
bars with tod in [02:00, 08:00) of the same session. mid = (high+low)/2, rng = high-low. ATR = Wilder ATR(14) of daily RTH
bars shifted one day. Skip the day if rng < min_atr*ATR, rng > max_atr*ATR or ATR is NaN. For 'london' also skip when the
level on the biased side was already broken between 08:00 and rth_open (the breakout happened pre-session).
Bias at the RTH open (open price o0 of the first RTH bar): long if o0 > mid, short if o0 < mid, none if equal. Optional
`gap_min` (fraction of price, 0 = off): |o0 - prior RTH close| / prior close must be >= gap_min.
If o0 is already beyond the biased level: skip the day when (o0 - level) > exhaust_frac*rng, else `outside_mode` 'skip' or
'pullback' (limit order at the level, valid until last_entry, same stop/target).
Entry: stop order at level +/- buffer_ticks*tick placed at the first RTH bar index, valid until `last_entry`; only the
biased side; one trade per day. Stop: `stop_mode` 'mid' = the session midpoint, 'frac' / 'frac(x)' = entry -/+ x*rng; both
capped at max_stop_atr*ATR from the entry. Target = entry +/- tgt_frac*rng. Exits: stop, target or forced flat at
`exit_time` (never later than 15:55 ET; 13:25 for MGC whose RTH closes 13:30).
Look-ahead: levels use bars strictly before rth_open; the bias uses the first RTH bar's OPEN only (the order is placed at
that bar's index, so it is live from that open and fills at max(open, level)+slip)."""
import re
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm, daily_bars
from strategies.common import overnight_range, daily_atr

NAME = 'Session-range breakout with midpoint bias (noon time stop)'
DESCRIPTION = __doc__
CONTRACTS = ['MNQ', 'MES', 'MGC']
PARAMS = {'levels': 'on', 'last_entry': '11:00', 'exit_time': '12:00', 'stop_mode': 'mid', 'stop_frac': 0.5, 'max_stop_atr': 0.4,
          'tgt_frac': 0.5, 'buffer_ticks': 2, 'min_atr': 0.25, 'max_atr': 1.2, 'exhaust_frac': 1.0, 'outside_mode': 'skip',
          'gap_min': 0.0, 'max_trades': 1}
GRID = {'levels': ['on', 'london'], 'tgt_frac': [0.5, 1.0], 'stop_mode': ['mid', 'frac(0.5)'], 'exit_time': ['12:00', '15:55'],
        'last_entry': ['10:30', '11:00']}


def _parse_stop_mode(mode, default_frac):
    """'mid' -> ('mid', None); 'frac' -> ('frac', default_frac); 'frac(0.5)' -> ('frac', 0.5)."""
    m = re.fullmatch(r'frac\(([0-9.]+)\)', str(mode))
    if m:
        return 'frac', float(m.group(1))
    if mode == 'frac':
        return 'frac', float(default_frac)
    return 'mid', None


def london_range(df1, start='02:00', end='08:00'):
    """High/low of the bars with tod in [start, end) per day_id."""
    d = df1[(df1['tod'] >= hm(start)) & (df1['tod'] < hm(end))]
    g = d.groupby('day_id')
    return pd.DataFrame({'lvl_high': g['high'].max(), 'lvl_low': g['low'].min(), 'n_bars': g.size()})


def _latest_flat(contract):
    """Last allowed flat time: 15:55 for the 16:00 close, otherwise rth_close - 5 min (MGC: 13:25)."""
    c = hm(contract.rth_close)
    m = c - 5
    return f'{m // 60:02d}:{m % 60:02d}'


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS, **params}
    it = Intents(df1)
    rth = (contract.rth_open, contract.rth_close)
    o_tod, c_tod = hm(rth[0]), hm(rth[1])
    last_entry = hm(p['last_entry'])
    latest = _latest_flat(contract)
    exit_time = p['exit_time'] if hm(p['exit_time']) <= hm(latest) else latest
    smode, sfrac = _parse_stop_mode(p['stop_mode'], p['stop_frac'])

    # ---- levels (strictly before rth_open)
    if p['levels'] == 'london':
        lv = london_range(df1, '02:00', '08:00')
        lv = lv[lv['n_bars'] >= 200]       # need most of the London session present
        pre = df1[(df1['tod'] >= hm('08:00')) & (df1['tod'] < o_tod)].groupby('day_id')
        lv = lv.join(pd.DataFrame({'pre_high': pre['high'].max(), 'pre_low': pre['low'].min()}))
    else:
        on = overnight_range(df1, rth[0])
        lv = pd.DataFrame({'lvl_high': on['on_high'], 'lvl_low': on['on_low']})
        lv['pre_high'] = np.nan; lv['pre_low'] = np.nan
    datr = daily_atr(df1, 14, rth_only=True, rth=rth)
    lv = lv.join(datr.rename('atr'))
    lv['rng'] = lv['lvl_high'] - lv['lvl_low']
    lv['mid'] = (lv['lvl_high'] + lv['lvl_low']) / 2.0
    ok = (lv['rng'] >= p['min_atr'] * lv['atr']) & (lv['rng'] <= p['max_atr'] * lv['atr']) & lv['atr'].notna() & (lv['rng'] > 0)
    lv = lv[ok]

    # ---- first RTH bar per day (open used for the bias), prior RTH close for the gap filter
    rth_bars = df1[(df1['tod'] >= o_tod) & (df1['tod'] < c_tod)]
    g = rth_bars.groupby('day_id')
    first = pd.DataFrame({'i0': g.apply(lambda x: x.index[0]), 'tod0': g['tod'].first(), 'o0': g['open'].first()})
    first = first[first['tod0'] <= o_tod + 5]   # the session must open on time (within 5 min)
    lv = lv.join(first, how='inner')
    if p['gap_min'] > 0:
        pdc = daily_bars(df1, rth_only=True, rth=rth)['close'].shift(1)
        lv = lv.join(pdc.rename('pdc'))
        gap = (lv['o0'] - lv['pdc']).abs() / lv['pdc']
        lv = lv[gap.notna() & (gap >= p['gap_min'])]

    buf = p['buffer_ticks'] * contract.tick
    valid = max(1, last_entry - o_tod)
    rows = {'stop': ([], [], [], [], []), 'limit': ([], [], [], [], [])}
    for d, r in lv.iterrows():
        o0 = r['o0']; mid = r['mid']; rng = r['rng']; cap = p['max_stop_atr'] * r['atr']
        if o0 > mid:
            side = 1; lvl = r['lvl_high']
        elif o0 < mid:
            side = -1; lvl = r['lvl_low']
        else:
            continue
        if p['levels'] == 'london':
            # skip when the biased level was already broken between 08:00 and rth_open
            if side > 0 and r['pre_high'] == r['pre_high'] and r['pre_high'] > lvl:
                continue
            if side < 0 and r['pre_low'] == r['pre_low'] and r['pre_low'] < lvl:
                continue
        outside = (o0 - lvl) * side
        kind = 'stop'; entry = lvl + side * buf
        if outside > 0:
            if outside > p['exhaust_frac'] * rng or p['outside_mode'] != 'pullback':
                continue
            kind = 'limit'; entry = lvl
        if smode == 'mid':
            sp_raw = mid
        else:
            sp_raw = entry - side * sfrac * rng
        # cap the stop distance at max_stop_atr * ATR from the entry
        sp = max(sp_raw, entry - cap) if side > 0 else min(sp_raw, entry + cap)
        if (entry - sp) * side <= 0:
            continue
        tp = entry + side * p['tgt_frac'] * rng
        L = rows[kind]
        L[0].append(int(r['i0'])); L[1].append(side); L[2].append(entry); L[3].append(sp); L[4].append(tp)
    for kind, L in rows.items():
        if L[0]:
            it.place(np.array(L[0], dtype=int), np.array(L[1], dtype=np.int8), entry_px=np.array(L[2]), kind=kind,
                     valid_bars=valid, stop_px=np.array(L[3]), tgt_px=np.array(L[4]))
    it.set_session(rth[0], p['last_entry'], exit_time)
    it.max_trades_day = p['max_trades']
    return it
