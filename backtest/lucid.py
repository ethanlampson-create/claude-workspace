"""Lucid Trading 50K LucidFlex account simulator.

Rules encoded (cross-checked across six independent 2026 sources; see research/lucid_rules.md):
Evaluation
- Start balance 50,000; profit target +3,000 (balance >= 53,000).
- Max Loss Limit (MLL): end-of-day trailing. MLL = highest END-OF-SESSION balance - 2,000, moves only at
  session close, and once the EOD balance exceeds 52,100 the MLL locks at 50,100. A breach is INTRADAY:
  if balance + open P&L touches the MLL at any time, the account fails.
- 50% consistency rule: at the moment of passing, largest single-day profit <= 50% of total profit
  (total = balance - 50,000). Trader keeps trading until satisfied.
- Minimum 2 trading days. No daily loss limit by default. Max 4 minis / 40 micros.
Funded (sim-funded)
- Fresh 50,000 balance, same MLL mechanics (initial 48,000; locks at 50,100 after EOD > 52,100).
- Contract scaling: 20 micros (2 minis) until EOD profit >= 1,000 -> 30 micros; >= 2,000 -> 40 micros.
- Payout: needs >= 5 separate days with EOD profit >= 150 in the current cycle, cycle net positive,
  min 500, max = 50% of profit capped at 2,000, 90% to trader. Up to 5 payouts then live.
- After a payout request the MLL is set to max(MLL, 50,100) (the "lock"); balance drops by the payout
  and the MLL never falls with it.
All of this is parameterised in Rules so a variant can be tested.
"""
from dataclasses import dataclass, field
import numpy as np
import pandas as pd


@dataclass
class Rules:
    start_balance: float = 50_000.0
    target: float = 3_000.0
    mll_distance: float = 2_000.0
    lock_trigger: float = 52_100.0   # EOD balance above which MLL locks
    lock_level: float = 50_100.0
    consistency: float = 0.50        # eval only; 0 => none
    min_days: int = 2
    eval_max_micros: int = 40
    funded_scaling: tuple = ((0.0, 20), (1_000.0, 30), (2_000.0, 40))  # (profit threshold, max micros)
    payout_min_days: int = 5
    payout_day_min_profit: float = 150.0
    payout_min: float = 500.0
    payout_max: float = 2_000.0
    payout_frac: float = 0.5
    split: float = 0.90
    max_payouts: int = 5
    payout_locks_mll: bool = True
    eval_fee: float = 146.0
    reset_fee: float = 90.0


def _mll_update(mll, peak_eod, rules):
    new = peak_eod - rules.mll_distance
    if peak_eod > rules.lock_trigger:
        new = rules.lock_level
    return max(mll, min(new, rules.lock_level))


def simulate_eval(pnl, min_eq, start, micros, rules: Rules, horizon=120, micros_schedule=None):
    """Run one evaluation starting at day index `start` with `micros` contracts (micro-equivalents; the
    per-contract daily arrays must be for ONE micro contract). Returns dict with outcome.
    micros_schedule: optional callable(day_in_eval, balance, mll, largest_day, total_profit) -> micros."""
    bal = rules.start_balance; mll = rules.start_balance - rules.mll_distance; peak = bal
    largest = 0.0; days = 0
    n = len(pnl)
    for k in range(start, min(n, start + horizon)):
        m = micros if micros_schedule is None else micros_schedule(days, bal, mll, largest, bal - rules.start_balance)
        m = min(m, rules.eval_max_micros)
        if m <= 0:
            days += 1
            continue
        # intraday breach check
        if bal + min_eq[k] * m <= mll:
            return {'outcome': 'fail', 'days': days + 1, 'end_day': k, 'balance': mll, 'largest_day': largest}
        day_pnl = pnl[k] * m
        bal += day_pnl; days += 1
        largest = max(largest, day_pnl)
        peak = max(peak, bal)
        mll = _mll_update(mll, peak, rules)
        if bal <= mll:
            return {'outcome': 'fail', 'days': days, 'end_day': k, 'balance': bal, 'largest_day': largest}
        profit = bal - rules.start_balance
        if profit >= rules.target and days >= rules.min_days and (rules.consistency <= 0 or largest <= rules.consistency * profit):
            return {'outcome': 'pass', 'days': days, 'end_day': k, 'balance': bal, 'largest_day': largest}
    return {'outcome': 'incomplete', 'days': days, 'end_day': min(n, start + horizon) - 1, 'balance': bal, 'largest_day': largest}


