"""5-min bullish FVG nested inside a 15-min bullish FVG, long only, fixed R-multiple target (NQ "Strategy B").

Family evidence_and_failures; source: GitHub prashanthaitha24/nq-strategy-b-bot (research/families/evidence_and_failures.md 2.1).

COMMON: all times ET. A decision on the close of 5-min bar k is executed at the 1-min index B5.i_next[k] (first 1-min bar after
the 5-min bar closes; skipped when -1 = session ended), market at that bar's open (+1 tick slippage in the engine). Every
"NQ point" parameter is scaled by PT = {MNQ: 1.0, MES: 0.28}; min_stop_pts = {MNQ: 6, MES: 4}. One position at a time (engine).
BARS: B5 = resample(df1, 5, rth_only=True); B15 = resample(df1, 15, rth_only=True). Both are CONTINUOUS across sessions (an RTH
chart), so zones persist into later days unless `same_session_only`.
FVG (bullish) on a bar series X: at bar j, if X.low[j] > X.high[j-2] + min_gap -> zone {bottom = X.high[j-2], top = X.low[j],
born_i = X.i_last[j], born_bar = j}. Bearish (side='both' only): X.high[j] < X.low[j-2] - min_gap -> {bottom = X.high[j],
top = X.low[j-2]}. min_gap = min_gap5 for B5, min_gap15 for B15.
ACTIVE: a bullish zone is active from bar j+1 until the first later bar whose low <= bottom (filled -> dead for good) or until
age = (current bar - j) > max_age bars; with same_session_only the zone also dies at the session end. "Active at k" uses bars
strictly before k (bar k's own low is tested by the signal). For B15 the bars strictly before k are the 15-min bars that COMPLETED
before 5-min bar k opened (i_last < B5.i_first[k]); the "current" 15-min bar for the age test is the one containing bar k.
SIGNAL on 5-min bar k with tod[k] >= entry_start and tod[k] + 5 <= last_entry: candidates = {f in F5 active at k, born before k,
such that there is F in F15 active at k, completed before bar k opened, with f.bottom >= F.bottom and f.top <= F.top + buffer_pts
(5-min zone inside the 15-min zone, buffer at the top); B5.low[k] <= f.top and B5.low[k] > f.bottom (bar k dips INTO the
5-min FVG, not through it); B5.close[k] > f.top (closes back above it)}. f = candidate with the highest top. c = B5.close[k];
stop = f.bottom - stop_off_pts; R = c - stop; skip if R < min_R or R > max_R or R < min_stop_pts. Order: market long at the
open of B5.i_next[k], stop_px = stop, tgt_px = c + rr * R; no trailing, no time exit. side='both' mirrors with bearish zones.
SESSION: set_session(entry_start, last_entry + 1 min, flat): the +1 min lets the signal bar that closes exactly at last_entry
fill at that minute's open (the published rule is "signal time 09:30-12:00"). Flat at `flat` (15:45 published).
RISK: max_trades_day = max_trades; daily_loss_stop = {MNQ: 40, MES: 35} x dls_mult; daily_profit_stop = {MNQ: 60, MES: 50} x
dps_mult ($ per ONE micro; 0 = off). `delay` = 1 places every order at B5.i_next[k+1] (sensitivity run)."""
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm, resample

NAME = '5-min FVG nested in 15-min FVG, long, 2R (NQ Strategy B)'
DESCRIPTION = __doc__
CONTRACTS = ['MNQ', 'MES']
PARAMS = {'rr': 2.0, 'buffer_pts': 5.0, 'stop_off_pts': 2.0, 'min_gap5': 2.0, 'min_gap15': 5.0, 'max_age5': 36, 'max_age15': 24,
          'entry_start': '09:30', 'last_entry': '12:00', 'flat': '15:45', 'max_trades': 2, 'side': 'long', 'same_session_only': False,
          'min_R': 8.0, 'max_R': 60.0, 'dls_mult': 1.0, 'dps_mult': 1.0, 'age_preset': None, 'delay': 0}
