"""Lucid Trading 50K LucidFlex account simulator.

Rules encoded (cross-checked across six independent 2026 sources; see research/lucid_rules.md):
Evaluation
- Start balance 50,000; profit target +3,000 (balance >= 53,000).
- Max Loss Limit (MLL): end-of-day trailing. MLL = highest END-OF-SESSION balance - 2,000, moves only at
  session close, and once the EOD balance exceeds 52,100 the MLL locks at 50,100. A breach is INTRADAY:
  if balance + open P&L touches the MLL at any time, the account fails.
- 50% consistency rule: at the moment of passing, largest single-day profit <= 50% of total profit
  (total = balance - 50,000). Trader keeps trading until satisfied.
- Minimum 2 trading days. No daily loss limit by default. Max 4 minis / 40 micros.
Funded (sim-funded)
- Fresh 50,000 balance, same MLL mechanics (initial 48,000; locks at 50,100 after EOD > 52,100).
- Contract scaling: 20 micros (2 minis) until EOD profit >= 1,000 -> 30 micros; >= 2,000 -> 40 micros.
- Payout: needs >= 5 separate days with EOD profit >= 150 in the current cycle, cycle net positive,
  min 500, max = 50% of profit capped at 2,000, 90% to trader. Up to 5 payouts then live.
- After a payout request the MLL is set to max(MLL, 50,100) (the "lock"); balance drops by the payout
  and the MLL never falls with it.
All of this is parameterised in Rules so a variant can be tested.
"""
from dataclasses import dataclass, field
import numpy as np
import pandas as pd


@dataclass
class Rules:
    start_balance: float = 50_000.0
    target: float = 3_000.0
    mll_distance: float = 2_000.0
    lock_trigger: float = 52_100.0   # EOD balance above which MLL locks
    lock_level: float = 50_100.0
    consistency: float = 0.50        # eval only; 0 => none
    min_days: int = 2
    eval_max_micros: int = 40
    funded_scaling: tuple = ((0.0, 20), (1_000.0, 30), (2_000.0, 40))  # (profit threshold, max micros)
    payout_min_days: int = 5
    payout_day_min_profit: float = 150.0
    payout_min: float = 500.0
    payout_max: float = 2_000.0
    payout_frac: float = 0.5
    split: float = 0.90
    max_payouts: int = 5
    payout_locks_mll: bool = True
    payout_base: str = 'total'       # 'total': 50% of (balance - start); 'cycle': 50% of profit since the last payout (unconfirmed reading)
    eval_fee: float = 146.0            # one-time per evaluation (LucidFlex has no monthly fee and no time limit)
    reset_fee: float = 90.0


def _mll_update(mll, peak_eod, rules):
    new = peak_eod - rules.mll_distance
    if peak_eod > rules.lock_trigger:
        new = rules.lock_level
    return max(mll, min(new, rules.lock_level))


