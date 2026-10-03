"""Inside-day range-target: open vs prior-day midpoint, trade from the open toward the prior extreme, stop at the midpoint.

edgeful 2025 / Connors-Raschke inside-day setup (family volatility_breakout, research/families/volatility_breakout.md 2.4-2.5,
spec research/specs/volatility_breakout.md section 3).

CONVENTIONS (all times ET). D = daily_bars(df1, rth_only=True, rth=(contract.rth_open, contract.rth_close)) = one RTH bar per
session (equities 09:30-16:00; gold pit 08:20-13:30). Every daily quantity for session d uses sessions < d only (shift(1));
NaN -> no trade. ATR = daily_atr(df1, 14) (already shifted). Early-close / thin RTH sessions are skipped.

DAILY SETUP (per session d): PDH = high[d-1], PDL = low[d-1], rng = PDH - PDL, mid = (PDH + PDL)/2.
  ID[d]  = high[d-1] < high[d-2] and low[d-1] > low[d-2]           (yesterday was an inside day)
  NR4[d] = rng[d-1] <= min(rng[d-4..d-1])                          (yesterday had the narrowest range of the last 4)
  setup_ok = {id: ID, nr4_or_id: NR4 or ID, id_nr4: ID and NR4, any: True}[setup]
OPEN: i0 = i_first[d] (the 09:30 / 08:20 bar); O = open[i0]; i1 = i0 + 1 (the order bar). Nothing after the open print is
  used for qualification.
DIRECTION: side = +1 if O > mid, -1 if O < mid, 0 -> skip. level = PDH (long) / PDL (short). dist = |level - O|.
TRADEABLE: setup_ok and side != 0 and (not require_inside_open or PDL < O < PDH) and min_dist_atr*ATR <= dist <= max_dist_atr*ATR
  and ATR, rng not NaN and not early_close.
ENTRY entry='market_0931': market at the open of bar i1 (+1 tick). entry='close_above_open': first 1-min bar k >= i1 of the
  same session with tod[k] < last_entry whose close is beyond O in the trade direction, PDL < close[k] < PDH and
  |level - close[k]| >= min_dist_atr*ATR -> market at the open of bar k+1 (same session); none -> no trade.
STOP: ref = O (market_0931) or close[k]. stop_mode='mid': R = |ref - mid|; 'frac': R = stop_frac*rng.
  R = min(R, max_stop_atr*ATR); R = max(R, min_stop_pts). Passed as stop_pts (applied from the actual fill).
TARGET: tgt_px = level + side*tgt_ext*rng (absolute; the engine needs a 1-tick trade-through).
TIME: time_stop != 'none' -> exit at the open of the first bar >= time_stop; forced flat at `flat`. One trade per day.
GOLD (MGC): pit daily bars; O = 08:20 open, i1 = 08:21, last_entry 09:30, time_stop option 11:30, flat 13:25.
"""
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm, daily_bars
from strategies.common import daily_atr

NAME = 'Inside-day range target (open vs prior midpoint, target prior extreme, stop at midpoint)'
DESCRIPTION = __doc__
CONTRACTS = ['MNQ', 'MES', 'MGC']
PARAMS = {'setup': 'id', 'entry': 'market_0931', 'stop_mode': 'mid', 'stop_frac': 0.5, 'tgt_ext': 0.0,
          'require_inside_open': True, 'min_dist_atr': 0.08, 'max_dist_atr': 0.6, 'max_stop_atr': 0.4,
          'min_stop_pts': None,          # None -> MIN_STOP_PTS[contract]
          'last_entry': '10:30', 'time_stop': 'none', 'flat': '15:55', 'max_trades': 1}
