"""Intraday noise-area momentum breakout (Zarattini-Aziz-Barbon, SSRN 4824172; Quantitativo ES/NQ 1-minute replication).
Family bot_popular_indicators, spec 1 (research/specs/bot_popular_indicators.md). 1-minute band stop orders, band-trailing exit.

RULES AS IMPLEMENTED (all times ET; RTH = (contract.rth_open, contract.rth_close): 09:30-16:00 MES/MNQ, 08:20-13:30 MGC pit):
BARS: 1-minute RTH bars only (rth_open <= tod < rth_close); no resampling.
PRE per session d (D = daily_bars(df1, rth_only=True, rth=rth)):
  O[d] = D.open (open of the rth_open 1-min bar); PC[d] = D.close.shift(1) (prior session's last 1-min close before
  rth_close, never the 16:14 / 17:00 print); ATRd[d] = Wilder ATR(14) of the daily RTH bars shifted one day.
  move[d, t] = |close(bar of day d at tod t) / O[d] - 1| for every RTH tod t; pivoted into a matrix M (rows = sessions
  with RTH bars, ascending; cols = tod). sigma[d, t] = M.rolling(lookback).mean().shift(1) along the day axis, i.e. the
  average |move| at that time of day over the previous `lookback` sessions, strictly days < d.
  Warm-up: the matrix is extended with the `lookback` sessions BEFORE df1's first session (backtest.data.load_1m, prior
  data only), so the first sessions of any run window can trade whatever warm-up the runner provides.
  NaN handling (documented deviation from a literal min_periods=lookback): the CFD feed has ~7.5% of sessions with the
  afternoon missing (US holidays / early closes trade until 13:00), so a per-cell min_periods=lookback would leave the
  13:00-16:00 columns NaN almost permanently. Instead: the day must have >= lookback prior sessions in M (full warm-up),
  and each cell needs >= 60% non-NaN observations in its window (pandas skipna). A missing bar therefore only drops that
  day from that time-of-day's average, which is the paper's definition.
  UB[d, t] = max(O[d], PC[d]) * (1 + vm*sigma[d, t]) rounded UP to the tick; LB[d, t] = min(O[d], PC[d]) * (1 - vm*sigma[d, t])
  rounded DOWN to the tick. Skip day d entirely if ATRd[d], PC[d] or sigma[d, entry_start] is NaN.
  hard[d] = max(hard_stop_atr * ATRd[d], 4 ticks). UB/LB at tod t depend only on prior days, today's open and yesterday's
  close, so they are known before bar t opens: placing the stop order on the touch bar is equivalent to a resting OCO
  stop bracket at (UB, LB).
STATE MACHINE per day d over 1-min bars i from entry_start until the flat time (pos = 0, n = 0, sp = NaN, skip_until = -1):
  if i < skip_until: continue.  U = UB[d, tod[i]]; L = LB[d, tod[i]] (NaN cell -> bar ignored).
  if pos == 0:
    if tod[i] >= last_entry or n >= max_trades: break (no new entries after last_entry; an open position keeps being managed).
    up = high[i] >= U;  dn = (low[i] <= L) and not long_only.  If neither: continue.
    side = +1 if up only; -1 if dn only; if both touched: +1 if (U - open[i]) <= (open[i] - L) else -1 (band nearer the
    bar's open assumed hit first).  level = U if side > 0 else L;  sp = level - side*hard[d].
    trail 'none': it.place(i, side, entry_px=level, kind='stop', valid_bars=1, stop_px=sp)
    trail 'atr':  same plus trail_pts=hard[d], trail_act_pts=hard[d] (engine ratchet after one hard-stop distance of MFE).
    pos = side; n += 1.  Entry-bar stop mirror (the engine checks the protective stop against the entry bar's extreme):
    if (side > 0 and low[i] <= sp) or (side < 0 and high[i] >= sp): pos = 0.
  else:
    Hard-stop mirror: if (pos > 0 and low[i] <= sp) or (pos < 0 and high[i] >= sp): pos = 0; continue.
    Band-trailing exit on the 1-min CLOSE (paper: stopped out when price re-enters the noise area):
    pos > 0 and close[i] < U -> it.exit_at(i+1, which=+1); pos = 0; skip_until = i+2.
    pos < 0 and close[i] > L -> it.exit_at(i+1, which=-1); pos = 0; skip_until = i+2.
    (Exit fills at the open of bar i+1; the engine ignores any signal on the bar a position was closed, so the machine
    resumes at i+2; reversals through the opposite band are allowed and count toward max_trades. If i+1 is in the next
    session the exit_at is not needed: the forced flat / session end handles it.)
  trail == 'atr' approximation: the engine may close a trade on the ratchet while the machine still believes it is open;
  placements the machine then makes while the engine is flat ARE taken by the engine (they carry their own stop), and
  placements made while the engine is in a position are ignored. After the machine's own exit/stop it is authoritative again.
SESSION: it.set_session(entry_start, last_entry, flat); it.max_trades_day = max_trades;
  it.daily_loss_stop = dls_mult * block; it.daily_profit_stop = dps_mult * block (Lucid risk block per ONE micro:
  MES 60/120, MNQ 80/160, MGC 80/160 $; dps_mult default 1.5 because this strategy's good days are the trend days).
GOLD (GOLD_DEFAULTS when contract.name in ('MGC', 'GC')): entry_start 08:25, last_entry 12:30, flat 13:25; O = 08:20 pit open,
  PC = prior 13:29 close, sigma over pit tods 08:20-13:29.
EXITS summary: hard stop (0.5 x ATR14d), band re-entry on the 1-min close, optional ATR ratchet, forced flat; no fixed target.
"""
import math
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm, daily_bars
from strategies.common import daily_atr

