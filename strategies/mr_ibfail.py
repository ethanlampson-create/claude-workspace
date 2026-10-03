"""Initial-balance failed-breakout fade (Market Profile; tradingstats ES/NQ 2015-2025 statistics).

IB = high/low of the 1-min bars from 09:30 for `ib_minutes` (default 60 -> 09:30..10:29 inclusive). ATR = 14-day RTH
daily ATR (lagged). Skip the day if IB range > `max_ib_atr` x ATR (extreme IB) or ATR is NaN.
Decision bars: 5-min RTH bars starting at IB end. BREAK = the first 5-min bar at/after the IB end and before
`break_deadline` whose high > IB_high (up) or low < IB_low (down); both in one bar -> the side farther from the bar's
open. Only the first break of the day is eligible. Extreme = running max high (up) / min low (down) from the break bar
on. FAILURE = a 5-min bar within `fail_window` minutes after the break bar's close (the next fail_window/5 bars) and
starting before `fail_deadline`, that closes back inside the IB (up: close < IB_high; down: close > IB_low).
ENTRY = market at the open of the 1-min bar after the failure bar (i_next), opposite to the break (failed up-break ->
short, failed down-break -> long). STOP = 1 tick beyond the extreme since the break, but no farther than
`stop_cap_atr` x ATR from entry (then stop = entry -/+ cap, relative to the fill). TARGET: 'mid' = IB midpoint,
'far' = opposite IB edge. TIME EXIT at the first bar >= `exit_time`; force flat at `flat`. One trade per day."""
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm, resample
from strategies.common import opening_range, daily_atr

NAME = 'IB failed-breakout fade'
DESCRIPTION = __doc__
CONTRACTS = ['MES', 'MNQ']
PARAMS = {'ib_minutes': 60, 'break_deadline': '11:30', 'fail_window': 30, 'fail_deadline': '12:00', 'stop_cap_atr': 0.25,
          'tgt': 'mid', 'exit_time': '13:00', 'flat': '15:55', 'max_ib_atr': 1.5, 'sides': 'both', 'max_trades': 1,
          'bar': 5, 'break_mode': 'touch', 'min_break_atr': 0.0}
# break_mode: 'touch' = any 5-min bar high/low beyond the IB edge (published rule); 'close' = the break bar must also
# CLOSE outside the IB (a confirmed break; follow-up hypothesis). min_break_atr: minimum excursion of the extreme beyond
# the IB edge, in ATR, for the failure to count (0 = published rule).
GRID = {'fail_window': [15, 30, 45], 'tgt': ['mid', 'far'], 'stop_cap_atr': [0.25, 0.40], 'sides': ['both', 'long']}