def simulate_eval(pnl, min_eq, start, micros, rules: Rules, horizon=120, micros_schedule=None, ntrades=None):
    """Run one evaluation starting at day index `start` with `micros` contracts (micro-equivalents; the
    per-contract daily arrays must be for ONE micro contract). Returns dict with outcome:
    'pass', 'fail', 'incomplete' (horizon exhausted) or 'censored' (data ended before resolution).
    A *trading day* is a session with at least one executed trade (ntrades > 0, or pnl/min_eq != 0 when ntrades is
    not given) on which contracts were actually traded (schedule > 0).
    micros_schedule: optional callable(day_in_eval, balance, mll, largest_day, total_profit) -> micros."""
    bal = rules.start_balance; mll = rules.start_balance - rules.mll_distance; peak = bal
    largest = 0.0; days = 0; tdays = 0
    n = len(pnl)
    last = min(n, start + horizon)
    for k in range(start, last):
        m = micros if micros_schedule is None else micros_schedule(days, bal, mll, largest, bal - rules.start_balance)
        m = min(m, rules.eval_max_micros)
        if m <= 0:
            days += 1
            continue
        traded = (ntrades[k] > 0) if ntrades is not None else (pnl[k] != 0.0 or min_eq[k] != 0.0)
        # intraday breach check
        if bal + min_eq[k] * m <= mll:
            return {'outcome': 'fail', 'days': days + 1, 'end_day': k, 'balance': mll, 'largest_day': largest}
        day_pnl = pnl[k] * m
        bal += day_pnl; days += 1
        if traded:
            tdays += 1
        largest = max(largest, day_pnl)
        peak = max(peak, bal)
        mll = _mll_update(mll, peak, rules)
        if bal <= mll:
            return {'outcome': 'fail', 'days': days, 'end_day': k, 'balance': bal, 'largest_day': largest}
        profit = bal - rules.start_balance
        if profit >= rules.target and tdays >= rules.min_days and (rules.consistency <= 0 or largest <= rules.consistency * profit):
            return {'outcome': 'pass', 'days': days, 'end_day': k, 'balance': bal, 'largest_day': largest}
    outcome = 'censored' if last == n and start + horizon > n else 'incomplete'
    return {'outcome': outcome, 'days': days, 'end_day': last - 1, 'balance': bal, 'largest_day': largest}


def simulate_funded(pnl, min_eq, start, micros_policy, rules: Rules, horizon=250, min_profit_to_request=4_000.0,
                    request_asap_after_first=False, stop_after_payouts=None):
    """Simulate a funded LucidFlex account from day index `start`.
    micros_policy: callable(balance, mll, profit_since_start, n_payouts, max_micros_allowed) -> micros to trade.
    Payout policy: request when eligible (5 qualifying days, cycle net positive, profit >= payout_min/frac) AND
    profit >= min_profit_to_request (default 4,000 so that the first payout is the full 2,000 and the balance
    after the lock keeps >= 1,900 of room)."""
    bal = rules.start_balance; mll = bal - rules.mll_distance; peak = bal
    payouts = []; qual_days = 0; cycle_start_bal = bal; days = 0
    n = len(pnl)
    stop_after = rules.max_payouts if stop_after_payouts is None else stop_after_payouts
    for k in range(start, min(n, start + horizon)):
        profit = bal - rules.start_balance
        cap = rules.funded_scaling[0][1]
        for thr, mx in rules.funded_scaling:
            if profit >= thr:
                cap = mx
        m = min(micros_policy(bal, mll, profit, len(payouts), cap), cap)
        if m > 0:
            if bal + min_eq[k] * m <= mll:
                return {'outcome': 'breach', 'days': days + 1, 'end_day': k, 'payouts': payouts, 'paid': sum(payouts) * rules.split,
                        'balance': mll, 'first_payout_day': payouts and payouts_days[0] or None}
            day_pnl = pnl[k] * m
            bal += day_pnl
            if day_pnl >= rules.payout_day_min_profit:
                qual_days += 1
        days += 1
        peak = max(peak, bal)
        mll = _mll_update(mll, peak, rules)
        if bal <= mll:
            return {'outcome': 'breach', 'days': days, 'end_day': k, 'payouts': payouts, 'paid': sum(payouts) * rules.split,
                    'balance': bal, 'first_payout_day': payouts_days[0] if payouts else None}
        profit = bal - rules.start_balance
        cycle_net = bal - cycle_start_bal
        amount = min(rules.payout_max, rules.payout_frac * (profit if rules.payout_base == 'total' else max(0.0, cycle_net)))
        eligible = qual_days >= rules.payout_min_days and cycle_net > 0 and amount >= rules.payout_min
        want = profit >= min_profit_to_request or (request_asap_after_first and len(payouts) > 0)
        if eligible and want:
            payouts.append(amount)
            if len(payouts) == 1:
                payouts_days = [days]
            bal -= amount
            if rules.payout_locks_mll:
                mll = max(mll, rules.lock_level)
            qual_days = 0; cycle_start_bal = bal
            if len(payouts) >= stop_after:
                return {'outcome': 'live', 'days': days, 'end_day': k, 'payouts': payouts, 'paid': sum(payouts) * rules.split,
                        'balance': bal, 'first_payout_day': payouts_days[0]}
    return {'outcome': 'alive', 'days': days, 'end_day': min(n, start + horizon) - 1, 'payouts': payouts,
            'paid': sum(payouts) * rules.split, 'balance': bal, 'first_payout_day': (payouts and payouts_days[0]) or None,
            'censored': start + horizon > n}


