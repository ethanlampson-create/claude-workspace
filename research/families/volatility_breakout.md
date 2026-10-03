# Family: Volatility-Based Breakout and Compression/Expansion Strategies

Research sweep date: 2026-10-03. Scope: Larry Williams volatility breakout (open + k x prior range / ATR), Crabel stretch ORB and ORBP, NR4 / NR7 / inside-day / 2-bar-NR conditioning, Bollinger/Keltner squeeze (TTM squeeze), ATR-channel and Keltner breakouts, volatility-contraction patterns, expansion-bar continuation, volatility regime classifiers and VIX / realized-vol percentile filters, expansion-day targeting, and the published parameter studies that exist for them. All times are US Eastern (ET).

Target use: Lucid Trading 50K LucidFlex (eval target $3,000; $2,000 END-OF-DAY trailing drawdown checked intraday; 50% consistency rule in eval; funded: no consistency rule, EOD trailing locks at $50,100 once EOD balance reaches $52,100; payout needs 5 days with >= $150 EOD profit; min payout $500, max 50% of profit capped at $2,000; day-trade only). Data available: 1-minute OHLC without volume for ES/NQ/GC proxies, 2010-11 to 2026-09; crude NOT available 2024-2026; daily futures and VIX from Yahoo.

Method note: 12 web searches were run (the session search budget then closed); ~30 pages were fetched, including the full text of Holmberg-Lonnbark-Lundstrom (2013, crude oil ORB) and Mesfin (2026, MNQ falsification study, arXiv 2605.04004). quantifiedstrategies.com, SSRN, ScienceDirect, ResearchGate, forexfactory and medium blocked automated fetches; where only a search snippet was available this is stated.

---

## 0. Executive summary

1. **The family's core claim (contraction precedes expansion) is real; the tradable edge from it is small and mostly below futures friction.** Independent, cost-aware tests published 2023-2026 are uniformly negative for *raw* breakouts: Fetna (SSRN 7428398, 2026) pre-registered 225 ORB cells on nine US futures over 16 years, gross +$1.57M, net -$6.49M at $25/round-trip, zero cells positive, median gross edge -0.01 tick/trade. Mesfin (arXiv 2605.04004, 2026) on MNQ 2021-2025 (947 days, 5-min bars, 2.0 pt/$4 round-trip friction, expanding walk-forward): eleven of fourteen OHLCV signal families have gross edge 0.07-1.50 pts/trade, below the friction floor; **chasing 5-minute range-expansion bars is actively wrong** (Asia-session bar with range > 1.5x the 20-bar average, next-bar continuation: T = -11.52, N = 1,955), because the move completes inside the signal bar. Oxford Strat's 1980-2016 tests of Crabel's stretch ORB, NR7-ORB and 2-bar-NR-ORB on 42 futures all rate "C": positive gross, "not currently tradeable" after $50/RT without additional rules; the mirror-image wide-range breakout rates "D" (PF 0.74, CAGR -5.1%, MDD 88%, win 23.8%).

2. **The one peer-reviewed positive result for a Williams-style threshold breakout is Holmberg, Lonnbark & Lundstrom (Finance Research Letters 2013)**: crude oil 1983-2011, threshold = open x (1 +/- rho) with rho set from the normal quantile of close/open log-returns, EOD exit, no stop, zero costs. Full sample long at the 1% tail: 188 trades, 61.2% winners, mean +0.258%/trade (p = 0.0001); at the 0.1% tail 80 trades, 71.3% winners, +0.403%. **The whole edge is in the high-volatility sub-sample 2001-2011** (1% long: 50 trades, 80% winners, +0.516%; 1992-2001: 62 trades, 58% winners, +0.084%, n.s.). Tightening the threshold raises both hit rate and mean return while cutting trade count. This is the cleanest statement of what the family can do: a *large* threshold (roughly 1.7-2.3 sigma of the daily open-to-close move), EOD exit, in a high-volatility regime.

3. **Conditioning beats triggering.** The robust statistics in this family are about *when* expansion happens, not which way: inside days on ES/NQ broke the prior day's range in the next NY session 87.8% (ES, 65/74) and 88.4% (NQ, 61/69) of the time in the six months to mid-2025 (edgeful); on NQ, opening above the prior-day midpoint reached the prior high 67% of the time, opening below reached the prior low 58%. tradingstats (6,142 ES/NQ sessions 2014-2025) found ATR regime changes continuation rates by < 1.8 percentage points - **volatility scales the dollar size of a breakout, not its probability**. The direction has to come from somewhere else (open vs. prior midpoint, prior-day close direction, trend filter), and the breakout should be sized in ATR units.

4. **Squeeze indicators (TTM, Bollinger bandwidth, Keltner) have no credible published intraday futures evidence.** Quantified Strategies' long-sample Bollinger-squeeze test "doesn't do particularly well for any asset" (PEP 1975-2026: 12.5% CAGR vs 14.8% buy-and-hold, 61% exposure); their Larry Williams volatility-channel breakout on SPY 1993-2026 was "poor" as trend-following and only marginal as mean-reversion (0.69%/trade, MDD 33%, PF < 1.75). TradeSearcher's audit of 2,036 TradingView "Volatility Breakout Strategy" runs: only 10 of 185 adequately-sized runs pass its quality gate, robustness score 18/100, "cannot be told apart from chance". The 2025 Gold (XAUUSD daily, long-only) results on mql5 (+35% to +60% for the year, win rate 48-55%) are gross, long-only, in a year gold rose ~60%: beta, not alpha.

5. **For the Lucid 50K rules the best-shaped candidates are**: (a) NR7 / ID-NR4-conditioned stretch ORB on ES or NQ, traded only 09:30-11:30 ET, EOD or capped exit, 1x-stretch stop, direction from open-vs-prior-midpoint; (b) a Williams open + k x prior-range breakout with k in 0.3-0.5 of yesterday's range (or the Holmberg 1%-quantile threshold), one attempt per day, prior-day down-close filter for longs, stop 0.5x range, EOD exit; (c) inside-day "range target" trade (long toward yesterday's high when the open is above yesterday's midpoint, stop at the midpoint, target the prior high - ~0.4x prior range median extension); (d) volatility percentile used **only for sizing and for a daily-loss cap**, not as an entry filter. Anything that holds to the close with no target produces a few huge days and many small losses, which collides with the eval's 50% consistency rule; a capped target of 0.4-0.5x the prior day's range (the median post-break extension on ES/NQ is 36-43% of the prior bar's range) converts the family's fat right tail into the many-small-green-days profile the payout rule wants.

---

## 1. Larry Williams volatility breakout (open + k x prior range)

### 1.1 Canonical rule (Williams, "Long-Term Secrets to Short-Term Trading", 1999; WH SelfInvest / NanoTrader implementation)

- **Origin**: Larry Williams; the 1987 Robbins World Cup result ($10k -> $1.1M) is the anecdote usually attached to it. The free WH SelfInvest / NanoTrader "L.W. Volatility Break-out" system is the most widely distributed fully specified version.
- **Rules (NanoTrader version, exact)**:
  - Range_y = High[yesterday] - Low[yesterday] (daily bar).
  - Buy stop at Open_today + 0.25 x Range_y; sell stop at Open_today - 0.25 x Range_y. Runs on a 5-minute chart; the first stop hit is the position.
  - Profit target and stop loss both at 2 x the "break-out range" (i.e., 2 x 0.25 x Range_y = 0.5 x Range_y) from entry.
  - Time filter: any open position is closed at 21:59 CET = **15:59 ET**.
