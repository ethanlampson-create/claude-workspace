"""Development-years search for the grader (2014-2024 only; 2025-26 untouched). Variants: model x target x feature set x
recency weighting x pooled/per-strategy. Score = walk-forward Spearman and the kept-minus-dropped R gap on 2014-2024."""
import os, sys, itertools, warnings
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from grading.grader import prep, feature_columns, make_model, to_grade, QUANTS, evaluate, OUT
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
warnings.filterwarnings('ignore')

COMPACT = ['tod', 'day_move', 'day_range', 'pos_in_pd_range', 'dist_pdh', 'dist_pdl', 'sweep_against', 'sweep_with', 'mom15', 'fvg_align', 'cisd',
           'or15', 'trend50_dir', 'trend200_dir', 'gap_dir', 'atr_ratio', 'vix_pct', 'dow', 'risk_atr', 'rr', 'mem_R20', 'mem_wr_hour',
           'is_orb_close30', 'is_mr_gapfade', 'is_orb_dbl', 'side']
MEMORY_ONLY = ['tod', 'dow', 'vix_pct', 'atr_ratio', 'mem_R20', 'mem_R50', 'mem_wr20', 'mem_loss_streak', 'mem_wr_hour', 'mem_R_hour', 'mem_wr_dow',
               'mem_wr_side', 'is_orb_close30', 'is_mr_gapfade', 'is_orb_dbl', 'side']


def model(kind, target):
    if kind == 'gbm':
        if target == 'win':
            return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.04, max_iter=200, min_samples_leaf=40, l2_regularization=1.0, early_stopping=False, random_state=0)
        return HistGradientBoostingRegressor(max_depth=3, learning_rate=0.04, max_iter=200, min_samples_leaf=40, l2_regularization=1.0, early_stopping=False, random_state=0)
    if kind == 'gbm_small':
        if target == 'win':
            return HistGradientBoostingClassifier(max_depth=2, learning_rate=0.03, max_iter=120, min_samples_leaf=80, l2_regularization=3.0, early_stopping=False, random_state=0)
        return HistGradientBoostingRegressor(max_depth=2, learning_rate=0.03, max_iter=120, min_samples_leaf=80, l2_regularization=3.0, early_stopping=False, random_state=0)
    if kind == 'linear':
        if target == 'win':
            return make_pipeline(SimpleImputer(strategy='median'), StandardScaler(), LogisticRegression(C=0.05, max_iter=2000))
        return make_pipeline(SimpleImputer(strategy='median'), StandardScaler(), Ridge(alpha=30.0))
    raise ValueError


def fitpred(kind, target, train, test, cols, hl):
    y = train['R_w'].values if target == 'R' else train['win'].values
    w = None
    if hl:
        age = (pd.Timestamp(f"{train['year'].max() + 1}-01-01") - pd.to_datetime(train['session'])).dt.days.values / 365.25
        w = 0.5 ** (age / hl)
    m = model(kind, target)
    cols = [c for c in cols if train[c].notna().sum() >= 30]      # per-strategy fits: drop features that strategy never has
    X = train[cols].values.astype(float); Xt = test[cols].values.astype(float)
    if kind == 'linear':
        m.fit(X, y, **({'logisticregression__sample_weight': w} if (w is not None and target == 'win') else ({'ridge__sample_weight': w} if w is not None else {})))
    else:
        m.fit(X, y, sample_weight=w)
    if target == 'win':
        return m.predict_proba(X)[:, 1], m.predict_proba(Xt)[:, 1]
    return m.predict(X), m.predict(Xt)


