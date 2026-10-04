"""Render reports/grading_report.md from results/grading/*. python3 -m grading.report <grader_tag>"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from grading.grader import grade_table, evaluate, GRADES
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'results', 'grading')


def pct(x):
    return 'n/a' if x is None or (isinstance(x, float) and np.isnan(x)) else f'{100 * x:.0f}%'


def num(x, d=0):
    return 'n/a' if x is None or (isinstance(x, float) and np.isnan(x)) else f'{x:,.{d}f}'


def config_table(res, variants, cname):
    rows = [('Trades taken (3 legs)', lambda v: num(v['trades'])),
            ('Net per unit book (1 micro each), $', lambda v: num(v['net_per_unit_book'])),
            ('P(pass) single attempt', lambda v: pct(v[cname].get('eval_pass_rate'))),
            ('P(pass within 21 sessions)', lambda v: pct(v[cname].get('eval_pass_within_21'))),
            ('Median sessions to pass', lambda v: num(v[cname].get('eval_median_days_to_pass'))),
            ('P(lose the fee) per attempt', lambda v: pct(v[cname].get('eval_p_loss_fee'))),
            ('P(funded) within attempts', lambda v: pct(v[cname].get('p_funded'))),
            ('P(funded) bootstrap 5%..95%', lambda v: f"{pct(v[cname].get('bs_p_funded_p05'))}..{pct(v[cname].get('bs_p_funded_p95'))}"),
            ('Worst start month P(funded)', lambda v: pct(v[cname].get('min_monthly_p_funded'))),
            ('P(first payout | funded)', lambda v: pct(v[cname].get('p_first_payout_given_funded'))),
            ('P(first payout) overall', lambda v: pct(v[cname].get('p_first_payout_overall'))),
            ('P(first payout) bootstrap 5%..95%', lambda v: f"{pct(v[cname].get('bs_p_first_payout_overall_p05'))}..{pct(v[cname].get('bs_p_first_payout_overall_p95'))}"),
            ('P(funded account blown before any payout | pass)', lambda v: pct(v[cname].get('p_breach_before_payout_given_pass'))),
            ('Median sessions funded -> first payout', lambda v: num(v[cname].get('median_days_to_first_payout'))),
            ('Mean payouts per funded account', lambda v: num(v[cname].get('mean_payouts_given_pass'), 2)),
            ('Mean paid | funded (90% split), $', lambda v: num(v[cname].get('mean_paid_given_funded'))),
            ('Expected net per campaign, $', lambda v: num(v[cname].get('expected_net'))),
            ('Expected net bootstrap 5% / 50% / 95%, $', lambda v: f"{num(v[cname].get('bs_expected_net_p05'))} / {num(v[cname].get('bs_expected_net_p50'))} / {num(v[cname].get('bs_expected_net_p95'))}"),
            ('P(expected net > 0) bootstrap', lambda v: pct(v[cname].get('bs_p_expected_net_positive'))),
            ('Zero-edge control expected net, $', lambda v: num(v[cname].get('zero_edge_expected_net'))),
            ]
    ps = [('Avg sessions to pass (passed evals)', lambda v: num(v[cname]['per_start'].get('avg_days_to_pass'), 1)),
          ('Avg sessions a failed eval lasted', lambda v: num(v[cname]['per_start'].get('avg_days_failed_eval_lasted'), 1)),
          ('Share of starts reaching a payout before data end', lambda v: pct(v[cname]['per_start'].get('share_of_starts_reaching_payout_before_data_end'))),
          ('Avg calendar sessions start -> first payout', lambda v: num(v[cname]['per_start'].get('avg_days_start_to_first_payout'), 1)),
          ('Median calendar sessions start -> first payout', lambda v: num(v[cname]['per_start'].get('median_days_start_to_first_payout'), 1)),
          ('Avg evals failed before first payout', lambda v: num(v[cname]['per_start'].get('avg_evals_failed_before_first_payout'), 2)),
          ('Avg funded accounts blown before first payout', lambda v: num(v[cname]['per_start'].get('avg_funded_blown_before_first_payout'), 2)),
          ('Avg accounts lost (evals + funded) before first payout', lambda v: num(v[cname]['per_start'].get('avg_accounts_blown_before_first_payout'), 2)),
          ('Avg fees paid until first payout, $', lambda v: num(v[cname]['per_start'].get('avg_fees_until_first_payout'))),
          ('Avg payouts per funded account (to breach/live)', lambda v: num(v[cname]['per_start'].get('avg_payouts_per_funded_account'), 2)),
          ('Avg gross paid per funded account, $', lambda v: num(v[cname]['per_start'].get('avg_gross_paid_per_funded_account'))),
          ]
    if all('per_start' in res[v][cname] for v in variants):
        rows += ps
    head = '| Metric | ' + ' | '.join(variants) + ' |\n|---|' + '---|' * len(variants) + '\n'
    body = ''.join(f'| {name} | ' + ' | '.join(f(res[v]) for v in variants) + ' |\n' for name, f in rows)
    return head + body


def md_table(df, floatfmt=3):
    return df.round(floatfmt).to_markdown()


def main(tag):
    acc = json.load(open(os.path.join(OUT, f'account_results_{tag}.json')))
    comp = pd.read_csv(os.path.join(OUT, 'model_comparison_dev.csv'), index_col=0)
    ctrl = pd.read_csv(os.path.join(OUT, 'controls_2025.csv'), index_col=0)
    dev = pd.read_csv(os.path.join(OUT, 'dev_search.csv')) if os.path.exists(os.path.join(OUT, 'dev_search.csv')) else None
    yr = pd.read_csv(os.path.join(OUT, 'per_year_dev.csv'), index_col=0)
    gs = json.load(open(os.path.join(OUT, 'grader_summary.json')))
    fx = pd.read_parquet(os.path.join(OUT, f'graded_fixed_{tag}.parquet')); wfo = pd.read_parquet(os.path.join(OUT, f'graded_wf_{tag}.parquet'))
    imp = None
    try:
        from grading.dev_search import COMPACT, model as mk
        from grading.grader import prep
        from sklearn.inspection import permutation_importance
        fixed_raw = prep(pd.read_parquet(os.path.join(OUT, 'trades_fixed.parquet')))
        tr = fixed_raw[fixed_raw['year'] < 2025]; te = fixed_raw[fixed_raw['year'] >= 2025]
        age = (pd.Timestamp('2025-01-01') - pd.to_datetime(tr['session'])).dt.days.values / 365.25
        m = mk('gbm_small', 'R'); m.fit(tr[COMPACT].values.astype(float), tr['R_w'].values, sample_weight=0.5 ** (age / 3.0))
        pi = permutation_importance(m, te[COMPACT].values.astype(float), te['R_w'].values, n_repeats=20, random_state=0, scoring='neg_mean_squared_error')
        imp = pd.Series(pi.importances_mean, index=COMPACT).sort_values(ascending=False); imp.to_csv(os.path.join(OUT, 'feature_importance_2025.csv'))
    except Exception as e:
        print('importance failed:', e)
    W = acc['wf_2025_2026']; F = acc.get('fixed_2011_2026_volnorm')
    L = []
    L.append('# Graded setups (A+ .. F) for the Sentinel legs: does taking only B-and-better setups help the Lucid accounts?\n')
    L.append('Scope: the three legs the two final configurations trade (orb_close30, mr_gapfade, orb_dbl on MNQ), 1-minute Nasdaq proxy Nov 2010 - Sep 2026, '
             'same engine, costs and Lucid simulator as `reports/final_report.md`. Nothing here is wired into any live/bot code.\n')
    b = W['baseline']; g = W.get('B_and_up'); sh = W.get('B_and_up_shuffled_grader'); ins = W.get('B_and_up_insample_grader')
    L.append('## Verdict\n')
    L.append(f"**Taking only B-and-better setups makes both accounts worse, not better.** On the 2025-01..2026-09 stream the honest (walk-forward) grader keeps "
             f"{g['trades']} of {b['trades']} setups. Aggressive: P(first payout) {pct(b['aggressive']['p_first_payout_overall'])} -> {pct(g['aggressive']['p_first_payout_overall'])}, "
             f"expected net per campaign ${num(b['aggressive']['expected_net'])} -> ${num(g['aggressive']['expected_net'])}. Safe: P(first payout) {pct(b['safe']['p_first_payout_overall'])} -> {pct(g['safe']['p_first_payout_overall'])}, "
             f"expected net ${num(b['safe']['expected_net'])} -> ${num(g['safe']['expected_net'])}. "
             f"A grader fitted on shuffled outcomes (no information) produces almost the same damage (Aggressive P(first payout) {pct(sh['aggressive']['p_first_payout_overall'])}, Safe {pct(sh['safe']['p_first_payout_overall'])}), "
             f"so the loss comes from trading less, not from picking worse. The grader fitted on the answers (in-sample) shows Aggressive P(first payout) {pct(ins['aggressive']['p_first_payout_overall'])} and expected net ${num(ins['aggressive']['expected_net'])}: "
             f"that is the number a non-walk-forward backtest would have reported, and it is not achievable.\n")
    L.append('Why: the Lucid rules pay for frequency given a positive expectancy per trade. A payout needs 5 qualifying days (>= $150) and >= $4,000 of profit while the account sits '
             'within $2,000 of an end-of-day trailing floor; halving the trade count halves the speed at which cushion builds but leaves every remaining trade\'s loss the same size, '
             f"so funded accounts are blown before their first payout far more often ({pct(b['aggressive']['p_breach_before_payout_given_pass'])} -> {pct(g['aggressive']['p_breach_before_payout_given_pass'])} for Aggressive). "
             'The confluences themselves (time of day, FVG/CISD proxies, sweeps, trend, VIX, ATR regime, the strategy\'s own memory) carry a rank correlation of about 0.1 with the outcome out of sample, '
             'which is far too little to pay for the lost frequency.\n')
    L.append('## Method\n')
    L.append('1. **Setup log.** Every signal the strategies would take is logged with what a trader could see at that moment (bars strictly before the entry bar): '
             'time of day, weekday, month; opening-range size/direction/position; gap, overnight range and direction; prior-day range, direction, position in the prior-day range, '
             'distance to prior-day high/low/close and overnight high/low; liquidity sweeps of PDH/PDL (with and against the trade); 5-, 15-, 30-minute momentum, '
             'realised volatility; fair-value-gap counts and whether the entry sits in a same-/opposite-direction FVG; a change-in-state-of-delivery (CISD) proxy and displacement of the last 5-minute candle; '
             'daily trend vs SMA20/50/200; 3- and 10-day returns; ATR regime (ATR vs its 60-day mean), VIX and its 100-day percentile; planned risk and target in ATR and the planned R:R; '
             'and the strategy\'s own memory (mean R and win rate of its last 20/50 setups, loss streak, expanding win rate in the same half-hour, weekday and side). '
             f'{len(gs["features"])} features in total. Outcome = realised R multiple (P&L / planned risk), winsorised to [-3, 3]. No volume exists in the data, so volume confluences are not available.\n')
    L.append('2. **Grader.** A model predicts the expected R of a setup from those features. Grades are bands of the prediction with thresholds fixed at fit time from the training setups: '
             'A+ = top 10%, A = next 15%, B = next 25%, C = next 25%, D = next 15%, F = bottom 10%. "B and up" = the better half of the setups the grader had seen when it was fitted.\n')
    L.append('3. **Walk-forward.** The grader used for year Y was fitted on setups before Y-01-01 only, refitted every January (first fit 2014). Model choice (type, target, feature set, '
             'recency weighting, pooled vs per-strategy) was made on 2014-2024 results only; 2025-26 was scored once with the chosen grader.\n')
    L.append('4. **Account re-run.** For each variant the engine is re-run with the rejected signals removed (exact intraday equity), the three legs are combined one micro each, '
             'and the two configurations are simulated as in the final report: Aggressive = 15 micros (5 units), one attempt; Safe = 9 micros (3 units), up to three attempts; funded book cut to 1 unit when the room to the MLL is under $900.\n')
    L.append('5. **Controls.** An *in-sample* grader (fitted on 2010-2026 including the test years) shows what a grader that has seen the answers reports; a *shuffled-label* grader '
             '(same model, outcomes permuted) shows what a grader with no information reports. Both filters are run through the same account simulation.\n')
    L.append('## 1. Does the grader know anything? (walk-forward, 2014-2024, fixed-parameter stream)\n')
    L.append('Rank correlation between predicted and realised R, share kept at "B and up", mean R kept vs dropped, profit factor of all vs kept setups.\n')
    L.append(md_table(comp[['n', 'spearman', 'kept_share', 'R_all', 'R_kept', 'R_dropped', 'wr_all', 'wr_kept', 'pf_all', 'pf_kept', 'net_all', 'net_kept', 'net_dropped']]) + '\n')
    L.append(f'Chosen grader: **{gs["chosen_model"]}** (highest pooled rank correlation on 2014-2024).\n')
    if dev is not None:
        L.append('Development search over 72 variants (model x target x feature set x recency half-life x pooled/per-strategy), best 12 by rank correlation on 2014-2024:\n')
        L.append(md_table(dev.sort_values('spearman', ascending=False).head(12)[['model', 'target', 'features', 'halflife', 'per_strategy', 'spearman', 'gap', 'years_gap_pos', 'kept_share', 'pf_all', 'pf_kept']].reset_index(drop=True)) + '\n')
        L.append('`gap` = mean R of kept minus dropped setups; `years_gap_pos` = share of the 11 development years in which the kept setups did better than the dropped ones.\n')
    L.append('Per year, chosen grader (OOS, fixed stream):\n')
    L.append(md_table(yr[['n', 'spearman', 'kept_share', 'R_all', 'R_kept', 'R_dropped', 'pf_all', 'pf_kept', 'net_all', 'net_kept']]) + '\n')
    L.append('Grade table 2014-2024 (OOS, fixed stream):\n')
    L.append(md_table(grade_table(fx[(fx['year'] >= 2014) & (fx['year'] <= 2024)])) + '\n')
    L.append('## 2. The 2025-26 test (the stream the final report is based on)\n')
    L.append('Grade table, walk-forward grader on the 2025-01..2026-09 walk-forward parameter stream:\n')
    L.append(md_table(grade_table(wfo)) + '\n')
    L.append('Walk-forward grader vs the two controls on the same 283 setups:\n')
    L.append(md_table(ctrl[['n', 'spearman', 'kept_share', 'R_all', 'R_kept', 'R_dropped', 'wr_all', 'wr_kept', 'pf_all', 'pf_kept', 'net_all', 'net_kept', 'net_dropped']]) + '\n')
    if imp is not None:
        L.append('Most useful features of the chosen grader fitted on 2010-2024, measured on the 2025-26 fixed stream (permutation importance in MSE units; negative = the feature hurt out of sample):\n')
        L.append(md_table(imp.head(12).to_frame('importance'), 5) + '\n')
    L.append('## 3. Account results 2025-01..2026-09, one account at a time\n')
    L.append('Baseline = every signal (what the final report simulates; small differences from that report come from indicators warmed on the full history instead of 45 days). '
             'B_and_up = walk-forward grader, grades A+/A/B taken (thresholds fixed at the January refit; it kept only 41% of 2025-26 setups because many looked unlike 2010-2024 setups, and it graded most orb_close30 signals F). B_and_up_trailing_thresholds = same predictions, but each setup is graded against the predictions of the previous 250 setups (causal), which keeps 57%. A_and_up and C_and_up for reference. The two control columns use the same B-and-up rule with the in-sample and the shuffled grader.\n')
    vars_ = ['baseline', 'B_and_up', 'B_and_up_trailing_thresholds', 'A_and_up', 'C_and_up', 'B_and_up_insample_grader', 'B_and_up_shuffled_grader']
    vars_ = [v for v in vars_ if v in W]
    L.append('### Aggressive configuration (15 micros, one attempt)\n'); L.append(config_table(W, vars_, 'aggressive') + '\n')
    L.append('### Safe configuration (9 micros, up to three attempts)\n'); L.append(config_table(W, vars_, 'safe') + '\n')
    L.append('Per-leg trade statistics 2025-26 (per micro, after costs):\n')
    rows = []
    for v in vars_:
        for s, m in W[v]['trade_metrics'].items():
            rows.append({'variant': v, 'leg': s, 'trades': m['trades'], 'net': round(m['net']), 'win_rate': round(m.get('win_rate', np.nan), 3), 'pf': round(m.get('profit_factor', np.nan), 2),
                         'max_dd_intraday': round(m['max_dd_intraday']), 'sharpe': round(m['sharpe_daily_ann'], 2)})
    L.append(pd.DataFrame(rows).to_markdown(index=False) + '\n')
    if F:
        L.append('## 4. Full history 2011-06..2026-09, risk-normalised (fixed parameters)\n')
        L.append('The same account simulation on the whole history, with each session\'s P&L scaled by ATR$(2025 median) / ATR$(then) so that one "unit" carries 2025-like dollar risk in every year '
                 f'(scale factor range {F["baseline"]["scale_factor_range"][0]:.1f}..{F["baseline"]["scale_factor_range"][1]:.1f}). Not literal micro counts; it answers "would the filter have helped across regimes", not "what would the account have paid in 2013". '
                 'Starts every 5th session for the calendar statistics. Note the strategies as a group were roughly flat-to-negative before 2021 (see per-year table above), so these pass rates are far below the 2025-26 ones.\n')
        vf = [v for v in ['baseline', 'B_and_up', 'A_and_up'] if v in F]
        L.append('Over the full history none of the variants beats its zero-edge control (the strategies as a group had no edge before 2021), so this section only says whether the filter changed anything relative to taking every signal: it did not, in either direction, beyond noise.\n')
        L.append('### Aggressive\n'); L.append(config_table(F, vf, 'aggressive') + '\n')
        L.append('### Safe\n'); L.append(config_table(F, vf, 'safe') + '\n')
        L.append('By two-year window (unit book, single attempt / three attempts as per configuration):\n')
        rows = []
        for per, d in F['baseline']['by_period'].items():
            r = {'period': per}
            for v in vf:
                dd = F[v]['by_period'].get(per, {})
                r[f'{v} AGG p_funded'] = round(dd.get('aggressive', {}).get('p_funded', np.nan), 2); r[f'{v} AGG net'] = round(dd.get('aggressive', {}).get('expected_net', np.nan) or np.nan)
                r[f'{v} SAFE p_funded'] = round(dd.get('safe', {}).get('p_funded', np.nan), 2); r[f'{v} SAFE net'] = round(dd.get('safe', {}).get('expected_net', np.nan) or np.nan)
            rows.append(r)
        L.append(pd.DataFrame(rows).to_markdown(index=False) + '\n')
    L.append('## Files\n')
    L.append('`grading/stream.py` (setup log + features), `grading/grader.py` (walk-forward grader, controls), `grading/dev_search.py` (model selection on 2014-2024), '
             '`grading/account.py` (engine re-run and account simulation), `grading/trailing.py` (causal trailing-threshold variant), `results/grading/` (graded setup tables, per-variant daily streams, JSON results).\n')
    open(os.path.join(ROOT, 'reports', 'grading_report.md'), 'w').write('\n'.join(L))
    print('written reports/grading_report.md')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'ridge')
