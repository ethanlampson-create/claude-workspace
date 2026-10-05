"""Setup grader: learn from past setups which ones tend to work, grade new ones A+ .. F, walk-forward.

Grades are letter bands of a predicted expected R-multiple. Thresholds are the 90/75/50/25/10 percentiles of the
predictions on the TRAINING setups, fixed at fit time, so 'B and up' means 'in the better half of the setups the
grader had seen when it was fitted', never 'in the better half of this year'.

Walk-forward: the grader used for year Y is fitted on setups whose session is before Y-01-01 only (fixed-parameter
stream, 2010-11 onward). It is applied to the fixed stream of year Y and, for 2025-26, to the walk-forward parameter
stream the final report's account numbers are based on.
Controls: 'insample' (fitted on everything incl. the test years: what a grader that has seen the answers reports) and
'shuffled' (fitted on permuted outcomes: what a grader with no information reports).

Models
- gbm:    gradient-boosted trees on all confluence features (NaN-aware), regularised.
- bucket: the literal 'memory log': mean R of past setups in the same (strategy, half-hour, VIX tercile, ATR-regime
          tercile, side) cell, shrunk toward the strategy mean (James-Stein style, k=30).
- ridge:  linear model on median-imputed standardised features.
"""
import os, sys, json, warnings
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from scipy.stats import spearmanr
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'results', 'grading')
warnings.filterwarnings('ignore')

NON_FEATURES = {'entry_ts', 'exit_ts', 'entry_px', 'exit_px', 'pnl', 'mae_pts', 'mfe_pts', 'reason', 'day_id', 'session', 'bars', 'entry_idx',
                'strategy', 'risk_pts', 'tgt_pts', 'risk_usd', 'R', 'mfe_R', 'mae_R', 'win', 'year', 'R_w', 'pred', 'grade', 'atr', '_wf'}
GRADES = ['A+', 'A', 'B', 'C', 'D', 'F']
QUANTS = [0.90, 0.75, 0.50, 0.25, 0.10]
RANK = {g: i for i, g in enumerate(GRADES)}


def feature_columns(df):
    cols = [c for c in df.columns if c not in NON_FEATURES and df[c].dtype != object]
    return cols


def prep(df):
    df = df.copy()
    df['year'] = pd.to_datetime(df['session']).dt.year
    df['R_w'] = df['R'].clip(-3, 3)
    for s in ('orb_close30', 'mr_gapfade', 'orb_dbl'):
        df['is_' + s] = (df['strategy'] == s).astype(int)
    return df


