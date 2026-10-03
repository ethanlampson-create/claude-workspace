"""Audit lens: backtest/engine.py fill semantics end to end, per-bar equity arrays, backtest/portfolio.py aggregation,
and the warm-up / window handling in backtest/run.py.

Every test encodes the behaviour a correct simulator SHOULD have. A test named test_BUG_* FAILS on the current code
and demonstrates the reported defect; the other tests pass and pin down behaviour that was audited and found correct
(warm-up isolation, early-close handling, portfolio intraday aggregation).
Conventions: MES-like contract (tick 0.25, $5/pt, $1.30 RT commission, 1 tick slippage per side).
"""
import types
import numpy as np
import pandas as pd
import pytest

from backtest import engine, portfolio
from backtest.engine import Intents
from backtest.contracts import Contract, CONTRACTS
import backtest.run as brun
from backtest.run import prepare, slice_window
import strategies

C = Contract('MES', 'SPXUSD', 5.0, 0.25, 1.30)
SLIP = 0.25; PV = 5.0; COMM = 1.30; THR = 0.25
TZ = 'America/New_York'


def make_df(bars, day_ids=None, tod0=570, tods=None):
    n = len(bars); arr = np.array(bars, dtype=float)
    day_ids = np.zeros(n, np.int32) if day_ids is None else np.asarray(day_ids, np.int32)
    tod = np.array([tod0 + i for i in range(n)], np.int32) if tods is None else np.asarray(tods, np.int32)
    base = pd.Timestamp('2025-03-03 00:00', tz=TZ)
    ts = [base + pd.Timedelta(days=int(d)) + pd.Timedelta(minutes=int(t)) for d, t in zip(day_ids, tod)]
    sess = [(base + pd.Timedelta(days=int(d))).date() for d in day_ids]
    return pd.DataFrame({'ts': ts, 'open': arr[:, 0], 'high': arr[:, 1], 'low': arr[:, 2], 'close': arr[:, 3],
                         'tod': tod, 'day_id': day_ids, 'session': sess})


def run(it, **kw):
    return engine.run(it, C, **kw)


def bar_of(df, ts):
    t = pd.Timestamp(ts); t = t.tz_localize('UTC') if t.tzinfo is None else t
    return int(np.where(df['ts'].dt.tz_convert('UTC') == t)[0][0])


# --------------------------------------------------------------------------------------------------------------
# HIGH (optimistic): limit entry whose bar OPENS AT the limit price is treated as an open fill
# --------------------------------------------------------------------------------------------------------------

def test_BUG_limit_entry_open_at_limit_credits_target_reached_before_the_trade_through():
    """Buy limit at 100.00 live from bar 1. Bar 1 opens AT 100.00, rallies to 104.5 (through the 104 target), then
    falls to 99.5 (the first trade-through of the limit) and closes 99.6. The engine sets fill_at_open = (o <= ppx)
    => True, so it treats the whole bar as held after the fill and books a +4 pt TARGET exit on the entry bar.
    In reality the limit can only fill when price trades through 99.75, which is AFTER the high: the trader is long
    at 100 into the 99.6 close (and is flattened at 99.35 next bar in this frame). The engine's own rule for intrabar
    limit fills ("the bar's favourable extreme may predate the fill, so only the stop is checked") is bypassed
    whenever the open sits within one tick of the limit, which for twap_revert (limit at the previous bar's close)
    is the common case. Same for a sell limit with o >= ppx."""
    df = make_df([(100, 100.5, 99.5, 100), (100, 104.5, 99.5, 99.6), (99.6, 100, 99, 99.5)])
    it = Intents(df); it.place([1], 1, entry_px=100.0, kind='limit', valid_bars=5, stop_px=90.0, tgt_px=104.0)
    it.force_flat[2] = True; it.allow_entry[2] = False
    tr, d = run(it)
    assert len(tr) == 1 and tr.entry_px[0] == pytest.approx(100.0)
    assert tr.reason[0] != 'target', f"target credited on the entry bar: exit {tr.exit_px[0]} pnl {tr.pnl[0]}"
    assert tr.pnl[0] < 0


def test_BUG_limit_entry_open_at_limit_short_side():
    df = make_df([(100, 100.5, 99.5, 100), (100, 100.5, 95.5, 100.4), (100.4, 101, 100, 100.5)])
    it = Intents(df); it.place([1], -1, entry_px=100.0, kind='limit', valid_bars=5, stop_px=110.0, tgt_px=96.0)
    it.force_flat[2] = True; it.allow_entry[2] = False
    tr, d = run(it)
    assert tr.reason[0] != 'target' and tr.pnl[0] < 0


