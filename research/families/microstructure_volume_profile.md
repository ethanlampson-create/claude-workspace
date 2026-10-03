# Family: Market Profile, Volume Profile, VWAP and Order-Flow Methods

Research sweep date: 2026-10-03. Scope: Market Profile (TPO, initial balance, range extension, poor highs/lows, single prints, value-area rules, 80% rule, open types), Volume Profile (POC, VAH/VAL, naked POC, HVN/LVN), session VWAP and standard-deviation bands, anchored VWAP, cumulative delta divergence, absorption/exhaustion, footprint imbalances and NYSE TICK extremes. For every method: the objective rule, the data it really needs, and whether an OHLC-only approximation exists. All times are US Eastern (ET).

Target use: Lucid Trading 50K LucidFlex (eval target $3,000; $2,000 END-OF-DAY trailing drawdown checked intraday; 50% consistency rule in eval; funded: no consistency, EOD trailing locks at $50,100 once EOD balance reaches $52,100; payout needs 5 days with >= $150 EOD profit; 4 minis/40 micros eval, 2 minis/20 micros at funded start; day-trade only). Data available to us: 1-minute OHLC **without volume** for ES/NQ/GC proxies 2010-11 to 2026-09, daily futures + VIX from Yahoo.

Method note: the shared web-search budget was exhausted after 6 of the planned searches, so the sweep relied on direct fetches of ~45 pages (tradingstats.net 1-minute studies 2014-2026, edgeful.com reports, the Zarattini-Aziz VWAP paper PDF (SSRN 4631351), arXiv 2508.06788 and 2605.04004, the pedrobraiti volume-profile falsification repo, the nullh0 VWAP-futures post-mortem, the sonu71072 XAUUSD VP backtest, LuxAlgo/Trader Dale/crosstrade/algobars rule pages, mypivots, marketcalls, metrotrade, tradethatswing). Blocked: nexusfi (403), quantifiedstrategies (bot wall), ShadowTrader (521), CME Market Profile handbook (503), Investopedia. Book-based rules (Dalton *Mind over Markets* / *Markets in Profile*, Steidlmayer, Brian Shannon *Maximum Trading Gains with Anchored VWAP*) are written from the standard definitions and marked as such.

---

## 0. Executive summary

1. **The geometry of the profile (POC, value area, 80% rule, day types) has essentially no published, cost-adjusted standalone edge.** The only systematic falsification found (pedrobraiti/volume-profile-trading, SPY 1993-2026, QQQ 1999-2026, walk-forward 8y/3y, 0.11% round-trip cost) concludes: *"the geometry alone (POC, Value Area, day-types, 80% Rule) is mostly folklore"*; bootstrap 95% CIs on profit factor include 1.0 for every instrument (SPY PF 1.66, CI [0.99, 2.83]); the 80% rule traversed the value area only 27-67% of the time; "bearish" day types bounced more than "bullish" ones. Independent practitioner tests of the 80% rule on ES report 60-62% completion, not 80% (mypivots TradeStation test; nexusfi thread). Any edge the repo did find required the **volume** signal-candle filter (QQQ edge-to-edge PF 1.14 -> 1.89 with 1.5x volume), which we cannot compute.

2. **What does have large-sample support is time-structure, not volume-structure: the initial balance (IB).** tradingstats.net (ES 2,686 days / NQ 2,833 days, 2015-2025, 1-minute) and its 12-year retest study (2014-2026, ~3,000 break-days each) give stable, year-by-year base rates that are fully codeable from OHLC: 96-98% of days break the IB; first break occurs in the C period (10:30-11:00) 64-65% of the time; when the 10:30-11:00 bar **closes** outside the IB, 100% extension follows 45.5% (ES up) / 50.0% (ES down) vs 18.8%/20.5% unconditional; the first retest of the broken IB level after a 1.1x extension continues 71% (NQ) / 77% (ES); narrow IB (< 0.5x ATR14) breaks 98.7% with 74.8% median extension while "extreme" IB (> 1.5x ATR) stays contained 33% of the time. These are reach/continuation rates, not P&L, but they are the raw material for the IB strategies in this family (sections 6-10).

3. **Session VWAP as a trend filter has one peer-style paper (Zarattini & Aziz 2023, QQQ 2018-2023: +671%, Sharpe 2.1, MDD 9.4%, alpha 38% t>5) but the mechanics are hostile to futures.** The rule is long whenever a 1-minute close is above VWAP and short otherwise, always in the market: 21,967 trades in 5.7 years, 17% hit ratio, gain:loss 5.7, worst day -5.1%. On QQQ at $0.0005/share commission it works; on MNQ/MES with a 2-point / 0.5-point friction floor it almost certainly does not (Mesfin 2026 found 11 of 14 five-minute MNQ signal families failed purely on friction). The paper's own time-of-day decomposition shows essentially all of the profit comes from 09:30-12:00 and 15:00-16:00; a 2-window implementation with a close-confirmation filter is the only version worth testing, and we must use a price-only VWAP proxy (session TWAP of typical price) because we have no volume.

4. **VWAP-band reversion is the most commonly coded idea in this family and the public evidence is thin and mixed**: crosstrade's rule sheet quotes 55-65% win rate / PF 1.2-1.6 *with* an ADX<25 and news filter and 45% win rate without; the one rigorous individual study (nullh0, Micro WTI, long-only VWAP deviation, 505 trades, Sharpe 4.93, 13/15 walk-forward windows positive) was shelved by its own author as not separable from a lucky slice; tradingstats' extremes study shows session extremes < 0.3 ATR from the open revert 85% of the time but > 1.0 ATR only ~20%, which is the quantitative reason band fades die on trend days. See intraday_mean_reversion.md section 1-2 for the companion rules; here we add the regime gates and the OHLC approximation.

5. **Order-flow methods (cumulative delta divergence, absorption, footprint imbalances, NYSE TICK) cannot be reproduced from our data and have no public cost-adjusted backtests.** Delta needs bid/ask-classified volume (Trader Dale: "centralized tick-by-tick bid/ask data, not tick count"); the only academic evidence found (arXiv 2508.06788, ES one-second OFI/return SVAR) says flow impacts "dissipate almost entirely within a second", i.e. the measurable order-flow predictability lives far below the 1-minute bar. A price-only pseudo-delta (sum of close-location-value per bar) is just a momentum oscillator and must be labelled as such. NYSE TICK needs breadth data we do not have; there is no OHLC proxy.

6. **For the Lucid 50K Flex the best-shaped candidates are**: (a) IB C-period close-confirmed extension with a 0.5x-1.0x IB-range target and 0.25x stop (section 6); (b) IB retest-continuation at the 1.1-1.2x extension level, 10:30-12:00 only (section 7); (c) IB-by-rejection bias with the 0-25% ending-zone filter traded as an IB75/IB50 limit entry (section 9); (d) time-based value-area edge-to-edge rotation on balanced days with an open-inside-value filter and a hard trend-day kill switch (section 2); (e) VWAP (TWAP-proxy) two-window trend trade 09:31-12:00 and 15:00-15:55 with close confirmation and a daily loss cap (section 13). Everything that is "always in the market" or relies on 10R runners (raw VWAP trend trading, naked-POC magnets days away) fights the 50% consistency rule and the EOD trailing drawdown.

---

## 1. Data reality: what we can and cannot compute from 1-minute OHLC