- **Williams' own text (standard interpretation)**: k between 0.5 and 0.7 of yesterday's range added to today's open; exit at the next day's open or on a bailout stop; trade-day-of-week (TDW) filters; prefer longs after a down close (the "range expands after contraction / after a down day" argument). No stop is specified in the book version beyond "the first profitable opening" exit.
- **Parameters**: k in {0.25, 0.5, 0.7}; stop/target multiples {0.5x range, 1x range, 2x k-range}; exit time 15:59 ET.
- **Evidence**: WH SelfInvest shows equity curves for DAX, Dow, NASDAQ, S&P 500, CAC 40, Bund ("profits are variable but none are negative"), no numbers, no costs. TradeSearcher audit of 2,036 TradingView backtests of the "Volatility Breakout Strategy" (close + k x (H-L), enter next open, stop at midpoint of prior low and entry, EOD exit): 185 runs with > 15 trades, 10 pass the quality gate, average t-stat 2.63 but p = 0.14, robustness 18/100, verdict "its average result can't be told apart from chance"; the best runs are single crypto-miner stocks on 1-2H bars. Quantified Strategies' SPY 1993-2026 test of Williams' *volatility channel* (close crosses above the N-day channel, N = 2..10) found the trend-following version "poor" and the mean-reversion version only marginal (0.69%/trade, MDD 33%, PF < 1.75).
- **Evidence quality**: 2 (famous, widely coded, but no cost-aware futures test that survives; the one audit says "chance").
- **Prop fit**: Shape is acceptable (one trade/day, stop and target defined, flat at 15:59). With k = 0.25 and 2x-k-range brackets the stop is 0.5 x yesterday's range - on ES in 2025 (daily range ~50-70 pts) that is 25-35 pts = $1,250-1,750 per mini, so **micros only** (10 MES = 1 ES; use 2-4 MES so a stop is $250-500). The time exit creates fat right-tail days; cap the target at 0.4-0.5x yesterday's range to fit the 50% consistency rule.
- **Data requirements**: daily OHLC + 1-minute bars; no volume needed.
- **Sources**: https://www.whselfinvest.com/en-lu/trading-platform/free-trading-strategies/tradingsystem/56-volatility-break-out-larry-williams-free ; https://www.best-trading-platforms.com/trading-platform-futures-forex-cfd-stocks-nanotrader/larry-williams-volatility-break-out-strategy ; https://tradesearcher.ai/strategies/1666-volatility-breakout-strategy ; https://www.quantifiedstrategies.com/larry-williams-volatility-strategy/ (fetched via reader) ; https://www.ebc.com/forex/larry-williams-strategy-wr-cot-signals-2026

### 1.2 Williams breakout, mql5 "Market Secrets" automation (Parts 5, 6, 8) - prior-range and swing-range variants

- **Origin**: mql5.com article series (2026), MQL5 expert advisors, tested on XAUUSD daily bars with 1-minute crossover detection.
- **Rules (Part 5, exact)**: Range_y = iHigh(1) - iLow(1) on the daily chart. Buy level = Open + Range_y x BuyMult; sell level = Open - Range_y x SellMult; detection by crossover on 1-minute data (not anticipatory stop orders). Stop = entry -/+ Range_y x StopMult. Target = stop distance x RewardMult. One position at a time, no stacking; direction switch long/short/both.
- **Rules (Part 6, swing-based range)**: Swing1 = |High[3 days ago] - Low[1 day ago]|, Swing2 = |High[1 day ago] - Low[3 days ago]|; working range = max(Swing1, Swing2); entry/stop/target as above using the swing range. Long only, 1% risk per trade.
- **Rules (Part 8, structure + time filters)**: entry only when the last three daily bars form a Williams short-term swing low (bar 2 is the extreme, no inside/outside bars) for longs; volatility model switchable between swing range and yesterday's range; optional trade-day-of-week and time-of-day windows; 2% auto risk.
- **Evidence (all XAUUSD daily, $10,000 start, long-only, 2025)**: Part 5: Jan 1 - Nov 30 2025 net +$6,203 (~+60%). Part 6: Jan 1 - Dec 31 2025 net +$4,450 (+44%), win rate 48.39%. Part 8: Jan 1 - Dec 30 2025 net +$3,711 (+35%), win rate 54.55%. No profit factor, drawdown, trade counts or cost assumptions disclosed; gold itself rose roughly 60% in 2025, so long-only results are dominated by beta.
- **Evidence quality**: 2 (one instrument, one year, long only, no costs, in-sample parameters).
- **Prop fit**: Daily-bar system with multi-day holds as published - violates no-overnight. Convertible to intraday by forcing a 15:55 ET exit, which the 1-minute detection already supports. Gold (MGC) is available in our data; the swing-range version (max of two 3-day swings) gives a larger, more stable range unit than yesterday's range alone and is worth carrying into the backtest as an alternative "volatility unit".
- **Data requirements**: daily OHLC + 1-minute bars.
- **Sources**: https://www.mql5.com/en/articles/20745 ; https://www.mql5.com/en/articles/20862 ; https://www.mql5.com/en/articles/21003

### 1.3 Williams VBO with trend filter and entry cutoff (practitioner / open-source variants)

- **Origin**: rusty_trader `stratlab/strategies/vbo.py` (GitHub, 2026, SPY/QQQ/megacaps 5-min 2021-2026) and freqtrade `LWBreakout.py` (nateemma/strategies).
- **Rules (rusty_trader, exact)**: trigger_long = Open_today + k x (High_y - Low_y), trigger_short symmetric; k default 0.5 (0.25-0.70 tested); entry on the first 5-minute bar whose high >= trigger, **only if the bar time is <= 11:30 ET** (late breakouts "empirically fail"); trend filter: long only if Open_today > SMA20(daily closes, shifted 1 day), short only if below; hold to EOD, flatten on the 15:55 bar; one entry per day per name; costs IBKR tiered + 1 bp slippage each side. Validation split 2021-2023 IS / 2024-2026 OOS with k in {0.3, 0.5, 0.7} and cutoff in {11:00, 11:30, 12:00}.
- **Rules (freqtrade LWBreakout, exact)**: buy_level = open + 0.66 x ATR(60 bars); sell_level = open - 0.15 x ATR(60); enter on close crossing above buy_level if (buy_level - sell_level)/close > 0.2%; exit on close crossing below sell_level. Crypto, hyper-optimised.
- **Evidence**: the rusty_trader docstring cites "documented multi-asset backtests: PF 1.15-1.35 raw, 1.35-1.60 with trend filter, Sharpe 0.85-1.25" attributed to Quantified Strategies archives; the result files could not be fetched and the numbers are unverified. Treat as a parameter prior only.
- **Evidence quality**: 1-2.
- **Prop fit**: Good shape for Lucid: one trade/day, direction from a daily trend filter, entry cutoff 11:30 ET avoids afternoon chop, EOD flat. Needs a stop (none in the open-source version) - use 0.5 x prior range or 1 x ATR(14, 5-min).
- **Data requirements**: daily + intraday OHLC.
- **Sources**: https://github.com/RyanTYT/rusty_trader (stratlab/stratlab/strategies/vbo.py) ; https://github.com/nateemma/strategies (SimpleStrategies/LWBreakout.py)

