"""Overnight (Globex 18:00 -> 09:30) range breakout at/after the RTH open, stop entries.

After the RTH open, buy stop at overnight high + buffer, sell stop at overnight low - buffer, valid until `last_entry`.
Only trade if the overnight range is between `min_atr` and `max_atr` x daily ATR. Stop = `stop_frac` x range (capped at
`max_stop_atr` x ATR); target = `rr` x risk; flat 15:55."""
import numpy as np, pandas as pd
from backtest.engine import Intents
from backtest.data import hm
from strategies.common import overnight_range, daily_atr

NAME = 'Overnight range breakout'
CONTRACTS = ['MES', 'MNQ']
PARAMS = {'rr': 1.5, 'stop_frac': 0.5, 'max_stop_atr': 0.4, 'buffer_ticks': 2, 'last_entry': '12:00', 'flat': '15:55', 'min_atr': 0.2, 'max_atr': 1.2, 'valid_minutes': 150, 'max_trades': 1}
GRID = {'rr': [1.0, 1.5, 2.0, 3.0], 'stop_frac': [0.3, 0.5, 1.0], 'last_entry': ['11:00', '12:00']}


def generate(df1, contract, params):
    p = {**PARAMS, **params}
    it = Intents(df1)
    rth = (contract.rth_open, contract.rth_close)
    on = overnight_range(df1, rth[0])
    datr = daily_atr(df1, 14, rth_only=True, rth=rth)
    on = on.join(datr.rename('atr'))
    rng = on['on_high'] - on['on_low']
    ok = (rng >= p['min_atr'] * on['atr']) & (rng <= p['max_atr'] * on['atr']) & on['atr'].notna()
    on = on[ok]; rng = rng[ok]
    # first RTH bar index per day
    first = df1[(df1['tod'] >= hm(rth[0])) & (df1['tod'] < hm(rth[1]))].groupby('day_id').apply(lambda x: x.index[0])
    buf = p['buffer_ticks'] * contract.tick
    h = df1['high'].values; l = df1['low'].values; day = df1['day_id'].values; tod = df1['tod'].values
    last_entry = hm(p['last_entry'])
    idx = []; sides = []; pxs = []; sps = []; tps = []
    for d, row in on.iterrows():
        if d not in first.index:
            continue
        i0 = int(first[d]); hi = row['on_high'] + buf; lo = row['on_low'] - buf; r = rng[d]
        cap = p['max_stop_atr'] * row['atr']
        k = i0; side = 0
        while k < len(df1) and day[k] == d and tod[k] < last_entry and (k - i0) < p['valid_minutes']:
            up = h[k] >= hi; dn = l[k] <= lo
            if up and dn:
                side = 1 if (hi - df1['open'].values[k]) <= (df1['open'].values[k] - lo) else -1; break
            if up:
                side = 1; break
            if dn:
                side = -1; break
            k += 1
        if side == 0:
            continue
        idx.append(i0); sides.append(side)
        if side > 0:
            sp = max(hi - p['stop_frac'] * r, hi - cap); pxs.append(hi); sps.append(sp); tps.append(hi + p['rr'] * (hi - sp))
        else:
            sp = min(lo + p['stop_frac'] * r, lo + cap); pxs.append(lo); sps.append(sp); tps.append(lo - p['rr'] * (sp - lo))
    it.place(np.array(idx, dtype=int), np.array(sides, dtype=np.int8), entry_px=np.array(pxs), valid_bars=p['valid_minutes'], stop_px=np.array(sps), tgt_px=np.array(tps))
    it.set_session(rth[0], p['last_entry'], p['flat'])
    it.max_trades_day = p['max_trades']
    return it
