"""Calendar-time account statistics for a final configuration on the walk-forward OOS stream (2025-01..data end).

1. Career: one account slot traded continuously from a start date. Eval -> on fail pay a reset and restart next
   session -> on pass run the funded account until it breaches or reaches 5 payouts -> buy a new eval next session.
   Records every fee, payout (gross; trader gets 90%), pass, blow-up and their dates.
2. Per-start statistics over every possible start session: single-attempt pass rate and days to pass, and the path
   to the first payout (evals failed and funded accounts blown before it, days, fees).
Copies of the same strategy on several accounts take identical trades, so N accounts = N x one account.
python3 -m backtest.career
"""
import json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.lucid import Rules, simulate_eval, _mll_update
from backtest.portfolio_opt import OOSLegs
from backtest.final_configs import unit_table, rules_in_units
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_funded(pnl, mn, s, base, reduced, r, min_req=4000.0, min_room=900.0):
    bal = r.start_balance; mll = bal - r.mll_distance; peak = bal; payouts = []; qual = 0; cyc = bal
    for k in range(s, len(pnl)):
        profit = bal - r.start_balance
        cap = r.funded_scaling[0][1]
        for thr, mx in r.funded_scaling:
            if profit >= thr:
                cap = mx
        m = min(base if (bal - mll) >= min_room else reduced, cap)
        if m > 0:
            if bal + mn[k] * m <= mll:
                return 'breach', k, payouts
            dp = pnl[k] * m; bal += dp
            if dp >= r.payout_day_min_profit:
                qual += 1
        peak = max(peak, bal); mll = _mll_update(mll, peak, r)
        if bal <= mll:
            return 'breach', k, payouts
        profit = bal - r.start_balance
        amount = min(r.payout_max, r.payout_frac * profit)
        if qual >= r.payout_min_days and bal - cyc > 0 and amount >= r.payout_min and profit >= min_req:
            payouts.append((k, amount)); bal -= amount; mll = max(mll, r.lock_level); qual = 0; cyc = bal
            if len(payouts) >= r.max_payouts:
                return 'live', k, payouts
    return 'alive', len(pnl) - 1, payouts


def career(pnl, mn, ntr, s, cfg, r, stop_at_first_payout=False):
    ev = []; k = s; new_account = True
    while k < len(pnl):
        fee = r.eval_fee if new_account else r.reset_fee
        e = simulate_eval(pnl, mn, k, cfg['eval_units'], r, 10 ** 6, None, ntr)
        ev.append(('fee', k, fee))
        if e['outcome'] != 'pass':
            if e['outcome'] == 'fail':
                ev.append(('eval_fail', e['end_day'], 0.0)); k = e['end_day'] + 1; new_account = False; continue
            ev.append(('eval_open', e['end_day'], 0.0)); break
        ev.append(('pass', e['end_day'], 0.0))
        out, end, pays = run_funded(pnl, mn, e['end_day'] + 1, cfg['funded_units'], cfg['reduced_units'], r)
        for (pk, amt) in pays:
            ev.append(('payout', pk, amt))
            if stop_at_first_payout:
                return ev
        ev.append(({'breach': 'funded_blown', 'live': 'went_live', 'alive': 'funded_open'}[out], end, 0.0))
        if out == 'alive':
            break
        k = end + 1; new_account = True
    return ev


def summarize_career(ev, sessions, r, cut=None):
    d = pd.DataFrame(ev, columns=['type', 'k', 'amt']); d['date'] = sessions[d['k'].values]
    if cut is not None:
        d = d[d['date'] <= cut]
    fees = d.loc[d.type == 'fee', 'amt'].sum(); gross = d.loc[d.type == 'payout', 'amt'].sum()
    return {'evals_bought': int((d.type == 'fee').sum()), 'evals_failed': int((d.type == 'eval_fail').sum()), 'evals_passed': int((d.type == 'pass').sum()),
            'funded_blown': int((d.type == 'funded_blown').sum()), 'went_live': int((d.type == 'went_live').sum()), 'payouts': int((d.type == 'payout').sum()),
            'gross_payouts': float(gross), 'received_90pct': float(gross * r.split), 'fees': float(fees), 'net': float(gross * r.split - fees),
            'first_payout_date': str(d.loc[d.type == 'payout', 'date'].min()) if (d.type == 'payout').any() else None}


