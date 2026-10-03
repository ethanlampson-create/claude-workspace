# Family: Trend-Following and Momentum (intraday + daily) on Index/Commodity Futures

Research sweep date: 2026-10-03. Target use: Lucid Trading 50K LucidFlex (eval target $3,000; $2,000 END-OF-DAY trailing drawdown; 50% consistency rule in eval; funded payout needs 5 days >= $150; day-trade only). Instruments we can backtest: 1-minute OHLC (no volume) for ES/MES, NQ/MNQ, GC/MGC, CL/MCL, Nov-2010 to Sep-2026. All times below are **ET**.

## Summary (read this first)

1. **The only strategies in this family with peer-reviewed, replicated, out-of-sample evidence on ES/NQ-like instruments are (a) the Zarattini-Barbon-Aziz "Noise Area" intraday momentum model and (b) the Gao-Han-Li-Zhou first-half-hour -> last-half-hour momentum effect.** Both are codeable from 1-minute OHLC (VWAP in (a) can be approximated with typical-price "VWAP" or replaced by the band-only stop; the paper reports both variants).
2. **Both have visibly decayed since 2025.** An independent replication of (a) on SPY and on ES (IB 1-min data, May-2024 to Jul-2026) reports Sharpe 1.1 full-sample but Sharpe ~0 on both instruments in 2025-2026. Gao et al.'s effect shrank ~75% in later samples and the QuantConnect 2015-2020 implementation had Sharpe -0.63. Treat them as regime-dependent (they pay in high-VIX periods: Sharpe 1.5 when VIX > ~20 and 3.5 when VIX > 40 in the SPY paper).
3. **Plain opening-range breakout (ORB) has no net edge after costs on index futures when run naively.** Two independent 2024-2026 tests (MQL5 replication on NQ/SPX/Dow/DAX/FTSE; a 516-session ES study Sept-2024 to 2026) show gross edge ~0.1R that equals round-trip cost, and all 12 ES configurations losing. ORB only shows positive out-of-sample results when **heavily filtered**: (i) daily 200-SMA direction filter + one-loss-per-day cap on MNQ (OOS Jan-2023 to Feb-2026: CAGR 15.7%, Sharpe 1.10, PF 1.32, max DD 12.8%, win rate 25%), (ii) ORB-size filter (skip when 5-min range > 0.55% of price) + 50%-of-range target + long-only (edgeful ES 6-month: 72% WR, PF 1.62), (iii) 30-min ORB with 5-min-close confirmation and wide-ORB (> 0.6x ATR) filter (continuation 70-77% on 12 years of ES/NQ).
4. **Statistical "trend day" structure is well documented on ES/NQ (2014-2026, ~3,000 days each)**: 30-min ORB continuation 64-71%, upside breaks ~9 points more reliable than downside, narrow Initial Balance (< 0.5x ATR) -> median IB extension 75% vs 22% for extreme IB; first 1-min/5-min close above the IB high during 10:30-11:00 raises the chance of a full 100%-IB extension from 19% to 45% (ES). These are **conditional probabilities, not P&L**, but they are exactly the filters a prop-fit day-trade system needs.
5. **Daily trend systems (Turtle/Donchian, MA crossovers, 12-month TSMOM, Supertrend, PSAR) are not day-trade compatible** and have decayed on US equity indices (SPY 40-in/20-out: 20-day forward return after breakout fell from +0.85% in the 1990s to +0.02% in 2020-2026). They remain useful only as **higher-timeframe bias filters** for intraday entries (e.g., trade ORB long only when close > 200-day SMA), and on gold (Supertrend H4 PF 3.2 in 2024-2026 on a one-way bull market; Donchian long gold 2000-2025 CAGR 6%, max DD 17%).
6. **Prop-fit verdict:** the most promising codeable candidates for a $2k EOD-trailing account are (ranked): Noise-Area momentum on MES/MNQ with micro sizing and a VIX/NR4 regime filter; filtered 15/30-min ORB on MNQ/MES (SMA-200 bias, one trade/day, 0.5-1.0x range target, hard $ stop); IB-breakout with C-period close confirmation and narrow-IB filter; last-half-hour momentum (small, consistent, 54% success, very low variance: good for the "5 days >= $150" payout requirement if sized at 2-4 MES); gap-and-go only on large gaps opening outside the prior day's range (fill rate 8%). Everything else in this family is either a filter, a daily-hold system, or unsupported by evidence.

---

## 1. Zarattini-Barbon-Aziz "Noise Area" Intraday Momentum (2024)

**Origin.** Carlo Zarattini, Andrea Barbon, Andrew Aziz, "Beat the Market: An Effective Intraday Momentum Strategy for S&P500 ETF (SPY)", Swiss Finance Institute Research Paper 24-97 / SSRN 4824172 (May 2024); 4th place, Quantpedia Awards 2025. Replicated on ES/NQ futures by Quantitativo (Jan 2025) and by codecat-ops (GitHub, SPY + ES, 2026).

