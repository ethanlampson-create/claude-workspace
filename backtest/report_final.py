"""Generate reports/final_report.md from results/final_selection.csv, results/final_configs.json and the legs' final.json.
python3 -m backtest.report_final
"""
import json, os, sys
import numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pct(x):
    return 'n/a' if x is None or (isinstance(x, float) and np.isnan(x)) else f'{100 * x:.0f}%'


def money(x):
    return 'n/a' if x is None or (isinstance(x, float) and np.isnan(x)) else f'${x:,.0f}'


def cfg_table(c):
    rows = [
        ('Evaluation size', f"{c['eval_micros']} micros total (unit {c['unit']} x {c['eval_units']})"),
        ('Funded size', f"{c['funded_micros']} micros, cut to {c['reduced_units'] * c['micros_per_unit']} when room to the MLL < $900, scaling cap respected"),
        ('Attempts modelled', str(c['attempts'])),
        ('P(pass) per attempt', pct(c.get('eval_pass_rate'))),
        ('P(pass within 21 sessions)', pct(c.get('eval_pass_within_21'))),
        ('P(pass within 42 sessions)', pct(c.get('eval_pass_within_42'))),
        ('Median sessions to pass', str(c.get('eval_median_days_to_pass'))),
        ('P(lose the fee) per attempt', pct(c.get('eval_p_loss_fee'))),
        ('P(funded) within attempts', f"{pct(c.get('p_funded'))} (bootstrap 5-95%: {pct(c.get('bs_p_funded_p05'))} - {pct(c.get('bs_p_funded_p95'))})"),
        ('Median sessions to funded', str(c.get('median_days_to_funded'))),
        ('P(first payout | funded)', pct(c.get('p_first_payout_given_funded'))),
        ('P(first payout) overall', f"{pct(c.get('p_first_payout_overall'))} (bootstrap: {pct(c.get('bs_p_first_payout_overall_p05'))} - {pct(c.get('bs_p_first_payout_overall_p95'))})"),
        ('Median sessions funded -> first payout', str(c.get('median_days_to_first_payout'))),
        ('Mean paid | funded (90% split)', money(c.get('mean_paid_given_funded'))),
        ('Mean fees per campaign', money(c.get('mean_fees'))),
        ('Expected net per campaign', f"{money(c.get('expected_net'))} (bootstrap 5/50/95%: {money(c.get('bs_expected_net_p05'))} / {money(c.get('bs_expected_net_p50'))} / {money(c.get('bs_expected_net_p95'))}; P(net>0) {pct(c.get('bs_p_expected_net_positive'))})"),
        ('Zero-edge control (same stream demeaned)', f"expected net {money(c.get('zero_edge_expected_net_per_eval'))}, pass rate {pct(c.get('zero_edge_pass_rate'))}"),
        ('Minimum monthly P(funded)', pct(c.get('min_monthly_p_funded'))),
    ]
    return '| Item | Value |\n|---|---|\n' + '\n'.join(f'| {a} | {b} |' for a, b in rows)


def monthly_table(c):
    m = c.get('monthly_pass_rate_21') or {}; n = c.get('monthly_n') or {}; mf = c.get('monthly_p_funded') or {}
    keys = sorted(set(m) | set(mf))
    if not keys:
        return ''
    out = '| Start month | starts | P(pass within 21 sessions) | P(funded within attempts) |\n|---|---|---|---|\n'
    for k in keys:
        out += f"| {k} | {n.get(k, '')} | {pct(m.get(k))} | {pct(mf.get(k))} |\n"
    return out


