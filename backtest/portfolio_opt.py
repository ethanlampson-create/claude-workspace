"""Portfolio construction over candidate strategy legs with EXACT combined intraday equity.

align_legs(legs, start, end) runs each leg once (per 1 micro) and returns aligned per-bar equity matrices so that any
integer weight vector (micros per leg) can be evaluated in milliseconds:
    daily(w) -> session, pnl = P @ w, min_eq = min over bars of (L @ w) per session, trades = T @ (w>0)
search() enumerates small integer grids (or coordinate descent) maximising a Lucid campaign objective.
"""
import itertools, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.portfolio import run_leg
from backtest.lucid import Rules
from backtest.campaign import campaign_mc, eval_constant, funded_room


class AlignedLegs:
    def __init__(self, legs, start, end, slip_ticks=None):
        self.legs = legs
        frames = []; dailies = []
        for k, leg in enumerate(legs):
            leg = dict(leg); leg['micros'] = 1
            tr, d, b = run_leg(leg, start, end, slip_ticks)
            sess = pd.Series(d['session'].values[b['day_id'].values], index=b['ts'].values)
            f = pd.DataFrame({f'low_{k}': b['eq_low'].values, f'close_{k}': b['eq_close'].values, f'sess_{k}': sess.values}, index=b['ts'].values)
            f = f[~f.index.duplicated()]
            frames.append(f); dailies.append(d.set_index('session'))
        big = pd.concat(frames, axis=1, sort=True)
        sess_cols = [c for c in big.columns if c.startswith('sess_')]
        big['session'] = big[sess_cols].bfill(axis=1).iloc[:, 0]
        K = len(legs)
        L = np.zeros((len(big), K)); C = np.zeros((len(big), K))
        for k in range(K):
            lo = big[f'low_{k}']; cl = big[f'close_{k}']; has = lo.notna()
            cl_f = cl.groupby(big['session']).ffill().fillna(0.0)
            lo_f = lo.where(has, cl_f).groupby(big['session']).ffill().fillna(0.0)
            L[:, k] = lo_f.values; C[:, k] = cl_f.values
        self.sessions_bar = big['session'].values
        self.session_ids, self.sess_codes = np.unique(self.sessions_bar, return_inverse=True)
        self.L = L; self.C = C
        D = len(self.session_ids)
        self.P = np.zeros((D, K)); self.T = np.zeros((D, K))
        for k, d in enumerate(dailies):
            d = d.reindex(self.session_ids)
            self.P[:, k] = d['pnl'].fillna(0.0).values; self.T[:, k] = d['trades'].fillna(0).values
        self.daily_corr = pd.DataFrame(self.P, columns=[l['strategy'] + '/' + l['contract'] for l in legs]).corr()

    def daily(self, w):
        w = np.asarray(w, float)
        low = self.L @ w
        D = len(self.session_ids)
        min_eq = np.full(D, 0.0)
        np.minimum.at(min_eq, self.sess_codes, low)
        return pd.DataFrame({'session': self.session_ids, 'pnl': self.P @ w, 'min_eq': np.minimum(min_eq, 0.0),
                             'max_eq': np.maximum((self.C @ w)[np.r_[np.where(np.diff(self.sess_codes) != 0)[0], len(self.sess_codes) - 1]], 0.0),
                             'trades': (self.T @ (w > 0)).astype(int)})

    def evaluate(self, w, rules=None, max_attempts=3, funded_base=None):
        rules = rules or Rules()
        d = self.daily(w)
        total = int(sum(w))
        fb = funded_base if funded_base is not None else min(total, 20)
        _, s = campaign_mc(d, eval_constant(1), funded_room(1, 900.0, 1) if total == 0 else _scaled_funded(w, fb, total), rules, max_attempts=max_attempts)
        return s, d


def _scaled_funded(w, funded_base, total):
    """Funded policy returning a multiplier on the unit weight vector (micros per leg = w * m / total)."""
    # The campaign simulator trades `micros` units of the per-unit daily stream; our unit is the weight vector w.
    # We approximate funded sizing by scaling the whole book: m = funded_base/total units, reduced near the lock.
    def f(bal, mll, profit, npay, cap):
        m = funded_base / total if total else 0
        if (bal - mll) < 900.0:
            m = m / 2
        return min(m, cap / total if total else 0)
    return f


def search(al: AlignedLegs, grid=(0, 5, 10, 15, 20), max_total=40, objective='expected_net', min_monthly=None, rules=None, max_attempts=3, top=15):
    K = len(al.legs); rows = []
    for w in itertools.product(grid, repeat=K):
        if sum(w) == 0 or sum(w) > max_total:
            continue
        s, d = al.evaluate(w, rules, max_attempts)
        row = {'w': w, 'total': sum(w), **{k: v for k, v in s.items() if k != 'monthly_p_funded'}}
        row['min_monthly'] = min(s['monthly_p_funded'].values()) if s.get('monthly_p_funded') else np.nan
        rows.append(row)
    df = pd.DataFrame(rows)
    if min_monthly is not None and 'min_monthly' in df:
        df = df[df['min_monthly'] >= min_monthly] if (df['min_monthly'] >= min_monthly).any() else df
    return df.sort_values(objective, ascending=False).head(top)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument('--legs', required=True); ap.add_argument('--start', default='2025-01-01'); ap.add_argument('--end', default='2026-09-30')
    ap.add_argument('--grid', default='0,5,10,15,20'); ap.add_argument('--max_total', type=int, default=40); ap.add_argument('--objective', default='expected_net')
    a = ap.parse_args()
    al = AlignedLegs(json.loads(a.legs), a.start, a.end)
    print('daily P&L correlation:\n', al.daily_corr.round(2).to_string())
    res = search(al, tuple(int(x) for x in a.grid.split(',')), a.max_total, a.objective)
    with pd.option_context('display.width', 250, 'display.max_rows', 200):
        print(res.round(3).to_string(index=False))