# age presets: A = short-lived, same session; B = published-like continuous; C = long-lived continuous
AGE_PRESETS = {'A': {'max_age5': 24, 'max_age15': 16, 'same_session_only': True},
               'B': {'max_age5': 36, 'max_age15': 24, 'same_session_only': False},
               'C': {'max_age5': 72, 'max_age15': 48, 'same_session_only': False}}
GRID = {'rr': [1.5, 2.0, 3.0], 'buffer_pts': [5.0, 10.0], 'age_preset': ['A', 'B', 'C'], 'max_trades': [1, 2]}

PT = {'MNQ': 1.0, 'NQ': 1.0, 'MES': 0.28, 'ES': 0.28}
MIN_STOP = {'MNQ': 6.0, 'NQ': 6.0, 'MES': 4.0, 'ES': 4.0}
DLS = {'MNQ': 40.0, 'NQ': 40.0, 'MES': 35.0, 'ES': 35.0}
DPS = {'MNQ': 60.0, 'NQ': 60.0, 'MES': 50.0, 'ES': 50.0}


def resolve(contract, params):
    p = {**PARAMS, **params}
    if p.get('age_preset'):
        p.update(AGE_PRESETS[p['age_preset']])
    pt = PT.get(contract.name, 1.0)
    p['_pt'] = pt
    for k in ('buffer_pts', 'stop_off_pts', 'min_gap5', 'min_gap15', 'min_R', 'max_R'):
        p[k + '_px'] = float(p[k]) * pt
    p['_min_stop'] = MIN_STOP.get(contract.name, 6.0 * pt)
    return p


class _Zones:
    """Incremental tracker of bullish FVG zones on one bar series (prices already oriented so that 'bullish' = up).
    feed(j) processes bar j: kills zones whose bottom was touched by bar j's low, then adds the zone born at bar j.
    active(cur_bar, day, max_age, same_session) returns the live zones as of bar `cur_bar` (bars < cur_bar fed)."""

    def __init__(self, lo, hi, i_last, day, min_gap):
        self.lo = lo; self.hi = hi; self.i_last = i_last; self.day = day; self.min_gap = min_gap
        self.z = []       # list of [born_bar, bottom, top, born_i, day]
        self.next = 0

    def feed_until(self, m):
        """Feed bars self.next .. m-1 (so that bars strictly before m are incorporated)."""
        lo, hi = self.lo, self.hi
        for j in range(self.next, m):
            l = lo[j]
            if self.z:
                self.z = [z for z in self.z if l > z[1]]
            if j >= 2 and l > hi[j - 2] + self.min_gap:
                self.z.append((j, hi[j - 2], l, self.i_last[j], self.day[j]))
        self.next = max(self.next, m)

    def active(self, cur_bar, cur_day, max_age, same_session):
        out = []
        for z in self.z:
            if cur_bar - z[0] > max_age:
                continue
            if same_session and z[4] != cur_day:
                continue
            out.append(z)
        # drop aged zones permanently (age only grows)
        self.z = [z for z in self.z if cur_bar - z[0] <= max_age]
        return out


