"""Adversarial audit of backtest/lucid.py + batch.lucid_scan + metrics.py as *decision tools* for sizing a real
Lucid 50K Flex account.

Rule mechanics (MLL trailing/lock, intraday breach, consistency, trading days, scaling, payout cycle, lock) were
re-derived by hand against research/lucid_rules.md and found consistent; the control tests at the bottom pin a few
boundary cases that were not covered. The findings are STATISTICAL: how the simulator's numbers are produced and
selected. The finding tests were promoted to regular tests once the behaviour was fixed (lower-bound sizing, bootstrap bands,
zero-edge control, pass-within-21 monthly rates with counts).

All synthetic daily tables are per ONE micro contract; seeds are fixed, so every number below is deterministic.
"""
import warnings
import numpy as np
import pandas as pd
import pytest

from backtest.lucid import Rules, monte_carlo, constant_micros, simulate_funded, simulate_eval, summarize_mc
from backtest.batch import lucid_scan, MICRO_SCAN

warnings.filterwarnings('ignore', category=RuntimeWarning)
R = Rules()


def make_daily(pnl, start='2025-01-02'):
    pnl = np.asarray(pnl, float)
    min_eq = np.minimum(pnl, 0.0) - np.abs(pnl) * 0.3          # some intraday excursion below the close
    return pd.DataFrame({'session': pd.bdate_range(start, periods=len(pnl)).date, 'pnl': pnl, 'min_eq': min_eq,
                         'max_eq': np.maximum(pnl, 0.0), 'trades': np.ones(len(pnl), int)})


def noise(seed, n=430, drift=0.0, scale=20.0):
    """i.i.d. fat-tailed daily P&L per micro, ~430 sessions = the 2025-01..2026-09 window."""
    return np.random.default_rng(seed).standard_t(4, n) * scale + drift


# ----------------------------------------------------------------------------------------------------------
# F1 (HIGH): lucid_scan picks the micros with the highest expected_net_per_eval ON THE SAME DATA it reports.
# The reported 'best' is max over 6 noisy estimates -> winner's curse. Demonstration: choose micros on series A,
# evaluate the same micros on an independent series B from the same process. If the selection were unbiased the
# in-sample best would not systematically exceed its out-of-sample value.
# ----------------------------------------------------------------------------------------------------------
def test_lucid_scan_lower_bound_does_not_overstate_out_of_sample():
    """lucid_scan selects the contract size by the block-bootstrap LOWER bound of expected net; the lower bound it
    reports in-sample must not exceed the out-of-sample point estimate of the same size on an independent series."""
    ins, oos = [], []
    for seed in range(10):
        a, b = noise(seed, drift=1.0), noise(1000 + seed, drift=1.0)
        ta, best = lucid_scan(make_daily(a), R, boot_reps=40)
        tb, _ = lucid_scan(make_daily(b, start='2026-03-02'), R, boot_reps=0)
        ins.append(float(best['exp_net_lb']))
        oos.append(float(tb.set_index('micros').loc[int(best['micros']), 'expected_net_per_eval']))
    gap = np.mean(ins) - np.nanmean(oos)
    assert gap <= 0.0, f'in-sample lower bound exceeds out-of-sample by ${gap:.0f} per eval'


def test_lucid_scan_reported_bound_is_not_a_winner_curse_on_zero_edge():
    """On zero-edge noise the reported (lower-bound) number must not exceed the best size's true averaged value."""
    tabs = []
    for seed in range(12):
        t, _ = lucid_scan(make_daily(noise(100 + seed)), R, boot_reps=40)
        tabs.append(t.set_index('micros')[['expected_net_per_eval', 'exp_net_lb']])
    pt = pd.concat([x['expected_net_per_eval'] for x in tabs], axis=1); lb = pd.concat([x['exp_net_lb'] for x in tabs], axis=1)
    reported = lb.max(axis=0).mean()            # what lucid_scan selects on, averaged over series
    best_true = pt.mean(axis=1).max()           # the best size's true (averaged) point value
    assert reported <= best_true + 10.0, f'{reported:.0f} reported vs {best_true:.0f} true'


