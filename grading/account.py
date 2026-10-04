"""Lucid account simulation of the two Sentinel configurations with and without the setup grade filter.

For every variant the engine is RE-RUN with the rejected signals removed (not a post-hoc drop of trade P&L), so the
intraday equity path used for the intraday breach check is exact. All three legs place at most one signal per session,
so removing a signal removes that session's trade and nothing else changes.

Variants are defined by a graded trade table (results/grading/graded_*.parquet) and a set of accepted grades.
Streams: 'wf' = walk-forward parameter path 2025-01..2026-09 (the final report's basis); 'fixed' = final parameters.
Full-history view: the fixed stream 2011-2026 with P&L risk-normalised to 2025 volatility (per-session factor
ATR$_2025 / ATR$_t, lagged), because a constant micro count is meaningless when the index was a tenth of its price.
"""
import os, sys, json, math
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.contracts import CONTRACTS
from backtest.data import load_1m
from backtest import engine
from backtest.run import prepare, WARMUP_DAYS
from backtest.lucid import Rules, campaign_fast, campaign_bootstrap, monte_carlo_fast, zero_edge_control, simulate_eval
from backtest.final_configs import rules_in_units
from backtest.career import career, run_funded
from backtest.metrics import metrics
from grading.stream import LEGS, CONTRACT, final_params, wf_path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'results', 'grading')
START, END = '2010-11-01', '2026-09-30'
CONFIGS = {'aggressive': {'eval_units': 5, 'funded_units': 5, 'reduced_units': 1, 'attempts': 1},
           'safe': {'eval_units': 3, 'funded_units': 3, 'reduced_units': 1, 'attempts': 3}}
MPU = 3   # micros per unit: one micro of each leg


class Frame:
    def __init__(self):
        self.contract = CONTRACTS[CONTRACT]
        self.df1 = load_1m(self.contract.data_symbol, (pd.Timestamp(START) - pd.Timedelta(days=WARMUP_DAYS)).strftime('%Y-%m-%d'), END)
        self._intents = {}

    def intents(self, sid, params, start, end):
        key = (sid, json.dumps(params, sort_keys=True), start, end)
        if key not in self._intents:
            _, it, _ = prepare(sid, CONTRACT, start, end, params, df1=self.df1)
            it.allow_entry &= (self.df1['session'].values <= pd.Timestamp(end).date())
            self._intents[key] = it
        return self._intents[key]

    def run(self, sid, params, start, end, reject_idx=None):
        it0 = self.intents(sid, params, start, end)
        sig = it0.sig.copy()
        if reject_idx is not None and len(reject_idx):
            sig[np.asarray(reject_idx, int)] = 0
        it = engine.Intents.__new__(engine.Intents); it.__dict__ = dict(it0.__dict__); it.sig = sig
        trades, daily, bars = engine.run(it, self.contract, return_bars=True)
        sessions = daily['session'].values
        bars = bars.copy(); bars['session'] = sessions[bars['day_id'].values]
        s0 = pd.Timestamp(start).date(); e0 = pd.Timestamp(end).date()
        bars = bars[(bars['session'] >= s0) & (bars['session'] <= e0)].reset_index(drop=True)[['ts', 'session', 'eq_low', 'eq_close']]
        daily = daily[(daily['session'] >= s0) & (daily['session'] <= e0)].reset_index(drop=True)
        trades = trades[(trades['session'] >= s0) & (trades['session'] <= e0)].reset_index(drop=True)
        return trades, daily, bars

    def leg(self, sid, stream, reject_idx=None):
        if stream == 'fixed':
            return self.run(sid, final_params(sid), START, END, reject_idx)
        parts = [self.run(sid, p, s, e, reject_idx) for (s, e, p) in wf_path(sid)]
        return (pd.concat([x[0] for x in parts]).reset_index(drop=True), pd.concat([x[1] for x in parts]).reset_index(drop=True),
                pd.concat([x[2] for x in parts]).reset_index(drop=True))