**Exact rules (from the paper).**
- For each prior day t-i and each time-of-day HH:MM, compute move(t-i, HH:MM) = |Close(HH:MM) / Open(9:30) - 1|.
- sigma(t, HH:MM) = mean of move over the last **14 days** (paper); 90 days gave the highest Sharpe (1.50 vs 1.35) in robustness tests, 5-60 days all within 1.23-1.35.
- UpperBound(t,HH:MM) = max(Open(9:30), Close(t-1, 16:00)) x (1 + VM x sigma); LowerBound = min(Open, PrevClose) x (1 - VM x sigma); VM = 1 (1.5 slightly better).
- Decisions are taken **only at HH:00 and HH:30** (semi-hourly), from 10:00 to 15:30. If price > UpperBound: long; if < LowerBound: short. Opposite crossover closes and reverses.
- Trailing stop (also only checked semi-hourly): Long stop = max(UpperBound at that time, VWAP); Short stop = min(LowerBound, VWAP). VWAP computed from RTH data only. Base variant uses opposite band as stop.
- All positions closed at 16:00 (replications use 15:55-16:00).
- Sizing: notional = AUM x min(4, sigma_target / sigma_SPY) with sigma_target = 2% daily; sigma_SPY = 14-day daily return std (Quantitativo's "improved" ES/NQ variant: 3% target, 8x cap).
- Costs: $0.0035/share commission, $0.001/share slippage (measured live).

**Evidence.**
- SPY 2007-Mar 2024 (paper): base (opp-band stop, 100% notional) total 178%, IRR 6.2%, vol 10.9%, Sharpe 0.61, hit ratio 54%, MDD 21%. Band+VWAP stop: 380%, 9.7%, 7.7% vol, Sharpe 1.24, hit 43%, MDD 12%. Band+VWAP + dynamic sizing: **1,985%, 19.6% IRR, 14.3% vol, Sharpe 1.33, hit 43%, MDD 25%, alpha 19.6%, beta -0.07**. 7,668 trades, avg holding 1.8 h, 37% winning trades, +0.09% avg trade. Sharpe ~1.5 when VIX > 20ish, 3.5 when VIX > 40. Day-of-week: Wed (18 bps, t=3.4) best, Mon/Tue weakest (9 bps). Daily-pattern filter: trading only after an **NR4 day** gives 22 bps/day, t = 5.14, Sharpe 3.2; NR7 16 bps (t=3.07); after a "Trend" day -2 bps (not significant).
- Futures FAQ: same rules on 33 futures (21 commodities, 12 equity indices), Jan 2007-Sep 2024: only 2 negative; average Sharpe 0.60; diversified portfolio Sharpe 1.65.
- Quantitativo ES/NQ (Databento 1-min, 2010-2024, costs $0.85+$1.40/contract + 0.25 tick slippage): paper settings on ES: 8.1%/yr, Sharpe 0.91, MDD 24%, WR 36%, +2 bps/trade, payoff 2.09; 90-day/3%/8x on ES: 16.8%/yr, Sharpe 1.25, MDD 21%; NQ: **24.3%/yr, Sharpe 1.67, MDD 24%, WR 38%, +6 bps/trade, payoff 2.25**. Longs +6 bps (43% WR), shorts +3 bps (34% WR). Flat 2010-2017; most profit 2018+.
- codecat-ops replication (SPY Jul-2020 to Jul-2026 1-min IEX; ES May-2024 to Jul-2026 IB 1-min; frozen parameters): Sharpe 1.11, alpha +16.7%/yr (t=2.85), +2.6 bps/trade, 41% WR, payoff 1.69; ES vs SPY returns correlated 0.97; 2020-2024 Sharpe 1.4-2.0 per year, 2022 +25.8%; **2025-2026 Sharpe ~0 on both instruments.** Walk-forward re-optimisation hurt (0.57 vs 0.92).

**Evidence quality: 4** (peer-reviewed working paper + two independent replications with code; decay in 2025-26 documented).

**Data requirements.** 1-min OHLC suffices; VWAP needs volume. Without volume, use the band-only stop (Sharpe 0.61 variant) or a proxy VWAP from typical price (bias: equal-weighted). The paper shows the VWAP stop roughly doubles Sharpe, so losing it matters; test both.

**Prop fit.** Pros: day-trade only, objective, few decisions per day (max 12 semi-hourly checks), positive skew, negative beta, works on NQ best. Cons: 37-43% win rate and many small losing days -> can violate "5 x $150 days" slowly; 2% daily vol target on $50k = ~$1,000/day stdev, far too much for a $2k EOD trailing DD (size so that daily stdev ~$300-400: ~1-2 MNQ/2-4 MES). Semi-hourly stop checks mean intra-bar excursions can exceed the stop; for a $2k EOD DD the EOD-only rule helps (intraday excursion does not count) but still require a hard $ stop. 2025-26 decay is the main risk; condition on VIX > 18-20 or NR4 prior day.

**Sources.** SFI RP 24-97 PDF (alexandria.unisg.ch); concretumgroup.com/beat-the-market-...; quantitativo.com/p/intraday-momentum-for-es-and-nq; github.com/codecat-ops/zarattini-2024-momentum-spy; quantifiedstrategies.substack.com/p/systematic-intraday-trend-following.

## 2. Market Intraday Momentum: first half-hour predicts last half-hour (Gao, Han, Li, Zhou)

**Origin.** Lei Gao, Yufeng Han, Sophia Zhengzi Li, Guofu Zhou, "Market Intraday Momentum", Journal of Financial Economics 129(2), 2018 (SSRN 2440866, 2014). Extended globally (16 markets) by Reading/Nottingham authors; to crude oil (Wen, Gong, Ma, Xu, Economic Modelling 2020) and commodity ETFs (Finance Research Letters 2020).

**Rules.** r1 = Close(10:00)/Close(prev day 16:00) - 1 (first half-hour return measured from prior close, i.e., includes the overnight gap). r12 = return 15:00-15:30. r13 = return 15:30-16:00.
- Timing strategy eta(r1): at 15:30 go long if r1 > 0, short if r1 < 0; exit 16:00 (MOC).
- eta(r1, r12): trade only if sign(r1) = sign(r12); else flat.
- Regression: r13 = a + 6.94 x r1 (slope x100), R2 1.6% in-sample, OOS R2 1.4%; combined r1+r12 R2 2.6% (OOS 2.0%); first-half-hour-high-volatility days R2 3.3%; crisis sub-period (2007-2009) R2 4.1% / 6.9% combined.

**Evidence.** SPY 1993-2013: eta(r1) 6.67%/yr, std 6.19%, **Sharpe 1.08**, skew +0.90, success rate 54.37% (vs 50.42% always-long); eta(r1,r12) 4.39%/yr, Sharpe 0.98, success **77.05%** (fewer trading days). Results "similar" on S&P 500 futures (internet appendix). Stronger on high-vol, high-volume, recession, and macro-release days (FOMC/CPI/GDP). QuantConnect replication 2015-2020 (SPY/IWM/IYR): Sharpe -0.63 overall, 1.45 during Feb-Mar 2020 crash. Global study: significant in 12/16 markets; later evidence says strength weakened ~75% out-of-sample. Crude oil (USO 1-min): in-sample R2 0.73%, OOS 0.66%, 1.92% in crisis vs 0.34% non-crisis. Gold/silver ETFs: predictability exists but from different half-hours, not the first.

**Evidence quality: 5** for the effect's existence (JFE + multiple replications); **2-3** for its 2022-2026 tradability (documented decay; small per-trade edge).

**Data requirements.** 1-min OHLC only. ES futures RTH 9:30-16:00; for CL use 9:00-14:30 pit session (first half-hour 9:00-9:30, last 14:00-14:30); GC 8:20-13:30.

**Prop fit.** One 30-minute trade per day, flat at close, very low variance; the eta(r1,r12) variant trades ~40% of days with 77% success. Edge per trade is tiny (~2-3 bps = ~1.5 ES points): at 4 MES the average day is ~+$30, so it will not hit $150/day alone; usable as a low-risk "consistency filler" or as the afternoon leg of a system. Last-half-hour slippage on MES/MNQ is small. Rotate on only when VIX > 20 or on macro-release days where the effect doubles.

**Sources.** SSRN 2440866 / JFE 2018; QuantConnect "Intraday ETF Momentum"; Wen et al. SSRN 3553682; PMC7480318; centaur.reading.ac.uk/95566.

## 3. Zarattini-Aziz 5-minute ORB (QQQ/TQQQ) and its replications

**Origin.** Zarattini & Aziz, "Can Day Trading Really Be Profitable?", SSRN 4416622 (Apr 2023). Replicated by MQL5 blog (5 indices, 2015-2026), QuantConnect, Concretum Polygon tutorial, Wealth-Lab.

**Rules.** Opening range = first 5-min candle (9:30-9:35). If candle closes up, buy at 9:35 open; if down, sell short; doji (open ~= close) -> no trade. Stop = 10% of the 14-day daily ATR from entry (Concretum tutorial variant: stop at the opening-bar low/high); target = 10R (effectively hold to close); exit at 16:00 if neither hit. Risk 1% of equity per trade; leverage cap 4x. Commissions $0.0035/share.

**Evidence.** QQQ 2016-2023: annualized alpha 33% net of commissions; TQQQ 1,484% vs QQQ 169% buy-and-hold. Concretum tutorial TQQQ Jan-2016 to Feb-2025: 2,328% total, CAGR 41.9%, Sharpe 1.07, **MDD -37%**. MQL5 replication NQ/SPX/Dow/DAX/FTSE CFDs Jan-2015 to Jun-2026, ~2,900 sessions each: gross +0.048 to +0.131 R/trade, hit rate 20-23% (NQ gross +0.131 R, matching the paper); **net of 2.5-4.0 points spread+slippage: NQ +0.002 R, SPX -0.081 R, Dow -0.081 R, DAX -0.038 R, FTSE -0.079 R; 2021-2026 OOS degraded**. Author's conclusion: the first candle carries ~0.1R of information, equal to round-trip cost on a 25-point stop.

**Evidence quality: 3** (working paper + multiple replications, but net-of-cost replications on futures/CFDs show ~zero).

**Data requirements.** 1-min OHLC only.

**Prop fit.** Poor as published: 20-23% win rate, 10R targets, MDD 37% -> incompatible with $2k EOD DD and with the 50% consistency rule (profits concentrated in a few huge days). Keep only as a signal component (first-5-min direction) inside filtered ORB variants (Section 4).

**Sources.** papers.ssrn.com/abstract=4416622; mql5.com/en/blogs/post/776235; concretumgroup.com/backtesting-the-opening-range-breakout-orb-strategy-using-polygon-io; cxoadvisory.com/technical-trading/day-trading-with-an-opening-range-breakout-strategy.

## 4. Filtered ORB (5/15/30-min) on ES/NQ/MNQ: practitioner backtests and statistical base rates

**Origin.** Toby Crabel (1990) popularized ORB; modern quantified versions by edgeful, Trade That Swing, TradingStats (12 years ES/NQ), "Backtests, Not Signals" (MNQ with SMA-200 filter, OOS 2023-2026), and a null-result ES study (july-backtester PR #400).

**Rules (the variants with evidence).**
- *4a. edgeful ES 5-min ORB (6 months to Apr-2026, 1 ES):* OR = 9:30-9:35. Enter on break of OR high/low. Stop = opposite side of OR, capped at $700/trade. Target = 50% of OR size. Skip if OR > 0.55% of price. Tuesday longs disabled. 115 trades, **72.2% WR, PF 1.62, +$10,825 on $10k**; MDD not disclosed.
- *4b. Trade That Swing NQ 15-min ORB (Oct-2024 to Oct-2025, 1 NQ):* OR = 9:30-9:45. Entry: a 5-min candle **closes** outside OR; long only; one trade/day; no trade if first close is below the OR low. Stop = other side of OR capped at $1,000 (50 NQ pts). Target = 50% of OR. Skip if OR > 0.8% of price; avoid Mon/Thu (recent tweak). 114 trades, **74.6% WR, PF 2.51, +$43,310 on $10k, MDD $2,725, avg win $846, avg loss $987**; equity "pretty flat" in the 90 days to Jul-2026.
- *4c. Backtests-Not-Signals MNQ ORB with trend filter:* long on break of OR high only if price > SMA(200) (daily-equivalent lookback, optimized 150-300); short mirror if < SMA(200). Stop = opposite side of OR, capped at 150 ticks ($75 on MNQ). Take profit = R-multiple (optimized 1.4-4.2). Forced exit at next session open (note: not flat at close; must be converted to 15:55 exit for Lucid). Stop trading after one losing trade per session. 1 MNQ, $0.68/side. In-sample Feb-2020 to Dec-2022: CAGR 19.3%, Sharpe 1.37, MDD 10.9%, WR 30.4%, 451 trades, PF 1.43. **OOS Jan-2023 to Feb-2026: CAGR 15.7%, Sharpe 1.10, MDD 12.8%, WR 24.9%, 474 trades, PF 1.32**; exposure ~24% of time.
- *4d. Null result (zachisit/july-backtester):* ES, 516 sessions from Sep-2024, OR = 15 or 30 min, breakout entries 9:45-11:00, exits 11:00 or close, ~1 tick cost. All 12 configurations lost (-$4,590 to -$17,698 per contract); "buy at 9:45 and hold to close" beat all of them (+$2,285 to +$22,735); placebo (fade vs follow) both lose; breakeven cost 0.15-0.73 ticks; equal-weighted by year the average R was negative in 10 of 17 years.
- *4e. Base rates (TradingStats, ES/NQ Jan-2014 to Jan-2026, RTH):* median OR size ES 5/15/30-min = 5.5/8.5/11.0 pts (0.16/0.24/0.31x ATR); NQ 26.5/40.25/51.5. Both sides of a 5-min OR get broken on 74% of ES days (double break), 48% for 30-min. Continuation (close in break direction) 30-min OR: ES 64.6% wick / 68.4% 1-min close / **70.7% 5-min close** (up-first 75.0%, down-first 65.8%); NQ 67.0/68.7/**71.5%**. Wide 30-min OR (> 0.6x ATR, 4-7% of days): continuation **77.5% ES / 74.2% NQ**. Reaching a 1.0x-range extension by close: ES 5-min 64%, 30-min 32%; NQ 30-min 26%. First break timing: 53% within 5 min of the OR close, ~87% within 30 min. Median MFE:MAE for ES 5-min with 5-min close confirm = 5.5 : 10.25 pts (0.54). Long breakouts beat shorts by ~9 points of continuation in every configuration. Edgeful (ES, 6 months to Nov-2024, 15-min OR): breakout-and-hold 16.9%, breakdown 16.2%, double break 66.9%; 0.5x extension hit 72%/68%, 1.0x 51%.

**Evidence quality: 3** (large-sample base rates + several independent backtests incl. one OOS; but also a well-designed null result; practitioner tests are short and optimized).

**Data requirements.** 1-min OHLC only (volume filters optional).

**Prop fit.** Good structurally: one trade/day, flat by close, defined stop. The only robust OOS variant (4c) has 25% WR and PF 1.3 — profits cluster, which stresses the 50% consistency rule; the high-WR variants (4a/4b: 72-75% WR with 0.5x-range targets, ~1:1 payoff) are better aligned with "many small green days" but are 6-12-month optimized and flattened in mid-2026. Risk per trade on MNQ/MES is small ($75-$500), compatible with $2k EOD DD at 1-4 micros. Use: 15/30-min OR, require a 5-min close outside, long-only or SMA-200 bias, skip ORs > 0.55-0.8% of price (or > 0.6x ATR for continuation plays), target 0.5-1.0x range, hard stop at opposite OR side, one trade/day, flat 15:55.

**Sources.** edgeful.com/blog/posts/5-minute-opening-range-breakout-es-strategy; tradethatswing.com/opening-range-breakout-strategy-up-400-this-year; backtestsnotsignals.substack.com/p/opening-range-breakout-real-edge; github.com/zachisit/july-backtester/pull/400; tradingstats.net/orb-breakout-strategy-guide; edgeful.com/blog/posts/the-opening-range-breakout-orb-trading-strategy.

## 5. Initial Balance (first-hour) breakout with C-period confirmation

**Origin.** Market Profile (Steidlmayer/Dalton) "IB extension"; quantified by TradingStats on ES/NQ Jan-2015 to Dec-2025 (2,686 ES / 2,833 NQ days).

**Rules (standard objective interpretation).** IB = high/low of 9:30-10:30. Long if a 30-min bar (10:30-11:00, "C period") **closes** above IB high; short if below IB low. Stop = IB midpoint (tight) or opposite IB extreme (wide). Target = 1.0x IB width extension (partial at 0.5x). Prefer narrow IB (< 0.5x 14-day ATR); skip extreme IB (> 1.5x ATR). Max 2 IB trades/day; flat 15:55.

**Evidence (base rates).** Any breakout 97.8% ES / 96.2% NQ; single up 38.3/40.6%, single down 30.9/33.0%, double 28.7/22.6%. 100%-IB extension by close: 18.8% up / 20.5% down (ES), 12.8/15.9% (NQ); **if the C-period closes above IB high, 100% extension rises to 45.5% ES / 33.2% NQ; below IB low: 50.0% / 41.7%**. Narrow IB median extension 74.8% of IB vs 22.3% for extreme IB; narrow IB double-breaks 33.6%, wide 4.8%. First break occurs 10:30-11:00 on 65% of days, > 80% by 11:30. Shallow retracement (< 25% of IB) after the break -> 93.8% close in the break direction; deep (>= 50%) -> only 24.8%. First break fails (closes back inside IB) 34%; downside breaks fail more (53% vs 45%). Median MAE 7.25 ES pts up / 9.0 down (0.20-0.26x ATR); median MFE 8.25 / 9.75. IB high = day high 33% of days; IB low = day low 40%. Only ~1 in 10 ES sessions is a true trend day.

**Evidence quality: 2** (large-sample descriptive statistics, no P&L backtest).

**Data requirements.** 1-min OHLC only.

**Prop fit.** Attractive: entry after 11:00 avoids the 9:30 chaos, stop ~0.25x ATR (ES ~8-10 pts = $40-50/MES), target 0.5-1.0x IB. Expected payoff near 1:1 with ~45-50% hit rate on the filtered subset -> thin but positive; needs the confirmation + narrow-IB + shallow-retrace filters to be worth costs. Must be backtested; no published equity curve.

**Sources.** tradingstats.net/initial-balance-breakout-statistics; satotrades.com/guides/initial-balance-futures.

## 6. Crabel ORB with "Stretch" and NR4 / NR7 / Inside-Day / 2-bar-NR setups

**Origin.** Toby Crabel, *Day Trading with Short Term Price Patterns and Opening Range Breakout* (1990); S&C magazine articles (1990); OxfordStrat 42-market test 1980-2013; Quantpedia/QuantifiedStrategies NR7 tests.

**Rules.** Noise = min(High - Open, Open - Low) each day; Stretch = 10-day SMA of Noise (OxfordStrat uses 2x). Setup days: NR4 (narrowest daily range of last 4), NR7 (of 7), ID (inside day), 2-bar NR (narrowest 2-day range vs 20 days), ID/NR4 combo ("double contraction"). Next day: buy stop at Open + Stretch, sell stop at Open - Stretch; the first fill is the position, the other is the protective stop; exit at close (Crabel) or time/target/6x ATR(20) stop (OxfordStrat). Trend-day heuristic (Crabel): a trend day opens near one extreme and closes near the other with >= 70% of the range between open and close.

**Evidence.** Crabel's book tables (S&P, 1982-1989): e.g., one ORB-after-pattern table shows 203 trades, 71% profitable, avg win $343 / avg loss $289; a generic pattern 94 trades, 59% profitable, avg win $403 / loss $210. OxfordStrat (42 futures, 1980-2013, 1% fixed-fractional): sensitivity charts positive for most hold/target combos, no summary stats published. Zarattini (SPY, 2007-2024): intraday momentum after NR4 day earns 22 bps/day (t=5.14, Sharpe 3.2) vs 12 bps unconditional; after NR7 16 bps (t=3.07). Gap-and-range stats are consistent with NR days preceding expansion.

**Evidence quality: 3** (book + multi-market test + the NR4 conditioning result in a peer-reviewed-style paper; the original S&P stats are 1980s).

**Data requirements.** Daily + 1-min OHLC; no volume.

**Prop fit.** Good filter for any day-trade trend strategy: trade only on days after NR4/NR7/ID. Stretch-based entries are tight (ES 10-day avg noise ~ 5-10 pts) and define the stop immediately; exit at close. Frequency: NR4 ~25% of days, NR7 ~14%. Combine with Section 1 or 4.

**Sources.** store.traders.com/-v08-c02-barnr-pdf.html; oxfordstrat.com/trading-strategies/toby-crabel-narrow-range-1; quantifiedstrategies.com/nr7-trading-strategy-toby-crabel (bot-gated); Zarattini et al. Table 5.

## 7. Gap-and-Go (opening gap continuation) on ES/NQ

**Origin.** Classic; quantified by TradingStats (NQ Jan-2015 to Dec-2025, 2,791 days; ES 2014-2024 indicator), edgeful, crosstrade.io.

**Rules (standard objective interpretation).** Gap = RTH open 9:30 minus prior RTH close 16:00 (or 16:15 settlement). Trade in gap direction only when the gap is large and opens outside yesterday's range: gap > 0.4% (ES) / 0.6% (NQ) of price, or > 0.7x 14-day ATR. Entry: break of first 5-min or 15-min high (gap up). Stop: gap midpoint or below the first-15-min low. Target: 1x the first-15-min range or trail by 20-EMA(5-min); flat 15:55. Fade (gap-fill) is the mirror strategy for tiny gaps inside the prior range (77.8% fill) and belongs to the mean-reversion family.

**Evidence.** NQ fill rates by size: tiny (< 0.3x ATR) 77.8%, small (0.3-0.7x) 42.0%, medium (0.7-1.2x) 25.6%, **large (> 1.2x ATR) 8.2%** -> ~92% of large gaps do not fill same day. Open inside prior range fills 70.4%; above range 47.1%; below 44.1%. Median fill time 18 min; 43% of fills happen by 10:30; 60.3% of all NQ gaps fill by close (ES ~70%). Gap-and-go win rate quoted at 50-55% vs 68-72% for gap fills (edgeful/crosstrade, no period). High-vol regime fills less (56.3%).

**Evidence quality: 2** (descriptive base rates; no published P&L curve for the continuation variant).

**Data requirements.** 1-min OHLC only.

**Prop fit.** Large-gap days are rare (~10-15% of days) but are exactly the trend days a $3k target needs; one trade/day, defined stop. Risk: large-gap days are also high-ATR days (NQ MAE P90 = 203 pts = $400/MNQ), so size at 1-2 micros. Not a stand-alone system; a day-selection filter.

**Sources.** tradingstats.net/gap-fill-strategy; tradingstats.net/when-do-gaps-fill; edgeful.com/blog/posts/trading-gap-fills; crosstrade.io/learn/trading-strategies/gap-and-go.

## 8. Larry Williams Volatility Breakout (open +/- k x prior range)

**Origin.** Larry Williams, *Long-Term Secrets to Short-Term Trading* (1999); MQL5 "Market Secrets Part 5" implementation (2026); WH SelfInvest system.

**Rules.** Range(t-1) = High(t-1) - Low(t-1). Buy stop at Open(t) + k_b x Range(t-1); sell stop at Open(t) - k_s x Range(t-1); k = 0.25-0.50 (Williams often used larger k for buys than sells and only traded with the direction of a trend/day-of-week filter). Stop = k_stop x Range(t-1) (default 0.5) or a $ stop; exit at close (day-trade version) or next day's open (Williams's "bail-out" exit: first profitable open). MQL5 variant: target = 4 x stop.

**Evidence.** MQL5 test on XAUUSD daily Jan-Nov 2025: +60% on $10k, no WR/PF reported. Classic published results are 1980s-90s S&P/bonds and not independently verified. No credible 2020s ES/NQ backtest found.

**Evidence quality: 2.**

**Data requirements.** Daily + 1-min OHLC.

**Prop fit.** Simple, one trade/day, flat at close; the 0.5x-prior-range gate on ES (~30-40 pts) is wide and sets the stop far ($150-200/MES), so only 1-2 micros fit the $2k DD. Equivalent to a wide, ATR-scaled ORB; test as a parameter of the ORB engine (gate = k x prior range instead of the OR extreme) rather than as a separate system.

**Sources.** mql5.com/en/articles/20745; whselfinvest.com (Volatility Break-out Larry Williams); quantifiedstrategies.com/larry-williams-volatility-strategy.

## 9. Turtle / Donchian channel breakout (daily and intraday adaptations)

**Origin.** Richard Dennis & William Eckhardt (1983); rules published by Curtis Faith (*Way of the Turtle*, 2007; "Original Turtle Trading Rules" PDF). Daily tests: StatOasis (SPY 1993-2026, 1,188 variants), Algomatic (NQ 1990-2025, Gold 2000-2025), MQL5 (EURUSD 2018-2024).

**Rules.** System 1: enter on 20-day high/low breakout, skip if the last S1 breakout in that direction was a winner, exit on 10-day opposite extreme. System 2: 55-day entry, 20-day exit, take all signals. N = 20-day Wilder ATR; unit = 1% equity / (N x $/pt); add units every 0.5N up to 4; stop 2N from the latest entry (all units). Intraday adaptation (standard): 20-bar/55-bar Donchian on 5-min or 15-min bars, exit on 10-bar opposite channel or at 15:55.

**Evidence.** SPY 40-in/20-out long: CAGR 2.7%, MDD 26.3%, WR 47.6%, PF 1.75, 84 trades in 33 years; 20-day entry beat 40-day (3.76% vs 2.69% CAR); every unfiltered short variant lost (490/594 <= 0); **20-day forward return after a 40-day breakout fell from +0.85% (1993-99) to +0.27% (2000s/2010s) to +0.02% (2020-26)**. Algomatic long-only Donchian: NQ 1990-2025 CAGR 4.05%, MDD 15.8%, WR 51%, R:R 1.98; NQ 2010-2025 CAGR 5.9%, MDD 14.0%; Gold 2000-2025 CAGR 6.0%, MDD 17.0%, WR 42.6%, R:R 2.6. Liberated Stock Trader: 35% WR, 2.4 R:R, expectancy 0.2 across 360 stock-years. No credible intraday Donchian backtest on ES/NQ found (a DAX 1-hour Donchian "did not ruin the account" over 15 years, ProRealCode, no stats).

**Evidence quality: 4** for the daily system's long-run behaviour (replicated many times) but **2** for intraday use.

**Data requirements.** Daily OHLC (1-min for intraday variants).

**Prop fit.** Daily system holds overnight: not allowed. 30-40% WR and multi-week holds violate consistency and payout cadence. Use only as a bias: e.g., take intraday longs only if close > 20-day high was the most recent breakout (or price above 55-day channel midpoint).

**Sources.** mql5.com/en/articles/23448; statoasis.com/overfit/research/40-in-20-out-...; algomatictrading.substack.com/p/strategy-8-the-easiest-trend-system; liberatedstocktrader.com/donchian-channels-indicator.

## 10. Raschke/Connors "Holy Grail" (ADX + 20-EMA pullback)

**Origin.** Linda Bradford Raschke & Laurence Connors, *Street Smarts* (1995), ch. "The Holy Grail".

**Rules.** 14-period ADX > 30 and rising (ADX today > ADX yesterday). Long: price pulls back to touch the 20-period EMA (Raschke uses EMA; some re-tellings use SMA); place a buy stop at the high of the bar that touched the EMA; initial stop below the pullback swing low (standard: 1 tick below the lowest low of the pullback); target = the most recent swing high; after a profitable move trail the stop to the EMA or exit at target; if stopped, re-enter on the next EMA touch while ADX > 30. Shorts mirror. Timeframe: any; for day trading use 5-min bars, RTH only, flat 15:55.

**Evidence.** No credible quantified backtest on ES/NQ found. A gold H1 (XAUUSD) ADX+EMA test reports 57% WR, 1.5 R:R over one month (anecdote). Practitioner consensus: works in persistent trends, chops in ranges; ADX > 30 occurs on a minority of intraday sessions.

**Evidence quality: 1-2** (book + anecdotes).

**Data requirements.** OHLC only.

**Prop fit.** Objective and codeable; pullback entries give tighter stops (ES ~4-8 pts on 5-min) which suits micros and the $2k EOD DD. Expect ~50% WR with ~1.2-1.5 R:R if it works at all; must be validated in our backtest. Natural pairing: trade Holy Grail pullbacks only on days already identified as trend days (Section 5/7 filters).

**Sources.** tradingsetupsreview.com/the-holy-grail-trading-setup; tradersmastermind.com/linda-raschke-trading-strategy; investinglive.com (Holy Grail); Street Smarts (book).

## 11. Intraday EMA crossover / EMA pullback (9/21 EMA on 5-min; 20/50 on 15-min)

**Origin.** Practitioner folklore; quantified fragments from NocNoe, FuturesHive, Backtestx, TradingSim (2025-26 blog tests).

**Rules (standard).** 5-min RTH bars. Long when EMA9 crosses above EMA21 (optionally require price > VWAP and EMA9 > EMA21 > EMA50); refinement: wait for the first pullback to the 21-EMA after the cross and enter on the break of that bar's high. Stop below both EMAs (10-15 ES pts / 25-40 NQ pts) or 1.5 x ATR(14, 5-min). Exit on opposite cross, or scale half at +2R and trail the rest; flat 15:55.

**Evidence.** Raw 9/21 cross on ES: 30-50 trades/quarter, 60-65% losers, PF ~1.2 on 5-min in one test; WR 45-50% trending, < 40% ranging. Blog-quoted WR of 65-80% for filtered versions are unsourced. No OOS evidence.

**Evidence quality: 1.**

**Data requirements.** OHLC (VWAP needs volume).

**Prop fit.** Many signals/day -> commissions and whipsaws; raw PF ~1.2 is below what a $2k DD account needs. Only worth testing as the entry mechanism inside a trend-day-filtered framework.

**Sources.** nocnoe.com/blog/moving-average-crossover-strategy-futures-day-trading; futureshive.com/blog/moving-average-strategies-futures-2025; backtestx.com/9-21-ema-crossover.

## 12. Supertrend (ATR 10, mult 3) trailing system

**Origin.** Olivier Seban (2009). Tests: dev.to/moonthetrain (gold & NZDUSD tick data 2020-2026, 32 parameter combos), PickMyTrade (MNQ/ES 2026 guide).

**Rules.** Basic band = HL2 +/- m x ATR(n); bands ratchet in the trend direction; long when close crosses above the upper band (trend flips), short on the lower band. Stop-and-reverse or exit on flip; intraday version flat at close. Defaults n=10, m=3 (7/2 for faster day-trading flips).

**Evidence.** Gold: M15 4,007 trades, WR 34%, PF 1.03; H1 PF 1.11; H4 PF 1.97 (2020-21 PF 1.09, 2022-23 PF 1.02, **2024-Sep-2026 PF 3.19** driven by the gold bull run); D1 PF 0.93; short side lost on gold. NZDUSD: PF 0.80-0.86 on all intraday frames. ES/MNQ: blog claims 55-65% WR in trending conditions, no stats.

**Evidence quality: 2** (one transparent multi-year test; conclusion: "a clean trend filter, not a stand-alone system").

**Data requirements.** OHLC only.

**Prop fit.** Low WR (33-37%) with occasional big winners is the opposite of what the consistency rule wants. On intraday frames PF ~1.0. Use as a trailing-stop/exit mechanism for strategies 4-7, not as an entry.

**Sources.** dev.to/moonthetrain/tradingview-supertrend-strategy-backtest-6-years-of-ticks-1ela; blog.pickmytrade.trade/supertrend-automation-for-mnq-es-futures-2026-guide; quantifiedstrategies.com/supertrend-indicator.

## 13. Parabolic SAR trailing system

**Origin.** J. Welles Wilder (1978). Tests: Unofficed (Indian equities, multiple frames); OptionsTradingIQ (SPX, options overlay).

**Rules.** SAR with AF start 0.02, step 0.02, max 0.20; long while price > SAR, flip on cross. Intraday: 5-/15-min bars, flat at close.

**Evidence.** Range-bound large-caps lost on most frames; trending commodity name profitable on daily+; no ES/NQ intraday stats. SPX overlay netted ~$400 over a test year.

**Evidence quality: 1.**

**Data requirements.** OHLC only.

**Prop fit.** Same as Supertrend: exit/trailing tool only.

**Sources.** unofficed.com/courses/entropy/lessons/backtesting-parabolic-sar-strategy; optionstradingiq.com/parabolic-sar-trading-strategy.

## 14. Keltner Channel breakout / pullback (20-EMA, 2 x ATR(14))

**Origin.** Chester Keltner (1960), Linda Raschke's modern form. Implementations: StockSharp, MQL5 EAs.

**Rules.** Mid = EMA(20); bands = Mid +/- 2 x ATR(14) (5-min default in StockSharp example). Breakout variant: long on close above upper band, exit on close back below Mid or stop at Mid; pullback variant (Raschke): in an up-trend (price above Mid, Mid rising) buy the first touch of Mid, stop below lower band, target upper band. Flat 15:55.

**Evidence.** Vendor claims (58%/yr on an MQL5 EA, 18-year tick test) are not independent. No peer-reviewed or OOS ES/NQ evidence found.

**Evidence quality: 1.**

**Data requirements.** OHLC only.

**Prop fit.** The Keltner pullback variant is the same mechanics as Holy Grail with volatility-scaled stops; test as a parameterization of Section 10.

**Sources.** doc.stocksharp.com/en/api-examples/0007_Keltner_Channel_Breakout; mql5.com/en/market/product/63119.

## 15. Multi-timeframe: daily trend bias + intraday breakout/pullback entry

**Origin.** Generic; the only quantified OOS instance in this sweep is the MNQ ORB with SMA(200) filter (Section 4c). Also QuantifiedStrategies "Multi-Timeframe Analysis" (no stats accessible), FMZ/ACY SMA stacks.

**Rules.** Bias: daily close > 200-SMA (or 20 > 200 with both rising; or last Donchian breakout up) -> long-only intraday; < -> short-only or flat. Entry: ORB (4c), IB breakout (5), Holy-Grail pullback (10). One loss per day cap.

**Evidence.** 4c OOS 2023-2026: Sharpe 1.10, PF 1.32, MDD 12.8% (MNQ). Base rates: long ORB continuation beats short by ~9 pts across all ES/NQ configurations (2014-2026); StatOasis: all short Donchian variants lose on SPY.

**Evidence quality: 3** (one OOS test; strong structural base rates for the long bias).

**Data requirements.** Daily + 1-min OHLC.

**Prop fit.** The single most useful idea in the family for prop accounts: cut the losing short side on equity indices in 2023-2026, cap one loss/day (protects the EOD trailing DD), and keep exposure ~25% of the time.

**Sources.** backtestsnotsignals.substack.com/p/opening-range-breakout-real-edge; tradingstats.net/orb-breakout-strategy-guide; quantifiedstrategies.com/multi-timeframe-analysis.

## 16. Time-series momentum (12-month sign) / CTA trend following (daily)

**Origin.** Moskowitz, Ooi, Pedersen (JFE 2012); Hurst-Ooi-Pedersen "A Century of Evidence". Benchmark: SG Trend Index.

**Rules.** Each month (or day) sign of the trailing 12-month excess return (or 1/3/12-month ensemble) -> long/short, scaled to 40%/sigma ex-ante vol; hold until sign flips.

**Evidence.** 58 futures 1985-2009 Sharpe ~1 (gross) in the paper; SG Trend Index: **2022 +27.35%** (best year since 2000), 2023 -3.3% (March -7.7%), 2024 ~+2.8%, 2025 +2.39%. Edge is multi-week, not intraday.

**Evidence quality: 5** for the daily/monthly effect; **n/a** intraday.

**Data requirements.** Daily data (Yahoo).

**Prop fit.** Not a day-trade strategy. Only use: bias/regime indicator (e.g., allow intraday longs in GC while 12-month TSMOM is positive; stand aside in CL when the sign is negative and realized vol is high).

**Sources.** Moskowitz-Ooi-Pedersen JFE 2012; thefullfx.com (SG Trend 2022); toptradersunplugged.com monthly reports; hedgenordic.com (2024 drivers).

## 17. VWAP trend-following (long above VWAP, VWAP as trailing stop)

**Origin.** Zarattini & Aziz, "Volume Weighted Average Price (VWAP): The Holy Grail for Day Trading Systems" (SSRN 2023); practitioner VWAP guides.

**Rules.** Compute RTH VWAP from 9:30. Long when price is above VWAP and VWAP is rising (standard: enter on a 5-min close above VWAP after a pullback that touched VWAP); stop = close below VWAP; exit 15:55. Short mirror. The Noise-Area paper uses VWAP only as the trailing stop (Section 1).

**Evidence.** In the Noise-Area paper, adding VWAP to the trailing stop doubled Sharpe (0.61 -> 1.24) and cut MDD from 21% to 12% on SPY 2007-2024. Stand-alone VWAP "bounce"/"breakout" win rates (70-80%) quoted in guides are unsourced.

**Evidence quality: 3** for VWAP-as-stop (peer-reviewed-style paper), **1** for VWAP-as-entry.

**Data requirements.** **Needs volume** for true VWAP; with OHLC-only we can approximate with a cumulative typical-price average (flag: approximation).

**Prop fit.** As a trailing-stop rule it is directly useful; as an entry it is untested.

**Sources.** Zarattini-Aziz VWAP paper (ref [5] in Beat the Market); ninjatrader.com/futures/blogs/vwap-strategies-futures; futureshive.com VWAP guide.

## 18. Intraday momentum in crude oil (first half-hour -> last half-hour, CL)

**Origin.** Wen, Gong, Ma, Xu, "Intraday momentum and return predictability: Evidence from the crude oil market", Economic Modelling 2020 (SSRN 3553682); China INE crude variant (Economic Modelling 2021).

**Rules.** On the CL pit session (9:00-14:30 ET), r1 = 9:00-9:30 return (from prior settlement), r_last = 14:00-14:30. Long at 14:00 if r1 > 0, short if r1 < 0, flat 14:30. Stronger when first-half-hour realized vol, volume, or overnight jump is high.

**Evidence.** USO 1-min: in-sample R2 0.729%, OOS R2 0.659%; crisis periods 1.92% vs 0.34%; timing strategy "significantly outperforms" always-long and buy-and-hold (figures not in the public summary).

**Evidence quality: 3** (journal paper, ETF not futures, no futures replication).

**Data requirements.** 1-min OHLC only.

**Prop fit.** Same profile as Section 2: one 30-min trade/day, tiny variance; MCL tick value is small ($1/tick), so 5-10 MCL are needed to matter; CL afternoon liquidity is fine. Low priority but cheap to test.

**Sources.** sciencedirect.com/science/article/abs/pii/S0264999319310417; harbourfronts.com/does-intraday-momentum-exist-in-the-crude-oil-market; PMC7480318 (commodity ETFs).

## 19. Trend-day identification (open-drive / gap + narrow IB / range expansion) as a day filter

**Origin.** Crabel (1990), Market Profile (Dalton), Raschke's "trend day" notes; quantified fragments from TradingStats, satotrades, microstrader, Zarattini Table 5.

**Rules (objective composite).** Flag a potential trend day at 10:30 if at least two of: (a) gap > 0.7x ATR opening outside yesterday's range; (b) IB width < 0.5x 14-day ATR (narrow); (c) first 30-min bar closes in the top/bottom 25% of its range and beyond yesterday's high/low (open-drive); (d) prior day NR4/NR7/ID. On flagged days trade only in the direction of the open (no fades), hold runners to 15:55 with a trailing stop at the 20-EMA(5-min) or VWAP. Negative filter: skip days whose IB > 1.5x ATR, and after a "Trend" day pattern (Zarattini: -2 bps next day).

**Evidence.** Only ~10% of ES sessions are trend days; narrow IB extends 3.4x further than extreme IB; large gaps fill only 8.2%; NR4 prior day doubles intraday-momentum PnL (22 vs 12 bps); 30-min OR > 0.6x ATR continues 77.5% (ES).

**Evidence quality: 2-3** (robust base rates from 10-12-year samples; composite rule is our synthesis).

**Data requirements.** Daily + 1-min OHLC.

**Prop fit.** Essential: the $3k target on $2k EOD DD requires catching a handful of trend days per month without bleeding on rotation days; this filter decides when Sections 1/4/5/10 are allowed to trade and when to sit out.

**Sources.** tradingstats.net (ORB, IB, gap pages); satotrades.com/guides/initial-balance-futures; Zarattini Table 5; Crabel (1990).

## 20. Momentum ignition after consolidation (Bollinger/Keltner "TTM squeeze" breakout)

**Origin.** John Carter (TTM Squeeze), John Bollinger (band-width squeeze); many TradingView scripts.

**Rules.** Squeeze on when BB(20, 2 sigma) lies inside KC(20, 1.5 x ATR); fire when BB re-exits KC; trade in the direction of momentum (close - midpoint of (highest high + lowest low)/2 and SMA, linear-regression slope > 0). Intraday: 5-min bars, stop = opposite KC band, target 2R or trail; flat 15:55. Volume-spike confirmation (> 150% of 20-bar average) is common but needs volume.

**Evidence.** No quantified ES/NQ backtest found; only indicator descriptions and vendor scripts.

**Evidence quality: 1.**

**Data requirements.** OHLC (volume optional).

**Prop fit.** Objective and cheap to test; conceptually overlaps with NR-day ORB (compression then expansion) which has better evidence. Low priority.

**Sources.** chartschool.stockcharts.com (Bollinger Band Squeeze); trendspider.com/learning-center/bb-kc-squeeze; litefinance.org (TTM squeeze).

## 21. Mark Fisher ACD (A-up / C-down from the opening range)

**Origin.** Mark Fisher, *The Logical Trader* (2002).

**Rules.** OR = first 5-30 min (Fisher: 5-30 min depending on market). A-up = OR high + A-value (market-specific, ~10% of the 10-day avg daily range); A-down = OR low - A. Long if price holds above A-up for a confirmation period (e.g., half the OR length); stop = back inside OR low (or OR midpoint); C-up/C-down = larger offsets used for failed-A reversals. Daily "pivot range" and 3-day rolling pivots as bias. Flat at close.

**Evidence.** Book anecdotes; no independent quantified test found (TradingView indicators only).

**Evidence quality: 1.**

**Data requirements.** OHLC only.

**Prop fit.** Equivalent to an ORB with an ATR-scaled buffer and time confirmation, which the base rates (Section 4e) suggest reduces false breaks; fold into the ORB parameter grid (buffer = 0-0.2x ATR, confirmation = 1-5 min close).

**Sources.** The Logical Trader (book); tradingview.com script RMlgLTOl (ACD lines).

## 22. "Buy at 9:45, hold to close" long-bias baseline (benchmark, not a strategy)

**Origin.** Control in zachisit/july-backtester PR #400 (ES, Sep-2024 to 2026, 516 sessions).

**Rules.** Buy 1 ES at 9:45, sell at 16:00 (or 11:00), no stop.

**Evidence.** +$2,285 (close exit) to +$22,735 (11:00 exit) per contract over the 2 years, beating all 12 ORB configs. This is the intraday drift of the 2024-2026 bull market, not an edge; but it quantifies how strong the long bias has been in the prime backtest window.

**Evidence quality: 2** (single control test).

**Prop fit.** Not tradable (no stop, index drift risk), but every candidate must beat this benchmark on 2025-2026 data, and it supports long-only configurations for ES/NQ in that window.

---

## What the evidence says works in 2022-2026 (and what does not)

- **Intraday momentum (Noise-Area) was excellent 2020-2024 (Sharpe 1.4-2.0/yr, +25.8% in 2022 while SPY fell 19.5%) and has been ~flat since early 2025 on both SPY and ES.** It is a long-volatility strategy: Sharpe scales with VIX (1.5 at VIX > 20, 3.5 at VIX > 40). In a calm, grinding 2025-26 tape it earns nothing after costs. Trade it only in elevated-VIX regimes and/or after NR4 days; NQ > ES.
- **Naive ORB does not work on index futures after costs (2015-2026 multi-index replication; 2024-2026 ES study).** Filtered ORB does: SMA-200 bias + one-loss cap on MNQ held up OOS 2023-2026 (Sharpe 1.1, PF 1.3, MDD 13%); high-WR 50%-of-range-target versions worked for 6-12 months to mid-2026 then flattened. Long breakouts are structurally better than shorts on ES/NQ (+9 pts continuation); 30-min ORs with 5-min-close confirmation continue 71-77% when wide (> 0.6x ATR).
- **Daily trend following was great in 2022 (SG Trend +27%) and poor since (2023 -3.3%, 2024 +2.8%, 2025 +2.4%)**; on SPY the Donchian post-breakout drift has decayed to ~0 in the 2020s; short-side Donchian loses. Gold is the exception: trend/Supertrend systems on GC printed PF ~3 in 2024-2026 on a one-directional bull market (regime risk).
- **First-half-hour -> last-half-hour momentum** is real but small and weaker than in 1993-2013; it reappears in stress (2020 crash Sharpe 1.45 in the QuantConnect test). Use as a low-risk afternoon add-on in high-VIX weeks.
- **Base-rate facts that did persist across 2014-2026 and are safe to build on:** both OR sides are hit on 2/3 of days (fade the first 5-min break or require close confirmation); narrow IB -> extension, extreme IB -> rotation; large gaps outside the prior range rarely fill (8%); first IB break comes 10:30-11:00 on 65% of days; shallow (< 25%) retracement after an IB break -> 94% continuation close.
- **Prop-specific implication.** A $3k target with $2k EOD trailing DD and 50% consistency wants ~15-25 trading days of modestly positive P&L rather than 2-3 home runs. That favors: micro contracts (2-4 MES or 1-2 MNQ), one or two trades/day, targets of 0.5-1.0x the opening/IB range (WR 60-75%, payoff ~1:1), hard $ stops <= $300/day, a long-only bias on ES/NQ, a trend-day filter to skip rotation days, and standing aside (or switching to the last-half-hour trade) when VIX < 15. Expected gross per good day on 4 MES with a 10-pt target: ~$200; the $150-day payout criterion is reachable roughly 40-50% of traded days under the base rates above, which needs to be verified in the backtest.

## Source list (fetched/used)
- SFI RP 24-97 "Beat the Market" PDF: https://alexandria.unisg.ch/server/api/core/bitstreams/a99aba00-f967-49b3-aceb-f544dc386e0b/content
- https://concretumgroup.com/beat-the-market-an-effective-intraday-momentum-strategy-for-sp500-etf-spy/
- https://www.quantitativo.com/p/intraday-momentum-for-es-and-nq
- https://github.com/codecat-ops/zarattini-2024-momentum-spy
- https://quantifiedstrategies.substack.com/p/systematic-intraday-trend-following
- Gao, Han, Li, Zhou "Market Intraday Momentum" (SSRN 2440866; JFE 2018): https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2440866
- https://www.quantconnect.com/learning/articles/investment-strategy-library/intraday-etf-momentum
- https://papers.ssrn.com/abstract=4416622 (Zarattini & Aziz ORB)
- https://www.mql5.com/en/blogs/post/776235 (ORB replication, 5 indices, net zero)
- https://concretumgroup.com/backtesting-the-opening-range-breakout-orb-strategy-using-polygon-io/
- https://www.quantconnect.com/research/18444/opening-range-breakout-for-stocks-in-play/
- https://tradingstats.net/orb-breakout-strategy-guide/
- https://tradingstats.net/initial-balance-breakout-statistics/
- https://tradingstats.net/gap-fill-strategy/
- https://www.edgeful.com/blog/posts/5-minute-opening-range-breakout-es-strategy
- https://www.edgeful.com/blog/posts/the-opening-range-breakout-orb-trading-strategy
- https://tradethatswing.com/opening-range-breakout-strategy-up-400-this-year/
- https://backtestsnotsignals.substack.com/p/opening-range-breakout-real-edge
- https://github.com/zachisit/july-backtester/pull/400
- https://satotrades.com/guides/initial-balance-futures
- https://oxfordstrat.com/trading-strategies/toby-crabel-narrow-range-1/
- https://store.traders.com/-v08-c02-barnr-pdf.html
- https://www.mql5.com/en/articles/20745 (Larry Williams volatility breakout)
- https://www.mql5.com/en/articles/23448 (Original Turtle rules)
- https://statoasis.com/overfit/research/40-in-20-out-the-hedge-fund-trend-strategy-still-in-use-today
- https://algomatictrading.substack.com/p/strategy-8-the-easiest-trend-system
- https://tradingsetupsreview.com/the-holy-grail-trading-setup
- https://www.futureshive.com/blog/moving-average-strategies-futures-2025
- https://nocnoe.com/blog/moving-average-crossover-strategy-futures-day-trading
- https://dev.to/moonthetrain/tradingview-supertrend-strategy-backtest-6-years-of-ticks-1ela
- https://unofficed.com/courses/entropy/lessons/backtesting-parabolic-sar-strategy/
- https://doc.stocksharp.com/en/api-examples/0007_Keltner_Channel_Breakout
- https://harbourfronts.com/does-intraday-momentum-exist-in-the-crude-oil-market/
- https://www.sciencedirect.com/science/article/abs/pii/S0264999319310417
- https://thefullfx.com/year-end-drop-fails-to-dampen-stellar-2022-for-trend-followers/ and toptradersunplugged.com monthly reports (SG Trend)
