"""ORB failed-breakout / double-break reversal: trade the SECOND break of the opening range.

Family orb_session (research/families/orb_session.md section 3.8, tradingstats / Edgeful double-break statistics).

Rules as implemented (all times ET, index contracts; gold anchors at contract.rth_open):
- DATA: 1-minute feed; 5-minute RTH bars via resample(df1, bar, rth_only=True, rth=(rth_open, rth_close)).
- OPENING RANGE: or_high / or_low over [rth_open, rth_open + or_minutes). rng = or_high - or_low. ATR = Wilder ATR(14) of
  daily RTH bars shifted one day (strategies.common.daily_atr). Skip the day if ATR is NaN, rng < min_range_atr*ATR or
  rng > max_range_atr*ATR.
- STATE MACHINE on the closed 5-minute bars that start at/after the OR end and before `last_entry`:
    1. FIRST BREAK : first bar with close > or_high (first_dir = +1) or close < or_low (first_dir = -1).
                     E = running max high (up) / min low (down) from the first-break bar onward until the failure bar
                     (inclusive); when require_fail is False, until the signal bar (inclusive).
    2. FAILURE     : a later bar whose close is back inside [or_low, or_high]. Skipped when require_fail is False.
    3. SECOND BREAK: after the failure, the first bar whose close is beyond the OPPOSITE side (close < or_low when
                     first_dir = +1, close > or_high when first_dir = -1). This is the signal bar. Entry = market at the
                     open of the 1-minute bar i_next (first 1-min bar after the signal bar; +1 tick slippage).
                     Strict reading: with require_fail = True a bar that closes straight through from one side to the
                     other without an inside close is NOT a signal (the state stays 'broken' in first_dir and a later
                     inside close is still required).
    4. One trade per day; no second break before last_entry -> no trade.
- CHASE FILTER: if the signal-bar close is more than skip_ext * rng beyond the broken side, skip.
- STOP: stop_mode 'extreme' = E (the failed extreme), 'mid' = OR midpoint. The distance from the entry (estimated by the
  signal-bar close) is capped at max_stop_atr * ATR; when the level is farther than the cap, the stop is placed at
  cap points from the actual fill (stop_pts).
- TARGET: fill -/+ tgt_frac * rng in the trade direction. Exits: stop, target, forced flat at `flat`. No trailing.
- SESSION: entries allowed in [rth_open + or_minutes, last_entry + bar); max_trades_day = 1.
- LOOK-AHEAD: every state transition uses only closed 5-minute bars; the order is placed at i_next and nothing from the
  entry bar or later is used.
Gold (MGC/GC): OR anchored at 08:20; defaults last_entry 11:00, flat 13:25 (overridable).
"""
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm, resample
from strategies.common import opening_range, daily_atr

NAME = 'ORB double-break reversal (second break of the 15/30-min range)'
DESCRIPTION = __doc__
CONTRACTS = ['MES', 'MNQ']
PARAMS = {'or_minutes': 30, 'require_fail': True, 'stop_mode': 'extreme', 'max_stop_atr': 0.6, 'tgt_frac': 0.75, 'skip_ext': 0.5,
          'last_entry': '12:30', 'min_range_atr': 0.1, 'max_range_atr': 0.8, 'flat': '15:55', 'max_trades': 1, 'bar': 5}
GOLD_DEFAULTS = {'last_entry': '11:00', 'flat': '13:25'}
GRID = {'or_minutes': [15, 30], 'stop_mode': ['extreme', 'mid'], 'tgt_frac': [0.5, 0.75, 1.0], 'require_fail': [True, False]}


