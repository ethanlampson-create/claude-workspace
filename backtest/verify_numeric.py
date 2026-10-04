"""Agent-free numeric verification of a strategy's fixed parameters: MAIN, PRIOR, 2015-2022 history, 2020 alone,
MAIN with 2-tick slippage, and top-10-day share of MAIN net. Writes results/<id>/verify_numeric.json.
python3 -m backtest.verify_numeric --ids a b c
"""
import argparse, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.run import run_strategy
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERIODS = {'main': ('2025-01-01', '2026-09-30'), 'prior': ('2023-01-01', '2024-12-31'), 'hist_2015_2022': ('2015-01-01', '2022-12-31'), 'y2020': ('2020-01-01', '2020-12-31')}


def verify(id_):
    j = json.load(open(os.path.join(ROOT, 'results', id_, 'final.json')))
    contract = j.get('contract') or 'MES'; params = j.get('params') or {}
    out = {'id': id_, 'contract': contract, 'params': params}
    for name, (s, e) in PERIODS.items():
        try:
            tr, d, m = run_strategy(id_, contract, s, e, params)
            out[name] = {'trades': m.get('trades'), 'net': m.get('net'), 'pf': m.get('profit_factor'), 'sharpe': m.get('sharpe_daily_ann'), 'pos_months': m.get('pct_pos_months'), 'dd_intra': m.get('max_dd_intraday')}
            if name == 'main' and len(d):
                dd = d.sort_values('pnl', ascending=False)
                out['main_top10_share'] = float(dd['pnl'].head(10).sum() / dd['pnl'].sum()) if dd['pnl'].sum() > 0 else None
                mo = pd.Series(d['pnl'].values, index=pd.to_datetime(d['session'])).resample('ME').sum()
                out['main_largest_month_share'] = float(mo.max() / mo.sum()) if mo.sum() > 0 else None
        except Exception as ex:
            out[name] = {'error': repr(ex)}
    try:
        tr, d, m = run_strategy(id_, contract, *PERIODS['main'], params, slip_ticks=2)
        out['main_slip2'] = {'trades': m.get('trades'), 'net': m.get('net'), 'pf': m.get('profit_factor')}
    except Exception as ex:
        out['main_slip2'] = {'error': repr(ex)}
    h = out.get('hist_2015_2022', {}); y = out.get('y2020', {})
    # ex-2020 profit factor approximated from gross wins/losses would need trade tables; report both periods instead
    out['criteria'] = {'hist_pf_ge_1': (h.get('pf') or 0) >= 1.0, 'slip2_pf_ge_1': (out['main_slip2'].get('pf') or 0) >= 1.0,
                       'prior_pf_ge_1': (out.get('prior', {}).get('pf') or 0) >= 1.0}
    json.dump(out, open(os.path.join(ROOT, 'results', id_, 'verify_numeric.json'), 'w'), indent=1, default=float)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--ids', nargs='+', required=True); a = ap.parse_args()
    rows = []
    for id_ in a.ids:
        o = verify(id_)
        rows.append({'id': id_, 'contract': o['contract'], 'main_pf': o.get('main', {}).get('pf'), 'prior_pf': o.get('prior', {}).get('pf'), 'hist15_22_pf': o.get('hist_2015_2022', {}).get('pf'),
                     'hist_trades': o.get('hist_2015_2022', {}).get('trades'), 'y2020_pf': o.get('y2020', {}).get('pf'), 'slip2_pf': o.get('main_slip2', {}).get('pf'),
                     'top10_share': o.get('main_top10_share'), 'largest_month_share': o.get('main_largest_month_share'), **{'crit_' + k: v for k, v in o['criteria'].items()}})
        print(rows[-1], flush=True)
    df = pd.DataFrame(rows)
    with pd.option_context('display.width', 250):
        print(df.round(3).to_string(index=False))