def run_variant(fixed, kind, target, fs, hl, per_strategy, years=range(2014, 2025)):
    cols = fs
    outs = []
    for Y in years:
        train = fixed[fixed['year'] < Y]; test = fixed[fixed['year'] == Y]
        if len(train) < 600 or not len(test):
            continue
        if per_strategy:
            parts = []
            for s in test['strategy'].unique():
                tr_s = train[train['strategy'] == s]; te_s = test[test['strategy'] == s].copy()
                if len(tr_s) < 150:
                    continue
                ptr, pte = fitpred(kind, target, tr_s, te_s, cols, hl)
                te_s['pred'] = pte; te_s['grade'] = to_grade(pte, np.quantile(ptr, QUANTS)); parts.append(te_s)
            if parts:
                outs.append(pd.concat(parts))
        else:
            ptr, pte = fitpred(kind, target, train, test, cols, hl)
            t = test.copy(); t['pred'] = pte; t['grade'] = to_grade(pte, np.quantile(ptr, QUANTS)); outs.append(t)
    return pd.concat(outs)


def main():
    fixed = prep(pd.read_parquet(os.path.join(OUT, 'trades_fixed.parquet')))
    allc = feature_columns(fixed)
    fsets = {'all': allc, 'compact': COMPACT, 'memory': MEMORY_ONLY}
    rows = []
    for kind, target, fs, hl, ps in itertools.product(('gbm', 'gbm_small', 'linear'), ('R', 'win'), ('all', 'compact', 'memory'), (None, 3.0), (False, True)):
        g = run_variant(fixed, kind, target, fsets[fs], hl, ps)
        e = evaluate(g); e.update({'model': kind, 'target': target, 'features': fs, 'halflife': hl, 'per_strategy': ps, 'gap': e['R_kept'] - e['R_dropped']})
        # year-by-year consistency of the kept-minus-dropped gap
        yg = g.groupby('year').apply(lambda x: x.loc[x['grade'].isin(['A+', 'A', 'B']), 'R_w'].mean() - x.loc[~x['grade'].isin(['A+', 'A', 'B']), 'R_w'].mean())
        e['years_gap_pos'] = float((yg > 0).mean()); e['n_years'] = int(len(yg))
        rows.append(e); print(kind, target, fs, hl, ps, 'rho', round(e['spearman'], 3), 'gap', round(e['gap'], 3), 'yrs+', round(e['years_gap_pos'], 2), 'pf', round(e['pf_all'], 2), '->', round(e['pf_kept'], 2), flush=True)
    df = pd.DataFrame(rows).sort_values('spearman', ascending=False)
    df.to_csv(os.path.join(OUT, 'dev_search.csv'), index=False)
    print(df[['model', 'target', 'features', 'halflife', 'per_strategy', 'spearman', 'gap', 'years_gap_pos', 'kept_share', 'pf_all', 'pf_kept', 'net_all', 'net_kept']].round(3).to_string(index=False))


if __name__ == '__main__' and len(sys.argv) == 1:
    main()


# ----------------------------------------------------------------------------------------------------------------------
def grade_streams(fixed, wf, kind, target, cols, hl, per_strategy, years=range(2014, 2027), shuffle_seed=None, insample=False):
    """Grade the fixed stream (walk-forward by year) and the wf stream (2025-26) with one variant. Returns (graded_fixed, graded_wf)."""
    rng = np.random.default_rng(shuffle_seed) if shuffle_seed is not None else None
    def fit_block(train, tests):
        if rng is not None:
            train = train.copy(); train['R_w'] = rng.permutation(train['R_w'].values); train['win'] = rng.permutation(train['win'].values)
        outs = []
        if per_strategy:
            for t in tests:
                parts = []
                for s in t['strategy'].unique():
                    tr_s = train[train['strategy'] == s]; te_s = t[t['strategy'] == s].copy()
                    if len(tr_s) < 150 or not len(te_s):
                        continue
                    ptr, pte = fitpred(kind, target, tr_s, te_s, cols, hl)
                    te_s['pred'] = pte; te_s['grade'] = to_grade(pte, np.quantile(ptr, QUANTS)); parts.append(te_s)
                outs.append(pd.concat(parts) if parts else t.iloc[0:0])
        else:
            for t in tests:
                if not len(t):
                    outs.append(t); continue
                ptr, pte = fitpred(kind, target, train, t, cols, hl)
                tt = t.copy(); tt['pred'] = pte; tt['grade'] = to_grade(pte, np.quantile(ptr, QUANTS)); outs.append(tt)
        return outs
    if insample:
        fx, w = fit_block(fixed, [fixed, wf])
        return fx.sort_values('entry_ts'), w.sort_values('entry_ts')
    fx_out = []; wf_out = []
    for Y in years:
        train = fixed[fixed['year'] < Y]
        if len(train) < 600:
            continue
        tests = [fixed[fixed['year'] == Y], wf[wf['year'] == Y]]
        a, b = fit_block(train, tests)
        fx_out.append(a); wf_out.append(b)
    return pd.concat(fx_out).sort_values('entry_ts'), pd.concat(wf_out).sort_values('entry_ts')


