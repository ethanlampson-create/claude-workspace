# Family: Opening Range Breakouts and Session-Structure Strategies

Research sweep date: 2026-10-03. Scope: ORB variants (5/15/30/60-min, Crabel stretch ORB, Mark Fisher ACD, initial balance / first-hour breakout, London / NY / Asia / overnight session-range breakouts, prior-day high/low breakouts), published ORB research (Zarattini & Aziz 2023, Zarattini/Barbon/Aziz 2024, Tsai et al. 2019 TORB, Mesfin 2026 arXiv falsification), independent replications, and practitioner / vendor backtests on ES, NQ, MNQ, GC, CL. All times are US Eastern (ET).

Target use: Lucid Trading 50K LucidFlex (eval target $3,000; $2,000 END-OF-DAY trailing drawdown; 50% consistency rule in eval; funded: no consistency, EOD trailing locks at $50,100 after balance reaches $52,100; payout needs 5 days with >= $150 EOD profit; day-trade only). Data available to us: 1-minute OHLC without volume for ES/NQ/GC/CL proxies, 2010-11 to 2026-09.

---

## 0. Executive summary

1. **The raw, unfiltered ORB (enter on a wick break of the first N minutes, stop at the other side, 1:1 or fixed target, no filter) is NOT an edge in index futures after costs.** Evidence: Mesfin 2026 (arXiv 2605.04004) on MNQ 2021-2025 walk-forward: ORB long best case +2.82 pts/trade net, T=0.88, year-unstable; ORB short negative in every year; pullback entry 80.7% stop-out. TradingView "Winning-Day ORB" 18-year NQ run: PF 0.87, last 365 days PF 0.63. Quantified Strategies: ORB on S&P, GC, SI, CL "almost completely obsolete". mql5 replication of the Zarattini 5-min rule on NQ/SPX/Dow/DAX/FTSE 2015-2026: gross matches paper (+0.13R, 23% hit rate) but net of spread/slippage "no market is distinguishable from zero".

2. **What survives after costs are three things**: (a) **conditioning** the breakout on context (direction of the opening-range candle, range width vs ATR, overnight/London midpoint position, day-of-week, trend filter); (b) **close-based confirmation** instead of wick entries, which raises continuation from ~59-65% to ~63-72% (tradingstats, 6,142 days ES/NQ 2014-2026); and (c) **asymmetric, capped exits** (target 0.25x-0.5x of the range with stop at the far side, or EOD exits with a tight stop) rather than 1:1 brackets. The one independently walk-forward-tested ORB with a published OOS that stayed positive is the MNQ ORB with an SMA(200) daily trend filter, risk-reward multiple exit and one-loss-per-session rule (IS 2020-22 Sharpe 1.37, OOS 2023-02/2026 Sharpe 1.10, PF 1.32, MDD 12.8% on $10k with ~20x leverage).

3. **Session-range breakouts (overnight 18:00-09:30, London 02:00-08:00) have a strong, stable *directional* statistic**: when the NY/RTH open is above the session midpoint, the session high breaks first 76% (overnight) / 83% (London) of the time on NQ 2015-2025. These are not P&L results, but the only open-source strategy in this family with a long out-of-sample record and costs included, "London Reclaim" (MNQ, 2019-2026, 1,367 trades, PF 1.26, Sharpe 1.44, max DD $2,107 at $100 risk/trade), is built on exactly these levels with a break-and-retest entry and 3.5R target.

4. **Published academic ORB performance is dominated by things we cannot use**: the 2024 stocks paper's 1,637% / Sharpe 2.81 comes almost entirely from the relative-volume (stocks-in-play) filter (unfiltered 5-min ORB on the same universe: +29% total over 8 years, Sharpe 0.48). The 2023 QQQ paper assumes zero slippage; break-even entry slippage is 2.2 cents/share (GitHub replication), and 76% of its filtered P&L is from 2022.

5. **For the Lucid 50K rules the best-shaped candidates are**: ORB-30 with close confirmation and a 0.25-0.5x range target (high win rate, small per-day P&L, suits consistency rule); ORB-15/30 with SMA200 trend filter and 1.4-2.4R exits (lower win rate, needs micro sizing so a loss day is <= $300-400); London/overnight midpoint-bias breakouts traded in the 09:30-11:00 window with a time stop at noon; and the IB (first-hour) C-period confirmation trade. Anything with 10R targets or EOD-only exits produces a few huge days and many small losses, which fights the 50% consistency rule and the EOD trailing drawdown.

---

## 1. Canonical academic / published ORB rules

### 1.1 Zarattini & Aziz (2023) "Can Day Trading Really Be Profitable?" 5-minute ORB on QQQ

- **Origin**: SSRN 4416622, first published 2023-04-10; Concretum Research / Peak Capital Trading (Andrew Aziz, Bear Bull Traders).
- **Instrument / period**: QQQ (and TQQQ) 2016-01-01 to 2023-02-17; 1,795 trades (replication: 1,775).
- **Rules (Table 1 of the paper)**:
  - Range = first 5-minute bar 09:30-09:35.
  - If the first bar closed up, buy at the open of the second bar (09:35); if closed down, sell short at 09:35. No trade if the first bar is a doji (open ~ close). Note: this is a *direction-of-first-candle* entry at 09:35, not a stop-order breakout.
  - Stop = low (long) / high (short) of the first 5-minute bar. Distance = $R.
  - Target = 10 x $R, else liquidate at 16:00 close.
  - Size so a stop loss = 1% of equity, capped by 4x leverage: shares = int(min(0.01*A/$R, 4*A/P)).
  - Commission $0.0005/share; **no slippage**.
- **Results**: QQQ: total +675% ($25k -> $192.8k), annualized 31%, Sharpe 1.12, annualized alpha 33% (p=0.0025), beta ~0, win rate 24%, mean +0.13R/trade, 51% long / 49% short. TQQQ: +1,485%, Sharpe 1.18, 46% annualized, 0.18R/trade. Max daily loss capped near -1R.
  - **Sensitivity study**: stop = 5% of 14-day ATR and EOD exit (no target) gave +9,350% on TQQQ, alpha 93% - the authors themselves flag this as unrealistic because a 5%-ATR stop on TQQQ is ~$0.08 and slippage is ignored.
- **Replications / critiques**:
  - giovannibrusco GitHub replication: matched 1,775 trades and Sharpe 1.06, CAGR 30.4%; **P&L crosses zero at ~2.2 cents/share entry slippage**; ~75% of trades exit on the stop, ~22% flat at close, 10R hit on ~2-3%. Adding an NQ-futures 09:25 confirmation filter: t=2.05 but 76% of the P&L from 2022, loses money in 2017, 2020, early 2023; bootstrap Sharpe CI [0.05, 1.41] overlaps buy-and-hold.
  - mql5 replication on NQ, SPX, Dow, DAX, FTSE cash-index CFDs 2015-01 to 2026-06 (2,899-2,937 sessions each): gross +0.13R and ~23% hit rate reproduced on all five; after 0.8-4.0 points spread/slippage four of five are negative, NQ +0.002R. "The edge is the size of the spread."
  - CXO Advisory: idealised execution assumptions.