def simulate_funded(pnl, min_eq, start, micros_policy, rules: Rules, horizon=250, min_profit_to_request=4_000.0,
                    request_asap_after_first=False, stop_after_payouts=None):
    """Simulate a funded LucidFlex account from day index `start`.
    micros_policy: callable(balance, mll, profit_since_start, n_payouts, max_micros_allowed) -> micros to trade.
    Payout policy: request when eligible (5 qualifying days, cycle net positive, profit >= payout_min/frac) AND
    profit >= min_profit_to_request (default 4,000 so that the first payout is the full 2,000 and the balance
    after the lock keeps >= 1,900 of room)."""
    bal = rules.start_balance; mll = bal - rules.mll_distance; peak = bal
    payouts = []; qual_days = 0; cycle_start_bal = bal; days = 0
    n = len(pnl)
    stop_after = rules.max_payouts if stop_after_payouts is None else stop_after_payouts
    for k in range(start, min(n, start + horizon)):
        profit = bal - rules.start_balance
        cap = rules.funded_scaling[0][1]
        for thr, mx in rules.funded_scaling:
            if profit >= thr:
                cap = mx
        m = min(micros_policy(bal, mll, profit, len(payouts), cap), cap)
        if m > 0:
            if bal + min_eq[k] * m <= mll:
                return {'outcome': 'breach', 'days': days + 1, 'end_day': k, 'payouts': payouts, 'paid': sum(payouts) * rules.split,
                        'balance': mll, 'first_payout_day': payouts and payouts_days[0] or None}
            day_pnl = pnl[k] * m
            bal += day_pnl
            if day_pnl >= rules.payout_day_min_profit:
                qual_days += 1
        days += 1
        peak = max(peak, bal)
        mll = _mll_update(mll, peak, rules)
        if bal <= mll:
            return {'outcome': 'breach', 'days': days, 'end_day': k, 'payouts': payouts, 'paid': sum(payouts) * rules.split,
                    'balance': bal, 'first_payout_day': payouts_days[0] if payouts else None}
        profit = bal - rules.start_balance
        cycle_net = bal - cycle_start_bal
        amount = min(rules.payout_max, rules.payout_frac * profit)
        eligible = qual_days >= rules.payout_min_days and cycle_net > 0 and amount >= rules.payout_min
        want = profit >= min_profit_to_request or (request_asap_after_first and len(payouts) > 0)
        if eligible and want:
            payouts.append(amount)
            if len(payouts) == 1:
                payouts_days = [days]
            bal -= amount
            if rules.payout_locks_mll:
                mll = max(mll, rules.lock_level)
            qual_days = 0; cycle_start_bal = bal
            if len(payouts) >= stop_after:
                return {'outcome': 'live', 'days': days, 'end_day': k, 'payouts': payouts, 'paid': sum(payouts) * rules.split,
                        'balance': bal, 'first_payout_day': payouts_days[0]}
    return {'outcome': 'alive', 'days': days, 'end_day': min(n, start + horizon) - 1, 'payouts': payouts,
            'paid': sum(payouts) * rules.split, 'balance': bal, 'first_payout_day': (payouts and payouts_days[0]) or None}


def constant_micros(m):
    return lambda bal, mll, profit, npay, cap: min(m, cap)


def monte_carlo(daily: pd.DataFrame, eval_micros, funded_policy, rules: Rules, start_every=1, eval_horizon=120,
                funded_horizon=250, min_profit_to_request=4_000.0, eval_schedule=None, funded_follows_eval=True):
    """Start an evaluation on every `start_every`-th session; if it passes, run the funded account from the next
    session. Returns per-start DataFrame and a summary dict. `daily` must have columns session, pnl, min_eq for
    ONE micro contract."""
    pnl = daily['pnl'].values; min_eq = daily['min_eq'].values; sessions = daily['session'].values
    rows = []
    n = len(pnl)
    for s in range(0, n - rules.min_days, start_every):
        ev = simulate_eval(pnl, min_eq, s, eval_micros, rules, eval_horizon, eval_schedule)
        row = {'start': sessions[s], 'eval': ev['outcome'], 'eval_days': ev['days'], 'eval_largest': ev['largest_day'], 'eval_balance': ev['balance']}
        if ev['outcome'] == 'pass' and funded_follows_eval and ev['end_day'] + 1 < n:
            fd = simulate_funded(pnl, min_eq, ev['end_day'] + 1, funded_policy, rules, funded_horizon, min_profit_to_request)
            row.update({'funded': fd['outcome'], 'funded_days': fd['days'], 'n_payouts': len(fd['payouts']), 'paid': fd['paid'],
                        'first_payout_day': fd['first_payout_day'], 'funded_balance': fd['balance']})
        rows.append(row)
    df = pd.DataFrame(rows)
    summ = summarize_mc(df, rules)
    return df, summ


def summarize_mc(df: pd.DataFrame, rules: Rules):
    out = {}
    n = len(df)
    out['n_starts'] = n
    out['pass_rate'] = float((df['eval'] == 'pass').mean()) if n else np.nan
    out['fail_rate'] = float((df['eval'] == 'fail').mean()) if n else np.nan
    out['incomplete_rate'] = float((df['eval'] == 'incomplete').mean()) if n else np.nan
    p = df[df['eval'] == 'pass']
    out['median_days_to_pass'] = float(p['eval_days'].median()) if len(p) else np.nan
    out['p90_days_to_pass'] = float(p['eval_days'].quantile(0.9)) if len(p) else np.nan
    if 'funded' in df.columns and len(p):
        f = p.dropna(subset=['funded'])
        out['p_first_payout_given_pass'] = float((f['n_payouts'] >= 1).mean()) if len(f) else np.nan
        out['p_breach_before_payout'] = float(((f['funded'] == 'breach') & (f['n_payouts'] == 0)).mean()) if len(f) else np.nan
        out['mean_paid_given_pass'] = float(f['paid'].mean()) if len(f) else np.nan
        out['median_days_to_first_payout'] = float(f['first_payout_day'].dropna().median()) if f['first_payout_day'].notna().any() else np.nan
        out['mean_payouts_given_pass'] = float(f['n_payouts'].mean()) if len(f) else np.nan
        out['p_live_5_payouts'] = float((f['funded'] == 'live').mean()) if len(f) else np.nan
        out['p_first_payout_unconditional'] = out['pass_rate'] * out['p_first_payout_given_pass'] if len(f) else np.nan
        out['expected_paid_per_eval'] = out['pass_rate'] * out['mean_paid_given_pass'] if len(f) else np.nan
        out['expected_net_per_eval'] = out['expected_paid_per_eval'] - rules.eval_fee if len(f) else np.nan
    # monthly pass rate: evals started in each calendar month
    if n:
        m = pd.to_datetime(df['start']).dt.to_period('M')
        out['monthly_pass_rate'] = df.groupby(m)['eval'].apply(lambda s: float((s == 'pass').mean())).to_dict()
    return out
