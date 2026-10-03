# Cross-Asset, Relative-Value and Regime-Filter Strategies: Family Report

Prepared 2026-10-03 for the Lucid Trading 50K LucidFlex project. All times are **ET**. "RTH" = 09:30-16:00 ET for ES/NQ. Data assumed available: 1-minute OHLC (no volume) for S&P 500 (ES/MES proxy), Nasdaq 100 (NQ/MNQ proxy) and Gold (GC/MGC proxy), Nov 2010 to Sep 2026; daily futures and VIX family from Yahoo (`^VIX`, `^VIX9D`, `^VIX3M`, `^VIX6M`, `^VVIX`, `DX-Y.NYB`, `^TNX`, `ES=F`, `NQ=F`, `GC=F`). Crude is not available 2024-2026.

Method note: this sweep was run after the session's WebSearch budget was exhausted, so it relied on direct fetches of canonical sources (arXiv API, Crossref API, Quantpedia, GitHub code search of StockSharp/TradingView/independent repos, QuantConnect strategy library, practitioner blogs) plus a full read of the one 2026 working paper that tests regime-gated intraday signals on MNQ with walk-forward validation (Mesfin 2026, arXiv:2605.04004). Several practitioner sites (Quantified Strategies, Alvarez, Quantifiable Edges' VIX course, SSRN, Elite Trader/NexusFi) are bot-blocked; where a well-known rule set could not be re-fetched, the most standard objective interpretation is written down and marked as such.

## 0. Summary

Scope: ES-vs-NQ spread/ratio mean reversion and lead-lag; SMT (ICT) cross-index divergence; VIX level, VIX spike and VIX term-structure signals for ES; synthetic volatility from OHLC (Williams VIX Fix); DXY-vs-gold and gold-vs-equities (safe-haven) signals; risk-on/risk-off intraday composites; correlation-regime, turbulence and absorption-ratio kill switches; GMM/HMM volatility-regime gating; relative-strength instrument selection between ES/NQ/GC; cross-asset time-series momentum filters; volatility-targeted sizing.

Headline findings:

1. **The best-evidenced items in this family are *filters and sizing rules*, not stand-alone entry signals.** Volatility-managed sizing (Moreira & Muir 2017, JF; Fleming-Kirby-Ostdiek 2001/2003) is peer-reviewed, replicated, and maps directly onto Lucid's consistency rule and EOD-trailing drawdown: scale contracts by 1/realized-vol so every day has roughly the same dollar risk. VIX-level and VIX-term-structure regime gates have weaker but consistent support (Simon & Wiggins 2001 for VIX as a contrarian predictor of S&P futures; Johnson 2017 and Cheng 2019 for term-structure information; Seeck 2026 and the algotr quadrant test from the mean-reversion family for intraday gating).
2. **ES/NQ lead-lag at 1-minute resolution is not an exploitable edge.** Hasbrouck (2003, JF) shows price discovery for both indexes happens in the E-minis themselves; Huth & Abergel (2011/2014) get ~60% directional accuracy for the lagger from the leader at tick scale but show a market-order strategy cannot beat the spread; Curme et al. (2015) show validated intraday lead-lag links shrink as markets got more efficient. With *cash-index* 1-minute proxies the apparent lead-lag is dominated by stale-price artifacts and must be treated as spurious.
3. **ES/NQ beta-neutral spread mean reversion has thin but positive public evidence at the daily horizon (Sharpe ~1.7, 2021-2025, single GitHub study; cointegration ADF p=0.039) and none at the intraday horizon on these two contracts.** The QuantConnect intraday-pairs template (10-min bars, z=2.33 entry/0.5 exit/4.0 stop) reaches Sharpe 3.0 on bank stocks 2013-2016, not on index futures. The 2023-2026 AI/semiconductor leadership episodes broke the NQ/ES relationship repeatedly, so any live version needs a short re-estimation window and a hard z-stop.
4. **Gold's safe-haven property is real but short-lived and conditional.** Baur & Lucey (2010, FR) and Baur & McDermott (2010, JBF, 1979-2009) find gold is a safe haven for US equities only in the extreme (bottom 5%/1%) return days and the effect fades within ~15 days; Akhtaruzzaman et al. (2021) show it failed in the liquidity phase of March 2020. The gold-DXY inverse link is significant at all intraday scales in 2017-2019 (Madani 2019) but weakened badly in 2023-2026 as both rose together. Both are usable only as *day-type* filters, not as stand-alone intraday signals.
5. **Regime-gated, longer-hold intraday signals beat single-bar OHLC patterns in the only rigorous 2021-2025 MNQ study found.** Mesfin (2026) falsifies 14 OHLCV signal families on 5-minute MNQ (gross edge 0.07-1.50 pts vs a 2.0-pt friction floor) but his two GMM-regime-gated positive controls pass walk-forward OOS (RTH Confluence: T=3.11, +11.82 pts/trade net, N=196; London Signal B: T=4.30, +4.09 pts, 61.5% win, N=247). Caveats are serious (53+ parameter combinations searched, one contaminated fold, 1-bar delay flips London B to T=-2.78) but the architectural lesson is useful: gate by regime, hold 60-75 minutes, enter on pullback.
6. **Prop fit.** This family's strategies are mostly low-frequency overlays. The ones that generate their own trades (ES/NQ spread MR, SMT divergence, gold shock-day longs, synthetic-VIX dip buys, GMM-gated pullbacks) produce 0-2 trades a day with small, hedged or time-limited exposures, which is consistency-friendly. The dangerous ones for a $2,000 EOD-trailing drawdown are unhedged "trade the laggard" catch-up trades and any spread trade without a z-score stop (spreads trend for days when leadership changes).

Evidence quality scale: 1 = anecdote/vendor claim, 2 = single practitioner backtest or script, 3 = large-sample practitioner study or single working paper, 4 = peer-reviewed or multiple independent backtests, 5 = peer-reviewed with multiple independent out-of-sample confirmations.

**Data flags used below:** [VOL] needs volume; [VIX-INTRADAY] needs intraday VIX (we have daily only); [FUTURES] needs real futures prices (cash-index proxies distort it); [DAILY-ONLY] the signal itself is daily and is used as an intraday filter.

---

## 1. ES-NQ beta-neutral spread z-score mean reversion (intraday)