| Concept | True input | OHLC-only approximation (what the backtest will use) | Fidelity |
|---|---|---|---|
| TPO profile, TPO POC, TPO value area | 30-min bars (price range per period) | Exact: build 30-min bars from 1-min, mark every tick level in [low, high] of each 30-min period; TPO count per level = number of periods touching it. Value area = standard Steidlmayer algorithm (start at POC row, add the larger of the two adjacent 2-row blocks above/below until >= 70% of TPOs). POC tie-break = row closest to the midpoint of the range (CBOT convention) | High (this *is* the original Market Profile; it never used volume) |
| Volume profile POC/VAH/VAL/HVN/LVN | volume at price | "Time-at-price" profile from 1-min bars: each 1-min bar adds 1 (or 1/(ticks in bar)) to every level in [low, high]. POC = most-visited level; VA = 70% of minutes. Correlates strongly with volume POC on index futures because volume per minute is far less variable than price per minute, but misses volume spikes | Medium-high for POC/VA, low for LVN detection |
| Naked POC | volume POC of prior sessions | time-at-price POC of prior RTH sessions, retired on first touch | Medium-high |
| Session VWAP | cumulative sum(P*V)/sum(V) | session TWAP of typical price (H+L+C)/3 on 1-min bars from 09:30 (or 18:00 for Globex-anchored). Bias: equal-weights quiet minutes; VWAP sits closer to opening-hour prices than TWAP does. Optional: weight 1-min bars by 1/(bar range) or by Yahoo hourly volume | Medium; Zarattini-Barbon-Aziz report the VWAP stop roughly doubles Sharpe vs no VWAP, so the proxy error matters; backtest both proxies |
| VWAP sigma bands | cumulative volume-weighted variance | cumulative std-dev of typical price around the TWAP, or k x ATR(14, 5-min) bands | Medium |
| Anchored VWAP | from an anchor bar | anchored TWAP from the same bar | Medium |
| Cumulative delta | bid/ask-classified volume | pseudo-delta = sum over bars of (C-O)/(H-L) x range, i.e. a close-location-value oscillator. This is NOT delta; it is price momentum | Low; label as "price-CVD" |
| Absorption / exhaustion / footprint imbalances | per-price bid x ask volume | none meaningful; only candle-shape proxies (long wick with close back inside = "absorption", range expansion then immediate reversal = "exhaustion") | Low |
| NYSE TICK | breadth tick data | none | Not available |

Costs to use everywhere: >= 1 tick slippage per side plus $1.5-2.5/side commission on micros (2-pt NQ / 0.5-pt ES friction floor killed 11 of 14 five-minute MNQ signal families in Mesfin 2026).

---

## 2. Value-area edge-to-edge rotation ("responsive" fade inside balance)

- **Origin**: Steidlmayer / Dalton (*Mind over Markets*, 1990; *Markets in Profile*, 2007): on a balanced day, responsive activity at the value-area extremes rotates price back toward the POC and across value. Codified as "range-day entries: fade extremes" (tradealgo), "buy near VAL, sell near VAH in range-bound markets" (quantvps), and tested as "Edge-to-Edge (E2E)" by pedrobraiti.
- **Rules (standard objective interpretation)**:
  - Reference profile = prior RTH session (09:30-16:00) TPO or time-at-price profile; VA = 70%.
  - Day filter: 09:30 open is **inside** the prior value area (balance presumption). Skip if the IB (09:30-10:30) range > 1.0x ATR14-daily or if the open is outside the prior day's range.
  - Long: after 10:00, price trades to within 2 ticks of VAL (or pierces it) and a 5-minute bar closes back above VAL. Short mirror at VAH.
  - Stop: 0.25 x VA width beyond the edge (or 1 tick beyond the rejection wick low, whichever is tighter, min 4 ES pts / 15 NQ pts).
  - Target 1 = POC (take half), target 2 = opposite VA edge. Time stop 15:30; flat 15:55.
  - Max 2 entries per side per day; no new entries after 14:30.
- **Parameters**: VA 70% (65-75); stop 0.25 x VA width (0.15-0.4); confirmation bar 5-min (1-15); IB width filter 1.0x ATR (0.8-1.2).
- **Evidence**: pedrobraiti (daily-bar rolling profile, OOS walk-forward): E2E PF 1.41 SPY, 2.06 QQQ, but 0.34-0.95 on Brazilian names; random-entry control p = 0.028 SPY / 0.30 QQQ; bootstrap PF CI includes 1.0; no alpha over exposure. matiasjuarezau-prog (QQQ 60 days of 5-min, previous-day/week profile, VA-edge mean reversion): v1 238 trades 58% WR **-8.59%**; v2 (EMA 3/9 trend filter) 164 trades 64.6% WR +0.75%; v5 (LVN stops, R:R >= 2) 87 trades 33.3% WR +4.66%, MDD -1.72%. tradealgo quotes 55-65% WR "when the value area filter is applied correctly" (unsourced). **Evidence quality: 2**.
- **Prop fit**: Good day shape (defined risk, target inside the day, many days with small positive P&L), but losses cluster on trend days that open inside value and then leave it; the open-inside-value + IB-width filter is mandatory. Approximate expected shape: ~55% WR, ~0.9-1.2 R, 0-2 trades/day. Codeable from OHLC (time-based VA).
- **Sources**: https://github.com/pedrobraiti/volume-profile-trading ; https://github.com/matiasjuarezau-prog/Volume-Profile-Backtesting ; https://www.tradealgo.com/trading-guides/futures/futures-trading-strategies ; https://www.quantvps.com/blog/value-area-trading-strategy-guide ; Dalton, *Mind over Markets* (book)

## 3. Market Profile 80% rule (value-area fill after re-entry)

- **Origin**: *The Profile Reports*, Dalton Capital Management 1987-1991; popularised in *Mind over Markets*. Definitions on mypivots, marketcalls, metrotrade, ShadowTrader.
- **Rules (canonical)**:
  - Prior-session value area (70%). Price **opens outside** the VA (above VAH or below VAL) or moves outside it.
  - Re-entry confirmation = **two consecutive 30-minute TPO periods inside the value area**. mypivots' precise reading: "the first bar can enter and close within the value area and the second bar opens within the value area"; marketcalls' variant: the test must occur within the first two 30-min periods (A/B), i.e. by 10:30.
  - Entry at the open of the period after confirmation (so typically 10:30 or 11:00), direction toward the far edge: short if re-entered from above VAH, long if from below VAL.
  - Stop: just outside the VA boundary at the re-entry point (metrotrade), standard distance 2-4 ES ticks beyond VAH/VAL; practitioners widen to 0.25 x VA width.
  - Target: the opposite VA boundary (full "fill"). Flat by 15:55 if not reached.
- **Parameters**: VA 70%; confirmation 2 x 30-min (variants 1 x 30-min, or two 15-min closes); max time to confirm 11:00-12:00.
- **Evidence**: name says 80% but every test found is lower: mypivots "testing on the E-mini S&P 500 has shown that this rule should probably be called the 60% rule"; a nexusfi member's TradeStation test ~62% completion (search snippet; thread blocked); pedrobraiti (recent 30-min sample): VA fully traversed 27-67%; tradealgo "55-65% win rates". No cost-adjusted P&L found. **Evidence quality: 2**.
- **Prop fit**: Mechanically attractive for the consistency rule: one trade, defined stop (small), target typically 0.7-1.5x the stop, ~60% completion -> expectancy around zero to mildly positive before costs unless the stop is tighter than the standard "just outside VA". Works only on balanced days; the two-period confirmation already filters out most open-drive days. Fully codeable from OHLC via TPO/time profile. Test with partial target (POC, which sits ~40-60% of the way) because completion falls sharply for the second half.
- **Sources**: https://www.mypivots.com/dictionary/definition/25/80-rule ; https://www.marketcalls.in/market-profile/market-profile-how-to-play-80-percentage-rule.html ; https://www.metrotrade.com/what-is-the-80-rule-in-futures-trading/ ; https://github.com/pedrobraiti/volume-profile-trading ; https://nexusfi.com/showthread.php?t=30847

