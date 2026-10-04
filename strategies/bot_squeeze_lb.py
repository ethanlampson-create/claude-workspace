"""LazyBear Squeeze Momentum (TTM squeeze) first-release breakout, linreg momentum direction, Keltner-band stop.

Family bot_popular_indicators, spec 8 (research/specs/bot_popular_indicators.md; research/families/bot_popular_indicators.md 2.8).
Formulas are the open-source SQZMOM_LB Pine script (BB 20/2.0, KC 20/1.5 useTrueRange, momentum length 20); the first-release /
momentum-direction entry and the KC-band stop are the standard Carter / Bitduke strategy reading; rr 2.0 and the 0.5 x ATR14d
stop clamp are the prop-account additions.

RULES AS IMPLEMENTED (all times ET; RTH = (contract.rth_open, contract.rth_close): 09:30-16:00 MES/MNQ, 08:20-13:30 MGC pit):
BARS: B = resample(df1, bar, rth_only=True, rth=rth), continuous across sessions (the first bar of a day continues the previous
  day's indicator state, TradingView "RTH chart" semantics). bar = 5 or 15.
INDICATORS on B (all rolling windows use min_periods = full window; NaN rows never trade):
  BB(bb_len, bb_mult): mid = SMA(close, bb_len); sd = POPULATION stdev of the last bb_len closes (ddof=0, Pine ta.stdev);
    bb_up = mid + bb_mult*sd, bb_dn = mid - bb_mult*sd.
  KC_LB(kc_len, kc_mult): ma = SMA(close, kc_len); TR[k] = max(high-low, |high-close[k-1]|, |low-close[k-1]|);
    rangema = SMA(TR, kc_len); kc_up = ma + kc_mult*rangema, kc_dn = ma - kc_mult*rangema.
  sqzOn[k] = bb_dn[k] > kc_dn[k] and bb_up[k] < kc_up[k];  sqzOff[k] = bb_dn[k] < kc_dn[k] and bb_up[k] > kc_up[k].
  run[k] = number of consecutive sqzOn bars ending at k (0 when not sqzOn[k]).
  Momentum (LazyBear exact): x[k] = close[k] - ((max(high[k-L+1..k]) + min(low[k-L+1..k]))/2 + SMA(close, L)[k])/2, L = mom_len;
    val[k] = linreg(x, L, 0) = fitted value at the LAST point of the OLS line through x[k-L+1..k] (intercept + slope*(L-1)).
  fire[k] = sqzOff[k] and sqzOn[k-1] and run[k-1] >= min_squeeze_bars            (first release bar only)
  side[k] = +1 if val[k] > 0 and val[k] > val[k-1]; -1 if val[k] < 0 and val[k] < val[k-1]; else 0 (no trade on that release).
ENTRY: for k with fire[k] and side[k] != 0, entry_start <= B.tod[k] < last_entry, i = B.i_next[k] != -1, module state flat,
  indicators and ATR14d[day(k)] not NaN, fewer than max_trades entries today:
  entry_ref = close[k]; raw_stop = kc_dn[k] (long) / kc_up[k] (short); dist = |entry_ref - raw_stop| clamped to
  [2 ticks, max_stop_atr*ATR14d[day(k)]] (ATR14d = Wilder ATR(14) of daily RTH bars, shifted one day);
  stop_px = entry_ref - side*dist rounded AWAY from the entry to the tick; tgt_px = entry_ref + side*rr*dist if exit_mode == 'rr'
  else NaN.  it.place(i, side, stop_px=stop_px, tgt_px=tgt_px): market at the next 1-min open (+1 tick slippage).
EXIT: exit_mode 'rr': stop / target / forced flat only.
  exit_mode 'mom_fade': first bar k' > k with k' - k >= 2 and (long) val[k'] < val[k'-1] / (short) val[k'] > val[k'-1]
  (histogram turns dark = momentum fading): it.exit_at(B.i_next[k'], which=side) (market at the next 1-min open); plus the hard
  stop and forced flat; no target.
POSITION STATE (module side, mirrors the engine): flat again after (a) the fade exit is emitted (from k'+1), (b) a stop-touch
  mirror on a bar after the entry bar (long: N-bar low <= stop_px; short: high >= stop_px), (c) a target-touch mirror in 'rr'
  mode (long: high >= tgt_px; short: low <= tgt_px; stop checked first, like the engine), or (d) the session end.
  New entries only when flat; max_trades entries per day.
SESSION: it.set_session(entry_start, last_entry + bar, flat): the engine window ends one bar after last_entry so that the signal
  bar starting just before last_entry (tod[k] < last_entry) can fill at its i_next; this keeps module state and engine in step.
  it.max_trades_day = max_trades; daily_loss_stop = dls_mult*block; daily_profit_stop = dps_mult*block (Lucid risk block per
  ONE micro: MES 60/120, MNQ 80/160, MGC 80/160 $).
GOLD (GOLD_DEFAULTS when contract.name in ('MGC', 'GC')): pit mapping, entries 08:35-12:30, flat 13:25.
"""
import math
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm, resample
from strategies.common import daily_atr

