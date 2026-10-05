"""Trade streams with per-setup confluence features for the three Sentinel legs (orb_close30, mr_gapfade, orb_dbl on MNQ).

Every setup the strategy would take is logged with the information a trader could see at the moment of entry and with
its realised outcome, so a grader can be fitted on the past and applied forward.

Streams
- 'fixed':  the final parameters (results/<id>/final.json) traded on the whole history 2010-11..2026-09.
- 'wf':     the walk-forward parameter path (results/<id>/walkforward.json wf_path) for 2025-01..2026-09, i.e. exactly
            the out-of-sample stream the final report's account numbers are based on.

Look-ahead rule: every feature for a trade entered at 1-minute index i uses bars < i only (the engine fills at the open
of bar i). Session-level features use sessions < d or the part of session d before the signal.
"""
import json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.contracts import CONTRACTS
from backtest.data import load_1m, hm, resample, daily_bars
from backtest import engine
from backtest.run import prepare, slice_window, WARMUP_DAYS
from strategies.common import daily_atr, prior_day_stats, overnight_range, opening_range
from strategies.mr_gapfade import vix_regime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEGS = ['orb_close30', 'mr_gapfade', 'orb_dbl']
CONTRACT = 'MNQ'


def final_params(sid):
    return json.load(open(os.path.join(ROOT, 'results', sid, 'final.json')))['params']


def wf_path(sid):
    j = json.load(open(os.path.join(ROOT, 'results', sid, 'walkforward.json')))
    return [(p['oos'].split('..')[0], p['oos'].split('..')[1], p['params']) for p in j['wf_path'] if p['oos'] >= '2025']


# --------------------------------------------------------------------------------------------------------------------
# session-level context (per day_id), all lagged / pre-open
# --------------------------------------------------------------------------------------------------------------------
def session_context(df1, contract):
    rth = (contract.rth_open, contract.rth_close)
    o_tod = hm(rth[0])
    pds = prior_day_stats(df1, rth=rth)[['session', 'pd_high', 'pd_low', 'pd_close']]
    d_rth = daily_bars(df1, rth_only=True, rth=rth)
    ctx = pds.copy()
    ctx['pd_open'] = d_rth['open'].shift(1)
    ctx['atr'] = daily_atr(df1, 14, rth_only=True, rth=rth)
    ctx['atr_mean60'] = ctx['atr'].rolling(60, min_periods=30).mean().shift(1)
    ctx['atr_ratio'] = ctx['atr'] / ctx['atr_mean60']
    ctx['atr_pct'] = 100 * ctx['atr'] / ctx['pd_close']
    cl = d_rth['close']
    for n in (20, 50, 200):
        ctx[f'trend{n}'] = (cl.shift(1) - cl.rolling(n, min_periods=n).mean().shift(1)) / ctx['atr']
    ctx['ret3'] = (cl.shift(1) - cl.shift(4)) / ctx['atr']
    ctx['ret10'] = (cl.shift(1) - cl.shift(11)) / ctx['atr']
    ctx['pd_range'] = (ctx['pd_high'] - ctx['pd_low']) / ctx['atr']
    ctx['pd_dir'] = (ctx['pd_close'] - ctx['pd_open']) / ctx['atr']
    onr = overnight_range(df1, rth[0])
    ctx['on_range'] = (onr['on_high'] - onr['on_low']) / ctx['atr']
    ctx['on_dir'] = (onr['on_close'] - onr['on_open']) / ctx['atr']
    ctx['on_high'] = onr['on_high']; ctx['on_low'] = onr['on_low']
    ob = df1[df1['tod'] == o_tod].drop_duplicates('day_id').set_index('day_id')
    ctx['open_0930'] = ob['open']
    ctx['gap'] = (ctx['open_0930'] - ctx['pd_close']) / ctx['atr']
    vr = vix_regime(df1, 100, 0.75)
    ctx['vix'] = vr['vix_lag1']
    ctx['vix_pct'] = (vr['vix_lag1'] - vr['vix_lo']) / (vr['vix_hi'] - vr['vix_lo']).replace(0, np.nan)
    for m in (15, 30):
        orr = opening_range(df1, rth[0], m)
        ctx[f'or{m}_high'] = orr['or_high']; ctx[f'or{m}_low'] = orr['or_low']; ctx[f'or{m}_i_end'] = orr['i_end']
        ctx[f'or{m}'] = (orr['or_high'] - orr['or_low']) / ctx['atr']
        ctx[f'or{m}_dir'] = (orr['or_close'] - orr['or_open']) / ctx['atr']
    ctx['dow'] = pd.to_datetime(ctx['session']).dt.dayofweek
    ctx['month'] = pd.to_datetime(ctx['session']).dt.month
    return ctx


