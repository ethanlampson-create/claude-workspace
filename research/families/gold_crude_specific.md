# Family: Gold (GC/MGC) specific intraday strategies (crude only as reference)

Research sweep date: 2026-10-03. All times **ET**. Scope: London AM/PM fix patterns, Asian-session accumulation and London-open reversals, 08:20 pit-open behaviour, US-open reversals, gold ORB / initial-balance variants, hour-of-day seasonality, gold/DXY, trend-day behaviour in the 2025-2026 record run, volatility and tick values for sizing on a Lucid 50K Flex.

Target use: Lucid Trading 50K LucidFlex (eval target $3,000; $2,000 END-OF-DAY trailing max loss, breach checked intraday on open P&L; 50% consistency rule in eval; funded: no consistency, 90/10, EOD trail locks at $50,100 once EOD balance reaches $52,100; payout needs 5 separate days with >= $150 EOD profit, min $500, max $2,000 per request; 4 minis / 40 micros in eval, 2 minis / 20 micros at funded start; flat by 16:45, Globex reopens 18:00).

**Method note.** The shared session had exhausted its WebSearch budget before this sweep started, so the evidence was gathered by (a) direct fetches of ~20 pages/papers (Wikipedia gold fixing, the Copenhagen Business School thesis "Gold Price Dynamics Around the Clock" PDF, tradethatswing, edgeful x3, Unger Academy blog2 x2, tradingstats, seasonalcharts, Semantic Scholar/arXiv APIs (rate-limited), Mesfin arXiv 2605.04004 PDF) and (b) **our own statistics on the local 1-minute spot-gold series `data/parquet/XAUUSD_1m.parquet` (histdata, 2009-2026, no volume, closed 17:00-18:00 ET)** plus `GC_1d.parquet` (Yahoo). Where a web source was blocked (SSRN, CME, Quantpedia, Investopedia, TradingView, GitHub search, mql5) it is said so. Spot gold is a close proxy for GC/MGC intraday (futures carry ~4-5%/yr adds about -1 bp/day of drift to long windows; irrelevant for minute-scale effects).

Scripts used (reproducible): `/tmp/claude-0/.../scratchpad/gold_stats{,2,3,4,5}.py` (hour-of-day returns, clock windows, ORB/IB break stats, DST validation, IB-pullback and Asian-breakout simulations). Suggested home if kept: `research/scripts/gold_intraday_stats.py`.

---

## Summary (read this first)

1. **The only gold-specific intraday effect that is both documented in the literature and still alive in 2025-2026 is the London-fix sell-off, concentrated in the last 2-3 minutes before each LBMA auction (05:28-05:31 ET for the AM fix, 09:58-10:01 ET for the PM fix).** On our 1-minute spot data the AM-fix window is negative in **every** sub-period 2011-2026 (t = -10.9, -7.4, -6.4, -4.9 for 2011-18 / 2019-24 / 2025 / 2026; 61-70% of days down). A DST test proves it is the fix and not a clock artefact: in the ~35 days a year when London is on GMT while New York is on EDT, the 05:28 effect vanishes (t = 0.1) and reappears at 06:28-06:31 (t = -5.5 in 2025-26); likewise 09:58 -> 10:58. Economic size is the problem: **$1.6-2.1 per MGC per day gross in 2011-2024 (below round-trip cost), $7-11 in 2025-2026** (net ~$4-8 per MGC per day). This is a consistency "filler", not an eval-passer.
2. **The "hat shape" (gold rises during Asian hours, falls during London/NY hours) is real and persistent in its eastern half, dead in its western half.** Long 18:00-02:00 ET is positive in 15 of 16 years (2011-21 t = 4.8; 2025-26 +$37 per MGC per day gross, but sd $388). Short 03:00-10:00 ET has been zero or negative since 2017. Long 18:00-02:00 is permitted by Lucid (same trading day, flat by 16:45 next day) but is an overnight-session trade; it needs a project decision.
3. **The Globex reopen minute (18:00 ET) carries a positive drift** (+2.6 bp 2019-24, +4.0 bp 2025-26 on the first 1-minute bar; 18:00-18:30 long positive 15/16 years, t = 6.6 for 2011-21). Most of it is in the first bar, so it is execution-sensitive and must be verified on GC futures prints before anyone trusts it.
4. **The 09:30-10:30 initial-balance pullback (tradethatswing / edgeful "GC IB algo") is the best-documented practitioner gold day-trade and we replicate it**: gross on 1 MGC, 2025: 164 trades, 54% win, PF 1.54, +$3,019, max DD $574; 2026 YTD: 127 trades, PF 1.34, +$2,921, max DD $1,331; 2022-24: PF 1.16, $3/trade (dead after costs). The author withdrew the strategy in July 2026 when the single-break rate fell toward 50%; our monthly single-break series confirms (90% Aug-2025 -> 52% Jul-2026 -> 56% Sep-2026). It is a **regime-gated** strategy.
5. **Gold ORBs off the 08:20 pit open do not work in 2025-26** (15/30-min first-break follow-through 46%, mean excursion at the 13:30 close -0.11 to -0.15 x range, i.e. a mild fade), after having worked in 2022-24 (+0.18 x range, t = 2.7-3.3 for 30/60-min). Sign instability = untradeable without a regime filter.
6. **Asian-range London breakout, Asian-accumulation/London-reversal, US-open reversal, London->NY continuation ("81%"), day-of-week and MGC z-score mean reversion all fail or are unreproducible** on OHLC (details per section). Mesfin 2026 (independent, 2023-2025 OOS): every MGC OU mean-reversion configuration negative after 0.5-pt friction (t down to -5.3); gold's 5-minute Hurst is ~0.5 (random walk), so do not fade it.
7. **Sizing on a $2,000 EOD-trailing account in 2025-2026 gold**: MGC = 10 oz, $1.00/tick (0.10), $10 per $1 move; GC = 100 oz, $10/tick, $100 per $1. Median full-day range 2025-26 $73 ($730 per MGC), 2026Q1 $133 ($1,330 per MGC); 14-day ATR peaked at $247/day (Feb 2026) = $2,470 per MGC; worst day -10.8% (2026-01-30); mean 1-minute range 09:00-11:00 ET $3.1 (= $31 per MGC per minute). **GC full-size is unusable**; 1-3 MGC with $100-250 stops is the working range; never hold through 08:30 or 14:00 macro prints with more than that.

---

## Context: the gold session clock (ET) and the 2025-2026 regime

