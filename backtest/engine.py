"""Bar-level fill simulator (numba) operating on 1-minute bars.

Strategies express *intents* on the 1-minute index (see Intents): a signal at bar i means the order is live
from the OPEN of bar i (the decision was made on information up to the close of bar i-1 or the close of the
strategy-timeframe bar ending at i-1). The engine fills market orders at the open (+slippage), stop-entry
orders when touched (at max(open, level) + slippage), protective stops when touched (at level - slippage),
and limit targets only when price trades THROUGH the level by `through_ticks` (no slippage).
When a bar touches both stop and target, the STOP is assumed to be hit first (conservative). On the entry bar the
stop is checked against the bar extreme (and the target too, except after an intrabar limit fill whose favourable
extreme may predate the fill); a protective stop already through at the fill executes immediately at the market.
Pending stop/limit orders are live for exactly `valid_bars` bars (min 1). A session that ends before the flat time
(early close) closes the position at the session's last bar.
One position at a time, fixed 1 contract; position sizing is applied by the account simulator.

Per-day outputs include the intraday minimum of (realized + unrealized) equity so the account simulator can
detect intraday breaches of an end-of-day-trailing max-loss limit.
"""
import numpy as np
import pandas as pd
from numba import njit

REASON = {1: 'stop', 2: 'target', 3: 'trail', 4: 'max_hold', 5: 'flat', 6: 'exit_signal', 7: 'session_end'}