def _tod_str(minutes: int) -> str:
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def signals(df1: pd.DataFrame, contract, p: dict) -> pd.DataFrame:
    """One row per day with a second-break signal: day_id, i_next, side, est (signal close), E, or_high, or_low, rng, atr,
    plus bookkeeping (first_dir, i_first_break, i_fail, i_signal, tod_signal). Used by generate() and for diagnostics."""
    rth = (contract.rth_open, contract.rth_close)
    bar = int(p['bar'])
    or_end = hm(contract.rth_open) + int(p['or_minutes'])
    last_entry = hm(p['last_entry'])
    b = resample(df1, bar, rth_only=True, rth=rth)
    orr = opening_range(df1, contract.rth_open, int(p['or_minutes']))
    datr = daily_atr(df1, 14, rth_only=True, rth=rth)
    orr = orr.join(datr.rename('atr'))
    orr['rng'] = orr['or_high'] - orr['or_low']
    ok = orr['atr'].notna() & (orr['rng'] >= p['min_range_atr'] * orr['atr']) & (orr['rng'] <= p['max_range_atr'] * orr['atr']) & (orr['rng'] > 0)
    orr = orr[ok]
    cand = b[(b['tod'] >= or_end) & (b['tod'] < last_entry) & (b['i_next'] >= 0)]
    cand = cand[cand['day_id'].isin(orr.index)]
    require_fail = bool(p['require_fail'])

    rows = []
    for d, g in cand.groupby('day_id', sort=True):
        o = orr.loc[d]
        oh = float(o['or_high']); ol = float(o['or_low'])
        hi = g['high'].values; lo = g['low'].values; cl = g['close'].values; inx = g['i_next'].values; tod = g['tod'].values
        first_dir = 0; failed = False; E = np.nan; i_fb = -1; i_fail = -1
        for k in range(len(g)):
            c = cl[k]
            if first_dir == 0:
                if c > oh:
                    first_dir = 1; E = hi[k]; i_fb = k
                elif c < ol:
                    first_dir = -1; E = lo[k]; i_fb = k
                continue
            # track the failed extreme until the failure bar (inclusive), or until the signal when no failure is required
            if not failed:
                E = max(E, hi[k]) if first_dir > 0 else min(E, lo[k])
            if require_fail and not failed:
                if ol <= c <= oh:
                    failed = True; i_fail = k
                continue
            # armed: failure seen (or not required) -> look for the opposite-side close
            if first_dir > 0 and c < ol:
                side = -1
            elif first_dir < 0 and c > oh:
                side = 1
            else:
                continue
            rows.append({'day_id': int(d), 'i_next': int(inx[k]), 'side': side, 'est': float(c), 'E': float(E), 'or_high': oh, 'or_low': ol,
                         'rng': float(o['rng']), 'atr': float(o['atr']), 'first_dir': first_dir, 'k_first_break': i_fb, 'k_fail': i_fail,
                         'k_signal': k, 'tod_signal': int(tod[k]), 'session': g['session'].iloc[k]})
            break
    cols = ['day_id', 'i_next', 'side', 'est', 'E', 'or_high', 'or_low', 'rng', 'atr', 'first_dir', 'k_first_break', 'k_fail', 'k_signal', 'tod_signal', 'session']
    return pd.DataFrame(rows, columns=cols)


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS}
    if contract.name in ('MGC', 'GC'):
        p.update(GOLD_DEFAULTS)
    p.update(params)
    it = Intents(df1)
    bar = int(p['bar'])
    or_end = hm(contract.rth_open) + int(p['or_minutes'])
    last_entry = hm(p['last_entry'])
    sig = signals(df1, contract, p)

    idx, side, stop_px, stop_pts, tgt_pts = [], [], [], [], []
    meta = []
    for r in sig.itertuples(index=False):
        s = int(r.side); est = float(r.est); rng = float(r.rng); cap = float(p['max_stop_atr'] * r.atr)
        level = r.or_low if s < 0 else r.or_high            # the side broken by the second break
        if (est - level) * s > p['skip_ext'] * rng:         # chasing: already too far beyond the broken side
            continue
        if p['stop_mode'] == 'mid':
            sl = 0.5 * (r.or_high + r.or_low)
        else:
            sl = float(r.E)
        dist = (sl - est) * (-s)                            # distance from the estimated entry to the stop level
        if dist <= 0:
            continue
        idx.append(int(r.i_next)); side.append(s); tgt_pts.append(p['tgt_frac'] * rng)
        if dist > cap:
            stop_px.append(np.nan); stop_pts.append(cap)
        else:
            stop_px.append(float(sl)); stop_pts.append(np.nan)
        meta.append({'day_id': r.day_id, 'session': r.session, 'i_next': r.i_next, 'side': s, 'est': est, 'stop_level': sl, 'capped': dist > cap,
                     'risk_pts': min(dist, cap), 'tgt_pts': p['tgt_frac'] * rng, 'tod_signal': r.tod_signal, 'first_dir': r.first_dir})
    if idx:
        it.place(np.array(idx, dtype=int), np.array(side, dtype=np.int8), stop_px=np.array(stop_px), stop_pts=np.array(stop_pts),
                 tgt_pts=np.array(tgt_pts))
    it.set_session(_tod_str(or_end), _tod_str(last_entry + bar), p['flat'])
    it.max_trades_day = int(p['max_trades'])
    it.meta = pd.DataFrame(meta)
    return it