# --------------------------------------------------------------------------------------------------------------
# HIGH (optimistic): portfolio.run_leg scales a MINI leg's commission down with the price P&L
# --------------------------------------------------------------------------------------------------------------

def test_BUG_portfolio_mini_leg_commission_is_divided_by_micro_ratio(monkeypatch):
    """run_leg converts an ES leg to micros with scale = micros / micro_ratio applied to pnl, which also divides the
    $4.20 mini round-trip commission to $0.42 per micro instead of charging the real $1.30 per micro. run.micro_daily
    was fixed for exactly this; run_leg was not: every ES/NQ/GC/CL leg in a portfolio is $0.88 per micro per round
    trip too generous (10 micros: $8.80 per trade) before the Lucid Monte Carlo."""
    df = make_df([(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100.25), (101, 101.5, 100.5, 101), (101, 101.5, 100.5, 101)])

    def fake_prepare(strategy_id, contract_name, start, end, params=None, df1=None):
        c = CONTRACTS[contract_name]; it = Intents(df); it.place([1], 1); it.force_flat[2] = True; it.allow_entry[2] = False
        return df, it, c
    monkeypatch.setattr(brun, 'prepare', fake_prepare)
    tr_es, d_es, b_es = portfolio.run_leg({'strategy': 'x', 'contract': 'ES', 'micros': 10}, '2025-03-03', '2025-03-03')
    tr_mes, d_mes, b_mes = portfolio.run_leg({'strategy': 'x', 'contract': 'MES', 'micros': 10}, '2025-03-03', '2025-03-03')
    assert d_mes.pnl[0] == pytest.approx(10 * ((101 - SLIP - 100 - SLIP) * PV - COMM))
    assert d_es.pnl[0] == pytest.approx(d_mes.pnl[0]), f"ES leg as 10 micros {d_es.pnl[0]} vs MES x10 {d_mes.pnl[0]}"
    assert b_es['eq_low'].min() == pytest.approx(b_mes['eq_low'].min())


# --------------------------------------------------------------------------------------------------------------
# MEDIUM: trade-table capacity is n//2+2 but one trade per bar is possible -> out-of-bounds writes (numba, no
# bounds check): silently truncated trades table / corrupted memory; with n=40 the same frame hangs the process.
# --------------------------------------------------------------------------------------------------------------

def test_BUG_trade_table_capacity_overflow_silently_drops_trades():
    """Entry at every bar with a 0.5 pt stop that is hit on the same bar: 12 bars -> 12 round trips. _simulate
    allocates room for 12//2+2 = 8 trades and keeps writing past the end. The daily table counts 12 trades and
    -60.6 of P&L, the trades table returns 8 (metrics.net = -40.4 from trades vs -60.6 from daily). Kept at n=12
    because n=40 makes the process hang (memory corruption), which would stall the suite."""
    n = 12
    df = make_df([(100, 100.5, 99.0, 100)] * n)
    it = Intents(df); it.place(np.arange(n), 1, stop_pts=0.5)
    tr, d = run(it)
    assert int(d.trades[0]) == len(tr), f"daily counts {int(d.trades[0])} trades, trades table has {len(tr)}"
    assert tr.pnl.sum() == pytest.approx(d.pnl[0])


# --------------------------------------------------------------------------------------------------------------
# MEDIUM (pessimistic): stop-entry filled intrabar charges the bar's PRE-fill adverse excursion to min_eq / MAE
# --------------------------------------------------------------------------------------------------------------