- Globex GC/MGC: 18:00 - 17:00 next day, Sunday-Friday (23 h); daily settlement 13:30 ET (COMEX "pit"/RTH convention 08:20-13:30 survives as the settlement window and on most platforms as the RTH template; the floor closed in 2016). Source: CBS thesis ch. 2.4; CME spec pages returned 403/503 to every fetch, so contract specs below are from the thesis plus general knowledge and should be re-checked on cmegroup.com.
- LBMA Gold Price auctions: 10:30 and 15:00 London = **05:30 and 10:00 ET** except for the UK/US DST mismatch weeks (second Sunday of March to last Sunday of March; last Sunday of October to first Sunday of November) when they are **06:30 and 11:00 ET**. Electronic ICE/IBA auction since March 2015 (telephone fix before). Fifteen direct participants.
- Macro prints that move gold: 08:30 ET (CPI, NFP, PCE), 10:00 ET (ISM, UMich - coincides with the PM fix), 14:00 ET FOMC. Mean 1-minute range at 08:30 in 2025-26 is $5.72 vs $3.5 at 08:20 and $2.3 at 15:00.
- 2025-2026 price path (GC front-month, month-end closes): Jan-25 2,812; Jun-25 3,308; Sep-25 3,873; Dec-25 4,341; **Feb-26 5,248 (peak)**; Mar-26 4,648; Jun-26 4,038; Sep-26 4,187. Max drawdown -24.9% (to 2026-07-16). Daily |return| mean 1.14%, daily sd 1.59% (2025-26). Worst days: 2026-01-30 -10.78%, 2026-03-19 -5.93%, 2025-10-21 -5.74%, 2025-12-29 -4.59%. Best: 2026-02-03 +6.07%.
- Session ranges (edgeful, 14-day ATR, 6 months to early 2026): GC Asia $116-128, London $119-130, NY $119-129 - **gold's overnight sessions carry as much range as NY**, unlike ES/NQ. Our data: median range 18:00-17:00 $73 (2025-26) vs $24.5 (2022-24); pit 08:20-13:30 $42 vs $17; NYSE hours $40 vs $15.
- Trend-day frequency (close in top/bottom 20% of the 18:00-17:00 range): 40.0% (2019-21), 44.2% (2022-24), 40.4% (2025-26) - **the record run did not make gold more "trendy" intraday**; it made it bigger. Skew: 25.9% of 2025-26 days close in the top 20% vs 14.5% in the bottom 20%.

---

## Strategy sections

Evidence-quality scale: 1 anecdote / vendor claim; 2 single backtest or own test only; 3 own test consistent with one published study, or two independent practitioner tests; 4 peer-reviewed plus independent OOS; 5 multiple peer-reviewed + multiple independent OOS.

### 1. Pre-AM-fix fade (short into the 05:30 ET LBMA auction)

- **Origin**: Caminschi & Heaney (2014, J. Futures Markets 34(12), "Fixing a leaky fixing"): GC and GLD 1-minute data over six years; statistically significant volume, volatility and *negative* return regularities in the 30 minutes before the fix, exploitable in a trading rule. Abrantes-Metz & Metz (2014, "Has there been a decade of London PM gold fixing manipulation?") and the LBMA Alchemist (Fertig) found large PM-fix moves were down ~2/3-92% of the time 2004-2013. CBS thesis (GC 5-min, 2001-2018): -3.7% annualised in the 30 min before the AM fix, AM-fix returns negative in 13 of 18 years (9 significant). Own test extends it to 2026 at 1-minute resolution.
- **Rules (objective)**: On days when the AM auction is at 05:30 ET (i.e. London-NY offset = 5 h; use `Europe/London` vs `America/New_York` offsets), **sell at the 05:28 bar open, cover at the 05:31 bar open** (market orders). No stop (3-minute hold; a 0.25% stop never triggers in practice). Variants: 05:25 -> 05:31 (more P&L, more noise), 05:20 -> 05:31. On DST-mismatch days shift the window to 06:28 -> 06:31. Skip if a scheduled release falls inside the window (none normally).
- **Parameters**: entry 05:28, exit 05:31; contracts 5-20 MGC (see sizing); no stop.
- **Evidence (own, spot 1-min, $ per MGC per day gross)**: 05:28-05:31: 2011-18 $1.58/day, 61% win, t = 10.9; 2019-24 $1.57, 57%, t = 7.4; **2025 $7.26, 69%, t = 6.4; 2026 $11.35, 70%, t = 4.9**. 05:25-05:31: $2.14 / $1.77 / $7.63 / $17.41 (t 11.2 / 6.7 / 5.1 / 6.0). Minute path 2025-26: 05:29 -1.12 bp, 05:30 -0.85 bp, 05:32 +0.48 bp (small rebound). DST validation: normal days 05:28-05:31 mean -1.06 bp (t = -13.6, n = 3,359, 2011-24) vs mismatch days -0.04 bp (t = -0.1); mismatch days 06:28-06:31 -4.98 bp (t = -5.5) in 2025-26. Published: see origin. **Evidence quality 4** (peer-reviewed mechanism + own 16-year OOS at minute resolution), but economic size small.
- **Prop fit**: Perfect shape (3-minute hold, 65-70% win, no overnight, no news) but tiny: at 2025-26 size and ~$3.2 round-trip cost, net ~$4-8 per MGC per day; 10 MGC = $40-80/day with sd ~$200-330. Useful as a daily "green-day" builder for the 5 x $150 payout rule only when stacked with another edge; cannot pass an eval alone (needs ~$3,000 / $60 = 50+ days). Fill risk: the 05:28-05:31 bars have mean 1-min range $2.0-2.6 in 2025-26; MGC spread 1-2 ticks at that hour; GC commission $2.30/side at Lucid, MGC assumed $0.50-0.75. Must be re-verified on GC/MGC futures prints (spot CFD feed may react a few seconds differently).
- **Data requirements**: 1-min OHLC only; a London/New York DST calendar.
- **Sources**: https://onlinelibrary.wiley.com/doi/abs/10.1002/fut.21636 (403; cited via thesis lit review) ; CBS thesis https://research-api.cbs.dk/ws/portalfiles/portal/59803241/651553_Thesis.pdf ; https://en.wikipedia.org/wiki/Gold_fixing ; https://www.lbma.org.uk/prices-and-data/lbma-gold-price ; own scripts gold_stats3/4/5.py.

