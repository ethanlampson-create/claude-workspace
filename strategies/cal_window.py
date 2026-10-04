"""Calendar day-window long with controls: TOTM, OPEX week, FOMC morning (Lucca-Moench), unconditional all-days control.

Family calendar_seasonal_structural (research/families/calendar_seasonal_structural.md; spec section 7, FOMC leg from
section 2). One module, one `window` parameter: the intraday-only (09:31 -> 15:55, never overnight) version of every
"long this day" calendar effect, measured against a built-in negative control (window='all_days' = unconditional long).
Mechanism (calendar-flow day selection) is distinct from everything else in strategies/. Honest prior is LOW: the report's
own verdict is that the TOTM / OPEX-week / pre-holiday / Santa edges are overnight (close -> open), so the expected verdict
is 'dead' with the FOMC morning drift the only plausible positive; the valuable output is the control-adjusted table.

CONVENTIONS (all ET; a 1-min bar with tod=T covers [T, T+1)). i(HH:MM) = index of the bar with tod = HH:MM (the CFD feed
omits tick-less minutes; a missing 09:31 bar = no trade that day, never the 09:30 print). A market order placed at i fills
at that bar's open + 1 tick. ATR14d = daily_atr(df1, 14, rth_only=True) (Wilder, shifted one day). D = daily_bars(df1,
rth_only=True); SMA_D(200) = sma(D.close, 200).shift(1). F = _cal_flags.flags(df1) (shared helper, defined with
cal_macro_pm) + two flags computed here on F's calendar sessions: precash[d] = session is T-4, T-3 or T-2 of its month
(counted from the month's last session); pre_witch5[d] = one of the 5 sessions before a quad-witching day.

WINDOW TABLE (window -> day flag, default side, exit):
  'totm'        F.totm                                              +1  exit_time        (T-1, T+1..T+3; ~48 days/yr)
  'opex_week'   F.opex_week                                         +1  exit_time        (Mon-Thu of monthly expiration week; ~48/yr)
  'fomc'        F.fomc and (not press_conf_only or F.press_conference) +1  min(exit_time, fomc_stmt_tod - 5 min) = 13:55 for 2013+
  'fomc_all'    F.fomc (every scheduled statement day)              +1  same pre-statement exit (the 2013-2024 ~91-event test)
  'all_days'    True                                                +1  exit_time        (NEGATIVE CONTROL: unconditional long)
  'payday'      F.payday                                            +1  (~24/yr)
  'pre_witch5'  pre_witch5                                          +1  (~20/yr)
  'pre_holiday' F.holiday_next                                      +1  (~9/yr; early-close eves are removed by run.prepare's
                                                                        thin-session filter; with skip_thin_sessions=False exit 12:55 there)
  'santa'       F.santa                                             +1  (7/yr)
  'precash'     precash                                             -1  (T-4..T-2 'dash for cash' short bias; ~36/yr; unverified)
  'dow_tuewed'  F.dow in {1, 2}                                     +1  (weekday tilt; ~100/yr; control-like)
PER SESSION d: day_ok = window flag and ATR14d non-NaN and (not trend_filter or D.close[d-1] > SMA_D(200)[d]);
  side = table default unless the side param is +1 / -1; exit_tod per the table (never later than 15:55).
ENTRY: i = i(entry_time) (09:31). The decision uses nothing after the 09:30 open (the windows are known from the calendar
  the day before). place(i, side, stop_pts = stop_atr x ATR14d, tgt_pts = target_atr x ATR14d if target_atr > 0). Market
  at the 09:31 open. No re-entry after a stop (max_trades_day 1).
EXIT: protective stop / optional target / exit_at(i(exit_tod)) = market at the open of the first bar >= exit_tod;
  force_flat from exit_tod[d] to session end on every session (per-session arrays because the exit differs on FOMC
  days); global force_flat at 15:55 regardless.
SESSION/RISK: set_session(entry_time, entry_time + 1 min, '15:55'); then it.force_flat[i] = True and it.allow_entry[i] =
  False for bars with tod >= exit_tod[d]. max_trades_day 1; daily stops moot. Stop 0.75 ATR ~ 45 ES pts = $225/MES -> the
  Lucid Monte Carlo sizes 3-5 micros; the FOMC window keeps the family spec's wide stop (never below 0.5 ATR).
"""
import datetime as _dt
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm, daily_bars
from strategies.common import daily_atr, sma
from strategies._cal_flags import flags

