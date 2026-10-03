"""Aggregate results/<id>/final.json files (written by the strategy lab agents) into a ranked scoreboard.
python3 -m backtest.scoreboard [--out results/scoreboard.csv]
final.json schema (flexible): {id, family, contract, params, period_main:{...metrics}, period_prior:{...}, lucid:{...}, verdict, notes}
"""
import argparse, glob, json, os, sys
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_all():
    rows = []
    for p in glob.glob(os.path.join(ROOT, 'results', '*', 'final.json')):
        try:
            j = json.load(open(p))
        except Exception as e:
            rows.append({'id': os.path.basename(os.path.dirname(p)), 'error': repr(e)}); continue
        m = j.get('period_main', {}) or {}; q = j.get('period_prior', {}) or {}; lu = j.get('lucid', {}) or {}
        rows.append({'id': j.get('id', os.path.basename(os.path.dirname(p))), 'family': j.get('family'), 'contract': j.get('contract'), 'verdict': j.get('verdict'),
                     'trades': m.get('trades'), 'net': m.get('net'), 'pf': m.get('profit_factor'), 'sharpe': m.get('sharpe_daily_ann'), 'pos_days': m.get('pct_pos_days'),
                     'dd_intra': m.get('max_dd_intraday'), 'prior_pf': q.get('profit_factor'), 'prior_net': q.get('net'),
                     'micros': lu.get('micros'), 'pass_rate': lu.get('pass_rate'), 'p_payout': lu.get('p_first_payout_unconditional'), 'exp_net': lu.get('expected_net_per_eval'),
                     'params': json.dumps(j.get('params')), 'notes': (j.get('notes') or '')[:200]})
    return pd.DataFrame(rows)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default=None); a = ap.parse_args()
    df = load_all()
    if len(df):
        df = df.sort_values(['exp_net', 'sharpe'], ascending=False, na_position='last')
        with pd.option_context('display.width', 250, 'display.max_colwidth', 40, 'display.max_rows', 500):
            print(df.drop(columns=['params', 'notes']).to_string(index=False))
        if a.out:
            df.to_csv(a.out, index=False)
    else:
        print('no final.json files yet')
