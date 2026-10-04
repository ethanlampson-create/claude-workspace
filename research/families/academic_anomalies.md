# Family: Academic / Quantpedia-style anomalies for equity-index and gold futures

Scope: intraday momentum, overnight premium, short-term reversal in futures, VIX-based timing, VIX term structure, pre-/post-FOMC, end-of-day reversal, trend + carry, gold/equity cross-asset, high-vol mean reversion, NQ/ES lead-lag, intraday seasonality, gap predictability, payday, Tuesday reversal, turn-of-month, witching days.

Target use: Lucid Trading 50K "LucidFlex" (target +$3,000; $2,000 EOD-trailing DD; 50% consistency in eval; day-trade only; 4 minis / 40 micros in eval). Backtest data: 1-minute OHLC (no volume) for ES/MES, NQ/MNQ, GC/MGC proxies, Nov-2010 to Sep-2026; daily futures + VIX from Yahoo. All times below are **US Eastern (ET)**.

Research date: 2026-10-03. Sweep: 25+ web searches (standard + extended), ~18 primary documents read (JFE papers, NY Fed staff reports, SSRN working papers, Quantpedia strategy pages, independent replications on GitHub/Substack/QuantConnect, two master's theses with 1-minute ES / 5-minute gold data).

---

## 0. Executive summary

**What is actually robust and codeable from 1-minute OHLC, day-only:**

1. **Rest-of-day -> last-30-minutes momentum (Baltussen, Da, Lammers, Martens, JFE 2021).** The single best-documented intraday effect for *futures*: 60+ contracts, 1974-2020, equity-index 1/N portfolio Sharpe 1.73 (gross), commodities 1.42, all four asset classes, coefficients *larger* in 2000-2020 than in 1974-1999 for equities. Codeable with one trade per day at 15:30 ET, flat at 16:00. Only ~2.7 bp/day average on the index, so per-contract dollars are small but the hit rate (55-61%) and daily consistency are exactly what the Lucid consistency / 5-green-day payout rules want.
2. **Noise-area intraday momentum (Zarattini, Aziz, Barbon 2024)**: Sharpe 1.33 on SPY 2007-2024 with full rule set published; independent replication (codecat-ops, 2020-2026) confirms Sharpe ~1.1 with beta ~0 and ES-vs-SPY correlation 0.97, but **Sharpe ~0 in 2025-2026** on both ES and SPY. Treat as "works in high-vol regimes, dead in grinding tape" and gate on VIX.
3. **Gap-fill on ES (Trequattrini / Nova SBE 2022, 1-min ES 2000-2021)**: same-day fill 62-65%; the long-side system had 73.6% win rate, max DD -$3,400 per contract, avg trade ~$67-73 after rules. Student thesis (evidence 2) but fully specified and directly in our data format.
4. **FOMC-day post-announcement reversal (14:00-16:00 ET)**: buy if the 24h pre-FOMC return is negative, sell if positive; 180 announcements 1997-2020; Sharpe ~2.5x the pre-FOMC drift. Eight days a year, day-only, fits the drawdown rule; too infrequent to be the core of an eval.
5. **Gold intraday "hat" seasonality (Copenhagen BS thesis, 5-min gold 2001-2018)**: gold systematically depreciates 02:00-11:00 ET (London/NY morning, through both fixes) and appreciates 11:00 ET-02:00 ET. Short-only 02:00-11:00 averaged +10%/yr gross, +13.5%/yr in 2013-2018; Fixing-window shorts (05:05-05:35, 09:35-10:05) +7.6%/yr. Needs re-validation post-2019 (gold bull market); evidence 2-3.

**What the literature says is dead or not day-tradeable:**
- Classic Gao et al. first-half-hour -> last-half-hour sign rule: Sharpe 1.08 in 1993-2013 but **negative** out of sample (QuantConnect 2015-2020 Sharpe -0.63; Marwood 2010-2018 Sharpe -2.7). Use the rest-of-day signal instead.
- Pre-FOMC drift: 49 bp/24h 1994-2011 -> 9 bp 2016-2019 (Kurov, Wolfe, Gilbert 2021); needs an overnight hold anyway.
- End-of-day *reversal* (Soebhag, Baltussen, Da 2024) is cross-sectional across single stocks; at the index level the last 30 minutes show *momentum*, not reversal.
- VIX term-structure slope predicts variance assets (Johnson 2017), not ES direction; usable only as a regime filter.
- Short-term reversal in futures (Wang 2003 / Quantpedia) is weekly and needs volume + open interest.
- Trend + carry (Koijen et al. 2018) is multi-day; use only as a daily directional filter.
- NQ/ES lead-lag at 1-minute: no credible published exploitable lead; futures lead cash by 0-5 min but NQ-vs-ES at 1-min is anecdotal.
- Payday (16th), Turnaround Tuesday, Monday effect: tiny, inconsistent across subperiods, and all documented close-to-close (overnight exposure).

A prop-firm structural note (Hall 2026 working paper): under EOD-trailing rules, break-even is roughly a 40.5-41.5% win rate at 1:1.5 R:R net of costs; pass rates are "manufacturable by sizing alone" — so the eval target should be hit by a strategy whose *funded* economics are positive, not by sizing up a coin flip.

---

## 1. Rest-of-day -> last-30-minute market intraday momentum (futures)

**Origin.** Baltussen, Da, Lammers, Martens, "Hedging Demand and Market Intraday Momentum", *Journal of Financial Economics* 142 (2021) 377-403. Robeco / Notre Dame / Erasmus. Extends Gao-Han-Li-Zhou (JFE 2018) from SPY to 60+ futures 1974-2020 and identifies gamma hedging (option market makers, leveraged ETFs) as the mechanism.

**Instruments in the paper.** ES, NQ, YM, S&P 400, global equity index futures (9:30-16:00 ET for US equity futures); GC COMEX gold with pit hours 8:20-13:30 ET; bonds; currencies.

**Rules (objective).**
- Define rROD = return from prior day's close (16:00 ET) to 15:30 ET today (overnight + first 5.5h RTH). Define rONFH = prior close to 10:00 ET.
- Strategy eta(rROD): at 15:30 ET go long if rROD > 0, short if rROD < 0. Flat at 16:00 ET. One trade per day.
- Strategy eta(rONFH, rROD): same, but trade only when sign(rONFH) == sign(rROD); otherwise flat.
- For gold under the paper's pit definition: "last 30 min" = 13:00-13:30 ET.

**Evidence (gross, 1/N by asset class, Dec-1974 to May-2020; Table 6).**
| Strategy | Equity idx ann.ret | SD | Sharpe | Success | Commodity ann.ret | Sharpe | Success |
|---|---|---|---|---|---|---|---|
| eta(rONFH) | 4.21% | 3.95% | 1.07 | 55% | 2.48% | 0.82 | 54% |
| eta(rONFH, rROD) | 5.47% | 3.42% | 1.60 | 61% | 3.29% | 1.29 | 56% |
| eta(rROD) | 6.86% | 3.96% | 1.73 | 55% | 4.34% | 1.42 | 56% |
| Always long last 30m | 0.44% | 4.20% | 0.11 | 53% | -0.68% | -0.19 | 51% |

Subsample regressions (Table 5): equity beta_ROD = 5.96 (t 4.80) in 1974-1999 and 3.98 (t 6.65) in 2000-2020; commodities 1.59 (t 3.92) and 1.04 (t 2.86). The effect **reverts over the next days** and is strongest in the last four months of the sample (Feb-May 2020). Authors state ES exploitation "yields a positive net Sharpe ratio when we assume transaction cost equal to a tick". Earlier SPY evidence: Gao et al. 2018, 1993-2013, sign-of-first-half-hour strategy 6.67%/yr, SD 6.19%, Sharpe 1.08, success 54.4%; after TAQ spread costs 4.46%/yr (post-2001) and 6.52% vs 7.96% (post-2005); profits 4x larger on FOMC-minutes days (20.04%/yr annualized on those days), stronger on high-vol, high-volume and recession days.

**Negative out-of-sample for the *first-half-hour* variant**: QuantConnect implementation (SPY/IWM/IYR, 1/2015-8/2020) Sharpe -0.63 vs benchmark 0.58, but Sharpe +1.45 during 2/19-3/23/2020; Marwood (stocksoftresearch) SPY 2010-2018 "price at 10:00 > prior close -> buy 15:30, sell close" net -1.37%/yr, win 49.7%. Lesson: use rROD (includes the whole day) and consider the sign-agreement filter.

**Prop-fit.** Excellent structurally: one 30-minute trade, flat by close, 55-61% win rate, low per-trade variance; avg edge ~2.7 bp/day on notional (~$90 gross/day on 1 ES at 6,800), daily SD ~25 bp (~$850 on 1 ES). To hit $3,000 in an eval you need ~4 ES equivalent for 8-10 weeks or to combine with a second strategy; the 50% consistency rule is naturally satisfied. Cost sensitivity is the main risk (1 tick RT on MES = $1.25 + commissions vs ~$9 expected gross/day/MES). Reversal next day is irrelevant for day-only.

**Evidence quality: 5** (peer-reviewed JFE, 60+ markets, 46 years, mechanism identified; independent SPY confirmations; but the 2020s-only evidence is thin and OOS replications of the weaker first-half-hour variant are negative).

**Data requirements.** 1-min OHLC only. Optional conditioning on net gamma exposure (needs options data; not available) and VIX (available daily).

**Sources.** JFE 2021 paper (academicweb.nd.edu/~zda/intramom.pdf); Gao, Han, Li, Zhou, "Market Intraday Momentum", JFE 2018 (SSRN 2440866); alphaarchitect.com/2014/08/attention-prop-traders...; quantconnect.com/research/15348/intraday-etf-momentum; stocksoftresearch.com/the-truth-about-intraday-momentum.

---

## 2. Noise-area intraday momentum ("Beat the Market")

**Origin.** Zarattini, Aziz, Barbon, "Beat the Market: An Effective Intraday Momentum Strategy for S&P500 ETF (SPY)", SSRN 4824172 (May 2024), Swiss Finance Institute WP 24-97; 4th place Quantpedia Awards 2025. Independent replication: github.com/codecat-ops/zarattini-2024-momentum-spy (SPY via Alpaca IEX; ES via IB/CME, 9 quarterly contracts May-2024 to Jul-2026). Parameter study: Maroy, SSRN 5095349.

**Rules (exact).**
1. For each minute-of-day HH:MM compute the average absolute move from the open over the last 14 trading days: sigma_HH:MM = mean_{i=1..14} |Close_{t-i,HH:MM} / Open_{t-i,9:30} - 1|.
2. Upper boundary = max(Open_t, Close_{t-1}) x (1 + sigma_HH:MM); Lower boundary = min(Open_t, Close_{t-1}) x (1 - sigma_HH:MM). (Gap-anchored: after a gap down the upper band is lifted by the gap size, etc.)
3. Check only on the half-hour marks (10:00, 10:30, ..., 15:30 ET). If price is above the upper band -> long; below the lower band -> short. First possible entry 10:00 ET.
4. Trailing stop for longs = max(upper band, session VWAP); for shorts = min(lower band, VWAP). Stops are evaluated only at the half-hour checks in the paper (replication: continuous). Reverse if the opposite band is breached.
5. Position size: shares = AUM x min(4, 2% / sigma_SPY,14d) / Open; i.e., 2% daily vol target, max 4x leverage.
6. Flat at 16:00 ET. Commission $0.0035/share, slippage $0.001/share assumed.

**Evidence.** SPY, May-2007 to Apr-2024 (paper): base (opposite-band stop) IRR 6.2%, vol 10.9%, Sharpe 0.61, hit 54%, MDD 21%; with band+VWAP stop IRR 9.7%, vol 7.7%, Sharpe 1.24, hit 43%, MDD 12%; with vol targeting total 1,985%, IRR 19.6%, vol 14.3%, Sharpe 1.33, hit 43%, MDD 25%, alpha 19.6%, beta -0.07. Years: 2016 -12.8%, 2017 -6.9%, 2018 +61.1%, 2020 +26.8%, 2021 +34.8%, 2022 +24.4%, 2023 +37.2%, Jan-Apr 2024 +12.9%. Avg PnL 12 bp/day (t 5.34); Wednesday best (18 bp, Sharpe 2.4), Monday/Tuesday weakest (9 bp). Sharpe rises with VIX at the open: ~1.5 overall, ~3.5 when VIX > 40.
Replication (codecat-ops): SPY 2020-2026 Sharpe 1.11, +16.7%/yr alpha (t 2.85), win 41%, payoff 1.69; 2022 +25.8% vs SPY -19.5%; **2025-2026 Sharpe ~0 / negative on both SPY and ES**; ES: +2 bp/trade, win 36%, payoff 2.1, SPY-ES return correlation 0.97. Walk-forward parameter re-selection (27 variants) lowered Sharpe from 0.92 to 0.57 — "parameter optimization does not rescue the strategy".

**Prop-fit.** Day-only, codeable from 1-min OHLC (VWAP needs volume -> approximate with typical-price mean or use band-only stop, which the paper shows is worse: Sharpe 0.61 vs 1.24). Win rate ~40% with payoff ~2 gives lumpy equity: a few big trend days make the money, which fights the 50% consistency rule in a short eval and the EOD trailing DD on whipsaw days (worst day -4.8% of notional with VWAP stop, -10.3% without). Best used with a VIX gate (trade only when VIX open > ~18-20) and MES sizing so a bad day is < $600.

**Evidence quality: 4** (published rules, long sample, independent replication incl. ES; but degradation in 2025-26 confirmed by the replicator).

**Data requirements.** 1-min OHLC; VWAP approximated without volume (flag).

**Sources.** ssrn.com/abstract=4824172; github.com/codecat-ops/zarattini-2024-momentum-spy; papers.ssrn.com/sol3/papers.cfm?abstract_id=5095349; quantpedia.com/quantpedia-awards-2025-winners-announcement.

---

## 3. 5-minute Opening Range Breakout (Zarattini-Aziz)

**Origin.** Zarattini & Aziz, "Can Day Trading Really Be Profitable?", SSRN 4416622 (Apr 2023), QQQ/TQQQ 2016-2023; Zarattini, Barbon, Aziz, "A Profitable Day Trading Strategy for the U.S. Equity Market", SSRN 4729284 (2024), 7,000 stocks 2016-2023.

**Rules (as published for QQQ).** Opening range = first 5-minute bar (9:30-9:35 ET). If bar is up, buy at 9:35 at the open of the second bar; if down, short. Stop = low (high) of the first 5-min bar; if the range is < 0.1x 14-day ATR the stop is placed at 0.1x ATR instead (paper's floor). Profit target = 10R; otherwise exit at 16:00 ET. Risk 1% of equity per trade; max leverage 4x. No trade if first bar is a doji.

**Evidence.** QQQ 2016-2023: annualized alpha 33% net of commissions; TQQQ version +1,484% vs +169% buy-and-hold. Stocks-in-play version: top-20 portfolio +1,600%, Sharpe 2.81, alpha 36%. Day-of-week: Mondays most profitable. Independent: no published OOS on ES/NQ with the exact rules; retail reports (tradethatswing "ORB up 400% this year" on NQ) are anecdotal. Hit ratio in the paper is low (~25-30%) with large payoff — equity curve is step-like.

**Prop-fit.** Day-only, 1-min OHLC sufficient. Low win rate + 10R target = long losing streaks and a few huge days; this is the profile most likely to **violate the 50% consistency rule** at the moment of passing and to produce clustered losing days against the $2,000 trailing DD. Workable only with a hard daily loss cap and a modest target (e.g., 2-3R) which the authors say reduces alpha.

**Evidence quality: 3** (two SSRN papers by the same group, no peer review, no independent OOS on futures; parameter choices partially in-sample).

**Data requirements.** 1-min OHLC (ATR from daily). Volume not needed.

**Sources.** papers.ssrn.com/abstract=4416622; concretumgroup.com/can-day-trading-really-be-profitable/; cxoadvisory.com/technical-trading/day-trading-with-an-opening-range-breakout-strategy.

---

## 4. ES overnight-gap fill (bidirectional)

**Origin.** M. Trequattrini, "Trading at the opening bell: Gap Filling strategy on the E-mini S&P 500", Nova SBE master's work project (Jan 2022), supervised by N. Hirschey; TradeStation 1-minute ES cash-session data 1/3/2000-10/27/2021.

**Statistics.** Gap up occurs 52.6% of days, gap down 45.8%; same-day fill 62.5% (gap up) and 65.3% (gap down); fill probability falls monotonically with gap size in points; every calendar month > 60% fill except Sep (58.8%) and Nov (57.5%); Mondays and Fridays worst.

**Rules (final long side).**
- Setup A (prior day up-close): trade only gaps down where Open < prior Close and Open > prior Low. Setup B (prior day down-close): Open < prior Close suffices.
- Filter: 1-min price > 5-day SMA of daily closes. No trading on Monday or Friday. Gap size < 0.2 x (2-day high-low range).
- Entry: buy limit at Open - 2 points (parameter "enter level = -2"); Stop (limit-based): Open - 0.5 x (5-day high-low range); Target: prior day's high; monetary stop $500 / monetary target $250 per contract; time exit at session end.
- Short side mirrored (enter +2 pts above open, stop 0.5 x range, $650/$650).

**Evidence (1 ES contract, 2000-2021, in-sample + OOS "comb" validation).** Long: Sharpe 1.05 on $50k, Calmar 3.12, avg trade $73, win 73.6%. Short: Sharpe 1.01, Calmar 1.67, PF 1.5, avg trade $74, max open DD -$3,550. Combined: Sharpe 2.0 on $50k, Calmar 2.47, avg trade $67.5, max DD -$3,400; profitable in 2000, 2001, 2008, 2020; August the only negative month on average. OOS percentiles beat IS 81.8% of the time (short). No results reported after Oct-2021.

**Prop-fit.** Very good shape for Lucid: high win rate, small targets, max DD per contract well inside $2,000 historically, flat by close. Weakness: avg trade ~$70 means ~45 winning trades to hit $3,000 at 1 contract; use 2-3 ES or 20-30 MES. Target/stop asymmetry ($250 target / $500 stop) is a classic high-win-rate shape that can produce a $1,000+ day on 2 contracts; keep daily loss cap <= $600.

**Evidence quality: 2** (single student thesis, parameters optimized in-sample with a validation scheme, no peer review; but the underlying fill statistics agree with other sources: 84% fill for 0.25-0.5% gaps, TradingView ES/NQ 2014-2024 stats).

**Data requirements.** 1-min OHLC only. Define "open" as 9:30 ET RTH open and "prior close" as 16:00 ET (or 16:15 settle) — the thesis used the cash session.

**Sources.** run.unl.pt/bitstream/10362/145336/1/individualcommon.pdf; nexusfi.com/a/concepts/fill-the-gap; tradingview.com/script/32pGGSWx-Gap-Fill-Probability-Statistics-ES-NQ.

---

## 5. Overnight drift and the opening reversal (time-of-day return structure)

**Origin.** Boyarchenko, Larsen, Whelan, "The Overnight Drift", NY Fed Staff Report 917 (2020) and Liberty Street Economics (May 2021); S&P 500 futures 1998-2019. Related: Lou, Polk, Skouras, "A Tug of War: Overnight vs Intraday Expected Returns", JFE 2019.

**Findings (annualized, ES).** Full overnight 16:15-9:30: +2.6% of a 4.3% close-to-close; 02:00-03:00 ET (European open) +3.6% alone; **9:30-12:00 ET negative** (~-3.9% annualized around the open), 12:00-15:00 flat, 15:00-16:15 positive. Conditional: after bottom-tercile end-of-day order imbalance (big sell-off into the close), overnight Asian-hours +7.6% and European-hours +12.4% annualized; after top-tercile imbalance, overnight returns are negative. Mechanism: dealer inventory/liquidity provision at the close.

**Codeable day-only rules (standard interpretation; the paper does not trade them).**
- Morning fade: on days with an up-gap > 0.3% (proxy for positive overnight imbalance), short at 9:31 ET, cover at 12:00 ET or on a stop of 0.5 x 14-day ATR; mirror for down-gaps only if yesterday's 15:00-16:00 return was strongly negative (reversal is asymmetric).
- Afternoon long bias: unconditional long 15:00-16:00 has essentially zero edge in Baltussen's data (Always-Long last 30 min = 0.44%/yr); use only with the rROD sign (Strategy 1).

**Prop-fit.** The useful part is as a prior: do not carry long momentum through 9:30-12:00 blindly; the overnight premium itself is **not capturable** under the no-overnight rule.

**Evidence quality: 4** for the time-of-day return pattern (peer-reviewed, 20+ years of futures); **2** for the derived intraday fade rule (untested as published).

**Data requirements.** 1-min OHLC; imbalance conditioning needs MOC/order flow (not available) — proxy with the last-hour return.

**Sources.** libertystreeteconomics.newyorkfed.org/2021/05/the-overnight-drift-in-us-equity-returns; researchonline.lse.ac.uk/id/eprint/87481; quantreturns.substack.com/p/overnight-mean-reversion.

---

## 6. Overnight-return reversal across ES / NQ / GC (cross-sectional, open-to-close)

**Origin.** Lou-Polk-Skouras (JFE 2019) overnight-intraday "tug of war"; practitioner test "Overnight Mean-Reversion" (quantreturns.substack.com, 2007-2025) on US equity index futures (ES, YM, NQ, EMD, NKD, RTY) and sector ETFs; Quantpedia note that an overnight-intraday reversal portfolio earns ~5x a conventional short-term reversal.

**Rules.** At 9:30 ET rank instruments by close-to-open overnight return; buy the lowest, sell the highest (demeaned weights), hold open -> close (16:00 ET). With only three instruments (ES, NQ, GC) the standard interpretation is: long the index future with the weaker overnight return, short the stronger, equal dollar; GC optional as a third leg.

**Evidence.** Equity-futures CO-OC strategy had the "highest Sharpe" of the variants tested with strong t-stats (exact numbers behind paywall); sector-ETF versions Sharpe 4.4-7.1 (t 17-19) before costs, which are not achievable on 2-3 futures. No independent futures-only numbers found.

**Prop-fit.** Market-neutral intraday spread (NQ vs ES) has low variance and daily P&L consistency, but the per-day edge on a 1-lot spread is tens of dollars; margin on NQ/ES spread is low so micro sizing is feasible. Correlation ES/NQ ~0.85 daily means the spread is a tech-vs-broad bet.

**Evidence quality: 3** (peer-reviewed cross-sectional mechanism in stocks; futures evidence is practitioner, undisclosed numbers).

**Data requirements.** 1-min OHLC for both legs; execution depends on the opening print.

**Sources.** quantreturns.substack.com/p/overnight-mean-reversion; researchonline.lse.ac.uk/id/eprint/119010; quantpedia.com/overnight-sentiment-and-the-intraday-return-dynamics.

---

## 7. Pre-FOMC announcement drift

**Origin.** Lucca & Moench, "The Pre-FOMC Announcement Drift", NY Fed Staff Report 512 / *Journal of Finance* 2015. Disappearance: Kurov, Wolfe, Gilbert, "The disappearing pre-FOMC announcement drift", *Finance Research Letters* 2021 (ES futures to Dec-2019); follow-up Applied Economics 2024 "short-lived or long-lasting?".

**Rule.** Long ES from 14:00 ET the day before a scheduled FOMC statement to 14:00 ET on announcement day (statement at 14:00 ET since 2011; 14:15 before). 8 events/year.

**Evidence.** 1994-2011: +49 bp average (t > 4.5), ~80% of annual equity premium, Sharpe 1.14 (close-to-14:00 window Sharpe 1.43). Kurov et al.: Apr-2011 to Dec-2015 +44.5 bp (press-conference meetings) vs **Jan-2016 to Dec-2019 +9.2 bp**; difference significant at 1%; explained by lower VIX (17.7 -> 14.7). Quantpedia composite "FOMC meeting effect" (buy close before, sell close after; SPY 1993-2019): 2.30%/yr, MDD 7.2%.

**Prop-fit.** Requires an overnight hold -> **not allowed**. Day-only variant (9:30-13:59 ET on FOMC day) has no published evidence and captures only part of the window.

**Evidence quality: 4** for the historical effect, **2** that it still exists after 2015.

**Sources.** newyorkfed.org staff report 512; pmc.ncbi.nlm.nih.gov/articles/PMC7525326; tandfonline.com/doi/full/10.1080/00036846.2024.2322573; quantpedia.com/quantpedias-composite-seasonalcalendar-strategy-case-study.

---

## 8. Post-FOMC intraday reversal (14:00-16:00 ET)

**Origin.** Insper "Essays in Financial Economics" (PhD, c. 2021-22; repositorio.insper.edu.br/handle/11224/7532), ES 1997-2020, 180 scheduled announcements; related: Boguth, Gregoire, Martineau (noise and reversal after FOMC), Quantpedia "Are FOMC announcements really informative?".

**Rule.** Compute the 24-hour pre-announcement return (14:00 ET prior day -> 13:59 ET). At 14:00 ET on FOMC day: **buy ES if the pre-FOMC return is negative, short if positive**; exit at 16:00 ET close.

**Evidence.** Negative relation between pre- and post-announcement returns "independent of uncertainty level and sample period"; strategy Sharpe ~2.5x that of the Lucca-Moench drift strategy over 1997-2020 (drift Sharpe ~1.1 -> reversal ~2.5-2.8, computed on event days). Boguth et al.: top-quintile post-announcement movers (+2%) fade to +1.5% within 30 days (multi-day, not intraday).

**Prop-fit.** Day-only, codeable, eight trades a year; the 14:00-14:05 move can be 1% on NQ, so use a wide stop (1x 14-day ATR) or enter at 14:05 after the initial print. A useful add-on, not an eval engine.

**Evidence quality: 3** (thesis + Quantpedia summary, no peer review, no post-2020 OOS).

**Sources.** repositorio.insper.edu.br/handle/11224/7532; quantpedia.com/are-fomc-announcements-really-informative; cxoadvisory.com/calendar-effects/stock-market-return-reversal-after-fomc-announcements.

---

## 9. End-of-day reversal (and why it does not apply to the index)

**Origin.** Soebhag, Baltussen, Da, "End-of-Day Reversal" (SSRN, Nov 2024), 2nd place Quantpedia Awards 2025; all US stocks, minute data.

**Rule.** At 15:30 ET sort stocks by rest-of-day return (prior close -> 15:00); long bottom decile, short top decile; hold 15:30-16:00 ET. Effect absent earlier in the day; attributed to retail contrarian buying into the close.

**Index-level implication.** The authors note that at the index level Baltussen found a *positive* end-of-day trend (Strategy 1). So for ES/NQ/GC the last-30-minute rule is momentum, not reversal. Do not fade the close on the index.

**Evidence quality: 4** (strong cross-sectional evidence), **0 relevance** for single-instrument futures.

**Sources.** eur.nl/en/ese/news/end-day-reversal-pattern-second-place-quantpedia-awards-2025; www3.nd.edu/~zda/EOD.pdf.

---

## 10. VIX-level regime gating (momentum vs mean-reversion)

**Origin.** Multiple: Gao et al. 2018 (intraday momentum stronger on high-vol days); Zarattini et al. 2024 (Sharpe by VIX at open: ~1.5 baseline, ~3.5 when VIX > 40); Rosa (cited therein); practitioner RSI-with-VIX-regime test (algotr.substack, ES/NQ/RTY).

**Codeable rules (standard interpretation).**
- Compute VIX open (daily, Yahoo) and its 100-day range. Regime 4 (top quartile of the 100-day range) and VIX > 20 absolute: run intraday momentum (Strategies 1 and 2) at full size. VIX < 15: run momentum at half size or skip; run gap-fill / mean-reversion.
- Practitioner RSI(3) mean-reversion on ES (Close > 190-SMA, RSI(3) < 20 entry; exit RSI(3) > 80 or 39 bars or 1,100-tick stop) improved Return/DD by ~34% when regime 4 was excluded. (Timeframe unspecified; bar-based exits imply multi-session holds -> adapt to intraday bars with a 16:00 flat.)

**Evidence.** Zarattini's VIX bar chart and Gao's vol-tercile regressions are in-sample conditioning, not OOS tests; the codecat replication found "no relation" between daily PnL and same-day VIX level in 2020-2026 (their Q&A). The 2025-26 Sharpe collapse coincided with a low, grinding VIX.

**Prop-fit.** Pure filter; costs nothing; likely the single most important switch for passing in a particular 2-3 month window.

**Evidence quality: 3**.

**Data requirements.** Daily VIX (available). VIX term structure (VIX3M, VIX9D) not in the data set -> flag.

**Sources.** ssrn.com/abstract=4824172 (Sec. 4.3); gao et al. Table 5; algotr.substack.com/p/stop-leaving-money-on-the-table-a.

---

## 11. VIX term-structure signals (VIX/VIX3M, futures basis)

**Origin.** T. Johnson, "Risk Premia and the VIX Term Structure", JFQA 2017 (1996-2013): slope predicts variance-asset returns (VIX futures, straddles, variance swaps) — low slope -> high next-day variance returns, spread 0.29-1.81% across 18 asset/maturity combos; slope also predicts next-quarter S&P returns with adj. R2 5.2%, but Johnson and CXO stress the VIX level itself has little directional power for SPX. Practitioner: VIX/VIX3M > 1 (backwardation) on ~8% of days since 2010; flips back to contango marked the April-2020 bottom.

**Codeable rule.** Daily: if VIX/VIX3M > 1.0 (backwardation) treat as stress regime -> allow shorts / mean-reversion longs only on 2-sigma dips; if < 0.9 (steep contango) -> trend-friendly, run momentum. Needs VIX3M (Yahoo ^VIX3M available since 2007; VIX futures basis not in our data).

**Evidence quality: 3** for variance assets, **2** for ES direction. Multi-day horizon; use as filter only.

**Sources.** cxoadvisory.com/volatility-effects/vix-term-structure-slope-and-variance-asset-future-returns; bauer.uh.edu Johnson_020712.pdf; tradingview VIX/VIX3M notes.

---

## 12. Turn-of-the-month (ToM)

**Origin.** Xu & McConnell, "Equity Returns at the Turn of the Month", FAJ 2008 (1926-2005); Quantpedia "Turn of the Month in Equity Indexes"; "Calendar Anomalies in Stock Index Futures" (ToM in S&P futures is "the only calendar effect that is statistically and economically significant and persistent"); ETF Trends analysis 1980-Q3 2024.

**Rule.** Long from the close of the last trading day of the month (t = -1) to the close of the 3rd trading day (t = +3); Quantpedia composite variant: last 4 + first 3 days.

**Evidence.** Quantpedia (SPY-equivalent 1926-2005): 7.2%/yr, Sharpe 1.04, vol 6.9%, MDD -20.8%. Composite case study (SPY 1993-2019): 3.01%/yr, MDD 12%. 1980-2024: holding only ToM days gives annual return just 0.89% below holding all other days with MDD 20%.

**Prop-fit.** Multi-day with overnight holds -> not allowed. Day-only version (long 9:30-16:00 on days -1..+3) has no published numbers; Boyarchenko's finding that intraday returns are weak suggests most ToM return is overnight. Use at most as a long-bias filter for Strategies 1-2 on those four days.

**Evidence quality: 4** (multi-day), **1-2** (intraday-only).

**Sources.** quantpedia.com/strategies/turn-of-the-month-in-equity-indexes; etftrends.com/etf-strategist-channel/turn-month-effect; fedinprint.org/item/fedawp/13394.

---

## 13. Payday anomaly (16th of month)

**Origin.** Ma & Pratt, "Payday Anomaly", SSRN 3257064; Quantpedia strategy page (1980-2010).

**Rule.** Long S&P 500 for the 16th calendar/trading day of each month (buy close of 15th, sell close of 16th).

**Evidence.** Quantpedia: Sharpe 0.60, vol 4.3%, MDD -12%; the 16th is the 3rd-best day after the 1st and 2nd. Composite case study 1993-2019: 2.08%/yr, MDD 8.6%. Authors note weakening as payrolls move to bi-weekly.

**Prop-fit.** Close-to-close, 12 days a year, tiny edge -> not usable; at most a long-bias flag.

**Evidence quality: 2**.

**Sources.** quantpedia.com/strategies/payday-anomaly; ssrn.com/abstract=3257064.

---

## 14. Turnaround Tuesday / Monday reversal

**Origin.** Quantified Strategies (Substack, SPY, "decades" of data); CXO Advisory day-of-week tests; press statistics (S&P since 1928).

**Rules (standard).** (a) If Thursday, Friday and Monday all closed down, buy Monday close, sell Tuesday close (582 cases since 1928, avg +0.20%; +0.63% when each day fell > 1%). (b) If Monday close < Monday open (or < Friday close), buy Monday close, sell Tuesday close: 212 SPY trades, avg +0.30%, win 56%, CAGR 1.8%, exposure 2.5%; with IBS filter avg +0.33%, win 57%; with extended exit CAGR 6.5-7%, win 60-69%. Day-only variant: buy Tuesday 9:30 ET open, sell 16:00 ET — untested.

**Evidence.** CXO: Monday-up -> Tuesday -0.03%, Monday-down -> Tuesday +0.18% over full sample, but "inconsistencies across subperiods undermine belief in a reliable effect". Monday effect in S&P reversed/weakened post-1987; persists more in Nasdaq/Russell.

**Prop-fit.** Overnight hold in the canonical version; ~50 trades/yr; small edge. Low priority.

**Evidence quality: 2**.

**Sources.** quantifiedstrategies.substack.com/p/turnaround-tuesday-strategy-backtest; cxoadvisory.com/calendar-effects/any-recent-day-of-the-week-anomalies; business.purdue.edu/faculty/mcconnell/publications/Day-of-the-Week-Effects-in-Financial-Futures.pdf.

---

## 15. Witching-day intraday short

**Origin.** Caporale & Plastun, "Witching Days and Abnormal Profits in the US Stock Market", CESifo WP 9360 (Oct 2021); DJIA, S&P 500, Nasdaq; daily data; multiple parametric and non-parametric tests plus a trading simulation.

**Rule.** On quadruple-witching days (3rd Friday of Mar/Jun/Sep/Dec) sell at the 9:30 ET open, cover at the 16:00 ET close. (Note: also the ES/NQ quarterly roll/expiry day; trade the next contract.)

**Evidence.** S&P 500: negative open-to-close return on witching day d(0) in 57% of cases, statistically significant; DJIA 55% and the simulated strategy beats random trading. Pre-/post-witching days and weeks: no robust anomaly. No transaction costs; 4 trades/yr.

**Prop-fit.** Day-only, trivial to code; too rare to matter for an eval but harmless as an overlay; expiry-day liquidity in the front contract is thin after 9:30 — use the new front month.

**Evidence quality: 3** (working paper, three indices, several tests; small n).

**Sources.** CESifo WP 9360 (witching.txt in scratchpad); Stoll & Whaley 1987 "triple witching hour".

---

## 16. Gold intraday "hat" seasonality and fixing-window shorts

**Origin.** Donati & co-author, "Gold Price Dynamics Around the Clock", Copenhagen Business School MSc thesis (May 2019): 18 years (2001-2018) of 5-minute gold prices, ~24h/day; Batten, Lucey, McGroarty, Peat, Urquhart (2017) 15 years of 5-min gold: strong intraday periodicity tied to market opens/closes; Caminschi & Heaney, JFM 2014: London PM fix (10:00 ET) — ~10 bp available in the 4 minutes after the fix starts, +4 bp in the 2 minutes before it ends, trades in the first minutes predict the fix direction; nothing after publication.

**Pattern.** "Hat-shaped" intraday seasonality: gold appreciates during Asian/eastern hours and depreciates during western hours; sharp dips in the half hours before the London AM (05:30 ET) and PM (10:00 ET) fixes, especially in the 2004-2013 "manipulation" years.

**Rules (thesis, times in ET).**
- Short strategy: short gold 02:00-11:00 ET every day, flat otherwise.
- Long strategy: long 11:00 ET-02:00 ET next day (overnight -> not allowed).
- Fixing strategy: short 05:05-05:35 ET and 09:35-10:05 ET.

**Evidence (gross, log returns, no costs).** Short: 2001-2006 +9.5%/yr, 2007-2012 +7.1%, 2013-2018 +13.5%, full +10.0%/yr (2013 +45%, 2015 +30.6%, 2017 -3.7%, 2018 -1.1%). Fixing: full +7.6%/yr, concentrated in 2008-2011 (+14 to +30%); the authors expect it "not to be particularly profitable from now on". Combo (long+short) +28.6%/yr, yearly Sharpe up to 1.61. With spreads charged at 100% the early-years results are heavily negative (5-min round trips); the Short strategy is two trades/day so spread cost matters much less than for Fixing.

**Prop-fit.** Short 02:00-11:00 ET on MGC is one trade/day, flat before the NY afternoon; micro gold (MGC = $10/pt) keeps daily variance small. Big caveat: 2019-2026 is a strong gold bull market (gold ~$1,300 -> $4,000+), so an unconditional daily short likely underperforms; must be re-tested on our 2010-2026 GC 1-min data and possibly conditioned on the overnight (Asia) move (fade only after an overnight rally).

**Evidence quality: 3** (two academic papers on periodicity + a thesis with strategy numbers; no post-2018 OOS; mechanism partly tied to a since-reformed fixing process).

**Data requirements.** 1-min GC OHLC covering 02:00-11:00 ET (Globex) — available.

**Sources.** research.cbs.dk/en/studentProjects/gold-price-dynamics-around-the-clock; Caminschi & Heaney 2014 (uwa_gold.txt); reading-clone.eprints-hosting.org/79175/1/BattenLuceyMcGroartyPeatUrquhart2017.pdf.

---

## 17. Gold last-30-minute momentum (commodity leg of Strategy 1)

**Origin.** Baltussen et al. 2021 include COMEX GC with pit hours 8:20-13:30 ET.

**Rule.** rROD = prior 13:30 ET close -> 13:00 ET; at 13:00 ET go long if rROD > 0, short if < 0; flat 13:30 ET. Alternative using modern liquidity: define "day" as 08:20-13:30 ET anyway (the paper's definition) since the Globex 17:00 close is not a natural hedging deadline.

**Evidence.** Commodity 1/N portfolio: eta(rROD) 4.34%/yr, Sharpe 1.42, success 56%; 2000-2020 commodity beta_ROD 1.04 (t 2.86) — weaker than equities. Gold-specific coefficients are in the paper's appendix (not extracted); treat as positive but smaller.

**Prop-fit.** One 30-min trade/day on MGC, independent of ES; diversifies daily P&L.

**Evidence quality: 4** (same JFE paper; gold-specific numbers not pulled).

---

## 18. Trend-following + carry as a daily directional filter

**Origin.** Koijen, Moskowitz, Pedersen, Vrugt, "Carry", JFE 2018; QuantConnect "Combined carry and trend"; Advisor Perspectives 2026 note (gold/silver in contango = negative carry >98% of the time since 1989; trend + positive carry > trend alone).

**Rule (filter form).** Daily: trend = sign(close - 100-day SMA) or 12-month return; carry for GC = (front - next)/front annualized (needs two contracts — not in our data; use the sign assumption "gold carry is negative"). For ES, carry ~ dividend yield - r (negative when rates > dividends). Take intraday momentum entries (Strategies 1, 2) only in the trend direction; take gap-fill / mean-reversion entries against the trend only with half size.

**Evidence.** Multi-asset trend + carry portfolio Sharpe ~1.1 -> ~1.5 in the Beyond Passive analysis; positive trend + positive carry gives higher forward Sharpe than trend alone. No intraday evidence.

**Evidence quality: 5** for the multi-day premia, **2** as an intraday filter.

**Data requirements.** Daily futures (available); carry needs term structure (flag: approximate).

**Sources.** quantconnect.com/research/16001/combined-carry-and-trend; advisorperspectives.com/commentaries/2026/02/26/trend-follow-carry-lessons-bonds-gold-2022.

---

## 19. Short-term (weekly) reversal in futures

**Origin.** Wang, "Trading activity and price reversals in futures markets" (Quantpedia "Short Term Reversal with Futures"), 24 US futures 1983-2000; also Bianchi et al. weekly reversal in 24 US futures; European index futures 1993-2002 (29.6%/yr long-short).

**Rule.** Wednesday-to-Wednesday: long the lowest prior-week return contracts, short the highest, restricted to high-volume / low-open-interest contracts; weights proportional to return minus cross-sectional mean.

**Evidence.** 29.6%/yr, Sharpe 0.82, vol 31%, MDD -58.7% (1983-2000). No post-2015 OOS found.

**Prop-fit.** Weekly holding -> not allowed; needs volume and open interest -> flagged.

**Evidence quality: 3**.

**Sources.** quantpedia.com/strategies/short-term-reversal-with-futures; theideafarm.com/alternative-investment/short-term-reversal-in-equity-index-futures.

---

## 20. Nasdaq-100 vs S&P 500 intraday lead-lag

**Origin.** Hasbrouck (2003) "Intraday Price Formation in U.S. Equity Index Markets": E-mini ES and NQ have the highest information shares (they lead cash/ETFs by 0-5 minutes). Practitioner claims that NQ leads ES in volatile tape (bookmap, edgeful) are anecdotal.

**Rule (standard interpretation, untested).** On 1-min bars, if NQ's 5-min return exceeds ES's by > 2x the rolling ratio of their vols and ES has not moved, buy ES for the next 5-15 min (and vice versa). Equivalent to a short-horizon pairs/relative-momentum trade.

**Evidence.** No published exploitable NQ->ES lead at 1-min; lead-lag between highly liquid futures is sub-minute and arbitraged. Daily correlation ~0.85; NQ moves 1.5-2x ES in %.

**Prop-fit.** Not recommended; costs on 1-min signals dominate.

**Evidence quality: 1**.

**Sources.** researchgate.net/publication/4992659_Intraday_Price_Formation_in_US_Equity_Index_Markets; bookmap.com/blog/nq-vs-es-why-they-move-together-until-they-dont.

---

## 21. Gold-equity cross-asset signals

**Origin.** Huang & Kilic, "Gold, platinum, and expected stock returns", JFE 2019 (gold/platinum ratio predicts monthly returns); SentimenTrader S&P/gold ratio drawdown signals (ratio -25% in 3 months to a 3-year low -> double-digit 12-month gains except 2008).

**Rule.** Monthly/weekly only: long-bias ES when the S&P/gold ratio has just made a 3-year low after a 25% three-month drop. No intraday ES-GC rule with published evidence; intraday ES/GC correlation is unstable.

**Prop-fit.** Not usable intraday; keep as regime context.

**Evidence quality: 2** (one JFE paper for a different ratio; retail signal otherwise).

**Sources.** sentimentrader.com/blog/the-sp-500-has-crashed-when-priced-in-gold; capital.com S&P/gold ratio analysis.

---

## 22. Intraday seasonality of returns and volatility (structural facts)

**Findings.** S&P volatility is U-shaped (high 9:30-10:30, trough 12:00-13:30, rising after 15:00); S&P futures show a growing share of volatility outside RTH ("Intraday Periodic Volatility Curves", JASA 2024). Index returns: negative around the open through ~12:00, flat midday, positive into the close (Boyarchenko); VIX drifts -0.8%/day open-to-close, mostly in the first 30 and last few minutes. The 15:30-16:00 index return is momentum (Strategy 1), while single stocks reverse (Strategy 9). Zarattini's momentum PnL by weekday: Wed 18 bp > Fri 13 > Thu 12 > Mon/Tue 9.

**Use.** Size stops by minute-of-day sigma (exactly what the noise-area band does); avoid initiating mean-reversion in the first 30 minutes; schedule momentum entries at 10:00 and 15:30 ET.

**Evidence quality: 4** for the volatility shape, **3** for the return shape.

**Sources.** ideas.repec.org/a/taf/jnlasa/v119y2024i546p1181-1191.html; cxoadvisory.com/?p=29380; libertystreeteconomics (above).

---

## 23. Options-expiration week effect

**Origin.** Quantpedia composite (SPY 1993-2019): buy close of the Friday before the 2nd Saturday, sell close of the following Thursday (the week before monthly OpEx). 4.93%/yr, MDD 20.4%. Multi-day, overnight -> not allowed; include only as a long-bias flag for OpEx week.

**Evidence quality: 3**.

---

## 24. What the evidence says works in 2022-2026

- **Index intraday momentum into the close (rROD -> 15:30-16:00)** is the best-supported futures effect; the gamma-hedging mechanism (dealers short gamma, leveraged-ETF rebalancing) is structural and the 2000-2020 coefficients are at least as strong as 1974-1999. No one has published a 2022-2026 ES test of the exact JFE rule; the closest evidence is Zarattini's monthly table (2022 +24%, 2023 +37%, Jan-Apr 2024 +13% for the noise-area version) and the codecat ES replication (positive through 2024, ~zero in 2025-2026).
- **Trend-day capture (noise-area, ORB)** delivered 2022-2024 and failed in the 2025-26 grind; the honest reading is "high-VIX dependent". Gate it with VIX > ~18-20 or realized 14-day vol > its 1-year median.
- **Gap fill** statistics (60-65% same-day fill, 84% for 0.25-0.5% gaps) are reported through 2021 and by TradingView ES/NQ 2014-2024 stats; the thesis says profits were rising over its last five years (2017-2021). It is the natural low-VIX complement to momentum.
- **FOMC post-announcement reversal** has evidence to 2020 only; the 2022-2024 hiking cycle produced several violent 14:00-16:00 reversals, so a 2022-2026 test is worth running; eight days/year.
- **Calendar effects** (ToM, payday, Tuesday, OpEx week) are mostly overnight and weak post-2010; **witching-day shorts** are the only day-only calendar rule with a published trading simulation (57% negative days).
- **Gold**: the intraday depreciation during London/NY morning (02:00-11:00 ET) was robust 2001-2018 but is untested in the 2019-2026 bull market; the fixing-window effect is likely gone post-2015 fix reform.
- **Dead or non-day-tradeable**: first-half-hour-only momentum (negative OOS), pre-FOMC drift (overnight, faded), VIX-term-structure direction, weekly futures reversal (needs volume/OI), NQ/ES lead-lag, gold-equity ratios.

**Recommended backtest queue (ranked for Lucid fit):** 1) eta(rROD) and eta(rONFH, rROD) on ES/NQ at 15:30 ET, MES/MNQ sizing; 2) ES gap-fill long/short with the thesis parameters; 3) noise-area momentum with band-only stop (no VWAP) and VIX gate; 4) GC 13:00-13:30 ET momentum and GC 02:00-11:00 short conditioned on overnight rally; 5) FOMC 14:00-16:00 reversal and witching-day short as overlays; 6) ORB 5-min with capped target (2-3R) only if 1-3 fail the consistency simulation.

**Lucid-specific constraints to simulate for each:** daily loss cap <= $600 (30% of the $2,000 trailing DD), largest-day-profit <= 50% of cumulative at the pass moment (prefer 55-73% win-rate rules), and a 5-day >= $150 EOD profit count for payouts (favors one-trade-per-day rules with ~55% hit rate over 35-40% hit-rate trend captures).
