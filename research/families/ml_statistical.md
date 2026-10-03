# Family: Machine learning and statistical modeling on intraday OHLC bars

Scope: gradient boosting / random forest on engineered bar features, meta-labeling and triple-barrier (Lopez de Prado), HMM/GMM regime switching, Hurst-exponent regime filter, Kalman trend estimators, ES-NQ cointegration/pairs, kNN/analog pattern matching, Lorentzian Classification (TradingView), LSTM/transformer claims, walk-forward validation practice, and the feature sets that have (and have not) shown out-of-sample value on ES/NQ.

Target: Lucid Trading 50K LucidFlex (eval target $3,000, $2,000 EOD-trailing drawdown, 50% consistency rule, 4 minis / 40 micros in eval, 2 minis / 20 micros at funded start, no overnight). Backtest data: 1-minute OHLC (no volume) for ES/MES, NQ/MNQ, GC/MGC proxies, Nov 2010 to Sep 2026; prime window 2025-01 to 2026-09. All times ET.

Method note: this sweep ran 6 web searches before the session's search budget was exhausted, then fetched and text-extracted 14 primary pages/PDFs (three 2026 arXiv papers on MNQ, the Hudson & Thames meta-labeling paper, the Cambridge HMM paper, Krauss et al. 2017 and Fischer & Krauss 2018 via econstor, the LSEG regime-detection study, QuantConnect strategy-library pages, TradeSearcher's Lorentzian aggregate, the TradingView Lorentzian page, LuxAlgo's Hurst guide, StockSharp's Hurst strategy, the Delmastro HMM repo, the Elite Trader ES/NQ thread, Quantitativo's ES/NQ intraday momentum). Where a source was unreachable (QuantStart Kalman pages returned 502, SSRN returned 403), the standard textbook formulation (Chan 2013; Lopez de Prado 2018) is given and labeled as such.

---

## 0. Executive summary

1. **The honest headline for this family is negative.** The best-controlled 2026 evidence on exactly our instrument class and window (MNQ, 5-minute bars, Dec 2021 to Sep 2025, expanding-window walk-forward with permutation tests) finds that gradient boosting and LSTM models built on OHLCV bar features predict rest-of-session direction at **50.00% to 50.89% out-of-sample versus a 51.8% base rate**, with permutation p-values of 0.135 (best GB) and 0.515 (LSTM), and feature importances that reshuffle every fold (Mesfin 2026, arXiv:2605.17724). A companion study of 14 OHLCV momentum-signal families on the same data found **none** cleared a five-gate validation after a 2.0-point MNQ round-trip friction (arXiv:2605.04004). Lorentzian Classification, the most popular "ML" indicator on TradingView, shows **0 of 96 backtests passing a quality gate, mean t-stat 0.52, p = 0.62** on an independent aggregator.

2. **What does survive is not "predict the next bar", it is "classify the state, then use a simple rule."** The two signals that passed the strict MNQ protocol are both **Gaussian-mixture regime-transition** signals with 60 to 75 minute holds (London Session Signal B: walk-forward OOS N = 247, mean net +4.09 pts/trade, T = 4.30, p = 0.000025, 61.5% win; RTH Confluence: OOS N = 196, +11.82 pts, T = 3.11). Both need volume z-scores (we have no volume) and both come from a single independent author with acknowledged selection exposure (53+ parameter combinations). They are the most credible ML leads in the family and should be reproduced with the volume feature dropped.

3. **Meta-labeling has the best peer-adjacent evidence for a prop account**, precisely because it does not try to forecast; it filters an existing rule's trades. On ES e-mini dollar bars, Hudson & Thames (Singh & Joubert 2019/2022) report OOS (Jan 2018 to Jan 2019) Sharpe moving from 0.47 to 1.31 and max drawdown from -28.2% to -6.5% for a Bollinger primary, and Sharpe 0.69 to 0.95 for an SMA-crossover primary. Fewer, better trades and a shallower drawdown is exactly what a $2,000 trailing-drawdown account needs. The primary models to meta-label should come from the ORB and intraday-momentum families (the Zarattini/Quantitativo noise-band model is positive every year since 2018 on ES/NQ).

4. **Daily-frequency HMM regime detection is reliable at the one job it is good at**, flagging crash/high-vol states (LSEG on ES futures 1997 to 2023; Delmastro 2018 to 2023, 2-regime Sharpe 0.76 vs SPY 0.56) and should be used as a **gate/sizer**, not as an intraday signal. The intraday HMM (Christensen, Turner & Godsill, Cambridge) reports pre-cost Sharpe above 2 on 1-minute ES but for one year (2011) only, with costs removing roughly 15%, and no OOS beyond that year.

5. **Hurst and Kalman** are useful feature/filters, not standalone edges. MNQ's 5-minute Hurst is about 0.59 (persistent) on 2021 to 2025 data while MGC is nearer 0.5, which argues for trend/breakout logic on NQ and against mean-reversion logic on gold at 5-minute scale. The most promising Kalman use is Mesfin's gap-continuation short (Kalman velocity on 1-minute bars in the first 30 minutes, z > 2.5): net +14.52 pts/trade, but only 35 OOS trades and 2024 negative, so it is a near-miss worth re-testing on our 16 years.

6. **ES-NQ pairs are a poor fit for this account**: the spread's intraday cointegration is unstable (persistence about 40% period-to-period in the QuantConnect study), practitioners report intraday ES/NQ "too much noise", and a hedged pair burns two legs of commission and margin against a 2-mini funded cap.

7. **Validation discipline is the family's real contribution.** Any ML candidate must pass: expanding-window walk-forward with at least 3 OOS years (2023, 2024, 2025/26), net-of-cost T >= 2 on OOS trades, >= 30 trades per fold, same sign every OOS year, and a permutation test. Anything that fails this will fail the eval.

---

## 1. Gradient boosting / random forest direction classifier on engineered OHLC features

**Origin.** Generic; canonical implementations in Jansen, *Machine Learning for Trading* (stefan-jansen/machine-learning-for-trading), QuantConnect "Gradient Boosting Model" (SPY, minute bars), and the Mesfin 2026 MNQ study, which is the cleanest test on our instrument.

