"""Hand-built daily-array tests for backtest/lucid.py against research/lucid_rules.md.

All arrays are per ONE micro contract (pnl = EOD net P&L, min_eq = intraday minimum of realized+unrealized
equity relative to the day's start, always <= min(0, pnl)).
"""
import numpy as np
import pandas as pd
import pytest

from backtest.lucid import Rules, simulate_eval, simulate_funded, constant_micros, monte_carlo, summarize_mc


def arr(*xs):
    return np.asarray(xs, dtype=float)


def rec_schedule(store, micros):
    """micros_schedule that records (day, balance, mll) before every day."""
    def f(day, bal, mll, largest, profit):
        store.append((day, bal, mll, largest, profit))
        return micros
    return f


def rec_policy(store, micros=None):
    """funded micros_policy that records (bal, mll, profit, npay, cap) and trades `micros` (or the cap)."""
    def f(bal, mll, profit, npay, cap):
        store.append((bal, mll, profit, npay, cap))
        return cap if micros is None else micros
    return f


# ----------------------------------------------------------------------------------------------------------
# MLL trailing / lock / intraday breach (eval)
# ----------------------------------------------------------------------------------------------------------

def test_mll_trails_highest_eod_and_moves_only_at_eod():
    r = Rules()
    store = []
    # 1 micro: +1500, then -500, then +100
    pnl = arr(1500, -500, 100); mn = arr(-10, -500, -10)
    simulate_eval(pnl, mn, 0, 1, r, micros_schedule=rec_schedule(store, 1))
    # before day0: mll 48,000; after +1500 EOD: 49,500; after losing day: unchanged
    assert [s[2] for s in store] == [48_000, 49_500, 49_500]


def test_intraday_breach_uses_prior_eod_mll_and_min_eq_times_micros():
    r = Rules()
    # day0 +1500/micro at 1 micro -> bal 51,500, mll 49,500. day1 dips 2,000 intraday (-> 49,500) then closes +100
    pnl = arr(1500, 100); mn = arr(-10, -2000)
    out = simulate_eval(pnl, mn, 0, 1, r)
    assert out['outcome'] == 'fail' and out['days'] == 2 and out['balance'] == 49_500
    # one dollar of room survives
    mn2 = arr(-10, -1999)
    assert simulate_eval(pnl, mn2, 0, 1, r)['outcome'] == 'incomplete'
    # micros multiply the excursion: 10 micros with min_eq -200/micro == -2000
    pnl10 = arr(150, 10); mn10 = arr(-1, -200)
    assert simulate_eval(pnl10, mn10, 0, 10, r)['outcome'] == 'fail'


def test_breach_on_first_day_before_any_eod():
    r = Rules()
    out = simulate_eval(arr(500), arr(-2000), 0, 1, r)
    assert out['outcome'] == 'fail' and out['days'] == 1 and out['end_day'] == 0


def test_breach_takes_priority_over_pass_on_same_day():
    r = Rules(consistency=0, min_days=1)
    out = simulate_eval(arr(3000), arr(-2000), 0, 1, r)
    assert out['outcome'] == 'fail'


def test_lock_at_50100_once_eod_above_52100():
    r = Rules()
    store = []
    # +2050 -> 52,050 (not locked, mll 50,050); +100 -> 52,150 (> 52,100 -> lock 50,100); +1000 -> 53,150 (stays 50,100)
    pnl = arr(2050, 100, 1000, -3000); mn = arr(0, 0, 0, -3000)
    out = simulate_eval(pnl, mn, 0, 1, r, micros_schedule=rec_schedule(store, 1))
    assert [s[2] for s in store] == [48_000, 50_050, 50_100, 50_100]
    assert out['outcome'] == 'incomplete'  # 53,150 - 3,000 = 50,150 > 50,100: not a breach


def test_lock_boundary_exact_values():
    r = Rules()
    store = []
    pnl = arr(2050, 100, 1000, -3049); mn = arr(0, 0, 0, -3049)
    out = simulate_eval(pnl, mn, 0, 1, r, micros_schedule=rec_schedule(store, 1))
    assert out['outcome'] == 'incomplete'  # 53,150 - 3,049 = 50,101 > 50,100
    pnl = arr(2050, 100, 1000, -3050); mn = arr(0, 0, 0, -3050)
    out = simulate_eval(pnl, mn, 0, 1, r)
    assert out['outcome'] == 'fail'        # 50,100 <= 50,100 touches


