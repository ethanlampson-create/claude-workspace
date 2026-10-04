"""Gap-and-go: large opening gap outside the prior day's range, first-range breakout continuation.

Family trend_momentum (research/families/trend_momentum.md; research/specs/trend_momentum.md spec 6). Equity RTH only
(MNQ primary, MES); not for MGC (a 08:20 pit "gap" spans 19h of trading and is a different object).

ALL TIMES ET. A 1-min bar with tod = T covers [T, T+1). The decision on bar i uses only bars <= i-1 plus the known
09:30 OPEN print.

DAILY FEATURES (per session d; every daily quantity comes from sessions < d):
  D = daily_bars(df1, rth_only=True, rth=('09:30','16:00')).  prev_close = D.close.shift(1) (last 1-min close with
  tod < 16:00 of the prior session, never the 16:14 print).  pd_high / pd_low = D.high / D.low shifted one session.
  atr = daily_atr(df1, 14, rth_only=True) (Wilder ATR of RTH daily bars, already shifted).  O930 = open of the 1-min
  bar with tod == 09:30.  Skip the day if any of these is NaN/missing or the session is an early close (session_info).
GAP QUALIFICATION: gap = O930 - prev_close.
  up_day = gap >= gap_atr*atr and (not outside_prior_range or O930 > pd_high)
  dn_day = gap <= -gap_atr*atr and (not outside_prior_range or O930 < pd_low) and direction == 'both'
  side = +1 (up_day) / -1 (dn_day); a day is at most one of the two; no trade otherwise.
FIRST RANGE: FR = opening_range(df1, '09:30', range_minutes) -> fr_high, fr_low, i_end.  Skip if fewer than
  range_minutes bars or fr_high == fr_low.  i0 = i_end + 1 (must be the same day_id).
ENTRY: one resting stop order placed at i0 on the gap side only: long buy stop at fr_high + 1 tick, short sell stop at
  fr_low - 1 tick; valid_bars = min(valid_minutes, bars from i0 to the bar whose tod == last_entry) (the order dies at
  last_entry).  Engine fills at max(open, level) + 1 tick slippage.
STOP: stop_mode 'range_low': fr_low - 1 tick (long) / fr_high + 1 tick (short); 'gap_mid': (O930 + prev_close)/2.
  dist = (level - raw_stop)*side.  dist <= 2 ticks: skip the day.  dist > max_stop_atr*atr: stop_pts = max_stop_atr*atr
  relative to the fill instead of stop_px; else stop_px = raw_stop.
TARGET: trail_atr == 0: tgt_px = level + side*tgt_mult*(fr_high - fr_low), no trailing.  trail_atr > 0: no target;
  trail_pts = trail_act_pts = trail_atr*atr (engine ratchets the stop to extreme -/+ trail_pts once the extreme is
  >= trail_act_pts beyond the fill; never loosens).
EXITS: protective stop, target (or trail), forced flat at `flat`.  One trade per day, no re-entry, no reversal.
SESSION/RISK: set_session(09:30 + range_minutes, last_entry, flat); max_trades_day = 1; daily_loss_stop = dls_block
  (MES 60 / MNQ 80 $ per micro: one full stop ends the day); daily_profit_stop off.
LOOK-AHEAD: prev_close / pd_high / pd_low / atr are shifted daily values; O930 is the 09:30 open print; FR is used only
  after i_end; the order goes live at i0 > i_end.  Nothing from bars >= i0 enters the decision.
"""
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm, daily_bars
from strategies.common import opening_range, daily_atr, session_info

NAME = 'Gap-and-go: large opening gap outside the prior range, first-range breakout continuation'
DESCRIPTION = __doc__
CONTRACTS = ['MNQ', 'MES']
PARAMS = {'gap_atr': 0.7, 'outside_prior_range': True, 'range_minutes': 15, 'direction': 'both', 'stop_mode': 'range_low',
          'max_stop_atr': 0.5, 'tgt_mult': 1.0, 'trail_atr': 0.0, 'last_entry': '10:30', 'valid_minutes': 60, 'flat': '15:55',
          'max_trades': 1, 'dls_block': {'MES': 60, 'MNQ': 80}}
GRID = {'gap_atr': [0.5, 0.7], 'range_minutes': [5, 15], 'stop_mode': ['range_low', 'gap_mid'], 'direction': ['both', 'long_only']}   # 16 combos
RTH = ('09:30', '16:00')