MIN_STOP_PTS = {'MES': 4.0, 'ES': 4.0, 'MNQ': 6.0, 'NQ': 6.0, 'MGC': 2.0, 'GC': 2.0}
GOLD_DEFAULTS = {'last_entry': '09:30', 'flat': '13:25'}
GOLD_TIME_STOP = {'13:00': '11:30'}      # the grid's equity time stop maps to this on gold
GRID = {'setup': ['id', 'nr4_or_id'], 'stop_mode': ['mid', 'frac'], 'tgt_ext': [0.0, 0.25], 'time_stop': ['none', '13:00']}


def _tod_str(minutes: int) -> str:
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def day_table(df1: pd.DataFrame, contract, p: dict) -> pd.DataFrame:
    """Per-session features and flags, all from sessions < d plus the open print of session d."""
    rth = (contract.rth_open, contract.rth_close)
    D = daily_bars(df1, rth_only=True, rth=rth)
    t = pd.DataFrame(index=D.index)
    t['session'] = D['session']; t['i0'] = D['i_first'].astype(int)
    t['pdh'] = D['high'].shift(1); t['pdl'] = D['low'].shift(1)
    t['rng'] = t['pdh'] - t['pdl']; t['mid'] = 0.5 * (t['pdh'] + t['pdl'])
    t['id'] = (D['high'].shift(1) < D['high'].shift(2)) & (D['low'].shift(1) > D['low'].shift(2))
    r = D['high'] - D['low']
    t['nr4'] = (r.shift(1) <= r.rolling(4, min_periods=4).min().shift(1))
    t['atr'] = daily_atr(df1, 14, rth_only=True, rth=rth).reindex(t.index)
    # early close / thin RTH session: fewer than 90% of the nominal RTH minutes or the last RTH bar > 30 min before the close
    o, c = hm(rth[0]), hm(rth[1])
    rr = df1[(df1['tod'] >= o) & (df1['tod'] < c)].groupby('day_id')
    nb = rr.size().reindex(t.index).fillna(0); lt = rr['tod'].last().reindex(t.index)
    t['early_close'] = (nb < 0.9 * (c - o)) | (lt < c - 30) | lt.isna()
    # the open print: the first RTH bar must be the rth_open bar itself
    tod = df1['tod'].values; opn = df1['open'].values
    t['open_ok'] = tod[t['i0'].values] == o
    t['O'] = opn[t['i0'].values]
    t['side'] = np.where(t['O'] > t['mid'], 1, np.where(t['O'] < t['mid'], -1, 0))
    t['level'] = np.where(t['side'] > 0, t['pdh'], t['pdl'])
    t['dist'] = (t['level'] - t['O']).abs()
    setup = p['setup']
    if setup == 'id':
        ok = t['id']
    elif setup == 'nr4_or_id':
        ok = t['id'] | t['nr4']
    elif setup == 'id_nr4':
        ok = t['id'] & t['nr4']
    elif setup == 'any':
        ok = pd.Series(True, index=t.index)
    else:
        raise ValueError(f'unknown setup {setup!r}')
    ok = ok & t['open_ok'] & (t['side'] != 0) & t['atr'].notna() & t['rng'].notna() & (t['rng'] > 0) & ~t['early_close']
    ok &= (t['dist'] >= float(p['min_dist_atr']) * t['atr']) & (t['dist'] <= float(p['max_dist_atr']) * t['atr'])
    if p['require_inside_open']:
        ok &= (t['O'] > t['pdl']) & (t['O'] < t['pdh'])
    t['tradeable'] = ok.fillna(False).astype(bool)
    return t