def grade_final(tag='best'):
    """Take the best development variant (by Spearman on 2014-2024) and write graded_*_{tag}.parquet plus the two controls."""
    from grading.grader import grade_table
    fixed = prep(pd.read_parquet(os.path.join(OUT, 'trades_fixed.parquet'))); wf = prep(pd.read_parquet(os.path.join(OUT, 'trades_wf.parquet')))
    dev = pd.read_csv(os.path.join(OUT, 'dev_search.csv')).sort_values('spearman', ascending=False)
    b = dev.iloc[0]
    fsets = {'all': feature_columns(fixed), 'compact': COMPACT, 'memory': MEMORY_ONLY}
    hl = None if pd.isna(b['halflife']) else float(b['halflife'])
    print('best variant:', dict(b[['model', 'target', 'features', 'halflife', 'per_strategy', 'spearman', 'gap', 'years_gap_pos']]))
    args = (b['model'], b['target'], fsets[b['features']], hl, bool(b['per_strategy']))
    fx, w = grade_streams(fixed, wf, *args)
    fx.to_parquet(os.path.join(OUT, f'graded_fixed_{tag}.parquet')); w.to_parquet(os.path.join(OUT, f'graded_wf_{tag}.parquet'))
    fxi, wi = grade_streams(fixed, wf, *args, insample=True)
    fxi.to_parquet(os.path.join(OUT, 'graded_fixed_insample.parquet')); wi.to_parquet(os.path.join(OUT, 'graded_wf_insample.parquet'))
    fxs, ws = grade_streams(fixed, wf, *args, shuffle_seed=1)
    fxs.to_parquet(os.path.join(OUT, 'graded_fixed_shuffled.parquet')); ws.to_parquet(os.path.join(OUT, 'graded_wf_shuffled.parquet'))
    ctrl = pd.DataFrame({'walk_forward_wf2025': evaluate(w), 'insample_wf2025': evaluate(wi), 'shuffled_wf2025': evaluate(ws),
                         'walk_forward_fixed2025': evaluate(fx[fx['year'] >= 2025]), 'insample_fixed2025': evaluate(fxi[fxi['year'] >= 2025])}).T
    ctrl.to_csv(os.path.join(OUT, 'controls_2025.csv'))
    yr = fx.groupby('year').apply(lambda g: pd.Series(evaluate(g))); yr.to_csv(os.path.join(OUT, 'per_year_dev.csv'))
    gs = json.load(open(os.path.join(OUT, 'grader_summary.json'))); gs['chosen_model'] = f"{b['model']} / target {b['target']} / features {b['features']} / half-life {hl} / per-strategy {bool(b['per_strategy'])}"
    gs['best_variant'] = {k: (None if pd.isna(v) else (v.item() if hasattr(v, 'item') else v)) for k, v in b.items()}
    json.dump(gs, open(os.path.join(OUT, 'grader_summary.json'), 'w'), indent=1, default=str)
    print('\nGrade table 2014-2024 OOS:'); print(grade_table(fx[(fx['year'] >= 2014) & (fx['year'] <= 2024)]).round(3).to_string())
    print('\nGrade table 2025-26 wf stream OOS:'); print(grade_table(w).round(3).to_string())
    print('\nControls:'); print(ctrl.round(3).to_string())


if __name__ == '__main__' and len(sys.argv) > 1 and sys.argv[1] == 'final':
    import json
    grade_final()
