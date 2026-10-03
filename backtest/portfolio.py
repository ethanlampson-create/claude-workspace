"""Combine several strategy legs (possibly on different instruments) into one account-level daily table with an
exact intraday equity path, for the Lucid simulator.

Each leg = dict(strategy=<id>, contract=<MES|MNQ|MGC|ES|...>, params={...}, micros=<int>) ; `micros` is the number
of MICRO contracts for that leg (a mini leg is converted). The combined per-bar equity is the sum of the legs' per-bar
equity series aligned on the 1-minute timestamp grid (forward-filled within a session), so the daily `min_eq` is the
true intraday minimum of the combined account (not the sum of the legs' minima). Output is per 1 "unit" where a unit
is the specified micros per leg; feed it to lucid.monte_carlo with micros=1 (or scale by an integer multiplier).
"""
import json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.contracts import CONTRACTS
from backtest.data import load_1m
from backtest import engine
import strategies


def run_leg(leg, start, end, slip_ticks=None):
    from backtest.run import prepare
    df1, it, contract = prepare(leg['strategy'], leg['contract'], start, end, leg.get('params', {}))
    trades, daily, bars = engine.run(it, contract, slip_ticks=slip_ticks, return_bars=True)
    s0 = pd.Timestamp(start).date()
    keep_d = daily['session'].values >= s0
    daily = daily[keep_d].reset_index(drop=True)
    bars = bars[np.isin(bars['day_id'].values, np.where(keep_d)[0])].reset_index(drop=True)
    bars['day_id'] = bars['day_id'] - int(np.where(keep_d)[0].min()) if keep_d.any() else bars['day_id']
    if len(trades):
        trades = trades[pd.to_datetime(trades['entry_ts']).dt.tz_convert('America/New_York').dt.date >= s0].reset_index(drop=True)
    scale = leg.get('micros', 1) / (contract.micro_ratio if contract.name in ('ES', 'NQ', 'GC', 'CL') else 1)
    trades = trades.copy(); trades['pnl'] *= scale; trades['leg'] = leg['strategy'] + '/' + leg['contract']
    bars = bars.copy(); bars['eq_low'] *= scale; bars['eq_close'] *= scale
    daily = daily.copy(); daily['pnl'] *= scale; daily['min_eq'] *= scale; daily['max_eq'] *= scale
    return trades, daily, bars


def combine(legs, start, end, slip_ticks=None):
    """Returns (trades, daily) for the combined account. daily has session, pnl, min_eq, max_eq, trades."""
    all_tr = []; all_daily = []; eq_low = []; eq_close = []
    for leg in legs:
        tr, d, b = run_leg(leg, start, end, slip_ticks)
        all_tr.append(tr); all_daily.append(d.set_index('session'))
        s_low = pd.Series(b['eq_low'].values, index=b['ts']); s_close = pd.Series(b['eq_close'].values, index=b['ts'])
        sess = pd.Series(d['session'].values[b['day_id'].values], index=b['ts'])
        eq_low.append(pd.DataFrame({'low': s_low, 'close': s_close, 'session': sess}))
    # align on union of timestamps; within a session forward-fill each leg's equity (a leg with no bar at that minute is unchanged)
    frames = []
    for k, f in enumerate(eq_low):
        f = f[~f.index.duplicated()]
        frames.append(f[['low', 'close']].add_suffix(f'_{k}').join(f[['session']].rename(columns={'session': f'session_{k}'})))
    big = pd.concat(frames, axis=1).sort_index()
    sessions = big[[c for c in big.columns if c.startswith('session_')]].bfill(axis=1).iloc[:, 0]
    # the union session label per timestamp: take the first non-null
    big['session'] = sessions
    lows = []; closes = []
    for k in range(len(legs)):
        lo = big[f'low_{k}']; cl = big[f'close_{k}']
        # within each session forward fill; before the leg's first bar of the session its equity is 0
        lo = lo.groupby(big['session']).ffill().fillna(0.0); cl = cl.groupby(big['session']).ffill().fillna(0.0)
        # a leg's intraday low at a timestamp where it has no bar is its last close (position unchanged) -> use close for ffilled points
        has = big[f'low_{k}'].notna()
        lo = lo.where(has, cl)
        lows.append(lo); closes.append(cl)
    tot_low = sum(lows); tot_close = sum(closes)
    g = pd.DataFrame({'low': tot_low, 'close': tot_close, 'session': big['session'].values}, index=big.index).groupby('session')
    daily = pd.DataFrame({'min_eq': g['low'].min().clip(upper=0.0), 'max_eq': g['close'].max().clip(lower=0.0)})
    pnl = sum(d['pnl'].reindex(daily.index).fillna(0.0) for d in all_daily)
    ntr = sum(d['trades'].reindex(daily.index).fillna(0) for d in all_daily)
    daily['pnl'] = pnl; daily['trades'] = ntr.astype(int)
    daily = daily.reset_index()[['session', 'pnl', 'min_eq', 'max_eq', 'trades']]
    trades = pd.concat(all_tr).sort_values('entry_ts').reset_index(drop=True)
    return trades, daily


if __name__ == '__main__':
    import argparse
    from backtest.metrics import metrics, fmt
    from backtest.lucid import Rules, monte_carlo, constant_micros
    ap = argparse.ArgumentParser(); ap.add_argument('--legs', required=True, help='JSON list of legs'); ap.add_argument('--start', default='2025-01-01'); ap.add_argument('--end', default='2026-09-30')
    ap.add_argument('--mult', type=int, default=1, help='multiplier applied to every leg size in the Lucid MC'); ap.add_argument('--mc', action='store_true')
    a = ap.parse_args()
    legs = json.loads(a.legs)
    trades, daily = combine(legs, a.start, a.end)
    m = metrics(trades, daily); print(fmt(m))
    if a.mc:
        df, s = monte_carlo(daily, a.mult, constant_micros(a.mult), Rules())
        print(json.dumps({k: v for k, v in s.items() if k != 'monthly_pass_rate'}, indent=1, default=float))
        print({str(k): round(v, 2) for k, v in s['monthly_pass_rate'].items()})
