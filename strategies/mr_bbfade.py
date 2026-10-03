"""Bollinger (20,2) rejection-wick fade with ADX<25 gate and trend-day kill switch (consistency filler).

BARS: 5-minute bars built from ALL session bars (backtest.data.resample(df1, 5, rth_only=False)) so the indicators are
mature at the RTH open; entries only inside the RTH entry window.
INDICATORS on 5-min closes (min_periods = full window; NaN rows never trade): mid = SMA(bb_len); sd = rolling
stdev(bb_len); upper/lower = mid +/- bb_sd * sd; ATR5 = Wilder ATR(atr_len) on the 5-min bars; ADX = ADX(adx_len) on the
5-min bars. Daily ATR = 14-day RTH ATR (lagged, strategies.common.daily_atr). rth_open_px = open of the first 1-min
bar at/after contract.rth_open ET of the session.
SIGNAL BAR b (all values at its close):
  LONG  if low_b <= lower_b AND (close_b - low_b) >= wick_frac * (high_b - low_b) AND high_b > low_b
        AND ADX_b < adx_max AND |close_b - rth_open_px| <= max_trend_atr * dailyATR   (trend-day kill switch)
  SHORT mirror: high_b >= upper_b AND (high_b - close_b) >= wick_frac * range.
  Implementation guard: the fixed target (mid_b) must be at least one tick beyond close_b in the trade direction.
  Optional max_rr (0 = off): skip when |mid_b - close_b| > max_rr * (distance from close_b to the stop); a target far
  beyond the ATR-sized stop means the bands are wide relative to recent bar ranges (expanding / trending volatility).
ENTRY: market at the open of the 1-min bar b.i_next (skipped when i_next == -1), only if that bar's time of day is in
[entry_start, entry_end). STOP: low_b - stop_atr * ATR5_b (long) / high_b + stop_atr * ATR5_b (short).
TARGET: mid_b (the SMA value at the signal bar, fixed). TIME STOP: time_bars * 5 minutes. Force flat at `flat` ET.
max_trades_day = max_trades; daily_loss_stop = loss_cap ($ per contract, 0 = off). One position at a time (engine).
Contract defaults: MES/MNQ entry 09:45-15:00, flat 15:55; MGC entry 08:30-13:00, flat 13:25 (pit session)."""
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm, resample
from strategies.common import atr, adx, sma, daily_atr

NAME = 'Bollinger rejection-wick fade (ADX gate, trend-day kill switch)'
DESCRIPTION = __doc__
CONTRACTS = ['MES', 'MNQ']
PARAMS = {'bb_len': 20, 'bb_sd': 2.0, 'wick_frac': 0.5, 'adx_len': 14, 'adx_max': 25, 'atr_len': 14, 'stop_atr': 1.0,
          'time_bars': 15, 'max_trend_atr': 0.6, 'entry_start': None, 'entry_end': None, 'flat': None, 'sides': 'both',
          'max_trades': 4, 'loss_cap': 0, 'bar': 5, 'max_rr': 0}
GRID = {'bb_sd': [2.0, 2.5], 'adx_max': [20, 25, 99], 'stop_atr': [1.0, 1.5], 'sides': ['both', 'long']}
GRID_FOLLOWUP = {'time_bars': [10, 15, 24], 'loss_cap': [0, 60]}
GRID_FOLLOWUP2 = {'max_rr': [0, 1.0], 'sides': ['both', 'long']}

_SESSION = {  # per contract: entry_start, entry_end, flat
    'MES': ('09:45', '15:00', '15:55'), 'ES': ('09:45', '15:00', '15:55'),
    'MNQ': ('09:45', '15:00', '15:55'), 'NQ': ('09:45', '15:00', '15:55'),
    'MGC': ('08:30', '13:00', '13:25'), 'GC': ('08:30', '13:00', '13:25'),
}


def resolve(contract, params):
    p = {**PARAMS, **params}
    es, ee, fl = _SESSION.get(contract.name, ('09:45', '15:00', '15:55'))
    if p['entry_start'] is None: p['entry_start'] = es
    if p['entry_end'] is None: p['entry_end'] = ee
    if p['flat'] is None: p['flat'] = fl
    return p


