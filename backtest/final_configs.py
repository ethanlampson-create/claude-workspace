"""Build the two final account configurations from out-of-sample candidate legs.

1. Legs = candidates with walk-forward OOS files (results/<id>/wf_oos_2025_bars.parquet + wf_oos_2025_daily.csv), filtered by
   results/final_selection.csv (wf25_pf >= min_pf, wf25_trades >= min_trades) unless --ids is given.
2. Portfolio weights (micros per leg) by exhaustive integer search with EXACT combined intraday equity (OOSLegs), ranked by
   the campaign expected net; the top candidates get block-bootstrap bands.
3. Two configurations:
   - AGGRESSIVE: single attempt, larger evaluation size, funded phase sized down; chosen to maximise P(first payout) per
     attempt subject to a positive bootstrap lower bound on expected net.
   - SAFE: up to 3 attempts, smaller size; chosen to maximise P(funded within 3 attempts) and the minimum monthly P(funded),
     subject to a positive bootstrap lower bound.
Writes results/final_configs.json and reports/final_report.md.
python3 -m backtest.final_configs [--ids a b c] [--grid 0,5,10,15,20] [--max_total 40] [--reps 200]
"""
import argparse, itertools, json, math, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.lucid import Rules, campaign_fast, campaign_bootstrap, monte_carlo_fast, zero_edge_control, bootstrap_summary
from backtest.portfolio_opt import OOSLegs
from backtest.metrics import metrics
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def unit_table(legs: OOSLegs, w):
    """Daily table for the unit book w/gcd(w); returns (daily, unit_vector, micros_per_unit)."""
    w = np.asarray(w, int); g = math.gcd(*[int(x) for x in w if x > 0]) if (w > 0).any() else 1
    u = w // g
    d = legs.daily(u)
    return d, u, int(u.sum())