@njit(cache=True)
def _simulate(o, h, l, c, day_id, allow_entry, force_flat,
              sig, entry_px, entry_kind, valid_bars, stop_px, tgt_px, stop_pts, tgt_pts,
              trail_pts, trail_act_pts, max_hold, exit_flag,
              tick, slip_ticks, point_value, commission_rt, through_ticks,
              daily_loss_stop, daily_profit_stop, max_trades_day):
    n = o.shape[0]
    ndays = day_id[n - 1] + 1
    cap = max(4096, n // 16 + 16)
    rec = np.empty((cap, 10))   # columns: ei, xi, side, ep, xp, pnl, mae, mfe, reason, day  (grows by doubling)
    nt = 0
    d_pnl = np.zeros(ndays); d_min = np.zeros(ndays); d_max = np.zeros(ndays); d_trades = np.zeros(ndays, np.int32)
    b_low = np.zeros(n); b_close = np.zeros(n)  # per-bar intraday equity (realized today + unrealized): worst point, at close
    slip = slip_ticks * tick; thr = through_ticks * tick
    pos = 0; ep = 0.0; sp = np.nan; tp = np.nan; trl = np.nan; trla = 0.0; mh = 0; held = 0; ei = 0; mae = 0.0; mfe = 0.0
    pend = 0; pkind = 1; ppx = 0.0; pexp = 0; psp = np.nan; ptp = np.nan; pspts = np.nan; ptpts = np.nan; ptrl = np.nan; ptrla = 0.0; pmh = 0
    cur_day = -1; realized = 0.0; trades_today = 0; halted = False
    for i in range(n):
        d = day_id[i]
        if d != cur_day:
            if pos != 0:
                # the session ended (early close / holiday / feed stop) before the forced-flat time: a trader would
                # flatten before the close, so exit at the last bar of the ending session (its close, with slippage)
                j = i - 1
                xpx = c[j] - slip * pos
                pnl = (xpx - ep) * pos * point_value - commission_rt
                if nt >= cap:
                    new = np.empty((cap * 2, 10)); new[:cap] = rec; rec = new; cap *= 2
                rec[nt, 0] = ei; rec[nt, 1] = j; rec[nt, 2] = pos; rec[nt, 3] = ep; rec[nt, 4] = xpx; rec[nt, 5] = pnl
                rec[nt, 6] = mae; rec[nt, 7] = mfe; rec[nt, 8] = 7; rec[nt, 9] = cur_day; nt += 1
                realized += pnl; d_pnl[cur_day] = realized; d_trades[cur_day] += 1
                if realized < d_min[cur_day]:
                    d_min[cur_day] = realized
                if realized > d_max[cur_day]:
                    d_max[cur_day] = realized
                if realized < b_low[j]:
                    b_low[j] = realized
                b_close[j] = realized
                pos = 0
            cur_day = d; realized = 0.0; trades_today = 0; halted = False; pend = 0
        if pos != 0:
            # ---------------- manage an open position: exits
            exit_now = False; xpx = 0.0; reason = 0; at_open = False
            if force_flat[i] or exit_flag[i] == 2 or (exit_flag[i] == 1 and pos > 0) or (exit_flag[i] == -1 and pos < 0) or (mh > 0 and held >= mh):
                xpx = o[i] - slip * pos
                exit_now = True; at_open = True
                if force_flat[i]:
                    reason = 5
                elif mh > 0 and held >= mh:
                    reason = 4
                else:
                    reason = 6
            else:
                if pos > 0:
                    if sp == sp and o[i] <= sp:
                        xpx = o[i] - slip; exit_now = True; at_open = True; reason = 1
                    elif tp == tp and o[i] >= tp + thr:
                        xpx = o[i]; exit_now = True; at_open = True; reason = 2
                    elif sp == sp and l[i] <= sp:
                        xpx = sp - slip; exit_now = True; reason = 1
                    elif tp == tp and h[i] >= tp + thr:
                        xpx = tp; exit_now = True; reason = 2
                else:
                    if sp == sp and o[i] >= sp:
                        xpx = o[i] + slip; exit_now = True; at_open = True; reason = 1
                    elif tp == tp and o[i] <= tp - thr:
                        xpx = o[i]; exit_now = True; at_open = True; reason = 2
                    elif sp == sp and h[i] >= sp:
                        xpx = sp + slip; exit_now = True; reason = 1
                    elif tp == tp and l[i] <= tp - thr:
                        xpx = tp; exit_now = True; reason = 2
                if exit_now and reason == 1 and trl == trl and held > 0 and ((pos > 0 and sp > ep) or (pos < 0 and sp < ep)):
                    reason = 3
            if pos > 0:
                worst = l[i] - ep; bestb = h[i] - ep
            else:
                worst = ep - h[i]; bestb = ep - l[i]
            if not exit_now and trl == trl:
                # trailing ratchet from this bar's extreme; if the close is already through the new level the trail
                # was certainly hit after the extreme -> exit on this bar at the trail level
                if pos > 0 and (h[i] - ep) >= trla:
                    ns = h[i] - trl
                    if sp != sp or ns > sp:
                        sp = ns
                    if c[i] <= sp:
                        xpx = sp - slip; exit_now = True; reason = 3
                elif pos < 0 and (ep - l[i]) >= trla:
                    ns = l[i] + trl
                    if sp != sp or ns < sp:
                        sp = ns
                    if c[i] >= sp:
                        xpx = sp + slip; exit_now = True; reason = 3
            if exit_now:
                if at_open:
                    worst = (xpx - ep) * pos; bestb = worst          # nothing of this bar was held
                elif reason == 1:
                    worst = (xpx - ep) * pos; bestb = 0.0            # closed at the stop; no favourable excursion credited
                elif reason == 3:
                    worst = (xpx - ep) * pos                         # trail: the extreme came first, then the trail level
                else:
                    bestb = (xpx - ep) * pos                         # target: favourable excursion bounded by the fill
            if worst < mae:
                mae = worst
            if bestb > mfe:
                mfe = bestb
            eq_low = realized + worst * point_value - commission_rt
            eq_high = realized + bestb * point_value - commission_rt
            if eq_low < d_min[d]:
                d_min[d] = eq_low
            if eq_high > d_max[d]:
                d_max[d] = eq_high
            b_low[i] = eq_low
            if exit_now:
                pnl = (xpx - ep) * pos * point_value - commission_rt
                if nt >= cap:
                    new = np.empty((cap * 2, 10)); new[:cap] = rec; rec = new; cap *= 2
                rec[nt, 0] = ei; rec[nt, 1] = i; rec[nt, 2] = pos; rec[nt, 3] = ep; rec[nt, 4] = xpx; rec[nt, 5] = pnl
                rec[nt, 6] = mae; rec[nt, 7] = mfe; rec[nt, 8] = reason; rec[nt, 9] = d; nt += 1
                realized += pnl; d_pnl[d] = realized; trades_today += 1; d_trades[d] += 1
                if realized < d_min[d]:
                    d_min[d] = realized
                if realized > d_max[d]:
                    d_max[d] = realized
                if realized < b_low[i]:
                    b_low[i] = realized
                b_close[i] = realized
                pos = 0; pend = 0
                if daily_loss_stop > 0 and realized <= -daily_loss_stop:
                    halted = True
                if daily_profit_stop > 0 and realized >= daily_profit_stop:
                    halted = True
            else:
                b_close[i] = realized + (c[i] - ep) * pos * point_value - commission_rt
                held += 1
            continue
        # ---------------- flat: pending order, then new signal
        b_low[i] = realized; b_close[i] = realized
        if (not allow_entry[i]) or halted or (max_trades_day > 0 and trades_today >= max_trades_day):
            pend = 0
            continue
        filled = False; side = 0; fill = 0.0; fill_at_open = False; kind = 0; base = 0.0
        if pend != 0:
            if i > pexp:
                pend = 0
            else:
                if pkind == 1:
                    if pend > 0 and h[i] >= ppx:
                        fill_at_open = o[i] >= ppx; fill = max(o[i], ppx) + slip; filled = True; side = 1
                    elif pend < 0 and l[i] <= ppx:
                        fill_at_open = o[i] <= ppx; fill = min(o[i], ppx) - slip; filled = True; side = -1
                else:
                    # limit entry: fills only when price trades THROUGH the level; an open already through it fills
                    # at the open, anything else is an intrabar fill at the level at an unknown time
                    if pend > 0 and l[i] <= ppx - thr:
                        fill_at_open = o[i] <= ppx - thr; fill = o[i] if fill_at_open else ppx; filled = True; side = 1
                    elif pend < 0 and h[i] >= ppx + thr:
                        fill_at_open = o[i] >= ppx + thr; fill = o[i] if fill_at_open else ppx; filled = True; side = -1
                if filled:
                    kind = pkind; base = o[i] if fill_at_open else ppx
                    sp = psp; tp = ptp; trl = ptrl; trla = ptrla; mh = pmh
                    if sp != sp and pspts == pspts:
                        sp = fill - pspts * side
                    if tp != tp and ptpts == ptpts:
                        tp = fill + ptpts * side
                    pend = 0
        if (not filled) and sig[i] != 0:
            if entry_px[i] != entry_px[i]:
                side = sig[i]; fill = o[i] + slip * side; filled = True; fill_at_open = True; kind = 0; base = o[i]
                sp = stop_px[i]; tp = tgt_px[i]; trl = trail_pts[i]; trla = trail_act_pts[i]; mh = max_hold[i]
                if sp != sp and stop_pts[i] == stop_pts[i]:
                    sp = fill - stop_pts[i] * side
                if tp != tp and tgt_pts[i] == tgt_pts[i]:
                    tp = fill + tgt_pts[i] * side
                pend = 0   # a market entry cancels any resting order
            else:
                vb = valid_bars[i]
                if vb < 1:
                    vb = 1
                pend = sig[i]; pkind = entry_kind[i]; ppx = entry_px[i]; pexp = i + vb - 1   # live on exactly vb bars
                psp = stop_px[i]; ptp = tgt_px[i]; pspts = stop_pts[i]; ptpts = tgt_pts[i]
                ptrl = trail_pts[i]; ptrla = trail_act_pts[i]; pmh = max_hold[i]
                if pkind == 1:
                    if pend > 0 and h[i] >= ppx:
                        fill_at_open = o[i] >= ppx; fill = max(o[i], ppx) + slip; filled = True; side = 1
                    elif pend < 0 and l[i] <= ppx:
                        fill_at_open = o[i] <= ppx; fill = min(o[i], ppx) - slip; filled = True; side = -1
                else:
                    if pend > 0 and l[i] <= ppx - thr:
                        fill_at_open = o[i] <= ppx - thr; fill = o[i] if fill_at_open else ppx; filled = True; side = 1
                    elif pend < 0 and h[i] >= ppx + thr:
                        fill_at_open = o[i] >= ppx + thr; fill = o[i] if fill_at_open else ppx; filled = True; side = -1
                if filled:
                    kind = pkind; base = o[i] if fill_at_open else ppx
                    sp = psp; tp = ptp; trl = ptrl; trla = ptrla; mh = pmh
                    if sp != sp and pspts == pspts:
                        sp = fill - pspts * side
                    if tp != tp and ptpts == ptpts:
                        tp = fill + ptpts * side
                    pend = 0
        if filled:
            pos = side; ep = fill; held = 0; ei = i; mae = 0.0; mfe = 0.0
            exit_now = False; xpx = 0.0; reason = 0; at_open = False
            if sp == sp and ((pos > 0 and sp >= base) or (pos < 0 and sp <= base)):
                # the protective stop is already through at the fill: it executes immediately at the market
                xpx = base - slip * pos; exit_now = True; reason = 1; at_open = fill_at_open
            elif fill_at_open or kind == 1:
                # everything after the fill is in this bar (open fill) or price moved through the trigger toward the
                # target (stop entry): check the stop first (conservative), then the target
                if pos > 0:
                    if sp == sp and l[i] <= sp:
                        xpx = sp - slip; exit_now = True; reason = 1
                    elif tp == tp and h[i] >= tp + thr:
                        xpx = tp; exit_now = True; reason = 2
                else:
                    if sp == sp and h[i] >= sp:
                        xpx = sp + slip; exit_now = True; reason = 1
                    elif tp == tp and l[i] <= tp - thr:
                        xpx = tp; exit_now = True; reason = 2
            else:
                # limit filled intrabar: the bar's favourable extreme may predate the fill, so only the stop is checked
                if pos > 0 and sp == sp and l[i] <= sp:
                    xpx = sp - slip; exit_now = True; reason = 1
                elif pos < 0 and sp == sp and h[i] >= sp:
                    xpx = sp + slip; exit_now = True; reason = 1
            if pos > 0:
                worst = l[i] - ep; bestb = h[i] - ep
            else:
                worst = ep - h[i]; bestb = ep - l[i]
            if (not exit_now) and (not fill_at_open):
                if kind == 1:
                    # intrabar stop-entry fill, stop untouched: the bar's adverse extreme was most likely printed
                    # BEFORE the trigger; only the close is certainly after the fill
                    worst = min(0.0, (c[i] - ep) * pos)
                else:
                    # intrabar limit fill: the favourable extreme may predate the fill; adverse extreme kept (conservative)
                    bestb = max(0.0, (c[i] - ep) * pos)
            if (not exit_now) and trl == trl:
                if pos > 0 and (h[i] - ep) >= trla:
                    ns = h[i] - trl
                    if sp != sp or ns > sp:
                        sp = ns
                    if c[i] <= sp:
                        xpx = sp - slip; exit_now = True; reason = 3
                elif pos < 0 and (ep - l[i]) >= trla:
                    ns = l[i] + trl
                    if sp != sp or ns < sp:
                        sp = ns
                    if c[i] >= sp:
                        xpx = sp + slip; exit_now = True; reason = 3
            if exit_now:
                if at_open:
                    worst = (xpx - ep) * pos; bestb = worst
                elif reason == 1:
                    worst = (xpx - ep) * pos; bestb = 0.0
                elif reason == 3:
                    worst = (xpx - ep) * pos
                else:
                    bestb = (xpx - ep) * pos
            if worst < mae:
                mae = worst
            if bestb > mfe:
                mfe = bestb
            eq_low = realized + worst * point_value - commission_rt
            eq_high = realized + bestb * point_value - commission_rt
            if eq_low < d_min[d]:
                d_min[d] = eq_low
            if eq_high > d_max[d]:
                d_max[d] = eq_high
            b_low[i] = eq_low
            if force_flat[i] and not exit_now:
                xpx = c[i] - slip * pos; exit_now = True; reason = 5
            if exit_now:
                pnl = (xpx - ep) * pos * point_value - commission_rt
                if nt >= cap:
                    new = np.empty((cap * 2, 10)); new[:cap] = rec; rec = new; cap *= 2
                rec[nt, 0] = ei; rec[nt, 1] = i; rec[nt, 2] = pos; rec[nt, 3] = ep; rec[nt, 4] = xpx; rec[nt, 5] = pnl
                rec[nt, 6] = mae; rec[nt, 7] = mfe; rec[nt, 8] = reason; rec[nt, 9] = d; nt += 1
                realized += pnl; d_pnl[d] = realized; trades_today += 1; d_trades[d] += 1
                if realized < d_min[d]:
                    d_min[d] = realized
                if realized > d_max[d]:
                    d_max[d] = realized
                if realized < b_low[i]:
                    b_low[i] = realized
                b_close[i] = realized
                pos = 0; pend = 0
                if daily_loss_stop > 0 and realized <= -daily_loss_stop:
                    halted = True
                if daily_profit_stop > 0 and realized >= daily_profit_stop:
                    halted = True
            else:
                b_close[i] = realized + (c[i] - ep) * pos * point_value - commission_rt
                held = 1
    if pos != 0:
        i = n - 1
        xpx = c[i] - slip * pos
        pnl = (xpx - ep) * pos * point_value - commission_rt
        if nt >= cap:
            new = np.empty((cap * 2, 10)); new[:cap] = rec; rec = new; cap *= 2
        rec[nt, 0] = ei; rec[nt, 1] = i; rec[nt, 2] = pos; rec[nt, 3] = ep; rec[nt, 4] = xpx; rec[nt, 5] = pnl
        rec[nt, 6] = mae; rec[nt, 7] = mfe; rec[nt, 8] = 5; rec[nt, 9] = cur_day; nt += 1
        realized += pnl; d_pnl[cur_day] = realized; d_trades[cur_day] += 1
        if realized < d_min[cur_day]:
            d_min[cur_day] = realized
        if realized < b_low[i]:
            b_low[i] = realized
        b_close[i] = realized
    return rec[:nt], d_pnl, d_min, d_max, d_trades, b_low, b_close


class Intents:
    """Order intents on the 1-minute index. All prices absolute; *_pts distances from the fill price."""

    def __init__(self, df1: pd.DataFrame):
        n = len(df1)
        self.df1 = df1
        self.n = n
        self.sig = np.zeros(n, np.int8)
        self.entry_px = np.full(n, np.nan)
        self.entry_kind = np.ones(n, np.int8)   # 1 = stop entry, 2 = limit entry (only used when entry_px is set)
        self.valid_bars = np.zeros(n, np.int32)
        self.stop_px = np.full(n, np.nan); self.tgt_px = np.full(n, np.nan)
        self.stop_pts = np.full(n, np.nan); self.tgt_pts = np.full(n, np.nan)
        self.trail_pts = np.full(n, np.nan); self.trail_act_pts = np.zeros(n)
        self.max_hold = np.zeros(n, np.int32)
        self.exit_flag = np.zeros(n, np.int8)
        self.allow_entry = np.ones(n, bool)
        self.force_flat = np.zeros(n, bool)
        self.daily_loss_stop = 0.0      # $ per contract, 0 = none
        self.daily_profit_stop = 0.0    # $ per contract, 0 = none
        self.max_trades_day = 0         # 0 = unlimited

    def set_session(self, entry_start: str, entry_end: str, flat_time: str):
        """Allow new entries only in [entry_start, entry_end) ET and force flat at the first bar >= flat_time.
        Times are 'HH:MM' ET. Overnight windows (start > end) are supported."""
        from .data import hm
        tod = self.df1['tod'].values
        s, e, f = hm(entry_start), hm(entry_end), hm(flat_time)
        if s <= e:
            win = (tod >= s) & (tod < e)
        else:
            win = (tod >= s) | (tod < e)
        self.allow_entry &= win
        # force flat from flat_time until the session ends (17:00) -- session bars after 17:00 belong to next day
        if f >= hm('18:00'):
            # evening flat time (overnight strategies): flat from flat_time through the rest of the session (< 18:00)
            fl = (tod >= f) | (tod < hm('18:00'))
        else:
            fl = (tod >= f) & (tod < hm('18:00'))   # 17:xx bars still belong to the same session
        self.force_flat |= fl
        self.allow_entry &= ~self.force_flat

    def place(self, idx, side, entry_px=np.nan, valid_bars=0, stop_px=np.nan, tgt_px=np.nan, stop_pts=np.nan,
              tgt_pts=np.nan, trail_pts=np.nan, trail_act_pts=0.0, max_hold=0, kind='stop'):
        """Place entries at 1-minute indices `idx` (array). `side` scalar or array (+1/-1). Other args scalar or array.
        entry_px NaN => market at the open of bar idx. Otherwise a pending order live from the open of bar idx for
        `valid_bars` bars: kind='stop' (buy above / sell below, filled at max(open, level)+slip) or kind='limit'
        (buy below / sell above, filled at the level only when price trades through it by through_ticks)."""
        idx = np.asarray(idx)
        idx = idx[idx >= 0]
        if len(idx) == 0:
            return
        self.sig[idx] = side
        self.entry_px[idx] = entry_px
        self.entry_kind[idx] = 2 if kind == 'limit' else 1
        self.valid_bars[idx] = valid_bars
        self.stop_px[idx] = stop_px; self.tgt_px[idx] = tgt_px
        self.stop_pts[idx] = stop_pts; self.tgt_pts[idx] = tgt_pts
        self.trail_pts[idx] = trail_pts; self.trail_act_pts[idx] = trail_act_pts
        self.max_hold[idx] = max_hold

    def exit_at(self, idx, which=2):
        idx = np.asarray(idx); idx = idx[idx >= 0]
        self.exit_flag[idx] = which


def run(intents: Intents, contract, slip_ticks=None, through_ticks=1.0, commission_rt=None, return_bars=False):
    df1 = intents.df1
    o = df1['open'].values.astype(np.float64); h = df1['high'].values.astype(np.float64)
    l = df1['low'].values.astype(np.float64); c = df1['close'].values.astype(np.float64)
    day_id = df1['day_id'].values.astype(np.int64)
    rec, d_pnl, d_min, d_max, d_trades, b_low, b_close = _simulate(
        o, h, l, c, day_id, intents.allow_entry, intents.force_flat,
        intents.sig, intents.entry_px, intents.entry_kind, intents.valid_bars, intents.stop_px, intents.tgt_px,
        intents.stop_pts, intents.tgt_pts, intents.trail_pts, intents.trail_act_pts, intents.max_hold,
        intents.exit_flag, float(contract.tick),
        float(contract.slip_ticks if slip_ticks is None else slip_ticks), float(contract.point_value),
        float(contract.commission_rt if commission_rt is None else commission_rt), float(through_ticks),
        float(intents.daily_loss_stop), float(intents.daily_profit_stop), int(intents.max_trades_day))
    t_ei = rec[:, 0].astype(np.int64); t_xi = rec[:, 1].astype(np.int64); t_side = rec[:, 2].astype(np.int8)
    t_reason = rec[:, 8].astype(np.int8); t_day = rec[:, 9].astype(np.int64)
    ts = pd.DatetimeIndex(df1['ts'])  # keeps the America/New_York tz (``.values`` would silently convert to naive UTC)
    sessions = df1.groupby('day_id')['session'].first()
    trades = pd.DataFrame({'entry_ts': ts.take(t_ei), 'exit_ts': ts.take(t_xi), 'side': t_side, 'entry_px': rec[:, 3], 'exit_px': rec[:, 4],
                           'pnl': rec[:, 5], 'mae_pts': rec[:, 6], 'mfe_pts': rec[:, 7], 'reason': [REASON.get(int(r), str(r)) for r in t_reason],
                           'day_id': t_day, 'session': sessions.reindex(t_day).values, 'bars': t_xi - t_ei})
    daily = pd.DataFrame({'session': sessions.values, 'pnl': d_pnl, 'min_eq': d_min, 'max_eq': d_max, 'trades': d_trades})
    if return_bars:
        bars = pd.DataFrame({'ts': ts, 'day_id': day_id, 'eq_low': b_low, 'eq_close': b_close})
        bars['ts'] = ts
        return trades, daily, bars
    return trades, daily