# --------------------------------------------------------------------------------------------------------------------
# bar-level context at the entry index (uses bars < i only)
# --------------------------------------------------------------------------------------------------------------------
def _fvg_features(b5, k_last, side, px):
    """5-minute bars b5 (arrays), k_last = index of the last COMPLETED 5-min bar before the entry. Fair-value gaps on the
    previous 24 bars: bullish FVG at k when low[k] > high[k-2]; bearish when high[k] < low[k-2]."""
    hi, lo = b5['high'], b5['low']
    k0 = max(2, k_last - 23)
    bull = bear = 0; in_dir = in_opp = 0
    for k in range(k0, k_last + 1):
        if lo[k] > hi[k - 2]:
            bull += 1
            z0, z1 = hi[k - 2], lo[k]
            if z0 <= px <= z1:
                if side > 0: in_dir = 1
                else: in_opp = 1
        elif hi[k] < lo[k - 2]:
            bear += 1
            z0, z1 = hi[k], lo[k - 2]
            if z0 <= px <= z1:
                if side < 0: in_dir = 1
                else: in_opp = 1
    recent = slice(max(2, k_last - 11), k_last + 1)
    bull12 = int(np.sum(lo[recent] > hi[max(0, recent.start - 2):k_last - 1])) if k_last - 1 > recent.start - 2 else 0
    return {'fvg_align': (bull - bear) * side, 'fvg_in_dir': in_dir, 'fvg_in_opp': in_opp, 'fvg_total': bull + bear}


def _cisd(b5, k_last, side):
    """Change in state of delivery proxy: the last completed 5-min close is beyond the open of the most recent run of
    opposite-coloured candles (a bullish CISD closes above the open of the last bearish run)."""
    op, cl = b5['open'], b5['close']
    k = k_last
    # the last bar must be in the trade direction
    if (cl[k] - op[k]) * side <= 0:
        return 0, 0.0
    j = k - 1
    while j >= 0 and (cl[j] - op[j]) * side < 0:
        j -= 1
    if j == k - 1:
        return 0, 0.0           # no opposite run immediately before
    run_open = op[j + 1]
    return int((cl[k] - run_open) * side > 0), float((cl[k] - run_open) * side)