- **Evidence quality**: 4 for the gross effect (peer-style paper + two independent replications), **2 for net tradability on futures**.
- **Prop fit**: Poor as published. 24% win rate with 1R losses and rare 10R winners is the worst possible shape for a 50% consistency rule and an EOD trailing drawdown: a long losing streak of 1R days is typical, and the few winning days are huge. Could only be used with the EOD-exit variant and micro sizing, and the edge is within slippage on futures.
- **Sources**: https://papers.ssrn.com/abstract=4416622 ; https://concretumgroup.com/can-day-trading-really-be-profitable/ ; https://github.com/giovannibrusco/zarattini-2023-orb-qqq ; https://www.mql5.com/en/blogs/post/776235 ; https://www.cxoadvisory.com/technical-trading/day-trading-with-an-opening-range-breakout-strategy

### 1.2 Zarattini, Barbon & Aziz (2024) "A Profitable Day Trading Strategy for the U.S. Equity Market" (stocks in play, 5/15/30/60-min ORB)

- **Origin**: SSRN 4729284, Swiss Finance Institute Research Paper 24-98, 2024; 7,000+ US stocks 2016-01-01 to 2023-12-31, 1-minute data.
- **Rules**:
  - Universe each day: open price > $5, 14-day average volume > 1,000,000 shares, 14-day ATR > $0.50.
  - Range = 09:30-09:35. Stop (entry) order at the 5-minute high if the first bar was bullish, at the 5-minute low if bearish; doji = no order.
  - Stop loss = 10% of 14-day ATR from fill. Exit at 16:00 if not stopped. No profit target.
  - Risk 1% of equity per position, max 4x leverage, commission $0.0035/share.
  - **Relative Volume (RV)** = volume in first 5 min / average first-5-min volume over the previous 14 days. Trade only RV >= 100% and only the top-20 RV stocks each day.
- **Results (Tables 1-3)**:

| Strategy | Total return | IRR | Vol | Sharpe | Hit ratio | MDD | Alpha |
|---|---|---|---|---|---|---|---|
| ORB base (no RV filter) | 29% | 3.2% | 6.6% | 0.48 | 41.4% | 13% | 3.3% |
| 5m ORB + RV top-20 | 1,637% | 41.6% | 14.8% | 2.81 | 48.4% | 12% | 35.8% |
| 15m ORB + RV | 272% | 17.4% | 12.2% | 1.43 | 44.7% | 11% | 16.9% |
| 30m ORB + RV | 21% | 2.3% | 11.1% | 0.21 | 42.4% | 35% | 2.8% |
| 60m ORB + RV | 39% | 4.1% | 10.2% | 0.40 | 42.3% | 21% | 4.4% |
| COMBO (equal weight) | 234% | 15.8% | 7.9% | 1.99 | 47.3% | 7% | 15.0% |
| S&P 500 | 198% | 14.2% | 18.3% | 0.78 | 54.9% | 34% | 0 |

  - Average P&L per trade rises monotonically with RV: ~0 below 100% RV, 0.08R above 100%, much higher above 30x.
- **Evidence quality**: 4 (large sample, net of commission, but no slippage and no explicit out-of-sample; QuantConnect replication of one year 2016 gave Sharpe 2.40).
- **Data requirements**: **needs volume** (relative volume) - cannot be reproduced on our OHLC-only futures data. The lesson that transfers: the edge concentrates in days with abnormal activity; on futures we can only proxy "in play" via opening-range width vs ATR, overnight gap size, or realised volatility of the first 5 minutes.
- **Prop fit**: not directly usable (single-name equities). The ORB-length ordering (5m >> 15m >> 60m > 30m) is for stocks with news; for index futures the tradingstats data show the opposite (longer ranges have higher continuation and far fewer double breaks).
- **Sources**: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4729284 ; https://www.wealth-lab.com/api/discussion/download/pdf/8007-ssrn-4729284-1-pdf ; https://www.quantconnect.com/research/18444/opening-range-breakout-for-stocks-in-play/ ; https://danfin.net/opening-range-breakout-research

### 1.3 Tsai et al. (2019) "Timely Opening Range Breakout (TORB)" on index futures

