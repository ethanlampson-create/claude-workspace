"""Adversarial tests for backtest/data.py, strategies/common.py, strategies/orb.py and backtest/run.py.

Each test encodes the behaviour a correct data layer / strategy SHOULD have. A failing test on the current code
demonstrates the suspected bug; a passing test means the suspicion was wrong (or pins down documented semantics).

Synthetic frames carry the same columns as backtest.data.load_1m output: ts (tz-aware America/New_York), open,
high, low, close, tod, day_id, session. Real-parquet tests are skipped when data/parquet/SPXUSD_1m.parquet is absent.
"""
import os
import numpy as np
import pandas as pd
import pytest

from backtest import data
from backtest.data import load_1m, resample, daily_bars, hm, PQ
from backtest.contracts import CONTRACTS, Contract
from backtest import engine
from backtest.engine import Intents
from backtest.run import micro_daily
from strategies.common import atr, daily_atr, opening_range, overnight_range, session_vwap
import strategies.orb as orb

TZ = 'America/New_York'
SPX_PQ = os.path.join(PQ, 'SPXUSD_1m.parquet')
needs_parquet = pytest.mark.skipif(not os.path.exists(SPX_PQ), reason='real SPXUSD parquet not present')


# --------------------------------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------------------------------

def label(df):
    """Apply the SAME session/tod/day_id convention as load_1m to a raw ts/ohlc frame, by running load_1m itself
    (via a fake parquet reader) so the production code path is what gets tested."""
    raise NotImplementedError  # tests use the `synthetic_loader` fixture instead


@pytest.fixture
def synthetic_loader(monkeypatch):
    """Returns a function raw_df -> load_1m(...) output, routed through the real load_1m code (fake read_parquet)."""
    def run(raw, start=None, end=None):
        data._cache.pop('SYNTH', None)
        monkeypatch.setattr(data.pd, 'read_parquet', lambda path: raw.copy())
        try:
            return load_1m('SYNTH', start, end)
        finally:
            data._cache.pop('SYNTH', None)
    return run


def raw_bars(rows):
    """rows: list of ('YYYY-MM-DD HH:MM', o, h, l, c) -> raw frame like the parquet (ts tz-aware, ohlc)."""
    ts = [pd.Timestamp(r[0], tz=TZ) for r in rows]
    arr = np.array([r[1:] for r in rows], dtype=float)
    return pd.DataFrame({'ts': ts, 'open': arr[:, 0], 'high': arr[:, 1], 'low': arr[:, 2], 'close': arr[:, 3]})


def labelled(rows):
    """Synthetic frame with the load_1m columns, labelling sessions by the documented convention
    (session = date of (wall-clock ts - 18h) + 1 day; weekend sessions excluded)."""
    raw = raw_bars(rows)
    wall = raw['ts'].dt.tz_localize(None)
    sess = (wall - pd.Timedelta(hours=18)).dt.normalize() + pd.Timedelta(days=1)
    raw['session'] = sess.dt.date
    raw['tod'] = (raw['ts'].dt.hour * 60 + raw['ts'].dt.minute).astype(np.int32)
    raw = raw[sess.dt.dayofweek < 5].reset_index(drop=True)
    raw['day_id'] = pd.factorize(raw['session'])[0].astype(np.int32)
    return raw


def tods(df, *hhmm):
    return [int(df.loc[df['tod'] == hm(t)].index[0]) for t in hhmm]


# --------------------------------------------------------------------------------------------------------------
# load_1m: session labelling
# --------------------------------------------------------------------------------------------------------------

