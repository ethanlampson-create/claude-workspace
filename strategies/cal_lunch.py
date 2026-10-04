"""Lunch effect: short 11:00-12:00 / long 12:00-14:00 (Quantpedia 2024), default long-only midday leg.

Family calendar_seasonal_structural (research/families/calendar_seasonal_structural.md section 9; spec
research/specs/calendar_seasonal_structural.md section 8). Source: Quantpedia "Lunch Effect in the U.S. Stock Market Indices"
(SPY 2010-05..2024-05): flat-to-negative returns before lunch, positive 12:00-14:00; long-only 12:00-14:00 leg ~5.2%/yr at 8% vol;
the short-then-long reversal is the paper's second version. Evidence quality 2 (single vendor backtest, no OOS, ~2 bp/day).

CONVENTIONS (all ET; as in cal_macro_pm). A 1-min bar with tod=T covers [T, T+1). i(HH:MM) = index of the first bar with
HH:MM <= tod < HH:MM+5 (normally the HH:MM bar; the CFD feed omits tick-less minutes). A market order placed at i(T) fills at that
bar's open + 1 tick, decided on bars up to T-1. ref(i) = close of bar i-1 (same session), the price "at T".
ATR14d = daily_atr(df1, 14, rth_only=True) (Wilder, shifted one day). F = strategies._cal_flags.flags(df1) (macro_day, fomc, opex).

DAY FILTER: day_ok[d] = not (skip_macro and (F.macro_day[d] or F.fomc[d])) and not (skip_opex and F.opex[d]) and ATR14d[d] non-NaN
  and every needed clock bar exists. macro_day is known at 08:32, long before 11:00 (no look-ahead).
STOP SIZE: stop_pts = stop_pct/100 x ref (stop_mode 'pct'; ref = close of the bar before the entry bar) or stop_atr x ATR14d[d] ('atr').
ENTRIES per session d with day_ok:
  variant 'short_only' / 'short_then_long': i_s = i(short_start) (11:00). place(i_s, -1, stop_pts); exit_at(i(reverse_time)) = market
     exit at the open of the 12:00 bar unless the protective stop fired first.
  variant 'long_only' / 'short_then_long': i_l = i(reverse_time) for long_only, i(reverse_time) + 1 for short_then_long (one position
     at a time: the engine exits the short at the 12:00 open and the long enters at the 12:01 open). place(i_l, +1, stop_pts with
     ref = close of bar i_l - 1); exit_at(i(long_exit)) = market exit at the open of the 14:00 bar. If the short's stop fired before
     12:00 the long still enters.
  No re-entry after a stop within a leg (max_trades_day caps the count; each leg has exactly one entry index). No targets.
EXIT: protective stop or clock exit; force_flat from long_exit (14:00) to session end so nothing can remain after 14:00.
  set_session(short_start, reverse_time + 2 min, long_exit) for 'short_then_long' / 'short_only';
  set_session(reverse_time, reverse_time + 2 min, long_exit) for 'long_only'.
SESSION/RISK: max_trades_day = min(max_trades, legs) (2 for short_then_long, 1 for the single-leg variants).
  daily_loss_stop = dls_mult x Lucid block (MES $60, MNQ $80 per micro; two clock trades a day can both lose on a trend day);
  daily_profit_stop none (small edge, no monster days).
Diagnostics: lunch_profile(df1, contract) returns the per-session 11:00->12:00 and 12:00->14:00 close-to-close returns (bp) with the
  macro_day / fomc / opex flags, the raw 'lunch profile' on our data (the reusable by-product even if the trade is dead).
"""
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm
from strategies.common import daily_atr
from strategies._cal_flags import flags

