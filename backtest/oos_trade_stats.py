"""Replay the walk-forward out-of-sample folds for a strategy (params per quarter from results/<id>/walkforward.json),
collect every OOS trade with its initial risk, and report trade count, win rate, mean R and largest-trade share.
1R = |fill - initial protective stop| x point value (per contract); R multiple = net trade P&L (after costs) / 1R.
python3 -m backtest.oos_trade_stats --ids orb_close30 mr_gapfade orb_dbl
"""
import argparse, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.run import prepare, slice_window
from backtest import engine
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fold_trades(id_, contract, s, e, params):
    df1, it, c = prepare(id_, contract, s, e, params)
    tr, d = engine.run(it, c)
    tr, d = slice_window(tr, d, s)
    if not len(tr):
        return tr, d
    ts = pd.DatetimeIndex(df1['ts'])
    pos = ts.get_indexer(pd.DatetimeIndex(tr['entry_ts']))
    # the signal is placed at the entry bar for these market-entry strategies; fall back to the last signal at or before it
    sig_idx = np.flatnonzero(it.sig != 0)
    k = sig_idx[np.searchsorted(sig_idx, pos, side='right') - 1]
    sp = it.stop_px[k]; spts = it.stop_pts[k]
    risk_pts = np.where(np.isnan(sp), spts, np.abs(tr['entry_px'].values - sp))
    tr = tr.copy(); tr['risk_usd'] = risk_pts * c.point_value; tr['R'] = tr['pnl'] / tr['risk_usd']
    tr['fold_params'] = json.dumps(params)
    return tr, d


def stats(id_):
    w = json.load(open(os.path.join(ROOT, 'results', id_, 'walkforward.json')))
    contract = w['contract']; trs = []
    for p in w['wf_path']:
        s, e = p['oos'].split('..')
        if e < '2025-01-01':
            continue
        s = max(s, '2025-01-01')
        tr, d = fold_trades(id_, contract, s, e, p['params'])
        trs.append(tr)
    t = pd.concat(trs).reset_index(drop=True)
    net = t['pnl'].sum(); wins = t[t['pnl'] > 0]
    return t, {'id': id_, 'contract': contract, 'trades': int(len(t)), 'net_per_micro': round(float(net), 2), 'win_rate': round(float((t['pnl'] > 0).mean()), 3),
               'mean_R': round(float(t['R'].mean()), 3), 'median_R': round(float(t['R'].median()), 3), 'avg_win_R': round(float(wins['R'].mean()), 3),
               'avg_loss_R': round(float(t.loc[t['pnl'] <= 0, 'R'].mean()), 3), 'avg_risk_usd_per_micro': round(float(t['risk_usd'].mean()), 2),
               'largest_trade_usd': round(float(t['pnl'].max()), 2), 'largest_trade_share_of_net': round(float(t['pnl'].max() / net), 3) if net > 0 else None,
               'largest_trade_date': str(pd.Timestamp(t.loc[t['pnl'].idxmax(), 'entry_ts']).date()),
               'largest_trade_share_of_gross_profit': round(float(t['pnl'].max() / wins['pnl'].sum()), 3),
               'wf25_net_reported': round(float(w['wf_2025']['net']), 2), 'exits': t['reason'].value_counts().to_dict(), 'sides': t['side'].value_counts().to_dict()}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--ids', nargs='+', required=True); a = ap.parse_args()
    out = {}
    for id_ in a.ids:
        t, s = stats(id_); out[id_] = s
        t.to_csv(os.path.join(ROOT, 'results', id_, 'wf_oos_2025_trades.csv'), index=False)
        print(json.dumps(s, default=str))
    json.dump(out, open(os.path.join(ROOT, 'results', 'oos_trade_stats.json'), 'w'), indent=1, default=str)