# ----------------------------------------------------------------------------------------------------------
# F2 (HIGH): the objective itself. expected_net_per_eval is an option value: on a ZERO-EDGE process it rises with
# leverage (per-micros means observed: 5:-86 10:-42 15:-3 20:+24 30:+44 40:+24) and lucid_scan reports a positive
# 'best' expected net on pure noise in ~52% of series. Maximising it therefore selects leverage, not edge, and a
# strategy with no edge is reported as a money-maker more often than not.
# ----------------------------------------------------------------------------------------------------------
def test_zero_edge_process_is_not_recommended():
    """The size selected on zero-edge noise must almost never be flagged `recommended` (positive lower bound AND
    beats the zero-edge control)."""
    rec = 0
    for seed in range(15):
        _, best = lucid_scan(make_daily(noise(100 + seed)), R, boot_reps=40)
        rec += bool(best['recommended'])
    assert rec / 15 < 0.2, f'zero-edge noise recommended in {rec}/15 series'


# ----------------------------------------------------------------------------------------------------------
# F3 (HIGH): precision. Starts overlap (every session starts a 120-session eval on the same path), so n_starts
# (~430) is not the sample size. Across independent series the pass_rate has sd ~0.125 while the binomial se
# implied by n_starts is ~0.023: effective n ~ 15. summarize_mc reports no interval, so a monthly or overall pass
# rate of e.g. 0.60 is read as precise when its 95% band is roughly +-0.25.
# ----------------------------------------------------------------------------------------------------------
def test_bootstrap_band_reflects_cross_series_dispersion():
    """Overlapping starts make n_starts overstate precision ~5x. The block-bootstrap band must be at least as wide as
    the naive binomial band implied by n_starts, and the summary must expose n_effective."""
    from backtest.lucid import bootstrap_summary, monte_carlo_fast
    prs = []; widths = []; naive = []
    for seed in range(12):
        d = make_daily(noise(900 + seed, drift=1.5))
        df, s = monte_carlo_fast(d, 20, 20, R)
        assert 'n_effective' in s
        prs.append(s['pass_rate'])
        bs = bootstrap_summary(d, 20, 20, R, reps=60)
        widths.append(bs['pass_rate_p95'] - bs['pass_rate_p05'])
        n = s['n_starts'] - s['n_censored']; p = max(s['pass_rate'], 1e-3)
        naive.append(2 * 1.645 * np.sqrt(p * (1 - p) / n))
    assert np.mean(widths) >= np.mean(naive), f'bootstrap band {np.mean(widths):.3f} narrower than naive {np.mean(naive):.3f}'


# ----------------------------------------------------------------------------------------------------------
# F4 (MEDIUM): monthly_pass_rate semantics. It is the EVENTUAL (120-session) pass rate of evals started in a
# month, so a month in which the strategy loses money shows 1.0 as long as the following months recover. That is
# not what 'monthly pass rate is valid' means for someone starting an eval in that month, and the per-month n
# (last months: 9, 5, 1 ...) is not reported.
# ----------------------------------------------------------------------------------------------------------
def test_monthly_pass_rate_does_not_credit_a_losing_month():
    pnl = np.concatenate([np.full(21, -50.0), np.full(60, 300.0)])   # Jan 2025: -$1,050; then +$300/day
    df, s = monte_carlo(make_daily(pnl), 1, constant_micros(1), R)
    jan = s['monthly_pass_rate']['2025-01' if '2025-01' in {str(k) for k in s['monthly_pass_rate']} else list(s['monthly_pass_rate'])[0]]
    assert jan < 1.0, f'January (strategy lost money every day) reports monthly pass rate {jan}'


def test_monthly_pass_rate_reports_counts():
    df, s = monte_carlo(make_daily(noise(7, drift=2.0)), 10, constant_micros(10), R)
    assert any(k.startswith('monthly_n') for k in s), 'summarize_mc gives rates without the number of starts behind them'


