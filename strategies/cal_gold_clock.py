"""Gold round-the-clock legs on MGC: London/western-hours short, pre-London-fix fades, NY-hours long (family calendar_seasonal_structural).

Source: Copenhagen Business School thesis "Gold Price Dynamics Around the Clock" (GC 5-min, 2001-2018; research/families/
calendar_seasonal_structural.md section 18; spec research/specs/calendar_seasonal_structural.md section 9). The thesis documents a
hat-shaped 24h return profile in NY time: gold rises during Asian hours (18:00-02:00 ET), falls through the London OTC / COMEX
hours to a local minimum at 10:00 ET (with -3.7 pp / -4.2 pp spikes in the 30 minutes before the London AM / PM fixes), then
rises again into the 17:00 close. Only the DAYTIME legs are implemented here; the Asian-hours long (18:00 -> 02:00) is an
overnight hold and is forbidden by the project convention.

CONVENTIONS (all times ET). A 1-min bar with tod = T covers [T, T+1). c(HH:MM) = close of the bar with tod = HH:MM - 1 min
(the price "at HH:MM"); i(HH:MM) = index of the bar with tod = HH:MM; an order placed at i(HH:MM) is a market order at that
bar's open (+1 tick slippage), decided on information up to the close of the previous bar. The gold data session runs
18:00 -> 17:00 (bars to 16:59); the entry at 03:00 of session d lies inside the session that opened at 18:00 the previous evening.
  prev_close17[d] = last 1-min close of session d-1 with tod < 17:00.   open18[d] = open of the first bar of session d with tod >= 18:00.
  ATRg            = daily_atr(df1, 14, rth_only=False)  (full-session daily ATR, shifted one session; context / report only).
  F               = strategies._cal_flags.flags(df1) computed on XAUUSD's own bars (macro0830 uses the 08:30-08:31 range).
  fixAM[d]/fixPM[d] = 10:30 / 15:00 Europe/London clock on the session date converted to ET (normally 05:30 / 10:00 ET;
                    04:30 / 09:00 or 06:30 / 11:00 ET in the 2-3 weeks per year when UK and US DST differ).

LEG TABLE (param `leg`; side; entry tod; exit tod; default stop_pct of the reference price)
  'west_short'  -1  03:00            10:00       0.6   London open to the thesis's 10:00 ET minimum (fixed ET clock; "Short 02:00-11:00" core)
  'pmfix_fade'  -1  fixPM - 30 min   fixPM       0.4   the -4.2 pp half-hour before the London PM auction
  'ny_long'     +1  10:05            16:30       0.5   rising leg of the U (GLD's drift accrues in NY hours)
  'amfix_fade'  -1  fixAM - 30 min   fixAM       0.4   implemented, not in the grid (30-min window vs $3.30 round-trip cost)
  'pmfix_momo'  +/- fixPM + 5 min    fixPM + 30  0.3   side = sign(c(fixPM+5) - c(fixPM+1)) = sign(close[tod fixPM+4] - close[tod fixPM]); the
                                                       Caminschi-Heaney post-fix leak (normally 10:05 -> 10:30); not in the grid; 2010-14 vs 2015-26 only
  stop_pct: the leg default is used unless leg == 'west_short' AND params give stop_pct (so a grid over `leg` keeps every leg's own
  default even when the base params carry west_short's 0.6). stop_mult scales the result. stop_pts = stop_pct * stop_mult / 100 * ref.

DAY FILTERS
  gap_skip:   skip session d when |open18[d] - prev_close17[d]| / prev_close17[d] > gap_skip_pct / 100 (or either price is missing).
  winter_only: trade only when America/New_York is on standard time on the session date (Nov-Mar; the thesis's strong half).
  skip_macro: for legs whose window contains 08:30 (west_short) the macro0830 flag is only known at 08:32 while the position has been
              open since 03:00, so the entry is NOT skipped (look-ahead); instead the position is forced flat at the open of the 08:32 bar
              (first bar with tod >= 08:32) when macro0830[d] fires.
  Any missing bar at the entry tod, the exit tod, or the reference bar (entry bar - 1 of the same session) -> no trade that day.
ENTRY: ref = close of the bar before the entry bar; Intents.place(i(entry), side, stop_pts = stop_pct*stop_mult/100*ref): market at the open.
       One entry per session (max_trades_day = 1); no re-entry after a stop.
EXIT:  protective stop (level - slip) or Intents.exit_at(i(exit)) = market at the open of the exit bar; force_flat from the exit tod to the
       session end; additionally nothing may be open at or after 16:30 ET (global guard, well inside Lucid's 16:45 gold deadline).
SESSION: fixed-clock legs use set_session(entry, entry + 1 min, exit); fix-anchored legs set it.allow_entry (entry bar only) and
       it.force_flat (from the exit bar) per session. Daily loss/profit stops are moot with one trade per day.
"""
import datetime as _dt
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm
from strategies.common import daily_atr
from strategies._cal_flags import flags

