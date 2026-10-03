"""ORB-30 with 5-minute close confirmation and a capped 0.5x-range target.

tradingstats "conservative setup" / Trade-That-Swing long-only variant (family orb_session, research/families/orb_session.md 3.2-3.3).

Rules as implemented (all times ET):
- 5-minute RTH bars built from the 1-minute feed (resample(..., rth_only=True, rth=(contract.rth_open, contract.rth_close))).
- Opening range (OR) = high/low/open/close of [rth_open, rth_open + or_minutes). rng = or_high - or_low.
  ATR = Wilder ATR(14) of daily RTH bars, shifted one day. Skip the day if rng < min_range_atr*ATR, rng > max_range_atr*ATR or ATR NaN.
- Direction mode: 'both' | 'long' (longs only) | 'trend' (long only if the prior daily close of the cash index is above its
  SMA(trend_len), short only if below; index closes from data/parquet/{SPX,NDX,GC}_1d.parquet, row strictly before the session).
  or_dir_filter: additionally require the OR candle (or_close vs or_open) to point in the trade direction (doji = skip).
- Signal: starting with the first 5-min bar at/after the OR end and whose start < last_entry (time stop), the first bar whose CLOSE
  is above or_high (long) / below or_low (short). Only the first signal of the day counts: if it is in a disallowed direction, no
  trade that day. Entry = market at the open of the next 1-minute bar (+1 tick slippage). If the signal close is already more
  than the target distance beyond the broken level (gap through), skip.
- Stop: 'opposite' = far side of the OR; 'mid' = OR midpoint; in both modes the distance is capped at max_stop_atr*ATR from
  the entry (cap applied relative to the actual fill when the level is too far). Target = fill +/- tgt_frac*rng. No trailing.
- Exits: stop, target, or forced flat at `flat`. One trade per day, no re-entry.
- Optional (improvement rounds, default off): trend_fast (second SMA that must agree with SMA(trend_len); KEPT in the chosen
  config: 50), min_on_range_atr (overnight-range volatility context), be_act_frac/trail_frac (breakeven trail), max_hold_min
  (time stop), reentry (every confirming close is a signal; engine's max_trades limits the count).
Gold (MGC/GC): OR anchored at 08:20 (contract.rth_open), defaults last_entry 09:30, flat 13:25 (overridable).
"""
import os
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm, resample, PQ
from strategies.common import opening_range, daily_atr, overnight_range

NAME = 'ORB-30 close-confirmed, capped 0.5x-range target'
DESCRIPTION = __doc__
CONTRACTS = ['MES', 'MNQ']
PARAMS = {'or_minutes': 30, 'direction': 'both', 'trend_len': 200, 'or_dir_filter': False, 'last_entry': '10:30',
          'stop_mode': 'opposite', 'max_stop_atr': 0.6, 'tgt_frac': 0.5, 'min_range_atr': 0.1, 'max_range_atr': 0.8,
          'flat': '15:55', 'max_trades': 1, 'bar': 5,
          # improvement-round parameters (defaults = original rule, i.e. off)
          'be_act_frac': 0.0,    # >0: once MFE >= be_act_frac*target, trail the stop (see trail_frac)
          'trail_frac': 0.0,     # trail distance as a fraction of the target distance (0 = same as be_act_frac -> stop at breakeven on activation)
          'max_hold_min': 0,     # >0: time stop, exit at market after this many minutes in the trade
          'reentry': False,      # True: every confirming close in the allowed direction is a signal (engine enforces max_trades)
          'trend_fast': 0,       # >0: additionally require the prior close vs SMA(trend_fast) to agree with the SMA(trend_len) side
          'min_on_range_atr': 0.0}  # >0: require the overnight (18:00 -> rth_open) range to be >= this many ATRs (volatility context)
GOLD_DEFAULTS = {'last_entry': '09:30', 'flat': '13:25'}
GRID = {'or_minutes': [15, 30], 'direction': ['both', 'long', 'trend'], 'stop_mode': ['opposite', 'mid'], 'tgt_frac': [0.5, 0.75]}
DAILY_FILE = {'SPXUSD': 'SPX_1d.parquet', 'NSXUSD': 'NDX_1d.parquet', 'XAUUSD': 'GC_1d.parquet', 'WTIUSD': 'CL_1d.parquet'}


def daily_trend(df1: pd.DataFrame, data_symbol: str, n: int) -> pd.Series:
    """+1 / -1 / NaN per day_id: prior daily close (row strictly before the session date) above / below its SMA(n)."""
    d = pd.read_parquet(os.path.join(PQ, DAILY_FILE[data_symbol]))['close'].astype(float)
    d.index = pd.to_datetime(d.index)
    d = d.sort_index()
    sma = d.rolling(n, min_periods=n).mean()
    sessions = df1.groupby('day_id')['session'].first()
    dates = pd.to_datetime(sessions.values)
    pos = d.index.searchsorted(dates, side='left') - 1
    ok = pos >= 0
    pc = np.where(ok, d.values[np.clip(pos, 0, len(d) - 1)], np.nan)
    ps = np.where(ok, sma.values[np.clip(pos, 0, len(d) - 1)], np.nan)
    tr = np.where(np.isnan(pc) | np.isnan(ps), np.nan, np.where(pc > ps, 1.0, np.where(pc < ps, -1.0, np.nan)))
    return pd.Series(tr, index=sessions.index)