NAME = 'Calendar day-window long with controls: TOTM, OPEX week, FOMC morning (Lucca-Moench), all-days control'
DESCRIPTION = __doc__
CONTRACTS = ['MES', 'MNQ']
PARAMS = {'window': 'totm', 'side': 'auto', 'entry_time': '09:31', 'exit_time': '15:55', 'stop_atr': 0.75, 'target_atr': 0.0,
          'trend_filter': False, 'press_conf_only': True, 'max_trades': 1}
GRID = {'window': ['totm', 'opex_week', 'fomc', 'all_days'], 'exit_time': ['12:00', '15:55'], 'stop_atr': [0.5, 1.0]}   # 16 combos
WINDOWS = ('totm', 'opex_week', 'fomc', 'all_days', 'payday', 'pre_witch5', 'pre_holiday', 'santa', 'precash', 'dow_tuewed', 'fomc_all')
DEFAULT_SIDE = {w: 1 for w in WINDOWS}
DEFAULT_SIDE['precash'] = -1
FLAT = '15:55'                 # global forced flat (equities; never later than 15:58)
EARLY_CLOSE_EXIT = '12:55'     # exit on half-day sessions (only reachable with skip_thin_sessions=False)


def _tod_str(minutes: int) -> str:
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def extra_flags(F: pd.DataFrame) -> pd.DataFrame:
    """precash (T-4..T-2 of the month) and pre_witch5 (the 5 sessions before a quad-witching day), on F's calendar sessions."""
    dates = F['session'].values
    cal = F['cal_session'].values.astype(bool)
    valid = [d for d, v in zip(dates, cal) if v]
    by_month = {}
    for d in valid:
        by_month.setdefault((d.year, d.month), []).append(d)
    precash = set()
    for lst in by_month.values():
        precash.update(lst[-4:-1])           # T-4, T-3, T-2 (T-1 = lst[-1] belongs to totm)
    witch = set(d for d, w, v in zip(dates, F['witching'].values, cal) if w and v)
    pre_w = set()
    for k, d in enumerate(valid):
        if d in witch:
            pre_w.update(valid[max(0, k - 5):k])
    out = pd.DataFrame(index=F.index)
    out['precash'] = np.array([d in precash for d in dates], dtype=bool)
    out['pre_witch5'] = np.array([d in pre_w for d in dates], dtype=bool)
    return out


def window_flags(F: pd.DataFrame, press_conf_only=True) -> pd.DataFrame:
    """One boolean column per window of the table (all 10 lines), indexed by day_id."""
    X = extra_flags(F)
    W = pd.DataFrame(index=F.index)
    W['totm'] = F['totm'].astype(bool)
    W['opex_week'] = F['opex_week'].astype(bool)
    W['fomc'] = F['fomc'].astype(bool) & (F['press_conference'].astype(bool) if press_conf_only else True)
    W['fomc_all'] = F['fomc'].astype(bool)
    W['all_days'] = True
    W['payday'] = F['payday'].astype(bool)
    W['pre_witch5'] = X['pre_witch5']
    W['pre_holiday'] = F['holiday_next'].astype(bool)
    W['santa'] = F['santa'].astype(bool)
    W['precash'] = X['precash']
    W['dow_tuewed'] = F['dow'].isin([1, 2])
    return W


