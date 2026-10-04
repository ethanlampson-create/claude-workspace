"""Gold intraday Donchian: long-only 20-bar channel breakout on 15-min MGC bars over the FULL ~23h session, daily
SMA-200 gate, 10-bar channel exit, flat 16:30 ET (family trend_momentum, research/specs/trend_momentum.md spec 13;
Turtle System 1 lengths 20-in / 10-out and the 2N ATR stop, long-only as in the Algomatic gold 2000-2025 test).

ALL TIMES ET. Gold data session: 18:00 -> 17:00 next day (bars exist 00:00-16:59 and 18:00-23:59; nothing 17:00-18:00).
BARS: B = resample(df1, bar, rth_only=False) for MGC/GC, i.e. N-minute bars over the whole session, CONTINUOUS across
  sessions (indicator state carries over the 17:00-18:00 break and over weekends; TradingView 'ETH chart' semantics).
  MES/MNQ (sanity comparison only): resample(df1, bar, rth_only=True, rth=(contract.rth_open, contract.rth_close)).
INDICATORS on B (windows exclude bar k; min_periods = full window; NaN -> no trade):
  hh[k] = max(high[k-n_entry..k-1]); ll[k] = min(low[k-n_exit..k-1]); ATRb[k] = Wilder atr(B, 20) (bar k is closed at decision time).
DAILY (gold, full session; equities RTH daily bars): Dfull = daily_bars(hist + df1, rth_only=False), one bar per session.
  The daily series is extended with `hist_days` calendar days of earlier 1-min history (load_1m is cached) so that the
  SMA(200) / 12-month lookback are warm on the first session of the window; only sessions < d are ever used.
  prev_close[d] = close.shift(1); SMA_D(200)[d] = close.rolling(200, min_periods=200).mean().shift(1);
  ATR14d_full[d] = Wilder ATR(14) of the daily bars, shifted one session.
  bias_ok[d]: 'sma200' -> prev_close > SMA_D(200); 'tsmom12' -> prev_close > close.shift(253) (close ~12 months earlier); 'none' -> True.
SIGNAL (long): breakout[k] = close[k] > hh[k] AND bias_ok[day_id[k]] AND entry_start <= tod[k] < last_entry AND i_next[k] != -1
  AND hh, ll, ATRb, ATR14d_full not NaN AND module state flat AND entries today < max_trades.
  direction: 'long_only' (default; shorts lost on gold in every published test) | 'short_only' | 'both' (mirror rules, diagnostics only).
ENTRY: it.place(i_next[k], +1, stop_px=sp) -> market at the open of the next 1-min bar (+1 tick slip). entry_ref = close[k].
  sp = max(close[k] - stop_atr_bars*ATRb[k], close[k] - max_stop_atr*ATR14d_full[d]) (the NEARER stop), rounded down to the tick;
  skip if close[k] - sp < 2 ticks. tgt 'none' = no target; 'rr2' -> tgt_px = entry_ref + 2.0*(entry_ref - sp).
EXIT: (1) channel exit: first bar k' > k with close[k'] < ll[k'] -> it.exit_at(i_next[k'], which=+1) (market at the next 1-min open;
  i_next == -1 -> the forced flat handles it); (2) the fixed hard stop sp (engine checks every 1-min bar); (3) forced flat at `flat`.
MODULE STATE (mirrors the engine so no second entry is emitted while in a position): flat again after (a) the channel exit is
  emitted (from k'+1), (b) a stop-touch mirror on an N-bar after the signal bar (low[k'] <= sp), (c) a target touch in 'rr2'
  mode (high[k'] >= tgt_px; stop checked first), (d) the forced flat / session end. Re-entry on a later breakout the same
  session is allowed up to max_trades.
SESSION / RISK: it.set_session(entry_start, last_entry + bar minutes, flat) (the signal bar starting just before last_entry can
  fill); it.max_trades_day = max_trades; it.daily_loss_stop = dls_block ($ per micro: MGC 80; MES 60 / MNQ 80);
  it.daily_profit_stop = 0 (off). Equity override: entry_start 09:35, last_entry 15:00, flat 15:55.
LOOK-AHEAD: channel windows end at k-1; the decision uses close[k]; the order is at i_next[k]; daily bias / ATR shifted one session.
"""
import math
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm, resample, daily_bars, load_1m
from strategies.common import atr

