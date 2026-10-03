"""Adversarial fill-semantics tests for backtest/engine.py on tiny synthetic 1-minute frames.

Each test encodes the behaviour a correct simulator SHOULD have. A failing test on the current code demonstrates
the suspected bug; a passing test means the suspicion was wrong.
Conventions: MES-like contract (tick 0.25, $5/pt, $1.30 RT commission, 1 tick slippage per side).
"""
import numpy as np
import pandas as pd
import pytest

from backtest import engine
from backtest.engine import Intents
from backtest.contracts import Contract

C = Contract('MES', 'SPXUSD', 5.0, 0.25, 1.30)   # slip_ticks=1 -> 0.25/side
SLIP = 0.25; PV = 5.0; COMM = 1.30; THR = 0.25     # through_ticks=1 default


def make_df(bars, day_ids=None, tod0=570):
    """bars: list of (o, h, l, c). One 1-minute bar per row, tod increasing from tod0 (09:30 by default)."""
    n = len(bars)
    arr = np.array(bars, dtype=float)
    day_ids = np.zeros(n, np.int32) if day_ids is None else np.asarray(day_ids, np.int32)
    tod = np.array([tod0 + i for i in range(n)], np.int32)
    base = pd.Timestamp('2025-03-03 00:00', tz='America/New_York')
    ts = [base + pd.Timedelta(days=int(d)) + pd.Timedelta(minutes=int(t)) for d, t in zip(day_ids, tod)]
    sess = [(base + pd.Timedelta(days=int(d))).date() for d in day_ids]
    return pd.DataFrame({'ts': ts, 'open': arr[:, 0], 'high': arr[:, 1], 'low': arr[:, 2], 'close': arr[:, 3],
                         'tod': tod, 'day_id': day_ids, 'session': sess})


def run(it, **kw):
    return engine.run(it, C, **kw)


def bar_of(df, ts):
    """Index of the 1-minute bar a trades-table timestamp refers to (tz-robust)."""
    t = pd.Timestamp(ts)
    t = t.tz_localize('UTC') if t.tzinfo is None else t
    return int(np.where(df['ts'].dt.tz_convert('UTC') == t)[0][0])


# --------------------------------------------------------------------------------------------------------------
# Baseline sanity (these should pass; they pin down the documented semantics)
# --------------------------------------------------------------------------------------------------------------

def test_market_entry_fills_at_open_plus_slip_and_commission_once():
    df = make_df([(100, 101, 99.5, 100.5), (100.5, 101, 100, 100.75), (100.75, 101, 100.5, 100.9)])
    it = Intents(df); it.place([1], 1); it.force_flat[2] = True; it.allow_entry[2] = False
    tr, d = run(it)
    assert len(tr) == 1
    assert tr.entry_px[0] == pytest.approx(100.5 + SLIP)
    assert tr.exit_px[0] == pytest.approx(100.75 - SLIP)
    assert tr.pnl[0] == pytest.approx((100.75 - SLIP - 100.5 - SLIP) * PV - COMM)
    assert tr.reason[0] == 'flat'


def test_short_sign_conventions():
    # short market entry at open - slip; stop_pts above, tgt_pts below; stop hit -> exit at sp + slip
    df = make_df([(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100), (100, 103, 99.9, 102.5), (102.5, 103, 102, 102.5)])
    it = Intents(df); it.place([1], -1, stop_pts=2.0, tgt_pts=4.0)
    tr, d = run(it)
    assert len(tr) == 1 and tr.side[0] == -1
    ep = 100 - SLIP
    assert tr.entry_px[0] == pytest.approx(ep)
    assert tr.exit_px[0] == pytest.approx(ep + 2.0 + SLIP)
    assert tr.pnl[0] == pytest.approx(-(2.0 + SLIP) * PV - COMM)
    assert tr.reason[0] == 'stop'