### 2. Pre-PM-fix fade (short into the 10:00 ET auction)

- **Origin**: same literature (the PM fix is the one studied by Caminschi-Heaney and Abrantes-Metz). CBS: -3.9% annualised in the 30 min before the PM fix; "Fixing" strategy (short 05:05-05:35 and 09:35-10:05) +7.6%/yr gross 2001-2018 but -9.3%/yr net of full spreads 2013-18.
- **Rules**: sell at 09:58 bar open, cover at 10:01 bar open (or 09:55 -> 10:01). Shift to 10:58 -> 11:01 on DST-mismatch days. Skip days with a 10:00 ET scheduled release (ISM, UMich, JOLTS, new home sales) or treat separately.
- **Evidence (own, $ per MGC per day gross)**: 09:58-10:01: 2011-18 $0.83 (t 3.3), 2019-24 $1.73 (t 3.6), 2025 $6.89 (60% win, t 3.2), 2026 $2.85 (t 0.6). 09:55-10:01: $1.75 / $0.89 / $8.65 / $8.07 (t 5.3 / 1.7 / 3.2 / 1.3). DST validation: normal days -0.90 bp (t -5.4, 2011-24), -1.89 bp (t -3.5, 2025-26); mismatch days 10:58-11:01 -4.57 bp (t -3.4, 2025-26). Minute 09:59: -0.51 bp (2019-24), -1.26 bp (2025-26). **Evidence quality 3** (weaker and noisier than the AM fix because 10:00 ET also carries US data).
- **Prop fit**: Same as 1, half the reliability, more event risk. Combine with 1 as a two-trade "fix pair" (~$10-15 per MGC per day gross in 2025-26).
- **Data requirements**: 1-min OHLC, DST calendar, 10:00 ET economic calendar (to exclude).
- **Sources**: as section 1.

### 3. Post-fix rebound / fix-leak momentum (10:00-10:04 direction -> 10:30; long 05:31-05:45)

- **Origin**: Caminschi-Heaney: GC returns in the 4 minutes after the PM fix starts were significant and the direction of early-fix trading predicted the published fix >90% of the time (information leak during the telephone fix). The fix became an electronic auction in March 2015.
- **Rules**: (a) Leak-momentum: at 10:04 go with the sign of the 10:00-10:04 move, exit 10:30, stop 0.3%. (b) Rebound: buy 05:31 open, sell 05:45 open (and buy 10:01, sell 10:15).
- **Evidence (own)**: (b) long 05:31-05:45: 2011-18 $1.13/MGC/day (t 4.8), 2019-24 $1.13 (t 3.1), 2025 $1.69 (t 1.0), 2026 $1.25 (t 0.2) - decaying to zero. Long 10:01-10:15: $2.38 (t 4.6) / $0.51 (t 0.9) / $8.41 (t 2.1) / -$1.38 (t -0.1). (a) not separately tested; the thesis and the 2015 auction change argue it is dead. **Evidence quality 2** (was 4 pre-2015).
- **Prop fit**: Do not trade; keep only as the exit timing for 1-2 (cover at 05:31/10:01, not later).
- **Data requirements**: 1-min OHLC.
- **Sources**: as section 1; https://en.wikipedia.org/wiki/Gold_fixing (auction since 2015).

### 4. Eastern-hours drift: long gold 18:00 -> 02:00 ET ("hat shape", Asian demand hours)

- **Origin**: CBS thesis "Gold Price Dynamics Around the Clock" (GC 5-min, 3 Jan 2001-31 Dec 2018): gold appreciates +18.6% annualised between 11:00 and 02:00 ET and depreciates -10.0% annualised in the remaining hours; "Long" strategy (buy 11:00, sell 02:00 next day) 18.6%/yr gross, Combo (long + short western hours) Sharpe 1.61 gross; net of 100% of spread: Long +6.3%/yr 2007-12, +1.7%/yr 2013-18 (spreads 0.25% of mid 2001-06, 0.06% 2007-12, 0.03% 2013-18). Eastern returns regress on China GDP growth and INR strength. Related: GLD earned only ~5.7% of its 2004-2024 gain overnight (US close-to-open), consistent with the daytime leg being flat-to-negative.
- **Rules**: buy at 18:01 (avoid the reopen print), sell at 02:00; stop 0.6% (approx. $25 at $4,200 = $250 per MGC); no trade if a scheduled Asian-hours event (BoJ, China data) is flagged; optional: only if the previous NY session (10:00-16:45) closed down (not tested).
- **Evidence (own, 18:00-02:00 open-to-close, $ per MGC per day gross)**: positive in 15 of 16 years (only 2022 -$0.23). 2011-21 mean ~$5/day, t = 4.79; 2022-24 $8.20; **2025 $40.0 (t 3.0), 2026 $32.0 (t 0.7)**; 2025-26 win 55%, sd $388. Day-of-week in Asia hours: Friday strongest 2022-24 (+10 bp, t 4.0), Wednesday 2025-26 (+28 bp, t 3.3) - unstable. The thesis' own caution: eastern returns were >10% almost every year 2001-2010 but weaker and less consistent after. **Evidence quality 3**.
- **Prop fit**: Allowed by Lucid (position opened 18:01 and closed 02:00 is inside one trading day; flat-by-16:45 rule untouched), but **not a day-trade in the project's RTH sense**; it holds through the Shanghai open and overnight news; sd $388 per MGC per day means 3 MGC risks ~$1,200 in a 1-sd day - too wide for the $2,000 trailing floor without a hard stop. With the 0.6% stop the expected hit rate and net edge must be simulated by the backtest team. Flag for a decision.
- **Data requirements**: 1-min OHLC; optional Asian event calendar.
- **Sources**: CBS thesis (above) ; calendar_seasonal_structural.md s.18 (sibling).

### 5. Globex reopen drift: long 18:00 -> 18:30 ET