NAME = 'Noise-area momentum breakout, 1-min band stops, band-trailing exit (Zarattini-Aziz-Barbon / Quantitativo)'
DESCRIPTION = __doc__
CONTRACTS = ['MNQ', 'MES']
PARAMS = {'lookback': 14, 'vm': 1.0, 'entry_start': '09:35', 'last_entry': '15:00', 'flat': '15:55', 'hard_stop_atr': 0.5,
          'trail': 'none', 'max_trades': 4, 'long_only': False, 'dls_mult': 1.0, 'dps_mult': 1.5}
GOLD_DEFAULTS = {'entry_start': '08:25', 'last_entry': '12:30', 'flat': '13:25'}
GRID = {'lookback': [14, 90], 'vm': [1.0, 1.5], 'trail': ['none', 'atr'], 'max_trades': [2, 4]}
# Lucid risk block per ONE contract: (daily_loss_stop, daily_profit_stop) in $
BLOCK = {'MES': (60.0, 120.0), 'MNQ': (80.0, 160.0), 'MGC': (80.0, 160.0),
         'ES': (600.0, 1200.0), 'NQ': (800.0, 1600.0), 'GC': (800.0, 1600.0)}
MIN_OBS_FRAC = 0.6   # per-cell minimum share of non-NaN |move| observations in the lookback window


def _move_frame(df: pd.DataFrame, rth, day_offset: int = 0) -> pd.DataFrame:
    """|close / RTH open - 1| per RTH 1-minute bar: columns day_id (+ offset), tod, move."""
    o_tod, c_tod = hm(rth[0]), hm(rth[1])
    O = daily_bars(df, rth_only=True, rth=rth)['open']
    r = df.loc[(df['tod'].values >= o_tod) & (df['tod'].values < c_tod), ['day_id', 'tod', 'close']]
    move = np.abs(r['close'].values / O.reindex(r['day_id'].values).values - 1.0)
    return pd.DataFrame({'day_id': r['day_id'].values + day_offset, 'tod': r['tod'].values, 'move': move})