- **Origin:** Classic pairs/stat-arb (Gatev-Goetzmann-Rouwenhorst 2006 for stocks); futures-specific implementations: honoreaa/Futures-MeanReversion (GitHub, 2025, daily ES=F vs NQ=F), QuantConnect "Intraday Dynamic Pairs Trading" (Miao 2014 two-stage correlation/cointegration), StockSharp #0222 Cointegration Pairs and #0299 Beta-Adjusted Pairs.
- **Entry (objective rules):** 5-minute bars, RTH only. Hedge ratio beta = slope of rolling OLS of ln(NQ) on ln(ES) over the last 20 sessions (re-estimated nightly; honoreaa's daily-price beta was 0.2241 for ES on NQ, i.e. ~4.46 NQ-points per ES-point). Spread S_t = ln(NQ_t) - beta * ln(ES_t). z_t = (S_t - mean(S, 60 bars)) / std(S, 60 bars). Enter when |z| >= 2.0 (QuantConnect uses 2.33): z >= +2 -> short NQ / long ES notional-neutral; z <= -2 -> long NQ / short ES. Notional neutrality with micros: 1 MNQ ($2 x ~NQ) against round(NQ*2 / (ES*5)) MES, typically 2 MES per 1 MNQ (check daily).
- **Exit:** |z| <= 0.5 (target), or |z| >= 3.5-4.0 (relationship break; QuantConnect uses 4.0), or 18 bars (90 min) time stop, or 15:55 flat. No overnight.
- **Filters:** Trade only if the 20-session ADF test on S rejects a unit root at p <= 0.05 (QuantConnect: correlation >= 0.9 and ADF p <= 0.05); skip the first 15 minutes (09:30-09:45) and FOMC days (14:00-15:00 blackout); skip if the 20-day ES-NQ daily-return correlation < 0.70 (leadership-change regime; see #12).
- **Parameters:** beta lookback 20 sessions (10-40); z lookback 60 bars (40-120); entry 2.0 (1.8-2.5); exit 0.5 (0-0.75); stop 3.5 (3-4); time stop 18 bars.
- **Timeframe/session:** 5-min, 09:45-15:55.
- **Evidence:** honoreaa (daily data 2021-01 to 2025-07, 30-day z lookback): Sharpe 1.67, annualized return 86% on $100k with annualized volatility 49%, ADF p=0.039 on residuals; daily, unlevered-looking numbers, single notebook, no cost model disclosed. QuantConnect/Miao template: CAGR 26.9%, Sharpe 3.0, beta 0.23 on US bank stocks 2013-2016 with 10-minute bars (not ES/NQ). StockSharp #0222 claims "about 103% annual" (vendor, unverified). No published intraday ES/NQ pairs backtest with numbers was found. Evidence quality **2**.
- **Prop fit:** Hedged exposure keeps daily P&L small and symmetric, which is good for the 50% consistency rule and the $150/day payout counter, but doubles commissions/slippage (4 legs per round trip) and the Lucid micro cap (40 micros eval / 20 funded) is not binding. The killer is a leadership regime change (e.g. AI-driven NQ outperformance in 2023-2025, or the April 2025 tariff drawdown when NQ beta spiked): the spread trends for days; the 3.5-z stop and the correlation filter are mandatory. [FUTURES]: cash SPX/NDX proxies smear the spread by 1-3 minutes of stale prints; with 5-minute bars this is tolerable, with 1-minute bars it creates fake reversion.
- **Sources:** https://github.com/honoreaa/Futures-MeanReversion ; https://www.quantconnect.com/learning/articles/investment-strategy-library/intraday-dynamic-pairs-trading-using-correlation-and-cointegration-approach ; https://github.com/StockSharp/AlgoTrading/tree/master/API/0201-0300/0222_Cointegration_Pairs ; https://github.com/StockSharp/AlgoTrading/tree/master/API/0201-0300/0299_Beta_Adjusted_Pairs_Trading

## 2. NQ-ES 30-minute return-differential fade ("dispersion spike" variant)

- **Origin:** Practitioner variant of #1 that works on return windows rather than price levels (avoids cointegration assumptions). Standard objective interpretation written here.
- **Entry:** d_t = cumulative 30-minute log return of NQ minus beta_r x cumulative 30-minute log return of ES, where beta_r is the 20-session regression slope of 5-min NQ returns on ES returns (typically 1.2-1.4). sigma_d = std of d over the last 60 sessions' same window. Enter when |d_t| >= 2.5 sigma_d: short the outperformer / long the underperformer, notional-neutral.
- **Exit:** d returns to 0.5 sigma_d, or 60 minutes, or |d| >= 4 sigma_d, or 15:55.
- **Filters:** Skip 09:30-10:00 (opening dispersion is informative, not noise, see #11); skip scheduled-news windows (08:30 releases already in the open; 10:00 ISM/consumer sentiment; 14:00 FOMC).
- **Parameters:** window 30 min (15-60), entry 2.5 sigma (2-3), exit 0.5, stop 4.0, time stop 60 min.
- **Evidence:** No published backtest. Related evidence from Huth & Abergel (asymmetric lagged cross-correlations at second scale) and Curme et al. (2015) (validated lead-lag links decay with time) suggests any 30-minute dispersion is mostly information, not noise. Evidence quality **1**.
- **Prop fit:** Same as #1; fewer trades, cleaner stats. Treat as a research variant, not a base case.
- **Sources:** https://arxiv.org/abs/1111.7103 ; https://arxiv.org/abs/1401.0462

## 3. Lead-lag "trade the laggard" (NQ 1-minute move -> ES catch-up)

- **Origin:** Prop-firm and day-trading folklore ("NQ leads, ES follows"); academic lead-lag literature (Kawaller-Koch-Koch 1987; Chan 1992; Hasbrouck 2003; Huth & Abergel 2011/2014; Curme et al. 2015; Buccheri-Corsi-Peluso 2021).
- **Entry (standard objective interpretation):** 1-minute bars. r_NQ(1m) z-score vs its 60-bar std >= 2.0 while r_ES(1m) < 0.3 x beta_r x r_NQ(1m) (ES has not yet moved). Buy ES (or sell if the NQ move is down) at the next bar open.
- **Exit:** +0.5 x beta_r x |r_NQ| captured, or 3 minutes, or 1 x ATR(14, 1-min) adverse. Flat 15:55.
- **Filters:** None that rescue it; see evidence.
- **Parameters:** z 2.0 (1.5-3), lag horizon 1-3 bars.
- **Evidence (negative):** Hasbrouck (2003, JF 58(6)): "most of the price discovery for both indexes occurs in the E-mini markets"; the ES and NQ e-minis are each the leader for their own index, with little cross-index lag at minute scale. Huth & Abergel: 60% next-midquote accuracy for the lagger from the leader at tick scale, but "a naive strategy based on market orders cannot make any profit of this effect because of the bid/ask spread"; lead-lag has intraday seasonality (changes at the US open and macro releases). Curme et al. (2015, Quant Finance): validated intraday lead-lag links decline between 2002-03 and 2011-12 ("growth in efficiency"). Mesfin (2026): all single-bar MNQ OHLCV patterns have gross edge 0.07-1.50 pts against a 2.0-pt friction floor. Evidence quality **3 (negative)**.
- **Prop fit:** Poor. Many tiny trades, cost-dominated, unhedged. [FUTURES]: with cash-index proxies the apparent "NQ leads SPX" signal is a stale-price artifact (index components update at different speeds), so a backtest on our data will look better than reality. Do not deploy without true futures data.
- **Sources:** https://doi.org/10.1046/j.1540-6261.2003.00609.x ; https://arxiv.org/abs/1111.7103 ; https://arxiv.org/abs/1401.0462 ; https://arxiv.org/abs/2605.04004

## 4. SMT divergence (ICT "Smart Money Technique", ES vs NQ swing failure)

- **Origin:** ICT (Michael Huddleston) mentorship; the single most popular cross-index signal in the prop-firm community. Open-source codifications: r1ckylel "SMT Divergence" (Pine, GitHub), LuxAlgo SMT Divergence, dozens of ICT all-in-one scripts.
- **Entry (codified from the r1ckylel script):** Pivot highs/lows on both instruments with `ta.pivothigh(high, strength, strength)` where strength = 3 ("Sensitive"; 1/5/8 for other sensitivities). A **bearish SMT** forms when, after a synchronized pair of pivot highs (A on ES, B on NQ, within +-2 bars), one instrument trades above its pivot (`high > p.a`) while the other does not (`sweptA != sweptB`). Bullish mirror at pivot lows. Standard trade: short the instrument that *failed* to make the new high (relative weakness) when its next 5-min bar closes back below its own pivot level; long mirror.
- **Exit:** Stop 1 tick above the higher of the two swing highs (for shorts); target the prior swing low or 2R, whichever first; time stop 60 min; flat 15:55.
- **Filters:** ICT "kill zones": 09:30-11:00 and 13:30-15:30 only; require the divergence to occur against a prior-day high/low, overnight high/low, or the 09:30-10:00 opening range (liquidity level) for the "sweep" leg; skip FOMC days.
- **Parameters:** pivot strength 3 (2-5); sync tolerance 2 bars; bar size 5-min (1-15); R multiple 2 (1.5-3).
- **Evidence:** No published backtest with numbers. The logic is objective and codeable; GitHub hosts 66 Pine files referencing SMT divergence, none with reported statistics. Mechanically it is a cross-sectional failed-breakout fade, which the mean-reversion family found works for small excursions and fails for large ones. Evidence quality **1**.
- **Prop fit:** Decent structure for Lucid: 1-3 trades/day, defined 1R stop, 2R target, inside RTH, flat by 15:55. Risk: on trend days both indices keep making highs and the "weak" one catches up, producing 2-3 consecutive 1R losses; cap at 2 losses/day. [FUTURES] mild: 5-min pivots on cash proxies are fine; 1-min pivots are not.
- **Sources:** https://github.com/Rickylel/SMT-Divergence-By-r1ckylel ; https://github.com/louisgundelwein/tradingview-scripts (ict-all-in-one.pine) ; https://github.com/fxraptor-alpha/pinescript-indicators (fractal-model.pine)

## 5. Opening-range cross-confirmation (ES and NQ both break, or only one breaks)

- **Origin:** SMT-lite applied to the opening range; standard objective interpretation (no canonical source).
- **Entry:** OR = 09:30-09:45 high/low on both ES and NQ. **Confirmed breakout:** both close a 5-min bar above their OR highs within 5 minutes of each other (by 10:30) -> long the stronger (larger % OR extension). **Divergent breakout:** one closes above OR high while the other has not and instead closes back inside -> fade the lone breaker (short it) with stop at its high.
- **Exit:** Confirmed: trail 2 x ATR(14, 5-min) or 15:30 exit (Gao et al. intraday-momentum logic). Divergent: target OR midpoint, stop 1 tick above high, time 45 min.
- **Filters:** Skip if OR range < 0.3 x ATR(14 days) (dead open) or > 1.5 x (news open).
- **Parameters:** OR length 15 min (5-30); confirmation window 5 min; ATR trail 2.
- **Evidence:** None published. Mesfin (2026) finds ORB long at a 75-minute hold on MNQ nets +2.82 pts/trade but T=0.88 and year-unstable (2023-2025), ORB short negative; the cross-confirmation filter is untested. Evidence quality **1**.
- **Prop fit:** Same as ORB family; cross-confirmation reduces trade count, which may improve average quality but there is no evidence either way.
- **Sources:** https://arxiv.org/abs/2605.04004 (ORB tables); orb_session.md in this folder for the base ORB evidence.

## 6. VIX stretch / VIX RSI daily overlay (Connors) for long-biased ES days

- **Origin:** Larry Connors & Cesar Alvarez, "Short Term Trading Strategies That Work" (2008), chapters "VIX stretches" and "VIX RSI"; StockSharp #0967 "Larry Connors VIX Reversal II"; Simon & Wiggins (2001, J. Futures Markets 21(5)) for the academic version.
- **Entry (standard objective interpretation of the published rules):** (a) **VIX stretch:** SPX close > SMA(200) and VIX close > 1.05 x SMA(10, VIX) for 3 consecutive days -> long bias for the next session. (b) **VIX RSI:** SPX close > SMA(200), RSI(2, VIX) > 90, and VIX open > previous VIX close -> long bias. (c) StockSharp "Connors VIX Reversal II": RSI(25, VIX) crosses above 61 -> long; crosses below 42 -> short; hold 7-12 days, no stops. Intraday use: on signal days run only long-side intraday strategies (dip buys, ORB long, VWAP reversion long) at 1.5x base size; otherwise base size; never short ES on signal days.
- **Exit (daily overlay):** overlay off when RSI(2, SPX) > 65 or VIX closes below SMA(10). Intraday trades still exit by 15:55.
- **Filters:** Trend filter SPX > SMA(200) is part of the rule; in 2022 (SPX < 200-day) the stretch signals fired repeatedly during a bear and lost.
- **Parameters:** stretch 5% (3-8%) for 3 days (2-4); RSI(2) > 90 (85-95); exit RSI(2, SPX) > 65 (60-75).
- **Evidence:** Simon & Wiggins (2001): on 1989-1999 S&P 500 futures, VIX, put/call and TRIN are contrarian predictors over multi-day horizons and "out-of-sample trading simulations demonstrate enhanced profitability when purchasing futures during heightened fear periods" (peer-reviewed; daily). Connors & Alvarez (2008) report high win rates (roughly 70-80%) for the SPX rules 1995-2007 in the book; exact figures could not be re-fetched. StockSharp gives no statistics. No intraday translation has been published. Evidence quality **3** (daily effect); **2** as an intraday overlay.
- **Prop fit:** Good as a sizing/direction overlay; it concentrates risk on a few high-vol days, so cap the increased size so that a 1.5 x ATR adverse move still fits inside the EOD-trailing room. [DAILY-ONLY].
- **Sources:** https://doi.org/10.1002/fut.4 ; https://github.com/StockSharp/AlgoTrading/tree/master/API/0901-1000/0967_Larry_Conners_Vix_Reversal_II ; Connors & Alvarez, Short Term Trading Strategies That Work (2008)

## 7. VIX term-structure regime gate (VIX/VIX3M and VIX9D/VIX ratios)

- **Origin:** Simon & Campasano (2014, J. Derivatives) VIX futures basis; Johnson (2017, JFQA 52(6)) "Risk Premia and the VIX Term Structure"; Cheng (2019, RFS 32(1)) "The VIX Premium"; Quantpedia "Exploiting Term Structure of VIX Futures"; practitioner use of VIX/VIX3M (Quantifiable Edges VIX course; Rob Hanna's 2024 NAAIM Founders Award paper "Chicken & Egg: Should you use the VIX to time the SPX?", SSRN 4808230, not fetchable).
- **Rule (objective):** r1 = VIX / VIX3M, r2 = VIX9D / VIX, both from prior-day closes (Yahoo `^VIX`, `^VIX3M`, `^VIX9D`). Regimes: **Calm contango** r1 < 0.90 -> trend/continuation strategies on, mean reversion at half size, full size overall. **Normal** 0.90 <= r1 < 1.00 -> all strategies base size. **Backwardation** r1 >= 1.00 (or r2 >= 1.05) -> long-only mean-reversion and gold shock-day longs on; ORB/trend shorts off; size 0.5x; no new trades after 14:00 on FOMC days. **Re-steepening day** (r1 crosses back below 1.00 after >= 2 days above) -> strongest long-bias day: ORB long and dip buys at base size.
- **Parameters:** thresholds 0.90/1.00/1.05; alternative daily-roll measure: (VIX3M - VIX) x (1/63) > 0.10 per day = contango (Simon-Campasano's 0.10 daily-roll threshold on futures).
- **Evidence:** Johnson (2017): the slope of the VIX term structure "conveys information about the price of variance risk rather than expected changes in the VIX" and its predictability for variance-swap/VIX-futures/straddle returns is incremental to other VRP proxies (peer-reviewed; horizon weeks to months). Cheng (2019): the VIX premium (futures price minus a statistical VIX forecast) falls before periods of market stress and predicts VIX futures returns (RFS). Simon & Campasano/Quantpedia: shorting front VIX futures when daily roll > 0.10 (contango) and buying when < -0.10, 5-day hold, hedged with ES, earned ~19.7%/yr 2007-2011 but "slightly negative" out of sample. For *equity* timing the published evidence is thin; practitioner statistics (Hanna) exist but are paywalled. Evidence quality **3** for term-structure information content; **2** as an ES intraday gate.
- **Prop fit:** Cheap, daily, robust to execution. Its main value is turning strategies *off* on backwardation days (Aug 5 2024, Apr 3-9 2025, Mar 2023 SVB), which is exactly where EOD-trailing accounts blow up. [DAILY-ONLY].
- **Sources:** https://quantpedia.com/strategies/exploiting-term-structure-of-vix-futures/ ; https://doi.org/10.1017/s0022109017000825 ; https://doi.org/10.1093/rfs/hhy062 ; https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4808230 ; https://www.macroption.com/vix-term-structure/

## 8. VIX-level bucket strategy switch

- **Origin:** Seeck (2026, SSRN) NQ implied-vol band study and the algotr VIX-quadrant test (both catalogued in intraday_mean_reversion.md), plus Fleming-Ostdiek-Whaley (1995) on VIX as the market's fear gauge.
- **Rule:** Prior-day VIX close buckets: <15 "quiet": mean-reversion fades at full size, ORB at half (small ranges); 15-20: all base; 20-30: trend/ORB at full, fades at half, no short fades; >30: long-only mean reversion in ES/NQ (+ gold shock-day longs), half size, daily loss cap halved. Alternative algotr version: rolling 100-day VIX high/low split into quartiles, exclude the top quartile from mean-reversion.
- **Parameters:** bucket edges 15/20/30 (adjust with a 2-year rolling percentile: 25th/50th/90th).
- **Evidence:** Seeck (2026): NQ IV-band fade Sharpe +0.38 at VXN<20, negative at 20-30, +0.64 at >=30. algotr: excluding the top VIX quartile improved return/drawdown by ~34% for an RSI(3) dip buyer on ES/NQ/RTY. Both single practitioner studies. Evidence quality **2-3**.
- **Prop fit:** Simple, daily, and directly addresses the fat-tail days. [DAILY-ONLY].
- **Sources:** intraday_mean_reversion.md (#6, #11) ; https://doi.org/10.1002/fut.3990150303

## 9. Volatility-managed position sizing (ATR/realized-vol targeting)

- **Origin:** Moreira & Muir (2017, JF 72(4)) "Volatility-Managed Portfolios"; Fleming, Kirby & Ostdiek (2001 JF; 2003 JFE) "The Economic Value of Volatility Timing"; standard CTA vol-targeting.
- **Rule:** Daily risk budget B (e.g. $300 on a 50K Flex). Expected adverse move per contract M = k x ATR(20 sessions, daily) x point value, k = 0.5 for intraday strategies with time stops. Contracts = floor(B / M), capped by Lucid limits (40 micros eval / 20 micros funded) and by a hard cap so that 1.5 x ATR(20) x contracts x point value <= 0.6 x remaining EOD-trailing room. Recompute nightly. Variant (Moreira-Muir): weight proportional to c / RV^2 where RV is last-month realized variance, with the weight capped at 1.5x base.
- **Parameters:** B = 0.5-0.75% of balance; k 0.5 (0.4-0.7); ATR window 20 (10-30); cap 1.5x.
- **Evidence:** Moreira & Muir: scaling by inverse lagged realized variance "produces large alphas, increases Sharpe ratios, and produces large utility gains" across the market and factor portfolios 1926-2015 (Sharpe gains of roughly 25-50% for the market factor; vol-managed market alpha ~4.9%/yr). Fleming-Kirby-Ostdiek: volatility-timing portfolios using intraday-realized volatility beat static portfolios with economically large fees investors would pay. Evidence quality **5** (monthly); **4** for daily ATR sizing in futures (standard CTA practice with many replications).
- **Prop fit:** The single most important rule for Lucid: constant dollar-risk days make the 50% consistency test and the five $150 days easy and keep the EOD-trailing floor far away. It also prevents the classic failure of over-sizing in low-vol (June-July) then holding that size into August/April spikes.
- **Sources:** https://doi.org/10.1111/jofi.12513 ; https://doi.org/10.2139/ssrn.276921 ; https://doi.org/10.2139/ssrn.205676

## 10. Williams VIX Fix synthetic-volatility dip buy (OHLC-only "VIX")

- **Origin:** Larry Williams (2007) "The VIX Fix"; ChrisMoody "CM Williams Vix Fix" (TradingView, most-used implementation); StockSharp #0454 Williams VIX Fix strategy.
- **Formula:** WVF_t = (Highest(Close, 22) - Low_t) / Highest(Close, 22) x 100. Bands: BB(WVF, 20, 2.0); percentile range: rangeHigh = 0.85 x Highest(WVF, 50). (StockSharp defaults: BbLength 20, BbMultiplier 2.0, WvfPeriod 20, WvfLookback 50, HighestPercentile 0.85, LowestPercentile 0.99.)
- **Entry:** On 5-minute ES/NQ/GC bars: WVF >= upper BB or WVF >= rangeHigh ("volatility climax") AND close < lower BB(20,2) of price AND the current bar's WVF < previous bar's WVF (climax has turned) -> long at next open.
- **Exit:** Close >= SMA(20) of price, or inverted-WVF climax (StockSharp exit), or 12 bars, or 1 x ATR(14) below entry; flat 15:55.
- **Filters:** Only when prior-day VIX < 30 and ADX(14, 5-min) < 30; long only.
- **Parameters:** lookback 22 (15-30); BB 20/2.0; percentile 0.85 (0.8-0.9); hold 12 bars.
- **Evidence:** No statistics published by either implementation ("designed for daily charts, works great on intraday" is the only claim). Mechanically equivalent to buying a Bollinger-lower-band touch after a volatility climax, which the mean-reversion family found has positive but fat-tailed evidence on ES. Evidence quality **1-2**.
- **Prop fit:** Long-only dip buying with time stops is consistency-friendly; the trend-day tail is the drawdown risk. Attractive only because it gives an OHLC-only intraday "VIX" we can compute on all three instruments (we have no intraday VIX). Partially substitutes for [VIX-INTRADAY].
- **Sources:** https://github.com/StockSharp/AlgoTrading/tree/master/API/0401-0500/0454_Williams_Vix_Fix ; https://www.tradingview.com/script/og7JPrRA-CM-Williams-Vix-Fix-Finds-Market-Bottoms/ ; https://github.com/marketcalls/openalgo (examples/python/william vix fix.py)

## 11. Intraday risk-on/risk-off composite (ES, NQ, GC agreement -> continuation)

- **Origin:** Gao, Han, Li & Zhou (2018, JFE 129(2)) "Market Intraday Momentum"; Xu, Li, Singh & Li (2024, SSRN 4765613) "Cross-Market Intraday Time-Series Momentum"; Smales (2016, Finance Research Letters) "Risk-on/Risk-off: financial market response to investor fear".
- **Entry:** At 10:00, compute 09:30-10:00 returns: s = sign(r_ES) + sign(r_NQ) - sign(r_GC) (gold is the risk-off leg; add - sign(VIX gap) if daily VIX open is used). If s = +3 ("clean risk-on") -> long ES (or NQ) at 10:00; if s = -3 -> short. Second entry window: at 15:00 if sign(r_ES, 09:30-15:00) agrees with s -> hold/enter for the last hour (Gao et al.: first half-hour return predicts last half-hour return).
- **Exit:** 15:55 (or 15:30 for the morning entry), stop 1.5 x ATR(14 days)/sqrt(6.5) (roughly a 1-hour ATR), no add-ons.
- **Filters:** Only when |r_ES(09:30-10:00)| >= 0.25% (Gao et al. find the effect is stronger on volatile days, high-volume days and macro-announcement days); skip if the day is a backwardation day under #7 and s is negative (crash days overshoot and reverse late).
- **Parameters:** window 30 min (15-60); magnitude 0.25% (0.15-0.5%); gold weight 1 (0-1).
- **Evidence:** Gao et al.: SPY 1993-2013, first half-hour return predicts last half-hour return with t-stats > 3, stronger in volatile periods and recessions; replicated across 10 other ETFs (peer-reviewed). Zhang/Xu et al. extend to cross-market futures (SSRN; abstract unavailable). Smales (2016): VIX changes drive risk-on/off responses across equities, bonds, gold and FX. The 3-asset *composite* has no published test. Evidence quality **4** for the base intraday-momentum effect; **2** for the composite.
- **Prop fit:** One or two trades a day, long hold, moderate stop; the last-hour leg is historically the most robust piece and is flat by 15:55. Sizing per #9 is essential because it trades the volatile days by construction. Gold leg uses XAU 1-min (available 23h).
- **Sources:** https://doi.org/10.1016/j.jfineco.2018.05.009 ; https://doi.org/10.2139/ssrn.4765613 ; https://doi.org/10.1016/j.frl.2016.03.010

## 12. Rolling cross-asset correlation-regime filter (ES-NQ, ES-GC)

- **Origin:** Standard risk-management practice; related to Kritzman et al. absorption ratio (#13). Objective interpretation written here.
- **Rule:** Nightly: rho_EN = corr(20-day daily returns ES, NQ); rho_EG = corr(20-day ES, GC). Regimes: **Index-coherent** rho_EN >= 0.85 -> index-directional strategies on, ES/NQ spread (#1-2) off. **Dispersion** rho_EN < 0.70 -> spread strategies on, directional at half size. **Flight-to-safety** rho_EG <= -0.30 -> gold shock-day longs (#14) on, ES short fades off, half size. **Everything-rally** rho_EG >= +0.50 and both above 20-day MAs -> treat gold as a risk asset (no safe-haven trades).
- **Parameters:** window 20 days (10-40); thresholds 0.85/0.70/-0.30/+0.50.
- **Evidence:** Descriptive only; no published backtest of these exact thresholds. Supported indirectly by Kritzman et al. (2011) (absorption ratio spikes precede drawdowns) and ORCA (2026) (spectral correlation features improve crash detection by 10.3 pp). Evidence quality **2**.
- **Prop fit:** Cheap gate; most useful for switching #1/#2 off when NQ/ES decouples for days (which is when spread MR bleeds). [DAILY-ONLY].
- **Sources:** https://doi.org/10.3905/jpm.2011.37.4.112 ; https://arxiv.org/abs/2604.17251

## 13. Turbulence index / absorption-ratio kill switch (Kritzman)

- **Origin:** Kritzman & Li (2010, FAJ 66(5)) "Skulls, Financial Turbulence, and Risk Management"; Kritzman, Li, Page & Rigobon (2011, JPM 37(4)) "Principal Components as a Measure of Systemic Risk"; extended by ORCA (Kriuk 2026, arXiv:2604.17251) and the Triadic Stress Index (Acedo 2026, arXiv:2608.10788).
- **Rule:** Basket of daily returns y (SPX, NDX, GC, TNX change, DXY, VIX change; add ETFs from Yahoo for a 10-20 asset basket). Turbulence d_t = (y_t - mu)' Sigma^{-1} (y_t - mu) with mu, Sigma from a trailing 2-year window (Mahalanobis distance). Absorption ratio AR = share of total variance explained by the top n/5 eigenvectors over a 500-day window; shift = (AR_15d - AR_1y) / std(AR_1y). Kill switch: if d_t > 90th percentile of its trailing 2-year distribution, or AR shift > +1 sigma, then next session: no new directional trades, spreads and gold trades at half size, daily loss cap halved; resume after 2 consecutive non-turbulent days.
- **Parameters:** percentile 90 (85-95); AR window 500 days; shift threshold 1 sigma; basket size >= 6.
- **Evidence:** Kritzman & Li: turbulent days are persistent and have lower returns/higher risk across asset classes; Kritzman et al.: "significant stock drawdowns were preceded by absorption ratio spikes" and stock prices depreciated after such spikes (1998-2010 US, peer-reviewed). ORCA (2026): 24 ETFs, 15 years daily, 8-fold walk-forward with 10-day gaps; crash-detection AUC 0.741; a risk-on/off rotation using its probabilities returned CAGR 15.6%, Sharpe 1.13, max DD -7.5% vs buy-and-hold 3.7%/-33.7% (single working paper). Evidence quality **3-4** for the risk measure; **3** for the trading overlay.
- **Prop fit:** Pure protection. Its cost is missed trend days after turbulence (which are often the best days); for an EOD-trailing account that trade-off is favourable. [DAILY-ONLY].
- **Sources:** https://doi.org/10.2469/faj.v66.n5.3 ; https://doi.org/10.3905/jpm.2011.37.4.112 ; https://arxiv.org/abs/2604.17251 ; arXiv:2608.10788

## 14. Gold safe-haven shock-day long (equity-shock -> buy GC/MGC)

- **Origin:** Baur & Lucey (2010, Financial Review 45(2)); Baur & McDermott (2010, JBF 34(8)); Akhtaruzzaman, Boubaker, Lucey & Sensoy (2021, Economic Modelling); Smales (2016).
- **Entry (objective):** Trigger A (overnight): ES return 18:00-09:25 <= -1.0% and XAU return over the same window >= 0 -> buy MGC at 09:30. Trigger B (intraday): ES return 09:30-11:00 <= -1.0% (or prior-day VIX close > 25 and VIX gap up >= +10% at the open) and XAU is above its 09:30 price -> buy MGC at 11:00. Add-on: none.
- **Exit:** 15:50 flat; stop 0.6 x ATR(14 days, GC) below entry; take profit +1.0 x ATR; exit early if ES recovers to within 0.3% of prior close (shock fading).
- **Filters:** Do not trade if rho_EG (20-day) >= +0.5 (gold trading as a risk asset); do not trade in a liquidity cascade (VIX > 45 and gold down > 1% at trigger time: March 2020-type and 7-8 April 2025-type days when gold is sold for margin).
- **Parameters:** shock threshold -1.0% (-0.75 to -1.5%); hold to 15:50; stop 0.6 ATR.
- **Evidence:** Baur & Lucey: gold is "a hedge against stocks on average and a safe haven in extreme stock market conditions", and "the safe haven property is short-lived" (~15 trading days), 1995-2005 US/UK/Germany daily. Baur & McDermott: 1979-2009, safe haven for US and major European markets at the 5%/1% quantiles, "a stabilizing force ... in the face of extreme negative market shocks". Akhtaruzzaman et al.: safe-haven held in early COVID, failed in the later phase. Madani (2019): intraday gold-USD dependence negative and significant at all scales May 2017-Mar 2019. Mesfin (2026): MGC OU mean reversion on 5-min bars fails (T -1.6 to -5.3), so gold is not a good intraday reversion instrument on its own. Evidence quality **4** for the daily property; **2** for this intraday implementation.
- **Prop fit:** Fires on ~5-15 days a year; small size (ATR-based), long only, flat by close. Useful because those shock days are the days when ES/NQ strategies should be off; it gives the account something to do without directional index risk. MGC is $10/pt, so a 1-ATR move on a $4,000+ gold price can be large; size by #9.
- **Sources:** https://doi.org/10.1111/j.1540-6288.2010.00244.x ; https://doi.org/10.1016/j.jbankfin.2009.12.008 ; https://doi.org/10.1016/j.econmod.2021.105588 ; https://arxiv.org/abs/1912.12590 ; https://arxiv.org/abs/2605.04004

## 15. DXY-trend directional filter for intraday gold

- **Origin:** Murphy, "Intermarket Analysis" (2004) dollar-gold inverse; Madani (2019, arXiv:1912.12590); Choi (2026, arXiv:2609.03437).
- **Rule:** Nightly from `DX-Y.NYB`: DXY_trend = sign(close - SMA(20)) and sign(5-day change). If both negative -> gold intraday strategies (ORB, EMA pullback, WVF dip buy) long-only; if both positive -> short-only or stand aside; mixed -> base rules. Optional intensity: if |5-day DXY change| > 1.0% scale gold size 1.25x in the implied direction.
- **Parameters:** SMA 20 (10-50); 5-day change (3-10 days); intensity 1.0%.
- **Evidence:** Madani: negative, significant average and tail dependence between gold and USD rates at every intraday time scale (2017-2019). Choi (2026): in a VAR spillover network gold futures are the dominant *transmitter* of shocks to FX and DXY, i.e. gold leads the dollar more than the reverse, which argues against using DXY as a leading filter. 2023-2026 reality: gold rose from ~$1,800 to above $4,000 while DXY was range-bound/rising for long stretches (central-bank buying), so the inverse link was weak at daily horizons. Evidence quality **2-3** (relationship exists; filter value unproven, likely degraded).
- **Prop fit:** Harmless as a tie-breaker; do not let it override price-based signals. [DAILY-ONLY]; no intraday DXY in our data.
- **Sources:** https://arxiv.org/abs/1912.12590 ; https://arxiv.org/abs/2609.03437 ; Murphy, Intermarket Analysis (Wiley, 2004)

## 16. Relative-strength instrument selection (ES vs NQ vs GC) for directional day strategies

- **Origin:** Cross-sectional momentum (Jegadeesh & Titman 1993; Asness, Moskowitz & Pedersen 2013 "Value and Momentum Everywhere", including index futures); practitioner "trade the strongest index" rule and NQ/ES ratio charts.
- **Rule:** For any long day-strategy (ORB long, dip buy, continuation), run it in the instrument with the highest RS score; for shorts, the lowest. RS score = 0.5 x z(overnight return 18:00-09:25 vs 60-day std) + 0.5 x z(5-session return). Ratio-chart version: R = NDX/SPX daily close; if R > SMA(20, R) and R's 5-day change > 0 -> prefer NQ for longs, ES for shorts; if R below -> prefer ES for longs, NQ for shorts. Gold enters the ranking only for long strategies and only if rho_EG (20-day) > 0 (gold trading as a risk asset).
- **Parameters:** weights 0.5/0.5; windows 5 sessions (3-10) and 60 days for z.
- **Evidence:** Asness-Moskowitz-Pedersen: 12-1 month cross-sectional momentum works across equity index futures, peer-reviewed (monthly). No published test of intraday/overnight relative strength for choosing between ES and NQ; Mesfin (2026) shows unconditional MNQ long at the open is slightly negative (-2.60 pts/trade 2022-2024, T=-0.75), so selection must add real value to matter. Evidence quality **4** (monthly), **1-2** (as an intraday selector).
- **Prop fit:** Costless overlay; its practical value for Lucid is that MNQ ($2/pt) vs MES ($5/pt) have very different dollar ATRs, so the selector must feed #9 sizing.
- **Sources:** https://doi.org/10.1111/jofi.12021 (Asness, Moskowitz, Pedersen 2013) ; https://arxiv.org/abs/2605.04004

## 17. Cross-asset time-series momentum direction filter (daily TSMOM)

- **Origin:** Moskowitz, Ooi & Pedersen (2012, JFE 104(2)) "Time Series Momentum"; Hurst, Ooi & Pedersen (2017) century evidence; CTA practice.
- **Rule:** For each instrument nightly: TS = sign(close - close 21 sessions ago) + sign(close - close 63 ago) + sign(close - close 252 ago). Allow intraday breakout/continuation entries only in the direction of TS when |TS| >= 2; allow mean-reversion entries only against TS (i.e. buy dips in uptrends). Neutral (|TS| < 2): base rules.
- **Parameters:** lookbacks 21/63/252; majority rule.
- **Evidence:** MOP 2012: 58 futures 1985-2009, 12-month TSMOM positive in every asset class, Sharpe ~1 diversified (peer-reviewed, replicated many times; weaker 2009-2019, revived 2022). Daily-filter-for-intraday use untested. Evidence quality **5** (monthly TSMOM); **2** (as intraday gate).
- **Prop fit:** Keeps the bot from shorting NQ ORB breaks in a 2023-2025-style melt-up, and from buying every dip in 2022. [DAILY-ONLY].
- **Sources:** https://doi.org/10.1016/j.jfineco.2011.11.003 ; https://doi.org/10.1111/jofi.12021

## 18. Expansion-bar (volatility-burst) reversal, synthetic intraday VIX spike

- **Origin:** StockSharp #1528 "VIX Spike" (needs intraday VIX; replaced here by a realized-range spike) and #0037 "VIX Trigger"; empirical anchor Mesfin (2026) Section 4.2.
- **Entry:** 5-min bars. Range spike when bar range >= 2.0 x SMA(20) of bar range (Mesfin tested 1.5x/2.0x/2.5x). Fade: if the spike bar closed down -> buy next open; if up -> sell next open. Variant (StockSharp VIX Spike): long only when a volatility proxy > mean + 2 x std(15 bars), exit after 10 bars.
- **Exit:** 6 bars (30 min) time stop or 1 x spike-bar range adverse; flat 15:55.
- **Filters:** RTH only (Mesfin's test was Asia session 20:00-02:00, where fades were also below friction); skip 09:30-09:45 and the first bar after 10:00/14:00 releases.
- **Parameters:** multiple 2.0 (1.5-2.5); SMA 20; hold 6 bars.
- **Evidence (mostly negative):** Mesfin: *continuation* after an expansion bar is significantly wrong (1.5x threshold, bar+1: T = -11.52, N = 1,955; mean gross -0.27 pts) because "the directional move ... is entirely consumed within the breakout bar" (bar-open to next-bar-open +32.24 pts, bar-close to next-open -0.17 pts). But the reversal's gross content is only 0.2-1.5 pts, below the 2.0-pt MNQ friction floor, so fading it does not pay either. StockSharp "VIX Trigger" claims "about 148% annual" (vendor, forex, unverified). Evidence quality **3 (negative for continuation; fade is below cost)**.
- **Prop fit:** Do not trade as a stand-alone. Use the finding as a rule: never enter continuation at the close of an expansion bar; wait for a pullback (as in #19).
- **Sources:** https://arxiv.org/abs/2605.04004 ; https://github.com/StockSharp/AlgoTrading/tree/master/API/1501-1600/1528_VIX_Spike ; https://github.com/StockSharp/AlgoTrading/tree/master/API/0001-0100/0037_VIX_Trigger

## 19. GMM volatility-regime gated pullback entry (Mesfin "RTH Confluence" architecture)

- **Origin:** Mesfin (2026, arXiv:2605.04004 v3) positive controls; general HMM/GMM regime literature (Park 2023 arXiv:2307.00459 PCA+HMM beats buy-and-hold Sharpe; Blake 2025 arXiv:2510.03236 regime switching improves SPX vol forecasts).
- **Entry (as specified in Appendix A of the paper, adapted for no-volume data):** 5-min MNQ bars RTH. Features per bar: ATR ratio = ATR(20, computed on 1-min bars and merged at the 5-min close) / fixed baseline (10.34 pts in the paper), [volume z-score (50 bars) -> replace with range z-score, flag], close position within bar range, 5-min return. Fit a 3-component GMM on the training year (regimes: 0 low activity, 1 active flow, 2 extreme volatility). Signal when regime = 1 AND rolling 200-bar first-order Markov P(1 -> 2) > 0.15 AND volume z > 0.5 (range z > 0.5 substitute). Entry = limit order at signal-bar close minus 25 x ATR_ratio points (ATR_ratio capped [0.5, 2.0]), valid for 6 bars, else cancel. Long only in the paper.
- **Exit:** Bar 13 after the signal bar (65 min) or end of RTH; stop 80 x ATR_ratio points below entry.
- **Filters:** The regime gate is the filter. London variant: 15-min bars 03:00-08:30, 3-state GMM refit each fold, enter long at next bar open on a clean regime-0 -> regime-2 transition (no regime 1 in prior 2 bars), exit 60 min or 08:30, stop 20 pts.
- **Parameters:** GMM 3 components; Markov window 200; P threshold 0.15; pullback 25 x ATR_ratio; hold 13 bars; stop 80 x ATR_ratio. London: 15-min, hold 60 min, stop 20.
- **Evidence:** RTH Confluence: in-sample 2022-2024 N=538, +15.77 pts/trade net, T=5.83, 61% win; walk-forward OOS N=196, +11.82 pts net (after 2.0-pt MNQ friction), SD 53.8, T=3.11, 2025 OOS +13.14; permutation p<0.001; unconditional long benchmark -2.60 pts (T=-0.75). London Signal B: OOS N=247, +4.09 pts, SD 14.97, T=4.30, p=0.000025, win 61.5%, per-trade Sharpe 0.27, bootstrap P(mean > 2 pts) 98.9%, parameter-sensitivity T 3.87-4.83; **but** a 1-bar (15-min) entry delay flips T to -2.78. Author-disclosed problems: 53+ parameter combinations searched before locking, ATR baseline computed on the full in-sample period, GMM fit on 2022 contaminates the 2022-H2 fold, idealized stop fills, no roll adjustment. Independent, non-peer-reviewed, single author. Evidence quality **3**.
- **Prop fit:** 1-2 trades/day, 65-minute hold, +11.8 MNQ pts = $23.6 per micro; 10 MNQ = ~$236 expected per trade, which clears the $150 payout-day threshold on average but with SD ~$1,076 per 10-micro trade; the 80 x ATR_ratio stop (~$1,600 on 10 MNQ at ATR_ratio 1) is too wide for a $2,000 EOD-trailing account; tighten to 40 x ATR_ratio and size by #9. [VOL] for the volume gate (approximate with range z-score; expect degradation). [FUTURES] mild.
- **Sources:** https://arxiv.org/abs/2605.04004 ; https://arxiv.org/abs/2307.00459 ; https://arxiv.org/abs/2510.03236

## 20. VIX open-gap day-type classifier

- **Origin:** Connors "VIX RSI" rule component (VIX open > prior close); practitioner VIX-gap studies (Quantifiable Edges, paywalled). Standard objective interpretation.
- **Rule:** VIX_gap = VIX open (09:30, Yahoo daily open) / prior VIX close - 1. **Fear gap** VIX_gap >= +8%: mean-reversion long day (buy dips, VWAP reversion long, gap-down fade) if SPX > SMA(200); no shorts. **Complacency gap** VIX_gap <= -5%: trend-day long bias (ORB long, continuation) at base size. Else: base rules. Secondary: if VIX closes below its open on a fear-gap day (intraday reversal) hold longs to 15:55.
- **Parameters:** +8% (5-12%), -5% (-3 to -8%).
- **Evidence:** No fetched statistics; Connors' published rule uses VIX open > prior close as a confirmation for the RSI(2) > 90 buy; Simon & Wiggins support the contrarian direction at multi-day horizons. Evidence quality **2**.
- **Prop fit:** Day-type labelling is cheap and keeps the bot from shorting gap-downs on fear days (where V-reversals destroy EOD-trailing accounts). Note the VIX "open" from Yahoo is the 09:30 print; the VIX computes from 03:15 so "open" is not a clean gap. [DAILY-ONLY].
- **Sources:** https://doi.org/10.1002/fut.4 ; Connors & Alvarez (2008)

## 21. Overnight cross-asset divergence at the open (ES vs NQ gap disagreement)

- **Origin:** Practitioner; related to #4/#5 and to the gap-fade evidence in intraday_mean_reversion.md. Objective interpretation.
- **Rule:** Gaps g_ES, g_NQ (09:30 open vs prior 16:00 close). If sign(g_ES) != sign(g_NQ) or |g_NQ - beta x g_ES| > 0.4% -> "disagreement open": fade the larger-gap instrument toward its prior close for 60 minutes (stop 0.5 x gap beyond the open), and do not run ORB that day. If both gaps agree and |g| in 0.1-0.5% -> normal gap-fade/ORB rules apply.
- **Parameters:** divergence 0.4% (0.25-0.6%); hold 60 min.
- **Evidence:** None published. Gap-fill fade in Mesfin (2026) on MNQ was negative at every entry time (09:30/09:45/10:00: -1.92/-1.05/-1.43 pts net, T -0.26 to -0.44), and gap-continuation short (Kalman velocity z > 2.5 in the first 30 minutes) was the best near-miss (+14.52 pts net, T=1.46, N=35, year-unstable). Evidence quality **1**.
- **Prop fit:** Research item only.
- **Sources:** https://arxiv.org/abs/2605.04004

## 22. VIX futures basis / VIX premium (not tradeable with our instruments; regime use only)

- **Origin:** Simon & Campasano (2014), Cheng (2019), Quantpedia #; eigenquant53/VRP (GitHub thesis backtest); Li (2016, arXiv:1605.07945) regime-switching VIX futures trading.
- **Rule:** The original strategy sells (buys) front VIX futures when the daily roll (front minus VIX, divided by days to expiry) exceeds +0.10 (-0.10), hedged with ES by regression, 5-day hold. For us only the signal is usable: daily roll > +0.10 = "carry regime" (equity-friendly; allow trend longs), < -0.10 = "stress regime" (same actions as backwardation in #7). VIX futures data would have to come from Yahoo `^VIX` vs `VX=F` (sparse) or be approximated by VIX3M - VIX.
- **Evidence:** Quantpedia reproduction: ~19.7%/yr 2007-2011 in-sample; "slightly negative" OOS afterwards. Cheng: VIX premium predicts VIX futures returns and declines before stress. Evidence quality **3** for the vol-product strategy; **2** for the equity gate.
- **Prop fit:** Signal only. [DAILY-ONLY].
- **Sources:** https://quantpedia.com/strategies/exploiting-term-structure-of-vix-futures/ ; https://doi.org/10.1093/rfs/hhy062 ; https://github.com/eigenquant53/VRP ; https://arxiv.org/abs/1605.07945

---

## What the evidence says works in 2022-2026

1. **Sizing and gating beat signals.** The only quality-4/5 evidence in this family is for volatility-managed sizing (#9), for the information content of VIX and its term structure (#6, #7, #22), for intraday momentum on volatile days (#11) and for gold's safe-haven behaviour on extreme days (#14). Every one of these is an overlay. The practical 2025-2026 build is: base intraday strategies from the other families, sized by ATR (#9), switched off or halved on backwardation/turbulence days (#7, #13), with instrument choice by relative strength (#16) and direction by daily TSMOM (#17).

2. **Regime-gated, 60-75 minute holds are the only intraday architecture that survived a 2021-2025 walk-forward on MNQ.** Mesfin (2026) kills 14 single-bar OHLCV patterns (gross 0.07-1.50 pts vs 2.0-pt friction) and passes two GMM-gated signals (#19) with T = 3.11 and 4.30 OOS. Even discounting heavily for his disclosed parameter search, the direction of the result is clear: do not predict the next bar; classify the regime, wait for a pullback, hold about an hour, and get out by a fixed bar.

3. **ES/NQ lead-lag is dead at 1-minute resolution (#3) and SMT divergence (#4) has zero published evidence.** Hasbrouck, Huth-Abergel and Curme et al. all point the same way; what remains is sub-second and spread-bound. Any "NQ leads SPX" edge that shows up on cash-index 1-minute proxies is a stale-price artifact and must be discounted to zero unless replicated on real futures.

4. **ES/NQ spread mean reversion (#1) is plausible but regime-dependent.** 2021-2025 daily evidence is positive (Sharpe 1.67, single study, cointegrated at p=0.039). The 2023-2025 AI leadership episodes and the April 2025 drawdown (NQ beta spiking, then the fastest NQ recovery in years) are exactly the periods where a 20-session beta goes stale; short lookbacks, a 3.5-z stop and the correlation gate (#12) are the difference between a consistency-friendly hedged strategy and a slow bleed.

5. **Gold decoupled from the dollar in 2023-2026, but not from equity shocks.** The DXY filter (#15) should be a tie-breaker at most; the equity-shock gold long (#14) remains a sensible 5-15 day/year specialist trade with the explicit liquidity-cascade exclusion (gold was sold with equities on 7-8 April 2025 before making new highs).

6. **Expansion bars and gap patterns are cost-bound in MNQ (#18, #21).** The strongest statistic in the 2026 study is the *negative* T = -11.5 for expansion-bar continuation: the move is over by the bar close. For the backtest this means every breakout-style entry in this project should be a pullback-limit entry (as in #19) rather than a market entry at bar close.

7. **Lucid-specific implication.** With a $2,000 EOD-trailing floor checked intraday and a 50% consistency test, the dominant design goal is many small positive days. In this family that favours: #9 sizing on everything; #7/#8/#13 as off-switches; #1 (hedged, with stops) and #19 (regime-gated, 1-2 trades/day) as trade generators; #14 as the shock-day specialist; #4 only if the backtest shows a positive edge net of a conservative 2-tick-per-leg cost, which the literature does not promise.

## Source list (fetched or verified via Crossref/arXiv during this sweep)

- Hasbrouck, J. (2003). Intraday price formation in U.S. equity index markets. Journal of Finance 58(6). https://doi.org/10.1046/j.1540-6261.2003.00609.x
- Huth, N., Abergel, F. (2011/2014). High frequency lead/lag relationships - empirical facts. arXiv:1111.7103 / J. Empirical Finance. https://arxiv.org/abs/1111.7103
- Curme, C., Tumminello, M., Mantegna, R., Stanley, H.E., Kenett, D. (2015). Emergence of statistically validated financial intraday lead-lag relationships. arXiv:1401.0462 / Quantitative Finance. https://arxiv.org/abs/1401.0462
- Simon, D.P., Wiggins, R.A. (2001). S&P futures returns and contrary sentiment indicators. Journal of Futures Markets 21(5). https://doi.org/10.1002/fut.4
- Fleming, J., Ostdiek, B., Whaley, R. (1995). Predicting stock market volatility: a new measure. Journal of Futures Markets. https://doi.org/10.1002/fut.3990150303
- Fleming, J., Kirby, C., Ostdiek, B. (2001, 2003). The economic value of volatility timing (using realized volatility). https://doi.org/10.2139/ssrn.205676 ; https://doi.org/10.2139/ssrn.276921
- Moreira, A., Muir, T. (2017). Volatility-managed portfolios. Journal of Finance 72(4). https://doi.org/10.1111/jofi.12513
- Johnson, T.L. (2017). Risk premia and the VIX term structure. JFQA 52(6). https://doi.org/10.1017/s0022109017000825
- Cheng, I.-H. (2019). The VIX premium. Review of Financial Studies 32(1). https://doi.org/10.1093/rfs/hhy062
- Simon, D.P., Campasano, J. (2014). The VIX futures basis: evidence and trading strategies. Journal of Derivatives; Quantpedia reproduction https://quantpedia.com/strategies/exploiting-term-structure-of-vix-futures/
- Kritzman, M., Li, Y. (2010). Skulls, financial turbulence, and risk management. FAJ 66(5). https://doi.org/10.2469/faj.v66.n5.3
- Kritzman, M., Li, Y., Page, S., Rigobon, R. (2011). Principal components as a measure of systemic risk. JPM 37(4). https://doi.org/10.3905/jpm.2011.37.4.112
- Kriuk, B. (2026). ORCA - Online Regime Correlation Analyzer. arXiv:2604.17251. https://arxiv.org/abs/2604.17251
- Acedo, A. (2026). The Triadic Stress Index in Financial Markets. arXiv:2608.10788
- Baur, D.G., Lucey, B.M. (2010). Is gold a hedge or a safe haven? Financial Review 45(2). https://doi.org/10.1111/j.1540-6288.2010.00244.x
- Baur, D.G., McDermott, T.K.J. (2010). Is gold a safe haven? International evidence. JBF. https://doi.org/10.1016/j.jbankfin.2009.12.008
- Akhtaruzzaman, M., Boubaker, S., Lucey, B., Sensoy, A. (2021). Is gold a hedge or a safe-haven asset in the COVID-19 crisis? Economic Modelling 102. https://doi.org/10.1016/j.econmod.2021.105588
- Madani, M.A. (2019). Generalised DMCA coefficient: hedge vs safe haven capabilities of gold (intraday). arXiv:1912.12590
- Choi, S.H. (2026). Markovian shock-source tracing ... exchange rates, gold futures and bitcoin. arXiv:2609.03437
- Smales, L.A. (2016). Risk-on/risk-off: financial market response to investor fear. Finance Research Letters. https://doi.org/10.1016/j.frl.2016.03.010
- Gao, L., Han, Y., Li, S.Z., Zhou, G. (2018). Market intraday momentum. JFE 129(2). https://doi.org/10.1016/j.jfineco.2018.05.009
- Xu, D., Li, B., Singh, T., Li, J. (2024). Cross-market intraday time-series momentum. SSRN 4765613.
- Moskowitz, T., Ooi, Y.H., Pedersen, L.H. (2012). Time series momentum. JFE 104(2). ; Asness, Moskowitz, Pedersen (2013). Value and momentum everywhere. JF 68(3).
- Mesfin, M. (2026). Structural limits of OHLCV-based intraday momentum signals in MNQ futures: a systematic falsification study. arXiv:2605.04004v3. https://arxiv.org/abs/2605.04004
- Park, E.W. (2023). PCA and HMM for forecasting stock returns. arXiv:2307.00459 ; Blake, A.C. (2025). Regime-switching methods for S&P 500 volatility forecasting. arXiv:2510.03236
- Li, J. (2016). Trading VIX futures under mean reversion with regime switching. arXiv:1605.07945
- Hanna, R. (2024). Chicken & Egg: should you use the VIX to time the SPX? NAAIM Founders Award; SSRN 4808230 (not fetchable).
- honoreaa (2025). Futures-MeanReversion: pairs trading ES=F and NQ=F. https://github.com/honoreaa/Futures-MeanReversion
- QuantConnect. Intraday dynamic pairs trading using correlation and cointegration approach (Miao 2014). https://www.quantconnect.com/learning/articles/investment-strategy-library/intraday-dynamic-pairs-trading-using-correlation-and-cointegration-approach
- StockSharp AlgoTrading library: #0037 VIX Trigger, #0222 Cointegration Pairs, #0299 Beta-Adjusted Pairs, #0454 Williams VIX Fix, #0967 Connors VIX Reversal II, #1528 VIX Spike. https://github.com/StockSharp/AlgoTrading
- r1ckylel. SMT Divergence (Pine). https://github.com/Rickylel/SMT-Divergence-By-r1ckylel
- ChrisMoody. CM Williams Vix Fix. https://www.tradingview.com/script/og7JPrRA-CM-Williams-Vix-Fix-Finds-Market-Bottoms/
- Macroption. VIX term structure (VIX9D/VIX/VIX3M/VIX6M definitions). https://www.macroption.com/vix-term-structure/
- eigenquant53/VRP (VIX term-structure thesis backtest). https://github.com/eigenquant53/VRP