def constant_micros(m):
    return lambda bal, mll, profit, npay, cap: min(m, cap)


def monte_carlo(daily: pd.DataFrame, eval_micros, funded_policy, rules: Rules, start_every=1, eval_horizon=120,
                funded_horizon=250, min_profit_to_request=4_000.0, eval_schedule=None, funded_follows_eval=True):
    """Start an evaluation on every `start_every`-th session; if it passes, run the funded account from the next
    session. Returns per-start DataFrame and a summary dict. `daily` must have columns session, pnl, min_eq for
    ONE micro contract."""
    pnl = daily['pnl'].values; min_eq = daily['min_eq'].values; sessions = daily['session'].values
    ntr = daily['trades'].values if 'trades' in daily else None
    rows = []
    n = len(pnl)
    for s in range(0, max(0, n - rules.min_days), start_every):
        ev = simulate_eval(pnl, min_eq, s, eval_micros, rules, eval_horizon, eval_schedule, ntr)
        row = {'start': sessions[s], 'eval': ev['outcome'], 'eval_days': ev['days'], 'eval_largest': ev['largest_day'], 'eval_balance': ev['balance']}
        if ev['outcome'] == 'pass' and funded_follows_eval and ev['end_day'] + 1 < n:
            fd = simulate_funded(pnl, min_eq, ev['end_day'] + 1, funded_policy, rules, funded_horizon, min_profit_to_request)
            row.update({'funded': fd['outcome'], 'funded_days': fd['days'], 'n_payouts': len(fd['payouts']), 'paid': fd['paid'],
                        'first_payout_day': fd['first_payout_day'], 'funded_balance': fd['balance'], 'funded_censored': bool(fd.get('censored', False))})
        rows.append(row)
    df = pd.DataFrame(rows, columns=['start', 'eval', 'eval_days', 'eval_largest', 'eval_balance', 'funded', 'funded_days', 'n_payouts', 'paid',
                                     'first_payout_day', 'funded_balance', 'funded_censored'])
    summ = summarize_mc(df, rules)
    return df, summ


