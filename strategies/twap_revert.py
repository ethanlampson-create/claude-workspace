"""Session TWAP band mean reversion (volume-free VWAP proxy), limit entries.

On N-minute RTH bars: anchor = session TWAP from RTH open; band = k * rolling std of (close - twap) over `lb` bars.
When close < twap - band, place a limit buy at the close of the signal bar for `valid` minutes (fade); mirror for shorts.
Stop = `stop_mult` * band beyond entry; target = back to TWAP (dynamic, approximated by a fixed target of `tgt_frac`*band
toward TWAP at entry). Max hold `max_hold` minutes; flat 15:55. Optional trend filter: only fade against moves when the
daily ATR-normalised move from the open is < `max_trend_atr` (avoid fading trend days)."""
import numpy as np, pandas as pd
from backtest.engine import Intents
from backtest.data import hm, resample
from strategies.common import session_vwap, daily_atr

NAME = 'TWAP band reversion'
CONTRACTS = ['MES', 'MNQ']
PARAMS = {'bar': 5, 'lb': 24, 'k': 2.0, 'stop_mult': 1.5, 'tgt_frac': 1.0, 'valid': 10, 'max_hold': 90, 'first_entry': '10:00', 'last_entry': '15:00',
          'flat': '15:55', 'max_trades': 3, 'max_trend_atr': 0.6}
GRID = {'k': [1.5, 2.0, 2.5], 'stop_mult': [1.0, 1.5, 2.0], 'tgt_frac': [0.5, 1.0], 'max_hold': [60, 120]}


def generate(df1, contract, params):
    p = {**PARAMS, **params}
    it = Intents(df1)
    rth = (contract.rth_open, contract.rth_close)
    b = resample(df1, p['bar'], rth_only=True, rth=rth)
    tw = session_vwap(b)
    dev = b['close'] - tw
    sd = dev.groupby(b['day_id']).transform(lambda s: s.rolling(p['lb'], min_periods=max(6, p['lb'] // 2)).std())
    band = p['k'] * sd
    datr = daily_atr(df1, 14, rth_only=True, rth=rth)
    day_open = b.groupby('day_id')['open'].transform('first')
    move = (b['close'] - day_open).abs() / b['day_id'].map(datr)
    ok = (b['tod'] >= hm(p['first_entry'])) & (b['tod'] < hm(p['last_entry'])) & band.notna() & (move < p['max_trend_atr']) & (b['i_next'] >= 0)
    lo = ok & (dev < -band); sh = ok & (dev > band)
    for mask, side in ((lo, 1), (sh, -1)):
        idx = b.loc[mask, 'i_next'].values
        px = b.loc[mask, 'close'].values
        bd = band.loc[mask].values
        it.place(idx, side, entry_px=px, kind='limit', valid_bars=p['valid'], stop_pts=p['stop_mult'] * bd, tgt_pts=p['tgt_frac'] * bd, max_hold=p['max_hold'])
    it.set_session(p['first_entry'], p['last_entry'], p['flat'])
    it.max_trades_day = p['max_trades']
    return it
