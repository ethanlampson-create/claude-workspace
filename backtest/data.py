"""Data loading, session labelling and resampling for the 1-minute proxies.

Conventions
- All timestamps are tz-aware America/New_York.
- A *session* (trading day) runs 18:00 ET (previous calendar day) to 17:00 ET; it is labelled by the
  calendar date of its RTH close (e.g. the session starting Sun 18:00 is labelled Monday).
- `tod` = minutes since midnight ET of the bar's *start* time.
"""
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PQ = os.path.join(ROOT, 'data', 'parquet')

_cache = {}

def load_1m(symbol: str, start=None, end=None) -> pd.DataFrame:
    """Load 1-minute bars for a data symbol (SPXUSD, NSXUSD, XAUUSD, WTIUSD) with session labels.
    Returns DataFrame with columns ts, open, high, low, close, session (date), tod (int minutes), day_id (int)."""
    key = symbol
    if key not in _cache:
        df = pd.read_parquet(os.path.join(PQ, f'{symbol}_1m.parquet'))
        df = df.sort_values('ts').reset_index(drop=True)
        ts = df['ts']
        # session date = date of (wall-clock ts - 18h) + 1 day  (18:00 Sun -> Monday). Wall-clock arithmetic: an
        # absolute-time subtraction would cross the DST switch on DST-start Sundays and mislabel the evening bars.
        shifted = ts.dt.tz_localize(None) - pd.Timedelta(hours=18)
        df['session'] = (shifted.dt.normalize() + pd.Timedelta(days=1)).dt.date
        df['tod'] = (ts.dt.hour * 60 + ts.dt.minute).astype(np.int32)
        df['dow'] = ts.dt.dayofweek.astype(np.int8)  # 0=Mon
        # drop Saturday sessions (should not exist) and empty sessions
        df = df[df['session'].map(lambda d: d.weekday()) < 5]
        df['day_id'] = pd.factorize(df['session'])[0].astype(np.int32)
        df = df.reset_index(drop=True)
        _cache[key] = df
    df = _cache[key]
    if start is not None:
        df = df[df['session'] >= pd.Timestamp(start).date()]
    if end is not None:
        df = df[df['session'] <= pd.Timestamp(end).date()]
    df = df.reset_index(drop=True)
    df['day_id'] = pd.factorize(df['session'])[0].astype(np.int32)
    return df

def hm(s: str) -> int:
    """'09:30' -> 570 minutes."""
    h, m = s.split(':'); return int(h) * 60 + int(m)

def resample(df1: pd.DataFrame, minutes: int, rth_only=False, rth=('09:30', '16:00')) -> pd.DataFrame:
    """Resample 1-minute bars to N-minute bars that never cross a session boundary.
    Adds i_first / i_last (1-minute index range), tod (bar start), and i_next (index of first 1-min bar
    after the bar closes, within the same session; -1 if none)."""
    d = df1
    if rth_only:
        o, c = hm(rth[0]), hm(rth[1])
        d = d[(d['tod'] >= o) & (d['tod'] < c)]
    # bucket by session and floor of minutes-since-18:00 within the session
    since_open = (d['tod'] - hm('18:00')) % 1440
    bucket = (since_open // minutes).astype(np.int64)
    g = d.groupby([d['day_id'], bucket], sort=True)
    idx = np.arange(len(df1))
    out = pd.DataFrame({
        'ts': g['ts'].first(),
        'open': g['open'].first(), 'high': g['high'].max(), 'low': g['low'].min(), 'close': g['close'].last(),
        'i_first': g.apply(lambda x: x.index[0]), 'i_last': g.apply(lambda x: x.index[-1]),
        'tod': g['tod'].first(), 'session': g['session'].first(), 'day_id': g['day_id'].first(),
    }).reset_index(drop=True)
    # i_next: the next 1-minute bar in the same session after i_last
    nxt = out['i_last'].values + 1
    same = (nxt < len(df1)) & (df1['day_id'].values[np.minimum(nxt, len(df1) - 1)] == out['day_id'].values)
    out['i_next'] = np.where(same, nxt, -1)
    return out

def daily_bars(df1: pd.DataFrame, rth_only=False, rth=('09:30', '16:00')) -> pd.DataFrame:
    """One bar per session (full session or RTH only)."""
    d = df1
    if rth_only:
        o, c = hm(rth[0]), hm(rth[1])
        d = d[(d['tod'] >= o) & (d['tod'] < c)]
    g = d.groupby('day_id', sort=True)
    out = pd.DataFrame({'session': g['session'].first(), 'open': g['open'].first(), 'high': g['high'].max(),
                        'low': g['low'].min(), 'close': g['close'].last(), 'i_first': g.apply(lambda x: x.index[0]),
                        'i_last': g.apply(lambda x: x.index[-1])})
    return out