def bar_features(df1, b5, ctx, i, side, strategy):
    """Features at entry index i (fill at the open of bar i). Uses closes/highs/lows of bars < i."""
    d = int(df1['day_id'].values[i]); c = ctx.loc[d]
    o = df1['open'].values; h = df1['high'].values; l = df1['low'].values; cl = df1['close'].values; tod = df1['tod'].values; day = df1['day_id'].values
    atr = c['atr']; px = cl[i - 1]
    f = {'tod': int(tod[i]), 'mins_since_open': int(tod[i]) - hm('09:30')}
    # today's RTH bars before i
    j0 = i - 1
    while j0 >= 0 and day[j0] == d and tod[j0] >= hm('09:30'):
        j0 -= 1
    j0 += 1
    if j0 <= i - 1 and tod[j0] >= hm('09:30'):
        dh = h[j0:i].max(); dl = l[j0:i].min(); dopen = o[j0]
    else:
        dh = dl = dopen = px
    f['day_move'] = (px - dopen) / atr * side            # move since the open in the trade direction (+ chasing, - fading)
    f['day_range'] = (dh - dl) / atr
    f['pos_in_day_range'] = (px - dl) / (dh - dl) if dh > dl else 0.5
    f['pos_in_day_range_dir'] = f['pos_in_day_range'] if side > 0 else 1 - f['pos_in_day_range']
    pdh, pdl, pdc = c['pd_high'], c['pd_low'], c['pd_close']
    f['pos_in_pd_range'] = (px - pdl) / (pdh - pdl) if pdh > pdl else 0.5
    f['dist_pdh'] = (pdh - px) / atr * side              # room to PDH in the trade direction (long: positive = room)
    f['dist_pdl'] = (px - pdl) / atr * side
    f['dist_pdc'] = (px - pdc) / atr * side
    f['dist_onh'] = (c['on_high'] - px) / atr * side
    f['dist_onl'] = (px - c['on_low']) / atr * side
    f['swept_pdh'] = int(dh > pdh); f['swept_pdl'] = int(dl < pdl)
    f['sweep_against'] = int((side > 0 and dl < pdl) or (side < 0 and dh > pdh))   # reversal after taking the other side's liquidity
    f['sweep_with'] = int((side > 0 and dh > pdh) or (side < 0 and dl < pdl))
    for n in (5, 15, 30):
        f[f'mom{n}'] = (cl[i - 1] - cl[max(0, i - 1 - n)]) / atr * side
    r = np.diff(np.log(cl[max(0, i - 31):i]))
    f['rv30'] = float(np.std(r) * np.sqrt(390) * px / atr) if len(r) > 5 else np.nan
    # 5-minute structure
    k_last = int(np.searchsorted(b5['i_last'], i - 1, side='right') - 1)
    if k_last >= 2 and b5['day_id'][k_last] == d:
        f.update(_fvg_features(b5, k_last, side, px))
        f['cisd'], f['cisd_disp'] = _cisd(b5, k_last, side)
        f['cisd_disp'] = f['cisd_disp'] / atr
        body = (b5['close'][k_last] - b5['open'][k_last]) * side
        rng5 = b5['high'][k_last] - b5['low'][k_last]
        f['last5_body'] = body / atr; f['last5_body_ratio'] = body / rng5 if rng5 > 0 else 0.0
        f['bars5_dir'] = int(np.sum(np.sign(b5['close'][max(0, k_last - 5):k_last + 1] - b5['open'][max(0, k_last - 5):k_last + 1]) == side))
    else:
        f.update({'fvg_align': np.nan, 'fvg_in_dir': np.nan, 'fvg_in_opp': np.nan, 'fvg_total': np.nan, 'cisd': np.nan, 'cisd_disp': np.nan,
                  'last5_body': np.nan, 'last5_body_ratio': np.nan, 'bars5_dir': np.nan})
    # OR context (only if the OR is complete before i)
    for m in (15, 30):
        if c[f'or{m}_i_end'] == c[f'or{m}_i_end'] and c[f'or{m}_i_end'] < i:
            f[f'or{m}'] = c[f'or{m}']; f[f'or{m}_dir'] = c[f'or{m}_dir'] * side
            f[f'or{m}_pos'] = ((px - c[f'or{m}_low']) / (c[f'or{m}_high'] - c[f'or{m}_low']) if c[f'or{m}_high'] > c[f'or{m}_low'] else 0.5)
            f[f'or{m}_pos'] = f[f'or{m}_pos'] if side > 0 else 1 - f[f'or{m}_pos']
        else:
            f[f'or{m}'] = np.nan; f[f'or{m}_dir'] = np.nan; f[f'or{m}_pos'] = np.nan
    # session context in the trade direction where it has a direction
    for k in ('trend20', 'trend50', 'trend200', 'ret3', 'ret10', 'pd_dir', 'on_dir', 'gap'):
        f[k + '_dir'] = c[k] * side
    for k in ('atr', 'atr_pct', 'atr_ratio', 'pd_range', 'on_range', 'vix', 'vix_pct', 'dow', 'month'):
        f[k] = c[k]
    f['gap_abs'] = abs(c['gap'])
    return f


