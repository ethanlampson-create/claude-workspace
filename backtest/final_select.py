"""Final selection: honest out-of-sample evidence for every lab candidate.

For each results/<id>/final.json (or an explicit list), on its best contract:
  1. Walk-forward 2021-01..2026-09 (IS 12 months, OOS 3 months, parameters chosen on trailing data only, coarse grid),
     concatenated OOS daily P&L; metrics for the whole OOS span and for the 2025-01..2026-09 subset.
  2. On the 2025-26 OOS subset: lucid_scan (bootstrap lower-bound sizing, zero-edge control).
  3. The agent's fixed final params re-run on MAIN and PRIOR for reference.
Writes results/<id>/walkforward.json and results/final_selection.csv ranked by the OOS 2025-26 lower-bound expected net.
python3 -m backtest.final_select [--ids a b c] [--jobs 4]
"""
import argparse, glob, json, os, sys, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.walkforward import walk_forward
from backtest.run import run_strategy
from backtest.metrics import metrics
from backtest.batch import lucid_scan
from backtest.lucid import Rules
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = ('2025-01-01', '2026-09-30'); PRIOR = ('2023-01-01', '2024-12-31')


def evaluate(id_, contract, params, jobs=4, wf_start='2021-01-01', is_months=12, oos_months=3, max_combos=24):
    out = {'id': id_, 'contract': contract, 'params': params}
    t0 = time.time()
    tr, d, path = walk_forward(id_, contract, wf_start, MAIN[1], is_months, oos_months, None, params, 'sharpe_daily_ann', jobs, max_combos=max_combos)
    out['wf_path'] = path
    if d is not None and len(d):
        out['wf_all'] = {k: v for k, v in metrics(tr, d).items() if k != 'monthly'}
        d['session'] = pd.to_datetime(d['session']).dt.date
        d25 = d[d['session'] >= pd.Timestamp(MAIN[0]).date()].reset_index(drop=True)
        tr25 = tr[pd.to_datetime(tr['entry_ts']).dt.tz_convert('America/New_York').dt.date >= pd.Timestamp(MAIN[0]).date()] if len(tr) else tr
        out['wf_2025'] = {k: v for k, v in metrics(tr25, d25).items() if k != 'monthly'}
        out['wf_2025_monthly'] = metrics(tr25, d25).get('monthly')
        if len(d25) > 60:
            t, best = lucid_scan(d25, Rules(), boot_reps=100)
            out['lucid_wf_2025'] = {k: (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v) for k, v in best.items() if not isinstance(v, dict)}
            out['lucid_wf_2025_table'] = t[['micros', 'pass_rate', 'pass_within_21', 'p_first_payout_unconditional', 'expected_net_per_eval', 'exp_net_lb', 'zero_edge_exp_net', 'p_loss_fee']].round(3).to_dict('records')
        d25.to_csv(os.path.join(ROOT, 'results', id_, 'wf_oos_2025_daily.csv'), index=False)
    for name, (s, e) in (('fixed_main', MAIN), ('fixed_prior', PRIOR)):
        try:
            trf, df_, m = run_strategy(id_, contract, s, e, params)
            out[name] = {k: v for k, v in m.items() if k != 'monthly'}
        except Exception as ex:
            out[name] = {'error': repr(ex)}
    out['seconds'] = time.time() - t0
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--ids', nargs='*', default=None); ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--min_main_pf', type=float, default=1.1); ap.add_argument('--max_combos', type=int, default=24); ap.add_argument('--wf_start', default='2021-01-01')
    a = ap.parse_args()
    files = glob.glob(os.path.join(ROOT, 'results', '*', 'final.json'))
    cands = []
    for p in files:
        try:
            j = json.load(open(p))
        except Exception:
            continue
        id_ = j.get('id') or os.path.basename(os.path.dirname(p))
        if a.ids and id_ not in a.ids:
            continue
        pf = (j.get('period_main') or {}).get('profit_factor', 0) or 0
        if a.ids or (j.get('verdict') in ('survivor', 'marginal') or pf >= a.min_main_pf):
            cands.append((id_, j.get('contract') or 'MES', j.get('params') or {}))
    print(f'{len(cands)} candidates: {[c[0] for c in cands]}')
    rows = []
    for id_, contract, params in cands:
        try:
            r = evaluate(id_, contract, params, a.jobs, wf_start=a.wf_start, max_combos=a.max_combos)
        except Exception as ex:
            print(id_, 'ERROR', repr(ex)); continue
        json.dump(r, open(os.path.join(ROOT, 'results', id_, 'walkforward.json'), 'w'), indent=1, default=str)
        w25 = r.get('wf_2025', {}); wa = r.get('wf_all', {}); lu = r.get('lucid_wf_2025', {}); fm = r.get('fixed_main', {}); fp = r.get('fixed_prior', {})
        row = {'id': id_, 'contract': contract, 'wf25_trades': w25.get('trades'), 'wf25_net': w25.get('net'), 'wf25_pf': w25.get('profit_factor'), 'wf25_sharpe': w25.get('sharpe_daily_ann'),
               'wf25_pos_months': w25.get('pct_pos_months'), 'wfall_net': wa.get('net'), 'wfall_pf': wa.get('profit_factor'), 'wfall_sharpe': wa.get('sharpe_daily_ann'),
               'lb_micros': lu.get('micros'), 'lb_exp_net': lu.get('exp_net_lb'), 'exp_net': lu.get('expected_net_per_eval'), 'pass_21': lu.get('pass_within_21'),
               'zero_edge': lu.get('zero_edge_exp_net'), 'recommended': lu.get('recommended'), 'fixed_main_pf': fm.get('profit_factor'), 'fixed_prior_pf': fp.get('profit_factor'), 'secs': round(r['seconds'])}
        rows.append(row); print(row)
    df = pd.DataFrame(rows)
    if len(df):
        df = df.sort_values(['lb_exp_net', 'wf25_sharpe'], ascending=False, na_position='last')
        df.to_csv(os.path.join(ROOT, 'results', 'final_selection.csv'), index=False)
        with pd.option_context('display.width', 250, 'display.max_rows', 200):
            print(df.round(3).to_string(index=False))