NAME = 'LazyBear Squeeze Momentum first-release breakout, linreg momentum direction, KC-band stop'
DESCRIPTION = __doc__
CONTRACTS = ['MNQ', 'MES']
PARAMS = {'bar': 5, 'bb_len': 20, 'bb_mult': 2.0, 'kc_len': 20, 'kc_mult': 1.5, 'mom_len': 20, 'min_squeeze_bars': 3,
          'exit_mode': 'rr', 'rr': 2.0, 'max_stop_atr': 0.5, 'entry_start': '09:45', 'last_entry': '14:30', 'flat': '15:55',
          'max_trades': 2, 'dls_mult': 1.0, 'dps_mult': 1.0}
GOLD_DEFAULTS = {'entry_start': '08:35', 'last_entry': '12:30', 'flat': '13:25'}
GRID = {'bar': [5, 15], 'kc_mult': [1.5, 2.0], 'exit_mode': ['rr', 'mom_fade'], 'min_squeeze_bars': [3, 6]}   # 16 combos
# Lucid risk block per ONE contract: (daily_loss_stop, daily_profit_stop) in $
BLOCK = {'MES': (60.0, 120.0), 'MNQ': (80.0, 160.0), 'MGC': (80.0, 160.0),
         'ES': (600.0, 1200.0), 'NQ': (800.0, 1600.0), 'GC': (800.0, 1600.0)}


def linreg_last(x: np.ndarray, n: int) -> np.ndarray:
    """Pine ta.linreg(x, n, 0): value at the last bar of the least-squares line fitted to the last n points (t = 0..n-1).
    NaN until n points are available or when the window contains a NaN."""
    out = np.full(len(x), np.nan)
    if len(x) < n:
        return out
    t = np.arange(n, dtype=float); tbar = t.mean(); sst = ((t - tbar) ** 2).sum()
    w = 1.0 / n + (t - tbar) * ((n - 1) - tbar) / sst          # fitted value at t = n-1 is a fixed linear combination of y
    win = np.lib.stride_tricks.sliding_window_view(x, n)
    out[n - 1:] = win @ w                                      # NaNs propagate naturally
    return out


def squeeze_table(B: pd.DataFrame, p: dict) -> pd.DataFrame:
    """Indicator columns on the N-minute bars: bb_up/bb_dn, kc_up/kc_dn, sqz_on/sqz_off, run, val, fire, side."""
    c = B['close']; h = B['high']; l = B['low']
    bb_len = int(p['bb_len']); kc_len = int(p['kc_len']); L = int(p['mom_len'])
    mid = c.rolling(bb_len, min_periods=bb_len).mean()
    sd = c.rolling(bb_len, min_periods=bb_len).std(ddof=0)
    bb_up = mid + float(p['bb_mult']) * sd; bb_dn = mid - float(p['bb_mult']) * sd
    ma = c.rolling(kc_len, min_periods=kc_len).mean()
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1, skipna=False)
    rangema = tr.rolling(kc_len, min_periods=kc_len).mean()
    kc_up = ma + float(p['kc_mult']) * rangema; kc_dn = ma - float(p['kc_mult']) * rangema
    ok = bb_up.notna() & kc_up.notna()
    sqz_on = ok & (bb_dn > kc_dn) & (bb_up < kc_up)
    sqz_off = ok & (bb_dn < kc_dn) & (bb_up > kc_up)
    # run length of consecutive sqz_on bars ending at k
    on = sqz_on.values.astype(np.int64)
    run = np.zeros(len(on), dtype=np.int64)
    r = 0
    for k in range(len(on)):
        r = r + 1 if on[k] else 0
        run[k] = r
    hh = h.rolling(L, min_periods=L).max(); ll = l.rolling(L, min_periods=L).min(); sc = c.rolling(L, min_periods=L).mean()
    x = (c - ((hh + ll) / 2.0 + sc) / 2.0).values
    val = linreg_last(x, L)
    vprev = np.r_[np.nan, val[:-1]]
    side = np.where(np.isnan(val) | np.isnan(vprev), 0, np.where((val > 0) & (val > vprev), 1, np.where((val < 0) & (val < vprev), -1, 0)))
    on_prev = np.r_[False, sqz_on.values[:-1]]; run_prev = np.r_[0, run[:-1]]
    fire = sqz_off.values & on_prev & (run_prev >= int(p['min_squeeze_bars']))
    out = B.copy()
    out['bb_up'] = bb_up.values; out['bb_dn'] = bb_dn.values; out['kc_up'] = kc_up.values; out['kc_dn'] = kc_dn.values
    out['sqz_on'] = sqz_on.values; out['sqz_off'] = sqz_off.values; out['run'] = run; out['val'] = val
    out['fire'] = fire; out['side'] = side.astype(np.int8)
    return out


