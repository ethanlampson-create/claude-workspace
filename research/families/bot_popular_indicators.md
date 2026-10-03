# Family: Popular automated/bot and indicator strategies — what the evidence actually says

Research date: 2026-10-03. Scope: TradingView "top" strategies (Supertrend, UT Bot, Chandelier Exit, Hull MA / Hull Suite, Squeeze Momentum, Nadaraya-Watson, LuxAlgo, MACD/RSI combos, Heikin-Ashi trend, Ichimoku, Renko/range-bar scalps), NinjaTrader/Tradovate bot vendors (Goldilocks, Vector Algorithmics, NQ Pilot and similar), prop-firm-popular NQ scalping bots, and independent backtests on ES/NQ (QuantConnect, Quantitativo, LiberatedStockTrader test series, StockCharts SystemTrader, Oxford Strat, dev.to tick-level tests, GitHub "Strategy Myth-Busting" series).

Target context: Lucid Trading 50K LucidFlex. Eval target $3,000; $2,000 EOD-trailing max drawdown (breach checked intraday on open P&L); 50% consistency rule in eval (largest day <= 50% of total profit at pass); funded: no consistency, drawdown locks at $50,100 once EOD balance hits $52,100; payout needs 5 separate EOD days >= $150, cycle net positive, min $500, max 50% of profit capped $2,000; 4 minis / 40 micros in eval, 2 minis / 20 micros at funded start; no overnight. Backtest data: 1-minute OHLC (no volume) for ES, NQ, GC 2010-11 to 2026-09, prime window 2025-01 to 2026-09.

Method note: 11 web searches were completed before the session-wide search budget was exhausted; the rest of the sweep was done by directly fetching ~35 canonical pages (TradingView/LuxAlgo script pages, vendor pages, independent test write-ups, QuantConnect backtest caches, Trustpilot) and GitHub code search to pull exact Pine formulas and defaults. Several canonical pages (quantifiedstrategies.com main site, SSRN, Medium) were bot-blocked (403); their substack/mirror equivalents were used where available.

---

## 1. Executive summary