**Objective rules (standard interpretation).**
- Bars: 5-minute RTH (09:30 to 16:00 ET) built from 1-minute data. Decision at bar close, fill at next bar open.
- Features (all computed from bars strictly before the decision bar): returns of last 1, 2, 3, 6, 12 bars; cumulative return since 09:30; overnight gap (09:30 open vs prior 16:00 close, divided by 20-day ATR); 20-bar ATR / 20-day average ATR (ATR ratio); close position within bar range ((C-L)/(H-L)) for last 3 bars; range of last 12 bars / 20-day ATR; minutes since open; day of week; prior-day return and prior-day range ratio; 10- and 20-day realized vol; distance from session TWAP (volume-free VWAP proxy) in ATR units.
- Label: sign of return from next bar open to N bars ahead (N = 3, 6 or 12 for 15/30/60 minutes), with a dead zone: label 0 if |return| < round-trip cost (MNQ 2.0 pts; MES 0.75 pts; MGC 0.5 pts).
- Model: LightGBM, 200 to 500 trees, depth 3 to 4, learning rate 0.03, min 200 samples per leaf, class-balanced; or RandomForest with max_samples set to average label uniqueness (Lopez de Prado ch. 4).
- Training: expanding window, retrain monthly, minimum 12 months of history; purge overlapping labels and 1-day embargo.
- Entry: long when P(up) > 0.58, short when P(down) > 0.58 (tune threshold on training data only); at most one position; no entries after 15:15 ET.
- Exit: N bars after entry, or stop 1.0 x 20-bar ATR, or 15:55 ET, whichever first.

**Parameters.** N in {3, 6, 12}; probability threshold 0.55 to 0.62; stop 1.0 ATR.

**Evidence.**
- Mesfin 2026 (arXiv:2605.17724), MNQ 5-min, 944 days Dec 2021 to Sep 2025, target "close > 10:30 open + 10 pts": GB-Daily 50.00% combined OOS accuracy (fold accuracies 53.31 / 45.60 / 51.48); GB-Intraday 50.00 to 50.89% (49.81 / 48.19 / 54.76), permutation p = 0.135 on the best fold against shuffled mean 50.04% (sd 3.99%); GB-VolAdj p = 0.390. Feature importance unstable: top feature atr_ratio (2023), bar_ret_6 (2024), bar_ret_10 (2025). Only bar_ret_2 (09:35 to 09:40 return) was top-5 in all folds.
- QuantConnect Gradient Boosting Model: SPY minute bars, 20 stumps, 4-week training, 10-minute hold, trade when predicted return > 0.05% cost: Sharpe -0.649 vs SPY 0.691 over 9/2015 to 9/2020.
- Krauss, Do & Huck 2017 (daily, cross-sectional S&P 500 stocks, 1992 to 2015): RF/GBT/DNN ensemble 0.45%/day before costs, 0.25% after; after-cost Sharpe RF 1.90, GBT 1.23, DNN 0.55; returns "declining in recent years". Not transferable to a single futures contract but shows RF beating GBT and DNN on noisy financial labels.
- Dixon et al. 2015 (5-minute futures, cited in Krauss) claimed 73% classification accuracy but without a trading P&L or costs; treat as not reproduced.

**Evidence quality: 2** (multiple independent tests; nearly all of them null or negative for single-instrument intraday).

**Prop-fit.** Poor as a standalone. If it is built, it must be as a filter on a rule-based primary (see section 2). Day-trade-only and OHLC-only are satisfied.

**Data requirements.** OHLC only (volume z-score features must be dropped). The MNQ study used volume as a feature in 1 of 30 intraday features; dropping it changes nothing material.

---

## 2. Meta-labeling a rule-based primary with triple-barrier labels (Lopez de Prado)

**Origin.** Lopez de Prado, *Advances in Financial Machine Learning* (2018), ch. 3; Hudson & Thames, "Does Meta-Labeling Add to Signal Efficacy?" (Singh & Joubert, 2019; PDF 2022), tested on S&P 500 e-mini futures.

**Objective rules.**
- Primary model: any deterministic rule that produces side (+1/-1) and timestamp. Hudson & Thames tested (a) Bollinger mean reversion, 1.5 sd bands on close, buy at/below lower band, sell at/above upper band; (b) SMA 20/50 crossover. For a prop account the primaries to use are the ones with the best stand-alone evidence in the other families: the noise-band intraday momentum model (Quantitativo/Zarattini: 14- or 90-day noise area, enter on exit from the band, trail on the band, flat at close; ES Sharpe 1.25, NQ 1.67 since 2010, positive every year since 2018) and the 09:30 to 09:55 ORB long with 75-minute hold (Mesfin: +2.82 pts net, T = 0.88, positive in 2023, 2024 and 2025).
- Event sampling: symmetric CUSUM filter on log price, S+ = max(0, S+ + y_t - E[y_t]), S- = min(0, ...), event when max(S+, -S-) > h with h = point-in-time daily volatility (EWMA span 100 bars). Apply only to the primary's signals (the filter prevents repeated triggers while price hovers at a threshold).
- Triple barrier on each primary signal: upper = entry + pt x sigma, lower = entry - sl x sigma, vertical = min(N bars, 15:55 ET). Hudson & Thames: pt = sl = 1 daily sd, vertical = 1 day. For intraday use: sigma = 20-bar ATR, pt = 2, sl = 1, vertical = 12 bars (60 minutes).
- Meta label: 1 if the primary's trade hit the profit barrier (or ended positive at vertical), else 0.
- Secondary model: RandomForest (Hudson & Thames: grid-searched, balanced by up-sampling positives; recommended: 500 trees, max_depth 5, min_samples_leaf 100, max_samples = average uniqueness). Features: RSI(14), 10- and 20-day vol, 7- and 15-bar MAs relative to price, 1 to 5 day autocorrelation, 1 to 5 day momentum (their set); add ATR ratio, gap/ATR, minutes since open, prior-day range ratio, Hurst(100-bar) and daily HMM state (sections 5, 7).
- Execution: take the primary's trade only when P(meta = 1) > 0.5 (or > 0.55 for fewer, better trades). Size by Lopez de Prado ch. 10: z = (p - 0.5)/sqrt(p(1-p)), m = 2 Phi(z) - 1, discretized to 1 to 3 micros per $10k.
- Validation: purged k-fold with embargo on the training set, then one locked walk-forward OOS run.

