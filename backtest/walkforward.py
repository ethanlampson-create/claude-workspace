"""Walk-forward validation: pick parameters on a trailing in-sample window, trade them on the next out-of-sample
window, roll forward. Reports the concatenated OOS performance (per micro) and the parameter path.

python3 -m backtest.walkforward --strategy orb --contract MES --is_months 12 --oos_months 3 --start 2019-01-01 --end 2026-09-30 [--metric sharpe_daily_ann]
"""
import argparse, json, os, sys, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.batch import grid_search, _combos
from backtest.run import run_strategy
from backtest.metrics import metrics, fmt
import strategies


def walk_forward(strategy_id, contract, start, end, is_months=12, oos_months=3, grid=None, base=None, metric='sharpe_daily_ann', jobs=4, min_trades=30):
    mod = strategies.load(strategy_id)
    grid = grid if grid is not None else getattr(mod, 'GRID', {})
    t0 = pd.Timestamp(start); tend = pd.Timestamp(end)
    oos_daily = []; oos_trades = []; path = []
    cur = t0 + pd.DateOffset(months=is_months)
    while cur < tend:
        is_s = (cur - pd.DateOffset(months=is_months)).strftime('%Y-%m-%d'); is_e = (cur - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        oos_s = cur.strftime('%Y-%m-%d'); oos_e = min(cur + pd.DateOffset(months=oos_months) - pd.Timedelta(days=1), tend).strftime('%Y-%m-%d')
        df = grid_search(strategy_id, contract, [(is_s, is_e)], grid, base, jobs=jobs, do_lucid=False)
        df = df[df.get('error').isna()] if 'error' in df else df
        df = df[df['trades'] >= min_trades] if len(df) else df
        if not len(df):
            cur = cur + pd.DateOffset(months=oos_months); continue
        best = df.sort_values(metric, ascending=False).iloc[0]
        params = json.loads(best['params'])
        tr, d, m = run_strategy(strategy_id, contract, oos_s, oos_e, params)
        oos_daily.append(d); oos_trades.append(tr)
        path.append({'is': f'{is_s}..{is_e}', 'oos': f'{oos_s}..{oos_e}', 'params': params, 'is_metric': float(best[metric]), 'is_net': float(best['net']),
                     'oos_net': float(d['pnl'].sum()), 'oos_trades': int(len(tr)), 'oos_pf': m.get('profit_factor')})
        cur = cur + pd.DateOffset(months=oos_months)
    if not oos_daily:
        return None, None, path
    daily = pd.concat(oos_daily).reset_index(drop=True); trades = pd.concat(oos_trades).reset_index(drop=True)
    return trades, daily, path


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--strategy', required=True); ap.add_argument('--contract', default='MES')
    ap.add_argument('--start', default='2019-01-01'); ap.add_argument('--end', default='2026-09-30'); ap.add_argument('--is_months', type=int, default=12)
    ap.add_argument('--oos_months', type=int, default=3); ap.add_argument('--grid', default=None); ap.add_argument('--base', default='{}')
    ap.add_argument('--metric', default='sharpe_daily_ann'); ap.add_argument('--jobs', type=int, default=4); ap.add_argument('--out', default=None)
    a = ap.parse_args(); t0 = time.time()
    tr, d, path = walk_forward(a.strategy, a.contract, a.start, a.end, a.is_months, a.oos_months, json.loads(a.grid) if a.grid else None, json.loads(a.base), a.metric, a.jobs)
    for p in path:
        print(p)
    if d is not None:
        m = metrics(tr, d); print('OOS concatenated:', fmt(m)); print('OOS monthly:', m.get('monthly'))
        if a.out:
            os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True); d.to_csv(a.out + '_oos_daily.csv', index=False); json.dump({'path': path, 'metrics': m}, open(a.out + '_wf.json', 'w'), indent=1, default=float)
    print(f'{time.time()-t0:.0f}s')
