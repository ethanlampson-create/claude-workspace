"""Small opening-gap fade toward the prior RTH close (fill-the-gap), long-biased.

DEFINITIONS (per session d, nothing after the 09:30 open is used for qualification):
  prior_close = last 1-min close with tod < 16:00 ET of the previous session (never 16:14 / 17:00).
  open_0930   = open of the 09:30 ET 1-min bar.  gap = (open_0930 - prior_close) / prior_close.
  PDH / PDL   = prior-session RTH (09:30-16:00) high / low.  ATR = 14-day RTH daily ATR (lagged).
QUALIFY: gap_min <= |gap| <= gap_max (percent); |gap| <= atr_mult * ATR%; the open is not outside the prior-day range
  by more than outside_atr * ATR (otherwise gap-and-go: skip); VIX gate: skip when vix_lag1 is in the top quartile of its
  trailing 100-session high/low range (VIX closes of sessions < d only).  FOMC/CPI calendar is not available -> not used.
DIRECTION: gap down -> LONG; gap up -> SHORT (sides='both' | 'long' | 'short').  skip_mon_gapup: skip Monday gap-ups.
ENTRY: market at the open of the bar at 09:30 + entry_delay minutes.  Skip if the gap already filled in the bars before
  entry (long: any high >= prior_close; short: any low <= prior_close).  Skip if the stop level was already breached before entry (the
  bracket would be dead on arrival; skip_beyond_stop=True).
STOP: one gap-distance beyond the open: open_0930 -/+ stop_mult * |gap_pts|, floored at stop_floor_atr * ATR (0 = published).
  TARGET: open_0930 + fill_frac * (prior_close - open_0930).
EXIT: flat at the open of the first bar >= exit_time (Intents.exit_at); force flat at `flat`.  One trade per day.
OPTIONAL (improvement rounds, all off by default so PARAMS = the published rule):
  entry='limit': instead of market at 09:30+delay, a limit order limit_frac * |gap_pts| beyond the open (buy the dip deeper
    than the open), live for limit_valid bars.  trend_filter='against': only fade gaps that go against the 20-day trend
    (gap-down when prior close > SMA(trend_len) of RTH closes, lagged; gap-up when below); 'with' is the mirror.
  trail_frac / trail_act_frac: trailing stop of trail_frac * |gap_pts| that activates once price has recovered
    trail_act_frac * |gap_pts| (equal values = break-even ratchet).  max_hold: minutes; daily_loss_stop: $ per contract.
"""
import os
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm, daily_bars, PQ
from strategies.common import daily_atr, prior_day_stats

NAME = 'Opening gap fade (fill the gap)'
DESCRIPTION = __doc__
CONTRACTS = ['MES', 'MNQ']
PARAMS = {'gap_min': 0.10, 'gap_max': 0.50, 'atr_mult': 0.7, 'stop_mult': 1.0, 'fill_frac': 1.0, 'entry_delay': 5,
          'exit_time': '11:00', 'flat': '15:55', 'sides': 'both', 'vix_gate': True, 'vix_lb': 100, 'vix_q': 0.75,
          'outside_atr': 0.5, 'skip_mon_gapup': False, 'skip_beyond_stop': True, 'max_trades': 1,
          'stop_floor_atr': 0.0, 'entry': 'market', 'limit_frac': 0.25, 'limit_valid': 15, 'trend_filter': 'none',
          'trend_len': 20, 'trail_frac': 0.0, 'trail_act_frac': 0.0, 'max_hold': 0, 'daily_loss_stop': 0.0}
GRID = {'gap_max': [0.35, 0.50, 0.70], 'stop_mult': [0.75, 1.0, 1.5], 'sides': ['both', 'long'], 'exit_time': ['11:00', '12:00']}


def vix_regime(df1: pd.DataFrame, lb=100, q=0.75) -> pd.DataFrame:
    """Per day_id: vix_lag1 (last VIX close strictly before the session date) and the high/low of the `lb` VIX closes
    ending at that lagged close. 'hot' = vix_lag1 >= low + q * (high - low). Only sessions < d are used."""
    vix = pd.read_parquet(os.path.join(PQ, 'VIX_1d.parquet'))['close']
    s = pd.Series(vix.values, index=pd.to_datetime(pd.to_datetime(vix.index).date)).sort_index()
    hi = s.rolling(lb, min_periods=lb).max(); lo = s.rolling(lb, min_periods=lb).min()
    sessions = df1.groupby('day_id')['session'].first()
    dates = pd.to_datetime(sessions.values)
    pos = s.index.searchsorted(dates, side='left') - 1          # last VIX close strictly before the session date
    ok = pos >= 0
    pc = np.clip(pos, 0, len(s) - 1)
    out = pd.DataFrame({'vix_lag1': np.where(ok, s.values[pc], np.nan), 'vix_hi': np.where(ok, hi.values[pc], np.nan),
                        'vix_lo': np.where(ok, lo.values[pc], np.nan)}, index=sessions.index)
    out['hot'] = out['vix_lag1'] >= out['vix_lo'] + q * (out['vix_hi'] - out['vix_lo'])
    return out


