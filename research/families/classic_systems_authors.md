# Family: Classic published trading systems and author methods

Research sweep date: 2026-10-03. Scope: Turtle rules; Larry Williams (Oops!, Smash Day, volatility breakout, %R); Raschke & Connors *Street Smarts* (Turtle Soup, Turtle Soup Plus One, 80-20s, Momentum Pinball, Holy Grail, ADX Gapper, Anti, Whiplash); Toby Crabel (stretch ORB, NR4/NR7/ID/IDnr4); Mark Fisher ACD; Perry Kaufman (KAMA, efficiency ratio); Tom DeMark (TD Setup/Sequential); Kevin Davey; Andrea Unger; Howard Bandy; Brent Penfold; Jake Bernstein; Murray Ruggiero; Thomas Stridsman; Art Collins; Charles LeBeau; John Ehlers; Welles Wilder; David Bean / Capstone ES-NQ systems. All times are US Eastern (ET). RTH for ES/NQ = 09:30-16:00; our day-trade cutoff is 15:55.

Target use: Lucid Trading 50K LucidFlex (eval target $3,000; $2,000 end-of-day trailing max-loss checked intraday; 50% consistency rule in eval; funded: 90/10, EOD trail locks at $50,100 after $52,100; payout needs 5 days >= $150 EOD; 4 minis/40 micros eval, 2 minis/20 micros at funded start; flat by 16:45). Data available: 1-minute OHLC (no volume) ES/NQ/GC proxies 2010-11 to 2026-09; daily futures and VIX from Yahoo.

Method note: the session's WebSearch budget was exhausted by the parent workflow after the first 6 searches, so the sweep was completed with ~70 direct page fetches (mesasoftware PDFs, oxfordstrat tests, Capstone product pages, DeMark, ProRealCode, nexusfi/elitetrader excerpts, x-trader.net, tradingsetupsreview, mql5, luxalgo, bettersystemtrader, KJ Trading). quantifiedstrategies.com (bot wall), Unger Academy (SiteGround captcha), Scribd and web.archive.org were unreachable; where a rule comes from the book itself rather than a fetched page it is marked **[book]** and where it is my standard objective interpretation of a vague source it is marked **[interp]**.

---

## 0. Executive summary

1. **Almost nothing in this family has a modern, independent, net-of-cost out-of-sample record on ES/NQ/GC intraday.** The classic authors published rules plus in-sample tables from the 1980s-2000s. The only systematic multi-decade re-tests found are oxfordstrat (42 US futures, 1980-2013/2019, daily bars, $50 round-turn): Crabel narrow-range ORB and Williams Bull Oops are both rated "C" (gross-positive, "not currently tradeable without additional rules" once costs are applied); Crabel wide-range is "D" (PF 0.74). Ehlers' own bond tests (2002-2007, no costs) show PF 1.7-2.1. Kevin Davey's 567,000-backtest exit study (40 futures, 60-min to daily, 2010-2020) found only **stock indices and metals** positive on average, and that **dollar targets beat ATR targets, targets beat stops, and stop-and-reverse beat every stand-alone exit**.

2. **What is still working in 2024-2026 according to the only vendor publishing year-by-year hypotheticals (Capstone / David Bean, no slippage):** NQ *gap-continuation* and *open-range* day-trade systems (Gap Continuation 2020 NQ: 2024 +$28,190, 2025 +$6,090, 2026 YTD +$6,645, PF 1.87, 59.5% wins; NQ Open Range 2026: 2024 +$62,510, 2025 +$39,880, 2026 +$28,465, PF 1.45, 37% wins). ES *gap-fill* and ES 09:31 *reversal* systems have gone flat-to-negative (ES GAPF I: 2024 -$100, 2025 +$475, 2026 -$3,675; ES Mirror 2020: 2024 -$1,275, 2025 -$375, 2026 -$2,625). Read-through: in the current regime, NQ continuation/breakout after the open > ES mean-reversion at the open.

