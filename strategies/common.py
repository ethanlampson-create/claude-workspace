"""Shared helpers for strategies: indicators and session utilities (all vectorised on pandas/numpy)."""
import numpy as np
import pandas as pd
from backtest.data import hm, resample, daily_bars


def atr(bars: pd.DataFrame, n: int) -> pd.Series:
    """Wilder ATR on a bar DataFrame with high/low/close."""
    h, l, c = bars['high'], bars['low'], bars['close']
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def rsi(s: pd.Series, n: int) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def adx(bars: pd.DataFrame, n: int) -> pd.Series:
    h, l, c = bars['high'], bars['low'], bars['close']
    up = h.diff(); dn = -l.diff()
    plus = np.where((up > dn) & (up > 0), up, 0.0); minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    atr_ = tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    pdi = 100 * pd.Series(plus, index=bars.index).ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / atr_
    mdi = 100 * pd.Series(minus, index=bars.index).ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / atr_
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def session_vwap(bars: pd.DataFrame, anchor_tod: int = None) -> pd.Series:
    """Time-weighted average price (no volume available) anchored at session start or at anchor_tod (minutes)."""
    tp = (bars['high'] + bars['low'] + bars['close']) / 3.0
    key = bars['day_id']
    if anchor_tod is not None:
        after = (bars['tod'] >= anchor_tod) & (bars['tod'] <= hm('17:00'))   # evening bars (>= 18:00) are pre-anchor
        key = bars['day_id'].astype(str) + '_' + after.astype(str)
    cs = tp.groupby(key).cumsum(); cnt = tp.groupby(key).cumcount() + 1
    return cs / cnt


def prior_day_stats(df1: pd.DataFrame, rth=('09:30', '16:00')) -> pd.DataFrame:
    """Per session: prior-session RTH high/low/close and full-session (globex) high/low; indexed by day_id."""
    d_rth = daily_bars(df1, rth_only=True, rth=rth)
    d_all = daily_bars(df1, rth_only=False)
    out = pd.DataFrame({'session': d_all['session']})
    out['pd_high'] = d_rth['high'].shift(1); out['pd_low'] = d_rth['low'].shift(1); out['pd_close'] = d_rth['close'].shift(1)
    out['on_high'] = d_all['high']; out['on_low'] = d_all['low']  # NOTE full-session high/low includes RTH; use overnight() for ETH only
    return out


def overnight_range(df1: pd.DataFrame, rth_open='09:30') -> pd.DataFrame:
    """Overnight (18:00 -> rth_open) high/low per day_id."""
    o = hm(rth_open)
    d = df1[(df1['tod'] >= hm('18:00')) | (df1['tod'] < o)]
    g = d.groupby('day_id')
    return pd.DataFrame({'on_high': g['high'].max(), 'on_low': g['low'].min(), 'on_open': g['open'].first(), 'on_close': g['close'].last()})


def opening_range(df1: pd.DataFrame, start='09:30', minutes=15) -> pd.DataFrame:
    """Opening range high/low per day_id over [start, start+minutes). Also i_end = last 1-min index in the range."""
    s = hm(start); e = s + minutes
    d = df1[(df1['tod'] >= s) & (df1['tod'] < e)]
    g = d.groupby('day_id')
    out = pd.DataFrame({'or_high': g['high'].max(), 'or_low': g['low'].min(), 'or_open': g['open'].first(), 'or_close': g['close'].last(),
                        'i_end': g.apply(lambda x: x.index[-1]), 'n_bars': g.size()})
    return out


def daily_atr(df1: pd.DataFrame, n=14, rth_only=True, rth=('09:30', '16:00')) -> pd.Series:
    """ATR of daily bars, shifted so that value at day_id d uses days < d."""
    d = daily_bars(df1, rth_only=rth_only, rth=rth)
    return atr(d, n).shift(1)


def vix_lag1(df1: pd.DataFrame) -> pd.Series:
    """Prior-day VIX close mapped to day_id (uses only information available before the session)."""
    import os
    from backtest.data import PQ
    vix = pd.read_parquet(os.path.join(PQ, 'VIX_1d.parquet'))['close']
    vix.index = pd.to_datetime(vix.index).date
    sessions = df1.groupby('day_id')['session'].first()
    # prior available VIX close strictly before the session date
    s = pd.Series(vix.values, index=pd.to_datetime(list(vix.index)))
    out = []
    dates = pd.to_datetime(sessions.values)
    pos = s.index.searchsorted(dates, side='left') - 1
    vals = np.where(pos >= 0, s.values[np.clip(pos, 0, len(s) - 1)], np.nan)
    return pd.Series(vals, index=sessions.index)


def session_info(df1: pd.DataFrame, rth=('09:30', '16:00')) -> pd.DataFrame:
    """Per day_id: first/last bar tod, number of RTH bars, early_close flag (last RTH bar before 15:30 ET), dow."""
    g = df1.groupby('day_id')
    out = pd.DataFrame({'session': g['session'].first(), 'first_tod': g['tod'].first(), 'last_tod': g['tod'].last()})
    r = df1[(df1['tod'] >= hm(rth[0])) & (df1['tod'] < hm(rth[1]))].groupby('day_id')
    out['rth_bars'] = r.size().reindex(out.index).fillna(0).astype(int)
    out['rth_last_tod'] = r['tod'].last().reindex(out.index)
    out['early_close'] = (out['rth_last_tod'] < hm('15:30')) | (out['rth_bars'] < 300)
    out['dow'] = pd.to_datetime(out['session']).dt.dayofweek
    return out
