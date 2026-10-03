"""Grid search, Lucid sizing optimisation and multi-period robustness for a strategy.

python3 -m backtest.batch --strategy orb --contract MES --periods 2025-01-01:2026-09-30 2023-01-01:2024-12-31 \
    [--grid '{"rr":[1,2]}'] [--jobs 4] [--out results/orb_MES]
Outputs one CSV row per (period, params) with trade metrics and the best Lucid sizing found by `lucid_scan`.
"""
import argparse, itertools, json, os, sys, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.contracts import CONTRACTS
from backtest.data import load_1m
from backtest import engine
from backtest.metrics import metrics
from backtest.lucid import Rules, monte_carlo, constant_micros
from backtest.run import prepare, slice_window, WARMUP_DAYS
import strategies


def _warm(start):
    return (pd.Timestamp(start) - pd.Timedelta(days=WARMUP_DAYS)).strftime('%Y-%m-%d')

MICRO_SCAN = (5, 10, 15, 20, 30, 40)


def to_micro(daily, contract):
    from backtest.run import micro_daily
    return micro_daily(daily, contract)


def lucid_scan(daily_micro, rules=None, micros=MICRO_SCAN, start_every=1, funded_same=True, min_profit_to_request=4000.0):
    """Run the Lucid Monte Carlo for several contract sizes; return the per-size summary table and the best row
    (max expected_net_per_eval subject to pass_rate>0)."""
    rules = rules or Rules()
    rows = []
    for m in micros:
        fm = m if funded_same else min(m, 20)
        _, s = monte_carlo(daily_micro, m, constant_micros(fm), rules, start_every=start_every, min_profit_to_request=min_profit_to_request)
        s = {k: v for k, v in s.items() if k != 'monthly_pass_rate'}
        mp = monte_carlo  # noqa
        s['micros'] = m; rows.append(s)
    t = pd.DataFrame(rows)
    best = t.sort_values('expected_net_per_eval', ascending=False).iloc[0] if 'expected_net_per_eval' in t and t['expected_net_per_eval'].notna().any() else t.iloc[0]
    return t, best


def _combos(grid):
    keys = list(grid.keys())
    for vals in itertools.product(*[grid[k] for k in keys]):
        yield dict(zip(keys, vals))


_DF = {}

def _worker(args):
    strategy_id, contract_name, start, end, params, slip, do_lucid = args
    contract = CONTRACTS[contract_name]
    key = (contract.data_symbol, start, end)
    if key not in _DF:
        _DF[key] = load_1m(contract.data_symbol, _warm(start), end)
    df1 = _DF[key]
    try:
        df1, it, contract = prepare(strategy_id, contract_name, start, end, params, df1)
        trades, daily = engine.run(it, contract, slip_ticks=slip)
        trades, daily = slice_window(trades, daily, start)
        m = metrics(trades, daily)
        row = {'strategy': strategy_id, 'contract': contract_name, 'start': start, 'end': end, 'params': json.dumps(params)}
        row.update({k: v for k, v in m.items() if k != 'monthly'})
        if do_lucid and len(trades) > 5:
            t, best = lucid_scan(to_micro(daily, contract))
            row.update({'best_micros': int(best['micros']), 'pass_rate': best['pass_rate'], 'p_first_payout_uncond': best.get('p_first_payout_unconditional'),
                        'exp_net_per_eval': best.get('expected_net_per_eval'), 'median_days_to_pass': best.get('median_days_to_pass'),
                        'p_first_payout_given_pass': best.get('p_first_payout_given_pass')})
        return row
    except Exception as e:
        return {'strategy': strategy_id, 'contract': contract_name, 'start': start, 'end': end, 'params': json.dumps(params), 'error': repr(e)}


def grid_search(strategy_id, contract_name, periods, grid=None, base_params=None, jobs=4, slip=None, do_lucid=True):
    mod = strategies.load(strategy_id)
    grid = grid if grid is not None else getattr(mod, 'GRID', {})
    base = {**(base_params or {})}
    combos = [dict(base, **c) for c in _combos(grid)] if grid else [base]
    tasks = [(strategy_id, contract_name, s, e, c, slip, do_lucid) for (s, e) in periods for c in combos]
    # preload data in parent so forked workers share it
    for (s, e) in periods:
        _DF[(CONTRACTS[contract_name].data_symbol, s, e)] = load_1m(CONTRACTS[contract_name].data_symbol, _warm(s), e)
    if jobs > 1 and len(tasks) > 1:
        import multiprocessing as mp
        with mp.get_context('fork').Pool(jobs) as pool:
            rows = pool.map(_worker, tasks, chunksize=1)
    else:
        rows = [_worker(t) for t in tasks]
    return pd.DataFrame(rows)


def robustness(df: pd.DataFrame) -> dict:
    """Fraction of grid points profitable, median/best net, and rank stability across periods."""
    out = {}
    ok = df[df.get('error').isna()] if 'error' in df else df
    for (s, e), g in ok.groupby(['start', 'end']):
        out[f'{s}..{e}'] = {'n': len(g), 'pct_profitable': float((g['net'] > 0).mean()), 'median_net': float(g['net'].median()),
                            'best_net': float(g['net'].max()), 'median_pf': float(g['profit_factor'].replace(np.inf, np.nan).median()),
                            'best_pass_rate': float(g['pass_rate'].max()) if 'pass_rate' in g else np.nan}
    periods = list(ok.groupby(['start', 'end']).groups.keys())
    if len(periods) >= 2:
        a = ok[(ok['start'] == periods[0][0]) & (ok['end'] == periods[0][1])].set_index('params')['net']
        b = ok[(ok['start'] == periods[1][0]) & (ok['end'] == periods[1][1])].set_index('params')['net']
        j = pd.concat([a, b], axis=1, join='inner'); j.columns = ['a', 'b']
        out['rank_corr_first_two_periods'] = float(j['a'].rank().corr(j['b'].rank())) if len(j) > 2 else np.nan
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--strategy', required=True); ap.add_argument('--contract', default='MES')
    ap.add_argument('--periods', nargs='+', default=['2025-01-01:2026-09-30'])
    ap.add_argument('--grid', default=None); ap.add_argument('--base', default='{}'); ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--slip', type=float, default=None); ap.add_argument('--no-lucid', action='store_true'); ap.add_argument('--out', default=None)
    a = ap.parse_args()
    periods = [tuple(p.split(':')) for p in a.periods]
    t0 = time.time()
    df = grid_search(a.strategy, a.contract, periods, json.loads(a.grid) if a.grid else None, json.loads(a.base), a.jobs, a.slip, not a.no_lucid)
    cols = [c for c in ['start', 'params', 'trades', 'net', 'win_rate', 'profit_factor', 'max_dd_intraday', 'sharpe_daily_ann', 'pct_pos_days', 'largest_day_share',
                        'best_micros', 'pass_rate', 'p_first_payout_uncond', 'exp_net_per_eval', 'error'] if c in df]
    with pd.option_context('display.width', 250, 'display.max_colwidth', 60, 'display.max_rows', 500):
        print(df[cols].sort_values(['start', 'net'], ascending=[True, False]).to_string(index=False))
    print(json.dumps(robustness(df), indent=1, default=float))
    print(f'{len(df)} runs in {time.time()-t0:.0f}s')
    if a.out:
        os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True); df.to_csv(a.out + '.csv', index=False)