NAME = 'Gold round-the-clock legs (western-hours short / pre-fix fade / NY-hours long)'
DESCRIPTION = __doc__
CONTRACTS = ['MGC']
PARAMS = {'leg': 'west_short', 'stop_pct': 0.6, 'stop_mult': 1.0, 'gap_skip_pct': 1.0, 'winter_only': False, 'skip_macro': True, 'max_trades': 1}
GRID = {'leg': ['west_short', 'ny_long', 'pmfix_fade'], 'winter_only': [False, True], 'stop_mult': [1.0, 1.5]}   # 12 combos; stop_pct = leg default

# side, entry, exit, default stop %, anchor ('am' / 'pm' fix or None = fixed ET clock). Anchored legs give entry/exit as minute offsets from the fix.
LEGS = {
    'west_short': {'side': -1, 'entry': hm('03:00'), 'exit': hm('10:00'), 'stop': 0.6, 'anchor': None},
    'pmfix_fade': {'side': -1, 'entry': -30, 'exit': 0, 'stop': 0.4, 'anchor': 'pm'},
    'ny_long':    {'side': +1, 'entry': hm('10:05'), 'exit': hm('16:30'), 'stop': 0.5, 'anchor': None},
    'amfix_fade': {'side': -1, 'entry': -30, 'exit': 0, 'stop': 0.4, 'anchor': 'am'},
    'pmfix_momo': {'side': 0, 'entry': 5, 'exit': 30, 'stop': 0.3, 'anchor': 'pm'},
}
MACRO_TOD = hm('08:30')
MACRO_KNOWN = hm('08:32')
HARD_FLAT = hm('16:30')
_LON = ZoneInfo('Europe/London'); _NY = ZoneInfo('America/New_York')


def fix_tod(dates, london_hm: str) -> np.ndarray:
    """ET minutes-of-day of a London wall-clock time on each date (handles the weeks when UK and US DST differ)."""
    h, m = (int(x) for x in london_hm.split(':'))
    out = np.full(len(dates), -1, dtype=int)
    cache = {}
    for k, d in enumerate(dates):
        if d is None or d != d:
            continue
        if d not in cache:
            t = _dt.datetime(d.year, d.month, d.day, h, m, tzinfo=_LON).astimezone(_NY)
            cache[d] = t.hour * 60 + t.minute
        out[k] = cache[d]
    return out


def ny_dst(dates) -> np.ndarray:
    """True when America/New_York is on daylight time on the session date (UTC offset -4h at noon of that date)."""
    out = np.zeros(len(dates), dtype=bool)
    for k, d in enumerate(dates):
        if d is None or d != d:
            continue
        out[k] = _dt.datetime(d.year, d.month, d.day, 12, tzinfo=_NY).utcoffset() == _dt.timedelta(hours=-4)
    return out


