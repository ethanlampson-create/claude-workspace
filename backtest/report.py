"""Diagnostics for a strategy run: where does the P&L come from and where is it lost?
python3 -m backtest.report --strategy orb --contract MES --start 2025-01-01 --end 2026-09-30 [--params '{}']
"""
import argparse, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.run import run_strategy
from backtest.metrics import metrics, fmt
from backtest.data import PQ


def breakdown(trades: pd.DataFrame, daily: pd.DataFrame) -> dict:
    out = {}
    if not len(trades):
        return {'note': 'no trades'}
    t = trades.copy()
    t['entry_ts'] = pd.to_datetime(t['entry_ts']); t['exit_ts'] = pd.to_datetime(t['exit_ts'])
    t['hour'] = t['entry_ts'].dt.hour; t['dow'] = t['entry_ts'].dt.dayofweek; t['month'] = t['entry_ts'].dt.to_period('M').astype(str)
    t['dur_min'] = (t['exit_ts'] - t['entry_ts']).dt.total_seconds() / 60
    def agg(g):
        return pd.DataFrame({'n': g.size(), 'net': g['pnl'].sum().round(1), 'avg': g['pnl'].mean().round(2), 'win': (g['pnl'].apply(lambda x: (x > 0).mean())).round(2)})
    out['by_hour'] = agg(t.groupby('hour')).to_dict('index')
    out['by_dow'] = agg(t.groupby('dow')).to_dict('index')
    out['by_month'] = agg(t.groupby('month')).to_dict('index')
    out['by_side'] = agg(t.groupby('side')).to_dict('index')
    out['by_reason'] = agg(t.groupby('reason')).to_dict('index')
    out['duration_quartiles_min'] = t['dur_min'].quantile([.25, .5, .75]).round(1).to_dict()
    out['mae_mfe_pts'] = {'mae_med': float(t['mae_pts'].median()), 'mfe_med': float(t['mfe_pts'].median()),
                          'winners_mae_med': float(t.loc[t.pnl > 0, 'mae_pts'].median()) if (t.pnl > 0).any() else None,
                          'losers_mfe_med': float(t.loc[t.pnl <= 0, 'mfe_pts'].median()) if (t.pnl <= 0).any() else None}
    # VIX regime
    try:
        vix = pd.read_parquet(os.path.join(PQ, 'VIX_1d.parquet'))['close']; vix.index = pd.to_datetime(vix.index).date
        t['vix'] = t['entry_ts'].dt.date.map(vix).ffill()
        t['vix_bucket'] = pd.cut(t['vix'], [0, 15, 20, 25, 35, 100], labels=['<15', '15-20', '20-25', '25-35', '>35'])
        out['by_vix'] = agg(t.groupby('vix_bucket', observed=True)).to_dict('index')
    except Exception as e:
        out['by_vix'] = f'n/a {e}'
    d = daily.copy(); d['session'] = pd.to_datetime(d['session'])
    out['daily'] = {'pos_days': int((d.pnl > 0).sum()), 'neg_days': int((d.pnl < 0).sum()), 'flat_days': int((d.pnl == 0).sum()),
                    'avg_pos': float(d.loc[d.pnl > 0, 'pnl'].mean()) if (d.pnl > 0).any() else 0, 'avg_neg': float(d.loc[d.pnl < 0, 'pnl'].mean()) if (d.pnl < 0).any() else 0,
                    'worst5': d.nsmallest(5, 'pnl')[['session', 'pnl']].astype(str).values.tolist(), 'best5': d.nlargest(5, 'pnl')[['session', 'pnl']].astype(str).values.tolist(),
                    'max_consec_losing_days': int(max((len(list(g)) for k, g in __import__('itertools').groupby(d.pnl < 0) if k), default=0))}
    # streaks of trades
    s = np.sign(t['pnl'].values); mx = 0; cur = 0
    for v in s:
        cur = cur + 1 if v <= 0 else 0; mx = max(mx, cur)
    out['max_consec_losing_trades'] = int(mx)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--strategy', required=True); ap.add_argument('--contract', default='MES')
    ap.add_argument('--start', default='2025-01-01'); ap.add_argument('--end', default='2026-09-30'); ap.add_argument('--params', default='{}')
    a = ap.parse_args()
    trades, daily, m = run_strategy(a.strategy, a.contract, a.start, a.end, json.loads(a.params))
    print(fmt(m)); print(json.dumps(breakdown(trades, daily), indent=1, default=str))
