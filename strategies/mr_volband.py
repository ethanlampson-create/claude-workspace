"""Implied-vol band fade (prior RTH close +/- VIX/16) with VIX regime gate -- Seeck (2026), SSRN 7364204.

Reference level: C_ref = prior session's RTH close (last 1-min close before rth_close ET of the previous session;
09:30-16:00 for MES/MNQ, 08:20-13:30 for MGC). Vol input V = prior-day VIX close (strategies.common.vix_lag1, never
today's) x vol_mult (1.0 MES, 1.25 MNQ as a fixed VXN/VIX proxy, there is no VXN series in data/parquet). With
vol_src='rv20' (MGC) V = annualised realised vol = stdev of the last 20 daily log RTH close-to-close returns of days
< d x sqrt(252) x 100. Band half-width w = C_ref * (V / divisor) / 100; Upper = C_ref + w, Lower = C_ref - w.
Entry window 09:35-15:00 ET (MGC 08:25-13:00). If the FIRST 1-min close inside the window is already beyond a band
that band is pre-breached and not traded that day. Signal: the first 1-min bar inside the window whose close < Lower
-> long at market at the open of the next bar; first close > Upper -> short. Each band fires at most once per session
(max 2 trades/day, one position at a time; a signal that arrives while a position is open is ignored).
Exits: time exit after `hold` minutes (paper), protective stop stop_mult * w beyond the breached band, optional target
(tgt_mode 'none' = paper, 'ref' = C_ref, 'band' = the breached band). Force flat 15:55 ET.
Regime gate (gate=True): trade only when vix_lag1 < vix_low or vix_lag1 >= vix_high (skip 20 <= VIX < 30). The gate
always uses the VIX even when vol_src='rv20'. NaN VIX / C_ref / RV -> no trade.
Contract-dependent defaults (vol_mult, vol_src, entry_start, entry_end) are resolved when the param is None."""
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm, daily_bars
from strategies.common import vix_lag1

NAME = 'Implied-vol band fade (VIX/16) with VIX regime gate'
DESCRIPTION = __doc__
CONTRACTS = ['MNQ', 'MES']
PARAMS = {'divisor': 16, 'hold': 30, 'stop_mult': 0.5, 'tgt_mode': 'none', 'gate': True, 'vix_low': 20, 'vix_high': 30,
          'vol_mult': None, 'vol_src': None, 'entry_start': None, 'entry_end': None, 'flat': '15:55', 'sides': 'both',
          'max_trades': 2, 'allow_open_outside': False, 'rv_n': 20}
GRID = {'divisor': [14, 16, 20], 'hold': [30, 60], 'stop_mult': [0.5, 1.0], 'gate': [True, False]}
GRID_FOLLOWUP = {'tgt_mode': ['none', 'ref', 'band'], 'sides': ['both', 'long']}

_DEFAULTS = {  # per contract: vol_mult, vol_src, entry_start, entry_end
    'MES': (1.0, 'vix', '09:35', '15:00'), 'ES': (1.0, 'vix', '09:35', '15:00'),
    'MNQ': (1.25, 'vix', '09:35', '15:00'), 'NQ': (1.25, 'vix', '09:35', '15:00'),
    'MGC': (1.0, 'rv20', '08:25', '13:00'), 'GC': (1.0, 'rv20', '08:25', '13:00'),
}


def resolve(contract, params):
    p = {**PARAMS, **params}
    vm, vs, es, ee = _DEFAULTS.get(contract.name, (1.0, 'vix', '09:35', '15:00'))
    if p['vol_mult'] is None: p['vol_mult'] = vm
    if p['vol_src'] is None: p['vol_src'] = vs
    if p['entry_start'] is None: p['entry_start'] = es
    if p['entry_end'] is None: p['entry_end'] = ee
    return p


