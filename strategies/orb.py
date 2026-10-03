"""Opening Range Breakout (reference implementation).

Rules: opening range = high/low of the first `or_minutes` minutes from RTH open. After the range completes, place a
buy stop at OR high + buffer and a sell stop at OR low - buffer (first fill cancels the other; one trade per day by
default). Stop = opposite side of the range (capped at `max_stop_atr` x daily ATR), or `stop_frac` x range.
Target = `rr` x risk. Exit flat at `flat` ET. Entries allowed until `last_entry` ET."""
import numpy as np
import pandas as pd
from backtest.engine import Intents
from backtest.data import hm
from strategies.common import opening_range, daily_atr

NAME = 'Opening Range Breakout'
DESCRIPTION = __doc__
CONTRACTS = ['MES', 'MNQ']
PARAMS = {'or_minutes': 15, 'rr': 2.0, 'stop_frac': 1.0, 'max_stop_atr': 0.5, 'buffer_ticks': 1, 'last_entry': '11:30',
          'flat': '15:55', 'max_trades': 1, 'min_range_atr': 0.05, 'max_range_atr': 0.6, 'valid_minutes': 120}
GRID = {'or_minutes': [5, 15, 30], 'rr': [1.0, 1.5, 2.0, 3.0], 'stop_frac': [0.5, 1.0]}


def generate(df1: pd.DataFrame, contract, params: dict) -> Intents:
    p = {**PARAMS, **params}
    it = Intents(df1)
    orr = opening_range(df1, contract.rth_open, p['or_minutes'])
    datr = daily_atr(df1, 14, rth_only=True, rth=(contract.rth_open, contract.rth_close))
    orr = orr.join(datr.rename('atr'))
    rng = orr['or_high'] - orr['or_low']
    ok = (rng >= p['min_range_atr'] * orr['atr']) & (rng <= p['max_range_atr'] * orr['atr']) & orr['atr'].notna()
    orr = orr[ok]
    i0 = orr['i_end'].values + 1
    i0 = i0[i0 < len(df1)]
    orr = orr.iloc[:len(i0)]
    buf = p['buffer_ticks'] * contract.tick
    # long and short stop orders, both live; engine takes whichever triggers first (one position at a time)
    stop_long = orr['or_high'].values - p['stop_frac'] * rng.loc[orr.index].values
    stop_short = orr['or_low'].values + p['stop_frac'] * rng.loc[orr.index].values
    cap = p['max_stop_atr'] * orr['atr'].values
    stop_long = np.maximum(stop_long, orr['or_high'].values + buf - cap)
    stop_short = np.minimum(stop_short, orr['or_low'].values - buf + cap)
    risk_l = (orr['or_high'].values + buf) - stop_long; risk_s = stop_short - (orr['or_low'].values - buf)
    # The engine supports one pending order at a time; emulate OCO by placing the long stop and, on the SAME bars,
    # we cannot place two. So we place both via alternating: use two Intents passes? Simpler: evaluate which side
    # triggers first on the 1-minute data and place only that side (deterministic, no look-ahead in outcome since
    # whichever level is touched first would have been the fill).
    h = df1['high'].values; l = df1['low'].values; day = df1['day_id'].values; tod = df1['tod'].values
    last_entry = hm(p['last_entry'])
    idx_list = []; side_list = []; px_list = []; sp_list = []; tp_list = []
    for j, (i_start, d) in enumerate(zip(i0, orr['day_id'].values if 'day_id' in orr else df1['day_id'].values[i0])):
        hi = orr['or_high'].values[j] + buf; lo = orr['or_low'].values[j] - buf
        k = i_start; first = 0; fill_i = -1
        while k < len(df1) and day[k] == day[i_start] and tod[k] < last_entry and (k - i_start) < p['valid_minutes']:
            up = h[k] >= hi; dn = l[k] <= lo
            if up and dn:
                # both sides touched within one bar: assume the side nearer the open triggered first; the engine will
                # then stop the trade out on the same bar (conservative: a loss, never a skipped day)
                first = 1 if (hi - df1['open'].values[k]) <= (df1['open'].values[k] - lo) else -1; fill_i = k; break
            if up:
                first = 1; fill_i = k; break
            if dn:
                first = -1; fill_i = k; break
            k += 1
        if first == 0:
            continue
        idx_list.append(i_start); side_list.append(first)
        if first > 0:
            px_list.append(hi); sp_list.append(stop_long[j]); tp_list.append(hi + p['rr'] * risk_l[j])
        else:
            px_list.append(lo); sp_list.append(stop_short[j]); tp_list.append(lo - p['rr'] * risk_s[j])
    it.place(np.array(idx_list, dtype=int), np.array(side_list, dtype=np.int8), entry_px=np.array(px_list),
             valid_bars=p['valid_minutes'], stop_px=np.array(sp_list), tgt_px=np.array(tp_list))
    it.set_session(contract.rth_open, p['last_entry'], p['flat'])
    it.max_trades_day = p['max_trades']
    return it