def day_signals(df1: pd.DataFrame, contract, p: dict) -> pd.DataFrame:
    """One row per day with a qualifying failed break: i_entry, side, stop_px/stop_pts, tgt_px plus diagnostics."""
    rth = (contract.rth_open, contract.rth_close)
    ib = opening_range(df1, contract.rth_open, int(p['ib_minutes']))
    datr = daily_atr(df1, 14, rth_only=True, rth=rth).rename('atr')
    ib = ib.join(datr)
    rng = ib['or_high'] - ib['or_low']
    ok = ib['atr'].notna() & (rng <= p['max_ib_atr'] * ib['atr']) & (rng > 0)
    ib = ib[ok]
    b = resample(df1, int(p['bar']), rth_only=True, rth=rth)
    ib_end_tod = hm(contract.rth_open) + int(p['ib_minutes'])
    brk_dl = hm(p['break_deadline']); fail_dl = hm(p['fail_deadline'])
    n_fail = max(1, int(p['fail_window']) // int(p['bar']))
    tick = contract.tick
    bh = b['high'].values; bl = b['low'].values; bo = b['open'].values; bc = b['close'].values
    btod = b['tod'].values; bnext = b['i_next'].values; bday = b['day_id'].values
    # per-day slices of the 5-min bar table
    starts = np.flatnonzero(np.r_[True, bday[1:] != bday[:-1]]); ends = np.r_[starts[1:], len(b)]
    day_pos = {int(bday[s]): (int(s), int(e)) for s, e in zip(starts, ends)}
    rows = []
    for d, r in ib.iterrows():
        d = int(d)
        if d not in day_pos:
            continue
        s, e = day_pos[d]
        ibh = float(r['or_high']); ibl = float(r['or_low']); atr_ = float(r['atr'])
        # decision bars: at/after IB end
        k0 = s
        while k0 < e and btod[k0] < ib_end_tod:
            k0 += 1
        # first break before the deadline
        kb = -1; side_brk = 0
        for k in range(k0, e):
            if btod[k] >= brk_dl:
                break
            up = bh[k] > ibh; dn = bl[k] < ibl
            if p['break_mode'] == 'close':
                up = up and bc[k] > ibh; dn = dn and bc[k] < ibl
            if up and dn:
                side_brk = 1 if (bh[k] - bo[k]) >= (bo[k] - bl[k]) else -1; kb = k; break
            if up:
                side_brk = 1; kb = k; break
            if dn:
                side_brk = -1; kb = k; break
        if kb < 0:
            continue
        # failure within the next n_fail bars, starting before fail_deadline
        kf = -1; ext = bh[kb] if side_brk > 0 else bl[kb]
        for k in range(kb + 1, min(e, kb + 1 + n_fail)):
            if btod[k] >= fail_dl:
                break
            ext = max(ext, bh[k]) if side_brk > 0 else min(ext, bl[k])
            inside = (bc[k] < ibh) if side_brk > 0 else (bc[k] > ibl)
            if inside:
                kf = k; break
        if kf < 0:
            continue
        depth = (ext - ibh) if side_brk > 0 else (ibl - ext)
        if depth < p['min_break_atr'] * atr_:
            continue
        i_entry = int(bnext[kf])
        if i_entry < 0:
            continue
        side = -side_brk
        if p['sides'] == 'long' and side < 0:
            continue
        if p['sides'] == 'short' and side > 0:
            continue
        ref = bc[kf]                                   # entry proxy: the failure bar's close (fill = next open + slip)
        cap = p['stop_cap_atr'] * atr_
        if side < 0:
            stop_abs = ext + tick; dist = stop_abs - ref
        else:
            stop_abs = ext - tick; dist = ref - stop_abs
        if dist > cap:
            stop_px = np.nan; stop_pts = cap
        else:
            stop_px = stop_abs; stop_pts = np.nan
        if p['tgt'] == 'far':
            tgt = ibl if side < 0 else ibh
        else:
            tgt = 0.5 * (ibh + ibl)
        rows.append({'day_id': d, 'i_entry': i_entry, 'side': side, 'stop_px': stop_px, 'stop_pts': stop_pts, 'tgt_px': tgt,
                     'ib_high': ibh, 'ib_low': ibl, 'atr': atr_, 'ib_rng_atr': (ibh - ibl) / atr_, 'break_tod': int(btod[kb]),
                     'fail_tod': int(btod[kf]), 'ext': float(ext), 'ref': float(ref), 'stop_dist': float(min(dist, cap))})
    cols = ['day_id', 'i_entry', 'side', 'stop_px', 'stop_pts', 'tgt_px', 'ib_high', 'ib_low', 'atr', 'ib_rng_atr', 'break_tod',
            'fail_tod', 'ext', 'ref', 'stop_dist']
    return pd.DataFrame(rows, columns=cols)


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS, **params}
    it = Intents(df1)
    sig = day_signals(df1, contract, p)
    if len(sig):
        it.place(sig['i_entry'].values.astype(int), sig['side'].values.astype(np.int8), entry_px=np.nan,
                 stop_px=sig['stop_px'].values.astype(float), stop_pts=sig['stop_pts'].values.astype(float),
                 tgt_px=sig['tgt_px'].values.astype(float))
    tod = df1['tod'].values; day = df1['day_id'].values
    ex = hm(p['exit_time'])
    after = (tod >= ex) & (tod < hm('18:00'))
    first_after = np.flatnonzero(after & np.r_[True, (day[1:] != day[:-1]) | ~after[:-1]])
    it.exit_at(first_after, which=2)
    it.set_session(contract.rth_open, p['exit_time'], p['flat'])
    it.max_trades_day = p['max_trades']
    return it
