"""Funnel + raw touch statistics for the outside-open setup (no engine, pure day-table study).
Usage: python3 results/mr_pdrange/funnel_study.py MNQ 2025-01-01 2026-09-30"""
import sys, numpy as np, pandas as pd
sys.path.insert(0, '/home/user/claude-workspace')
from backtest.contracts import CONTRACTS
from backtest.data import load_1m, hm
from strategies.mr_pdrange import day_table, PARAMS

con = sys.argv[1]; start = sys.argv[2]; end = sys.argv[3]
contract = CONTRACTS[con]
df1 = load_1m(contract.data_symbol, (pd.Timestamp(start) - pd.Timedelta(days=45)).strftime('%Y-%m-%d'), end)
p = dict(PARAMS)
t = day_table(df1, contract, p)
t = t[pd.to_datetime(t['session']) >= pd.Timestamp(start)]
print(f'== {con} {start}..{end}: sessions={len(t)}')
out = t[t['side'] != 0]
print(f'open outside prior RTH range: {len(out)} ({len(out)/len(t):.1%})  long(open<PDL)={int((out.side>0).sum())} short={int((out.side<0).sum())}')
q1 = out[(out['dist_pct'] >= p['min_dist'])]
print(f'  dist >= {p["min_dist"]}%: {len(q1)}')
q2 = q1[q1['dist_pct'] <= p['max_dist']]
print(f'  dist <= {p["max_dist"]}%: {len(q2)}   (<=0.50%: {int((q1.dist_pct<=0.5).sum())}, <=1.0%: {int((q1.dist_pct<=1.0).sum())})')
q3 = q2[q2['dist_atr'] <= p['dist_atr']]
print(f'  dist <= {p["dist_atr"]} ATR: {len(q3)}')
q4 = q3[q3['gap_pct'] <= p['gap_cap']]
print(f'  gap <= {p["gap_cap"]}%: {len(q4)}')
print('  dist_pct distribution of outside opens (all):', out['dist_pct'].describe(percentiles=[.25,.5,.75,.9]).round(3).to_dict())

# raw touch statistics on all outside opens with dist >= min_dist (no max cap), bucketed by dist_pct
tod = df1['tod'].values; day = df1['day_id'].values; h = df1['high'].values; l = df1['low'].values
n = len(df1)
rows = []
for d, r in q1.iterrows():
    i0 = int(r['i_open']); side = int(r['side']); lvl = r['level']; op = r['open_0930']; dist = r['dist']
    stop_dist = max(p['stop_mult'] * dist, p['min_stop_pct'] / 100 * op)
    sp = op - stop_dist if side > 0 else op + stop_dist
    k = i0; touch_tod = None; stop_tod = None
    while k < n and day[k] == d and tod[k] < hm('16:00'):
        hit = (h[k] >= lvl) if side > 0 else (l[k] <= lvl)
        st = (l[k] <= sp) if side > 0 else (h[k] >= sp)
        if hit and touch_tod is None:
            touch_tod = tod[k]
        if st and stop_tod is None:
            stop_tod = tod[k]
        k += 1
    rows.append({'side': side, 'dist_pct': r['dist_pct'], 'dist_atr': r['dist_atr'], 'gap_pct': r['gap_pct'], 'dow': r['dow'],
                 'touch_pre0935': touch_tod is not None and touch_tod < hm('09:35'),
                 'touch_by_1000': touch_tod is not None and touch_tod < hm('10:00'),
                 'touch_by_1200': touch_tod is not None and touch_tod < hm('12:00'),
                 'touch_by_1600': touch_tod is not None,
                 'stop_first_by_1200': stop_tod is not None and stop_tod < hm('12:00') and (touch_tod is None or stop_tod <= touch_tod)})
s = pd.DataFrame(rows)
s['bucket'] = pd.cut(s['dist_pct'], [0, 0.1, 0.2, 0.3, 0.5, 1.0, 10], right=True)
g = s.groupby(['bucket'], observed=True).agg(n=('side', 'size'), pre0935=('touch_pre0935', 'mean'), by1000=('touch_by_1000', 'mean'), by1200=('touch_by_1200', 'mean'),
                                              by1600=('touch_by_1600', 'mean'), stop_first=('stop_first_by_1200', 'mean'))
print('raw touch rates by dist bucket (all outside opens, dist >= min_dist, stop = open -/+ max(1x dist, 0.15%)):')
print(g.round(3).to_string())
g2 = s[s['dist_pct'] <= 0.5].groupby('side').agg(n=('side', 'size'), pre0935=('touch_pre0935', 'mean'), by1000=('touch_by_1000', 'mean'),
                                                 by1200=('touch_by_1200', 'mean'), by1600=('touch_by_1600', 'mean'), stop_first=('stop_first_by_1200', 'mean'))
print('by side (dist <= 0.5%):'); print(g2.round(3).to_string())
g3 = s[s['dist_pct'] <= 0.5].groupby('dow').agg(n=('side', 'size'), by1200=('touch_by_1200', 'mean'), stop_first=('stop_first_by_1200', 'mean'))
print('by weekday (dist <= 0.5%):'); print(g3.round(3).to_string())
