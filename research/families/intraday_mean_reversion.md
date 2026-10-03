# Intraday Mean-Reversion Strategies: Family Report

Prepared 2026-10-03 for the Lucid Trading 50K LucidFlex project. All times are **ET** unless stated. "RTH" = 09:30-16:00 ET for ES/NQ. Data assumed available: 1-minute OHLC (no volume) for ES, NQ, GC, CL proxies, 2010-11 to 2026-09.

## 0. Summary

Scope covered: VWAP reversion/bands, Bollinger and Keltner reversion, RSI(2)/Connors-style intraday, opening-gap fades (with size/trend filters), full-gap and Larry Williams "Oops" fades, prior-day high/low and outside-day reversion, Turtle Soup and 80-20s, initial-balance (IB) extension and failed-break fades, opening-range whipsaw / fade-the-first-move, overnight-range fades, implied-vol (VXN/16) band fades, intraday z-score fades, lunch reversal, mean reversion into the close, high/low-of-day fades, weekly-open reversion, and overnight-return reversal (cross-sectional across our 4 instruments).

Headline findings:

1. **The best-evidenced intraday reversion edges on ES/NQ are *level* reversion, not *indicator* reversion.** Price returning to a reference level (prior close after a small gap, prior-day high/low after an outside open, weekly open, VWAP, IB edge after an over-extension) has large-sample statistics (2,500-3,100 sessions, 1-minute data, 2014-2026) with fill/touch rates of 60-93% depending on the distance filter. Indicator fades (RSI(2), Bollinger, Keltner, z-score) on 1-5 minute bars have weak or negative public evidence; they only work with strong regime filters.
2. **Distance filters dominate everything.** Across every study, the probability of reversion collapses as the excursion grows: same-day gap fill 78% at 0.1-0.25% vs 26% at 1-2% (S&P); NQ weekly-open touch 92.9% at <0.25% vs 45.5% at >1.5%; high/low-of-day fade 85% at <0.3 ATR vs 20% at >1.0 ATR. Fade small, do not fade large.
3. **Shorts are the weak side.** Multiple independent sources (StatOasis 2,400 z-score backtests, shareplanner gap study, tradingstats IB study) find fading strength (shorting up-moves) is a net loser in the 2014-2026 long-biased regime, while buying dips/filled gap-downs has positive expectancy. Default to long-only or long-biased fades on ES/NQ.
4. **Volatility regime matters in a non-monotone way.** Seeck (SSRN 2026) finds the NQ implied-vol band fade has positive Sharpe only at VXN<20 (0.38) and VXN>=30 (0.64), negative in between; the VIX-quadrant study finds mean reversion should exclude the top volatility quartile. The arXiv 2025 tick study finds genuine reversion only at 2-30 minute horizons; from ~1 hour out, trends persist.
5. **Prop fit.** The EOD-trailing $2,000 drawdown and 50% consistency rule favor strategies with many small positive days: small-gap fades, outside-day reversion, weekly-open fades and IB over-extension fades, run on MES/MNQ with time stops and flat-by-15:55. Indicator fades with 3-8 trades/day and 0.8R winners are consistency-friendly but have fat left tails on trend days; they require an ADX/trend-day kill switch.
6. **Data caveat.** True VWAP needs volume; with OHLC only, VWAP must be approximated by a session cumulative TWAP of typical price (or by weighting with hourly Yahoo volume), and VWAP-SD bands by the cumulative standard deviation of typical price. All VWAP strategies are flagged accordingly.

Evidence quality scale: 1 = anecdote/vendor claim, 2 = single practitioner backtest or TradingView script, 3 = large-sample practitioner study or single working paper, 4 = peer-reviewed or multiple independent backtests, 5 = peer-reviewed with multiple independent out-of-sample confirmations.

---

## 1. VWAP standard-deviation band reversion (±2σ)

- **Origin:** Practitioner standard (Brian Shannon, Market Profile/VWAP community); many public implementations (TradingView "VWAP SD2 Reversion", LuxAlgo VWAP bands, NexusFi VWAP SD bands).
- **Entry:** Session VWAP anchored at 09:30 (or 18:00 Globex open). Bands = VWAP ± k × cumulative std-dev of typical price. Long when a 5-min bar closes below VWAP − 2σ and the next bar closes back above the band (re-entry confirmation; the TradingView variant adds RSI(14) > 30 and MACD cross within a 5-bar window). Short mirror only if daily trend filter allows.
- **Exit:** Target = VWAP (optionally VWAP − 0.25σ to front-run). Stop = 1 × ATR(14) beyond the extreme of the signal bar, or a close beyond −3σ. Time stop 12 bars (60 min). Flat 15:55.
- **Filters:** Skip if first 15 minutes (bands immature), skip if ADX(14, 5-min) > 25, skip if |open gap| > 0.75% (trend-day risk). Optional: only trade in direction of prior-day close vs 20-day MA.
- **Parameters:** k=2.0 (range 1.5-3.0); ATR stop 1.0 (0.75-1.5); time stop 12 bars (6-24); min VWAP-to-band distance >= 0.15% of price so the target pays for costs.
- **Timeframe/session:** 5-min (or 1-min with 3-bar confirmation), 09:45-15:30.
- **Evidence:** LuxAlgo/NexusFi descriptive: ±2σ is where reversion "plays out most consistently"; on trend days price rides the band for hours. No public ES backtest with numbers; TradingView VWAP SD2 script disclosed no stats. Evidence quality **2**.
- **Prop fit:** Good day structure (flat daily, many small trades), but the trend-day tail is the drawdown killer; needs the ADX/gap kill switch and a daily loss cap around $300-400 on a 50K Flex. **Data flag: VWAP needs volume; approximate with cumulative TWAP of typical price.**
- **Sources:** https://www.luxalgo.com/library/concept/vwap-bands.md ; https://tr.tradingview.com/script/oSV81CXs-VWAP-SD2-Reversion-Long/ ; https://nexusfi.com/a/indicators/vwap-standard-deviation-bands

## 2. VWAP ± K×ATR reversion (StockSharp #0235)