1. **No popular TradingView indicator strategy has credible, independent, after-cost evidence of a positive intraday edge on ES or NQ.** The best-documented independent tests of these indicators on intraday data (LiberatedStockTrader's 5-minute tests on Dow 30 stocks; dev.to tick-level Supertrend test on Gold/NZDUSD 2020-2026; Oxford Strat HMA on 42 futures 1980-2016) find win rates of 35-45%, profit factors of 0.86-1.10 outside strong trends, and results that live or die with the trend regime of the test window.
2. **Where these indicators "work" it is as slow trend filters on daily/weekly bars in trending markets** (Supertrend 10/3 weekly S&P 1960-2026: 68% win rate, 41 trades, 25% max DD; Supertrend daily NQ 2005-2026: 52.7% win rate, CAGR 4.6%, 34-day average hold). That regime is irrelevant to an intraday, flat-by-close prop account.
3. **The vendor-bot world is worse.** The only vendor with a verifiable live track record found (Aeromir Goldilocks, 2x MGC, Oct-2024 to Feb-2026) shows PF 1.32, 48% win rate, $45 average trade, and an $8,368 max drawdown that is 4.2x Lucid's $2,000 drawdown room. Vector Algorithmics ("70-80% win rates, 85% first-attempt pass rate") shut its website and Discord; Trustpilot reviews report 50% account losses and prop accounts closed for bot use.
4. **Three structural failure modes make most of these indicators unsuitable for Lucid Flex**: (a) always-in-the-market flip logic (Supertrend, UT Bot, Chandelier, Hull, HA) produces long losing strings in chop; (b) synthetic-bar strategies (Heikin-Ashi, Renko, range bars) show inflated backtests because fills happen at synthetic prices (NinjaTrader support, EliteTrader and pine-script maintainers all document this); (c) repainting (Nadaraya-Watson default mode, LuxAlgo signals) means published hit rates cannot be reproduced live.
5. **What does have real evidence for intraday ES/NQ 2018-2025**: the intraday "noise-area" momentum breakout (Zarattini-Aziz-Barbon SPY paper; Quantitativo's ES/NQ replication with Databento 1-minute data, $2.25/side costs, 0.5-tick round-trip slippage): NQ Sharpe 1.67, 24.3% annual return, 24% max DD on a 3% vol target, 38% win rate, payoff 2.25, 65% positive months; flat 2010-2017, real edge 2018 onward. It is codeable from 1-minute OHLC only. This is the benchmark the indicator strategies should be measured against, and the only one in this family worth carrying forward as a core candidate; a session-filtered Supertrend/UT-Bot trailing exit may be useful only as an exit mechanic on top of it.
6. Prop-fit rule of thumb used throughout: with $2,000 drawdown room and a $3,000 target, any strategy whose historical max drawdown on 1 mini (or 10 micros) exceeds ~$1,200-1,500, or whose typical single winning day exceeds ~$1,200, will either blow the drawdown or violate the 50% consistency rule. Most trend-flip indicators fail on the first criterion; most "scalp bots" fail on cost drag.

---

## 2. Strategy sections

Evidence quality scale: 1 = anecdote / vendor claim; 2 = single self-reported backtest, no costs or synthetic bars; 3 = independent backtest with costs, one market/period; 4 = multiple independent tests with costs across markets/periods; 5 = peer-reviewed plus multiple independent OOS replications.

### 2.1 Supertrend (10, 3) trend-flip, always in the market

- **Origin**: Olivier Seban; TradingView built-in; the most-used "bot" indicator on PickMyTrade/TradersPost webhook automations.
- **Rules (exact, from the standard Pine implementation)**: `hl2 = (high+low)/2`; `upper = hl2 + mult*ATR(len)`; `lower = hl2 - mult*ATR(len)`; final lower band ratchets up while price stays above it (`lower := lower > prevLower or close[1] < prevLower ? lower : prevLower`), final upper band ratchets down symmetrically; direction flips to up when `close > prevUpper`, to down when `close < prevLower`. Long on flip up, short on flip down; exit on the opposite flip (always in). Defaults ATR 10, multiplier 3 (Wilder ATR).
- **Parameters seen in practice**: 10/3 (default), 14/3 (LiberatedStockTrader), 7/2 scalping 1-5m MNQ (PickMyTrade), 14/2.5 5-min and 10/3 15-min (propfirmpinescripts.com), 1/4 (a QuantConnect MES example that produced 0 trades due to a code bug).
- **Evidence**:
  - dev.to tick-level test (Exness tick archives, Jan 2020-Sep 2026, real spread + $3.50/lot/side): Gold H4 267 trades, 43.4% win, PF 1.97, but PF 3.19 in the 2024-26 gold rally vs PF 1.02 in 2022-23; NZDUSD H1 1,115 trades, 35.6% win, PF 0.86. Author's conclusion: "multiplier 3 appears to be the single setting that fit the gold uptrend, not an edge".
  - LiberatedStockTrader (TrendSpider, Dow 30 stocks, 14/3, 4,052 trades): 5-minute 2,597 trades, 42% win, avg win +0.8% / avg loss -0.4%, max DD -7%; daily 1,455 trades, 43% win, max DD -39%; verdict "not profitable for swing traders"; the 5-minute expectancy was marginally positive before costs only.
  - Quantified Strategies (S&P 500 weekly, 10/3, 1960-2026): 41 trades, 68% win, 25% max DD, 63% time invested, $100k to ~$5.4M (no dividends). Weekly, not intraday.
  - Algomatic Trading (daily NQ and Gold futures, Jan 2005-Apr 2026, 1-pt/0.5-pt spread): NQ 93 trades, 52.69% win, CAGR 4.59%, max DD -14.22%, avg hold 34 days; Gold 91 trades, 47.25% win, CAGR 5.72%, max DD -15.10%. Multiplier outside 2.5-3.5 "degrades performance substantially".
  - propfirmpinescripts.com (vendor, NQ 15-min 2024-2026, RTH filter): claims 48-55% win, avg winner 2.0-2.5x avg loser, 1-3 trades/session, "strings of 3-5 losers". No trade log published.
- **Evidence quality**: 3 (independent after-cost tests exist; all show regime dependence; none show an intraday ES/NQ edge).
- **Prop-fit**: Poor as a stand-alone intraday system. Always-in flip logic on 5-15 min ES/NQ yields 35-45% win rate and multi-day losing strings that will eat $2,000 of EOD trailing drawdown on 1 mini in a chop week. Usable only as a trailing-exit mechanic or a higher-timeframe direction filter.
- **Data requirements**: OHLC only. Fully codeable.
- **Sources**: https://dev.to/moonthetrain/tradingview-supertrend-strategy-backtest-6-years-of-ticks-1ela ; https://www.liberatedstocktrader.com/supertrend-indicator/ ; https://quantifiedstrategies.substack.com/p/the-supertrend-indicator-backtested ; https://algomatictrading.substack.com/p/strategy-18-the-supertrend-crossover ; https://propfirmpinescripts.com/strategies/supertrend-pine-script.html ; https://blog.pickmytrade.trade/supertrend-automation-for-mnq-es-futures-2026-guide/

### 2.2 Supertrend "prop-firm" session variant (RTH-filtered, fixed-dollar stop, daily kill switch)

- **Origin**: propfirmpinescripts.com and similar vendors packaging Supertrend for Topstep/Apex/Tradeify/Lucid style accounts.
- **Rules**: Supertrend 14/2.5 on 5-min (or 10/3 on 15-min) MES/MNQ; take flips only during 09:30-16:00 ET (preferred 09:30-11:30 ET); direction must agree with VWAP side and opening bias; fixed dollar stop per trade ($50-100 MES, $30-60 MNQ on 5-min); exit on opposite flip or stop; no new entries once session loss reaches 80% of the firm daily limit; no entries within 30 minutes of NFP/CPI/FOMC; bar-close execution only; flat before close.
- **Parameters**: ATR 14 / mult 2.5 (5m) or ATR 10 / mult 3.0 (15m); stop $50-150 per mini-equivalent.
- **Evidence**: vendor claim only: NQ 15-min 2024-2026, 48-55% win rate, 2.0-2.5x payoff, 1-3 trades/day. No trade list, no cost statement.
- **Evidence quality**: 1.
- **Prop-fit**: The session filter, fixed stop and kill switch are the right prop-account scaffolding and should be reused around any strategy. The signal itself is unproven. Worth one backtest pass as a baseline against which the noise-area breakout (2.23) is compared.
- **Data requirements**: OHLC; VWAP needs volume (approximate with hl2 or time-weighted average price if no volume).
- **Sources**: https://propfirmpinescripts.com/strategies/supertrend-pine-script.html

### 2.3 UT Bot Alerts (ATR trailing stop, Yo_adriiiiaan / QuantNomad)

- **Origin**: TradingView open-source script "UT Bot Alerts" (QuantNomad port of Yo_adriiiiaan's UT Bot). Among the most-copied "bot" scripts; basis of the "ULTIMATE scalping" YouTube strategies.
- **Rules (exact, from source)**: inputs `a` (Key Value) default 1, `c` (ATR period) default 10, `h` (Heikin Ashi source) default false. `nLoss = a * ATR(c)`. Trailing stop: if `src > stop[1] and src[1] > stop[1]` then `stop = max(stop[1], src - nLoss)`; else if `src < stop[1] and src[1] < stop[1]` then `stop = min(stop[1], src + nLoss)`; else `stop = src > stop[1] ? src - nLoss : src + nLoss`. `ema1 = EMA(src,1)` (= src). Buy when `src > stop and crossover(ema1, stop)`; Sell when `src < stop and crossover(stop, ema1)`. Strategy version: long on Buy, short on Sell, reverse on opposite signal (always in).
- **Popular settings**: a=2, c=1 on 5-minute ("most commonly recommended" for scalping); a=1.5-2, c=5-10 for 1-5m; a=3-4, c=10-14 for 1H-4H; a=2, c=6 in the "Ultimate scalping" combo.
- **Evidence**: TradeSearcher aggregate of 105 community backtests: average PF 1.0, average max DD 65%, driven by crypto/stock daily charts; no index-futures intraday results. pineify.app/tradesearcher anecdotes: EUR/USD 4H ~60% win over ~25 trades; BTC 15m 8 of 12 signals hit 1:2 R in two weeks. A Freqtrade/Python port claiming "3202% profit" (Medium, blocked) is a crypto spot backtest with no stated costs. No independent ES/NQ test with costs found.
- **Evidence quality**: 1-2.
- **Prop-fit**: Poor stand-alone. a=2,c=1 on 5-min NQ flips several times per hour in chop; with $5/tick NQ costs plus 1-tick slippage the expectancy is negative in every honest test of comparable ATR-flip systems. Its trailing-stop formula is a decent exit tool (it is a Chandelier variant on close).
- **Data requirements**: OHLC. Heikin-Ashi option must be off for honest fills.
- **Sources**: https://github.com/unikonkon/NextJS_Bot_Crypto_trading-indicator_Pro/blob/main/lib/UT%20Bot%20Alerts.pine ; https://pineify.app/resources/blog/ut-bot-alerts-guide-best-settings-strategy-and-how-to-use-on-tradingview ; https://tradesearcher.ai/strategies/1594-ut-bot-strategy ; https://tradesearcher.ai/blog/ut-bot-alerts-strategy-guide-backtest-examples

### 2.4 Chandelier Exit (Le Beau) as a trend-flip system (everget script)

- **Origin**: Charles Le Beau; TradingView port by everget (GPL-3), widely used in "CE + 200 EMA" and "CE + ZLSMA" bot strategies.
- **Rules (exact)**: length 22, mult 3.0 (everget default; Le Beau's book uses 22/3; StockCharts tests 22/1 and 22/2), `useClose = true`. `longStop = highest(close, len) - mult*ATR(len)`, ratcheted: `longStop := close[1] > longStop[1] ? max(longStop, longStop[1]) : longStop`; `shortStop = lowest(close, len) + mult*ATR(len)` ratcheted symmetrically. `dir = close > shortStop[1] ? 1 : close < longStop[1] ? -1 : dir[1]`. Buy on dir flip to 1, sell on flip to -1. Common filter: longs only if close > EMA(200), shorts only if close < EMA(200).
- **Evidence**: No independent intraday futures test found. StockCharts SystemTrader (daily SPY/QQQ/IJR 2000-2016, $10 commission) used CE only as the exit of an RSI(5) mean-reversion system (see 2.5). TradingView "CE + 200 EMA" strategy page publishes no metrics.
- **Evidence quality**: 2.
- **Prop-fit**: Same objection as Supertrend/UT Bot (it is the same object: a ratcheting ATR stop). Fine as an exit; unproven as an entry.
- **Data requirements**: OHLC.
- **Sources**: https://github.com/everget/tradingview-pinescript-indicators/blob/master/trailing_stops/chandelier_exit.pine ; https://www.tradingview.com/script/T7c4n0Qu/

### 2.5 RSI(5) dip-buy with Chandelier Exit (StockCharts SystemTrader)

- **Origin**: Arthur Hill, StockCharts SystemTrader, Dec 2016.
- **Rules**: Regime filter: S&P 500 50-day SMA > 200-day SMA. Entry: RSI(5) crosses below 30 (variant A) or crosses back above 30 (variant B); buy next open. Exit: close below Chandelier Exit (22,1) or (22,2); sell next open. $100k capital, $10/trade. Long only.
- **Evidence**: Daily, 2000-12-01 to 2016-12-01. SPY (22,1) variant B: CAR 4.8%, 62% win, max DD -20.8%; QQQ (22,1) B: CAR 6.1%, 60% win, max DD -25.6%; IJR (22,1) B: CAR 10.8%, 83% win, max DD -12.6%, 80 trades, 35% exposure. Tighter exit (22,1) beat (22,2) everywhere.
- **Evidence quality**: 3 (independent, with commissions, 16 years, three ETFs) but daily holding period.
- **Prop-fit**: Not usable as published (multi-day holds). The intraday translation (RSI(5) on 5-min bars below 30 in an up-trending session, exit on 22-bar 1-ATR chandelier or at 15:55 ET) is a standard interpretation, untested here.
- **Data requirements**: OHLC.
- **Sources**: https://articles.stockcharts.com/article/articles-arthurhill-2016-12-systemtrader---testing-a-mean-reverion-system-with-the-chandelier-exit-spy-qqq-ijr---rsi5/

### 2.6 Hull Moving Average slope flip / Hull Suite (InSilico)

- **Origin**: Alan Hull (2005); TradingView "Hull Suite by InSilico" (HMA/EHMA/THMA, default length 55; 180-200 for "floating S/R").
- **Rules (exact)**: `HMA(n) = WMA(2*WMA(src, n/2) - WMA(src, n), round(sqrt(n)))`; `EHMA` same with EMA; `THMA(n) = WMA(3*WMA(src,n/3) - WMA(src,n/2) - WMA(src,n), n)`. Trend up when `HULL > HULL[2]`, down when `HULL < HULL[2]`. Long on up flip, short on down flip, reverse on opposite (always in). Alternative: price crosses HMA(40) on 30-min bars (QuantConnect example).
- **Evidence**:
  - Oxford Strat (42 US futures, 1980-2016, dual HMA with 6-ATR(20) stop, no costs): base case length 250 CAGR 11.5%, Sharpe 0.60, max DD 58%, win 30.8%, PF 1.10; best case length 750 CAGR 18.9%, Sharpe 0.93, DD 49.9%. Conclusion: only very slow lengths (>500 bars) work and the second HMA can be dropped. Rated "C".
  - QuantConnect public backtest (SPY, 30-min bars, HMA 40 cross, 2015-present, $240 fees, 200 trades): CAGR 5.45%, Sharpe 0.43, max DD 9.3%, win rate 5% (!) with profit/loss ratio 22.4: almost all trades are tiny whipsaw losses offset by rare large wins.
  - Udemy/vendor "Futures trading with the HMA" courses: no results published.
- **Evidence quality**: 3 for the slow trend-following version (one independent 36-year multi-market test); 2 for intraday.
- **Prop-fit**: Poor. 5% win rate / 95% small losses is exactly the pattern that trips a $2,000 EOD-trailing drawdown before the rare big winner arrives, and the rare big winner then trips the 50% consistency rule.
- **Data requirements**: OHLC.
- **Sources**: https://oxfordstrat.com/?p=16347 ; https://quantconnect.com/terminal/cache/embedded_backtest_175f86ff5679b080571133e72b58799c.html ; https://github.com/g-moe/Trading-Indicators/blob/main/Tradingview/hull-suite-by-insilico.pine

### 2.7 Hull Suite + LSMA "best 1-minute scalping" (YouTube, Myth-Busting #9)

- **Origin**: YouTube "I Tested The Best 1 Minute Scalping Strategy"; automated by myncrypto "Strategy Myth-Busting #9".
- **Rules**: 1-minute chart. Hull Suite length 55 (HMA). LSMA length 25. Long when Hull Suite is red and LSMA crosses above the Hull line; short when Hull Suite is green and LSMA crosses below. Stop at the latest swing low/high; target 1:4 risk-reward. Optional ADX > 25 filter (off by default). Commission 0.075%.
- **Evidence**: none published by the automator; the YouTube claim is unverified. The script was built explicitly to test the claim and the header states no validated result.
- **Evidence quality**: 1.
- **Prop-fit**: 1:4 R with counter-trend entries implies a ~25% win rate requirement just to break even; on 1-minute NQ with $5/tick costs this is a long-shot. Not recommended.
- **Data requirements**: OHLC.
- **Sources**: https://github.com/hasnocool/tradingview-pine-scripts (file "Strategy Myth-Busting #9 - HullSuite+LSMA - [MYN].pine")

### 2.8 Squeeze Momentum (LazyBear / TTM Squeeze) breakout

- **Origin**: John Carter, "Mastering the Trade"; LazyBear's SQZMOM_LB is the most-liked open-source TradingView oscillator.
- **Rules (exact)**: BB length 20, mult 2.0; KC length 20, mult 1.5, useTrueRange = true. `sqzOn = lowerBB > lowerKC and upperBB < upperKC`; `sqzOff = lowerBB < lowerKC and upperBB > upperKC`. Momentum `val = linreg(close - avg(avg(highest(high,20), lowest(low,20)), sma(close,20)), 20, 0)`. Standard strategy: enter long on the first `sqzOff` bar after a `sqzOn` run when `val > 0` (and rising), short when `val < 0` (and falling); exit when `val` crosses back toward zero or changes slope (histogram color change), or on a fixed stop/target.
- **Evidence**: Bitduke's TradingView strategy port reports "~12% drawdown" on XBTUSD/ETHUSD 1H-4H with no profit/win-rate figures. A babypips blog logged AAPL 3-minute: 14 trades, 50% then 38% profitable; 2H: 4 of 4 then 70%. No ES/NQ test with costs found. LuxAlgo's own library page: "squeezes can fire into failed moves".
- **Evidence quality**: 1-2.
- **Prop-fit**: Signal frequency is low (a few per day on 5-min), which is good for consistency, but there is no evidence of edge after costs. A plausible research variant for the backtest loop: 5-min ES/NQ, squeeze release between 09:45 and 14:30 ET, stop at the opposite KC band, target 2R or 15:55 ET flat.
- **Data requirements**: OHLC. (Carter's original also wants volume; LazyBear's does not.)
- **Sources**: https://github.com/masdanil/TA (LazyBear SQZMOM_LB source) ; https://www.tradingview.com/script/5tuGpzpd-Squeeze-Momentum-Strategy-based-on-Indicator-LazyBear-Bitduke/ ; https://www.luxalgo.com/library/indicator/qp9BoNyS-strategy-for-squeeze-momentum-indicator/

### 2.9 Nadaraya-Watson Envelope mean reversion (LuxAlgo)

- **Origin**: LuxAlgo open-source "Nadaraya-Watson Envelope"; viral on YouTube 2022-2024.
- **Rules (exact, endpoint / non-repainting mode)**: bandwidth h = 8.0, mult = 3.0, window = 500 bars. Gaussian weight `w(i) = exp(-(i^2)/(2h^2))` for i = 0..window-1; `basis = sum(src[i]*w(i)) / sum(w(i))`; `dev = SMA(|src - basis|, window) * mult`; upper = basis + dev, lower = basis - dev. Long when close crosses back above the lower band (or touches it), short when it crosses back below the upper band; exit at basis or a %-stop. Default mode (repainting smoothing = on) re-fits the whole window every bar and must not be used for backtests.
- **Evidence**: LuxAlgo's own page: "extremity crossings describe stretch, not guaranteed reversals, and nothing suggests this envelope outperforms traditional band tools." No independent test with costs found. All viral win-rate claims come from the repainting mode.
- **Evidence quality**: 1.
- **Prop-fit**: Mean-reversion at 3x MAD on 1-5 min ES/NQ fires mostly on trend days, i.e., exactly when it loses most. Not recommended; if tested, use endpoint mode, add a regime filter and a hard stop.
- **Data requirements**: OHLC.
- **Sources**: https://www.luxalgo.com/library/indicator/Nadaraya-Watson-Envelope ; https://github.com/geraked/tradingview (strategies/NWERSIASF.pine, h=8, mult=3, repaint=false)

### 2.10 LuxAlgo Signals & Overlays (paid, closed source)

- **Origin**: LuxAlgo Premium/Ultimate ($27.99-32.99/month annual), "highest-rated paid indicator on TradingView".
- **Rules**: Closed source. Confirmation signals are a smoothed trend-flip (reported to be a Supertrend/EMA-slope family with a "sensitivity" input); "contrarian" signals are oscillator extremes. Cannot be reproduced exactly.
- **Evidence**: Company-shared backtests: 55% win, PF 1.4, 18% max DD across BTC/AAPL/EURUSD (ad hoc selection). Independent/community: signals "shift on the same bar", 55% backtest becomes ~50/50 live; "even with a 60% win rate you will lose money" with their backtester; QuantVPS/lunefi comparison score 4.3 vs competitors. Reddit anecdote of "64% profit" on NVDA 1-minute is paper trading.
- **Evidence quality**: 1.
- **Prop-fit**: Not codeable from OHLC without reverse engineering; repainting reports; no futures evidence. Exclude.
- **Data requirements**: proprietary; flag.
- **Sources**: https://www.quantvps.com/blog/luxalgo-review ; https://lunefi.com/blog/best-luxalgo-alternatives-tradingview

### 2.11 MACD (12, 26, 9) zero-line / signal-cross trend

- **Origin**: Gerald Appel; universal default.
- **Rules (as tested)**: Entry when `MACD hist > 0 and MACD > 0 and MACD > signal`; exit when `signal > MACD`. Executed at next open or HL2.
- **Evidence** (LiberatedStockTrader, Dow 30, 606,422 test trades): daily OHLC 20 years: 40% win, avg win +7.6% / loss -3.6%, only 1 of 30 stocks beat buy-and-hold; 5-minute 3 months OHLC: 40% win, +0.42% / -0.21%, 8 of 30 beat B&H; with Heikin-Ashi bars 44% win and 15 of 30 beat B&H (but HA fills are synthetic, see 2.14). Conclusion: MACD "consistently underperforms buy-and-hold".
- **Evidence quality**: 3 (independent, large sample, but stocks and no explicit commission on 5-min).
- **Prop-fit**: Poor stand-alone; a 40% win rate with ~2:1 payoff is break-even before futures costs.
- **Data requirements**: OHLC.
- **Sources**: https://www.liberatedstocktrader.com/macd-indicator/

### 2.12 RSI(14) 30/70 cross mean reversion

- **Rules (as tested)**: Buy when RSI(14) crosses above 30; sell when RSI(14) crosses below 70.
- **Evidence** (LiberatedStockTrader, 23,487 trades): 1-minute (20 days): 20% win; 5-minute (1 month): 23% win; 1-hour (4 years): 53% win, best setting; daily (27 years): 20% win. S&P 500 daily RSI-14 26 years: +1,282% vs +881% B&H (long-only, in a bull market). Visa 1-hour 3 years: +53% vs +11.75%, 65% win.
- **Evidence quality**: 3 (independent, large sample; intraday results are clearly negative).
- **Prop-fit**: 1- and 5-minute RSI cross systems lose; 60-minute is the only setting with any signal, which yields at most a handful of trades a week. Not a core candidate; RSI(2)/RSI(5) on 5-min with a session trend filter is the standard interpretation worth one pass.
- **Data requirements**: OHLC.
- **Sources**: https://www.liberatedstocktrader.com/rsi-indicator/

### 2.13 MACD + RSI combo (standard objective interpretation)

- **Origin**: ubiquitous YouTube/TradingView "MACD + RSI + 200 EMA" scalp.
- **Rules (standard interpretation, no single canonical source)**: 5-minute bars, 09:35-15:30 ET. Long: close > EMA(200), RSI(14) < 30 within last 5 bars and now rising, MACD(12,26,9) line crosses above signal. Short mirrored with RSI > 70 and close < EMA(200). Stop 1.5x ATR(14), target 2x stop or flat 15:55 ET.
- **Evidence**: No independent, after-cost test on ES/NQ found. Component tests (2.11, 2.12) are negative intraday. The "Strategy Myth-Busting #7 MACDBB+SSL+VSF" script exists but publishes no results.
- **Evidence quality**: 1.
- **Prop-fit**: Low-frequency (0-2 signals/day), so it will not blow up fast, but no evidence of edge.
- **Data requirements**: OHLC.
- **Sources**: component sources above; https://github.com/hasnocool/tradingview-pine-scripts

### 2.14 Heikin-Ashi colour-flip trend (plus 50/200 EMA)

- **Rules**: `haClose = (o+h+l+c)/4`; `haOpen = (haOpen[1]+haClose[1])/2`; `haHigh = max(h, haOpen, haClose)`; `haLow = min(l, haOpen, haClose)`. Long when HA candle turns green (haClose > haOpen) and real close > EMA(50); exit on first red HA candle or fixed target (vendor example: 20 ES points). Shorts mirrored.
- **Evidence**: PickMyTrade guide (vendor): "65% backtested win rate on ES 5-min in 2024 bull runs; 55% live after fees"; "TradingView results overstated 10-15%". NinjaTrader forum/EliteTrader: strategies backtested on HA series fill at synthetic HA prices; one poster's 46,000-trade ES HA backtest showed a "10% edge" that was "too massive to be real"; fix is signal on HA, execute on real OHLC with 1-2 ticks slippage. casoon/pine-scripts README: on HA/Renko/Kagi/Range charts "orders fill at synthetic bar prices and the result is meaningless, reliably flattering, never reproducible". LiberatedStockTrader MACD test shows HA raising apparent win rate 40% to 44% (daily) and B&H-beaters from 8 to 15 of 30 (5-min), consistent with synthetic-fill inflation.
- **Evidence quality**: 2 (the only hard evidence is that HA backtests are inflated).
- **Prop-fit**: Only acceptable if executed at real OHLC. The HA flip is then just a lagging 2-bar average cross; no evidence of edge.
- **Data requirements**: OHLC. Flag: must execute on real bars.
- **Sources**: https://blog.pickmytrade.io/heikin-ashi-charts-trading-strategy-automation-guide.md ; https://elitetrader.com/et/threads/ninjascript-backtesting-data-series-heiken-ashi-vs-others.375746/ ; https://github.com/casoon/pine-scripts

### 2.15 Smoothed Heikin-Ashi Trend (TraderHalai BACKTEST)

- **Rules**: HA computed on SMA(10)-smoothed OHLC; the script computes the real close needed to flip HA colour and trades the flip. Long on green flip, short on red flip; 1% stop; 10% equity sizing; 0.1% commission; 10 ticks slippage; market orders; repainting off.
- **Evidence** (author, Bitcoin): 8H 1,046 trades, +249%, CAGR 14.0%, max DD 7.9%, win 28%, PF 2.02; 1D 429 trades, +458%, PF 2.80; 5D 69 trades, +1,615%, PF 10.45. Crypto, long-bias era, self-reported.
- **Evidence quality**: 2.
- **Prop-fit**: 28% win rate trend-following on multi-hour bars; not transferable to an intraday ES/NQ flat-by-close account.
- **Data requirements**: OHLC.
- **Sources**: https://de.tradingview.com/script/Is0LQdiz-Smoothed-Heikin-Ashi-Trend-on-Chart-TraderHalai-BACKTEST/

### 2.16 Ichimoku Cloud breakout (9, 26, 52)

- **Rules (as tested)**: Long when close > Senkou A and close > Senkou B (price above cloud); exit when close < both spans; or (QuantConnect) long when Chikou crosses above the cloud, short when it crosses below.
- **Evidence**: LiberatedStockTrader (Dow 30, daily, 20 years, 600 stock-years): 90% of stocks underperformed B&H, ~60% of trades lose; QQQ +175% vs +815% B&H (66 trades, R/R 2.85); SPY +118% vs +294% B&H (59 trades, R/R 3.01). Wooster independent study: SPY weekly 2019-2020 underperforms B&H. QuantConnect energy-sector study 2015-2020: Sharpe -0.31 vs XLE -0.08.
- **Evidence quality**: 3 (several independent tests, all negative vs benchmark).
- **Prop-fit**: Exclude. Slow, low win rate, no intraday evidence.
- **Data requirements**: OHLC.
- **Sources**: https://www.liberatedstocktrader.com/?p=54 ; https://www.quantconnect.com/research/9031/ichimoku-clouds-in-the-energy-sector/ ; https://openworks.wooster.edu/independentstudy/9433

### 2.17 Renko / range-bar brick-reversal scalps

- **Rules (standard)**: Renko brick = k x ATR(14) (typical NQ 10-20 points, ES 2-4 points); long after 2 consecutive up bricks following a down brick (or brick colour flip + EMA(20) of brick closes rising); exit on first opposite brick or N bricks profit. Range bars: fixed range (e.g., NQ 8-12 pts), same flip logic.
- **Evidence**: No independent after-cost test found. Vendor article headlined "Best settings based on data" contains no data. All tooling maintainers (NinjaTrader support, pine-script maintainers) warn that strategies backtested on Renko/range charts fill at synthetic prices and are "reliably flattering". Renko on a 1-minute OHLC feed also cannot be reconstructed exactly (intrabar brick formation), so any Lucid backtest would be an approximation.
- **Evidence quality**: 1.
- **Prop-fit**: Exclude as an entry engine. Flag: synthetic bars; approximate at best from 1-minute OHLC.
- **Data requirements**: tick data for exact bricks; approximate from 1-minute OHLC. Flag.
- **Sources**: https://www.liberatedstocktrader.com/renko-charts/ ; https://github.com/casoon/pine-scripts ; https://elitetrader.com/et/threads/ninjascript-backtesting-data-series-heiken-ashi-vs-others.375746/

### 2.18 UT Bot + STC + Hull Suite "ULTIMATE scalping" (YouTube, Myth-Busting #1)

- **Rules**: Long when STC(80, 27, 50) is green, below 25 and rising; Hull Suite(55) green; UT Bot (key 2, ATR 6) in buy state. Short mirrored (STC red, above 75, falling; Hull red; UT Bot sell). Stop 15% default (effectively off), four take-profit levels; commission 0.075%; $500 capital.
- **Evidence**: none published; built to test the YouTube claim. No results in header.
- **Evidence quality**: 1.
- **Prop-fit**: Three lagging trend tools in agreement means late entries and few signals; untested.
- **Data requirements**: OHLC.
- **Sources**: https://github.com/hasnocool/tradingview-pine-scripts (file "Strategy Myth-Busting #1 - UT Bot+STC+Hull [MYN].pine")

### 2.19 PSAR + MA(50/200) + Squeeze Momentum + HawkEye Volume "7% per day" (Myth-Busting #6)

- **Rules**: Long when PSAR(0.02, 0.02) dot flips below price and prior bar breaches above the last dot; price above both 50 and 200 MA and 50 > 200; Squeeze Momentum histogram green; HawkEye Volume (200) green. Short mirrored. Stop 999% (off), four TP levels.
- **Evidence**: none; the "7% per day" claim is the YouTube title.
- **Evidence quality**: 1.
- **Prop-fit**: Requires volume (HawkEye). Exclude or approximate without the volume leg.
- **Data requirements**: volume for HawkEye leg; flag.
- **Sources**: https://github.com/hasnocool/tradingview-pine-scripts (file "Strategy Myth-Busting #6 - PSAR+MA+SQZMOM+HVI - [MYN].pine")

### 2.20 BB_BUY (EMA(10) cross of BB(42,2) basis + Awesome Oscillator) + Supertrend (10,3) (Myth-Busting #3)

- **Rules**: Long when EMA(10) crosses above BB(42, 2.0) basis, close above basis, AO(77,10) condition agrees, and Supertrend(10,3) is green; short mirrored with Supertrend red. Optional ADX > 25. TP levels 100% default; stop 99.9% (off).
- **Evidence**: none published.
- **Evidence quality**: 1.
- **Prop-fit**: Untested; low frequency.
- **Data requirements**: OHLC.
- **Sources**: https://github.com/hasnocool/tradingview-pine-scripts (file "Strategy Myth-Busting #3 - BB_BUY+SuperTrend - [MYN].pine")

### 2.21 OSGFC (one-sided Gaussian filter channel, depth 10, ATR 21 x 0.628) + Supertrend (10,3) (Myth-Busting #12)

- **Rules**: 15-minute, forex/crypto. Long when OSGFC and Supertrend both signal buy on the same bar; short when both signal sell; exit when the Gaussian filter flips.
- **Evidence**: none published.
- **Evidence quality**: 1.
- **Prop-fit**: Untested.
- **Data requirements**: OHLC.
- **Sources**: https://github.com/hasnocool/tradingview-pine-scripts (file "Strategy Myth-Busting #12 - OSGFC+SuperTrend - [MYN].pine")

### 2.22 Vendor bot: Aeromir "Goldilocks" (NinjaTrader, 2x Micro Gold)

- **Rules**: Proprietary. Trades 2 MGC contracts on a 4-minute chart; starts shortly after the European open (~03:00 ET) and flattens by the end of RTH (~13:30 ET gold pit close / 17:00 ET); "steady, low-volatility" intraday logic. Bundle with "Low Volume Hunter" and "Simple Price Pattern"; $348-435/quarter, $1,276/year; VPS needed.
- **Evidence (live, streamed by the vendor, Oct 14 2024-Feb 13 2026)**: 479 trades, net $21,378, 48.0% win, PF 1.32, avg trade $45, max DD $8,368, Calmar 2.55. About $1,330/month on 2 MGC (~$67/pt per contract pair) during a historic gold rally.
- **Evidence quality**: 2 (vendor live track, unaudited, single regime).
- **Prop-fit**: The $8,368 max drawdown is 4.2x Lucid's $2,000 room even at 2 micros; scaling to 1 MGC still implies ~$4,200. Cannot be run inside a 50K Flex. Rule-level lesson: 48% win / PF 1.32 / $45 average on micros is what a decent live bot actually looks like.
- **Data requirements**: proprietary; cannot be replicated.
- **Sources**: https://futures.aeromir.com/goldilocks ; https://blog.pickmytrade.trade/ninjatrader-prop-bots-vs-pickmytrade-apex-topstep/

### 2.23 Vendor bot: Vector Algorithmics (NinjaTrader/IBKR, 30+ algos)

- **Claims**: "70-80% win rates, 5-15% monthly returns, 85% first-attempt prop pass rate, +174% since launch"; $497-2,497 one-time plus $60-299/month VPS.
- **Evidence**: Website closed; Discord closed after performance complaints; 159 Trustpilot reviews: some report 3-14.5%/month, others "lost 50%", "consistent losses May-June 2026", "small wins and HUGE losses"; one user spent $4k passing Apex evals then had all PA accounts closed for algo use. Refund-guarantee disputes.
- **Evidence quality**: 1.
- **Prop-fit**: Exclude. Also a reminder that some firms terminate funded accounts for unattended bots; Lucid's automation policy must be checked before any live deployment.
- **Sources**: https://www.trustpilot.com/review/vectoralgorithmics.com ; https://blog.pickmytrade.trade/ninjatrader-prop-bots-vs-pickmytrade-apex-topstep/

### 2.24 Intraday "noise-area" momentum breakout (Zarattini-Aziz-Barbon; Quantitativo ES/NQ replication) — the benchmark that actually has evidence

- **Origin**: "Beat the Market: An Effective Intraday Momentum Strategy for S&P500 ETF (SPY)", Zarattini, Aziz, Barbon, SSRN 4824172 (2024); replicated on ES and NQ futures by Quantitativo (Jan 2025) with Databento 1-minute data.
- **Rules (paper, standard interpretation of the published method)**: For each time-of-day t (checked every 30 minutes in the paper; 1-minute works), compute `sigma_t = mean over last L days of |close_t / open_day - 1|` (paper L = 14; Quantitativo found L = 90 better). Upper band `UB_t = max(open_day, close_prev_day) * (1 + sigma_t)`, lower band `LB_t = min(open_day, close_prev_day) * (1 - sigma_t)`. Go long when price crosses above UB_t, short when it crosses below LB_t (one position at a time, reversals allowed). Trailing stop = the band that was crossed (or VWAP in the paper's variant); stopped out if price re-enters the noise area. Flat at 15:50-15:55 ET. Size = (target daily vol / realized 14-day daily vol) with a leverage cap (paper 2%/4x; Quantitativo 3%/8x).
- **Evidence** (Quantitativo, 2010-Jan 2025, $0.85 commission + $1.40 exchange fee per side, 0.25 tick slippage per side):
  - ES, L=14, 2% vol target: 8.1%/yr, Sharpe 0.91, max DD 24%, win 36%, payoff 2.09, +2 bps/trade.
  - ES, L=90, 3% vol: 16.8%/yr, Sharpe 1.25, max DD 21%, win ~37%, +3-4 bps/trade.
  - NQ, L=90, 3% vol: 24.3%/yr, Sharpe 1.67, max DD 24%, win 38%, payoff 2.25, +6 bps/trade.
  - Portfolio 50% NQ strat / 25% ES strat / 25% NQ long: 22.4%/yr, Sharpe 1.57, max DD 15%, 65% positive months, worst month -6.6%, 2 negative years in 16.
  - Caveats: flat 2010-2017, edge mostly 2018-2025; results "highly sensitive" to slippage, 0.5 tick round trip "already optimistic"; the paper's 2007-2010 inclusion flattered the SPY numbers (SPY paper: 19.6%/yr, Sharpe 1.33, +1,985% 2007-2024 net of costs); L=14 to 90 is an in-sample optimization; author is forward-testing.
- **Evidence quality**: 4 (SSRN working paper plus an independent replication on the exact instruments with explicit futures costs; not peer-reviewed; OOS forward test pending).
- **Prop-fit**: Best in family. Day-trade only, OHLC only, objective, ~1-3 trades/day, 36-38% win with 2.1-2.25 payoff. Translate to Lucid sizing: with 1 NQ or 10 MNQ, a typical day's P&L is +/- $300-900, so the 50% consistency rule needs the eval to run >= 6-8 trading days; worst-week drawdown at that size can approach $2,000, so eval sizing should be 1 NQ / 2 ES or 5-10 micros with a $600-800 daily stop. The band-trailing stop and 15:55 ET flat are already prop-compliant.
- **Data requirements**: 1-minute OHLC only; VWAP variant needs volume (use band stop instead).
- **Sources**: https://www.quantitativo.com/p/intraday-momentum-for-es-and-nq ; https://www.concretumgroup.com/beat-the-market-an-effective-intraday-momentum-strategy-for-sp500-etf-spy/ ; https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4824172

### 2.25 "Do our strategies work on the E-mini" (Automated Trading Strategies substack; multi-strategy ES vs NQ)

- **Rules**: Proprietary NinjaTrader strategy pack (34+ strategies, mostly intraday breakout/pullback); only aggregate numbers published.
- **Evidence** (backtest, Nov 2020-Nov 2021): ES $1.1M total across strategies, avg PF 1.41, avg DD -5.5% ($11k), ~3 trades/day; NQ $3.1M, avg PF 1.50, avg DD -6.85% ($19k), ~12 trades/day. Best ES single strategy: 175 trades/yr, PF 2.28, $92k; most consistent: 2,259 trades/yr, PF 1.21, $44k, worst day -$1,887.
- **Evidence quality**: 1-2 (vendor, one bull year, no rules).
- **Prop-fit**: Not codeable; included only because its drawdown-per-strategy ($11-19k on full-size contracts in a single bull year) is a useful reality check: even "good" NQ bots draw down 5-10x Lucid's room at 1 mini.
- **Sources**: https://automatedtradingstrategies.substack.com/p/do-our-strategies-work-on-the-e-mini

---

## 3. What the evidence says works in 2022-2026 (and what does not)

**Works, with real after-cost evidence on ES/NQ 1-minute data:**
- Intraday noise-area momentum breakout (2.24): Sharpe 1.25-1.67 on ES/NQ 2010-2025 with the edge concentrated 2018-2025; 36-38% win, 2.1-2.25 payoff, 65% positive months, flat by 15:55 ET. This is the only strategy in this family that should go into the Lucid backtest loop as a core candidate. Required adaptations: lookback 14 vs 90 days walk-forward tested on 2025-2026; 1-NQ / 10-MNQ sizing; $600-800 daily loss stop; skip FOMC/CPI minutes; verify slippage at 1 tick per side rather than 0.25.

**Works only as components, not as systems:**
- ATR ratchet stops (Supertrend, UT Bot, Chandelier): consistent evidence that a tighter ratchet (Chandelier 22x1 beat 22x2; Supertrend multiplier 2.5-3.5 only) improves exits of an otherwise-defined entry. Use as the trailing stop of the breakout above, not as an entry signal.
- RTH session filter (09:30-11:30 ET first-half entries), fixed dollar stop, 80%-of-daily-limit kill switch, no entries within 30 min of NFP/CPI/FOMC: the prop-bot vendors converge on this scaffolding and it directly addresses Lucid's intraday-checked drawdown.

**Does not work intraday on index futures (after costs), per independent tests:**
- Supertrend flip on 5-15 min (42% win, PF ~1.0 outside trends); UT Bot a=2/c=1 on 5-min (no honest test shows PF > 1 on indices); HMA flip (5% win rate / 95% whipsaw on SPY 30-min); MACD 12/26/9 (40% win, underperforms B&H on 5-min and daily); RSI(14) 30/70 on 1- and 5-minute (20-23% win); Ichimoku (90% of stocks underperform B&H; negative Sharpe vs sector benchmark); Nadaraya-Watson (no evidence, repaints by default); LuxAlgo (55% claimed becomes ~50% live; repainting reports).

**Known backtest traps specific to this family (must be enforced in the engine):**
1. Synthetic bars: never fill at Heikin-Ashi, Renko or range-bar prices; compute the signal on the synthetic series if desired, fill at real 1-minute OHLC with >= 1 tick slippage each side plus $2.25-2.50 commission per side per mini ($0.85-1.30 per micro).
2. Repainting: Nadaraya-Watson must be in endpoint mode; LuxAlgo cannot be reproduced; all signals must be evaluated on confirmed bar closes.
3. Always-in logic: convert every flip system to flat-by-15:55-ET and no new entries after 15:30 ET before measuring.
4. Regime fit: every positive Supertrend/UT Bot result found was a 2020-2021 or 2024-2026 trend-regime artefact; any candidate must survive 2022 (down, high vol) and 2023 H2 (chop) in the walk-forward, not just 2025-2026.
5. Vendor track records: Goldilocks (PF 1.32, 48% win, $45/trade on 2 MGC, DD $8.4k) is the realistic ceiling for a working retail bot; anything advertising 70-80% win rates or "85% pass rate" (Vector) has no supporting evidence and the vendor has since shut down.

**Lucid-specific sizing implications:**
- $2,000 EOD trailing drawdown with intraday breach check means the engine must track (closed P&L + open P&L) against the trailing floor on every 1-minute bar.
- With a $3,000 target and 50% consistency, the pass requires at least two days contributing and realistically 6-10 days of +$300-600; single +$1,500 days are the enemy. Vol-targeted sizing (as in 2.24) naturally caps this; fixed-contract flip systems do not.
- Payout gate (5 EOD days >= $150, net-positive cycle) favours a strategy with 55-65% positive days of modest size; the breakout's 36-38% trade win rate aggregates to roughly 55-60% positive days at 1-3 trades/day in Quantitativo's monthly statistics (65% positive months), which should be verified day-by-day in the backtest.

---

## 4. Source list (fetched)

- https://dev.to/moonthetrain/tradingview-supertrend-strategy-backtest-6-years-of-ticks-1ela
- https://www.liberatedstocktrader.com/supertrend-indicator/
- https://quantifiedstrategies.substack.com/p/the-supertrend-indicator-backtested
- https://algomatictrading.substack.com/p/strategy-18-the-supertrend-crossover
- https://propfirmpinescripts.com/strategies/supertrend-pine-script.html
- https://blog.pickmytrade.trade/supertrend-automation-for-mnq-es-futures-2026-guide/
- https://www.quantitativo.com/p/intraday-momentum-for-es-and-nq
- https://www.concretumgroup.com/beat-the-market-an-effective-intraday-momentum-strategy-for-sp500-etf-spy/
- https://pineify.app/resources/blog/ut-bot-alerts-guide-best-settings-strategy-and-how-to-use-on-tradingview
- https://tradesearcher.ai/strategies/1594-ut-bot-strategy
- https://tradesearcher.ai/blog/ut-bot-alerts-strategy-guide-backtest-examples
- https://github.com/unikonkon/NextJS_Bot_Crypto_trading-indicator_Pro (UT Bot Alerts.pine source)
- https://github.com/everget/tradingview-pinescript-indicators (chandelier_exit.pine)
- https://www.tradingview.com/script/T7c4n0Qu/
- https://articles.stockcharts.com/article/articles-arthurhill-2016-12-systemtrader---testing-a-mean-reverion-system-with-the-chandelier-exit-spy-qqq-ijr---rsi5/
- https://oxfordstrat.com/?p=16347
- https://quantconnect.com/terminal/cache/embedded_backtest_175f86ff5679b080571133e72b58799c.html
- https://www.quantconnect.com/terminal/cache/embedded_backtest_d1a455c21990cc62bc896e325fe2b36a.html
- https://github.com/g-moe/Trading-Indicators (hull-suite-by-insilico.pine)
- https://github.com/masdanil/TA (Squeeze Momentum Indicator [LazyBear].pine)
- https://www.tradingview.com/script/5tuGpzpd-Squeeze-Momentum-Strategy-based-on-Indicator-LazyBear-Bitduke/
- https://www.luxalgo.com/library/indicator/qp9BoNyS-strategy-for-squeeze-momentum-indicator/
- https://www.luxalgo.com/library/indicator/Nadaraya-Watson-Envelope
- https://github.com/geraked/tradingview (NWERSIASF.pine, LRCUTB.pine)
- https://github.com/DmitryJbanov/TradingAPP (nadaraya-watson-original.pine, non-repaint strategy)
- https://www.quantvps.com/blog/luxalgo-review
- https://www.liberatedstocktrader.com/macd-indicator/
- https://www.liberatedstocktrader.com/rsi-indicator/
- https://www.liberatedstocktrader.com/?p=54 (Ichimoku test)
- https://www.liberatedstocktrader.com/renko-charts/
- https://www.quantconnect.com/research/9031/ichimoku-clouds-in-the-energy-sector/
- https://blog.pickmytrade.io/heikin-ashi-charts-trading-strategy-automation-guide.md
- https://elitetrader.com/et/threads/ninjascript-backtesting-data-series-heiken-ashi-vs-others.375746/
- https://de.tradingview.com/script/Is0LQdiz-Smoothed-Heikin-Ashi-Trend-on-Chart-TraderHalai-BACKTEST/
- https://github.com/casoon/pine-scripts (strategies/README.md on synthetic-bar fills)
- https://github.com/hasnocool/tradingview-pine-scripts (Strategy Myth-Busting #1, #3, #6, #9, #12)
- https://futures.aeromir.com/goldilocks
- https://blog.pickmytrade.trade/ninjatrader-prop-bots-vs-pickmytrade-apex-topstep/
- https://www.trustpilot.com/review/vectoralgorithmics.com
- https://automatedtradingstrategies.substack.com/p/do-our-strategies-work-on-the-e-mini
- https://www.propscorer.com/blog/best-prop-firms-nq-scalping
- https://www.clearedge.trading/post/topstep-vs-apex-automated-trading-rules-bot-comparison