def test_BUG_stop_entry_intrabar_fill_charges_prefill_dip_to_min_eq():
    """Buy stop at 101 on bar 1 (open 100). The bar dips to 95 BEFORE it can trigger the stop (price must pass 101
    to fill; the stop at 90 is never touched) and closes 101.4. The position never held the 95 print, yet min_eq is
    -32.55 (6.25 pts below the fill) instead of the -1.55 actually experienced (bar 2 low 101.2). On ORB MES
    2025-01..2026-09 this applies to 431 of 437 trades (mean 3.5 pts = $17.6/micro, max 23.25 pts = $116/micro, i.e.
    $2,325 at 20 micros: a phantom full-MLL breach from a single entry bar); it is the reported MAE of 51 trades.
    Where the low is also below the protective stop the engine's documented 'stop first' policy applies and the
    stop exit is the (conservative) answer; here no stop is touched, so the charge is pure overstatement."""
    df = make_df([(100, 100.5, 99.5, 100), (100, 101.5, 95, 101.4), (101.4, 101.6, 101.2, 101.5)])
    it = Intents(df); it.place([1], 1, entry_px=101.0, valid_bars=5, stop_px=90.0)
    it.force_flat[2] = True; it.allow_entry[2] = False
    tr, d = run(it)
    ep = 101.25
    assert tr.reason[0] == 'flat'
    # the only adverse excursion actually held is the forced-flat exit itself at bar 2's open (101.4 - slip = 101.15)
    assert tr.mae_pts[0] == pytest.approx(101.15 - ep), f"mae {tr.mae_pts[0]} includes the pre-fill low"
    assert d.min_eq[0] == pytest.approx((101.15 - ep) * PV - COMM) and d.min_eq[0] <= d.pnl[0] + 1e-9, f"min_eq {d.min_eq[0]}"


# --------------------------------------------------------------------------------------------------------------
# LOW: a market entry does not cancel a resting pending order; the stale order fills after the market trade exits
# --------------------------------------------------------------------------------------------------------------

def test_BUG_market_entry_leaves_stale_pending_order_that_fills_later():
    """Bar 1: buy stop at 105 valid 10 bars. Bar 2: market buy (stop 97) fills; bar 3 stops it out. Bar 4 trades
    through 105 and the pending order from bar 1 -- never cancelled by the market entry (a new STOP signal does
    replace it, a MARKET signal does not) -- opens a second, unintended trade. 'One pending order at a time' should
    mean the newest order supersedes."""
    df = make_df([(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100), (100, 100.5, 95, 100),
                  (100, 106, 99.5, 105), (105, 105.5, 104.5, 105)])
    it = Intents(df); it.place([1], 1, entry_px=105.0, valid_bars=10); it.place([2], 1, stop_px=97.0)
    tr, d = run(it)
    assert [bar_of(df, t) for t in tr.entry_ts] == [2], f"entries at bars {[bar_of(df, t) for t in tr.entry_ts]}"


# --------------------------------------------------------------------------------------------------------------
# LOW: slice_window keeps a session's P&L in `daily` but drops its evening trades from `trades`
# --------------------------------------------------------------------------------------------------------------

def test_BUG_slice_window_filters_trades_by_calendar_date_not_session():
    """The first session of the window (Mon 2025-03-03) starts Sun 18:00 ET. A trade entered Sun 18:05 belongs to
    that session (daily keeps its P&L) but slice_window filters trades by entry_ts.date() >= start and drops it, so
    metrics.net (from trades) and the Lucid input (from daily) disagree for any overnight strategy."""
    trades = pd.DataFrame({'entry_ts': [pd.Timestamp('2025-03-02 18:05', tz=TZ), pd.Timestamp('2025-03-03 09:35', tz=TZ)],
                           'pnl': [10.0, 5.0], 'day_id': [1, 1]})
    daily = pd.DataFrame({'session': [pd.Timestamp('2025-02-28').date(), pd.Timestamp('2025-03-03').date()],
                          'pnl': [0.0, 15.0], 'min_eq': [0.0, 0.0], 'max_eq': [0.0, 15.0], 'trades': [0, 2]})
    t2, d2 = slice_window(trades, daily, '2025-03-03')
    assert d2.pnl.sum() == pytest.approx(15.0)
    assert t2.pnl.sum() == pytest.approx(d2.pnl.sum()), f"trades net {t2.pnl.sum()} vs daily net {d2.pnl.sum()}"


# --------------------------------------------------------------------------------------------------------------
# LOW: trailing stop that was certainly hit inside the bar (close below the new trail level) is deferred to the
# next bar's open (pessimistic by the open gap in most cases; optimistic only if the next bar gaps back above it)
# --------------------------------------------------------------------------------------------------------------