# ----------------------------------------------------------------------------------------------------------
# Pass condition: target, min_days, consistency
# ----------------------------------------------------------------------------------------------------------

def test_consistency_blocks_pass_until_largest_day_le_half_profit():
    r = Rules()
    # +2000, +1200 -> profit 3200, largest 2000 > 1600 -> keep trading; +900 -> 4100, 2000 <= 2050 -> pass day 3
    pnl = arr(2000, 1200, 900, 1000); mn = arr(0, 0, 0, 0)
    out = simulate_eval(pnl, mn, 0, 1, r)
    assert out['outcome'] == 'pass' and out['days'] == 3 and out['end_day'] == 2 and out['balance'] == 54_100


def test_consistency_uses_balance_minus_start_not_sum_of_winners():
    r = Rules()
    # winners 2000 + 1600 = 3600 (largest 2000 <= 1800? no). with a -300 loser profit = 3300 -> 2000 > 1650 -> no pass
    pnl = arr(2000, -300, 1600, 400); mn = arr(0, -300, 0, 0)
    out = simulate_eval(pnl, mn, 0, 1, r)
    # day 4: profit 3700, largest 2000 > 1850 -> still no pass
    assert out['outcome'] == 'incomplete'


def test_target_is_balance_ge_53000_and_min_days_two():
    r = Rules(consistency=0)
    out = simulate_eval(arr(3000, 0), arr(0, 0), 0, 1, r)
    assert out['outcome'] == 'pass' and out['days'] == 2  # first day alone is blocked by min_days


def test_losing_day_with_trades_counts_toward_min_days():
    r = Rules(consistency=0)
    out = simulate_eval(arr(-100, 3100), arr(-100, 0), 0, 1, r)
    assert out['outcome'] == 'pass' and out['days'] == 2


def test_min_days_should_not_count_days_without_trades():
    """Lucid's 'trading day' is a day with at least one executed trade. The simulator counts every session
    (pnl == 0, no trade) and every schedule-zero day as a trading day, so an account with ONE trading day can
    'pass' once consistency is off (the documented variant: 'one source says none'). Under the default 50%
    consistency this is masked because the ratio needs >= 2 profitable days."""
    r = Rules(consistency=0)
    # day0: no trade at all (pnl 0, min_eq 0); day1: +3000 -> only one trading day
    out = simulate_eval(arr(0, 3000), arr(0, 0), 0, 1, r)
    assert out['outcome'] != 'pass', 'passed with a single trading day'


def test_min_days_schedule_zero_day_is_not_a_trading_day():
    r = Rules(consistency=0)
    sched = lambda day, bal, mll, largest, profit: 0 if day == 0 else 1
    out = simulate_eval(arr(500, 3000), arr(0, 0), 0, 1, r, micros_schedule=sched)
    assert out['outcome'] != 'pass', 'passed with a single trading day (day 0 was not traded)'


# ----------------------------------------------------------------------------------------------------------
# Funded: scaling, payouts, lock, balance reduction, live
# ----------------------------------------------------------------------------------------------------------

def test_funded_contract_scaling_table_by_eod_profit():
    r = Rules()
    store = []
    # trade the cap each day. day0: +50/micro * 20 = +1000 -> cap 30; day1: +40 * 30 = +1200 -> profit 2200 -> cap 40
    # day2: -40 * 40 = -1600 -> profit 600 -> cap back to 20 (bal 50,600 > locked mll 50,100)
    pnl = arr(50, 40, -40, 0); mn = arr(0, 0, -40, 0)
    simulate_funded(pnl, mn, 0, rec_policy(store), r)
    assert [s[4] for s in store] == [20, 30, 40, 20]
    assert [s[2] for s in store] == [0, 1000, 2200, 600]


def test_funded_intraday_breach_before_first_eod_and_no_nameerror():
    r = Rules()
    out = simulate_funded(arr(100), arr(-100), 0, constant_micros(20), r)
    assert out['outcome'] == 'breach' and out['days'] == 1 and out['first_payout_day'] is None and out['payouts'] == []
    out = simulate_funded(arr(100, -2000), arr(0, -2000), 0, constant_micros(1), r)
    assert out['outcome'] == 'breach' and out['days'] == 2 and out['first_payout_day'] is None
    out = simulate_funded(arr(10, 10), arr(0, 0), 0, constant_micros(1), r)
    assert out['outcome'] == 'alive' and out['first_payout_day'] is None and out['paid'] == 0


