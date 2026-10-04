"""Macro-day gated last-half-hour momentum (Gao-Han-Li-Zhou, JFE 2018, conditional on CPI/NFP/FOMC days).

Family calendar_seasonal_structural (research/families/calendar_seasonal_structural.md; spec section 3). Distinct from
strategies/intraday_momentum.py by the day-set gate: an OHLC-derived 08:30 / 14:00 event detector plus the FOMC
statement table (strategies/_cal_flags.py), and by the pre-08:30 reference price.

CONVENTIONS (all ET). A 1-min bar with tod=T covers [T, T+1). c(HH:MM) = close of the last bar with tod < HH:MM (normally
the HH:MM-1 bar; the CFD feed omits tick-less minutes, so the last bar within the previous 5 minutes is used). i(HH:MM) =
index of the first bar with HH:MM <= tod < HH:MM+5 (normally the HH:MM bar); a market order placed there fills at that
bar's open + 1 tick. prev_close[d] = last RTH close (tod < 16:00) of session d-1. ATR14d = daily_atr(df1, 14, rth_only=True)
(Wilder, shifted one day). F = _cal_flags.flags(df1, k0830, k1400, median_lookback).

PER SESSION d:
  ref_px = prev_close (ref='prev_close') | open of the 09:30 bar ('open') | c(08:30) = close of the 08:29 bar, before any
           08:30 release ('pre0830').
  r1 = c(10:00)/ref_px - 1;  r12 = c(15:30)/c(15:00) - 1   (c(15:30) is the close of the 15:29 bar: nothing at/after the
       15:30 entry bar is used).
  day_ok: days='all' -> True; 'macro_only' -> F.macro_day (08:30 reaction >= k0830 x rolling-60 median, or FOMC statement day);
          'non_macro' -> not F.macro_day; 'fomc_minutes_only' -> F.macro1400 (known 14:02 < 15:30).
          skip_witching: no trade on quad-witching Fridays. skip_fomc: no trade on FOMC statement days. ATR must be non-NaN.
  sig = sign(r1) if |c(10:00) - ref_px| >= thresh_atr x ATR else 0 (thresh_atr=0: sign only, as published).
        variant 'r1_r12': sig only when sign(r12) == sign(r1). variant 'always_long': sig = +1 (negative control).
        sig = 0 when any input is missing.
ENTRY: day_ok and sig != 0 -> market at the open of i(entry_time) (15:30), stop_pts = stop_atr x ATR. No target, no re-entry.
EXIT: protective stop, or forced flat at the open of the first bar with tod >= flat (15:58).
SESSION/RISK: set_session(entry_time, entry_time + 5 min, flat); max_trades_day = 1; no daily stops (one trade per day).
PORTFOLIO NOTE: the paper's "size up 1.5-2x on release days" = leg A days='all' + leg B days='macro_only' in backtest.portfolio.
"""
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm, daily_bars
from strategies.common import daily_atr
from strategies._cal_flags import flags

NAME = 'Macro-day gated last-half-hour momentum (Gao-Han-Li-Zhou on CPI/NFP/FOMC days)'
DESCRIPTION = __doc__
CONTRACTS = ['MES', 'MNQ']
PARAMS = {'ref': 'prev_close', 'variant': 'r1', 'days': 'macro_only', 'entry_time': '15:30', 'flat': '15:58',
          'thresh_atr': 0.0, 'stop_atr': 0.4, 'skip_witching': True, 'skip_fomc': False,
          'k0830': 3.0, 'k1400': 3.0, 'median_lookback': 60, 'max_trades': 1}
GRID = {'ref': ['prev_close', 'pre0830'], 'days': ['macro_only', 'all'], 'variant': ['r1', 'r1_r12'], 'stop_atr': [0.3, 0.6]}   # 16 combos
_WIN = 5   # minutes of tolerance for a missing minute bar (CFD feed gap)


def _close_at(df1: pd.DataFrame, t: int) -> pd.Series:
    """c(t): close of the last bar with t-_WIN <= tod < t, per day_id (NaN when no such bar)."""
    b = df1[(df1['tod'] >= t - _WIN) & (df1['tod'] < t)]
    return b.groupby('day_id')['close'].last()