def _tod_str(minutes: int) -> str:
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS}
    if contract.name in ('MGC', 'GC'):
        p.update(GOLD_DEFAULTS)
    p.update(params)
    it = Intents(df1)
    rth = (contract.rth_open, contract.rth_close)
    tick = float(contract.tick)
    bar = int(p['bar'])
    e_start = hm(p['entry_start']); e_last = hm(p['last_entry'])
    rr = float(p['rr']); max_stop_atr = float(p['max_stop_atr']); max_trades = int(p['max_trades'])
    use_rr = str(p['exit_mode']) == 'rr'

    B = resample(df1, bar, rth_only=True, rth=rth)
    T = squeeze_table(B, p)
    datr = daily_atr(df1, 14, rth_only=True, rth=rth)
    atr_d = T['day_id'].map(datr).values

    day = T['day_id'].values; tod = T['tod'].values; i_next = T['i_next'].values
    c = T['close'].values; h = T['high'].values; l = T['low'].values
    kc_up = T['kc_up'].values; kc_dn = T['kc_dn'].values; val = T['val'].values
    fire = T['fire'].values; sd_ = T['side'].values
    ind_ok = ~(np.isnan(kc_up) | np.isnan(val) | np.isnan(T['bb_up'].values))
    nB = len(T)

    e_idx, e_side, e_sp, e_tp = [], [], [], []
    x_idx, x_which = [], []
    pos = 0; sp = np.nan; tp = np.nan; k_entry = -1; ntr = 0; cur_day = -1
    for k in range(nB):
        if day[k] != cur_day:                       # session boundary: flat, reset the per-day trade count
            cur_day = day[k]; pos = 0; ntr = 0
        if pos != 0:
            # engine mirrors on the bars after the entry bar (the fill is at the open of bar k_entry+1's first minute)
            if (pos > 0 and l[k] <= sp) or (pos < 0 and h[k] >= sp):
                pos = 0                             # hard stop touched (checked before the target, like the engine)
            elif use_rr and ((pos > 0 and h[k] >= tp) or (pos < 0 and l[k] <= tp)):
                pos = 0                             # target touched
            elif (not use_rr) and k - k_entry >= 2 and not np.isnan(val[k]) and not np.isnan(val[k - 1]) and \
                    ((pos > 0 and val[k] < val[k - 1]) or (pos < 0 and val[k] > val[k - 1])):
                if i_next[k] >= 0:
                    x_idx.append(int(i_next[k])); x_which.append(int(pos))
                pos = 0
                continue                            # flat from k+1 on (no entry on the exit bar)
            else:
                continue
            # position closed inside bar k: a release on this same bar may start a new trade (its fill is after the bar)
        if ntr >= max_trades or not fire[k] or sd_[k] == 0 or tod[k] < e_start or tod[k] >= e_last or i_next[k] < 0:
            continue
        if not ind_ok[k] or np.isnan(atr_d[k]):
            continue
        side = int(sd_[k]); ref = float(c[k])
        raw = kc_dn[k] if side > 0 else kc_up[k]
        dist = abs(ref - raw)
        dist = min(max(dist, 2.0 * tick), max_stop_atr * float(atr_d[k]))
        if dist <= 0:
            continue
        if side > 0:
            spx = math.floor((ref - dist) / tick + 1e-9) * tick
        else:
            spx = math.ceil((ref + dist) / tick - 1e-9) * tick
        tpx = ref + side * rr * dist if use_rr else np.nan
        e_idx.append(int(i_next[k])); e_side.append(side); e_sp.append(spx); e_tp.append(tpx)
        pos = side; sp = spx; tp = tpx; k_entry = k; ntr += 1
    if e_idx:
        it.place(np.array(e_idx, dtype=int), np.array(e_side, dtype=np.int8), stop_px=np.array(e_sp), tgt_px=np.array(e_tp))
    if x_idx:
        it.exit_at(np.array(x_idx, dtype=int), which=np.array(x_which, dtype=np.int8))
    it.set_session(p['entry_start'], _tod_str(e_last + bar), p['flat'])
    it.max_trades_day = max_trades
    dls, dps = BLOCK.get(contract.name, (0.0, 0.0))
    it.daily_loss_stop = float(p['dls_mult']) * dls
    it.daily_profit_stop = float(p['dps_mult']) * dps
    return it