- **Origin:** StockSharp strategy library (open C#/Python), 2024-25.
- **Entry:** Long when Close < VWAP − K×ATR(14); short when Close > VWAP + K×ATR(14). Default K=2.0, 5-min candles.
- **Exit:** Long exits when Close >= VWAP; short when Close <= VWAP. ATR-based protective stop (default 2×ATR).
- **Parameters:** K 1.5-3.0; ATR period 10-20; candle 3/5/15-min.
- **Evidence:** Vendor claim "average annual return ~58%", a sample showed PF 1.37, win rate 37-48%, drawdown <1% (unverified, unclear period). Evidence **1-2**.
- **Prop fit:** Same as #1; low win rate (37-48%) with target-at-VWAP means long waits; consistency fine, but not obviously profitable net of ES/NQ costs. Needs volume (flag).
- **Sources:** https://doc.stocksharp.com/en/api-examples/0235_VWAP_Mean_Reversion ; https://stocksharp.com/store/strategies.0235_vwap_mean_reversion/

## 3. Bollinger (20,2) band rejection fade with ADX filter

- **Origin:** Classic; codified rules from crosstrade.io "Bollinger Mean Reversion" (2025) and Unger Academy's futures BB mean-reverting work.
- **Entry:** 5-min bars, BB(20, 2.0 SD). Long: bar touches/closes below lower band AND closes above its own low with a lower wick >= 50% of bar range (or bullish engulfing). Short mirror at upper band. Enter next bar open.
- **Exit:** Target = middle band (SMA20). Stop = 1×ATR(14) beyond the rejection-bar extreme. Time stop 15 bars (5-min) / 10 bars (15-min). Flat 15:55.
- **Filters:** Skip if ADX(14) > 25. Skip if 20-bar structure shows higher highs and higher lows (for shorts) or lower lows (for longs).
- **Parameters:** BB length 20 (15-30), SD 2.0 (1.8-2.5), ADX cutoff 25 (20-30), ATR stop 1.0 (0.75-1.5), time stop 15 bars.
- **Evidence:** crosstrade states for ES in range regimes: win rate 58-65%, avg win/loss 0.8R/1R, PF 1.3-1.6, 3-8 trades/day, 0 on trend days; "the outlier big loss when a trend breaks out while fading can be significant". No audited backtest; Unger's BB futures article was unreachable. Evidence **2**.
- **Prop fit:** High trade frequency and small per-trade risk make the 50% consistency rule easy; fat-tailed loss days are the EOD-drawdown risk. Use MES/MNQ, cap daily loss at ~$350, stop trading after 2 consecutive losers in a trend day.
- **Sources:** https://crosstrade.io/learn/trading-strategies/bollinger-mean-reversion ; https://benzinga.com/z/34175944

## 4. Keltner channel reversion (EMA20 ± 2×ATR)

- **Origin:** Chester Keltner (1960) channel; reversion variant codified in StockSharp #0031 "Keltner Reversion" and #0073.
- **Entry:** 5-min. Long when Close < EMA(20) − 2.0×ATR(14) and flat; short when Close > EMA(20) + 2.0×ATR(14).
- **Exit:** Long closes when Close > EMA(20); short when Close < EMA(20). Stop 2×ATR from entry. Flat 15:55 (add).
- **Parameters:** EMA 20 (10-30), ATR 14 (10-20), multiplier 2.0 (1.5-3.0), stop 2.0×ATR (1.0-3.0).
- **Evidence:** Vendor claims ~106-130% annual (unverified, no period/instrument). No independent ES test found. Evidence **1**.
- **Prop fit:** Equivalent to Bollinger but ATR-width; same trend-day tail. Only use with ADX < 25 and long-only bias on ES/NQ.
- **Sources:** https://doc.stocksharp.com/en/api-examples/0031_Keltner_Reversion ; https://stocksharp.com/store/strategies.0073_keltner_channel_reversal/

## 5. Connors RSI(2) applied intraday

- **Origin:** Larry Connors & Cesar Alvarez, "Short Term Trading Strategies That Work" (2008), daily bars.
- **Entry (as coded, ProRealCode):** Close > MA(200) and Close < MA(5) and RSI(2) < 10 -> buy at market. Short: Close < MA(200), Close > MA(5), RSI(2) > 90.
- **Exit:** Long exit when Close > MA(5); short when Close < MA(5). Intraday version: flat 15:55; add 1.5×ATR stop.
- **Parameters:** RSI 2 (2-4), thresholds 10/90 (5-15 / 85-95), MA 200 bars, MA 5 bars.
- **Evidence:** Robust on daily bars for indices (Connors; many replications). Intraday: ProRealCode users report "catastrophic" on 1-min and poor on 15-min; "the system isn't designed for day trading". Evidence for intraday use: **2 (negative)**.
- **Prop fit:** Poor as-is intraday. A regime-gated cousin (strategy #6) shows how to rescue it.
- **Sources:** https://prorealcode.com/prorealtime-trading-strategies/rsi-2-strategy-larry-connors ; https://steemit.com/fmz/@fmz.com/larry-connors-rsi2-mean-reversion-strategy

## 6. RSI(3) dip-buy with VIX-quadrant regime gate (ES/NQ/RTY)

- **Origin:** algotr Substack (2025), EasyLanguage; tested on ES, NQ, RTY.
- **Entry:** Long when RSI(3) < 20 and Close > MA(190). Exit when RSI(3) > 80, or after 39 bars, or 1,100-tick stop (very wide; for ES that is ~275 points, effectively a disaster stop).
- **Regime gate:** VIX rolling 100-bar high/low split into four equal bands; mean reversion allowed in regimes 1-3, **excluded in regime 4 (top quartile)**.
- **Evidence:** Author reports ~34% improvement in Return/Drawdown with the gate, fewer trades, shallower drawdowns; absolute numbers not given; bar size appears daily/intraday-mixed. Evidence **2**.
- **Prop fit:** The regime gate (skip when VIX is in the top quartile of its 100-day range) is the transferable idea; the base system as written holds too long for day-trade-only. For our use: RSI(3,5-min) < 20 with Close > 190-bar MA, exit RSI>80 or 39 bars or 15:55, 1×ATR stop.
- **Sources:** https://algotr.substack.com/p/stop-leaving-money-on-the-table-a

## 7. Small opening-gap fade (fill-the-gap)

- **Origin:** Classic floor-trader play; statistics from thetrading.tools, VT Markets, shareplanner, tradethatswing, edgeful; academic antecedents Fung-Mok-Lam (JBF 2000) and Grant-Wolf-Yu (JBF 2005).
- **Gap definition:** RTH open (09:30) minus prior RTH close (16:00 settle or 16:00 1-min close), as % of price. (Using 16:15 or 17:00 closes changes the stats; be consistent.)
- **Entry:** At 09:31-09:35 (after the first 1-5 min bar), fade toward prior close if 0.10% <= |gap| <= 0.50% (ES) or <= 0.7×ATR(14-day). Prefer gap-down longs (gap-ups fade less reliably; gap-up Monday worst).
- **Exit:** Target = prior close (full fill) or 75% fill. Stop = 1.0 × gap distance beyond the open (or 0.5×ATR-day). Time exit 11:00 (median fill time ~45 min) or 12:00; flat at target or time.
- **Filters:** Skip if |gap| > 0.75-1% (fill 26-27% same day), skip if open is outside prior-day range by more than 0.5×ATR (becomes "gap-and-go"), skip FOMC/CPI days, skip if VIX top-quartile. Optional: trade only when gap is against the 20-day trend direction (gap-down in uptrend).
- **Parameters:** gap band 0.10-0.50% (0.05-0.70%), stop multiple 1.0 (0.5-1.5), fill fraction 1.0 (0.5-1.0), time exit 11:00 (10:30-12:00).
- **Evidence:** S&P same-day fill: 78% for 0.1-0.25% up-gaps (91% within 5 sessions), 60% for 0.25-0.5%, 46% for 0.5-1%, 26% for 1-2%, 27% for >2%. SPY/QQQ 1%+ gaps: ~50% fill intraday; avg open-to-close after 1%+ gap-up is −0.2% (SPY) / −0.5% (QQQ) but ~90% still close above prior close; after gap-down +0.21% (SPY). edgeful NQ: gap-ups fill ~60%, gap-downs ~56%, Mondays ~77%. Academic: S&P futures reversals after large opening changes (1982-1990s; 1987-2002) are significant but mostly eaten by a bid-ask cost proxy. A recent 24-month gap-fade t-stat for stocks has "decayed to noise" (Concretum). Evidence **3** (large samples, but mixed on net profitability).
- **Prop fit:** One trade/day, early, with an objective target and time stop: ideal for consistency and the EOD drawdown. Expected ~$40-120/day on 2-4 MES at 0.2-0.4% gaps; days without a qualifying gap are flat (fine). Key risk: trend-day gap-and-go; stop sizing must be strict.
- **Sources:** https://www.thetrading.tools/gap-analysis ; https://www.shareplanner.com/blog/strategies-for-trading/fading-the-gap-how-large-overnight-moves-in-spy-and-qqq-play-out-during-the-trading-day.html ; https://tradethatswing.com/high-probability-stock-market-statistics/ ; https://scholars.hkbu.edu.hk/en/publications/intraday-price-reversals-for-index-futures-in-the-us-and-hong-kon/ ; https://researchwith.montclair.edu/en/publications/intraday-price-reversals-in-the-us-stock-index-futures-market-a-1/ ; https://sentimentrader.com/blog/third-gap-of-1 ; https://concretumgroup.substack.com/p/identifying-stocks-to-fade

## 8. Full-gap (outside prior day range) fade - "SP500 Session Gap Fade"

- **Origin:** TradingView open-source strategy (2025), ES 5-min.
- **Entry:** Full gap down = today's first-bar high < yesterday's low -> long at bar close; full gap up = today's first-bar low > yesterday's high -> short. Session 09:30-16:30 (08:30-15:30 CT).
- **Exit:** Target = entry ± gap distance × 0.7-1.0; Stop = entry ∓ gap distance × 1.0; forced flat N minutes before session end. Optional candle-colour exit.
- **Parameters:** TP mult 0.7-1.0, SL mult 1.0 (0.75-1.5), flat time 15:45.
- **Evidence:** Script shows avg risk 0.4% over 200 trades, $2 RT commission, 1-tick slippage; no net stats disclosed. Evidence **2**.
- **Prop fit:** Rare setups (true full gaps are a minority of days), binary outcome; fine as an add-on filter inside #7 but not as a standalone eval strategy.
- **Sources:** https://www.tradingview.com/script/J1U1NNgx-SP500-Session-Gap-Fade-Strategy/

## 9. Larry Williams "Oops" gap reversal

- **Origin:** Larry Williams, "How I Made One Million Dollars..." / "Long-Term Secrets to Short-Term Trading" (1999); tested by Oxfordstrat (42 futures, 1980-2011) and Unger Academy (2024-25).
- **Entry:** Bull Oops: Open[today] < Low[yesterday] -> buy stop at Low[yesterday]. Bear Oops: Open > High[yesterday] -> sell stop at High[yesterday]. Intraday: order active 09:30-11:30 only.
- **Exit:** Original: exit on close of day n (1-40); ATR exit at Entry − ATR(20)×k; disaster stop 6×ATR. Day-trade version: stop = today's low (or 0.5×ATR), target = prior close or 1×ATR, flat 15:55.
- **Parameters:** Time_Index 1 (day-trade), ATR_Index 1-2, ATR length 20.
- **Evidence:** Oxfordstrat 32-year 42-market sensitivity study: profitable but "C" grade overall; folklore claim "93% of the time price reverses to close the gap" is unverified. Evidence **3** for existence, **2** for profitability.
- **Prop fit:** Same family as #7 but requires the open to be *outside* the prior range, then re-entry: this is precisely the "outside day" statistic (#10) with a stop-order trigger. Good objective rule; low frequency.
- **Sources:** https://oxfordstrat.com/trading-strategies/bull-oops-pattern/ ; https://ungeracademy.com/?p=7737 ; https://www.luxalgo.com/library/concept/classic-bar-setups.md

## 10. Outside-day / prior-day-range re-entry (open beyond PDH/PDL, fade back to the level)

- **Origin:** edgeful "outside days" and "previous day's range" reports; tradethatswing SPY stats; Taylor/Raschke prior-day-high/low fades.
- **Entry:** If 09:30 open > prior-day RTH high (PDH): short at 09:31-09:45 targeting PDH (price reverses to touch PDH 71-75% of sessions on NQ/SPY). If open < PDL: long targeting PDL (64-71%). Require |open − level| <= 0.2-0.3% (effect diminishes beyond ~0.2% per tradethatswing) and <= 0.5×ATR.
- **Exit:** Target = PDH/PDL touch (or prior close as extended target); stop = 1× the open-to-level distance (min 0.15%); time exit 12:00; flat 15:55.
- **Filters:** Long side preferred (NQ 75% for open-above fade vs 64% for open-below means the *short* fade has the higher touch rate here, but stop-loss tails are worse on shorts in 2023-2026; test both). Skip if gap > 1%.
- **Evidence:** edgeful NQ: 75% reverse to touch PDH after opening above it, 64% to PDL; "ES Friday opens below yesterday's low -> ~100%" (small sample); tradethatswing SPY 6-month: 71%/71%, "diminishes significantly for gaps exceeding 0.2%". Evidence **3** (large sample, but touch rate is not P&L).
- **Prop fit:** Single early trade, objective target: good. Caveat from edgeful/reddit: reversion velocity has slowed; touch may come hours later, so the time stop matters.
- **Sources:** https://docs.edgeful.com/trade-using-edgeful/price-action-reports/outside-days ; https://r.til.io/r/FuturesTrading/comments/1bxkwdr/es_reverses_back_into_yesterdays_range_100_of_the ; https://tradethatswing.com/high-probability-stock-market-statistics/

## 11. Prior-session low/high re-cross (Unger Academy "Strategy 1")

- **Origin:** Andrea Unger / Unger Academy, "Two Proven Mean-Reverting Strategies for Trading S&P 500 Futures" (2024).
- **Entry:** 15-min bars on ES. Long when a 15-min bar closes back **above** the previous session's low (after having been below it). Short when a 15-min bar closes back **below** the previous session's high. Unger adds undisclosed filters "especially on the short side".
- **Exit:** Stop $1,300 (26 ES pts), target $4,000 (80 ES pts) per 1 ES; exit at session end (Unger versions often hold to a time exit; day-trade: flat 15:55).
- **Evidence:** ~750 trades over ~6-7 years incl. OOS; avg trade ~$300; 2022 +$15k, 2023 +$18k on 1 ES. Evidence **2-3** (vendor backtest, reasonable sample).
- **Prop fit:** Avg $300/ES trade ≈ $30/MES; $1,300 stop on ES = $130 on MES; with 4 MES risk is $520/trade - too big for a $2k EOD trail unless stop is cut to ~$500 ES-equivalent. Win rate not disclosed; likely <45% (target 3× stop) which is bad for consistency. Use the re-cross trigger with a tighter stop (0.5×ATR) and target at prior close.
- **Sources:** https://blog2.ungeracademy.com/?p=102

## 12. Unger "Strategy 2": buy below session low minus an offset

- **Origin:** Same article.
- **Entry:** Limit buy at current session low − offset (offset optimized; standard interpretation 0.25-0.5×ATR(14-day) or a fixed point count), different parameters for short side.
- **Exit:** Stop $800, target $3,000 per ES; time exit at session end.
- **Evidence:** ~1,800 trades, avg ~$140/trade, 2020 +$40k, 2023 +$33k. Evidence **2**.
- **Prop fit:** Limit-order dip-buy with big target/stop ratio -> low win rate; fine for net profit, poor for the 50% consistency rule unless sized small. Translate to MES: $14/trade average.
- **Sources:** https://blog2.ungeracademy.com/?p=102

## 13. Turtle Soup / Turtle Soup Plus One (intraday adaptation)

- **Origin:** Connors & Raschke, "Street Smarts" (1995).
- **Original (daily):** Today makes a new 20-day low; prior 20-day low is >= 4 days old; place buy stop 5-10 ticks above the prior 20-day low; initial stop one tick below today's low; exit same day or next (Plus One: enter the next day if the failure happens then); trail.
- **Intraday adaptation (standard):** On 5-min RTH bars: price breaks the prior-day low (or 20-bar low with the prior low >= 4 bars old) by >= 2 ticks, then a bar closes back above that level -> buy stop 1 tick above the level. Stop 1 tick below the breakout extreme (max 0.5×ATR). Target 1×ATR(5-min, 20) or VWAP; trail to breakeven after 1R. Flat 15:55.
- **Evidence:** No quantified results in the book; LuxAlgo notes edges are "regime-dependent: better in rotational markets, poor in persistent trends". Overlaps with #10/#11 and with the IB failed-break statistics (#15). Evidence **2**.
- **Prop fit:** Stop-order entries confirm failure first (lower loss size); good risk control; frequency moderate. Shorts (failed upside breaks) are weaker in 2023-2026.
- **Sources:** https://www.luxalgo.com/library/concept/turtle-soup.md ; https://roboforex.com/blog/education/trading-strategies-that-were-a-revolution-three-strategies-of-linda-raschke/

## 14. 80-20s (Taylor technique fade of prior-day extremes)

- **Origin:** Connors & Raschke, "Street Smarts" (1995), citing George Taylor and Steve Moore.
- **Setup day:** Yesterday opened in the top 20% of its range and closed in the bottom 20% (bullish setup) or opened in the bottom 20% and closed in the top 20% (bearish setup); yesterday's range larger than the 10-day average range (MQL5 implementation).
- **Entry:** Bullish: today trades at least 5 ticks below yesterday's low; place buy stop at yesterday's low. Bearish mirror at yesterday's high. Active 09:30-13:00.
- **Exit:** Initial stop at today's extreme; trail; exit at close (Raschke: "this is a day-trade"). Day-trade version: target prior close or 1×ATR; flat 15:55.
- **Evidence:** Book statistics (Moore): close in top/bottom 10% -> 80-90% chance of follow-through next morning but only 50% close higher/lower; MQL5 FX test positive on EURUSD/USDJPY/USDCHF over 17 years (daily bars) but "needs serious upgrade". Evidence **2-3**.
- **Prop fit:** Rare setups (few per month); objective; small risk. Useful as a filter that upgrades #10 rather than a standalone.
- **Sources:** https://www.mql5.com/en/articles/2785 ; https://www.forex.academy/analysis-of-the-connors-rashckes-80-20-strategy/

## 15. Initial-balance failed-breakout fade

- **Origin:** Market Profile (Steidlmayer); statistics from tradingstats.net (ES/NQ 2015-2025, 1-min) and trevortrades.
- **IB:** 09:30-10:30 high/low. 
- **Entry:** After 10:30, if price breaks IB high/low and then a 5-min bar closes back **inside** the IB within 30 minutes of the break (or before 11:30), fade: short on failed upside break (target IB midpoint, then IB low), long on failed downside break. Downside failures are more common (ES 53.2% vs 45.2%) -> long bias.
- **Exit:** Target = IB midpoint (1st) / opposite IB edge (2nd, 29.8% of ES breakouts reach it); stop 1 tick beyond the breakout extreme (<= 0.25×ATR-day; median MAE of breakouts is only 0.20-0.26×ATR); time exit 13:00; flat 15:55.
- **Filters:** Skip "Extreme" IB (>1.5×ATR, 33% stay contained). Avoid trading the *first* break before it fails (65% of first breaks happen in C period 10:30-11:00). Wednesday has the highest double-break rate (36.8%).
- **Evidence:** ES: 34.0% of first breaks fail (close back inside), 46.8% of failed breaks turn into double breakouts, 55.7% of all breakouts retrace 50% into the IB, 29.8% reach the opposite edge; deep retrace (>=50%) -> only 24.8% close in break direction. NQ similar. 2,686 ES / 2,833 NQ days, stable across years. Evidence **3** (large sample, descriptive, not P&L).
- **Prop fit:** 0-1 trades/day mid-morning, defined stop (small), partial targets: good for consistency. Should be combined with #16 (opening-range whipsaw) since 37-43% of outside-close days are whipsaw days.
- **Sources:** https://tradingstats.net/initial-balance-breakout-statistics/ ; https://www.trevortrades.com/initial-balance ; https://www.linnsoft.com/comment/543 ; https://www.luxalgo.com/library/concept/initial-balance.md

## 16. IB over-extension fade (>=1.4-1.5× IB range retest)

- **Origin:** tradingstats.net "Initial Balance Retest: Continue or Reverse?" (NQ/ES, Feb 2014-May 2026, 1-min).
- **Entry:** After an IB break, when price extends to >= 1.4× (NQ) / 1.5× (ES) the IB range (measured from the IB midpoint or as "extension level" = IB high + 0.4-0.5×IB range), and the move was a slow grind (took > 45 min) and it is after 12:00, fade toward the IB edge on the first 5-min close back below the extension level. Also fade when a deep retest (>=50% retrace into IB) occurs.
- **Exit:** Target = broken IB edge (retest) then IB midpoint; stop = 0.25× IB range beyond the extension high; time exit 15:45.
- **Evidence:** At 1.1× extension, continuation 71-77% vs reversal 16%; at 1.5×, continuation 18-25% vs reversal 27% and runaway 55%. Afternoon (14:00-16:00) 1.2× retests continue only 23% (vs 58% morning). Fast moves continue 62% vs slow grinds 42%. Evidence **3**.
- **Prop fit:** Low frequency, afternoon, counter-trend into the close - the EOD drawdown risk is the "runaway" cohort (55% at 1.5×), which does not retest at all; so only fade *after* a retest/failure, never at the level. Marginal as a standalone; better as the exit logic for breakout longs.
- **Sources:** https://tradingstats.net/initial-balance-retest-statistics/

## 17. Opening-range whipsaw / fade-the-first-move

- **Origin:** SMB Capital "First Ticks - Wrong Ticks" (ES opening-drive study); tradingstats.net "Opening Range Close-Outside Statistics" (2014-2026); tradethatswing.
- **Entry (whipsaw fade):** OR = 09:30-10:00 (30-min). If the first break of the OR occurs by 10:30 and price then closes (5-min) back inside the OR, enter in the opposite direction targeting the opposite OR edge. Condition on an "in value" open (open inside prior-day value area / inside prior-day range), where whipsaw rate is highest (41.5% NQ, 47.0% ES).
- **Entry (opening-drive fade, scalp):** After a directional drive off the 09:30 open of >= 0.15% within the first 5-10 minutes, fade toward the opening print; SMB: price trades back through the open tick within 30 min 84.3% of the time, median 2 min.
- **Exit:** Target = opposite OR edge (whipsaw) / opening print (drive fade); stop = 1 tick beyond the failed-break extreme (or 0.25×OR width); time exit 11:30.
- **Evidence:** On whipsaw days the first break was the fake-out 73-78% of the time (NQ 78.4%, ES 73.4%); whipsaws are 37-43% of outside-close days. SMB fade after an opening drive: 57.9% winners, avg win 0.75 ES points (old data, pre-2015, thin edge). 5-min ORB: 71% of days break both sides (SPY). Evidence **3** for the structural stats, **2** for P&L.
- **Prop fit:** Early, small stop, quick resolution: consistency-friendly. Net edge after costs is thin unless the in-value filter is used. Watch out: the base rate is that 70-73% of days close *outside* the 30-min OR, i.e. the OR is a launchpad; fade only after the failure is confirmed.
- **Sources:** https://tradingstats.net/opening-range-close-probability/ ; https://www.smbtraining.com/blog/first-ticks-wrong-ticks ; https://tradethatswing.com/high-probability-stock-market-statistics/

## 18. Overnight (Globex) range fade

- **Origin:** Practitioner (futures.io/NexusFi threads, TradingView "AI MES Globex Overnight" and ORB-failure scripts, edgeful overnight-range reports).
- **Entry:** ON range = 18:00 (prior day) to 09:30 high/low. If the RTH open is inside the ON range: fade the first touch of the ON high (short) or ON low (long) between 09:35 and 11:30 when the touch bar closes back inside the range; alternatively fade a *failed* break (break then 5-min close back inside within 15 min).
- **Exit:** Target = ON midpoint (then opposite edge); stop = 0.25× ON range beyond the edge (max 0.3×ATR-day); time exit 12:00.
- **Filters:** Skip if ON range < 0.3×ATR-day (too tight, breaks easily) or > 1.2×ATR-day; skip 08:30 data days (CPI/NFP) per TradingView "news blackout 08:00-09:30".
- **Evidence:** No large-sample public statistics with P&L; scripts only. Opening-range studies show *breakout failure* fades work better than level fades. Evidence **1-2**.
- **Prop fit:** Similar structure to #15/#17 with a different reference range; keep as a variant to test, not a priority.
- **Sources:** https://my.tradingview.com/scripts/multitimeframe/page-4 ; https://futures.io/traders-hideout/446-10-tick-open-range-play-2.html ; https://www.edgeful.com/blog/posts/edgeful-reports-the-complete-guide

## 19. NQ implied-volatility band fade (±VXN/16 from prior close) - Seeck (2026)

- **Origin:** Leander Seeck, "Volatility as a Signal Switch: Regime-dependent Intraday Mean Reversion in Nasdaq-100 Futures", SSRN 7364204 (2026).
- **Entry:** Daily band = prior-session close × (1 ± VXN/16/100) [VXN/16 converts annualised vol to a 1-day 1-SD move, i.e. ÷√256]. When intraday NQ breaches the band (first 1-min close beyond it), enter toward the prior close (long on lower-band breach, short on upper).
- **Exit:** 30-minute time exit (paper's rule); alternative: exit at band re-entry or at prior close. Stop: not specified; standard interpretation 0.5× band width beyond the band.
- **Regime:** Reversion probability significant in all VXN buckets, but Sharpe positive only at VXN < 20 (0.38) and VXN >= 30 (0.64); slightly negative at 20-30. Trade only in the two extreme buckets.
- **Evidence:** 860 breach events 2018-2026; unconditional same-session reversion 85.2%; walk-forward IS 2018-2022 (n=298) Sharpe 0.47, OOS 2023-2026 (n=191) Sharpe 1.29. Single working paper. Evidence **3**.
- **Prop fit:** Very attractive: objective, 1-min executable, uses VIX/VXN daily data we have (use VIX for ES with VIX/16; VXN from Yahoo ^VXN for NQ), ~100 events/year, built-in time stop, and the OOS window overlaps our prime window. Band breaches often happen on big-range days, so size by band width (risk 0.25× band per trade on MNQ).
- **Sources:** https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7364204

## 20. Intraday z-score fade (rolling-mean deviation)

- **Origin:** Generic; quantified by StatOasis (2,400 variants, SPY 1993-2026, ES 2007-2026, daily) and arXiv 2501.16772 (tick data, 2010-2023, S&P and other futures).
- **Entry:** z = (Close − SMA(N)) / StdDev(N) on 1- or 5-min bars. Long when z < −2.0 (−1.5 to −3.0); short when z > +2.0 (shorts expected to lose on ES/NQ). Optional: require the bar to close back above the −2σ line.
- **Exit:** z > 0 (or −0.5/+0.5), time stop 5-10 bars, 1×ATR stop, flat 15:55.
- **Parameters:** N = 20-60 bars (1-min: 30; 5-min: 20); entry −2 (−1.5..−3); exit 0 (−0.5..+0.5).
- **Evidence:** arXiv 2025 (14 years tick data, S&P/Eurostoxx/FTSE/Nikkei/rates/FX/commodities): significant mean reversion at 2-16 min horizons (t = 13.6), reverting regime "up to ~30 minutes", persistence beyond ~1 hour; strong trends revert less. StatOasis (daily): long-only z-fades profitable in ~99-100% of variants (median R-expectancy 0.15-0.20, win rate ~70%) but no variant beat buy-and-hold; **970 of 971 short variants lost**. Evidence **3-4** for the existence of short-horizon reversion, **2** for a specific intraday rule.
- **Prop fit:** Short-horizon (minutes) reversion exists but is tiny per trade (basis points); after $1-2 commissions + 1 tick slippage on MES/MNQ the edge is marginal. Only viable with 1-min bars, high-vol days (VIX > 20 raises per-trade magnitude), long-only, time-of-day 09:35-11:30.
- **Sources:** https://statoasis.com/overfit/research/understanding-z-score-and-its-application-in-mean-reversion-strategies ; https://arxiv.org/html/2501.16772v1

## 21. Lunch reversal (11:00 short / 12:00 long / 14:00 exit)

- **Origin:** Quantpedia "Lunch Effect in the U.S. Stock Market Indices" (2024, SPY 2010-05 to 2024-05), citing Parness "The Art of Trend Trading"; related: R_Omega "buy the losers at 12:30" (PLoS One 2023, S&P 500/NASDAQ-100 stocks).
- **Entry:** Short SPY/ES at 11:00; at 12:00 cover and go long; exit long at 14:00. (Pattern: negative drift 11:00-12:00, positive drift 13:00-14:00.)
- **Exit:** Pure time exits; add a 0.5×ATR-day disaster stop.
- **Evidence:** Quantpedia shows equity curve but no numbers in text; effect is a drift of a few basis points per hour: positive but small, cost-sensitive. R_Omega: buy the 5 worst S&P 500 stocks (ranked on first six half-hours) at 12:30, sell at close -> +0.335%/day in 2020-21 vs +0.098% index (stocks, not index futures). Evidence **2-3**.
- **Prop fit:** Index-level drift is too small per day for a $3k target without heavy size; the lunch window (11:30-13:00) is better used as a *no-trade/kill* window for other strategies, and 13:00-14:00 as a long-bias filter.
- **Sources:** https://quantpedia.com/lunch-effect-in-the-u-s-stock-market-indices/ ; https://pmc.ncbi.nlm.nih.gov/articles/PMC10490999/

## 22. Mean reversion into the close (last-hour fade)

- **Origin:** End-of-day reversal literature (Quantpedia Awards 2025 runner-up, stock-level, retail-driven); Baltussen-Da-Lammers-Martens "Hedging demand and market intraday momentum" (JFE 2021).
- **Rule (standard):** At 15:00, if the day's open-to-15:00 return is beyond ±0.5×ATR-day (or ±1%), fade it; exit 15:55. Stock-level version: buy the day's worst decile at 15:30, sell at close.
- **Evidence:** For *index futures* the literature says the opposite: the first half-hour return positively predicts the last half-hour (intraday momentum, driven by gamma hedging), and tradingstats finds late-session extremes "represent genuine trend legs" with low fade rates. The end-of-day reversal is a *single-stock* retail effect, not an index effect. Evidence for the index-level fade: **2 (negative)**.
- **Prop fit:** Do not fade ES/NQ into the close; if anything, the last 30 minutes favour continuation of the day's direction. Flagged as not recommended.
- **Sources:** https://www.eur.nl/en/news/end-day-reversal-pattern-second-place-quantpedia-awards-2025 ; https://academicweb.nd.edu/~zda/intramom.pdf ; https://tradingstats.net/high-of-the-day-hold/

## 23. High/low-of-day extreme fade (ATR-depth gated)

- **Origin:** tradingstats.net "How often does the NQ high of the day hold? 7-year study" (NQ/ES/YM/RTY 2019-2026, 14,300 extremes per market).
- **Entry:** When price sets a new session extreme that is shallow (< 0.3× ATR-day from the RTH open) during the morning, and the next 5-min bar closes back from the extreme, fade it toward the open.
- **Exit:** Target = 50% retrace of the excursion (the study's definition of a "fade"); stop 0.10-1.0×ATR; time exit 2 hours.
- **Evidence:** 58-59% of extremes retrace 50%+; lows fade (61%) more than highs (55%); shallow (<0.3 ATR) ~85% fade vs deep (>1.0 ATR) ~20%. Critical: with fixed 50% targets, the stop-width sweep gives 37% win/1.6:1 (0.10 ATR stop) to 91% win/0.17:1 (1.0 ATR stop) and "expectancy approaches breakeven regardless of stop width". Author's discretionary A+/A calls: 70% hit rate, 75% profitable months, two 9-trade losing streaks. Evidence **3** (large sample; mechanical expectancy ~0).
- **Prop fit:** Mechanical version is breakeven before costs - not a standalone. The depth gate (only fade shallow excursions; never fade >1 ATR) is a reusable filter for #1-#4.
- **Sources:** https://tradingstats.net/high-of-the-day-hold/

## 24. Weekly-open reversion (Tuesday fade toward Monday's 09:30 open)

- **Origin:** tradingstats.net "Mean Reversion Trading Strategy: 565 weeks of NQ data" (NQ, 2015-01 to 2025-12, 1-min RTH).
- **Entry:** WO = Monday 09:30 RTH open. On Tuesday 09:30-10:00, if |Tuesday open − WO| < 0.25% (best), or < 0.50% (good), enter toward WO; prefer Tuesday open **below** WO (long). Bonus condition: WO already touched in the overnight (ETH) session (raises RTH touch rate to 82.7%; three-factor cell 100% of 42).
- **Exit:** Target = WO touch; stop = 1× the open-to-WO distance (min 0.15%); time exit 11:30 (73% of first touches occur by 11:30; median 43 min); flat 15:55 if still open, re-enter Wednesday only if < 0.25% away.
- **Evidence:** 69.7% of weeks revert to WO (394/565); 92.9% when Tuesday opens within 0.25% (n=127); 75.5% at 0.25-0.50%; below-WO + tiny = 98.2% (54/55). Not-touched weeks are "gap and go" 66.7% of the time. Annual rates 59.6% (2020-21) to 86.3% (2016). Evidence **3**.
- **Prop fit:** Excellent for consistency: one defined trade on Tuesday mornings, high touch rate at small distance, objective target. Expected ~15-25 trades/year on NQ alone (fewer with the tiny filter); extend to ES/GC/CL to raise frequency (untested there).
- **Sources:** https://tradingstats.net/mean-reversion-trading-strategy/

## 25. Overnight-return reversal, cross-sectional across ES/NQ/GC/CL (hold open-to-close)

- **Origin:** Akbas, Boehmer, Jiang & Koch (2022) "Overnight returns, daytime reversals, and firm-specific..." via Quantpedia "Overnight-Intraday Daily Reversal in Commodities / futures"; quantreturns.substack (2025) replication on ES/YM/NQ/EMD/NKD/RTY 2007-2025.
- **Entry:** At 09:30 compute each instrument's overnight return (prior 16:00 close -> 09:30 open), demean cross-sectionally (winsorize). Long the lowest (most negative) overnight return instrument(s), short the highest. Equal-weight, dollar-neutral.
- **Exit:** Flat at 15:55 (open-to-close hold). Disaster stop 1×ATR-day per leg.
- **Parameters:** Number of legs 1-2 per side; minimum overnight-return spread threshold (e.g., > 0.3%) to avoid noise trades.
- **Evidence:** Equity-futures basket daily return ~0.09%, Sharpe 3.2+ (gross, market-neutral), 2007-2025; sector-ETF versions Sharpe 4-7 (gross). Academic version "five times larger" than conventional reversal, robust across equity-index, rate, commodity and FX futures 1982-2014. Evidence **4** (academic + independent replication), but **our 4-instrument universe is far smaller than the papers', so expect much lower Sharpe**.
- **Prop fit:** Day-trade only, flat by close: perfect for the no-overnight rule. Cross-asset (ES vs GC vs CL) legs are not hedged, so EOD drawdown exposure is the sum of legs; use micros (MES/MNQ/MGC/MCL) and 1 contract per leg. Gold and crude overnight sessions dominate their daily range, so the "overnight return" there is a different animal - test separately.
- **Sources:** https://quantreturns.substack.com/p/overnight-mean-reversion ; https://quantpedia.com/strategies/short-term-reversal-with-futures ; https://www.cxoadvisory.com/technical-trading/overnightintraday-return-reversal-trading/

## 26. Vendor benchmark: "Phoenix" NQ M5 mean reversion (aeromir)

- **Origin:** aeromir.com commercial automated strategy (2025-26); proprietary rules, listed here only as a benchmark for what a 5-min NQ mean-reversion system reports and how it maps to prop pass rates.
- **Rules:** Undisclosed ("rule-based mean reversion", M5, zero overnight).
- **Evidence (vendor):** NQ Jan 2020-May 2026: 2,626 trades, 69.8% win, PF 1.30, max DD $17,611 (9.4%), ~1.7 trades/day, 75% profitable months, max losing streak 5. ES (untrained): $135k, 64.2% win. Simulated prop evals ($50k, $3k target, $2.5k trailing, MNQ, 5,000 sims): pass rate 32% at 1 MNQ, **70.4% at 2 MNQ (median 88 trades)**, 65.9% at 3, 59.3% at 4, 56.3% at 5. Evidence **1-2** (vendor, unaudited).
- **Prop fit lesson:** Even a PF-1.3, 70%-win M5 system passes only ~70% of $50k evals at the "right" size and 32% at 1 micro; sizing, not edge, drives pass rate; too much size (5 MNQ) lowers pass rate to 56%. Our Lucid sim should sweep contracts the same way.
- **Sources:** https://futures.aeromir.com/phoenix

---

## What the evidence says works in 2022-2026

1. **Level-reversion with distance filters survives.** The 2014-2026 1-minute studies (tradingstats: OR, IB, weekly open, extremes; edgeful: outside days, gap fills) show stable base rates across years (IB breakout 96.5-99.2% every year; weekly-open touch 59.6-86.3%). Small-gap fills and outside-day re-entries remain 60-93% events when the distance is small (< 0.25-0.5% / < 0.5×ATR).
2. **Regime dependence is explicit.** The MNQ regime paper (arXiv 2605.11423) finds reversal dominance in 2022-2023 and continuation dominance in 2024 ("no fixed directional rule survives all three years"). Seeck's NQ band fade is best at VXN >= 30 (2022, April 2025) and at VXN < 20 (2023-24 grind), negative in between. The practical rule: run reversion with a VIX/VXN gate and a trend-day kill switch (ADX>25 on 5-min, |gap|>0.75%, or OR broken with shallow retrace).
3. **Shorts lost.** StatOasis (ES 2007-2026): 970/971 short z-fade variants lost. shareplanner: 1%+ gap-ups still close above prior close ~90% of the time. tradingstats: upside IB breaks fail less (45%) than downside (53%). In 2023-2026 the long-only or long-biased versions of every fade are the ones with positive expectancy.
4. **Indicator fades on 1-5 min bars are marginal after costs.** Short-horizon reversion is real (arXiv: 2-30 minute horizon, t=13.6) but tiny per trade; RSI(2) intraday is reported as a loser; Bollinger/Keltner fades only produce PF 1.3-1.6 in explicitly range-bound sessions and give it back on trend days.
5. **Into-the-close fades do not work on index futures** (intraday momentum from hedging demand; late extremes are trend legs). Reserve the last hour for continuation or no trading.
6. **Most promising for the Lucid 50K Flex backtest (ranked):** (a) #19 NQ/ES implied-vol band fade with VXN/VIX gate, (b) #7 small-gap fade (gap-down longs first), (c) #24 weekly-open Tuesday fade, (d) #10 outside-day re-entry, (e) #15 IB failed-break fade (long bias), (f) #25 cross-sectional overnight reversal, (g) #3 Bollinger fade with ADX<25 and long bias as a high-frequency consistency filler. All are codeable from 1-minute OHLC plus daily VIX/VXN; only #1/#2 need volume (approximate with TWAP).

## Sources consulted (all)

- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7364204
- https://statoasis.com/overfit/research/understanding-z-score-and-its-application-in-mean-reversion-strategies
- https://arxiv.org/html/2501.16772v1
- https://arxiv.org/pdf/2605.11423
- https://tradingstats.net/opening-range-close-probability/
- https://tradingstats.net/initial-balance-breakout-statistics/
- https://tradingstats.net/initial-balance-retest-statistics/
- https://tradingstats.net/high-of-the-day-hold/
- https://tradingstats.net/mean-reversion-trading-strategy/
- https://tradethatswing.com/high-probability-stock-market-statistics/
- https://www.shareplanner.com/blog/strategies-for-trading/fading-the-gap-how-large-overnight-moves-in-spy-and-qqq-play-out-during-the-trading-day.html
- https://www.thetrading.tools/gap-analysis
- https://docs.edgeful.com/trade-using-edgeful/price-action-reports/outside-days
- https://r.til.io/r/FuturesTrading/comments/1bxkwdr/es_reverses_back_into_yesterdays_range_100_of_the
- https://quantpedia.com/lunch-effect-in-the-u-s-stock-market-indices/
- https://pmc.ncbi.nlm.nih.gov/articles/PMC10490999/
- https://crosstrade.io/learn/trading-strategies/bollinger-mean-reversion
- https://doc.stocksharp.com/en/api-examples/0235_VWAP_Mean_Reversion
- https://doc.stocksharp.com/en/api-examples/0031_Keltner_Reversion
- https://prorealcode.com/prorealtime-trading-strategies/rsi-2-strategy-larry-connors
- https://algotr.substack.com/p/stop-leaving-money-on-the-table-a
- https://www.luxalgo.com/library/concept/turtle-soup.md
- https://www.mql5.com/en/articles/2785
- https://blog2.ungeracademy.com/?p=102
- https://oxfordstrat.com/trading-strategies/bull-oops-pattern/
- https://www.tradingview.com/script/J1U1NNgx-SP500-Session-Gap-Fade-Strategy/
- https://tr.tradingview.com/script/oSV81CXs-VWAP-SD2-Reversion-Long/
- https://quantreturns.substack.com/p/overnight-mean-reversion
- https://quantpedia.com/strategies/short-term-reversal-with-futures
- https://futures.aeromir.com/phoenix
- https://scholars.hkbu.edu.hk/en/publications/intraday-price-reversals-for-index-futures-in-the-us-and-hong-kon/
- https://researchwith.montclair.edu/en/publications/intraday-price-reversals-in-the-us-stock-index-futures-market-a-1/
- https://www.smbtraining.com/blog/first-ticks-wrong-ticks
- https://www.trevortrades.com/initial-balance
- https://www.linnsoft.com/comment/543
- https://sentimentrader.com/blog/gap-and-crap
- https://sentimentrader.com/blog/third-gap-of-1
- https://www.eur.nl/en/news/end-day-reversal-pattern-second-place-quantpedia-awards-2025
- https://academicweb.nd.edu/~zda/intramom.pdf
- https://www.luxalgo.com/library/concept/vwap-bands.md