def main():
    sel_p = os.path.join(ROOT, 'results', 'final_selection.csv'); cfg_p = os.path.join(ROOT, 'results', 'final_configs.json')
    sel = pd.read_csv(sel_p) if os.path.exists(sel_p) else pd.DataFrame()
    cfg = json.load(open(cfg_p)) if os.path.exists(cfg_p) else None
    L = []
    L.append('# Lucid 50K Flex: strategy research, backtest and account simulation. Final report\n')
    L.append('Data: 1-minute S&P 500 / Nasdaq 100 / gold proxies (histdata.com) Nov 2010 - Sep 2026, validated against ES/NQ/GC futures. '
             'Costs: $1.30 round trip per micro, 1 tick slippage per side on market/stop fills, limit fills only on trade-through. '
             'Rules: `research/lucid_rules.md`. Engine and simulator audited (tests/, 98 tests).\n')
    L.append('## How to read the numbers\n')
    L.append('- **Walk-forward OOS 2025** = parameters chosen only on the trailing 12 months, traded on the next 3, rolled 2022-2026; the 2025-01..2026-09 slice is the honest estimate. In-sample (MAIN) numbers are shown for reference only.\n'
             '- **Bootstrap bands** are moving-block bootstraps of the daily P&L (block 20 sessions). Overlapping evaluation starts make the raw start count overstate precision roughly five-fold.\n'
             '- **Zero-edge control** = the same daily stream with its mean removed. A configuration must beat its control clearly to mean anything.\n'
             '- **P(pass within 21 sessions)** by start month is what "monthly pass rate" means here: evaluations started in that month that pass within about a month.\n')
    if len(sel):
        L.append('## Candidate strategies (per micro contract, after costs)\n')
        cols = ['id', 'contract', 'fixed_main_pf', 'fixed_prior_pf', 'wf25_trades', 'wf25_net', 'wf25_pf', 'wf25_sharpe', 'wf25_pos_months', 'wfall_pf', 'lb_micros', 'exp_net', 'lb_exp_net', 'zero_edge', 'recommended']
        cols = [c for c in cols if c in sel]
        t = sel[cols].copy()
        for c in t.columns:
            if t[c].dtype.kind == 'f':
                t[c] = t[c].round(2)
        L.append(t.to_markdown(index=False) + '\n')
        L.append('Columns: fixed_* = in-sample profit factor with the final parameters (MAIN 2025-26, PRIOR 2023-24); wf25_* = walk-forward OOS 2025-26; wfall_pf = walk-forward OOS 2022-26; lb_micros/exp_net/lb_exp_net = size chosen by bootstrap lower bound, point and 5th-percentile expected net per evaluation; zero_edge = control; recommended = lower bound > 0 and beats control.\n')
    if cfg:
        L.append('## Portfolio legs\n')
        L.append('Legs: ' + ', '.join(cfg['legs']) + '\n')
        corr = pd.DataFrame(cfg['correlation'])
        L.append('Daily P&L correlation (walk-forward OOS 2025):\n\n' + corr.round(2).to_markdown() + '\n')
        for name, key in (('Configuration A: Aggressive (fast pass, first payout)', 'aggressive'), ('Configuration B: Safe (one evaluation reaches funded)', 'safe')):
            c = cfg[key]
            L.append(f'## {name}\n')
            L.append(f"Weights per leg (micros): {dict(zip(cfg['legs'], c['weights']))}\n")
            L.append(cfg_table(c) + '\n')
            mt = monthly_table(c)
            if mt:
                L.append('Monthly view (start month of the evaluation):\n\n' + mt)
        L.append('## Strategy rules\n')
        for id_ in cfg['legs']:
            p = os.path.join(ROOT, 'results', id_, 'final.json')
            if os.path.exists(p):
                j = json.load(open(p))
                L.append(f"### {id_} ({j.get('contract')})\n\nParameters: `{json.dumps(j.get('params'))}`\n\nModule: `strategies/{id_}.py`. Details and attempt log: `results/{id_}/README.md`; verification: `results/{id_}/verify.md` (if present).\n")
    L.append('## Caveats that matter\n')
    L.append('- Proxy data: index CFD prices, not the futures contract; intraday returns correlate 0.87-0.89 hourly with ES/NQ/GC, but fills, spreads and overnight sessions differ. Early-close (holiday) sessions are skipped.\n'
             '- Rule interpretations encoded conservatively but unconfirmed with Lucid directly: payout base (50% of total profit vs cycle profit), MLL lock at $50,100 on payout request, one-time evaluation fee. See `research/lucid_rules.md`.\n'
             '- Selection effects: many strategies and parameters were examined; walk-forward and bootstrap bands reduce but do not remove the optimism. Treat lower bounds as the planning numbers.\n'
             '- 2025-2026 included an unusual volatility regime (April 2025 tariff crash, record gold run). Monthly tables show where the strategies did not work.\n')
    os.makedirs(os.path.join(ROOT, 'reports'), exist_ok=True)
    open(os.path.join(ROOT, 'reports', 'final_report.md'), 'w').write('\n'.join(L))
    print('wrote reports/final_report.md')


if __name__ == '__main__':
    main()