def test_session_labels_basic_week(synthetic_loader):
    df = synthetic_loader(raw_bars([
        ('2025-06-01 18:00', 1, 1, 1, 1),   # Sunday evening -> Monday session
        ('2025-06-02 09:30', 1, 1, 1, 1),   # Monday RTH
        ('2025-06-02 16:59', 1, 1, 1, 1),
        ('2025-06-02 17:30', 1, 1, 1, 1),   # between 17:00 and 18:00 -> still Monday by the (ts-18h)+1 rule
        ('2025-06-02 18:00', 1, 1, 1, 1),   # -> Tuesday
        ('2025-06-06 16:14', 1, 1, 1, 1),   # Friday close
        ('2025-06-06 17:00', 1, 1, 1, 1),   # 17:00 - 18h = Thu 23:00 -> still Friday (session really ends 17:59)
        ('2025-06-06 18:00', 1, 1, 1, 1),   # -> Saturday label -> dropped
    ]))
    got = [(str(t)[:16], str(s)) for t, s in zip(df['ts'], df['session'])]
    assert got == [('2025-06-01 18:00', '2025-06-02'), ('2025-06-02 09:30', '2025-06-02'), ('2025-06-02 16:59', '2025-06-02'),
                   ('2025-06-02 17:30', '2025-06-02'), ('2025-06-02 18:00', '2025-06-03'), ('2025-06-06 16:14', '2025-06-06'),
                   ('2025-06-06 17:00', '2025-06-06')]
    assert list(df['tod']) == [1080, 570, 1019, 1050, 1080, 974, 1020]
    assert list(df['day_id']) == [0, 0, 0, 0, 1, 2, 2]


def test_dst_start_sunday_evening_bars_belong_to_monday_session(synthetic_loader):
    """BUG (low): `ts - 18h` on tz-aware stamps is absolute time, so on the US DST-start Sunday 18:00 EDT - 18h
    lands on Saturday 23:00 EST; the 18:00-18:59 bars get a Sunday label and are DROPPED from the Monday session.
    The shift must be done on wall-clock time."""
    df = synthetic_loader(raw_bars([
        ('2025-03-09 18:00', 1, 1, 1, 1), ('2025-03-09 18:30', 1, 1, 1, 1), ('2025-03-09 19:00', 1, 1, 1, 1),
        ('2025-03-10 09:30', 1, 1, 1, 1),
    ]))
    assert len(df) == 4, 'DST-start Sunday 18:00-18:59 bars were dropped'
    assert set(str(s) for s in df['session']) == {'2025-03-10'}


def test_date_filter_keeps_sunday_evening_and_reindexes_day_id(synthetic_loader):
    df = synthetic_loader(raw_bars([
        ('2025-05-30 09:30', 1, 1, 1, 1), ('2025-06-01 18:00', 1, 1, 1, 1), ('2025-06-02 09:30', 1, 1, 1, 1),
        ('2025-06-03 09:30', 1, 1, 1, 1),
    ]), start='2025-06-01', end='2025-06-02')
    assert [str(t)[:16] for t in df['ts']] == ['2025-06-01 18:00', '2025-06-02 09:30']
    assert list(df['day_id']) == [0, 0] and list(df.index) == [0, 1]


# --------------------------------------------------------------------------------------------------------------
# resample / daily_bars
# --------------------------------------------------------------------------------------------------------------

def test_resample_bucket_math_no_session_crossing_and_i_next():
    rows = []
    # session A (Mon): 18:00..18:05 Sunday evening, then 09:30..09:35 Monday
    for m in range(6):
        rows.append((f'2025-06-01 18:{m:02d}', 100 + m, 101 + m, 99 + m, 100.5 + m))
    for m in range(6):
        rows.append((f'2025-06-02 09:{30 + m:02d}', 200 + m, 201 + m, 199 + m, 200.5 + m))
    # session B (Tue): first bar 18:00 Monday
    rows.append(('2025-06-02 18:00', 300, 301, 299, 300.5))
    df = labelled(rows)
    out = resample(df, 5)
    assert list(out['tod']) == [1080, 1085, 570, 575, 1080]
    assert list(out['day_id']) == [0, 0, 0, 0, 1]
    assert list(out['i_first']) == [0, 5, 6, 11, 12] and list(out['i_last']) == [4, 5, 10, 11, 12]
    # OHLC aggregation of the first bucket
    assert out.loc[0, 'open'] == 100 and out.loc[0, 'high'] == 105 and out.loc[0, 'low'] == 99 and out.loc[0, 'close'] == 104.5
    # i_next = first 1-min bar after the bar closes within the same session; -1 for the session's last bar
    assert list(out['i_next']) == [5, 6, 11, -1, -1]
    # no bucket spans the 18:00 session boundary
    assert (df['day_id'].values[out['i_first']] == df['day_id'].values[out['i_last']]).all()
    assert out['ts'].is_monotonic_increasing