def test_BUG_trailing_stop_hit_within_the_ratchet_bar_is_deferred_to_next_open():
    """trail 2 pts, active immediately. Bar 1 (entry 100.25) runs to 106 then closes 103: the trail level 104 was
    unambiguously traded through after the high (the close is after the high). Bar 2 gaps up to 105 and never
    comes back: the engine keeps the position and later closes it flat at 104.75 (+4.5) where a real trailing
    stop had filled at 103.75 (+3.5). 0.18% of consecutive SPXUSD 1-minute bars gap >= 1 pt, so the usual effect is
    the opposite (exit at the next open, below the trail level)."""
    df = make_df([(100, 100.5, 99.5, 100), (100, 106, 99.9, 103), (105, 105.5, 104.5, 105), (105, 105.5, 104.5, 105)])
    it = Intents(df); it.place([1], 1, stop_px=97.0, trail_pts=2.0, trail_act_pts=0.0)
    it.force_flat[3] = True; it.allow_entry[3] = False
    tr, d = run(it)
    assert tr.reason[0] == 'trail' and tr.exit_px[0] == pytest.approx(104.0 - SLIP), f"got {tr.reason[0]} at {tr.exit_px[0]}"


# --------------------------------------------------------------------------------------------------------------
# Audited and found correct (these pass): warm-up isolation, early close, per-bar equity, portfolio aggregation
# --------------------------------------------------------------------------------------------------------------

def _fake_strategy(monkeypatch, gen):
    mod = types.SimpleNamespace(generate=gen)
    monkeypatch.setattr(strategies, 'load', lambda sid: mod)


def test_warmup_pending_order_and_position_cannot_leak_into_the_window(monkeypatch):
    """prepare() masks allow_entry before `start`; the engine cancels a pending order on any bar where entries are
    not allowed and never holds a position across a session boundary, so neither a pending stop placed on the last
    warm-up bar (valid for 10 bars) nor a market entry on a warm-up bar reaches the first window session."""
    df = make_df([(100, 100.5, 99.5, 100)] * 4 + [(100, 106, 99.5, 105), (105, 105.5, 104.5, 105), (105, 105.5, 104.5, 105)],
                 day_ids=[0, 0, 0, 0, 1, 1, 1])

    def gen(df1, contract, params):
        it = Intents(df1); it.place([1], 1); it.place([3], 1, entry_px=104.0, valid_bars=10); return it
    _fake_strategy(monkeypatch, gen)
    df1, it, c = prepare('fake', 'MES', '2025-03-04', '2025-03-04', {}, df1=df)
    assert not it.allow_entry[:4].any() and it.allow_entry[4:].all()
    tr, d = engine.run(it, c)
    tr, d = slice_window(tr, d, '2025-03-04')
    assert len(tr) == 0 and len(d) == 1 and d.trades[0] == 0 and d.pnl[0] == 0.0


def test_warmup_days_are_excluded_from_daily_and_metrics(monkeypatch):
    df = make_df([(100, 100.5, 99.5, 100)] * 3 + [(100, 100.5, 99.5, 100)] * 3, day_ids=[0, 0, 0, 1, 1, 1])

    def gen(df1, contract, params):
        it = Intents(df1); it.place([1, 4], 1); it.force_flat[[2, 5]] = True; it.allow_entry[[2, 5]] = False; return it
    _fake_strategy(monkeypatch, gen)
    tr, d, m = brun.run_strategy('fake', 'MES', '2025-03-04', '2025-03-04', {}, df1=df)
    assert m['days'] == 1 and m['trades'] == 1 and list(d.session) == [pd.Timestamp('2025-03-04').date()]


def test_early_close_session_is_flattened_at_its_last_bar_with_consistent_equity():
    """Holiday session ending 12:58 (no bar reaches flat_time 15:55): the position is closed at the 12:58 close with
    slippage (session_end), the next session's 18:00 gap is not seen, and min_eq <= pnl on that day. On SPXUSD
    2025-01..2026-09, 17 sessions end at 12:58/13:13 (NYSE holidays with a 13:00/13:15 ET futures halt)."""
    df = make_df([(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100.2), (100.2, 100.6, 99.8, 100.4), (90, 91, 89, 90), (90, 90.5, 89.5, 90)],
                 day_ids=[0, 0, 0, 1, 1], tods=[776, 777, 778, 1080, 1081])
    it = Intents(df); it.set_session('09:30', '15:00', '15:55'); it.place([1], 1, stop_px=95.0)
    tr, d = run(it)
    assert len(tr) == 1 and tr.reason[0] == 'session_end' and bar_of(df, tr.exit_ts[0]) == 2
    assert tr.exit_px[0] == pytest.approx(100.4 - SLIP) and tr.day_id[0] == 0
    assert d.min_eq[0] <= d.pnl[0] + 1e-9 and d.min_eq[1] == 0.0 and d.pnl[1] == 0.0


