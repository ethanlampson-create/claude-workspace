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


WARMUP_DAYS = 45  # calendar days of extra history loaded before `start` so indicators are warm on the first day


def thin_sessions(df1, contract):
    """day_ids of sessions with fewer than 80% of the typical number of RTH bars (holiday / early-close / feed gaps).
    Fills on those sessions are at holiday liquidity, so entries are skipped there by default."""
    from backtest.data import hm
    o, c = hm(contract.rth_open), hm(contract.rth_close)
    rth = df1[(df1['tod'] >= o) & (df1['tod'] < c)].groupby('day_id').size()
    rth = rth.reindex(range(int(df1['day_id'].max()) + 1)).fillna(0)
    typical = rth[rth > 0].median() if (rth > 0).any() else 0
    return rth.index.values[rth.values < 0.8 * typical]


def prepare(strategy_id, contract_name, start, end, params=None, df1=None, skip_thin_sessions=True):
    """Load data with warm-up, generate intents, forbid entries before `start` and (by default) on thin sessions.
    Returns (df1, intents, contract)."""
    contract = CONTRACTS[contract_name]
    if df1 is None:
        df1 = load_1m(contract.data_symbol, (pd.Timestamp(start) - pd.Timedelta(days=WARMUP_DAYS)).strftime('%Y-%m-%d'), end)
    mod = strategies.load(strategy_id)
    it = mod.generate(df1, contract, params or {})
    it.allow_entry &= (df1['session'].values >= pd.Timestamp(start).date())
    if skip_thin_sessions:
        thin = thin_sessions(df1, contract)
        if len(thin):
            it.allow_entry &= ~np.isin(df1['day_id'].values, thin)
    return df1, it, contract


def slice_window(trades, daily, start):
    """Keep sessions >= start in both tables; trades are filtered by their SESSION (an evening trade of the first
    session belongs to the window), falling back to entry date when no session column is present."""
    s = pd.Timestamp(start).date()
    daily = daily[daily['session'] >= s].reset_index(drop=True)
    if len(trades):
        if 'session' in trades:
            keep = trades['session'].values >= s
        elif 'day_id' in trades and 'session' in daily and len(daily):
            keep = np.ones(len(trades), bool)
        else:
            keep = pd.to_datetime(trades['entry_ts']).dt.tz_convert('America/New_York').dt.date >= s
        trades = trades[keep].reset_index(drop=True)
    return trades, daily


def run_strategy(strategy_id, contract_name, start, end, params=None, slip_ticks=None, df1=None):
    df1, it, contract = prepare(strategy_id, contract_name, start, end, params, df1)
    trades, daily = engine.run(it, contract, slip_ticks=slip_ticks)
    trades, daily = slice_window(trades, daily, start)
    return trades, daily, metrics(trades, daily)


def run_strategy_bars(strategy_id, contract_name, start, end, params=None, slip_ticks=None, df1=None):
    """Like run_strategy but also returns the per-bar intraday equity (ts, session, eq_low, eq_close) for the window."""
    df1, it, contract = prepare(strategy_id, contract_name, start, end, params, df1)
    trades, daily, bars = engine.run(it, contract, slip_ticks=slip_ticks, return_bars=True)
    sessions = daily['session'].values
    bars = bars.copy(); bars['session'] = sessions[bars['day_id'].values]
    s0 = pd.Timestamp(start).date()
    bars = bars[bars['session'] >= s0].reset_index(drop=True)[['ts', 'session', 'eq_low', 'eq_close']]
    trades, daily = slice_window(trades, daily, start)
    return trades, daily, bars, metrics(trades, daily)


def micro_daily(daily, contract):
    """Convert a per-MINI daily table to per-MICRO: divide the price P&L by the micro ratio but re-charge the micro
    commission per trade (a micro round trip costs more than a tenth of a mini round trip). Prefer simulating the
    micro contract directly; this conversion is exact for pnl and approximate for min_eq/max_eq on multi-trade days."""
    from backtest.contracts import MICRO_OF
    if contract.name in MICRO_OF:
        micro = CONTRACTS[MICRO_OF[contract.name]]
        d = daily.copy(); k = d['trades'].values
        for col in ('pnl', 'min_eq', 'max_eq'):
            d[col] = (d[col].values + contract.commission_rt * k) / contract.micro_ratio - micro.commission_rt * k
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
