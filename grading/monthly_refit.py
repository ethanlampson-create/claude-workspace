"""Live-bot memory test: refit the chosen grader at the start of every month of 2025-26 on every setup closed before
that month (2010-2024 history plus the 2025-26 trades already finished), grade that month, compare kept vs vetoed.
python3 -m grading.monthly_refit"""
# Live-bot memory test: refit the chosen grader at the start of every month of 2025-26 on ALL setups finished before
# that month (2010-11 fixed stream history + the live 2025-26 trades already closed), then grade that month's setups.
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from grading.grader import prep, to_grade, QUANTS, evaluate
from grading.dev_search import COMPACT, fitpred
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results', 'grading')
fixed = prep(pd.read_parquet(f'{OUT}/trades_fixed.parquet')); wf = prep(pd.read_parquet(f'{OUT}/trades_wf.parquet'))
hist = fixed[pd.to_datetime(fixed['session']) < '2025-01-01']
wf['m'] = pd.to_datetime(wf['session']).dt.to_period('M')
out = []
for m in sorted(wf['m'].unique()):
    t0 = m.to_timestamp()
    train = pd.concat([hist, wf[pd.to_datetime(wf['session']) < t0]])     # everything closed before this month
    test = wf[wf['m'] == m].copy()
    ptr, pte = fitpred('gbm_small', 'R', train, test, COMPACT, 3.0)
    test['pred'] = pte; test['grade'] = to_grade(pte, np.quantile(ptr, QUANTS)); out.append(test)
g = pd.concat(out); k = g['grade'].isin(['A+', 'A', 'B'])
g.to_parquet(f'{OUT}/graded_wf_monthly_refit.parquet')
s = lambda x: f'{len(x)} trades, {int(x.win.sum())} winners, {int((1 - x.win).sum())} losers, win rate {x.win.mean():.0%}, net ${x.pnl.sum():,.0f}'
print('kept  :', s(g[k])); print('vetoed:', s(g[~k]))
e = evaluate(g); print({k2: round(v, 3) for k2, v in e.items() if k2 in ('spearman', 'kept_share', 'R_kept', 'R_dropped')})