NAME = 'Lunch effect: short 11:00-12:00 / long 12:00-14:00 (Quantpedia 2024), default long-only midday leg'
DESCRIPTION = __doc__
CONTRACTS = ['MES', 'MNQ']
PARAMS = {'variant': 'long_only', 'short_start': '11:00', 'reverse_time': '12:00', 'long_exit': '14:00',
          'stop_mode': 'pct', 'stop_pct': 0.4, 'stop_atr': 0.4, 'skip_macro': True, 'skip_opex': False, 'max_trades': 2,
          'dls_mult': 1.0}
GRID = {'variant': ['long_only', 'short_then_long'], 'stop_pct': [0.3, 0.5], 'long_exit': ['13:30', '14:00'],
        'skip_macro': [True, False]}   # 16 combos (stop_mode fixed 'pct'); extra single run outside the grid: stop_mode='atr'
LOSS_BLOCK = {'MES': 60.0, 'MNQ': 80.0, 'MGC': 80.0, 'ES': 600.0, 'NQ': 800.0, 'GC': 800.0}
_WIN = 5   # minutes of tolerance for a missing minute bar (CFD feed gap)
VARIANTS = ('long_only', 'short_then_long', 'short_only')


def _tod_str(minutes: int) -> str:
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def _index_at(df1: pd.DataFrame, t: int) -> pd.Series:
    """i(t): 1-min index of the first bar with t <= tod < t+_WIN, per day_id (float, NaN when missing)."""
    b = df1[(df1['tod'] >= t) & (df1['tod'] < t + _WIN)]
    if not len(b):
        return pd.Series(dtype=float)
    first = b.groupby('day_id').head(1)
    return pd.Series(first.index.values.astype(float), index=first['day_id'].values)


def _close_at(df1: pd.DataFrame, t: int) -> pd.Series:
    """c(t): close of the last bar with t-_WIN <= tod < t, per day_id (the price 'at' t)."""
    b = df1[(df1['tod'] >= t - _WIN) & (df1['tod'] < t)]
    return b.groupby('day_id')['close'].last()


def _ref_close(df1: pd.DataFrame, idx: pd.Series) -> np.ndarray:
    """Close of the bar before each entry index (NaN when that bar belongs to another session or the index is missing)."""
    n = len(df1); day = df1['day_id'].values; cl = df1['close'].values
    ii = idx.values
    ok = ~np.isnan(ii)
    i = np.where(ok, ii, 1).astype(int)
    prev = np.clip(i - 1, 0, n - 1)
    same = ok & (i >= 1) & (day[prev] == day[np.clip(i, 0, n - 1)])
    return np.where(same, cl[prev], np.nan)


def day_table(df1: pd.DataFrame, contract, p: dict) -> pd.DataFrame:
    """Per-session inputs (indexed by day_id): flags, ATR, the clock indices and reference closes, day_ok.
    Every column uses only information available before the 11:00 bar opens (macro_day is known at 08:32)."""
    if p['variant'] not in VARIANTS:
        raise ValueError(f'unknown variant={p["variant"]!r}')
    rth = (contract.rth_open, contract.rth_close)
    F = flags(df1, rth=rth)
    t = pd.DataFrame(index=F.index)
    t['session'] = F['session']
    for col in ('macro_day', 'macro0830', 'fomc', 'opex'):
        t[col] = F[col].astype(bool)
    t['atr'] = daily_atr(df1, 14, rth_only=True, rth=rth).reindex(t.index)
    ts, tr, tx = hm(p['short_start']), hm(p['reverse_time']), hm(p['long_exit'])
    if not (ts < tr < tx):
        raise ValueError('need short_start < reverse_time < long_exit')
    t['i_short'] = _index_at(df1, ts).reindex(t.index)
    t['i_rev'] = _index_at(df1, tr).reindex(t.index)
    t['i_exit'] = _index_at(df1, tx).reindex(t.index)
    if p['variant'] == 'short_then_long':
        # the long enters one bar after the short's clock exit; that bar must belong to the same session
        n = len(df1); day = df1['day_id'].values
        ir = t['i_rev'].values
        nxt = np.where(np.isnan(ir), np.nan, np.clip(ir + 1, 0, n - 1))
        ok = ~np.isnan(nxt) & (day[np.where(np.isnan(nxt), 0, nxt).astype(int)] == t.index.values)
        t['i_long'] = np.where(ok, nxt, np.nan)
    else:
        t['i_long'] = t['i_rev']
    t['ref_short'] = _ref_close(df1, t['i_short'])
    t['ref_long'] = _ref_close(df1, t['i_long'])
    ok = t['atr'].notna() & t['i_exit'].notna()
    if p['variant'] in ('short_only', 'short_then_long'):
        ok &= t['i_short'].notna() & t['i_rev'].notna() & t['ref_short'].notna()
    if p['variant'] in ('long_only', 'short_then_long'):
        ok &= t['i_long'].notna() & t['ref_long'].notna() & (t['i_long'] < t['i_exit'])
    if p['skip_macro']:
        ok &= ~(t['macro_day'] | t['fomc'])
    if p['skip_opex']:
        ok &= ~t['opex']
    t['day_ok'] = ok
    return t


