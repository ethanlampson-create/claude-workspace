"""Mesfin ORB long with a pure TIME exit (arXiv 2605.04004 'ORB long, bar+15'), family evidence_and_failures.

Published rule (MNQ 5-min RTH bars, Dec 2021-Aug 2025, walk-forward OOS N=447, net +2.82 pts after 2.0-pt friction,
positive in each OOS year 2023/2024/2025, T=0.88): opening range = 09:30-09:55 (five 5-min bars); buy at the next bar
open after the first 5-min close above the OR high; hold 15 bars (75 minutes); no target. Shorts were negative OOS and
are not implemented.

Rules as implemented (all times ET, decisions on the close of a 5-min bar, order at the next 1-min open + 1 tick):
- B5 = resample(df1, 5, rth_only=True): buckets anchored at 18:00 so RTH bars start 09:30, 09:35, ... .
- OR = opening_range(df1, or_start, or_minutes): or_high / or_low over [or_start, or_start + or_minutes).
- Daily features use days < d only: ATR14d = daily_atr(df1, 14, rth_only=True); prev_close[d] = RTH close of day d-1;
  SMA200_D[d] = SMA(200) of RTH daily closes up to d-1. The SMA / VVG quantiles need more history than the 45-day
  warm-up the runner loads, so the module reloads up to `hist_days` calendar days of 1-min data BEFORE the first session
  of df1 (cheap: load_1m caches the full parquet) and builds the daily RTH series on history + df1. Only sessions < d
  enter any feature of day d.
- VVG gate (skip_vvg=True; OHLC-only version of arXiv 2605.11423): gap[d] = open(09:30 bar)/prev_close - 1;
  r30[d] = close(09:59 bar)/prev_close - 1; qg[d] / qr[d] = 2/3-quantile of |gap| / |r30| over sessions strictly before d
  (NaN -> gate off until 120 sessions exist); vvg[d] = |gap| >= qg and |r30| >= qr. r30 is known at 10:00, which is when the
  earliest signal bar (09:55-09:59) can fire; a signal bar is only accepted when its close time >= rth_open + 30 min.
- Per session: skip if ATR14d NaN; if trend_filter == 'sma200' require SMA200 not NaN and prev_close > SMA200; if skip_vvg
  and vvg skip. Scan 5-min bars k with tod >= OR end and tod + 5 <= last_entry (09:55 .. 11:25) in order; at the FIRST bar
  with close > or_high: i = B5.i_next[k + delay] (same day, else skip); c = close[k]; stop = or_low (stop_mode 'or_low') or
  c - stop_atr * ATR14d ('atr'), or none ('none', the published rule, diagnostic only);
  stop = min(stop, c - min_stop_pts[contract]); market long at bar i with stop_px = stop
  and max_hold = hold_min 1-min bars. No target: exit after hold_min minutes, at the stop, or at the `flat` time.
  max_trades = 1 -> only the first signal of the day is placed. max_trades = 2 -> every qualifying bar is placed (the
  engine ignores signals while in a position) and the daily loss stop (dls) halts the day after a losing first trade.
- Session: entries allowed in [OR end, last_entry + 5) so the bar that starts at 11:25 can fill at 11:30; flat 15:55.
  Lucid risk block per ONE micro: daily_loss_stop = dls[contract] * dls_mult, daily_profit_stop = dps[contract] * dps_mult.
- `delay` (sensitivity): order at B5.i_next[k + delay] instead of B5.i_next[k]. Slippage sensitivity via `--slip 2`.
Gold (MGC): OR 08:20 for 25 min, signals from 08:45, last entry 10:30, flat 13:25, ATR14d on 08:20-13:30 daily bars.
"""
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm, resample, daily_bars, load_1m
from strategies.common import opening_range, daily_atr, sma

NAME = 'Mesfin ORB long, 25-min OR, close-confirmed entry, 75-min time exit'
DESCRIPTION = __doc__
CONTRACTS = ['MNQ', 'MES']
PARAMS = {'or_start': None, 'or_minutes': 25, 'hold_min': 75, 'trend_filter': 'none', 'stop_mode': 'or_low', 'stop_atr': 0.5,
          'last_entry': '11:30', 'max_trades': 1, 'skip_vvg': False, 'flat': '15:55', 'dls_mult': 1.0, 'dps_mult': 2.0,
          'delay': 0, 'sma_len': 200, 'vvg_min_sessions': 120, 'vvg_q': 2.0 / 3.0, 'hist_days': 420,
          'min_stop_pts': {'MNQ': 6.0, 'MES': 4.0, 'MGC': 1.5},
          'dls': {'MNQ': 40.0, 'MES': 35.0, 'MGC': 40.0}, 'dps': {'MNQ': 60.0, 'MES': 50.0, 'MGC': 60.0}}
GOLD_DEFAULTS = {'last_entry': '10:30', 'flat': '13:25'}
GRID = {'hold_min': [60, 75, 120], 'trend_filter': ['none', 'sma200'], 'stop_mode': ['or_low', 'atr'], 'skip_vvg': [False, True]}


def _tod_str(minutes: int) -> str:
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def _per_contract(v, contract, default):
    if isinstance(v, dict):
        return float(v.get(contract.name, default))
    return float(v)


