"""Initial Balance (first hour) C-period confirmation breakout, midpoint stop, IB-extension target (Market Profile).

Family orb_session (research/families/orb_session.md: tradingstats IB statistics ES/NQ 2015-2025). All times ET.

Rules as implemented:
- IB = high/low of the 1-min bars in [rth_open, rth_open+60) (09:30-10:30 equities; 08:20-09:20 gold) via
  strategies.common.opening_range. ib_rng = ib_high - ib_low; ib_mid = midpoint. ATR = Wilder ATR(14) of daily RTH bars,
  shifted one day (daily_atr). The C period is built from the 1-min bars (opening_range anchored at the IB end).
- Width filter: skip the day if ib_rng < ib_min_atr*ATR, ib_rng > ib_max_atr*ATR or ATR NaN. `narrow_only`: additionally
  require ib_rng < narrow_atr*ATR (0.5).
- mode 'c_confirm' (default): C period = [IB end, IB end + c_minutes) (10:30-11:00 equities, 09:20-09:50 gold). At its close, if
  C close > ib_high -> long, if C close < ib_low -> short, else no trade. Reject if the C close is already more than
  max_ext_entry*ib_rng beyond the broken edge (do not chase). Entry = market at the open of the first 1-min bar after the
  C bar (i_next = 11:00, +1 tick slippage).
- mode 'narrow_break': only if ib_rng < narrow_atr*ATR: buy stop at ib_high + buffer and sell stop at ib_low - buffer, live
  from the first bar after the IB (10:30) until last_entry (12:00). OCO emulated as in strategies/orb.py by scanning the
  1-min data for the first touch and placing only that side (both touched in one bar -> the side nearer that bar's open).
- Stop: stop_mode 'mid' = ib_mid (level) or 'atr' = fill -/+ stop_atr*ATR (distance). Distance capped at max_stop_atr*ATR
  from the fill (cap applied as a relative distance when the level is too far).
- Target = ib_high + tgt_ext*ib_rng (long) / ib_low - tgt_ext*ib_rng (short), absolute level.
- retrace_exit (optional): after entry, the first 1-min CLOSE that is more than retrace_frac*ib_rng back inside the IB
  from the broken edge triggers a market exit at the open of the next bar (engine exit_flag, side-specific).
- Exits: stop, target, retrace signal, forced flat at `flat`. One trade per day, no re-entry.
- Session: c_confirm -> entries in [IB end + 30 min, last_entry) (default 11:00-11:01); narrow_break -> [IB end, last_entry)
  (default 10:30-12:00). Gold defaults: C-entry 09:50, last_entry 09:51 / 10:50, flat 13:25.
Look-ahead: the C bar is fully closed before the i_next order; the IB is only used after its last bar; ATR is shifted;
the narrow_break scan only decides which pending stop would have filled first (the fill itself is simulated by the engine).
"""
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm
from strategies.common import opening_range, daily_atr

NAME = 'IB C-period confirmation breakout (midpoint stop, IB-extension target)'
DESCRIPTION = __doc__
CONTRACTS = ['MES', 'MNQ']
PARAMS = {'mode': 'c_confirm', 'ib_minutes': 60, 'c_minutes': 30, 'ib_min_atr': 0.2, 'ib_max_atr': 1.5, 'narrow_only': False,
          'narrow_atr': 0.5, 'max_ext_entry': 0.5, 'stop_mode': 'mid', 'stop_atr': 0.25, 'max_stop_atr': 0.5, 'tgt_ext': 0.5,
          'retrace_exit': False, 'retrace_frac': 0.5, 'buffer_ticks': 1, 'last_entry': None, 'flat': '15:55', 'max_trades': 1}
GOLD_DEFAULTS = {'flat': '13:25'}
GRID = {'mode': ['c_confirm', 'narrow_break'], 'stop_mode': ['mid', 'atr'], 'tgt_ext': [0.5, 1.0], 'ib_max_atr': [1.0, 1.5],
        'narrow_only': [False, True]}