- **Origin**: own finding while mapping hour-of-day returns; mechanism plausible (queued Asian buy orders after the 17:00-18:00 halt; the 17:00->18:00 gap itself is ~0: -0.55 bp 2022-24, +0.95 bp 2025-26).
- **Rules**: buy at the 18:00 open (unrealistic) or 18:01 open (realistic), sell at 18:30; stop 0.3%.
- **Evidence (own, $ per MGC per day gross)**: 18:00-18:30: positive 15/16 years; 2011-21 t = 6.6; 2022-24 $7.24 (62% win); 2025 $16.11 (63% win, t 3.1); 2026 $29.80 (62%, t 2.5). But the first bar carries most of it (18:00 1-min bar mean +2.56 bp 2019-24, +4.03 bp 2025-26, and its mean range is $5.68 in 2025-26): **18:01-18:30**: 2011-18 $1.41 (t 4.0), 2019-24 $2.95 (t 4.4), 2025 $8.41 (t 1.7), 2026 $6.12 (t 0.4). 18:01-19:00: 2025-26 $15/day, t 2.3. **Evidence quality 2** (own only; execution-sensitive; spot CFD reopen prints may differ from GC).
- **Prop fit**: Allowed (after 18:00); small; realistic version (18:01 entry) ~$6-8 per MGC net in 2025-26; needs verification on futures. Consider as a second "filler" with section 1.
- **Data requirements**: 1-min OHLC.
- **Sources**: own scripts gold_stats2/3/4.py.

### 6. Western-hours short: 03:00 -> 10:00 ET (London open to PM fix)

- **Origin**: CBS thesis "Short" strategy (sell 02:00, buy 11:00): +10.0%/yr gross 2001-2018; net +6.2%/yr 2013-18, negative 2017-18. Caulfield/Speck-style "gold is sold during London" folklore (seasonalcharts.com intraday gold chart, spot 2002-2012).
- **Rules**: sell 03:00, cover 10:00 (or 10:01), stop 0.6%, skip if |overnight move| > 1%.
- **Evidence (own, $ per MGC per day gross)**: 2011 +$13.5, 2012 +$7.8, 2013 +$23.8 (t 3.5), 2015 +$9.6; **2017-2020 negative, 2021 +$11.5, 2022-24 ~0, 2025 -$3.8, 2026 +$14.4 (t 0.26)**; 2025-26 win 46%. **Evidence quality 2** (published gross effect; dead OOS).
- **Prop fit**: No. Shorting the 2025-26 gold trend during London hours had a 46% win rate and sd $376 per MGC per day.
- **Data requirements**: 1-min OHLC.
- **Sources**: CBS thesis; https://www.seasonalcharts.com/en/intraday/metals/gold (2002-2012 spot chart, no numbers in text).

### 7. NY-hours long: 10:05 -> 16:45 ET (right leg of the U)

- **Origin**: CBS thesis daily cumulative pattern (local minimum at ~10:00 ET, rising to 17:00); GLD daytime-return observation.
- **Rules**: buy 10:05 (after the fix), sell 16:45, stop 0.8%.
- **Evidence (own)**: 2011-24 average ~+$2/MGC/day with t < 1.5 every year; 2025 +$28.5/day (59% win, t 2.4); **2026 -$46.6/day (44% win, t -1.6)**. **Evidence quality 1-2**.
- **Prop fit**: No - it is just long gold during the US day; it inherits the trend and the 2026 drawdown.
- **Data requirements**: 1-min OHLC.
- **Sources**: CBS thesis; own.

### 8. London/NY overlap long 06:00 -> 08:00 ET (2025-26 artefact)

- Hour-of-day table shows 06:00-08:00 at +3.9 bp/day (t 2.3) in 2025-26 but -0.8 bp (2019-21) and -0.8 bp (2022-24), with 2011-24 yearly t-stats mostly negative. **Evidence quality 1 (data-mined)**. Not a strategy; listed so the backtest team does not rediscover it.

### 9. Gold opening-range breakout off the 08:20 pit open (15/30/60-minute) and its fade

- **Origin**: generic ORB (Crabel/Fisher) applied to the COMEX open; relaxedtrader "Gold Opening Range Breakout" (vendor; buys a "statistically significant" new intraday high after the opening range, exits at the next session open - average hold 1.5 days, i.e. overnight; backtest 2001-2015 / live 2016-2026: PF 1.69, CAGR 18.1%, 57.1% win, 531 trades, MDD 19.6% at $50k per GC); Quantified Strategies reports plain ORB on GC/SI/CL as negative. Edgeful tracks a 15-min ORB and 60-min IB for ES/NQ (ES 43% close above / 36% below / 20% inside; single IB break 74-80%) but publishes no GC ORB numbers.
- **Rules (standard)**: range = 08:20-08:35 (or 08:50 / 09:20) high-low; buy stop 1 tick above the high / sell stop below the low on the first 1-min close beyond; stop = opposite side of the range (cap 0.5%); exit 13:30 settlement or target 1 x range. Fade variant: enter against the first break when price closes back inside the range within 15 minutes; target range midpoint.
- **Evidence (own, first-break follow-through = close at 13:30 beyond the broken side; mean excursion at close in units of range)**: 15-min: 2019-21 51.3% / +0.13 x (t 1.4); 2022-24 47.8% / +0.01 x; **2025-26 46.2% / -0.11 x** (median range $10.2). 30-min: 51.3% / -0.05 x; 52.2% / **+0.18 x (t 2.7)**; **46.5% / -0.15 x (t -1.5)** (median $13.6). 60-min (08:20-09:20): 47.8% / -0.05 x; 54.0% / +0.18 x (t 3.3); 49.2% / +0.03 x (median $19.0). Single-break rates 33-61%: gold's pit-open range is broken on both sides most days. **Evidence quality 2** (own; vendor claims unverifiable; sign flips between regimes).
- **Prop fit**: Poor. Breakout and fade each worked in one regime and failed in the next; the 2025-26 reading (follow-through 46%, negative excursion) says a *fade* of the 15/30-min pit ORB had a small edge, but t = -1.5 is not enough to risk $2,000 of room on. If tested at all: 60-min range, only when the trailing-40-day ATR is rising and the single-break rate (sec. 11) is > 70%.
- **Data requirements**: 1-min OHLC.
- **Sources**: https://relaxedtrader.com/store/gold-opening-range-breakout-trading-strategy/ (page blank on fetch; summary from orb_session.md s.6.3) ; https://www.quantifiedstrategies.com/opening-range-breakout-strategy/ (bot-walled) ; https://www.edgeful.com/blog/posts/best-time-to-trade-futures ; own.

### 10. Pit-open first-10-minute fade (short 08:20 -> 08:30 ET)

