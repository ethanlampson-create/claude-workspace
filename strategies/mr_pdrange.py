"""Outside-open re-entry: open beyond the prior-day RTH high/low, fade back to that level.

Two published variants (research/families/intraday_mean_reversion.md items 9 and 10):
  entry='market'  edgeful "outside days" / tradethatswing: open above PDH -> short at 09:35 targeting PDH; open below
                  PDL -> long targeting PDL (reported 64-75% touch rates on NQ, decaying beyond ~0.2% distance).
  entry='stop'    Larry Williams "Oops": the order is a STOP at the prior-day extreme that only fills once price
                  re-crosses back into the prior range (failure confirmed first); valid 09:31-11:30.

DEFINITIONS (per session d; nothing after the 09:30 open is used for qualification):
  PDH / PDL   = previous session RTH (09:30-16:00 ET) high / low  (strategies.common.prior_day_stats, shifted).
  prior_close = last 1-min close with tod < 16:00 ET of the previous session.
  open_0930   = open of the 09:30 ET 1-min bar.  ATR = 14-day RTH daily ATR, lagged (daily_atr).
SETUP: LONG if open_0930 < PDL, SHORT if open_0930 > PDH; level = PDL / PDH; dist = |open_0930 - level|.
QUALIFY: min_dist% * open <= dist <= max_dist% * open; dist <= dist_atr * ATR; |open_0930 - prior_close| / prior_close
  <= gap_cap%.  sides = both | long | short.
ENTRY entry='market': market at the open of the (09:30 + entry_delay) bar.  Skip if the level was already touched in
  the bars before entry (long: any high >= PDL; short: any low <= PDH).  Skip if the stop is already breached at the
  last pre-entry close (skip_beyond_stop; the bracket would be dead on arrival - my addition, same as mr_gapfade).
  Stop  = open_0930 -/+ max(stop_mult * dist, min_stop_pct% * open).
  Target = level + tgt_ext * (prior_close - level)   (tgt_ext 0 = the level itself, 1 = the prior close).
ENTRY entry='stop': from the 09:31 bar a buy stop at PDL + 1 tick (sell stop at PDH - 1 tick), live until
  stop_valid_until (valid_bars = minutes from 09:31 to that time).  Stop = level -/+ max(stop_mult * dist,
  min_stop_pct% * open).  Target = level +/- min(|prior_close - level|, tgt_atr * ATR) (prior close capped at 1 ATR).
  Days whose target would be closer than min_tgt_pct% of the open to the level are skipped (prior close sat at the
  level: the target would be at/below the fill - my addition).
EXIT: flat at the open of the first bar >= exit_time (Intents.exit_at), force flat at `flat`.  One trade per day.
"""
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm
from strategies.common import daily_atr, prior_day_stats

NAME = 'Outside-open re-entry to prior-day high/low (edgeful outside days / Williams Oops)'
DESCRIPTION = __doc__
CONTRACTS = ['MNQ', 'MES']
PARAMS = {'entry': 'market', 'max_dist': 0.30, 'min_dist': 0.05, 'dist_atr': 0.5, 'stop_mult': 1.0, 'min_stop_pct': 0.15,
          'tgt_ext': 0.0, 'tgt_atr': 1.0, 'entry_delay': 5, 'stop_valid_until': '11:30', 'exit_time': '12:00',
          'flat': '15:55', 'gap_cap': 1.0, 'sides': 'both', 'max_trades': 1, 'skip_beyond_stop': True, 'min_tgt_pct': 0.05}
GRID = {'entry': ['market', 'stop'], 'max_dist': [0.20, 0.30, 0.50], 'stop_mult': [1.0, 1.5], 'sides': ['both', 'long']}
FOLLOWUP_GRID = {'tgt_ext': [0.0, 0.5, 1.0], 'exit_time': ['12:00', '13:00']}