def test_resample_rth_only_i_next_is_next_bar_in_session_even_if_outside_rth():
    rows = [('2025-06-02 09:29', 1, 1, 1, 1)] + [(f'2025-06-02 15:{55 + m:02d}', 1, 1, 1, 1) for m in range(5)] \
        + [('2025-06-02 16:00', 1, 1, 1, 1)]
    df = labelled(rows)
    out = resample(df, 5, rth_only=True)
    assert len(out) == 1 and out.loc[0, 'tod'] == 955 and out.loc[0, 'i_first'] == 1 and out.loc[0, 'i_last'] == 5
    assert out.loc[0, 'i_next'] == 6  # the 16:00 bar (documented: within session, not within RTH)


def test_daily_bars_rth_only_and_daily_atr_has_no_lookahead():
    rows = []
    d0 = pd.Timestamp('2025-06-02')
    highs = [101, 103, 102, 110]
    for k in range(4):
        day = (d0 + pd.offsets.BDay(k)).strftime('%Y-%m-%d')
        rows.append((f'{day} 09:00', 50, 500, 1, 50))             # pre-market junk must not enter RTH bars
        rows.append((f'{day} 09:30', 100, highs[k], 99, 100))
        rows.append((f'{day} 15:59', 100, 100.5, 99.5, 100))
    df = labelled(rows)
    db = daily_bars(df, rth_only=True)
    assert list(db['high']) == highs and list(db['low']) == [99] * 4
    a = daily_atr(df, n=2, rth_only=True)
    # value at day 3 must not depend on day 3's bars
    expected = atr(db.iloc[:3], 2).iloc[-1]
    assert a.loc[3] == pytest.approx(expected)
    assert np.isnan(a.loc[0])


# --------------------------------------------------------------------------------------------------------------
# opening_range / overnight_range / session_vwap
# --------------------------------------------------------------------------------------------------------------

def test_opening_range_window_half_open_and_i_end():
    rows = [('2025-06-01 18:00', 90, 95, 85, 90), ('2025-06-02 09:29', 1, 300, 0, 1),
            ('2025-06-02 09:30', 100, 101, 99, 100), ('2025-06-02 09:44', 100, 102, 98.5, 100),
            ('2025-06-02 09:45', 100, 150, 50, 100)]
    df = labelled(rows)
    o = opening_range(df, '09:30', 15)
    assert o.loc[0, 'or_high'] == 102 and o.loc[0, 'or_low'] == 98.5 and o.loc[0, 'i_end'] == 3 and o.loc[0, 'n_bars'] == 2


def test_overnight_range_excludes_rth_and_17h_bars():
    rows = [('2025-06-02 17:30', 70, 75, 65, 70),   # belongs to Monday session (tail) -> not Tuesday overnight
            ('2025-06-02 18:00', 90, 95, 85, 90), ('2025-06-03 03:00', 91, 96, 86, 91), ('2025-06-03 09:29', 92, 93, 88, 92),
            ('2025-06-03 09:30', 100, 200, 10, 100)]
    df = labelled(rows)
    on = overnight_range(df, '09:30')
    assert on.loc[1, 'on_high'] == 96 and on.loc[1, 'on_low'] == 85 and on.loc[1, 'on_open'] == 90 and on.loc[1, 'on_close'] == 92


