"""RSI(5) cross-back dip-buy with a Chandelier(22,1) ratchet exit in an SMA50>SMA200 regime.

Intraday translation of StockCharts SystemTrader (Arthur Hill, Dec 2016: RSI(5) mean reversion on SPY/QQQ/IJR with the
Chandelier Exit) -- family bot_popular_indicators, research/families/bot_popular_indicators.md 2.5, spec section 5.

Rules as implemented (all times ET):
- BARS: B = resample(df1, bar, rth_only=True, rth=(rth_open, rth_close)); the N-minute series is continuous across sessions
  (TradingView "RTH chart" semantics), so RSI / ATR / Chandelier at the first bar of a day use the previous day's last RTH bars.
- INDICATORS on B (src = close): r = Wilder RSI(rsi_len) (common.rsi); a14 = Wilder ATR(14); a22 = Wilder ATR(ce_len).
  Chandelier (everget, useClose): ls_raw[k] = max(close[k-ce_len+1..k]) - ce_mult*a22[k];
  ls[k] = max(ls_raw[k], ls[k-1]) if close[k-1] > ls[k-1] else ls_raw[k]  (seed ls = ls_raw at the first non-NaN bar);
  ss_raw[k] = min(close[k-ce_len+1..k]) + ce_mult*a22[k]; ss[k] = min(ss_raw[k], ss[k-1]) if close[k-1] < ss[k-1] else ss_raw[k].
- THRESHOLD: thresh = {2: 10, 5: 30, 14: 30}[rsi_len]; the short threshold is 100 - thresh.
- REGIME per session (regime == 'sma50_200'): daily closes of the cash index (data/parquet/{SPX,NDX,GC}_1d.parquet, mapped from
  the data symbol exactly as orb_close30.daily_trend: the row strictly before the session date); s50 = SMA(50), s200 = SMA(200)
  of those closes at that lagged row; long_ok = s50 > s200; short_ok = direction == 'both' and s50 < s200. NaN SMA = no trade.
  regime == 'none': long_ok = True, short_ok = direction == 'both'.
- ENTRY (long; short mirrored): N-bar k with entry_start <= B.tod[k] < last_entry, i = B.i_next[k] != -1, long_ok on that day,
  module position state flat, and the deciding cross on bar k:
    variant 'B' (default): r[k-1] < thresh and r[k] >= thresh (cross back above the threshold);
    variant 'A': r[k-1] >= thresh and r[k] < thresh (cross below, the original's falling-knife variant; not in the grid).
    Short (variant B): r[k-1] > 100-thresh and r[k] <= 100-thresh.
  entry_ref = close[k]; stop_px = entry_ref -/+ stop_atr*a14[k] (longs rounded down to the tick, shorts rounded up);
  it.place(i, side, stop_px=stop_px): market at the next 1-minute open (+1 tick). No target (the original has none).
- EXIT: Chandelier ratchet on confirmed N-bars only, evaluated after min_hold bars so an entry below the line does not exit on
  the next bar: for the first k' > k with k' - k >= min_hold and (long) close[k'] < ls[k'] / (short) close[k'] > ss[k']:
  it.exit_at(B.i_next[k'], which=+1 / -1). Plus the hard stop and the forced flat at `flat`.
- POSITION STATE (module side, so one trade at a time and new entries only when flat): flat again when (a) the chandelier exit
  is emitted (flat from k'+1), (b) any N-bar k'' in (k, k'] has low[k''] <= stop_px (long) / high[k''] >= stop_px (short),
  i.e. the engine's stop was hit, or (c) the session ends. Per-day entries capped at max_trades (and engine max_trades_day).
- SESSION: set_session(entry_start, last_entry + bar, flat) -- the engine window ends one N-bar after last_entry so the
  signal bar that starts just before last_entry can fill at its i_next, which keeps the module state and the engine in step.
  daily_loss_stop = dls_mult * block, daily_profit_stop = dps_mult * block (Lucid risk block per micro: MES 60/120,
  MNQ 80/160, MGC 80/160).
Gold (MGC/GC): entry_start 08:35, last_entry 12:30, flat 13:25 (pit mapping; regime from GC_1d closes).
Control cell outside the grid: rsi_len=14 on MES (independent 1-/5-min RSI(14) tests show 20-23% win) to calibrate the engine
against a known-bad system.
"""
import os
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm, resample, PQ
from strategies.common import atr, rsi