- **Origin**: own hour-of-day/clock map; folklore that the COMEX open is "sold into" after the overnight run.
- **Rules**: sell 08:20 open, cover 08:30 open; no stop (10-minute hold); skip 08:30-release days (the exit is at 08:30:00, before the print, but spreads widen at 08:29).
- **Evidence (own, $ per MGC per day gross)**: 2011-16 ~0; 2017 +$1.75 (t 2.9); 2021 +$4.26 (t 2.7); 2023 -$2.10; 2024 +$3.06 (t 1.9); **2025 +$5.05 (t 1.9, 59% win); 2026 +$6.84 (t 1.3)**; 2025-26 combined t = 2.2. Hourly table: 08:20-08:30 window -1.10 bp (t -2.4) 2019-21, -0.24 bp 2022-24, -1.52 bp (t -2.2) 2025-26. **Evidence quality 1-2**.
- **Prop fit**: Marginal; ~$3 net per MGC per day in 2025-26; 1-minute bar at 08:20 averages $3.54 (2025-26), so a 10-contract market order can lose a tick or two of the edge. Candidate for the "filler" basket only after futures verification.
- **Data requirements**: 1-min OHLC; 08:30 calendar.
- **Sources**: own (gold_stats3.py).

### 11. Initial-balance (09:30-10:30 ET) break-and-pullback - the tradethatswing / edgeful "GC IB algo"

- **Origin**: tradethatswing "Initial Balance Breakout Gold Day Trading Strategy" (backtest 13 Jan 2025-9 Jan 2026, updated Feb/Apr/Jul 2026); edgeful "GC trading strategy: the initial balance algo that returned $106k in 12 months" (12 months to Jan 2026). Both are vendor backtests on 1-2 GC contracts.
- **Rules (tradethatswing, original)**: session 09:30-16:00; IB = 09:30-10:30 high/low; after the first 1-min close beyond the IB high (low), place a limit **25% of the IB range inside the broken level** (long at IB_high - 0.25 x IB); stop 60% of IB from entry; target 50% of IB **measured from the IB extreme** (long target = IB_high + 0.50 x IB); 1 contract; close at session end if neither hit; one trade per day. Feb-2026 variant: IB range 0.4-2% of price, longs only, 10% retrace entry, 35% stop, 30% target (from entry): 20 trades in 3 months, 70% win, +121% on $10k, MDD 12.85%. Apr-2026 variant (7-year test 2019-2026): IB range 0-2%, long and short, 25% retrace, **100% stop, 20% target**: +445% in the last year, "very well since about May 2024". **Jul-2026 update: "the single-break percentage has significantly dropped ... avoid until the data shows improvement."**
- **Rules (edgeful)**: 5-min chart; entry on a 1% retracement after the IB high/low breaks; stop = 60% retrace back into the IB; TP1 0.25 x IB beyond the break, TP2 0.50 x IB; 2 contracts on $50k. GC single-break 79.23% / double 13.08% / no-break 7.69% (last 6 months to Jan 2026). Results: WR 65.76%, PF 1.935, MDD 11.6%, +$105,890 on $50k, no costs stated, "re-optimise monthly".
- **Evidence (vendor)**: tradethatswing original: 142 trades in ~250 days, win just over 50%, avg win ~$1,100 vs avg loss ~$600 per GC, +411% on $10k, MDD 25%, commissions included. **Evidence (own replication, spot 1-min, 1 MGC, gross, limit fills assumed when touched)**: original rules: 2022-24 434 trades, 49% win, PF 1.16, +$1,354 ($3/trade - dead after $3.2 cost), max DD $663; **2025: 164 trades, 54% win, PF 1.54, +$3,019 ($18/trade), max DD $574, worst trade -$228; 2026 YTD: 127 trades, 50% win, PF 1.34, +$2,921 ($23/trade), max DD $1,331, worst -$395.** Apr-2026 variant (100% stop / 20% target): 2025 78-79% win, PF 1.49 ($10/trade); 2026 PF 1.06 ($3/trade). Feb-2026 longs-only variant: 2025 PF 1.83 ($19/trade, 77 trades); **2026 PF 0.76 (-$1,217)**. Monthly single-break rate (09:30-10:30 IB, our data): 2025 68-90% (mean ~79%); 2026: Jan 81, Feb 80, Mar 82, Apr 62, May 76, Jun 73, **Jul 52**, Aug 90, **Sep 56**. Overall single-break 82% in every period 2019-2026 (double 17-18%, no-break 7-8%), follow-through of the first break to the 16:00 close only ~50%, mean excursion +0.05-0.07 x IB - which is why the pullback-entry/short-target design works and a plain break-and-hold does not. **Evidence quality 3** (two vendors + own replication; honest decay).
- **Prop fit**: The best gold candidate in this family for the eval window, **but only in MGC and only regime-gated**. In 2025, 1 MGC made ~$250/month gross; 5 MGC would be ~$1,250/month with a max DD ~$2,900 (5 x $574) - already more than the $2,000 room. Realistic: 3 MGC, stop 60% x IB (median IB $16-31 in 2025-26 -> $100-190 per MGC -> $300-570 per trade), 1 trade/day, ~13 trades/month, ~55% win. Gate: trade only while the trailing-40-day single-break rate > 70% and the IB range is 0.4-2% of price; stand aside otherwise (Jul and Sep 2026 would have been skipped). Consistency: avg win ~$180-250 per 3 MGC keeps any single day < 50% of a $3,000 target.
- **Data requirements**: 1-min OHLC (5-min for the edgeful variant).
- **Sources**: https://tradethatswing.com/one-trade-a-day-gold-strategy-411-in-last-year-fully-automatable/ ; https://www.edgeful.com/blog/posts/gc-trading-strategy-initial-balance-algo ; own gold_stats4.py.

### 12. Asian-range (18:00-02:00 ET) London breakout