def test_session_vwap_anchor_excludes_prior_evening_bars():
    """BUG (medium): the anchored key is `tod >= anchor_tod`, but the session starts at 18:00, so the 18:00-23:59
    bars of the previous evening (tod 1080+) satisfy the condition and are cumulated INTO the post-anchor group.
    An 09:30-anchored VWAP therefore starts the RTH already loaded with six hours of overnight prices."""
    rows = [('2025-06-01 18:00', 110, 110, 110, 110), ('2025-06-01 18:01', 110, 110, 110, 110),
            ('2025-06-02 09:30', 100, 100, 100, 100), ('2025-06-02 09:31', 102, 102, 102, 102)]
    df = labelled(rows)
    v = session_vwap(df, anchor_tod=hm('09:30'))
    assert v.iloc[2] == pytest.approx(100.0)
    assert v.iloc[3] == pytest.approx(101.0)


# --------------------------------------------------------------------------------------------------------------
# Intents.set_session masks
# --------------------------------------------------------------------------------------------------------------

def test_set_session_overnight_entry_window_and_flat_mask():
    rows = [('2025-06-02 19:00', 1, 1, 1, 1), ('2025-06-02 20:00', 1, 1, 1, 1), ('2025-06-02 23:00', 1, 1, 1, 1),
            ('2025-06-03 01:00', 1, 1, 1, 1), ('2025-06-03 02:00', 1, 1, 1, 1), ('2025-06-03 04:59', 1, 1, 1, 1),
            ('2025-06-03 05:00', 1, 1, 1, 1), ('2025-06-03 12:00', 1, 1, 1, 1), ('2025-06-03 17:00', 1, 1, 1, 1)]
    df = labelled(rows)
    it = Intents(df); it.set_session('20:00', '02:00', '05:00')
    assert list(it.allow_entry) == [False, True, True, True, False, False, False, False, False]
    assert list(it.force_flat) == [False, False, False, False, False, False, True, True, True]


def test_force_flat_covers_every_bar_until_the_session_ends():
    """BUG (low): set_session says 'session bars after 17:00 belong to next day', but load_1m labels 17:01-17:59
    bars as the SAME session (17:30 - 18h = 23:30 previous day). The flat mask stops at 17:00, so a position still
    open on such a bar is not flattened by the mask; the engine only closes it at the session boundary. Bars in
    17:01-17:59 exist in the data (about 28 per minute-of-day in the 2025-2026 window)."""
    rows = [('2025-06-02 15:55', 1, 1, 1, 1), ('2025-06-02 17:00', 1, 1, 1, 1), ('2025-06-02 17:30', 1, 1, 1, 1),
            ('2025-06-02 18:00', 1, 1, 1, 1)]
    df = labelled(rows)
    assert list(df['day_id']) == [0, 0, 0, 1]
    it = Intents(df); it.set_session('09:30', '11:30', '15:55')
    assert list(it.force_flat) == [True, True, True, False]


# --------------------------------------------------------------------------------------------------------------
# ORB first-touch resolution on synthetic days
# --------------------------------------------------------------------------------------------------------------

MES = CONTRACTS['MES']
ORB_P = {'min_range_atr': 0.0, 'max_range_atr': 10.0, 'max_stop_atr': 10.0}  # neutralise ATR filters


def orb_frame(test_day_bars, n_warm=16):
    """n_warm warm-up sessions with a constant 99-101 opening range (daily ATR -> 2.0), then the test day whose
    opening range is also 99-101 and whose post-range bars are `test_day_bars` [('HH:MM', o, h, l, c), ...]."""
    rows = []
    d0 = pd.Timestamp('2025-05-01')
    days = [(d0 + pd.offsets.BDay(k)).strftime('%Y-%m-%d') for k in range(n_warm + 1)]
    for day in days[:-1]:
        for m in range(15):
            rows.append((f'{day} 09:{30 + m:02d}', 100, 101, 99, 100))
        rows.append((f'{day} 15:55', 100, 100, 100, 100))
    td = days[-1]
    for m in range(15):
        rows.append((f'{td} 09:{30 + m:02d}', 100, 101, 99, 100))
    for t, o, h, l, c in test_day_bars:
        rows.append((f'{td} {t}', o, h, l, c))
    return labelled(rows), td