def day_table(df1: pd.DataFrame, contract, p: dict) -> pd.DataFrame:
    """Per-session features and qualification flags (all computed with information available at the 09:30 open)."""
    rth = (contract.rth_open, contract.rth_close)
    o_tod = hm(rth[0])
    pds = prior_day_stats(df1, rth=rth)                      # pd_high / pd_low / pd_close (RTH, shifted one session)
    datr = daily_atr(df1, 14, rth_only=True, rth=rth).rename('atr')
    ob = df1[df1['tod'] == o_tod]
    first = pd.DataFrame({'i_open': pd.Series(ob.index.values, index=ob['day_id'].values), 'open_0930': ob['open'].values})
    first = first[~first.index.duplicated()]
    t = pds.join(datr).join(first, how='inner')
    t['dow'] = pd.to_datetime(t['session']).dt.dayofweek
    t['gap'] = (t['open_0930'] - t['pd_close']) / t['pd_close']            # fraction
    t['gap_pct'] = 100.0 * t['gap']
    t['atr_pct'] = 100.0 * t['atr'] / t['pd_close']
    vr = vix_regime(df1, int(p['vix_lb']), float(p['vix_q']))
    t = t.join(vr)
    # 20-day trend of RTH closes, lagged: SMA over sessions <= d-1 compared with the prior close (sessions < d only)
    dcl = daily_bars(df1, rth_only=True, rth=rth)['close']
    t['sma_lag'] = dcl.rolling(int(p['trend_len']), min_periods=int(p['trend_len'])).mean().shift(1).reindex(t.index)
    t['trend_up'] = t['pd_close'] > t['sma_lag']
    ag = t['gap_pct'].abs()
    q = (ag >= p['gap_min']) & (ag <= p['gap_max']) & t['atr'].notna() & t['pd_close'].notna()
    q &= ag <= p['atr_mult'] * t['atr_pct']
    q &= (t['open_0930'] <= t['pd_high'] + p['outside_atr'] * t['atr']) & (t['open_0930'] >= t['pd_low'] - p['outside_atr'] * t['atr'])
    if p['vix_gate']:
        q &= t['hot'].notna() & ~t['hot'].astype(bool)
    side = np.where(t['gap'] < 0, 1, -1)
    if p['sides'] == 'long':
        q &= side > 0
    elif p['sides'] == 'short':
        q &= side < 0
    if p['skip_mon_gapup']:
        q &= ~((t['dow'] == 0) & (side < 0))
    if p['trend_filter'] == 'against':          # gap-down in an uptrend (long), gap-up in a downtrend (short)
        q &= t['sma_lag'].notna() & (((side > 0) & t['trend_up']) | ((side < 0) & ~t['trend_up']))
    elif p['trend_filter'] == 'with':
        q &= t['sma_lag'].notna() & (((side > 0) & ~t['trend_up']) | ((side < 0) & t['trend_up']))
    t['side'] = side
    t['qualify'] = q
    return t


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS, **params}
    it = Intents(df1)
    t = day_table(df1, contract, p)
    t = t[t['qualify']]
    o_tod = hm(contract.rth_open)
    entry_tod = o_tod + int(p['entry_delay'])
    tod = df1['tod'].values; day = df1['day_id'].values
    h = df1['high'].values; l = df1['low'].values; c = df1['close'].values
    n = len(df1)
    idx = []; sides = []; sps = []; tps = []; eps = []; trl = []; trla = []
    use_limit = p['entry'] == 'limit'
    for d, r in t.iterrows():
        i0 = int(r['i_open']); side = int(r['side'])
        # entry bar: first bar of this session with tod >= entry_tod (normally exactly 09:30 + delay)
        k = i0
        while k < n and day[k] == d and tod[k] < entry_tod:
            k += 1
        if k >= n or day[k] != d or tod[k] != entry_tod:
            continue                                            # missing entry bar: skip the day
        pre_lo = l[i0:k].min(); pre_hi = h[i0:k].max(); last_c = c[k - 1]
        gap_pts = abs(r['open_0930'] - r['pd_close'])
        stop_dist = max(p['stop_mult'] * gap_pts, p['stop_floor_atr'] * r['atr'])
        if side > 0:
            if pre_hi >= r['pd_close']:
                continue                                        # gap-down already filled (price rose to prior close)
            sp = r['open_0930'] - stop_dist
            tp = r['open_0930'] + p['fill_frac'] * (r['pd_close'] - r['open_0930'])
            if p['skip_beyond_stop'] and last_c <= sp:
                continue
        else:
            if pre_lo <= r['pd_close']:
                continue                                        # gap-up already filled (price fell to prior close)
            sp = r['open_0930'] + stop_dist
            tp = r['open_0930'] - p['fill_frac'] * (r['open_0930'] - r['pd_close'])
            if p['skip_beyond_stop'] and last_c >= sp:
                continue
        ep = (r['open_0930'] - side * p['limit_frac'] * gap_pts) if use_limit else np.nan
        idx.append(k); sides.append(side); sps.append(sp); tps.append(tp); eps.append(ep)
        trl.append(p['trail_frac'] * gap_pts if p['trail_frac'] > 0 else np.nan)
        trla.append(p['trail_act_frac'] * gap_pts)
    if idx:
        it.place(np.array(idx, dtype=int), np.array(sides, dtype=np.int8), entry_px=np.array(eps),
                 kind='limit' if use_limit else 'stop', valid_bars=int(p['limit_valid']) if use_limit else 0,
                 stop_px=np.array(sps), tgt_px=np.array(tps), trail_pts=np.array(trl), trail_act_pts=np.array(trla),
                 max_hold=int(p['max_hold']))
    # time exit: first bar >= exit_time in every session (harmless when flat)
    ex = hm(p['exit_time'])
    after = (tod >= ex) & (tod < hm('18:00'))
    first_after = np.flatnonzero(after & np.r_[True, (day[1:] != day[:-1]) | ~after[:-1]])
    it.exit_at(first_after, which=2)
    it.set_session(contract.rth_open, p['exit_time'], p['flat'])
    it.max_trades_day = p['max_trades']
    it.daily_loss_stop = float(p['daily_loss_stop'])
    return it