- **Origin**: forex "London breakout" / "Asian box" folklore (babypips, axi and mql5 pages all 403/404 on fetch); tradingstats.net lists "Overnight Range Breakout" and "London Session Breakout" modules (NQ only). Standard rules per practitioners: mark the Asian-session high/low, trade the first break during the London open, stop at the opposite side or midpoint, exit at the NY open or fix.
- **Rules (standard interpretation, as simulated)**: range = 18:00-02:00 high/low (variant 18:00-03:00); entry = first 1-min close beyond the range between 02:00 and 08:00; stop = range midpoint capped at 0.6% from entry; exit 10:00 ET (variant 16:45) or stop; one trade/day.
- **Evidence (own, 1 MGC gross)**: 2022-24: 688 trades, 32% win, PF 0.97, -$637, max DD $2,690 (exit 16:45: PF 1.04); 2025: 202 trades, 39% win, PF 1.08, +$1,133, max DD $1,864 (exit 16:45: PF 1.14, +$2,348, DD $2,698); **2026: 125 trades, 49% win, PF 1.38, +$5,250, max DD $3,964** (exit 16:45: PF 1.35). Follow-through statistics (first break of the 18:00-02:00 range -> close at 10:00 beyond it): 47-51% in 2019-24, **55.5% in 2025-26 with mean excursion +0.11 x range (t 2.6)**; single-break 69% (2019-24) -> 87.5% (2025-26) - the Asian range got so wide ($40 median vs $9) that it is rarely broken twice. **Evidence quality 2**.
- **Prop fit**: Poor for a $2,000 trailing account: win rate 32-49%, max DD $2-4k per single MGC, and the 2026 profit came from a few huge trend days (consistency-rule killer). The only usable fact is the 2025-26 excursion statistic, which argues for *holding* a London-session break rather than fading it.
- **Data requirements**: 1-min OHLC.
- **Sources**: https://tradingstats.net/ (modules list) ; own gold_stats2/4.py.

### 13. Asian accumulation -> London-open reversal (fade the overnight move at 03:00)