## 4. Value-area acceptance breakout (open outside value, initiative continuation)

- **Origin**: Dalton open-type / "acceptance vs rejection" logic; tested as "VA Breakout (BRK)" by pedrobraiti; steady-turtle and tradealgo "trend-day: buy dips to VAH / sell rallies to VAL with 8-point stop".
- **Rules (standard)**:
  - Open above prior VAH (below VAL for shorts). Acceptance = price does **not** trade back inside the VA during the first two 30-min periods (09:30-10:30), or two consecutive 30-min closes above VAH.
  - Entry: at 10:30 if accepted, buy at market; or (pullback version) buy the first touch of VAH after 10:30 on a 5-min close back above it, stop 8 ES pts / 30 NQ pts below VAH (tradealgo), target 1 x VA width above VAH, runner trailed by 30-min lows; flat 15:55.
  - Skip if the gap from prior close > 1.2x ATR14 (large gaps have lower IB extension, tradingstats 56% vs 63-67% median).
- **Evidence**: pedrobraiti BRK OOS PF 1.38 SPY / 1.58 QQQ / 1.12 BOVA11, 0.96-0.99 Brazil singles (daily bars, not intraday). tradingstats: when the open is above the prior day's range ES single-up 40.7% vs single-down 33.2% (small bias), inside 37.7/29.9, below 36.3/30.4, i.e. the open-location bias is weak on its own. The strongest related statistic is the opening-candle continuation: a green 09:30-10:30 candle closes the NQ session green 73.9% (51/69) and a red one red 71.7% (edgeful, 6 months). **Evidence quality: 2**.
- **Prop fit**: Trend-day participation with a defined stop; a lower-frequency complement to section 2 (the two are mutually exclusive by the open-location filter). Runner exits give fat right tail; cap by taking 2/3 at 1 x VA width to protect the 50% rule.
- **Sources**: https://github.com/pedrobraiti/volume-profile-trading ; https://tradingstats.net/initial-balance-breakout-statistics/ ; https://www.edgeful.com/blog/posts/initial-balance-masterclass ; https://www.tradealgo.com/trading-guides/futures/futures-trading-strategies

## 5. POC reversion and naked-POC magnet

- **Origin**: Volume-profile community (Trader Dale, Fluxus, LuxAlgo "Naked POC as level", algobars "Naked POC Retest" template); tested as "POC Reversion (REV)" by pedrobraiti.
- **Rules**:
  - (a) **Intraday POC reversion**: prior-session POC (time-based). When price is > 0.5 x VA width away from the prior POC after 10:00 and a 5-min bar closes back toward it (reversal bar), enter toward the POC; stop 0.25 x VA width beyond the signal bar extreme; target POC. Skip on trend days (IB > 1.0x ATR).
  - (b) **Naked POC retest** (algobars): identify POCs of the last 5-10 sessions never revisited since their session ended; when price is below a naked POC and "momentum shifts" (price above VWAP, rising volume), go long targeting the naked POC; stop 1 ATR below entry or prior-session low (tighter); short mirror with stop at prior session high. Claimed 3-5R "from strong trend entries".
