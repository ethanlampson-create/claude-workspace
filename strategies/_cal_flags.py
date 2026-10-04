"""Shared per-session calendar / event flags for the calendar_seasonal_structural family (spec section 1).

NOT a strategy (leading underscore keeps strategies.available() from listing it). Usage:
    from strategies._cal_flags import flags
    F = flags(df1, k0830=3.0, k1400=3.0, median_lookback=60)      # DataFrame indexed by day_id

Every column uses only sessions <= d (event detectors: bars of session d itself, known at 08:32 / 14:02) or fixed
calendar arithmetic (3rd Friday, FOMC table). The repo has NO economic calendar: CPI/NFP/PPI/GDP mornings are detected
from the size of the 08:30 reaction itself (OHLC only), FOMC-minutes afternoons from the 14:00 reaction, and FOMC
statement days come from the hard-coded table below (verified against federalreserve.gov, 2013-2026, on 2026-10-04).

Conventions: all times ET; a 1-min bar with tod=T covers [T, T+1). The CFD feed prints no bar for a minute without a
tick (1-2 minute gaps, mostly 2013-2017), so the two-bar event ranges use whichever of the two bars exist (NaN only when
both are missing). "Session" for the calendar arithmetic = a day on which the market was open (>= 60 RTH bars, half-days
included); `valid` marks the full sessions that backtest.run.prepare actually trades.

Columns:
  session, dow, rth_bars, valid (full session: >= 80% of the typical RTH bar count), cal_session (market open: >= 60 RTH
  bars; the set the calendar arithmetic runs on), early_close (last RTH bar before 15:30)
  r0830, rel0830, macro0830 (known 08:32) | r1400, rel1400, macro1400 (known 14:02; afternoon use only)
  fomc, fomc_stmt_tod (minutes), press_conference, fomc_minus1, macro_day (= macro0830 | fomc), fomc_minutes (= macro1400 & ~fomc)
  opex, witching, opex_week, totm, totm_pos, payday, holiday_next, santa
"""
import datetime as _dt
import numpy as np
import pandas as pd
from backtest.data import hm
from strategies.common import session_info

# second (statement) day of every scheduled FOMC meeting. 2021-2026 verified on federalreserve.gov/monetarypolicy/fomccalendars.htm,
# 2013-2020 on the fomchistoricalYYYY.htm pages (2026-10-04). March 2020: the scheduled 03-18 meeting was replaced by the
# 03-03 / 03-15 emergency actions -> excluded (7 dates). 2025-08-22 was a notation vote, not a meeting -> excluded.
_FOMC = {
    2010: ['01-27', '03-16', '04-28', '06-23', '08-10', '09-21', '11-03', '12-14'],
    2011: ['01-26', '03-15', '04-27', '06-22', '08-09', '09-21', '11-02', '12-13'],
    2012: ['01-25', '03-13', '04-25', '06-20', '08-01', '09-13', '10-24', '12-12'],
    2013: ['01-30', '03-20', '05-01', '06-19', '07-31', '09-18', '10-30', '12-18'],
    2014: ['01-29', '03-19', '04-30', '06-18', '07-30', '09-17', '10-29', '12-17'],
    2015: ['01-28', '03-18', '04-29', '06-17', '07-29', '09-17', '10-28', '12-16'],
    2016: ['01-27', '03-16', '04-27', '06-15', '07-27', '09-21', '11-02', '12-14'],
    2017: ['02-01', '03-15', '05-03', '06-14', '07-26', '09-20', '11-01', '12-13'],
    2018: ['01-31', '03-21', '05-02', '06-13', '08-01', '09-26', '11-08', '12-19'],
    2019: ['01-30', '03-20', '05-01', '06-19', '07-31', '09-18', '10-30', '12-11'],
    2020: ['01-29', '04-29', '06-10', '07-29', '09-16', '11-05', '12-16'],
    2021: ['01-27', '03-17', '04-28', '06-16', '07-28', '09-22', '11-03', '12-15'],
    2022: ['01-26', '03-16', '05-04', '06-15', '07-27', '09-21', '11-02', '12-14'],
    2023: ['02-01', '03-22', '05-03', '06-14', '07-26', '09-20', '11-01', '12-13'],
    2024: ['01-31', '03-20', '05-01', '06-12', '07-31', '09-18', '11-07', '12-18'],
    2025: ['01-29', '03-19', '05-07', '06-18', '07-30', '09-17', '10-29', '12-10'],
    2026: ['01-28', '03-18', '04-29', '06-17', '07-29', '09-16', '10-28', '12-09'],
}
FOMC_STATEMENT_DATES = frozenset(_dt.date(y, int(md[:2]), int(md[3:])) for y, l in _FOMC.items() for md in l)
# statement released at 12:30 on these 2011-2012 press-conference meetings; 14:15 for the other pre-2013 meetings; 14:00 since 2013
_STMT_1230 = frozenset(_dt.date(*map(int, s.split('-'))) for s in
                       ['2011-04-27', '2011-06-22', '2011-11-02', '2012-01-25', '2012-04-25', '2012-06-20', '2012-09-13', '2012-12-12'])