def test_orb_places_short_when_low_side_touched_first_and_fills_like_engine():
    df, td = orb_frame([('09:45', 100, 100.5, 99.5, 100), ('09:46', 100, 100.5, 98.5, 99),
                        ('09:47', 99, 101.5, 98.9, 101), ('15:55', 101, 101, 101, 101)])
    it = orb.generate(df, MES, ORB_P)
    i45 = tods(df[df['session'] == pd.Timestamp(td).date()], '09:45')[0]
    assert np.flatnonzero(it.sig).tolist() == [i45] and it.sig[i45] == -1   # order live from the bar after the OR
    assert it.entry_px[i45] == pytest.approx(98.75) and it.stop_px[i45] == pytest.approx(101.0)
    assert it.tgt_px[i45] == pytest.approx(98.75 - 2.0 * (101.0 - 98.75))
    tr, daily = engine.run(it, MES)
    assert len(tr) == 1 and tr.side[0] == -1
    assert str(tr.entry_ts[0])[:16] == f'{td} 09:46' and tr.entry_px[0] == pytest.approx(98.75 - 0.25)
    assert str(tr.exit_ts[0])[:16] == f'{td} 09:47' and tr.exit_px[0] == pytest.approx(101.0 + 0.25) and tr.reason[0] == 'stop'
    assert tr.pnl[0] == pytest.approx((98.5 - 101.25) * 5.0 - 1.30)


def test_orb_no_entry_at_or_after_last_entry():
    df, td = orb_frame([('09:45', 100, 100.5, 99.5, 100), ('11:30', 100, 103, 99.5, 102), ('15:55', 102, 102, 102, 102)])
    tr, _ = engine.run(orb.generate(df, MES, ORB_P), MES)
    assert len(tr) == 0
    df, td = orb_frame([('09:45', 100, 100.5, 99.5, 100), ('11:29', 100, 103, 99.5, 102), ('15:55', 102, 102, 102, 102)])
    tr, _ = engine.run(orb.generate(df, MES, ORB_P), MES)
    assert len(tr) == 1 and tr.side[0] == 1 and str(tr.entry_ts[0])[:16] == f'{td} 11:29'


def test_orb_ambiguous_bar_is_not_silently_skipped():
    """SUSPECTED BIAS (low): a 1-minute bar that touches both breakout levels is skipped by orb.py ('conservative').
    In reality one side fills and the bar then trades through the opposite side, which with stop_frac=1 is the
    protective stop: the realistic (and conservative) outcome is a losing trade, not no trade. Dropping these
    whipsaw days is optimistic. (0 occurrences on 2025-01..2026-09 MES with 5- or 15-minute ranges, so the
    effect on the current numbers is nil; the test documents the semantics.)"""
    df, td = orb_frame([('09:45', 100, 101.5, 98.5, 100), ('15:55', 100, 100, 100, 100)])
    tr, _ = engine.run(orb.generate(df, MES, ORB_P), MES)
    assert len(tr) == 1 and tr.pnl[0] < 0


# --------------------------------------------------------------------------------------------------------------
# run.micro_daily
# --------------------------------------------------------------------------------------------------------------