3. **The structurally best-shaped candidates for the Lucid rules** (objective, OHLC-only, flat by close, many small days) are: (a) Crabel stretch ORB restricted to NR4/ID/NR7 setup days with a close-based trigger; (b) Street Smarts 80-20 / Turtle-Soup-style failed-breakout re-entries at the prior-day low/high (stop-order entry confirms failure, stop = today's extreme, target = prior close); (c) Williams volatility breakout (open + k x prior range) with a bond/trend filter and EOD exit, sized in micros; (d) Momentum Pinball (LBR/RSI < 30 / > 70 day filter + first-hour range breakout), which is literally an ORB with a daily mean-reversion filter; (e) Fisher ACD A-up/A-down with a time-confirmation and a "failed-A" reversal, which is a risk-control wrapper for any ORB; (f) Ehlers roofing-filter stochastic traded *anticipatorily* (enter when the oscillator crosses below 0.2 / above 0.8, not on the turn) as an intraday 5-minute mean-reversion engine with a reversal-on-adverse-excursion rule.

4. **Poor fits**: Turtle S1/S2 (multi-week holds; 20-day breakouts on ES have been a loser since ~2010 and cannot be held overnight here, but N = ATR(20) sizing and the "skip after a winner" filter are reusable); TD Sequential (low frequency, discretionary perfection/cancellation rules); KAMA crossover (whipsaw, lag); Collins' open-to-close daily biases (hold open-to-close with no stop, large single-day P&L, hurts the consistency rule and the $2k intraday floor unless micro-sized); Ruggiero intermarket (needs other markets / report calendar); Bandy mean reversion (equities, multi-day).

5. **Evidence-quality distribution**: 1 strategy at 4 (Turtle, historical), most at 2, several at 1. Nothing in this family is 5. Treat every claim below as a hypothesis for the 2025-2026 1-minute backtest, not a result.

---

## 1. Richard Dennis / William Eckhardt: the Original Turtle rules (System 1 and System 2)

- **Origin**: Turtle program 1983-1988; rules published free by Curtis Faith (originalturtles.org, now tradingblox.com/originalturtles/originalturtlerules.pdf, 17 MB scan). **[book]** for the details below (the PDF is a scan; rules are the well-known canonical text).
- **Rules**:
  - N = 20-day exponential-style average of True Range: PDN = (19 x PDN_prev + TR)/20.
  - Unit = 1% of account / (N x dollars per point). Limits: 4 units per market, 6 per closely correlated group, 10 loosely correlated, 12 per direction.
  - **System 1**: enter long on a 1-tick break above the 20-day high (short: below the 20-day low). *Skip* the signal if the previous 20-day breakout in that market was a winner (a breakout is a "loser" if price moved 2N against entry before a profitable 10-day exit); the 55-day breakout is always taken as a fail-safe.
  - **System 2**: enter on a 55-day breakout, always.
  - Add 1 unit every 1/2 N of favorable movement up to 4 units; stops 2N from the most recent entry, all earlier stops raised by 1/2 N when adding. "Whipsaw" variant: stops at 1/2 N with re-entry.
  - Exit S1 at the 10-day low (longs) / 10-day high (shorts); S2 at the 20-day low/high. Stop orders are not held in the market; executed on breach.
- **Parameters**: 20/10 (S1), 55/20 (S2), N length 20, 2N stop, 1/2 N pyramid step.
- **Evidence**: Historical (1983-1988 Turtle program ~80%/yr; Faith's and Trading Blox forum re-tests through the 2000s are positive on a 40+ market portfolio). On single-market ES since 2010 the 20-day breakout has been a well-documented loser (sibling report trend_momentum.md s.9). No intraday version has evidence. Evidence quality **4** for the historical portfolio result, **2** for any ES/NQ use today.
- **Prop fit**: Poor as published (multi-day holds are forbidden; overnight gaps). Reusable pieces: (i) N-based position sizing (micros = floor(risk$ / (k x N_5min x $ per point))); (ii) the "skip the next breakout after a winner" filter applied to intraday ORBs; (iii) 55-bar vs 20-bar lookbacks on 5-minute bars as an intraday Donchian (test only, no published evidence).
- **Data requirements**: daily OHLC only.
- **Sources**: https://www.tradingblox.com/originalturtles/ ; https://www.tradingblox.com/originalturtles/originalturtlerules.pdf ; https://www.tradingblox.com/tbforum/viewforum.php?f=6

## 2. Larry Williams: Oops! gap reversal

- **Origin**: Larry Williams, *How I Made One Million Dollars Last Year Trading Commodities* (1973) and *Long-Term Secrets to Short-Term Trading* (1999, ch. "Oops!").
- **Rules (as published)**:
  - Buy Oops: today's open < yesterday's low. Place a buy stop at yesterday's low (Williams: "a tick or two above"). Sell Oops: today's open > yesterday's high; sell stop at yesterday's high.
  - The gap bar cannot confirm itself; a fill happens only when price trades back through yesterday's extreme (luxalgo: "filled only if price trades back up through it").
  - Stop: beyond the day's extreme (the gap bar's low for longs). Williams' exit: "bail-out" at the first profitable open, or a dollar stop; day-trade variant exits at the close.
  - Williams' filters **[book]**: trade day of week (TDW), the bond market trend (buy S&P Oops only if T-bonds closed higher than 5 days ago), and only after a down close for buys.
- **Modern implementations**: mql5 article 21741 / forge "lwOopsPatternExpert": minimum gap size, validity window (3 bars), confirmation = a completed bar closing back through the level, SL at gap bar extreme, TP = R x riskRewardRatio. TradingView "Larry Williams Oops Strategy" (xtradernet): buy stop at yesterday's low + filter ticks only if yesterday was a down candle; stop trails the current day's low; force-flat in the last bar of the session; no target.
- **Evidence**: oxfordstrat "Bull Oops" (42 US futures, 1980-2011, daily, 1% fixed fractional, exits = time 1-40 days or ATR(20) x 1-6, stop 6 x ATR): rated **C** (positive gross; sensitivity charts, no table). mql5 XAUUSD daily 2022-2026: 8 trades, +$523 on $10k (meaningless sample). Unger Academy 2025 "We tested Larry Williams' Oops pattern" exists but the page is captcha-walled; sibling report (intraday_mean_reversion.md s.9) could not extract numbers either. Evidence quality **2**.
- **Prop fit**: Objective and low-risk per trade (stop = gap extreme, typically 0.3-0.6 x ATR on ES/NQ). Frequency is low (open outside the prior day's range ~15-25% of days on NQ). Fits the consistency rule (many small wins, target = prior close or 1 x ATR). Best treated as a special case of the "open outside the prior range, fade back to the level" statistic.
- **Data requirements**: OHLC only (daily + 1-min).
- **Sources**: https://oxfordstrat.com/trading-strategies/bull-oops-pattern/ ; https://www.mql5.com/en/articles/21741 ; https://forge.mql5.io/CHACHAIAN/lwOopsPatternExpert ; https://www.tradingview.com/script/7Gqs0Sqn-Larry-Williams-Oops-Strategy/ ; https://www.luxalgo.com/library/concept/classic-bar-setups.md ; https://ungeracademy.com/blog/we-tested-larry-williams-oops-pattern-the-results-might-surprise-you (blocked)

## 3. Larry Williams: Smash Day (naked and hidden)

- **Origin**: *Long-Term Secrets to Short-Term Trading* (1999), "Smash Day patterns". **[book]** plus ProRealCode forum implementation.
- **Rules**:
  - Naked buy smash day: a day that closes **below the previous day's low** (a downside "smash"). Buy the next day on a buy stop at the smash day's **high**; order valid for that day only. Naked sell smash day: a close above the previous day's high; sell stop at the smash day's low.
  - Hidden smash day (buy): a day that closes in the bottom 25% of its range (a weak close) but does not take out the prior low; buy next day above its high. Hidden sell: close in the top 25% of range without a new high; sell below its low. **[book, paraphrased]**
  - Stop: below the smash day low (longs). Exit: Williams' bail-out (first profitable open) or at the close for a day-trade; ProRealCode version: fixed SL/TP in ticks plus filter High[1] < High[n] (n = 5-30) so the smash occurs below the recent range.
  - Williams combined with TDW and the bond-trend filter.
- **Evidence**: Book tables (S&P and bonds, 1980s-90s) only; ProRealCode thread has code but no stats. Evidence quality **1**.
- **Prop fit**: It is a one-day failed-breakdown reversal (the same statistic as Turtle Soup / outside-day re-entry) executed intraday as a stop at the prior day's high: risk = smash day range (often > 1 x ATR on NQ, too big for 1 mini; use 2-5 micros). Low frequency.
- **Data requirements**: daily OHLC + 1-min.
- **Sources**: https://www.prorealcode.com/topic/larry-williams-smash-day/ ; https://www.prorealcode.com/?s=larry+williams

## 4. Larry Williams: volatility breakout (open + k x prior range) with bond / TDW filters

- **Origin**: *Long-Term Secrets to Short-Term Trading* ch. 4 "Volatility breakouts - the momentum breakthrough"; also *The Definitive Guide to Futures Trading*. Kaufman, *Trading Systems and Methods*, documents the same "Williams volatility breakout" family. **[book]**
- **Rules (standard objective form)**:
  - Range_prev = yesterday's high - low (Williams also uses the larger of the last 1-3 ranges or the true range).
  - Buy stop at today's open + k x Range_prev; sell stop at today's open - k x Range_prev. Williams' published k values are market-specific, mostly in 0.5-0.8 (S&P examples used ~0.5-0.6; bonds ~0.7). A single k = 0.6 is the standard interpretation.
  - Stop: the opposite stop (reverse) or a dollar stop; exit at the close (day-trade) or bail-out at the first profitable open.
  - Filters Williams reports as material: trade only on specific days of the week (TDW; in his S&P tables buys were best early in the week), and only when T-bonds closed higher than 5 (or 10) days ago for buys; take buys only after a down close (and sells after an up close) in some versions.
- **Evidence**: Book in-sample tables (S&P 1982-1998) show high percent-profitable (80%+) with the bond filter **[book]**. The entire modern ORB literature (sibling orb_session.md: Zarattini 2023/2024, Mesfin 2026 falsification on MNQ) is the independent test of "open + fraction of a range" entries: gross edge exists, net edge is within slippage unless filtered. Evidence quality **2** (for the specific Williams formulation), **3** for the general ORB family.
- **Prop fit**: Good structure (one entry, hard stop, EOD exit). With k = 0.6 on NQ (prior range ~250-400 pts in 2025) the trigger is 150-240 pts from the open, which is why the strategy often triggers late or not at all; on ES (range ~50-80) trigger = 30-50 pts, stop-and-reverse width = 60-100 pts = $3,000-5,000 per mini. **Must be traded in micros with a dollar stop, not the full reverse stop.** The bond filter is codeable from Yahoo daily ZB/ZN.
- **Data requirements**: daily OHLC + 1-min; daily T-bond closes (Yahoo) for the filter.
- **Sources**: Williams (1999) ch. 4 [book]; https://www.prorealcode.com/?s=larry+williams ; sibling report research/families/orb_session.md

## 5. Larry Williams: Williams %R (10-day) oversold/overbought

- **Origin**: Williams (1973); formula widely documented. **[book]** for Williams' 10-period preference.
- **Rules**: %R = (HighestHigh(n) - Close) / (HighestHigh(n) - LowestLow(n)) x -100. Default n = 14 (Williams used 10). Overbought 0 to -20, oversold -80 to -100. Williams' own usage: buy when %R has been below -90/-80 and the market is in an uptrend by a longer measure (he used a trend filter such as price above its longer %R regime or the bond filter), sell the mirror; also "momentum failure" (fails to re-enter the zone) as a reversal signal.
- **Objective intraday form [interp]**: 5-min RTH bars, %R(14) crosses up through -80 with a daily trend filter (close > 20-day SMA) -> long; exit when %R > -20 or at 15:55; stop 0.75 x ATR(14, 5-min).
- **Evidence**: No independent ES/NQ test found; TradingView/Investopedia describe the indicator only. Evidence quality **1**.
- **Prop fit**: Mean-reversion oscillator entries give many small trades, which fits the consistency rule, but every published oscillator test (Ehlers s.21) shows that *waiting for the turn/confirmation* loses after lag; use the anticipatory crossing instead (see s.21).
- **Data requirements**: OHLC.
- **Sources**: https://www.tradingview.com/support/solutions/43000501985-williams-r/ ; https://www.ireallytrade.com/

## 6. Street Smarts: Turtle Soup and Turtle Soup Plus One

- **Origin**: Connors & Raschke, *Street Smarts* (1995), ch. 1-2. Fetched summaries from technical.traders.com and roboforex agree on the core numbers.
- **Rules (Turtle Soup, buy)**:
  1. Today the market makes a new 20-day low (the lower the better).
  2. The *previous* 20-day low must have occurred at least **4 trading days** earlier.
  3. After the new low is made, place a buy stop **5-10 ticks above the previous 20-day low**. Good for today only.
  4. If filled, place a sell stop **1 tick below today's low**.
  5. If stopped out, re-enter at the original entry price on day 1 or 2 if it is re-triggered (book rule). Take profits over 2-6 days; trail the stop as the trade works.
  - Sell: mirror at a new 20-day high.
- **Turtle Soup Plus One**: identical, except the close of the day that makes the new 20-day low must be at or below the previous 20-day low; the buy stop is placed the **next** day at the previous 20-day low; stop 1 tick below the lower of the last two days' lows.
- **Intraday adaptation [interp]** (used by the sibling mean-reversion report s.13): 5-min RTH, level = prior-day low or 20-bar low with the prior extreme >= 4 bars old; price breaks the level by >= 2 ticks then a bar closes back above it -> buy stop 1 tick above the level; stop 1 tick below the breakout extreme (cap 0.5 x ATR); target 1 x ATR or VWAP; flat 15:55.
- **Evidence**: No statistics in the book; ProRealCode M30 forex "Turtle Soup" (5-bar lows, EMA 21/30 filter, 3 x ATR stop) reported "bad profit factor" though positive long-term; luxalgo: "regime-dependent, better in rotational markets". Evidence quality **2**.
- **Prop fit**: Good risk shape (stop at the failed-break extreme, typically 0.2-0.5 x ATR), low frequency, failures of *downside* breaks have the better record in 2023-2026 (shorts weaker).
- **Data requirements**: daily OHLC + 1-min.
- **Sources**: https://technical.traders.com/tradersonline/display.asp?art=2414 ; https://roboforex.com/blog/education/trading-strategies-that-were-a-revolution-three-strategies-of-linda-raschke/ ; https://www.prorealcode.com/prorealtime-trading-strategies/turtle-soup/ ; https://www.luxalgo.com/library/concept/turtle-soup.md

## 7. Street Smarts: 80-20s (and the 90-10 variant)

- **Origin**: *Street Smarts* ch. 3, crediting George Taylor and Steve Moore's statistics.
- **Rules (buy)**:
  1. Yesterday opened in the **top 20%** of its daily range and closed in the **bottom 20%** (80-20 day). Moore's version requires the close in the bottom 10% ("90-10") for the strongest statistic.
  2. Today, the market must trade **at least 5-15 ticks below yesterday's low** (mql5: 5 ticks; luxalgo: "a move back through the prior extreme").
  3. Place a buy stop at **yesterday's low**. If filled, initial stop at today's low; trail; **this is a day trade** - exit by the close (book).
  - Sell: mirror (open in bottom 20%, close in top 20%; today trades above yesterday's high; sell stop at yesterday's high).
  - mql5 implementation adds: yesterday's range > 20-day average range; one trade per day; optional TP = multiple of the extremum break.
- **Evidence**: Book: Moore's stat "close in the top/bottom 10% -> 80-90% chance of follow-through the next morning, but only ~50% chance of closing beyond"; mql5 (2016) EURUSD/USDJPY/XAUUSD daily 4-6 years: 233 trades, "marginal profitability... requires modernization". Evidence quality **2**.
- **Prop fit**: Rare (a few setups a month per instrument), objective, tight risk, day-trade by construction; best as an upgrade filter for the generic prior-day-extreme fade.
- **Data requirements**: daily OHLC + 1-min.
- **Sources**: https://www.mql5.com/en/articles/2785 ; https://www.luxalgo.com/library/concept/classic-bar-setups.md ; https://roboforex.com/blog/education/trading-strategies-that-were-a-revolution-three-strategies-of-linda-raschke/

## 8. Street Smarts: Momentum Pinball

- **Origin**: *Street Smarts* ch. 4. **[book]** for the entry mechanics; ProRealCode has the indicator.
- **Rules**:
  - LBR/RSI = 3-period RSI of the **1-day rate of change** (close - close[1]) on daily bars. (ProRealCode's "Momentum Pinball" indicator uses the same differencing idea with period 14 and 40/60 levels - that is a different parameterisation; the book uses 3 and 30/70.)
  - Buy day: yesterday's LBR/RSI closed **below 30**. Today: let the first hour (09:30-10:30) form. Place a buy stop above the first-hour high. If filled, stop at the first-hour low (book: "a few ticks below"). If the trade is profitable at the close, hold overnight and exit the next morning (exit on the open or on a trail). Day-trade version: exit at 15:55.
  - Sell day: LBR/RSI closed **above 70**; sell stop below the first-hour low; stop above the first-hour high.
  - If stopped out, re-enter once if the first-hour extreme is re-broken.
- **Evidence**: None independent found; the setup is a daily mean-reversion filter (3-period RSI of ROC < 30 = two to three down days) on top of a 60-minute ORB, and the ORB component has the modern literature behind it (sibling orb_session.md: IB/first-hour breakouts with context filters ~60-72% continuation). Evidence quality **1-2**.
- **Prop fit**: Very good structurally: trades at most once a day, after 10:30 (past the opening chaos), risk = first-hour range (ES ~15-30 pts, NQ 80-200 -> micros), directional filter from the prior days. Overnight hold must be dropped.
- **Data requirements**: daily closes + 1-min.
- **Sources**: https://www.prorealcode.com/prorealtime-indicators/momentum-pinball/ ; Street Smarts ch. 4 [book]

## 9. Street Smarts: Holy Grail (ADX + 20-EMA pullback)

- **Origin**: *Street Smarts* ch. 6. Also covered by the sibling trend_momentum.md s.10; the rule set here is the fetched tradingsetupsreview version.
- **Rules (long)**:
  1. 14-period ADX **> 30 and rising** (book: "30 and rising"; some sources use 20).
  2. Price retraces to the **20-period EMA** (tradingsetupsreview uses SMA; the book says EMA).
  3. Buy stop at the **high of the bar that touched the EMA**; if not filled and the next bar touches again, lower the stop to that bar's high.
  4. Initial stop below the recent swing low. Target: the recent swing high (take partial); trail the rest; cancel if ADX turns down.
  - Short: mirror with -DI dominant.
- **Evidence**: Book examples; tradingsetupsreview examples (HP daily winner, EUR/USD loser) and the caveat that high ADX often marks exhaustion. No quantified ES/NQ test. Evidence quality **2**.
- **Prop fit**: On 5-min ES/NQ RTH bars this is a pullback-in-trend-day entry with a tight stop (4-8 ES pts), ~50% win rate, 1.2-1.5 R: acceptable for the consistency rule in micros. ADX(14) on 5-min bars needs ~30 bars of history, so first signals come after 12:00 unless ADX is carried from the overnight session.
- **Data requirements**: OHLC.
- **Sources**: https://www.tradingsetupsreview.com/the-holy-grail-trading-setup/ ; https://roboforex.com/blog/education/trading-strategies-that-were-a-revolution-three-strategies-of-linda-raschke/

## 10. Street Smarts: ADX Gapper (trend-filtered Oops)

- **Origin**: *Street Smarts* ch. 7. **[book]**
- **Rules (buy)**: (1) ADX(14) > 30 **[book; some summaries say 20]** and +DI > -DI (established uptrend). (2) Today opens **below yesterday's low** (gap down against the trend). (3) Buy stop at yesterday's low. (4) Stop at today's low. (5) Trail; exit at the close or the next day; do not hold if the day closes under yesterday's low. Short: mirror in a downtrend (open above yesterday's high).
- **Evidence**: Book only. It is the Oops pattern (s.2) with a Wilder trend filter, i.e. the same mechanism as the "open outside the prior range" fade with the losing side (counter-trend) removed. Evidence quality **1-2**.
- **Prop fit**: Same as Oops, lower frequency, better expected directional accuracy; stop = open-to-prior-low distance (small).
- **Data requirements**: daily OHLC + 1-min.
- **Sources**: Street Smarts ch. 7 [book]; https://www.tradingview.com/support/solutions/43000502250-average-directional-index-adx/

## 11. Street Smarts: The Anti (stochastic hook against the slow line)

- **Origin**: *Street Smarts* ch. 8; roboforex summary gives the parameters.
- **Rules**: Slow stochastic with parameters **7, 10, 3** (7-period %K, smoothed 10 and 3; the book uses a 7-period stochastic with slow %K and %D). (1) %D (slow line) establishes the short-term trend direction, e.g. rising. (2) %K hooks against %D for 3-4 bars (pullback). (3) Enter when %K "hooks back" in the direction of %D: buy stop above the high of the hook bar. (4) Stop below the low of the hook bar (roboforex: "an SL under the minimum/maximum of the signal candlestick"). (5) "The order is held strictly one day"; day-trade: exit at the close. Works "on nearly any timeframe" (Raschke used it on 5-min to daily).
- **Evidence**: Book examples only. Evidence quality **1**.
- **Prop fit**: Pullback-continuation on 5-min bars; small stops; frequent signals. Needs a trend-day filter or it fades badly on rotational days.
- **Data requirements**: OHLC.
- **Sources**: https://roboforex.com/blog/education/trading-strategies-that-were-a-revolution-three-strategies-of-linda-raschke/

## 12. Street Smarts: Whiplash (climax reversal) - standard interpretation

- **Origin**: *Street Smarts* part 3 "Climax patterns", ch. 9. The book text was not retrievable; the rules below are the **[interp]** most standard objective reading used by implementations.
- **Rules (sell)**: Day 1: the market makes a new 20-day high. Day 2: trades above Day 1's high and then reverses to **close below Day 1's low** (outside-reversal "whiplash"). Day 3: sell stop 1 tick below Day 2's low; stop 1 tick above Day 2's high; exit at the close of Day 3 or on a 2-day time stop. Buy: mirror after a new 20-day low.
- **Evidence**: None; oxfordstrat's "Reversal Patterns part 2" (Wyckoff/Crabel/Appel outside-reversal entries at the open, 42 futures 1980-2019, $50 costs) gives the only related number: base case PF 0.97, CAGR -0.4%, win 34.5%, rated C; it only becomes positive with 8:1 reward:risk exits (CAGR 4.2%, Sharpe 0.70). Evidence quality **1**.
- **Prop fit**: Low frequency; large stop (Day-2 range); the oxfordstrat result says daily reversal patterns need huge targets, which is the wrong shape for the consistency rule. Low priority.
- **Data requirements**: daily OHLC + 1-min.
- **Sources**: https://oxfordstrat.com/trading-strategies/reversal-patterns-part-2/

## 13. Toby Crabel: Opening Range Breakout with the "Stretch", and ORB II

- **Origin**: Toby Crabel, *Day Trading with Short Term Price Patterns and Opening Range Breakout* (1990); x-trader.net "Descubriendo a Toby Crabel I-III" summarise the book; oxfordstrat tests a swing version.
- **Rules**:
  - **Stretch** = 10-day simple average of the smaller of (High - Open) and (Open - Low) on daily bars (x-trader: "la media movil de las ultimas 10 diferencias entre la apertura y el maximo o el minimo", whichever is smaller). oxfordstrat multiplies by 2.0.
  - Buy stop at Open + Stretch; sell stop at Open - Stretch. The first order filled is the position, the other becomes the reversal/protective stop. All positions liquidated at the close.
  - "The earlier in the session an entry triggers, the higher the probability of success": entries in the first 10 minutes are best; cancel unfilled orders after 5-10 minutes (ORB II) or by 10:30-11:30 (standard ORB).
  - **ORB II**: a wide-range, strongly directional bar in the first 5 minutes is itself the signal; enter in its direction immediately.
  - **Setups that raise the ORB hit rate**: Inside Day, NR4/NR7 (including dojis), Bull/Bear Hook, ID/NR4. Avoid ORBs after Wide-Spread days ("success rate drops notably").
  - **Gap rules (S&P specific)**: bigger gaps -> higher continuation probability; ORBs counter to the gap are "minimally profitable"; gaps unfilled by mid-session tend to continue; expect profit within ~30 minutes. Bonds and gold behave opposite to equity-index gaps.
- **Evidence**: Crabel's own S&P tables (1982-1989) show 60-71% profitable-at-close after NR4/ID setups (sibling trend_momentum.md s.6 cites one table: 203 trades, 71% profitable, avg win $343 / avg loss $289). oxfordstrat "Narrow Range N-day" and "NR7" tests (42 futures, 1980-2013/2016, stretch x2, 6 x ATR stop, 10-day time exit): rated **C**: "once the cost of trading is applied, the pattern is not currently tradeable without additional rules". "Wide Range N-day": **D**, net -$873k, CAGR -5.1%, Sharpe -1.45, MDD 88%, win 23.8%, PF 0.74, confirming "narrow range > wide range". Unger Academy 2025 "Testing Toby Crabel's ORB on Nasdaq" exists (captcha-walled). Evidence quality **3** for the setup statistics, **2** for net profitability.
- **Prop fit**: Best-shaped ORB in this family: the stretch on ES in 2025 is ~5-10 pts (NQ 25-60 pts), so stop = 2 x stretch is $500-1,000 per ES mini -> trade MES/MNQ. EOD exits produce fat tails; add a 0.5-1.0 x daily-ATR target. Trade only on NR4/ID/NR7 days (2-4 setups a week across ES/NQ/GC).
- **Data requirements**: OHLC only.
- **Sources**: https://www.x-trader.net/descubriendo-a-toby-crabel-ii/ ; https://www.x-trader.net/descubriendo-a-toby-crabel-iii/ ; https://oxfordstrat.com/trading-strategies/narrow-range/ ; https://oxfordstrat.com/?p=3707 ; https://oxfordstrat.com/trading-strategies/wide-range-pattern/ ; https://www.mql5.com/en/blogs/post/772126

## 14. Toby Crabel: ID/NR4 and NR7 bar breakouts (pattern-bar break instead of stretch)

- **Origin**: Crabel (1990); modern codifications by tradingsetupsreview and the mql5 "NR7 ORB EA".
- **Rules**:
  - NR4 = today's range is the narrowest of the last 4; NR7 = narrowest of the last 7; ID = high < prior high and low > prior low; ID/NR4 = both. Bull Hook = an NRx day that opens above the prior high and closes below the prior close; Bear Hook = opens below the prior low and closes above the prior close.
  - Entry: buy stop 1 tick above the pattern bar's high, sell stop 1 tick below its low; stop at the opposite end of the pattern bar; cancel if the next bar does not trigger (tradingsetupsreview). mql5 EA variant: compression zone = high/low of the 7-bar window, 1-pip break, stop at the other side, flat at session end, no new trades on the last candle.
  - tradingsetupsreview adds a trend filter: the last 7 bars entirely above (below) the 20-EMA for longs (shorts); warns against trading consecutive NR7s (congestion).
  - Intraday use: apply NR7/ID on 5-, 15- or 30-minute bars (mql5 recommends M30) with the same mechanics.
- **Evidence**: Crabel's tables; oxfordstrat NR7 study "C" (positive gross, fails $50 costs on daily swing exits); no modern net ES/NQ test. Evidence quality **2**.
- **Prop fit**: Tight, objective risk (pattern-bar range); works as the setup filter for s.13 and for the generic ORB; intraday 15/30-min NR7 breakouts give 1-3 trades a day.
- **Data requirements**: OHLC.
- **Sources**: https://www.tradingsetupsreview.com/inside-daynr4/ ; https://www.tradingsetupsreview.com/nr7-trading-strategy/ ; https://www.mql5.com/en/blogs/post/772126 ; https://oxfordstrat.com/?p=8148

## 15. Mark Fisher: ACD (A-up / A-down, C-up / C-down, pivot range)

- **Origin**: Mark B. Fisher, *The Logical Trader* (Wiley 2002); elitetrader excerpts of the 1,400-page ACD thread; TradingView "Session OR A-Lines" implementation. Also summarised in sibling orb_session.md s.2.2.
- **Rules**:
  - Opening range (OR): first N minutes of the session. Fisher: CL 45 min (pit 08:30 ET era; today 09:00-09:45), S&P ~20 min in the pit era; modern ES/NQ practice 5-15 min (09:30-09:45). "Counter-trend traders use a wider OR, breakout traders a narrower one."
  - A values: **20-25% of a 5- or 10-day ATR** (elitetrader excerpt: "Using 20% to 25% of either a 5 or 10 day ATR is a good start for both the A and C values"); Fisher's CL example A = 0.08, C = 0.13. TradingView script defaults: A = 0.5% of OR, C = 1-2% of OR (a different scaling).
  - A-up = OR high + A; confirmed long when price **holds above A-up for a time window** (standard: half the OR length, e.g. 7-8 min for a 15-min OR) - "price needing to spend a certain amount of time above/below A/C levels to enter". Stop: back inside the OR (the OR high for longs) or the low of the confirmation bar on strong days; "minimize your risk by time, not by price".
  - Failed A: an A-up that fails and trades to C-down (OR low - C) is a C-down reversal short with the stop above the OR. "Only the first fade at the A level has reliable edge."
  - Pivot range: daily pivot P = (H+L+C)/3; second number = (H+L)/2; pivot range = P +/- |P - (H+L)/2|. Narrow pivot ranges (and 3 consecutive small pivots) precede volatile sessions; trade with the bias when price is above/below the pivot range. 3-day rolling pivot for swing bias.
  - Fisher's own framing: "ACD is about RISK management. There is no edge in ACD other than a viable method to control your risk."
- **Evidence**: Anecdotal; Fisher's statistics: the 5-min OR is the high or low of the day ~15-18% of the time for CL; the thread claims ~75% win rate on *longer-term* confirmed trades. No rigorous public backtest. Evidence quality **1-2**.
- **Prop fit**: As a wrapper (time-confirmed breakout, failed-A reversal, trade the first A only) it fixes the two biggest ORB failure modes (wick breaks, re-triggering). A = 0.2 x ATR(10) on ES in 2025 = 12-16 pts, so an A-up long with the OR low as stop risks 25-40 pts ($1,250-2,000 per mini): micros only, or use the confirmation-bar low.
- **Data requirements**: OHLC only.
- **Sources**: https://www.elitetrader.com/et/threads/excerpts-from-the-1400-page-acd-method-thread-mark-fisher.377419/ ; https://www.tradingview.com/script/RMlgLTOl-Dr-Yazdani-V063-Session-OR-A-Lines/ ; https://nexusfi.com/a/strategies/acd-trading-method (403)

## 16. Perry Kaufman: KAMA with the standard-deviation filter, and the Efficiency Ratio as a regime filter

- **Origin**: Kaufman, *Smarter Trading* (1995) and *Trading Systems and Methods* (ch. 17, "Adaptive techniques"), pp. 436-438 cited by Ehlers. **[book]** (Wikipedia/stockcharts pages were unreachable this session).
- **Rules**:
  - Efficiency Ratio ER(n) = |C - C[n]| / sum_{i=1..n} |C_i - C_{i-1}|, n = 10.
  - Smoothing constant SC = [ER x (fast - slow) + slow]^2 with fast = 2/(2+1) = 0.6667, slow = 2/(30+1) = 0.0645.
  - KAMA = KAMA[1] + SC x (C - KAMA[1]).
  - Kaufman's trading rule: buy when KAMA turns up by more than a **filter = 1.0 x standard deviation of the 1-bar KAMA changes over the last 20 bars** (he suggests 0.1-1.0 x); sell/exit when KAMA turns down by more than the filter. Variant: price crossing KAMA.
  - Efficiency Ratio filter: treat ER > ~0.3 as "trending" (take breakouts/trend entries) and ER < ~0.3 as "noisy" (mean-revert or stand aside). Kaufman also publishes a noise-adjusted breakout length (shorter lookbacks in high-noise markets).
- **Evidence**: Kaufman's own daily tests across futures and stocks (1990s); Ehlers' MAMA paper cites KAMA as the volatility-adaptive predecessor. No modern intraday ES evidence. Evidence quality **2**.
- **Prop fit**: As a signal generator it is a lagging trend-follower (bad shape intraday). As a **regime filter** (ER on 5-min or daily bars) it is cheap and objective: use ER(10, daily) > 0.3 to allow breakout strategies and < 0.3 to allow fades.
- **Data requirements**: OHLC.
- **Sources**: https://www.mesasoftware.com/papers/MAMA.pdf (cites Kaufman pp. 436-438); Kaufman, Trading Systems and Methods [book]

## 17. Tom DeMark: TD Setup (9) and TD Sequential Countdown (13)

- **Origin**: DeMark, *The New Science of Technical Analysis* (1994); rules per demark.com "Sequential indicator" page (fetched).
- **Rules**:
  - Price flip: close < close[4] after a close > close[4] (bearish flip starts a buy setup).
  - **TD Buy Setup**: 9 consecutive closes less than the close 4 bars earlier. **Sell Setup**: 9 consecutive closes greater than the close 4 bars earlier. Perfected when the low of bar 8 or 9 is below the lows of bars 6 and 7 (sell: highs above). TDST = the extreme of the setup (buy setup's highest high / sell setup's lowest low) used as the risk/target level.
  - **TD Countdown**: starts at bar 9; counts (non-consecutively) closes <= the low 2 bars earlier (buy) / >= the high 2 bars earlier (sell) until 13. Deferral: the 13 bar's low must be <= the close of countdown bar 8 (buy); otherwise "+". Cancellation if an opposite setup completes or a TDST is violated; recycling if an overlapping setup reaches 22 bars or its range is 100-200% of the prior setup. Reversal expected within 12 bars of the 13.
  - Standard trading rule **[interp]**: buy on the close of setup bar 9 (aggressive) or countdown 13; stop = lowest low of the setup minus that bar's true range ("risk level"); target the TDST.
- **Evidence**: No independent ES/NQ test found; academic tests exist mainly on crypto/equities with mixed results (not fetched). demark.com sells the indicator. Evidence quality **1-2**.
- **Prop fit**: On 5-min RTH bars a 9-count takes 45 minutes and a 13 takes hours, so 0-2 signals a day; exhaustion entries against the trend have a poor shape on trend days. Low priority; the 9-count is usable as a "do not chase" filter for breakout systems.
- **Data requirements**: OHLC.
- **Sources**: https://demark.com/sequential-indicator/

## 18. Kevin Davey: Strategy Factory, published price patterns and the 567,000-backtest exit study

- **Origin**: Kevin Davey, *Building Winning Algorithmic Trading Systems* (2014), kjtradingsystems.com articles (fetched).
- **What is codeable**:
  - **15 price patterns** (article): e.g. (1) count up/down closes over BCount bars, go long if more ups and close < close[pullback] (pullback momentum); (3) short when consecutive up-closes >= BCount and close > close[PCount] (counter-trend); (12-14) outside/inside bar sequences with momentum direction; (15) morning/evening doji star with 10-bar momentum, sample shown on 90-minute mini S&P. Davey shows "non-optimized" sample equity curves, not statistics.
  - **Exit study** (40 futures, 60-min to daily bars, 2010-2020, 5 entry types x 15 exit types): "Stop & Reverse is still the best"; dollar target second, breakeven stop third; "dollar-based exits are generally better than ATR exits; target exits are generally better than stop exits"; trailing, parabolic, chandelier and indicator exits all under-performed; **only metals and stock indices had positive average returns**.
  - Davey's Mini S&P 500 strategy is "fully disclosed" (TradeStation code) to course members: $121k+ hypothetical OOS per contract over 5 years; rules not public.
  - Process rules that matter for our loop: limited-parameter entries, walk-forward, Monte Carlo on OOS trades, no re-optimising after a loss.
- **Evidence**: Vendor/author backtests; the exit study is large but not independently replicated. Evidence quality **2**.
- **Prop fit**: The exit study is directly actionable for Lucid: fixed-dollar targets ($150-400 per MES/MNQ day) and breakeven stops are exactly what the 5 x $150 payout-day rule and the consistency rule reward; ATR trailing stops are not.
- **Data requirements**: OHLC.
- **Sources**: https://kjtradingsystems.com/15-algo-trading-price-patterns.html ; https://kjtradingsystems.com/algo-trading-exits.html ; https://kjtradingsystems.com/

## 19. Andrea Unger / Unger Academy: bias and mean-reverting ES strategies

- **Origin**: Unger Academy blog (2023-2025). Only blog2 post 102 is fetchable (sibling intraday_mean_reversion.md s.11-12 extracted it); the posts "We tested Larry Williams' Oops", "Testing Toby Crabel's ORB on Nasdaq", "How to exploit Gold futures' recurring patterns (2 lines of code)", "Trading the Mini S&P 500: an unusual strategy", "Trading myths on the test bench" are captcha-walled.
- **Codeable Unger rules (from post 102)**:
  - Strategy 1 (ES, 15-min bars): long when a bar closes back **above the previous session's low** after trading below it; short when a bar closes back below the previous session's high. Stop $1,300, target $4,000 per ES; exit at session end. ~750 trades over ~6-7 years, avg ~$300/trade; 2022 +$15k, 2023 +$18k per ES.
  - Strategy 2: limit buy at the current session low minus an offset; stop $800, target $3,000; ~1,800 trades, avg ~$140.
  - Unger's "bias" method **[interp of the gold post title]**: compute average open-to-close P&L by hour-of-day and day-of-week over 10+ years; trade the recurring window with a time stop (the gold article's "2 lines of code" is a buy-at-time / sell-at-time rule).
- **Evidence**: Vendor backtests with OOS claims, no slippage disclosure. Evidence quality **2**.
- **Prop fit**: Strategy 1 is a Turtle-Soup-style re-cross with large targets (low win rate -> bad for consistency); use the trigger with a 0.5 x ATR stop and prior-close target. Time-of-day biases on GC are testable directly on our 1-min data.
- **Data requirements**: OHLC.
- **Sources**: https://blog2.ungeracademy.com/?p=102 ; https://ungeracademy.com/blog/how-to-exploit-gold-futures-recurring-patterns-with-2-lines-of-code (blocked) ; https://ungeracademy.com/blog/testing-toby-crabel-s-opening-range-breakout-does-it-really-work-code-backtest-on-nasdaq (blocked)

## 20. Art Collins: *Beating the Financial Futures Market* biases (ES/NQ/Russell/bonds, open-to-close)

- **Origin**: Art Collins (Wiley 2006, with Robert Pardo); Better System Trader ep. 73 (fetched); Scribd TOC (search snippet confirms the systems "15 Day High-Low Average" and "Fading Two Same-Way Open-to-Closes" with TradeStation code from p. 205). Rules below are **[book]** from the TOC and the interview.
- **Rules (daily, trade open-to-close, no intraday stop in the book)**:
  - Fade two same-way open-to-closes: if the last two days both closed above their opens, sell at today's open and cover at the close; if both closed below their opens, buy the open, sell the close (interview example: "two out of the last three open-to-close moves were down, so tomorrow should be a buyer").
  - 15-day high-low average: buy the open when yesterday's close is above the 15-day average of (H+L)/2, sell when below (trend bias), exit on close.
  - Day-of-week biases (long bias early in the week in the S&P), open-vs-prior-close biases, and S&P/Nasdaq/Russell cross-confirmation.
  - Combination: score each bias +1/-1 like card counting; trade only when the net score exceeds a threshold ("combining small biases").
  - His 4 optimization rules: results must be in a "good neighbourhood", work across related markets (S&P, Russell, Nasdaq), profits spread through the test period, hypothesis stated in advance.
- **Evidence**: Book tables 1990s-2005 (not retrievable); no modern OOS. Evidence quality **2**.
- **Prop fit**: Open-to-close holds without a stop expose the account to the full daily range (ES 2025: $2,500-4,000 per mini on a bad day) which can breach the $2,000 intraday floor in one session; usable only in 1-3 micros, or as a **directional filter** for the intraday systems above (e.g. take only ORB longs when the Collins score is positive).
- **Data requirements**: daily OHLC (Yahoo) for scores; 1-min for execution.
- **Sources**: https://bettersystemtrader.com/073-simple-concepts-to-build-robust-stratgies-art-collins/ ; https://www.scribd.com/document/507754748/ (TOC only)

## 21. John Ehlers: MAMA/FAMA crossover, roofing-filter stochastic (anticipatory), and PDF-inferred RSI/Fisher strategies

- **Origin**: Ehlers, mesasoftware.com papers (fetched PDFs: MAMA.pdf; "Predictive Indicators for Effective Trading Strategies" (2013); "Inferring Trading Strategies from Probability Distribution Functions" (2008); "A procedure to evaluate trading strategy robustness").
- **Rules**:
  - **MAMA/FAMA**: price = (H+L)/2; Hilbert-transform homodyne discriminator measures the dominant cycle period; alpha = FastLimit / DeltaPhase bounded to [SlowLimit, FastLimit] with FastLimit = 0.5, SlowLimit = 0.05; MAMA = alpha x price + (1 - alpha) x MAMA[1]; FAMA = 0.5 x alpha x MAMA + (1 - 0.5 alpha) x FAMA[1]. Long when MAMA crosses above FAMA, exit/short on the opposite cross (code in the paper).
  - **Roofing filter + stochastic (anticipatory)**: 2-pole high-pass with 48-bar critical period, then SuperSmoother with 10-bar period (code listing 2), then a stochastic of the filtered series (e.g. 20 bars). Ehlers' demonstration: on **10 years of daily S&P futures**, buying when the roofed stochastic turns up through 20% (confirmation) **loses consistently**, while buying when it **crosses below 20%** (anticipating the trough) and shorting when it **crosses above 80%** "obtains consistent winners" (equity curve only, no table).
  - **PDF-inferred strategies** (US T-bond futures, 5 years to 2007-12-07, 1 contract, no costs, fixed parameters): (a) Channel-cycle: normalise close within the N-bar channel, band-pass, enter on sine/cosine crossings; (b) Generic RSI: smoothed RSI; sell short when it crosses *above* the upper threshold, buy when it crosses *below* the lower threshold (anticipatory, no confirmation); (c) High-pass + Fisher transform with the same anticipatory thresholds. All three **reverse the position if the trade moves against entry by a set percentage** (trend-continuation guard). Results: Channel: $54,968, 142 trades, 53.5% win, PF 1.72, DD $15,520; RSI: $72,468, 119 trades, 57.1%, PF 2.05, DD $11,625; Fisher: $73,125, 135 trades, 57.0%, PF 2.10, DD $9,125. Monte Carlo annualised: Channel most-likely $11,650 / DD $7,647 (88% chance of break-even or better); RSI $17,085 / $6,219 (96.6%).
  - MAMA test: 100 stocks 1998-2001, long only, 1,317 trades, 37.5% profitable, $4.86/share average vs ~$0.30 costs, 4.4 trades/yr/stock.
  - Robustness paper: optimise with a genetic algorithm (population 40, keep 2,000 tests); the ratio of the median test's net profit to the best test's net profit (~75%) is the expected OOS retention; one Ehlers intraday strategy had 692 trades over 2015-01 to 2018-06.
- **Evidence**: Author's own tests, no costs, bonds/daily; nothing on ES/NQ intraday. Evidence quality **2-3** (numbers published, single author, no OOS).
- **Prop fit**: The anticipatory oscillator with an adverse-excursion reversal is a natural 5-minute ES mean-reversion engine (57% wins, PF ~2 in his data): small stops, several trades a day, EOD flat. The reversal rule turns losers into trend trades, which also caps single-day loss. Highest-priority Ehlers item; MAMA/FAMA is too slow intraday.
- **Data requirements**: OHLC.
- **Sources**: https://www.mesasoftware.com/papers/MAMA.pdf ; https://www.mesasoftware.com/papers/PredictiveIndicators.pdf ; https://www.mesasoftware.com/papers/InferringTradingStrategies.pdf ; https://www.mesasoftware.com/papers/ROBUSTNESS.pdf ; https://www.mesasoftware.com/papers/

## 22. Welles Wilder: DMI/ADX crossover with the extreme-point rule, Parabolic SAR, RSI, Volatility System

- **Origin**: Wilder, *New Concepts in Technical Trading Systems* (1978). TradingView ADX page fetched; the rest **[book]**.
- **Rules**:
  - DMI: +DM = H - H[1] if > L[1] - L and > 0 else 0; -DM mirror; +DI = 100 x Wilder-smoothed(+DM)/ATR, 14 periods; ADX = Wilder-smoothed |+DI - -DI| / (+DI + -DI) x 100. Trend if ADX > 25 (20-25 indeterminate). **Crossover rule**: buy when +DI crosses above -DI with ADX > 25; the stop is the extreme point (the low of the crossover bar); the signal stays valid even if the DIs re-cross unless the extreme point is breached.
  - Parabolic SAR: SAR_next = SAR + AF x (EP - SAR); AF starts 0.02, +0.02 per new extreme, max 0.20; always in the market, stop-and-reverse.
  - RSI(14): 30/70; failure swings.
  - Volatility System: ARC = 3 x ATR(7); SAR = significant close +/- ARC; stop-and-reverse.
- **Evidence**: Historical; sibling trend_momentum.md s.13 covers modern tests (Indian equities, SPX options overlays). No ES intraday net evidence. Evidence quality **2**.
- **Prop fit**: ADX as a *filter* (trend-day vs rotation) is the useful piece; SAR/DMI crossover systems whipsaw intraday. Davey's exit study ranks parabolic exits below dollar targets.
- **Data requirements**: OHLC.
- **Sources**: https://www.tradingview.com/support/solutions/43000502250-average-directional-index-adx/

## 23. Charles LeBeau: Chandelier exit, Yo-Yo exit, ADX filter

- **Origin**: LeBeau & Lucas, *Technical Traders Guide to Computer Analysis of the Futures Market* (1992); LeBeau's "System Traders Club" bulletins. **[book]**
- **Rules**: Chandelier exit (long) = highest high since entry - 3 x ATR(22) (LeBeau used 2.5-4 x; stockcharts default 22/3); Yo-Yo exit = yesterday's close - 2 x ATR (re-anchored every bar; catches one-day reversals); ADX rule: trade trend systems only when ADX(14) > 20 **and rising**; counter-trend when ADX is falling from above 30. His "25 x 25" bond system: enter when the close exceeds the close 25 days ago and ADX(14) is rising, exit on a 25-day... (exact exit not retrievable) **[approx]**.
- **Evidence**: None modern; Davey's exit study found chandelier exits below dollar targets. Evidence quality **1-2**.
- **Prop fit**: Exits only; the Yo-Yo (close - 2 x ATR on 5-min bars) is a sensible intraday disaster stop that moves with volatility.
- **Data requirements**: OHLC.
- **Sources**: https://kjtradingsystems.com/algo-trading-exits.html (chandelier ranking)

## 24. David Bean / Capstone Trading Systems: ES/NQ gap-fill, gap-continuation, open-range and reversal day-trade systems

- **Origin**: David Bean, *Seven Trading Systems for the S&P Futures* (2010, EasyLanguage disclosed) and *Algorithmic Trading Systems: Advanced Gap Strategies for the Futures Markets*; Capstone product pages (fetched, hypothetical, 1 contract, slippage/commission **not disclosed**; algorithmictradingreviews.org rated the vendor 5/10 for exactly that reason).
- **Rules (as disclosed)**:
  - Four gap types **[book description]**: open above yesterday's high; open inside the range above the close; inside the range below the close; open below yesterday's low. Gap Fill = fade toward the prior close with a PT/SL ratio; Gap Continuation = trade in the gap direction when "early momentum aligns with the initial move".
  - ES GAPF I (700 PT / 500 SL): entry **09:32 ET** every qualifying day, mean reversion; stats 614 trades, 63.2% wins, PF 1.21, avg win $442 / avg loss -$633, max DD $12,538, Sharpe 0.62; by year 2021 +$8,575, 2022 +$5,825, 2023 +$15,925, **2024 -$100, 2025 +$475, 2026 YTD -$3,675**.
  - ES Mirror 2020: long only, entry **09:31 ET**, stop $525, target $675, 415 trades, 50.6% wins, PF 1.22, DD $9,225; 2023 +$8,263; **2024 -$1,275, 2025 -$375, 2026 -$2,625**.
  - Gap Continuation 2020 NQ: long-only continuation, max loss $1,225/trade (~49 NQ pts), 506 trades 2017-2026, 59.5% wins, PF 1.87, avg win $982 / loss -$771, DD $10,090, Sharpe 1.42; 2020 +$22,575, 2021 +$20,815, 2022 +$16,115, 2023 +$21,955, **2024 +$28,190, 2025 +$6,090, 2026 +$6,645**. Marketed as prop-firm suitable.
  - Gap Continuation 2026 NQ: 732 trades, 57.7% wins, PF 1.83, avg trade $164, stop $1,225, DD $6,585, exits by 15:30; **2024 +$23,655, 2025 +$10,520, 2026 +$5,705**.
  - NQ GAPC 2024: 1,096 trades, 47.0% wins, PF 1.38, avg $196, largest loss -$1,270, DD $18,210; **2024 +$23,790, 2025 +$9,960, 2026 +$11,615**; trades 10:30-15:30.
  - NQ Open Range 2026: 1,127 trades, 37.4% wins, PF 1.45, avg $258, avg win $2,213 / loss -$912, largest loss -$1,025, DD $17,755, Sharpe 1.17; **2024 +$62,510, 2025 +$39,880, 2026 +$28,465** (2019 -$5,090).
- **Evidence**: Vendor hypotheticals with an unusually long year-by-year record; no slippage; systems are periodically re-released (2019/2020/2022/2023/2024/2026 versions = survivorship). Evidence quality **2**.
- **Prop fit**: The *shape* of the NQ continuation systems (57-60% wins, avg win ~1.3 x avg loss, $1,225 stop) is prop-friendly in micros (MNQ stop $122); the ES gap-fill shape (63% wins but avg loss > avg win and PF 1.21) is fragile and has decayed. The open-range system's 37% win rate with $2,213 average winners is the wrong shape for the 50% consistency rule.
- **Data requirements**: OHLC; Bean's gap definitions use the RTH prior close (16:00 settlement vs 16:15 close must be fixed).
- **Sources**: https://capstonetradingsystems.com/pages/trading-systems ; https://capstonetradingsystems.com/products/es-gapf-i-700-pt-500-sl ; https://capstonetradingsystems.com/products/es-mirror-2020 ; https://capstonetradingsystems.com/products/gap-continuation-2020-nq ; https://capstonetradingsystems.com/products/gap-continuation-2026-nq ; https://capstonetradingsystems.com/products/nq-gapc-2024 ; https://capstonetradingsystems.com/products/nq-open-range-2026 ; https://books.apple.com/us/book/seven-trading-systems-for-the-s-p-futures/id460008338 ; https://algorithmictradingreviews.org/2018/05/24/capstone-trading-systems/

## 25. Howard Bandy: short-horizon mean reversion, CAR25 / safe-f

- **Origin**: Bandy, *Mean Reversion Trading Systems* (2013), *Quantitative Technical Analysis* (2015); Better System Trader ep. 61 and 6 (fetched).
- **Rules [book, standard form]**: daily equities/ETFs; z-score of close vs its 20-day mean (or RSI(2)/DV2); buy at the close when z < -1.5 (RSI(2) < 10); exit at the close when z > 0 (RSI(2) > 70) or after 3-5 days; no stops (stops hurt mean reversion in his tests). Objective function CAR25 (25th-percentile compound return from Monte Carlo of trade outcomes); position size = safe-f such that P(DD > 20% over 2 years) < 5%. His stated benchmark for a competitive system: "65% or better accuracy", holding 1-2 days, 20-40 trades a year.
- **Evidence**: Author's tests on US equities; the framework (CAR25/safe-f) is directly reusable for our Monte-Carlo monthly-pass-rate engine. Evidence quality **2**.
- **Prop fit**: Multi-day equity mean reversion is not tradable here; the sizing framework is. His accuracy/holding-period benchmark argues for intraday strategies with >= 60% win rate and small targets, which matches the Lucid consistency and payout-day rules.
- **Data requirements**: n/a (framework).
- **Sources**: https://bettersystemtrader.com/061-foundations-of-trading-howard-bandy/ ; https://bettersystemtrader.com/006-dr-howard-bandy/

## 26. Brent Penfold: price-bar pattern portfolio (P24)

- **Origin**: Penfold, *The Universal Principles of Successful Trading* (2010); Better System Trader ep. 101 (fetched).
- **Rules**: 1-5 bar daily OHLC patterns, e.g. key reversal bar = "today opens below yesterday's close, makes a higher high, then closes lower than yesterday's close" (sell signal next day below the low); any pattern must show positive expectancy across a 24-market universal portfolio (currencies, rates, indices, energies, metals, softs, grains, meats) before being used; short/medium/long-term versions; no indicator parameters.
- **Evidence**: Author's portfolio tests, no numbers published. Evidence quality **1**.
- **Prop fit**: Daily patterns with next-day stop entries; same shape as Smash Day / Whiplash (low frequency, range-sized stops). The "must work across the whole portfolio" acceptance test is a useful robustness criterion for ES/NQ/GC.
- **Data requirements**: daily OHLC + 1-min.
- **Sources**: https://bettersystemtrader.com/101-trading-price-patterns-with-brent-penfold/

## 27. Jake Bernstein: *The Compleat Day Trader* 30-minute breakout and gap methods

- **Origin**: Bernstein (McGraw-Hill 1995, 2nd ed. 2007). **[book]**; no fetchable source with the rules.
- **Rules (as published, standard form)**: (a) 30-minute breakout: range of the first 30 minutes (09:30-10:00); buy stop above / sell stop below; stop at the opposite side; exit at the close; (b) Gap method: if the open gaps beyond yesterday's close and the market then trades back through the open in the direction of the gap fill, fade the gap toward yesterday's close, stop beyond the day's extreme; (c) MACD/momentum divergence day-trade timing; (d) day-of-week/seasonal filters.
- **Evidence**: Book tables only; the 30-min ORB is covered by the modern ORB literature (sibling orb_session.md: ORB-30 with close confirmation and 0.25-0.5 x range targets is among the best-shaped). Evidence quality **1** for Bernstein's specifics.
- **Prop fit**: Covered under ORB-30 in orb_session.md.
- **Data requirements**: OHLC.
- **Sources**: sibling report research/families/orb_session.md

## 28. Murray Ruggiero: report-day fade, intermarket bond/S&P filters, adaptive channel breakout

- **Origin**: Ruggiero, *Cybernetic Trading Strategies* (1997); Better System Trader ep. 42 (fetched).
- **Rules**: (a) Report-day trade: "Traders overreact before major economic announcements": sell a strong pre-report rally / buy a strong pre-report sell-off; "won 63% of report day trades"; (b) Intermarket: use a moving-average cross of the related market (T-bonds for the S&P; utilities for bonds; XAU for gold) as the directional filter; divergence (S&P down while bonds up) = buy S&P; rules invert at 2.6 standard deviations (rough-sets finding); (c) adaptive channel breakout: channel length = measured dominant cycle (MESA) so breakouts shorten in fast markets. Robustness test: average net profit across the whole parameter grid >= 2 x its standard deviation, profitable across the whole range.
- **Evidence**: Book and interview claims; no modern OOS. Evidence quality **1-2**.
- **Prop fit**: Intermarket filters are codeable from Yahoo daily (ZB/ZN vs ES); the report-day rule needs an economic calendar (**flag: external data**) - our 1-min data lets us approximate with fixed times (08:30 ET releases, 10:00 ET, 14:00 FOMC) but not with the release calendar itself.
- **Data requirements**: daily cross-market data (Yahoo), economic calendar (not available).
- **Sources**: https://bettersystemtrader.com/042-murray-ruggiero/

## 29. Thomas Stridsman: Meander system (volatility-band open fade) and *Trading Systems That Work*

- **Origin**: Stridsman, *Trading Systems That Work* (2000) and *Trading Systems and Money Management* (2003). **[book, approx]**
- **Rules (Meander, standard interpretation)**: over the last 5 days compute the percentage distance of each day's O, H, L, C from the previous close (20 observations); mean m and standard deviation s; the "meander" band for today = yesterday's close x (1 + m +/- s). Buy on the open if the open is below the lower band (an unusually weak open), sell on the open if above the upper band; exit on the close (day trade) or next open; no stop in the original, Stridsman adds a 1-2 x ATR stop in later versions. Also from the books: "Harris 3L-R" (three lower lows then reversal), "Dynamic Breakout" (Pruitt; lookback length scaled by 20-day volatility ratio), "Hybrid System No. 1".
- **Evidence**: Book tests on S&P/other futures 1990s (positive, modest); no modern test. Evidence quality **1**.
- **Prop fit**: Meander is an objective "open outside the expected band -> fade" rule, i.e. a volatility-normalised cousin of Oops/80-20/opening-gap fades; worth including as a parameterisation of the gap-fade family with a stop at the day's extreme.
- **Data requirements**: daily OHLC + 1-min.
- **Sources**: Stridsman (2000) [book]

---

## 30. What the evidence says works in 2022-2026 (and what does not)

1. **Direct 2024-2026 numbers exist only from Capstone** (s.24): NQ gap-continuation and open-range day trades stayed profitable every year 2020-2026 in hypothetical no-slippage tests, with 2025 the weakest year (+$6k to +$40k per NQ), while ES gap-fill (09:32 fade) and ES 09:31 long-reversal systems were flat-to-negative in 2024, 2025 and 2026. The same sign pattern appears in the sibling ORB/mean-reversion sweeps (NQ ORB with trend filter OOS Sharpe 1.10 2023-2026; opening-gap fades decaying). **Bias the backtest queue toward NQ/MNQ continuation after the open, ES/MES fades only with tight time stops.**

2. **Costs decide everything in this family.** oxfordstrat's multi-decade tests of Crabel narrow-range ORB and Williams Oops are gross-positive and net-of-$50 marginal; the sibling replication of the Zarattini 5-min ORB on NQ nets +0.002R. The Capstone stats exclude slippage. For MES/MNQ assume 1 tick + commission ~$1.50-2.00 round turn per micro contract and 2 ticks on stop fills; any candidate whose gross edge is < 3 ticks/trade is dead.

3. **Exit design is where the published evidence is strongest and most transferable**: Davey's 567k-backtest study (2010-2020, 40 futures) says dollar targets > ATR targets, targets > stops, breakeven stops third, trailing/parabolic/chandelier worse; only indices and metals positive. Ehlers shows confirmation-based oscillator entries lose and anticipatory entries win on daily S&P. Together with the Lucid payout rule (5 days >= $150) this argues for: fixed dollar targets ($150-400/day on micros), breakeven after 1R, hard EOD flat, no trailing stops.

4. **Pattern filters still carry information**: Crabel's narrow-range/inside-day setups precede expansion (oxfordstrat: narrow range > wide range by a wide margin, D-rated wide range PF 0.74); Momentum Pinball's 3-period RSI-of-ROC and 80-20's open/close location filters select days where the prior-day extreme is more likely to be a failed break. These are cheap daily filters to layer onto the ORB / prior-day-level engines.

5. **Dead or unusable here**: Turtle entries on ES/NQ (multi-week, overnight), TD Sequential (rare, discretionary), KAMA/MAMA crossovers (lag), Collins' stop-less open-to-close holds (single-day loss can hit the $2,000 intraday floor), Ruggiero's intermarket/report trades (data), Bandy's multi-day equity reversion.

6. **Backtest queue derived from this family (concrete first parameter sets, ET)**:
   - F1 Crabel stretch ORB, NR4/ID/NR7 days only, close-confirmed 1-min break of Open +/- Stretch(10) between 09:31 and 10:30, stop = 1 x stretch beyond the open (not the full reverse), target = 0.5 x 14-day ATR, flat 15:55. MES/MNQ/MGC.
   - F2 Momentum Pinball: daily LBR/RSI(3 of ROC1) < 30 -> long only; buy stop above the 09:30-10:30 high after 10:30; stop = first-hour low capped at 0.5 x ATR; target 1 x first-hour range; flat 15:55.
   - F3 80-20 / Turtle Soup prior-day-extreme re-entry: setup = 80-20 day or 20-day-low day; today trades >= 5 ticks beyond the level; stop order at the level; stop = today's extreme (cap 0.5 x ATR); target = prior close; active 09:30-13:00.
   - F4 Williams volatility breakout: open + 0.6 x prior range (and - 0.6 for shorts), ZB close > ZB close 5 days ago for longs only, dollar stop $150-250 per micro, EOD exit; TDW as a tested parameter.
   - F5 ACD wrapper: OR 09:30-09:45, A = 0.2 x ATR(10, daily), long only after 8 consecutive minutes above A-up, stop = confirmation-bar low, failed-A reversal short at C-down = OR low - 0.3 x ATR with stop above OR high; one A trade per day.
   - F6 Ehlers anticipatory oscillator on 5-min ES: roofing filter (48/10), stochastic(20) of the filtered series; long when it crosses below 0.2, short when above 0.8; reverse if adverse excursion > 0.4 x ATR; exit on the opposite signal or 15:55; skip 09:30-09:45.
   - F7 Capstone-style NQ gap continuation: open outside yesterday's RTH range or beyond the close by > 0.3 x ATR; wait for the 09:30-09:45 range; enter on a close-confirmed break in the gap direction; stop $120 per MNQ (~50 pts/10 = micro equivalent of Bean's $1,225), target 1.3 x stop, flat 15:30.
   Filters to test on all of them: Kaufman ER(10, daily) regime; ADX(14, daily) > 25; Collins two-same-way-closes score; Turtle "skip after a winner".

---

## Sources (consolidated)

- Turtle: https://www.tradingblox.com/originalturtles/ ; https://www.tradingblox.com/originalturtles/originalturtlerules.pdf
- Williams Oops: https://oxfordstrat.com/trading-strategies/bull-oops-pattern/ ; https://www.mql5.com/en/articles/21741 ; https://forge.mql5.io/CHACHAIAN/lwOopsPatternExpert ; https://www.tradingview.com/script/7Gqs0Sqn-Larry-Williams-Oops-Strategy/ ; https://www.luxalgo.com/library/concept/classic-bar-setups.md
- Williams Smash Day / misc: https://www.prorealcode.com/topic/larry-williams-smash-day/ ; https://www.prorealcode.com/?s=larry+williams ; https://www.ireallytrade.com/
- Williams %R: https://www.tradingview.com/support/solutions/43000501985-williams-r/
- Street Smarts: https://technical.traders.com/tradersonline/display.asp?art=2414 ; https://roboforex.com/blog/education/trading-strategies-that-were-a-revolution-three-strategies-of-linda-raschke/ ; https://www.mql5.com/en/articles/2785 ; https://www.tradingsetupsreview.com/the-holy-grail-trading-setup/ ; https://www.prorealcode.com/prorealtime-trading-strategies/turtle-soup/ ; https://www.prorealcode.com/prorealtime-indicators/momentum-pinball/ ; https://www.luxalgo.com/library/concept/turtle-soup.md
- Crabel: https://www.x-trader.net/descubriendo-a-toby-crabel-ii/ ; https://www.x-trader.net/descubriendo-a-toby-crabel-iii/ ; https://oxfordstrat.com/trading-strategies/narrow-range/ ; https://oxfordstrat.com/?p=3707 ; https://oxfordstrat.com/?p=8148 ; https://oxfordstrat.com/trading-strategies/wide-range-pattern/ ; https://www.tradingsetupsreview.com/inside-daynr4/ ; https://www.tradingsetupsreview.com/nr7-trading-strategy/ ; https://www.mql5.com/en/blogs/post/772126 ; https://nexusfi.com/a/strategies/opening-range-breakout
- Fisher ACD: https://www.elitetrader.com/et/threads/excerpts-from-the-1400-page-acd-method-thread-mark-fisher.377419/ ; https://www.tradingview.com/script/RMlgLTOl-Dr-Yazdani-V063-Session-OR-A-Lines/ ; https://nexusfi.com/a/strategies/acd-trading-method
- Kaufman: https://www.mesasoftware.com/papers/MAMA.pdf (citation) ; https://oxfordstrat.com/trading-strategies/livermore-system-1/ (Kaufman 2020 Livermore codification, CAGR 17.2%, Sharpe 0.93, MDD 43.9%, 1980-2020, 42 futures, rated C)
- DeMark: https://demark.com/sequential-indicator/
- Davey: https://kjtradingsystems.com/15-algo-trading-price-patterns.html ; https://kjtradingsystems.com/algo-trading-exits.html ; https://kjtradingsystems.com/
- Unger: https://blog2.ungeracademy.com/?p=102 ; https://ungeracademy.com/blog/we-tested-larry-williams-oops-pattern-the-results-might-surprise-you ; https://ungeracademy.com/blog/testing-toby-crabel-s-opening-range-breakout-does-it-really-work-code-backtest-on-nasdaq
- Collins: https://bettersystemtrader.com/073-simple-concepts-to-build-robust-stratgies-art-collins/ ; https://futures.io/traders-hideout/48637-beating-financial-futures-market-art-collins.html
- Ehlers: https://www.mesasoftware.com/papers/MAMA.pdf ; https://www.mesasoftware.com/papers/PredictiveIndicators.pdf ; https://www.mesasoftware.com/papers/InferringTradingStrategies.pdf ; https://www.mesasoftware.com/papers/ROBUSTNESS.pdf
- Wilder: https://www.tradingview.com/support/solutions/43000502250-average-directional-index-adx/
- Bean / Capstone: https://capstonetradingsystems.com/pages/trading-systems and the product pages listed in s.24 ; https://algorithmictradingreviews.org/2018/05/24/capstone-trading-systems/ ; https://books.apple.com/us/book/seven-trading-systems-for-the-s-p-futures/id460008338
- Bandy / Penfold / Ruggiero: https://bettersystemtrader.com/061-foundations-of-trading-howard-bandy/ ; https://bettersystemtrader.com/101-trading-price-patterns-with-brent-penfold/ ; https://bettersystemtrader.com/042-murray-ruggiero/
- Hikkake (Chesler; related failed-inside-bar pattern): https://oxfordstrat.com/trading-strategies/modified-hikkake-pattern/ (1980-2019, 42 futures, $50 costs: CAGR 2.5%, Sharpe 0.34, MDD 18.5%, win 33.8%, PF 1.05, rated C) ; https://www.tradingsetupsreview.com/hikkake/