class MemLegs:
    """Aligned per-bar equity of several legs (same construction as backtest.portfolio_opt.OOSLegs, from memory)."""
    def __init__(self, legs):   # legs: dict sid -> (trades, daily, bars)
        self.ids = list(legs); frames = []; dailies = []
        for k, sid in enumerate(self.ids):
            _, d, b = legs[sid]
            ts = pd.DatetimeIndex(b['ts'])
            f = pd.DataFrame({f'low_{k}': b['eq_low'].values, f'close_{k}': b['eq_close'].values, f'sess_{k}': b['session'].values}, index=ts)
            frames.append(f[~f.index.duplicated()]); dailies.append(d.set_index('session'))
        big = pd.concat(frames, axis=1, sort=True)
        big['session'] = big[[c for c in big.columns if c.startswith('sess_')]].bfill(axis=1).iloc[:, 0]
        K = len(self.ids); L = np.zeros((len(big), K)); C = np.zeros((len(big), K))
        for k in range(K):
            lo = big[f'low_{k}']; cl = big[f'close_{k}']; has = lo.notna()
            cl_f = cl.groupby(big['session']).ffill().fillna(0.0)
            lo_f = lo.where(has, cl_f).groupby(big['session']).ffill().fillna(0.0)
            L[:, k] = lo_f.values; C[:, k] = cl_f.values
        self.session_ids, self.sess_codes = np.unique(big['session'].values, return_inverse=True)
        self.L = L; self.C = C; D = len(self.session_ids)
        self.P = np.zeros((D, K)); self.T = np.zeros((D, K))
        for k, d in enumerate(dailies):
            d = d[~d.index.duplicated()].reindex(self.session_ids)
            self.P[:, k] = d['pnl'].fillna(0.0).values; self.T[:, k] = d['trades'].fillna(0).values

    def daily(self, w):
        w = np.asarray(w, float); low = self.L @ w; D = len(self.session_ids)
        min_eq = np.zeros(D); np.minimum.at(min_eq, self.sess_codes, low)
        return pd.DataFrame({'session': self.session_ids, 'pnl': self.P @ w, 'min_eq': np.minimum(min_eq, 0.0), 'trades': (self.T @ (w > 0)).astype(int)})


def per_start_stats(d, cfg, r, start_every=1):
    """Calendar statistics per possible start session (backtest.career logic): eval pass rate, days, path to first payout."""
    pnl = d['pnl'].values; mn = d['min_eq'].values; ntr = d['trades'].values; n = len(pnl)
    rows = []
    for s in range(0, n - 2, start_every):
        e = simulate_eval(pnl, mn, s, cfg['eval_units'], r, 10 ** 6, None, ntr)
        ev1 = career(pnl, mn, ntr, s, cfg, r, stop_at_first_payout=True)
        types = [x[0] for x in ev1]; got = 'payout' in types
        rows.append({'s': s, 'eval': e['outcome'], 'eval_days': e['days'], 'got_payout': got, 'days_to_first_payout': (ev1[-1][1] - s + 1) if got else None,
                     'evals_failed_before': types.count('eval_fail'), 'funded_blown_before': types.count('funded_blown'),
                     'fees_to_first_payout': sum(x[2] for x in ev1 if x[0] == 'fee'), 'open_at_end': not got})
    ps = pd.DataFrame(rows); res = ps[ps['eval'].isin(['pass', 'fail'])]; passes = res[res['eval'] == 'pass']
    fund = []
    for s in passes['s']:
        e = simulate_eval(pnl, mn, int(s), cfg['eval_units'], r, 10 ** 6, None, ntr)
        o, end, pays = run_funded(pnl, mn, e['end_day'] + 1, cfg['funded_units'], cfg['reduced_units'], r)
        fund.append({'outcome': o, 'n_payouts': len(pays), 'gross': sum(a for _, a in pays), 'days_to_first': (pays[0][0] - e['end_day']) if pays else None})
    fd = pd.DataFrame(fund); fdr = fd[fd['outcome'] != 'alive'] if len(fd) else fd
    gp = ps[ps['got_payout']]
    f = lambda x: float(x) if x == x else None
    return {'n_starts': int(len(ps)), 'eval_pass_rate_single_attempt': f((res['eval'] == 'pass').mean()),
            'avg_days_to_pass': f(passes['eval_days'].mean()), 'median_days_to_pass': f(passes['eval_days'].median()),
            'avg_days_failed_eval_lasted': f(res.loc[res['eval'] == 'fail', 'eval_days'].mean()),
            'p_first_payout_given_funded': f((fdr['n_payouts'] >= 1).mean()) if len(fdr) else None,
            'avg_payouts_per_funded_account': f(fdr['n_payouts'].mean()) if len(fdr) else None,
            'avg_gross_paid_per_funded_account': f(fdr['gross'].mean()) if len(fdr) else None,
            'funded_outcomes': fdr['outcome'].value_counts().to_dict() if len(fdr) else {},
            'avg_days_pass_to_first_payout': f(fd['days_to_first'].dropna().mean()) if len(fd) else None,
            'share_of_starts_reaching_payout_before_data_end': f(ps['got_payout'].mean()),
            'avg_days_start_to_first_payout': f(gp['days_to_first_payout'].mean()) if len(gp) else None,
            'median_days_start_to_first_payout': f(gp['days_to_first_payout'].median()) if len(gp) else None,
            'avg_evals_failed_before_first_payout': f(gp['evals_failed_before'].mean()) if len(gp) else None,
            'avg_funded_blown_before_first_payout': f(gp['funded_blown_before'].mean()) if len(gp) else None,
            'avg_accounts_blown_before_first_payout': f((gp['evals_failed_before'] + gp['funded_blown_before']).mean()) if len(gp) else None,
            'avg_fees_until_first_payout': f(gp['fees_to_first_payout'].mean()) if len(gp) else None}


