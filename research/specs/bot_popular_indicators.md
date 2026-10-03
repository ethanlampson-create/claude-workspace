# Specs: Popular automated/bot and indicator strategies (TradingView "top" scripts, prop-bot vendors, YouTube "myth-busting" combos) for the Lucid 50K LucidFlex backtest

Source report: `/home/user/claude-workspace/research/families/bot_popular_indicators.md` (read fully; 25 sections).
Engine contract: `/home/user/claude-workspace/docs/STRATEGY_GUIDE.md`, `backtest/engine.py` (`Intents.place / set_session / exit_at`, `max_trades_day`, `daily_loss_stop`, `daily_profit_stop`, `trail_pts / trail_act_pts / max_hold`), helpers in `strategies/common.py` (`atr`, `ema`, `sma`, `rsi`, `adx`, `session_vwap` (TWAP proxy), `opening_range`, `daily_atr`, `prior_day_stats`, `vix_lag1`, `session_info`), `backtest.data.resample(df1, N, rth_only=True)` (adds `tod` = bar start, `i_first`, `i_last`, `i_next`).

Headline from the report, which drives the priorities below: **no popular TradingView indicator strategy has credible independent after-cost evidence of an intraday edge on ES/NQ** (independent intraday tests: 35-45% win, PF 0.86-1.10 outside strong trends; synthetic-bar and repainting backtests are inflated). The one member of the family with real 1-minute ES/NQ evidence after explicit futures costs is the intraday noise-area momentum breakout (Zarattini-Aziz-Barbon; Quantitativo replication: NQ Sharpe 1.67, 24.3%/yr, DD 24%, 38% win, payoff 2.25, 65% positive months). Everything else in this file is a **baseline or a long shot** that is cheap to code because the formulas are exact (pulled from the open-source Pine code), and whose main value is (a) proving/disproving the indicator on our data with honest fills and (b) supplying reusable exit mechanics (ATR ratchets) and prop scaffolding (session filter, fixed stop, kill switch).

## 0. Conventions used by every spec below

**Times**: all ET. Data session 18:00 -> 17:00 (equity CFD feed stops ~16:14). RTH equities 09:30-16:00; gold pit 08:20-13:30 (gold trades ~23h). A 1-minute bar with `tod = T` covers `[T, T+1)`. A decision taken on the close of the bar with `tod = T-1` is executed at the bar with `tod = T` (`i_next`), i.e. **market at next 1-minute open (+1 tick slippage)** unless the spec says `kind='stop'` or `kind='limit'`. On N-minute bars `B = resample(df1, N, rth_only=True)` decisions use the N-bar close and the order index is `B.i_next[k]` (skip `-1`: the session ended). The N-minute series is **continuous across sessions** (RTH bars of consecutive days concatenated, TradingView "RTH chart" semantics); every rolling/EWM indicator uses `min_periods` = full window and NaN rows never trade.

**Forced flat**: equities **15:55** (never later than 15:58). Gold pit specs 13:25. No overnight, no weekends.

**Honest-fill rule (mandatory for this family)**: signals may be computed on any synthetic series (Heikin-Ashi, Renko bricks, smoothed OHLC) but **every fill happens at real 1-minute OHLC** through the engine (market at next open + 1 tick, stop entries at max(open, level) + 1 tick, protective stops at level - 1 tick, targets only when traded through by 1 tick). All indicators are evaluated on **confirmed** bars only (bar `k` is used at `B.i_next[k]`). Repainting modes (Nadaraya-Watson default smoothing) are forbidden; endpoint/causal versions are specified.

**Flip-system execution pattern** (always-in indicators converted to day-trade-only). On a flip to `side` at N-bar `k` with `i = B.i_next[k]`:
```
exit_at(i, which=-side)          # closes an opposite position at the open of bar i (exit reason 6)
place(i, side, ...)              # fills at the open of bar i if already flat (e.g. stopped out earlier)
place(i+1, side, ...)            # engine ignores a signal on the bar where a position was just closed, so the
                                 # reversal fills one bar later; only if bar i+1 is in the same session and
                                 # tod(i+1) < last_entry.  Both placements carry the same stop/target.
```
Engine facts behind this: a signal on a bar where a position is open (or closed on that same bar) is ignored; `exit_flag = +1 / -1 / 2` closes long / short / any at the bar open; pending `kind='stop'|'limit'` orders live `valid_bars` bars; `daily_loss_stop` / `daily_profit_stop` look at **realized** P&L only and only block **new** entries, so every entry must carry a hard protective stop.

**Costs per micro, per round trip, already in the engine**: MES $2.50 slippage + $1.30 commission = $3.80; MNQ $1.00 + $1.30 = $2.30; MGC $2.00 + $1.30 = $3.30. "Average trade >= 2x costs" means >= $7.6 / $4.6 / $6.6 per micro.

**Lucid risk block** (default for every spec unless overridden; values per ONE micro contract, the Lucid Monte Carlo scales 5-40 micros):
- `daily_loss_stop`: MES $60, MNQ $80, MGC $80 (grid multiplier `dls_mult {1.0, 1.5}`). At 10 micros this is $600-$1,200, <= 60% of the $2,000 EOD-trailing distance, so one bad day cannot breach a floor that started the day >= $1,200 below balance.
- `daily_profit_stop`: MES $120, MNQ $160, MGC $160 (grid multiplier `dps_mult {1.0, 1.5}`). At 10 micros ~$1,200-$1,800/day so that no single day is > 50% of the $3,000 target (consistency rule) and so the funded phase collects many >= $150 days instead of one big one. The scan over micros in `backtest.lucid` is what finally picks the size; these stops just shape the daily distribution.
- Kill switch semantics match the prop-bot vendors' "stop at 80% of the firm daily limit"; Lucid Flex has no explicit daily loss limit, so the block stands in for it.
- One position at a time; `max_trades_day` as specified; always `set_session(entry_start, last_entry, flat)`.
- News blackout (no entries within 30 min of NFP/CPI/FOMC) is NOT implemented: there is no event calendar in the data set. CPI/NFP (08:30) are outside RTH entry windows anyway; the FOMC 14:00 bar is covered by the hard stop + daily loss stop. Document, do not fake.

**Indicator definitions (exact; `src = close` unless stated; `n`-bar windows need `n` confirmed bars)**:
- `ATR(n)`: Wilder (`common.atr`, EWM alpha 1/n). `ATR14d = daily_atr(df1, 14, rth_only=True)` (daily RTH ATR shifted one day).
- `EMA(n)` = `common.ema` (span n). `SMA(n)` = `common.sma`. `WMA(n) = sum_{i=0..n-1} (n-i)*src[k-i] / sum_{i}(n-i)`.
- `HMA(n) = WMA(2*WMA(src, floor(n/2)) - WMA(src, n), round(sqrt(n)))`. Slope colour: up if `HMA[k] > HMA[k-2]`, down if `HMA[k] < HMA[k-2]`.
- `LSMA(n)` = `linreg(src, n, 0)` = endpoint of the least-squares line through the last n closes.
- `RSI(n)` = Wilder (`common.rsi`). `MACD = EMA(12) - EMA(26)`, `signal = EMA(MACD, 9)`, `hist = MACD - signal`.
- `BB(n, k)`: `mid = SMA(close, n)`, `sd = population stdev(close, n)` (Pine `ta.stdev` default), `bb_up/bb_dn = mid +- k*sd`.
- `KC_LB(n, m)` (LazyBear, useTrueRange): `ma = SMA(close, n)`, `rangema = SMA(TR, n)`, `kc_up/kc_dn = ma +- m*rangema`.
- `Supertrend(len, mult)`: `hl2 = (H+L)/2`; `up = hl2 - mult*ATR(len)`; `dn = hl2 + mult*ATR(len)`;
  `up_f[k] = close[k-1] > up_f[k-1] ? max(up[k], up_f[k-1]) : up[k]`; `dn_f[k] = close[k-1] < dn_f[k-1] ? min(dn[k], dn_f[k-1]) : dn[k]`;
  `trend[k] = (trend[k-1] == -1 and close[k] > dn_f[k-1]) ? +1 : (trend[k-1] == +1 and close[k] < up_f[k-1]) ? -1 : trend[k-1]` (seed +1);
  `st_line = trend > 0 ? up_f : dn_f`. Flip up at k: `trend[k] == +1 and trend[k-1] == -1`.