### 1.4 Holmberg, Lonnbark & Lundstrom (2013): normal-quantile ORB threshold on crude oil - the peer-reviewed version of 1.1

- **Origin**: "Assessing the profitability of intraday opening range breakout strategies", Finance Research Letters 10 (2013), Umea University working paper ues845. Full text fetched.
- **Rules (exact)**: Let R_t = log(Close_t / Open_t). rho_alpha = mu_hat + sigma_hat x q_alpha, where mu_hat and sigma_hat are the mean and SD of R_t and q_alpha is the standard-normal quantile (alpha = 10%, 5%, 1%, 0.5%, 0.1% tail). Upper threshold psi_u = Open x (1 + rho), lower psi_l = Open x (1 - rho). If High_t > psi_u a long was established at psi_u; if Low_t < psi_l a short at psi_l; **all positions closed at the day's close; no stop, no target**; perfect fill at the threshold, zero spread, zero commission. Returns R_long = log(Close/psi_u), R_short = -log(Close/psi_l). Significance by a co-integrated OHLC bootstrap (Brock et al. 1992 style). rho is estimated on the full sample (ex post), which the authors acknowledge.
- **Data**: US crude oil futures, CSI continuous, 1983-03-30 to 2011-01-26, 6,976 days; daily return SD 0.72%.
- **Results (Table 2)**:

| Sample | alpha | rho (%) | Long N | Long win% | Long mean % | p | Short N | Short win% | Short mean % | p |
|---|---|---|---|---|---|---|---|---|---|---|
| Full 1983-2011 | 10% | 0.94 | 738 | 60.6 | 0.202 | 0.0000 | 826 | 54.2 | 0.144 | 0.0000 |
| | 1% | 1.69 | 188 | 61.2 | 0.258 | 0.0001 | 224 | 62.1 | 0.244 | 0.0003 |
| | 0.1% | 2.24 | 80 | 71.3 | 0.403 | 0.0010 | 98 | 62.3 | 0.249 | 0.0147 |
| 1983-1992 | 1% | 1.41 | 72 | 48.6 | 0.114 | 0.125 | 73 | 57.5 | 0.198 | 0.056 |
| 1992-2001 | 1% | 1.10 | 62 | 58.1 | 0.084 | 0.036 | 79 | 53.2 | -0.026 | 0.68 |
| 2001-2011 | 1% | 2.32 | 50 | 80.0 | 0.516 | 0.006 | 64 | 64.1 | 0.388 | 0.0006 |
| 2001-2011 | 10% | 1.30 | 245 | 66.1 | 0.281 | 0.0000 | 300 | 59.7 | 0.248 | 0.0000 |

  - Both hit rate and mean return rise as the threshold tightens; the authors attribute the whole effect to the high-volatility 2001-2011 decade ("market volatility and ORB profitability should be expected to go hand in hand").
- **Evidence quality**: 4 (peer-reviewed, bootstrap significance, 28 years) but **gross of all costs, in-sample threshold, no stop**, crude only. On crude in 2001-2011 a 1% threshold was ~$0.60-0.90 per barrel, and the mean +0.5% ($0.30-0.45) per trade is ~10x a $25 round-trip, so the net edge would have survived costs in that decade.
- **Prop fit**: Mechanically ideal (one entry per day at a known level, EOD exit) but the no-stop EOD exit gives a wide daily P&L distribution. We cannot test crude 2024-2026; the method transfers directly to ES/NQ/GC: compute rho from a rolling 250-day window of close/open log returns, use the 1% quantile (roughly 2.3 sigma of the open-to-close move; on ES with sigma ~0.8% that is ~1.8%, i.e. ~110 pts in 2025 - which rarely triggers) or the 5-10% quantile (~1.3-1.6 sigma) for a usable trade count, add a stop at the open and a 15:55 ET exit.
- **Data requirements**: daily OHLC + 1-minute (for the actual fill and stop).
- **Sources**: http://www.econ.umu.se/ueslpnr/ues845.pdf ; https://www.sciencedirect.com/science/article/abs/pii/S1544612312000438 ; https://api.semanticscholar.org/graph/v1/paper/41976a41fcd90c259cda953560bef07f601f7741

### 1.5 Generic ATR breakout from open/close (Kaufman-style; "Intraday Volatility Breakout Blueprint")

- **Origin**: Perry Kaufman, "Trading Systems and Methods" (volatility breakout chapter: entry at prior close +/- k x ATR(n), k ~1-3 on daily bars - standard interpretation); crackingmarkets.com "Intraday Volatility Breakout Blueprint" (2025); StockSharp "ATR Range Breakout".
- **Rules (crackingmarkets, exact where given)**: ATR = average daily range (length unspecified; use 14); breakout levels = prior close +/- k x ATR with k = 0.33 as the example; long above the upper level, short below the lower; **one breakout attempt per market per day**; fixed stop 0.33 x ATR; exit at end of day. Context filter: only trade after a "narrow day / low-volatility contraction" with a trend filter and a "volatility expansion pattern"; the filtered version is claimed to have 3x the expectancy per trade and 6x fewer trades. Instruments SPY, QQQ, IWM, GLD, TLT; commission $0.005/share; no win rate, PF or drawdown published.
- **StockSharp ATR Range Breakout**: measures the price move over N bars and opens a position when the move exceeds ATR; vendor claims "about 169%/yr" with no details - ignore the number.
- **Evidence quality**: 1-2 (blog claims, no tables).
- **Prop fit**: Same shape as 1.1 with ATR instead of yesterday's range; the "one attempt per day + 0.33 ATR stop + EOD" rule set is codeable and gives a small, bounded daily loss (0.33 x ATR14 on ES ~ 20 pts = $100/MES). Good micro candidate; the narrow-day pre-filter is the NR4/ID conditioning of section 2.
- **Data requirements**: daily + 1-minute OHLC.
- **Sources**: https://www.crackingmarkets.com/intraday-volatility-breakout-blueprint/ ; https://www.nuget.org/packages/StockSharp.Strategies.0044_ATR_Range.py

---

## 2. Crabel stretch ORB, ORBP and narrow-range conditioning

### 2.1 Crabel stretch ORB (base) and ORBP (one-sided preference)

- **Origin**: Toby Crabel, "Day Trading with Short Term Price Patterns and Opening Range Breakout" (1990) and the 1988-1989 Stocks & Commodities ORB series (V6:9, V7:4, V7:5). Independent implementation and 35-36-year test by Oxford Strat.
- **Rules (exact, Oxford Strat / Crabel)**:
  - Noise_i = min(High_i - Open_i, Open_i - Low_i); Stretch = SMA(Noise, 10) x Stretch_Multiple (Crabel 1.0; Oxford Strat tests 1.0 and 2.0).
  - Buy stop at Open + Stretch; sell stop at Open - Stretch; the first fill is the position, the other becomes the protective stop; if both fire the same day it is one losing trade, no reversal.
  - Crabel's own exit: same-day close (day-trade) - "take profits quickly, usually at the close of the first day or on the first profitable close". Oxford Strat tests N-day close exits (N = 1..40/50), a "stretch exit" (opposite stretch level of the entry day) and an ATR(20) x 6 stop.
  - **ORBP** (preference): in a market with a directional bias take only the one-sided stop; cancel it if the opposite stretch is hit first; the protective stop goes in only after the fill. Oxford Strat's two filter versions: price channel (long only if High > highest high of the last L days, L in 2..100) and momentum (long only if Close > Close[L bars ago], L in 2..100).
  - Crabel's qualitative rules (x-trader summary of the book): the earlier in the session the stop fills, the better (ideally within the first 10 minutes); best preceding patterns are Inside Day, NR days (including dojis), bear/bull hooks and ID-NR combinations; **never take an ORB after a Wide Spread (WS) day**; in S&P "ORB II" is a wide, strongly directional first 5-minute bar - place stops near the open and cancel everything not filled within 5-10 minutes.