def test_micro_daily_of_a_mini_run_matches_the_micro_contract_run():
    """BUG (medium, optimistic): micro_daily divides a mini's daily P&L by micro_ratio, which also divides the
    mini commission ($4.20 RT -> $0.42 per micro) although a real micro costs $1.30 RT. Every ES/NQ-simulated
    round trip is credited $0.88 per micro too much before the Lucid Monte Carlo."""
    rows = [('2025-06-02 09:30', 100, 100.5, 99.5, 100), ('2025-06-02 09:31', 100, 100.5, 99.5, 100.25),
            ('2025-06-02 09:32', 101, 101.5, 100.5, 101), ('2025-06-02 09:33', 101, 101.5, 100.5, 101)]
    df = labelled(rows)

    def run_with(contract):
        it = Intents(df); it.place([1], 1); it.force_flat[2] = True; it.allow_entry[2] = False
        tr, daily = engine.run(it, contract)
        return tr, daily

    tr_es, d_es = run_with(CONTRACTS['ES'])
    tr_mes, d_mes = run_with(CONTRACTS['MES'])
    conv = micro_daily(d_es, CONTRACTS['ES'])
    assert tr_mes.pnl[0] == pytest.approx((101 - 0.25 - 100 - 0.25) * 5.0 - 1.30)
    assert conv['pnl'].iloc[0] == pytest.approx(d_mes['pnl'].iloc[0])
    assert conv['min_eq'].iloc[0] == pytest.approx(d_mes['min_eq'].iloc[0])


# --------------------------------------------------------------------------------------------------------------
# Real parquet: timezone conversion, session bounds, day_id contiguity, warm-up
# --------------------------------------------------------------------------------------------------------------

def us_eu_dst_mismatch_weeks(year):
    """Trading dates (Mon-Fri) in the weeks where US DST is on but EU DST is off (2nd Sunday March .. last Sunday
    March) and where EU DST is off but US DST is still on (last Sunday October .. 1st Sunday November)."""
    def nth_sunday(month, n):
        d = pd.Timestamp(year=year, month=month, day=1)
        d = d + pd.Timedelta(days=(6 - d.dayofweek) % 7)
        return d + pd.Timedelta(days=7 * (n - 1))
    def last_sunday(month):
        d = pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)
        return d - pd.Timedelta(days=(d.dayofweek + 1) % 7)
    out = set()
    for a, b in [(nth_sunday(3, 2), last_sunday(3)), (last_sunday(10), nth_sunday(11, 1))]:
        for d in pd.date_range(a, b - pd.Timedelta(days=1)):
            if d.dayofweek < 5:
                out.add(d.date())
    return out


@pytest.fixture(scope='module')
def spx():
    return load_1m('SPXUSD', '2025-01-01', '2026-09-30')


@needs_parquet
def test_real_day_id_contiguous_and_sessions_sorted(spx):
    ids = spx['day_id'].values
    assert ids[0] == 0 and (np.diff(ids) >= 0).all() and set(np.diff(ids)) <= {0, 1}
    assert ids[-1] + 1 == spx['session'].nunique()
    assert spx['ts'].is_monotonic_increasing
    # Monday sessions begin with the Sunday 18:00 bar
    first = spx.groupby('day_id').first()
    mondays = first[pd.to_datetime(first['session']).dt.dayofweek == 0]
    assert (mondays['ts'].dt.dayofweek == 6).mean() > 0.9


@needs_parquet
def test_real_0930_is_widest_bar_in_both_seasons_outside_mismatch_weeks(spx):
    d = spx[(spx['tod'] >= 480) & (spx['tod'] <= 1000)].copy()
    d['rng'] = d['high'] - d['low']
    bad = us_eu_dst_mismatch_weeks(2025) | us_eu_dst_mismatch_weeks(2026)
    d = d[~d['session'].isin(bad)]
    edt = d['ts'].dt.tz_convert('UTC').dt.hour != d['ts'].dt.hour + 5
    for name, s in [('EST', d[~edt]), ('EDT', d[edt])]:
        med = s.groupby('tod')['rng'].median()
        assert med[570] > med[510] and med[570] > med[600], f'{name}: 09:30 bar is not the widest'