- `UTBot(a, c)`: `nLoss = a*ATR(c)`; `stop[k] = (src > stop[k-1] and src[k-1] > stop[k-1]) ? max(stop[k-1], src - nLoss) : (src < stop[k-1] and src[k-1] < stop[k-1]) ? min(stop[k-1], src + nLoss) : (src > stop[k-1] ? src - nLoss : src + nLoss)`;
  Buy at k: `src[k] > stop[k] and src[k-1] <= stop[k-1]`; Sell: `src[k] < stop[k] and src[k-1] >= stop[k-1]` (EMA(src,1) == src). Heikin-Ashi source OFF.
- `Chandelier(len, mult)` (everget, useClose): `ls_raw = highest(close, len) - mult*ATR(len)`; `ls[k] = close[k-1] > ls[k-1] ? max(ls_raw[k], ls[k-1]) : ls_raw[k]`; `ss_raw = lowest(close, len) + mult*ATR(len)`; `ss[k] = close[k-1] < ss[k-1] ? min(ss_raw[k], ss[k-1]) : ss_raw[k]`; `dir[k] = close[k] > ss[k-1] ? +1 : close[k] < ls[k-1] ? -1 : dir[k-1]`.
- `HA`: `haClose = (O+H+L+C)/4`; `haOpen[k] = (haOpen[k-1] + haClose[k-1])/2` (seed `(O+C)/2`); green = `haClose > haOpen`.
- `PSAR(af0, inc, afmax)`: Wilder parabolic SAR (standard TradingView `ta.sar`).
- `STC(len, fast, slow)` (shayankm, smoothing 0.5): `m = EMA(src, fast) - EMA(src, slow)`; `k1 = 100*(m - lowest(m, len)) / (highest(m, len) - lowest(m, len))` (carry previous when range 0); `d1[k] = d1[k-1] + 0.5*(k1 - d1[k-1])`; `k2 = 100*(d1 - lowest(d1, len)) / (highest(d1, len) - lowest(d1, len))`; `STC[k] = STC[k-1] + 0.5*(k2 - STC[k-1])`.
- `AO(fast, slow) = SMA(hl2, fast) - SMA(hl2, slow)` (standard 5/34; the Myth-Busting #3 script reads "AO(77,10)" = slow 77 / fast 10).
- `Ichimoku(9, 26, 52)`: `tenkan = (highest(H,9)+lowest(L,9))/2`; `kijun = ... 26`; `senkouA[k] = (tenkan[k-26] + kijun[k-26])/2`; `senkouB[k] = (highest(H,52)[k-26] + lowest(L,52)[k-26])/2` (the cloud displayed at k was computed 26 bars earlier: no look-ahead); `cloud_top = max(A, B)`, `cloud_bot = min(A, B)`.
- `OSGF(depth)` (one-sided / causal Gaussian filter; reconstructed from loxx's description, flagged): `w(i) = exp(-i^2 / (2*(depth/2)^2))`, `G[k] = sum_{i=0..depth-1} close[k-i]*w(i) / sum w(i)`.
- `TWAP = session_vwap(bars)` = cumulative mean of (H+L+C)/3 from 09:30: **approximation of VWAP** (no volume), flagged wherever used.
- `R` = |entry_ref - initial stop| in points; `$R = R x point_value`. `entry_ref` = the deciding close (market orders) or the order level (stop/limit).

**Evidence quality (EQ)**: 1 anecdote/vendor claim; 2 single self-reported test, no costs or synthetic bars; 3 independent test with costs, one market/period; 4 multiple independent tests with costs; 5 peer-reviewed + OOS replications. **Priority** 5 = best prior under Lucid constraints with evidence, 1 = long shot. **Complexity** 1 = a few lines on existing helpers, 5 = multi-state intraday machine.

**Relationship to `research/specs/trend_momentum.md`**: `trend_momentum__noise_area` (30-min decision steps, market entries) and `trend_momentum__squeeze_breakout` (simplified squeeze) already exist. Specs 1 and 8 below are deliberately different variants (1-minute band stop-orders with band-trailing exit; exact LazyBear momentum with first-release rule) and keep their own ids so both can be compared.

---

## 1. bot_popular_indicators__noise_area_1m_bands  (Zarattini-Aziz-Barbon intraday momentum, 1-minute band stop-orders, band-trailing exit; Quantitativo ES/NQ replication)

Priority **5**, complexity **4**, instruments MNQ (best per Quantitativo), MES; MGC optional (pit session mapping below, no published evidence). Bar size: 1-minute. EQ **4** (SSRN paper + independent replication on ES/NQ 1-min Databento data with $2.25/side and 0.25-tick slippage; not peer-reviewed; edge concentrated 2018-2025, flat 2010-2017; "highly sensitive to slippage"). This is the only spec in the family the report recommends as a core candidate.

Data gap: the paper's VWAP trailing-stop variant needs volume; this spec uses the paper's base variant (the crossed band is the trailing stop) which needs no volume. Vol-targeted sizing (2-3% daily vol target, 4-8x cap) is replaced by Lucid micro sizing from the Monte Carlo plus the per-trade ATR hard stop.

```
PARAMS (defaults = paper): lookback=14 (days; Quantitativo found 90), vm=1.0, entry_start='09:35', last_entry='15:00',
  flat='15:55', hard_stop_atr=0.5, trail='none' | 'atr', max_trades=4, long_only=False, min_sigma_pts=4 ticks
PRE (per session d, RTH 1-min bars 09:30 <= tod < 16:00):
  D = daily_bars(df1, rth_only=True); O930[d] = D.open; prev_close[d] = D.close.shift(1); atr[d] = ATR14d[d]
  move[d, t] = | close(bar with tod t) / O930[d] - 1 |            for every RTH tod t (09:30..15:59)
  M = pivot(move) -> rows day_id, cols tod (missing bars -> NaN, ignored by the mean)
  sigma[d, t] = M.rolling(lookback, min_periods=lookback).mean().shift(1)[d, t]   # strictly days < d
  UB[d, t] = max(O930[d], prev_close[d]) * (1 + vm*sigma[d, t])
  LB[d, t] = min(O930[d], prev_close[d]) * (1 - vm*sigma[d, t])
  (UB/LB at tod t depend only on prior days, today's 09:30 open and yesterday's close -> known before bar t opens)
  skip day d if sigma[d, .] is NaN or atr[d] is NaN;  band levels are rounded to the tick (UB up, LB down)
STATE MACHINE per session d over 1-min bars i with entry_start <= tod[i] < last_entry; pos = 0; n = 0:
  t = tod[i]; U = UB[d, t]; L = LB[d, t]
  if pos == 0:
     if n >= max_trades: break
     up = high[i] >= U;  dn = (low[i] <= L) and not long_only
     if not (up or dn): continue
     side = up and not dn ? +1 : dn and not up ? -1 : ((U - open[i]) <= (open[i] - L) ? +1 : -1)   # both touched: side nearer the open
     level = side > 0 ? U : L;  hard = max(hard_stop_atr*atr[d], 4 ticks)
     if trail == 'none': place(i, side, entry_px=level, kind='stop', valid_bars=1, stop_px=level - side*hard)
     else:               place(i, side, entry_px=level, kind='stop', valid_bars=1, stop_px=level - side*hard,
                                trail_pts=hard, trail_act_pts=hard)      # engine ratchet after +1 hard-stop distance
     pos = side; ep = level; sp = level - side*hard; n += 1
     # mirror the engine's entry-bar stop check (stop is checked against the entry bar's extreme):
     if (side > 0 and low[i] <= sp) or (side < 0 and high[i] >= sp): pos = 0
  else:
     # 1) hard stop (mirror engine): long stopped if low[i] <= sp; short if high[i] >= sp  -> pos = 0; continue
     # 2) band-trailing exit (paper: stopped when price re-enters the noise area), evaluated on the 1-min close
     if pos > 0 and close[i] < U:  exit_at(i+1, which=+1); pos = 0; skip bar i+1 (no entry can register on the exit bar)
     if pos < 0 and close[i] > L:  exit_at(i+1, which=-1); pos = 0; skip bar i+1
     # reversal: the opposite band is tested again by the state machine from bar i+2 (paper allows reversals)
  (when trail == 'atr' the engine may also exit on the ratchet; the state machine cannot see it exactly, so after a
   band exit or hard stop the machine is authoritative, otherwise the engine simply ignores redundant placements)
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = max_trades; Lucid risk block
  (daily_loss_stop = 1.0 x block; daily_profit_stop = 1.5 x block: this strategy's good days are the trend days
   that produce the $3k, so give it more room than the mean-reversion specs).
GOLD MAPPING (optional MGC run): O930 -> 08:20 pit open, prev_close -> prior 13:30 pit close, RTH = 08:20-13:30,
  entry_start 08:25, last_entry 12:30, flat 13:25.
```
Grid (32 combos): `lookback {14, 90}`, `vm {1.0, 1.5}`, `entry_start {09:35, 10:00}`, `trail {none, atr}`, `max_trades {2, 4}`. Fixed: hard_stop_atr 0.5, last_entry 15:00, long_only False (add one `long_only=True` MNQ run: the 2025-26 tape is long-biased and the paper's SPY version was long-biased too). Walk-forward must include 2022 (down, high vol) and 2023 H2 (chop); the 90-day lookback is an in-sample choice of Quantitativo's.

Risk: hard stop 0.5 x ATR14d (ES ~25-35 pts = $125-175/MES, NQ ~100-150 pts = $200-300/MNQ): large per trade, so expect the Lucid scan to settle at 4-8 micros, not 20. Typical day at 1 NQ (10 MNQ) is +/-$300-900 (Quantitativo), so the eval needs >= 6-8 contributing days for the 50% consistency rule; the `daily_profit_stop` enforces that mechanically.

Evidence recap: ES L=14 2%-vol 8.1%/yr Sharpe 0.91 DD 24% win 36% payoff 2.09; ES L=90 16.8%/yr Sharpe 1.25; NQ L=90 24.3%/yr Sharpe 1.67 DD 24% win 38% payoff 2.25 (+6 bps/trade); 50/25/25 portfolio 22.4%/yr Sharpe 1.57 DD 15%, 65% positive months, worst month -6.6%; SPY paper 2007-24 19.6%/yr Sharpe 1.33. Benchmark for every other spec in this file.

## 2. bot_popular_indicators__supertrend_session  (Supertrend flip, RTH session filter, fixed $ stop, kill switch; canonical always-in 10/3 is the filters-off corner)

Priority **2**, complexity **2**, instruments MES, MNQ; bar size 5-min (14/2.5) and 15-min (10/3.0). EQ **1** for the prop variant (vendor claim NQ 15-min 2024-26: 48-55% win, 2.0-2.5x payoff, 1-3 trades/day, no log), **3** for the canonical flip (independent: 42% win / PF ~1.0 outside trends on 5-min stocks; Gold H4 PF 3.19 in the 2024-26 rally vs 1.02 in 2022-23; multiplier outside 2.5-3.5 degrades sharply). Report verdict: the scaffolding is right, the signal is unproven; run as the baseline every other flip system is compared against.

Data gap: VWAP agreement filter needs volume -> `filter='twap'` uses `session_vwap` (TWAP, flagged approximation); `filter='none'` is the canonical system.

```
PARAMS: bar=5, atr_len=14, mult=2.5   (bar=15 -> atr_len=10, mult=3.0), filter='none' | 'twap',
  stop_mode='line' | 'fixed', stop_usd=75 (per MICRO: MES 15 pts, MNQ 37.5 pts), max_stop_atr=0.5,
  entry_start='09:35', last_entry='11:30' | '15:00', flat='15:55', max_trades=3
PRE on B = resample(df1, bar, rth_only=True) (continuous RTH series):
  trend, up_f, dn_f, st_line = Supertrend(atr_len, mult);  flip_up[k] = trend[k]==+1 and trend[k-1]==-1; flip_dn mirror
  twap[k] = session_vwap(B)[k]   (only if filter == 'twap')
  atr_d = ATR14d[day of k]
ENTRY: for each k with flip_up[k] or flip_dn[k], B.tod[k] in [entry_start, last_entry), i = B.i_next[k] != -1:
  side = flip_up ? +1 : -1
  if filter == 'twap' and (side > 0 and close[k] <= twap[k] or side < 0 and close[k] >= twap[k]): skip
  entry_ref = close[k]
  stop_px = stop_mode == 'line' ? st_line[k] (= up_f[k] for longs, dn_f[k] for shorts) : entry_ref - side*stop_usd/point_value
  stop_px = clamp so that |entry_ref - stop_px| <= max_stop_atr*atr_d and >= 2 ticks
  FLIP PATTERN: exit_at(i, which=-side); place(i, side, stop_px=stop_px); place(i+1, side, stop_px=stop_px)
EXIT: opposite flip (exit_at at the next flip's i), hard stop, flat 15:55. No target (vendor: ride the flip).
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = max_trades; Lucid risk block (dls 1.0x, dps 1.0x).
```
Grid (32 combos): `bar {5, 15}`, `mult {2.5, 3.0}`, `filter {none, twap}`, `stop_mode {line, fixed}`, `last_entry {11:30, 15:00}`. Fixed: atr_len tied to bar (14 / 10), stop_usd 75, max_trades 3. Report tip: 7/2 on 1-5-min MNQ (PickMyTrade) is a scalping setting with no evidence; do not grid it.

Risk: 35-45% win with strings of 3-5 losers; `stop_mode='line'` on 15-min NQ can be 60-100 pts ($120-200/MNQ) -> the `max_stop_atr` clamp and the daily loss stop are what keep 10 micros inside the $2,000 room. Drop if PF < 1.1 on 2023-2024 with the same parameters.

## 3. bot_popular_indicators__utbot_session  (UT Bot Alerts ATR trailing-stop flip, session-filtered)

Priority **1**, complexity **2**, instruments MNQ, MES; bar size 5-min and 15-min. EQ **1** (TradeSearcher aggregate of 105 community backtests: avg PF 1.0, avg max DD 65%; no ES/NQ test with costs; the popular a=2/c=1 5-min setting flips several times per hour in chop). Same object as Supertrend/Chandelier (a close-based ATR ratchet); included as the second baseline and because its stop line is a reusable exit.

```
PARAMS: bar=5, a=1.0 (Key Value; default), c=10 (ATR period; default), ha_source=False (must stay False),
  entry_start='09:35', last_entry='15:00', flat='15:55', max_trades=3, max_stop_atr=0.5, tgt='none' | 'rr2'
PRE on B = resample(df1, bar, rth_only=True): stop_line, buy[k], sell[k] = UTBot(a, c) with src = close
ENTRY: for k with buy[k] (side +1) or sell[k] (side -1), B.tod[k] in window, i = B.i_next[k] != -1:
  entry_ref = close[k]; stop_px = stop_line[k]   (the trailing stop value at the signal bar)
  clamp |entry_ref - stop_px| to [2 ticks, max_stop_atr*ATR14d]
  tgt_px = tgt == 'rr2' ? entry_ref + side*2*|entry_ref - stop_px| : NaN
  FLIP PATTERN: exit_at(i, -side); place(i, side, stop_px, tgt_px); place(i+1, side, stop_px, tgt_px)
EXIT: opposite UT signal (exit_at), hard stop, target (if any), flat.
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = max_trades; Lucid risk block.
```
Grid (16 combos): `bar {5, 15}`, `a {1.0, 2.0}`, `c {6, 10}`, `tgt {none, rr2}`. Fixed window 09:35-15:00. (The "a=2, c=1" 5-min setting is deliberately excluded: c=1 makes nLoss = 2 x one bar's TR, a pure noise follower.)

Risk: expect negative expectancy after $2.30-3.80/trade on 5-min; the 15-min variant with rr2 is the only cell worth watching. Drop if PF < 1.1 on 2023-2026.

## 4. bot_popular_indicators__chandelier_ema200_flip  (Chandelier Exit direction flip with optional EMA(200) side filter)

Priority **1**, complexity **2**, instruments MNQ, MES; bar size 5-min and 15-min. EQ **2** (no published metrics for the flip system; as an EXIT the tighter 22x1 beat 22x2 everywhere in the StockCharts tests). Included to settle whether the tighter ratchet (mult 1) works as an entry on index futures; it is the reusable exit for spec 5.

```
PARAMS: bar=5, len=22, mult=3.0 (everget default; StockCharts 1.0/2.0), ema_filter=200 (0 = off),
  entry_start='09:35', last_entry='15:00', flat='15:55', max_trades=3, max_stop_atr=0.5
PRE on B = resample(df1, bar, rth_only=True): ls, ss, dir = Chandelier(len, mult); e200 = EMA(close, ema_filter)
  flip_up[k] = dir[k]==+1 and dir[k-1]==-1; flip_dn mirror
ENTRY: for k with a flip, B.tod[k] in window, i = B.i_next[k] != -1:
  side = flip_up ? +1 : -1
  if ema_filter > 0 and ((side > 0 and close[k] <= e200[k]) or (side < 0 and close[k] >= e200[k])): skip
  entry_ref = close[k]; stop_px = side > 0 ? ls[k] : ss[k]; clamp |entry_ref - stop_px| to [2 ticks, max_stop_atr*ATR14d]
  FLIP PATTERN: exit_at(i, -side); place(i, side, stop_px); place(i+1, side, stop_px)
EXIT: opposite dir flip (exit_at), hard stop, flat. No target.
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = max_trades; Lucid risk block.
```
Grid (12 combos): `bar {5, 15}`, `mult {1.0, 2.0, 3.0}`, `ema_filter {0, 200}`. Fixed len 22.

Risk: mult 1.0 on 5-min = many small stop-outs (the 5%-win / rare-big-win profile of the HMA tests is the failure mode); mult 3.0 = $150+ stops per micro. Drop if PF < 1.1 on 2023-2026.

## 5. bot_popular_indicators__rsi_dip_chandelier  (RSI(5) dip-buy with Chandelier exit, intraday translation of StockCharts SystemTrader; RSI(2)/RSI(14) as grid points)

Priority **2**, complexity **2**, instruments MES, MNQ; bar size 5-min RTH. EQ **3** for the daily original (SPY/QQQ/IJR 2000-2016 with commissions: CAR 4.8-10.8%, 60-83% win, DD 12.6-25.6%, tighter exit better) but the intraday translation is untested (report: "standard interpretation, untested here"); independent 1-/5-min RSI(14) 30/70 tests are clearly negative (20-23% win), so `rsi_len=14` is the control cell.

```
PARAMS: bar=5, rsi_len=5, thresh = {2: 10, 5: 30, 14: 30}[rsi_len], variant='B' (cross back above thresh) | 'A' (cross below),
  regime='sma50_200' (daily RTH closes: SMA_D(50) > SMA_D(200) for longs, < for shorts) | 'none',
  direction='long_only' | 'both', ce_len=22, ce_mult=1.0, stop_atr=1.5 (x ATR(14) on B), entry_start='09:45',
  last_entry='15:00', flat='15:55', max_trades=3, min_hold=1
PRE: B = resample(df1, bar, rth_only=True); r = RSI(close, rsi_len) on B; ls, ss, dir = Chandelier(ce_len, ce_mult) on B;
  a = ATR(14) on B; D = daily_bars(rth_only=True); s50 = SMA(D.close, 50).shift(1); s200 = SMA(D.close, 200).shift(1)
  long_ok[d] = regime=='none' or s50[d] > s200[d];  short_ok[d] = direction=='both' and (regime=='none' or s50[d] < s200[d])
ENTRY (long; short mirrored with 100-thresh): for k with B.tod[k] in window, i = B.i_next[k] != -1, long_ok[day(k)]:
  variant B: r[k-1] < thresh and r[k] >= thresh     (cross back above)
  variant A: r[k-1] >= thresh and r[k] < thresh     (cross below; buys the falling knife, as in the original variant A)
  entry_ref = close[k]; stop_px = entry_ref - stop_atr*a[k]
  place(i, +1, stop_px=stop_px)                     # market at next 1-min open
EXIT: for every k' > entry bar with close[k'] < ls[k'] (everget ratchet; evaluated only after min_hold bars so an entry
  below the chandelier line does not exit on the next bar): exit_at(B.i_next[k'], which=+1).  Hard stop. Flat 15:55.
  No fixed target (the original has none); optional grid `tgt {none, rr1}` if the hit rate is high but the ratchet gives back.
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = max_trades; Lucid risk block (dls 1.0x, dps 1.0x).
```
Grid (36 combos): `rsi_len {2, 5, 14}`, `ce_mult {1.0, 2.0, 3.0}`, `direction {long_only, both}`, `stop_atr {1.5, 2.5}`. Fixed: variant B, regime sma50_200, bar 5. One extra run with `variant='A'` and `regime='none'` on MES only.

Risk: a dip-buy in a trending-up regime is the one indicator setup here whose profile (60-80% win, small payoff) matches Lucid's "many small green days" need; its danger is the trend-day short-circuit (RSI(5) < 30 at 10:00 on a -2% day), which is why the regime filter and hard stop are not optional.

## 6. bot_popular_indicators__hull_flip  (Hull Suite slope flip / price-cross HMA, session-filtered)

Priority **1**, complexity **2**, instruments MNQ, MES; bar size 5/15/30-min. EQ **3** for the slow version (Oxford Strat 42 futures 1980-2016, no costs: only lengths > 500 bars viable, PF 1.10, DD 58%, rated C) and the QuantConnect SPY 30-min HMA(40) cross (CAGR 5.45%, Sharpe 0.43, win rate 5% with P/L ratio 22.4): the pattern that trips a $2,000 EOD-trailing DD before the rare winner, which then trips the consistency rule. Included for completeness and as a cheap test of the Hull Suite default on our data.

```
PARAMS: bar=15, len=55 (Hull Suite default), mode='slope' | 'cross' (close crosses HMA(len)), stop_atr=1.5 (x ATR(14) on B),
  entry_start='09:35', last_entry='15:00', flat='15:55', max_trades=3
PRE on B = resample(df1, bar, rth_only=True): h = HMA(close, len); a = ATR(14) on B
  mode slope: up[k] = h[k] > h[k-2]; flip_up[k] = up[k] and not up[k-1]; flip_dn mirror (h[k] < h[k-2] and not before)
  mode cross: flip_up[k] = close[k] > h[k] and close[k-1] <= h[k-1]; flip_dn mirror
ENTRY: for k with a flip, tod in window, i = B.i_next[k] != -1: side; entry_ref = close[k]; stop_px = entry_ref - side*stop_atr*a[k]
  FLIP PATTERN: exit_at(i, -side); place(i, side, stop_px); place(i+1, side, stop_px)
EXIT: opposite flip (exit_at), hard stop, flat.
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = max_trades; Lucid risk block.
```
Grid (24 combos): `bar {5, 15, 30}`, `len {40, 55}`, `mode {slope, cross}`, `stop_atr {1.0, 2.0}`.

Risk: expect < 30% win; the only question is whether the payoff survives $2.30-3.80 per trade. Drop fast.

## 7. bot_popular_indicators__hull_lsma_scalp  (Hull Suite(55) + LSMA(25) cross, "best 1-minute scalping", Myth-Busting #9)

Priority **1**, complexity **3**, instruments MNQ, MES; bar size 1-min (as published) and 5-min. EQ **1** (YouTube claim; the automation script publishes no result). Counter-trend 1:4 R needs ~25% win just to break even after costs; included because it is fully specified and cheap.

```
PARAMS: bar=1, hull_len=55, lsma_len=25, swing_n=10 (bars for the swing stop), rr=4.0, adx_filter=0 (0 = off; 25 = on),
  entry_start='09:45', last_entry='15:00', flat='15:55', max_trades=4, max_stop_atr=0.3 (x ATR14d), min_stop_ticks=4
PRE on B (bar == 1 -> RTH 1-min bars directly; else resample): h = HMA(close, hull_len); hull_up[k] = h[k] > h[k-2];
  ls = LSMA(close, lsma_len); adx14 = ADX(14) on B
ENTRY long (short mirrored): not hull_up[k] (Hull red) and ls[k] > h[k] and ls[k-1] <= h[k-1] (LSMA crosses above the Hull line)
  and (adx_filter == 0 or adx14[k] > adx_filter); tod in window; i = B.i_next[k] (bar 1: i = k+1)
  entry_ref = close[k]; stop_px = min(low[k-swing_n+1 .. k]) - 1 tick; clamp |entry_ref - stop_px| to [min_stop_ticks, max_stop_atr*ATR14d]
  tgt_px = entry_ref + rr*(entry_ref - stop_px)
  place(i, +1, stop_px=stop_px, tgt_px=tgt_px)
EXIT: stop, target, flat 15:55 (no signal exit).
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = max_trades; Lucid risk block.
```
Grid (16 combos): `bar {1, 5}`, `rr {2.0, 4.0}`, `swing_n {10, 20}`, `adx_filter {0, 25}`.

Risk: on 1-min NQ the swing stop is often 4-8 ticks = $2-4/MNQ, i.e. the stop is the cost: the 5-min cells are the only honest ones. Drop if PF < 1.1.

## 8. bot_popular_indicators__squeeze_momentum_lazybear  (LazyBear SQZMOM_LB exact: first squeeze-release bar, momentum direction, KC stop)

Priority **2**, complexity **3**, instruments MNQ, MES; bar size 5-min and 15-min. EQ **2** (Bitduke port: ~12% DD on BTC/ETH 1H-4H, no win/PF; AAPL 3-min anecdote 38-50%; LuxAlgo: "squeezes can fire into failed moves"). Low signal frequency is good for consistency; no evidence of edge after costs. Differs from `trend_momentum__squeeze_breakout` by using LazyBear's exact momentum (linreg of the mid-range deviation), the first-release rule, and the momentum-fade exit.

```
PARAMS: bar=5, bb_len=20, bb_mult=2.0, kc_len=20, kc_mult=1.5, mom_len=20, min_squeeze_bars=3, exit_mode='rr' | 'mom_fade',
  rr=2.0, max_stop_atr=0.5 (x ATR14d), entry_start='09:45', last_entry='14:30', flat='15:55', max_trades=2
PRE on B = resample(df1, bar, rth_only=True):
  bb_up, bb_dn = BB(bb_len, bb_mult); kc_up, kc_dn = KC_LB(kc_len, kc_mult)
  sqzOn[k] = bb_dn[k] > kc_dn[k] and bb_up[k] < kc_up[k];  sqzOff[k] = bb_dn[k] < kc_dn[k] and bb_up[k] > kc_up[k]
  run[k] = number of consecutive sqzOn bars ending at k
  val[k] = linreg(close - ((highest(high, mom_len) + lowest(low, mom_len))/2 + SMA(close, mom_len))/2, mom_len, 0)
  fire[k] = sqzOff[k] and sqzOn[k-1] and run[k-1] >= min_squeeze_bars        # first release bar only
  side[k] = val[k] > 0 and val[k] > val[k-1] ? +1 : val[k] < 0 and val[k] < val[k-1] ? -1 : 0
ENTRY: for k with fire[k] and side[k] != 0, B.tod[k] in [entry_start, last_entry), i = B.i_next[k] != -1:
  entry_ref = close[k]; stop_px = side > 0 ? kc_dn[k] : kc_up[k]; clamp |entry_ref - stop_px| to [2 ticks, max_stop_atr*ATR14d]
  tgt_px = exit_mode == 'rr' ? entry_ref + side*rr*|entry_ref - stop_px| : NaN
  place(i, side, stop_px=stop_px, tgt_px=tgt_px)       # market at next 1-min open
EXIT: exit_mode 'rr': stop / target / flat.  exit_mode 'mom_fade': for k' > entry bar with (long) val[k'] < val[k'-1]
  (histogram turns dark green = momentum fading) and k' - entry_k >= 2: exit_at(B.i_next[k'], +1); plus stop and flat.
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = max_trades; Lucid risk block.
```
Grid (16 combos): `bar {5, 15}`, `kc_mult {1.5, 2.0}`, `exit_mode {rr, mom_fade}`, `min_squeeze_bars {3, 6}`. Fixed rr 2.0, bb 20/2.0.

Risk: 0-2 trades/day, stop = KC band (ES 5-min ~6-10 pts = $30-50/MES). The compression-then-expansion idea overlaps NR-day ORBs in `trend_momentum`; keep only if it adds trades on days the ORB specs do not fire.

## 9. bot_popular_indicators__nadaraya_watson_endpoint_mr  (LuxAlgo Nadaraya-Watson envelope, endpoint (non-repainting) mode, band re-entry mean reversion)

Priority **1**, complexity **3**, instruments MES, MNQ; bar size 5-min. EQ **1** (LuxAlgo: "nothing suggests this envelope outperforms traditional band tools"; all viral hit rates come from the repainting mode). Included only in endpoint mode with a regime filter and hard stop, as the report prescribes.

```
PARAMS: bar=5, h=8.0 (bandwidth), mult=3.0, window=500 (bars, continuous RTH series ~6.4 days), regime='none' | 'adx25'
  (ADX(14) on B < 25 at entry), stop_atr=1.0 (x ATR(14) on B), max_hold=24 bars, entry_start='10:00', last_entry='15:00',
  flat='15:55', max_trades=3
PRE on B = resample(df1, bar, rth_only=True):
  w(i) = exp(-i^2/(2*h^2)), i = 0..window-1
  basis[k] = sum_i close[k-i]*w(i) / sum_i w(i)                 # endpoint estimate, uses bars <= k only (NO repaint)
  mae[k]   = SMA(|close - basis|, window)[k] * mult;  upper = basis + mae; lower = basis - mae
  adx14 = ADX(14) on B
ENTRY long (short mirrored on upper): close[k-1] < lower[k-1] and close[k] >= lower[k] (cross back above the lower band),
  regime ok, tod in window, i = B.i_next[k] != -1:
  entry_ref = close[k]; stop_px = entry_ref - stop_atr*ATR14(B)[k]; tgt_px = basis[k] (fixed at entry; must be > entry_ref + 2 ticks else skip)
  place(i, +1, stop_px=stop_px, tgt_px=tgt_px, max_hold=max_hold*bar)     # max_hold in 1-min bars
EXIT: target (basis), stop, max_hold, flat.
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = max_trades; Lucid risk block.
```
Grid (16 combos): `h {8, 16}`, `mult {2.0, 3.0}`, `regime {none, adx25}`, `stop_atr {1.0, 2.0}`. Fixed window 500, bar 5.

Risk: 3x MAD excursions on index futures are trend-day events; the ADX gate is the only thing between this and a $2,000 week. Drop if PF < 1.1 on 2023-2026.

## 10. bot_popular_indicators__macd_rsi_ema200  (MACD(12,26,9) zero-line / signal-cross trend, and the MACD + RSI + 200 EMA combo)

Priority **1**, complexity **2**, instruments MES, MNQ; bar size 5-min and 15-min. EQ **3** for the MACD component (LiberatedStockTrader, 606k trades: 40% win, underperforms B&H on daily and 5-min; HA bars inflate it), **1** for the combo (no after-cost ES/NQ test). Included because it is the most-copied YouTube scalp and its two components have honest negative tests, so this is a calibration of our engine against known-bad systems as much as a candidate.

```
PARAMS: bar=5, mode='macd_only' | 'combo', direction='long_only' | 'both', ema_len=200, rsi_len=14, rsi_lo=30, rsi_hi=70,
  rsi_lookback=5, stop_atr=1.5 (x ATR(14) on B), rr=2.0, entry_start='09:35', last_entry='15:30', flat='15:55', max_trades=3
PRE on B = resample(df1, bar, rth_only=True): macd, sig, hist = MACD(12,26,9); e200 = EMA(close, ema_len); r = RSI(close, rsi_len); a = ATR(14)
ENTRY long (short mirrored: hist<0, macd<0, macd<sig / r > rsi_hi and falling / close < e200):
  mode macd_only: cond[k] = hist[k] > 0 and macd[k] > 0 and macd[k] > sig[k];  enter on the first bar cond becomes true
  mode combo:     cond[k] = close[k] > e200[k] and min(r[k-rsi_lookback+1..k]) < rsi_lo and r[k] > r[k-1]
                            and macd[k] > sig[k] and macd[k-1] <= sig[k-1]     (signal-line cross on bar k)
  tod in window; i = B.i_next[k] != -1; entry_ref = close[k]; stop_px = entry_ref - stop_atr*a[k]
  macd_only: place(i, +1, stop_px=stop_px)                               # exit when sig > macd (LST rule)
  combo:     place(i, +1, stop_px=stop_px, tgt_px=entry_ref + rr*stop_atr*a[k])
EXIT: macd_only: for k' > entry with sig[k'] > macd[k']: exit_at(B.i_next[k'], +1); stop; flat.  combo: stop / target / flat.
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = max_trades; Lucid risk block.
```
Grid (16 combos): `mode {macd_only, combo}`, `bar {5, 15}`, `stop_atr {1.0, 1.5}`, `direction {long_only, both}`.

Risk: 40% win with ~2:1 payoff is break-even before costs per the independent test; expect PF < 1.0 after costs. Calibration spec; drop.

## 11. bot_popular_indicators__heikin_ashi_flip_ema50  (Heikin-Ashi colour flip + EMA(50) side, signals on HA, fills on real OHLC; smoothed-HA variant)

Priority **1**, complexity **2**, instruments MES, MNQ; bar size 5-min and 15-min. EQ **2** (the only hard evidence is that HA backtests are inflated by synthetic fills: NinjaTrader/EliteTrader 46,000-trade ES test "too massive to be real"; vendor claims 65% backtest -> 55% live). Honest-fill rule enforced: the HA flip is then a lagging 2-bar average cross.

Data flag: signals on the HA series, fills on real bars (mandatory).

```
PARAMS: bar=5, smooth=0 (0 = raw OHLC; 10 = HA on SMA(10)-smoothed O/H/L/C as in TraderHalai), ema_len=50,
  stop_atr=1.0 (x ATR(14) on real B), tgt_mode='none' | 'rr2', entry_start='09:35', last_entry='15:00', flat='15:55', max_trades=3
PRE on B = resample(df1, bar, rth_only=True):
  src = B if smooth == 0 else {o,h,l,c: SMA(B.o/h/l/c, smooth)}
  haClose = (src.o+src.h+src.l+src.c)/4; haOpen[k] = (haOpen[k-1] + haClose[k-1])/2 (seed (src.o+src.c)/2)
  green[k] = haClose[k] > haOpen[k]; e50 = EMA(B.close, ema_len) (REAL close); a = ATR(14) on real B
  flip_up[k] = green[k] and not green[k-1] and B.close[k] > e50[k];  flip_dn[k] = not green[k] and green[k-1] and B.close[k] < e50[k]
ENTRY: for k with a flip, tod in window, i = B.i_next[k] != -1: side; entry_ref = B.close[k] (REAL close)
  stop_px = entry_ref - side*stop_atr*a[k]; tgt_px = tgt_mode == 'rr2' ? entry_ref + side*2*stop_atr*a[k] : NaN
  place(i, side, stop_px=stop_px, tgt_px=tgt_px)     # market at next real 1-min open (+1 tick)
EXIT: first opposite HA colour bar k' (green[k'] != green[entry]): exit_at(B.i_next[k'], side); stop; target; flat.
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = max_trades; Lucid risk block.
```
Grid (16 combos): `bar {5, 15}`, `smooth {0, 10}`, `stop_atr {1.0, 2.0}`, `tgt_mode {none, rr2}`.

Risk: the vendor's "20 ES points" target is 4x a 5-min ATR; `rr2` stands in for it. Expect the honest version to show no edge; the comparison against a (deliberately not implemented) HA-fill version is the point.

## 12. bot_popular_indicators__ichimoku_cloud_intraday  (Ichimoku 9/26/52 cloud breakout, intraday)

Priority **1**, complexity **2**, instruments MES, MNQ; bar size 15-min and 30-min. EQ **3** (several independent daily tests, all negative vs benchmark: Dow 30 90% underperform, QuantConnect energy Sharpe -0.31, SPY weekly underperforms). The report says exclude; it is codeable, so it gets one minimal pass as a long shot and a known-bad calibration.

```
PARAMS: bar=15, t=9, k=26, s=52, mode='price_cloud' | 'chikou', direction='long_only' | 'both', stop_atr=1.5 (x ATR(14) on B),
  max_stop_atr=0.5 (x ATR14d), entry_start='09:45', last_entry='15:00', flat='15:55', max_trades=2
PRE on B = resample(df1, bar, rth_only=True) (continuous RTH series): tenkan, kijun, senkouA, senkouB, cloud_top, cloud_bot = Ichimoku(t, k, s)
  (senkou spans at bar k are the values computed at bar k-26: no look-ahead; need >= 78 bars of history)
  price_cloud: flip_up[k] = close[k] > cloud_top[k] and close[k-1] <= cloud_top[k-1] and tenkan[k] > kijun[k]; flip_dn mirror below cloud_bot
  chikou:      flip_up[k] = close[k] > cloud_top[k-26] and close[k-1] <= cloud_top[k-27] (today's close vs the cloud 26 bars back); mirror
ENTRY: for k with a flip, tod in window, direction ok, i = B.i_next[k] != -1: entry_ref = close[k]
  stop_px = side > 0 ? min(kijun[k], entry_ref - stop_atr*ATR14(B)[k]) : mirror; clamp |entry_ref - stop_px| <= max_stop_atr*ATR14d
  place(i, side, stop_px=stop_px)
EXIT: close back inside/through the cloud (long: close[k'] < cloud_top[k']) -> exit_at(B.i_next[k'], side); stop; flat.
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = max_trades; Lucid risk block.
```
Grid (16 combos): `bar {15, 30}`, `mode {price_cloud, chikou}`, `stop_atr {1.5, 3.0}`, `direction {long_only, both}`.

Risk: few trades, low win rate; drop after one pass unless PF >= 1.2 on 2023-2026.

## 13. bot_popular_indicators__renko_brick_reversal_approx  (Renko brick-reversal scalp, bricks built from 1-minute closes, fills on real bars)

Priority **1**, complexity **3**, instruments MNQ, MES; bar size: 1-minute closes -> Renko bricks of `size_atr x ATR14d` (NQ ~10-20 pts, ES ~2-4 pts, matching the lore). EQ **1** (no independent after-cost test; every tool maintainer documents that Renko backtests fill at synthetic prices and are "reliably flattering").

Data flag (approximation, not faithful to tick Renko): bricks form on 1-minute **closes** only (a tick-level brick that forms and reverses inside one minute is invisible), bricks reset at each 09:30 open (anchor = first RTH close) so overnight gaps do not print phantom bricks, and all fills are at the next real 1-minute open + 1 tick. Results are an approximation of what a tick-Renko bot would see and must be labelled as such.

```
PARAMS: size_atr=0.05 (brick = size_atr x ATR14d, rounded to a tick, min 2 ticks), n_confirm=2 (up bricks after a down brick),
  tgt_bricks=3, stop_bricks=2, ema_filter=0 (0 = off; 20 = EMA(20) of brick closes must be rising for longs),
  entry_start='09:40', last_entry='15:00', flat='15:55', max_trades=4
BRICK BUILDER per session d (RTH 1-min closes c[i], i from the 09:30 bar):  size = brick size for day d
  top = bot = c[first]; bricks = []     # classic Renko: an up brick needs close >= top + size; a down brick needs close <= bot - size
  for each bar i: while c[i] >= top + size: push(+1, top, top+size at bar i); bot = top; top += size
                   while c[i] <= bot - size: push(-1, bot-size, bot at bar i); top = bot; bot -= size
  (several bricks can print on one 1-min bar; a brick's bar index is the 1-min bar whose close completed it)
  brick_close series = top of up bricks / bottom of down bricks; e20 = EMA(brick_close, 20) if ema_filter
ENTRY long (short mirrored): at 1-min bar i (tod in window) where the last n_confirm bricks are all +1 and the brick before them
  is -1 and all n_confirm bricks completed at bar i or later than the previous entry/exit; (ema_filter: e20 rising)
  entry_ref = close[i]; stop_px = entry_ref - stop_bricks*size; tgt_px = entry_ref + tgt_bricks*size
  place(i+1, +1, stop_px=stop_px, tgt_px=tgt_px)         # market at the next real 1-min open
EXIT: first opposite brick completing at bar j > entry bar: exit_at(j+1, +1); stop; target; flat.
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = max_trades; Lucid risk block.
```
Grid (16 combos): `size_atr {0.05, 0.10}`, `n_confirm {1, 2}`, `tgt_bricks {3, 6}`, `ema_filter {0, 20}`. Fixed stop 2 bricks.

Risk: brick = 3 ES pts -> stop $30/MES, target $45-90; costs $3.80 per trade are 10%+ of the stop. If PF < 1.1 here, the tick version will not be better after real slippage.

## 14. bot_popular_indicators__utbot_stc_hull_ultimate  (UT Bot + Schaff Trend Cycle + Hull Suite confluence, "ULTIMATE scalping", Myth-Busting #1)

Priority **1**, complexity **3**, instruments MNQ, MES; bar size 5-min and 15-min. EQ **1** (no results published; built to test the YouTube claim). Three lagging trend tools in agreement = late, infrequent entries.

```
PARAMS: bar=5, ut_a=2.0, ut_c=6, stc=(80, 27, 50), stc_lo=25, stc_hi=75, hull_len=55, tgt='none' | 'rr2',
  max_stop_atr=0.5 (x ATR14d), entry_start='09:35', last_entry='15:00', flat='15:55', max_trades=3
PRE on B = resample(df1, bar, rth_only=True):
  ut_stop, ut_buy, ut_sell = UTBot(ut_a, ut_c); ut_state[k] = close[k] > ut_stop[k] ? +1 : -1
  s = STC(80, 27, 50); stc_up[k] = s[k] > s[k-1]
  h = HMA(close, hull_len); hull_up[k] = h[k] > h[k-2]
  long_ok[k]  = s[k] < stc_lo and stc_up[k] and hull_up[k] and ut_state[k] == +1
  short_ok[k] = s[k] > stc_hi and not stc_up[k] and not hull_up[k] and ut_state[k] == -1
  fire_long[k] = long_ok[k] and not long_ok[k-1]  (first bar of agreement); fire_short mirror
ENTRY: for k with fire, tod in window, i = B.i_next[k] != -1: side; entry_ref = close[k]; stop_px = ut_stop[k]
  clamp |entry_ref - stop_px| to [2 ticks, max_stop_atr*ATR14d]; tgt_px = tgt == 'rr2' ? entry_ref + side*2*|entry_ref - stop_px| : NaN
  place(i, side, stop_px=stop_px, tgt_px=tgt_px)
EXIT: UT Bot opposite signal (ut_sell for longs) -> exit_at(B.i_next[k'], side); stop; target; flat.
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = max_trades; Lucid risk block.
```
Grid (16 combos): `bar {5, 15}`, `ut_a {1.0, 2.0}`, `tgt {none, rr2}`, `stc_lo/hi {25/75, 50/50}` (50/50 = "STC on the right side of the midline", the loose reading).

Risk: likely < 1 trade/day; too few trades to pass an eval on time even if positive. Drop if PF < 1.1.

## 15. bot_popular_indicators__psar_ma_squeeze_confluence  (PSAR flip + 50/200 MA stack + LazyBear squeeze momentum; HawkEye volume leg DROPPED, Myth-Busting #6)

Priority **1**, complexity **3**, instruments MNQ, MES; bar size 5-min and 15-min. EQ **1** ("7% per day" is a YouTube title; no results).

Data flag: the HawkEye Volume(200) leg needs volume, which the data does not have; it is **dropped**, so this spec is a superset of the published rule (more signals than the original would take). This is noted as an approximation, not a faithful replication; if the OHLC-only confluence has no edge the original cannot be rescued by the volume filter alone.

```
PARAMS: bar=5, af0=0.02, af_inc=0.02, af_max=0.2, ma_mode='50_200' | '50_only', ma_len_fast=50, ma_len_slow=200, tgt='none' | 'rr2',
  max_stop_atr=0.5 (x ATR14d), entry_start='09:35', last_entry='15:00', flat='15:55', max_trades=3
PRE on B = resample(df1, bar, rth_only=True): psar = PSAR(af0, af_inc, af_max); m50 = SMA(close, 50); m200 = SMA(close, 200)
  val = LazyBear momentum as in spec 8; mom_green[k] = val[k] > 0 and val[k] > val[k-1]; mom_red mirror
  psar_flip_up[k] = psar[k] < low[k] and psar[k-1] > high[k-1]       # dot moves below price this bar
  stack_up[k] = ma_mode == '50_only' ? close[k] > m50[k] : (close[k] > m50[k] > m200[k])
  fire_long[k] = psar_flip_up[k] and stack_up[k] and mom_green[k]; fire_short mirror
ENTRY: for k with fire, tod in window, i = B.i_next[k] != -1: side; entry_ref = close[k]; stop_px = psar[k] (the new dot)
  clamp |entry_ref - stop_px| to [2 ticks, max_stop_atr*ATR14d]; tgt_px = tgt == 'rr2' ? entry_ref + side*2*|entry_ref - stop_px| : NaN
  place(i, side, stop_px=stop_px, tgt_px=tgt_px)
EXIT: PSAR flips back (long: psar[k'] > low[k']... i.e. psar[k'] >= close[k']) -> exit_at(B.i_next[k'], side); stop; target; flat.
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = max_trades; Lucid risk block.
```
Grid (16 combos): `bar {5, 15}`, `ma_mode {50_200, 50_only}`, `tgt {none, rr2}`, `af_inc {0.02, 0.01}`.

Risk: PSAR stop right after a flip is tight (good for $R) but the flip itself is late; expect < 1 trade/day. Drop if PF < 1.1.

## 16. bot_popular_indicators__bb_ema10_ao_supertrend  (EMA(10) cross of BB(42,2) basis + Awesome Oscillator + Supertrend(10,3), "Best 3 Buy and Sell Indicators", Myth-Busting #3)

Priority **1**, complexity **2**, instruments MNQ, MES; bar size 5-min and 15-min. EQ **1** (no results published).

```
PARAMS: bar=5, bb_len=42, bb_mult=2.0, ema_len=10, ao=(10, 77) | (5, 34), st=(10, 3.0), exit_mode='st_flip' | 'ema_cross',
  tgt='none' | 'rr2', max_stop_atr=0.5 (x ATR14d), entry_start='09:35', last_entry='15:00', flat='15:55', max_trades=3
PRE on B = resample(df1, bar, rth_only=True): basis = SMA(close, bb_len); e10 = EMA(close, ema_len); ao = AO(ao_fast, ao_slow)
  trend, up_f, dn_f, st_line = Supertrend(10, 3.0)
  fire_long[k] = e10[k] > basis[k] and e10[k-1] <= basis[k-1] and close[k] > basis[k] and ao[k] > 0 and ao[k] > ao[k-1] and trend[k] == +1
  fire_short mirror (e10 crosses below basis, close < basis, ao < 0 and falling, trend == -1)
ENTRY: for k with fire, tod in window, i = B.i_next[k] != -1: side; entry_ref = close[k]; stop_px = st_line[k]
  clamp |entry_ref - stop_px| to [2 ticks, max_stop_atr*ATR14d]; tgt_px = tgt == 'rr2' ? entry_ref + side*2*|entry_ref - stop_px| : NaN
  place(i, side, stop_px=stop_px, tgt_px=tgt_px)
EXIT: exit_mode st_flip: Supertrend flips against -> exit_at(B.i_next[k'], side); ema_cross: e10 crosses back through basis -> exit_at. Stop; target; flat.
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = max_trades; Lucid risk block.
```
Grid (16 combos): `bar {5, 15}`, `ao {(10,77), (5,34)}`, `exit_mode {st_flip, ema_cross}`, `tgt {none, rr2}`. (Optional ADX > 25 filter is off; the script's default.)

Risk: Supertrend-line stop on 15-min NQ is wide; the clamp caps it at 0.5 ATR14d. Drop if PF < 1.1.

## 17. bot_popular_indicators__osgfc_supertrend  (one-sided Gaussian filter channel + Supertrend(10,3) agreement, Myth-Busting #12)

Priority **1**, complexity **3**, instruments MNQ, MES; bar size 15-min (as published) and 5-min. EQ **1** (no results published; forex/crypto context).

Data flag: the exact loxx OSGF kernel was not retrievable; the causal Gaussian weighting above (`sigma = depth/2`) is a reconstruction and is labelled as such in the module docstring.

```
PARAMS: bar=15, depth=10, atr_len=21, ch_mult=0.628, st=(10, 3.0), st_cond='state' | 'flip', tgt='none' | 'rr2',
  max_stop_atr=0.5 (x ATR14d), entry_start='09:35', last_entry='15:00', flat='15:55', max_trades=2
PRE on B = resample(df1, bar, rth_only=True): G = OSGF(depth); a21 = ATR(atr_len); ch_up = G + ch_mult*a21; ch_dn = G - ch_mult*a21
  g_up[k] = G[k] > G[k-1]
  osg_buy[k] = close[k] > ch_up[k] and close[k-1] <= ch_up[k-1]; osg_sell[k] = close[k] < ch_dn[k] and close[k-1] >= ch_dn[k-1]
  trend = Supertrend(10, 3.0).trend; st_flip_up[k] = trend[k]==+1 and trend[k-1]==-1
  fire_long[k] = osg_buy[k] and (st_cond == 'state' ? trend[k] == +1 : st_flip_up[k]); fire_short mirror
ENTRY: for k with fire, tod in window, i = B.i_next[k] != -1: side; entry_ref = close[k]; stop_px = side > 0 ? ch_dn[k] : ch_up[k]
  clamp |entry_ref - stop_px| to [2 ticks, max_stop_atr*ATR14d]; tgt_px = tgt == 'rr2' ? entry_ref + side*2*|entry_ref - stop_px| : NaN
  place(i, side, stop_px=stop_px, tgt_px=tgt_px)
EXIT: Gaussian filter slope flips against the position (long: not g_up[k']) -> exit_at(B.i_next[k'], side); stop; target; flat.
SESSION: set_session(entry_start, last_entry, flat); max_trades_day = max_trades; Lucid risk block.
```
Grid (16 combos): `bar {5, 15}`, `st_cond {state, flip}`, `ch_mult {0.628, 1.0}`, `tgt {none, rr2}`.

Risk: `st_cond='flip'` (both signal on the same bar) will produce a handful of trades per year; `state` is the testable reading. Drop if PF < 1.1.

---

## Dropped or folded (and why)

| Report section | Decision |
|---|---|
| 2.1 Supertrend (10,3) canonical always-in | Folded into spec 2 as the `filter='none'`, `stop_mode='line'`, `last_entry='15:00'` corner (flat 15:55 is mandatory anyway; the always-in overnight version is not allowed). |
| 2.10 LuxAlgo Signals & Overlays | Dropped: closed source, cannot be replicated from OHLC, repainting reports. |
| 2.12 RSI(14) 30/70 cross | Folded into spec 5 as `rsi_len=14` (control cell; independent 1-/5-min tests show 20-23% win). The 60-min version yields a handful of trades a week and cannot pass an eval on time. |
| 2.11 MACD zero-line stand-alone | Folded into spec 10 as `mode='macd_only'`. |
| 2.15 Smoothed Heikin-Ashi (TraderHalai) | Folded into spec 11 as `smooth=10`; its published BTC 8H/1D results are multi-day trend following and irrelevant intraday. |
| 2.19 HawkEye Volume leg | Needs volume; dropped from spec 15 (flagged as a superset approximation). |
| 2.22 Aeromir Goldilocks | Dropped: proprietary. Used only as the realistic ceiling for a live retail bot (PF 1.32, 48% win, $45/trade on 2 MGC, max DD $8,368 = 4.2x Lucid's room). |
| 2.23 Vector Algorithmics | Dropped: proprietary, vendor shut down; also a warning that some firms close funded accounts for unattended bots (check Lucid's automation policy before live deployment). |
| 2.25 Automated Trading Strategies pack | Dropped: proprietary; reality check only ($11-19k per-strategy drawdowns on minis in a bull year). |
| VWAP in spec 2 | TWAP proxy (`session_vwap`), flagged; not faithful enough for anything beyond a side filter. |
| Vol-targeted sizing (spec 1) | Replaced by Lucid micro sizing from the Monte Carlo plus ATR hard stop; the paper's 2-3% vol target has no meaning on a fixed-contract prop account. |
| News blackout (spec 2 vendor rule) | Not implemented: no event calendar in the data set. |

## Notes for the backtest agents

- Run order: spec 1 first and in full (grid + 2023-2024 hold-out + 2010-2024 plateau + walk-forward through 2022 and 2023 H2); it is the only candidate with evidence and the benchmark for the rest. Then specs 2, 5, 8 (priority 2) as one batch. Specs 3, 4, 6, 7, 9-17 are one-pass long shots: run the grid on 2023-01..2026-09, keep anything with PF >= 1.2 and >= 60 trades, drop the rest and record the result in `results/<id>/README.md` so the family is closed out with numbers.
- Engine traps specific to this family: (1) never fill at HA/Renko/smoothed prices; (2) every signal is on a confirmed bar (`B.i_next`); (3) reversals need the two-bar pattern (`exit_at(i)`, `place(i)`, `place(i+1)`); (4) `daily_loss_stop` / `daily_profit_stop` are realized-only and block new entries only, so no entry without `stop_px`; (5) regime fit: any positive Supertrend/UT-Bot/HA cell found must survive 2022 and 2023 H2 before it is believed.
- Consistency-rule arithmetic: with `daily_profit_stop` at 1.0x the block and 10 micros the largest day is ~$1,200-1,600 < 50% of $3,000; spec 1 runs at 1.5x and will therefore want fewer micros (4-8). With 20 micros the block must be halved or the Monte Carlo will show consistency failures.
- Payout gate: 5 EOD days >= $150 with a net-positive cycle favours a 55-65% positive-day profile; specs 5 and 8 are the only indicator specs with a plausible path to that, spec 1 gets there via trade count (1-3/day) rather than win rate. Verify day-by-day positive-day share in the report, not just monthly.
