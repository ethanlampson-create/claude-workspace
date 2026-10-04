"""Trend-day runner: composite 10:30 trend-day flag, trade the open's direction with a trailing runner.

Family trend_momentum (research/families/trend_momentum.md section 19, research/specs/trend_momentum.md spec 8).
Instruments MES, MNQ (equity RTH 09:30-16:00 ET). All times ET; decisions at 10:30 use only bars with tod <= 10:29 plus
daily data shifted so session d sees sessions < d only.

DAILY FEATURES (sessions < d): D = daily_bars(rth_only) ; atr = daily_atr(14) (shifted) ; prev_close = D.close.shift(1);
  pd_high / pd_low = D.high / D.low shifted 1; range1 = (D.high - D.low).shift(1); O1 / C1 = D.open / D.close shifted 1;
  H2 / L2 = D.high / D.low shifted 2.  NR4[d] = range1[d] == min(range of sessions d-4..d-1) (needs 4 prior sessions);
  NR7 analog over d-7..d-1; ID[d] = H1 < H2 and L1 > L2.  O930 = open of the tod == 09:30 bar.
INTRADAY FEATURES (known at 10:30): IB = opening_range('09:30', 60) -> ib_high / ib_low / c1029 (close of the 10:29 bar) /
  i_end (index of the 10:29 bar); width = ib_high - ib_low; ib_mid.  OR30 = opening_range('09:30', 30) -> or_high / or_low /
  or_close (close of the 09:59 bar).  Skip the day if IB < 55 bars, OR30 < 28 bars, atr NaN, early close (session_info),
  width == 0 or the 09:30 bar is missing.
FLAGS (0/1): direction = sign(c1029 - O930) (0 -> no trade).
  a) gap_out   = |O930 - prev_close| >= gap_atr*atr AND (O930 > pd_high or O930 < pd_low) AND sign(O930 - prev_close) == direction
  b) narrow_ib = width < narrow_ib_atr*atr
  c) open_drive = (direction > 0 and or_close >= or_low + 0.75*(or_high - or_low) and or_close > pd_high)
               OR (direction < 0 and or_close <= or_low + 0.25*(or_high - or_low) and or_close < pd_low)
  d) nr_prior  = NR4 or NR7 or ID
  score = a + b + c + d.
NEGATIVE FILTERS: width > max_ib_atr*atr (extreme IB = rotation day) -> skip; skip_after_trend_day and |C1 - O1| >= 0.7*range1
  (yesterday was a trend day) -> skip.   trade_day = score >= min_score and direction != 0 and no negative filter.
ENTRY (one per day, the direction's side only; i1030 = index of the tod == 10:30 bar = i_end + 1, same day):
  entry_mode 'market_1030': market at the 10:30 open (+1 tick slip); entry_ref = c1029.
  entry_mode 'ib_break_stop': stop order at ib_high + 1 tick (long) / ib_low - 1 tick (short), live from 10:30 for the
    minutes until last_entry; entry_ref = level.  If price is already beyond the level at 10:29 the order fills at the
    10:30 open (allowed).
STOP: stop_mode 'ib_mid' -> raw_stop = ib_mid; 'ib_opp' -> ib_low (long) / ib_high (short). dist = (entry_ref - raw_stop)*direction.
  dist <= 2 ticks -> skip the day. dist > max_stop_atr*atr -> stop_pts = max_stop_atr*atr (relative to the fill), else stop_px = raw_stop.
EXIT (runner): trail_pts = trail_atr*atr, trail_act_pts = trail_act_atr*atr (engine ratchet off the bar extreme once MFE >= act,
  never loosens, exit when the close is through the trailed stop). tgt_atr > 0 -> tgt_px = entry_ref + direction*tgt_atr*atr,
  else no target. Forced flat at `flat`. No re-entry after a stop (max_trades 1).
  tie_trail_act (default True): trail_act_atr follows trail_atr so a grid over trail_atr moves both (spec: "tied").
SESSION / RISK: set_session('10:30', last_entry, flat); max_trades_day = max_trades; daily_loss_stop = dls_block[contract];
  daily_profit_stop = dps_mult * dps_block[contract].
LOOK-AHEAD: all daily inputs shifted; flags use bars <= 10:29; the order index is the 10:30 bar.
"""
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm, daily_bars
from strategies.common import opening_range, daily_atr, session_info