@needs_parquet
def test_real_sunday_open_is_stamped_1800_every_week():
    """BUG (high): in the weeks where US and EU DST disagree the histdata stamps are one hour BEHIND ET (the
    Sunday Globex open is stamped 17:00, the Friday 16:14 close 15:14, the cash open sits at tod 510).
    2025: Sundays 03-09, 03-16, 03-23 and 10-26; 2026: 03-08, 03-15, 03-22. Read from the RAW parquet because
    load_1m labels those 17:xx Sunday bars as a Sunday session and silently drops them."""
    raw = pd.read_parquet(SPX_PQ, columns=['ts'])
    raw = raw[(raw['ts'] >= pd.Timestamp('2025-01-01', tz=TZ)) & (raw['ts'].dt.dayofweek == 6)]
    first = raw.groupby(raw['ts'].dt.date)['ts'].min()
    off = first[first.dt.hour < 18]
    assert len(off) == 0, f'Sundays whose first bar is stamped before 18:00: {[str(d) for d in off.index]}'


@needs_parquet
def test_real_monday_sessions_start_at_1800_in_loaded_frame(spx):
    """Consequence of the two labelling issues on the loaded frame: the Monday session after the US DST start
    (2025-03-10, 2026-03-09) begins at 19:00 instead of 18:00 (17:xx mis-stamped bars labelled Sunday and dropped,
    18:xx bars dropped by the absolute-time 18h shift)."""
    first = spx.groupby('day_id').first().set_index('session')
    got = {d: int(first.loc[pd.Timestamp(d).date(), 'tod']) for d in ('2025-03-10', '2026-03-09')}
    assert got == {'2025-03-10': 1080, '2026-03-09': 1080}, f'first bar tod of the DST-start Monday sessions: {got}'


@needs_parquet
def test_real_mismatch_weeks_cash_open_is_at_tod_570(spx):
    """Same bug as above, seen from the strategy's point of view: in those weeks the widest bar is tod 510 (the
    real 09:30 ET open) so the ORB opening range is computed on the real 10:30-10:45 and 'flat at 15:55' is really
    16:55 ET (after the cash close; the CFD has no bars there, so positions are carried to the next session)."""
    d = spx[(spx['tod'].isin([510, 570]))].copy()
    d['rng'] = d['high'] - d['low']
    for year in (2025, 2026):
        wk = d[d['session'].isin(us_eu_dst_mismatch_weeks(year))]
        if len(wk) == 0:
            continue
        med = wk.groupby('tod')['rng'].median()
        assert med[570] > med[510], f'{year}: in the US/EU DST mismatch weeks tod 570 is not the cash open'


@needs_parquet
def test_real_orb_trades_from_the_start_of_the_requested_window():
    """Indicators need history before the requested window (daily_atr needs 14 RTH sessions). backtest.run.prepare
    loads a warm-up period before `start`, forbids entries before `start`, and slice_window drops warm-up days, so the
    first requested month is fully represented and no position is carried in from the warm-up."""
    from backtest.run import prepare, slice_window
    df1, it, contract = prepare('orb', 'MES', '2025-01-01', '2025-03-31', {})
    sess = df1['session'].values
    first_sig = sess[np.flatnonzero(it.sig & it.allow_entry)[0]]
    assert first_sig <= pd.Timestamp('2025-01-08').date(), f'first allowed ORB signal only on {first_sig}'
    assert not it.allow_entry[sess < pd.Timestamp('2025-01-01').date()].any()
    tr, d = engine.run(it, contract)
    tr, d = slice_window(tr, d, '2025-01-01')
    assert d['session'].iloc[0] >= pd.Timestamp('2025-01-01').date() and d['session'].iloc[0] <= pd.Timestamp('2025-01-03').date()
    assert pd.to_datetime(tr['entry_ts']).dt.tz_convert('America/New_York').dt.date.min() >= pd.Timestamp('2025-01-01').date()