_PC_EXTRA = frozenset([_dt.date(2011, 4, 27), _dt.date(2011, 11, 2)])


def fomc_stmt_tod(date) -> int:
    if date >= _dt.date(2013, 1, 1):
        return hm('14:00')
    return hm('12:30') if date in _STMT_1230 else hm('14:15')


def press_conference(date) -> bool:
    if date not in FOMC_STATEMENT_DATES:
        return False
    if date.year >= 2019:
        return True
    if date.year <= 2010:
        return False
    return date.month in (3, 6, 9, 12) or date in _PC_EXTRA


def nth_weekday(year: int, month: int, weekday: int, n: int) -> _dt.date:
    """n-th `weekday` (0=Mon) of the month."""
    first = _dt.date(year, month, 1)
    off = (weekday - first.weekday()) % 7
    return first + _dt.timedelta(days=off + 7 * (n - 1))


def _two_bar_range(df1: pd.DataFrame, t0: int) -> pd.Series:
    """max(high) - min(low) over the bars with tod in {t0, t0+1}; NaN when both bars are missing (per day_id)."""
    b = df1[(df1['tod'] >= t0) & (df1['tod'] <= t0 + 1)]
    g = b.groupby('day_id')
    return (g['high'].max() - g['low'].min())


def flags(df1: pd.DataFrame, k0830: float = 3.0, k1400: float = 3.0, median_lookback: int = 60,
          rth=('09:30', '16:00')) -> pd.DataFrame:
    info = session_info(df1, rth=rth)
    out = pd.DataFrame(index=info.index)
    out['session'] = info['session']
    out['dow'] = info['dow'].astype(int)
    out['rth_bars'] = info['rth_bars']
    typical = info.loc[info['rth_bars'] > 0, 'rth_bars'].median() if (info['rth_bars'] > 0).any() else 0
    out['valid'] = info['rth_bars'] >= 0.8 * typical                    # full session (what backtest.run trades)
    # calendar session = the market was open (>= 60 RTH bars; half-days included). Feb-Jul 2023 the CFD feed prints only
    # ~180 RTH bars/session, so a 'thin' criterion would wrongly turn that half-year into holidays for the calendar flags.
    out['cal_session'] = info['rth_bars'] >= 60
    out['early_close'] = out['cal_session'] & (info['rth_last_tod'] < hm('15:30'))

    # ---- event detectors (OHLC only). rel = range / rolling median of the PRIOR `median_lookback` sessions.
    mp = max(1, int(round(0.8 * median_lookback)))        # tolerate a few missing-bar sessions in the window
    for name, t0, k in (('0830', hm('08:30'), k0830), ('1400', hm('14:00'), k1400)):
        r = _two_bar_range(df1, t0).reindex(out.index)
        med = r.shift(1).rolling(median_lookback, min_periods=mp).median()
        rel = r / med.replace(0, np.nan)
        out['r' + name] = r
        out['rel' + name] = rel
        out['macro' + name] = (rel >= k).fillna(False).astype(bool)

    # ---- FOMC table
    dates = out['session'].values
    out['fomc'] = np.array([d in FOMC_STATEMENT_DATES for d in dates], dtype=bool)
    out['fomc_stmt_tod'] = np.array([fomc_stmt_tod(d) if d in FOMC_STATEMENT_DATES else -1 for d in dates], dtype=int)
    out['press_conference'] = np.array([press_conference(d) for d in dates], dtype=bool)
    out['macro_day'] = out['macro0830'] | out['fomc']
    out['fomc_minutes'] = out['macro1400'] & ~out['fomc']

    # ---- calendar flags on the set of calendar sessions (market open)
    valid_dates = [d for d, v in zip(dates, out['cal_session'].values) if v]
    early = set(d for d, e in zip(dates, out['early_close'].values) if e)
    vset = set(valid_dates)
    vidx = {d: k for k, d in enumerate(valid_dates)}       # ordinal among valid sessions
    out['fomc_minus1'] = False
    nxt = {valid_dates[k]: valid_dates[k + 1] for k in range(len(valid_dates) - 1)}
    out['fomc_minus1'] = np.array([(nxt.get(d) in FOMC_STATEMENT_DATES) if d in nxt else False for d in dates], dtype=bool)

    # opex: 3rd Friday if it is a full session, else the Thursday before (Good Friday)
    opex_dates = set()
    years = sorted({d.year for d in dates})
    for y in years:
        for m in range(1, 13):
            f = nth_weekday(y, m, 4, 3)
            if f in vset:
                opex_dates.add(f)
            elif (f - _dt.timedelta(days=1)) in vset:
                opex_dates.add(f - _dt.timedelta(days=1))
    out['opex'] = np.array([d in opex_dates for d in dates], dtype=bool)
    out['witching'] = out['opex'] & np.isin([d.month for d in dates], [3, 6, 9, 12])
    week_of_opex = {(d - _dt.timedelta(days=d.weekday())) for d in opex_dates}          # Monday of each opex week
    out['opex_week'] = np.array([(d - _dt.timedelta(days=d.weekday())) in week_of_opex and d not in opex_dates and d.weekday() <= 3
                                 for d in dates], dtype=bool)

    # turn of the month: last full session of a month (T-1) or the first three of a month (T+1..T+3); payday; santa
    by_month = {}
    for d in valid_dates:
        by_month.setdefault((d.year, d.month), []).append(d)
    totm_pos = {}
    payday = set(); santa = set()
    months = sorted(by_month)
    for key in months:
        lst = by_month[key]
        totm_pos[lst[-1]] = -1
        for k, d in enumerate(lst[:3]):
            totm_pos[d] = k + 1
        mid = [d for d in lst if d.day >= 15]
        if mid:
            payday.add(mid[0])
            k = vidx[mid[0]]
            if k + 1 < len(valid_dates):
                payday.add(valid_dates[k + 1])
        if key[1] == 12:
            santa.update(lst[-5:])
        if key[1] == 1:
            santa.update(lst[:2])
    out['totm_pos'] = np.array([totm_pos.get(d, 0) for d in dates], dtype=int)
    out['totm'] = out['totm_pos'] != 0
    out['payday'] = np.array([d in payday for d in dates], dtype=bool)
    out['santa'] = np.array([d in santa for d in dates], dtype=bool)

    def _next_weekday(d):
        n = d + _dt.timedelta(days=1)
        while n.weekday() >= 5:
            n += _dt.timedelta(days=1)
        return n
    last = dates[-1] if len(dates) else None
    # pre-holiday day: the next weekday is closed or a half-day (within the data range)
    out['holiday_next'] = np.array([((_next_weekday(d) not in vset) or (_next_weekday(d) in early)) and (_next_weekday(d) <= last)
                                    for d in dates], dtype=bool)
    return out