def test_per_bar_equity_arrays_track_realized_plus_unrealized_and_exit_bar():
    df = make_df([(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100), (100, 101, 98, 100.5), (100.5, 102.5, 100, 102), (102, 102.5, 101.5, 102)])
    it = Intents(df); it.place([1], 1, stop_px=90.0, tgt_px=102.0)
    tr, d, bars = run(it, return_bars=True)
    ep = 100.25
    assert bars.eq_low[0] == 0.0 and bars.eq_close[0] == 0.0
    assert bars.eq_low[1] == pytest.approx((99.5 - ep) * PV - COMM) and bars.eq_close[1] == pytest.approx((100 - ep) * PV - COMM)
    assert bars.eq_low[2] == pytest.approx((98 - ep) * PV - COMM)
    # bar 3: target 102 filled at 102 (high 102.5 >= 102 + thr); low 100 charged (stop-first policy), close = realized
    pnl = (102 - ep) * PV - COMM
    assert tr.reason[0] == 'target' and bars.eq_low[3] == pytest.approx((100 - ep) * PV - COMM) and bars.eq_close[3] == pytest.approx(pnl)
    assert bars.eq_low[4] == pytest.approx(pnl) and bars.eq_close[4] == pytest.approx(pnl)
    assert d.min_eq[0] == pytest.approx((98 - ep) * PV - COMM) and d.pnl[0] == pytest.approx(pnl)


def test_portfolio_combine_takes_true_intraday_minimum_of_the_sum(monkeypatch):
    """Two legs whose drawdowns occur at different minutes: the combined min_eq is the min over minutes of the sum
    (-100 here), not the sum of the legs' minima (-200); when they coincide it is -200."""
    sess = pd.Timestamp('2025-03-03').date()
    t = [pd.Timestamp('2025-03-03 09:30', tz=TZ) + pd.Timedelta(minutes=k) for k in range(4)]

    def leg(lows, closes):
        bars = pd.DataFrame({'ts': t, 'day_id': [0] * 4, 'eq_low': lows, 'eq_close': closes})
        daily = pd.DataFrame({'session': [sess], 'pnl': [closes[-1]], 'min_eq': [min(lows)], 'max_eq': [max(closes)], 'trades': [1]})
        trades = pd.DataFrame({'entry_ts': [t[0]], 'pnl': [closes[-1]], 'leg': ['x']})
        return trades, daily, bars
    legs = {'A': leg([-100, 0, 0, 20], [-10, 0, 10, 20]), 'B': leg([0, -100, 0, 30], [0, 0, 10, 30])}
    monkeypatch.setattr(portfolio, 'run_leg', lambda lg, s, e, slip=None: legs[lg['strategy']])
    tr, d = portfolio.combine([{'strategy': 'A'}, {'strategy': 'B'}], '2025-03-03', '2025-03-03')
    assert d.min_eq[0] == pytest.approx(-100.0) and d.pnl[0] == pytest.approx(50.0) and d.trades[0] == 2 and d.max_eq[0] == pytest.approx(50.0)
    legs['B'] = leg([-100, 0, 0, 30], [0, 0, 10, 30])
    tr, d = portfolio.combine([{'strategy': 'A'}, {'strategy': 'B'}], '2025-03-03', '2025-03-03')
    assert d.min_eq[0] == pytest.approx(-200.0)


def test_same_bar_entry_exit_force_flat_and_daily_stops_on_entry_bar():
    """A market entry on a force_flat bar is closed at that bar's close (reason flat); a same-bar stop-out trips the
    daily loss stop so no further entries happen that day."""
    df = make_df([(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 99.6), (100, 100.5, 95, 100), (100, 100.5, 99.5, 100)])
    it = Intents(df); it.place([1], 1); it.force_flat[1] = True
    tr, d = run(it)
    assert tr.reason[0] == 'flat' and tr.exit_px[0] == pytest.approx(99.6 - SLIP) and int(tr.bars[0]) == 0
    it = Intents(df); it.place([2, 3], 1, stop_px=97.0); it.daily_loss_stop = 10.0
    tr, d = run(it)
    assert len(tr) == 1 and tr.reason[0] == 'stop' and d.min_eq[0] == pytest.approx(d.pnl[0])