def config_stats(d, name, reps=200, per_start=True, start_every=1):
    cfg = CONFIGS[name]; r = rules_in_units(MPU)
    s = campaign_fast(d, cfg['eval_units'], cfg['funded_units'], r, max_attempts=cfg['attempts'], funded_min_room=900.0, funded_reduced=cfg['reduced_units'])
    out = {k: v for k, v in s.items() if k not in ('monthly_p_funded', 'monthly_n')}
    out['monthly_p_funded'] = s.get('monthly_p_funded')
    if reps:
        bs = campaign_bootstrap(d, cfg['eval_units'], cfg['funded_units'], r, max_attempts=cfg['attempts'], reps=reps, funded_min_room=900.0, funded_reduced=cfg['reduced_units'])
        out.update({'bs_' + k: v for k, v in bs.items() if k != 'reps'})
        z = zero_edge_control(d, cfg['eval_units'], cfg['funded_units'], r, funded_min_room=900.0, funded_reduced=cfg['reduced_units'])
        out['zero_edge_expected_net'] = z.get('expected_net_per_eval'); out['zero_edge_pass_rate'] = z.get('pass_rate')
    _, m1 = monte_carlo_fast(d, cfg['eval_units'], cfg['funded_units'], r, funded_min_room=900.0, funded_reduced=cfg['reduced_units'])
    out.update({'eval_pass_rate': m1.get('pass_rate'), 'eval_pass_within_21': m1.get('pass_within_21'), 'eval_pass_within_42': m1.get('pass_within_42'),
                'eval_median_days_to_pass': m1.get('median_days_to_pass'), 'eval_p_loss_fee': m1.get('p_loss_fee'),
                'p_breach_before_payout_given_pass': m1.get('p_breach_before_payout'), 'mean_payouts_given_pass': m1.get('mean_payouts_given_pass')})
    if per_start:
        out['per_start'] = per_start_stats(d, cfg, r, start_every)
    return out


def vol_scale(frame, daily, ref_start='2025-01-01', ref_end='2026-09-30'):
    """Per-session factor ATR$_ref / ATR$_t with ATR$_t = 60-session mean of the lagged daily RTH ATR (causal)."""
    from strategies.common import daily_atr
    c = frame.contract
    a = daily_atr(frame.df1, 14, rth_only=True, rth=(c.rth_open, c.rth_close)).rolling(60, min_periods=20).mean()
    sess = frame.df1.groupby('day_id')['session'].first()
    a = a.reindex(sess.index).ffill()          # sessions without RTH bars (holidays) carry the previous value
    a = pd.Series(a.values, index=sess.values)
    ref = a[(pd.to_datetime(a.index) >= ref_start) & (pd.to_datetime(a.index) <= ref_end)].median()
    f = (ref / a).reindex(daily['session'].values).bfill().values
    return f


def scaled(daily, f):
    d = daily.copy(); d['pnl'] = d['pnl'] * f; d['min_eq'] = d['min_eq'] * f
    return d


def variant_rejects(graded, keep, sid, stream_filter=None):
    g = graded[graded['strategy'] == sid]
    rej = g[~g['grade'].isin(keep)]
    return rej['entry_idx'].values.astype(int)