def day_table(df1: pd.DataFrame, contract, p: dict) -> pd.DataFrame:
    """Per-session features and qualification flags, all known at the 09:30 open. Indexed by day_id."""
    rth = (contract.rth_open, contract.rth_close)
    o_tod = hm(rth[0])
    pds = prior_day_stats(df1, rth=rth)                       # pd_high / pd_low / pd_close, shifted one session
    datr = daily_atr(df1, 14, rth_only=True, rth=rth).rename('atr')
    ob = df1[df1['tod'] == o_tod]
    first = pd.DataFrame({'i_open': pd.Series(ob.index.values, index=ob['day_id'].values), 'open_0930': ob['open'].values})
    first = first[~first.index.duplicated()]
    t = pds.join(datr).join(first, how='inner')
    t['dow'] = pd.to_datetime(t['session']).dt.dayofweek
    above = t['open_0930'] > t['pd_high']; below = t['open_0930'] < t['pd_low']
    t['side'] = np.where(below, 1, np.where(above, -1, 0))
    t['level'] = np.where(below, t['pd_low'], np.where(above, t['pd_high'], np.nan))
    t['dist'] = (t['open_0930'] - t['level']).abs()
    t['dist_pct'] = 100.0 * t['dist'] / t['open_0930']
    t['dist_atr'] = t['dist'] / t['atr']
    t['gap_pct'] = 100.0 * (t['open_0930'] - t['pd_close']).abs() / t['pd_close']
    q = (t['side'] != 0) & t['atr'].notna() & t['pd_close'].notna()
    q &= (t['dist_pct'] >= p['min_dist']) & (t['dist_pct'] <= p['max_dist'])
    q &= t['dist_atr'] <= p['dist_atr']
    q &= t['gap_pct'] <= p['gap_cap']
    if p['sides'] == 'long':
        q &= t['side'] > 0
    elif p['sides'] == 'short':
        q &= t['side'] < 0
    t['qualify'] = q
    return t


def _first_bar_at(tod, day, i0, want_tod, n):
    """Index of the first bar of day[i0]'s session with tod >= want_tod, or -1."""
    k = i0
    while k < n and day[k] == day[i0] and tod[k] < want_tod:
        k += 1
    if k >= n or day[k] != day[i0]:
        return -1
    return k


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS, **params}
    it = Intents(df1)
    t = day_table(df1, contract, p)
    t = t[t['qualify']]
    o_tod = hm(contract.rth_open)
    tod = df1['tod'].values; day = df1['day_id'].values
    h = df1['high'].values; l = df1['low'].values; c = df1['close'].values
    n = len(df1); tick = contract.tick
    mode = p['entry']
    idx = []; sides = []; pxs = []; vbs = []; sps = []; tps = []
    for d, r in t.iterrows():
        i0 = int(r['i_open']); side = int(r['side']); lvl = float(r['level']); dist = float(r['dist'])
        op = float(r['open_0930']); pc = float(r['pd_close']); atr_ = float(r['atr'])
        stop_dist = max(p['stop_mult'] * dist, p['min_stop_pct'] / 100.0 * op)
        if mode == 'market':
            entry_tod = o_tod + int(p['entry_delay'])
            k = _first_bar_at(tod, day, i0, entry_tod, n)
            if k < 0 or tod[k] != entry_tod:
                continue                                        # missing entry bar: skip the day
            pre_lo = l[i0:k].min(); pre_hi = h[i0:k].max(); last_c = c[k - 1]
            tp = lvl + p['tgt_ext'] * (pc - lvl)
            if side > 0:
                if pre_hi >= lvl:
                    continue                                    # level already touched before entry
                sp = op - stop_dist
                if p['skip_beyond_stop'] and last_c <= sp:
                    continue
            else:
                if pre_lo <= lvl:
                    continue
                sp = op + stop_dist
                if p['skip_beyond_stop'] and last_c >= sp:
                    continue
            idx.append(k); sides.append(side); pxs.append(np.nan); vbs.append(0); sps.append(sp); tps.append(tp)
        else:
            k = _first_bar_at(tod, day, i0, o_tod + 1, n)
            if k < 0 or tod[k] != o_tod + 1:
                continue
            vb = hm(p['stop_valid_until']) - int(tod[k])
            if vb < 1:
                continue
            tgt_dist = min(abs(pc - lvl), p['tgt_atr'] * atr_)
            if tgt_dist < p['min_tgt_pct'] / 100.0 * op:
                continue                                        # prior close at the level: no room for a target
            if side > 0:
                px = lvl + tick; sp = lvl - stop_dist; tp = lvl + tgt_dist
            else:
                px = lvl - tick; sp = lvl + stop_dist; tp = lvl - tgt_dist
            idx.append(k); sides.append(side); pxs.append(px); vbs.append(vb); sps.append(sp); tps.append(tp)
    if idx:
        it.place(np.array(idx, dtype=int), np.array(sides, dtype=np.int8), entry_px=np.array(pxs, dtype=float),
                 kind='stop', valid_bars=np.array(vbs, dtype=np.int32), stop_px=np.array(sps), tgt_px=np.array(tps))
    # time exit: first bar >= exit_time in every session (harmless when flat)
    ex = hm(p['exit_time'])
    after = (tod >= ex) & (tod < hm('18:00'))
    first_after = np.flatnonzero(after & np.r_[True, (day[1:] != day[:-1]) | ~after[:-1]])
    it.exit_at(first_after, which=2)
    entry_end = p['stop_valid_until'] if mode == 'stop' else p['exit_time']
    it.set_session(contract.rth_open, entry_end, p['flat'])
    it.max_trades_day = p['max_trades']
    return it