def summarize_mc(df: pd.DataFrame, rules: Rules):
    """Summary over evaluation starts. Evals that could not resolve because the DATA ENDED ('censored') are excluded
    from every rate; evals that exhausted the horizon ('incomplete') count as non-passes."""
    out = {}
    n = len(df)
    out['n_starts'] = n
    res = df[df['eval'] != 'censored'] if n else df
    out['n_censored'] = int(n - len(res))
    m = len(res)
    out['pass_rate'] = float((res['eval'] == 'pass').mean()) if m else np.nan
    out['fail_rate'] = float((res['eval'] == 'fail').mean()) if m else np.nan
    out['incomplete_rate'] = float((res['eval'] == 'incomplete').mean()) if m else np.nan
    p = res[res['eval'] == 'pass']
    out['median_days_to_pass'] = float(p['eval_days'].median()) if len(p) else np.nan
    out['p90_days_to_pass'] = float(p['eval_days'].quantile(0.9)) if len(p) else np.nan
    f = p.dropna(subset=['funded']) if len(p) else p
    if len(f):
        # funded runs still alive with no payout at the data end are censored for the first-payout question
        fc = f['funded_censored'].fillna(False).astype(bool) if 'funded_censored' in f else pd.Series(False, index=f.index)
        fr = f[~((f['funded'] == 'alive') & (f['n_payouts'] == 0) & fc)]
        out['n_funded_resolved'] = int(len(fr))
        out['p_first_payout_given_pass'] = float((fr['n_payouts'] >= 1).mean()) if len(fr) else np.nan
        out['p_breach_before_payout'] = float(((fr['funded'] == 'breach') & (fr['n_payouts'] == 0)).mean()) if len(fr) else np.nan
        out['mean_paid_given_pass'] = float(fr['paid'].mean()) if len(fr) else np.nan
        out['median_days_to_first_payout'] = float(fr['first_payout_day'].dropna().median()) if fr['first_payout_day'].notna().any() else np.nan
        out['mean_payouts_given_pass'] = float(fr['n_payouts'].mean()) if len(fr) else np.nan
        out['p_live_5_payouts'] = float((fr['funded'] == 'live').mean()) if len(fr) else np.nan
        out['p_first_payout_unconditional'] = out['pass_rate'] * out['p_first_payout_given_pass'] if len(fr) else np.nan
        out['expected_paid_per_eval'] = out['pass_rate'] * out['mean_paid_given_pass'] if len(fr) else np.nan
        out['expected_net_per_eval'] = out['expected_paid_per_eval'] - rules.eval_fee if len(fr) else np.nan
    # pass-within-k curves (k sessions after the start) and the loss-of-fee probability
    for k in (21, 42, 63):
        out[f'pass_within_{k}'] = float(((res['eval'] == 'pass') & (res['eval_days'] <= k)).mean()) if m else np.nan
    out['p_loss_fee'] = float(res['eval'].isin(['fail', 'incomplete']).mean()) if m else np.nan
    # primary rates over starts that had the full evaluation horizon available (no censoring selection)
    if 'full_horizon' in df and m:
        fh = res[res['full_horizon'].astype(bool)]
        out['n_full_horizon'] = int(len(fh)); out['pass_rate_full_horizon'] = float((fh['eval'] == 'pass').mean()) if len(fh) else np.nan
    # effective sample size: overlapping starts are highly correlated; ~ resolved starts / median sessions to resolve
    if m:
        med_res = float(res['eval_days'].median()) if res['eval_days'].notna().any() else np.nan
        out['n_effective'] = float(m / max(1.0, med_res)) if med_res == med_res else np.nan
    # monthly statistics by start month (censored excluded):
    #   monthly_pass_rate  = P(pass within 21 sessions | start in month)   <- what "can I pass this month" means
    #   monthly_fail_rate  = P(fail within 21 sessions | start in month)
    #   monthly_pass_rate_eventual = P(pass within the horizon | start in month)
    #   monthly_n = number of resolved starts in the month (months with < 15 are thin)
    if m:
        mo = pd.to_datetime(res['start']).dt.to_period('M').astype(str)
        g = res.groupby(mo)
        out['monthly_pass_rate'] = g.apply(lambda x: float(((x['eval'] == 'pass') & (x['eval_days'] <= 21)).mean())).to_dict()
        out['monthly_fail_rate'] = g.apply(lambda x: float(((x['eval'] == 'fail') & (x['eval_days'] <= 21)).mean())).to_dict()
        out['monthly_pass_rate_eventual'] = g['eval'].apply(lambda x: float((x == 'pass').mean())).to_dict()
        out['monthly_n'] = g.size().astype(int).to_dict()
    else:
        out['monthly_pass_rate'] = {}; out['monthly_fail_rate'] = {}; out['monthly_pass_rate_eventual'] = {}; out['monthly_n'] = {}
    return out


# =====================================================================================================================
# Fast (numba) Monte Carlo for the standard policies, block bootstrap, zero-edge control
# =====================================================================================================================
from numba import njit