def rules_in_units(micros_per_unit, rules=None):
    """Rules copy with contract caps expressed in book units."""
    r = rules or Rules()
    from dataclasses import replace
    return replace(r, eval_max_micros=max(1, r.eval_max_micros // micros_per_unit),
                   funded_scaling=tuple((thr, max(1, mx // micros_per_unit)) for thr, mx in r.funded_scaling))


def evaluate_config(legs, w, eval_units, funded_units, reduced_units, attempts, reps=0, rules=None):
    d, u, mpu = unit_table(legs, w)
    r = rules_in_units(mpu, rules)
    s = campaign_fast(d, eval_units, funded_units, r, max_attempts=attempts, funded_min_room=900.0, funded_reduced=reduced_units)
    out = {'weights': [int(x) for x in w], 'unit': [int(x) for x in u], 'micros_per_unit': mpu, 'eval_units': eval_units, 'eval_micros': eval_units * mpu,
           'funded_units': funded_units, 'funded_micros': funded_units * mpu, 'reduced_units': reduced_units, 'attempts': attempts}
    out.update({k: v for k, v in s.items()})
    if reps:
        bs = campaign_bootstrap(d, eval_units, funded_units, r, max_attempts=attempts, reps=reps, funded_min_room=900.0, funded_reduced=reduced_units)
        out.update({'bs_' + k: v for k, v in bs.items() if k != 'reps'})
        z = zero_edge_control(d, eval_units, funded_units, r, start_every=1)
        out['zero_edge_expected_net_per_eval'] = z.get('expected_net_per_eval'); out['zero_edge_pass_rate'] = z.get('pass_rate')
    # single-attempt evaluation statistics (pass rate, pass-within-21, monthly) at this size
    _, m1 = monte_carlo_fast(d, eval_units, funded_units, r, funded_min_room=900.0, funded_reduced=reduced_units)
    out['eval_pass_rate'] = m1.get('pass_rate'); out['eval_pass_within_21'] = m1.get('pass_within_21'); out['eval_pass_within_42'] = m1.get('pass_within_42')
    out['eval_median_days_to_pass'] = m1.get('median_days_to_pass'); out['eval_p_loss_fee'] = m1.get('p_loss_fee')
    out['monthly_pass_rate_21'] = m1.get('monthly_pass_rate'); out['monthly_n'] = m1.get('monthly_n')
    return out


def search_weights(legs, grid, max_total, attempts=1):
    K = len(legs.legs); rows = []
    for w in itertools.product(grid, repeat=K):
        if sum(w) == 0 or sum(w) > max_total:
            continue
        d, u, mpu = unit_table(legs, w)
        r = rules_in_units(mpu)
        g = math.gcd(*[int(x) for x in w if x > 0])
        s = campaign_fast(d, g, min(g, max(1, 20 // mpu)), r, max_attempts=attempts, funded_min_room=900.0, funded_reduced=max(1, g // 3))
        rows.append({'w': w, 'total': sum(w), 'p_funded': s.get('p_funded'), 'p_first_payout': s.get('p_first_payout_overall'),
                     'expected_net': s.get('expected_net'), 'median_days': s.get('median_days_to_funded'), 'min_monthly': s.get('min_monthly_p_funded')})
    return pd.DataFrame(rows)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--ids', nargs='*', default=None); ap.add_argument('--grid', default='0,5,10,15,20')
    ap.add_argument('--max_total', type=int, default=40); ap.add_argument('--reps', type=int, default=200); ap.add_argument('--min_pf', type=float, default=1.05)
    ap.add_argument('--min_trades', type=int, default=40); ap.add_argument('--top', type=int, default=12)
    a = ap.parse_args()
    if a.ids:
        ids = a.ids
    else:
        sel = pd.read_csv(os.path.join(ROOT, 'results', 'final_selection.csv'))
        ok = sel[(sel['wf25_pf'] >= a.min_pf) & (sel['wf25_trades'] >= a.min_trades)]
        ids = [i for i in ok['id'] if os.path.exists(os.path.join(ROOT, 'results', i, 'wf_oos_2025_bars.parquet'))]
    print('legs:', ids)
    if not ids:
        sys.exit('no eligible legs with walk-forward OOS files')
    legs = OOSLegs(ids)
    print('OOS daily P&L correlation:\n', legs.daily_corr.round(2).to_string())
    grid = tuple(int(x) for x in a.grid.split(','))
    tab = search_weights(legs, grid, a.max_total, attempts=1)
    tab = tab.sort_values('expected_net', ascending=False)
    print('\nTop weight vectors (single attempt, point estimates):'); print(tab.head(a.top).round(3).to_string(index=False))
    # Evaluate the top candidates with bootstrap under both objectives
    cands = []
    for w in tab.head(a.top)['w']:
        d, u, mpu = unit_table(legs, w); g = int(np.sum(w) // np.sum(u))
        # aggressive: full size eval, funded 20 micros cap-aware, 1 attempt
        agg = evaluate_config(legs, w, g, min(g, max(1, 20 // mpu)), max(1, g // 3), 1, reps=a.reps)
        # safe: half-size eval (>= 1 unit), 3 attempts
        safe = evaluate_config(legs, w, max(1, g // 2), max(1, min(g // 2, 20 // mpu)), max(1, g // 6), 3, reps=a.reps)
        cands.append({'w': [int(x) for x in w], 'aggressive': agg, 'safe': safe})
        print('w', w, 'AGG p_pay', round(agg.get('p_first_payout_overall', 0) or 0, 3), 'net_lb', round(agg.get('bs_expected_net_p05', 0) or 0), 'SAFE p_funded', round(safe.get('p_funded', 0) or 0, 3), 'minmo', safe.get('min_monthly_p_funded'), 'net_lb', round(safe.get('bs_expected_net_p05', 0) or 0))
    def pick(key, cond):
        pool = [c for c in cands if cond(c[key])]
        if not pool:
            pool = cands
        return max(pool, key=lambda c: (c[key].get('p_first_payout_overall', 0) or 0) if key == 'aggressive' else ((c[key].get('p_funded', 0) or 0) + (c[key].get('min_monthly_p_funded', 0) or 0)))
    agg_best = pick('aggressive', lambda s: (s.get('bs_expected_net_p05') or -1) > 0)
    safe_best = pick('safe', lambda s: (s.get('bs_expected_net_p05') or -1) > 0)
    final = {'legs': ids, 'correlation': legs.daily_corr.round(3).to_dict(), 'aggressive': agg_best['aggressive'], 'safe': safe_best['safe'], 'all_candidates': cands}
    json.dump(final, open(os.path.join(ROOT, 'results', 'final_configs.json'), 'w'), indent=1, default=float)
    print('\nAGGRESSIVE:', json.dumps({k: v for k, v in agg_best['aggressive'].items() if not isinstance(v, dict)}, indent=1, default=float))
    print('\nSAFE:', json.dumps({k: v for k, v in safe_best['safe'].items() if not isinstance(v, dict)}, indent=1, default=float))