- **Origin**: IEEE Access vol. 7, pp. 32061-32071 (2019). Markets: DJIA, S&P 500, NASDAQ, HSI, TAIEX index futures, 1-minute data, 2003-2013.
- **Rules (standard interpretation)**: observe the range from session open to a "probe time" t; after t, buy a break above the probe-range high / sell a break below the low; exit at session close (no stop/target in the base version). The paper searches the probe time per market.
- **Results**: >8% annual returns with p < 3% in all five markets; best TAIEX 20.28%/yr. The optimal probe time is "relatively short in the U.S. market" (within ~5 minutes of the open per Zeiierman's summary) and long (up to ~200 min) in Asian markets. TORB signals aligned with foreign-institution order flow on TAIEX.
- **Evidence quality**: 4 (peer-reviewed) but period ends 2013, no transaction costs reported, and we could not access the full text (403s).
- **Prop fit**: the US finding (very short probe time, EOD exit) is essentially the Zarattini QQQ rule with no stop; EOD-only exits give fat-tailed daily P&L and no drawdown control - needs a stop and daily cap for a $2k EOD trailing account.
- **Sources**: https://www.semanticscholar.org/paper/4492a7792de759178a2110beaafce9a2fc3590b8 ; https://www.researchgate.net/publication/331076454 ; https://www.zeiierman.com/blog/profit-potential-with-torb-strategy-in-index-futures-trading

### 1.4 Mesfin (2026) "Structural Limits of OHLCV-Based Intraday Momentum Signals in MNQ Futures" (arXiv 2605.04004) - negative result for plain ORB

- **Data**: MNQ 5-minute RTH bars (aggregated from 1-min), 2021-12 to 2025-08, 947 days; friction 2.0 NQ points round trip ($4/micro); signal at bar close, fill at next bar open; expanding-window walk-forward (train 2022; OOS 2023, 2024, 2025-partial). Five pass criteria: T >= 2.0 on net returns, positive net after friction, consistent sign across OOS folds, >= 30 trades per fold, year stability.
- **ORB definition tested**: OR = 09:30-09:55 (first six 5-min bars). Entry on break; hold N bars.

| Variant | N (OOS) | Net pts/trade | T | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|
| ORB long, hold 1 bar | 447 | -0.82 | -0.82 | -2.11 | -1.54 | +6.11 |
| ORB long, hold 15 bars (75 min) | 447 | +2.82 | +0.88 | +2.43 | +7.04 | +15.05 |
| ORB short, hold 1 bar | 428 | -3.45 | -3.16 | -2.73 | -4.74 | -0.15 |
| ORB short, hold 15 bars | 428 | -2.16 | -0.58 | | | |
| ORB pullback entry (20-pt stop) | 83 | -4.44 | -1.27 | 80.7% stop-out rate | | |

  - Asia-session (20:00-02:00) range-expansion bars: all negative net. Gap-fill fades at 09:30/09:45/10:00: all negative. An unconditional "buy 09:30, exit bar 13" benchmark 2022-2024: -2.60 pts, T=-0.75.
  - Positive controls that pass: "RTH Confluence" (GMM regime + Markov gate + volume z-score, pullback entry, exit bar 13): OOS T=3.11, +11.82 pts, N=196 - **needs volume**; "London Session Signal B" (GMM on 15-min London bars 03:00-08:30, long on regime transition, exit 60 min or 08:30, 20-pt stop): OOS T=4.30, +4.09 pts, 61.5% win, N=247 - **needs volume features**, and a one-bar delay flips T to -2.78.
- **Takeaways for us**: in 2023-2025 MNQ, ORB **longs** with a ~75-minute hold are mildly positive and improving (+15 pts/trade in 2025 partial), ORB **shorts** lose consistently, pullback/retest entries into the range are bad, and a 2-point friction floor eats any 5-min-bar signal with < 2 pts gross.
- **Evidence quality**: 4 (walk-forward, costs, preprint not peer reviewed).
- **Sources**: https://arxiv.org/abs/2605.04004 ; https://arxiv.org/pdf/2605.04004

---

## 2. Classic ORB systems (books)

### 2.1 Toby Crabel ORB with "Stretch" (1990)

- **Origin**: Toby Crabel, *Day Trading with Short Term Price Patterns and Opening Range Breakout* (1990).
- **Rules**:
  - Noise_i = min(High_i - Open_i, Open_i - Low_i) on daily bars; Stretch = SMA(10) of Noise (Crabel) - oxfordstrat's test multiplies by 2.0.
  - Buy stop at Open + Stretch; sell stop at Open - Stretch; the first stop filled is the position, the other is the protective stop. One trade per day; if both fire = one loss, no reversal.
  - Exit: Crabel's base study exits at the close of the entry day (day trade). Crabel's finding: the earlier in the session the stop is hit, the higher the probability the trade is profitable at the close - so an entry-time cutoff (e.g., no entries after 10:30-11:00) is a standard filter.
  - Setup filters (Crabel's pattern library): NR4, NR7, inside day (ID), ID/NR4, 2-bar NR, Hook days, "Doji" days, gap days. NR7 and ID/NR4 precede range expansion and are the highest-probability ORB setups.
- **Evidence**: Crabel's original tables (1980s S&P, bonds, etc.) show 60-70% profitable-at-close after NR4/ID setups. oxfordstrat tested a swing version (hold 10 days, 6x ATR stop) on 42 US futures 1980-2013: positive before costs, "deteriorated significantly" with $50 RT commission/slippage, rating C. No modern ES-specific day-trade test with numbers found.
- **Parameters**: Stretch lookback 10 (range 5-20); multiplier 1.0 (Crabel) to 2.0; entry cutoff 10:30-11:30; exit at 15:55-16:00.
- **Data**: daily OHLC + 1-min for intraday fills. OK for us.
- **Evidence quality**: 3 (book + multiple independent tests, mostly old).
- **Prop fit**: Decent shape (stop = 2x stretch, roughly 0.4-0.6x daily range on ES = $300-700 per ES, so micros needed); EOD exit gives fat tails; NR7/ID filters make it ~2-4 trades/week, slow for a $3k target but fine for consistency.
- **Sources**: https://oxfordstrat.com/trading-strategies/narrow-range/ ; https://nexusfi.com/a/strategies/opening-range-breakout ; https://www.tradingview.com/script/hzvhXCy9-PumpC-Opening-Range-Breakout-ORB-Stretch-Range

### 2.2 Mark Fisher ACD (2002)

- **Origin**: Mark B. Fisher, *The Logical Trader* (Wiley 2002); MBF Clearing. Framework, not a mechanical system.
- **Rules (standard objective interpretation)**:
  - Opening range (OR): Fisher used ~20 min for S&P pit, 45 min for CL (CL 8:30 ET pit era; today 9:00-9:45 ET); common modern choices ES/NQ 15 min (09:30-09:45), CL 30-45 min from 09:00, GC 30 min from 08:20.
  - A-up = OR high + A; A-down = OR low - A, where A ~ 20-25% of the 5- or 10-day ATR (or 20-25% of 30-day average daily range). Book example for CL: A = 0.08, C = 0.13 ($/bbl).
  - **A-up confirmed** only if price holds above A-up for at least half the OR length (e.g., 7.5 min for a 15-min OR) - "the time rule". Enter long on confirmation; stop at the OR low or back below A-up; many use "the low of the confirmation bar".
  - Failed A: if an A-up fails and price trades to C-down (OR low - C, C > A), that is a C-down reversal (short) with stop above the OR. Fisher: "minimize risk by time, not by price".
  - Daily pivot range (3-day rolling pivots; narrow pivot ranges predict volatile sessions); number line scoring (A-up +1, A-down -1, neutral 0) for multi-day bias. Exit at session close.
- **Evidence**: anecdotal/practitioner; Fisher's statistics: 5-min OR is the high or low of the day ~15-18% of the time for CL, 10-min OR 17-23%. No rigorous public backtest found.
- **Evidence quality**: 2.
- **Prop fit**: time-confirmation reduces whipsaws vs raw ORB, stop size ~0.25-0.5x ATR; manageable with micros. Few signals per day, EOD exit.
- **Sources**: https://nexusfi.com/a/strategies/acd-trading-method ; https://www.elitetrader.com/et/threads/excerpts-from-the-1400-page-acd-method-thread-mark-fisher.377419/ ; https://www.tradingview.com/script/iwAJMMbv-ACD-Indicator-TradingFinder-M-Fisher-Pivots-Methodology-Signal

### 2.3 Larry Williams volatility breakout (open +/- fraction of prior range)

- **Origin**: Larry Williams, *Long-Term Secrets to Short-Term Trading* (1999) and earlier; widely cloned.
- **Rules**: buy stop at today's open + k x (yesterday's high - low), sell stop at open - k x range, k = 0.25 (WH SelfInvest default) to 0.5-0.7 (Williams used 0.5-0.7 with trend/day-of-week filters); exit at close (or next open). Filters: trend (close > SMA), day of week, "inside day"/NR.
- **Evidence**: vendor backtests "variable profits but none negative" (WH SelfInvest); no modern ES numbers.
- **Evidence quality**: 2.
- **Prop fit**: similar to Crabel; k=0.25 on ES with a ~60-pt daily range = 15-pt trigger and 30-pt stop-and-reverse width, too big for 1 ES; micros.
- **Sources**: https://whselfinvest.com/en-be/trading-platform/free-trading-strategies/tradingsystem/56-volatility-break-out-larry-williams-free

---

## 3. Modern ORB implementations with numbers (ES / NQ)

### 3.1 ORB with SMA(200) trend filter, R:R exit, one loss per session - "Backtests, Not Signals" (MNQ, walk-forward)

- **Rules**: OR = first N minutes after 09:30 (default 15 or 30 - article uses the standard 30-min OR). If daily close > SMA(200): longs only; below: shorts only. Entry on break of the range; stop = opposite side of the range, capped at 150 ticks (37.5 NQ pts); target = RR x stop distance, RR optimized 1.4-4.4 (step 0.2); stop trading for the day after one loss; force exit at session end. $10k account, ~20x leverage (1 MNQ-equivalent).
- **Results**: IS 2020-02-12 to 2022-12-30: +108.6%, Sharpe 1.37, MDD -10.9%, 451 trades, win 30.4%, PF 1.43. **OOS 2023-01-03 to 2026-02-27: +94.6%, Sharpe 1.10, MDD -12.8%, 474 trades, win 24.9%, PF 1.32.** Smooth heat-map across SMA 150-300 and RR 1.4-4.4.
- **Evidence quality**: 3 (independent, true OOS, but single author/blog).
- **Prop fit**: good drawdown shape (12.8% on $10k = ~$1,280 at ~1 MNQ... scale: 1 contract per $10k implies about 5 MNQ on $50k would give MDD ~$6k, so size 1-2 MNQ for a $2k EOD trailing). Low win rate (25-30%) means 3-5 losing days in a row are routine; daily loss is capped at one stop (<= 37.5 pts = $75/MNQ). The 50% consistency rule is OK because targets are capped at 1.4-2.4R.
- **Sources**: https://backtestsnotsignals.substack.com/p/opening-range-breakout-real-edge

### 3.2 ORB-30 with 5-minute close confirmation and capped target - tradingstats "conservative setup"

- **Data**: ES and NQ, 6,142+ days 2014-2026 (break/continuation statistics, not P&L).
- **Statistics**:

| | ES 5m | ES 15m | ES 30m | NQ 5m | NQ 15m | NQ 30m |
|---|---|---|---|---|---|---|
| Double-break rate | 74.3% | 61.0% | 47.9% | 69.2% | 52.6% | 39.4% |
| Continuation (wick entry; close in break direction) | 58.6% | 59.6% | 64.6% | | | ~67% |
| Continuation (5-min close confirmation) | 63.3% | 65.8% | 70.7% | 63.3% | 67.3% | 71.5% |
| Median range width (pts) | 5.5 | 8.5 | 11.0 | 26.5 | 40.25 | 51.5 |
| 1.0x extension hit by close | 64% | | 32-34% | 58% | | 26-28% |

  - Time to first break after 30-min OR: ES 52.7% within 5 min, 74% within 15 min.
  - Filters: ORB candle internal direction aligns with first break 77-80%; up-candle adds 3-7 pts continuation (NQ 30m up: 70.3%). Day of week: Monday best (ES 30m 68.2% cont., 41.3% double), Wednesday worst (61.3%, 54.7% double), Friday NQ 72.0%. Gap direction: negligible. ATR regime: negligible (within 1.7 pts). **Wide OR (> 0.6x ATR14): continuation 77.5% ES / 74.2% NQ, double-break 20.8%** (small sample).
  - Edge stability 2014-2025: "has not degraded" (ES 30m range 60.5-68.5% by year).
- **Recommended rules**: enter on a 5-min close beyond the 09:30-10:00 range; stop at opposite side (~11 ES / ~51.5 NQ pts); target 0.25-0.5x range; time stop: skip if no break by 10:30; expected win ~70%. Aggressive: wick entry on 5-min OR, stop 10.25 ES / 43.5 NQ, target 1.0x, ~58% win, time stop 10:00.
- **Evidence quality**: 3 (large sample descriptive statistics; no slippage or P&L).
- **Prop fit**: very good shape for consistency: small, frequent wins (0.25-0.5 x 11 pts = 2.75-5.5 ES pts = $137-275 per ES, $14-28 per MES); stop ~$550/ES, $55/MES. Needs 4-8 MES to make $150+/day, with a $220-440 worst day. Caveat: 0.25x target with an 11-pt stop is a 1:4 reward:risk; 70% win gives thin expectancy (0.7x2.75 - 0.3x11 = -1.4 pts!) - so the 0.5x target + partial profit management or a mid-range stop is required for positive expectancy. The engine must verify.
- **Sources**: https://tradingstats.net/orb-strategy-research/ ; https://tradingstats.net/orb-breakout-strategy-guide/

### 3.3 ORB-15 NQ, close-confirmed, 50%-range target, long-only in uptrend - Trade That Swing (Cory Mitchell)

- **Rules**: OR = 09:30-09:45. Entry on a 5-minute candle close outside the OR high (long) - long only when the trend is up; short rules were dropped. Stop = opposite side of OR, capped at $1,000 (50 NQ pts). Target = 50% of OR size. Skip if OR > 0.8% of price. One trade per day; if the first 5-min close is below the OR, no trade that day. Exclude Mondays and Thursdays (July 2026 update). Flat by close.
- **Results (backtest, ~1 year to Oct 2025, 1 NQ)**: +$43,310 on $10k, 114 trades, 74.56% win, PF 2.51, max DD $2,725; avg win ~$846, avg loss ~$987. Author warns monthly re-optimisation is needed and that it is "not set-and-forget".
- **Evidence quality**: 2 (vendor, in-sample, optimized day-of-week filters).
- **Prop fit**: with MNQ (1/10) the numbers become +$4.3k/yr per MNQ, DD $272, avg loss $99 - clean for a $2k EOD trailing with 3-5 MNQ; 75% win rate and 0.5x-range targets keep daily P&L small and even, good for the consistency rule.
- **Sources**: https://tradethatswing.com/opening-range-breakout-strategy-up-400-this-year/

### 3.4 ORB-5 ES, 50%-range target, 100%-range stop - edgeful

- **Rules**: OR = 09:30-09:35. Breakout entry above/below. Target 50% of OR; stop = 100% of OR (opposite edge) with $700 max loss; skip if OR > 0.55% of price; no long breakouts on Tuesday. 1 ES.
- **Results (6 months, 2025)**: +$10,825 on $10k (108%), 115 trades, 72.17% win, PF 1.62; DD not disclosed. Edgeful's NQ 15-min variant 2025-08-04 to 2026-08-03: +$85,230, 69.5% win, PF 2.21, 141 trades, max DD -$10,815 (1 NQ).
- **Evidence quality**: 2 (vendor, short window, optimized filters).
- **Prop fit**: 5-min ES OR median 5.5 pts: target 2.75 pts = $137/ES, stop 5.5 pts = $275/ES; 72% win on 1:2 gives +0.72x137 - 0.28x275 = +$22/trade before costs, thin: very sensitive to slippage (1 tick each side = $25). The NQ 15-min variant's $10.8k DD per NQ = ~$1,080 per MNQ: too close to $2k for more than 1 MNQ.
- **Sources**: https://www.edgeful.com/blog/posts/5-minute-opening-range-breakout-es-strategy ; https://x.com/edgeful/article/2085119983152153086

### 3.5 ORB-30 ES, 1.5x range target / 0.75x range stop (insigtrade)

- **Rules**: OR 09:30-10:00; stop orders at OR high/low; target 1.5 x OR width; stop 0.75 x OR width; exit by 15:45. Sharpe ~0.8 2021-2025 claimed. No other numbers.
- **Evidence quality**: 1.
- **Source**: https://insigtrade.com/blog/automated-futures-trading-strategies-that-work-in-2026

### 3.6 ORB-15 with fixed-dollar 1:1 bracket, close confirmation - TradingView "Winning-Day ORB" (negative evidence)

- **Rules**: OR 09:30-10:00 on 15-min bars; entry on candle close beyond the range during 10:00-15:00; one long and one short attempt per day; bracket $150 net target, 1:1 (or stop = % of OR width, target = multiple); $2.50/side + 1 tick slippage; flat 16:00.
- **Results**: NQ1! ~18 years: 48.0% win (2,096/4,364), PF 0.866, net negative; last 365 days PF 0.632 (44.5% win). ES last 365 days 57.1% win (n=338), MNQ 53.5%.
- **Takeaway**: an unfiltered symmetric bracket ORB loses after costs; the edge only appears with asymmetric exits and context filters.
- **Evidence quality**: 2 (open-source script, long sample, but TradingView fills).
- **Source**: https://www.tradingview.com/script/R3JrEIKY-Opening-Range-Breakout-Winning-Day-ORB-NQ-MNQ-ES-YM/

### 3.7 Capstone "NQ Open Range" (vendor system)

- Rules proprietary (opening-range trend capture in the morning). Hypothetical 2017-01 to 2026-10: net +$254,505, max DD $45,010, win 34.3%, PF 1.18, 2,423 trades, avg win $2,002 / avg loss -$885, avg trade $105, Sharpe 0.73, largest loss -$1,025 (1 NQ). Evidence 1-2. DD $4.5k per MNQ: fails the Lucid drawdown even at 1 MNQ.
- **Source**: https://capstonetradingsystems.com/products/open-range-nq

### 3.8 ORB double-break / failed-breakout reversal (second break)

- **Rules (standard)**: after the first break of the N-minute OR fails (price closes back inside the range) and then breaks the *opposite* side, enter in the second direction; stop beyond the failed extreme (or the OR midpoint); target 0.5x-1.0x range or EOD.
- **Statistics (tradingstats, ES/NQ 2014-2026)**: on double-break days the second break "wins" (close in its direction) 55.3% (5m), 63.9% (15m), 67.9% ES / 72.2% NQ (30m); median time between breaks 22-23 min (5m), 50-58 min (15m), 88-96 min (30m). Edgeful: ES 15-min double breaks = 66.9% of days (6 months to Nov 2024); 15-min NQ second-breakout entries 57% win, avg win 1.8R, avg loss 1.0R, ~+0.43R/trade (sample not disclosed).
- **Evidence quality**: 2-3 (descriptive stats; one vendor expectancy claim).
- **Prop fit**: good for the consistency rule (frequent, medium-size trades, defined stop); it is the mirror image of the breakout and reduces the double-break problem on 5/15-min ranges.
- **Sources**: https://tradingstats.net/orb-strategy-research/ ; https://www.edgeful.com/blog/posts/the-opening-range-breakout-orb-trading-strategy

### 3.9 ORB break-and-retest (midpoint retest)

- **Rules (QuantCrawler script)**: OR = first 15 minutes; breakout confirmed by a close beyond the range by X ticks; wait for a pullback to the OR midpoint (or OR edge); enter on touch; stop beyond opposite side; session end 16:00; resets after each signal. No published statistics; Mesfin 2026 found a pullback entry into the range stopped out 80.7% of the time on MNQ, and the London Reclaim repo found retest entries help on session levels. Treat as unproven.
- **Evidence quality**: 1.
- **Source**: https://www.tradingview.com/script/KxfvieAq-QuantCrawler-ORB-Break-Retest-15m-Opening-Range-Strategy

### 3.10 ORB length comparison on equities (orbsetups.com, 614 symbols, 2024-12 to 2026-03)

- 5-min 53.8% win, 15-min 51.0%, 30-min 49.4% (full target = full stop = range width). Half-target/full-stop: 68.9% win on 5-min. Highest expectancy: 15-min full/full ($0.044/trade). Long breakouts ~2x the average P&L of shorts. Equities only; evidence 2.
- **Source**: https://orbsetups.com/research/5-minute-vs-15-minute-vs-30-minute-opening-range-which-timeframe-has-the-best-win-rate/

---

## 4. Initial balance / first-hour strategies

### 4.1 Initial Balance (09:30-10:30) breakout and extension - Dalton / Market Profile

- **Origin**: Peter Steidlmayer / James Dalton (*Mind over Markets*, *Markets in Profile*). IB = first hour range (A and B 30-min TPO periods).
- **Statistics (tradingstats, ES 2,686 days and NQ 2,833 days, 2015-01-05 to 2025-12-29)**:
  - Any IB break by close: ES 97.8%, NQ 96.2%; single up 38.3/40.6%, single down 30.9/33.0%, double 28.7/22.6%.
  - Width tiers (vs ATR14): narrow < 0.5x ATR: 98.7% break, median extension 74.8% of IB (ES); extreme > 1.5x ATR: 66.7% break, 22.3% extension.
  - Extension ladder ES by close: 25% ext 52.0% up / 47.3% down; 50% ext 38.2/36.5%; 100% ext 18.8/20.5%; 150% 8.1/11.6%; 200% 4.4/7.1%.
  - First break timing: 65.2% in C period (10:30-11:00), 15.3% D, 7.1% E; < 10% after 13:30.
  - **C-period confirmation**: if the 10:30-11:00 bar closes above the IB high, ES reaches 100% up-extension 45.5% (vs 18.8% unconditional), NQ 33.2%; below IB low: ES 50.0%, NQ 41.7%. C closes inside IB ~66% of days (no trade).
  - IB formed high first -> single down break dominates (ES 44.8%); low first -> single up (ES 52.5%).
  - Retracement after break: shallow (< 25%) -> 93.8% close in break direction, 0% doubles; deep (>= 50%) -> 24.8% close in direction, 52.7% double.
  - Median MAE from break: ES 7.25 pts up / 9.0 down (~0.2-0.26 x ATR); median MFE 8.25 / 9.75. First break fails (closes back inside) 34% of the time; downside breaks fail 53% vs upside 45%.
  - Day of week: Wednesday highest breakout conviction (98.5%, 68.4% median ext.) but also highest double rate (36.8%).
- **Standard objective rules** (two variants):
  - IB-C confirmation: at 11:00, if the 10:30-11:00 30-min bar closed outside the IB, enter in that direction; stop at IB midpoint (~0.5 IB) or 0.25 x ATR; target 50-100% IB extension; flat 15:55.
  - IB narrow-range breakout: if IB width < 0.5 x ATR14, stop orders at IB high/low from 10:30; stop opposite side or midpoint; target 50% extension; cancel after 12:00.
- **Evidence quality**: 3 (large-sample statistics; no net P&L).
- **Prop fit**: IB width on ES ~0.5-1.0 x ATR (30-60 pts in 2025) means a full-range stop of $1,500-3,000/ES: must use midpoint stops and MES. Few trades (~1/day), later-session exposure (11:00-15:55). Suits "safe" configuration with 2-4 MES.
- **Sources**: https://tradingstats.net/initial-balance-breakout-statistics/ ; https://tradingstats.net/initial-balance-retest-statistics/ ; https://www.tradingview.com/script/UYVre3kq-Initial-Balance-Breakout-Extension-Statistics-ES-NQ/

### 4.2 thinkorswim "FirstHourBreakout" (reference implementation)

- Rules: 09:30 check overnight volume > 5-day average (volatility bias; **needs volume** - optional via `use filter`); 10:30 record first-hour high/low; 10:45-15:45 buy stop above high / sell stop below low; close all at 16:15 (adjust to 15:55 for prop). No published stats. Evidence 1.
- **Source**: https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/E-K/FirstHourBreakout

---

## 5. Session-range breakouts (overnight / London / Asia)

### 5.1 Overnight (Globex 18:00-09:30) range breakout with midpoint bias

- **Statistics (tradingstats, NQ 2015-01-02 to 2025-12-30, 2,827 days)**: RTH breaks at least one overnight level 94.2% (only-high 38.7%, only-low 32.6%, both 22.9%, none 5.8%). High first 54.1% unconditional. **RTH open above ON midpoint -> ON high breaks first 76.2% (n=1,605); below -> low first 75.6% (n=1,211).** Median time to first break 11 minutes (09:41); 68.7% within 30 min, 81.1% within 60 min; 33.5% in the first 5 minutes. Conditional sweep (other side also breaks) 24% (tiny gaps 32.3%, large gaps > 0.69% 12.9%). Large gap + above midpoint: 81.9% high first; + below: 84.1% low first. Tuesday + below midpoint + gap down: 99.1% break, 75.5% low first (n=222).
- **Standard objective rules**: at 09:30 compute ON high/low/mid (18:00-09:29 1-min bars). Bias = side of midpoint. Place a stop order at the biased ON level (if not already beyond it; if the open is already outside the ON range, use the first-5-min pullback or skip). Stop = ON midpoint or 0.5 x ATR5-min x k; target = 0.5-1.0 x ON range beyond the level (median penetration beyond London levels on NQ is 42-46 pts); time stop 11:00-12:00; flat 15:55. Skip if the open is > 1 ON-range beyond the level (exhaustion).
- **Evidence quality**: 3 (descriptive).
- **Prop fit**: good: early-session trades, defined level, 76% directional accuracy; risk is the 24% sweep. Works on ES/NQ/GC/CL from OHLC only.
- **Sources**: https://tradingstats.net/overnight-high-low-breakout-strategy/

### 5.2 London session (02:00-08:00) range breakout at 08:00 with midpoint bias

- **Statistics (tradingstats, NQ 2015-2025, 2,839 days, 1-min)**: break of a London level during 08:00-16:00 98.4% (AM only 97.0%); high first 53.9%. **NY open (08:00) above London midpoint -> London high first 82.7% (n=1,232); below -> low first 82.4% (n=823)**; at midpoint no edge. Median time to first break 58 min (~08:58); 75th percentile before 09:35. Median penetration 41.6 pts above high / 45.8 below low (75th pct 95.8 / 112.5). Sweep both sides 45.7% full day (34.7% AM only). London closed up -> NY breaks high first 72.4%; closed down -> low first 67.7%. Monday cleanest (38.7% sweep), Friday worst (51.1%).
- **nqstats ALN (NQ 2016-2025, 2,542 sessions)**: Asia 20:00-02:00, London 02:00-08:00, NY 08:00-16:00. "Partial engulf up" (41% of days): NY breaks London high 80.8%; "partial engulf down" (30%): breaks London low 75.0%; Asia engulfs London (6.9%): breaks both 56%.
- **Standard objective rules**: at 08:00 mark London H/L/mid; if price above mid, buy stop at London high (or at 09:30 if not yet broken, enter on the first 5-min close above); stop beyond opposite London level capped at 0.5 x range or a fixed 40-50 NQ pts; target 1.0 x median penetration (~45 NQ pts) or 0.5 x London range; exit at 12:00 to avoid the 46% sweep-both risk. For our day-trade-only account, trades can only be taken 09:30-15:55 (Lucid day session), so entries before 09:30 are not available: use the 09:30 open vs London midpoint as the bias and treat not-yet-broken London levels as the trigger.
- **Evidence quality**: 3 (descriptive).
- **Sources**: https://tradingstats.net/london-breakout-strategy/ ; https://nqstats.com/aln_sessions.html

### 5.3 "London Reclaim" MNQ/NQ breakout-and-retest on London and PDH/PDL levels (open source, costs included)

- **Origin**: GitHub AskElira/london-reclaim (2026), research only.
- **Rules**: London session 02:00-08:30 high/low; previous-day high/low (18:00 session cut). Entry windows 09:30-11:00 and 13:30-15:30; flat 15:55. A "sweep" = price trades beyond a level; then wait for a confirmed 3-bar pullback swing; place a stop order 1 tick beyond the breakout extreme (retest-continuation entry). Stop = 1 tick beyond the pullback swing extreme, must be <= 45 NQ pts; target 3.5R. Max 4 trades/day (one per direction per level); afternoon window skips levels already swept in the morning. 1-min bars; 1 tick slippage; $0.37/side; $100 fixed risk/trade; $50k start.
- **Results**: 2019-05-06 to 2026-08-24: 1,367 trades, PF 1.26, Sharpe 1.44, win 32%, max DD $2,107, +$19,029 (+38%, ~4.5%/yr at $100 risk). In-sample 2021-07 to 2026-07: 891 trades, PF 1.29, Sharpe 1.55, DD $1,512. OOS-pre 2019-05 to 2021-07: 470 trades, PF 1.21, Sharpe 1.31, DD $2,107. Avg win ~$211, avg loss ~$77.
- **Evidence quality**: 3 (open code, two periods, realistic costs; single author).
- **Prop fit**: closest fit in this family: day-trade only, 1-min OHLC only (no volume), DD $2.1k at $100 risk -> at $75 risk the max DD would be ~$1.6k, inside the $2k EOD trailing (EOD trailing is less punitive than intraday). Weakness: 32% win and 3.5R targets produce streaks of small losing days (consistency rule is fine because the largest day is ~3.5 x $75 x trades/day); ~190 trades/yr = slow eval (~+$2.8k/yr at $75 risk) - must scale risk to ~$150-200 for the "fast" config, which pushes DD to $3-4k. Use as a component, not alone.
- **Sources**: https://github.com/AskElira/london-reclaim

### 5.4 Asia session (19:00/20:00-02:00) range breakout

- Rules (common): mark Asia high/low; trade NY break with the London/overnight bias; TradingView "NY vs Asia Statistical Levels" classifies the 08:00 open into 4 buckets (inside lower/upper half, above high, below low). No net P&L evidence; Mesfin 2026: Asia-session range-expansion bars are negative after friction (T = -4.9 to -11.5). Edgeful has "Asian range breakout" reports (no public numbers).
- **Evidence quality**: 1-2. Treat as a filter (ALN pattern), not a stand-alone strategy.
- **Sources**: https://www.tradingview.com/script/Yo04T1a0-NY-vs-Asia-Statistical-Levels/ ; https://nqstats.com/aln_sessions.html ; https://arxiv.org/abs/2605.04004

### 5.5 Mesfin "London Session Signal B" (reference only - needs volume)

- Long at next 15-min bar open after a clean GMM regime transition (Bearish Chop -> Bullish Drift) on 03:00-08:30 London bars; exit 60 min or 08:30; 20-pt stop; walk-forward OOS N=247, +4.09 pts net, T=4.30, 61.5% win. Needs volume z-score and a fitted GMM; trades before 09:30 (not allowed on our account). Catalogued for completeness; evidence 4 but unusable.

---

## 6. Prior-day high/low and daily-range-based breakouts

### 6.1 Previous-day high/low (PDH/PDL) breakout / target

- **Statistics (edgeful, last-12-month windows)**: if NQ opens inside yesterday's range, ~75% chance it tests PDH or PDL; open above yesterday's midpoint -> PDH touched 67%, below -> PDL 58%. If price opens above PDH / below PDL, "almost 100%" chance it trades back into yesterday's range at some point (ES). Inside-day (daily bar inside prior day): next-day breakout of the inside day's range 87.8% ES (65/74), 88.4% NQ (61/69) during NY session (6-month sample). YM: 81% green when PDH breaks, 63% red when PDL breaks (sample unspecified).
- **Standard rules**: (a) breakout: stop order at PDH/PDL once broken by a 5-min close, stop 0.3-0.5 x ATR, target 0.5 x prior-day range, flat 15:55; (b) break-and-retest (tradezella 2026 ES/NQ H1 backtest: retest entry has lower win rate but higher expectancy than fading; both degrade sharply on FOMC/NFP days); (c) PDH/PDL as the *target* for an ORB or midpoint-bias trade (edgeful).
- **Evidence quality**: 2.
- **Prop fit**: fine as a level/target set; as a raw breakout the "100% re-entry" statistic means a plain PDH break is a poor momentum signal - prefer PDH/PDL as targets or as part of the London Reclaim retest logic.
- **Sources**: https://www.edgeful.com/blog/posts/inside-day-in-trading-breakout-data ; https://edgeful.com/blog/posts/ultimate-bullish-setup-trading-NQ ; https://www.tradezella.com/strategies/break-retest ; https://r.til.io/r/FuturesTrading/comments/1bxkwdr/

### 6.2 NR7 / inside-day filtered ORB (Crabel pattern filter)

- **Rules**: trade the N-minute ORB (or Crabel stretch ORB) only on days after an NR7 (today's range the narrowest of the last 7), NR4, inside day, or ID/NR4; prior-day-range contraction predicts range expansion. Stop opposite side; exit at close.
- **Evidence**: Crabel (1990) tables; edgeful inside-day break rates 88%; no modern net P&L. Evidence 2.
- **Prop fit**: raises signal quality, lowers frequency (~15-20% of days).

### 6.3 Gold ORB (relaxedtrader) and CL pit-open ORB

- Gold: buys a "statistically significant" new intraday high after the opening range, exits at the next session open (avg hold 1.5 days -> **overnight, not allowed**); backtest 2001-2015 / live 2016-2026: PF 1.69, CAGR 18.1%, win 57.1%, 531 trades, MDD 19.6% at $50k/contract. Evidence 2 (vendor). An EOD-exit adaptation on MGC would need re-testing.
- CL: pit-open ORB marks 09:00-09:15 high/low on 1-min; break with retest entry (CL breakouts "fail more often than index traders expect"); stop beyond range; no stats. Evidence 1.
- GC/CL ORB note: Quantified Strategies reports ORB on GC, SI, CL as negative in their backtests (as on S&P).
- **Sources**: https://relaxedtrader.com/store/gold-opening-range-breakout-trading-strategy/ ; https://damnpropfirms.com/trading-guides/opening-range-breakout-strategy-futures-traders/ ; https://www.quantifiedstrategies.com/opening-range-breakout-strategy/

---

## 7. Filters and exits catalogued across sources

| Filter / exit | Evidence | Effect |
|---|---|---|
| Close-based confirmation (5-min close beyond range) vs wick | tradingstats 2014-2026 | +4-6 pts continuation (ES 30m 64.6 -> 70.7%) |
| OR candle direction = break direction | tradingstats | 77-80% alignment; +3-7 pts continuation |
| Wide OR > 0.6 x ATR14 | tradingstats | continuation 77.5% ES / 74.2% NQ; doubles 20.8% (small n) |
| Narrow IB < 0.5 x ATR | tradingstats | 98.7% break, 74.8% median extension |
| OR size cap (0.55-0.8% of price) | edgeful, TTS | avoids huge stops; in-sample |
| Day of week | tradingstats, TTS, edgeful | Mon/Fri best for ES/NQ 30m continuation; Wed worst (chop); vendors drop Tue/Mon/Thu in-sample (fragile) |
| Daily trend SMA(150-300) one-directional | Backtests Not Signals | OOS Sharpe 1.10 retained; smooth parameter surface |
| Session midpoint bias (overnight / London) | tradingstats | 76% / 83% first-break direction |
| Gap size (> 0.69%) + midpoint | tradingstats | 82-84% direction, lower sweep (12.9%) |
| Relative volume (stocks in play) | Zarattini 2024 | Sharpe 0.48 -> 2.81 (equities; needs volume) |
| Longs only (index drift) | Mesfin 2026, orbsetups | ORB shorts negative every year on MNQ 2023-25; long P&L ~2x shorts on equities |
| One loss per session | Backtests Not Signals | part of OOS-validated spec |
| Time stop (no break by 10:00/10:30; exit by 12:00 for session levels) | tradingstats | majority of breaks occur in first 15-60 min; sweeps rise after noon |
| Target 0.25-0.5x range with far-side stop | tradingstats, TTS, edgeful | 70-75% win; requires checking expectancy vs. stop width |
| 1.4-2.4R target with far-side stop capped 150 ticks | BNS | 25-30% win, PF 1.3-1.4, OOS-validated |
| 3.5R target with swing stop <= 45 pts | London Reclaim | 32% win, PF 1.26, Sharpe 1.44 |
| 10R / EOD only | Zarattini | 24% win, fat right tail; slippage-fragile |
| Avoid FOMC/NFP/CPI days | tradezella, insigtrade | both PDH/PDL variants "degrade sharply" on event days |

---

## 8. What the evidence says works in 2022-2026 (and what does not)

**Does not work (net of costs) in 2022-2026 index futures**
- Plain wick-entry ORB with symmetric or fixed-dollar brackets (TradingView 18-yr NQ PF 0.87; last-365-day PF 0.63).
- ORB shorts on NQ/MNQ (negative in 2023, 2024, 2025; Mesfin).
- Retest/pullback entries back inside the opening range (80.7% stop-out, Mesfin).
- First-5-min-direction entries on index futures without a volume/"in play" filter: gross +0.13R reproduces but net ~0 on NQ/SPX (mql5 2015-2026; GitHub replication break-even at 2.2c/share on QQQ, P&L concentrated in 2022).
- Asia-session range-expansion momentum; gap-fill fades at 09:30-10:00 (Mesfin).

**Works, or at least holds up out of sample, in 2022-2026**
- ORB long with a longer hold (75 min) on MNQ: +2.4 / +7.0 / +15.1 pts net per trade in 2023/2024/2025 (not significant at T=0.88, but monotonically improving).
- ORB with daily SMA(200) directional filter + 1.4-4.4R exits + one-loss stop: OOS 2023-02/2026 Sharpe 1.10, PF 1.32, MDD -12.8% (MNQ).
- ORB-30 continuation statistics are regime-stable 2014-2025 (ES 30m 60.5-68.5% by year); close confirmation lifts to ~71%.
- Overnight / London midpoint bias: 76% / 83% first-break direction (2015-2025 full sample, including 2022-2025).
- London Reclaim (session-level sweep + retest, 3.5R): positive in both 2019-2021 and 2021-2026 windows with costs.
- Vendor in-sample results for 2025-2026 (NQ 15-min close-confirmed long-only ORB, 0.5x-range target: 70-75% win, PF 2.2-2.5) are consistent with the above direction but are curve-fit on day-of-week filters and should be expected to shrink by half out of sample.

**Implications for the Lucid 50K Flex backtests**
- Favor: close-confirmed ORB-15/30 longs (or trend-filtered both ways) with capped targets; overnight/London midpoint-bias breakouts in the 09:30-11:00 window with noon time stops; IB C-period confirmation trades; London Reclaim-style level retests with $75-150 fixed risk.
- Size in micros so one stop <= $150-250 and the worst plausible day (2 losses) <= $500 to keep the EOD trailing $2k alive through 4-6 losing days; the EOD (not intraday) trailing means intraday MAE is forgiving - only the close matters.
- For the 50% consistency rule: no single day may exceed $1,500 at the moment of passing a $3,000 target; cap daily profit (stop trading after +$600-800) or cap targets at 0.5x range. Avoid 10R/EOD-only exits in eval; they can be re-enabled funded (no consistency rule).
- For payouts (5 days >= $150): the high-win-rate capped-target variants (ORB-30 close-confirmed, TTS-style ORB-15) produce the most >= $150 days per month; the low-win-rate R-multiple variants produce fewer but larger days.
- Costs: use >= 1 tick slippage per side plus commissions ($1.5-2.5/side micro) in the engine; a 2-pt NQ / 0.5-pt ES friction floor killed most 5-minute-bar signals in the academic test.

---

## 9. Source list

- Zarattini & Aziz (2023) SSRN 4416622 - https://papers.ssrn.com/abstract=4416622 ; PDF mirror https://wealth-lab.com/api/discussion/download/pdf/6590-ORB-Strategy-pdf
- Zarattini, Barbon & Aziz (2024) SSRN 4729284 - https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4729284 ; PDF mirror https://www.wealth-lab.com/api/discussion/download/pdf/8007-ssrn-4729284-1-pdf
- Replications: https://github.com/giovannibrusco/zarattini-2023-orb-qqq ; https://www.mql5.com/en/blogs/post/776235 ; https://www.quantconnect.com/research/18444/opening-range-breakout-for-stocks-in-play/ ; https://danfin.net/opening-range-breakout-research ; https://www.cxoadvisory.com/technical-trading/day-trading-with-an-opening-range-breakout-strategy
- Tsai et al. (2019) IEEE Access TORB - https://www.semanticscholar.org/paper/4492a7792de759178a2110beaafce9a2fc3590b8 ; https://www.zeiierman.com/blog/profit-potential-with-torb-strategy-in-index-futures-trading
- Mesfin (2026) arXiv 2605.04004 - https://arxiv.org/abs/2605.04004
- Crabel ORB - https://oxfordstrat.com/trading-strategies/narrow-range/ ; https://nexusfi.com/a/strategies/opening-range-breakout
- Fisher ACD - https://nexusfi.com/a/strategies/acd-trading-method ; https://www.elitetrader.com/et/threads/excerpts-from-the-1400-page-acd-method-thread-mark-fisher.377419/
- tradingstats - https://tradingstats.net/orb-strategy-research/ ; https://tradingstats.net/orb-breakout-strategy-guide/ ; https://tradingstats.net/initial-balance-breakout-statistics/ ; https://tradingstats.net/overnight-high-low-breakout-strategy/ ; https://tradingstats.net/london-breakout-strategy/
- nqstats ALN - https://nqstats.com/aln_sessions.html
- Backtests Not Signals - https://backtestsnotsignals.substack.com/p/opening-range-breakout-real-edge
- London Reclaim - https://github.com/AskElira/london-reclaim
- Trade That Swing - https://tradethatswing.com/opening-range-breakout-strategy-up-400-this-year/
- edgeful - https://www.edgeful.com/blog/posts/5-minute-opening-range-breakout-es-strategy ; https://www.edgeful.com/blog/posts/the-opening-range-breakout-orb-trading-strategy ; https://www.edgeful.com/blog/posts/inside-day-in-trading-breakout-data
- TradingView scripts - https://www.tradingview.com/script/R3JrEIKY-Opening-Range-Breakout-Winning-Day-ORB-NQ-MNQ-ES-YM/ ; https://www.tradingview.com/script/KxfvieAq-QuantCrawler-ORB-Break-Retest-15m-Opening-Range-Strategy ; https://www.tradingview.com/script/iwAJMMbv-ACD-Indicator-TradingFinder-M-Fisher-Pivots-Methodology-Signal
- Others - https://capstonetradingsystems.com/products/open-range-nq ; https://insigtrade.com/blog/automated-futures-trading-strategies-that-work-in-2026 ; https://orbsetups.com/research/5-minute-vs-15-minute-vs-30-minute-opening-range-which-timeframe-has-the-best-win-rate/ ; https://relaxedtrader.com/store/gold-opening-range-breakout-trading-strategy/ ; https://damnpropfirms.com/trading-guides/opening-range-breakout-strategy-futures-traders/ ; https://quantifiedstrategies.substack.com/p/opening-range-breakout-trading-strategies ; https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/E-K/FirstHourBreakout ; https://whselfinvest.com/en-be/trading-platform/free-trading-strategies/tradingsystem/56-volatility-break-out-larry-williams-free
