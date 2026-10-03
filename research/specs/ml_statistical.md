# Specs: Machine learning and statistical modeling on intraday OHLC bars, for the Lucid 50K LucidFlex backtest

Source report: `/home/user/claude-workspace/research/families/ml_statistical.md` (read in full; the structured findings JSON was supplied inline by the harness, no `findings/ml_statistical.json` existed at spec time).
Engine contract: `/home/user/claude-workspace/docs/STRATEGY_GUIDE.md`, `backtest/engine.py` (`Intents.place / set_session / exit_at`, `max_trades_day`, `daily_loss_stop`, `daily_profit_stop`, `max_hold`, `valid_bars`, `kind='stop'|'limit'`), helpers in `strategies/common.py` (`atr`, `ema`, `sma`, `rsi`, `adx`, `session_vwap` (TWAP proxy), `prior_day_stats`, `overnight_range`, `opening_range`, `daily_atr`, `vix_lag1`, `session_info`), `backtest.data.load_1m / resample / daily_bars / hm`, Lucid simulator `backtest.lucid.monte_carlo / simulate_eval / Rules`.

**Headline from the report, restated so the backtest agents allocate time correctly.** Predicting the next bars with GB/RF/LSTM on single-instrument OHLC features is null out-of-sample on MNQ 2021-2025 (50.0-50.9% accuracy vs a 51.8% base rate, permutation p 0.135-0.515). Lorentzian Classification is 0/96 on an independent aggregate. What survived strict walk-forward is (a) **state classification followed by a simple rule** (GMM regime transitions, 60-75 min holds, T 3.1-4.3, single author, volume feature we must replace), (b) **meta-labeling** of a rule-based primary (ES e-mini OOS: Sharpe 0.47 -> 1.31, max DD -28% -> -6.5%), and (c) **daily regime gating and vol-targeted sizing** as overlays that reduce the size of losing days. The family's value for a $2,000 EOD-trailing-drawdown account is therefore variance reduction (filter, gate, size), not forecasting. Specs 1, 4, 5 are the ones to spend engine time on; specs 10-12 are experiment arms / negative controls that exist so the loop runs them once, logs the null, and stops.

---

## 0. Conventions used by every spec below

### 0.1 Time, sessions, fills
All times **ET**. Data session 18:00 -> ~16:14 (equity CFD feed), 18:00 -> 17:00 gold. RTH equities 09:30-16:00; gold pit 08:20-13:30. A 1-minute bar with `tod = T` covers `[T, T+1)`. A decision taken "at the close of bar `tod = T-1`" is placed at the 1-minute index of bar `tod = T` (`i_next` on resampled frames, skip `-1`): **market at next open** (+1 tick slippage) unless the spec says `kind='stop'` or `kind='limit'`. On N-minute bars (`resample(df1, N, rth_only=True, rth=(start, end))`) decisions use the N-bar close and the order index is `i_next`. `resample` buckets by minutes since 18:00, so 5/15/30-minute bars align on :00/:15/:30/:45 for any `start` that is a multiple of the bar size past 18:00 (03:00, 09:30 both are).

Forced flat: equities **15:55** (never later than 15:58); London-session spec flat **08:30**; gold 13:25 for pit-only, 16:30 for full-session. No overnight, no weekends.

Engine costs are already included: 1 tick slippage per side on market/stop fills (none on limit fills), $1.30 round-trip micro commission. In points, the round-trip cost `cost_pts` used for label dead zones is **MES 0.76, MNQ 1.15, MGC 0.33** (2 ticks slip + commission / point value). These replace the report's 0.75 / 2.0 / 0.5 protocol values; the report's MNQ 2.0 is more conservative and is used as the robustness check (`--slip 2`).