- **Evidence**: Oxford Strat, 42 US futures 1980-2015/16, $1M, 1% fixed-fractional: without costs the stretch ORB is positive across the sensitivity grid; with $50/RT commission and slippage it is "not currently tradeable without some additional rules"; rating **C**. The price-channel and momentum filters "improve the base ORB" and "longer holding periods are preferred" - i.e., the daily-exit version is the weakest. No tabulated PF/Sharpe were published for the C-rated pages; for the mirror-image **Wide Range N-Day pattern + stretch ORB** (breakout after the widest 2-day range of the last 20) the published base case with $50/RT is net -$873,375, Sharpe -1.45, PF 0.74, CAGR -5.09%, MDD 88.3%, win rate 23.8%, rating **D** - direct confirmation of Crabel's "no ORB after wide spread" rule.
- **Evidence quality**: 3 (long multi-market independent test; costs applied; but no published numbers for the C-rated versions and the 42-market portfolio is not an index day-trade).
- **Prop fit**: The day-trade stretch ORB is codeable to the tick from 1-minute data (Open = 09:30 ET print; stretch from the last 10 daily sessions). Stretch on ES in 2025 is ~10-15 pts, so a 1x-stretch stop is $500-750/ES or $50-75/MES: well inside a $300-400 daily loss budget with 4-6 MES. The failure mode is the ~45% of days where both stops fire; the ORBP filter (take one side only, from open-vs-prior-midpoint or a 10-day momentum) is the published fix.
- **Data requirements**: 1-minute OHLC (session open, intraday extremes) + daily series.
- **Sources**: https://oxfordstrat.com/?p=8118 ; https://oxfordstrat.com/trading-strategies/orbp-with-price-channel-filter/ ; https://oxfordstrat.com/trading-strategies/orbp-trend/ ; https://oxfordstrat.com/trading-strategies/wide-range-pattern/ ; https://www.x-trader.net/descubriendo-a-toby-crabel-ii/ ; https://www.x-trader.net/descubriendo-a-toby-crabel-iii/ ; https://store.traders.com/-v06-c09-playing-pdf.html ; https://store.traders.com/-v07-c04-orb-pdf.html

### 2.2 NR7 + stretch ORB and NR7 + prior-day-range breakout

- **Origin**: Crabel (1990); Oxford Strat "NR7 Pattern (Setup & Exit)" and "Price Breakout with NR7 Pattern" (Connors/Raschke-style entry).
- **Rules (exact)**:
  - Setup: today's daily range (H-L) is narrower than each of the previous six days' ranges (NR_Length = 6 -> NR7; tested 1..20).
  - Entry A (stretch ORB): next day buy stop at Open + Stretch (SMA10 of noise x 2.0), sell stop at Open - Stretch; first fill is the trade, the other is the stop; no same-day reversal.
  - Entry B (price breakout): next day buy stop one tick above the NR7 day's high, sell stop one tick below its low; the other side is the protective stop.
  - Exits tested: close of day N (N = 1..40), stretch exit, ATR(20) x 6 stop.
- **Evidence**: 42 US futures, 1980-01 to 2016-01, $1M, 1% fixed fractional: pattern "performs better when NR_Length >= 6", longer holds preferred; **without costs viable, with $50/RT "not currently tradeable without some additional rules"**; rating **C** for both entry versions, "similar performance". Quantified Strategies' NR7 article (blocked; snippet) reports NR4 tests of "60% or better in all but two, none above 70%" for next-day outcomes. rusty_trader's docstring cites "SPY 1993-recent, NR7 + 200-day SMA + Donchian break: 75-77% win, PF 2.30-2.35, ~0.45%/trade, MDD 13-19%, 3-5 day hold" attributed to Quantified Strategies - unverified, and a multi-day swing, not a day trade. The same repo's own intraday test notes "NR7 has 87% win but PF < 1 because the 13% losers are large" before adding a stop at the NR7 low.
- **Evidence quality**: 3 for "NR7 raises the odds of a range-expansion day", 2 for any tradable day-trade P&L.
- **Prop fit**: NR7 occurs on ~15-20% of days, so a pure NR7-only system gives 3-4 trades/month per instrument - too few to accumulate 5 x $150 days quickly, but fine as the "safe" overlay (NR7 or ID on any of ES/NQ/GC gives ~1 setup every 2 days). The large-loser problem means a hard stop (NR7-day low/high or 1x stretch) and a capped target are mandatory.
- **Data requirements**: daily OHLC + 1-minute.
- **Sources**: https://oxfordstrat.com/trading-strategies/nr7/ ; https://oxfordstrat.com/trading-strategies/price-breakout-nr7/ ; https://www.quantifiedstrategies.com/nr7-trading-strategy-toby-crabel/ ; https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/narrow-range-day-nr7 ; https://github.com/RyanTYT/rusty_trader (stratlab/stratlab/strategies/nr7.py)

### 2.3 2-bar NR (xBNR) + stretch ORB

- **Origin**: Crabel (1990) "x Bar Narrow Range"; Oxford Strat "Toby Crabel - 2-Bar NR Pattern".
- **Rules (exact)**: Setup: the 2-day range (highest high - lowest low of the last two days) is the narrowest of any 2-day range within the previous 20 days (Look_Back = 20, NR_Size = 2). Entry: next day buy stop at Open + Stretch, sell stop at Open - Stretch, Stretch = SMA10(noise) x 2.0. Exits tested: Nth-day close (1..40), target = Target_Index x initial risk (1.0..10.0), stretch exit, ATR(20) x 6 stop.
- **Evidence**: 42 US futures, 1980-2013 (33 years), rating **C**; with $50/RT performance "degradation illustrated"; no tabulated numbers.
- **Evidence quality**: 3 (same caveats as 2.2).
- **Prop fit**: Rarer than NR7 (~5-8% of days); use as a confidence tier for sizing (e.g., 2x the normal micro count on xBNR days), not as a stand-alone.
- **Sources**: https://oxfordstrat.com/?p=8118 ; https://oxfordstrat.com/trading-strategies/toby-crabel-narrow-range-2/

### 2.4 ID/NR4 (Connors & Raschke, "Street Smarts", 1995)