def rth_open_px(df1: pd.DataFrame, rth_open: str) -> pd.Series:
    """Open of the first 1-min bar at/after rth_open ET per day_id (NaN when the session has no such bar)."""
    o = hm(rth_open)
    d = df1[(df1['tod'] >= o) & (df1['tod'] < o + 30)]
    return d.groupby('day_id')['open'].first()


def signals(df1: pd.DataFrame, contract, p: dict) -> pd.DataFrame:
    """5-min bars with indicator columns and boolean long/short signal flags."""
    b = resample(df1, p['bar'], rth_only=False)
    c = b['close']
    mid = sma(c, p['bb_len'])
    sd = c.rolling(p['bb_len'], min_periods=p['bb_len']).std()
    b['mid'] = mid; b['upper'] = mid + p['bb_sd'] * sd; b['lower'] = mid - p['bb_sd'] * sd
    b['atr5'] = atr(b, p['atr_len'])
    b['adx'] = adx(b, p['adx_len'])
    datr = daily_atr(df1, 14, rth_only=True, rth=(contract.rth_open, contract.rth_close))
    b['datr'] = b['day_id'].map(datr)
    b['rth_open_px'] = b['day_id'].map(rth_open_px(df1, contract.rth_open))
    rng = b['high'] - b['low']
    tod_next = pd.Series(np.where(b['i_next'].values >= 0, df1['tod'].values[np.maximum(b['i_next'].values, 0)], -1), index=b.index)
    s, e = hm(p['entry_start']), hm(p['entry_end'])
    in_win = (tod_next >= s) & (tod_next < e) & (b['tod'] >= hm(contract.rth_open))   # signal bar inside RTH, entry inside window
    base = (b['i_next'] >= 0) & in_win & (rng > 0) & b['mid'].notna() & b['atr5'].notna() & b['adx'].notna() \
        & b['datr'].notna() & b['rth_open_px'].notna() & (b['adx'] < p['adx_max']) \
        & ((c - b['rth_open_px']).abs() <= p['max_trend_atr'] * b['datr'])
    tick = contract.tick
    b['long'] = base & (b['low'] <= b['lower']) & ((c - b['low']) >= p['wick_frac'] * rng) & (b['mid'] >= c + tick)
    b['short'] = base & (b['high'] >= b['upper']) & ((b['high'] - c) >= p['wick_frac'] * rng) & (b['mid'] <= c - tick)
    if p['max_rr'] and p['max_rr'] > 0:
        risk_l = (c - b['low']) + p['stop_atr'] * b['atr5']; risk_s = (b['high'] - c) + p['stop_atr'] * b['atr5']
        b['long'] &= (b['mid'] - c) <= p['max_rr'] * risk_l
        b['short'] &= (c - b['mid']) <= p['max_rr'] * risk_s
    if p['sides'] == 'long':
        b['short'] = False
    elif p['sides'] == 'short':
        b['long'] = False
    return b


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = resolve(contract, params)
    it = Intents(df1)
    b = signals(df1, contract, p)
    hold = int(p['time_bars']) * int(p['bar'])
    for col, side in (('long', 1), ('short', -1)):
        m = b[col].values
        if not m.any():
            continue
        idx = b.loc[m, 'i_next'].values.astype(int)
        if side > 0:
            stop_px = b.loc[m, 'low'].values - p['stop_atr'] * b.loc[m, 'atr5'].values
        else:
            stop_px = b.loc[m, 'high'].values + p['stop_atr'] * b.loc[m, 'atr5'].values
        tgt_px = b.loc[m, 'mid'].values
        it.place(idx, side, stop_px=stop_px, tgt_px=tgt_px, max_hold=hold)
    it.set_session(p['entry_start'], p['entry_end'], p['flat'])
    it.max_trades_day = int(p['max_trades'])
    it.daily_loss_stop = float(p['loss_cap'])
    return it