def _index_at(df1: pd.DataFrame, t: int) -> pd.Series:
    """i(t): 1-min index of the first bar with t <= tod < t+_WIN, per day_id."""
    b = df1[(df1['tod'] >= t) & (df1['tod'] < t + _WIN)]
    return pd.Series(b.groupby('day_id').apply(lambda x: x.index[0]), dtype=float)


def _tod_str(minutes: int) -> str:
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def day_table(df1: pd.DataFrame, contract, p: dict) -> pd.DataFrame:
    """Per-session inputs and the signal; every column uses information available before the entry bar opens."""
    rth = (contract.rth_open, contract.rth_close)
    F = flags(df1, k0830=float(p['k0830']), k1400=float(p['k1400']), median_lookback=int(p['median_lookback']), rth=rth)
    D = daily_bars(df1, rth_only=True, rth=rth)
    t = pd.DataFrame(index=F.index)
    t['session'] = F['session']
    t['atr'] = daily_atr(df1, 14, rth_only=True, rth=rth).reindex(t.index)
    t['prev_close'] = D['close'].shift(1).reindex(t.index)
    ob = df1[df1['tod'] == hm(rth[0])].groupby('day_id')['open'].first()
    t['open_0930'] = ob.reindex(t.index)
    t['c0830'] = _close_at(df1, hm('08:30')).reindex(t.index)
    t['c1000'] = _close_at(df1, hm('10:00')).reindex(t.index)
    t['c1500'] = _close_at(df1, hm('15:00')).reindex(t.index)
    et = hm(p['entry_time'])
    t['c_entry'] = _close_at(df1, et).reindex(t.index)                 # c(15:30): close of the 15:29 bar
    t['i_entry'] = _index_at(df1, et).reindex(t.index)                 # i(15:30): the 15:30 bar (fills at its open)
    ref = {'prev_close': t['prev_close'], 'open': t['open_0930'], 'pre0830': t['c0830']}[p['ref']]
    t['ref_px'] = ref
    t['r1'] = t['c1000'] / t['ref_px'] - 1.0
    t['r12'] = t['c_entry'] / t['c1500'] - 1.0
    for col in ('macro_day', 'macro0830', 'macro1400', 'fomc', 'witching'):
        t[col] = F[col]
    days = p['days']
    if days == 'all':
        ok = pd.Series(True, index=t.index)
    elif days == 'macro_only':
        ok = t['macro_day'].astype(bool)
    elif days == 'non_macro':
        ok = ~t['macro_day'].astype(bool)
    elif days == 'fomc_minutes_only':
        ok = t['macro1400'].astype(bool)
    else:
        raise ValueError(f'unknown days={days!r}')
    if p['skip_witching']:
        ok &= ~t['witching'].astype(bool)
    if p['skip_fomc']:
        ok &= ~t['fomc'].astype(bool)
    ok &= t['atr'].notna() & t['i_entry'].notna()
    move = t['c1000'] - t['ref_px']
    sig = np.sign(move).where(move.abs() >= float(p['thresh_atr']) * t['atr'], 0.0)
    sig = sig.where(t['c1000'].notna() & t['ref_px'].notna(), 0.0)
    if p['variant'] == 'r1_r12':
        sig = sig.where(t['r12'].notna() & (np.sign(t['r12']) == np.sign(t['r1'])), 0.0)
    elif p['variant'] == 'always_long':
        sig = pd.Series(1.0, index=t.index)
    elif p['variant'] != 'r1':
        raise ValueError(f'unknown variant={p["variant"]!r}')
    t['sig'] = sig.fillna(0.0).astype(int)
    t['day_ok'] = ok
    return t


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS, **params}
    it = Intents(df1)
    t = day_table(df1, contract, p)
    tr = t[t['day_ok'] & (t['sig'] != 0)]
    if len(tr):
        it.place(tr['i_entry'].values.astype(int), tr['sig'].values.astype(np.int8),
                 stop_pts=(float(p['stop_atr']) * tr['atr']).values)
    et = hm(p['entry_time'])
    it.set_session(p['entry_time'], _tod_str(et + _WIN), p['flat'])
    it.max_trades_day = int(p['max_trades'])
    return it
