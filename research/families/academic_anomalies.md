# Family: Academic / Quantpedia-style anomalies for equity-index and gold futures

Prepared 2026-10-03 for the Lucid Trading 50K LucidFlex project (ES/MES, NQ/MNQ, GC/MGC; 1-minute OHLC, no volume; prime backtest window 2025-01 to 2026-09).
All times are US Eastern (ET). "RTH" = 09:30-16:00 ET cash session. Lucid-relevant constants: ES $50/pt (MES $5/pt), NQ $20/pt (MNQ $2/pt), GC $100/pt (MGC $10/pt); eval target $3,000, EOD-trailing max drawdown $2,000, 50% consistency rule in eval (largest day <= 50% of total profit at pass), flat before session close every day.

Research method note: the session's web-search budget was exhausted before this sweep started, so the sweep was executed by fetching primary sources directly (NY Fed / Fed staff reports, journal PDFs on author sites, Concretum/Zarattini paper PDFs, arXiv, Quantpedia, QuantConnect, Quantocracy-indexed practitioner replications) and extracting rules and numbers from the full texts (pdftotext). Where a source is vague, the most standard objective interpretation is stated and labeled "interpretation".

---

## 0. Executive summary

| # | Strategy | Core evidence | Post-2015 OOS? | Prop-fit for Lucid 50K Flex |
|---|----------|---------------|----------------|-----------------------------|
| 1 | Market intraday momentum (first 30 min -> last 30 min), Gao-Han-Li-Zhou | JFE 2018, SPY 1993-2013, Sharpe ~1 in-sample | Yes, and it is DEAD for SPY/QQQ/DIA: net -2.3 bp/day, t=-5.2 (2014-2026); QuantConnect 2015-2020 Sharpe -0.63 | Poor as published; only the "last-half-hour" window idea survives via #3 |
| 2 | Noise-Area intraday momentum ("Beat the Market", Zarattini-Aziz-Barbon) | SPY 2007-2024: 19.6%/yr, Sharpe 1.33, MDD 25%, hit 43% | Independent ES/NQ replication 2010-2025 (Quantitativo): ES Sharpe 1.25, NQ 1.67 (90-day lookback), flat 2010-2017, works 2018-2025 | BEST candidate in this family: day-trade only, OHLC-only, vol-targeted |
| 3 | Last-half-hour "hedging-demand" momentum (Baltussen-Da-Lammers-Martens) | JFE 2021, ~60 futures incl. ES, driven by option gamma hedging | Mixed; ETF version decayed, futures version not independently re-tested post-2020 | Medium; only on large-|move| days, 15:30-16:00 |
| 4 | ATR-band intraday breakout (Concretum "QuanTips #2" baseline) | SPY 5-min 2007-2026: CAGR >13%, Sharpe 0.87 net | In-sample includes 2022-2026 | Good; simplest codeable trend rule |
| 5 | 5-minute Opening Range Breakout (Zarattini-Aziz) | QQQ/TQQQ 2016-2023 Sharpe 1.12-1.19, win 24%; TQQQ 2016-2025 replication CAGR 41.9%, Sharpe 1.07 | Yes on TQQQ (2024 +33%, 2025 +22%). FAILS on MNQ 2022-2025 under strict walk-forward (Mesfin 2026): longs T=0.88, shorts negative | Medium; long-only, tight ATR stop, EOD exit; low win rate conflicts with consistency rule |
| 6 | Pre-FOMC announcement drift (Lucca-Moench) | NY Fed SR 512: 1994-2011, +49 bp per meeting, Sharpe 1.14; 98/131 positive | 2011-2018: ~40 bp only on press-conference meetings; SPY 1993-2024: Sharpe 0.5-0.6, flat 2016-2019, strong 2020-2024 | Good as an 8x/yr overlay; must be converted to a same-session trade (09:30 -> 13:55 ET on FOMC day) |
| 7 | Overnight drift 02:00-03:00 ET in ES (Boyarchenko-Larsen-Whelan) | NY Fed SR 917: ES 1998-2020, +1.48 bp/day (3.7%/yr), Sharpe 1.1 pre-cost, -0.5 post-cost; conditional "buy-the-dip" 01:30-03:30 Sharpe 1.8 pre / 1.1 post | Positive 20 of 23 years; 2020 best year (+10.7%) | Medium; tiny edge per day, needs MES x many and conditioning on prior-day sell-off; within-session so allowed if Lucid "overnight" = through 17:00 close (verify) |
| 8 | Overnight (close-to-open) premium, hold 16:00->09:30 | SPY 2000-2026 overnight 7.2%/yr Sharpe 0.67 (Quanter Lab); Robot Wealth confirms through 2024 | Yes, but net of costs the isolated overnight-only rule loses; NightShares ETFs closed 2023 | Poor/forbidden-ish: requires holding through the cash close; only viable as a 18:00->09:30 Globex hold if allowed |
| 9 | Turnaround Tuesday (conditional on Monday down) | SPY 1993-2026: Tuesday +0.10% after Monday down, +0.33% after Fri+Mon down; VTI 2007-2025 ensemble +0.469%/trade t=3.29 | Yes, stable across eras | Good small overlay: long ES Tuesday 09:30-15:59 after a down Monday (day-trade version untested; overnight version is the documented one) |
| 10 | Gold Friday effect | GLD Thu close -> Fri close, Sharpe 0.93 (2007-2025) | Yes (sample ends 2025) | Medium; day-trade variant (GC Friday RTH) untested |
| 11 | Payday anomaly (16th of month) | Ma-Pratt; S&P 1980-2010, Sharpe 0.6 | No post-2015 test found | Weak overlay |
| 12 | VIX term-structure regime filter (VIX vs VIX3M) | Simon-Campasano 2014; Concretum "Volatility Edge" 2008-2025: dual signal Sharpe 0.87-1.0 vs 0.48 passive short-vol | Yes | Good as a regime switch for other rules (daily VIX/VIX3M from Yahoo) |
| 13 | VIX-level / realized-vol scaling of intraday trend exposure | Beat the Market: Sharpe rises with VIX (>=3.5 when VIX>40) | In-sample 2007-2024 | Good: use vol-targeting, not VIX gating |
| 14 | ES short-term mean reversion in high-vol regime (RSI(2)/VIX gate) | S&P constituents 2006-2025: VIX>=20 gate 5.1% CAGR Sharpe 0.47 vs 0.30 (Quanter Lab); Connors RSI2 lineage | Yes but on stocks, multi-day | Weak for day-trading; only as a "long bias after down days when VIX>20" filter |
| 15 | Intraday return seasonality (hour-of-day, day-of-week) | SR 917: 09:00-10:00 ET avg -1.2 bp (t=2.6, only in recessions, Thu/Fri); 17:00-18:00 -0.43 bp; Beat the Market: Wed best (18 bp, t=3.4) | Partly (1998-2020; 2007-2024) | Use as timing filters: avoid 09:30-10:00 longs, prefer 10:00+ entries |
| 16 | Overnight-gap predictability (fade vs continuation) | MNQ 2022-2025 walk-forward: gap-fill fade FAILS (net -1.9 pts, T=-0.44); gap-continuation short near-miss (+14.5 pts net, T=1.46, 35 trades) | Yes (negative) | Poor as stand-alone; gap handling belongs inside #2's band formula |
| 17 | End-of-day momentum on large-move days (leveraged-ETF rebalancing flow) | QuantRocket: 14:00->close when |day move|>6%: CAGR 31%, Sharpe 1.95 (2008-2016); decays from 2017 | Decayed | Weak-medium; sub-case of #3 |
| 18 | Nasdaq-S&P lead-lag | Only daily relative-strength regime evidence (Quantifiable Edges); intraday futures lead-lag arbitraged to minutes | None credible | Poor; at most a relative-strength regime filter |
| 19 | Gold-equity cross-asset signals (gold-oil ratio, gold/platinum, safe-haven day effect) | Fang-Su-Yin (SSRN 3950940): 1 sd of gold/oil ratio -> +6.6% next-year excess return; Baur-Lucey safe haven on extreme down days | Monthly only | Poor for intraday; a 1-day "long MGC when ES down >1% by 10:00" variant is an untested interpretation |
| 20 | Time-series momentum + carry (daily directional bias) | MOP 2012 (TSMOM 12m, Sharpe >1 diversified); KMPV 2018 (diversified carry Sharpe 1.49) | Yes (extensively) | Use as daily sign filter for ES/NQ/GC intraday longs/shorts; commodity carry needs curve data (flag) |
| 21 | Fast-alpha 5-minute reversal execution overlay (Concretum) | SPY 5-min 2007-2026: 1-bar reversal ~ -1 bp next bar; unprofitable standalone after costs; as entry/exit overlay on #4 it raises Sharpe above 0.87 | In-sample through 2026 | Good as execution logic (wait for one opposite 5-min bar before entering/stopping) |
| 22 | VWAP trend day-trading (Concretum) and morning order-flow reversal (Quantpedia 2026) | QQQ 2018-2023 671%, MDD 9.4%; OFI 2-day decline signal Sharpe ~1.5 2021-2026 | Yes | FLAGGED: need volume / order flow; VWAP approximable by TWAP of 1-min closes only |