NAME = 'Trend-day runner (composite 10:30 flag, trailing runner)'
DESCRIPTION = __doc__
CONTRACTS = ['MES', 'MNQ']
PARAMS = {'min_score': 2, 'entry_mode': 'market_1030', 'stop_mode': 'ib_mid', 'max_stop_atr': 0.5,
          'trail_atr': 0.3, 'trail_act_atr': 0.3, 'tie_trail_act': True, 'tgt_atr': 0.0,
          'gap_atr': 0.7, 'narrow_ib_atr': 0.5, 'max_ib_atr': 1.5, 'skip_after_trend_day': True,
          'last_entry': '12:00', 'flat': '15:55', 'max_trades': 1,
          'dls_block': {'MES': 60, 'MNQ': 80}, 'dps_block': {'MES': 120, 'MNQ': 160}, 'dps_mult': 1.5,
          'direction': 'both'}   # 'both' | 'long' (optional longs-only run)
GRID = {'min_score': [1, 2], 'entry_mode': ['market_1030', 'ib_break_stop'], 'stop_mode': ['ib_mid', 'ib_opp'],
        'trail_atr': [0.25, 0.4]}   # 16 combos; trail_act_atr tied to trail_atr (tie_trail_act)
IB_MINUTES = 60
OR_MINUTES = 30


