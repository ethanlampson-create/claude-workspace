"""Variant with CAUSAL TRAILING grade thresholds: instead of fixing the bands at the January refit from the training
distribution, each setup is graded against the predictions of the previous 250 graded setups (pooled fixed stream), so
'B and up' always keeps about half of the recent setups. Addresses the 41% kept share of the fixed-threshold grader on
2025-26 (it graded most orb_close30 setups F because they looked unlike 2010-2024 setups). Writes
graded_wf_best_trailing.parquet and account_results_best_trailing.json (wf stream, Aggressive + Safe)."""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from grading.grader import to_grade, QUANTS, evaluate, grade_table
from grading.account import Frame, run_variants, OUT


def trailing_grades(fx, target, window=250):
    """fx: graded fixed stream (has pred); target: table to grade (has pred, entry_ts). Thresholds from the last `window`
    fixed-stream predictions strictly before each target setup's entry time."""
    fx = fx.sort_values('entry_ts'); p = fx['pred'].values; t = pd.DatetimeIndex(fx['entry_ts']).values
    out = target.copy(); g = []
    for ts, pr in zip(pd.DatetimeIndex(target['entry_ts']).values, target['pred'].values):
        k = np.searchsorted(t, ts, side='left')
        ref = p[max(0, k - window):k]
        g.append(to_grade(np.array([pr]), np.quantile(ref, QUANTS))[0] if len(ref) >= 50 else 'C')
    out['grade'] = g
    return out


def main():
    fx = pd.read_parquet(os.path.join(OUT, 'graded_fixed_best.parquet')); wf = pd.read_parquet(os.path.join(OUT, 'graded_wf_best.parquet'))
    # for 2025-26 wf setups the reference pool is the fixed stream's own 2025-26 predictions before that time plus 2024
    wft = trailing_grades(fx, wf)
    fxt = trailing_grades(fx[fx['year'] < 2025], fx[fx['year'] < 2025])   # development view with trailing thresholds
    wft.to_parquet(os.path.join(OUT, 'graded_wf_best_trailing.parquet'))
    print('dev 2014-2024 trailing thresholds:', {k: round(v, 3) for k, v in evaluate(fxt[fxt['year'] >= 2014]).items()})
    print('wf 2025-26 trailing thresholds:', {k: round(v, 3) for k, v in evaluate(wft).items()})
    print(grade_table(wft).round(3).to_string())
    frame = Frame()
    res = run_variants(frame, {'B_and_up_trailing_thresholds': (wft, ('A+', 'A', 'B'))}, 'wf', reps=200, per_start=True)
    acc = json.load(open(os.path.join(OUT, 'account_results_best.json')))
    acc['wf_2025_2026'].update(res); acc['wf_2025_2026_trailing_eval'] = {'dev_2014_2024': evaluate(fxt[fxt['year'] >= 2014]), 'wf_2025_2026': evaluate(wft)}
    json.dump(acc, open(os.path.join(OUT, 'account_results_best.json'), 'w'), indent=1, default=float)


if __name__ == '__main__':
    main()