def level_hit_stats(df1: pd.DataFrame, contract, p: dict, start=None, end=None) -> pd.DataFrame:
    """DIAGNOSTIC: share of qualifying sessions where `level` was touched (high >= PDH / low <= PDL) after the open,
    by side and by setup in {id, any}. Uses the session's own RTH bars only for the outcome, never for qualification."""
    rth = (contract.rth_open, contract.rth_close)
    D = daily_bars(df1, rth_only=True, rth=rth)
    rows = []
    for setup in ('id', 'nr4_or_id', 'any'):
        t = day_table(df1, contract, {**p, 'setup': setup})
        t = t[t['tradeable']]
        if start is not None:
            t = t[t['session'] >= pd.Timestamp(start).date()]
        if end is not None:
            t = t[t['session'] <= pd.Timestamp(end).date()]
        hi = D['high'].reindex(t.index); lo = D['low'].reindex(t.index)
        hit = np.where(t['side'] > 0, hi >= t['level'], lo <= t['level'])
        stop = np.where(t['side'] > 0, lo <= t['mid'], hi >= t['mid'])
        for s in (1, -1):
            m = t['side'].values == s
            rows.append({'setup': setup, 'side': 'long' if s > 0 else 'short', 'n': int(m.sum()),
                         'hit_level': float(hit[m].mean()) if m.any() else np.nan,
                         'touch_mid': float(stop[m].mean()) if m.any() else np.nan})
    return pd.DataFrame(rows)


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS}
    if contract.name in ('MGC', 'GC'):
        p.update(GOLD_DEFAULTS)
    p.update(params)
    if contract.name in ('MGC', 'GC') and p['time_stop'] in GOLD_TIME_STOP:
        p['time_stop'] = GOLD_TIME_STOP[p['time_stop']]
    min_stop = float(p['min_stop_pts']) if p['min_stop_pts'] is not None else MIN_STOP_PTS.get(contract.name, 4.0)
    it = Intents(df1)
    t = day_table(df1, contract, p)
    t = t[t['tradeable']]
    tod = df1['tod'].values; day = df1['day_id'].values; c = df1['close'].values
    n = len(df1)
    o_tod = hm(contract.rth_open)
    last_entry = hm(p['last_entry'])
    use_scan = p['entry'] == 'close_above_open'
    min_d = float(p['min_dist_atr']); max_stop_atr = float(p['max_stop_atr']); tgt_ext = float(p['tgt_ext'])
    idx, sides, spts, tpx = [], [], [], []
    for d, r in t.iterrows():
        i0 = int(r['i0']); i1 = i0 + 1; side = int(r['side'])
        if i1 >= n or day[i1] != d:
            continue
        rng = float(r['rng']); atr = float(r['atr']); level = float(r['level']); mid = float(r['mid'])
        if use_scan:
            k = i1; found = -1
            while k < n and day[k] == d and tod[k] < last_entry:
                ck = c[k]
                if (ck - r['O']) * side > 0 and r['pdl'] < ck < r['pdh'] and abs(level - ck) >= min_d * atr:
                    found = k; break
                k += 1
            if found < 0 or found + 1 >= n or day[found + 1] != d:
                continue
            ref = float(c[found]); order = found + 1
        else:
            ref = float(r['O']); order = i1
        if p['stop_mode'] == 'mid':
            R = abs(ref - mid)
        elif p['stop_mode'] == 'frac':
            R = float(p['stop_frac']) * rng
        else:
            raise ValueError(f'unknown stop_mode {p["stop_mode"]!r}')
        R = min(R, max_stop_atr * atr); R = max(R, min_stop)
        idx.append(order); sides.append(side); spts.append(R); tpx.append(level + side * tgt_ext * rng)
    if idx:
        it.place(np.array(idx, dtype=int), np.array(sides, dtype=np.int8), stop_pts=np.array(spts), tgt_px=np.array(tpx))
    if p['time_stop'] != 'none':
        ts = hm(p['time_stop'])
        after = (tod >= ts) & (tod < hm('18:00'))
        first_after = np.flatnonzero(after & np.r_[True, (day[1:] != day[:-1]) | ~after[:-1]])
        it.exit_at(first_after, which=2)
    e_start = o_tod + 1
    e_end = last_entry if use_scan else o_tod + 2
    it.set_session(_tod_str(e_start), _tod_str(e_end), p['flat'])
    it.max_trades_day = int(p['max_trades'])
    it.daily_loss_stop = 0.0; it.daily_profit_stop = 0.0
    return it