# ----------------------------------------------------------------------------------------------------------
# F5 (LOW, verified mild & pessimistic here): censoring excludes unresolved tail starts, so starts within
# `horizon` of the data end contribute only their fast-resolving outcomes. On this process the all-resolved pass
# rate is ~1.5pp BELOW the full-horizon one (fails resolve faster than passes). Kept as a bound, not a failure.
# ----------------------------------------------------------------------------------------------------------
def test_censoring_bias_is_small_on_fat_tailed_noise():
    diffs = []
    for seed in range(30):
        df, s = monte_carlo(make_daily(noise(500 + seed, drift=1.5)), 20, constant_micros(20), R)
        full = df.iloc[: 430 - 120]
        diffs.append(s['pass_rate'] - (full['eval'] == 'pass').mean())
    assert abs(np.mean(diffs)) < 0.03
    assert np.mean(diffs) < 0   # direction on this process: pessimistic


# ----------------------------------------------------------------------------------------------------------
# Control tests: rule mechanics re-derived by hand and found consistent with research/lucid_rules.md.
# ----------------------------------------------------------------------------------------------------------

def test_second_payout_is_half_of_total_profit_not_cycle_profit():
    """Encoded interpretation (matches the doc's '50% of profit'): after a 2,000 payout the balance is 52,000; a
    cycle gain of only 1,000 (5 x 200) makes profit 3,000 -> amount 1,500 > cycle gain. If Lucid computes 50% of
    CYCLE profit this is optimistic by 1,000 on the second payout; flagged as an interpretation risk, not a bug."""
    pnl = np.concatenate([np.full(5, 800.0), np.full(5, 200.0)]); mn = np.zeros_like(pnl)
    out = simulate_funded(pnl, mn, 0, constant_micros(1), R, request_asap_after_first=True)
    assert out['payouts'] == [2000.0, 1500.0]


def test_funded_cap_drops_after_payout_reduces_balance():
    """Scaling is re-derived from balance - 50,000 each day, so a payout lowers the cap; 54,000 -> 52,000 keeps 40."""
    store = []
    def pol(bal, mll, profit, npay, cap):
        store.append(cap); return 1
    pnl = np.full(6, 800.0); mn = np.zeros(6)
    simulate_funded(pnl, mn, 0, pol, R)
    assert store == [20, 20, 30, 40, 40, 40]


def test_mll_update_exact_lock_trigger_and_cap():
    """peak 52,100 exactly -> 50,100; peak 60,000 -> still 50,100; MLL never decreases."""
    from backtest.lucid import _mll_update
    assert _mll_update(48_000, 52_100, R) == 50_100
    assert _mll_update(48_000, 60_000, R) == 50_100
    assert _mll_update(50_100, 50_500, R) == 50_100


def test_eval_pass_requires_consistency_on_the_pass_day_itself():
    """+2,500 on the day the target is crossed (profit 3,000) is 83% of profit -> no pass, keep trading."""
    out = simulate_eval(np.array([500.0, 2500.0, 100.0]), np.zeros(3), 0, 1, R)
    assert out['outcome'] != 'pass' or out['days'] == 3


def test_expected_net_uses_single_fee_and_90_split():
    pnl = np.full(40, 750.0)
    df, s = monte_carlo(make_daily(pnl), 1, constant_micros(1), R)
    assert s['expected_net_per_eval'] == pytest.approx(s['pass_rate'] * s['mean_paid_given_pass'] - 146.0)
    assert df['paid'].dropna().iloc[0] == pytest.approx(0.9 * 2000.0 * df['n_payouts'].dropna().iloc[0])


def test_metrics_intraday_drawdown_is_vs_prior_eod_peak():
    from backtest.metrics import metrics
    d = pd.DataFrame({'session': pd.bdate_range('2025-01-02', periods=3).date, 'pnl': [100.0, -50.0, 30.0],
                      'min_eq': [-20.0, -80.0, -10.0], 'max_eq': [100.0, 0.0, 30.0], 'trades': [1, 1, 1]})
    m = metrics(pd.DataFrame({'pnl': [100.0, -50.0, 30.0]}), d)
    assert m['max_dd_intraday'] == -80.0 and m['max_dd_closed'] == -50.0
    assert m['sharpe_daily_ann'] == pytest.approx(np.mean([100, -50, 30]) / np.std([100, -50, 30], ddof=1) * np.sqrt(252))
