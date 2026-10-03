"""ORB-30 with a daily SMA(200) one-directional trend filter, R-multiple exit and one-loss-per-session rule.

Published spec ("Backtests, Not Signals" MNQ walk-forward, OOS 2023-02..2026-02 Sharpe 1.10 / PF 1.32):
- TREND FILTER: daily closes from data/parquet/{NDX,SPX}_1d.parquet. For session d use the close of the last daily
  row strictly before d (one-day lag). bias = long if lagged close > SMA(sma_len) of lagged closes, short if below,
  NaN -> no trade. Only breakouts in the bias direction are placed (one side only, no OCO).
- OPENING RANGE: [09:30, 09:30 + or_minutes). rng = or_high - or_low. Skip the day if rng < min_range_atr * ATR14
  (daily RTH ATR, shifted).
- ENTRY: stop order at or_high + buffer (long bias) / or_low - buffer (short bias), placed on the first 1-min bar after
  the range, valid until last_entry (wick entry: fill = max(open, level) + 1 tick slippage).
- STOP: opposite side of the range, distance capped at min(rng, stop_cap_pts[contract], max_stop_atr * ATR).
- TARGET: rr * stop distance. No trailing. Forced flat at `flat` (15:55 ET).
- ONE-LOSS RULE: default max_trades = 1 (the published runs are effectively one trade per day). `reentry=True`
  re-places the same order after a stop-out while tod < last_entry (max 2 trades/day) with a daily loss stop of
  1.0 x cap $ per contract, so a full-cap loss halts the day.
Optional filters / exits (all OFF by default so PARAMS == the published rule; see results/orb_sma_rr/README.md):
- max_vix: skip the session when the prior-day VIX close (strategies.common.vix_lag1) is above this level.
- sides: 'both' | 'long' | 'short' -> only place orders in that direction (bias still decides the side).
- trail_r / trail_act_r: trailing stop of trail_r x risk, armed once the trade is trail_act_r x risk in profit.
- max_range_atr: skip the day when the opening range is wider than this x ATR14.
- require_or_dir: the opening-range close must be on the bias side of its open (range closed with the trend).
- max_hold: time stop in minutes (0 = none).
Look-ahead: SMA uses closes strictly before the session; the order is live only after the range completes; the
day's own range/ATR are never used in the entry decision.
"""
import os
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm, PQ
from strategies.common import opening_range, daily_atr, vix_lag1

NAME = 'ORB-30 + daily SMA200 trend filter, R-multiple exit, one loss per session'
DESCRIPTION = __doc__
CONTRACTS = ['MNQ', 'MES']
PARAMS = {'or_minutes': 30, 'sma_len': 200, 'rr': 2.0, 'stop_cap_pts': {'MNQ': 37.5, 'MES': 10.0, 'MGC': 7.5},
          'max_stop_atr': 0.5, 'buffer_ticks': 1, 'last_entry': '12:00', 'min_range_atr': 0.1, 'max_trades': 1,
          'flat': '15:55', 'reentry': False,
          # optional filters / exits, all off by default (= published rule)
          'max_vix': None, 'sides': 'both', 'trail_r': None, 'trail_act_r': 1.0, 'max_range_atr': None,
          'require_or_dir': False, 'max_hold': 0}
GRID = {'sma_len': [150, 200, 250], 'rr': [1.4, 2.0, 2.4, 3.0], 'or_minutes': [15, 30], 'last_entry': ['11:00', '12:00']}

DAILY_FILE = {'MNQ': 'NDX_1d.parquet', 'NQ': 'NDX_1d.parquet', 'MES': 'SPX_1d.parquet', 'ES': 'SPX_1d.parquet',
              'MGC': 'GC_1d.parquet', 'GC': 'GC_1d.parquet'}