- **Origin**: trader folklore ("Asia buys, London sells"; the thesis' hat shape is sometimes read this way).
- **Rules (standard)**: if 18:00-03:00 move > +0.5% sell at 03:00 (and vice-versa), target the Asian midpoint, stop 0.4%, exit 10:00.
- **Evidence (own)**: P(03:00-10:00 return has the opposite sign to the 18:00-03:00 return) = 51.3% (2019-21), 50.9% (2022-24), **46.3% (2025-26)**; conditional on |Asian move| > 0.5%: 50.3%, 53.5%, **40.6%** (i.e. 59% continuation in 2025-26; mean London return after an Asian up-move +7.1 bp, after a down-move -7.0 bp). corr(Asia, London) = 0.03, 0.03, -0.04. **Evidence quality 2 - refuted.**
- **Prop fit**: Do not trade. If anything, continuation.
- **Sources**: own gold_stats.py.

### 14. US-open (09:30 ET) reversal of the pre-open move

- **Origin**: folklore (equity-open flows reverse the pit-open move).
- **Rules**: if 08:20-09:30 move > +0.3% (0.5%) sell at 09:30 and cover 11:00, stop 0.4%; mirror for down-moves.
- **Evidence (own)**: 2019-24: after +0.3% the 09:30-11:00 mean is +1.6 bp (54% up) - no reversal; after -0.3% -2.4 bp (continuation). 2025-26: after +0.3% **-11.2 bp (49% up, t -1.1, n = 77)**; after +0.5% -0.1 bp; after -0.3% +1.8 bp. **Evidence quality 1** (inconsistent, t < 1.2).
- **Prop fit**: No.
- **Sources**: own gold_stats5.py.

### 15. PM-fix reversal of the pit-open run (08:20-10:00 move > 0.5% -> fade 10:00-13:30)

- **Rules**: if 08:20-10:00 > +0.5%, sell 10:01, cover 13:30; mirror.
- **Evidence (own)**: 2019-24: after +0.5% mean -1.1 bp (52% up); after -0.5% -7.9 bp (continuation down). 2025-26: after +0.5% -5.8 bp (47% up, n = 57, t -0.8); after -0.5% **-19.2 bp but 58% up** (fat left tail, i.e. crash days keep falling). **Evidence quality 1**. Not tradable.

### 16. London-session -> NY-session continuation (edgeful "81%")

- **Origin**: edgeful "trading sessions explained": "when GC's London session (03:00-11:00) closes positive, the NY session follows green 81% of the time."
- **Rules (as literally stated)**: at 11:00 if the 03:00-11:00 bar is up, buy and hold to 16:00 (or 16:45); mirror for down.
- **Evidence (own, non-overlapping 11:00-16:00 leg)**: P(up | London up) = 52.9% (2019-24, mean +2.8 bp, t 1.7) and **51.0% (2025-26, mean -1.6 bp)**; P(up | London down) 50.4% / 59.3%; corr(London, NY-after-11) = 0.08 / -0.06. The 81% can only be reproduced if the NY session is defined to *overlap* London (09:30-11:00 is in both), which is not a trade. **Evidence quality 1 (not reproducible)**.
- **Prop fit**: No.
- **Sources**: https://www.edgeful.com/blog/posts/trading-sessions-explained ; own.

### 17. Overnight-move continuation / trend-day following (2025-2026 "record run" behaviour)

- **Origin**: trend-day literature (Crabel/Fisher), 2025-26 narrative that gold "trends all day".
- **Rules (standard)**: if the 18:00-09:30 move is > +0.5% (1%), buy at 09:30 and hold to 16:00 with a stop at the overnight midpoint; mirror for shorts.
- **Evidence (own)**: corr(overnight, NYSE-hours) = 0.03 (2019-24), 0.10 (2025-26). After > +0.5%: NYSE mean +0.1 bp (55% up) 2019-24; +3.1 bp (57% up, t 0.5) 2025-26. After > +1%: +2.3 bp / +1.7 bp. After < -0.5%: -7.8 bp (44% up) / -5.4 bp (50%); after < -1%: -8.2 / -13.1 bp (47%). Trend-day share 40-44% in every period; 2025-26 skew 25.9% top-20% closes vs 14.5% bottom-20%. **Evidence quality 1-2**: there is mild down-move continuation (crash days) and essentially no up-move continuation beyond the unconditional drift.
- **Prop fit**: As a *filter* only: do not buy pullbacks on days that gapped down > 1% overnight (2026-01-30, 2026-03-19 type days); otherwise no standalone edge.
- **Sources**: own gold_stats5.py; GC_1d.

### 18. Unger Academy intraday mean-reversion on gold futures (previous-session level re-cross)

- **Origin**: Unger Academy blog2 "Exploring Gold Futures with Trend-Following and Mean-Reverting Strategies" (15 Aug 2024).
- **Rules (as published, exchange time unspecified)**: long when price falls below the **previous session's low** and then crosses back above it; short mirror on the previous session's high; stop $1,800, target $1,600 per GC; intraday (session-end exit implied); the companion multiday trend system (session high/low breakouts after a certain time of day, $2,000 stop, no target, 45% win, +$30k in 2023) is **not** day-trade compatible.
- **Evidence (vendor)**: since 2016 ~650 trades, win "above 50%", average trade ~$144 per GC; "rough period" 2019-2020, strong 2022-2024; no DD/PF/slippage disclosed. **Evidence quality 2**.
- **Prop fit**: Scaled to MGC: stop $180, target $160, avg trade ~$14 gross (barely 4x cost). Shape is right (prior-day level, defined stop, EOD exit) and it is a *long-when-weak* rule that would have suffered in the 2026 crash days (stop $180 per MGC hit repeatedly). Test as a Turtle-Soup variant with a 0.5 x ATR stop and prior-close target; low priority.
- **Data requirements**: 1-min OHLC.
- **Sources**: https://blog2.ungeracademy.com/exploring-gold-futures-with-trend-following-and-mean-reverting-strategies/ ; https://ungeracademy.com/blog/how-to-exploit-gold-futures-recurring-patterns-with-2-lines-of-code (captcha-walled; the "2 lines" are a buy-at-time/sell-at-time rule - covered by sections 4-7).

### 19. Vendor benchmark: Aeromir "Goldilocks" (2 MGC, 4-minute, 03:00 -> 13:30 ET)

- Proprietary rules; live streamed track 14 Oct 2024-13 Feb 2026: 479 trades, net $21,378, 48.0% win, PF 1.32, avg $45/trade (2 MGC), **max DD $8,368**, Calmar 2.55, ~$1,330/month. Evidence quality 2 (vendor, unaudited, one regime). Its $8.4k DD on 2 MGC is 4x Lucid's room - the realistic ceiling for a "working" retail gold bot and a warning for sizing. Source: https://futures.aeromir.com/goldilocks (via bot_popular_indicators.md s.2.22).

### 20. MGC 5-minute OU / z-score mean reversion (do not)

- **Origin**: Mesfin, arXiv 2605.04004 v3 (Sept 2026), independent: MGC 5-min, 1,091 days (~2021-2025), friction 0.50 pt ($5) round trip, walk-forward with 2023/2024/2025 OOS.
- **Rules tested**: OU z-score entry at |z| > 1.5 or 2.0 on 5-min bars, long and short, exit at mean / time.
- **Evidence**: all four configurations negative after friction: z1.5 long N = 2,634, net -0.55 pt, t = -5.32; z1.5 short N = 3,059, -0.49, t = -4.36; z2.0 long -0.27, t = -1.63; z2.0 short -0.39, t = -2.11; yearly 2023/2024 all negative, 2025 -0.08 to +0.52. 60-min OU half-life ~8 h, "structurally incompatible with intraday execution". MGC Hurst ~0.5 vs MNQ 0.59 (random walk, not mean-reverting). **Evidence quality 3 (independent OOS failure)**.
- **Sources**: https://arxiv.org/abs/2605.04004 ; local extraction scratchpad/mesfin.txt.

### 21. Day-of-week filters for gold sessions

- Tully & Lucey (COMEX 1982-2002): no robust weekday seasonality. Own: Asia-hours Friday +10.3 bp (t 4.0) and Monday -6.0 bp (t -1.8) in 2022-24; in 2025-26 Wednesday +28 bp (t 3.3), Friday +1.5 bp - no persistence. NYSE-hours by weekday: nothing with |t| > 1.3 in either period. **Evidence quality 1.** Use none.

### 22. Gold / US-dollar (DXY) intraday lead-lag filter

- **Origin**: Pukthuanthong & Roll (2011, JBF "Gold and the Dollar (and the Euro, Pound, and Yen)"), Reboredo (2013), Capie-Mills-Wood (2005): gold is negatively related to the dollar contemporaneously at daily and lower frequencies; no published intraday lead-lag edge found (SSRN/Scholar blocked; Semantic Scholar rate-limited after the first query). CBS thesis regressions: JPY strength and Brent raise western-hours gold returns; INR strength and China GDP raise eastern-hours returns - a cross-sectional explanation, not a timing signal.
- **Rules (if DXY intraday were available)**: trade gold only in the direction of the 30-minute DXY move (gold long if DXY down > 0.1%); or use EURUSD 1-min from histdata as the proxy.
- **Evidence**: none intraday; **evidence quality 2** as a filter. **Data requirement: DXY or EURUSD intraday - not in the current data set (histdata EURUSD 1-min is downloadable with the existing script).**

### 23. Macro-print jump avoidance (08:30 / 10:00 / 14:00 ET)

- **Origin**: "What triggers intraday price jumps and co-jumps in gold?" (2025, found via Semantic Scholar; abstract not retrievable after rate-limiting); general announcement-jump literature. Own data: mean 1-min range 08:30 $5.72 vs 08:20 $3.54 and 08:31 $3.51; 10:00 $5.11 vs 10:01 $3.98; 18:00 $5.68 (reopen).
- **Rules**: no new entries 08:28-08:35, 09:58-10:05 (unless running sections 1-2 deliberately), 13:58-14:10 on FOMC days; widen stops or flatten before 08:30 on CPI/NFP days.
- **Evidence quality 2** (own bar-size data; literature not fetched). Pure risk-management, applies to every gold strategy above.
- **Data requirements**: economic calendar.

### 24. Close-hour drift (16:00-17:00 ET) - diagnostic only

- 16:00-17:00 return: -1.63 bp (t -3.7) 2019-21, +0.35 bp 2022-24, -1.73 bp (t -1.8) 2025-26; the final 16:45-17:00 slice is negative in every period (t 2.4 / 3.5 / 4.1 for a short, 2011-18 / 2019-24 / 2025), with the 16:59 bar alone -0.93 to -1.24 bp (settlement/last-print artefact likely). Lucid requires flat by 16:45, so none of this is tradable; it matters only as "do not carry a long into 16:45" and as a caution that spot-feed last bars are noisy.

---

## What the evidence says works in 2022-2026 (gold)

**Works, with caveats**
- *Pre-fix fade (05:28-05:31 ET; 09:58-10:01 ET)*: alive, mechanism verified by the DST shift, t > 4 in 2025 and 2026, 65-70% win, but $7-11 per MGC per day gross; before 2025 it did not cover costs. Treat as a consistency builder (many small green days) at 5-20 MGC, re-verified on futures prints first.
- *IB (09:30-10:30) break-and-pullback (sec. 11)*: PF 1.5 in 2025 and 1.3 in 2026 YTD gross per MGC with 50-54% win and ~$20/trade; dead in 2022-24 (PF 1.16, $3/trade); regime-gate on the trailing single-break rate (> 70%) and IB width (0.4-2%). This is the one gold day-trade worth putting through the Lucid simulator first.
- *Eastern-hours long (18:00-02:00)*: statistically the most persistent long window (15/16 years) and large in 2025-26, but it is an overnight-session hold with sd ~$390 per MGC per day; only with a hard 0.6% stop and a project decision to allow Globex-session trades.
- *Reopen drift (18:01-18:30)*: small, consistent pre-2025, execution-sensitive.

**Does not work / refuted on 2022-2026 data**
- Western-hours short 03:00-10:00 (dead since 2017); NY-hours long 10:05-16:45 (sign flips with the trend; -$47 per MGC per day in 2026); pit-open ORB breakout (follow-through 46% in 2025-26) and fade (t -1.5); Asian-range London breakout (PF 0.97-1.14 until the 2026 outliers, DD $2-4k per MGC); Asian->London reversal (59% continuation in 2025-26); US-open reversal; London->NY "81%" (52% on OHLC); PM-fix reversal; weekday filters; MGC z-score mean reversion (t -5.3 OOS, Mesfin); post-fix leak momentum (killed by the 2015 auction).

**Regime facts the backtest must respect (2025-01 to 2026-09)**
- Gold's daily range tripled vs 2022-24 (median $73 vs $24.5; 2026Q1 $133). One MGC now carries $730-1,330 of daily range; one GC $7,300-13,300. The $2,000 EOD-trailing floor therefore allows **1-3 MGC with $100-250 stops** (10-15% of room per trade), never a GC.
- 2025 was an up-trend with 25.9% of days closing in the top fifth of their range; 2026 contained a -24.9% drawdown with -10.8%, -5.9%, -5.7% days. Any long-biased gold rule must be tested across both halves; the IB algo's own author withdrew it in July 2026.
- Costs: Lucid GC $2.30/side; MGC not listed (assume $0.50-0.75/side); MGC spread 1-2 ticks ($1-2) in liquid hours, wider at 18:00 and in the fix minutes; Mesfin's 0.5-pt ($5) round-trip is the stress case. Net edge per trade must exceed ~$5 per MGC to be deployable.
- Spot-vs-futures: the local gold series is spot (histdata), no volume; the fix-minute and session effects transfer, but fills at the 18:00 reopen and the 16:59 last print are spot-feed specific. Re-run sections 1, 2, 5, 10 on GC/MGC 1-minute futures before committing money.

---

## Position-sizing reference (50K Lucid Flex, 2025-2026 gold)

| Item | GC | MGC |
|---|---|---|
| Size | 100 oz | 10 oz |
| Tick | $0.10 = $10 | $0.10 = $1.00 |
| $ per $1/oz move | $100 | $10 |
| Hours | 18:00-17:00 ET Sun-Fri; settle 13:30 ET | same |
| Lucid commission/side | $2.30 | not listed (assume $0.50-0.75) |
| Median daily range 2025-26 ($73) | $7,300 | $730 |
| Median daily range 2026Q1 ($133) | $13,300 | $1,330 |
| Mean 1-min range 09:00-11:00 ET ($3.1) | $310 | $31 |
| 08:30 ET bar mean range ($5.7) | $570 | $57 |
| 14-day ATR peak Feb 2026 ($247) | $24,700 | $2,470 |
| Worst day 2026-01-30 (-10.8%, ~$500) | ~$50,000 | ~$5,000 |

Rule of thumb for a $2,000 EOD-trailing room: risk <= $200-300 per trade (10-15% of room) => 2-3 MGC with a $10 stop ($100 per contract, ~0.25% of price) or 1 MGC with a $25 stop; one open position at a time; no gold position through 08:30 on CPI/NFP days with more than 1 MGC. Lucid's 40-micro eval cap is never the binding constraint; the drawdown is.

---

## Sources (fetched unless marked)

- CBS thesis "Gold Price Dynamics Around the Clock" (GC 5-min 2001-2018; strategies, spreads, fixing anomalies) https://research-api.cbs.dk/ws/portalfiles/portal/59803241/651553_Thesis.pdf
- Caminschi & Heaney (2014) JFM 34(12) "Fixing a leaky fixing" https://onlinelibrary.wiley.com/doi/abs/10.1002/fut.21636 (403; via thesis lit review)
- Abrantes-Metz & Metz (2014) "Has There Been a Decade of London PM Gold Fixing Manipulation?" (Semantic Scholar id 737d60e5...; SSRN 403)
- Wikipedia "Gold fixing" https://en.wikipedia.org/wiki/Gold_fixing ; LBMA Gold Price https://www.lbma.org.uk/prices-and-data/lbma-gold-price ; Wikipedia "Gold as an investment" https://en.wikipedia.org/wiki/Gold_as_an_investment
- tradethatswing IB gold strategy https://tradethatswing.com/one-trade-a-day-gold-strategy-411-in-last-year-fully-automatable/
- edgeful GC IB algo https://www.edgeful.com/blog/posts/gc-trading-strategy-initial-balance-algo ; best time to trade futures https://www.edgeful.com/blog/posts/best-time-to-trade-futures ; sessions explained https://www.edgeful.com/blog/posts/trading-sessions-explained
- Unger Academy gold strategies https://blog2.ungeracademy.com/exploring-gold-futures-with-trend-following-and-mean-reverting-strategies/
- Mesfin (2026) arXiv 2605.04004 v3 (MGC OU results) https://arxiv.org/abs/2605.04004
- seasonalcharts intraday gold (2002-2012 spot) https://www.seasonalcharts.com/en/intraday/metals/gold
- tradingstats.net (module list) https://tradingstats.net/
- Aeromir Goldilocks https://futures.aeromir.com/goldilocks (via sibling report)
- relaxedtrader gold ORB https://relaxedtrader.com/store/gold-opening-range-breakout-trading-strategy/ (blank on fetch; via orb_session.md)
- Sibling reports: research/families/calendar_seasonal_structural.md s.18; microstructure_volume_profile.md s.10; orb_session.md s.6.3; evidence_and_failures.md s.4; bot_popular_indicators.md s.2.22
- Blocked/unavailable this session: Quantpedia (466), CME contract specs (403/503), SSRN (403), Investopedia, TradingView scripts, GitHub search (session-bound), mql5, babypips/axi (404), Semantic Scholar (429 after first query), arXiv API (0 results for gold+intraday).
- Own statistics: `data/parquet/XAUUSD_1m.parquet`, `data/parquet/GC_1d.parquet`; scripts gold_stats.py ... gold_stats5.py in the session scratchpad.