def bands(df1, contract, p):
    """Per day_id: C_ref (prior RTH close), V (vol in annualised %), w, upper, lower, vix (lag1) and tradable flag."""
    rth = (contract.rth_open, contract.rth_close)
    d = daily_bars(df1, rth_only=True, rth=rth)                     # sessions with at least one RTH bar
    all_days = pd.Index(np.arange(int(df1['day_id'].max()) + 1), name='day_id')
    c_ref = d['close'].shift(1).reindex(all_days)                   # strictly the previous session's RTH close
    vix = vix_lag1(df1).reindex(all_days)
    if p['vol_src'] == 'rv20':
        r = np.log(d['close']).diff()
        rv = r.rolling(p['rv_n'], min_periods=p['rv_n']).std().shift(1) * np.sqrt(252) * 100.0   # days < d only
        V = rv.reindex(all_days)
    else:
        V = vix * p['vol_mult']
    w = c_ref * (V / p['divisor']) / 100.0
    out = pd.DataFrame({'c_ref': c_ref, 'V': V, 'w': w, 'vix': vix})
    out['upper'] = c_ref + w; out['lower'] = c_ref - w
    ok = c_ref.notna() & V.notna() & vix.notna() & (w > 0)
    if p['gate']:
        ok &= (vix < p['vix_low']) | (vix >= p['vix_high'])
    out['ok'] = ok
    return out


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = resolve(contract, params)
    it = Intents(df1)
    b = bands(df1, contract, p)
    day = df1['day_id'].values; tod = df1['tod'].values; close = df1['close'].values
    n = len(df1)
    s, e = hm(p['entry_start']), hm(p['entry_end'])
    win = (tod >= s) & (tod < e)
    up = b['upper'].reindex(day).values; lo = b['lower'].reindex(day).values; ok = b['ok'].reindex(day).fillna(False).values.astype(bool)
    cref = b['c_ref'].reindex(day).values; w = b['w'].reindex(day).values
    below = win & ok & (close < lo); above = win & ok & (close > up)
    # first window bar per day -> pre-breach check
    wi = np.flatnonzero(win & ok)
    if len(wi) == 0:
        it.set_session(p['entry_start'], p['entry_end'], p['flat']); it.max_trades_day = p['max_trades']; return it
    first_bar = pd.Series(wi).groupby(day[wi]).first()               # day_id -> index of first window bar
    pre_lo = pd.Series(below[first_bar.values], index=first_bar.index)   # lower band already breached at window open
    pre_hi = pd.Series(above[first_bar.values], index=first_bar.index)
    idx_l = []; idx_s = []
    for mask, store, pre in ((below, idx_l, pre_lo), (above, idx_s, pre_hi)):
        j = np.flatnonzero(mask)
        if len(j) == 0:
            continue
        first = pd.Series(j).groupby(day[j]).first()                    # first breach bar per day
        if not p['allow_open_outside']:
            first = first[~pre.reindex(first.index).fillna(False).values.astype(bool)]
        sig = first.values + 1                                          # order live from the open of the NEXT bar
        keep = (sig < n)
        sig = sig[keep]
        keep2 = day[sig] == day[sig - 1]                                # same session
        store.extend(sig[keep2].tolist())
    if p['sides'] == 'long':
        idx_s = []
    elif p['sides'] == 'short':
        idx_l = []
    for idx, side in ((np.array(idx_l, dtype=int), 1), (np.array(idx_s, dtype=int), -1)):
        if len(idx) == 0:
            continue
        wd = w[idx]; band = lo[idx] if side > 0 else up[idx]
        stop_px = band - side * p['stop_mult'] * wd
        if p['tgt_mode'] == 'ref':
            tgt_px = cref[idx]
        elif p['tgt_mode'] == 'band':
            tgt_px = band
        else:
            tgt_px = np.full(len(idx), np.nan)
        it.place(idx, side, stop_px=stop_px, tgt_px=tgt_px, max_hold=int(p['hold']))
    it.set_session(p['entry_start'], p['entry_end'], p['flat'])
    it.max_trades_day = p['max_trades']
    return it