def daily_features(df1: pd.DataFrame, contract, p: dict) -> pd.DataFrame:
    """Per day_id of df1: prev_close, sma (both from days < d), gap, r30 (the day's own, known by rth_open+30), vvg flag.
    The daily RTH series is built on `hist_days` calendar days of earlier 1-min history plus df1."""
    rth = (contract.rth_open, contract.rth_close)
    o_tod = hm(contract.rth_open)
    first = df1['session'].iloc[0]
    t0 = (pd.Timestamp(first) - pd.Timedelta(days=int(p['hist_days']))).strftime('%Y-%m-%d')
    t1 = (pd.Timestamp(first) - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    hist = load_1m(contract.data_symbol, t0, t1)
    parts = []
    for d in (hist, df1):
        if len(d) == 0:
            continue
        db = daily_bars(d, rth_only=True, rth=rth).set_index('session')
        bo = d[d['tod'] == o_tod].groupby('session')['open'].first()
        c30 = d[d['tod'] == o_tod + 29].groupby('session')['close'].last()
        db['o_open'] = bo.reindex(db.index); db['c30'] = c30.reindex(db.index)
        parts.append(db[['close', 'o_open', 'c30']])
    D = pd.concat(parts)
    D = D[~D.index.duplicated(keep='last')].sort_index()
    out = pd.DataFrame(index=D.index)
    out['prev_close'] = D['close'].shift(1)
    out['sma'] = sma(D['close'], int(p['sma_len'])).shift(1)
    out['gap'] = D['o_open'] / out['prev_close'] - 1.0
    out['r30'] = D['c30'] / out['prev_close'] - 1.0
    q = float(p['vvg_q']); mp = int(p['vvg_min_sessions'])
    out['qg'] = out['gap'].abs().expanding(min_periods=mp).quantile(q).shift(1)
    out['qr'] = out['r30'].abs().expanding(min_periods=mp).quantile(q).shift(1)
    out['vvg'] = (out['gap'].abs() >= out['qg']) & (out['r30'].abs() >= out['qr'])   # NaN compares False -> gate off
    sessions = df1.groupby('day_id')['session'].first()
    feat = out.reindex(sessions.values)
    feat.index = sessions.index
    return feat


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS}
    if contract.name in ('MGC', 'GC'):
        p.update(GOLD_DEFAULTS)
    p.update(params)
    it = Intents(df1)
    rth = (contract.rth_open, contract.rth_close)
    or_start = p['or_start'] or contract.rth_open
    or_end = hm(or_start) + int(p['or_minutes'])
    last_entry = hm(p['last_entry'])
    bar = 5
    delay = int(p['delay'])
    min_stop = _per_contract(p['min_stop_pts'], contract, 6.0)

    b = resample(df1, bar, rth_only=True, rth=rth)
    orr = opening_range(df1, or_start, int(p['or_minutes']))
    datr = daily_atr(df1, 14, rth_only=True, rth=rth)
    orr = orr.join(datr.rename('atr'))
    feat = daily_features(df1, contract, p)
    orr = orr.join(feat)

    ok = orr['atr'].notna() & (orr['n_bars'] >= int(p['or_minutes']) - 2)
    if p['trend_filter'] == 'sma200':
        ok &= orr['sma'].notna() & orr['prev_close'].notna() & (orr['prev_close'] > orr['sma'])
    if p['skip_vvg']:
        ok &= ~orr['vvg'].fillna(False).astype(bool)
    orr = orr[ok]

    # candidate signal bars: start at/after the OR end, close by last_entry, fully closed before i_next
    cand_mask = (b['tod'] >= or_end) & (b['tod'] + bar <= last_entry) & b['day_id'].isin(orr.index)
    if p['skip_vvg']:
        cand_mask &= (b['tod'] + bar) >= hm(contract.rth_open) + 30      # r30 must be known at the signal bar close
    cand = b[cand_mask]
    oh = cand['day_id'].map(orr['or_high']).values
    sig = cand[cand['close'].values > oh]
    if int(p['max_trades']) <= 1:
        sig = sig.groupby('day_id').head(1)
    # order bar: i_next of bar k + delay (same session)
    pos = sig.index.values + delay
    pos_ok = pos < len(b)
    pos_c = np.minimum(pos, len(b) - 1)
    same_day = pos_ok & (b['day_id'].values[pos_c] == sig['day_id'].values)
    i_ord = np.where(same_day, b['i_next'].values[pos_c], -1)
    c = sig['close'].values
    d_id = sig['day_id'].values
    if p['stop_mode'] == 'or_low':
        stop = orr['or_low'].reindex(d_id).values
    elif p['stop_mode'] == 'atr':
        stop = c - float(p['stop_atr']) * orr['atr'].reindex(d_id).values
    else:                                   # 'none': the published rule had no protective stop (pure time exit)
        stop = np.full(len(c), -np.inf)
    stop = np.minimum(stop, c - min_stop)
    stop = np.where(np.isfinite(stop), stop, np.nan)
    keep = i_ord >= 0
    if keep.any():
        it.place(i_ord[keep].astype(int), 1, stop_px=stop[keep], max_hold=int(p['hold_min']))
    it.set_session(_tod_str(or_end), _tod_str(last_entry + bar), p['flat'])
    it.max_trades_day = int(p['max_trades'])
    it.daily_loss_stop = _per_contract(p['dls'], contract, 40.0) * float(p['dls_mult'])
    it.daily_profit_stop = _per_contract(p['dps'], contract, 60.0) * float(p['dps_mult'])
    return it