def test_stop_hit_before_target_same_bar_open_position():
    df = make_df([(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100), (100, 110, 90, 100)])
    it = Intents(df); it.place([1], 1, stop_px=97.0, tgt_px=104.0)
    tr, d = run(it)
    assert tr.reason[0] == 'stop' and tr.exit_px[0] == pytest.approx(97.0 - SLIP)


def test_gap_through_stop_fills_at_open():
    df = make_df([(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100), (95, 96, 94, 95.5)])
    it = Intents(df); it.place([1], 1, stop_px=97.0)
    tr, d = run(it)
    assert tr.exit_px[0] == pytest.approx(95.0 - SLIP) and tr.reason[0] == 'stop'


def test_limit_target_requires_trade_through():
    df = make_df([(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100), (100, 104.0, 99.9, 103), (103, 104.25, 102.9, 104)])
    it = Intents(df); it.place([1], 1, tgt_px=104.0)
    tr, d = run(it)
    assert bar_of(df, tr.exit_ts[0]) == 3 and tr.exit_px[0] == pytest.approx(104.0) and tr.reason[0] == 'target'


def test_no_reentry_on_exit_bar_and_one_position_at_a_time():
    df = make_df([(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100), (100, 100.5, 95, 100), (100, 100.5, 99.5, 100)])
    it = Intents(df); it.place([1, 2, 3], 1, stop_px=97.0)
    tr, d = run(it)
    # trade 1 enters bar1, stops bar2; sig on bar2 ignored (exit bar); sig on bar3 enters, closed at end of data
    assert [bar_of(df, t) for t in tr.entry_ts] == [1, 3]


def test_pending_cancelled_when_allow_entry_false():
    df = make_df([(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100), (100, 106, 99.5, 105)])
    it = Intents(df); it.place([1], 1, entry_px=105.0, valid_bars=10); it.allow_entry[2] = False
    tr, d = run(it)
    assert len(tr) == 0


def test_daily_loss_stop_halts_and_max_trades_day():
    df = make_df([(100, 100.5, 99.5, 100)] + [(100, 100.5, 95, 100)] * 6)
    it = Intents(df); it.place(np.arange(1, 7), 1, stop_px=97.0); it.daily_loss_stop = 20.0
    tr, d = run(it)
    # each trade loses (100.25-96.75)*5+1.3 = 18.8 -> after 2 trades realized = -37.6 <= -20 -> halted
    assert len(tr) == 2
    it = Intents(df); it.place(np.arange(1, 7), 1, stop_px=97.0); it.max_trades_day = 1
    tr, d = run(it)
    assert len(tr) == 1


def test_trailing_stop_updates_after_bar_no_lookahead():
    # trail 2 pts, activates at +3. bar2 high 106 -> after bar2 stop = 104. bar3 low 103.9 -> stop hit at 104 - slip
    df = make_df([(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100), (100, 106, 99.9, 105), (105, 105.5, 103.9, 104.5)])
    it = Intents(df); it.place([1], 1, stop_px=97.0, trail_pts=2.0, trail_act_pts=3.0)
    tr, d = run(it)
    assert bar_of(df, tr.exit_ts[0]) == 3 and tr.exit_px[0] == pytest.approx(104.0 - SLIP) and tr.reason[0] == 'trail'


def test_dmin_includes_unrealized_and_resets_per_day():
    df = make_df([(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100), (100, 100.5, 96, 100), (100, 100.5, 99.5, 100),
                  (100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100)], day_ids=[0, 0, 0, 0, 1, 1])
    it = Intents(df); it.place([1], 1, stop_px=90.0); it.force_flat[3] = True; it.allow_entry[3] = False
    tr, d = run(it)
    ep = 100.25
    assert d.min_eq[0] == pytest.approx((96 - ep) * PV - COMM)
    assert d.min_eq[1] == 0.0


# --------------------------------------------------------------------------------------------------------------
# Suspected bugs
# --------------------------------------------------------------------------------------------------------------