Key cross-cutting finding: on 5-minute MNQ bars 2022-2025, every single-bar OHLCV pattern (ORB variants, gap fill, volume spikes/dry-ups, Asia-session expansion, event-day trend, OU mean reversion on MGC) failed a 5-gate walk-forward test; gross edge was 0.07-1.5 pts/trade vs a 2.0-pt friction floor (Mesfin 2026, arXiv 2605.04004). The strategies that do survive in 2018-2026 hold positions for hours (noise-area / ATR-band trend, pre-FOMC, conditional day-of-week), are volatility-targeted, and trade at most 1-3 times per day.

---

## 1. Market Intraday Momentum (first half-hour predicts last half-hour)

**Origin.** Gao, Han, Li, Zhou (2018), "Market Intraday Momentum", Journal of Financial Economics 129(2), 394-414 (SSRN 2440866). Quantpedia strategy "Market Intraday Momentum" is derived from it.

**Rules (as published).**
- Instrument: SPY (also IWM, IYR, other ETFs). Data 1993-2013, 1-min bars.
- Predictors: r1 = return 09:30-10:00 (includes overnight gap, measured from prior close to 10:00 in the paper's main spec) and r12 = return 15:00-15:30.
- Regression: r13 (15:30-16:00) = a + b1*r1 + b12*r12 + e; both betas positive and significant.
- Trading rule: at 15:30, go long for the last half hour if r1 > 0 (or if both r1 and r12 > 0), short if r1 < 0; exit at 16:00 close (MOC).
- Reported: average annual return 6.67% for SPY, 11.72% IWM, 24.22% IYR (QuantConnect's summary of the paper); success rate ~55-60%; stronger on high-volatility, high-volume, recession and major-news (FOMC) days.

**Evidence quality: 4** for existence in the original sample (peer-reviewed, replicated in multiple markets), but every independent post-publication test says the net edge is gone for large-cap index products:
- Dead Signals Lab (2026), "Replication: Intraday Momentum, Eight Years Later": SPY 2014-2026, QQQ 2011-2026, IWM/DIA 2004-2026; rule = sign of 09:30-10:00 return, enter 15:30, exit close; net -2.30 bp/day, t = -5.17, win rate 43-49%, at 2 bp round-trip (robust to 1 bp). IWM gross +1.40 bp/day pre-2018, +0.08 bp/day post-2018. Large caps show slight reversal, not momentum.
- QuantConnect Strategy Library "Intraday ETF Momentum": SPY/IWM/IYR, 2015-01 to 2020-08, Sharpe -0.63 vs benchmark 0.58; only positive during Feb-Mar 2020 crash (Sharpe 1.45).

**Prop-fit.** Poor. A 30-minute hold on ES captures ~0.1-0.2% moves (5-12 ES pts) against ~0.25-0.5 pt round-trip friction; sign-only rule has no edge net since 2014. Keep only the lesson that the last 30 minutes carry a conditional momentum (see #3) and that any edge is concentrated on high-VIX / FOMC days.

**Data requirements.** 1-min OHLC only. Sources: Gao et al. (JFE 2018); https://deadsignalslab.substack.com/p/replication-intraday-momentum-eight ; https://www.quantconnect.com/tutorials/strategy-library/intraday-etf-momentum ; https://eranraviv.com/market-intraday-momentum/

---

## 2. Noise-Area intraday momentum ("Beat the Market") - SPY paper and ES/NQ replication

**Origin.** Zarattini, Aziz, Barbon (2024), "Beat the Market: An Effective Intraday Momentum Strategy for S&P500 ETF (SPY)", SSRN 4824172; full PDF: https://concretumgroup.com/wp-content/uploads/2026/02/Beat-the-Market.pdf. Independent futures replication: Quantitativo, "Intraday momentum for ES and NQ" (2025), https://www.quantitativo.com/p/intraday-momentum-for-es-and-nq.

**Exact rules (paper).**
1. For each of the previous 14 days (i = 1..14) and each time-of-day HH:MM, compute move_{t-i,HH:MM} = |Close_{t-i,HH:MM} / Open_{t-i,09:30} - 1|.
2. sigma_{t,HH:MM} = mean over the 14 days of move_{t-i,HH:MM} (a time-of-day-dependent "average move from open" curve; rises through the day, so the band is U/funnel shaped).
3. UpperBound_{t,HH:MM} = max(Open_{t,09:30}, Close_{t-1,16:00}) * (1 + VM * sigma_{t,HH:MM}); LowerBound = min(Open_{t,09:30}, Close_{t-1,16:00}) * (1 - VM * sigma_{t,HH:MM}). VM = volatility multiplier, default 1 (lower VM -> more trades, higher total return, lower Sharpe).
4. Decisions only at HH:00 and HH:30 (first decision 10:00). If price > UpperBound -> long; if price < LowerBound -> short; otherwise flat.
5. Exit: (a) at the 16:00 close always; (b) trailing stop checked only at half-hour marks: long stop = max(UpperBound_{t,HH:MM}, VWAP_{t,HH:MM}); short stop = min(LowerBound, VWAP). Base version used the opposite band as the stop; the "current band + VWAP" stop doubled the Sharpe (0.61 -> 1.24) and cut MDD (-10.3% worst-day -> -4.8%).
6. Sizing: shares = AUM * min(4, 0.02 / sigma_SPY,14d) / Open, i.e. target 2% daily vol with 4x cap (sigma = 14-day std of daily returns).
7. Costs: $0.0035/share commission + $0.001/share slippage (measured on 1,000+ live orders).

**Reported performance (SPY, May 2007 - Apr 2024).**
- Base (opposite-band stop, 100% notional): total 178%, 6.2%/yr, vol 10.9%, Sharpe 0.61.
- Current band + VWAP stop, 100%: 380%, 9.7%/yr, vol 7.7%, Sharpe 1.24, hit ratio 43%, MDD 12%.
- Current band + VWAP stop, vol-targeted (2%, cap 4x): 1,985% total, 19.6%/yr, vol 14.3%, Sharpe 1.33, MDD 25%, hit 43%, 7,668 trades, best trade +9.1%, worst -2.9%, alpha 19.6%/yr, beta -0.07.
- Conditional results: Sharpe rises monotonically with VIX at the open (approx. 1.5 for VIX>6 up to ~3.5 for VIX>40). Day-of-week: Wed 18 bp/day (t=3.42), Thu 12 bp (t=2.39), Fri 13 bp (t=2.39), Mon 9 bp (t=1.84), Tue 9 bp (t=2.00). Daily patterns: NR4 (narrowest range of 4) days 22 bp (t=5.14), Triangle 14 bp (t=3.19); after a "trend day" -2 bp (t=-0.24).

**Independent ES/NQ replication (Quantitativo, Databento 1-min, 2010-2025).** Costs $0.85 commission + $1.40 fees per contract per transaction + 0.25 tick slippage per transaction. Original 14-day/2%/4x version under-performed the paper (realistic slippage, no 2008). Improved version: 90-day lookback for the band, 3% daily vol target, 8x cap: ES 16.8%/yr, Sharpe 1.25, MDD 21%, win ~38%, +4 bp/trade; NQ 24.3%/yr, Sharpe 1.67, MDD 24%, win 38%, +6 bp/trade; combined portfolio Sharpe 1.57, MDD 15%, 65% positive months, 2 negative years in 16, worst month -6.6% (Sep 2011). Important: "basically flat 2010-2017, works from 2018 on."

**Evidence quality: 4.** Published paper with full code-level spec, live-measured slippage, plus an independent replication on the exact instruments we trade, with the improvement that the band lookback is longer (90 d). Not peer-reviewed; the 2018+ regime dependence is a caveat.

**Prop-fit: Best in family.** Day-trade only, flat at close, OHLC-only (VWAP can be approximated by the cumulative mean of 1-min closes or (H+L+C)/3 since no volume; flag). Expect ~1-2 entries per active day, ~40% hit rate, wins 2-3x losses. For Lucid 50K: scale to a $600-900 daily-vol budget (e.g., 3-6 MES or 2-4 MNQ when ES 14-day daily vol is ~1%); a +4-6 bp/trade edge on ES at 6 MES notional ($180k) is ~$70-110 per trade. Consistency rule: cap daily profit at ~$1,200 by stopping new entries once the day's P&L exceeds the cap. Band checks only at HH:00/HH:30 keep trades per day low (good for the $2k EOD trailing DD).

**Data requirements.** 1-min OHLC; VWAP needs volume (approximate). Sources: Beat-the-Market PDF (above); Quantitativo ES/NQ post; QuantSeeker/Quantpedia discussion of the paper.

---

## 3. Last-half-hour momentum driven by hedging demand (and the end-of-day reversal it competes with)

**Origin.** Baltussen, Da, Lammers, Martens (2021), "Hedging demand and market intraday momentum", Journal of Financial Economics 142(1), 377-403 (Robeco/SSRN 3760365). Related: Heston, Korajczyk, Sadka (2010 JF) periodicity; Bogousslavsky (2021 JFE) overnight vs last-half-hour cross-section; the leveraged-ETF rebalancing mechanism (QuantRocket post below).

**Rules (standard interpretation of the paper).**
- Universe in paper: ~60 futures (equity indices incl. ES, bonds, commodities, FX), 1-min data, roughly 1996/2000-2019.
- At 15:30 ET compute the "rest-of-day" return R_rod = Close_{15:30}/Close_{prior day 16:00} - 1 (the paper uses the return from the prior close to 30 min before close; some specs use open-to-15:30).
- Go long for 15:30-16:00 if R_rod > 0, short if R_rod < 0. Paper finds a positive coefficient that is strongest in equity index futures and when market makers / option dealers are short gamma (after large moves, when realized vol is high), and when leveraged-ETF rebalancing is large. The effect is a continuation (momentum), not a reversal.
- Reported: significant positive last-half-hour predictability across 60+ markets (t-stats 3-6 in pooled regressions); long-short last-half-hour strategy Sharpe ~1 in equity indices in-sample (paper figure; exact number not re-extracted here - flagged).

**Competing evidence (end-of-day reversal).** Dead Signals Lab finds slight last-half-hour *reversal* (not momentum) for SPY/QQQ/DIA 2014-2026 when conditioned on the first half hour; the Baltussen signal conditions on the whole day and on hedging demand, which is the difference. QuantRocket (2017) "Intraday momentum with leveraged ETFs": signal = prior close -> 14:00 return, enter 14:00, exit 15:45 if |move| > threshold; +/-6% threshold on 3x ETFs gave CAGR 31% after costs, Sharpe 1.95 (2008-2016) but "flattens out beginning in 2017".

**Objective rule to test on ES/NQ (interpretation).** If |Close_{15:30}/Close_{prev 16:00} - 1| >= k * sigma_daily (k ~ 0.75-1.0) then take the direction of that move at 15:30 and exit at 15:59; otherwise do nothing. Expect edge concentrated on high-vol days and option-expiry/FOMC days.

**Evidence quality: 4** (peer-reviewed across many futures) for the unconditional effect; 2 for post-2020 persistence (not independently re-tested; the ETF cousin decayed).

**Prop-fit.** Medium. 30-minute hold limits risk (~0.2-0.4% of notional); needs enough MES to make 5-10 pts matter (10 MES = $250-500 per 5-10 pts). Fits consistency rule well (small, frequent days), but fat-tailed on FOMC/NFP days.

**Data requirements.** 1-min OHLC only (gamma proxy requires options data: flagged, use realized-vol proxy). Sources: Baltussen et al. JFE 2021; https://www.quantrocket.com/blog/leveraged-etf-intraday-momentum/ ; Dead Signals Lab replication.

---

## 4. ATR-band intraday breakout (Concretum "Fast Alphas" baseline trend model)

**Origin.** Concretum QuanTips #2, "Improving Performance with Fast Alphas: A Tactical Overlay for Intraday Trend Trading" (2026), SSRN 6391638; PDF https://concretumgroup.com/wp-content/uploads/2026/02/Improving-Performance-with-Fast-Alphas-A-Tactical-Overlay-for-Intraday-Trend-Trading.pdf. Rule attributed to Kaufman, Trading Systems and Methods (2013).

**Exact rules.**
- Data: SPY 5-min bars, Jan 2007 - Jan 2026, RTH only.
- At session open: Upper = Open_{09:30} + 0.5 * ATR(14) (daily ATR), Lower = Open_{09:30} - 0.5 * ATR(14).
- Long when a bar closes above Upper; short when a bar closes below Lower. Execution only at HH:00, HH:15, HH:30, HH:45.
- Stop: position closed if price returns to the session open level (the open acts as the stop). All positions flat at the close.
- Sizing: 14-day realized vol of daily SPY returns, target 2% daily portfolio vol; size fixed for the day.
- Reported: CAGR > 13%, Sharpe ~0.87 net of fees, "double-digit CAGR" with no regime filter.
- Fast-alpha overlay (#21): delay entries until one opposite-direction 5-min bar prints (long entry needs a negative 5-min bar first), and delay stop-exits until one bar in the position's favor; this raises the Sharpe above 0.87 (exact improved figure cut off in extraction; paper states "improves the Sharpe ratio from 0.87 to [higher]").

**Evidence quality: 3** (practitioner research note, in-sample 2007-2026 including the prime window, net of costs, no walk-forward).

**Prop-fit.** Good. Simplest fully codeable intraday trend rule; the open-as-stop keeps max loss per trade ~0.5 ATR (ES ATR14 ~ 60-80 pts in 2025 -> 30-40 pts = $150-200 per MES). One to two trades per day. Pair with 15:59 flat and a daily loss cap of $600.

**Data requirements.** OHLC only. Sources: PDF above.

---

## 5. 5-minute Opening Range Breakout (ORB) with ATR stop and EOD exit

**Origin.** Zarattini & Aziz (2023), "Can Day Trading Really Be Profitable?", SSRN 4416622 (PDF https://concretumgroup.com/wp-content/uploads/2026/02/Can-Day-Trading-Really-Be-Profitable.pdf); "A Profitable Day Trading Strategy for the U.S. Equity Market" (2024, SSRN 4729284, stocks in play); Concretum replication with Polygon data (2025) https://www.concretumgroup.com/backtesting-the-opening-range-breakout-orb-strategy-using-polygon-io/ ; falsification on MNQ: Mesfin (2026) arXiv 2605.04004.

**Exact rules (paper).**
- Instrument QQQ / TQQQ, 2016-01-01 to 2023-02-17, 5-min bars.
- If the first 5-min candle (09:30-09:35) closes up, buy at the open of the second candle (09:35); if it closes down, sell short at 09:35; no trade on doji.
- Stop = low of the first candle (long) / high (short); R = entry - stop. Target 10R or end of day, whichever first. Risk 1% of equity per trade, max leverage 4x, commission $0.0005/share, no slippage.
- Results QQQ: total 675% (vs 169% buy-hold), alpha 33%/yr, Sharpe 1.12, win rate 24%, 51% of trades long; TQQQ: 1,484% total, 48%/yr, vol 39%, Sharpe 1.19, MDD 28%.
- Sensitivity: best = stop at 5% of 14-day ATR and hold to EOD (no target): TQQQ +9,350% 2016-2023, alpha 93%/yr (authors warn slippage with an $0.08 stop makes this unrealistic at size).
- Polygon replication (TQQQ, 2016-01-01 to 2025-02-21, stop at OR high/low, no target, EOD exit, 1% risk, 4x cap): total 2,328%, CAGR 41.9%, Sharpe 1.07, MDD -37.1%; by year 2016 +92%, 2018 +90%, 2019 +50%, 2021 +44%, 2023 +13%, 2024 +33%, 2025 (partial) +22%.

**Negative evidence on futures.** Mesfin (2026), MNQ 5-min RTH, Dec 2021 - Aug 2025, 947 days, OR = 09:30-09:55, entry next bar open, 2.0-pt round-trip friction, expanding-window walk-forward (OOS 2023/2024/2025): ORB long bar+1 net -0.82 pts (T=-0.82); ORB long bar+15 (75-min hold) net +2.82 pts, T=0.88 (2023 +2.43, 2024 +7.04, 2025 +15.05: improving but not significant); ORB short bar+1 net -3.45 (T=-3.16); ORB short bar+15 -2.16; pullback entry -4.44. Verdict: FAIL on all five gates. Unconditional long 09:30 -> 10:35 in MNQ 2022-2024: -2.60 pts, T=-0.75.

**Evidence quality: 3.** Two consistent in-sample papers plus one favorable replication (same group) on a 3x ETF; one independent strict test on MNQ is negative/weak. ORB shorts are consistently bad; longs with long holds are marginally positive.

**Prop-fit.** Medium-low. 24% win rate with 10R targets produces lumpy equity (a few huge days), which collides with the 50% consistency rule in the eval and with the $2k trailing drawdown (strings of 1R losses). If used: long-only, 15-min opening range, stop = 0.1-0.25 x ATR(14), EOD exit, 1 MES-2 MES, and cap the daily profit.

**Data requirements.** OHLC only. Sources listed above.

---

## 6. Pre-FOMC announcement drift

**Origin.** Lucca & Moench (2015, JF; NY Fed Staff Report 512, 2011/2013), PDF https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr512.pdf. Updates: Lucca & Moench, Liberty Street Economics (Nov 2018) "The Pre-FOMC Announcement Drift: More Recent Evidence"; Quant Seeker (2025) "Trading the Fed: The Pre-FOMC Drift is Alive"; Liu, Tang & Zhou (2022) on FOMC risk premium; Cocoma (2017) theory (Quantpedia #75 "FOMC meeting effect").

**Rules and numbers (SR 512).**
- Sample Sep 1994 - Mar 2011, 131 scheduled meetings; announcements at 14:15 ET (since 2013 the statement is at 14:00 ET).
- Window: 14:00 ET day before -> 14:00 ET announcement day (24h "2pm-to-2pm"). Mean excess return +49 bp (t > 4.5); other 2pm-2pm windows < 0.5 bp. 98 of 131 positive (75%). Annualized Sharpe of "long SPX 14:00 day before, sell 15 min before the announcement, cash otherwise" = 1.14. Alternative windows: close-to-14:00 (i.e., 16:00 prior day -> 14:00) Sharpe 1.43; close two days before -> 14:00: +54 bp, Sharpe ~1. Post-announcement 14:00-16:00 return ~0; close-to-close FOMC day +33 bp, Sharpe 0.84. Pre-1994 (1980-93) +20 bp on meeting days.
- Timing shape: slight rise on the afternoon before, then "drifts sharply higher in the morning of scheduled FOMC announcements" to about +50 bp by 14:00.
- Conditioning: higher when the Treasury curve slope is low and when VIX is high (1 sd VIX -> +31 bp); the drift is NOT in Treasuries or fed funds futures; confirmed in E-mini futures from Sep 1997; similar in 5 foreign indices (Sharpe 0.75-1.04).

**Post-2011 evidence.**
- Liberty Street 2018 (Apr 2011 - Jun 2018): ~40 bp but only before meetings with a Chair press conference; no excess return before non-press-conference meetings; returns now start the morning of the day before and run to about lunchtime on announcement day. All meetings have press conferences since 2019.
- Quant Seeker 2025: SPY Jan 1993 - Dec 2024, long at the close before the meeting day, exit at the close of the announcement day: CAGR ~4%, Sharpe 0.5-0.6 while invested only ~5% of days; TQQQ/SPXL versions 8-9% CAGR, Sharpe ~0.6, MDD ~18%; flat 2016-2019, strong again 2020-2024; larger in high-VIX periods.

**Objective day-trade rule for Lucid (interpretation, because overnight holds are not allowed).** On the 8 scheduled FOMC decision days per year, buy ES/MES at 09:30 ET (or at 18:00 ET Globex reopen the prior evening if within-session holds are permitted) and sell at 13:55 ET, before the 14:00 statement; never hold through 14:00. Skip if VIX < 13 (drift concentrated in high-VIX regimes). Expected +15-35 bp per event in the morning portion (interpretation from the drift shape; the paper does not report the 09:30-14:00 slice separately: flag).

**Evidence quality: 5** (peer-reviewed, replicated by the Fed and independents, OOS to 2024), with the caveat that 2016-2019 was flat.

**Prop-fit.** Good as an overlay: 8 trades/yr, defined risk (stop 0.5% below entry), eligible for the "$150 EOD profit day" payout count. Will not pass an eval alone.

**Data requirements.** OHLC + FOMC calendar + VIX daily. Sources: SR 512 PDF; https://libertystreeteconomics.newyorkfed.org/2018/11/the-pre-fomc-announcement-drift-more-recent-evidence/ ; https://www.quantseeker.com/p/trading-the-fed-the-pre-fomc-drift ; https://quantpedia.com/explaining-fomc-drift/

---

## 7. Overnight drift in ES at the European open (02:00-03:00 ET)

**Origin.** Boyarchenko, Larsen, Whelan, "The Overnight Drift", NY Fed Staff Report 917 (Feb 2020, rev. Aug 2022), PDF https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr917.pdf. Replicated by Bondarenko & Muravyev (2020).

**Findings.**
- ES mid-quote returns, Jan 1998 - Dec 2020 (23 years). Hourly average log return 02:00-03:00 ET = +1.48 bp/day (3.7%/yr); 24:00-01:00 +0.46 bp, 01:00-02:00 +0.43 bp; opening hour 09:00-10:00 ET -1.2 bp (t=2.6), 17:00-18:00 -0.43 bp. The 02:00-03:00 hour is positive in 20 of 23 years, significant in 17, on every weekday, the only hour that stays significant in both 1998-2010 and 2011-2020 halves; largest year 2020 (+10.7%); slightly negative in 2002 and 2008-type years.
- Mechanism: end-of-day order imbalance (negative RSV = relative signed volume at 15:15-16:15) is reversed when European liquidity arrives; reversals after sell-offs are much stronger than after rallies; larger when VIX is high.
- Strategies 2004-2020 (Table IX): long 02:00-03:00 (OD): 3.8%/yr, Sharpe 1.1 pre-cost, about -0.5 after bid-ask; OD+ = long 01:30-03:30: Sharpe 1.3 pre-cost, 0.3 post-cost; "Buy-the-Dip" = OD+ only on days following negative closing order flow (~50% of days): Sharpe 1.8 pre-cost, 1.1 post-cost, positively skewed. Continuous ES hold same period 8.9%/yr Sharpe 0.42; CTO (16:15->09:30) 4.6%/yr; OTC 4.2%/yr.

**Objective rule (interpretation for OHLC-only).** Proxy "negative closing order flow" by the prior RTH day's close-to-close return < 0 (or last-hour 15:00-16:00 return < 0). On such days buy ES/MES at 01:30 ET and sell at 03:30 ET; otherwise do nothing. Use limit entries to avoid paying the spread (the paper shows the post-cost Sharpe is the difference between 1.8 and 1.1).

**Evidence quality: 4** (Fed staff report, long sample, replicated; post-cost edge is thin and the conditioning variable needs volume: flagged).

**Prop-fit.** Medium. Within the CME trading session (18:00->17:00), so not an "overnight hold" if Lucid defines overnight as holding through the 17:00 close - verify with Lucid. Edge per day ~1.5-3 bp of notional = $4-8 per MES; needs 10-20 MES to matter, which raises tail risk around European data at 03:00-04:00 ET. Many tiny positive days helps the consistency rule but each day rarely clears the $150 payout-day threshold.

**Data requirements.** 1-min OHLC for the Globex session (available); RSV needs volume (flag). Sources: SR 917 PDF; https://robotwealth.com/revisiting-overnight-vs-intraday-equity-returns/

---

## 8. Overnight (close-to-open) equity premium

**Origin.** Cooper, Cliff, Gulen (2008) "Return differences between trading and non-trading hours"; Lou, Polk, Skouras (2019 JFE) "A tug of war: overnight vs intraday expected returns" (https://personal.lse.ac.uk/polk/research/TugofWar.pdf); Kelly & Clark; Quantpedia "Overnight anomaly".

**Rules.** Buy SPY/ES at 16:00 close, sell at 09:30 open next day; or hold 18:00 Globex reopen -> 09:30.

**Evidence.** Quanter Lab (2026): S&P 500 constituents Jul 2000 - Jul 2026: close-to-open 7.2%/yr, Sharpe 0.67; open-to-close negative in early sub-periods; buy-and-hold 12.1%/yr Sharpe 0.63. Net of costs the overnight-only rule fails: break-even cost ~0.01%/trade; at 0.05%/side "a dollar shrank to less than a cent" over 26 years; at half a cent per share it only matches buy-and-hold; NightShares ETFs (NSPY, NIWM) launched 2022, closed 2023 after under-performing. Robot Wealth (2024): SPY 2000-2024, most of the return still comes overnight 2020-2024, but so do most of the big negative returns. Lou-Polk-Skouras: at the firm level overnight and intraday returns show persistence within component and reversal across components; aggregate returns higher overnight than intraday.

**Evidence quality: 4** for the existence of the premium; 4 that it is not harvestable net via daily round trips.

**Prop-fit.** Poor. Holding through the 17:00 ET session close is prohibited; the 18:00 -> 09:30 slice is tradable in ES (no commissions on the cash close) but the per-night edge (~2-3 bp) is below ES friction unless conditioned (see #7). The intraday (09:30-16:00) leg has historically been ~0 on average: a reason to prefer conditional intraday rules over unconditional long bias.

**Data requirements.** OHLC only. Sources: https://quanterlab.com/research/the-overnight-gain-is-real-no-trade-keeps-it-the-rule-that-chases-it-buys-wrecks ; Robot Wealth; LSE TugofWar PDF.

---

## 9. Turnaround Tuesday (conditional on Monday down)

**Origin.** Cross (1973) and Gibbons-Hess (1981) day-of-week literature; Quantpedia "Turnaround Tuesday"; TradeQuantiX (2025/26) "Market Effect Research: Turnaround Tuesday Effect" https://www.tradequantixnewsletter.com/p/market-effect-research-turnaround ; Beyond Passive (2025) "Fridays for Gold, Tuesdays for Stocks" https://beyondpassive.substack.com/p/fridays-for-gold-tuesdays-for-stocks.

**Rules and numbers.**
- SPY 1993-2026 (TradeQuantiX): unconditional Tuesday +0.071% (~1.5x the average day). Enter Monday close, exit Tuesday close: +0.10% when Monday closed down; +0.33% when both Friday and Monday closed down. The Monday-down conditioning is "stable over time" across three eras; the best unconditional weekday rotates (Mon -> Tue -> Wed).
- VTI Dec 2007 - Sep 2025 (Beyond Passive): ensemble rule = enter Monday close if (VIX/VIX3M in top decile, i.e. backwardation, and Monday < Friday close) OR (outside top decile and both Friday and Monday down); exit Tuesday close. Mean +0.469%/trade, t = 3.29, 176 trades (~10/yr); inside backwardation decile t = 3.04. Combined with the GLD Friday rule (#10): $1 -> $4.36, MDD -6.1%, t = 4.99, Sharpe 1.18.

**Objective day-trade rule (interpretation).** The documented edge is Monday close -> Tuesday close, which includes the overnight. The Lucid-compatible version is: if Monday RTH close < Friday close (and optionally Friday also down, or VIX > VIX3M), buy ES/MES at 09:30 Tuesday, exit 15:59. The split of the +0.33% between overnight and Tuesday RTH is not reported: must be backtested.

**Evidence quality: 3** (long samples, two independent practitioner tests, no peer-reviewed post-2015 paper found).

**Prop-fit.** Good overlay: ~10-25 trades/yr, typically a 0.2-0.5% expected move = 10-25 ES pts; 4 MES gives $200-500 on an average winner. Fits the "5 days >= $150" payout rule well.

**Data requirements.** Daily OHLC, VIX and VIX3M daily (Yahoo ^VIX, ^VIX3M). 

---

## 10. Gold Friday effect (Thursday close -> Friday close)

**Origin.** Beyond Passive (2025) "Fridays for Gold, Tuesdays for Stocks"; related academic: Blose & Gondhalekar (2013) weekend effect in gold; Caminschi & Heaney (2014) on the London PM fix (10:00 ET) price pressure.

**Rule.** Buy GLD (GC) at Thursday close, sell at Friday close; rationale: risk managers add weekend protection on Thursday afternoon/Friday. Reported GLD Dec 2007 - Sep 2025: Sharpe 0.93 (return per trade not extracted).

**Day-trade interpretation.** Long MGC/GC on Fridays from 08:20 ET (COMEX open-outcry-equivalent / high liquidity) or 09:30 to 13:25 ET (pre-settlement), flat before 17:00. Untested split between overnight and RTH.

**Evidence quality: 2** (single practitioner study; adjacent peer-reviewed day-of-week gold literature is mixed).

**Prop-fit.** Medium-low. GC moves 1-1.5%/day in 2025-2026 (= $40-60 per MGC); a 0.1-0.2% Friday drift is small vs noise; use only as a tilt (prefer long-side gold trend trades on Fridays).

**Data requirements.** Daily/1-min OHLC only.

---

## 11. Payday anomaly (16th of the month)

**Origin.** Ma & Pratt, "Payday Anomaly" (SSRN 3257064); Quantpedia strategy "Payday Anomaly" https://quantpedia.com/strategies/payday-anomaly/ (Quantpedia-confidence "strong", complexity "simple").

**Rule.** Hold the S&P 500 (ETF/futures) on the 16th calendar day of each month (if a weekend/holiday, the next trading day; interpretation). The 16th "statistically and economically outperforms all other calendar days except the 1st and 2nd."

**Reported.** Backtest 1980-2010: mean +0.214% per event, annual ~2.57%, vol 4.31%, Sharpe 0.6, MDD -12.06%. Caveat from the authors: bi-weekly pay schedules dilute the mid-month effect.

**Evidence quality: 3** (SSRN paper + Quantpedia; no post-2015 OOS found).

**Prop-fit.** Weak overlay: 12 days/yr, +20 bp expected; day-trade version (09:30-15:59 on the 16th) is an interpretation, untested.

**Data requirements.** Daily calendar only.

---

## 12. VIX term-structure regime filter (VIX vs VIX3M; futures basis)

**Origin.** Simon & Campasano (2014 JAI) "The VIX futures basis: evidence and trading strategies"; Johnson (2017 JFQA) "Risk premia and the VIX term structure"; Robot Wealth "The VIX futures basis" https://robotwealth.com/the-vix-futures-basis/ ; Concretum/Zarattini (2025) "The Volatility Edge" SSRN 5316487, PDF https://concretumgroup.com/wp-content/uploads/2026/02/The-Volatility-Edge.pdf ; Quantpedia "VIX term structure" strategies.

**Rules (Concretum, VIX ETN proxies 2008-2025, signals computed 15:45 ET, MOC execution, 5 bp cost, 2% rebalance band).**
- eVRP = VIX - expected realized vol (from recent realized vol); contango if VIX < VIX3M, backwardation if VIX > VIX3M.
- Strategy 3 (eVRP + BoC): short vol 20% if eVRP > 0 and VIX < VIX3M; short vol 10% if eVRP <= 0 and VIX < VIX3M; long vol 20% if eVRP <= 0 and VIX > VIX3M.
- Strategy 4 adds sizing by VIX/100.
- Results: passive short vol 6.2%/yr, Sharpe 0.48, MDD -32%; add eVRP timing -> MDD -24%; dual signal -> Sharpe 0.87, MDD -15%, alpha 8.1%, corr to S&P 0.35; dual + sizing -> ~16.3%/yr, Sharpe ~1.0, equity correlation < 0.5.
- Robot Wealth / Simon-Campasano: slope of the VX term structure predicts VX returns at daily/weekly/monthly horizons; long VX when short-dated IV > long-dated IV, short otherwise; strong gains in stress periods.
- Beyond Passive: VIX/VIX3M top decile (backwardation) is where the conditional Tuesday long edge is strongest (t = 3.04).

**Use for ES/NQ intraday (interpretation).** Daily regime switch computed from the prior close: (a) contango (VIX < VIX3M) and VIX < 20 -> normal regime, trade #2/#4 trend rules at full vol budget; (b) backwardation (VIX > VIX3M) -> favor long-side mean-reversion after down days (#9, #14) and halve trend-rule size on the short side; (c) VIX > 35 -> halve all sizes (Lucid DD protection) even though per-trade Sharpe is highest here (#13).

**Evidence quality: 4** (peer-reviewed basis predictability; multiple independent backtests to 2025).

**Prop-fit.** Good as a filter; not a stand-alone ES strategy.

**Data requirements.** Daily ^VIX and ^VIX3M from Yahoo (available); VX futures curve not needed.

---

## 13. VIX / realized-vol conditioning of intraday trend returns

**Origin.** Beat the Market section 4.1 (Rosa 2019 cited); Gao et al. (2018) show intraday momentum stronger in high-vol periods; SR 512 shows the pre-FOMC drift larger when VIX is high.

**Finding.** Sharpe of the noise-area strategy by VIX-at-open bucket rises from ~1.5 (all days) to ~3.5 when VIX > 40, then drops for extreme VIX due to few observations. The strategy already vol-targets (2%/day) so this is incremental.

**Rule (interpretation).** Keep vol-targeting (position = budget / sigma_14d) and do not switch off trend rules in high VIX; instead cap notional by the Lucid DD budget: max daily loss <= 30% of remaining trailing-DD room.

**Evidence quality: 3.** **Prop-fit:** Good (sizing component). **Data:** daily VIX (Yahoo) or 14-day realized vol from OHLC.

---

## 14. ES short-term mean reversion in high-volatility regimes (RSI(2) / VIX-gated dip buying)

**Origin.** Connors & Alvarez RSI(2) family; Quanter Lab (2026) "RSI(2) mean reversion on the S&P 500, 2006 to 2025: dips, trading costs and the VIX" https://quanterlab.com/research/navigating-mean-reversion-breaking-down-the-base-mechanism ; Alvarez Quant Trading mean-reversion posts; MNQ/MGC OU tests in Mesfin (2026).

**Rules and numbers (Quanter Lab, S&P 500 point-in-time constituents, 2006-2025, 0.1%/side cost).** Entry: RSI(2) < 10 and close > 200-day MA; exit: close > 5-day MA. Every dip: 3.6% CAGR net (14.2% gross), Sharpe 0.30, MDD -32%, ~2,480 trades/yr. VIX >= 20 gate: 5.1% CAGR, Sharpe 0.47, MDD -27.5%, ~740 trades/yr, 60% of annual windows winning; gate shines 2020-2022, zero trades in 2017. Most of the 20-day bounce (0.94%) is market beta (0.06% excess).
- Negative: OU mean reversion on MGC 5-min bars (2022-2025, 0.5-pt friction) is negative in every configuration (T from -1.6 to -5.3); 60-min OU half-life ~8 hours - too slow for intraday. Beat the Market finds the opposite (momentum) works better in high vol.

**Objective index-level rule to test (interpretation).** If ES closed down 2+ consecutive days, VIX >= 20, and the 09:30-10:00 return is <= 0, buy at 10:00, stop 0.6 x ATR14 below, exit 15:59. Expect low frequency.

**Evidence quality: 2** for the intraday index version (not found tested); 3 for the multi-day stock version.

**Prop-fit.** Weak; multi-day holds are not allowed and 5-min mean reversion in futures fails after costs.

**Data requirements.** Daily OHLC + VIX.

---

## 15. Intraday return seasonality (hour-of-day, day-of-week)

**Origin.** Harris (1986); Heston, Korajczyk, Sadka (2010 JF) "Intraday patterns in the cross-section of stock returns" (half-hour return periodicity at daily lags); SR 917 hourly decomposition of ES 1998-2020; Beat the Market day-of-week table; Mesfin (2026) unconditional benchmarks; Kahler "Daily extremes - significance of time" (fetch failed; from the title only).

**Facts (ES, SR 917, 1998-2020).** 09:00-10:00 ET avg -1.2 bp/day (t=2.6), significantly negative only in recessions (2000-03, 2007-08, 2020) and on Thursdays/Fridays; 17:00-18:00 -0.43 bp; 02:00-03:00 +1.5 bp (the only hour significant in both halves); CTO 16:15->09:30 4.6%/yr vs OTC 4.2%/yr (2004-2020). MNQ 2022-2024: unconditional long 09:30 -> 10:35 = -2.60 pts net, T=-0.75 (no morning drift). Day-of-week for the noise-area strategy (SPY 2007-2024): Wed 18 bp (t=3.42), Fri 13, Thu 12, Tue 9, Mon 9 (t=1.84); Monday's move happens in the first 30 min so a 10:00 first entry misses it.

**Rules (interpretation).** (1) No unconditional longs 09:30-10:00; first directional entry at 10:00. (2) Prefer Wednesday (FOMC/trend days) and Thursday-Friday for trend rules; (3) HKS periodicity: the sign of the same half-hour's return on the previous day(s) predicts today's half-hour return in the cross-section of stocks - for a single index the effect is weak; treat as low priority.

**Evidence quality: 4** for the facts; 2 for a stand-alone tradable rule.

**Prop-fit.** Filter only. **Data:** OHLC only.

---

## 16. Overnight-gap predictability (gap fill vs gap continuation)

**Origin.** Berkman, Koch, Tuttle, Zhang (2012 JFQA) "Paying attention: overnight returns and the hidden cost of buying at the open" (attention stocks); Gao et al. (2018) use the overnight-inclusive first half hour; Mesfin (2026) MNQ gap tests; Beat the Market gap adjustment of the bands.

**Numbers (MNQ 5-min, 2022-2025 walk-forward, 2-pt friction).** Gap-fill fade entered 09:30: net -1.92 pts, T=-0.44 (2023 -2.84, 2024 +3.93, 2025 +2.02) -> FAIL. Gap-continuation short (gap down + negative Kalman-filtered 1-min velocity in the first 30 min): gross +16.53, net +14.52 pts, T=1.46, 35 trades (2023 +14.5, 2024 -11.9, 2025 +10.3) -> near-miss on year stability and trade count. Volatility-Volume-Gap classifier days (4.4% of days: top-tercile |first-30-min return|, |gap| and first-bar volume): 77.6% peak-reversal rate but no stable directional rule (reversal +8.35 in 2024, -22.76 in 2025).

**Rule (interpretation).** Do not trade gap fills on ES/NQ. The usable form is Beat the Market's: widen the noise band to max(open, prior close)/min(open, prior close) so gap-direction continuation is only traded once price exceeds the band from the gap-adjusted anchor.

**Evidence quality: 2.** **Prop-fit:** poor stand-alone. **Data:** OHLC (VVG needs volume: flag).

---

## 17. End-of-day momentum on large-move days (leveraged-ETF rebalancing)

**Origin.** Cheng & Madhavan (2009) on LETF rebalancing; QuantRocket (2017) "Intraday momentum with leveraged ETFs" https://www.quantrocket.com/blog/leveraged-etf-intraday-momentum/ ; Baltussen et al. (2021) include LETF flows as a driver of #3.

**Rule.** Signal = return from prior close to 14:00 ET; if |signal| > threshold (2% for 3x ETFs; optimum 6%), enter in the signal direction at 14:00, exit 15:45. Results: 14 LETFs 2008-2016, +/-6% threshold: CAGR 31% after costs, Sharpe 1.95; performance flat from 2017 (sponsors moved rebalancing/hedging earlier and into the close auction). Single-ETF (DRN) unprofitable after costs OOS.

**ES/NQ translation (interpretation).** |prior close -> 14:00 NQ move| > 2% (ES > 1.3%): trade direction 14:00 -> 15:55. Few signals per year outside 2020/2022/2025-04.

**Evidence quality: 3** (decayed). **Prop-fit:** weak-medium (rare, high-vol days clash with DD budget). **Data:** OHLC only.

---

## 18. Nasdaq - S&P lead-lag

**Origin.** Index-futures-lead-cash literature (Kawaller, Koch, Koch 1987; Stoll & Whaley 1990; Chan 1992) documents lead-lag of minutes that has since been arbitraged to seconds. Quantifiable Edges (2023) "NASDAQ no longer leading the SPX" uses a daily relative-strength line (NASDAQ vs SPX ratio vs its moving average) and states the market "performed substantially better over the years when the NASDAQ has been leading" without numbers.

**Rule (interpretation).** Regime filter: ratio NQ/ES close vs its 20-day average; above -> allow long-side trend entries in both, below -> allow short-side only or halve longs. Intraday lead-lag (NQ 1-min return predicting ES next-minute) should be tested but is expected to be ~0 net.

**Evidence quality: 1.** **Prop-fit:** poor; filter at best. **Data:** OHLC only.

---

## 19. Gold - equity cross-asset signals

**Origin.** Huang & Kilic (2019 JFE) gold/platinum ratio predicts equity premium; Fang, Su, Yin (SSRN 3950940) gold-oil ratio (1 sd -> +6.60% next-year excess return, monthly data); Bouri & Demir (2025 FRL) bitcoin/gold ratio (post-COVID only); Baur & Lucey (2010) gold is a safe haven on extreme equity down days; Beyond Passive gold/Tuesday combination (#10); "Speculation, cross-market sentiment and the predictability of gold market volatility" (J. Behavioral Finance 2022). Summarized at https://blog.harbourfronts.com/2025/06/09/gold-ratios-as-stock-market-predictors/.

**Rules.** Monthly: increase equity exposure when gold/oil or gold/platinum ratio rises (risk-off premium builds). Daily safe-haven: on days when ES is down > 1% by 10:00 ET, buy MGC at 10:00 and exit 15:55 (interpretation; Baur-Lucey document contemporaneous positive gold returns on extreme equity down days, not an intraday rule).

**Evidence quality: 2** for intraday; 4 for monthly predictors (peer-reviewed).

**Prop-fit.** Poor for intraday; the 2025-2026 gold regime (strong uptrend, 1-2% daily ranges) makes long-side gold trend rules (#20) more relevant than cross-asset timing. Needs oil (not available 2024-2026: flag) or platinum for ratios.

---

## 20. Time-series momentum and carry as a daily directional bias (ES, NQ, GC)

**Origin.** Moskowitz, Ooi, Pedersen (2012 JFE) "Time series momentum" (https://pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf); Koijen, Moskowitz, Pedersen, Vrugt (2018 JFE) "Carry" (https://pages.stern.nyu.edu/~lpederse/papers/Carry.pdf); Baltas & Kosowski; Quantpedia "Time Series Momentum Effect" (20.7%/yr, vol 15.7% on its landing table) and "Asset Class Trend-Following" (11.27%/yr, vol 6.87%).

**Rules.** TSMOM: sign of the past 12-month excess return of each contract, position scaled to 40% annualized vol (position = 0.4 / sigma_ex-ante), monthly; positive for every one of 58 contracts (1985-2009), diversified Sharpe > 1; S&P 500 futures sample mean 3.47%/yr vol 15.45%; gold 5.36%/yr vol 21.37% (passive). Carry: equity carry = (expected dividend yield - rf) from the futures basis; commodity carry = slope of the futures curve (front vs next); per-asset-class Sharpe 0.6-0.9; diversified carry Sharpe 1.49 (carry1-12 0.95). Fast variants (1-3 month lookbacks) have higher turnover and remain positive.

**Use for Lucid (interpretation).** Daily bias: compute 20/60/120-day return sign for ES/NQ/GC; only take intraday trend entries (#2/#4) in the bias direction, or size counter-bias trades at 50%. Carry for ES is positive almost always (dividend yield < rf in 2023-2026 flips it slightly negative; flag) and for gold is negative (contango), so carry adds little at a daily horizon.

**Evidence quality: 5** for the anomaly; 2 for the intraday-filter usage.

**Prop-fit.** Filter only; needs futures curve for carry (not available: flag).

---

## 21. Fast-alpha 5-minute reversal as an execution overlay

**Origin.** Concretum QuanTips #2 (see #4).

**Facts (SPY 5-min, 2007-2026).** After one positive 5-min bar the next bar averages about -1 bp; after streaks of 4+ bars the reversal is larger; standalone the N=1 reversal rule has a CAGR of ~31.9% gross but is unprofitable at IBKR standard commissions (break-even roughly $0.0005/share), i.e. not monetizable alone.
As an overlay on the ATR-band breakout: enter only after one opposite-direction 5-min bar following the 15-min breakout confirmation; exit at the stop only after one favorable 5-min bar. Net effect: better average entry/exit prices, Sharpe above the 0.87 baseline, modest change in exposure.

**Rule for ES/NQ.** Same logic with 1-min bars aggregated to 5-min; use limit orders at the prior bar's extreme instead of market orders (saves ~1 tick per side = $1.25-2.50 per MES/MNQ, which is the entire gross edge per the MNQ study).

**Evidence quality: 3.** **Prop-fit:** Good (execution), reduces the friction that kills single-bar signals. **Data:** OHLC only.

---

## 22. Volume / order-flow based day-trading (VWAP trend; morning order-flow reversal) - FLAGGED

**Origin.** Zarattini & Aziz (2023) "Volume Weighted Average Price: The Holy Grail for Day Trading Systems", SSRN 4631351 (PDF https://concretumgroup.com/wp-content/uploads/2026/02/Volume-Weighted-Average-Price.pdf); Quantpedia (2026) "Can Weakening Morning Order Flow Predict SPY Reversals?" https://quantpedia.com/can-weakening-morning-order-flow-predict-spy-reversals/ and "Building and Testing Trend-Following Strategies on One-Minute SPY Data" (retail-activity signals, 2021-2026).

**Rules and numbers.** VWAP trend: long when the 1-min close is above the RTH-only VWAP, short below (positions reversed on crossovers, flat at close); QQQ 2018-2023: $25k -> $192,656 (671%), MDD 9.4% (vs buy-hold 126%, MDD 37%, Sharpe 0.7); TQQQ: 8,242% total, 116%/yr. 56% of 1-min bars close above VWAP; QQQ repriced higher above VWAP and lower below VWAP.
Morning order-flow reversal: signal = order-flow imbalance (trades at ask minus at bid) in 09:30-10:00 declines for two consecutive days; enter long at 15:59, hold overnight or the full next day; Apr 2021 - Apr 2026: Sharpe ~1.5, better drawdown than price-based reversal benchmarks; signal strongest from the first 30 minutes.

**Data requirements: volume and signed order flow are NOT in our dataset.** VWAP can be approximated by the cumulative mean of 1-min (H+L+C)/3 (TWAP), which the VWAP paper does not test; order-flow signals cannot be approximated from OHLC.

**Evidence quality: 3** (VWAP paper in-sample, no walk-forward; Quantpedia test short sample). **Prop-fit:** VWAP-trend version is day-trade friendly but whipsaw-heavy (many reversals per day = friction); only test with the TWAP proxy and half-hour decision points.

---

## What the evidence says works in 2022-2026 (and what does not)

**Works or still shows an edge (with the stated conditions):**
1. Noise-area / volatility-band intraday trend following on ES and NQ with half-hour decision points, VWAP/band trailing stop, EOD exit and daily vol targeting: Sharpe 1.25 (ES) / 1.67 (NQ) 2010-2025 net of $2.25 + 0.25 tick per transaction; the edge appears from 2018 onward and improves with VIX. Longer band lookbacks (90 d) beat 14 d on futures. This is the backbone candidate for Lucid.
2. ATR-band breakout (open +/- 0.5 ATR14, 15-min execution, open-as-stop, EOD exit): Sharpe 0.87 net on SPY 2007-Jan 2026, improved by the "wait for one opposite 5-min bar" execution overlay.
3. Pre-FOMC drift: alive in 2020-2024 (press-conference meetings; all meetings since 2019), strongest when VIX is high; flat 2016-2019. Eight events per year.
4. Conditional Turnaround Tuesday (Monday down, especially Friday+Monday down or VIX in backwardation): +0.3-0.5% per trade, t ~3.3, stable across eras to 2026 (overnight-inclusive; RTH-only split must be tested).
5. VIX term structure (VIX vs VIX3M) as a regime switch: robust through 2025 for vol products and as a conditioner for the Tuesday effect.
6. Overnight drift 02:00-03:00 ET in ES: positive in 20 of 23 years to 2020 and the best year was 2020; post-cost only with conditioning on a prior-day sell-off and passive (limit) entries.

**Does not work (post-2015 OOS):**
1. The published first-half-hour -> last-half-hour sign rule on SPY/QQQ/DIA (net -2.3 bp/day, t = -5.2, 2014-2026) and on SPY/IWM/IYR 2015-2020 (Sharpe -0.63).
2. Single-bar OHLCV signals on 5-min MNQ 2022-2025 (ORB long/short with 1-bar holds, pullback entries, gap fill fades, volume spikes/dry-ups, Asia-session expansion, event-day trend, OU mean reversion on MGC): gross edge 0.07-1.5 pts/trade vs 2.0-pt friction; ORB shorts are reliably negative; only ORB long with a 75-min hold (+2.82 pts, T=0.88) and gap-continuation short (+14.5 pts, T=1.46) are near-misses.
3. Isolated overnight (close-to-open) harvesting: real premium, zero after daily round-trip costs (NightShares ETFs closed in 2023).
4. Leveraged-ETF end-of-day momentum: decayed since 2017.
5. 5-min reversal "fast alpha" as a stand-alone (costs exceed the ~1 bp edge).

**Design implications for the Lucid 50K Flex backtest.**
- Build the engine around #2 (noise-area trend) with #4 as a simpler fallback, #21 execution logic (limit entries after a one-bar pullback), daily vol targeting (budget ~ $600-900/day, i.e. 30-45% of the $2,000 trailing DD), and a profit cap per day (~$1,200) to satisfy the 50% consistency rule in the eval.
- Overlays that add independent, small, positive days (payout rule: 5 days >= $150): pre-FOMC morning long (#6), conditional Tuesday long (#9), VIX-regime switching (#12), day-of-week/time-of-day filters (#15: no 09:30-10:00 longs; Wed-Fri emphasis).
- Do not spend backtest cycles on: first/last half-hour sign rules (#1), gap fills (#16), 5-min mean reversion in MGC (#14), volume/order-flow rules (#22) that cannot be computed from OHLC.
- Instruments: NQ/MNQ shows the larger intraday-trend edge (Sharpe 1.67 vs 1.25); ES/MES is smoother; GC/MGC has no positive intraday-pattern evidence in this family except the Friday tilt (#10) and the macro trend filter (#20).

---

## Source list (fetched and read in full unless noted)

- Lucca & Moench, "The Pre-FOMC Announcement Drift", NY Fed Staff Report 512 (PDF, full text).
- Lucca & Moench, Liberty Street Economics, "The Pre-FOMC Announcement Drift: More Recent Evidence" (Nov 2018).
- Quant Seeker, "Trading the Fed: The Pre-FOMC Drift is Alive" (2025).
- Quantpedia, "Explaining the FOMC Drift" (2017) and strategy #75.
- Boyarchenko, Larsen, Whelan, "The Overnight Drift", NY Fed Staff Report 917 (PDF, full text, rev. 2022).
- Lou, Polk, Skouras, "A tug of war: Overnight versus intraday expected returns", JFE 2019 (PDF).
- Quanter Lab, "The overnight gain is real, no trade keeps it..." (2026); Robot Wealth, "Revisiting overnight vs intraday equity returns" (2024).
- Gao, Han, Li, Zhou, "Market Intraday Momentum", JFE 2018 (SSRN blocked; summarized via QuantConnect, Eran Raviv, Dead Signals Lab and the MNQ paper's citations).
- Dead Signals Lab, "Replication: Intraday Momentum, Eight Years Later" (2026).
- QuantConnect Strategy Library, "Intraday ETF Momentum" (2015-2020 backtest).
- Zarattini, Aziz, Barbon, "Beat the Market" (2024) PDF, full text.
- Quantitativo, "Intraday momentum for ES and NQ" (2025).
- Concretum, "Improving Performance with Fast Alphas" (2026) PDF, full text.
- Zarattini & Aziz, "Can Day Trading Really Be Profitable?" (2023) PDF, full text; Concretum ORB/Polygon replication (2025).
- Zarattini & Aziz, "Volume Weighted Average Price" (2023) PDF, full text.
- Zarattini et al., "The Volatility Edge" (2025) PDF, full text.
- Mesfin, "Structural Limits of OHLCV-Based Intraday Momentum Signals in MNQ Futures: A Systematic Falsification Study", arXiv 2605.04004v3 (2026) PDF, full text.
- Christensen, Turner, Godsill, "Hidden Markov Models Applied To Intraday Momentum Trading With Side Information", arXiv 2006.08307 (ES 1-min, pre-cost Sharpe > 2 on one year; not used as evidence).
- Moskowitz, Ooi, Pedersen, "Time Series Momentum", JFE 2012 (PDF); Koijen, Moskowitz, Pedersen, Vrugt, "Carry", JFE 2018 (PDF); AQR summary pages.
- Quantpedia: "Payday Anomaly" strategy page; "Can Weakening Morning Order Flow Predict SPY Reversals?" (2026); "Building and Testing Trend-Following Strategies on One-Minute SPY Data" (2026); landing-page performance table (Time Series Momentum 20.7%, Asset Class Trend-Following 11.27%).
- TradeQuantiX, "Market Effect Research: Turnaround Tuesday Effect"; Beyond Passive, "Fridays for Gold, Tuesdays for Stocks" (2025).
- Quanter Lab, "RSI(2) mean reversion on the S&P 500, 2006 to 2025".
- Robot Wealth, "The VIX Futures Basis"; QuantRocket, "Intraday Momentum with Leveraged ETFs".
- Quantifiable Edges, "NASDAQ no longer leading the SPX" (2023); Harbourfronts, "Gold Ratios as Stock Market Predictors" (2025).
- Not reachable in this session (noted for follow-up): SSRN pages (403), Alpha Architect (403), ScienceDirect (403), Semantic Scholar API (429), Quantpedia site search (returns home page), welovealgos.com (DNS), Kahler quanttrader.com (empty page).