def test_payout_requires_5_qualifying_days_and_min_profit():
    r = Rules()
    # 1 micro. four days of +1000 (qualify) + one day of +100 (does NOT qualify, < 150): profit 4100, no payout
    pnl = arr(1000, 1000, 1000, 1000, 100, 200); mn = arr(0, 0, 0, 0, 0, 0)
    out = simulate_funded(pnl[:5], mn[:5], 0, constant_micros(1), r)
    assert out['payouts'] == []
    # sixth day +200 qualifies -> 5 qualifying days, profit 4300 -> payout min(2000, 0.5*4300) = 2000
    out = simulate_funded(pnl, mn, 0, constant_micros(1), r)
    assert out['payouts'] == [2000.0] and out['first_payout_day'] == 6 and out['paid'] == pytest.approx(1800.0)
    assert out['balance'] == 54_300 - 2000


def test_payout_blocked_until_min_profit_to_request_then_locks_mll():
    r = Rules()
    store = []
    # 1 micro: 5 x +700 = 3500 (eligible: amount 1750 >= 500, 5 qual days) but < 4000 -> no request
    pnl = arr(700, 700, 700, 700, 700, 500, -1900, -1); mn = arr(0, 0, 0, 0, 0, 0, -1900, -1)
    out = simulate_funded(pnl, mn, 0, rec_policy(store, 1), r)
    # after day 5 (profit 4000): payout 2000 -> balance 52,000; mll locked at 50,100; peak NOT reduced
    assert out['payouts'] == [2000.0] and out['first_payout_day'] == 6
    # day 6 (index 6) sees bal 52,000 / mll 50,100
    assert store[6][0] == 52_000 and store[6][1] == 50_100
    # -1900 -> 50,100 at EOD touches the lock -> breach
    assert out['outcome'] == 'breach' and out['end_day'] == 6


def test_payout_lock_room_is_only_2000_minus_lock_after_full_payout():
    r = Rules()
    pnl = arr(800, 800, 800, 800, 800, -1899, -1); mn = arr(0, 0, 0, 0, 0, -1899, -1)
    out = simulate_funded(pnl, mn, 0, constant_micros(1), r)
    # after payout bal 52,000; -1899 -> 50,101 survives; -1 -> 50,100 breach at EOD
    assert out['outcome'] == 'breach' and out['end_day'] == 6 and out['balance'] == 50_100


def test_payout_amount_min_500_and_half_profit():
    r = Rules()
    # min_profit_to_request=1000, 5 x +200 -> profit 1000 -> amount 500 -> bal 50,500, mll 50,100 (400 of room)
    pnl = arr(200, 200, 200, 200, 200, -400); mn = arr(0, 0, 0, 0, 0, -400)
    out = simulate_funded(pnl, mn, 0, constant_micros(1), r, min_profit_to_request=1000)
    assert out['payouts'] == [500.0] and out['outcome'] == 'breach' and out['balance'] == 50_100


def test_payout_cycle_resets_and_five_payouts_go_live():
    r = Rules()
    # cycle 1: 5 x +800 -> 4000 -> payout 2000 -> bal 52,000. each later cycle: 5 x +400 -> 54,000 -> payout 2000
    pnl = np.concatenate([arr(800) * np.ones(5)] + [arr(400) * np.ones(5)] * 4 + [arr(400) * np.ones(5)])
    mn = np.zeros_like(pnl)
    out = simulate_funded(pnl, mn, 0, constant_micros(1), r)
    assert out['outcome'] == 'live' and out['payouts'] == [2000.0] * 5 and out['paid'] == pytest.approx(9000.0)
    assert out['days'] == 25 and out['first_payout_day'] == 5 and out['balance'] == 52_000


def test_qualifying_days_do_not_carry_across_cycles():
    r = Rules()
    # cycle 1: 5 x +800 -> payout. cycle 2: 4 x +500 (profit 4000) -> NOT eligible (only 4 qualifying days)
    pnl = np.concatenate([np.full(5, 800.0), np.full(4, 500.0)]); mn = np.zeros_like(pnl)
    out = simulate_funded(pnl, mn, 0, constant_micros(1), r)
    assert out['payouts'] == [2000.0] and out['outcome'] == 'alive' and out['balance'] == 54_000


