# Family: Published backtests, forward tests and documented failure modes for ES / NQ / MES / MNQ day-trading systems

Research sweep date: 2026-10-03. Scope: any ES/NQ/MES/MNQ (and SPY/QQQ-as-proxy) day-trading system with *published numbers*, with priority on results that cover 2022-2026; independent out-of-sample (OOS) replications; documented reasons intraday systems fail live; realistic cost assumptions for MES/MNQ at a prop firm; and the ES/NQ volatility regime of 2025-2026. All times ET.

Target use: Lucid Trading 50K LucidFlex (eval target $3,000; $2,000 end-of-day trailing max-loss, breach checked intraday; 50% consistency rule in eval; funded: no consistency, EOD trailing locks at $50,100 once EOD balance >= $52,100; payout needs 5 days with >= $150 EOD profit; 4 minis / 40 micros in eval, 2 minis / 20 micros at funded start; flat by 16:45 ET). Data available: 1-minute OHLC (no volume) for S&P 500, Nasdaq 100 and Gold proxies 2010-11 to 2026-09, daily futures + VIX from Yahoo.

Method note. The web-search budget of this session was exhausted before this sweep started, so the sweep was done by direct fetches of known canonical sources (arXiv, Concretum/SSRN mirrors, GitHub, Kevin Davey, Build Alpha, Better System Trader, prop-firm review sites), by GitHub repository search, and by **computing the 2022-2026 regime statistics directly from the workspace's own 1-minute and daily data** (`data/parquet/SPXUSD_1m.parquet`, `NSXUSD_1m.parquet`, `ES_1d`, `NQ_1d`, `VIX_1d`). SSRN, Quantified Strategies, Reddit, IBKR, CME and AMP fee pages were blocked (403/503) and are cited only where an accessible mirror or the local data could substitute. Evidence quality is rated 1 (anecdote) to 5 (peer-reviewed with multiple independent OOS tests).

---

## 0. Executive summary

1. **The single most important 2022-2026 fact: every publicly documented, properly out-of-sample-tested OHLC-only intraday ES/NQ rule has an edge that is either (a) inside transaction costs, or (b) real in 2020-2024 and gone or negative in 2025-2026.**
   - Mesfin (arXiv 2605.04004v3, Sept 2026): 14 retail signal families (ORB, gap fill, gap continuation, volume spike/dry-up, Asia-session expansion, liquidity-grab fade, event-day drift, VVG regime reversal/continuation, MGC OU mean reversion) on MNQ 5-minute bars, 947 days Dec 2021-Aug 2025, expanding-window walk-forward with 2023/2024/2025 as OOS years, 2.0-point round-trip friction. **None passed.** Eleven have gross edge of 0.07-1.50 pts/trade (below friction); three clear friction but are year-unstable (ORB long 75-min hold net +2.82 pts, T=0.88; gap-continuation short net +14.52 pts, T=1.46; VVG reversal net +13.49 pts, T=1.26, N=35).
   - Zarattini-Aziz-Barbon "Beat the Market" SPY intraday momentum (Sharpe 1.33, 2007-2024): two independent replications reproduce it in-sample (Sharpe 1.34 / 1.11), then find **OOS Sharpe 0.39 (May 2024-Mar 2026, p<0.001 for the decline)** and **2025 Sharpe -0.27, 2026 YTD -1.91** on both SPY and ES futures (daily returns correlated 0.97). Walk-forward re-optimisation made it worse (0.57 vs 0.92 fixed). Costs do not explain the collapse.
   - ML on MNQ 5-minute OHLCV (LSTM, gradient boosting, arXiv 2605.17724): OOS accuracy 50.0-50.9% vs a 51.8% base rate. The VVG "big day" classifier (arXiv 2605.11423) identifies real behaviour (77.6% of flagged days reverse from their intraday peak) but no directional rule survives (best T=1.46).

2. **What did pass a walk-forward test with costs (same author, same protocol) uses regime classification plus a 60-75 minute hold**, not single-bar OHLC pattern prediction: London Session Signal B (03:00-08:30 ET, 15-min bars, GMM regime transition, long only, exit 60 min or 08:30; OOS N=247, net +4.09 MNQ pts/trade, T=4.30, win 61.5%, p=0.000025, parameter range T=3.87-4.83) and RTH Confluence (GMM regime + Markov gate + volume z-score + ATR-scaled pullback, exit bar 13; OOS N=196, net +11.82 pts, T=3.11). Both need volume as a GMM feature (approximable with range/|return| only), and the London signal flips sign if entry is delayed one 15-minute bar.

3. **The regime that the backtest must survive (computed from the workspace data):** ES realised vol by quarter 2025Q1-2026Q3 = 17.3, 30.0 (tariff shock, VIX peak 52.3), 8.9 (lowest in the 2022-2026 sample), 13.0, 14.0, 13.5, 11.4 %; NQ 23.9, 35.3, 11.3, 18.4, 17.9, 22.6, 20.0 %. Median RTH range 56 ES pts (2025) / 61 (2026); 263 NQ pts (2025) / 366 (2026). Trend-day share (|close-open| > 0.7 x range) fell from 0.27-0.34 in 2022 to 0.11-0.31 in 2025-26 (mean ~0.21). Daily ES return autocorrelation was negative in 2025 (-0.19, -0.08, -0.23 by quarter) and ~0 in 2026: **2025 was a mean-reverting, mostly low-vol tape punctuated by one two-month vol spike; 2026 is mid-vol and choppy.** The academic "first half-hour predicts last half-hour" effect is absent in ES/NQ 2022-2026 (same-sign rate 45-50%, correlation -0.09 to +0.10).

4. **Cost realism for the simulator.** Lucid's published commissions: MES/MNQ $0.50 per side, ES/NQ $1.75 per side, GC $2.30 per side (MGC not listed; assume $0.50-0.75). Independent MNQ studies use 2.0 pts ($4.00) round-trip all-in for 5-minute-bar systems; GitHub practitioner backtests use 1 tick per side + $1.50/side; the SPY/ES replication used 0.25 bps on ES. Recommended simulator defaults: commission per Lucid, plus **1 tick per side slippage on every market/stop fill in RTH (MES $1.25, MNQ $0.50, MGC $1.00), 2 ticks in the 09:30-09:31 minute, around 08:30/10:00/14:00 releases, and in ETH**, limit orders filled only if price trades through the limit by >= 1 tick. That gives MES ~$3.50 (0.7 pt) and MNQ ~$2.00 (1.0 pt) round trip; stress-test at 2x (which is Mesfin's MNQ floor). A rule whose gross edge per trade is below 2 MNQ pts / 1 ES pt is not tradable.