def _tod_str(minutes: int) -> str:
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def day_table(df1: pd.DataFrame, p: dict) -> pd.DataFrame:
    """Per-session features and the gap qualification (all known at the 09:30 open). Indexed by day_id.
    Columns: session, prev_close, pd_high, pd_low, atr, o930, i_open, early_close, gap, gap_atr (gap / atr), side (0 = no trade)."""
    D = daily_bars(df1, rth_only=True, rth=RTH)
    t = pd.DataFrame({'session': D['session'], 'prev_close': D['close'].shift(1), 'pd_high': D['high'].shift(1), 'pd_low': D['low'].shift(1)})
    t['atr'] = daily_atr(df1, 14, rth_only=True, rth=RTH)
    ob = df1[df1['tod'] == hm(RTH[0])]
    first = pd.DataFrame({'i_open': ob.index.values, 'o930': ob['open'].values}, index=ob['day_id'].values)
    first = first[~first.index.duplicated()]
    t = t.join(first, how='left')
    t['early_close'] = session_info(df1, rth=RTH)['early_close'].reindex(t.index).fillna(True).astype(bool)
    t['gap'] = t['o930'] - t['prev_close']
    t['gap_atr'] = t['gap'] / t['atr']
    ok = t[['prev_close', 'pd_high', 'pd_low', 'atr', 'o930']].notna().all(axis=1) & ~t['early_close'] & (t['atr'] > 0)
    thr = float(p['gap_atr']) * t['atr']
    opr = bool(p['outside_prior_range'])
    up = ok & (t['gap'] >= thr) & ((t['o930'] > t['pd_high']) if opr else True)
    dn = ok & (t['gap'] <= -thr) & ((t['o930'] < t['pd_low']) if opr else True) & (p['direction'] == 'both')
    t['side'] = np.where(up, 1, np.where(dn, -1, 0)).astype(int)
    return t


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS, **params}
    it = Intents(df1)
    tick = float(contract.tick)
    rm = int(p['range_minutes'])
    last_entry = hm(p['last_entry'])
    valid_minutes = int(p['valid_minutes'])
    cap_atr = float(p['max_stop_atr']); tgt_mult = float(p['tgt_mult']); trail_atr = float(p['trail_atr'])

    t = day_table(df1, p)
    t = t[t['side'] != 0]
    fr = opening_range(df1, RTH[0], rm)
    t = t.join(fr, how='inner')
    t = t[(t['n_bars'] >= rm) & (t['or_high'] > t['or_low'])]

    tod = df1['tod'].values; day = df1['day_id'].values; n = len(df1)
    idx, sides, eps, vbs, sps, spts, tps, trl, trla = [], [], [], [], [], [], [], [], []
    for d, r in t.iterrows():
        side = int(r['side']); i0 = int(r['i_end']) + 1
        if i0 >= n or day[i0] != d:
            continue
        # bars from i0 up to (not including) the bar whose tod == last_entry: the order dies at last_entry
        k = i0
        while k < n and day[k] == d and tod[k] < last_entry:
            k += 1
        nb = k - i0
        if nb < 1:
            continue
        vb = min(valid_minutes, nb)
        fh = float(r['or_high']); fl = float(r['or_low']); atr = float(r['atr'])
        level = fh + tick if side > 0 else fl - tick
        if p['stop_mode'] == 'gap_mid':
            raw_stop = 0.5 * (float(r['o930']) + float(r['prev_close']))
        else:
            raw_stop = fl - tick if side > 0 else fh + tick
        dist = (level - raw_stop) * side
        if dist <= 2 * tick:
            continue
        cap = cap_atr * atr
        if dist > cap:
            sp, spt = np.nan, cap
        else:
            sp, spt = raw_stop, np.nan
        if trail_atr > 0:
            tp = np.nan; tr_ = trail_atr * atr; tra = trail_atr * atr
        else:
            tp = level + side * tgt_mult * (fh - fl); tr_ = np.nan; tra = 0.0
        idx.append(i0); sides.append(side); eps.append(level); vbs.append(vb); sps.append(sp); spts.append(spt)
        tps.append(tp); trl.append(tr_); trla.append(tra)
    if idx:
        it.place(np.array(idx, dtype=int), np.array(sides, dtype=np.int8), entry_px=np.array(eps), kind='stop',
                 valid_bars=np.array(vbs, dtype=np.int32), stop_px=np.array(sps), stop_pts=np.array(spts), tgt_px=np.array(tps),
                 trail_pts=np.array(trl), trail_act_pts=np.array(trla))
    it.set_session(_tod_str(hm(RTH[0]) + rm), p['last_entry'], p['flat'])
    it.max_trades_day = int(p['max_trades'])
    dls = p['dls_block']
    it.daily_loss_stop = float(dls.get(contract.name, 0.0)) if isinstance(dls, dict) else float(dls)
    it.daily_profit_stop = 0.0
    return it