def plan_features(it, i, side, entry_est, atr, contract):
    """Risk / reward of the order placed at index i, from the intents arrays (stop_px or stop_pts, tgt_px or tgt_pts)."""
    sp, tp = it.stop_px[i], it.tgt_px[i]; spts, tpts = it.stop_pts[i], it.tgt_pts[i]
    risk = spts if spts == spts else (entry_est - sp) * side
    tgt = tpts if tpts == tpts else (tp - entry_est) * side
    return {'risk_atr': risk / atr, 'tgt_atr': tgt / atr, 'rr': tgt / risk if risk > 0 else np.nan, 'risk_pts': risk, 'tgt_pts': tgt}


def memory_features(tr):
    """Causal 'memory' of the strategy's own history: stats of the setups logged BEFORE each trade (same strategy)."""
    tr = tr.sort_values('entry_ts').copy()
    out = pd.DataFrame(index=tr.index)
    for sid, g in tr.groupby('strategy'):
        R = g['R']; win = (g['pnl'] > 0).astype(float)
        out.loc[g.index, 'mem_R20'] = R.shift(1).rolling(20, min_periods=10).mean()
        out.loc[g.index, 'mem_R50'] = R.shift(1).rolling(50, min_periods=20).mean()
        out.loc[g.index, 'mem_wr20'] = win.shift(1).rolling(20, min_periods=10).mean()
        # consecutive losses before this trade
        loss = (g['pnl'] <= 0).astype(int).values
        streak = np.zeros(len(g)); s = 0
        for k in range(len(g)):
            streak[k] = s
            s = s + 1 if loss[k] else 0
        out.loc[g.index, 'mem_loss_streak'] = streak
        # expanding win rate / mean R in the same hour bucket and same weekday (prior trades only)
        for key, name in ((g['tod'] // 30, 'hour'), (g['dow'], 'dow'), (g['side'], 'side')):
            cs = win.groupby(key).cumsum() - win; cn = win.groupby(key).cumcount()
            out.loc[g.index, f'mem_wr_{name}'] = (cs / cn.replace(0, np.nan)).where(cn >= 15)
            csR = R.groupby(key).cumsum() - R
            out.loc[g.index, f'mem_R_{name}'] = (csR / cn.replace(0, np.nan)).where(cn >= 15)
    return out


# --------------------------------------------------------------------------------------------------------------------
def run_leg(sid, params, start, end, df1_all, b5, ctx, contract):
    """Run one leg on [start, end]; return (trades with features and entry index, daily, bars, intents, df1 slice info)."""
    df1 = df1_all  # already the full frame; prepare() restricts entries to >= start
    _, it, _ = prepare(sid, contract.name, start, end, params, df1=df1)
    it.allow_entry &= (df1['session'].values <= pd.Timestamp(end).date())
    trades, daily, bars = engine.run(it, contract, return_bars=True)
    sessions = daily['session'].values
    bars = bars.copy(); bars['session'] = sessions[bars['day_id'].values]
    s0 = pd.Timestamp(start).date(); e0 = pd.Timestamp(end).date()
    keep = (bars['session'] >= s0) & (bars['session'] <= e0)
    bars = bars[keep].reset_index(drop=True)[['ts', 'session', 'eq_low', 'eq_close']]
    daily = daily[(daily['session'] >= s0) & (daily['session'] <= e0)].reset_index(drop=True)
    trades = trades[(trades['session'] >= s0) & (trades['session'] <= e0)].reset_index(drop=True)
    # entry index: engine fills at the open of the signal bar for market orders; map entry_ts -> index
    ts_index = pd.DatetimeIndex(df1['ts'])
    ei = ts_index.get_indexer(pd.DatetimeIndex(trades['entry_ts']))
    assert (ei >= 0).all()
    assert (it.sig[ei] != 0).all(), 'entry bar is not the signal bar (non-market entry?)'
    rows = []
    for k, i in enumerate(ei):
        side = int(trades['side'].iloc[k]); d = int(df1['day_id'].values[i])
        f = bar_features(df1, b5, ctx, i, side, sid)
        f.update(plan_features(it, i, side, df1['close'].values[i - 1], ctx.loc[d, 'atr'], contract))
        f['entry_idx'] = int(i); f['strategy'] = sid
        rows.append(f)
    feat = pd.DataFrame(rows)
    tr = pd.concat([trades, feat], axis=1)
    tr['risk_usd'] = tr['risk_pts'] * contract.point_value + contract.commission_rt
    tr['R'] = tr['pnl'] / tr['risk_usd']
    tr['mfe_R'] = tr['mfe_pts'] * contract.point_value / tr['risk_usd']
    tr['mae_R'] = -tr['mae_pts'] * contract.point_value / tr['risk_usd']
    tr['win'] = (tr['pnl'] > 0).astype(int)
    return tr, daily, bars, it


def build_streams(start='2010-11-01', end='2026-09-30', out_dir=None, verbose=True):
    contract = CONTRACTS[CONTRACT]
    df1 = load_1m(contract.data_symbol, (pd.Timestamp(start) - pd.Timedelta(days=WARMUP_DAYS)).strftime('%Y-%m-%d'), end)
    ctx = session_context(df1, contract)
    b5df = resample(df1, 5, rth_only=True, rth=(contract.rth_open, contract.rth_close))
    b5 = {k: b5df[k].values for k in ('open', 'high', 'low', 'close', 'i_first', 'i_last', 'day_id')}
    streams = {}
    for sid in LEGS:
        tr, daily, bars, it = run_leg(sid, final_params(sid), start, end, df1, b5, ctx, contract)
        streams[('fixed', sid)] = (tr, daily, bars)
        if verbose:
            print(f'fixed {sid}: {len(tr)} trades {start}..{end} net {tr.pnl.sum():.0f}', flush=True)
        parts = []; dl = []; bl = []
        for (s, e, p) in wf_path(sid):
            tr_w, d_w, b_w, _ = run_leg(sid, p, s, e, df1, b5, ctx, contract)
            parts.append(tr_w); dl.append(d_w); bl.append(b_w)
        trw = pd.concat(parts).reset_index(drop=True); dw = pd.concat(dl).reset_index(drop=True); bw = pd.concat(bl).reset_index(drop=True)
        streams[('wf', sid)] = (trw, dw, bw)
        if verbose:
            print(f'wf {sid}: {len(trw)} trades net {trw.pnl.sum():.0f} (report: see results/{sid}/wf_oos_2025_daily.csv)', flush=True)
    # memory features over each stream family (fixed: own history; wf: fixed history before 2025 + wf trades)
    fixed_all = pd.concat([streams[('fixed', s)][0] for s in LEGS]).reset_index(drop=True)
    fixed_all = fixed_all.join(memory_features(fixed_all))
    wf_all = pd.concat([streams[('wf', s)][0] for s in LEGS]).reset_index(drop=True)
    hist = fixed_all[pd.to_datetime(fixed_all['session']) < '2025-01-01'].drop(columns=[c for c in fixed_all.columns if c.startswith('mem_')])
    both = pd.concat([hist.assign(_wf=0), wf_all.assign(_wf=1)]).reset_index(drop=True)
    both = both.join(memory_features(both))
    wf_all = both[both['_wf'] == 1].drop(columns=['_wf']).reset_index(drop=True)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        fixed_all.to_parquet(os.path.join(out_dir, 'trades_fixed.parquet')); wf_all.to_parquet(os.path.join(out_dir, 'trades_wf.parquet'))
        for (kind, sid), (tr, d, b) in streams.items():
            d.to_csv(os.path.join(out_dir, f'daily_{kind}_{sid}.csv'), index=False); b.to_parquet(os.path.join(out_dir, f'bars_{kind}_{sid}.parquet'))
    return fixed_all, wf_all, streams, df1, b5, ctx


if __name__ == '__main__':
    import time; t0 = time.time()
    out = os.path.join(ROOT, 'results', 'grading')
    fixed_all, wf_all, streams, _, _, _ = build_streams(out_dir=out)
    print(fixed_all.groupby('strategy').agg(n=('pnl', 'size'), net=('pnl', 'sum'), wr=('win', 'mean'), R=('R', 'mean')).round(3))
    print(wf_all.groupby('strategy').agg(n=('pnl', 'size'), net=('pnl', 'sum'), wr=('win', 'mean'), R=('R', 'mean')).round(3))
    print(f'{time.time()-t0:.0f}s')