NAME = 'RSI(5) cross-back dip-buy, Chandelier(22,1) ratchet exit, SMA50>SMA200 regime (SystemTrader intraday)'
DESCRIPTION = __doc__
CONTRACTS = ['MES', 'MNQ']
PARAMS = {'bar': 5, 'rsi_len': 5, 'variant': 'B', 'regime': 'sma50_200', 'direction': 'long_only', 'ce_len': 22, 'ce_mult': 1.0,
          'stop_atr': 1.5, 'min_hold': 1, 'entry_start': '09:45', 'last_entry': '15:00', 'flat': '15:55', 'max_trades': 3,
          'dls_mult': 1.0, 'dps_mult': 1.0}
GOLD_DEFAULTS = {'entry_start': '08:35', 'last_entry': '12:30', 'flat': '13:25'}
GRID = {'rsi_len': [2, 5], 'ce_mult': [1.0, 2.0], 'direction': ['long_only', 'both'], 'stop_atr': [1.5, 2.5]}   # 16 combos
THRESH = {2: 10, 5: 30, 14: 30}
DAILY_FILE = {'SPXUSD': 'SPX_1d.parquet', 'NSXUSD': 'NDX_1d.parquet', 'XAUUSD': 'GC_1d.parquet', 'WTIUSD': 'CL_1d.parquet'}
BLOCK_DLS = {'MES': 60.0, 'MNQ': 80.0, 'MGC': 80.0, 'ES': 600.0, 'NQ': 800.0, 'GC': 800.0}
BLOCK_DPS = {'MES': 120.0, 'MNQ': 160.0, 'MGC': 160.0, 'ES': 1200.0, 'NQ': 1600.0, 'GC': 1600.0}


def regime_sma(df1: pd.DataFrame, data_symbol: str, fast: int = 50, slow: int = 200) -> pd.DataFrame:
    """Per day_id: s_fast / s_slow = SMA(fast) / SMA(slow) of the cash-index daily closes at the row strictly before the
    session date (NaN when not enough history)."""
    d = pd.read_parquet(os.path.join(PQ, DAILY_FILE[data_symbol]))['close'].astype(float)
    d.index = pd.to_datetime(d.index)
    d = d.sort_index()
    sf = d.rolling(fast, min_periods=fast).mean(); ss = d.rolling(slow, min_periods=slow).mean()
    sessions = df1.groupby('day_id')['session'].first()
    dates = pd.to_datetime(sessions.values)
    pos = d.index.searchsorted(dates, side='left') - 1
    ok = pos >= 0
    pc = np.clip(pos, 0, len(d) - 1)
    return pd.DataFrame({'s_fast': np.where(ok, sf.values[pc], np.nan), 's_slow': np.where(ok, ss.values[pc], np.nan)},
                        index=sessions.index)


def chandelier(close: np.ndarray, a: np.ndarray, n: int, mult: float):
    """everget Chandelier Exit (useClose): ratcheting long stop `ls` and short stop `ss` on confirmed bars."""
    c = pd.Series(close)
    ls_raw = (c.rolling(n, min_periods=n).max() - mult * a).values
    ss_raw = (c.rolling(n, min_periods=n).min() + mult * a).values
    m = len(close)
    ls = np.full(m, np.nan); ss = np.full(m, np.nan)
    pl = np.nan; ps = np.nan
    for k in range(m):
        lr = ls_raw[k]; sr = ss_raw[k]
        if lr == lr:
            if pl == pl and close[k - 1] > pl:
                pl = max(lr, pl)
            else:
                pl = lr
            ls[k] = pl
        if sr == sr:
            if ps == ps and close[k - 1] < ps:
                ps = min(sr, ps)
            else:
                ps = sr
            ss[k] = ps
    return ls, ss