### 0.2 Indicators (exact definitions)
- `ATR14d` = `daily_atr(df1, 14, rth_only=True)`: Wilder ATR of RTH daily bars, shifted one day (day d uses days < d). NaN never trades.
- `ATR1m_20` = `atr(df1_rth, 20)` Wilder ATR on 1-minute RTH bars (rolling across sessions; a volatility estimate from past bars only). `ATR5m_20` = Wilder ATR(20) on 5-minute RTH bars (`resample(..., 5, rth_only=True)`), likewise `ATR15m_20`.
- `TR_b` = max(H-L, |H-pc|, |L-pc|) of bar b, pc = prior bar close.
- `base5[d]` = mean of 5-minute RTH `TR` over the 20 sessions before d (per-session means, shifted); `base1[d]` same on 1-minute bars; `base15_lon[d]` same on 15-minute 03:00-08:30 bars. `atr_ratio_b = ATR_b / base[d]`.
- `act_z_b` (**OHLC-only stand-in for the papers' 50-bar volume z-score; FLAGGED approximation**) = z-score over the last 50 bars of `TR_b / ATR20_b` (rolling mean/sd, `min_periods=50`). Rationale: range per unit of recent volatility is the only activity measure OHLC gives; the author's own `atr_ratio` already carries most of it, so the GMM loses one partly redundant feature rather than an independent one. Where volume was a *gate* (RTH Confluence `volume z > 0.5`) the stand-in is a weaker gate and the spec's grid includes turning it off.
- `clpos_b` = (C-L)/(H-L), 0.5 when H == L.
- `O930`, `prev_close`, `pd_high/pd_low` as in the trend_momentum specs (`daily_bars(rth_only=True)`, `prior_day_stats`).
- `TWAP` = `session_vwap(df1_rth)` (equal-weighted typical price from 09:30; VWAP proxy, flagged).
- `rv10[d]`, `rv20[d]` = sd of the last 10 / 20 daily RTH log returns, shifted one day.
- `VIX_lag` = `vix_lag1(df1)`.
- Feature set **F_base** (used by specs 1, 10, 11; every item uses bars <= the decision bar only; 5-minute RTH bars unless stated; within-session lags that do not exist yet are filled with 0 and `mso` disambiguates them):
  `r1, r2, r3, r6, r12` = C_b / C_{b-k} - 1 (same session); `cum_ret` = C_b / O930 - 1; `gap_atr` = (O930 - prev_close) / ATR14d; `atr_ratio_b`; `clpos_b, clpos_{b-1}, clpos_{b-2}`; `range12_atr` = (max H - min L over last 12 bars) / ATR14d; `mso` = minutes since 09:30; `dow`; `pd_ret` = prev_close / prev_prev_close - 1; `pd_range_ratio` = (pd_high - pd_low) / ATR14d; `rv10, rv20`; `twap_dist` = (C_b - TWAP_b) / ATR5m_20; `rsi14` = `rsi(close5, 14)`. Optional add-ons (`features='base+regime'`): `hurst_s` (spec 9), `p_stress` (spec 4), `vvg_day` (spec 12).

### 0.3 The extended-history pattern (mandatory for every spec that fits a model)
`backtest.run.prepare` loads only `WARMUP_DAYS = 45` calendar days before `--start`, and the Lucid Monte Carlo starts an evaluation on every session of the run window, so **training history must never come from the run window and warm-up sessions must never appear in `daily`**. Every model-fitting spec therefore does, inside `generate(df1, contract, params)`:
```
s0, s1 = df1['session'].min(), df1['session'].max()
hist = load_1m(contract.data_symbol, s0 - (train_months + 2) months, s1)      # own load; df1 is a suffix of it
features / labels / models are computed on `hist`
decisions are produced for sessions in df1 only, keyed by (session, tod)
idx = df1.reset_index().merge(decisions, on=['session','tod'])['index']       # map to df1's 1-minute index
it.place(idx, ...)
```
`day_id` differs between `hist` and `df1`; never join on it. Model fits are **walk-forward inside generate**: for each calendar month m of df1, fit on `hist` sessions `< first_session(m) - embargo_days` restricted to the trailing `train_months`, predict month m; `retrain_every` months may be 1 or 3 to save time. Log the number of configurations tried in `results/<id>/README.md` (deflated-Sharpe input).

### 0.4 Libraries
Installed: numpy 2.4, scipy 1.17, pandas 3.0, numba 0.68. **Not installed: scikit-learn, lightgbm, hmmlearn, statsmodels** (PyPI is reachable: `pip install scikit-learn hmmlearn`, `lightgbm` optional). Each spec names its sklearn/hmmlearn call and a numpy fallback; appendix A gives the fallbacks (GMM EM, HMM forward + Baum-Welch, Kalman, IRLS logistic). Random forests / gradient boosting have no numpy fallback: if sklearn cannot be installed, `model='logit'` is the only option for specs 1 and 10 (Fischer & Krauss found logistic insignificant where RF was not; record that).

### 0.5 Validation protocol (report section 17; every ML candidate must pass before it goes to the Lucid MC)
1. Expanding-window walk-forward with yearly OOS folds: test 2023, 2024, 2025, 2026-partial (training always ends >= 1 day before the fold). Report each fold.
2. Gates, all required: net-of-cost mean per trade > 0 with T >= 2.0 on pooled OOS trades; >= 30 trades per OOS fold; net > 0 in every OOS year; permutation test (shuffle training labels, or entry dates for rule systems, 200 times) p < 0.05; deflated Sharpe > 0 given the logged config count.
3. Hyperparameters only inside purged 5-fold CV with a 1-day embargo on the training fold; one locked OOS run per candidate.
4. Then the normal checks: `backtest.batch` on 2025-01..2026-09 and 2023-01..2024-12, plateau not spike, and `backtest.lucid` MC pass rate / first-payout probability.
Overlays (specs 4, 5) are validated differently: the overlaid primary must show lower max EOD drawdown and a lower worst-10-day sum with <= 15% loss of net on 2023-2026, and a higher Lucid pass rate or expected net per evaluation.

### 0.6 Lucid risk block (default for every trading spec unless overridden; values per ONE micro contract)
- `daily_loss_stop`: MES $60, MNQ $80, MGC $80 (grid multiplier `{1.0, 1.5}`). At 10 micros this is $600-$1,200, <= 60% of the $2,000 MLL distance.
- `daily_profit_stop`: MES $120, MNQ $160, MGC $160 (grid multiplier `{1.0, 1.5, none}`). At 10 micros caps a day at ~$1,200-$1,800 < 50% of the $3,000 target (consistency rule) and spreads a funded cycle over many >= $150 days.
- Both stops only prevent NEW entries; every entry carries a hard protective stop. One position at a time; `max_trades_day` as specified; `set_session(entry_start, entry_end, flat)` always.
- **Per-trade bet sizing (Lopez de Prado ch. 10, report section 16) is not implementable in the engine** (one fixed contract per run). It is replaced by the probability threshold `p_thr` (trade / no trade) and, for day-level sizing, by the daily-multiplier post-processor of specs 4 and 5. Not a separate spec.

### 0.7 Daily-multiplier post-processor (specs 4 and 5)
The engine's `daily` table (`pnl, min_eq, max_eq` per ONE micro) is linear in contracts, and `monte_carlo`'s `eval_schedule` callable has no calendar index. So an overlay with per-session multiplier `mult[session]` is applied exactly as
```
d = daily.copy(); m = mult.reindex(d['session']).fillna(1.0).values
for col in ('pnl', 'min_eq', 'max_eq'): d[col] = d[col].values * m
d['trades'] = np.where(m > 0, d['trades'], 0)
monte_carlo(d, eval_micros=base_micros, constant_micros(min(base_micros, 20)), Rules())
```
Add this as `backtest/overlays.py: apply_daily_mult(daily, mult)` (new file; the spec does not touch existing files). In-engine, the same overlay as a pure skip is `it.allow_entry &= (mult_of_day[df1.day_id] > 0)`.

Priority 5 = best prior under Lucid constraints with evidence, 1 = long shot / negative control. Complexity 1 = a few lines on existing helpers, 5 = model fitting inside a multi-state intraday machine.

---

## 1. ml_statistical__meta_label_filter  (meta-labeling a rule-based primary; Lopez de Prado / Hudson & Thames)

Priority **4**, complexity **4**, instruments MES, MNQ (MGC with a gold primary); bar size: primary's (1-min data, 5-min features). EQ 3 (ES e-mini OOS 2018-19: Sharpe 0.47 -> 1.31, MDD -28.2% -> -6.5% on a Bollinger primary; 0.69 -> 0.95 on an SMA primary; one team, dollar bars). Best prop fit in the family: fewer trades, same day-trade structure, drawdown reduction is the eval's key property.

Data gap: the paper's dollar bars need volume; time bars are used (expect weaker meta accuracy). No other volume dependence.

Primaries: any **stateless** registered strategy whose every trade comes from one `place` call (ORB family, gap-and-go, last-half-hour, Crabel, Kalman gap spec 6, GMM specs 2/3). The noise-band state machine (`trend_momentum__noise_area`) is excluded: cancelling one of its entries changes its later state.

```
PARAMS: primary='trend_momentum__orb_sma200_oneloss' (+ primary_params = that spec's defaults), model='rf' | 'logit',
  p_thr=0.55, label_mode='pnl' | 'barrier', pt=2.0, sl=1.0, vert_bars=12 (5-min bars; barrier mode only),
  train_months=24, retrain_every=1, embargo_days=1, min_train_trades=150, n_trees=500, max_depth=5, min_leaf=50,
  max_samples=0.5, features='base' | 'base+regime', passthrough_when_untrained=False, flat=primary's flat
PRE:
  hist = load_1m(sym, s0 - train_months - 2 months, s1)                                  # 0.3
  it_p = primary.generate(hist, contract, primary_params); tr_p, _ = engine.run(it_p, contract)    # primary's realised trades on hist, costs included
  for each primary trade j: e_j = 1-min index of its fill (entry_ts -> index); pl_j = max{i <= e_j : it_p.sig[i] != 0}  (placement bar);
     dec_j = pl_j - 1 (last bar closed before the order went live); X_j = F_base at the 5-min bar containing dec_j (bars <= dec_j only)
     y_j (label_mode='pnl')     = 1 if pnl_j > 0 else 0
     y_j (label_mode='barrier') = 1 if, scanning 1-min bars e_j .. exit_j, high >= entry + pt*sigma_j is touched before low <= entry - sl*sigma_j
                                  (mirror for shorts), where sigma_j = ATR5m_20 at dec_j and the scan ends at min(vert_bars*5 bars, flat); else 0
  WALK-FORWARD over calendar months m of df1 (refit every retrain_every months):
     train = { j : exit session(j) <= first_session(m) - embargo_days  and  entry session(j) >= first_session(m) - train_months }
     if |train| < min_train_trades: month m gets p_j = NaN  (-> no trades, or pass the primary through unfiltered if passthrough_when_untrained)
     model='rf':    sklearn RandomForestClassifier(n_estimators=n_trees, max_depth, min_samples_leaf=min_leaf, max_samples, class_weight='balanced', n_jobs=4)
     model='logit': IRLS logistic on standardized X with L2 lambda=1.0 (appendix A4)
     p_j = P(y=1 | X_j) for the primary's trades whose placement session is in month m
  keep_j = (p_j >= p_thr)
ENTRY: it = Intents(df1); copy the primary's intents for df1's sessions from it_p via (session, tod) -> index (sig, entry_px, entry_kind, valid_bars,
  stop/tgt/trail/max_hold arrays, exit_flag, allow_entry window, force_flat), then set sig = 0 at the placement bars of trades with keep_j == False.
  (Equivalent and simpler when the primary is deterministic: run primary.generate(df1, ...) and zero sig at the mapped placement bars.)
  Pending orders of rejected trades are cancelled before they go live, so one-position-at-a-time interactions are unchanged for one-trade-per-day primaries;
  for multi-trade primaries a cancelled order may let a later same-day order fill that was previously blocked: accept (it is what live trading would do).
STOP / TARGET / EXIT: the primary's. SESSION: the primary's. max_trades_day: the primary's.
RISK: the primary's Lucid block; because the filter removes trades, re-run the Lucid scan (fewer, better trades support more micros).
```
Grid (24): `primary {trend_momentum__orb_sma200_oneloss, trend_momentum__orb_close_confirm_halfrange, trend_momentum__last_half_hour}`, `model {rf, logit}`, `p_thr {0.50, 0.60}`, `label_mode {pnl, barrier}`. Fixed: train_months 24, features 'base' (one extra run with 'base+regime' on the best combo).

Acceptance (beyond 0.5): versus the unfiltered primary on each of 2023, 2024, 2025, 2026 folds, the filtered version must (a) keep 40-75% of trades, (b) raise profit factor, (c) lower max intraday drawdown per micro in >= 3 of 4 folds. If it only removes trades at random (PF unchanged) it is dropped and the primary runs bare. Note from the report: the secondary model needs several hundred primary trades; ORB-type primaries give ~150/yr, so train_months 24 is the floor and 36 is the robustness run.

## 2. ml_statistical__gmm_london_transition  (Mesfin "London Session Signal B" rebuilt without volume)

Priority **3**, complexity **4**, instruments MNQ (published), MES; bar size 15-min on 03:00-08:30 ET bars. EQ 3 (walk-forward OOS N=247, net +4.09 pts/trade, T=4.30, p=0.000025, win 61.5%, sensitivity T 3.87-4.83; single author, 53+ configs disclosed; a 15-minute entry delay flips T to -2.78). Prop fit: <= 1 trade per session, 60-minute hold, flat before RTH, and it does not overlap any RTH strategy, so it stacks as an extra leg.

Data gap: the 50-bar volume z-score feature is replaced by `act_z` (0.2, flagged). London 1-min bars exist in the data (330 bars per session 03:00-08:29, checked). ET/London DST mismatch weeks (2-3 per year) are ignored.

```
PARAMS: bar=15, sess=('03:00','08:30'), last_entry='07:30', hold_min=60, stop_mode='pts' | 'atr', stop_pts=20 (MNQ; MES 5), stop_atr=1.0,
  n_comp=3, z_win=200, act_win=50, dc_n=4, clean_bars=2, train_months=24, retrain_every=3, direction='long' | 'both', tgt_mult=0 (none) | 2.0,
  flat='08:30', max_trades=1
BARS: B = resample(hist, 15, rth_only=True, rth=('03:00','08:30'))     # 22 bars/session, aligned on :00/:15/:30/:45
FEATURES per bar b (bars <= b only; rolling windows run across sessions):
  ATR15m_20_b; atr_ratio_b = ATR15m_20_b / base15_lon[d];  act_z_b (0.2, window act_win);  clpos_b;  ret_b = C_b/C_{b-1} - 1;
  dircon_b = fraction of bars b-dc_n+1..b with sign(ret) == sign(ret_b)
  z-score each feature over the last z_win bars (min_periods z_win), then standardize with mean/sd of the training fold.
MODEL (per walk-forward fold, 0.3): GMM n_comp components, full covariance, fitted on the training bars
  (sklearn GaussianMixture(n_components=3, covariance_type='full', n_init=5, max_iter=200, random_state=0) or appendix A1).
MAP components -> regimes on the training fold: R1 "Extreme Vol" = highest mean atr_ratio; of the other two, R2 "Bullish Drift" = higher mean ret
  (tie: higher dircon), R0 "Bearish Chop" = the other. Degenerate fold (mean ret of R2 - R0 < 0.1 sd of ret): no trades in the fold, log it.
STATE: s_b = argmax posterior component for OOS bars (predict with the fold's fitted GMM and scaler).
SIGNAL at close of bar b (same session for b-3..b, tod(b) + 15 <= last_entry):
  long  if s_b == R2 and s_{b-1} == R0 and R1 not in {s_{b-2}, s_{b-3}}               # clean R0 -> R2, no R1 in the prior clean_bars
  short (direction='both' only, unpublished mirror) if s_b == R0 and s_{b-1} == R2 and R1 not in prior clean_bars
ENTRY: place(B.i_next[b], side, stop_pts = stop_pts or stop_atr*ATR15m_20_b, tgt_pts = tgt_mult*stop (if tgt_mult>0), max_hold = hold_min)
  market at the first 1-min bar of the next 15-min bar: this is the paper's zero-delay fill. Stress test: shift idx by +5 and +15 bars (the paper's sign flip
  at a 15-min delay must reproduce; if it does not, the signal is not the paper's).
EXIT: max_hold 60 1-min bars, or flat 08:30, or the stop (or target).  SESSION: set_session('03:00', last_entry, '08:30'); max_trades_day = 1.
RISK: 20-pt MNQ stop = $40/micro ($800 at 20 micros); daily_loss_stop = 1.0x block; daily_profit_stop none needed (one trade). This leg's P&L lands in
  the same session as the RTH legs for the Lucid EOD/consistency math.
```
Grid (32): `stop_mode {pts, atr}`, `hold_min {45, 60}`, `clean_bars {1, 2}`, `direction {long, both}`, `dc_n {4, 8}`. Fixed: bar 15, n_comp 3, z_win 200, train_months 24, retrain quarterly; one extra run with the `act_z` feature removed (4-feature GMM) to measure what the volume stand-in contributes.

Acceptance: the paper's T >= 2 and >= 30 trades per yearly fold on MNQ 2023-2026 with the volume feature replaced; mean net >= +2 pts on MNQ. Then the Lucid scan.

## 3. ml_statistical__gmm_rth_confluence  (Mesfin "RTH Confluence": GMM state + Markov transition gate + pullback limit entry)

Priority **2**, complexity **4**, instruments MNQ (published), MES; bar size 5-min RTH with 1-min ATR. EQ 3 (OOS N=196, +11.82 pts, T=3.11; in-sample 2022-24 N=538, 61% win; contaminated first OOS fold and a globally fixed ATR baseline disclosed; replications failed until the 1-min ATR detail was published). Prop fit weaker than spec 2: the 80 x ATR_ratio stop is ~$160/micro, so the Lucid scan will cap it near 5 micros unless the tighter stop in the grid holds.

Data gap: `volume z > 0.5` gate replaced by `act_z > act_z_min` (flagged); the grid includes `act_z_min = -inf` (gate off).

```
PARAMS: bar=5, n_comp=3, trans_win=200, p_trans_min=0.15, act_z_min=0.5 | -inf, pb_k=2.4, valid_bars=30, hold_bars=60, stop_k=7.7 | 4.0,
  baseline='rolling20d' | 'train_median', train_months=12, retrain_every=3, first_signal='09:45', last_entry='15:00', flat='15:55', max_trades=2
FEATURES per 5-min RTH bar b (bars <= b):
  ATR1m_20 at B.i_last[b] (1-min Wilder ATR, rolling across sessions); atr_ratio_b = ATR1m_20 / base1[d]  (baseline='rolling20d')
     or / median(ATR1m_20 over the training fold) (baseline='train_median'; the paper used one fixed 10.34 for 2022-25, so this is closer to it)
  act_z_b (0.2, 50 bars of 5-min TR / ATR5m_20);  clpos_b;  ret5_b = C_b/C_{b-1} - 1.    Standardize with training-fold mean/sd (no rolling z here).
MODEL: GMM 3 components, full covariance, fit per walk-forward fold on the trailing train_months of RTH bars (sklearn GaussianMixture or A1).
MAP by mean atr_ratio on the training fold: R0 lowest = "Quiet", R1 middle = "Active Flow", R2 highest = "Expansion".
STATE: s_b = argmax posterior. TRANSITION GATE: P12_b = #(s_{t-1}==R1 and s_t==R2) / #(s_{t-1}==R1) over t in (b-trans_win, b]  (NaN if denominator < 10).
FIRE at close of bar b (tod(b) >= first_signal, tod(b)+5 <= last_entry): s_b == R1 and P12_b > p_trans_min and act_z_b > act_z_min.
ENTRY: level = C_b - pb_k * ATR1m_20_b  (paper: 25 x ATR_ratio pts = 25/10.34 x ATR1m_20 ~ 2.4 x; ATR_ratio capped [0.5, 2.0] -> cap pb at [1.2, 4.8] x base1[d])
  place(B.i_next[b], +1, entry_px=level, kind='limit', valid_bars=valid_bars (6 five-min bars), stop_pts = stop_k*ATR1m_20_b, max_hold=hold_bars)
  (limit fills need price to trade 1 tick through the level; no entry slippage). A second signal while an order is pending is ignored (engine: one pending order).
EXIT: max_hold hold_bars (paper: bar 13 after the signal bar = 65 min from signal; the engine counts from the fill, so 60 approximates it), flat 15:55, or the stop.
SESSION: set_session('09:45', last_entry, flat); max_trades_day = max_trades.
RISK: stop_k 7.7 -> ~80 pts MNQ = $160/micro: daily_loss_stop = 1.0x block is one stop; the Lucid scan will stop at ~5 micros. stop_k 4.0 is the prop-sized variant.
```
Grid (32): `stop_k {4.0, 7.7}`, `p_trans_min {0.10, 0.15}`, `act_z_min {0.5, -inf}`, `baseline {rolling20d, train_median}`, `pb_k {1.5, 2.4}`. Fixed: valid 30, hold 60, train 12 months quarterly refit.

Acceptance: T >= 2, >= 30 trades per fold, positive each of 2023-2026 on MNQ; the unconditional-long control (same entries without the regime/transition gate) must be worse. Drop after one grid pass if the pooled T < 1.5.

## 4. ml_statistical__hmm_daily_gate  (daily 2-state Gaussian HMM stress gate; overlay, not a strategy)

Priority **4**, complexity **3**, instruments: gate for MES, MNQ, MGC primaries; bar size daily. EQ 3 for regime identification (LSEG ES 1997-2023; Delmastro 2018-23 Sharpe 0.76 vs 0.56, MDD -24.5% vs -33.7%), 2 for incremental intraday P&L. Prop fit good: converts the trending-vol regime that breaches a $2,000 EOD-trailing MLL into a sizing decision with zero extra trades.

```
PARAMS: vol_feature='rv10' | 'vix_lag', W=2707 (max window, days), W_min=750, refit_days=21, thr_half=0.5, thr_off=0.7,
  mode_off='half' | 'off' | 'trend_only', source='intraday' (RTH closes from load_1m since 2010-11) | 'yahoo' (data/parquet/ES_1d.parquet)
INPUT (daily, through session d-1 only): r_d = log(C_d / C_{d-1}) of RTH closes; v_d = sd(r_{d-9..d}) (vol_feature='rv10') or log(VIX close d) (vix_lag);
  X_d = [r_d, log v_d] standardized with the training window's mean/sd.
MODEL: 2-state Gaussian HMM, full covariance. Every refit_days sessions, fit by Baum-Welch on X over the last min(W, available) days ending at d-1,
  W_min required (hmmlearn GaussianHMM(n_components=2, covariance_type='full', n_iter=200), 3 random restarts, keep best log-likelihood; or appendix A2).
  Between refits run only the forward filter with the fixed parameters; p_stress[d] = filtered P(state = stress | X_1..X_{d-1}) where stress = the state with
  the larger emission variance of r (ties: lower mean). Filtered, never smoothed (lookahead). 3 states are not in the grid (report: the "neutral" state hurt).
GATE -> daily multiplier mult[d]:
  p_stress < thr_half: 1.0;  thr_half <= p_stress < thr_off: 0.5;  p_stress >= thr_off: 0.5 (mode_off='half') | 0.0 (mode_off='off') |
  (mode_off='trend_only': 0.0 for mean-reversion primaries, 1.0 for ORB/trend primaries; the primary declares its type in a `kind` attribute).
USE: in-engine skip  it.allow_entry &= mult[day] > 0  (through a `regime_gate` param added to the primary's params by the wrapper), and sizing through
  apply_daily_mult (0.7) before the Lucid MC. The multiplier of day d is known at the close of d-1 (sizing can be set before the open).
```
Grid (16): `thr_half {0.5, 0.7}`, `thr_off {0.7, 0.9}`, `vol_feature {rv10, vix_lag}`, `mode_off {half, off}`. Fixed: W 2707, refit 21 days.

Acceptance (0.5 overlay rule): on the best 2-3 primaries from the other families, worst-10-day sum and max EOD drawdown fall, net falls <= 15%, Lucid pass rate or expected net per eval rises on 2023-2026. Known failure mode (LSEG): detection lags several days; the 2022 bear market was lagged. Never act on same-day states.

## 5. ml_statistical__har_vol_sizing  (HAR-RV volatility forecast -> daily micro count; overlay)

Priority **4**, complexity **2**, instruments: sizing overlay for any MES/MNQ/MGC leg; bar size daily from 5-min returns. EQ 3 for forecasting (arXiv:2510.03236 regime-conditioned HAR beat HAR in all sub-periods), 2 for P&L (Quantitativo vol-targeted ES/NQ: 65% positive months, worst -6.6%). Prop fit strong: it caps the largest day (consistency rule) and shrinks on the high-vol days that breach the trailing MLL.

```
PARAMS: target_risk=300 (eval) | 200 (funded), sd_lookback=60 traded days, m_min=2, m_max=20 | 30, regime='off' | 'on', refit_days=21, min_days=500
DAILY REALIZED VOL (through d-1): RV_d = sum of squared log returns of the 5-min RTH bars of day d; sd_d = sqrt(RV_d).
HAR-RV: regress sd_d on [1, sd_{d-1}, mean(sd_{d-5..d-1}), mean(sd_{d-22..d-1})] by OLS (numpy lstsq) on an expanding window (min_days), refit every refit_days;
  fsd[d] = forecast for day d from data <= d-1.
  regime='on': 2-component GMM (A1) on (log sd_d, |r_d|) fitted on the same window; P_hi[d] = posterior of the high component at d-1; fit two HAR regressions
  weighted by P_hi and 1-P_hi; fsd[d] = P_hi * fsd_hi + (1-P_hi) * fsd_lo  (the paper's coefficient-based soft-regime HAR).
STRATEGY SCALE: s_strat[d] = sd of the primary's per-micro daily pnl over the last sd_lookback traded sessions before d (shifted); its vol-adjusted forecast
  dsd[d] = s_strat[d] * fsd[d] / mean(fsd over those same sessions).
MICROS: micros[d] = clip(floor(target_risk / dsd[d]), m_min, m_max); eval cap 40 and funded cap 20 are enforced by Rules.
USE: apply_daily_mult(daily, micros[d]) then monte_carlo(d, eval_micros=1, constant_micros(1), Rules())  (the $ schedule is already baked in; the funded
  phase reuses the eval target_risk, so run both targets and report both).
```
Grid (16): `target_risk {200, 300}`, `sd_lookback {40, 60}`, `regime {off, on}`, `m_max {20, 30}`.

Acceptance: versus constant micros at the Lucid-scan optimum, the vol-targeted schedule must raise the pass rate or cut the consistency-rule failures with equal or better expected net per evaluation. Report the largest-day / total-profit ratio distribution.

## 6. ml_statistical__kalman_gap_continuation  (Kalman velocity on the first 30 minutes; gap-continuation short)

Priority **2**, complexity **3**, instruments MNQ (published), MES, MGC (pit open 08:20-08:50 window); bar size 1-min 09:30-10:00, hold 75 min. EQ 2 (35 OOS trades 2023-25: net +14.52 pts, T=1.46, by year +14.5 / -11.9 / +10.3; fails the trade-count and year-sign gates; the author's "most credible near-miss", recommends more years, which the 2010+ data gives). Prop fit: ~1 trade/month with a large edge; only useful as an extra leg on a daily base strategy.

```
PARAMS: win=('09:30','10:00'), z_thr=2.5, direction='short' | 'both', hold_min=75, stop_mode='atr5' (1.5 x ATR5m_20) | 'daily' (0.25 x ATR14d),
  q_scale=1e-5, min_hist_days=120, gap_min_atr=0.0, flat='15:55'
KALMAN (local linear trend) per session d on the 30 1-min closes c_1..c_30 of 09:30-09:59:
  state x=[level, vel]; F=[[1,1],[0,1]]; Hm=[1,0]; Q = q_scale * c_1^2 * [[1/3,1/2],[1/2,1]]; R = ATR1m_20(at 09:29)^2
  x0=[c_1, 0]; P0=diag(R, R); for k=2..30: predict x=Fx, P=FPF'+Q; K=P Hm'/(Hm P Hm' + R); x += K(c_k - Hm x); P=(I-K Hm)P   (appendix A3)
  v_d = x[1] after the 30th update (pts per minute).   gap_d = O930 - prev_close.
  z_v[d] = (v_d - mean{v_d' : d' < d}) / sd{v_d' : d' < d}, expanding over prior sessions, NaN until min_hist_days (the paper's "top 0.62% of |z|").
SIGNAL at 10:00 (bar tod 10:00 is the entry bar):
  short if gap_d < -gap_min_atr*ATR14d and z_v[d] < -z_thr;   long (direction='both') if gap_d > +gap_min_atr*ATR14d and z_v[d] > +z_thr
ENTRY: place(i of bar tod 10:00, side, stop_pts = 1.5*ATR5m_20 (at 09:55 bar) | 0.25*ATR14d, max_hold = hold_min)
EXIT: max_hold 75, or stop, or flat 15:55.   SESSION: set_session('10:00', '10:01', flat); max_trades_day 1.
RISK: 1.5 x ATR5m_20 on MNQ ~ 30 pts = $60/micro; this leg can share a day with ORB legs (different window) only in the portfolio runner, not in one module.
```
Grid (24): `z_thr {2.0, 2.5}`, `direction {short, both}`, `stop_mode {atr5, daily}`, `hold_min {75, 120}`, `gap_min_atr {0.0, 0.25}` minus the 8 combos with direction=short and gap_min_atr=0.25 beyond the first pass (keep <= 24). Fixed q_scale 1e-5 (sensitivity run at 1e-4).

Acceptance: run 2011-2026 (the author's own recommendation); needs >= 30 trades per yearly fold which only the long+short, z 2.0 variant can supply; otherwise it is a feature (`z_v`) for spec 1, not a strategy.

## 7. ml_statistical__kalman_slope_trend  (local-linear-trend Kalman slope with significance dead zone)

Priority **2**, complexity **2**, instruments MNQ, MES, MGC; bar size 5-min RTH (grid 15). EQ 2 (no published OOS ES intraday result; a smoother, it inherits the momentum family's evidence: MNQ 5-min Hurst ~0.59 says trend logic is the right sign on NQ). Prop fit: few trades per day, ATR stop, flat 15:55; a cheap experiment.

```
PARAMS: bar=5, qr=1e-4, k_in=2.0, k_out=0.0 | 1.0, reset_at_open=True | False, stop_atr=1.0, first_entry='10:00', last_entry='15:00', flat='15:55', max_trades=4
FILTER on 5-min RTH closes (across sessions, or reset at 09:30 with level=O930, slope=0, P=diag(R,R) when reset_at_open):
  R = ATR5m_20_b^2; Q = qr * R * [[1/3,1/2],[1/2,1]]; same recursion as spec 6 (A3); after bar b: slope_b, P_slope_b = P[1,1].
SIGNAL at close of bar b: long if slope_b > +k_in*sqrt(P_slope_b); short if slope_b < -k_in*sqrt(P_slope_b); else none.
ENTRY: if flat and signal and tod in [first_entry, last_entry): place(B.i_next[b], side, stop_pts = stop_atr*ATR5m_20_b)
EXIT: when in a long and slope_b < +k_out*sqrt(P_slope_b): exit_at(B.i_next[b]) (mirror shorts); or the stop; or flat 15:55.
SESSION: set_session(first_entry, last_entry, flat); max_trades_day = max_trades; Lucid block.
```
Grid (24): `qr {1e-4, 1e-3}`, `k_in {1.5, 2.5}`, `k_out {0.0, 1.0}`, `reset_at_open {True, False}`, `bar {5, 15}` (drop reset for bar 15 to stay <= 24). Benchmark: must beat `trend_momentum__ema_cross_pullback` on the same instrument and window, else fold into that spec as a smoother option.

## 8. ml_statistical__hmm_intraday_trend  (Christensen-Turner-Godsill HMM on bar returns, with a dead zone)

Priority **2**, complexity **4**, instruments MES (published on ES), MNQ; bar size 5-min RTH (paper: 1-min, always-in; grid 15). EQ 2 (2011 only: pre-cost Sharpe > 2 for Baum-Welch HMM and IOHMM, costs -15%, no other year). Prop fit weak as published (1-min flipping); the 5-min version with a dead zone and a 6-trade cap is the testable form.

```
PARAMS: bar=5, K=3, dz=1.0, dz_exit=0.0, train_months=6, retrain_every=1, stop_atr=1.0, first_entry='09:40', last_entry='15:00', flat='15:55', max_trades=6,
  include_globex=False | True (paper used 02:00-16:15; True trains on and decodes 02:00-15:55 bars but entries stay RTH)
RETURNS: y_b = 1e4 * log(C_b / C_{b-1}) on 5-min bars (within the chosen window; the first bar of a session uses the prior session's last close).
MODEL per walk-forward month: Gaussian HMM with K states, scalar emissions N(mu_k, s_k^2), transition matrix A, fitted by Baum-Welch on the trailing train_months
  (hmmlearn GaussianHMM(n_components=K, covariance_type='diag', n_iter=100) or A2). Order states by mu_k. sigma_E = sd of E_b over the training bars (below).
ONLINE DECODE per OOS session: alpha_0 = stationary distribution of A; for each bar b: alpha <- normalize((A' alpha) * N(y_b; mu, s)); E_b = sum_k alpha_k mu_k.
SIGNAL at close of bar b: long if E_b > +dz*sigma_E; short if E_b < -dz*sigma_E; exit-to-flat if sign(E_b) != position side or |E_b| < dz_exit*sigma_E.
ENTRY: place(B.i_next[b], side, stop_pts = stop_atr*ATR5m_20_b) when flat and tod in window;  EXIT: exit_at(B.i_next[b]) on the exit condition, stop, or flat 15:55.
SESSION: set_session(first_entry, last_entry, flat); max_trades_day = max_trades; Lucid block.
IOHMM side information (vol-ratio and seasonality splines in the transition matrix) is NOT specced: without it the paper's HMM still had Sharpe > 2; add only if the base passes.
```
Grid (32): `K {2, 3}`, `dz {0.5, 1.0}`, `bar {5, 15}`, `train_months {6, 12}`, `include_globex {False, True}`. Fixed dz_exit 0, stop 1.0 ATR. Expect many small trades: the 1.15-pt MNQ cost per trade is the binding constraint; report mean net per trade in cost units.

## 9. ml_statistical__hurst_regime_switch  (rolling Hurst exponent gate; trend and mean-reversion branches)

Priority **2**, complexity **3**, instruments MNQ, MES (MGC: trend branch only; report: OU mean reversion on MGC negative in every configuration, T down to -5.32); bar size 5-min RTH. EQ 2 (StockSharp crypto anecdotes; LuxAlgo: 100-bar H is "extremely noisy"; Mesfin: MNQ 5-min H ~0.59, MGC ~0.5). Prop fit neutral: primarily a gate (`hurst_gate` for specs 1 and 10 and for other families' primaries), standalone branches are the test of whether the gate carries information.

```
PARAMS: bar=5, W=100 | 200 (bars), taus=2..20, ema_n=10, h_lo=0.45, h_hi=0.55 | 0.60, branch='trend' | 'mr' | 'both', don_n=20, sma_n=20, dev_atr=1.0,
  stop_atr_trend=1.0, stop_atr_mr=1.5, valid_bars=25, first_entry='10:00', last_entry='15:00', flat='15:55', max_trades=3
HURST at bar b (log closes p over the last W 5-min RTH bars, rolling across sessions): for tau in taus: sd_tau = sd(p_t - p_{t-tau}) over the window;
  H_b = OLS slope of log(sd_tau) on log(tau);  H_s = EMA(H, ema_n) (common.ema).  NaN until W + ema_n bars.
GATE: trend regime if H_s > h_hi; mr regime if H_s < h_lo; else flat (no new entries). Exposed as hurst_gate(hist, params) -> per-(session, tod) regime for other specs.
TREND BRANCH (branch in {trend, both}) at close of bar b in trend regime, flat, tod in window:
  buy stop at max(H_{b-don_n..b-1}) + 1 tick (sell stop at min(L) - 1 tick): place(B.i_next[b], side, entry_px=level, kind='stop', valid_bars=valid_bars,
  stop_pts = stop_atr_trend*ATR5m_20_b)   (whichever side is nearer the close is placed; the engine holds one pending order).  Exit: stop or flat 15:55.
MR BRANCH (branch in {mr, both}; never on MGC) at close of bar b in mr regime, flat:
  long if C_b < SMA(sma_n)_b - dev_atr*ATR5m_20_b: place(B.i_next[b], +1, tgt_px = SMA_b, stop_pts = stop_atr_mr*ATR5m_20_b); mirror short.
  Also exit_at(B.i_next[b]) if H_s rises above 0.5 while in an MR trade (StockSharp rule).
SESSION: set_session(first_entry, last_entry, flat); max_trades_day = max_trades; Lucid block.
```
Grid (24): `W {100, 200}`, `h_hi {0.55, 0.60}`, `branch {trend, mr, both}`, `dev_atr {1.0, 1.5}`. Fixed h_lo 0.45, bar 5.

Acceptance: as a gate it must raise the gated primary's PF on 2023-2026 with <= 30% fewer trades; as a standalone it is dropped if PF < 1.2.

## 10. ml_statistical__direction_classifier  (RF / GB / logit on F_base with next-N, triple-barrier or trend-scanning labels; experiment arm and negative control)

Priority **1**, complexity **4**, instruments MNQ, MES, MGC; bar size 5-min RTH. EQ 2, strongly null (Mesfin MNQ 2021-25: GB 50.0-50.9% OOS, p=0.135; QuantConnect SPY GBM Sharpe -0.65). Folds report sections 1 (next-N GB/RF), 3 (triple-barrier + CUSUM direct classifier) and 14 (trend-scanning labels) into one module with `label_mode` and `events` switches, because they share features, model, and the null baseline. Its purpose in the loop: build and validate the F_base feature pipeline that spec 1 reuses, run once per instrument, log the null, stop. It also produces `p_up` as an optional feature for spec 1.

```
PARAMS: bar=5, label_mode='nextN' | 'triple' | 'trendscan', N=6, pt=1.5, sl=1.5, vert=30 (1-min bars), L_set=(6,12,24,36), events='all' | 'cusum',
  cusum_h_mult=3.0, model='rf' | 'logit' | 'lgbm', p_thr=0.58, stop_atr=1.0, train_months=24, retrain_every=1, embargo_days=1,
  n_trees=300, max_depth=4, min_leaf=200, first_entry='09:45', last_entry='15:15', flat='15:55', max_trades=3
FEATURES: F_base at each 5-min bar b (0.2). model='lgbm' adds nothing; it is LightGBM(n_estimators=300, max_depth=4, learning_rate=0.03, min_child_samples=200).
EVENTS: events='all': every 5-min bar close in the window. events='cusum': symmetric CUSUM on 1-min log closes within the session, S+ = max(0, S+ + y_t),
  S- = min(0, S- + y_t), event when max(S+, -S-) > h, h = cusum_h_mult * ATR1m_20 / C (report: ~ a 3-minute-vol move), reset after each event;
  decision bars are the 5-min bars containing an event.
LABELS (computed on hist, used only for training; the trade exits mirror them):
  nextN:     y = sign(C_{b+N} - O_{b+1}), 0 if |C_{b+N} - O_{b+1}| < cost_pts (same session; else no label)
  triple:    sigma = ATR5m_20_b; scan 1-min bars from B.i_next[b] for vert bars (or to 15:55): +1 if high >= O + pt*sigma first, -1 if low <= O - sl*sigma first,
             else sign(C_end - O) with 0 inside cost_pts
  trendscan: for L in L_set: OLS of C_{b+1..b+L} on 1..L; t_L = slope / se(slope); L* = argmax |t_L|; y = sign(slope_{L*}), sample weight |t_{L*}|
  Sample weights (triple, trendscan): weight x average uniqueness (overlapping label windows); RF max_samples = mean uniqueness.
MODEL per walk-forward month (0.3): drop training samples whose label window ends after first_session(m) - embargo_days (purge + embargo);
  fit on {y != 0}; p_up_b = P(y=+1 | X_b) on the OOS month.
SIGNAL at close of bar b (tod in window): long if p_up >= p_thr; short if p_up <= 1 - p_thr.
ENTRY: place(B.i_next[b], side, stop_pts = stop_atr*ATR5m_20_b, max_hold = N*5 (nextN) | vert (triple) | L*_modal*5 (trendscan));
  triple additionally sets tgt_pts = pt*sigma and stop_pts = sl*sigma (the barriers are the exits).
SESSION: set_session(first_entry, last_entry, flat); max_trades_day = max_trades; Lucid block.
```
Grid (32): `label_mode {nextN, triple}`, `N {6, 12}` (nextN) / `vert {30, 60}` (triple), `model {rf, logit}`, `p_thr {0.55, 0.60}`, `events {all, cusum}`. One extra run `label_mode=trendscan`, model rf. Fixed train 24 months, monthly refit.

Acceptance: the 0.5 gates. Expected outcome: fails them; record OOS accuracy and permutation p per fold in `results/<id>/README.md` as the family's negative control and do not re-run. Also report the feature-importance rank correlation between folds (the report found it unstable).

## 11. ml_statistical__knn_analog  (kNN analog forecasting on normalized bar windows; Lorentzian Classification as the negative-control mode)

Priority **1**, complexity **3**, instruments MNQ, MES, MGC; bar size 5-min RTH. EQ 1 (no credible OOS on ES/NQ/GC; Lorentzian: 0/96 backtests pass, mean t 0.52, p 0.62). numpy only (no sklearn needed), so it is a cheap experiment arm; `mode='lorentzian'` reproduces the TradingView defaults so the loop can show the null on our instruments and close the question.

```
PARAMS: mode='analog' | 'lorentzian', bar=5, lib_months=24, purge_bars=30, same_tod=True, k=50 (analog) | 8 (lorentzian), horizon=6 (analog) | 4 (lorentzian),
  conf=0.25, stop_atr=1.0, first_entry='10:30', last_entry='15:00', flat='15:55', max_trades=3, vol_filter=True, lc_min_votes=4
mode='analog':
  vector v_b = [ r_{b-11..b} / (ATR5m_20_b / C_b) ] (12 returns in ATR units) ++ [atr_ratio_b]; tod bucket = 30-min bucket of tod(b)
  library at month m: all bars of the trailing lib_months with a known horizon-bar forward return F = C_{b+horizon} - C_b (same session), excluding the last
  purge_bars bars before the decision; same_tod restricts neighbours to the same bucket.
  neighbours = k nearest by Euclidean distance; f = mean F (pts); disp = sd F.
  long if f > cost_pts + conf*disp/sqrt(k); short if f < -(cost_pts + conf*disp/sqrt(k)).
mode='lorentzian' (jdehorty defaults): features on 5-min bars F1 rsi(14), F2 WaveTrend(10,11) [ap=(H+L+C)/3; esa=EMA(ap,10); d=EMA(|ap-esa|,10);
  ci=(ap-esa)/(0.015 d); wt=EMA(ci,11)], F3 CCI(20) [(tp-SMA20(tp))/(0.015 x mean |tp-SMA20|)], F4 adx(20), F5 rsi(9); each min-max scaled on the library.
  label_hist = sign(C_{t+4} - C_t). Neighbours: every 4th bar back over the last 2000 bars (modulo-4 spacing), distance sum_i log(1 + |f_i - f_i,hist|),
  keep the k=8 nearest; pred = sum of their labels in [-8, 8]. long if pred >= lc_min_votes, short if pred <= -lc_min_votes.
  vol_filter: trade only if ATR5m(1) > ATR5m(10) (the script's "recent ATR > historical ATR"). Regime filter, kernel and EMA/SMA filters off.
ENTRY (both modes): place(B.i_next[b], side, stop_pts = stop_atr*ATR5m_20_b, max_hold = horizon*5).  SESSION: set_session(first_entry, last_entry, flat); max_trades.
```
Grid (16 per mode): analog `k {20, 50}`, `horizon {6, 12}`, `conf {0.25, 0.5}`, `same_tod {True, False}`; lorentzian `k {8}`, `lc_min_votes {1, 4}`, `vol_filter {True, False}`, `horizon {4, 8}`.

Acceptance: 0.5 gates; expected to fail. One pass per instrument, log, stop.

## 12. ml_statistical__vvg_day_classifier  (Volatility-(Volume)-Gap day state: fade / follow the open on classifier days; OHLC-only)

Priority **1**, complexity **2**, instruments MNQ (published), MES; bar size 1-min for the state, 5-min ATR. EQ 2 (state is real: 77.6% of classifier days reverse from the intraday peak; no directional rule stable: reversal +13.49 pts T=1.26 N=35 with 2025 -22.76; continuation T=-1.64; "a research asset, not an operational signal"). Fires ~4.4% of sessions (~10/yr), far below the 30-trades-per-fold gate, so the main deliverable is the `vvg_day` feature for spec 1.

Data gap: first-5-min-bar volume replaced by first-5-min-bar range relative to its 20-session mean (flagged; `use_range_cond=False` drops the condition, leaving a gap x opening-move classifier).

```
PARAMS: mode='reversal' | 'continuation' | 'close_fade', q=0.67, use_range_cond=True | False, hold_min=65, stop_atr=1.5, min_hist=120, flat='15:55'
STATE at 10:00 of session d (prior-session information plus 09:30-09:59 bars):
  g_d = |O930 - prev_close| / ATR14d;  m_d = |C(09:59) - O930| / ATR14d;  a_d = (H-L of 09:30-09:34) / mean over the prior 20 sessions of the same range
  each compared with the q-quantile of its own values over sessions < d (expanding, NaN until min_hist sessions)
  vvg_day[d] = g_d >= Q_g and m_d >= Q_m and (a_d >= Q_a or not use_range_cond)
ENTRY on vvg_day:
  reversal:     at bar tod 10:00, side = -sign(C(09:59) - O930), market; stop_pts = stop_atr*ATR5m_20; max_hold = hold_min
  continuation: same, side = +sign(...)
  close_fade:   at bar tod 15:30, side = -sign(C(15:29) - O930), market; stop_pts = 1.0*ATR5m_20; flat 15:55
SESSION: reversal/continuation set_session('10:00','10:01', flat); close_fade set_session('15:30','15:31', flat); max_trades_day 1; Lucid block.
```
Grid (16): `mode {reversal, continuation, close_fade}` (x) `q {0.67, 0.75}` (x) `use_range_cond {True, False}`, `hold_min {65, 120}` for the 10:00 modes only.

Acceptance: pooled 2011-2026 (the only way to reach N >= 30 per fold is to use the full history) T >= 2 and same sign in the 2023-2026 folds; otherwise keep `vvg_day` as a feature and drop the module.

---

## Dropped or folded (and why)

| Report section | Decision |
|---|---|
| 1. GB/RF next-N-bar direction classifier | Specced as the `label_mode='nextN'` arm of spec 10 (negative control). Priority 1 because the best-controlled test on our instrument and window is null. |
| 3. Triple-barrier + CUSUM direct classifier | Folded into spec 10 (`label_mode='triple'`, `events='cusum'`); shares features, model and the null baseline. |
| 14. Trend-scanning labels | Folded into spec 10 (`label_mode='trendscan'`). |
| 11. Lorentzian Classification | Folded into spec 11 (`mode='lorentzian'`) as the negative control with the TradingView defaults; 0/96 independent backtests pass. |
| 12. LSTM / transformer sequence models | **Dropped.** Documented OOS failure at this data scale (MNQ p=0.515; ~250 session labels/yr vs tens of thousands needed), no torch/tensorflow installed, and nothing in the report suggests a configuration that would differ. The loop must not spend time here. |
| 9. ES-NQ intraday statistical-arbitrage spread | **Dropped.** The engine runs one instrument and one position per run, so a two-leg hedged spread cannot be simulated; even if it could, the report rates it poor (cointegration persists ~40% period to period, two legs of cost, the 20-micro funded cap split across legs, spread trends on rotation days). Its only defensible descendant, a one-leg ES-confirms-NQ relative-strength filter, belongs to the mean-reversion family's specs. |
| 16. Probability-to-size bet sizing | Not a strategy and not implementable per trade in the engine (fixed contract per run). Replaced by `p_thr` in specs 1/10 and by the daily multiplier of specs 4/5 (section 0.6). |
| 17. Validation protocol | Not a strategy; it is section 0.5 and binds every spec above. |
| 6. (second half) IOHMM side information | Omitted from spec 8 until the plain HMM passes; the paper's plain HMM already had the headline Sharpe. |
| Volume features in 1, 6, 13 | Replaced by the `act_z` range-activity stand-in (section 0.2) where the feature was one of several; where volume was the gate (RTH Confluence) the grid includes removing the gate. No spec depends on volume to exist. |

## Portfolio notes for the backtest agents

- Order of work: specs 4 and 5 first (overlays; they improve whichever primaries the other families produce and need no new edge), then spec 1 on the best 2-3 stateless primaries, then spec 2 (an independent 03:00-08:30 leg that stacks with any RTH leg without overlapping windows). Specs 3, 6, 7, 8, 9 are one grid pass each; specs 10-12 are one pass per instrument, logged as negative controls.
- Session stacking: spec 2 (03:00-08:30) + any RTH leg on the same contract do not overlap, but the engine runs one strategy per module; combine in `backtest.portfolio` / `portfolio_opt` with `micros` per leg, and remember that both legs' P&L fall in the same Lucid session (EOD trailing and consistency math).
- Consistency arithmetic for the meta-labelled primaries: the filter removes trades, so the Lucid scan usually moves to more micros; keep `daily_profit_stop` at 1.0x block so the largest day stays below 50% of $3,000 at the chosen size.
- Every ML spec must log its configuration count; the deflated-Sharpe gate in 0.5 is meaningless without it. Reuse the same feature pipeline (`strategies/ml_features.py`, new file) across specs 1, 10, 11 so the walk-forward and purge logic is written once.
- Never report an ML spec from a single walk-forward run; the 2023 and 2024 folds are the hold-out that decides whether the 2025-2026 result is selection.

---

## Appendix A. numpy fallbacks (used when sklearn / hmmlearn are unavailable)

A1. GMM (EM, full covariance), X (n x p) standardized:
```
init: k-means++ style: pick K rows as means, cov_k = cov(X), pi_k = 1/K;  repeat 200 times or until loglik change < 1e-6:
  E: log r_nk = log pi_k + log N(x_n; mu_k, S_k) (scipy.stats.multivariate_normal.logpdf, allow_singular with 1e-6 ridge); r = softmax over k
  M: N_k = sum_n r_nk; pi_k = N_k/n; mu_k = sum_n r_nk x_n / N_k; S_k = sum_n r_nk (x_n-mu_k)(x_n-mu_k)' / N_k + 1e-6 I
5 random restarts, keep the best loglik. predict = argmax_k r_nk.
```
A2. Gaussian HMM (K states, emissions N(mu_k, S_k)), forward filter and Baum-Welch:
```
forward (filter): alpha_1 = pi * b_1; for t>1: alpha_t = (A' alpha_{t-1}) * b_t; c_t = sum(alpha_t); alpha_t /= c_t; loglik = sum log c_t;  filtered P = alpha_t
backward: beta_T = 1; beta_t = A (b_{t+1} * beta_{t+1}) / c_{t+1}
Baum-Welch: gamma_t = alpha_t * beta_t (normalize); xi_t(i,j) = alpha_t(i) A_ij b_{t+1}(j) beta_{t+1}(j) / c_{t+1};
  pi = gamma_1; A_ij = sum_t xi_t(i,j) / sum_t gamma_t(i); mu_k, S_k = gamma-weighted mean and covariance (+1e-6 I); 200 iterations or loglik change < 1e-6; 3 restarts.
stationary distribution = left eigenvector of A with eigenvalue 1, normalized.
```
A3. Kalman local linear trend: as written in spec 6 (predict: x=Fx, P=FPF'+Q; update: S=HPH'+R, K=PH'/S, x+=K(y-Hx), P=(I-KH)P).

A4. Logistic regression (IRLS, L2): standardize X, add intercept; w=0; repeat 25 times: p = sigmoid(Xw); W = p(1-p); w = solve(X'WX + lambda I, X'W(Xw + (y-p)/W)); lambda = 1.0 on standardized features.