def run_variants(frame, variants, stream, reps=200, per_start=True, start_every=1, full_history=False):
    """variants: dict name -> (graded_df or None, keep tuple). Returns dict name -> results."""
    results = {}
    for vname, (graded, keep) in variants.items():
        legs = {}
        for sid in LEGS:
            rej = variant_rejects(graded, keep, sid) if graded is not None else None
            legs[sid] = frame.leg(sid, stream, rej)
        ml = MemLegs(legs); d = ml.daily([1, 1, 1])
        tr = pd.concat([legs[s][0].assign(strategy=s) for s in LEGS])
        res = {'trades': int(len(tr)), 'net_per_unit_book': float(d['pnl'].sum()), 'trade_metrics': {s: {k: v for k, v in metrics(legs[s][0], legs[s][1]).items() if k != 'monthly'} for s in LEGS}}
        if full_history:
            f = vol_scale(frame, d); d2 = scaled(d, f)
            d2 = d2[pd.to_datetime(d2['session']) >= '2011-06-01'].reset_index(drop=True)
            res['scale_factor_range'] = [float(np.nanmin(f)), float(np.nanmax(f))]
            for cname in CONFIGS:
                res[cname] = config_stats(d2, cname, reps=reps, per_start=per_start, start_every=start_every)
            # also per 2-year window pass rates (single attempt, unit book) for the time profile
            res['by_period'] = {}
            for y0 in range(2011, 2026, 2):
                dd = d2[(pd.to_datetime(d2['session']).dt.year >= y0) & (pd.to_datetime(d2['session']).dt.year <= y0 + 1)].reset_index(drop=True)
                if len(dd) > 60:
                    res['by_period'][f'{y0}-{y0 + 1}'] = {c: {k: v for k, v in config_stats(dd, c, reps=0, per_start=False).items() if k in ('p_funded', 'p_first_payout_overall', 'expected_net', 'eval_pass_rate', 'median_days_to_funded')} for c in CONFIGS}
        else:
            for cname in CONFIGS:
                res[cname] = config_stats(d, cname, reps=reps, per_start=per_start, start_every=start_every)
        results[vname] = res
        d.to_csv(os.path.join(OUT, f'daily_unit_{stream}_{vname}.csv'), index=False)
        print(f"[{stream}] {vname}: trades {res['trades']} net/unit {res['net_per_unit_book']:.0f} | AGG p_funded {res['aggressive'].get('p_funded', float('nan')):.2f} p_pay {res['aggressive'].get('p_first_payout_overall', float('nan')):.2f} net {res['aggressive'].get('expected_net', float('nan')):.0f} | SAFE p_funded {res['safe'].get('p_funded', float('nan')):.2f} p_pay {res['safe'].get('p_first_payout_overall', float('nan')):.2f} net {res['safe'].get('expected_net', float('nan')):.0f}", flush=True)
    return results


def main(grader_tag, only_full=False):
    frame = Frame()
    if only_full:
        out = json.load(open(os.path.join(OUT, f'account_results_{grader_tag}.json')))
        fx_g = pd.read_parquet(os.path.join(OUT, f'graded_fixed_{grader_tag}.parquet')); BPLUS = ('A+', 'A', 'B'); APLUS = ('A+', 'A')
        variants_fx = {'baseline': (None, None), 'B_and_up': (fx_g, BPLUS), 'A_and_up': (fx_g, APLUS)}
        out['fixed_2011_2026_volnorm'] = run_variants(frame, variants_fx, 'fixed', reps=100, per_start=True, start_every=5, full_history=True)
        json.dump(out, open(os.path.join(OUT, f'account_results_{grader_tag}.json'), 'w'), indent=1, default=float)
        return
    wf_g = pd.read_parquet(os.path.join(OUT, f'graded_wf_{grader_tag}.parquet'))
    wf_in = pd.read_parquet(os.path.join(OUT, 'graded_wf_insample.parquet'))
    wf_sh = pd.read_parquet(os.path.join(OUT, 'graded_wf_shuffled.parquet'))
    fx_g = pd.read_parquet(os.path.join(OUT, f'graded_fixed_{grader_tag}.parquet'))
    BPLUS = ('A+', 'A', 'B'); APLUS = ('A+', 'A')
    variants = {'baseline': (None, None), 'B_and_up': (wf_g, BPLUS), 'A_and_up': (wf_g, APLUS), 'C_and_up': (wf_g, ('A+', 'A', 'B', 'C')),
                'B_and_up_insample_grader': (wf_in, BPLUS), 'B_and_up_shuffled_grader': (wf_sh, BPLUS)}
    out = {'wf_2025_2026': run_variants(frame, variants, 'wf', reps=200, per_start=True)}
    json.dump(out, open(os.path.join(OUT, f'account_results_{grader_tag}.json'), 'w'), indent=1, default=float)
    variants_fx = {'baseline': (None, None), 'B_and_up': (fx_g, BPLUS), 'A_and_up': (fx_g, APLUS)}
    out['fixed_2011_2026_volnorm'] = run_variants(frame, variants_fx, 'fixed', reps=100, per_start=True, start_every=5, full_history=True)
    json.dump(out, open(os.path.join(OUT, f'account_results_{grader_tag}.json'), 'w'), indent=1, default=float)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'ridge', only_full=(len(sys.argv) > 2 and sys.argv[2] == 'full'))