def main():
    c = json.load(open(os.path.join(ROOT, 'results', 'final_configs.json')))
    legs = OOSLegs(c['legs'])
    out = {}
    for name in ('aggressive', 'safe'):
        cfg = c[name]; w = c[name + '_weights']
        d, u, mpu = unit_table(legs, w); r = rules_in_units(mpu)
        pnl = d['pnl'].values; mn = d['min_eq'].values; ntr = d['trades'].values; sess = pd.to_datetime(d['session']).values
        n = len(pnl)
        # 1) career from the first session of 2025
        ev = career(pnl, mn, ntr, 0, cfg, r)
        car = {'through_2025': summarize_career(ev, sess, r, np.datetime64('2025-12-31')), 'through_data_end': summarize_career(ev, sess, r)}
        evd = pd.DataFrame(ev, columns=['type', 'k', 'amt']); evd['date'] = pd.to_datetime(sess[evd['k'].values]).strftime('%Y-%m-%d')
        car['events'] = evd.to_dict('records')
        # careers starting at the first session of each month of 2025 (how much the start date matters)
        months = []
        for m in pd.period_range('2025-01', '2025-12', freq='M'):
            s0 = int(np.argmax(pd.to_datetime(sess).to_period('M') == m))
            sm = summarize_career(career(pnl, mn, ntr, s0, cfg, r), sess, r)
            months.append({'start_month': str(m), **sm})
        car['by_start_month'] = months
        # 2) per-start statistics
        rows = []
        for s in range(n - 2):
            e = simulate_eval(pnl, mn, s, cfg['eval_units'], r, 10 ** 6, None, ntr)
            ev1 = career(pnl, mn, ntr, s, cfg, r, stop_at_first_payout=True)
            types = [x[0] for x in ev1]
            got = 'payout' in types
            pay_k = ev1[-1][1] if got else None
            rows.append({'s': s, 'eval': e['outcome'], 'eval_days': e['days'], 'got_payout': got, 'days_to_first_payout': (pay_k - s + 1) if got else None,
                         'evals_failed_before': types.count('eval_fail'), 'funded_blown_before': types.count('funded_blown'),
                         'fees_to_first_payout': sum(x[2] for x in ev1 if x[0] == 'fee')})
        ps = pd.DataFrame(rows)
        res = ps[ps['eval'].isin(['pass', 'fail'])]
        # funded-account statistics: every funded account started from any eval pass on any start
        fund = []
        for s in sorted(set(int(simulate_eval(pnl, mn, s, cfg['eval_units'], r, 10 ** 6, None, ntr)['end_day']) for s in range(n - 2))):
            pass
        passes = res[res['eval'] == 'pass']
        for s in passes['s']:
            e = simulate_eval(pnl, mn, int(s), cfg['eval_units'], r, 10 ** 6, None, ntr)
            o, end, pays = run_funded(pnl, mn, e['end_day'] + 1, cfg['funded_units'], cfg['reduced_units'], r)
            fund.append({'outcome': o, 'n_payouts': len(pays), 'gross': sum(a for _, a in pays), 'days_to_first': (pays[0][0] - e['end_day']) if pays else None})
        fd = pd.DataFrame(fund); fdr = fd[fd['outcome'] != 'alive'] if len(fd) else fd
        gp = ps[ps['got_payout']]
        out[name] = {
            'weights': dict(zip(c['legs'], w)), 'eval_micros': cfg['eval_micros'], 'funded_micros': cfg['funded_micros'],
            'career_from_2025_01': car,
            'per_start': {
                'n_starts': int(len(ps)), 'eval_pass_rate': float((res['eval'] == 'pass').mean()),
                'avg_days_to_pass': float(passes['eval_days'].mean()), 'median_days_to_pass': float(passes['eval_days'].median()),
                'avg_days_failed_eval_lasted': float(res.loc[res['eval'] == 'fail', 'eval_days'].mean()),
                'p_first_payout_from_one_eval': float(((res['eval'] == 'pass')).mean() * ((fdr['n_payouts'] >= 1).mean() if len(fdr) else np.nan)),
                'p_first_payout_given_funded': float((fdr['n_payouts'] >= 1).mean()) if len(fdr) else None,
                'avg_payouts_per_funded_account': float(fdr['n_payouts'].mean()) if len(fdr) else None,
                'avg_gross_paid_per_funded_account': float(fdr['gross'].mean()) if len(fdr) else None,
                'funded_outcomes': fdr['outcome'].value_counts().to_dict() if len(fdr) else {},
                'avg_days_pass_to_first_payout': float(fd['days_to_first'].dropna().mean()) if len(fd) else None,
                'share_of_starts_reaching_a_payout_before_data_end': float(ps['got_payout'].mean()),
                'avg_days_start_to_first_payout': float(gp['days_to_first_payout'].mean()) if len(gp) else None,
                'median_days_start_to_first_payout': float(gp['days_to_first_payout'].median()) if len(gp) else None,
                'avg_evals_failed_before_first_payout': float(gp['evals_failed_before'].mean()) if len(gp) else None,
                'avg_funded_blown_before_first_payout': float(gp['funded_blown_before'].mean()) if len(gp) else None,
                'avg_fees_until_first_payout': float(gp['fees_to_first_payout'].mean()) if len(gp) else None,
                'max_accounts_blown_before_first_payout': int((gp['evals_failed_before'] + gp['funded_blown_before']).max()) if len(gp) else None,
            }}
    json.dump(out, open(os.path.join(ROOT, 'results', 'career_stats.json'), 'w'), indent=1, default=str)
    for name, o in out.items():
        print('=' * 20, name.upper(), o['weights'], 'eval', o['eval_micros'], 'funded', o['funded_micros'])
        for per in ('through_2025', 'through_data_end'):
            print(' career', per, o['career_from_2025_01'][per])
        print(' per_start', json.dumps(o['per_start'], indent=1, default=str))
        bm = pd.DataFrame(o['career_from_2025_01']['by_start_month'])
        print(bm[['start_month', 'evals_bought', 'evals_failed', 'evals_passed', 'funded_blown', 'payouts', 'received_90pct', 'fees', 'net', 'first_payout_date']].round(0).to_string(index=False))


if __name__ == '__main__':
    main()