def prior_history(df1: pd.DataFrame, data_symbol: str, sessions: int) -> pd.DataFrame:
    """1-minute bars of the ~`sessions` sessions strictly before df1's first session (warm-up for the sigma matrix;
    only data prior to df1 is used, so no look-ahead). Empty when nothing earlier exists."""
    from backtest.data import load_1m
    first = pd.Timestamp(df1['session'].iloc[0])
    start = (first - pd.Timedelta(days=int(sessions * 1.6) + 20)).strftime('%Y-%m-%d')
    end = (first - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    try:
        ext = load_1m(data_symbol, start, end)
    except Exception:
        return df1.iloc[0:0]
    ext = ext[ext['session'] < first.date()]
    if len(ext):
        ext = ext.copy(); ext['day_id'] = pd.factorize(ext['session'])[0].astype(np.int32)
        ext = ext.reset_index(drop=True)
    return ext


def noise_bands(df1: pd.DataFrame, rth, lookback: int, vm: float, tick: float, data_symbol: str = None):
    """Per 1-minute bar: UB / LB (NaN outside RTH or when sigma is unavailable) and per-day tables O, PC, sigma matrix.
    The sigma matrix is warmed with the `lookback` sessions before df1 (prior_history) so that the first sessions of a
    window can trade whatever the runner's warm-up length is."""
    o_tod, c_tod = hm(rth[0]), hm(rth[1])
    D = daily_bars(df1, rth_only=True, rth=rth)
    O = D['open']; PC = D['close'].shift(1)
    tod = df1['tod'].values; day = df1['day_id'].values
    in_rth = (tod >= o_tod) & (tod < c_tod)
    frames = [_move_frame(df1, rth)]
    if data_symbol is not None:
        ext = prior_history(df1, data_symbol, lookback + 5)
        if len(ext):
            k = int(ext['day_id'].max()) + 1
            frames.insert(0, _move_frame(ext, rth, day_offset=-k))     # prior sessions get day_ids -k .. -1
    mv = pd.concat(frames, ignore_index=True)
    M = mv.pivot(index='day_id', columns='tod', values='move').sort_index()
    min_obs = max(2, int(math.ceil(MIN_OBS_FRAC * lookback)))
    sigma = M.rolling(lookback, min_periods=min_obs).mean().shift(1)
    sigma.iloc[:lookback] = np.nan                   # full warm-up: >= lookback prior sessions in M
    sigma = sigma.loc[sigma.index >= 0]
    # map sigma[d, t] onto the 1-minute index
    n = len(df1)
    sig = np.full(n, np.nan)
    rows = sigma.index.get_indexer(day[in_rth]); cols = sigma.columns.get_indexer(tod[in_rth])
    ok = (rows >= 0) & (cols >= 0)
    vals = np.full(ok.shape[0], np.nan)
    vals[ok] = sigma.values[rows[ok], cols[ok]]
    sig[in_rth] = vals
    hi_ref = np.maximum(O, PC).reindex(day).values   # max(O, PC) per bar (NaN when PC NaN)
    lo_ref = np.minimum(O, PC).reindex(day).values
    ub = np.ceil(hi_ref * (1.0 + vm * sig) / tick - 1e-9) * tick
    lb = np.floor(lo_ref * (1.0 - vm * sig) / tick + 1e-9) * tick
    return ub, lb, sigma, O, PC


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS}
    if contract.name in ('MGC', 'GC'):
        p.update(GOLD_DEFAULTS)
    p.update(params)
    it = Intents(df1)
    rth = (contract.rth_open, contract.rth_close)
    tick = float(contract.tick)
    lookback = int(p['lookback']); vm = float(p['vm'])
    e_start = hm(p['entry_start']); e_last = hm(p['last_entry']); flat_tod = hm(p['flat'])
    max_trades = int(p['max_trades']); long_only = bool(p['long_only']); use_trail = str(p['trail']) == 'atr'

    ub, lb, sigma, O, PC = noise_bands(df1, rth, lookback, vm, tick, contract.data_symbol)
    datr = daily_atr(df1, 14, rth_only=True, rth=rth)
    hard_d = np.maximum(float(p['hard_stop_atr']) * datr, 4.0 * tick)
    # day validity: ATR, prior close and sigma at entry_start must exist
    sig_es = sigma[e_start] if e_start in sigma.columns else pd.Series(np.nan, index=sigma.index)
    valid_days = set(int(d) for d in sigma.index if (not np.isnan(sig_es.loc[d])) and d in PC.index and not np.isnan(PC.loc[d])
                     and d in hard_d.index and not np.isnan(hard_d.loc[d]))

    tod = df1['tod'].values; day = df1['day_id'].values
    o = df1['open'].values; h = df1['high'].values; l = df1['low'].values; c = df1['close'].values
    n = len(df1)
    # bar ranges per day for the managed window [entry_start, flat)
    win = (tod >= e_start) & (tod < flat_tod)
    idx_all = np.flatnonzero(win)
    if len(idx_all) == 0:
        it.set_session(p['entry_start'], p['last_entry'], p['flat']); return it
    starts = idx_all[np.r_[True, day[idx_all][1:] != day[idx_all][:-1]]]
    ends = idx_all[np.r_[day[idx_all][1:] != day[idx_all][:-1], True]]

    e_idx, e_side, e_level, e_sp, e_trl, e_trla = [], [], [], [], [], []
    x_idx, x_which = [], []
    for i0, i1 in zip(starts.tolist(), ends.tolist()):
        d = int(day[i0])
        if d not in valid_days:
            continue
        hard = float(hard_d.loc[d])
        pos = 0; ntr = 0; sp = np.nan; skip_until = -1
        i = i0
        while i <= i1:
            if i < skip_until:
                i += 1; continue
            U = ub[i]; L = lb[i]
            if U != U or L != L:
                i += 1; continue
            if pos == 0:
                if tod[i] >= e_last or ntr >= max_trades:
                    break
                up = h[i] >= U
                dn = (l[i] <= L) and (not long_only)
                if not (up or dn):
                    i += 1; continue
                if up and not dn:
                    side = 1
                elif dn and not up:
                    side = -1
                else:
                    side = 1 if (U - o[i]) <= (o[i] - L) else -1
                level = U if side > 0 else L
                sp = level - side * hard
                e_idx.append(i); e_side.append(side); e_level.append(level); e_sp.append(sp)
                e_trl.append(hard if use_trail else np.nan); e_trla.append(hard if use_trail else 0.0)
                pos = side; ntr += 1
                if (side > 0 and l[i] <= sp) or (side < 0 and h[i] >= sp):
                    pos = 0                                   # stopped on the entry bar (engine mirror)
            else:
                if (pos > 0 and l[i] <= sp) or (pos < 0 and h[i] >= sp):
                    pos = 0; i += 1; continue                 # hard stop (engine mirror)
                if (pos > 0 and c[i] < U) or (pos < 0 and c[i] > L):
                    j = i + 1
                    if j < n and day[j] == d:
                        x_idx.append(j); x_which.append(pos)
                    pos = 0; skip_until = i + 2
            i += 1
    if e_idx:
        it.place(np.array(e_idx, dtype=int), np.array(e_side, dtype=np.int8), entry_px=np.array(e_level), kind='stop', valid_bars=1,
                 stop_px=np.array(e_sp), trail_pts=np.array(e_trl), trail_act_pts=np.array(e_trla))
    if x_idx:
        it.exit_flag[np.array(x_idx, dtype=int)] = np.array(x_which, dtype=np.int8)
    it.set_session(p['entry_start'], p['last_entry'], p['flat'])
    it.max_trades_day = max_trades
    dls, dps = BLOCK.get(contract.name, (0.0, 0.0))
    it.daily_loss_stop = float(p['dls_mult']) * dls
    it.daily_profit_stop = float(p['dps_mult']) * dps
    return it