- **Origin**: Linda Raschke and Larry Connors, "Street Smarts" ch. "ID/NR4"; built on Crabel's inside-day + NR4 combination ("the IDnr4 is the highest-probability ORB setup Crabel identified" - luxalgo library summary).
- **Rules (standard interpretation of the book)**: Setup day = inside day (H < H[1] and L > L[1]) AND NR4 (range < each of the previous three days' ranges). Next day: buy stop one tick above the setup day's high and sell stop one tick below its low. On a fill, the opposite stop stays as a stop-and-reverse. If the trade is not profitable within two days, exit. Trail the stop. (Book gives examples only; no statistics.)
- **Evidence**: Quantifiable Edges on SPY: all inside days 2001-2008 (215 instances) closed lower the next day 54% of the time, mean next-day move -0.2% (avg loss 0.9%, avg gain 0.6%); inside days with down closes (104) closed down 58% of the time with losses 2.1x gains; an "outside day then inside day" setup had an edge only in the 1990s and "a complete flatline" since 1999; inside days below the 200-day MA had a steady bearish edge through 2010 that "has not provided a downside edge" over 2009-2011. **Net: the daily direction after an inside day is at best weakly bearish and unstable; the expansion itself is the reliable part.** Edgeful (six months to mid-2025, NY session 09:30-16:00 ET): after an inside day price broke out of yesterday's range 87.84% of the time on ES (65/74) and 88.41% on NQ (61/69).
- **Evidence quality**: 2 for the trading rules (book), 3 for the expansion statistic.
- **Prop fit**: The stop-and-reverse clause is the problem for a trailing-drawdown account (two losses in one day). Use the one-sided version: direction from open-vs-prior-day-midpoint (see 2.5), stop at the opposite side of the ID/NR4 bar or 1x stretch, target the prior day's high/low, flat by 15:55 ET.
- **Data requirements**: daily OHLC + 1-minute.
- **Sources**: https://www.luxalgo.com/library/concept/nr4-nr7-narrow-range-bars.md ; https://quantifiableedges.blogspot.com/search?q=inside+day ; https://www.edgeful.com/blog/posts/inside-day-in-trading-breakout-data

### 2.5 Inside-day range-target trade with open-vs-midpoint bias (edgeful 2025)

- **Origin**: edgeful.com "inside day in trading: what the breakout data says across ES, NQ, TSLA, NVDA" (2025); the directional statistic matches the overnight/London midpoint statistics in the ORB family report.
- **Rules (objective version of the article)**: Yesterday was an inside day. Today, if the 09:30 ET open is above yesterday's midpoint, go long on the first 1-minute close back above the open (or at 09:31 at market) with target = yesterday's high and stop = yesterday's midpoint (or 0.5 x yesterday's range, whichever is tighter); if the open is below the midpoint, mirror short toward yesterday's low. Flat at 15:55 ET or on target/stop.
- **Evidence**: NQ, six months to mid-2025: open above the midpoint -> prior high reached 67% of the time; open below -> prior low reached 58%; range broken either side 87.8% (ES) / 88.4% (NQ). No P&L published; sample 69-74 sessions.
- **Evidence quality**: 2 (short sample, no costs, vendor), but consistent with 11-year statistics on session midpoints.
- **Prop fit**: Very good shape: high-probability target that is typically 0.3-0.6x yesterday's range away, a defined stop, and a flat-by-close rule. On an inside day yesterday's range is small, so both target and stop are small ($100-300 per MES-equivalent lot), which is the "many small green days" profile the payout rule rewards.
- **Data requirements**: daily OHLC + 1-minute.
- **Sources**: https://www.edgeful.com/blog/posts/inside-day-in-trading-breakout-data

### 2.6 WR7-down -> NR7 (Quantifiable Edges)

- **Origin**: Rob Hanna, Quantifiable Edges, 2008-2009 studies on NDX (back to 1986) and S&P 500.
- **Rules (exact)**: Day 1 is a wide-range-7 day (range wider than each of the previous six) with a lower close; Day 2 is an NR7 day (range narrower than each of the previous six). Go long at Day 2's close; exits tested at 1, 3 and 5 days.
- **Evidence**: NDX since 1986: average next-day gain "over 10x a normal day" (normal day = +0.06%), 3-day gain "over 5x" normal, high win rate and average win > average loss; updated 2009 with "a decent upside edge over the next week-plus"; sample sizes not stated.
- **Evidence quality**: 2 (blog, small samples, no costs).
- **Prop fit**: Not a day trade. Use only as a next-day long-bias input for the breakout direction (ORBP long-only on the day after a WR7-down/NR7 pair).
- **Sources**: https://quantifiableedges.blogspot.com/search?q=NR7

---

## 3. Squeeze, channel and compression indicators

### 3.1 TTM Squeeze (John Carter)

- **Origin**: John Carter, "Mastering the Trade" (2005); thinkorswim TTM_Squeeze study; TradingView "NA-GPT TTM Squeeze Strategy" (long-only, 21-SMA trailing stop).
- **Rules (exact, luxalgo / thinkorswim)**: Bollinger Bands = SMA(20) +/- 2 x SD(20); Keltner Channels = EMA(20) +/- 1.5 x ATR(20). Squeeze ON when both Bollinger bands are inside the Keltner channel; squeeze OFF ("fire") on the first bar where the Bollinger bands move back outside. Momentum histogram = linear regression (length 20) of (close - midpoint), midpoint = average of the Donchian(20) midpoint and SMA(20). Entry on the first squeeze-off bar in the direction of the histogram; exit when the histogram fades toward zero (or, in the TradingView strategy, on a 21-SMA cross). thinkorswim's "alert line" is the band-width ratio threshold.
- **Evidence**: no credible intraday futures backtest found. Quantified Strategies' Bollinger-squeeze test (rules paywalled) concluded it "doesn't do particularly well for any asset, perhaps except consumer staples"; PEP 1975-2026: 12.5% CAGR vs 14.8% buy-and-hold, 61% exposure, MDD 26%. One GitHub ensemble (TTM squeeze + ADX + XGBoost + HMM) on Pakistan equities claims 66.7% win / 106.7% over 10 years - not applicable.
- **Evidence quality**: 1.
- **Prop fit**: Codeable from OHLC on 5-minute bars; squeeze states are infrequent and often "cycle on and off through chop" (luxalgo). Not a primary candidate; could be an additional compression flag for the intraday stretch ORB (e.g., require a 5-min squeeze-ON state at 09:30-10:00 before taking the breakout).
- **Data requirements**: intraday OHLC only.
- **Sources**: https://www.luxalgo.com/library/concept/ttm-squeeze.md ; https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/T-U/TTM-Squeeze ; https://www.tradingview.com/script/9pbRIoJQ-NA-GPT-TTM-Squeeze-Strategy/ ; https://www.quantifiedstrategies.com/bollinger-band-squeeze-strategy/ ; https://github.com/FatalEmperor/psx-squeeze-ensemble

### 3.2 Bollinger bandwidth / BB-vs-ATR squeeze (ProRealCode screener form)

- **Rules (exact)**: bbs = 2 x SD(close, 20) / (1.6 x ATR(20)); squeeze when bbs < 1 (Bollinger half-width below 1.6 ATR); more meaningful when it persists several bars; pair with a trend filter (e.g., SMA50 > SMA200) for direction; breakout = close outside the Bollinger band after the squeeze. Luxalgo percentile convention: bandwidth percentile over 252 bars < 20 = compression.
- **Evidence**: none quantitative; the QS Bollinger-squeeze result above applies.
- **Evidence quality**: 1.
- **Prop fit**: compression flag only.
- **Sources**: https://www.prorealcode.com/prorealtime-market-screeners/bollinger-bands-squeeze-screener-daily-volatility-compression-with-atr-ratio/ ; https://www.luxalgo.com/library/concept/volatility-percentile-rank.md

### 3.3 Keltner channel breakout (intraday)