def _tod_str(minutes: int) -> str:
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def _stop(side, est_entry, ib_high, ib_low, atr_, p):
    """(stop_px, stop_pts) for the engine given an estimated entry price; NaN for the unused one. None = invalid."""
    cap = float(p['max_stop_atr'] * atr_)
    if p['stop_mode'] == 'atr':
        return np.nan, float(min(p['stop_atr'] * atr_, cap))
    mid = 0.5 * (ib_high + ib_low)
    dist = (est_entry - mid) * side
    if dist <= 0:
        return None
    if dist > cap:
        return np.nan, cap
    return float(mid), np.nan


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS}
    if contract.name in ('MGC', 'GC'):
        p.update(GOLD_DEFAULTS)
    p.update(params)
    it = Intents(df1)
    rth = (contract.rth_open, contract.rth_close)
    ib_minutes = int(p['ib_minutes']); c_minutes = int(p['c_minutes'])
    ib_end = hm(contract.rth_open) + ib_minutes          # 10:30
    c_end = ib_end + c_minutes                           # 11:00
    mode = p['mode']
    if p['last_entry'] is None:
        last_entry = c_end + 1 if mode == 'c_confirm' else ib_end + 90
    else:
        last_entry = hm(p['last_entry'])

    ib = opening_range(df1, contract.rth_open, ib_minutes)
    datr = daily_atr(df1, 14, rth_only=True, rth=rth).rename('atr')
    ib = ib.join(datr)
    ib['rng'] = ib['or_high'] - ib['or_low']
    ok = ib['atr'].notna() & (ib['rng'] > 0) & (ib['rng'] >= p['ib_min_atr'] * ib['atr']) & (ib['rng'] <= p['ib_max_atr'] * ib['atr'])
    if p['narrow_only'] or mode == 'narrow_break':
        ok &= ib['rng'] < p['narrow_atr'] * ib['atr']
    # the IB must be complete (a thin session with no bar near the IB end would otherwise give a partial range)
    ok &= ib['n_bars'] >= int(0.8 * ib_minutes)
    ib = ib[ok]

    h = df1['high'].values; l = df1['low'].values; o = df1['open'].values; c = df1['close'].values
    day = df1['day_id'].values; tod = df1['tod'].values; n = len(df1)
    buf = p['buffer_ticks'] * contract.tick
    idx, side, entry_px, stop_px, stop_pts, tgt_px = [], [], [], [], [], []
    valid = 0
    rows = []   # (i_entry, side, ib_high, ib_low) for the retrace exit scan

    if mode == 'c_confirm':
        # C period = [ib_end, c_end) built from the 1-min bars (a 30-min resample would mis-align on gold's 08:20 open);
        # i_next = the first 1-min bar after the C period in the same session
        cb = opening_range(df1, _tod_str(ib_end), c_minutes)
        cb = cb[cb.index.isin(ib.index) & (cb['n_bars'] >= int(0.8 * c_minutes))]
        for d, r in cb.iterrows():
            i_e = int(r['i_end']) + 1
            if i_e >= n or day[i_e] != d:
                continue
            ibr = ib.loc[d]; ibh = float(ibr['or_high']); ibl = float(ibr['or_low']); rng = float(ibr['rng']); atr_ = float(ibr['atr'])
            cc = float(r['or_close'])
            if cc > ibh:
                s = 1; ext = cc - ibh
            elif cc < ibl:
                s = -1; ext = ibl - cc
            else:
                continue
            if ext > p['max_ext_entry'] * rng:
                continue
            st = _stop(s, cc, ibh, ibl, atr_, p)
            if st is None:
                continue
            tp = ibh + p['tgt_ext'] * rng if s > 0 else ibl - p['tgt_ext'] * rng
            if (tp - cc) * s <= contract.tick:
                continue
            idx.append(i_e); side.append(s); entry_px.append(np.nan); stop_px.append(st[0]); stop_pts.append(st[1]); tgt_px.append(tp)
            rows.append((i_e, s, ibh, ibl, rng))
    elif mode == 'narrow_break':
        valid = max(1, last_entry - ib_end)
        for d, ibr in ib.iterrows():
            i0 = int(ibr['i_end']) + 1
            if i0 >= n or day[i0] != d:
                continue
            ibh = float(ibr['or_high']); ibl = float(ibr['or_low']); rng = float(ibr['rng']); atr_ = float(ibr['atr'])
            hi = ibh + buf; lo = ibl - buf
            k = i0; first = 0
            while k < n and day[k] == d and tod[k] < last_entry and (k - i0) < valid:
                up = h[k] >= hi; dn = l[k] <= lo
                if up and dn:
                    first = 1 if (hi - o[k]) <= (o[k] - lo) else -1; break
                if up:
                    first = 1; break
                if dn:
                    first = -1; break
                k += 1
            if first == 0:
                continue
            s = first; est = hi if s > 0 else lo
            st = _stop(s, est, ibh, ibl, atr_, p)
            if st is None:
                continue
            tp = ibh + p['tgt_ext'] * rng if s > 0 else ibl - p['tgt_ext'] * rng
            idx.append(i0); side.append(s); entry_px.append(est); stop_px.append(st[0]); stop_pts.append(st[1]); tgt_px.append(tp)
            rows.append((i0, s, ibh, ibl, rng))
    else:
        raise ValueError(f'unknown mode {mode!r}')

    if idx:
        it.place(np.array(idx, dtype=int), np.array(side, dtype=np.int8), entry_px=np.array(entry_px, dtype=float),
                 valid_bars=valid, stop_px=np.array(stop_px, dtype=float), stop_pts=np.array(stop_pts, dtype=float),
                 tgt_px=np.array(tgt_px, dtype=float))
    if p['retrace_exit'] and rows:
        flat_tod = hm(p['flat'])
        for i_e, s, ibh, ibl, rng in rows:
            lvl = (ibh - p['retrace_frac'] * rng) if s > 0 else (ibl + p['retrace_frac'] * rng)
            k = i_e
            while k < n - 1 and day[k] == day[i_e] and tod[k] < flat_tod:
                if (s > 0 and c[k] < lvl) or (s < 0 and c[k] > lvl):
                    if day[k + 1] == day[i_e]:
                        it.exit_at(np.array([k + 1]), which=s)   # side-specific: a no-op if already flat
                    break
                k += 1
    start = c_end if mode == 'c_confirm' else ib_end
    it.set_session(_tod_str(start), _tod_str(last_entry), p['flat'])
    it.max_trades_day = int(p['max_trades'])
    return it