class Bucket:
    def __init__(self, k=30):
        self.k = k
    def _cells(self, df):
        vix_t = pd.cut(df['vix'], self._vq, labels=False, include_lowest=True)
        atr_t = pd.cut(df['atr_ratio'], self._aq, labels=False, include_lowest=True)
        return pd.DataFrame({'s': df['strategy'].values, 'h': (df['tod'] // 30).values, 'v': vix_t.fillna(1).astype(int).values,
                             'a': atr_t.fillna(1).astype(int).values, 'side': df['side'].values})
    def fit(self, df, y):
        self._vq = np.unique(np.nanquantile(df['vix'], [0, 1 / 3, 2 / 3, 1])); self._aq = np.unique(np.nanquantile(df['atr_ratio'], [0, 1 / 3, 2 / 3, 1]))
        self._vq[0] = -np.inf; self._vq[-1] = np.inf; self._aq[0] = -np.inf; self._aq[-1] = np.inf
        c = self._cells(df); c['y'] = y.values
        self.smean = c.groupby('s')['y'].mean().to_dict()
        g = c.groupby(['s', 'h', 'v', 'a', 'side'])['y'].agg(['sum', 'count'])
        self.cell = g.to_dict('index')
        return self
    def predict(self, df):
        c = self._cells(df)
        out = np.empty(len(c))
        for i, r in enumerate(c.itertuples(index=False)):
            key = (r.s, r.h, r.v, r.a, r.side); m0 = self.smean.get(r.s, 0.0)
            g = self.cell.get(key)
            if g is None:
                out[i] = m0
            else:
                out[i] = (g['sum'] + self.k * m0) / (g['count'] + self.k)
        return out


def make_model(name, seed=0):
    if name == 'gbm':
        return HistGradientBoostingRegressor(max_depth=3, learning_rate=0.04, max_iter=250, min_samples_leaf=40, l2_regularization=1.0,
                                             early_stopping=False, random_state=seed)
    if name == 'ridge':
        return make_pipeline(SimpleImputer(strategy='median'), StandardScaler(), Ridge(alpha=30.0))
    if name == 'bucket':
        return Bucket()
    raise ValueError(name)


def fit_predict(name, train, tests, cols, seed=0, shuffle=False):
    y = train['R_w'].copy()
    if shuffle:
        y = pd.Series(np.random.default_rng(seed).permutation(y.values), index=y.index)
    m = make_model(name, seed)
    if name == 'bucket':
        m.fit(train, y); ptrain = m.predict(train); preds = [m.predict(t) for t in tests]
    else:
        X = train[cols].values.astype(float)
        m.fit(X, y.values); ptrain = m.predict(X); preds = [m.predict(t[cols].values.astype(float)) for t in tests]
    thr = np.quantile(ptrain, QUANTS)   # descending: A+ >= thr[0], A >= thr[1], ...
    return preds, thr, m


def to_grade(pred, thr):
    g = np.full(len(pred), 'F', dtype=object)
    for i, t in enumerate(thr):
        pass
    # A+ >= q90, A >= q75, B >= q50, C >= q25, D >= q10, F below
    bands = ['A+', 'A', 'B', 'C', 'D']
    assigned = np.zeros(len(pred), bool)
    for band, t in zip(bands, thr):
        sel = (~assigned) & (pred >= t)
        g[sel] = band; assigned |= sel
    return g


def walk_forward(fixed, wf, name, years=range(2014, 2027), min_train=600, shuffle=False, seed=0):
    cols = feature_columns(fixed)
    outs_fixed = []; outs_wf = []; fits = {}
    for Y in years:
        train = fixed[fixed['year'] < Y]
        if len(train) < min_train:
            continue
        tests = [fixed[fixed['year'] == Y]]
        wfY = wf[wf['year'] == Y] if wf is not None else None
        if wfY is not None and len(wfY):
            tests.append(wfY)
        preds, thr, m = fit_predict(name, train, tests, cols, seed, shuffle)
        t0 = tests[0].copy(); t0['pred'] = preds[0]; t0['grade'] = to_grade(preds[0], thr); outs_fixed.append(t0)
        if len(tests) > 1:
            t1 = tests[1].copy(); t1['pred'] = preds[1]; t1['grade'] = to_grade(preds[1], thr); outs_wf.append(t1)
        fits[Y] = {'n_train': int(len(train)), 'thr': [float(x) for x in thr]}
    fx = pd.concat(outs_fixed).sort_values('entry_ts') if outs_fixed else None
    wfo = pd.concat(outs_wf).sort_values('entry_ts') if outs_wf else None
    return fx, wfo, fits


def insample(fixed, wf, name, seed=0):
    cols = feature_columns(fixed)
    preds, thr, m = fit_predict(name, fixed, [fixed, wf], cols, seed)
    fx = fixed.copy(); fx['pred'] = preds[0]; fx['grade'] = to_grade(preds[0], thr)
    w = wf.copy(); w['pred'] = preds[1]; w['grade'] = to_grade(preds[1], thr)
    return fx, w, thr


def evaluate(df, label='R_w', keep=('A+', 'A', 'B')):
    """Grader quality on a graded table: rank correlation, kept share, mean R kept vs dropped, profit factor kept vs all."""
    if df is None or not len(df):
        return {}
    k = df['grade'].isin(keep)
    def pf(x):
        w = x[x > 0].sum(); l = -x[x <= 0].sum(); return float(w / l) if l > 0 else np.inf
    rho = spearmanr(df['pred'], df[label], nan_policy='omit').correlation if df['pred'].nunique() > 1 else np.nan
    out = {'n': int(len(df)), 'spearman': float(rho), 'kept_share': float(k.mean()),
           'R_all': float(df['R_w'].mean()), 'R_kept': float(df.loc[k, 'R_w'].mean()) if k.any() else np.nan, 'R_dropped': float(df.loc[~k, 'R_w'].mean()) if (~k).any() else np.nan,
           'wr_all': float(df['win'].mean()), 'wr_kept': float(df.loc[k, 'win'].mean()) if k.any() else np.nan,
           'pf_all': pf(df['pnl']), 'pf_kept': pf(df.loc[k, 'pnl']) if k.any() else np.nan,
           'net_all': float(df['pnl'].sum()), 'net_kept': float(df.loc[k, 'pnl'].sum()), 'net_dropped': float(df.loc[~k, 'pnl'].sum())}
    return out


def grade_table(df):
    g = df.groupby('grade').agg(n=('pnl', 'size'), win_rate=('win', 'mean'), mean_R=('R_w', 'mean'), net=('pnl', 'sum'), avg_pnl=('pnl', 'mean'))
    g['pf'] = df.groupby('grade')['pnl'].apply(lambda x: x[x > 0].sum() / max(1e-9, -x[x <= 0].sum()))
    return g.reindex([x for x in GRADES if x in g.index])


def main():
    fixed = prep(pd.read_parquet(os.path.join(OUT, 'trades_fixed.parquet')))
    wf = prep(pd.read_parquet(os.path.join(OUT, 'trades_wf.parquet')))
    cols = feature_columns(fixed)
    print(f'{len(cols)} features:', cols)
    summary = {'features': cols}
    dev_years = (2014, 2024)
    # ---- model comparison on the development years (fixed stream, walk-forward)
    comp = []
    for name in ('gbm', 'bucket', 'ridge'):
        fx, wfo, fits = walk_forward(fixed, wf, name)
        dev = fx[(fx['year'] >= dev_years[0]) & (fx['year'] <= dev_years[1])]
        e = evaluate(dev); e['model'] = name; comp.append(e)
        for s, g in dev.groupby('strategy'):
            es = evaluate(g); es['model'] = name + '/' + s; comp.append(es)
        fx.to_parquet(os.path.join(OUT, f'graded_fixed_{name}.parquet')); wfo.to_parquet(os.path.join(OUT, f'graded_wf_{name}.parquet'))
        summary[name] = {'fits': fits}
    comp = pd.DataFrame(comp).set_index('model')
    print('\nDevelopment years 2014-2024, walk-forward (fitted on years before each year):')
    print(comp.round(3).to_string())
    comp.to_csv(os.path.join(OUT, 'model_comparison_dev.csv'))
    # choose by development Spearman on the pooled table (pre-registered rule: highest rank correlation)
    best = comp.loc[['gbm', 'bucket', 'ridge'], 'spearman'].idxmax()
    summary['chosen_model'] = best; print('\nchosen model:', best)
    # stability of the chosen model across seeds (gbm only)
    fx = pd.read_parquet(os.path.join(OUT, f'graded_fixed_{best}.parquet')); wfo = pd.read_parquet(os.path.join(OUT, f'graded_wf_{best}.parquet'))
    print('\nGrade table, development years (fixed stream, OOS):'); print(grade_table(fx[(fx['year'] >= 2014) & (fx['year'] <= 2024)]).round(3).to_string())
    print('\nGrade table, 2025-26 fixed stream (OOS):'); print(grade_table(fx[fx['year'] >= 2025]).round(3).to_string())
    print('\nGrade table, 2025-26 walk-forward stream (OOS):'); print(grade_table(wfo).round(3).to_string())
    print('\nPer year (fixed stream, chosen model):')
    yr = fx.groupby('year').apply(lambda g: pd.Series(evaluate(g))).round(3)
    print(yr[['n', 'spearman', 'kept_share', 'R_all', 'R_kept', 'R_dropped', 'pf_all', 'pf_kept', 'net_all', 'net_kept']].to_string())
    yr.to_csv(os.path.join(OUT, 'per_year_dev.csv'))
    # ---- controls
    fx_in, wf_in, thr_in = insample(fixed, wf, best)
    fx_in.to_parquet(os.path.join(OUT, 'graded_fixed_insample.parquet')); wf_in.to_parquet(os.path.join(OUT, 'graded_wf_insample.parquet'))
    fx_sh, wf_sh, _ = walk_forward(fixed, wf, best, shuffle=True, seed=1)
    fx_sh.to_parquet(os.path.join(OUT, 'graded_fixed_shuffled.parquet')); wf_sh.to_parquet(os.path.join(OUT, 'graded_wf_shuffled.parquet'))
    ctrl = pd.DataFrame({'walk_forward_wf2025': evaluate(wfo), 'insample_wf2025': evaluate(wf_in), 'shuffled_wf2025': evaluate(wf_sh),
                         'walk_forward_fixed2025': evaluate(fx[fx['year'] >= 2025]), 'insample_fixed2025': evaluate(fx_in[fx_in['year'] >= 2025])}).T
    print('\n2025-26 test: walk-forward grader vs in-sample grader vs shuffled-label grader:'); print(ctrl.round(3).to_string())
    ctrl.to_csv(os.path.join(OUT, 'controls_2025.csv'))
    # feature importance (permutation on the last walk-forward fit) for the report
    if best == 'gbm':
        from sklearn.inspection import permutation_importance
        train = fixed[fixed['year'] < 2025]; m = make_model('gbm'); m.fit(train[cols].values.astype(float), train['R_w'].values)
        test = pd.concat([fixed[fixed['year'] >= 2025]])
        pi = permutation_importance(m, test[cols].values.astype(float), test['R_w'].values, n_repeats=10, random_state=0, scoring='neg_mean_squared_error')
        imp = pd.Series(pi.importances_mean, index=cols).sort_values(ascending=False)
        imp.to_csv(os.path.join(OUT, 'feature_importance_2025.csv')); print('\nTop features (permutation importance on 2025-26 fixed stream):'); print(imp.head(15).round(5).to_string())
    json.dump(summary, open(os.path.join(OUT, 'grader_summary.json'), 'w'), indent=1, default=float)


if __name__ == '__main__':
    main()