def _stop_pts(p: dict, ref: np.ndarray, atr: np.ndarray) -> np.ndarray:
    if p['stop_mode'] == 'pct':
        return float(p['stop_pct']) / 100.0 * ref
    if p['stop_mode'] == 'atr':
        return float(p['stop_atr']) * atr
    raise ValueError(f'unknown stop_mode={p["stop_mode"]!r}')


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS, **params}
    it = Intents(df1)
    t = day_table(df1, contract, p)
    tr = t[t['day_ok']]
    variant = p['variant']
    legs = 2 if variant == 'short_then_long' else 1
    if len(tr):
        atr = tr['atr'].values
        if variant in ('short_only', 'short_then_long'):
            it.place(tr['i_short'].values.astype(int), -1, stop_pts=_stop_pts(p, tr['ref_short'].values, atr))
            it.exit_at(tr['i_rev'].values.astype(int), which=2)          # market exit at the 12:00 open
        if variant in ('long_only', 'short_then_long'):
            it.place(tr['i_long'].values.astype(int), +1, stop_pts=_stop_pts(p, tr['ref_long'].values, atr))
            it.exit_at(tr['i_exit'].values.astype(int), which=2)         # market exit at the 14:00 open
    start = p['short_start'] if variant != 'long_only' else p['reverse_time']
    it.set_session(start, _tod_str(hm(p['reverse_time']) + 2), p['long_exit'])
    it.max_trades_day = min(int(p['max_trades']), legs)
    it.daily_loss_stop = float(p['dls_mult']) * LOSS_BLOCK.get(contract.name, 0.0)
    return it


def lunch_profile(df1: pd.DataFrame, contract, short_start='11:00', reverse_time='12:00', long_exit='14:00') -> pd.DataFrame:
    """Per session: r_am = c(reverse_time)/c(short_start) - 1 and r_pm = c(long_exit)/c(reverse_time) - 1 in basis points
    (close-to-close, no costs), with the macro_day / fomc / opex flags and the year. c(T) = close of the last bar before T."""
    rth = (contract.rth_open, contract.rth_close)
    F = flags(df1, rth=rth)
    out = pd.DataFrame(index=F.index)
    out['session'] = F['session']
    out['year'] = pd.to_datetime(out['session']).dt.year
    for col in ('macro_day', 'fomc', 'opex', 'valid'):
        out[col] = F[col].astype(bool)
    c1 = _close_at(df1, hm(short_start)).reindex(out.index)
    c2 = _close_at(df1, hm(reverse_time)).reindex(out.index)
    c3 = _close_at(df1, hm(long_exit)).reindex(out.index)
    out['c_short'] = c1; out['c_rev'] = c2; out['c_exit'] = c3
    out['r_am_bp'] = 1e4 * (c2 / c1 - 1.0)
    out['r_pm_bp'] = 1e4 * (c3 / c2 - 1.0)
    return out