- **Origin**: Chester Keltner (1960) / Linda Raschke's ATR version; StockSharp "Keltner Channel Breakout" (5-minute default), mql5 EAs.
- **Rules (exact, StockSharp defaults)**: EMA(20) +/- 2 x ATR(14) on 5-minute bars; long on a close above the upper band, short below the lower; exit when price crosses back through the EMA or on the stop.
- **Evidence**: vendor claims "about 58% average annual return, best in stocks" and "18 years of 99%-quality tick data" for an MT5 EA on EURUSD; no PF/DD/trade tables; nothing on ES/NQ/GC.
- **Evidence quality**: 1.
- **Prop fit**: A 2-ATR Keltner break on 5-minute bars is a late entry (the move has already travelled 2 ATR from the mean) - the same "move completed inside the signal bar" problem Mesfin documents. Not recommended as an entry; the 1.5-ATR Keltner band is useful as the squeeze reference in 3.1.
- **Sources**: https://doc.stocksharp.com/en/api-examples/0007_Keltner_Channel_Breakout ; https://www.mql5.com/en/market/product/63119

### 3.4 ATR-channel / ATR-compression breakout (NQ 60-min; "ATR Volatility Compression")

- **Origin**: medium.com/coding-nexus "ATR Volatility Compression: A Winning Breakout Strategy With Python" (NQ 60-minute bars); FMZ "ATR Channel Squeeze Breakout"; tradingcode.net ATR channel breakout. Pages blocked (403); rules below are the standard reading of the search summaries.
- **Rules (standard interpretation)**: compression = ATR(14) at its lowest of the last N bars (or ATR(14)/ATR(100) below a threshold such as 0.7); after compression, buy a break of the highest high of the compression window, sell a break of the lowest low; stop = 1 x ATR(14) (or the opposite side of the window); target = k x ATR (FMZ uses ATR-based TP/SL); FMZ adds a momentum confirmation (e.g., RSI or MACD sign) and a channel = SMA +/- m x ATR.
- **Evidence**: none verifiable (the pages could not be fetched; search summaries describe NQ 60-minute results without numbers).
- **Evidence quality**: 1.
- **Prop fit**: 60-minute bars give too few setups and multi-day holds; on 5-15-minute bars within RTH it becomes an intraday compression breakout that is codeable, but the evidence that it beats the simpler NR/ID daily conditioning is absent.
- **Sources**: https://medium.com/coding-nexus/atr-volatility-compression-a-winning-breakout-strategy-with-python-8aba9008a65b ; https://medium.com/@FMZQuant/atr-channel-squeeze-breakout-strategy-volatility-breakout-trading-system-with-momentum-indicator-be10b8784ee9 ; https://www.tradingcode.net/tradingview/atr-channel-breakout/

### 3.5 Volatility Contraction Pattern (VCP) intraday (StockSharp)

- **Rules (vendor defaults)**: sequence of narrowing ranges on 5-minute bars (lookback 20), MA(20) for exits; entry on a break above the highest high / below the lowest low of the contraction; exit on a cross of the MA or stop. Vendor claims "about 166% average annual return, best in stocks"; no details.
- **Evidence quality**: 1.
- **Prop fit**: not a candidate as published; the Minervini VCP is a multi-week equity pattern.
- **Sources**: https://stocksharp.com/store/strategies.0043_vcp/

### 3.6 Session "volatility bands" breakout (HunterBreakOut, NQ)

- **Rules (vendor)**: session open range + volatility bands around it; entry on a close beyond the band during the 09:30 ET window; fixed stop and target. Backtest: NQ, 533 trades, 66% win, ~$34,000 net, period/costs/drawdown undisclosed.
- **Evidence quality**: 1 (vendor).
- **Sources**: https://huntersalgo.com/guides/best-nq-breakout-strategy

---

## 4. Expansion-bar continuation and volatility-regime classifiers (the 2026 MNQ falsification study)

### 4.1 Expansion-bar continuation (Mesfin 2026, Asia session) - NEGATIVE RESULT

- **Origin**: Mathias Mesfin, "Structural Limits of OHLCV-Based Intraday Momentum Signals in MNQ Futures: A Systematic Falsification Study", arXiv 2605.04004 (May 2026). MNQ 5-minute RTH bars Dec 2021 - Aug 2025 (947 days) plus Asia session 20:00-02:00 ET; friction 2.0 MNQ pts ($4) per round trip; expanding walk-forward (train 2022 -> test 2023; train 2022-23 -> test 2024; train 2022-24 -> test Jan-Aug 2025); pass = OOS T >= 2, >= 30 trades per fold, positive net, same sign in all three OOS years, permutation p < 0.001.
- **Rules (exact)**: in the Asia session, a 5-minute bar whose range exceeds 1.5x / 2.0x / 2.5x the rolling 20-bar average range; enter at the next bar's open in the bar's direction; hold 1 or 6 bars.
- **Results (Table 5, net of 2 pts)**: 1.5x/b+1: N 1,955, gross -0.27, net -2.27 pts, T = -11.52; 1.5x/b+6: net -2.08, T = -4.86; 2.0x/b+1: N 778, net -2.35, T = -7.42; 2.5x/b+6: N 340, gross +1.06, net -0.94, T = -0.90. The author's companion measurement: mean move from the expansion bar's open to the next bar's open +32.24 pts in the expansion direction, but from the bar's close to the next open -0.17 pts - "the directional move exists but is entirely consumed within the breakout bar".
- **Evidence quality**: 4 (walk-forward, net of friction, large N) - as a negative.
- **Implication for the family**: any rule that waits for a *completed* expansion bar on 5-minute (or coarser) data and then enters is structurally late. Entries must be resting stop orders at a pre-computed level (open + k x range, stretch, prior-day high/low) that fill *during* the expansion, and 1-minute bars are needed to simulate that fill honestly.

### 4.2 Volatility-regime classifier days (VVG) - fade vs. follow the opening move

- **Rules (exact)**: VVG fires when, simultaneously, |first-30-minute return|, |overnight gap| and first-bar volume deviation from a 20-day baseline are all in the top tercile of their expanding-window distributions (~4.4% of days). Reversal entry = fade the opening direction; continuation = follow it; a 15:30 ET close-fade variant.
- **Results (net)**: reversal: N 35, mean +13.49 pts, T = 1.26, by year 2023 -11.45 / 2024 +8.35 / 2025 -22.76; continuation: -17.49 pts, T = -1.64, 2023 -49.00 / 2024 +37.00 / 2025 +18.76. Classifier-positive days are "genuinely distinct" (25.6 bp next-day return spread, 77.6% peak-reversal rate) but "no fixed directional rule survives across all three test years".
- **Evidence quality**: 3 (walk-forward but N = 35).
- **Data requirements**: **needs volume** (first-bar volume deviation) - can only be approximated by the two price conditions (|first-30-min return| and |gap| in the top tercile).
- **Prop fit**: regime flag only. The practical lesson is that the highest-volatility opens are the days a fixed breakout rule gets whipsawed; a daily loss cap and reduced size on top-tercile-gap days is the Lucid-compatible use.

### 4.3 The MNQ friction ceiling and the two positive controls

- Eleven of fourteen OHLCV families have gross edge 0.07-1.50 pts/trade on 5-minute MNQ, below the 2.0-pt friction floor; the ORB long with a 15-bar (75-minute) hold is the best single-bar family (gross +4.82, net +2.82 pts, T = 0.88, by year +2.43 / +7.04 / +15.05). The two signals that pass all five gates (RTH Confluence: OOS T = 3.11, +11.82 pts, N = 196, 61% win; London Session B: OOS T = 4.30, +4.09 pts, N = 247, 61.5% win, exit at 60 min or 08:30 ET) both use Gaussian-mixture regime classification with 60-75-minute holds, and London B's edge **flips sign with a one-bar (15-minute) entry delay** (T +4.30 -> -2.78). Both use volume features.
- **Sources**: https://arxiv.org/abs/2605.04004 ; https://arxiv.org/pdf/2605.04004