5. **For the Lucid 50K the evidence points to**: (i) few trades per day with gross edge >= 4-5 pts MNQ / 1.5-2 pts MES per trade, (ii) 60-120 minute holds rather than next-bar exits, (iii) regime/volatility gates that keep the system flat on dead days (Gary Hart: "systems don't trade when movement cannot overcome costs; some sit out three months"), (iv) stop-and-reverse or fixed-dollar targets rather than trailing/parabolic exits (Davey's 567,000-backtest exit study on 40 futures incl. ES/NQ), (v) a daily loss cap of ~$300-400 so that a 5-6 day losing streak cannot approach the $2,000 EOD trailing floor, and (vi) sizing that keeps the best single day under ~$600 in eval so the 50% consistency rule is satisfied by day 6-10 rather than fought.

---

## 1. Academic and quasi-academic ES/NQ/SPY intraday systems with 2022-2026 OOS evidence

### 1.1 Zarattini, Aziz & Barbon (2024) "Beat the Market" intraday momentum on SPY (and ES by replication)

- **Origin**: Concretum Research / SSRN 4824172 (May 2024). SPY 2007-2024, 1-minute data.
- **Rules (standard reading; the exact formula is in the paper, the replications below implement it)**:
  - Noise area at each minute t: boundary = reference +/- sigma_t, where sigma_t = 14-day average of |close_t / open - 1| at that same time of day (so the band widens through the day), and reference = max(open, previous close) for the upper band, min(open, previous close) for the lower band (gap-anchored).
  - Check every 30 minutes (10:00, 10:30, ..., 15:30). If price is above the upper band go/stay long; below the lower band go/stay short; inside the band go flat.
  - Trailing stop = the band itself or VWAP, whichever is nearer (replications use the band/VWAP as the stop level, evaluated at the 30-minute marks). Forced flat at 16:00.
  - Size: target 2% daily volatility using a 14-day realised-vol estimate, capped at 4x leverage. Commission $0.0035/share + $0.001/share slippage in the OOS replication.
- **Published results**: total +1,985% net, 19.6%/yr, Sharpe 1.33, hit ratio 43%, max DD 25%, beta ~0, 2007-2024.
- **Independent replications (both GitHub, 2026)**:
  - giovannibrusco/zarattini-2024-momentum-spy: SPY (Alpaca 1-min, Jul 2020-Jul 2026) and **ES futures (IB 1-min, May 2024-Jul 2026, 9 contracts, volume-crossover roll)**. In-sample 2020-2024 Sharpe 1.4-2.0/yr, alpha 23-28%, +25.8% in 2022 (SPY -19.5%). Full 2020-26 Sharpe 1.11, alpha +16.7%/yr (t=2.85), +2.6 bps/trade, win 41%, payoff 1.69. **ES: +2 bps/trade, 36% win, payoff 2.1, daily-return correlation with SPY 0.97. 2025 Sharpe -0.27, 2026 YTD -1.91 on both.** Pre-registered 27-variant grid: paper config ranked first (nothing to promote). Quarterly walk-forward reselection: Sharpe 0.57 vs 0.92 fixed. Deflated Sharpe applied. Costs (0.4 bps/RT SPY, 0.25 bps ES, 1-tick sensitivity) do not explain 2025-26. Verdict: "genuine in-sample, not allocable today, not dismissible as dead."
  - PazSheimy/spy-intraday-momentum-oos: IQFeed 1-min SPY. In-sample 2015-2024 replication 19.8%/yr, Sharpe 1.34, hit 44.8%, MDD 26.2% (paper 19.6%, 1.33, 43%, 25%). **OOS May 2024-Mar 2026: 4.8%/yr, Sharpe 0.39, hit 45.0%, MDD 18.5%; decline significant at p<0.001; underperforms buy-and-hold.**
- **Evidence quality**: 4 for the in-sample effect (paper + two independent replications match); **the OOS evidence is also quality 4 and it is negative for 2025-26**.
- **Prop fit**: Poor as published for 2025-26. Shape is also wrong for the eval: 41-45% win rate, EOD exits, fat right tail (big days in 2020/2022 vol spikes) and long flat stretches. Possible salvage for our use: use the noise band only as a *filter* (do not trade inside the band) for other entries, and only when 14-day realised vol is above a threshold; the brusco repo's VIX-regime tables show the edge lived in VIX > 20 regimes.
- **Data requirements**: OHLC only (VWAP can be approximated by typical-price average without volume). Fully codeable.
- **Sources**: https://concretumgroup.com/beat-the-market-an-effective-intraday-momentum-strategy-for-sp500-etf-spy/ ; https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4824172 ; https://github.com/giovannibrusco/zarattini-2024-momentum-spy (docs/CONCLUSIONS.md) ; https://github.com/PazSheimy/spy-intraday-momentum-oos

### 1.2 Gao, Han, Li & Zhou (2018) "Market Intraday Momentum" (first half-hour -> last half-hour)

- **Origin**: Journal of Financial Economics 129(2), 394-414. SPY 1993-2013, plus 10 other ETFs.
- **Rule**: r_last30 (15:30-16:00) is positively predicted by r_first30 measured from the previous close (prev close -> 10:00) and by r_12th (15:00-15:30). Strategy: at 15:30 go long if the first-half-hour return (from prev close) is positive, short if negative; exit 16:00. Effect strongest on high-volatility, high-volume, recession and macro-news days.
- **Published results**: statistically and economically significant (abstract); the paper reports a timing strategy with success rate ~ 55% and positive Sharpe over 1993-2013 (figures from the paper, not re-verified here because SSRN/JFE were blocked).
- **Our 2022-2026 check (workspace 1-min data, ES/NQ proxies, RTH 09:30-16:00)**: same-sign rate of first-30 vs last-30 = 48.2/49.4/48.8/48.6/44.8% (ES, 2022-2026) and 49.4/48.4/44.7/50.2/46.5% (NQ); correlations -0.09 to +0.10. Rest-of-day (prev close -> 15:30) vs last-30 same-sign: 55.0/48.3/48.8/47.0/45.4% (ES). **No usable intraday momentum at the close in ES/NQ in 2023-2026**; the 2022 bear market is the only year with a hint (55%).
- **Evidence quality**: 5 for the original (peer-reviewed, many follow-ups); **1-2 for 2022-2026 applicability** (our own check shows nothing).
- **Prop fit**: one trade/day at 15:30 is attractive operationally but the edge is not there in the target window. Mean last-30-min move 2025-26 is 17 bps ES ($57 on 1 MES at ES 6700) / 17-20 bps NQ, so even a 55% hit rate would net roughly $2-4 per MES trade after costs. Not viable.
- **Sources**: https://ideas.repec.org/a/eee/jfinec/v129y2018i2p394-414.html ; local computation (`research/families/evidence_and_failures.md`, section 6).

### 1.3 Baltussen, Da, Lammers & Martens (2021) "Hedging Demand and Market Intraday Momentum"

- **Origin**: JFE 142(1), 377-403. 60+ futures (equity indices, bonds, commodities, FX), 1974-2020.
- **Rule**: last-30-minute return is positively predicted by the return from previous close to 30 minutes before the close; the move reverts over the following days. Attributed to gamma hedging by option market makers and leveraged-ETF rebalancing; strongest in equity index futures and when dealer gamma is negative.
- **Published results**: "economically and statistically highly significant" across asset classes (abstract); index futures show the largest coefficients.
- **Our 2022-2026 check**: ES to-15:30 -> last-30 correlation 0.06, 0.03, -0.08, -0.03, -0.01 by year; NQ 0.10, 0.05, -0.07, -0.04, 0.01. **Zero to slightly negative in 2024-2026.** Consistent with the brusco finding that the gamma-driven intraday trend edge compressed after 2024 (0DTE option volume changed the dealer-gamma profile).
- **Evidence quality**: 5 original; **1 for 2024-2026**.
- **Prop fit**: not viable in the target window; could be re-enabled by a VIX > 25 gate (the only 2022-26 periods with a positive sign were the 2022 bear and 2025Q2), but sample is tiny.
- **Sources**: https://ideas.repec.org/a/eee/jfinec/v142y2021i1p377-403.html

### 1.4 Mesfin (2026) "Structural Limits of OHLCV-Based Intraday Momentum Signals in MNQ Futures" - the 14 failures

- **Origin**: arXiv 2605.04004 (v3, 2026-09-15), independent researcher. MNQ continuous front-month, 5-minute OHLCV, **RTH 09:30-16:00 ET, Dec 2021-Aug 2025, 947 complete days**, NinjaTrader data, no roll adjustment. MGC 1,091 days for the OU test. Asia tests on 20:00-02:00 ET bars.
- **Protocol**: signal at bar close, entry next bar open. Friction **2.0 MNQ pts ($4.00) round trip** (spread + NinjaTrader exchange fees + conservative slippage); MGC 0.50 pts ($5.00). Expanding-window walk-forward: train 2022 -> test 2023; train 2022-23 -> test 2024; train 2022-24 -> test 2025 (Jan-Aug). Pass requires all of: OOS net T >= 2.0, >= 30 trades per fold, positive net, same sign in 2023/2024/2025, permutation p < 0.001.
- **Results by family (all OOS, net of 2.0 pts; T on net returns)**:

| Family | Exact rule as tested | N (OOS) | Net pts/trade | T | 2023 / 2024 / 2025 | Verdict |
|---|---|---|---|---|---|---|
| ORB long, bar+1 | OR = 09:30-09:55 (6 bars); buy next open after a close above OR high; exit after 1 bar | 447 | -0.82 | -0.82 | -2.11 / -1.54 / +6.11 | fail |
| **ORB long, bar+15 (75 min)** | same entry, hold 15 bars | 447 | **+2.82** (gross +4.82) | 0.88 | +2.43 / +7.04 / +15.05 | fail (T, stability) |
| ORB short, bar+1 | sell below OR low | 428 | -3.45 | -3.16 | -2.73 / -4.74 / -0.15 | fail |
| ORB short, bar+15 | | 428 | -2.16 | -0.58 | -2.06 / -1.04 / -0.59 | fail |
| ORB pullback entry | enter on retest of OR level after break, 20-pt stop | 83 | -4.44 | -1.27 | 80.7% stop-out rate | fail |
| Asia expansion bar 1.5x, b+1 | 20:00-02:00 ET, 5-min bar range > 1.5x rolling 20-bar avg, go with the bar | 1,955 | -2.27 | **-11.52** | | fail (reversal, not continuation) |
| Asia expansion 2.5x, b+6 | | 340 | -0.94 (gross +1.06) | -0.90 | | fail |
| Asia liquidity grab, fade | pierce of session extreme then close back inside; fade | 6,442 events | -2.20 | -14.12 | gross 0.2-0.8 pts either way | fail |
| Gap fill fade 09:30 / 09:45 / 10:00 | fade the overnight gap at the stated time | 766 / 721 / 721 | -1.92 / -1.05 / -1.43 | -0.44 / -0.26 / -0.38 | 09:30: -2.84 / +3.93 / +2.02 | fail |
| **Gap continuation short** | Kalman-filter velocity on 1-min bars in the first 30 min; short when standardized downward velocity > 2.5 (top 0.62%) | 35 (~12/fold) | **+14.52** (gross +16.53) | 1.46 | +14.53 / -11.87 / +10.27 | fail (2024, N/fold) |
| Volume spike up / down, H=1 | | 2,122 / 2,412 | -1.92 / -2.45 | -2.21 / -3.08 | | fail (needs volume) |
| Volume dry-up exhaustion | | 1,060 / 723 | -2.42 / -1.99 | -5.28 / -3.59 | | fail (needs volume) |
| VVG reversal (fade opening) | top-tercile |gap|, |first-30-min return|, first-bar volume; fade | 35 | +13.49 | 1.26 | -11.45 / +8.35 / -22.76 | fail |
| VVG continuation | | 35 | -17.49 | -1.64 | -49.0 / +37.0 / +18.8 | fail |
| Event-day trend | FOMC/CPI/NFP/PCE etc. (993 events), enter after spike bars | | T 0.14-0.69 from bar+6 | | 2025: 12 trades, -9.56 | fail |
| MGC OU mean reversion 5-min, z 1.5/2.0 | | 1,172-3,059 | -0.27 to -0.55 | -1.6 to -5.3 | half-life of 60-min OU ~8 h | fail |

- **Documented failure modes (the paper's own taxonomy)**: (1) gross edge below friction (11 of 14; "on five-minute bars in a contract as liquid as MNQ the equilibrium gross edge sits near 1-2 points"); (2) year instability - one strong OOS year next to negative ones (ORB long, VVG); (3) too few trades per fold (gap continuation, VVG close-fade); plus two mechanism findings: **expansion/breakout moves are consumed inside the signal bar** (open-to-next-open +32.24 pts in the breakout direction vs close-to-next-open -0.17 pts), so bar-close systems capture the reversal; and the **London signal flips sign with a one-bar delay** (T +4.30 -> -2.78).
- **Evidence quality**: 4 (pre-specified criteria, walk-forward, costs, corrections published after external replication attempts; single author, single instrument).
- **Prop fit**: this is the reference list of what NOT to build as a bare rule. The two near-misses worth re-testing on our 1-minute data (longer history helps the N problem): ORB long with a 75-minute time exit (positive all three OOS years; the ORB family report already found the SMA200-filtered variant survives) and the gap-continuation short (Kalman velocity can be approximated by a linear-regression slope of 1-min closes 09:30-10:00 standardised by its 60-day distribution).
- **Sources**: https://arxiv.org/abs/2605.04004 (PDF v3 read in full)

### 1.5 Mesfin positive control A: London Session Signal B (MNQ, 03:00-08:30 ET)

- **Rules (Appendix A.2)**: 15-minute MNQ bars 03:00-08:30 ET. Five features per bar (ATR ratio, volume z-score, close position within range, 15-min return, directional consistency), rolling z-scored then StandardScaled. 3-component GMM refit each walk-forward fold, components mapped to Regime 0 (bearish chop), 1 (extreme volatility), 2 (bullish drift) by vol z-score and directional consistency. **Entry: long at the next 15-min bar open after a clean R0 -> R2 transition (no R1 label in the prior two bars). Exit: 60 minutes after entry or 08:30 ET, whichever first. Stop 20 pts fixed (idealised fill).** Friction 2.0 pts RT.
- **Results**: walk-forward OOS N=247, mean net +4.09 pts, SD 14.97, **T=4.30, p=0.000025, win 61.5%**, per-trade Sharpe 0.27, bootstrap P(mean > 2 pts)=98.9%, T range 3.87-4.83 across parameter variations; unconditional long benchmark over 639 sessions -0.47 pts (T -0.22). Static full-sample figure (N=289, T=5.15, +5.77) superseded. **One-bar delay: T -2.78 (mean -2.91); two-bar delay T -2.16.**
- **Evidence quality**: 3 (walk-forward, costs, permutation; but single author, uses the same data as the 14 failures, and the sign flip under delay means it may be a bar-boundary artefact).
- **Prop fit**: good shape (61% win, +$8/contract/trade, SD $30, ~80 trades/yr at 1 MNQ; 20 MNQ -> ~+$650/month gross of the Lucid commission, daily SD ~$600). Trades in the Lucid-allowed pre-market window and is flat by 08:30, well before the 09:30 open. **Data requirement: volume z-score is one of five GMM features; we can only approximate with range-based activity (|return|, range/ATR). Must be flagged as approximated.** Must also be implemented with entry at the exact bar open (no delay).
- **Sources**: https://arxiv.org/abs/2605.04004 Appendix A.2

### 1.6 Mesfin positive control B: RTH Confluence Signal (MNQ, 09:30-16:00 ET)

- **Rules (Appendix A.1)**: 5-min bars. 4-feature GMM (ATR ratio = 20-bar ATR computed on **1-minute** bars / fixed 10.34 baseline; 50-bar volume z-score; close position in range; 5-min return) fit once on 2022. Fire when: regime label = 1 (Active Flow) AND rolling 200-bar first-order Markov P(1 -> 2) > 0.15 AND 50-bar volume z > 0.5. **Entry: limit at a pullback of 25 x ATR_ratio points below the signal-bar close within 6 bars (cancel if not reached); ATR_ratio capped [0.5, 2.0]. Exit: bar 13 from signal-bar open (65 min) or session end. Stop: 80 x ATR_ratio pts (idealised fill).**
- **Results**: in-sample 2022-24 N=538, +15.77 pts, T 5.83, win 61.0%; **walk-forward OOS N=196, +11.82 pts net, SD 53.8, T=3.11, permutation p<0.001; 2025 OOS +13.14 pts**; unconditional 09:30 long, 13-bar hold 2022-24: -2.60 pts (T -0.75, N=759). Author's own caveats: 53+ parameter combinations searched before locking; GMM fit contaminates the 2022-H2 fold; ATR baseline computed on the full in-sample period.
- **Evidence quality**: 3 (same as above, with heavier selection exposure).
- **Prop fit**: +$23.6/MNQ/trade, ~55 trades/yr, SD $108/trade/contract: at 10 MNQ roughly +$1,100/month with ~$1,100 per-trade SD, so a single trade can approach the eval's consistency cap. Needs volume (two of the gates). Approximable only loosely.
- **Sources**: https://arxiv.org/abs/2605.04004 Appendix A.1

### 1.7 Mesfin companion papers: VVG classifier and ML on MNQ

- **VVG classifier (arXiv 2605.11423v3)**: flags a session when |overnight gap|, |first-30-min return| and first-bar volume vs 20-day baseline are all in the top tercile of expanding-window distributions (4.4% of days, ~40 days). Flagged days: 77.6% reverse from intraday peak before close, mean peak-to-close giveback 11.73 pts, next-day return spread 25.6 bps; **but 2024 mean close +40.74 vs 2025 -42.48**. Eight directional configurations: best T=1.46 (+7.80 pts, N=127, reversal with OLS filter). Evidence 3. Prop fit: useful as a *risk filter* (flagged days are the ones that produce the account-killing reversals), not as an entry. Volume can be dropped (gap and first-30 return alone are OHLC).
- **LSTM vs gradient boosting (arXiv 2605.17724)**: target = MNQ close > 10:30 open + 10 pts; 944 days; OOS accuracy 50.0-50.9% (GBM) and 50.6% (LSTM) vs 51.8% base rate, permutation p 0.135 / 0.515, feature importance unstable. Evidence 3. Prop fit: none; confirms that 4 years of 5-min OHLCV is insufficient for ML.
- **Sources**: https://arxiv.org/abs/2605.11423 ; https://arxiv.org/abs/2605.17724

### 1.8 Zarattini & Aziz (2023) QQQ 5-minute ORB and Concretum VWAP system

- Covered in detail in `orb_session.md` section 1.1 (ORB: Sharpe 1.12 gross on QQQ, break-even at 2.2 c/share slippage, net ~0 on NQ CFDs 2015-2026 per the mql5 replication).
- **Concretum "VWAP: the Holy Grail for Day Trading Systems"** (Jan 2018-Sep 2023, QQQ/TQQQ): rule as published is simply long when price is above VWAP, short below, flat at close, net of commissions (no slippage stated). QQQ: +671% ($25k -> $192.6k), MDD 9.4%, Sharpe 2.1; TQQQ +8,242%. No stop/target/time-window detail, no OOS, and the CXO critique of the sibling ORB paper (no spread, no slippage, 4x leverage, perfect fills) applies. Evidence 2. Prop fit: a VWAP cross system on 1-min futures fires dozens of times a day in chop; the mql5 ORB replication shows this family's edge is "the size of the spread". Only usable with a strong filter (e.g., trade the VWAP side only after a noise-area breakout, per 1.1).
- **Sources**: https://concretumgroup.com/volume-weighted-average-price-vwap-the-holy-grail-for-day-trading-systems/ ; https://www.cxoadvisory.com/technical-trading/day-trading-with-an-opening-range-breakout-strategy ; https://concretumgroup.com/papers/

---

## 2. Practitioner / open-source ES-NQ-MNQ systems with published 2022-2026 numbers

### 2.1 "NQ Strategy B": 5-min inverse FVG inside 15-min FVG, long-only (GitHub prashanthaitha24/nq-strategy-b-bot)

- **Rules (exact, from README)**: 5-min and 15-min MNQ bars (Databento OHLCV). Conditions all true: (1) an active (unfilled) 5-min bullish fair-value gap exists; (2) that 5-min FVG lies inside an active 15-min bullish FVG zone (5-pt buffer at the top); (3) the current 5-min bar's low dips into the 5-min FVG; (4) the current 5-min bar closes above the 5-min FVG top; (5) time 09:30-12:00 ET; (6) no open position and daily trade count below cap. **Stop = 5-min FVG bottom - 2 pts; target = 2R; hard exit 15:45 ET. Long only** (shorts: 42.5% win vs 56.5% longs). Fees included (amount not stated).
- **Results, 1 MNQ, Jan 2023-May 2026**: 432 trades (~140/yr), win 53.5%, PF ~2.3, net +$17,187, max DD $786, 4/4 years and 13/14 quarters profitable; 2023: 127 trades, 46.5%, PF 1.44, +$1,974, DD $621; 2024: 139, 52.5%, 2.24, +$5,430, DD $610; **2025: 117, 57.3%, 2.47, +$6,623, DD $786; 2026 (4 mo): 47, 68.1%, 2.82, +$3,319, DD $668.** Predecessor ("ATB") on the same data: +$8,305 with $5,766 max monthly DD. Author's realistic expectation: +$3-4k/yr/contract after a "1.5-2.5x haircut from slippage and edge erosion". No live or forward results.
- **Evidence quality**: 2 (single author, full-sample numbers, rules refined on the same data - the "Strategy B vs ATB" comparison is itself a selection step; no walk-forward; fills on 5-min bars with no stated slippage). The rising win rate 46 -> 68% over 2023-2026 is a red flag for in-sample tuning toward the recent period.
- **Prop fit**: the *shape* is exactly what the Lucid rules want: ~0.5 trades/day, 53-57% win, 2R target, max DD < $800 per contract, 85% profitable months. Scaled to 5 MNQ: ~+$2,750/month in 2025 at ~$3,900 max DD (too much for the $2,000 EOD trailing floor at 5; use 2-3 MNQ in eval, ~$1,100-1,650/month). Fully codeable from OHLC (FVG = 3-bar gap pattern). **Must be re-derived on our data with walk-forward before trusting any number.**
- **Sources**: https://github.com/prashanthaitha24/nq-strategy-b-bot

### 2.2 ICT-style session models on NQ/MNQ (GitHub asiatrada/algorithmic-trading-bot)

- **Rules (names only; README does not disclose exact conditions)**: PDH break-and-retest (previous-day high), Asian-range break-and-retest, "Silver Bullet" (10:00-11:00 and 14:00-15:00 ET windows), OTE (61.8-78.6% Fibonacci pullback) with tiered risk, opening-range FVG fade, M2022 multi-timeframe sweep.
- **Results**: 14+ months, 141+ trades, win 63%+, PF 1.89, win/loss 2.1:1, max DD ~15%, Sharpe 1.4+. 60-day sweep: PDH break-retest 61%/PF 1.89; Asian break-retest 58%/1.74; Silver Bullet bidirectional 64%/1.92; OTE long 55%/1.67; OR-FVG bull 62%/1.85. No costs stated, no dates, no OOS.
- **Evidence quality**: 1.
- **Prop fit**: the PDH/Asian-range break-and-retest and the time-window ("Silver Bullet") ideas are codeable from OHLC and overlap with the session-structure family; treat the numbers as unverified.
- **Sources**: https://github.com/asiatrada/algorithmic-trading-bot

### 2.3 Walk-forward MNQ research bot (GitHub kjw616/mnq-strategy-research, Oct 2026)

- Designs on 2023-2024, runs untouched on 2025-present. Strategies: liquidity sweep + FVG, CRT, HTF sweep, Fibonacci golden zone, multi-timeframe EMA cross, rejection blocks, "Keen's Indicator v2.1" (1,086 trades; median stop 2.34 pts = $4.69 on 1 MNQ, 90th pct 7.05 pts). **Documented failure: "an EMA-cross edge that replicated walk-forward disappeared once realistic commissions and slippage were applied."** No P&L tables in the README. Evidence 1-2. Lesson: stops of 2-7 MNQ pts are below the 2-pt friction floor - any system with median stop < ~10 MNQ pts is a slippage-donation machine.
- **Sources**: https://github.com/kjw616/mnq-strategy-research

### 2.4 MNQ/MGC S/R breakout with honest backtest-vs-live framework (GitHub marcwong515-art/futures-backtester)

- **Rules**: swing-pivot levels clustered within a tolerance, valid after >= 3 touches; long on close above resistance, short on close below support, next-bar-open execution; stop = 1/4 of breakout-bar wick (or 1/4 bar range); 2 micros fixed. **Execution model: 1 tick slippage per side on adverse fills, $1.50/contract/side commission, stops filled at stop price or at the open if gapped through, session-end exits at bar close with no slippage.** Results tables unpopulated; live log pending. Evidence 1 for the strategy, but the cost model is a sensible template. Flags "bar-level stop approximation" and "stale prices" as expected live divergences.
- **Sources**: https://github.com/marcwong515-art/futures-backtester

### 2.5 MNQ/MGC size-of-day forecasting as a filter (GitHub Matswm86/mwm-morning-brief)

- Not a directional strategy. Pre-open call on whether today's RTH range will exceed its 26-day median: **63.9% walk-forward hit rate over 1,719 days**; 15:25 CET regime lens (NARROW / NO CALL / WIDE vs trailing 20-session median) **65.2% over 5 years vs 58.9% for naive persistence**; intraday trend-vs-chop nowcast 62% precision on 252 held-out sessions; "first-touch geometry" 77.6% = random-walk baseline (i.e., no edge in which side of the range breaks first). Evidence 2. Prop fit: a range-expansion forecast built from prior ranges/gaps (OHLC-only) is a legitimate gate for breakout vs mean-reversion mode selection; the 59% persistence baseline itself (yesterday wide -> today wide) is the simplest codeable version.
- **Sources**: https://github.com/Matswm86/mwm-morning-brief

### 2.6 Kevin Davey exit study (KJ Trading Systems)

- 40 futures including ES, ES.D (day session), NQ, RTY, YM, NK; Jan 2010-2020; bar sizes 60/120/360/720/1440 min; 5 entry types x 3 lengths (15/25/35 bars); 567,000 backtests; slippage and commission "determined from real money trading and bid-ask analysis" (values not disclosed). **Ranking by return on account: stop-and-reverse > dollar target > breakeven stop > trailing stop > parabolic. No exit was positive in every sector; metals and stock indices were profitable on average.** Companion articles: walk-forward results are "somewhat optimistic" vs real-time but far better than plain backtests; incubate 3-6 months; Monte Carlo on trade order for drawdown; "if you can see where the backtest ended and incubation began from 10 feet away, you have a problem"; "once slippage and commissions were added, most [indicator entries] lost money"; momentum indicators and RSI were the entries that held up, most others 45-55% accurate.
- **Evidence quality**: 3 (very large systematic test, but vendor-published without the underlying numbers).
- **Prop fit**: directly relevant to exit design: fixed-dollar targets (which also create the many-small-positive-days profile the payout rule needs) and reversals beat trailing/parabolic stops on index futures at 60-min+ bars.
- **Sources**: https://kjtradingsystems.com/algo-trading-exits.html ; https://kjtradingsystems.com/walkforward-testing-for-algorithmic-trading.html ; https://kjtradingsystems.com/monte-carlo-simulation.html ; https://bettersystemtrader.com/162-building-effective-entries-and-exits-kevin-davey/

### 2.7 Jeff Swanson independent-filter method (Better System Trader ep. 196)

- Baseline simple entry; test each filter alone against the full baseline sample (never stacked), keep only filters that improve net profit or profit/DD, combine, then OOS. **Target for intraday futures: ~$100 net per trade after costs.** Most-used filter: 150-200-day moving average bull/bear regime. Documented failure: five stacked filters shrink 1,000 trades to ~80 and hide each filter's effect. Evidence 2 (method, not a strategy).
- **Sources**: https://bettersystemtrader.com/196-how-to-avoid-curve-fitting-using-independent-testing-jeff-swanson/

### 2.8 Gary Hart on intraday futures (Better System Trader ep. 085)

- "Pure price-based approaches have become increasingly difficult"; the "edge in purely price-based systems is gone" after QE suppressed intraday vol (2011-12); what still works for him: **volatility thresholds in every intraday system (no trade when expected movement cannot overcome costs; some systems idle for three months)** and market-internals inputs (advance/decline, up/down volume, put/call, VIX behaviour). Day-trading systems' drawdowns anti-correlate with swing systems' (day trading thrives in high vol). Evidence 1-2. Prop fit: the volatility-gate idea is codeable (ATR/VIX thresholds); internals are not available to us.
- **Sources**: https://bettersystemtrader.com/085-intraday-trading-strategies-gary-hart/

### 2.9 Unger Academy ES / NQ strategies

- Blog index lists "Nasdaq Trading Strategies: 36% or 56% Winning Trades" and "S&P 500 Trading: Two Strategies Averaging Over $220 per Trade" (https://ungeracademy.com/blog/nasdaq-trading-strategies-win-rate ; https://ungeracademy.com/blog/sp-500-trading-220-average-trade). The article bodies returned empty to the fetcher, so rules and numbers could not be verified. Unger's published practice (from his books/courses, not re-verified here): intraday breakout/reversal entries on 5-15-min ES/NQ bars confined to time windows, exits at session end, and a standing assumption of ~$25-50 slippage+commission per round turn on minis. Evidence 1 for this sweep.

---

## 3. Documented reasons day-trading systems fail live

| Failure mode | Evidence | Number to remember |
|---|---|---|
| Gross edge below friction | Mesfin 2026: 11 of 14 MNQ families have gross 0.07-1.50 pts/trade vs 2.0-pt friction; Asia liquidity grab gross 0.2-0.8 pts (T -14 net); kjw616 EMA cross died with costs; mql5 ORB replication "the edge is the size of the spread" | 5-min OHLC single-bar signals on MNQ: equilibrium gross edge ~1-2 pts |
| Signal consumed inside the signal bar | Mesfin: expansion bars open-to-next-open +32.24 pts vs close-to-next-open -0.17; London B flips from T +4.30 to -2.78 with one 15-min bar delay | bar-close entry captures the reversal |
| Edge decay / regime change after publication | Zarattini SPY momentum: IS Sharpe 1.33 -> OOS 0.39 (2024-26), 2025 -0.27, 2026 -1.91 on ES; gamma-hedging intraday momentum ~0 in ES/NQ 2024-26 (local check) | assume any published 2007-2024 result is halved or zeroed post-2024 |
| Year instability | Mesfin: gap-continuation short +14.5 / -11.9 / +10.3 by year; VVG reversal +8.4 (2024) / -22.8 (2025) | require same sign in each OOS year |
| Overfitting / selection | Brusco: quarterly walk-forward reselection Sharpe 0.57 vs 0.92 fixed; Build Alpha: parameter spike vs plateau (RSI-14 ES example Sharpe 1.2 alone, 0.2-0.9 neighbours = spike), Monte Carlo permutation ("a large percentage of good-looking backtests fail"); Mesfin RTH control searched 53+ combos; Swanson: five stacked filters leave 80 of 1,000 trades | +/-10% parameter plateau, permutation p < 0.05, Deflated Sharpe |
| Too few trades per period | Mesfin: 35 trades over three OOS years cannot pass; nq-strategy-b 47 trades in 4 months | >= 30 trades per OOS fold |
| Tiny stops | kjw616: median stop 2.34 MNQ pts ($4.69) vs $4 friction | stop must be >> 2x round-trip cost |
| Idealised stop fills | Mesfin and marcwong both flag "filled at exact stop price" as idealised; gap-through stops at next open | fill stops at worse of stop price / next bar open, +1 tick |
| Population base rate | Chague et al. 2019 (Brazilian index futures day traders, 300+ days): 97% lose after fees, 1.1% earn more than minimum wage, 0.5% more than a bank teller; best trader $310/day with daily SD $632-3,308 | the typical result of discretionary day trading is a loss |
| Overnight vs intraday drift | Robot Wealth (SPY 2000-2024): most cumulative return and most big losses occur overnight; intraday drift small. Local: ES RTH open-to-close annualised +7.3% (2025), +6.5% (2026) vs overnight +8.2% / +10.3% | no free long bias inside RTH; a day-only system must earn its edge |
| Low-vol dead zones | Gary Hart: systems idle up to 3 months; local: ES RV 8.9% in 2025Q3 (lowest of 2022-26) | gate on ATR/VIX; expect multi-week flat spells |

Additional live-divergence items (from the GitHub execution models and Davey/Build Alpha): bar-level approximation of intrabar stop/target order (worst-case: assume stop hit first when both are inside one bar); continuous-contract roll jumps if not back-adjusted (Mesfin uses raw concatenation, our data are index proxies with no rolls but with a basis vs the futures); data-feed differences (brusco: Alpaca IEX ~3% of consolidated volume, VWAP approximated; still correlated 0.97 with IB ES); stale/missing bars (our 2023 proxy data has only 172-184 RTH days - treat 2023 statistics with care).

---

## 4. Realistic cost assumptions for MES / MNQ / MGC at Lucid

**Published commissions (Lucid, per side, all platforms)**: ES and NQ $1.75; MES and MNQ $0.50; CL $2.00; GC $2.30; currencies $2.40; grains/livestock $2.80 (spicyfutures.com review of Lucid, 2026). MGC not listed; assume $0.50-0.75. Platforms: Rithmic feed (Sierra, Quantower, MotiveWave, ATAS, Bookmap, MultiCharts, R Trader Pro) or CQG feed (NinjaTrader, Tradovate, TradingView). Retail comparison: NinjaTrader/Tradovate list $0.39 (free plan) / $0.29 / $0.09 per side for micros plus exchange, clearing and NFA fees (CME micro E-mini exchange fee is roughly $0.35 per side plus NFA $0.02 - the fee page itself could not be fetched; treat as approximate). So Lucid's $0.50 is in line with retail all-in micro pricing.

**Slippage evidence**: Mesfin uses 2.0 MNQ pts ($4.00) round trip for spread + fees + slippage on 5-min bar signals (and 0.5 MGC pts = $5); marcwong uses 1 tick per side + $1.50/side; brusco models ES at 0.25 bps (~0.17 ES pts at 6,700) and tested 1-tick slippage; nq-strategy-b expects a 1.5-2.5x haircut to backtest P&L from slippage and erosion; Zarattini ORB replications break even at 2.2 c/share (~1 ES tick-equivalent) of entry slippage.

**Local bar-size context (RTH, 2025-01 to 2026-09)**: median 1-minute range 2.45 ES pts (~10 ticks) and 12.3 NQ pts (~49 ticks); by hour the mean 1-min range is 4.6 ES / 26.9 NQ in the 09:xx hour, 3.8 / 20.5 at 10:xx, 2.6-2.8 / 12-13 pts from 12:00 to 15:xx. Median RTH daily range 56 ES / 263 NQ pts in 2025, 61 / 366 in 2026. Mean |close-open| 36 ES / 167 NQ (2025), 33 / 195 (2026).

**Recommended simulator defaults (per contract)**:

| Item | MES | MNQ | MGC |
|---|---|---|---|
| Tick | 0.25 pt = $1.25 | 0.25 pt = $0.50 | 0.10 = $1.00 |
| Commission per side (Lucid) | $0.50 | $0.50 | $0.60 (assumed) |
| Slippage per market/stop fill, RTH 09:31-15:59 | 1 tick ($1.25) | 1 tick ($0.50) | 1 tick ($1.00) |
| Slippage 09:30:00-09:31, 08:30/10:00/14:00 (+/-2 min), ETH | 2 ticks | 2-3 ticks | 2 ticks |
| Limit fills | only if price trades through limit by >= 1 tick | same | same |
| Round trip all-in, base case | ~$3.50 (0.7 pt) | ~$2.00 (1.0 pt) | ~$3.20 |
| Stress case (Mesfin floor) | $7.00 (1.4 pt) | $4.00 (2.0 pt) | $5.00 (0.5 pt) |

Rule of thumb from the evidence: a system is not deployable unless mean gross P&L per trade >= 2x the stress-case round trip (>= 2.8 MES pts, >= 4 MNQ pts, >= 1.0 MGC pt) and the median stop is >= 5x the round trip.

**Sources**: https://spicyfutures.com/lucid-trading-review/ ; https://www.tradovate.com/pricing/ ; https://www.ninjatrader.com/pricing/ ; https://arxiv.org/abs/2605.04004 ; https://github.com/marcwong515-art/futures-backtester ; https://github.com/giovannibrusco/zarattini-2024-momentum-spy ; https://github.com/prashanthaitha24/nq-strategy-b-bot ; local bar statistics.

---

## 5. The ES / NQ volatility regime 2025-2026 (computed from workspace data)

Quarterly realised volatility (annualised, from daily closes), average daily range in % of close, trend-day fraction (|close-open| / (high-low) > 0.7), lag-1 autocorrelation of daily returns, and VIX:

| Quarter | ES RV % | ES range % | ES trend-day | ES ac1 | NQ RV % | NQ range % | NQ trend-day | NQ ac1 | VIX mean (min-max) |
|---|---|---|---|---|---|---|---|---|---|
| 2022 Q1-Q4 | 21-29 | 2.0-2.5 | 0.20-0.34 | -0.06..0.16 | 28-38 | 2.6-3.4 | 0.25-0.34 | -0.15..0.10 | 25-27 |
| 2023 Q1-Q4 | 11-17 | 1.1-1.7 | 0.19-0.27 | ~0.0-0.09 | 16-23 | 1.5-2.2 | 0.21-0.27 | ~0.0-0.06 | 15-21 |
| 2024 Q1-Q4 | 11-16 | 1.0-1.4 | 0.14-0.27 | -0.07..0.14 | 15-24 | 1.4-2.0 | 0.16-0.27 | -0.05..0.10 | 14-17 (Aug spike 38.6) |
| 2025 Q1 | 17.3 | 1.55 | 0.21 | -0.19 | 23.9 | 2.09 | 0.25 | -0.20 | 18.6 (14.8-27.9) |
| 2025 Q2 | 30.0 | 2.21 | 0.26 | -0.08 | 35.3 | 2.66 | 0.23 | -0.12 | 23.6 (16.3-52.3) |
| 2025 Q3 | 8.9 | 0.90 | 0.22 | -0.23 | 11.3 | 1.17 | 0.22 | -0.17 | 16.0 (14.2-20.4) |
| 2025 Q4 | 13.0 | 1.21 | 0.16 | -0.01 | 18.4 | 1.66 | 0.25 | -0.11 | 17.8 (13.5-26.4) |
| 2026 Q1 | 14.0 | 1.53 | 0.11 | -0.10 | 17.9 | 2.01 | 0.18 | -0.08 | 20.5 (14.5-31.0) |
| 2026 Q2 | 13.5 | 1.30 | 0.31 | -0.08 | 22.6 | 2.04 | 0.34 | -0.10 | 18.3 (15.3-25.8) |
| 2026 Q3 | 11.4 | 1.01 | 0.22 | 0.01 | 20.0 | 1.78 | 0.22 | 0.06 | 16.1 (14.2-20.7) |

Intraday structure (1-minute proxies, RTH 09:30-16:00; annualised open-to-close drift; same-sign rates):

| Year | ES RTH drift %/yr | ES overnight %/yr | ES first30 -> last30 same sign | ES to-15:30 -> last30 | ES overnight -> RTH | NQ RTH drift | NQ overnight | NQ first30 -> last30 | NQ overnight -> RTH |
|---|---|---|---|---|---|---|---|---|---|
| 2022 | -1.7 | -17.8 | 48.2% | 55.0% | 52.6% | -7.5 | -27.6 | 49.4% | 57.0% |
| 2023 (partial data) | +25.6 | -1.5 | 49.4% | 48.3% | 47.1% | +32.5 | -4.0 | 48.4% | 46.7% |
| 2024 | -0.8 | +19.7 | 48.8% | 48.8% | 50.0% | -2.2 | +22.4 | 44.7% | 52.4% |
| 2025 | +7.3 | +8.2 | 48.6% | 47.0% | 44.9% | +5.9 | +13.6 | 50.2% | 45.3% |
| 2026 (to Sep) | +6.5 | +10.3 | 44.8% | 45.4% | 48.6% | +12.2 | +14.1 | 46.5% | 48.6% |

Reading: (1) 2025 had two regimes - a Feb-May tariff-driven vol spike (ES RV 30%, VIX to 52, 2-3% daily ranges) and an unusually quiet Jun-Dec (ES RV 9-13%, ranges ~1%); 2026 so far is mid-vol (ES 11-14%, NQ 18-23%) with VIX mostly 15-21 and a Q1 spike to 31. (2) Daily returns were **mean-reverting in 2025** (ac1 -0.19 to -0.23 outside Q2) and roughly uncorrelated in 2026; overnight -> RTH same-sign below 50% in 2025 (gap-fade tendency) - this is the environment in which the SPY/ES trend-following intraday momentum lost money. (3) Trend-day share ~0.2 in 2025-26 vs ~0.3 in 2022: four of five days are two-sided. (4) First-half-hour / rest-of-day momentum into the close is absent in both indices since 2023. (5) NQ carries roughly 1.5-1.7x the vol of ES and a larger 2026 range expansion (median RTH range +39% vs 2025) - NQ/MNQ offers more points per trade to pay costs, which is why most 2025-26 open-source work is on MNQ. Caveat: the 1-minute series are index/CFD proxies (SPXUSD, NSXUSD) with a 2023 data gap; the daily table uses Yahoo ES/NQ futures.

---

## 6. What the evidence says works in 2022-2026 (and what does not)

**Does not work (documented, with OOS numbers)**: bare ORB wick breakouts with next-bar or 1:1 exits (ORB report + Mesfin); fading or following overnight gaps on a clock (Mesfin gap fill, all three times negative); Asia-session breakout-bar continuation (T -11.5: the move is over by bar close); liquidity-grab fades (gross < friction); volume-spike/dry-up signals (needs volume anyway, and T -2 to -5); post-news drift after the spike bars; OU mean reversion on 5-min MGC; EMA crosses on MNQ after costs; ML classifiers on 4 years of 5-min OHLCV; first-half-hour -> last-half-hour and gamma-hedging close momentum on ES/NQ since 2023; the SPY/ES noise-area intraday momentum since 2025 (Sharpe -0.27 in 2025, -1.91 in 2026 YTD); any system with median stop < 10 MNQ pts or gross edge < 2 MNQ pts.

**Survived a walk-forward with costs (but with caveats)**: London-session GMM regime transition, long, 60-min hold, flat by 08:30 (T 4.30, 61.5% win, needs exact-bar entry, volume feature approximated); RTH confluence pullback with 65-min hold (T 3.11, heavy parameter search); the SMA200-filtered MNQ ORB with R-multiple exit and one-loss-per-session rule (ORB report: OOS 2023-26 Sharpe 1.10, PF 1.32); "London Reclaim" break-and-retest of the 02:00-08:00 range (ORB report: 2019-26 PF 1.26, Sharpe 1.44 with costs).

**Full-sample practitioner results covering 2025-26 that are at least objectively specified**: 5-min inverse-FVG-inside-15-min-FVG long-only 09:30-12:00, 2R target, flat 15:45 (2025: +$6,623 per MNQ, max DD $786, 57% win; no OOS). The whole ICT break-and-retest cluster (PDH, Asian range) has only unverified numbers.

**Design principles the evidence supports for the Lucid 50K**:
1. Trade NQ/MNQ or ES/MES with holds of 60-120 minutes (or to a fixed-dollar target) - not next-bar exits - so gross edge per trade (>= 4 MNQ / 1.5 ES pts) clears costs (Mesfin ceiling; Davey exit ranking).
2. Enter at the exact bar open after a signal, or with a resting limit at a pullback; never "wait for confirmation" of an expansion bar (the move is inside the bar).
3. Gate on volatility and day type: ATR/VIX floor (Hart), range-expansion forecast or persistence (Matswm86: 59-65%), and skip VVG-type days (top-tercile |gap| and |first-30-min return|: 78% reverse from the peak).
4. Prefer long-only in RTH for NQ-type setups (nq-strategy-b: 56.5% vs 42.5% win), but do not rely on intraday drift (RTH drift is +6-7%/yr for ES, overnight carries the premium).
5. Fixed-dollar or R-multiple targets and daily caps: Davey's ranking plus the Lucid payout rule (5 days >= $150) and eval consistency rule favour many $150-600 days over a few $1,500 days. With a 57% win / 2R system at 3 MNQ, median winning day is ~$150-300; cap daily loss at $300-400 and stop after one loss per session (ORB report) so a 6-day losing streak costs < $2,000.
6. Validate exactly the Mesfin way on our own data: train 2010-2022 or 2021-2024, test each of 2023/2024/2025/2026 separately, demand positive net in each, >= 30 trades per year, +/-10% parameter plateau, permutation p < 0.05, Deflated Sharpe for the number of variants tried; then haircut the result by 1.5-2x before sizing (nq-strategy-b author's own expectation).
7. Expect long flat spells: 2025Q3 and 2026Q3 ES realised vol was 9-11%; a system that forces trades then will bleed the $2,000 drawdown.

---

## 7. Source list

- Mesfin M. (2026) Structural Limits of OHLCV-Based Intraday Momentum Signals in MNQ Futures, arXiv:2605.04004v3 - https://arxiv.org/abs/2605.04004
- Mesfin M. (2026) A Validated Volatility-Volume-Gap Classifier for Regime Identification in MNQ, arXiv:2605.11423v3 - https://arxiv.org/abs/2605.11423
- Mesfin M. (2026) Sequential Structure in Intraday Futures Data: LSTM vs Gradient Boosting on MNQ, arXiv:2605.17724 - https://arxiv.org/abs/2605.17724
- Zarattini, Aziz, Barbon (2024) Beat the Market: An Effective Intraday Momentum Strategy for the S&P500 ETF (SPY) - https://concretumgroup.com/beat-the-market-an-effective-intraday-momentum-strategy-for-sp500-etf-spy/ ; SSRN 4824172
- giovannibrusco (2026) Independent replication and OOS validation of Zarattini 2024 on SPY and ES - https://github.com/giovannibrusco/zarattini-2024-momentum-spy
- PazSheimy (2026) Independent OOS replication of Zarattini 2025 SPY intraday momentum - https://github.com/PazSheimy/spy-intraday-momentum-oos
- Gao, Han, Li, Zhou (2018) Market Intraday Momentum, JFE 129(2) - https://ideas.repec.org/a/eee/jfinec/v129y2018i2p394-414.html
- Baltussen, Da, Lammers, Martens (2021) Hedging Demand and Market Intraday Momentum, JFE 142(1) - https://ideas.repec.org/a/eee/jfinec/v142y2021i1p377-403.html
- Concretum Research papers index - https://concretumgroup.com/papers/ ; VWAP paper - https://concretumgroup.com/volume-weighted-average-price-vwap-the-holy-grail-for-day-trading-systems/
- CXO Advisory critique of the ORB day-trading paper - https://www.cxoadvisory.com/technical-trading/day-trading-with-an-opening-range-breakout-strategy
- QuantConnect replication of stocks-in-play ORB - https://www.quantconnect.com/research/18444/opening-range-breakout-for-stocks-in-play/
- prashanthaitha24 (2026) NQ Strategy B (FVG) - https://github.com/prashanthaitha24/nq-strategy-b-bot
- asiatrada (2026) NQ/MNQ multi-strategy bot - https://github.com/asiatrada/algorithmic-trading-bot
- kjw616 (2026) MNQ strategy research with walk-forward - https://github.com/kjw616/mnq-strategy-research
- marcwong515-art (2026) MNQ/MGC S/R breakout backtester with execution model - https://github.com/marcwong515-art/futures-backtester
- Matswm86 (2026) MNQ/MGC morning brief with walk-forward range forecasts - https://github.com/Matswm86/mwm-morning-brief
- Kevin Davey, KJ Trading Systems: exit study - https://kjtradingsystems.com/algo-trading-exits.html ; walk-forward - https://kjtradingsystems.com/walkforward-testing-for-algorithmic-trading.html ; after-backtest process - https://kjtradingsystems.com/monte-carlo-simulation.html ; why AI strategies fail - https://kjtradingsystems.com/why-most-ai-strategies-fail.html
- Build Alpha: Monte Carlo permutation - https://www.buildalpha.com/monte-carlo-permutation/ ; parameter permutation (plateau vs spike, ES RSI example) - https://www.buildalpha.com/parameter-permutation-test/ ; noise test - https://www.buildalpha.com/noise-test/
- Better System Trader: ep. 085 Gary Hart intraday futures - https://bettersystemtrader.com/085-intraday-trading-strategies-gary-hart/ ; ep. 162 Kevin Davey entries/exits - https://bettersystemtrader.com/162-building-effective-entries-and-exits-kevin-davey/ ; ep. 196 Jeff Swanson independent filter testing - https://bettersystemtrader.com/196-how-to-avoid-curve-fitting-using-independent-testing-jeff-swanson/
- Robot Wealth, overnight vs intraday equity returns (2024 update) - https://robotwealth.com/revisiting-overnight-vs-intraday-equity-returns/
- Chague, De-Losso, Giovannetti (2019) Day Trading for a Living? (statistics via https://en.wikipedia.org/wiki/Day_trading)
- Lucid Trading commissions and platforms - https://spicyfutures.com/lucid-trading-review/ ; retail micro pricing - https://www.tradovate.com/pricing/ ; https://www.ninjatrader.com/pricing/
- Unger Academy blog index (articles not retrievable) - https://ungeracademy.com/blog
- Local data computations: `data/parquet/SPXUSD_1m.parquet`, `NSXUSD_1m.parquet`, `ES_1d.parquet`, `NQ_1d.parquet`, `VIX_1d.parquet` (scripts run inline during this sweep; see sections 4-5 for the numbers).