def day_table(df1: pd.DataFrame, contract, p: dict) -> pd.DataFrame:
    """Per-session inputs: every column uses only the calendar and sessions < d (ATR, SMA) or the 09:30 open at most."""
    rth = (contract.rth_open, contract.rth_close)
    F = flags(df1, rth=rth)
    W = window_flags(F, bool(p['press_conf_only']))
    w = p['window']
    if w not in W.columns:
        raise ValueError(f'unknown window={w!r}; one of {list(W.columns)}')
    D = daily_bars(df1, rth_only=True, rth=rth)
    t = pd.DataFrame(index=F.index)
    t['session'] = F['session']
    t['atr'] = daily_atr(df1, 14, rth_only=True, rth=rth).reindex(t.index)
    t['prev_close'] = D['close'].shift(1).reindex(t.index)
    t['sma200'] = sma(D['close'], 200).shift(1).reindex(t.index)
    t['open_0930'] = df1[df1['tod'] == hm(rth[0])].groupby('day_id')['open'].first().reindex(t.index)
    et = hm(p['entry_time'])
    ib = df1[df1['tod'] == et].groupby('day_id').apply(lambda x: x.index[0])
    t['i_entry'] = pd.Series(ib, dtype=float).reindex(t.index)
    ie = t['i_entry'].fillna(0).astype(int).values
    t['ref'] = np.where(t['i_entry'].notna() & (ie > 0), df1['close'].values[np.maximum(ie - 1, 0)], np.nan)   # close of bar i-1 (the 09:30 bar)
    for c in W.columns:
        t['w_' + c] = W[c]
    t['fomc'] = F['fomc'].astype(bool)
    t['press_conference'] = F['press_conference'].astype(bool)
    t['early_close'] = F['early_close'].astype(bool)
    t['dow'] = F['dow']
    # exit time per session (minutes): exit_time, earlier on FOMC days for the fomc window, 12:55 on half-days, <= 15:55
    xt = np.full(len(t), min(hm(p['exit_time']), hm(FLAT)), dtype=int)
    if w in ('fomc', 'fomc_all'):
        st = F['fomc_stmt_tod'].values.astype(int)
        xt = np.where(t['fomc'].values & (st > 0), np.minimum(xt, st - 5), xt)
    xt = np.where(t['early_close'].values, np.minimum(xt, hm(EARLY_CLOSE_EXIT)), xt)
    t['exit_tod'] = xt
    side = DEFAULT_SIDE[w]
    if p['side'] not in ('auto', None):
        side = int(np.sign(int(p['side']))) or side
    t['side'] = side
    ok = W[w].astype(bool) & t['atr'].notna() & t['i_entry'].notna()
    if p['trend_filter']:
        ok &= t['prev_close'].notna() & t['sma200'].notna() & (t['prev_close'] > t['sma200'])
    t['day_ok'] = ok
    return t


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS, **params}
    it = Intents(df1)
    t = day_table(df1, contract, p)
    tod = df1['tod'].values
    day_id = df1['day_id'].values
    tr = t[t['day_ok']]
    if len(tr):
        idx = tr['i_entry'].values.astype(int)
        stop = float(p['stop_atr']) * tr['atr'].values
        tgt = float(p['target_atr']) * tr['atr'].values if float(p['target_atr']) > 0 else np.nan
        it.place(idx, tr['side'].values.astype(np.int8), stop_pts=stop, tgt_pts=tgt)
        # exit_at the first bar >= exit_tod of each trading session (market at its open)
        xt_bar = tr['exit_tod'].reindex(day_id).values
        cand = np.flatnonzero((tod >= xt_bar) & (tod < hm('18:00')))
        if len(cand):
            first = pd.Series(cand).groupby(day_id[cand]).min().values
            it.exit_at(first)
    et = hm(p['entry_time'])
    it.set_session(p['entry_time'], _tod_str(et + 1), FLAT)
    # per-session flat window (differs on FOMC / half-day sessions): flat from exit_tod to session end, no entries there
    xt_all = t['exit_tod'].reindex(day_id).fillna(hm(FLAT)).values
    fl = (tod >= xt_all) & (tod < hm('18:00'))
    it.force_flat |= fl
    it.allow_entry &= ~it.force_flat
    it.max_trades_day = int(p['max_trades'])
    return it