### 4.4 Pre-registered 225-cell ORB study (Fetna 2026) - cost floor for the whole family

- **Origin**: Mulham Fetna, "Opening-Range Breakout Does Not Survive Trading Costs: A Pre-Registered 225-Cell Study on Sixteen Years of Futures Data", SSRN 7428398 (2026). Only the abstract (search snippet) was accessible.
- **Design**: nine liquid US futures, 16 years, 225 fully specified ORB variants (range lengths x entry types x exits), $25 per round trip.
- **Results**: gross +$1.57M on the confirmation window, net -$6.49M; **0 of 225 cells** meet the pre-registered positive bar; median gross edge -0.01 tick per trade.
- **Evidence quality**: 4 (pre-registered, multi-market, costs) - as a negative.
- **Implication**: any candidate from this family must show a gross edge of at least ~1.5-2 ES pts (6-8 NQ pts, $0.5 GC) per trade in our own 1-minute test before costs, or it is noise.
- **Sources**: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7428398

---

## 5. Volatility regime filters and expansion-day targeting

### 5.1 ATR / VIX / realized-vol regime as an entry filter - what the data say

- **tradingstats (ES/NQ, 6,142 sessions 2014-2025)**: 15- and 30-minute ORB continuation rates differ by <= 1.7 pp between low, normal and high ATR regimes; double-break rates within 1.8 pp. What changes is range width: ES 5-minute OR 7.00 pts (low ATR) vs 11.25 pts (high), +61%; ES 30-minute OR 9.00 vs 15.00, +67%. "The edge is not in the points, it is in the percentages."
- **Holmberg et al. (crude 1983-2011)**: the threshold-breakout edge is concentrated in the high-volatility decade 2001-2011 (1% long: 80% winners, +0.52%/trade vs 58% / +0.08% in 1992-2001). Interpretation: with a *fixed* cost per trade, higher volatility raises the gross edge per trade relative to cost; the probability of continuation does not need to change.
- **Zarattini-Aziz QQQ ORB replication (ORB family report)**: 76% of the filtered P&L came from 2022, the high-VIX year.
- **Mesfin VVG**: top-tercile gap / first-30-minute days behave differently but with unstable sign.
- **Convention for a percentile filter (luxalgo)**: percentile = share of the last 252 daily readings at or below today's (more robust than min-max rank); < 20 = compression, > 80 = stress; calibrate by bucketing strategy P&L by percentile at entry rather than adopting the thresholds blindly. Parkinson (log high/low) realized vol is a more efficient intraday estimator than ATR.
- **Objective filter candidates for the backtest**: (i) VIX close yesterday in its 252-day percentile bucket (Yahoo ^VIX); (ii) ATR(14)/close percentile; (iii) yesterday's range / ATR(14) (< 0.7 = NR-like compression; > 1.5 = wide spread, skip per Crabel); (iv) overnight gap / ATR(14) (> 1.0 = top-tercile-like, reduce size).
- **Evidence quality**: 3 (the "no effect on continuation probability" result and the "edge scales with vol relative to fixed costs" result are each supported by one large independent dataset).
- **Prop fit**: Use regime for **sizing and risk**, not for direction: contracts = floor(daily_risk_budget / (stop_in_ATR x ATR14 x $/pt)), with the daily risk budget <= $300-400 on a $2,000 trailing drawdown; skip days where yesterday's range > 1.5 x ATR(14) (Crabel WS rule; Oxford Strat D-rating).
- **Sources**: https://tradingstats.net/orb-strategy-research/ ; http://www.econ.umu.se/ueslpnr/ues845.pdf ; https://www.luxalgo.com/library/concept/volatility-percentile-rank.md ; https://arxiv.org/abs/2605.04004

### 5.2 Expansion targeting: how far price runs after a break (tradingstats 2014-2026)

- **Study**: ES and NQ continuous futures 2014-2026, bars 1H/4H/8H/12H/daily/weekly (tens of thousands of lower-timeframe bars; ~630 weekly bars per instrument). Extension measured as a percentage of the prior bar's own range beyond the broken high.
- **Results (median / 85th / 99th percentile extension)**: NQ 1H 39% / 105% / 335%; NQ 4H 43% / 119% / 342%; NQ daily 36% / 91% / 214%; ES 1H 40% / 100% / 307%; ES 4H 42% / 114% / 328%; ES daily 36% / 87% / 239%.
- **Use**: after a daily-range break (the Williams / ID / NR trades above) a target of 0.35-0.40 x yesterday's range beyond the broken level is reached about half the time; 0.9-1.2x only ~15% of the time. This is the quantitative basis for capping targets at ~0.4x prior range to satisfy the consistency rule, and for not expecting 2x-range targets (the NanoTrader default) to be hit often.
- **Evidence quality**: 3.
- **Sources**: https://tradingstats.net/price-extension-after-breakout/

### 5.3 Daily-range-vs-ATR "exceed or respect" statistics (edgeful ATR report)

- Edgeful publishes per-ticker rates of the daily range exceeding the prior ATR but the numbers are platform-only; the useful objective idea is the "ATR exhaustion" rule: once today's range has already reached 1.0 x ATR(14), stop taking breakout entries in the direction of the day's move (the remaining expected extension is small). Evidence quality 1 (method only).
- **Sources**: https://www.edgeful.com/blog/posts/atr-average-true-range-report ; https://www.edgeful.com/blog/posts/atr-zones-indicator-tradingview

---

## 6. Other published parameter studies and negative results worth keeping

- **Williams volatility channel (Quantified Strategies, SPY 1993-2026)**: long when close crosses above the N-day channel (N = 2..10) - "poor"; the inverse (buy a cross below the lower channel, N = 10) 0.69%/trade, MDD 33%, PF < 1.75, ~40% exposure. Evidence 2. Not intraday.
- **Donchian + ATR risk management (Poluri, SSRN 6272239)**: abstract not accessible; daily trend-following with ATR stops/sizing; listed for completeness.
- **NSE intraday breakout block study (Wang & Gangwar, SSRN 5198458)**: not accessible (403); Indian equities.
- **TradingView "Universal Breakout Strategy" (KedArc Quant)**: ~35% win rate at ~1.8 reward/risk - typical shape of an unconditioned breakout.
- **Inside-day fade statistics (Quantifiable Edges)**: see 2.4 - the next-day *direction* after an inside day was mildly bearish 2001-2008 and flat after 2009.

---

## 7. What the evidence says works in 2022-2026

1. **Raw breakouts of any volatility unit do not clear futures friction** on their own. The three cost-aware studies that overlap our prime window (Fetna 2026: 0/225 cells; Mesfin 2026: 11/14 families below the 2-pt MNQ floor, ORB-long best at T = 0.88; the mql5 five-index replication in the ORB family report) agree, and they agree with Oxford Strat's 36-year "C" ratings for Crabel's stretch ORB and NR7. Expect the unconditioned version of every strategy in this file to be flat-to-negative on ES/NQ 2025-2026 after $4-5 per MES/MNQ round trip.

