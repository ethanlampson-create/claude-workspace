"""Campaign simulation and sizing policies for the two target configurations.

A *campaign* is a sequence of evaluation attempts on the same strategy stream: start an eval; if it fails, buy a
reset/new eval and start again the next session, up to `max_attempts`; once passed, run the funded account.
This answers "how likely is it that ONE of my evals makes it to funded (and to a first payout), how long does it take,
and what does it cost" for a given sizing policy. Because attempts on the same days are perfectly correlated,
sequential attempts are the honest model (parallel copies of the same account add nothing).

Sizing policies (micro contracts):
- constant(n)
- cushion(base, step_per, max_n): base micros, +1 per `step_per` dollars of EOD cushion above the start balance
- room(base, min_room, reduced): base micros while (balance - MLL) >= min_room, else `reduced`
Funded policies get (balance, mll, profit, n_payouts, cap) and should keep risk small near the lock.
"""
import argparse, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.lucid import Rules, simulate_eval, simulate_funded, constant_micros


def eval_constant(n):
    return lambda day, bal, mll, largest, profit: n


def eval_cushion(base, step_per=500.0, max_n=40):
    return lambda day, bal, mll, largest, profit: int(min(max_n, base + max(0.0, profit) // step_per))


def eval_room(base, min_room=900.0, reduced=None):
    reduced = reduced if reduced is not None else max(1, base // 2)
    return lambda day, bal, mll, largest, profit: base if (bal - mll) >= min_room else reduced


def funded_room(base, min_room=900.0, reduced=None, after_payout=None):
    """Trade `base` micros while room >= min_room, else `reduced`; optionally a different base after the first payout."""
    reduced = reduced if reduced is not None else max(1, base // 2)
    def f(bal, mll, profit, npay, cap):
        b = base if (npay == 0 or after_payout is None) else after_payout
        n = b if (bal - mll) >= min_room else reduced
        return int(min(n, cap))
    return f


def simulate_campaign(pnl, min_eq, ntr, start, eval_sched, funded_policy, rules: Rules, max_attempts=3, eval_horizon=120,
                      funded_horizon=250, min_profit_to_request=4000.0, max_days=400):
    """Sequential eval attempts from `start`; returns dict with attempts, fees, days_to_funded, funded outcome."""
    n = len(pnl); k = start; attempts = 0; fees = 0.0; days = 0
    while attempts < max_attempts and k < n and days < max_days:
        attempts += 1; fees += rules.eval_fee if attempts == 1 else rules.reset_fee
        ev = simulate_eval(pnl, min_eq, k, 1, rules, eval_horizon, eval_sched, ntr)
        days += ev['days']
        if ev['outcome'] == 'pass':
            fd = simulate_funded(pnl, min_eq, ev['end_day'] + 1, funded_policy, rules, funded_horizon, min_profit_to_request) if ev['end_day'] + 1 < n else None
            return {'funded': True, 'attempts': attempts, 'fees': fees, 'days_to_funded': days, 'end_day': ev['end_day'],
                    'funded_outcome': fd['outcome'] if fd else 'censored', 'n_payouts': len(fd['payouts']) if fd else 0,
                    'paid': fd['paid'] if fd else 0.0, 'first_payout_day': fd['first_payout_day'] if fd else None,
                    'funded_censored': (fd.get('censored', False) if fd else True)}
        if ev['outcome'] in ('censored',):
            return {'funded': False, 'attempts': attempts, 'fees': fees, 'days_to_funded': None, 'end_day': ev['end_day'], 'censored': True}
        if ev['outcome'] == 'incomplete':
            return {'funded': False, 'attempts': attempts, 'fees': fees, 'days_to_funded': None, 'end_day': ev['end_day'], 'censored': False}
        k = ev['end_day'] + 1
    return {'funded': False, 'attempts': attempts, 'fees': fees, 'days_to_funded': None, 'end_day': k, 'censored': k >= n}


def campaign_mc(daily, eval_sched, funded_policy, rules=None, max_attempts=3, start_every=1, **kw):
    rules = rules or Rules()
    pnl = daily['pnl'].values; mn = daily['min_eq'].values; ntr = daily['trades'].values if 'trades' in daily else None
    rows = []
    for s in range(0, max(0, len(pnl) - rules.min_days), start_every):
        r = simulate_campaign(pnl, mn, ntr, s, eval_sched, funded_policy, rules, max_attempts, **kw)
        r['start'] = daily['session'].values[s]; rows.append(r)
    df = pd.DataFrame(rows)
    res = df[~df.get('censored', pd.Series(False, index=df.index)).fillna(False).astype(bool)] if len(df) else df
    out = {'n_starts': int(len(df)), 'n_resolved': int(len(res))}
    if len(res):
        out['p_funded'] = float(res['funded'].mean())
        f = res[res['funded']]
        out['mean_attempts_given_funded'] = float(f['attempts'].mean()) if len(f) else np.nan
        out['median_days_to_funded'] = float(f['days_to_funded'].median()) if len(f) else np.nan
        out['p90_days_to_funded'] = float(f['days_to_funded'].quantile(0.9)) if len(f) else np.nan
        out['mean_fees'] = float(res['fees'].mean())
        fr = f[~((f['funded_outcome'] == 'alive') & (f['n_payouts'] == 0) & f['funded_censored'].astype(bool))] if len(f) else f
        out['p_first_payout_given_funded'] = float((fr['n_payouts'] >= 1).mean()) if len(fr) else np.nan
        out['p_first_payout_overall'] = out['p_funded'] * out['p_first_payout_given_funded'] if len(fr) else np.nan
        out['mean_paid_given_funded'] = float(fr['paid'].mean()) if len(fr) else np.nan
        out['expected_net'] = out['p_funded'] * out['mean_paid_given_funded'] - out['mean_fees'] if len(fr) else np.nan
        out['median_days_to_first_payout'] = float(fr['first_payout_day'].dropna().median()) if len(fr) and fr['first_payout_day'].notna().any() else np.nan
        mo = pd.to_datetime(res['start']).dt.to_period('M')
        out['monthly_p_funded'] = {str(k): round(float(v), 2) for k, v in res.groupby(mo)['funded'].mean().items()}
    return df, out


def two_configs(daily, rules=None, sizes=(5, 8, 10, 12, 15, 20, 25, 30, 40)):
    """Scan sizing for the Aggressive (fast pass, first payout) and Safe (one eval reaches funded) objectives.
    Returns a table per size and policy family."""
    rules = rules or Rules()
    rows = []
    for n in sizes:
        for pol_name, es, fp in [
            ('constant', eval_constant(n), funded_room(min(n, 20), 900.0, max(1, n // 3))),
            ('room', eval_room(n, 900.0, max(1, n // 2)), funded_room(min(n, 20), 900.0, max(1, n // 3))),
            ('cushion', eval_cushion(n, 500.0, 40), funded_room(min(n, 20), 900.0, max(1, n // 3))),
        ]:
            for att in (1, 3):
                _, s = campaign_mc(daily, es, fp, rules, max_attempts=att)
                rows.append({'micros': n, 'policy': pol_name, 'attempts': att, **{k: v for k, v in s.items() if k != 'monthly_p_funded'},
                             'min_monthly_p_funded': min(s.get('monthly_p_funded', {0: np.nan}).values()) if s.get('monthly_p_funded') else np.nan})
    return pd.DataFrame(rows)


if __name__ == '__main__':
    from backtest.portfolio import combine
    from backtest.run import run_strategy
    ap = argparse.ArgumentParser(); ap.add_argument('--legs', default=None); ap.add_argument('--strategy', default=None); ap.add_argument('--contract', default='MES')
    ap.add_argument('--params', default='{}'); ap.add_argument('--start', default='2025-01-01'); ap.add_argument('--end', default='2026-09-30'); ap.add_argument('--out', default=None)
    a = ap.parse_args()
    if a.legs:
        _, daily = combine(json.loads(a.legs), a.start, a.end)
    else:
        _, daily, _ = run_strategy(a.strategy, a.contract, a.start, a.end, json.loads(a.params))
    t = two_configs(daily)
    with pd.option_context('display.width', 250, 'display.max_rows', 500):
        print(t.round(3).to_string(index=False))
    if a.out:
        t.to_csv(a.out, index=False)