def day_table(df1: pd.DataFrame, p: dict) -> pd.DataFrame:
    """Per-session frame (indexed by day_id): session, dst, fix tods, gap, macro0830, ATRg, entry/exit/ref indices and the
    day_ok flag for the requested leg. Only information available before the entry bar is used for day_ok."""
    leg = LEGS[p['leg']]
    tod = df1['tod'].values; day = df1['day_id'].values
    n = len(df1); ndays = int(day.max()) + 1
    g = df1.groupby('day_id')
    sess = g['session'].first().reindex(range(ndays))
    t = pd.DataFrame({'session': sess.values}, index=sess.index)
    F = flags(df1, rth=('08:20', '13:30'))
    t['dst'] = ny_dst(t['session'].values)
    t['macro0830'] = F['macro0830'].reindex(t.index).fillna(False).values.astype(bool)
    t['atr'] = daily_atr(df1, 14, rth_only=False).reindex(t.index).values
    t['fix_am'] = fix_tod(t['session'].values, '10:30')
    t['fix_pm'] = fix_tod(t['session'].values, '15:00')
    # gap filter inputs: previous session's last close before 17:00 and this session's first bar at/after 18:00
    pc = df1[tod < hm('17:00')].groupby('day_id')['close'].last().reindex(t.index)
    t['prev_close17'] = pc.shift(1).values
    t['open18'] = df1[tod >= hm('18:00')].groupby('day_id')['open'].first().reindex(t.index).values
    t['gap_pct'] = 100.0 * (t['open18'] - t['prev_close17']).abs() / t['prev_close17']
    # leg clock per session
    if leg['anchor'] is None:
        t['entry_tod'] = leg['entry']; t['exit_tod'] = leg['exit']
    else:
        fx = t['fix_pm'] if leg['anchor'] == 'pm' else t['fix_am']
        t['entry_tod'] = fx + leg['entry']; t['exit_tod'] = fx + leg['exit']
    # (day, tod) -> first 1-min index lookup
    pos = np.full((ndays, 1440), -1, dtype=np.int64)
    order = np.arange(n)[::-1]                 # reversed so the FIRST bar of any duplicate (day, tod) wins
    pos[day[order], tod[order]] = order
    et = t['entry_tod'].values.astype(int); xt = t['exit_tod'].values.astype(int)
    di = np.arange(ndays)
    t['i_entry'] = pos[di, np.clip(et, 0, 1439)]
    t['i_exit'] = pos[di, np.clip(xt, 0, 1439)]
    ie = t['i_entry'].values
    ref_ok = (ie > 0) & (day[np.clip(ie - 1, 0, n - 1)] == di)
    t['ref'] = np.where(ref_ok, df1['close'].values[np.clip(ie - 1, 0, n - 1)], np.nan)
    # first bar at/after 08:32 of each session (macro flat) and whether the leg's window contains 08:30
    after = pos[:, MACRO_KNOWN:hm('18:00')]
    has = after >= 0
    t['i_macro_flat'] = np.where(has.any(axis=1), after[di, np.argmax(has, axis=1)], -1)
    t['straddles_0830'] = (t['entry_tod'] <= MACRO_TOD) & (t['exit_tod'] > MACRO_TOD)
    # side (pmfix_momo needs the post-fix closes; everything else is fixed)
    if p['leg'] == 'pmfix_momo':
        c0 = pos[di, np.clip(t['fix_pm'].values, 0, 1439)]; c4 = pos[di, np.clip(t['fix_pm'].values + 4, 0, 1439)]
        ok = (c0 >= 0) & (c4 >= 0)
        cl = df1['close'].values
        mv = np.where(ok, cl[np.clip(c4, 0, n - 1)] - cl[np.clip(c0, 0, n - 1)], np.nan)
        t['side'] = np.where(np.isnan(mv), 0, np.sign(mv)).astype(int)
    else:
        t['side'] = leg['side']
    # day filters (entry-time information only)
    ok = (t['i_entry'] >= 0) & (t['i_exit'] >= 0) & (t['i_exit'] > t['i_entry']) & t['ref'].notna() & (t['side'] != 0)
    ok &= t['gap_pct'].notna() & (t['gap_pct'] <= float(p['gap_skip_pct']))
    if p['winter_only']:
        ok &= ~t['dst'].astype(bool)
    t['day_ok'] = ok
    return t


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS, **params}
    if p['leg'] not in LEGS:
        raise ValueError(f"unknown leg {p['leg']}")
    leg = LEGS[p['leg']]
    stop_pct = float(p['stop_pct']) if (p['leg'] == 'west_short' and 'stop_pct' in params) else float(leg['stop'])
    stop_pct *= float(p['stop_mult'])
    it = Intents(df1)
    t = day_table(df1, p)
    tr = t[t['day_ok']]
    tod = df1['tod'].values; day = df1['day_id'].values
    if len(tr):
        idx = tr['i_entry'].values.astype(int)
        side = tr['side'].values.astype(np.int8)
        it.place(idx, side, stop_pts=stop_pct / 100.0 * tr['ref'].values)
        it.exit_at(tr['i_exit'].values.astype(int), which=2)
    if leg['anchor'] is None:
        it.set_session(_tod_str(leg['entry']), _tod_str(leg['entry'] + 1), _tod_str(leg['exit']))
    else:
        allow = np.zeros(len(df1), bool)
        if len(tr):
            allow[tr['i_entry'].values.astype(int)] = True
        it.allow_entry &= allow
        xt = t['exit_tod'].reindex(range(int(day.max()) + 1)).fillna(hm('17:00')).values.astype(int)[day]
        it.force_flat |= (tod >= xt) & (tod < hm('18:00'))
        it.allow_entry &= ~it.force_flat
    # macro0830 flat for legs whose window contains 08:30 (decided at the close of 08:31, executed at the 08:32 open)
    if p['skip_macro'] and bool(t['straddles_0830'].iloc[0]):
        mf = t[(t['macro0830']) & (t['i_macro_flat'] >= 0)]['i_macro_flat'].values.astype(int)
        if len(mf):
            it.force_flat[mf] = True
    # nothing may be open at or after 16:30 ET
    guard = (tod >= HARD_FLAT) & (tod < hm('18:00'))
    it.force_flat |= guard
    it.allow_entry &= ~guard
    it.max_trades_day = int(p['max_trades'])
    return it