**Evidence.**
- Hudson & Thames, ES e-mini dollar bars (dollar bars had Jarque-Bera 143,045 vs 1,782,853 for time bars). Bollinger primary OOS 2018-01-04 to 2019-01-28: accuracy 17% to 63%, precision 0.17 to 0.20, Sharpe 0.47 to 1.31, max DD -28.2% to -6.5%. SMA primary OOS 2018-01-18 to 2019-01-31: accuracy 48% to 55%, precision 0.48 to 0.54, Sharpe 0.69 to 0.95 ("outperforms on a risk-adjusted basis" but not all metrics).
- Lopez de Prado reports (book, and "meta-labeling lifts precision and raw profit factor in 38/42 instruments" in follow-up work cited by search results) that the method's main effect is drawdown reduction, not return increase. One year of OOS and a single team; no ES-specific independent replication found.

**Evidence quality: 3.**

**Prop-fit.** Best in family. Trades fewer, keeps the primary's day-trade structure, and the drawdown reduction is the key eval property. Risk: the secondary model is retrained on the primary's own trade history, so it needs several hundred primary trades before it has signal (the noise-band model on NQ produces roughly 150 to 200 trades/year; ORB produces about 150/year).

**Data requirements.** OHLC only. Dollar bars cannot be built without volume; use time bars (the paper's result is on dollar bars, so expect weaker meta-model accuracy on time bars).

---

## 3. Triple-barrier labeled direct classifier with CUSUM event sampling (ML as primary)

**Origin.** Lopez de Prado 2018 ch. 2 to 3; blackarbs "Labeling and Meta-Labeling Returns for ML Prediction"; crypto/Korean replications (Springer 2025, arXiv:2504.02249) found triple-barrier labels beat next-bar labels.

**Objective rules.**
- Events: CUSUM on 1-minute log close, h = 0.5 x 20-day daily sd scaled to intraday (h = daily_sd x sqrt(1/390) x 3, i.e. roughly a 3-minute-vol move); only 09:35 to 15:15 ET.
- Labels at each event: triple barrier with pt = sl = 1.5 x 20-bar ATR, vertical = 30 bars; label = +1/-1 on barrier touch, sign(return) at vertical (0 if within cost).
- Features as in section 1 plus fractionally differentiated close (d chosen as smallest d with ADF p < 0.05 on the training window; typically 0.3 to 0.5) and the Hurst(100) reading.
- Model: RF with max_samples = average uniqueness, sample weights by return attribution x uniqueness, time-decay 0.5 over the training window.
- Trade: side = argmax class if P > 0.55; exit on the same barriers used for labeling, or 15:55 ET.
- Validation: purged 5-fold CV with 1-day embargo for hyperparameters; expanding walk-forward for the reported result.

**Evidence.** No credible OOS result on ES/NQ/GC. The replications are on crypto and Korean equities; the MNQ 2026 null results (section 1) apply directly since the only difference is the label.

**Evidence quality: 2.**

**Prop-fit.** Poor until proven; include only as an experiment arm of the backtest loop. Costs dominate: on MNQ the 2.0-point friction floor exceeded the gross edge of 11 of 14 OHLCV signal families.

**Data requirements.** OHLC only.

---

## 4. HMM intraday momentum on 1-minute ES (Christensen, Turner & Godsill)

**Origin.** "Hidden Markov Models Applied To Intraday Momentum Trading With Side Information", Cambridge Signal Processing Lab, arXiv:2006.08307 (work done 2012, posted 2020).

**Objective rules.**
- Data: 1-minute ES, 01:00 to 15:15 Chicago time (02:00 to 16:15 ET), front month rolled 12 days before expiry.
- Model: HMM whose latent state is the trend (drift) with K = 2 or 3 states, Gaussian emissions on 1-minute log returns; emission means for K = 3 estimated by Baum-Welch at mu = [-0.0198, -0.0057, +0.0183] (units: ticks-scaled returns). Learn parameters on the prior half-year; infer online with the forward algorithm.
- Signal at t: expected trend = sum_k P(state k | returns up to t) x mu_k; position = sign(expected trend), lagged one bar (no look-ahead). Side information (IOHMM): ratio of realized vol (fast window 50 / slow window, spline-fitted) and intraday seasonality spline enter the transition matrix.
- Position always on during the session (long or short); for prop use, flat 15:55 ET and no entry 09:28 to 09:33 ET.

**Evidence.** 2011 only (258 days, 856 bars/day). Pre-cost annualized Sharpe above 2.0 for Baum-Welch HMM and IOHMM variants; MCMC-estimated variant failed to beat long-only (long-only Sharpe 0.4 that year). Costs reduce Sharpe about 15% (authors' estimate). IOHMM beats plain HMM by over 10%. No test of other years; parameters learned on H2 2010.

**Evidence quality: 2** (peer-quality methodology, single year, pre-cost headline).

**Prop-fit.** Weak: an always-in 1-minute flip strategy generates many trades per day; at 0.5 tick slippage per side on MES ($0.625 per round trip per micro plus about $1.00 commission) the 2011 edge is unlikely to survive 2025 conditions. Worth testing as a 5-minute variant with a probability dead zone (flat when |expected trend| < threshold).

**Data requirements.** OHLC only (close-to-close returns). Globex-session bars for the 02:00 to 09:30 ET portion if replicated exactly.

---

## 5. Daily HMM regime gate (2-state Gaussian HMM on returns and volatility)

**Origin.** LSEG Developer Portal "Market regime detection using statistical and ML based approaches" (ES futures ESc1 1997 to 2023; HMM vs GMM vs agglomerative clustering); Delmastro, Regime-Switching-HMM-Factor-Investing (GitHub, 2018 to 2023); Wang, Lin & Mikkelsen 2020, *J. Risk Financial Manag.* 13(12):311.

**Objective rules.**
- Inputs: daily ES (or NQ) log return and 10-day rolling realized vol (Delmastro) or log return of the 7-day MA of closes (LSEG).
- Model: Gaussian HMM, 2 states (3 adds a "neutral" state that hurt: 3-regime Sharpe 0.66 vs 2-regime 0.76). Re-estimate daily on a rolling window of 2,707 trading days (about 10.7 years), using data through the prior close only; decode with the filtered (not smoothed) probability of the last day.
- Mapping: state with the higher mean / lower vol = "normal" (allow longs, full size); state with higher vol = "stress" (allow shorts only, or halve size, or stand aside). For our purpose: use P(stress) to (a) halve micro count when > 0.5, (b) disable mean-reversion primaries and enable trend primaries when > 0.7.
- Signal lag: regime shift detection lags by several days (LSEG); never act on same-day smoothed states.

**Evidence.**
- Delmastro (Jan 2018 to Dec 2023): 2-regime 16.5% CAGR, 20.2% vol, Sharpe 0.76, MDD -24.5% vs SPY 12.0%, 20.4%, 0.56, -33.7%; 62% of time invested, 38% cash. No costs (few trades, so immaterial).
- LSEG (ES 1997 to Feb 2023): HMM best state continuity; long in normal / short in crash beats buy-and-hold by sidestepping 2008 and shorting 2020; lagged in 2022; "out-of-sample results proved significantly worse than in-sample"; no costs.
- Wang et al. 2020: OOS Sep 2017 to Apr 2020, regime-switched factor portfolio beat each single factor model.

**Evidence quality: 3** for regime identification; 2 for incremental P&L in an intraday system.

**Prop-fit.** Good as an overlay. It converts the eval's biggest risk (a trending-vol regime that destroys a mean-reversion rule) into a sizing decision. Zero extra trades.

**Data requirements.** Daily OHLC (Yahoo ES/NQ futures). VIX can replace the vol feature.

---

## 6. GMM regime-transition signals on MNQ (Mesfin "London Session Signal B" and "RTH Confluence")

**Origin.** Mesfin 2026, arXiv:2605.04004 sections 5 and Appendix A (positive controls); companion arXiv:2605.11423.

**Objective rules, London Session Signal B.**
- Bars: 15-minute, 03:00 to 08:30 ET (London session), MNQ.
- Features (5), each rolling z-scored then StandardScaler'd on the training fold: ATR ratio (20-bar ATR / baseline), volume z-score (50-bar), close position within bar range, 15-minute return, directional consistency (fraction of last n bars with same sign).
- GMM with 3 components, refit at each walk-forward fold on training data only; components mapped to Regime 0 "Bearish Chop", Regime 1 "Extreme Volatility", Regime 2 "Bullish Drift" by a two-step heuristic on vol z-score and directional consistency.
- Entry: long at the next 15-minute bar open after a clean R0 to R2 transition (no R1 in the prior 2 bars).
- Exit: 60 minutes after entry, or 08:30 ET, whichever first. Stop 20 points fixed. Friction 2.0 pts round trip.

**Objective rules, RTH Confluence.**
- Bars: 5-minute RTH. GMM 3 components, 4 features (ATR ratio = 20-bar ATR computed on 1-minute bars / 10.34 baseline, 50-bar volume z-score, close position, 5-minute return). Fit once on 2022.
- Fire when regime = 1 (Active Flow), rolling 200-bar first-order transition probability P(1 to 2) > 0.15, and volume z > 0.5.
- Entry: limit at signal close minus 25 x ATR_ratio points (ATR_ratio capped [0.5, 2.0]) within 6 bars; cancel if not filled. Exit at bar 13 from the signal bar or RTH close. Stop 80 x ATR_ratio points.

**Evidence.**
- London B walk-forward OOS: N = 247, mean net +4.09 pts (sd 14.97), T = 4.30, p = 0.000025, win 61.54%, per-trade Sharpe 0.27, bootstrap P(mean > 2.0 pts) = 98.9%, parameter sensitivity T = 3.87 to 4.83. A 1-bar (15-minute) entry delay flips T to -2.78: the edge is consumed inside the first post-transition bar.
- RTH Confluence walk-forward OOS: N = 196, +11.82 pts (sd 53.8), T = 3.11, p < 0.001; in-sample 2022 to 2024 N = 538, +15.77 pts, 61.0% win; unconditional long benchmark -2.60 pts, T = -0.75. Author discloses 53+ parameter combinations across 7 parameters, a contaminated first OOS fold, and a globally fixed ATR baseline.
- External replications failed until the 1-minute ATR detail was disclosed; none has been published as successful.

**Evidence quality: 3** (rigorous protocol, single author, selection exposure acknowledged, no independent confirmation).

**Prop-fit.** London B is attractive on paper: one trade per session at most, 60-minute hold, 61% win, flat before RTH. At 20 micros, +4.09 pts x $2 x 20 = +$164 expected per trade with sd about $600; on a $2,000 trailing drawdown that is a tolerable but not safe risk profile (a 20-point stop x 20 micros = $800). RTH Confluence's 80 x ATR_ratio stop is too wide for the account at more than 5 micros.

**Data requirements.** Volume z-score is a feature in both GMMs (flag). It can be replaced by a range-based activity proxy (bar range / 20-bar ATR), which the author's own "ATR ratio" feature already captures; expect some loss. London B needs Globex-session 1-minute bars (03:00 to 08:30 ET).

---

## 7. Hurst-exponent regime filter (trend vs mean-reversion switch)

**Origin.** Mandelbrot/Peters R/S analysis; QuantStart "Basics of Statistical Mean Reversion Testing" (variance-of-lagged-differences estimator); LuxAlgo Hurst concept guide; StockSharp "Hurst Exponent Reversion" and "Hurst Exponent Volatility Filter" strategies; TradingView "Hurst Exponent Strategy" scripts.

**Objective rules.**
- Estimator: variance-ratio / generalized Hurst on log close: for lags tau in 2..20 compute sd of (p_t - p_{t-tau}); H = slope of log(sd) vs log(tau). Window 100 to 390 bars of 1-minute closes (one session) or 100 bars of 5-minute; smooth with a 10-bar EMA (LuxAlgo: raw rolling H "jumps bar to bar" and a 100-bar window is "an extremely noisy object").
- Thresholds: H > 0.55 trend regime, H < 0.45 mean-reversion regime, otherwise flat (LuxAlgo zones; StockSharp uses 0.5 with a 100-candle window).
- Trend branch: breakout of the 20-bar high/low with 1 x ATR stop and 15:55 ET exit (or hand off to the ORB primary).
- Mean-reversion branch (StockSharp): long if H < 0.5 and close < MA(20); short if H < 0.5 and close > MA(20); exit at the MA or when H > 0.5; stop 2%.
- Prop use: a feature/gate for sections 2 and 5, not a standalone system.

**Evidence.** StockSharp claims about 121% (reversion) and about 163% (vol filter) average annual returns on crypto, undated, no drawdown: anecdote. Mesfin 2026 measured MNQ 5-minute H about 0.59 and MGC nearer 0.5 (2021 to 2025) and found OU mean reversion on MGC negative in every configuration (T = -1.63 to -5.32 on 1,172 to 3,059 OOS trades), consistent with "H near 0.5 means do not fade". No peer-reviewed intraday ES/NQ Hurst-switching backtest found.

**Evidence quality: 2.**

**Prop-fit.** Neutral; cheap to compute, adds no trades. Its main value is to turn off mean-reversion primaries on NQ (persistent at 5-minute scale) and to flag days where H collapses toward 0.5.

**Data requirements.** OHLC only.

---

## 8. Kalman-filter trend / velocity estimator (incl. gap-continuation short)

**Origin.** Local-linear-trend Kalman filter (Harvey); Mesfin 2026 "gap continuation short (Kalman v > 2.5)" (the most credible near-miss in the MNQ study); Kalman-smoothed moving-average crossovers common in practitioner code.

**Objective rules, gap-continuation short.**
- At 09:30 ET compute the overnight gap (09:30 open vs prior 16:00 close). Run a 2-state Kalman filter (level, velocity) on 1-minute closes from 09:30 to 10:00 with transition noise q = 1e-5 x price^2 and observation noise r = (1-minute ATR)^2 (standard choice; the paper gives no numbers).
- Standardize the 10:00 velocity by its expanding-window sd; if gap < 0 and velocity z < -2.5 (continuation of a down gap), short at 10:00 next bar open. The paper used "v > 2.5" as the top 0.62% of |z|.
- Exit: 15 x 5-minute bars (75 minutes) or 15:55 ET; stop 1.5 x 20-bar ATR.
- Long mirror was not reported as positive; test but expect asymmetry.

**Objective rules, Kalman adaptive trend (generic).**
- State x = [level, slope]; prediction level_t = level_{t-1} + slope_{t-1}; Kalman gain from q/r ratio (q/r = 1e-4 behaves like a 20 to 30 bar EMA on 5-minute bars).
- Long when slope > +k x sqrt(P_slope) with k = 2, short when < -2 x sqrt(P_slope); flat otherwise; exits on sign change or 15:55 ET.

**Evidence.** Gap continuation short: 35 OOS trades total (about 12/fold), gross +16.53 pts, net +14.52 pts, T = 1.46, by year +14.53 (2023), -11.87 (2024), +10.27 (2025 partial). Fails trade-count and year-stability gates. Author recommends extending to 2019+ data to triple the sample, which our 2010+ data allows. Generic Kalman trend following has no published OOS ES intraday result; it is a smoother, so it inherits the momentum family's evidence.

**Evidence quality: 2.**

**Prop-fit.** Rare-event signal (about 1 trade per month) with large per-trade edge: good for the consistency rule only if combined with a daily base strategy; stand-alone it cannot produce the 5 x $150 payout days.

**Data requirements.** OHLC only; prior-session close for the gap.

---

## 9. ES-NQ intraday statistical-arbitrage spread (rolling OLS / Kalman hedge, z-score bands)

**Origin.** QuantConnect "Intraday Dynamic Pairs Trading Using Correlation and Cointegration Approach" (bank stocks, 10-minute bars, 2013); Chan, *Algorithmic Trading* (2013) ch. 3 Kalman hedge (EWA/EWC, delta = 1e-4, Ve = 1e-3); QuantStart Kalman pairs articles (unreachable this session); Elite Trader "Pair trading ES/NQ" thread.

**Objective rules (standard interpretation).**
- Legs: MES and MNQ 1-minute closes; hedge ratio beta from (a) rolling 390-bar OLS of log(MNQ) on log(MES), or (b) Kalman with state [intercept, beta], transition cov delta/(1-delta) x I with delta = 1e-4, observation var Ve = 1e-3 (Chan).
- Spread e_t = log(MNQ_t) - (alpha + beta x log(MES_t)); z = e_t / rolling 120-bar sd (OLS) or e_t / sqrt(Q_t) (Kalman).
- Gate: Engle-Granger ADF on the trailing 20 sessions' 5-minute spread, p <= 0.05, re-tested daily (QuantConnect uses 3-month lookback, correlation >= 0.9 and ADF p <= 0.05).
- Entry: z > +2.33 short MNQ / long MES in dollar-neutral ratio (1 MNQ to about 2 MES notional currently about $45k vs $30k, so 2 MNQ : 3 MES); z < -2.33 opposite. Exit |z| < 0.5; stop |z| > 4.0; flat 15:55 ET. QuantConnect: entry 2.33, exit 0.5, stop 4.0.
- No trades 09:30 to 09:45 ET and 15:45 to 16:00 ET.

**Evidence.** QuantConnect's result (26.9% annual return, Sharpe 3.0, beta 0.23) is on 20 bank stocks over Sep to Nov 2013 only. The same tutorial reports high correlation persisting only about 50% and cointegration only about 40% between adjacent periods. Springer *Comput. Econ.* 2023 (Chen et al.) finds a large share of intraday spread processes fail to converge to the sample mean. Elite Trader practitioners: ES/NQ "too much noise" intraday, 60-minute charts gave modest signals, $130 to $510 per intraday trade vs $1,380 to $3,660 on daily holds. No published ES/NQ intraday OOS Sharpe found.

**Evidence quality: 2.**

**Prop-fit.** Poor. Two legs of commission and slippage, the 20-micro funded cap splits across legs, and the spread trends intraday on index-rotation days (exactly the days that breach a $2,000 drawdown). The one defensible use is a 1-leg version: trade NQ in the direction of the ES-NQ spread's z-score reversal only when ES confirms (relative-strength filter), which belongs to the mean-reversion family.

**Data requirements.** OHLC only, both legs aligned to the same minute.

---

## 10. kNN / analog pattern matching on normalized bar windows

**Origin.** Classic analog forecasting (Lorenz "analogues"; Farmer & Sidorowich nearest-neighbor prediction); trading adaptations in Robot Wealth and various GitHub repos; Lorentzian Classification (section 11) is the most popular variant.

**Objective rules (standard interpretation).**
- Pattern vector: last 12 five-minute bar returns standardized by the 20-bar ATR, plus minutes-since-open bucket (so only same-time-of-day analogs match) and ATR ratio.
- Library: all historical pattern vectors with known 6-bar forward return, from the trailing 2 years, excluding the last 30 bars (purge).
- Distance: Euclidean (or Lorentzian, sum log(1 + |x_i - y_i|)); k = 50 neighbors (k = 8 as in Lorentzian is too noisy for a single-instrument library).
- Forecast = mean forward return of the k neighbors; dispersion = their sd. Trade long when forecast > cost + 0.25 x dispersion / sqrt(k); short symmetric; hold 6 bars; stop 1 ATR; flat 15:55 ET.

**Evidence.** No credible OOS result on ES/NQ/GC. The MNQ 2026 study's LSTM (which learns a sequence representation) and GB (12-bar return features) both failed; a kNN on the same inputs is a lower-capacity version of the same hypothesis. Lorentzian aggregate (below) is null.

**Evidence quality: 1.**

**Prop-fit.** Poor; experiment arm only.

**Data requirements.** OHLC only.

---

## 11. Lorentzian Classification (TradingView, jdehorty)

**Origin.** "Machine Learning: Lorentzian Classification" by jdehorty (TradingView, 2023); Premium version; Backtest Adapter; TradeSearcher aggregate of 96 backtests.

**Objective rules (defaults).**
- Features (5): F1 RSI(14,1), F2 WaveTrend(10,11), F3 CCI(20,1), F4 ADX(20,2), F5 RSI(9,1); each pair of numbers is (param A, param B) with B defaulting to an EMA smoother of 1.
- Label: direction of close 4 bars ahead (+1/-1).
- Neighbors: k = 8 approximate nearest neighbors over max 2000 bars back, sampling only every 4th historical bar (modulo-4 chronological spacing) to reduce autocorrelated duplicates; distance = sum_i log(1 + |f_i - f_i,hist|).
- Prediction = sum of neighbor labels (-8..+8); signal = sign.
- Filters on by default: volatility filter (recent ATR vs longer ATR), regime filter (Klinger/curvature-style with threshold -0.1); off by default: ADX > 20, EMA(200)/SMA(200) direction.
- Kernel: Nadaraya-Watson rational-quadratic, lookback 8, relative weighting 8, regression starts at bar 25; "trade with kernel" requires kernel slope to agree.
- Exit: fixed 4-bar hold by default; "dynamic exits" adjust the exit on kernel crossovers. Author states the trade stats panel "is NOT meant to be used as a substitute for proper backtesting" and estimates mid-bar entries (a "worst case" option exists).

**Evidence.** TradeSearcher: 96 TradingView backtests with more than 15 trades across 250+ symbols, "0 of 96 pass our quality gate", average t-statistic 0.52, p = 0.62, "statistically indistinguishable from chance"; the displayed winners are daily-bar single-name equities and crypto (e.g. FSR 1D +66%, 16 trades). No ES/NQ/GC result shown. Author-published stats are in-sample by construction.

**Evidence quality: 2** (one independent aggregate, strongly null).

**Prop-fit.** Poor. Not worth engine time except as a negative control.

**Data requirements.** OHLC only.

---

## 12. LSTM / transformer sequence models on bar returns (and why they fail)

**Origin.** Fischer & Krauss 2018 (*EJOR*, S&P 500 constituents, 1992 to 2015); Mesfin 2026 (MNQ 5-minute); Sezer, Gudelek & Ozbayoglu 2020 survey (arXiv:1911.13288); Kronos-style candlestick foundation models (Shi et al. 2025) that motivated the MNQ test.

**Objective rules (Mesfin configuration, the relevant one).**
- Input: sequence of the 12 five-minute bar returns 09:30 to 10:25 ET, 1 feature per step.
- Network: single LSTM layer, 16 units, dropout, sigmoid output; target = session close > 10:30 open + 10 pts; expanding-window walk-forward with folds 2022 to 2023, 2022-23 to 2024, 2022-24 to 2025.
- Trade: long at 10:30 if P > 0.5 (or thresholded), exit 15:55 ET.

**Evidence.**
- Mesfin: combined OOS accuracy 50.59% vs 51.8% base rate; permutation p = 0.515. Authors' conclusion: 944 days of single-instrument 5-minute bars is below the data scale at which sequence models can learn anything; "an empirical lower bound on data scale requirements".
- Fischer & Krauss (daily, cross-sectional, 240-day sequences, 25 units): 0.46%/day and Sharpe 5.8 before costs over 1993 to 2015; after 5 bps per half-turn, annualized 82.3% and Sharpe 2.34; but by sub-period the 2010 to 2015 window is "a time of deterioration" with cumulative profit near zero or negative in the plot (LSTM and RF alike). RF was second (Sharpe 1.87) and logistic regression was insignificant (t = 1.67).
- Why they fail on single-instrument intraday: (i) signal-to-noise of roughly 0.5% to 1% accuracy edge needs tens of thousands of independent labels, and a futures contract gives about 250 session-level labels per year; (ii) non-stationarity reshuffles the feature-label map yearly (feature-importance instability in every MNQ fold); (iii) cost floor of 1 to 2 points on MNQ exceeds the gross edge; (iv) most published wins are cross-sectional (hundreds of stocks per day) or pre-2010.

**Evidence quality: 3** (that they fail OOS at this scale).

**Prop-fit.** Not usable. Documented so the backtest loop does not spend time on it.

**Data requirements.** OHLC only.

---

## 13. Volatility-Volume-Gap (VVG) day classifier: fade the open on "classifier days"

**Origin.** Mesfin 2026, arXiv:2605.11423 and 2605.04004 section 4.6.

**Objective rules.**
- A day is "classifier-positive" if all three are in the top tercile of their expanding-window distribution: |overnight gap|, |first-30-minute return| (09:30 to 10:00 ET), and first 5-minute bar volume relative to a 20-day baseline (drop this third condition for OHLC-only; use first-bar range / 20-day average first-bar range instead).
- Fires on about 4.4% of sessions (40 days in 947).
- Reversal entry: at 10:00 ET, fade the direction of the first 30 minutes; exit at bar 13 after entry (65 minutes) or 15:55 ET; stop 1.5 x 20-bar ATR. Continuation entry: opposite. Close fade: enter at 15:30 against the day's direction, exit 15:55.

**Evidence.** Classifier days are behaviorally distinct (77.6% reverse from intraday peak before close, mean peak-to-close giveback 11.73 pts, 25.6 bp next-day spread), but no directional rule is stable: reversal net +13.49 pts, T = 1.26, N = 35 (2023 -11.45, 2024 +8.35, 2025 -22.76); continuation -17.49, T = -1.64 (2023 -49.00, 2024 +37.00, 2025 +18.76). Best configuration in the companion paper: +7.80 pts net on 127 OOS trades. Author: "a research asset, not an operational trading signal".

**Evidence quality: 2** (rigorous, null for tradability).

**Prop-fit.** Poor as written; the state itself (high gap + high opening range) is a useful feature for the meta-model in section 2.

**Data requirements.** Volume in the original (flag); range substitute available.

---

## 14. Trend-scanning labels with a tree classifier (Lopez de Prado)

**Origin.** Lopez de Prado, *Machine Learning for Asset Managers* (2020) ch. 5 "trend scanning"; daru.finance review of labeling/CV.

**Objective rules.**
- For each 5-minute bar t, fit OLS of close on time over horizons L in {6, 12, 24, 36} bars forward; take the L with the largest |t-stat of slope|; label = sign(slope) with weight |t|.
- Train RF (as in section 3) on the section 1 features with sample weights = |t| x uniqueness.
- Trade: side = predicted label if P > 0.55; hold until the predicted horizon L* (use the training set's modal L) or 15:55 ET; stop 1 x ATR.

**Evidence.** Method only; no published OOS ES/NQ intraday result. Shares the null baseline from section 1.

**Evidence quality: 1.**

**Prop-fit.** Experiment arm only.

**Data requirements.** OHLC only.

---

## 15. Regime-aware volatility forecast for contract sizing

**Origin.** arXiv:2510.03236 "Improving S&P 500 Volatility Forecasting through Regime-Switching Methods" (May 2014 to May 2025, realized vol from 5-minute returns; coefficient-based soft-regime HAR with Bayesian GMM clustering and XGBoost beats HAR baseline in pre-COVID, COVID and post-COVID windows); standard vol targeting (Quantitativo's ES/NQ model targets 2% to 3% daily vol).

**Objective rules.**
- Daily realized vol RV_t from 1-minute returns (sum of squared 5-minute returns, annualized).
- Forecast tomorrow's RV with HAR-RV (lags 1, 5, 22 days); optionally condition HAR coefficients on a 2-state GMM over (RV_t, |daily return|).
- Contracts = floor(target_daily_risk / (forecast daily sd in $ per micro)), with target_daily_risk = $300 in eval (15% of the $2,000 drawdown), $200 at funded start; cap 20 micros.

**Evidence.** Forecasting improvements are documented; translation to P&L is indirect. Quantitativo's vol-targeted ES/NQ model: 65% positive months, worst month -6.6%.

**Evidence quality: 3** for forecasting; 2 for trading effect.

**Prop-fit.** Strong; directly addresses the consistency rule (caps the largest day) and the trailing drawdown.

**Data requirements.** OHLC only; VIX optional.

---

## 16. Probability-to-size bet sizing (Lopez de Prado ch. 10) and threshold trading

**Origin.** *Advances in Financial Machine Learning* ch. 10.

**Objective rules.** For a classifier probability p of the chosen side: z = (p - 1/2) / sqrt(p(1-p)); m = 2 Phi(z) - 1 in [0, 1]; contracts = round(m x max_contracts). Average concurrent bets if several signals are live; discretize m to steps of 0.25 to avoid churning. Trade nothing below p = 0.55.

**Evidence.** Book-level; no independent OOS on futures.

**Evidence quality: 1.**

**Prop-fit.** Useful plumbing for sections 2, 3 and 6; adds no edge.

**Data requirements.** None beyond the classifier.

---

## 17. Validation protocol (not a strategy, mandatory for everything above)

**Origin.** Lopez de Prado 2018 ch. 7 (purged k-fold, embargo), ch. 12 (CPCV), Bailey & Lopez de Prado 2014 (deflated Sharpe), Mesfin 2026 (five-gate protocol).

**Rules.**
1. Expanding-window walk-forward with yearly folds: train <= 2022, test 2023; train <= 2023, test 2024; train <= 2024, test 2025; train <= 2025, test 2026 (partial). Report each fold.
2. Pass gates (all required): net-of-cost mean per trade > 0 with T >= 2.0 on OOS trades; >= 30 trades per OOS fold; same sign in every OOS year; permutation test (shuffle labels or entry dates 200+ times) p < 0.05, p < 0.001 preferred; deflated Sharpe > 0 given the number of configurations tried.
3. Costs: MES 0.75 pts, MNQ 2.0 pts, MGC 0.5 pts round trip (Mesfin's values; include $1.0 to $1.4 per side commission).
4. Hyperparameter search only inside purged 5-fold CV with a 1-day embargo on the training fold; one locked OOS run per candidate; log the count of configurations.
5. Fill convention: signal at bar close, fill at next 1-minute open; stops filled at the stop price plus 1 tick slippage.
6. Session discipline: no entries before 09:33 or after 15:15 ET for RTH systems; forced flat 15:55 ET.

---

## 18. What the evidence says works in 2022-2026 (and what does not)

**Works, with caveats.**
- Regime classification feeding a simple rule: GMM/HMM states on multi-feature bar vectors with 60 to 75 minute holds (London B T = 4.30; RTH Confluence T = 3.11) are the only ML signals that passed a strict walk-forward on MNQ across 2023, 2024 and 2025. Both must be rebuilt without volume and re-validated on our data.
- Meta-labeling a rule with real edge: on ES futures it cut drawdown by three quarters while raising Sharpe (OOS 2018 to 2019). The candidates to label are the noise-band intraday momentum model (positive every year since 2018 on ES/NQ) and the 09:30 to 09:55 ORB long with 75-minute hold (positive 2023 to 2025 but T = 0.88 unfiltered).
- Daily HMM stress gating and regime-aware vol sizing: reduce the size and frequency of the large losing days that breach a $2,000 EOD trailing drawdown. These are overlays, not signals.
- Hurst as an instrument/timeframe diagnostic: NQ 5-minute H about 0.59 (trend logic), gold H about 0.5 (do not fade intraday).

**Does not work (documented null results on our instruments and window).**
- Next-N-bar direction prediction with GB/RF/LSTM on single-instrument OHLC(V) features: 50.0% to 50.9% OOS accuracy, p = 0.135 to 0.515, unstable feature importance (MNQ 2021 to 2025).
- 11 of 14 OHLCV momentum-signal families: gross edge 0.07 to 1.50 pts vs 2.0-pt friction; the Asia-session expansion signal is significantly wrong-way (T = -11.52).
- Lorentzian Classification: 0/96 pass, mean t = 0.52.
- OU/z-score mean reversion on MGC 5-minute bars: negative in every configuration, T down to -5.32; the 60-minute OU half-life is about 8 hours, longer than a session.
- Intraday ES-NQ pairs: cointegration persists about 40% of adjacent periods; practitioners report intraday noise.
- Cross-sectional ML stat-arb (Krauss; Fischer & Krauss): large pre-2010 returns, near-zero 2010 to 2015, and structurally unavailable on one futures contract.

**Prop-specific implications.**
- The account's binding constraints are the $2,000 trailing drawdown and the 50% consistency rule, so the family's value is in trade filtering (meta-labeling), regime gating and vol sizing, which reduce variance without needing to forecast. Treat every "ML predicts direction" candidate as a negative control in the backtest loop.
- Expected per-trade edges that survived are 4 to 12 MNQ points net on 60 to 75 minute holds, i.e. $8 to $24 per micro per trade. To reach $3,000 with a largest day under 50% of the total requires roughly 20 to 40 such trades at 10 to 20 micros, so at least a month of eval at one or two signals per day; this is compatible with a 5-payout-day cycle at funded size only if the win rate (about 60%) and the 20-point stop hold up in 2026.
- Signals whose edge disappears with a one-bar delay (London B) need 1-minute fills at bar boundaries; our 1-minute data supports that, but any additional latency assumption should be stress-tested (the paper shows a sign flip at a 15-minute delay).

---

## Sources

- Mesfin, M. (2026). Sequential Structure in Intraday Futures Data: LSTM vs Gradient Boosting on MNQ. arXiv:2605.17724. https://arxiv.org/abs/2605.17724
- Mesfin, M. (2026). Structural Limits of OHLCV-Based Intraday Momentum Signals in MNQ Futures: A Systematic Falsification Study. arXiv:2605.04004. https://arxiv.org/abs/2605.04004
- Mesfin, M. (2026). A Validated Volatility-Volume-Gap Classifier for Regime Identification in MNQ Intraday Data. arXiv:2605.11423. https://arxiv.org/abs/2605.11423
- Singh, A. & Joubert, J. Does Meta-Labeling Add to Signal Efficacy? Hudson & Thames. https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/ and PDF https://hudsonthames.org/wp-content/uploads/2022/04/Does-Meta-Labeling-Add-to-Signal-Efficacy.pdf
- Christensen, H., Turner, R., Godsill, S. Hidden Markov Models Applied To Intraday Momentum Trading With Side Information. arXiv:2006.08307. https://arxiv.org/abs/2006.08307
- Delmastro, A. Regime-Switching-HMM-Factor-Investing (GitHub). https://github.com/AlessandroDelmastro/Regime-Switching-HMM-Factor-Investing
- LSEG Developer Portal. Market regime detection using Statistical and ML based approaches. https://developers.lseg.com/en/article-catalog/article/market-regime-detection
- Wang, Lin, Mikkelsen (2020). Regime-Switching Factor Investing with Hidden Markov Models. JRFM 13(12):311. https://www.mdpi.com/1911-8074/13/12/311
- QuantConnect. Gradient Boosting Model. https://www.quantconnect.com/learning/articles/investment-strategy-library/gradient-boosting-model
- QuantConnect. Intraday Dynamic Pairs Trading Using Correlation and Cointegration Approach. https://www.quantconnect.com/tutorials/strategy-library/intraday-dynamic-pairs-trading-using-correlation-and-cointegration-approach
- jdehorty. Machine Learning: Lorentzian Classification (TradingView). https://www.tradingview.com/script/WhBzgfDu-Machine-Learning-Lorentzian-Classification/
- TradeSearcher. Lorentzian Classification Strategy, 96 backtests. https://tradesearcher.ai/strategies/2019-lorentzian-classification-strategy
- LuxAlgo. Hurst Exponent concept guide. https://www.luxalgo.com/library/concept/hurst-exponent/
- StockSharp. Hurst Exponent Reversion strategy. https://stocksharp.com/store/strategies.0228_hurst_exponent_reversion/
- Krauss, Do, Huck (2017). Deep neural networks, gradient-boosted trees, random forests: Statistical arbitrage on the S&P 500. https://www.econstor.eu/bitstream/10419/130166/1/856307327.pdf
- Fischer & Krauss (2018). Deep learning with long short-term memory networks for financial market predictions. https://www.econstor.eu/bitstream/10419/157808/1/886576210.pdf
- Sezer, Gudelek, Ozbayoglu (2020). Financial time series forecasting with deep learning: a systematic literature review 2005-2019. arXiv:1911.13288. https://arxiv.org/abs/1911.13288
- arXiv:2510.03236. Improving S&P 500 Volatility Forecasting through Regime-Switching Methods. https://arxiv.org/abs/2510.03236
- Quantitativo. Intraday Momentum for ES and NQ. https://www.quantitativo.com/p/intraday-momentum-for-es-and-nq
- Elite Trader. Pair trading ES/NQ. https://www.elitetrader.com/et/threads/pair-trading-es-nq.55838/
- reasonabledeviations. Notes on Advances in Financial Machine Learning. https://reasonabledeviations.com/notes/adv_fin_ml/
- Jansen, S. machine-learning-for-trading (GitHub). https://github.com/stefan-jansen/machine-learning-for-trading
- Lopez de Prado, M. (2018). Advances in Financial Machine Learning. Wiley. Lopez de Prado (2020). Machine Learning for Asset Managers. Cambridge.
- Chan, E. (2013). Algorithmic Trading: Winning Strategies and Their Rationale. Wiley (Kalman pairs, ch. 3).