@njit(cache=True)
def _mc_nb(pnl, min_eq, ntr, micros, f_base, f_min_room, f_reduced, start_balance, target, mll_dist, lock_trig, lock_lvl,
           consistency, min_days, eval_max, scal_thr, scal_mx, pay_days, pay_day_min, pay_min, pay_max, pay_frac, split,
           max_pay, pay_locks, eval_h, funded_h, min_profit_req, start_every):
    n = pnl.shape[0]
    ns = (max(0, n - min_days) + start_every - 1) // start_every
    ev_out = np.zeros(ns, np.int8); ev_days = np.zeros(ns, np.int32); ev_end = np.zeros(ns, np.int32)
    fd_out = np.zeros(ns, np.int8); fd_np = np.zeros(ns, np.int32); fd_paid = np.zeros(ns); fd_first = np.full(ns, -1, np.int32)
    fd_cens = np.zeros(ns, np.int8); starts = np.zeros(ns, np.int32)
    k = 0
    for s in range(0, max(0, n - min_days), start_every):
        starts[k] = s
        # ---------------- evaluation
        bal = start_balance; mll = start_balance - mll_dist; peak = bal; largest = 0.0; days = 0; tdays = 0
        last = min(n, s + eval_h); out = 2; endd = last - 1
        m = min(micros, eval_max)
        for i in range(s, last):
            if bal + min_eq[i] * m <= mll:
                out = 0; days += 1; endd = i; bal = mll; break
            dp = pnl[i] * m; bal += dp; days += 1
            if ntr[i] > 0:
                tdays += 1
            if dp > largest:
                largest = dp
            if bal > peak:
                peak = bal
            newm = peak - mll_dist
            if peak > lock_trig:
                newm = lock_lvl
            if newm > mll:
                mll = min(newm, lock_lvl)
            if bal <= mll:
                out = 0; endd = i; break
            profit = bal - start_balance
            if profit >= target and tdays >= min_days and (consistency <= 0 or largest <= consistency * profit):
                out = 1; endd = i; break
        if out == 2 and last == n and s + eval_h > n:
            out = 3
        ev_out[k] = out; ev_days[k] = days; ev_end[k] = endd
        # ---------------- funded
        if out == 1 and endd + 1 < n:
            s2 = endd + 1
            bal = start_balance; mll = bal - mll_dist; peak = bal; npay = 0; paid = 0.0; qual = 0; cyc = bal; fdays = 0
            fo = 3; first = -1
            last2 = min(n, s2 + funded_h)
            for i in range(s2, last2):
                profit = bal - start_balance
                cap = scal_mx[0]
                for j in range(scal_thr.shape[0]):
                    if profit >= scal_thr[j]:
                        cap = scal_mx[j]
                mm = f_base if (bal - mll) >= f_min_room else f_reduced
                if mm > cap:
                    mm = cap
                if mm > 0:
                    if bal + min_eq[i] * mm <= mll:
                        fo = 1; fdays += 1; break
                    dp = pnl[i] * mm; bal += dp
                    if dp >= pay_day_min:
                        qual += 1
                fdays += 1
                if bal > peak:
                    peak = bal
                newm = peak - mll_dist
                if peak > lock_trig:
                    newm = lock_lvl
                if newm > mll:
                    mll = min(newm, lock_lvl)
                if bal <= mll:
                    fo = 1; break
                profit = bal - start_balance
                amount = min(pay_max, pay_frac * profit)
                if qual >= pay_days and (bal - cyc) > 0 and amount >= pay_min and profit >= min_profit_req:
                    npay += 1; paid += amount * split
                    if first < 0:
                        first = fdays
                    bal -= amount
                    if pay_locks and lock_lvl > mll:
                        mll = lock_lvl
                    qual = 0; cyc = bal
                    if npay >= max_pay:
                        fo = 2; break
            fd_out[k] = fo; fd_np[k] = npay; fd_paid[k] = paid; fd_first[k] = first
            fd_cens[k] = 1 if (fo == 3 and s2 + funded_h > n) else 0
        k += 1
    return starts, ev_out, ev_days, ev_end, fd_out, fd_np, fd_paid, fd_first, fd_cens


_EV = {0: 'fail', 1: 'pass', 2: 'incomplete', 3: 'censored'}
_FD = {0: None, 1: 'breach', 2: 'live', 3: 'alive'}