def _tod_str(minutes: int) -> str:
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def clock_profile(df1: pd.DataFrame, slot_min: int = 30) -> pd.DataFrame:
    """Mean close-to-close return of XAUUSD by `slot_min`-minute clock slot (ET, slot start), in basis points, with the
    t-statistic, the share of positive sessions and the cumulative path from 18:00 (the 'hat shape' as realised on our data).
    The slot ending at T uses the close of the last bar with tod < T versus the close of the last bar with tod < T - slot_min
    (the first slot of the session, 18:00 -> 18:30, starts from the previous session's last close)."""
    tod = df1['tod'].values
    since = (tod - hm('18:00')) % 1440
    slot = since // slot_min
    key = df1['day_id'].values * 1000 + slot
    last = pd.Series(df1['close'].values, index=key).groupby(level=0).last()
    full = pd.MultiIndex.from_product([np.arange(df1['day_id'].max() + 1), np.arange(1440 // slot_min)])
    s = pd.Series(last.values, index=last.index)
    frame = pd.DataFrame({'close': s})
    frame['day'] = frame.index // 1000; frame['slot'] = frame.index % 1000
    wide = frame.pivot(index='day', columns='slot', values='close').reindex(columns=np.arange(1440 // slot_min))
    flat = wide.values.ravel()
    prev = pd.Series(flat).ffill().shift(1).values.reshape(wide.shape)   # last available close before the slot
    ret = 1e4 * (wide.values - prev) / prev
    ret[np.isnan(wide.values)] = np.nan
    rows = []
    for k in range(wide.shape[1]):
        r = ret[:, k]; r = r[~np.isnan(r)]
        start = (hm('18:00') + k * slot_min) % 1440
        rows.append({'slot_start_et': _tod_str(start), 'n': len(r), 'mean_bp': r.mean() if len(r) else np.nan,
                     'tstat': r.mean() / r.std(ddof=1) * np.sqrt(len(r)) if len(r) > 2 else np.nan,
                     'pct_pos': (r > 0).mean() if len(r) else np.nan, 'std_bp': r.std(ddof=1) if len(r) > 1 else np.nan})
    out = pd.DataFrame(rows)
    out['cum_bp'] = out['mean_bp'].cumsum()
    return out