def test_BUG1_stop_entry_gap_open_fill_ignores_bar_low_for_protective_stop():
    """Buy-stop at 101 placed on bar 1. Bar 1 opens at 102 (above the trigger) so the engine fills at the OPEN
    (max(o, ppx)+slip = 102.25) -- the entire rest of the bar is therefore AFTER the fill. The bar's low (90) is far
    below the protective stop (95), yet the engine only compares the CLOSE to the stop for stop-entry fills and keeps
    the position open. A real account would be stopped at 94.75 on this bar. Optimistic => HIGH."""
    df = make_df([(100, 100.5, 99.5, 100), (102, 103, 90, 102.5), (102.5, 103, 102, 102.5)])
    it = Intents(df); it.place([1], 1, entry_px=101.0, valid_bars=5, stop_px=95.0)
    it.force_flat[2] = True; it.allow_entry[2] = False
    tr, d = run(it)
    assert len(tr) == 1
    assert tr.entry_px[0] == pytest.approx(102.25)
    assert tr.reason[0] == 'stop', f"expected stop exit on the entry bar, got {tr.reason[0]} at {tr.exit_px[0]}"
    assert tr.exit_px[0] == pytest.approx(95.0 - SLIP)
    assert tr.pnl[0] == pytest.approx((94.75 - 102.25) * PV - COMM)


def test_BUG1b_stop_entry_intrabar_fill_ambiguous_bar_resolved_in_favour_of_trader():
    """Same as above but the fill is intrabar (open 100.5 < trigger 101). The bar touches the trigger (fill) AND
    trades through the protective stop (low 90 < 95) and closes above the stop. The engine's documented policy for
    ambiguous bars is 'stop first' (conservative); here the ambiguity is resolved in the trader's favour (no exit).
    Note the short side is symmetric."""
    df = make_df([(100, 100.5, 99.5, 100), (100.5, 103, 90, 102.5), (102.5, 103, 102, 102.5)])
    it = Intents(df); it.place([1], 1, entry_px=101.0, valid_bars=5, stop_px=95.0)
    it.force_flat[2] = True; it.allow_entry[2] = False
    tr, d = run(it)
    assert tr.reason[0] == 'stop' and tr.exit_px[0] == pytest.approx(95.0 - SLIP)


def test_BUG2_market_entry_with_stop_already_breached_at_open_books_a_profit():
    """Long market entry on a bar whose OPEN (95) is already below the absolute protective stop (100): the engine
    fills the entry at 95.25 and then 'stops out' at sp - slip = 99.75, i.e. a +4.5 pt WIN from a trade that
    gapped through its stop. A sell stop resting above the market is executed immediately at the market, so the
    exit must be <= open - slip and the trade must lose. Any 'stop = prior bar low' market-entry strategy would
    harvest free profit on every gap-down open. Optimistic."""
    df = make_df([(100, 100.5, 99.5, 100), (95, 96, 94, 95.5), (95.5, 96, 95, 95.5)])
    it = Intents(df); it.place([1], 1, stop_px=100.0)
    it.force_flat[2] = True; it.allow_entry[2] = False
    tr, d = run(it)
    assert len(tr) == 1 and tr.reason[0] == 'stop'
    assert tr.exit_px[0] <= 95.0 - SLIP + 1e-9, f"exit {tr.exit_px[0]} is above the bar open"
    assert tr.pnl[0] < 0


def test_BUG2b_short_market_entry_with_stop_already_breached_at_open():
    df = make_df([(100, 100.5, 99.5, 100), (105, 106, 104, 104.5), (104.5, 105, 104, 104.5)])
    it = Intents(df); it.place([1], -1, stop_px=100.0)
    it.force_flat[2] = True; it.allow_entry[2] = False
    tr, d = run(it)
    assert tr.exit_px[0] >= 105.0 + SLIP - 1e-9 and tr.pnl[0] < 0