def monte_carlo_fast(daily, micros, funded_base=None, rules: Rules = None, start_every=1, eval_horizon=120, funded_horizon=250,
                     min_profit_to_request=4_000.0, funded_min_room=900.0, funded_reduced=None):
    """numba Monte Carlo with constant eval micros and the standard funded policy (base micros while the room to the
    MLL is >= funded_min_room, else funded_reduced; always within the scaling cap). Same outputs as monte_carlo."""
    rules = rules or Rules()
    res = _run_nb(daily, micros, funded_base, rules, start_every, eval_horizon, funded_horizon, min_profit_to_request, funded_min_room, funded_reduced)
    pnl = daily['pnl'].values
    starts, ev_out, ev_days, ev_end, fd_out, fd_np, fd_paid, fd_first, fd_cens = res
    sessions = daily['session'].values
    df = pd.DataFrame({'start': sessions[starts], 'eval': [_EV[int(x)] for x in ev_out], 'eval_days': ev_days, 'eval_end': ev_end,
                       'funded': [_FD[int(x)] for x in fd_out], 'n_payouts': fd_np, 'paid': fd_paid,
                       'first_payout_day': [int(x) if x >= 0 else np.nan for x in fd_first], 'funded_censored': fd_cens.astype(bool)})
    df.loc[df['eval'] != 'pass', ['funded', 'n_payouts', 'paid', 'first_payout_day']] = [None, 0, 0.0, np.nan]
    df['full_horizon'] = (starts + eval_horizon) <= len(pnl)
    return df, summarize_mc(df, rules)


def _fast_stats(ev_out, ev_days, fd_np, fd_paid, fd_out, fd_cens, rules, k=21):
    """Headline statistics straight from the simulator arrays (no pandas), for bootstrap replicates."""
    res = ev_out != 3
    m = int(res.sum())
    if m == 0:
        return {'pass_rate': np.nan, 'pass_within_21': np.nan, 'p_first_payout_unconditional': np.nan, 'expected_net_per_eval': np.nan, 'p_loss_fee': np.nan}
    passed = res & (ev_out == 1)
    pr = passed.sum() / m
    pw = (passed & (ev_days <= k)).sum() / m
    pl = (res & ((ev_out == 0) | (ev_out == 2))).sum() / m
    # funded resolved: passed and not (alive with no payout and censored)
    fr = passed & ~((fd_out == 3) & (fd_np == 0) & (fd_cens == 1))
    nfr = int(fr.sum())
    if nfr:
        pfp = (fd_np[fr] >= 1).sum() / nfr; paid = fd_paid[fr].mean()
        return {'pass_rate': pr, 'pass_within_21': pw, 'p_first_payout_unconditional': pr * pfp, 'expected_net_per_eval': pr * paid - rules.eval_fee, 'p_loss_fee': pl}
    return {'pass_rate': pr, 'pass_within_21': pw, 'p_first_payout_unconditional': 0.0 if pr == 0 else np.nan, 'expected_net_per_eval': -rules.eval_fee if pr == 0 else np.nan, 'p_loss_fee': pl}