def test_cycle_must_be_net_positive():
    r = Rules()
    # cycle 1 -> payout at 54,000 -> 52,000. cycle 2: 5 x +200 then -1500: profit 1500 (<4000) ... use asap flag
    pnl = np.concatenate([np.full(5, 800.0), np.full(5, 200.0), arr(-1100)]); mn = np.minimum(pnl, 0)
    out = simulate_funded(pnl, mn, 0, constant_micros(1), r, request_asap_after_first=True)
    # after 5 x +200 the cycle is +1000 and profit 3000 -> amount 1500 -> second payout taken immediately
    assert out['payouts'][:2] == [2000.0, 1500.0]


def test_funded_horizon_alive_end_day():
    r = Rules()
    pnl = np.full(10, 10.0); mn = np.zeros(10)
    out = simulate_funded(pnl, mn, 2, constant_micros(1), r, horizon=5)
    assert out['outcome'] == 'alive' and out['days'] == 5 and out['end_day'] == 6


def test_eval_horizon_incomplete_end_day():
    r = Rules()
    pnl = np.full(10, 10.0); mn = np.zeros(10)
    out = simulate_eval(pnl, mn, 3, 1, r, horizon=4)
    assert out['outcome'] == 'incomplete' and out['days'] == 4 and out['end_day'] == 6
    out = simulate_eval(pnl, mn, 8, 1, r, horizon=120)
    assert out['days'] == 2 and out['end_day'] == 9


# ----------------------------------------------------------------------------------------------------------
# monte_carlo / summarize_mc
# ----------------------------------------------------------------------------------------------------------

def make_daily(pnl, start='2025-01-02'):
    sessions = pd.bdate_range(start, periods=len(pnl)).date
    return pd.DataFrame({'session': sessions, 'pnl': np.asarray(pnl, float), 'min_eq': np.minimum(np.asarray(pnl, float), 0.0),
                         'max_eq': np.maximum(np.asarray(pnl, float), 0.0), 'trades': (np.asarray(pnl) != 0).astype(int)})


def test_monte_carlo_starts_funded_next_session_and_summary_fields():
    r = Rules()
    # every eval passes in 4 days (+750/day, largest 750 <= 1500 at profit 3000)
    d = make_daily(np.full(40, 750.0))
    df, s = monte_carlo(d, 1, constant_micros(1), r, start_every=1)
    assert s['n_starts'] == 38  # range(0, n - min_days)
    passed = df[df['eval'] == 'pass']
    assert (passed['eval_days'] == 4).all()
    # funded begins the session after the pass day: 6 days of +750 -> 4500 -> payout 2000 (5 qualifying days needed)
    first = df.iloc[0]
    assert first['funded'] in ('alive', 'live', 'breach') and first['n_payouts'] >= 1 and first['first_payout_day'] == 6
    assert s['expected_net_per_eval'] == pytest.approx(s['pass_rate'] * s['mean_paid_given_pass'] - r.eval_fee)
    assert s['p_first_payout_unconditional'] == pytest.approx(s['pass_rate'] * s['p_first_payout_given_pass'])


def test_monthly_pass_rate_not_biased_by_data_end_truncation():
    """Evals started near the end of the data cannot finish; they are 'incomplete', not failures, yet pass_rate,
    monthly_pass_rate and expected_net_per_eval all treat them as non-passing and still charge the eval fee.
    Here NO eval ever fails and every eval that has >= 4 sessions passes; the last month's rate should be 1.0."""
    r = Rules()
    d = make_daily(np.full(40, 750.0), start='2025-01-02')  # 2025-01-02 .. ~2025-02-26
    df, s = monte_carlo(d, 1, constant_micros(1), r)
    assert s['fail_rate'] == 0.0
    last_month = max(s['monthly_pass_rate'])
    assert s['monthly_pass_rate'][last_month] == 1.0, s['monthly_pass_rate']


def test_summarize_mc_on_too_short_daily_does_not_raise():
    r = Rules()
    d = make_daily([100.0, 100.0])  # n == min_days -> zero starts
    df, s = monte_carlo(d, 1, constant_micros(1), r)
    assert s['n_starts'] == 0


def test_monte_carlo_uses_trades_column_for_trading_days():
    """A strategy that trades once a week: min_days must count executed-trade days. Here the eval 'passes' on
    the second calendar session although only one session had a trade (consistency disabled to isolate min_days)."""
    r = Rules(consistency=0)
    d = make_daily([3000.0, 0.0, 0.0, 0.0])
    df, s = monte_carlo(d, 1, constant_micros(1), r)
    assert df.iloc[0]['eval'] != 'pass' or df.iloc[0]['eval_days'] > 2