- **Evidence**: pedrobraiti POC-REV OOS PF 1.13 SPY / 1.63 QQQ, 0.85-0.99 elsewhere; volume-permutation test p = 0.002 SPY but 0.08 QQQ, > 0.8 Brazil. LuxAlgo: "there is no dependable fill rate to trade against mechanically"; "a naked POC can sit untested for weeks or months". No intraday futures backtest found. **Evidence quality: 1-2**.
- **Prop fit**: (a) is a legitimate target rule (the POC is where the day's time was spent; using it as a partial target for sections 2-3 is more useful than as an entry). (b) is a swing/magnet idea with open-ended timing; unsuitable as a standalone day-trade signal, usable only as an intraday target when a naked POC lies within the day's expected range (< 1 ATR away).
- **Sources**: https://algobars.com/strategy-templates/volume-profile/naked-poc-retest/ ; https://www.luxalgo.com/library/concept/naked-poc-as-level/ ; https://github.com/pedrobraiti/volume-profile-trading ; https://futuresindicators.com/learn/naked-pocs-magnets-in-the-market

## 6. Initial balance range extension with C-period close confirmation

- **Origin**: Steidlmayer/Dalton IB (first two 30-min periods, 09:30-10:30) and range extension; statistics from tradingstats.net "Initial Balance Breakout Statistics: ES & NQ 2015-2025" (1-minute, RTH, ES 2,686 days / NQ 2,833 days). Overlaps with the first-hour breakout in orb_session.md section 1.x; this section records the profile-specific rules and numbers.
- **Rules (objective)**:
  - IB = high/low of 09:30-10:30. ATR14 on daily RTH bars. IB tier: narrow < 0.5x ATR, normal 0.5-1.0x, wide 1.0-1.5x, extreme > 1.5x.
  - Confirmation entry: wait for the C period (10:30-11:00) to **close** above IB high (below IB low); buy at the 11:00 open (or on the first 1-min close beyond the IB high after 10:30 if you accept wick entries). Skip "extreme" IB days (6 ES / 13 NQ days only, 33% never break).
  - Stop: IB midpoint (aggressive) or IB high minus 0.25 x IB range (median MAE of breakouts is only 0.20-0.26 x ATR). Target: +0.5x IB range (38.2% ES by close unconditional, much higher when C-period confirmed), scale to +1.0x (ES 45.5% up / 50.0% down after C-period confirmation vs 18.8% / 20.5% unconditional). Flat 15:55.
  - Directional priors: if IB low formed first, single-up 52.5% vs single-down 17.0% (ES); if IB high formed first, single-down 44.8% vs single-up 24.0%. Shallow retracement (< 25% of IB) after the break closes in break direction 93.8% ES / 92.4% NQ; deep (>= 50%) only 24.8% / 23.9% with 52.7% / 46.3% double-breaks -> exit on a 50% retrace.
- **Key base rates (ES / NQ)**: any break 97.8% / 96.2%; single-up 38.3% / 40.6%; single-down 30.9% / 33.0%; double 28.7% / 22.6%; first break in C period 65.2% / 63.9%; C-period closes outside IB 33.7% / 32.8% of days; first break fails (closes back inside) 34.0% / 34.8%, upside fails 45.2% / 42.9%, downside fails 53.2% / 52.2%; IB high = RTH high 33.0% / 36.7%, IB low = RTH low 40.4% / 44.4%; median MFE/MAE from break ~1.1 (narrow/normal), 2.14 ES-up-wide, 0.64-0.86 extreme; narrow IB median extension 74.8% ES / 63.8% NQ. Year-by-year breakout rate never left 96.5-99.2% (ES) 2015-2025; median extension 2022-2025: ES 71.9/68.3/71.0/64.2%, NQ 60.8/59.3/54.7/50.6%.
- **Evidence quality: 3** (very large, consistent, 1-minute, multi-year; no P&L modelled).
- **Prop fit**: This is the cleanest OHLC-codeable structure in the family. With a 0.25x-range stop and 0.5x-range target, the implied payoff is 2:1 at ~45-50% hit (after C-period confirmation) before costs -> positive but modest; one trade per day, defined risk, suits consistency. Weak side is NQ (100% extension only 33% even after confirmation); ES is the better instrument. Gold: see section 10.
- **Sources**: https://tradingstats.net/initial-balance-breakout-statistics/ ; https://steady-turtle.com/knowledge/initial-balance-trading-strategy ; https://www.edgeful.com/blog/posts/initial-balance-masterclass

## 7. IB retest-and-continue (1.1x-1.2x extension pullback entry)

- **Origin**: tradingstats.net "Does Price Retest the Initial Balance - and What Happens Next?" (NQ/ES, Feb 2014-May 2026, 1-min, ~3,000 break-days each, long+short pooled).
- **Rules (objective)**:
  - After the first post-10:30 break of the IB, wait for price to reach extension 1.1x (IB high + 0.1 x IB range) or 1.2x. Then place a limit order at the broken IB level (long at IB high after an up-break), valid only if the first return happens between 10:30 and 12:00 and the move to the extension was "fast" (median arrival 5 min at 1.1x, 19 min at 1.2x; use < 30 min).
  - Entry on the first touch (90% of first returns hold within 10% of R of the level); add a 1-min rejection-wick confirmation if desired (+5 pp continuation: 71% vs 66% NQ; 75% vs 70% ES).
  - Stop: IB midpoint (failed retests reach the IB mid 69-81% of the time, the opposite IB edge 36-56%), or 0.25 x R below the level for a tighter 1:2.
  - Target: new high beyond the extension; median second leg +0.45R (NQ) / +0.56R (ES) beyond the prior high, 1 in 5 adds a full R. Practical target = prior extension high + 0.4R; flat 15:55.
- **Statistics (NQ, ES in parentheses)**: at 1.1x: reached 91%, ran away without retest 13%, retest -> continue 71% (77%), retest -> reverse 16%; return rate 87% (90%). At 1.2x: continue 52% (60%), reverse 22%, return 75% (81%). Crossover where reverse > continue: ~1.4x NQ, ~1.5x ES. Fast moves at 1.2x: continue 62% vs slow 42%. Time of day (1.2x): 10:30-12:00 continue 58% / reverse 20%; 14:00-16:00 continue 23% / reverse 32%. Narrow IB: 81% return, 73% continue; wide IB: 62% / 54%. Down-breaks return more often (81% vs 70%) with similar continuation.
- **Evidence quality: 3** (large sample, 12 years, no entry/stop/target modelled).
- **Prop fit**: High hit rate (70-77% continuation) with a stop at the IB mid (0.5R) and a modest target (0.4-0.5R beyond the prior high, i.e. ~0.5-0.6R from entry) -> roughly 1:1 at 70% = good expectancy, small daily P&L, exactly the consistency-friendly shape. Fully OHLC-codeable. Companion fade (>= 1.4x/1.5x, afternoon, slow) is in intraday_mean_reversion.md section 16.
- **Sources**: https://tradingstats.net/initial-balance-retest-statistics/

## 8. IB width / ATR regime filter (narrow-IB breakout, wide-IB fade)

- **Origin**: steady-turtle IB guide (1,586 NQ sessions, 5 years), tradingstats IB tiers, Dalton's "IB width tells you the day type".
- **Rules**: compute IB width / ATR14 (daily) at 10:30. Narrow tercile (< 0.5x ATR or lowest 20% of trailing 60-day IB widths): trade breakouts only (section 6/7); 41.1% reach 1x extension, median day range 1.91x IB (steady-turtle), 99.3% break, 84.5% median extension (tradingstats smallest-20%). Wide tercile: 15.5% reach 1x, median day range 1.51x IB -> fade IB edges (section 2 logic applied to the IB instead of the prior VA), or stand aside. Extreme (> 1.5x ATR): no trade.
- **Evidence quality: 3** as a conditioning statistic; **1** as a standalone P&L claim.
- **Prop fit**: not a strategy by itself; it is the gate that decides which of sections 2/3 (fade) or 4/6/7 (breakout) runs on a given day. Required for every IB/VA system here.
- **Sources**: https://steady-turtle.com/knowledge/initial-balance-trading-strategy ; https://tradingstats.net/initial-balance-breakout-statistics/

## 9. IB-by-rejection bias with ending-zone filter (IB75 / IB50 limit entries)

- **Origin**: edgeful.com reports: "IB by rejection deep dive", "Initial balance ending zone", "IB75 strategy", "IB masterclass" (NQ/ES, NY session, 5-min, 6-12 month samples 2025-2026).
- **Rules (objective)**:
  - At 10:30 record which IB extreme formed first. Bias: if the IB low formed first, expect the IB high to break first (NQ 78.5%, ES ~60-63%, GC 70.5%); if the high formed first, expect the low to break (NQ 77.4% in the deep dive, but only 50.8% in the 6-month masterclass sample; GC no edge 42/47%).
  - Ending-zone filter: express the 10:30 close as a % of the IB range measured from the side opposite the first-formed level. If the close is in the 0-24.99% zone (i.e. near the expected-break side), the bias improves to 86.6% NQ / 86.4% ES (67/66 sessions of 131). Masterclass: low-first + close near high -> high breaks first 90% (36/40); high-first + close near low -> low breaks 73% (22/30).
  - Entry (IB75 variant, contrarian case): when the IB closes in the 75-100% zone (pulled back toward the first-formed level), place a limit at the 75% level (25% away from the first-formed level), stop under the 50% midpoint, target = the first-formed level; 18 of 22 qualifying sessions (12 NQ, 10 ES, Aug 2025-Aug 2026) broke toward the target (81.8%), ~1 setup per month per instrument.
  - Entry (main variant): with bias confirmed, buy a limit at the 25% retracement into the IB from the expected-break side with stop at the 50% level (1:1 to the IB edge, 0.1 extension touched 91.9% / 0.2 extension 71.0% / 0.5 extension 43.6% on breakout days), or at 50% with stop at the far IB edge. Exit majority at 0.2 extension; flat 15:55.
- **Evidence**: 6-12 month samples (129-258 sessions), vendor-published, no costs, and the "high formed first" leg is unstable across samples (77% vs 51%). Hold-through-close is only 52-64% even when the break occurs. **Evidence quality: 2**.
- **Prop fit**: A natural filter on top of sections 6-7 (trade only the expected side). The limit-entry version has a tight stop (0.25-0.5 x IB) and a 1:1-ish target that is hit > 85% of the time in the vendor sample; if that survives 2015-2026 on our data it is an ideal consistency-rule trade. Must be re-validated over the full history because the samples are tiny.
- **Sources**: https://www.edgeful.com/blog/posts/ib-by-rejection-deep-dive ; https://www.edgeful.com/blog/posts/initial-balance-ending-zone ; https://www.edgeful.com/blog/posts/ib75-strategy ; https://www.edgeful.com/blog/posts/initial-balance-masterclass

## 10. Gold (GC) initial-balance breakout algos

- **Origin**: tradethatswing "Initial Balance Breakout Gold Day Trading Strategy" (Jan 2025-Jan 2026); edgeful "GC trading strategy: initial balance algo" (12 months to Jan 31 2026).
- **Rules (tradethatswing)**: IB 09:30-10:30. After a break of the IB high/low, enter 25% of the IB range **inside** the broken level (pullback limit); stop 60% of the IB range from entry; target 50% of the IB range measured from the IB high (longs) / low (shorts); 1 GC contract; RTH only.
- **Rules (edgeful)**: 5-min chart; entry on a 1% retracement after the IB high/low breaks; stop = 60% retrace back into the IB; TP1 0.25x IB beyond the break, TP2 0.5x; 2 GC contracts.
- **Results**: tradethatswing: 142 trades in ~250 days, win rate just over 50%, avg win ~$1,100 vs avg loss ~$600, +411% (later +445%) on $10k, MDD 25%; **author's July 2026 update: single-break rate fell to ~50/50 and "avoid until the data shows improvement"**. edgeful: WR 65.76%, PF 1.935, MDD 11.6%, +$105,890 on $50k with 2 contracts, no costs stated, author warns re-optimise monthly. **Evidence quality: 2** (vendor backtests, 1 year, in-sample, already decayed).
- **Prop fit**: Full-size GC on a $2k EOD trailing account is impossible (a 60%-of-IB stop on a $30-40 IB is $1,800-2,400 per contract); it has to be MGC (1/10 size) x 2-5. The 2025 gold trend produced the numbers; the author's own 2026 withdrawal is the honest OOS. Test only as a regime-gated variant (ATR rising, single-break rate over trailing 40 days > 70%).
- **Sources**: https://tradethatswing.com/one-trade-a-day-gold-strategy-411-in-last-year-fully-automatable/ ; https://www.edgeful.com/blog/posts/gc-trading-strategy-initial-balance-algo

## 11. Poor highs/lows, single prints and prior-day structure targets

- **Origin**: Dalton, *Markets in Profile* / *Mind over Markets* ("poor high/low", "excess", "single prints", "unfinished business").
- **Objective definitions (from 30-min TPO built from 1-min data)**:
  - Poor high = the session high row has >= 2 TPOs (touched in two or more 30-min periods) with no single-print excess tail above it; a "tail/excess" = >= 2 consecutive single-TPO rows at the extreme. Poor low mirror.
  - Single prints = rows inside the profile with exactly 1 TPO (fast directional movement); the range they span is a target when revisited (fill expected).
  - Rule A (repair): on the next session, a poor high is a *long* target/magnet (expected to be revisited and exceeded): buy a pullback after 10:00 when the day is trending up, target = poor high + 2 ticks, stop 0.25 x prior VA width below entry. Rule B: a tail/excess high is a *short* reference: fade the first retest with a 5-min close rejection, stop 2 ticks above the tail, target POC.
  - Rule C (single prints): when price re-enters a single-print zone, expect it to be traversed fully; enter on the first 5-min close inside the zone, target the other end, stop at the zone entry edge.
- **Evidence**: no quantified backtests found anywhere; youngmoneyinvestments explicitly: "I have not supplied any statistics". The closest quantitative support is tradingstats' extremes study (NQ/ES/YM/RTY 2019-2026, ~14,300 extremes per market): 58-59% of running session extremes fade at least halfway back toward the open; < 0.3 ATR from open 85% fade; > 1.0 ATR ~20%; and its "high-grade calls" classifier (70% hit, AUC 0.82 walk-forward 2021-2026, two 9-trade losing streaks in ~2,650 calls) which is proprietary. **Evidence quality: 1** for the Dalton rules, **3** for the extreme-fade base rates.
- **Prop fit**: Only usable as target/level logic for other sections; standalone it is discretionary. The "poor high repair" idea converts to an objective rule (prior-day high touched in >= 2 periods -> add it as a target for section 4/6 longs).
- **Sources**: https://tradingstats.net/high-of-the-day-hold/ ; https://youngmoneyinvestments.com/blog/es-futures-market-profile-guide ; Dalton, *Markets in Profile* (book)

## 12. Open-type classification as a day-type gate (open-drive / open-test-drive / open-rejection-reverse / open-auction)

- **Origin**: Dalton, *Mind over Markets* ch. 3 (standard definitions; ShadowTrader glossary blocked at fetch time).
- **Objective rules (standard interpretation on 1-min/5-min bars, 09:30-10:00)**:
  - Open-drive: price never trades back through the 09:30 open after the first 5 minutes and the first 30-min bar closes in the outer 25% of its range beyond yesterday's VA -> trend-day presumption, 85-90% confidence in Dalton's words (no numbers published).
  - Open-test-drive: price probes yesterday's high/low or VA edge within the first 15-30 min, fails, then drives through the open the other way (first 30-min bar's range has one wick > 40% of the bar beyond the open side).
  - Open-rejection-reverse: initial move > 0.25 x ATR followed by a reversal back through the open within 30 min -> balance / two-sided day.
  - Open-auction: first 30 minutes trade both sides of the open with no excursion > 0.2 x ATR -> rotational day, prefer fades (section 2).
  - Usage: open-drive/open-test-drive -> run sections 4/6/7 only, no fades; open-rejection-reverse / open-auction (inside yesterday's VA) -> run sections 2/3.
- **Evidence**: no published stats for the open types themselves; the nearest proxies are edgeful's opening-candle continuation (green first hour -> green close 73.9% NQ; red -> red 71.7%; 66-129 sessions) and tradingstats' first-30-min "open-above/inside/below prior range" table (weak). pedrobraiti: "day-types do not predict continuation". **Evidence quality: 1-2**.
- **Prop fit**: pure filter; cheap to code; test whether it improves the daily-P&L distribution of sections 2/6/7 rather than as a standalone.
- **Sources**: Dalton, *Mind over Markets* (book); https://www.edgeful.com/blog/posts/initial-balance-masterclass ; https://github.com/pedrobraiti/volume-profile-trading

## 13. Session VWAP trend trading (Zarattini & Aziz 2023, "VWAP: the Holy Grail for Day Trading Systems")

- **Origin**: SSRN 4631351 (Nov 2023), Concretum Research / Peak Capital Trading. Full PDF reviewed.
- **Rules (exact, from section 3 of the paper)**:
  - RTH-only VWAP from 09:30 (pre/post-market excluded). At 09:31:00, if price is above VWAP, buy at the open of the next 1-minute bar; if below, sell short.
  - Stop/reverse: exit (and reverse) only when a **1-minute candle closes** on the other side of VWAP; an intrabar cross does not trigger. Position is otherwise held to the 16:00 close. Always in the market after 09:31 (either long or short).
  - Sizing: 100% of equity, no leverage (R:R unknown because the stop is time-varying). Commission $0.0005/share; no slippage.
- **Results (QQQ, 2018-01-02 to 2023-09-28)**: $25,000 -> $192,656, +671%, 43%/yr, vol 18%, Sharpe 2.1, MDD 9.4% (early 2019), alpha 38%/yr (t > 5), beta ~0; 21,967 trades, hit ratio 17.0%, gain:loss 5.67, worst trade -1.4%, worst day -5.1%, best day +6.5%. TQQQ: +8,242%, 116%/yr, vol 54%, Sharpe 1.7, MDD 36.1%, 22,399 trades, commissions $400,619 (16% of the ending equity). Control: SMA9/20/100/200 versions of the same always-in system gave Sharpe 1.3/0.5/0.7/0.9 with MDD 41/42/17/21%, so VWAP specifically matters. Time of day: cumulative 1-share P&L ($600 over the period vs $200 for buy-and-hold) accrues almost entirely 09:30-12:00 and 15:00-16:00; "a more cost-efficient implementation may avoid trading between 12pm and 3pm". Above-VWAP minutes were 56% of minutes and carried the positive repricing; below-VWAP minutes carried negative repricing.
- **Replications / critiques**: none independent found. Zarattini-Barbon-Aziz 2024 (SPY noise-band paper, see trend_momentum.md section 1) used VWAP only as a trailing stop and found it doubled Sharpe (0.61 -> 1.24). Mesfin 2026 (MNQ 5-min, 2021-2025) shows a 2-point friction floor eliminates most sub-2-point 5-minute signals, which is the regime a 17%-hit, ~15-trades/day VWAP flip system lives in. **Evidence quality: 3** for QQQ (SSRN paper with full tables, no OOS, no slippage, single team), **1** for net futures tradability.
- **OHLC approximation**: VWAP -> session TWAP of typical price (or 1-min close average). Expect the proxy to lag true VWAP slightly in the first hour when volume is front-loaded.
- **Prop-fit variant to test** (our standard interpretation of the paper's own time-of-day finding): trade only 09:31-12:00 and 15:00-15:55; require a 5-minute (not 1-minute) close beyond VWAP to enter and to exit; skip re-entry within 10 minutes of a stop; daily loss cap $300-400 on MES/MNQ; flat 15:55. This cuts trade count by ~5-10x and the whipsaw commissions that the always-in version pays; it must still be checked against the 50% consistency rule because the profitable days are big trend days (worst/best day +/-5-6% of equity on QQQ).
- **Sources**: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4631351 ; https://concretumgroup.com/volume-weighted-average-price-vwap-the-holy-grail-for-day-trading-systems/ ; https://concretumgroup.com/wp-content/uploads/2026/02/Volume-Weighted-Average-Price.pdf ; https://arxiv.org/abs/2605.04004

## 14. VWAP standard-deviation band reversion (+/-2 sigma) with regime gates

- **Origin**: practitioner standard (Brian Shannon; LuxAlgo VWAP bands; crosstrade.io "VWAP Reversion"; ferroquant; StockSharp #0235). Core rules also in intraday_mean_reversion.md sections 1-2; this entry adds the gate parameters and the one rigorous individual test.
- **Rules (crosstrade.io, most specific public rule sheet)**:
  - Session VWAP from 09:30 with cumulative sigma bands. Setup: price extends >= 2 sigma from VWAP, then a rejection candle (pin bar / engulfing) on 5-min; market order at the next bar open.
  - Stop: 1 x ATR(14, 5-min) beyond the trigger bar extreme. Target: VWAP (optionally half at VWAP, trail the rest).
  - Mandatory filters: skip when ADX(14) on 5-min > 25; skip FOMC/CPI/NFP/ISM days; skip if the opening-hour range > 2x its 20-day average. Windows: 10:00-11:30 and 13:30-14:30; avoid 09:30-10:00, FOMC 14:00-16:00, Friday 14:30-16:00. Wednesday/Thursday best.
- **Claimed statistics**: win rate 55-65% with filters, 45% without; avg winner 0.8-1.2 x avg loser; PF 1.2-1.6; 2-5 trades/day on ES in good regimes (crosstrade, no sample stated). tradealgo "VWAP fade": entry 12+ ES pts above VWAP with reversal signal, stop VWAP + 20 pts, target VWAP, 55-65% WR (unsourced). ferroquant: 7 years tick data with walk-forward claimed, no numbers published.
- **Independent test**: nullh0/trading-strategy-postmortem (Micro WTI, long-only, buy when price deviates below session VWAP by a threshold, target VWAP-anchored, volatility-scaled stop, EOD flat, earliest-entry filter): 505 trades (~89/yr), WR 62.2%, +223.5%, MDD -12.6% notional, Sharpe 4.93, pooled OOS Sharpe 5.42, 13/15 walk-forward windows positive, bootstrap Sharpe CI [4.19, 6.89]; **author declined to deploy**: "I couldn't cleanly separate a real edge from an edge that exists only in this particular slice of history" (one month excluded, ~0.36 trades/day). Base-rate context (tradingstats extremes): excursions < 0.3 ATR from the open revert 85%, 0.3-1.0 ATR much less, > 1.0 ATR ~20%. **Evidence quality: 2**.
- **OHLC approximation**: TWAP + cumulative std of typical price, or k x ATR bands (StockSharp #0235 uses VWAP +/- 2 x ATR(14) on 5-min with exit at VWAP).
- **Prop fit**: many small trades, defined stops, target inside the day: consistency-friendly; the loss tail is trend days, hence the ADX/opening-range/news gates are not optional. Long-biased version first (the MR family found short fades lose in 2014-2026).
- **Sources**: https://crosstrade.io/learn/trading-strategies/vwap-reversion ; https://github.com/nullh0/trading-strategy-postmortem ; https://ferroquant.com/strategy/vwap-reversion ; https://tradingstats.net/high-of-the-day-hold/ ; https://www.tradealgo.com/trading-guides/futures/futures-trading-strategies

## 15. VWAP pullback continuation ("VWAP bounce" on trend days)

- **Origin**: Brian Shannon / practitioner standard; tradezella "VWAP bounce 55-65%, reclaim 50-60%, deviation scalp 60-70%, exhaustion 35-45%" target win rates (unsourced); tradinginvestingstrategies Substack "Institutional Pullback VWAP" (SPY 1h, RSI(2) < 30 at VWAP, 2017-01 to 2025-11: 254 trades, WR 45.67%, PF 1.692, +5.10% total, MDD 0.53%); tradealgo: "sustained positive VWAP slope in first hour -> continuation > 65% of the time".
- **Rules (standard objective interpretation)**:
  - Trend qualification at 10:30: every 5-min close since 10:00 above VWAP and VWAP slope positive (VWAP(10:30) > VWAP(10:00)); or the IB low formed first and C-period closed above IB high (section 6/9).
  - Entry: first pullback after 10:30 that touches VWAP (within 1 x 5-min ATR) and prints a 5-min close back above VWAP; buy at next open. One pullback per trend leg, max 2/day; no entries after 14:30.
  - Stop: VWAP - 0.5 sigma (or 1 x ATR(14, 5-min)) below VWAP. Target 1: session high; target 2: +1 sigma band; trail by VWAP close (Zarattini-Barbon-Aziz stop logic). Flat 15:55.
- **Evidence**: SPY hourly RSI(2) variant PF 1.69 (tiny edge per trade, 0.53% MDD); the VWAP-as-trailing-stop effect is peer-style (Sharpe 0.61 -> 1.24 on SPY 2007-2024); win-rate ranges quoted by vendors are not backed by samples. **Evidence quality: 2**.
- **OHLC approximation**: TWAP proxy; the slope test is robust to the proxy.
- **Prop fit**: good shape (tight stop under a reference, target at the day high, 1-2 trades/day); it is the trend-day complement of section 14 and shares the IB/open-type gate. Expect ~50-55% WR at ~1.3-1.8 R if the vendor numbers are honest; must be validated.
- **Sources**: https://tradinginvestingstrategies.substack.com/p/the-simple-vwap-strategy-pine-script-tradingview ; https://www.tradezella.com/blog/vwap-trading-strategy ; https://www.tradealgo.com/trading-guides/futures/futures-trading-strategies ; trend_momentum.md section 1 (Zarattini-Barbon-Aziz)

## 16. Anchored VWAP from prior-day extremes / event bars (Shannon, MIDAS)

- **Origin**: Paul Levine MIDAS (1995), Brian Shannon *Maximum Trading Gains with Anchored VWAP* (2023), LuxAlgo "Anchored VWAP as level"; scalpradar "Backtesting an anchored VWAP strategy" (ES 15-min, CPI anchor).
- **Rules (objective versions)**:
  - (a) **Dual prior-day AVWAP breakout** (forextester write-up, USDJPY): anchor one VWAP at the prior day's high bar and one at the prior day's low bar; long on a close above the upper AVWAP, short on a close below the lower; reverse on the opposite signal; flat 15:55 for our use.
  - (b) **AVWAP level trade** (LuxAlgo/Shannon): anchor at the most recent swing high/low of >= 1 x ATR or at the 09:30 open after a gap > 0.5 x ATR; entry = rejection wick or defended 5-min close at the AVWAP line in the direction of the anchor's trend; invalidation = 5-min close through the line ("acceptance"); target = prior session extreme.
  - (c) **Event AVWAP** (scalpradar): anchor at the 08:30 CPI bar; next day at 11:00 go long if the prior close was above the AVWAP, short if below; stop 25 ES pts, target 100 ticks (25 pts), 15-min bars.
- **Evidence**: (c) ES Dec 2022-Feb 2024: 11 trades, +$4,600, Sharpe 0.42, zero slippage, author calls it "a simplistic, naive algorithm". (a)/(b): no published statistics ("no quantitative validation is provided", LuxAlgo). **Evidence quality: 1**.
- **OHLC approximation**: anchored TWAP of typical price from the anchor bar.
- **Prop fit**: (b) is just a dynamic support/resistance variant of section 15 with an extra free parameter (the anchor); test only if section 15 works. (c) is too infrequent (~1 trade/month) to matter for the payout rule.
- **Sources**: https://scalpradar.com/blog/2024/03/backtesting-an-anchored-vwap-strategy/ ; https://www.luxalgo.com/library/concept/anchored-vwap-as-level/ ; https://forextester.com/blog/anchored-vwap/

## 17. Cumulative delta (CVD) divergence at a level

- **Origin**: Trader Dale ("Bulletproof cumulative delta strategy", "How to predict price reversals using cumulative delta"), LuxAlgo "Delta divergence", gocharting; universally cited by order-flow educators.
- **Rules (objective, LuxAlgo/Trader Dale)**:
  - CVD = cumulative (ask-executed volume - bid-executed volume), session-anchored. Swing pivots with a symmetric 2-5 bar window.
  - Bearish divergence: price higher high with CVD equal-or-lower high; bullish: price lower low with CVD higher low. Bar-level variant: bar closes up on negative delta (or down on positive delta).
  - Trader Dale: trade only when the divergence occurs **at a level** (4-hour volume-profile POC / heavy-volume zone or S/R); 1-min chart for entry, 5/15-min for context; long when price drops to the level and delta rises; "tight stop" beyond the level; target not specified (standard: prior swing / 1:1.5).
  - LuxAlgo: "divergences can stack repeatedly while a trend keeps running, so most order-flow traders wait for structure to break before trading against the move" -> add a 5-min structure break (close back above the last lower high) as the trigger.
- **Data requirement**: bid/ask-classified contract volume ("centralized tick-by-tick bid/ask data, not tick count"; TradingView tick-count CVD is not delta). **We have none.** The price-only proxy (sum of (C-O)/(H-L) x range per 1-min bar) is a close-location momentum line, not delta; divergence between it and price is simply a momentum divergence (RSI-like). Flag any backtest as "price-CVD".
- **Evidence**: no win rates anywhere ("hypothetical, NOT TRADED IN A LIVE ACCOUNT", Trader Dale); a YouTube single-day NQ test (+244 pts on 2024-11-11) is an anecdote; academic: arXiv 2508.06788 (ES, one-second OFI/return SVAR, 15-min windows) finds flow impact significant at the one-second horizon and "shocks dissipate almost entirely within a second", with flow impact *declining* around macro news; i.e. documented order-flow predictability is sub-second, not minutes. tradealgo quotes "60-70% win rate on setups with clear absorption or delta divergence" (unsourced). **Evidence quality: 1**.
- **Prop fit**: not codeable with fidelity. If tested at all, test the price-CVD divergence + level + structure-break version as a momentum-divergence entry and expect nothing special.
- **Sources**: https://www.trader-dale.com/how-to-predict-price-reversals-using-cumulative-delta-a-complete-guide/ ; https://www.trader-dale.com/the-bulletproof-cumulative-delta-trading-strategy-the-complete-guide-8th-nov-24/ ; https://www.luxalgo.com/library/concept/delta-divergence/ ; https://www.luxalgo.com/blog/cumulative-volume-delta-explained/ ; https://arxiv.org/abs/2508.06788

## 18. Absorption and exhaustion (footprint) at value-area edges

- **Origin**: order-flow education (Bookmap, Sierra Chart, Jigsaw, tradealgo "order flow trading" section); pedrobraiti's "Volume Exhaustion (EXH)" is the only quantified relative.
- **Rules (objective footprint versions)**: absorption = at a level, >= N consecutive price ticks where aggressive volume on one side is >= 3x the other yet price fails to move through (stacked imbalances absorbed), trade the fade of the aggressive side after a 1-min close back from the level, stop 2 ticks beyond the absorption extreme, target VWAP/POC. Exhaustion = volume climax bar (>= 2x 20-bar average) at a new extreme with delta flipping on the next bar, fade with stop beyond the climax wick.
- **OHLC-only proxies**: absorption ~ 1-min bar at a level with range >= 1.5x ATR(20, 1-min) whose close is within 20% of the open (effort without result); exhaustion ~ 5-min bar with range >= 2x ATR(14, 5-min) closing in the back 30% of its range at a new session extreme. These are candlestick patterns; they do not measure absorption.
- **Evidence**: pedrobraiti EXH (buy new lows on below-average volume, daily bars) OOS PF 1.51 SPY / 1.94 QQQ / 2.16 BOVA11, +1.80%/trade QQQ, the strongest sleeve in that study and the one that passed the volume-permutation test on SPY (p = 0.002) - but it needs volume and is daily. tradealgo "60-70%" unsourced. **Evidence quality: 1** (intraday), 2 (daily with volume).
- **Prop fit**: not reproducible; the candlestick proxies may be tested as confirmation filters for sections 2 and 7 only.
- **Sources**: https://github.com/pedrobraiti/volume-profile-trading ; https://www.tradealgo.com/trading-guides/futures/futures-trading-strategies ; https://www.luxalgo.com/library/concept/delta-divergence/

## 19. Footprint stacked-imbalance continuation

- **Origin**: footprint-chart vendors (Sierra Chart, NinjaTrader Order Flow+, gocharting); rule: >= 3 stacked diagonal bid/ask imbalances (ratio >= 300%) on consecutive price levels in a bar mark initiative buying/selling; trade continuation on the first pullback into the stacked zone, stop below the zone, target 1:2.
- **Data**: per-price bid x ask volume. **No OHLC approximation exists.** **Evidence quality: 1** (no public backtest with numbers found).
- **Prop fit**: excluded from the backtest; listed for completeness.
- **Sources**: https://gocharting.com/docs/orderflow/delta-and-cumulative-delta-bars ; https://www.luxalgo.com/library/concept/delta-divergence/

## 20. NYSE TICK extremes (fade and trend-confirmation)

- **Origin**: Linda Raschke / Steve Rhodes / "Trading the TICK" practitioner lore; standard thresholds +/-800 (ordinary extreme), +/-1000 (fade candidates on rotational days), +/-1200-1500 (trend-day confirmation, do not fade); the first hour's TICK high/low and the cumulative TICK (sum of 1-min TICK closes) as a day-type gauge.
- **Rules (standard)**: on days whose cumulative TICK is near zero by 10:30 (balanced), fade ES on a 1-min TICK print <= -1000 with a 1-min close back above the signal bar low, stop 1 tick below the extreme bar, target VWAP or +0.25 x ATR; skip when the 09:30-10:00 TICK made a new extreme beyond +/-1200 (trend day) and instead buy pullbacks (section 15) only while cumulative TICK stays positive.
- **Data**: NYSE TICK (breadth, $TICK) - **not in our data and no OHLC proxy**. A 1-min ES return z-score fade is a different (and weaker) signal; the MR family already covers z-score fades with negative public evidence for shorts.
- **Evidence**: no public cost-adjusted backtest located (searches blocked; CXO had no TICK article). **Evidence quality: 1**.
- **Prop fit**: excluded from the backtest.
- **Sources**: Raschke & Connors, *Street Smarts* (book, "TICK" chapter notes); https://www.cxoadvisory.com/?s=NYSE+TICK (no results)

## 21. Gap into prior close / prior POC as a profile-target trade (cross-reference)

- **Origin**: edgeful "How often gaps fill on NQ" (NY session, 6 months, 131 gaps); the prior close is also usually inside the prior value area and within ~0.3 x VA width of the prior POC, so a gap fill is the profile trader's "return to value".
- **Numbers**: NQ overall full fill 55.0% (gap-ups 52.6%, gap-downs 58.2%); gaps < 0.4% of price (~118 NQ pts): 25%-fill 100%, 50% 96.4%, 75% 96.4%, full 92.9% (56 gaps); gaps >= 0.4%: 25% 77.3%, 50% 49.3%, full 26.7% (75 gaps). ES: small gaps 66.2% full fill (77 gaps), large 28.3% (53). Rule used: enter at 09:30 against the gap, stop 0.5% past the open (held on 48/52 filled small gaps), target full fill for small gaps, 25% of the gap for large gaps.
- **Evidence quality: 2-3** (6-month sample here; multi-year gap statistics are in intraday_mean_reversion.md section 7). Prop fit and full rules: see that report; the profile-specific addition is to use the prior POC (not just the prior close) as the second target when the open is outside the prior VA.
- **Sources**: https://www.edgeful.com/blog/posts/how-often-gaps-fill-nq

## 22. Volume-profile (session fixed-range POC) retest with POC-distance filter - XAUUSD example

- **Origin**: sonu71072/XAUUSD-Volume-Profile-Backtest (M5 gold CFD, tick volume, two sessions; V7/V8).
- **Rules**: previous completed session's 100-bin fixed-range profile (70% VA). Signal candle closes with body ratio >= 0.70 at/through the POC in the direction of the close; enter next open; stop 1R (session-based), target +2R; one trade per session; sessions 03:30-06:00 IST (~17:00-19:30 ET prior evening) and 18:55-19:55 IST (08:25-09:25 ET). V8 adds |entry - POC| / |entry - stop| <= 0.20.
- **Results**: V7 full sample 59 trades, WR 37.3%, PF 1.19, +7R; OOS (2025-09-12 to 2026-09-11) 27 trades, PF 1.00, 0.00R, MDD -5R. V8: full 31 trades, WR 48.4%, PF 1.88, +14R; OOS 13 trades, WR 53.8%, PF 2.33, +8R - but the filter threshold was chosen on the full sample. Costs (V3): a medium cost model turned an earlier version's -18.7R into -33.5R. Author: "does not establish a positive out-of-sample edge". **Evidence quality: 2** (honest, tiny).
- **Prop fit**: the lesson is the cost sensitivity and the sample size; the only transferable rule is "signal candle closing through the POC with body >= 70% of range, entry next bar, fixed 1R/2R" which we can test with the time-at-price POC on GC RTH.
- **Sources**: https://github.com/sonu71072/XAUUSD-Volume-Profile-Backtest

---

## 23. What the evidence says works in 2022-2026

1. **Time-structure base rates are stable and recent**: tradingstats' IB breakout rate stayed 96.5-99.2% (ES) every year 2015-2025, median extension 64-72% in 2022-2025 (ES) and 50-61% (NQ); the retest study runs to May 2026 and the C-period-confirmation / retest-continuation conditionals are the strongest OHLC-codeable statistics in this family. edgeful's 2025-2026 samples (IB by rejection 78%, ending-zone 86%, IB75 18/22) point the same way but are small. **Build the IB systems first (sections 6, 7, 9, gated by 8/12).**
2. **Volume-profile geometry does not survive adversarial testing** (pedrobraiti, data to June 2026): no sleeve's PF bootstrap CI excludes 1.0, no alpha over exposure, 80% rule 27-67%. The time-based VA is still useful as a *target map* (POC, VA edges) for the IB and VWAP trades and as the balance/imbalance day filter (open inside vs outside value) - treat it as a lens, as that study concludes.
3. **VWAP**: the only paper-grade result (QQQ 2018-2023, Sharpe 2.1) is an always-in, 17%-hit flip system whose profits sit in 09:30-12:00 and 15:00-16:00; on micro futures with a 2-pt NQ friction floor the raw version should be assumed dead and only the two-window, 5-min-close-confirmed variant tested. VWAP band fades have vendor win rates (55-65% with ADX/news gates) and one rigorous but self-shelved individual test (MCL, Sharpe 4.9, long-only). The 2019-2026 extremes study (85% fade < 0.3 ATR, ~20% > 1.0 ATR) tells us band fades must be distance- and regime-gated and long-biased.
4. **Gold IB breakouts printed spectacular 2025 numbers (PF 1.9, +400%) and the author withdrew the strategy in July 2026** as the single-break rate collapsed to 50/50 - a live example of regime dependence inside our prime window. Gate GC/MGC IB trades on a trailing single-break rate.
5. **Order flow**: no cost-adjusted public evidence at the 1-minute horizon; the academic ES evidence (2025) locates flow predictability at the one-second scale. Delta/absorption/footprint/TICK are out of scope for an OHLC backtest and should be labelled "not reproducible" rather than approximated and over-sold.
6. **Costs decide**: Mesfin 2026 (MNQ 2021-2025): 11 of 14 five-minute signal families failed only because gross < 2.0 NQ pts/trade; the XAUUSD VP test lost 15R more under a medium cost model. Every strategy here must clear >= 1 tick/side slippage + commissions on micros; anything averaging < 1.5 ES pts / 6 NQ pts gross per trade is not worth coding.

## 24. Ranked candidates for the Lucid 50K Flex backtest (this family)

| Rank | Strategy | Section | Why |
|---|---|---|---|
| 1 | IB retest-continuation at 1.1-1.2x, 10:30-12:00, stop IB mid, target +0.4-0.5R | 7 | 70-77% continuation, 12-yr 1-min sample, ~1:1, one trade/day, consistency-friendly |
| 2 | IB C-period close-confirmed extension, 0.25x stop / 0.5x-1.0x target, ES first | 6 | 45-50% reach 100% ext after confirmation vs 19-20% base; defined risk |
| 3 | IB-by-rejection + ending-zone limit entry (IB75 / 25%-retrace with stop at 50%) | 9 | 86-90% directional bias in 2025-26 samples; must be re-validated on 2015-2026 |
| 4 | Time-based value-area edge-to-edge rotation on open-inside-value, narrow/normal-IB days | 2 | defined stop, POC partial target, fits balance days; kill on trend days |
| 5 | VWAP(TWAP-proxy) two-window trend trade, 5-min close confirmation, daily loss cap | 13 | paper-grade QQQ evidence, time-of-day structure; friction risk |
| 6 | VWAP-band long-biased fade with ADX < 25 / opening-range / news gates | 14 | vendor 55-65% WR; distance-gated by the extremes study |
| 7 | VWAP pullback continuation on IB-confirmed trend days | 15 | tight stop, day-high target; complements 14 |
| 8 | 80% rule with POC partial target | 3 | ~60% completion on ES; low expectancy unless stop is tight |
| 9 | GC/MGC IB breakout, gated on trailing single-break rate | 10 | great 2025, dead mid-2026; regime-gate only |
| - | CVD divergence, absorption, footprint, TICK | 17-20 | not reproducible from OHLC; excluded |
