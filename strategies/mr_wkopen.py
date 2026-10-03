"""Weekly-open reversion: day-2 fade toward the week's first RTH open (tradingstats NQ 565-week study).

WEEK: the first session of a week is the first session whose weekday (dow of the session date) is lower than the
  previous session's weekday (Monday normally; Tuesday after a Monday holiday).  WO = open of that session's first RTH
  1-min bar (09:30 ET equities, 08:20 ET gold).
TRADE DAY: the next session of the same week (normally Tuesday).  allow_day3: if day 2 did not qualify (or was skipped),
  the same rule applies on day 3 with max_dist capped at 0.25%.
SETUP (at the trade day's RTH open, using only the first RTH bar): d = (open_rth - WO) / WO.
  qualify  min_dist% <= |d| <= max_dist%.  Open below WO -> LONG toward WO; above -> SHORT (sides='both'|'long'|'short').
  require_eth_touch: the overnight span (18:00 previous evening .. bar before the RTH open) must have traded through WO.
  Skip if WO was already touched in the RTH bars before entry (with entry_delay=1 that is the 09:30 bar only).
ENTRY: market at the open of the bar at rth_open + entry_delay minutes.
STOP: open_rth -/+ max(stop_mult * |open_rth - WO|, min_stop_pct% * open_rth).   TARGET: WO (fill 1 tick through).
TIME EXIT: open of the first bar >= exit_time.  Force flat at `flat`.  One trade per session, one trade per week.
"""
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm
from strategies.common import session_info

NAME = 'Weekly-open reversion (day-2 fade toward the week open)'
DESCRIPTION = __doc__
CONTRACTS = ['MNQ', 'MES', 'MGC']
PARAMS = {'max_dist': 0.25, 'min_dist': 0.05, 'stop_mult': 1.0, 'min_stop_pct': 0.15, 'entry_delay': 1, 'exit_time': '11:30',
          'flat': '15:55', 'sides': 'both', 'require_eth_touch': False, 'allow_day3': False, 'max_trades': 1}
GRID = {'max_dist': [0.25, 0.50], 'stop_mult': [1.0, 1.5], 'exit_time': ['11:30', '13:00'], 'sides': ['both', 'long']}
GRID_FOLLOWUP = {'require_eth_touch': [True, False], 'allow_day3': [True, False]}


def week_table(df1: pd.DataFrame, contract) -> pd.DataFrame:
    """Per day_id: dow, i_open (index of the first RTH bar), open_rth, overnight low/high (18:00 .. RTH open),
    week_id and day_in_week (1 = first session of the week), WO (week open) for every session."""
    o_tod = hm(contract.rth_open)
    si = session_info(df1, rth=(contract.rth_open, contract.rth_close))
    # first RTH bar of every session: the first bar with tod >= rth_open (normally exactly rth_open)
    r = df1[(df1['tod'] >= o_tod) & (df1['tod'] < hm('18:00'))]
    g = r.groupby('day_id')
    first = pd.DataFrame({'i_open': g.apply(lambda x: x.index[0]), 'open_tod': g['tod'].first(), 'open_rth': g['open'].first()})
    on = df1[(df1['tod'] >= hm('18:00')) | (df1['tod'] < o_tod)].groupby('day_id')
    onr = pd.DataFrame({'on_low': on['low'].min(), 'on_high': on['high'].max()})
    t = si[['session', 'dow']].join(first).join(onr)
    prev_dow = t['dow'].shift(1)
    new_week = (t['dow'] < prev_dow) | prev_dow.isna()
    t['week_id'] = new_week.cumsum()
    t['day_in_week'] = t.groupby('week_id').cumcount() + 1
    # the week open: the first session's open_rth (only valid when its first RTH bar is at the RTH open, +-5 min)
    wo = t[t['day_in_week'] == 1].set_index('week_id')
    wo_val = wo['open_rth'].where((wo['open_tod'] - o_tod).abs() <= 5)
    t['WO'] = t['week_id'].map(wo_val)
    return t


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS, **params}
    it = Intents(df1)
    t = week_table(df1, contract)
    o_tod = hm(contract.rth_open)
    entry_tod = o_tod + int(p['entry_delay'])
    tod = df1['tod'].values; day = df1['day_id'].values
    h = df1['high'].values; l = df1['low'].values
    n = len(df1)
    idx = []; sides = []; sps = []; tps = []
    traded_week = set()
    for d, r in t.iterrows():
        diw = int(r['day_in_week']); w = int(r['week_id'])
        if diw == 2:
            max_dist = float(p['max_dist'])
        elif diw == 3 and p['allow_day3'] and w not in traded_week:
            max_dist = min(float(p['max_dist']), 0.25)
        else:
            continue
        if not (np.isfinite(r['WO']) and np.isfinite(r['open_rth']) and np.isfinite(r['i_open'])):
            continue
        if r['open_tod'] != o_tod:
            continue                                            # first RTH bar missing: no clean open
        wo = float(r['WO']); op = float(r['open_rth'])
        dist = 100.0 * (op - wo) / wo
        if not (float(p['min_dist']) <= abs(dist) <= max_dist):
            continue
        side = 1 if dist < 0 else -1
        if p['sides'] == 'long' and side < 0:
            continue
        if p['sides'] == 'short' and side > 0:
            continue
        if p['require_eth_touch'] and not (np.isfinite(r['on_low']) and r['on_low'] <= wo <= r['on_high']):
            continue
        i0 = int(r['i_open']); k = i0
        while k < n and day[k] == d and tod[k] < entry_tod:
            k += 1
        if k >= n or day[k] != d or tod[k] != entry_tod:
            continue                                            # entry bar missing
        pre_hi = h[i0:k].max(); pre_lo = l[i0:k].min()
        if (side > 0 and pre_hi >= wo) or (side < 0 and pre_lo <= wo):
            continue                                            # WO already touched before entry
        stop_dist = max(float(p['stop_mult']) * abs(op - wo), float(p['min_stop_pct']) / 100.0 * op)
        sp = op - side * stop_dist
        idx.append(k); sides.append(side); sps.append(sp); tps.append(wo)
        traded_week.add(w)
    if idx:
        it.place(np.array(idx, dtype=int), np.array(sides, dtype=np.int8), stop_px=np.array(sps), tgt_px=np.array(tps))
    ex = hm(p['exit_time'])
    after = (tod >= ex) & (tod < hm('18:00'))
    first_after = np.flatnonzero(after & np.r_[True, (day[1:] != day[:-1]) | ~after[:-1]])
    it.exit_at(first_after, which=2)
    it.set_session(contract.rth_open, p['exit_time'], p['flat'])
    it.max_trades_day = p['max_trades']
    return it