def _signals(b5, b15, p, bullish=True):
    """Return arrays (idx, stop, target, close, bar_k) for one direction. For the bearish side the prices are negated so the
    bullish logic applies; prices are negated back before returning."""
    s = 1.0 if bullish else -1.0
    lo5 = (s * (b5['low'] if bullish else b5['high'])).values.astype(float)
    hi5 = (s * (b5['high'] if bullish else b5['low'])).values.astype(float)
    cl5 = (s * b5['close']).values.astype(float)
    lo15 = (s * (b15['low'] if bullish else b15['high'])).values.astype(float)
    hi15 = (s * (b15['high'] if bullish else b15['low'])).values.astype(float)
    tod5 = b5['tod'].values; day5 = b5['day_id'].values; i_first5 = b5['i_first'].values; i_next5 = b5['i_next'].values
    i_last5 = b5['i_last'].values; i_last15 = b15['i_last'].values; day15 = b15['day_id'].values
    z5 = _Zones(lo5, hi5, i_last5, day5, p['min_gap5_px'])
    z15 = _Zones(lo15, hi15, i_last15, day15, p['min_gap15_px'])
    # number of 15-min bars completed before 5-min bar k opened
    n15_before = np.searchsorted(i_last15, i_first5, side='left')
    t0 = hm(p['entry_start']); t1 = hm(p['last_entry'])
    buf = p['buffer_pts_px']; off = p['stop_off_pts_px']
    same = bool(p['same_session_only']); a5 = int(p['max_age5']); a15 = int(p['max_age15'])
    delay = int(p.get('delay', 0) or 0)
    idx = []; stops = []; tgts = []; closes = []; bars = []
    n = len(b5)
    for k in range(n):
        z5.feed_until(k)            # bars strictly before k
        z15.feed_until(n15_before[k])
        tk = tod5[k]
        if tk < t0 or tk + 5 > t1:
            continue
        lk = lo5[k]; ck = cl5[k]
        f5 = z5.active(k, day5[k], a5, same)
        if not f5:
            continue
        f15 = z15.active(n15_before[k], day5[k], a15, same)
        if not f15:
            continue
        best = None
        for (j, bot, top, born_i, zd) in f5:
            if not (lk <= top and lk > bot and ck > top):
                continue
            ok = False
            for (J, BOT, TOP, BI, ZD) in f15:
                if bot >= BOT and top <= TOP + buf:
                    ok = True; break
            if not ok:
                continue
            if best is None or top > best[2]:
                best = (j, bot, top, born_i, zd)
        if best is None:
            continue
        kk = k + delay
        if kk >= n or day5[kk] != day5[k]:
            continue
        i = i_next5[kk]
        if i < 0:
            continue
        stop = best[1] - off
        R = ck - stop
        if R < p['min_R_px'] or R > p['max_R_px'] or R < p['_min_stop']:
            continue
        idx.append(i); stops.append(s * stop); tgts.append(s * (ck + p['rr'] * R)); closes.append(s * ck); bars.append(k)
    return np.array(idx, dtype=int), np.array(stops), np.array(tgts), np.array(closes), np.array(bars, dtype=int)


def _mult(v):
    if v is None or (isinstance(v, str) and v.lower() == 'none'):
        return 0.0
    return float(v)


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = resolve(contract, params)
    it = Intents(df1)
    rth = ('09:30', '16:00')
    b5 = resample(df1, 5, rth_only=True, rth=rth)
    b15 = resample(df1, 15, rth_only=True, rth=rth)
    meta = []
    sides = [(1, True)] if p['side'] == 'long' else [(-1, False), (1, True)]
    for side, bullish in sides:
        idx, sp, tp, cl, bars = _signals(b5, b15, p, bullish)
        if len(idx):
            it.place(idx, np.full(len(idx), side, dtype=np.int8), stop_px=sp, tgt_px=tp)
            meta.append(pd.DataFrame({'i': idx, 'side': side, 'close': cl, 'stop': sp, 'tgt': tp, 'bar5': bars}))
    it.meta = pd.concat(meta, ignore_index=True) if meta else pd.DataFrame(columns=['i', 'side', 'close', 'stop', 'tgt', 'bar5'])
    end = hm(p['last_entry']) + 1
    it.set_session(p['entry_start'], f'{end // 60:02d}:{end % 60:02d}', p['flat'])
    it.max_trades_day = int(p['max_trades'])
    it.daily_loss_stop = float(DLS.get(contract.name, 40.0)) * _mult(p['dls_mult'])
    it.daily_profit_stop = float(DPS.get(contract.name, 60.0)) * _mult(p['dps_mult'])
    return it