NAME = 'Gold intraday Donchian 20/10, long-only, full session, SMA-200 gate'
DESCRIPTION = __doc__
CONTRACTS = ['MGC']
PARAMS = {'bar': 15, 'n_entry': 20, 'n_exit': 10, 'bias': 'sma200', 'direction': 'long_only', 'stop_atr_bars': 2.0,
          'max_stop_atr': 0.5, 'tgt': 'none', 'entry_start': '02:00', 'last_entry': '13:00', 'flat': '16:30',
          'max_trades': 2, 'dls_block': 80,
          'hist_days': 420}      # calendar days of earlier 1-min history used to warm the daily SMA(200) / 12-month lookback
EQUITY_DEFAULTS = {'entry_start': '09:35', 'last_entry': '15:00', 'flat': '15:55', 'dls_block': {'MES': 60, 'MNQ': 80}}
GRID = {'n_entry': [20, 55], 'n_exit': [10, 20], 'bias': ['sma200', 'none'], 'bar': [15, 60]}   # 16 combos
GOLD = ('MGC', 'GC')


def _per_contract(v, contract, default):
    if isinstance(v, dict):
        return float(v.get(contract.name, default))
    return float(v)


def _tod_str(minutes: int) -> str:
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def daily_features(df1: pd.DataFrame, contract, p: dict, full_session: bool) -> pd.DataFrame:
    """Per day_id of df1: prev_close, sma200, close_12m (close 253 sessions before d, i.e. ~12 months before prev_close),
    atr14 (Wilder ATR(14) of the daily bars) - every value from sessions < d. The daily series (full 18:00->17:00 session
    for gold, RTH for equities) is built on `hist_days` calendar days of earlier 1-min history plus df1."""
    rth = (contract.rth_open, contract.rth_close)
    first = df1['session'].iloc[0]
    t0 = (pd.Timestamp(first) - pd.Timedelta(days=int(p['hist_days']))).strftime('%Y-%m-%d')
    t1 = (pd.Timestamp(first) - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    hist = load_1m(contract.data_symbol, t0, t1)
    parts = []
    for d in (hist, df1):
        if len(d) == 0:
            continue
        db = daily_bars(d, rth_only=not full_session, rth=rth).set_index('session')
        parts.append(db[['open', 'high', 'low', 'close']])
    D = pd.concat(parts)
    D = D[~D.index.duplicated(keep='last')].sort_index()
    out = pd.DataFrame(index=D.index)
    out['prev_close'] = D['close'].shift(1)
    out['sma200'] = D['close'].rolling(200, min_periods=200).mean().shift(1)
    out['close_12m'] = D['close'].shift(253)
    out['atr14'] = atr(D, 14).shift(1)
    sessions = df1.groupby('day_id')['session'].first()
    feat = out.reindex(sessions.values)
    feat.index = sessions.index
    return feat


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS}
    gold = contract.name in GOLD
    if not gold:
        p.update(EQUITY_DEFAULTS)
    p.update(params)
    it = Intents(df1)
    bar = int(p['bar']); n_entry = int(p['n_entry']); n_exit = int(p['n_exit'])
    tick = float(contract.tick)
    entry_start = hm(p['entry_start']); last_entry = hm(p['last_entry']); flat_tod = hm(p['flat'])
    max_trades = int(p['max_trades'])
    direction = p['direction']
    allow_long = direction in ('long_only', 'both'); allow_short = direction in ('short_only', 'both')
    use_tgt = str(p['tgt']).lower() in ('rr2', 'rr2.0')
    rr = 2.0

    if gold:
        b = resample(df1, bar, rth_only=False)
    else:
        b = resample(df1, bar, rth_only=True, rth=(contract.rth_open, contract.rth_close))
    b = b.reset_index(drop=True)
    # channels exclude bar k (shift(1) then rolling over the previous n bars); ATR(20) on the N-min bars
    hi_prev = b['high'].shift(1); lo_prev = b['low'].shift(1)
    hh_in = hi_prev.rolling(n_entry, min_periods=n_entry).max().values     # long entry channel
    ll_in = lo_prev.rolling(n_entry, min_periods=n_entry).min().values     # short entry channel
    ll_out = lo_prev.rolling(n_exit, min_periods=n_exit).min().values      # long exit channel
    hh_out = hi_prev.rolling(n_exit, min_periods=n_exit).max().values      # short exit channel
    atrb = atr(b, 20).values

    feat = daily_features(df1, contract, p, full_session=gold)
    bias = str(p['bias'])
    if bias == 'sma200':
        bias_long = (feat['prev_close'] > feat['sma200']).values
        bias_short = (feat['prev_close'] < feat['sma200']).values
    elif bias == 'tsmom12':
        bias_long = (feat['prev_close'] > feat['close_12m']).values
        bias_short = (feat['prev_close'] < feat['close_12m']).values
    elif bias == 'none':
        bias_long = np.ones(len(feat), bool); bias_short = np.ones(len(feat), bool)
    else:
        raise ValueError(f'unknown bias {bias!r}')
    atr_d = feat['atr14'].values
    nd = len(feat)

    day = b['day_id'].values.astype(np.int64); tod = b['tod'].values.astype(np.int64); i_next = b['i_next'].values.astype(np.int64)
    close = b['close'].values.astype(np.float64); high = b['high'].values.astype(np.float64); low = b['low'].values.astype(np.float64)
    s_bars = float(p['stop_atr_bars']); s_day = float(p['max_stop_atr'])

    idx, sides, stops, tgts = [], [], [], []
    exit_idx, exit_which = [], []
    pos = 0; sp = np.nan; tp = np.nan; cur_day = -1; entries_today = 0
    for k in range(len(b)):
        d = int(day[k])
        if d != cur_day:
            # new session: the forced flat / session end closed any open position
            cur_day = d; entries_today = 0; pos = 0
        if pos != 0:
            # (d) forced flat already happened at the first 1-min bar >= flat
            if tod[k] >= flat_tod and tod[k] < hm('18:00'):
                pos = 0
            # (b) stop-touch mirror, (c) target touch (stop checked first)
            elif pos > 0 and low[k] <= sp:
                pos = 0
            elif pos < 0 and high[k] >= sp:
                pos = 0
            elif use_tgt and pos > 0 and high[k] >= tp:
                pos = 0
            elif use_tgt and pos < 0 and low[k] <= tp:
                pos = 0
            # (a) channel exit at the next 1-min open
            elif pos > 0 and not np.isnan(ll_out[k]) and close[k] < ll_out[k]:
                if i_next[k] >= 0:
                    exit_idx.append(int(i_next[k])); exit_which.append(1)
                pos = 0
            elif pos < 0 and not np.isnan(hh_out[k]) and close[k] > hh_out[k]:
                if i_next[k] >= 0:
                    exit_idx.append(int(i_next[k])); exit_which.append(-1)
                pos = 0
            continue
        # flat: look for a breakout
        if entries_today >= max_trades or i_next[k] < 0 or not (entry_start <= tod[k] < last_entry):
            continue
        if d >= nd or np.isnan(atrb[k]) or np.isnan(atr_d[d]) or np.isnan(ll_out[k]) or np.isnan(hh_out[k]):
            continue
        c = close[k]
        side = 0
        if allow_long and not np.isnan(hh_in[k]) and c > hh_in[k] and bias_long[d]:
            side = 1
        elif allow_short and not np.isnan(ll_in[k]) and c < ll_in[k] and bias_short[d]:
            side = -1
        if side == 0:
            continue
        dist = min(s_bars * atrb[k], s_day * atr_d[d])          # the NEARER of the two stops
        if side > 0:
            s_px = math.floor((c - dist) / tick + 1e-9) * tick
        else:
            s_px = math.ceil((c + dist) / tick - 1e-9) * tick
        if (c - s_px) * side < 2 * tick - 1e-9:
            continue
        t_px = c + rr * (c - s_px) if use_tgt else np.nan       # entry_ref +/- rr * stop distance (sign follows the side)
        idx.append(int(i_next[k])); sides.append(side); stops.append(float(s_px)); tgts.append(float(t_px))
        pos = side; sp = s_px; tp = t_px; entries_today += 1
    if idx:
        it.place(np.array(idx, dtype=int), np.array(sides, dtype=np.int8), stop_px=np.array(stops), tgt_px=np.array(tgts))
    if exit_idx:
        ex = np.array(exit_idx, dtype=int); wh = np.array(exit_which, dtype=np.int8)
        for w in (1, -1):
            if (wh == w).any():
                it.exit_at(ex[wh == w], which=int(w))
    it.set_session(p['entry_start'], _tod_str(last_entry + bar), p['flat'])
    it.max_trades_day = max_trades
    it.daily_loss_stop = _per_contract(p['dls_block'], contract, 80.0)
    it.daily_profit_stop = 0.0
    return it