def _tod_str(minutes: int) -> str:
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS}
    if contract.name in ('MGC', 'GC'):
        p.update(GOLD_DEFAULTS)
    p.update(params)
    it = Intents(df1)
    rth = (contract.rth_open, contract.rth_close)
    bar = int(p['bar']); rsi_len = int(p['rsi_len']); ce_len = int(p['ce_len']); ce_mult = float(p['ce_mult'])
    stop_atr = float(p['stop_atr']); min_hold = int(p['min_hold']); max_trades = int(p['max_trades'])
    thresh = float(THRESH.get(rsi_len, 30)); thresh_s = 100.0 - thresh
    variant = str(p['variant']).upper()
    direction = str(p['direction']); regime = str(p['regime'])
    entry_start = hm(p['entry_start']); last_entry = hm(p['last_entry'])
    tick = float(contract.tick)

    B = resample(df1, bar, rth_only=True, rth=rth)
    close = B['close'].values.astype(float); low = B['low'].values.astype(float); high = B['high'].values.astype(float)
    r = rsi(B['close'], rsi_len).values
    a14 = atr(B, 14).values
    a22 = atr(B, ce_len).values
    ls, ss = chandelier(close, a22, ce_len, ce_mult)
    tod = B['tod'].values; day = B['day_id'].values; i_next = B['i_next'].values

    # per-session regime permissions
    days = np.unique(day)
    if regime == 'sma50_200':
        rg = regime_sma(df1, contract.data_symbol, 50, 200).reindex(days)
        ok = rg['s_fast'].notna() & rg['s_slow'].notna()
        long_ok = (ok & (rg['s_fast'] > rg['s_slow'])).to_dict()
        short_ok = (ok & (rg['s_fast'] < rg['s_slow']) & (direction == 'both')).to_dict()
    else:
        long_ok = {d: True for d in days}
        short_ok = {d: direction == 'both' for d in days}

    # module-side position state machine over the confirmed N-bars
    idx, side, stop_px = [], [], []
    ex_idx, ex_which = [], []
    pos = 0; k_entry = -1; sp = np.nan; cur_day = -1; n_day = 0
    m = len(B)
    for k in range(m):
        d = day[k]
        if d != cur_day:                       # (c) the session ended: flat
            cur_day = d; pos = 0; n_day = 0
        if pos != 0:
            # (b) stop mirror: the engine's protective stop was hit inside this N-bar
            if (pos > 0 and low[k] <= sp) or (pos < 0 and high[k] >= sp):
                pos = 0
            elif k - k_entry >= min_hold and ((pos > 0 and ls[k] == ls[k] and close[k] < ls[k]) or
                                              (pos < 0 and ss[k] == ss[k] and close[k] > ss[k])):
                if i_next[k] != -1:
                    ex_idx.append(int(i_next[k])); ex_which.append(pos)
                pos = 0
                continue                       # (a) flat from k'+1: no entry on the exit bar itself
            else:
                continue
        # flat: look for the deciding cross on bar k
        if k == 0 or not (entry_start <= tod[k] < last_entry) or i_next[k] == -1 or n_day >= max_trades:
            continue
        r0 = r[k - 1]; r1 = r[k]
        if r0 != r0 or r1 != r1 or a14[k] != a14[k]:
            continue
        s = 0
        if variant == 'A':
            if long_ok.get(d, False) and r0 >= thresh and r1 < thresh:
                s = 1
            elif short_ok.get(d, False) and r0 <= thresh_s and r1 > thresh_s:
                s = -1
        else:
            if long_ok.get(d, False) and r0 < thresh and r1 >= thresh:
                s = 1
            elif short_ok.get(d, False) and r0 > thresh_s and r1 <= thresh_s:
                s = -1
        if s == 0:
            continue
        ref = close[k]
        if s > 0:
            spx = np.floor((ref - stop_atr * a14[k]) / tick) * tick
        else:
            spx = np.ceil((ref + stop_atr * a14[k]) / tick) * tick
        if not (spx == spx) or (s > 0 and spx >= ref) or (s < 0 and spx <= ref):
            continue
        idx.append(int(i_next[k])); side.append(s); stop_px.append(float(spx))
        pos = s; k_entry = k; sp = spx; n_day += 1
    if idx:
        it.place(np.array(idx, dtype=int), np.array(side, dtype=np.int8), stop_px=np.array(stop_px))
    if ex_idx:
        it.exit_at(np.array(ex_idx, dtype=int), which=np.array(ex_which, dtype=np.int8))
    it.set_session(p['entry_start'], _tod_str(last_entry + bar), p['flat'])
    it.max_trades_day = max_trades
    it.daily_loss_stop = BLOCK_DLS.get(contract.name, 60.0) * float(p['dls_mult'])
    it.daily_profit_stop = BLOCK_DPS.get(contract.name, 120.0) * float(p['dps_mult'])
    return it
