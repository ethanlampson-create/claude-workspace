"""Performance metrics from trade and daily P&L tables (per 1 contract)."""
import numpy as np
import pandas as pd


def metrics(trades: pd.DataFrame, daily: pd.DataFrame) -> dict:
    out = {}
    d = daily['pnl'].values
    t = trades['pnl'].values if len(trades) else np.array([])
    out['trades'] = int(len(t))
    out['net'] = float(t.sum()) if len(t) else 0.0
    out['days'] = int(len(d))
    out['trading_days'] = int((daily['trades'] > 0).sum())
    if len(t):
        w = t[t > 0]; lo = t[t <= 0]
        out['win_rate'] = float(len(w) / len(t))
        out['avg_trade'] = float(t.mean())
        out['avg_win'] = float(w.mean()) if len(w) else 0.0
        out['avg_loss'] = float(lo.mean()) if len(lo) else 0.0
        out['profit_factor'] = float(w.sum() / -lo.sum()) if len(lo) and lo.sum() < 0 else np.inf
        out['expectancy_R'] = float(t.mean() / -lo.mean()) if len(lo) and lo.mean() < 0 else np.nan
        out['trades_per_day'] = float(len(t) / max(1, len(d)))
    eq = np.cumsum(d)
    peak = np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:]
    dd = eq - peak
    out['max_dd_closed'] = float(dd.min()) if len(dd) else 0.0
    # intraday drawdown: equity at start of day + min_eq
    eq0 = np.concatenate([[0.0], eq[:-1]]) if len(eq) else np.array([])
    intr = eq0 + daily['min_eq'].values if len(eq) else np.array([])
    peak0 = np.maximum.accumulate(np.concatenate([[0.0], eq]))[:-1] if len(eq) else np.array([])
    out['max_dd_intraday'] = float((intr - peak0).min()) if len(intr) else 0.0
    out['mean_day'] = float(d.mean()) if len(d) else 0.0
    out['std_day'] = float(d.std(ddof=1)) if len(d) > 1 else 0.0
    out['sharpe_daily_ann'] = float(d.mean() / d.std(ddof=1) * np.sqrt(252)) if len(d) > 1 and d.std(ddof=1) > 0 else 0.0
    active = d[daily['trades'].values > 0]
    out['pct_pos_days'] = float((active > 0).mean()) if len(active) else 0.0
    out['largest_day'] = float(d.max()) if len(d) else 0.0
    out['worst_day'] = float(d.min()) if len(d) else 0.0
    out['largest_day_share'] = float(d.max() / d.sum()) if len(d) and d.sum() > 0 else np.nan
    # monthly
    if len(d):
        m = pd.Series(d, index=pd.to_datetime(daily['session'])).resample('ME').sum()
        out['months'] = int(len(m)); out['pct_pos_months'] = float((m > 0).mean()); out['worst_month'] = float(m.min()); out['best_month'] = float(m.max())
        out['monthly'] = {str(k.date())[:7]: round(float(v), 2) for k, v in m.items()}
    return out


def fmt(m: dict) -> str:
    keys = ['trades', 'net', 'win_rate', 'avg_trade', 'profit_factor', 'max_dd_closed', 'max_dd_intraday', 'sharpe_daily_ann',
            'pct_pos_days', 'largest_day', 'worst_day', 'largest_day_share', 'pct_pos_months', 'worst_month']
    return ' | '.join(f"{k}={m[k]:.3f}" if isinstance(m.get(k), float) else f"{k}={m.get(k)}" for k in keys if k in m)