def _tod_str(minutes: int) -> str:
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def day_table(df1: pd.DataFrame, contract, p: dict) -> pd.DataFrame:
    """Per-session features, flags, score and trade_day flag (everything computable at the 10:30 decision)."""
    rth = (contract.rth_open, contract.rth_close)
    o_tod = hm(rth[0])
    D = daily_bars(df1, rth_only=True, rth=rth)
    t = pd.DataFrame({'session': D['session']})
    t['atr'] = daily_atr(df1, 14, rth_only=True, rth=rth)
    t['prev_close'] = D['close'].shift(1)
    t['pd_high'] = D['high'].shift(1); t['pd_low'] = D['low'].shift(1)
    rng = D['high'] - D['low']
    r1 = rng.shift(1)
    t['range1'] = r1
    t['O1'] = D['open'].shift(1); t['C1'] = D['close'].shift(1)
    H2 = D['high'].shift(2); L2 = D['low'].shift(2)
    t['nr4'] = (r1 == r1.rolling(4, min_periods=4).min()) & r1.notna()
    t['nr7'] = (r1 == r1.rolling(7, min_periods=7).min()) & r1.notna()
    t['id'] = (t['pd_high'] < H2) & (t['pd_low'] > L2)
    # open of the tod == rth_open bar (not the first available RTH bar)
    ob = df1[df1['tod'] == o_tod]
    o930 = pd.Series(ob['open'].values, index=ob['day_id'].values)
    t['O930'] = o930[~o930.index.duplicated()].reindex(t.index)
    ib = opening_range(df1, rth[0], IB_MINUTES).rename(columns={'or_high': 'ib_high', 'or_low': 'ib_low', 'or_close': 'c1029',
                                                                  'i_end': 'ib_i_end', 'n_bars': 'ib_bars'})
    orr = opening_range(df1, rth[0], OR_MINUTES).rename(columns={'i_end': 'or_i_end', 'n_bars': 'or_bars'})
    t = t.join(ib[['ib_high', 'ib_low', 'c1029', 'ib_i_end', 'ib_bars']]).join(orr[['or_high', 'or_low', 'or_close', 'or_bars']])
    t = t.join(session_info(df1, rth)[['early_close']])
    t['width'] = t['ib_high'] - t['ib_low']
    t['ib_mid'] = 0.5 * (t['ib_high'] + t['ib_low'])
    valid = (t['ib_bars'] >= 55) & (t['or_bars'] >= 28) & t['atr'].notna() & (~t['early_close'].astype(bool)) & (t['width'] > 0) \
        & t['O930'].notna() & t['prev_close'].notna()
    t['direction'] = np.sign(t['c1029'] - t['O930']).fillna(0).astype(int)
    dirn = t['direction']
    gap = t['O930'] - t['prev_close']
    t['gap_out'] = ((gap.abs() >= p['gap_atr'] * t['atr']) & ((t['O930'] > t['pd_high']) | (t['O930'] < t['pd_low']))
                    & (np.sign(gap) == dirn)).astype(int)
    t['narrow_ib'] = (t['width'] < p['narrow_ib_atr'] * t['atr']).astype(int)
    orw = t['or_high'] - t['or_low']
    up_drive = (dirn > 0) & (t['or_close'] >= t['or_low'] + 0.75 * orw) & (t['or_close'] > t['pd_high'])
    dn_drive = (dirn < 0) & (t['or_close'] <= t['or_low'] + 0.25 * orw) & (t['or_close'] < t['pd_low'])
    t['open_drive'] = (up_drive | dn_drive).astype(int)
    t['nr_prior'] = (t['nr4'] | t['nr7'] | t['id']).astype(int)
    t['score'] = t['gap_out'] + t['narrow_ib'] + t['open_drive'] + t['nr_prior']
    t['extreme_ib'] = t['width'] > p['max_ib_atr'] * t['atr']
    t['prev_trend_day'] = ((t['C1'] - t['O1']).abs() >= 0.7 * t['range1']) & (t['range1'] > 0)
    neg = t['extreme_ib'] | (t['prev_trend_day'] if p['skip_after_trend_day'] else False)
    t['valid'] = valid
    t['trade_day'] = valid & (t['score'] >= int(p['min_score'])) & (dirn != 0) & ~neg
    if p.get('direction', 'both') == 'long':
        t['trade_day'] &= dirn > 0
    return t


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS, **params}
    it = Intents(df1)
    tick = float(contract.tick)
    ib_end = hm(contract.rth_open) + IB_MINUTES
    last_entry = hm(p['last_entry'])
    valid_bars = max(1, last_entry - ib_end)
    trail_atr = float(p['trail_atr'])
    trail_act_atr = trail_atr if p.get('tie_trail_act', True) else float(p['trail_act_atr'])
    tgt_atr = float(p['tgt_atr']); cap_atr = float(p['max_stop_atr'])
    use_stop_entry = p['entry_mode'] == 'ib_break_stop'

    t = day_table(df1, contract, p)
    t = t[t['trade_day']]
    tod = df1['tod'].values; day = df1['day_id'].values; n = len(df1)
    idx, side, eps, sps, spts, tps, trl, trla = [], [], [], [], [], [], [], []
    for d, r in t.iterrows():
        i = int(r['ib_i_end']) + 1
        if i >= n or day[i] != d or tod[i] != ib_end:
            continue                                   # 10:30 bar missing: skip the day
        s = int(r['direction']); atr = float(r['atr'])
        if use_stop_entry:
            level = r['ib_high'] + tick if s > 0 else r['ib_low'] - tick
            entry_ref = float(level)
        else:
            level = np.nan
            entry_ref = float(r['c1029'])
        if p['stop_mode'] == 'ib_opp':
            raw_stop = float(r['ib_low'] if s > 0 else r['ib_high'])
        else:
            raw_stop = float(r['ib_mid'])
        dist = (entry_ref - raw_stop) * s
        if dist <= 2 * tick:
            continue                                   # stop would be on top of / beyond the entry: skip the day
        cap = cap_atr * atr
        if dist > cap:
            sp, spt = np.nan, cap                      # cap relative to the actual fill
        else:
            sp, spt = raw_stop, np.nan
        tp = entry_ref + s * tgt_atr * atr if tgt_atr > 0 else np.nan
        idx.append(i); side.append(s); eps.append(level); sps.append(sp); spts.append(spt); tps.append(tp)
        trl.append(trail_atr * atr if trail_atr > 0 else np.nan); trla.append(trail_act_atr * atr)
    if idx:
        it.place(np.array(idx, dtype=int), np.array(side, dtype=np.int8), entry_px=np.array(eps), kind='stop',
                 valid_bars=valid_bars if use_stop_entry else 0, stop_px=np.array(sps), stop_pts=np.array(spts),
                 tgt_px=np.array(tps), trail_pts=np.array(trl), trail_act_pts=np.array(trla))
    it.set_session(_tod_str(ib_end), p['last_entry'], p['flat'])
    it.max_trades_day = int(p['max_trades'])
    dls = p['dls_block']; dps = p['dps_block']
    it.daily_loss_stop = float(dls.get(contract.name, 0.0) if isinstance(dls, dict) else dls)
    it.daily_profit_stop = float(p['dps_mult']) * float(dps.get(contract.name, 0.0) if isinstance(dps, dict) else dps)
    return it