def test_BUG3_target_gap_open_exit_uses_full_bar_low_for_excursion():
    """Position closed at the OPEN of bar 2 (open 106 >= target 105 + thr). The rest of bar 2 (low 85) was never
    held, yet d_min and mae are charged with it. Pessimistic (overstates intraday drawdown => spurious Lucid MLL
    breaches on big winning days)."""
    df = make_df([(100, 100.5, 99.5, 100), (100, 101, 99.5, 100.5), (106, 107, 85, 100), (100, 100.5, 99.5, 100)])
    it = Intents(df); it.place([1], 1, stop_px=90.0, tgt_px=105.0)
    tr, d = run(it)
    ep = 100.25
    assert tr.reason[0] == 'target' and tr.exit_px[0] == pytest.approx(106.0)
    # worst excursion actually held: bar1 low 99.5 vs entry 100.25
    assert tr.mae_pts[0] == pytest.approx(99.5 - ep)
    assert d.min_eq[0] == pytest.approx((99.5 - ep) * PV - COMM)


def test_BUG3b_target_intrabar_exit_mfe_bounded_by_fill_price():
    """Target filled at 105 (limit) but mfe reports the bar high (120). Cosmetic/analytics only."""
    df = make_df([(100, 100.5, 99.5, 100), (100, 101, 99.5, 100.5), (100.5, 120, 100, 110)])
    it = Intents(df); it.place([1], 1, stop_px=90.0, tgt_px=105.0)
    tr, d = run(it)
    assert tr.reason[0] == 'target'
    assert tr.mfe_pts[0] == pytest.approx(105.0 - 100.25)


def test_BUG4_stop_entry_entry_bar_never_checks_target():
    """Buy-stop at 101 fills intrabar on bar 1 (open 100 < 101). The bar then runs to 110 (through the 105 target)
    with a low (99.8) that never approaches the stop (95). Price must cross 101 before reaching 110, so the target
    was unambiguously hit AFTER the fill. The engine skips the target check on stop-entry bars; bar 2 opens back
    at 100 and the trade is later flattened for a loss instead of +3.75 pts."""
    df = make_df([(100, 100.5, 99.5, 100), (100, 110, 99.8, 108), (100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100)])
    it = Intents(df); it.place([1], 1, entry_px=101.0, valid_bars=5, stop_px=95.0, tgt_px=105.0)
    it.force_flat[3] = True; it.allow_entry[3] = False
    tr, d = run(it)
    assert len(tr) == 1 and tr.entry_px[0] == pytest.approx(101.25)
    assert tr.reason[0] == 'target', f"got {tr.reason[0]} at {tr.exit_px[0]}"
    assert tr.exit_px[0] == pytest.approx(105.0)


def test_BUG5_valid_bars_off_by_one_vs_orb_scan_window():
    """Order placed at bar 1 with valid_bars=1. strategies/orb.py scans `(k - i_start) < valid_minutes`, i.e. the
    order is live on exactly valid_bars bars (bar 1 only). The engine keeps it live while i <= i_start+valid_bars
    (bars 1 AND 2), one bar longer."""
    df = make_df([(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100), (100, 106, 99.5, 105), (105, 105.5, 104, 105)])
    it = Intents(df); it.place([1], 1, entry_px=105.0, valid_bars=1)
    tr, d = run(it)
    assert len(tr) == 0, f"order filled on bar {int(tr.bars[0]) if len(tr) else None} after its validity window"