def daily_trend_bias(df1: pd.DataFrame, contract, sma_len: int) -> pd.Series:
    """Per day_id: +1 if the lagged daily close (last daily row strictly before the session date) is above its
    SMA(sma_len), -1 if below, 0 if the SMA is not yet defined. Uses the cash index daily file (long history), never df1."""
    d = pd.read_parquet(os.path.join(PQ, DAILY_FILE[contract.name]))
    close = pd.Series(d['close'].values.astype(float), index=pd.to_datetime(d.index)).sort_index()
    close = close[~close.index.duplicated(keep='last')]
    sma = close.rolling(sma_len, min_periods=sma_len).mean()
    sessions = df1.groupby('day_id')['session'].first()
    dates = pd.to_datetime(sessions.values)
    pos = close.index.searchsorted(dates, side='left') - 1          # last row strictly before the session date
    ok = pos >= 0
    posc = np.clip(pos, 0, len(close) - 1)
    c = np.where(ok, close.values[posc], np.nan); s = np.where(ok, sma.values[posc], np.nan)
    bias = np.where(np.isnan(c) | np.isnan(s), 0, np.where(c > s, 1, np.where(c < s, -1, 0))).astype(np.int8)
    return pd.Series(bias, index=sessions.index)


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS, **params}
    it = Intents(df1)
    rth = (contract.rth_open, contract.rth_close)
    orr = opening_range(df1, contract.rth_open, p['or_minutes'])
    datr = daily_atr(df1, 14, rth_only=True, rth=rth)
    orr = orr.join(datr.rename('atr'))
    orr['bias'] = daily_trend_bias(df1, contract, int(p['sma_len'])).reindex(orr.index).fillna(0).astype(int)
    orr['rng'] = orr['or_high'] - orr['or_low']
    # a complete range is required (no partial ranges on early/late starts)
    ok = orr['atr'].notna() & (orr['rng'] >= p['min_range_atr'] * orr['atr']) & (orr['bias'] != 0) & (orr['n_bars'] >= p['or_minutes'] - 2)
    if p.get('max_range_atr') is not None:
        ok &= orr['rng'] <= float(p['max_range_atr']) * orr['atr']
    if p.get('max_vix') is not None:
        vix = vix_lag1(df1).reindex(orr.index)          # prior-day VIX close only (no look-ahead)
        ok &= vix.notna() & (vix <= float(p['max_vix']))
    if p.get('sides', 'both') == 'long':
        ok &= orr['bias'] > 0
    elif p.get('sides', 'both') == 'short':
        ok &= orr['bias'] < 0
    if p.get('require_or_dir'):
        ok &= np.sign(orr['or_close'] - orr['or_open']) == orr['bias']
    orr = orr[ok]
    i0 = orr['i_end'].values + 1
    keep = i0 < len(df1)
    orr = orr[keep]; i0 = i0[keep]
    tod = df1['tod'].values; day = df1['day_id'].values
    last_entry = hm(p['last_entry'])
    cap = p['stop_cap_pts']
    cap = float(cap[contract.name]) if isinstance(cap, dict) else float(cap)
    buf = p['buffer_ticks'] * contract.tick
    stop_dist = np.minimum.reduce([orr['rng'].values, np.full(len(orr), cap), p['max_stop_atr'] * orr['atr'].values])
    stop_dist = np.maximum(stop_dist, 2 * contract.tick)
    side = orr['bias'].values.astype(np.int8)
    level = np.where(side > 0, orr['or_high'].values + buf, orr['or_low'].values - buf)
    sp = level - side * stop_dist
    tp = level + side * float(p['rr']) * stop_dist
    trail = np.full(len(orr), np.nan); trail_act = np.zeros(len(orr))
    if p.get('trail_r') is not None:
        trail = float(p['trail_r']) * stop_dist; trail_act = float(p['trail_act_r']) * stop_dist
    mh = int(p.get('max_hold') or 0)
    # the order is live from the first bar after the range until last_entry
    valid = last_entry - tod[i0]
    good = (valid >= 1) & (day[i0] == orr.index.values)
    i0, side, level, sp, tp, valid = i0[good], side[good], level[good], sp[good], tp[good], valid[good]
    trail, trail_act = trail[good], trail_act[good]
    if p['reentry']:
        # re-place the identical order on every bar of the entry window: while pending it is a no-op, while in a
        # position the engine ignores it, and after an exit it re-arms (max 2 trades/day, daily loss stop = cap $)
        idx = []; sd = []; lv = []; s_ = []; t_ = []; vb = []; tr_ = []; ta_ = []
        for k in range(len(i0)):
            n = int(valid[k])
            rng_i = np.arange(i0[k], i0[k] + n)
            idx.append(rng_i); sd.append(np.full(n, side[k], np.int8)); lv.append(np.full(n, level[k]))
            s_.append(np.full(n, sp[k])); t_.append(np.full(n, tp[k])); vb.append(np.arange(n, 0, -1))
            tr_.append(np.full(n, trail[k])); ta_.append(np.full(n, trail_act[k]))
        if idx:
            it.place(np.concatenate(idx), np.concatenate(sd), entry_px=np.concatenate(lv), valid_bars=np.concatenate(vb),
                     stop_px=np.concatenate(s_), tgt_px=np.concatenate(t_), trail_pts=np.concatenate(tr_),
                     trail_act_pts=np.concatenate(ta_), max_hold=mh)
        it.max_trades_day = 2
        it.daily_loss_stop = 1.0 * cap * contract.point_value
    else:
        it.place(i0, side, entry_px=level, valid_bars=valid, stop_px=sp, tgt_px=tp, trail_pts=trail, trail_act_pts=trail_act, max_hold=mh)
        it.max_trades_day = int(p['max_trades'])
    or_end = hm(contract.rth_open) + int(p['or_minutes'])
    it.set_session(f'{or_end // 60:02d}:{or_end % 60:02d}', p['last_entry'], p['flat'])
    return it
