"""Run a strategy backtest and (optionally) the Lucid Monte Carlo.
Usage: python3 -m backtest.run --strategy orb --contract MES --start 2025-01-01 --end 2026-09-30 [--params '{"rr":2}'] [--mc --micros 10]
"""
import argparse, json, os, sys, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.contracts import CONTRACTS
from backtest.data import load_1m
from backtest import engine
from backtest.metrics import metrics, fmt
from backtest.lucid import Rules, monte_carlo, constant_micros
import strategies


def run_strategy(strategy_id, contract_name, start, end, params=None, slip_ticks=None):
    contract = CONTRACTS[contract_name]
    df1 = load_1m(contract.data_symbol, start, end)
    mod = strategies.load(strategy_id)
    it = mod.generate(df1, contract, params or {})
    trades, daily = engine.run(it, contract, slip_ticks=slip_ticks)
    return trades, daily, metrics(trades, daily)


def micro_daily(daily, contract):
    """Convert per-contract daily table to per-MICRO-contract (if a mini was simulated)."""
    if contract.name in ('ES', 'NQ', 'GC', 'CL'):
        d = daily.copy(); d['pnl'] /= contract.micro_ratio; d['min_eq'] /= contract.micro_ratio; d['max_eq'] /= contract.micro_ratio
        return d
    return daily


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--strategy', required=True); ap.add_argument('--contract', default='MES')
    ap.add_argument('--start', default='2025-01-01'); ap.add_argument('--end', default='2026-09-30')
    ap.add_argument('--params', default='{}'); ap.add_argument('--mc', action='store_true'); ap.add_argument('--micros', type=int, default=10)
    ap.add_argument('--funded_micros', type=int, default=10); ap.add_argument('--slip', type=float, default=None)
    ap.add_argument('--save', default=None)
    a = ap.parse_args()
    t0 = time.time()
    trades, daily, m = run_strategy(a.strategy, a.contract, a.start, a.end, json.loads(a.params), a.slip)
    print(f"[{a.strategy} {a.contract} {a.start}..{a.end}] {fmt(m)}  ({time.time()-t0:.1f}s)")
    if a.mc:
        rules = Rules()
        d = micro_daily(daily, CONTRACTS[a.contract])
        df, s = monte_carlo(d, a.micros, constant_micros(a.funded_micros), rules)
        print(json.dumps({k: v for k, v in s.items() if k != 'monthly_pass_rate'}, indent=1, default=float))
        print('monthly pass rate:', s.get('monthly_pass_rate'))
    if a.save:
        os.makedirs(os.path.dirname(a.save) or '.', exist_ok=True)
        trades.to_csv(a.save + '_trades.csv', index=False); daily.to_csv(a.save + '_daily.csv', index=False)
        json.dump(m, open(a.save + '_metrics.json', 'w'), indent=1, default=float)
