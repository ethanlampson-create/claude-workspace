# Family: Gold (GC/MGC) specific intraday strategies (crude only as reference)

Research sweep date: 2026-10-03 (second pass, full web sweep). All times **ET** unless stated. Scope: London AM/PM fix patterns, Asian-session accumulation and London-open reversals, 08:20 pit-open behaviour, US-open reversals, gold ORB / initial-balance variants, hour-of-day seasonality, gold/DXY, trend-day behaviour in the 2025-2026 record run, volatility and tick values for sizing on a Lucid 50K Flex.

Target use: Lucid Trading 50K LucidFlex (eval target $3,000; $2,000 END-OF-DAY trailing max loss, breach checked intraday on open P&L; 50% consistency rule in eval; funded: no consistency, 90/10, EOD trail locks at $50,100 once EOD balance reaches $52,100; payout needs 5 separate days with >= $150 EOD profit, min $500, max $2,000 per request; 4 minis / 40 micros in eval, 2 minis / 20 micros at funded start; flat by 16:45, Globex reopens 18:00). Rules file: `research/lucid_rules.md`.

**Method.** 22 WebSearch queries (academic, Quantpedia, practitioner, TradingView/GitHub, prop-firm community) and ~30 page/PDF fetches: Caminschi & Heaney (2014, JFM), Abrantes-Metz via LBMA Alchemist, Batten-Lucey-McGroarty-Peat-Urquhart (2017, PLoS ONE, 5-min OTC gold 2000-2015), RIETI/Kobe DP 17-E-120 (1-min COMEX/TOCOM gold), CBS thesis "Gold Price Dynamics Around the Clock" (GC 5-min 2001-2018; the PDF now returns 403, numbers come from the earlier session's fetch and the CBS portal abstract), Quantpedia (gold market-timing paper, GLD/GDX overnight), Quantified Strategies (GLD overnight), In Gold We Trust (weekday/month stats), tradethatswing (IB gold algo, all 2026 updates), edgeful, marketstalkers (GC market profile), pro-scalper (Asian-range statistics), Unger Academy (3 gold pages; 2 others bot-walled), Mesfin arXiv 2605.04004 (MGC OU table), Abond1234 GC-1m study (GitHub), ilahuerta XAUUSD pullback repo, Harry197 drift-VWAP repo, three TradingView gold scripts, WisdomTree/CNBC on the Jan-2026 crash, ahasignals gold-DXY tracker, and several prop-firm guides. Blocked: Wiley/SSRN/ResearchGate (403), Benzinga (403), Medium (403), TradingView "GC/MGC VWAP Pullback ADX Regime" (404), Unger Academy pages p=8581/7005/8610/6678 (JS/bot wall), proptradingvibes gold guide (410). Where a source is vague the **most standard objective interpretation** is written and flagged.

**Own statistics** (kept from the first pass, reproducible): local 1-minute spot gold `data/parquet/XAUUSD_1m.parquet` (histdata, 2009-2026, no volume, closed 17:00-18:00 ET) and `data/parquet/GC_1d.parquet` (Yahoo); scripts `gold_stats{,2,3,4,5}.py` in the session scratchpad (suggested home `research/scripts/gold_intraday_stats.py`). Spot is a close proxy for GC/MGC intraday (carry ~4-5%/yr = ~-1 bp/day on long windows; irrelevant at minute scale), but the Abond1234 study found GC's first-contact price trades on MGC in the same minute only 80% of the time, so tick-precise MGC fills must be modelled with slippage.

---

## Summary (read this first)

1. **The only gold-specific intraday effect that is both documented in peer-reviewed work and still alive in 2025-2026 is the sell-off into the LBMA auctions** (05:28-05:31 ET AM fix; 09:58-10:01 ET PM fix). Literature: Caminschi & Heaney 2014 (GC/GLD 1-min: significant volume/volatility/return regularities around the PM fix; early-fix trades predicted the published fix >90%; nothing after publication); Abrantes-Metz: large PM-fix moves were down 92% of the time in 2010 and >= 2/3 in six of the years 2004-2013; CBS thesis: AM-fix returns negative in 13 of 18 years. Own 1-min test: AM-fix window negative in **every** sub-period 2011-2026 (t = -10.9/-7.4/-6.4/-4.9), and a DST test (effect moves to 06:28 when London is on GMT and NY on EDT) proves it is the fix, not the clock. Size: $1.6-2.1 per MGC per day gross in 2011-24 (below cost), **$7-11 in 2025-26** (net ~$4-8). A consistency "filler", not an eval-passer.
2. **The "hat shape" (gold rises in eastern hours, falls in London/NY hours)** is the oldest gold intraday anomaly (Kirtley/SK Options: long PM-fix-to-AM-fix, short AM-to-PM since 2001, "+1700%", $100M -> $2.6B gross; CBS thesis: +18.6%/yr eastern vs -10%/yr western 2001-18, Sharpe 1.61 gross, below market net of spreads). The eastern half is alive (long 18:00-02:00 positive 15 of 16 years; 2025-26 +$32-40 per MGC per day gross, sd $388); the western short has been dead since 2017. The eastern leg is a Globex-session hold, not an RTH day-trade.
3. **The Globex reopen minute (18:00 ET) carries positive drift** (first 1-min bar +2.6 bp 2019-24, +4.0 bp 2025-26; 18:00-18:30 positive 15/16 years). Mostly in the first bar: execution-sensitive, must be verified on GC prints.
4. **The 09:30-10:30 initial-balance break-and-pullback (tradethatswing / edgeful) is the best-documented practitioner gold day-trade and we replicate it**: 1 MGC gross 2025: 164 trades, 54% win, PF 1.54, +$3,019, max DD $574; 2026 YTD PF 1.34, +$2,921, DD $1,331; 2022-24 PF 1.16 ($3/trade, dead after costs). Author withdrew it on 13 Jul 2026 ("single-break percentage ... nearly 50/50"); our monthly single-break series agrees (90% Aug-25 -> 52% Jul-26 -> 56% Sep-26). **Regime-gated.**
5. **Pit-open (08:20) ORBs do not work in 2025-26** (15/30-min first-break follow-through 46%, excursion at 13:30 -0.11 to -0.15 x range) after working in 2022-24 (+0.18 x range, t 2.7-3.3). Market-profile practitioners (marketstalkers) confirm GC's IB is "messier" and wider (45-60% of ADR vs 35-45% on ES) and that GC trends ~45% of days.
6. **Refuted or unreproducible on OHLC**: Asian-range London breakout (PF 0.97-1.14 until 2026 outliers; DD $2-4k per MGC), Asian->London reversal (59% *continuation* in 2025-26), US-open reversal, London->NY "81%", PM-fix reversal, weekday filters, MGC z-score mean reversion (Mesfin: t -5.3 OOS), VWAP pullback on gold (Harry197: 36 trades, 47%, t -1.5, 0 of 27 grid cells positive in both halves), and the Abond1234 study's 196 pre-registered GC 1-min directional strategies (2021-2026, ~4M simulated trades): **none advanced**, deflated Sharpe 0.
7. **Sizing on a $2,000 EOD-trailing account in 2025-26 gold**: MGC = 10 oz, $1.00/tick, $10 per $1/oz; GC = $10/tick, $100 per $1. Median full-day range 2025-26 $73 ($730 per MGC), 2026Q1 $133; 14-day ATR peaked at $247/day (Feb 2026); worst day 2026-01-30 -10.8% (spot -8.9% to $4,915 after touching ~$5,600 that week; biggest daily loss since 1983). **GC is unusable; 1-3 MGC with $100-250 stops is the working range**; never hold through 08:30/14:00 prints with more than that.

---

## Context: the gold session clock (ET), published intraday stylised facts, and the 2025-26 regime

- **Globex GC/MGC**: 18:00-17:00 next day, Sun-Fri; daily settlement window 13:29:00-13:30:00 ET (active month); the COMEX pit open 08:20 ET still anchors institutional flow (fortraders, marketstalkers); 60-min "COMEX IB" = 08:20-09:20, 90-min = 08:20-09:50. The NY-equity IB 09:30-10:30 is what tradethatswing/edgeful use.
- **LBMA Gold Price auctions**: 10:30 and 15:00 London = **05:30 and 10:00 ET** except DST-mismatch weeks (2nd-last Sunday of March; last Sunday Oct-first Sunday Nov) when they are **06:30 and 11:00 ET**. Electronic ICE/IBA auction since 20 March 2015; telephone fix before. The PM fix coincides with the 10:00 ET FX "NY cut" option expiry (marketstalkers: "the single most reliable intraday catalyst on GC"; extension-then-reversal into 10:00, reversal 10:00-10:15).
- **Shanghai Gold Exchange**: 09:00-11:30 and 13:30-15:30 Beijing = 21:00-23:30 / 01:30-03:30 ET (20:00-22:30 / 00:30-02:30 ET in US DST); SHFE night session to 02:30 Beijing. No published intraday COMEX effect at the SGE open was found; the thesis' eastern-hours drift covers it.
- **Macro prints**: 08:30 ET (CPI, NFP, PCE), 10:00 ET (ISM, UMich - on top of the PM fix), 14:00 ET FOMC. Own: mean 1-min range at 08:30 in 2025-26 $5.72 vs $3.54 at 08:20 and $2.3 at 15:00; 10:00 bar $5.11; 18:00 reopen $5.68. Vendor typicals (goldenviperea, undated): FOMC $30-60 within 2 h, NFP $20-40 within 30 min, CPI $15-35.
- **Published hour-of-day facts**: Batten et al. 2017 (5-min OTC gold, May 2000-Apr 2015): volume n-shaped, peaking 11:00-17:00 GMT (06:00-12:00 ET); gold volatility flat until 12:00 GMT, rising to a peak at 14:00 GMT (**09:00-10:00 ET**), then declining; bid-ask spread flat all day with a bump at the 21:00-22:00 GMT closure. RIETI 17-E-120 (1-min COMEX gold, 128 days 2015-16): first interval after the Tokyo open (19:00-21:05 ET winter) is the least informationally efficient of the day; NY day session (08:15-14:00 ET winter) shows informed trading; volatility L-shaped in Tokyo hours, U-shaped in London hours, declining through NY. Quantified Strategies / Quantpedia: GLD earns essentially all of its return close-to-open (11.4%/yr overnight vs 11.8% B&H; 0.04%/trade), intraday ~0.
- **Day types** (marketstalkers, GC): trend days ~45% (vs 5-10% ES), normal-variation 20-25%, normal 15-20%, neutral 10-15%; dead zones 04:00-06:00 ET (London morning + AM fix) and 12:00-14:00 ET. Own (close in top/bottom 20% of the 18:00-17:00 range): 40.0% (2019-21), 44.2% (2022-24), 40.4% (2025-26) - the record run did not make gold trendier intraday, it made it bigger; skew 25.9% top-20% closes vs 14.5% bottom-20% in 2025-26.
- **2025-26 price path** (GC month-end): Jan-25 2,812; Jun-25 3,308; Sep-25 3,873; Dec-25 4,341; **Feb-26 5,248 peak** (intraday ~5,600 late Jan); Mar-26 4,648; Jun-26 4,038; Sep-26 4,187; max DD -24.9% to 2026-07-16. Gold +27% 2024, +66-67% 2025. Daily |ret| mean 1.14%, sd 1.59%. Worst: 2026-01-30 -10.8%, 2026-03-19 -5.9%, 2025-10-21 -5.7%; best 2026-02-03 +6.1%.
- **Session ranges**: edgeful 14-day ATR (6 months to early 2026): GC Asia $116-128, London $119-130, NY $119-129 - overnight sessions carry as much range as NY. Own medians: full day $73 (2025-26) vs $24.5 (2022-24); pit 08:20-13:30 $42 vs $17; NYSE hours $40 vs $15.
- **Gold/DXY**: 30-day correlation -0.25 (Apr 2026) vs -0.45 long-run; 2025 saw gold +66% with DXY 108 -> 99.6 but 2026 "gold and DXY strength coexist" (ahasignals, StoneX). Daily/lower-frequency negative relation documented (Pukthuanthong & Roll 2011); no published intraday lead-lag edge.

---

## Strategy sections

Evidence-quality scale: 1 anecdote / vendor claim; 2 single backtest or own test only; 3 own test consistent with one published study, or two independent practitioner tests; 4 peer-reviewed plus independent OOS; 5 multiple peer-reviewed + multiple independent OOS.

### 1. Pre-AM-fix fade (short into the 05:30 ET LBMA auction)

- **Origin**: Caminschi & Heaney (2014) J. Futures Markets 34(11):1003-1039 "Fixing a leaky fixing" (GC + GLD 1-min; significant return advantages in the 4 minutes after the fix starts; early-fix trades predict the published fix direction, "in some cases exceeding 90%"; no effect after publication). Abrantes-Metz & Metz (2014; LBMA Alchemist 73 rebuttal by Fertig): screening 2001-2013, anomalous from 2004: large PM-fix moves down 92% of the time in 2010 and >= 2/3 in six years. CBS thesis (GC 5-min 2001-2018): -3.7% annualised in the 30 min before the AM fix, negative in 13 of 18 years (9 significant); "Fixing" strategy (short 05:05-05:35 and 09:35-10:05) +7.6%/yr gross but -9.3%/yr net of full spreads 2013-18. Own test extends it to 2026 at 1-min resolution.
- **Rules (objective)**: on days when London-NY offset = 5 h, **sell at the 05:28 bar open, cover at the 05:31 bar open** (market orders; variants 05:25->05:31, 05:20->05:31). No stop (3-min hold). On DST-mismatch days use 06:28->06:31. Skip if a scheduled release falls in the window (none normally).
- **Parameters**: entry 05:28, exit 05:31; 5-20 MGC; no stop.
- **Evidence (own, $ per MGC per day gross)**: 05:28-05:31: 2011-18 $1.58 (61% win, t 10.9); 2019-24 $1.57 (57%, t 7.4); **2025 $7.26 (69%, t 6.4); 2026 $11.35 (70%, t 4.9)**. 05:25-05:31: $2.14/$1.77/$7.63/$17.41 (t 11.2/6.7/5.1/6.0). Minute path 2025-26: 05:29 -1.12 bp, 05:30 -0.85 bp, 05:32 +0.48 bp. DST validation: normal days -1.06 bp (t -13.6, n 3,359, 2011-24) vs mismatch days -0.04 bp (t -0.1); mismatch days 06:28-06:31 -4.98 bp (t -5.5) in 2025-26. **Evidence quality 4** (peer-reviewed mechanism + 16-year own OOS), economically small.
- **Prop fit**: perfect shape (3-min hold, 65-70% win, no overnight, no news) but tiny: net ~$4-8 per MGC per day in 2025-26 at ~$3.2 round-trip; 10 MGC = $40-80/day, sd ~$200-330. Green-day builder for the 5 x $150 payout rule when stacked with another edge; alone needs 50+ days to pass. Fill risk: 05:28-05:31 bars average $2.0-2.6 range; MGC spread 1-2 ticks at that hour. Re-verify on GC/MGC prints.
- **Data requirements**: 1-min OHLC; London/NY DST calendar.
- **Sources**: https://ideas.repec.org/a/wly/jfutmk/v34y2014i11p1003-1039.html ; https://www.lbma.org.uk/alchemist/issue-73/has-there-been-a-decade-of-london-pm-gold-fixing-manipulation ; https://research.cbs.dk/en/studentProjects/gold-price-dynamics-around-the-clock/ ; own gold_stats3/4/5.py.

### 2. Pre-PM-fix fade (short into the 10:00 ET auction)

- **Origin**: same literature (the PM fix is the one Caminschi-Heaney and Abrantes-Metz study). CBS: -3.9% annualised in the 30 min before the PM fix. marketstalkers: PM fix + NY cut = "extension-then-reversal" into 10:00.
- **Rules**: sell 09:58 open, cover 10:01 open (variant 09:55->10:01); 10:58->11:01 on DST-mismatch days; skip days with a 10:00 ET release (ISM, UMich, JOLTS, new-home sales).
- **Evidence (own, $ per MGC per day gross)**: 09:58-10:01: 2011-18 $0.83 (t 3.3); 2019-24 $1.73 (t 3.6); 2025 $6.89 (60% win, t 3.2); 2026 $2.85 (t 0.6). 09:55-10:01: $1.75/$0.89/$8.65/$8.07 (t 5.3/1.7/3.2/1.3). DST validation: normal -0.90 bp (t -5.4, 2011-24), -1.89 bp (t -3.5, 2025-26); mismatch 10:58-11:01 -4.57 bp (t -3.4, 2025-26). **Evidence quality 3** (noisier: 10:00 also carries US data).
- **Prop fit**: half the reliability of 1, more event risk; combine as a "fix pair" (~$10-15 per MGC per day gross 2025-26).
- **Data requirements**: 1-min OHLC, DST calendar, 10:00 ET calendar.
- **Sources**: as 1; https://marketstalkers.co.uk/blog/posts/market-profile-on-gold-futures-gc.

### 3. Post-fix rebound / fix-leak momentum (10:00-10:04 direction -> 10:30; long 05:31-05:45; 10:00-10:15 "NY-cut reversal")

- **Origin**: Caminschi-Heaney leak result (pre-2015 telephone fix). marketstalkers: reversal once PM fix and NY cut clear, 10:00-10:15.
- **Rules**: (a) leak-momentum: at 10:04 go with the sign of 10:00-10:04, exit 10:30, stop 0.3%; (b) rebound: buy 05:31, sell 05:45 (and 10:01->10:15); (c) NY-cut reversal: if 08:20-10:00 move > 0.4%, fade at 10:01, target 50% retrace, stop beyond the 10:00 extreme, exit 10:30.
- **Evidence (own)**: (b) long 05:31-05:45: $1.13 (t 4.8) 2011-18, $1.13 (t 3.1) 2019-24, $1.69 (t 1.0) 2025, $1.25 (t 0.2) 2026 - decaying. Long 10:01-10:15: $2.38 (t 4.6)/$0.51/$8.41 (t 2.1)/-$1.38. (c) see section 15 (fading the pit-open run after 10:00 is not significant). **Evidence quality 2** (was 4 before the 2015 auction).
- **Prop fit**: do not trade; use only as the exit timing for 1-2.
- **Sources**: as 1; https://en.wikipedia.org/wiki/Gold_fixing.

### 4. Eastern-hours drift: long gold 18:00 -> 02:00 ET (hat shape; "PM-fix-to-AM-fix" overnight trade)

- **Origin**: Kirtley / SK Options (Benzinga, c. 2012): long from the London PM fix to the next AM fix and short AM-to-PM since 2001, "+1700%", $100M -> $2.6B gross, "not including expenses". CBS thesis (GC 5-min 2001-2018): +18.6%/yr annualised 11:00-02:00 ET vs -10.0%/yr elsewhere; Long strategy 18.6%/yr gross, Combo Sharpe 1.61 gross; net of 100% spread Long +6.3%/yr 2007-12, +1.7%/yr 2013-18; eastern returns load on China GDP and INR. Quantified Strategies/Quantpedia: GLD gains are close-to-open. RIETI: Tokyo-hours gold trading is "uninformed" (consistent with flow-driven drift).
- **Rules**: buy 18:01 (avoid the reopen print), sell 02:00; stop 0.6% (~$25 = $250 per MGC); no trade if a scheduled Asian-hours event (BoJ, China data) is flagged; optional filter: previous NY session (10:00-16:45) closed down (untested).
- **Evidence (own, 18:00-02:00, $ per MGC per day gross)**: positive 15/16 years (2022 -$0.23); 2011-21 ~$5/day, t 4.79; 2022-24 $8.20; **2025 $40.0 (t 3.0); 2026 $32.0 (t 0.7)**; 2025-26 win 55%, sd $388. **Evidence quality 3** (thesis + Kirtley + own; all gross).
- **Prop fit**: allowed by Lucid (opened 18:01, closed 02:00, inside one trading day) but a Globex-session hold through Shanghai and overnight news; 3 MGC risk ~$1,200 in a 1-sd day; only with the hard stop and a project decision to allow Globex trades. Simulate the stop's hit rate.
- **Data requirements**: 1-min OHLC; optional Asian calendar.
- **Sources**: https://www.benzinga.com/content/2286623/... (403 on fetch; via search abstract) ; CBS portal ; https://quantifiedstrategies.substack.com/p/a-quantitative-look-at-the-gold-overnight ; https://quantpedia.com/dangers-of-relying-on-ohlc-prices-the-case-of-overnight-drift-in-gdx-etf/.

### 5. Globex reopen drift: long 18:00 -> 18:30 ET

- **Origin**: own; mechanism plausible (queued Asian orders after the 17:00-18:00 halt; the 17:00->18:00 gap is ~0). Batten et al.: spread bump at the 21:00-22:00 GMT closure (i.e. a less liquid reopen).
- **Rules**: buy 18:01 open, sell 18:30; stop 0.3%.
- **Evidence (own)**: 18:00-18:30 positive 15/16 years; 2011-21 t 6.6; 2022-24 $7.24 (62%); 2025 $16.11 (63%, t 3.1); 2026 $29.80 (62%, t 2.5). First bar carries most (18:00 bar +2.56 bp 2019-24, +4.03 bp 2025-26, range $5.68). **18:01-18:30**: $1.41 (t 4.0)/$2.95 (t 4.4)/$8.41 (t 1.7)/$6.12 (t 0.4); 18:01-19:00 2025-26 $15/day (t 2.3). **Evidence quality 2** (own; spot-feed reopen prints may differ from GC).
- **Prop fit**: allowed; realistic ~$6-8 per MGC net 2025-26; second "filler" with 1 after futures verification.
- **Sources**: own gold_stats2/3/4.py; Batten et al. https://doi.org/10.1371/journal.pone.0174232.

### 6. Western-hours short: 03:00 -> 10:00 ET (London open to PM fix; "AM-to-PM fix short")

- **Origin**: Kirtley AM-fix-to-PM-fix short; CBS "Short" (sell 02:00, buy 11:00): +10.0%/yr gross 2001-18, net +6.2%/yr 2013-18, negative 2017-18; folklore "large corrections concentrate between the 10:30 and 15:00 London fixes" (search snippet).
- **Rules**: sell 03:00, cover 10:00 (or 10:01); stop 0.6%; skip if |overnight move| > 1%.
- **Evidence (own, $ per MGC per day gross)**: 2011 +$13.5, 2012 +$7.8, 2013 +$23.8 (t 3.5), 2015 +$9.6; 2017-20 negative; 2021 +$11.5; 2022-24 ~0; 2025 -$3.8; 2026 +$14.4 (t 0.26); 2025-26 win 46%, sd $376. **Evidence quality 2** (published gross effect; dead OOS).
- **Prop fit**: no.
- **Sources**: as 4; https://www.seasonalcharts.com/en/intraday/metals/gold.

### 7. NY-hours long: 10:05 -> 16:45 ET

- **Rules**: buy 10:05, sell 16:45, stop 0.8%. **Evidence (own)**: 2011-24 ~+$2/MGC/day, t < 1.5 every year; 2025 +$28.5 (59%, t 2.4); **2026 -$46.6 (44%, t -1.6)**. Quality 1-2. **Prop fit**: no (it is just long gold in US hours; inherits the trend and the 2026 drawdown).

### 8. London/NY overlap long 06:00 -> 08:00 ET

- 2025-26 +3.9 bp/day (t 2.3) but -0.8 bp in 2019-21 and 2022-24. Batten: this is the volume ramp, not a return effect. **Quality 1 (data-mined)**; listed so it is not rediscovered.

### 9. Gold opening-range breakout off the 08:20 pit open (15/30/60-minute) and its fade

- **Origin**: Crabel/Fisher ORB applied to the COMEX open. algoking "Gold ORB" (default 30-min range; stop opposite side or midpoint; target 1-2 x range; filters: daily trend, no trades within 30 min of news, DXY/S&P confirmation; "30-40% of breakouts fail"; no backtest). relaxedtrader vendor system (buys a new intraday high after the opening range, exits next session open - average hold 1.5 days, overnight; 2001-2015 backtest + live 2016-26: PF 1.69, CAGR 18.1%, 57.1% win, 531 trades, MDD 19.6% on $50k per GC). breakouttradingacademy: "breakouts of the first 30-60 min of COMEX trading have historically performed better than random-session strategies" (no numbers; recommends swing over day-trading gold). marketstalkers: COMEX IB 08:20-09:20, 45-60% of ADR, narrow IBs unusually bullish; the "80% rule" works on GC with lower hit rates and best when re-entry happens before 10:00.
- **Rules (standard)**: range = 08:20-08:35 (or 08:50 / 09:20) high-low; buy stop 1 tick above high / sell stop below low on first 1-min close beyond; stop = opposite side (cap 0.5%); exit 13:30 settlement or target 1 x range. Fade: enter against the first break when price closes back inside within 15 min; target midpoint.
- **Evidence (own, first-break follow-through to 13:30; mean excursion in range units)**: 15-min: 51.3%/+0.13x (2019-21), 47.8%/+0.01x (2022-24), **46.2%/-0.11x (2025-26)**, median range $10.2. 30-min: 51.3%/-0.05x; 52.2%/**+0.18x (t 2.7)**; **46.5%/-0.15x (t -1.5)**, median $13.6. 60-min: 47.8%/-0.05x; 54.0%/+0.18x (t 3.3); 49.2%/+0.03x, median $19.0. Single-break 33-61%. **Evidence quality 2** (vendor claims unverifiable; sign flips across regimes).
- **Prop fit**: poor. If tested: 60-min range, only when 40-day ATR is rising and the trailing single-break rate (sec. 11) > 70%; fade variant t -1.5 is not enough to risk $2,000 of room.
- **Data requirements**: 1-min OHLC.
- **Sources**: https://algoking.net/markets/uk/gold-opening-range-breakout ; https://relaxedtrader.com/store/gold-opening-range-breakout-trading-strategy/ ; https://breakouttradingacademy.com/can-you-create-an-effective-strategy-to-day-trade-gold/ ; marketstalkers (above); own.

### 10. Pit-open first-10-minute fade (short 08:20 -> 08:30 ET)

- **Rules**: sell 08:20 open, cover 08:30 open; no stop; skip 08:30-release days. **Evidence (own, $ per MGC per day gross)**: 2011-16 ~0; 2017 +$1.75 (t 2.9); 2021 +$4.26 (t 2.7); 2023 -$2.10; 2024 +$3.06 (t 1.9); **2025 +$5.05 (t 1.9, 59%); 2026 +$6.84 (t 1.3)**; 2025-26 t 2.2. Quality 1-2. **Prop fit**: marginal (~$3 net per MGC per day); 08:20 bar averages $3.54 so size costs ticks. Filler candidate after futures verification.

### 11. Initial-balance (09:30-10:30 ET) break-and-pullback - the tradethatswing / edgeful "GC IB algo"

- **Origin**: tradethatswing "Initial Balance Breakout Gold Day Trading Strategy: +445% in the Last Year" (backtest 13 Jan 2025-9 Jan 2026; updates Feb/Apr/Jul 2026); edgeful "GC IB algo that returned $106k in 12 months".
- **Rules (tradethatswing original, exact)**: session 09:30-16:00; IB = 09:30-10:30 high/low; after the first break of IB high (low) place a limit **25% of the IB range inside the broken level** (long at IB_high - 0.25 x IB); stop **60% of IB from entry**; target **50% of IB measured from the IB extreme** (long target = IB_high + 0.50 x IB); 1 GC; exit at session close if neither hit; one trade/day. Feb-2026 variant: IB 0.4-2% of price, longs only, 10% retrace entry, 35% stop, 30% target: 20 trades/3 months, 70% win, +121% on $10k, MDD 12.85%. Apr-2026 variant (2019-26 test): IB 0-2%, long+short, 25% retrace, **100% stop, 20% target**: +445% last year, "very well since about May 2024". **13 Jul 2026: "single break percentage has significantly dropped ... nearly 50/50 ... avoid until the data shows improvement."**
- **Rules (edgeful)**: 5-min; entry on 1% retrace after the IB break; stop = 60% retrace into IB; TP1 0.25 x IB, TP2 0.50 x IB; 2 GC on $50k; GC single-break 79.2% / double 13.1% / none 7.7% (6 months to Jan 2026); WR 65.8%, PF 1.935, MDD 11.6%, +$105,890, no costs stated, "re-optimise monthly".
- **Evidence (vendor)**: 142 trades in ~250 days, win "a little over 50%", avg win ~$1,100 vs avg loss ~$600 per GC, +411% on $10k, MDD 25%, commissions included. **Own replication (spot 1-min, 1 MGC gross, limit fills when touched)**: 2022-24 434 trades, 49%, PF 1.16, +$1,354 ($3/trade), DD $663; **2025 164 trades, 54%, PF 1.54, +$3,019 ($18/trade), DD $574, worst -$228; 2026 YTD 127 trades, 50%, PF 1.34, +$2,921 ($23/trade), DD $1,331, worst -$395.** Apr-26 variant: 2025 78-79% win, PF 1.49 ($10/trade); 2026 PF 1.06. Feb-26 longs-only: 2025 PF 1.83; **2026 PF 0.76**. Monthly single-break rate: 2025 68-90% (mean ~79%); 2026 Jan 81, Feb 80, Mar 82, Apr 62, May 76, Jun 73, **Jul 52**, Aug 90, **Sep 56**. Overall single-break 82% in every period 2019-26, first-break follow-through to 16:00 only ~50%, excursion +0.05-0.07 x IB - hence pullback-entry/short-target works and break-and-hold does not. **Evidence quality 3** (two vendors + own replication; honest decay).
- **Prop fit**: the best gold candidate for the eval window, **MGC only, regime-gated**. 2025: 1 MGC ~$250/month gross; 5 MGC ~$1,250/month with DD ~$2,900 (> room). Realistic: 3 MGC, stop 60% x IB (median IB $16-31 -> $100-190 per MGC -> $300-570/trade), 1 trade/day, ~13 trades/month, ~55% win. Gate: trailing-40-day single-break > 70% and IB 0.4-2% of price (Jul and Sep 2026 skipped). Consistency: avg win $180-250 per 3 MGC keeps any day < 50% of $3,000.
- **Data requirements**: 1-min OHLC (5-min for edgeful).
- **Sources**: https://tradethatswing.com/one-trade-a-day-gold-strategy-411-in-last-year-fully-automatable/ ; https://www.edgeful.com/blog/posts/gc-trading-strategy-initial-balance-algo ; own gold_stats4.py.

### 12. Asian-range (18:00-02:00 ET) London breakout, and the sweep-and-reverse variant

- **Origin**: forex "London breakout"/"Asian box" (alphanex: range 00:00-07:00 UTC = 19:00/20:00-02:00/03:00 ET, entry on candle *close* beyond the range after 07:00 UTC, stop opposite side or midpoint, TP1 1 x range, TP2 prior day H/L; filters: range size, news, Tue-Thu, HTF trend; FX pairs, no stats). pro-scalper (XAUUSD): London breaks the Asian high first 53-56% of days; 1 x range target hit ~58%, 1.5 x ~39%, 2 x ~24%; both sides swept ~18%; sweep 10-30 pips beyond the range in the first 60-90 s after 08:00 London, direction set 8-15 min after open; "delayed London breakout" = wait for a full M5 close back inside/beyond after 08:15 London, stop 10-15 pips beyond the sweep wick. grandalgo/ACY: same "London sweeps the Asia range" narrative. TradingView "Asia Session Reversal Strategy GOLD": reversal of the initial push in 01:00-02:00 UTC (20:00-21:00 ET summer) on 1-min, 30-min bias, 3:1 R:R, no stats.
- **Rules (standard, as simulated)**: range = 18:00-02:00 H/L (variant 18:00-03:00); entry = first 1-min close beyond the range 02:00-08:00; stop = midpoint capped 0.6%; exit 10:00 (variant 16:45); one trade/day. Sweep-and-reverse variant (objective reading of pro-scalper): if price trades beyond the range 03:00-03:15 ET and a 5-min bar closes back inside by 03:30, enter toward the opposite side, stop 0.15% beyond the sweep extreme, target the opposite range edge, exit 10:00.
- **Evidence (own, 1 MGC gross)**: breakout 2022-24: 688 trades, 32% win, PF 0.97, -$637, DD $2,690 (16:45 exit PF 1.04); 2025: 202 trades, 39%, PF 1.08, +$1,133, DD $1,864 (16:45: PF 1.14, +$2,348, DD $2,698); **2026: 125 trades, 49%, PF 1.38, +$5,250, DD $3,964**. First-break follow-through to 10:00: 47-51% (2019-24), **55.5% in 2025-26, excursion +0.11 x range (t 2.6)**; single-break 69% -> 87.5% (Asian range median $40 vs $9). Sweep-and-reverse not simulated (needs the first pass's 03:00-03:30 bars; low priority given 59% continuation in sec. 13). **Evidence quality 2** (vendor stats on XAUUSD CFDs unverifiable).
- **Prop fit**: poor for $2,000 trailing: 32-49% win, DD $2-4k per MGC, 2026 profit from a few trend days (consistency killer). Usable fact: hold a London break rather than fade it in 2025-26.
- **Data requirements**: 1-min OHLC.
- **Sources**: https://alphanex.io/blog/london-breakout-strategy ; https://www.pro-scalper.com/xauusd-strategies/asian-session-gold-strategy ; https://grandalgo.com/blog/asian-session-trading-strategy ; https://kr.tradingview.com/script/CSROlPWp-Asia-Session-Reversal-Strategy-GOLD-Full-Version ; own gold_stats2/4.py.

### 13. Asian accumulation -> London-open reversal (fade the overnight move at 03:00)

- **Rules (standard)**: if 18:00-03:00 move > +0.5% sell at 03:00 (mirror), target Asian midpoint, stop 0.4%, exit 10:00. **Evidence (own)**: P(London sign opposite to Asia) 51.3% (2019-21), 50.9% (2022-24), **46.3% (2025-26)**; conditional on |Asia| > 0.5%: 50.3%, 53.5%, **40.6%** (59% continuation; London after Asian up +7.1 bp, after down -7.0 bp). corr 0.03/0.03/-0.04. **Quality 2 - refuted.** Prop fit: no.

### 14. US-open (09:30 ET) reversal of the pre-open move

- **Rules**: if 08:20-09:30 > +0.3% (0.5%) sell 09:30, cover 11:00, stop 0.4%; mirror. **Evidence (own)**: 2019-24 after +0.3%: +1.6 bp (54% up); after -0.3%: -2.4 bp. 2025-26 after +0.3%: -11.2 bp (49% up, t -1.1, n 77); after +0.5%: -0.1 bp; after -0.3%: +1.8 bp. ikeawesom XAUUSD PDH/PDL sweep backtest claims ~70% win (71.2% on 15-min) but its R:R, costs and period are not disclosed. **Quality 1.** Prop fit: no.

### 15. PM-fix / NY-cut reversal of the pit-open run (08:20-10:00 > 0.5% -> fade 10:00-13:30)

- **Rules**: if 08:20-10:00 > +0.5% sell 10:01, cover 13:30; mirror. **Evidence (own)**: 2019-24 after +0.5%: -1.1 bp (52% up); after -0.5%: -7.9 bp. 2025-26 after +0.5%: -5.8 bp (47% up, n 57, t -0.8); after -0.5%: -19.2 bp but 58% up (crash-day tail). marketstalkers' "extension-then-reversal at 10:00" is a market-profile observation without numbers. **Quality 1.** Not tradable as stated; a 10:01-10:30 version with a tight stop is untested.

### 16. London-session -> NY-session continuation (edgeful "81%")

- **Origin**: edgeful "when GC's London session (03:00-11:00) closes positive, NY follows green 81%"; edgeful market-session breakout report (YM: NY breaks London H or L 83.2%, double 4.8%, none 12%; rules: wait for 11:00 London close, bias from the opening-candle colour, target the London H/L).
- **Rules (literal)**: at 11:00, if 03:00-11:00 is up, buy to 16:00 (mirror). Breakout version: after 11:00 trade the first break of the 03:00-11:00 range, stop midpoint, target 1 x range, exit 16:00.
- **Evidence (own, non-overlapping 11:00-16:00)**: P(up | London up) 52.9% (2019-24, +2.8 bp, t 1.7), **51.0% (2025-26, -1.6 bp)**; P(up | London down) 50.4%/59.3%; corr 0.08/-0.06. The 81% only reproduces if NY overlaps London (09:30-11:00). **Quality 1.** Prop fit: no.
- **Sources**: https://www.edgeful.com/blog/posts/trading-sessions-explained ; https://www.edgeful.com/blog/posts/market-session-breakout-report-trading-strategy.

### 17. Overnight-move continuation / trend-day following (2025-26 record-run behaviour)

- **Rules**: if 18:00-09:30 > +0.5% (1%), buy 09:30, hold to 16:00, stop at the overnight midpoint; mirror. **Evidence (own)**: corr(overnight, NYSE hours) 0.03 (2019-24), 0.10 (2025-26). After > +0.5%: +0.1 bp (55%) / +3.1 bp (57%, t 0.5); > +1%: +2.3/+1.7 bp; < -0.5%: -7.8 (44%) / -5.4 bp (50%); < -1%: -8.2/-13.1 bp (47%). Trend-day share 40-44% all periods (marketstalkers ~45%). **Quality 1-2**: mild down-continuation (crash days), no up-continuation beyond drift.
- **Prop fit**: filter only - no pullback longs on days that gapped down > 1% (2026-01-30, 2026-03-19 type).

### 18. Unger Academy intraday systems on gold futures (three published logics)

- **Origin**: Unger Academy blog posts (GC, 5-min, data from 2008; symmetrical long/short; EOD exit; monetary stop/target/breakeven). (a) "Intraday mean-reverting": wait for a directional move, enter the opposite way when recovery is signalled - long when recent lows are broken and price recovers, i.e. a **false-breakout of the previous session's low/high** (companion post: 15-min bars for the false-break test; hybrid 5-min long / 15-min short); 600 trades/15 years (~40/yr), net $67,000, avg $110/GC; $22,000 Apr 2021-Apr 2023 ($260/trade); OOS since 2018 avg ~$135, 80% profitable in 2022 "net of fees and slippage". blog2 version (Aug 2024): stop $1,800, target $1,600 per GC, ~650 trades since 2016, win > 50%, avg ~$144. (b) "Flat-session breakout" (trend): **if yesterday's close is within a small distance of the previous close (a "flat" session), buy a break of yesterday's high / sell a break of yesterday's low, exit end of session**, trades last ~2 h; 1,200 trades, net $202,000, avg $162/GC, live since 2016 "performing as in-sample". (c) Aug-2025 "Strategy of the Month: intraday reversal on gold" (page bot-walled; no rules).
- **Rules (objective interpretation)**: (a) on 15-min bars, if a bar's low < previous session low and a later bar closes back above it (within the same session, before 13:00 ET), buy at that close; stop $18/oz, target $16/oz (MGC: $180/$160), exit 16:45; mirror. (b) if |close(d-1) - close(d-2)| < 0.3 x ATR(20) [threshold unspecified by Unger; 0.3 x ATR is the standard reading], buy stop at high(d-1) + 1 tick / sell stop at low(d-1) - 1 tick, active 03:00-13:00 ET, stop $20/oz, no target, exit 16:45.
- **Evidence**: vendor equity curves only, 1 GC, no DD/PF disclosed; both are **multi-year** and (b) has a live record since 2016 per the vendor. **Quality 2.**
- **Prop fit**: (a) long-when-weak, suffered in 2026 crash days (MGC stop $180 hit repeatedly) - low priority; (b) is a proper day-trade trend rule with a prior-day reference and a flat filter; test on 1-min with MGC sizing (stop $200/MGC). Both avg trades ($110-162 per GC = $11-16 per MGC) are thin after costs.
- **Data requirements**: 1-min OHLC (daily closes derived).
- **Sources**: https://ungeracademy.com/blog/intraday-trading-on-gold-usd37-000-of-gain-in-2-years-with-these-strategies-rules-details ; https://ungeracademy.com/?p=6696 ; https://blog2.ungeracademy.com/exploring-gold-futures-with-trend-following-and-mean-reverting-strategies/ ; https://ungeracademy.com/?p=8581 (blocked).

### 19. Vendor benchmark: Aeromir "Goldilocks" (2 MGC, 4-min, ~03:00 -> 13:30 ET)

- Proprietary entries; trades 2 MGC "from just after the European open until the RTH close"; live-streamed track 14 Oct 2024-13 Feb 2026: 479 trades, net $21,378, 48.0% win, PF 1.32, avg $45/trade, **max DD $8,368**, Calmar 2.55, ~$1,330/month. Quality 2 (vendor, unaudited). Its $8.4k DD on 2 MGC is 4x Lucid's room: the realistic ceiling for a "working" retail gold bot and a warning for sizing. Sources: https://aeromir.com/?p=1377261 ; https://futures.aeromir.com/goldilocks.

### 20. MGC 5-minute OU / z-score mean reversion (do not)

- **Origin**: Mesfin (2026) arXiv 2605.04004 "Structural limits of OHLCV-based intraday momentum signals in MNQ futures" sec. 4.8 - independent cross-instrument test on MGC 5-min, 1,091 days (2021-2025), friction 0.50 pt ($5) round trip, OOS 2023/2024/2025.
- **Rules**: OU z-score on 5-min bars, enter at |z| > 1.5 or 2.0, long and short, exit at mean/time.
- **Evidence (Table 9)**: z1.5 long N 2,634 net -0.55 pt t -5.32 (2023 -1.97, 2024 -2.24, 2025 -0.08); z1.5 short N 3,059 -0.49 t -4.36; z2.0 long N 1,172 -0.27 t -1.63 (2025 +0.52); z2.0 short N 1,421 -0.39 t -2.11; all FAIL. 60-min OU half-life ~8 h, "structurally incompatible with intraday execution". MGC Hurst ~0.5 (random walk) vs MNQ 0.59. **Quality 3** (independent OOS failure). Related null: Abond1234 (GC 1-min 2021-2026) - 196 pre-registered directional strategies across trend/MR/breakout/vol/VWAP/session/regime families, none advanced; BH q = 1.0; CSCV overfit probability 0 with zero OOS profit.
- **Sources**: https://arxiv.org/abs/2605.04004 ; https://github.com/Abond1234/GC-1m-OHLCV-QUANTITATIVE-ANALYSIS.

### 21. Day-of-week filters for gold sessions

- **Published**: In Gold We Trust (GLD 11/2004-12/2023): Monday -0.01%, Friday +0.11% average daily return, all other days positive; skipping Mondays lifts GLD 330.8% -> 412.1%. Weekday study (Tokyo/London/NY, 2016): Friday significantly positive, Tuesday significantly negative. Tully & Lucey (COMEX 1982-2002): no robust weekday seasonality. Practitioner: Tue-Thu "most consistent" (goldenviperea, alphanex).
- **Own (intraday windows)**: Asia-hours Friday +10.3 bp (t 4.0) and Monday -6.0 bp (t -1.8) in 2022-24; 2025-26 Wednesday +28 bp (t 3.3), Friday +1.5 bp - no persistence; NYSE-hours by weekday nothing with |t| > 1.3. **Quality 1-2** (daily Friday effect is real-ish at the daily level but not an intraday rule). Use none, except a possible "no new longs Monday Asia" sanity filter.
- **Sources**: https://ingoldwetrust.report/nuggets/calendar-anomalies-and-the-gold-market/?lang=en ; https://businessperspectives.org/.../weekday-effects-on-gold-tokyo-london-and-new-york-markets.

### 22. Gold / US-dollar (DXY) intraday lead-lag filter

- **Origin**: Pukthuanthong & Roll (2011 JBF), Reboredo (2013), Capie-Mills-Wood (2005): negative daily relation. 2025-26: 30-day corr -0.25 (Apr 2026) vs -0.45 baseline; weekly windows swing to -0.92; "the same CPI print can lift both" (ahasignals, StoneX, marctomarket). No published intraday lead-lag edge found.
- **Rules (if DXY/EURUSD intraday is loaded)**: trade gold only with the 30-min DXY move (gold long if DXY down > 0.1%); or gate longs off when the 20-day gold/DXY correlation > 0 (decoupled regime). **Quality 2** as a filter, untested.
- **Data requirement: DXY or EURUSD 1-min - not in the current data set** (histdata EURUSD 1-min is downloadable with the existing script).
- **Sources**: https://ahasignals.com/gold-dxy-divergence-tracker/ ; https://www.stonex.com/en-gb/news-and-analysis/us-dollar-rebound-puts-gold-bear-pennant-in-focus-2026-09-01/.

### 23. Macro-print handling: jump avoidance and post-event continuation (08:30 / 10:00 / 14:00 ET)

- **Avoidance rule**: no new entries 08:28-08:35, 09:58-10:05 (unless running 1-2 deliberately), 13:58-14:10 on FOMC days; flatten before 08:30 on CPI/NFP with > 1 MGC. Own bar sizes: 08:30 $5.72, 10:00 $5.11, 18:00 $5.68 vs ~$3 baseline. Vendor typicals: FOMC $30-60/2 h, NFP $20-40/30 min, CPI $15-35.
- **Continuation rule (breakouttradingacademy, objective reading)**: after a CPI/FOMC release that moves gold > 1% within 15 min, wait for a 15-30 min consolidation, then enter on the break of that consolidation in the direction of the initial move; stop = consolidation opposite side; exit 13:30 (CPI) / 16:45 (FOMC). No stats published. Mesfin (MNQ) found no persistent post-news drift once the spike bars are excluded (12 trades, mean -9.56 pts) - a caution. The "fade 14:00, go with 14:30" FOMC rule circulating (94% over 33 events) is for SPY/SPX, anecdotal, and not gold evidence.
- **Quality 2** (avoidance), 1 (continuation). **Data requirements**: economic calendar.
- **Sources**: breakouttradingacademy (above) ; https://thefinancialbit.beehiiv.com/p/profitable-strategy ; https://www.goldenviperea.com/blog/gold-trading/gold-trading-sessions/.

### 24. EMA-pullback "4-phase state machine" on XAUUSD 5-min (ilahuerta-IA, GitHub)

- **Rules (exact from the repo)**: 5-min bars, liquid-hours filter; EMA(1) vs EMA(14/18/24) multi-crossover with an EMA-angle (trend strength) filter -> ARMED; wait for a 1-3 bar counter-trend pullback -> WINDOW_OPEN (2 bars); enter on breakout of the pullback bar's high (low); stop 2.5 x ATR; target 12 x ATR; OCA bracket; invalidate on opposite signal; 1% risk sizing.
- **Evidence (repo backtest, XAUUSD 5-min 10 Jul 2020-25 Jul 2025, 100 oz)**: 175 trades (~3/month), 55.4% win, PF 1.64, Sharpe 0.89, MDD 5.81% ($7,059 on $100k), +44.75%, avg win $1,187 / avg loss -$913, expectancy $251/trade. Single in-sample run, CFD data, no slippage stated. **Quality 2.**
- **Prop fit**: 12 x ATR targets mean multi-hour/overnight holds (not flat-by-close as written); converted to a 16:45 exit the expectancy is unknown. Per MGC the $913 average loss = ~$91 - compatible with room, but ~3 trades/month cannot pass an eval. Low priority; useful as a trend-pullback template for sec. 11's gate.
- **Data requirements**: 1-min/5-min OHLC.
- **Source**: https://github.com/ilahuerta-IA/backtrader-pullback-window-xauusd.

### 25. VWAP pullback (drift-VWAP; TradingView "GC/MGC VWAP Pullback ADX Regime Prop-Safe"; "Gold Asia VWAP Pullback Trend")

- **Rules (Harry197 drift-VWAP, exact)**: skip 09:30-10:30; require price on one side of VWAP, VWAP slope consistent over 15 min, and >= 0.1% move in that direction over the past hour; enter at the open of the bar after the first pullback bar that touches VWAP; ~80 pts risk for 40-50 pts target (gold units as given); max 4 trades/day, stop after 2 consecutive losses, no entries after 15:30, flat 15:55. TradingView prop-safe version (404 on fetch): ADX regime gate, VWAP pullback, daily loss limit. Asia version: pullback to session VWAP in trend direction during the Asia window, ATR stop, optional session-end exit (no stats).
- **Evidence**: Harry197 on GC=F 19 Jul-28 Sep 2026: 36 trades, 47.2% win, -0.050%/trade, t -1.5; walk-forward grid 27 settings: **0 of 27 positive in both halves**; "no edge survived costs". Quality 2 (negative). Generic VWAP-bounce claims (55-65% win on large-cap stocks) are not gold evidence.
- **Prop fit**: no on current evidence. **Data requirement: VWAP needs volume - not available; a TWAP/typical-price proxy must be flagged as an approximation.**
- **Sources**: https://github.com/Harry197-beep/drift-vwap-strategy_ ; https://www.tradingview.com/script/NWBqWw6O-Gold-Asia-VWAP-Pullback-Trend-Entries-Exits/ ; https://jp.tradingview.com/script/spuY1FTo-GC-MGC-VWAP-Pullback-ADX-Regime-Prop-Safe (404).

### 26. Session-regime indicator stacks published for prop accounts (TradingView mattkelly914 "Gold Futures Prop-Firm Strategy (GC) 1-18-2026"; MrHalo993 "Enhanced Gold Scalping")

- **Rules (mattkelly914, exact)**: 5-15 min; longs only; NY AM 08:30-11:30 trend mode: ADX(14) > 30, price > EMA200, EMA21 crosses above EMA55 or 20-bar high break, volume > 1.4 x SMA20, max 2 trades; NY PM 11:30-15:00 and Asia 18:00-02:00 mean-reversion mode: ADX <= 30, close < lower BB(20,2), RSI(14) < 25, max 2 trades/session; stop 1.7 x ATR(14); trail activates at +1.0 ATR, trails 1.0 ATR; daily loss halt -$600; news blackout CPI/NFP/ISM/FOMC. No performance shown. **MrHalo993**: 15-min, MACD cross + RSI(>30 long/<70 short) + EMA50 side + ATR threshold, hours 08:00-20:00 Amsterdam (02:00-14:00 ET), ATR stop, R:R 2:1; no stats.
- **Evidence**: none published. Abond1234's 196-strategy null covers exactly these families on GC 1-min 2021-26. **Quality 1.**
- **Prop fit**: structure (session modes, ADX gate, daily loss halt, news blackout) is a sensible wrapper; the signals themselves have no evidence. Volume filter not computable on our data (flag).
- **Sources**: https://www.tradingview.com/script/7fdK8QOM-Gold-Futures-Prop-Firm-Strategy-GC-1-18-2026/ ; https://in.tradingview.com/script/kMJnP1lu-Enhanced-Gold-Scalping-Strategy-Backtest-with-Time-Filter/.

### 27. Close-hour drift (16:00-17:00 ET) - diagnostic only

- 16:00-17:00: -1.63 bp (t -3.7) 2019-21, +0.35 bp 2022-24, -1.73 bp (t -1.8) 2025-26; the 16:45-17:00 slice negative every period (short t 2.4/3.5/4.1), 16:59 bar -0.93 to -1.24 bp (settlement/last-print artefact). Lucid needs flat by 16:45, so untradeable; implication: do not carry a long into 16:45, and spot-feed last bars are noisy.

### Crude (CL/MCL) - reference only

Not backtestable here (no 2024-26 data). The analogous structural clocks are the 09:00 ET pit open, 10:30 ET EIA (Wed), 14:30 ET settlement, and the 11:00-14:30 trend-day window; the Unger "flat-session breakout" and "false-break of prior-day H/L" logics are the same ones they publish for CL. Nothing further recorded.

---

## What the evidence says works in 2022-2026 (gold)

**Works, with caveats**
- *Pre-fix fade (05:28-05:31; 09:58-10:01 ET)*: peer-reviewed mechanism, alive in 2025-26 (t > 4 AM, t ~3 PM in 2025), 65-70% win, verified by the DST shift; $7-11 per MGC per day gross, below cost before 2025. Consistency builder at 5-20 MGC after futures-print verification.
- *IB (09:30-10:30) break-and-pullback (sec. 11)*: PF 1.5 (2025) / 1.3 (2026 YTD) gross per MGC, 50-54% win, ~$20/trade; dead 2022-24; author-withdrawn Jul 2026; gate on trailing single-break > 70% and IB 0.4-2%. **First gold candidate for the Lucid simulator.**
- *Eastern-hours long (18:00-02:00)*: most persistent long window (15/16 years; Kirtley/CBS lineage), large in 2025-26, but a Globex hold with sd ~$390 per MGC per day; only with a 0.6% stop and a project decision on Globex trades.
- *Reopen drift (18:01-18:30)*: small, consistent pre-2025, execution-sensitive.
- *Unger "flat-session breakout" (sec. 18b)*: the only vendor gold day-trade with a claimed live record since 2016; untested here; thin per-trade edge; worth one replication.

**Does not work / refuted on 2022-2026 data**
- Western-hours short 03:00-10:00 (dead since 2017); NY-hours long (sign flips; -$47/MGC/day 2026); pit-open ORB breakout (46% follow-through 2025-26) and fade (t -1.5); Asian-range London breakout (PF 0.97-1.14, DD $2-4k/MGC); Asian->London reversal (59% continuation); US-open reversal; London->NY "81%" (52% on OHLC); PM-fix reversal; weekday filters; MGC OU/z-score MR (Mesfin t -5.3); VWAP pullback on gold (0/27 grid cells); post-fix leak momentum (killed by the 2015 auction); every generic indicator stack (Abond1234: 196 strategies, none; BH q = 1.0).

**Regime facts the backtest must respect (2025-01 to 2026-09)**
- Daily range tripled vs 2022-24 (median $73 vs $24.5; 2026Q1 $133; ATR14 peak $247). One MGC carries $730-1,330 of daily range. The $2,000 EOD-trailing floor allows **1-3 MGC with $100-250 stops**, never a GC (Aeromir's 2-MGC bot drew down $8.4k).
- 2025 = up-trend (25.9% top-fifth closes); 2026 = -24.9% drawdown with -10.8%/-5.9%/-5.7% days. Any long-biased rule must be tested on both halves.
- Costs: Lucid GC $2.30/side; MGC assume $0.50-0.75/side; MGC spread 1-2 ticks in liquid hours, wider at 18:00 and fix minutes; Mesfin's $5 round-trip is the stress case; net edge must exceed ~$5 per MGC per trade. GC->MGC same-minute fill match only 80% (Abond1234): add 1 tick slippage.
- Spot vs futures: fix-minute and session effects transfer; 18:00 reopen and 16:59 prints are feed-specific. Re-run sections 1, 2, 5, 10 on GC/MGC 1-min before committing money.

---

## Position-sizing reference (50K Lucid Flex, 2025-2026 gold)

| Item | GC | MGC |
|---|---|---|
| Size | 100 oz | 10 oz |
| Tick | $0.10 = $10 | $0.10 = $1.00 |
| $ per $1/oz move | $100 | $10 |
| Hours | 18:00-17:00 ET Sun-Fri; settle 13:29-13:30 ET | same |
| Lucid commission/side | $2.30 | not listed (assume $0.50-0.75) |
| Prop day margin (typical) | - | $100-300 |
| Median daily range 2025-26 ($73) | $7,300 | $730 |
| Median daily range 2026Q1 ($133) | $13,300 | $1,330 |
| Mean 1-min range 09:00-11:00 ET ($3.1) | $310 | $31 |
| 08:30 ET bar mean range ($5.7) | $570 | $57 |
| 14-day ATR peak Feb 2026 ($247) | $24,700 | $2,470 |
| Worst day 2026-01-30 (-10.8%, ~$500) | ~$50,000 | ~$5,000 |

Rule of thumb for a $2,000 EOD-trailing room: risk <= $200-300 per trade (10-15% of room) => 2-3 MGC with a $10 stop (~0.25% of price) or 1 MGC with a $25 stop; one position at a time; no gold through 08:30 on CPI/NFP with > 1 MGC. The 40-micro eval cap is never binding; the drawdown is. Eval maths: a $3,000 target with the 50% consistency rule needs >= 2 profitable days of ~$1,500 or, realistically, 10-20 days of $150-300 - which is exactly the "fix pair + IB algo + reopen" basket's profile, not a single trend-day's.

---

## Sources

Academic / peer-reviewed
- Caminschi & Heaney (2014) "Fixing a leaky fixing", J. Futures Markets 34(11) 1003-1039 - https://ideas.repec.org/a/wly/jfutmk/v34y2014i11p1003-1039.html (Wiley 403)
- Abrantes-Metz & Metz (2014) via LBMA Alchemist 73 (Fertig) - https://www.lbma.org.uk/alchemist/issue-73/has-there-been-a-decade-of-london-pm-gold-fixing-manipulation
- Batten, Lucey, McGroarty, Peat, Urquhart (2017) "Stylized facts of intraday precious metals", PLoS ONE 12(4) - https://pdfs.semanticscholar.org/d107/164c9810e46729698c5f0c410f8be78c5f10.pdf
- RIETI DP 17-E-120 "Intraday seasonality in efficiency, liquidity, volatility and volume: platinum and gold futures in Tokyo and New York" - https://www.rieti.go.jp/jp/publications/dp/17e120.pdf
- Donati & Jung (2019) CBS thesis "Gold Price Dynamics Around the Clock" - https://research.cbs.dk/en/studentProjects/gold-price-dynamics-around-the-clock/ (PDF 403 this session)
- Mesfin (2026) arXiv 2605.04004 (MGC OU table 9) - https://arxiv.org/abs/2605.04004
- Quantpedia "An extensive test of market timing strategies in the gold market" (1990-2015) - https://quantpedia.com/an-extensive-test-of-market-timing-strategies-in-the-gold-market/
- Weekday effects on gold: Tokyo, London, NY (2016) - https://businessperspectives.org/component/zoo/weekday-effects-on-gold-tokyo-london-and-new-york-markets
- Pukthuanthong & Roll (2011) "Gold and the Dollar" JBF (not fetched)

Practitioner / vendor
- tradethatswing IB gold - https://tradethatswing.com/one-trade-a-day-gold-strategy-411-in-last-year-fully-automatable/
- edgeful GC IB algo, sessions, session-breakout report - https://www.edgeful.com/blog/posts/gc-trading-strategy-initial-balance-algo ; https://www.edgeful.com/blog/posts/trading-sessions-explained ; https://www.edgeful.com/blog/posts/market-session-breakout-report-trading-strategy
- marketstalkers GC market profile - https://marketstalkers.co.uk/blog/posts/market-profile-on-gold-futures-gc
- Unger Academy - https://ungeracademy.com/blog/intraday-trading-on-gold-usd37-000-of-gain-in-2-years-with-these-strategies-rules-details ; https://ungeracademy.com/?p=6696 ; https://blog2.ungeracademy.com/exploring-gold-futures-with-trend-following-and-mean-reverting-strategies/
- pro-scalper Asian session gold - https://www.pro-scalper.com/xauusd-strategies/asian-session-gold-strategy
- alphanex London breakout - https://alphanex.io/blog/london-breakout-strategy
- algoking gold ORB - https://algoking.net/markets/uk/gold-opening-range-breakout ; relaxedtrader - https://relaxedtrader.com/store/gold-opening-range-breakout-trading-strategy/
- breakouttradingacademy - https://breakouttradingacademy.com/can-you-create-an-effective-strategy-to-day-trade-gold/
- Quantified Strategies GLD overnight - https://quantifiedstrategies.substack.com/p/a-quantitative-look-at-the-gold-overnight ; Quantpedia GDX overnight - https://quantpedia.com/dangers-of-relying-on-ohlc-prices-the-case-of-overnight-drift-in-gdx-etf/
- Kirtley/SK Options overnight gold trade (Benzinga, 403) - https://www.benzinga.com/content/2286623/the-overnight-gold-trade-that-is-up-1700-since-2001-sam-kirtley-of-sk-options-tradin
- In Gold We Trust calendar anomalies - https://ingoldwetrust.report/nuggets/calendar-anomalies-and-the-gold-market/?lang=en
- Aeromir Goldilocks - https://aeromir.com/?p=1377261
- goldenviperea sessions - https://www.goldenviperea.com/blog/gold-trading/gold-trading-sessions/ ; quantvps - https://www.quantvps.com/blog/when-to-trade-gold ; tradersmastermind hours - https://tradersmastermind.com/gold-trading-hours-comex-london-fix/ ; fortraders hours - https://fortraders.com/blog/gold-futures-trading-hours ; theforexscalpers MGC - https://theforexscalpers.com/mgc-micro-gold-futures-trading-for-beginners-complete-2025-scalping-guide/ ; damnpropfirms MGC - https://damnpropfirms.com/trading-guides/mgc-tick-value-micro-gold-futures-contract-specs/
- Gold/DXY - https://ahasignals.com/gold-dxy-divergence-tracker/ ; https://www.stonex.com/en-gb/news-and-analysis/us-dollar-rebound-puts-gold-bear-pennant-in-focus-2026-09-01/
- Jan-2026 crash - https://www.wisdomtree.com/us/insights/blog/gold-and-silvers-most-volatile-day ; https://gvwire.com/2026/01/30/gold-set-for-steepest-daily-drop-since-1983-silver-eyes-worst-day-ever/ ; https://www.cnbc.com/2026/01/26/gold-record-surges-past-new-5000-record.html

Code / open implementations
- Abond1234 GC 1-min study - https://github.com/Abond1234/GC-1m-OHLCV-QUANTITATIVE-ANALYSIS
- ilahuerta-IA XAUUSD pullback - https://github.com/ilahuerta-IA/backtrader-pullback-window-xauusd
- Harry197-beep drift VWAP - https://github.com/Harry197-beep/drift-vwap-strategy_
- ikeawesom XAUUSD PDH/PDL sweep - https://github.com/ikeawesom/xauusd-backtest ; yulz008 GOLD_ORB EA - https://github.com/yulz008/GOLD_ORB
- TradingView: mattkelly914 GC prop-firm - https://www.tradingview.com/script/7fdK8QOM-Gold-Futures-Prop-Firm-Strategy-GC-1-18-2026/ ; Asia Session Reversal GOLD - https://kr.tradingview.com/script/CSROlPWp-Asia-Session-Reversal-Strategy-GOLD-Full-Version ; Gold Asia VWAP Pullback - https://www.tradingview.com/script/NWBqWw6O-Gold-Asia-VWAP-Pullback-Trend-Entries-Exits/ ; Enhanced Gold Scalping - https://in.tradingview.com/script/kMJnP1lu-Enhanced-Gold-Scalping-Strategy-Backtest-with-Time-Filter/

Sibling reports: research/families/calendar_seasonal_structural.md s.18; microstructure_volume_profile.md s.10; orb_session.md s.6.3; evidence_and_failures.md s.4; bot_popular_indicators.md s.2.22. Own statistics: `data/parquet/XAUUSD_1m.parquet`, `data/parquet/GC_1d.parquet`; scripts gold_stats.py ... gold_stats5.py (session scratchpad).