def _run_nb(daily, micros, funded_base, rules, start_every=1, eval_horizon=120, funded_horizon=250, min_profit_to_request=4_000.0,
            funded_min_room=900.0, funded_reduced=None):
    pnl = np.ascontiguousarray(daily['pnl'].values, dtype=np.float64); mn = np.ascontiguousarray(daily['min_eq'].values, dtype=np.float64)
    ntr = np.ascontiguousarray(daily['trades'].values, dtype=np.int64) if 'trades' in daily else (np.abs(pnl) + np.abs(mn) > 0).astype(np.int64)
    fb = int(min(micros, 20) if funded_base is None else funded_base)
    fr = int(max(1, fb // 3) if funded_reduced is None else funded_reduced)
    thr = np.array([t for t, _ in rules.funded_scaling], dtype=np.float64); mx = np.array([m for _, m in rules.funded_scaling], dtype=np.int64)
    return _mc_nb(pnl, mn, ntr, int(micros), fb, float(funded_min_room), fr, rules.start_balance, rules.target, rules.mll_distance,
                  rules.lock_trigger, rules.lock_level, rules.consistency, int(rules.min_days), int(rules.eval_max_micros), thr, mx,
                  int(rules.payout_min_days), rules.payout_day_min_profit, rules.payout_min, rules.payout_max, rules.payout_frac, rules.split,
                  int(rules.max_payouts), bool(rules.payout_locks_mll), int(eval_horizon), int(funded_horizon), float(min_profit_to_request), int(start_every))


def block_bootstrap_indices(n, block, rng):
    """Moving-block bootstrap: concatenate random blocks of `block` consecutive sessions to length n."""
    nb = int(np.ceil(n / block)); starts = rng.integers(0, max(1, n - block + 1), size=nb)
    idx = np.concatenate([np.arange(s, s + block) for s in starts])[:n]
    return idx


def bootstrap_summary(daily, micros, funded_base=None, rules: Rules = None, reps=200, block=20, seed=0, **kw):
    """Block-bootstrap distribution of the headline Monte Carlo statistics. Returns dict of percentiles (5/50/95),
    P(expected_net > 0) and the number of reps. Uses the fast simulator and array-only statistics."""
    rules = rules or Rules(); rng = np.random.default_rng(seed)
    n = len(daily); cols = ['pass_rate', 'p_first_payout_unconditional', 'expected_net_per_eval', 'pass_within_21', 'p_loss_fee']
    acc = {c: [] for c in cols}
    base = daily.reset_index(drop=True)
    pnl0 = base['pnl'].values.astype(np.float64); mn0 = base['min_eq'].values.astype(np.float64)
    ntr0 = base['trades'].values.astype(np.int64) if 'trades' in base else (np.abs(pnl0) + np.abs(mn0) > 0).astype(np.int64)
    for r in range(reps):
        idx = block_bootstrap_indices(n, block, rng)
        d = pd.DataFrame({'pnl': pnl0[idx], 'min_eq': mn0[idx], 'trades': ntr0[idx]})
        starts, ev_out, ev_days, ev_end, fd_out, fd_np, fd_paid, fd_first, fd_cens = _run_nb(d, micros, funded_base, rules, **kw)
        st = _fast_stats(ev_out, ev_days, fd_np, fd_paid, fd_out, fd_cens, rules)
        for c in cols:
            acc[c].append(st.get(c, np.nan))
    out = {'reps': reps, 'block': block}
    for c in cols:
        a = np.array(acc[c], dtype=float); a = a[~np.isnan(a)]
        if len(a):
            out[c + '_p05'] = float(np.percentile(a, 5)); out[c + '_p50'] = float(np.percentile(a, 50)); out[c + '_p95'] = float(np.percentile(a, 95))
    a = np.array(acc['expected_net_per_eval'], dtype=float); a = a[~np.isnan(a)]
    out['p_expected_net_positive'] = float((a > 0).mean()) if len(a) else np.nan
    return out


def zero_edge_control(daily, micros, funded_base=None, rules: Rules = None, **kw):
    """Same Monte Carlo on the DEMEANED daily stream (edge removed, volatility and intraday structure kept): what the
    simulator would report for a strategy with no edge. A candidate must beat this clearly."""
    rules = rules or Rules()
    d = daily.copy(); mu = d['pnl'].mean()
    d['pnl'] = d['pnl'] - mu; d['min_eq'] = np.minimum(d['min_eq'] - mu, 0.0)
    starts, ev_out, ev_days, ev_end, fd_out, fd_np, fd_paid, fd_first, fd_cens = _run_nb(d, micros, funded_base, rules, **kw)
    return _fast_stats(ev_out, ev_days, fd_np, fd_paid, fd_out, fd_cens, rules)