def _tod_str(minutes: int) -> str:
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS}
    if contract.name in ('MGC', 'GC'):
        p.update(GOLD_DEFAULTS)
    p.update(params)
    it = Intents(df1)
    rth = (contract.rth_open, contract.rth_close)
    bar = int(p['bar'])
    or_end = hm(contract.rth_open) + int(p['or_minutes'])
    last_entry = hm(p['last_entry'])

    b = resample(df1, bar, rth_only=True, rth=rth)
    orr = opening_range(df1, contract.rth_open, int(p['or_minutes']))
    datr = daily_atr(df1, 14, rth_only=True, rth=rth)
    orr = orr.join(datr.rename('atr'))
    orr['rng'] = orr['or_high'] - orr['or_low']
    ok = orr['atr'].notna() & (orr['rng'] >= p['min_range_atr'] * orr['atr']) & (orr['rng'] <= p['max_range_atr'] * orr['atr']) & (orr['rng'] > 0)
    if float(p['min_on_range_atr']) > 0:
        onr = overnight_range(df1, contract.rth_open)
        onw = (onr['on_high'] - onr['on_low']).reindex(orr.index)
        ok &= onw.notna() & (onw >= float(p['min_on_range_atr']) * orr['atr'])
    orr = orr[ok]
    if p['direction'] == 'trend':
        trend = daily_trend(df1, contract.data_symbol, int(p['trend_len']))
        if int(p['trend_fast']) > 0:
            tf = daily_trend(df1, contract.data_symbol, int(p['trend_fast']))
            trend = trend.where(tf == trend)        # both SMAs must agree, else NaN = no trade
        orr = orr.join(trend.rename('trend'))
    else:
        orr['trend'] = np.nan

    # candidate 5-min bars: fully closed before i_next, start at/after OR end and before the time stop
    cand = b[(b['tod'] >= or_end) & (b['tod'] < last_entry) & (b['i_next'] >= 0)]
    cand = cand[cand['day_id'].isin(orr.index)]
    oh = cand['day_id'].map(orr['or_high']).values; ol = cand['day_id'].map(orr['or_low']).values
    sig = np.where(cand['close'].values > oh, 1, np.where(cand['close'].values < ol, -1, 0))
    cand = cand.assign(sig=sig)
    if p['reentry']:
        first = cand[cand['sig'] != 0]                              # every confirming close is a signal; engine limits trades/day
    else:
        first = cand[cand['sig'] != 0].groupby('day_id').head(1)   # only the first break of the day counts
    be_act = float(p['be_act_frac']); trail_f = float(p['trail_frac']) if float(p['trail_frac']) > 0 else be_act
    max_hold = int(p['max_hold_min'])

    idx, side, stop_px, stop_pts, tgt_pts, trail_pts, trail_act = [], [], [], [], [], [], []
    for _, r in first.iterrows():
        d = int(r['day_id']); s = int(r['sig']); o = orr.loc[d]
        # direction permission
        if p['direction'] == 'long' and s < 0:
            continue
        if p['direction'] == 'trend' and (np.isnan(o['trend']) or int(o['trend']) != s):
            continue
        if p['or_dir_filter']:
            cdir = np.sign(o['or_close'] - o['or_open'])
            if cdir != s:
                continue
        rng = float(o['rng']); cap = float(p['max_stop_atr'] * o['atr']); tgt = float(p['tgt_frac'] * rng)
        est = float(r['close'])
        level = o['or_high'] if s > 0 else o['or_low']
        if (est - level) * s > tgt:       # gapped through: already beyond the target distance from the level
            continue
        if p['stop_mode'] == 'mid':
            sl = 0.5 * (o['or_high'] + o['or_low'])
        else:
            sl = o['or_low'] if s > 0 else o['or_high']
        dist = (est - sl) * s
        if dist <= 0:
            continue
        idx.append(int(r['i_next'])); side.append(s); tgt_pts.append(tgt)
        if be_act > 0:
            trail_act.append(be_act * tgt); trail_pts.append(trail_f * tgt)
        else:
            trail_act.append(0.0); trail_pts.append(np.nan)
        if dist > cap:                    # too far: cap the stop distance relative to the actual fill
            stop_px.append(np.nan); stop_pts.append(cap)
        else:
            stop_px.append(float(sl)); stop_pts.append(np.nan)
    if idx:
        it.place(np.array(idx, dtype=int), np.array(side, dtype=np.int8), stop_px=np.array(stop_px), stop_pts=np.array(stop_pts),
                 tgt_pts=np.array(tgt_pts), trail_pts=np.array(trail_pts), trail_act_pts=np.array(trail_act), max_hold=max_hold)
    # entries only from the OR end up to the close of the last admissible signal bar (bar start < last_entry => fill <= last_entry)
    it.set_session(_tod_str(or_end), _tod_str(last_entry + bar), p['flat'])
    it.max_trades_day = int(p['max_trades'])
    return it