2. **Entering after a completed expansion bar is actively negative** (T = -11.5 on 1,955 MNQ Asia-session trades). All entries in this family should be resting stop orders at levels known before the session (open +/- k x range, open +/- stretch, prior-day high/low), filled from 1-minute data, with the entry window limited to 09:30-11:30 ET (rusty_trader's cutoff; Crabel's "the earlier the fill, the better").

3. **The compression statistic is robust; the direction statistic is not.** Inside days expanded beyond the prior day's range 87.8% (ES) / 88.4% (NQ) of the time in 2025; NR7 / 2-bar NR days have been "C-rated" positive gross for 36 years. But next-day direction after an inside day is a coin flip or mildly bearish (QE), and the volatility-classifier days flip sign year to year (Mesfin). Direction has to be imported: open above/below the prior-day midpoint (67% / 58% target-hit rates on NQ 2025; 76-83% session-high-first rates in the ORB family data), prior-day close direction, or a 10-20-day momentum/price-channel filter (Oxford Strat's ORBP improvements).

4. **Volatility should set size, not permission.** Continuation probability is flat across ATR regimes (tradingstats); the gross edge per trade scales with volatility while costs are fixed (Holmberg's 2001-2011 result; the 2022-heavy P&L of the QQQ ORB). So: contracts = risk budget / (stop in ATR units x ATR), skip only the Crabel wide-spread days (yesterday's range > 1.5 x ATR14), and reduce size on top-tercile gap days.

5. **Capped targets convert the family into the Lucid payout shape.** EOD-only exits produce the Zarattini-style distribution (24% winners, rare 10R days) that fails the 50% consistency rule and leaves a trailing-drawdown account exposed on losing streaks. The median post-break extension on ES/NQ is 36-43% of the prior bar's range, so a 0.4x-range target with a 0.5x-range stop (roughly 50-55% hit rate at 0.8:1) or a 0.4x target with a 0.25x-0.33x ATR stop (crackingmarkets) gives many $150-400 days, which is exactly the 5-day/$150 payout requirement. The 2x-range bracket in the NanoTrader default is hit too rarely to rely on.

6. **Concrete candidates to hand to the backtest (all flat by 15:55 ET, one attempt per instrument per day, micros)**:
   - **VB-1 Williams open + k x range, conditioned**: k = 0.3-0.5 of yesterday's range (also test stretch = SMA10 of min(H-O, O-L) x 1-2 and the Holmberg 5-10% quantile threshold); long only if open > yesterday's midpoint (short mirror); skip if yesterday's range > 1.5 x ATR14; entry window 09:30-11:30; stop 0.5 x range or the open; target 0.4 x range; EOD exit fallback.
   - **VB-2 ID/NR4 or NR7 stretch ORB**: same as VB-1 but only on days after an inside day, NR4, ID/NR4, NR7 or 2-bar-NR; allow 1.5-2x the micro count on ID/NR4 and 2-bar-NR days.
   - **VB-3 Inside-day range-target**: after an inside day, trade from the open toward yesterday's high (open above midpoint) or low (open below), stop at the midpoint, target the prior extreme; expect ~60-67% hits on NQ.
   - **VB-4 ATR-unit breakout with 0.33-ATR stop**: prior close +/- 0.33-0.5 x ATR14 (daily), 0.33 x ATR stop, 0.4-0.5 x ATR target, one attempt, 09:30-11:30 window, long/short by 10-day momentum (close > close[10]).
   - **Overlay for all**: daily loss cap $300-400 (stop trading for the day), VIX / ATR percentile used for sizing only, no trades on days when the overnight gap > 1 x ATR14 in the eval phase.
   - **Expect**: 40-55% win rates, PF 1.1-1.4 after $4-5/RT micro costs if the conditioning works, ~8-15 trades/month per instrument on VB-1/VB-4 and ~4-8 on VB-2/VB-3; the family's realistic contribution to a Lucid eval is steady $100-300 days rather than fast passes, so it suits the "safe" configuration better than the "fast" one.

---

## 8. Source list

- Holmberg, Lonnbark, Lundstrom (2013) Finance Research Letters: http://www.econ.umu.se/ueslpnr/ues845.pdf
- Mesfin (2026) arXiv 2605.04004: https://arxiv.org/abs/2605.04004 ; https://arxiv.org/pdf/2605.04004
- Fetna (2026) SSRN 7428398: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7428398
- Tsai et al. (2019) IEEE Access TORB (context): https://www.researchgate.net/publication/331076454
- Oxford Strat Crabel tests: https://oxfordstrat.com/?p=8118 ; https://oxfordstrat.com/trading-strategies/nr7/ ; https://oxfordstrat.com/trading-strategies/price-breakout-nr7/ ; https://oxfordstrat.com/trading-strategies/orbp-with-price-channel-filter/ ; https://oxfordstrat.com/trading-strategies/orbp-trend/ ; https://oxfordstrat.com/trading-strategies/wide-range-pattern/ ; https://oxfordstrat.com/trading-strategies/toby-crabel-narrow-range-2/
- Crabel summaries: https://www.x-trader.net/descubriendo-a-toby-crabel-ii/ ; https://www.x-trader.net/descubriendo-a-toby-crabel-iii/ ; https://store.traders.com/-v06-c09-playing-pdf.html ; https://store.traders.com/-v07-c04-orb-pdf.html ; https://time-price-research-astrofin.blogspot.com/2023/09/nr4-nr7-narrow-range-4-7-id-inside-days.html ; https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/narrow-range-day-nr7 ; https://www.luxalgo.com/library/concept/nr4-nr7-narrow-range-bars.md
- Larry Williams implementations: https://www.whselfinvest.com/en-lu/trading-platform/free-trading-strategies/tradingsystem/56-volatility-break-out-larry-williams-free ; https://www.best-trading-platforms.com/trading-platform-futures-forex-cfd-stocks-nanotrader/larry-williams-volatility-break-out-strategy ; https://www.mql5.com/en/articles/20745 ; https://www.mql5.com/en/articles/20862 ; https://www.mql5.com/en/articles/21003 ; https://tradesearcher.ai/strategies/1666-volatility-breakout-strategy ; https://www.tradingview.com/script/cGIaJaSy/ ; https://github.com/RyanTYT/rusty_trader ; https://github.com/nateemma/strategies ; https://www.quantifiedstrategies.com/larry-williams-volatility-strategy/
- Squeeze / channels: https://www.luxalgo.com/library/concept/ttm-squeeze.md ; https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/T-U/TTM-Squeeze ; https://www.tradingview.com/script/9pbRIoJQ-NA-GPT-TTM-Squeeze-Strategy/ ; https://www.quantifiedstrategies.com/bollinger-band-squeeze-strategy/ ; https://www.prorealcode.com/prorealtime-market-screeners/bollinger-bands-squeeze-screener-daily-volatility-compression-with-atr-ratio/ ; https://doc.stocksharp.com/en/api-examples/0007_Keltner_Channel_Breakout ; https://stocksharp.com/store/strategies.0043_vcp/ ; https://www.crackingmarkets.com/intraday-volatility-breakout-blueprint/ ; https://huntersalgo.com/guides/best-nq-breakout-strategy
- Statistics: https://tradingstats.net/orb-strategy-research/ ; https://tradingstats.net/price-extension-after-breakout/ ; https://www.edgeful.com/blog/posts/inside-day-in-trading-breakout-data ; https://quantifiableedges.blogspot.com/search?q=inside+day ; https://quantifiableedges.blogspot.com/search?q=NR7 ; https://www.luxalgo.com/library/concept/volatility-percentile-rank.md