def test_BUG6_set_session_flat_time_between_1700_and_midnight_sets_no_force_flat():
    """An overnight strategy asking to be flat at 23:00 gets force_flat == False everywhere, so the position is
    silently carried to the next session's first bar (reason session_gap)."""
    tods = list(range(18 * 60, 24 * 60, 30)) + list(range(0, 17 * 60 + 1, 30))
    n = len(tods)
    df = pd.DataFrame({'ts': [pd.Timestamp('2025-03-03', tz='America/New_York') + pd.Timedelta(minutes=t) for t in tods],
                       'open': 100.0, 'high': 100.5, 'low': 99.5, 'close': 100.0, 'tod': np.array(tods, np.int32),
                       'day_id': np.zeros(n, np.int32), 'session': pd.Timestamp('2025-03-03').date()})
    it = Intents(df); it.set_session('18:00', '22:00', '23:00')
    tod = df['tod'].values
    assert it.force_flat[tod == 23 * 60].all(), "no force_flat bar at 23:00"
    assert not it.allow_entry[tod == 23 * 60].any()


def test_BUG7_session_carry_close_allows_reentry_on_same_bar_and_stale_mae():
    """A position carried across a session boundary is closed at the open of the first bar of the new session and
    a NEW entry is allowed on that very bar (the engine otherwise forbids re-entry on an exit bar)."""
    df = make_df([(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100), (90, 91, 89, 90), (90, 90.5, 89.5, 90)],
                 day_ids=[0, 0, 1, 1])
    it = Intents(df); it.place([1, 2], 1)
    tr, d = run(it)
    assert tr.reason[0] == 'session_gap' and bar_of(df, tr.exit_ts[0]) == 2
    assert not (len(tr) > 1 and bar_of(df, tr.entry_ts[1]) == 2), "re-entered on the session-gap exit bar"


def test_BUG8_end_of_data_close_not_reflected_in_min_eq():
    """A position still open on the last bar is closed at close - slip and the loss is added to d_pnl but d_min is
    not updated, so daily.min_eq > daily.pnl for that day (intraday minimum above the end-of-day value)."""
    df = make_df([(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100), (100, 100.5, 99.9, 90)])
    it = Intents(df); it.place([1], 1)
    tr, d = run(it)
    assert d.min_eq[0] <= d.pnl[0] + 1e-9, f"min_eq {d.min_eq[0]} > pnl {d.pnl[0]}"


def test_BUG9_trade_timestamps_lose_timezone():
    """engine.run builds entry_ts/exit_ts from df1['ts'].values, which drops the America/New_York tz and emits naive
    UTC. daily.session is an ET date, so trade times are 4-5 h off and a trade after 19:00 ET lands on the wrong
    calendar day in any downstream grouping by entry_ts."""
    df = make_df([(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100)])
    it = Intents(df); it.place([1], 1)
    tr, d = run(it)
    assert pd.Timestamp(tr.entry_ts[0]) == df.ts[1]


def test_BUG10_flat_time_not_enforced_when_session_ends_before_flat_time():
    """Holiday / early-close session: bars stop at 09:33 (no bar at or after flat_time 15:55), next bar is the
    18:00 reopen of the NEXT session which gaps 10 points. set_session only marks bars with tod >= flat_time, so
    nothing is force-flat; the engine carries the position through the halt and closes it at the reopen
    ('session_gap'). A prop account is flattened before the early close, so the overnight/weekend gap P&L
    (10 of 424 ORB trades on 2025-2026 SPXUSD, two of them held Fri->Sun) is a fill that cannot happen."""
    df = make_df([(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100.2), (100.2, 100.5, 99.5, 100.4),
                  (90, 91, 89, 90), (90, 90.5, 89.5, 90)], day_ids=[0, 0, 0, 0, 1, 1])
    df.loc[4:, 'tod'] = [18 * 60, 18 * 60 + 1]
    it = Intents(df); it.set_session('09:30', '11:30', '15:55'); it.place([1], 1)
    tr, d = run(it)
    assert len(tr) == 1
    assert tr.day_id[0] == 0 and bar_of(df, tr.exit_ts[0]) <= 3, f"closed on bar {bar_of(df, tr.exit_ts[0])} ({tr.reason[0]})"
    assert tr.reason[0] != 'session_gap'
    assert d.min_eq[0] <= d.pnl[0] + 1e-9
