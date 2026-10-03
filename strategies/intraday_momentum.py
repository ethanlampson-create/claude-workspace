"""Market intraday momentum (Gao, Han, Li, Zhou 2018): the first half-hour return predicts the last half-hour return.

Rule: at `entry_time` ET (default 15:30), if the return from the RTH open (or prior close) to `entry_time` exceeds
`thresh` x daily ATR, enter in the direction of the move at market, exit at `flat` (default 15:58). Stop = `stop_atr` x ATR.
Variants: `ref` = 'open' (open-to-now) or 'close' (prior close-to-now) or 'first30' (first 30-min return only)."""
import numpy as np, pandas as pd
from backtest.engine import Intents
from backtest.data import hm
from strategies.common import daily_atr, daily_bars

NAME = 'Intraday momentum (first-half-hour -> last-half-hour)'
CONTRACTS = ['MES', 'MNQ']
PARAMS = {'entry_time': '15:30', 'ref': 'open', 'thresh': 0.25, 'stop_atr': 0.5, 'flat': '15:58'}
GRID = {'entry_time': ['15:00', '15:30'], 'ref': ['open', 'close', 'first30'], 'thresh': [0.0, 0.2, 0.4], 'stop_atr': [0.3, 0.6]}


def generate(df1, contract, params):
    p = {**PARAMS, **params}
    it = Intents(df1)
    rth = (contract.rth_open, contract.rth_close)
    datr = daily_atr(df1, 14, rth_only=True, rth=rth)
    d = daily_bars(df1, rth_only=True, rth=rth)
    t = hm(p['entry_time'])
    # price at entry_time: last 1-min close before t, per day
    pre = df1[(df1['tod'] < t) & (df1['tod'] >= hm(rth[0]))]
    g = pre.groupby('day_id')
    px_now = g['close'].last(); i_last = g.apply(lambda x: x.index[-1])
    if p['ref'] == 'open':
        ref = d['open']
    elif p['ref'] == 'close':
        ref = d['close'].shift(1)
    else:
        f30 = df1[(df1['tod'] >= hm(rth[0])) & (df1['tod'] < hm(rth[0]) + 30)].groupby('day_id')['close'].last()
        ref = d['open']; px_now = f30.reindex(px_now.index)
    mv = (px_now - ref.reindex(px_now.index)) / datr.reindex(px_now.index)
    ok = mv.abs() > p['thresh']
    idx = (i_last[ok] + 1).values; side = np.sign(mv[ok]).astype(np.int8).values
    stops = (p['stop_atr'] * datr.reindex(px_now.index)[ok]).values
    good = idx < len(df1)
    it.place(idx[good], side[good], stop_pts=stops[good])
    it.set_session(p['entry_time'], p['flat'], p['flat'])
    it.max_trades_day = 1
    return it
