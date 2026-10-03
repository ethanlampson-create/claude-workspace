"""Cross-sectional overnight-return reversal across MES / MNQ / MGC (open-to-close hold).

Akbas, Boehmer, Jiang & Koch (2022) overnight-intraday reversal, applied to our three proxies. Each contract is its own
run; the three legs are combined with backtest.portfolio.

UNIVERSE (inside generate): the other proxies are loaded with backtest.data.load_1m for the same session span as df1
  (SPXUSD, NSXUSD, XAUUSD). universe='all3' (default) = SPX+NSX+XAU; universe='eq' = SPX+NSX only (a contract that is
  not in the universe, i.e. MGC with 'eq', produces no trades).
SAME CLOCK FOR EVERY INSTRUMENT: prior_close = last 1-min close with tod < 16:00 ET of the previous session;
  open_0930 = open of the 09:30 ET 1-min bar (XAU too, even though its pit open is 08:20: this keeps the overnight
  windows aligned). r_k = (open_0930_k - prior_close_k) / prior_close_k in percent, for each instrument k present that
  session. A session missing any instrument (no 09:30 bar, no prior close, or prior sessions not the same date across
  instruments) -> no trade. Demeaned x_k = r_k - mean_k(r); spread = max(r) - min(r).
SIGNAL for the contract being run (X): LONG X if x_X is the minimum of the universe AND spread >= thresh AND
  x_X <= -thresh/2; SHORT X if x_X is the maximum AND spread >= thresh AND x_X >= +thresh/2; otherwise flat.
  sides = 'both' | 'long' | 'short'.
ENTRY: market at the open of the `entry_time` (09:31 ET) 1-min bar; the decision uses the 09:30 open only.
STOP: disaster stop stop_atr * 14-day RTH ATR (lagged; RTH per the contract spec: 09:30-16:00 equities, 08:20-13:30
  gold) from the fill. No target.
EXIT: force flat at the open of the first bar >= `flat` (15:55 ET) for all contracts (MGC included, within its 16:45
  limit). One trade per day per instrument. Position = 1 micro per leg in the portfolio run.
"""
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm, load_1m
from strategies.common import daily_atr

NAME = 'Cross-sectional overnight-return reversal (MES/MNQ/MGC)'
DESCRIPTION = __doc__
CONTRACTS = ['MES', 'MNQ', 'MGC']
PARAMS = {'thresh': 0.30, 'universe': 'all3', 'stop_atr': 1.0, 'entry_time': '09:31', 'flat': '15:55', 'sides': 'both',
          'max_trades': 1}
GRID = {'thresh': [0.20, 0.30, 0.50], 'universe': ['eq', 'all3'], 'stop_atr': [0.75, 1.0, 1.5], 'sides': ['both', 'long']}

UNIVERSES = {'all3': ['SPXUSD', 'NSXUSD', 'XAUUSD'], 'eq': ['SPXUSD', 'NSXUSD']}


def inst_table(df: pd.DataFrame) -> pd.DataFrame:
    """Per session (date index): prior_close (last close with tod < 16:00 of the PREVIOUS session), prior_session (its
    date), open_0930 and the overnight return r (percent). Only sessions with both values are kept."""
    c16 = df[df['tod'] < hm('16:00')].groupby('session')['close'].last()
    t = pd.DataFrame({'close16': c16})
    t['prior_close'] = t['close16'].shift(1)
    t['prior_session'] = pd.Series(t.index, index=t.index).shift(1)
    o = df[df['tod'] == hm('09:30')].groupby('session')['open'].first().rename('open_0930')
    t = t.join(o, how='inner')
    t = t[t['prior_close'].notna() & t['open_0930'].notna()]
    t['r'] = 100.0 * (t['open_0930'] - t['prior_close']) / t['prior_close']
    return t


def cross_section(df1: pd.DataFrame, contract, universe: str) -> pd.DataFrame:
    """Per session: r_<sym> for every universe member, mean / max / min, and x (demeaned r) for the run contract.
    Sessions where any member is missing, or whose prior sessions are not the same date for all members, are dropped."""
    syms = UNIVERSES[universe]
    s0, s1 = df1['session'].min(), df1['session'].max()
    tabs = {}
    for sym in syms:
        d = df1 if sym == contract.data_symbol else load_1m(sym, str(s0), str(s1))
        tabs[sym] = inst_table(d)
    cs = None
    for sym, t in tabs.items():
        part = t[['r', 'prior_session']].rename(columns={'r': f'r_{sym}', 'prior_session': f'ps_{sym}'})
        cs = part if cs is None else cs.join(part, how='inner')
    ps = cs[[f'ps_{s}' for s in syms]]
    cs = cs[(ps.nunique(axis=1) == 1)]
    R = cs[[f'r_{s}' for s in syms]]
    cs['r_mean'] = R.mean(axis=1); cs['r_max'] = R.max(axis=1); cs['r_min'] = R.min(axis=1)
    cs['spread'] = cs['r_max'] - cs['r_min']
    if contract.data_symbol in syms:
        cs['x'] = cs[f'r_{contract.data_symbol}'] - cs['r_mean']
        cs['is_min'] = cs[f'r_{contract.data_symbol}'] <= cs['r_min']
        cs['is_max'] = cs[f'r_{contract.data_symbol}'] >= cs['r_max']
    else:
        cs['x'] = np.nan; cs['is_min'] = False; cs['is_max'] = False
    return cs


def signals(df1: pd.DataFrame, contract, p: dict) -> pd.DataFrame:
    """Per session date: side (+1 / -1 / 0) and the cross-section columns."""
    cs = cross_section(df1, contract, p['universe'])
    th = float(p['thresh'])
    ok = cs['spread'] >= th
    lo = ok & cs['is_min'] & (cs['x'] <= -th / 2)
    sh = ok & cs['is_max'] & (cs['x'] >= th / 2)
    side = np.where(lo, 1, np.where(sh, -1, 0))
    if p['sides'] == 'long':
        side = np.where(side > 0, side, 0)
    elif p['sides'] == 'short':
        side = np.where(side < 0, side, 0)
    cs['side'] = side
    return cs


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS, **params}
    it = Intents(df1)
    cs = signals(df1, contract, p)
    cs = cs[cs['side'] != 0]
    rth = (contract.rth_open, contract.rth_close)
    datr = daily_atr(df1, 14, rth_only=True, rth=rth)            # indexed by day_id, lagged one session
    sess_of_day = df1.groupby('day_id')['session'].first()
    atr_by_session = pd.Series(datr.values, index=sess_of_day.reindex(datr.index).values)
    e_tod = hm(p['entry_time'])
    eb = df1[df1['tod'] == e_tod]
    entry_idx = pd.Series(eb.index.values, index=eb['session'].values)
    entry_idx = entry_idx[~entry_idx.index.duplicated()]
    idx = []; sides = []; sps = []
    for sess, r in cs.iterrows():
        if sess not in entry_idx.index:
            continue                                            # no 09:31 bar: skip the day
        a = atr_by_session.get(sess, np.nan)
        if not np.isfinite(a) or a <= 0:
            continue                                            # ATR not warm: do not trade
        idx.append(int(entry_idx[sess])); sides.append(int(r['side'])); sps.append(float(p['stop_atr']) * float(a))
    if idx:
        it.place(np.array(idx, dtype=int), np.array(sides, dtype=np.int8), stop_pts=np.array(sps))
    e_end = '%02d:%02d' % divmod(e_tod + 1, 60)
    it.set_session(p['entry_time'], e_end, p['flat'])
    it.max_trades_day = p['max_trades']
    return it
