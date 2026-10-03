# Family: Calendar, Seasonal, Time-of-Day and Structural-Flow Effects (index futures and gold)

Research sweep date: 2026-10-03. Scope: overnight-vs-intraday split (Knuteson; Lou/Polk/Skouras), weekday effects and Turnaround Tuesday, turn-of-month / payday / month-end "dash for cash", pre-FOMC drift (Lucca and Moench) and FOMC-day patterns, CPI/NFP-day patterns, options expiration (OPEX week, quad witching, 0DTE amplification), VIX expiration, closing-auction (MOC) flows 15:50-16:00, lunch doldrums, first/last-30-minute intraday momentum (Gao-Han-Li-Zhou), pre-holiday and Santa rally, Keloharju return seasonality, gold round-the-clock seasonality and London fixes. All times are US Eastern (ET).

Target use: Lucid Trading 50K LucidFlex (eval target $3,000; $2,000 END-OF-DAY trailing drawdown checked intraday; 50% consistency rule in eval; funded: no consistency, EOD trailing locks at $50,100 once EOD balance reaches $52,100; payout needs 5 separate days with >= $150 EOD profit and a net-positive cycle; 4 minis / 40 micros in eval, 2 minis / 20 micros at funded start; flat before close, no overnight/weekend holding). Data available: 1-minute OHLC without volume for ES/NQ/GC proxies, Nov 2010 to Sep 2026; daily futures and VIX from Yahoo.

Search budget note: the shared session hit its WebSearch cap after 12 searches in this sweep, so the remaining evidence was pulled by fetching ~35 pages/papers directly (Quantpedia, CXO Advisory, NY Fed staff report 512 (Lucca-Moench), Gao-Han-Li-Zhou (SSRN 2440866), Caporale-Plastun CESifo 9360, Keloharju-Linnainmaa-Nyberg NBER 20815, a Copenhagen Business School 2001-2018 gold microstructure thesis, Caminschi-Heaney JFM 2014, Elms SSRN 6564078 via Harbourfront, Cboe 0DTE study, Imperial MOC-imbalance thesis, Applied Economics & Finance 2025 weekday-overnight paper, Kosch-Forsberg arXiv 2609.12227, Seasonax, Schaeffer's, Shareplanner, TradeQuantix, Investui, Wikipedia/Stock Trader's Almanac). Pages that could not be read (403/paywall/503) are noted where relevant.

---

## 0. Executive summary

1. **The dominant structural fact in this family is that index returns accrue overnight, not intraday.** SPY 1993-2024: 480.57 of 530.53 points (90.6%) came close-to-open; QQQ 92.9% (Applied Economics & Finance 2025, Table 2). Knuteson (arXiv 2201.00223) shows the same for all major indices 1990-2021. For a day-trade-only prop account this is bad news for *any* long-biased intraday holding rule: the unconditional open-to-close drift in ES/NQ is ~zero to slightly negative, and the "always long the last half-hour" benchmark earned -1.11%/yr (Gao et al. 1993-2013). Everything below must therefore be a *conditional* intraday rule, not a buy-the-day rule. Quantpedia also warns the overnight/intraday gap nearly vanished in 2010-2021 before reappearing 2017-2020, i.e. it is regime-dependent.

2. **The only effects in this family with (a) peer-reviewed evidence, (b) an intraday, flat-by-close implementation, and (c) at least some post-2020 confirmation are:**
   - **Pre-FOMC morning drift** (Lucca-Moench, NY Fed SR 512): +49 bp in the 2pm-to-2pm window before scheduled announcements (131 meetings 1994-2011, 98/131 positive, Sharpe 1.14), with the drift concentrated in the *morning of the announcement day* and zero average return after 2:00 pm. Out-of-sample 2011-2015 it was +26 bp/meeting but not significant (31 meetings); Applied Economics 2025 finds it survives for press-conference meetings. Only 8 days per year.
   - **Market intraday momentum** (Gao-Han-Li-Zhou, 2018 JFE): sign of the 9:30-10:00 return (vs prior close) predicts the 15:30-16:00 return. Timing strategy: 6.67%/yr, vol 6.19%, Sharpe 1.08, 54.4% success, in the market only 30 minutes a day; after bid-ask costs 4.46%/yr (post-2001) and 6.52%/yr (post-2005). Adding the 15:00-15:30 sign as a confirmation (trade only when both agree) cuts return to 4.39% but lifts success rate to 77%. R2 on FOMC-minutes days 11.0% vs 2.5% otherwise; gains ~3x on CPI days and ~4x on FOMC-minutes days.
   - **Witching-day weakness**: S&P 500 negative on 57% and Nasdaq negative on 67% of quad-witching days 2000-2021 (Caporale-Plastun CESifo 9360, significant in 7/7 tests for SPX d(0)); Schaeffer's: since 2021 the SPX was positive in <30% of triple-witching *weeks*, averaging -0.71%. Seasonax (2006-2021, 59 events): +0.58% avg, 71% win in the 5 days before the witching day, then weakness on the day itself.
   - **Expiration-day range amplification**: Elms (SSRN 6564078, 2016-2025, 2,294 days): high near-expiry ATM open interest is associated with ~16% wider daily ranges (p<0.001); no pinning. Implication for ES/NQ: favour breakout/continuation over fade on monthly OPEX and quarterly witching Fridays.

3. **Effects that are real on a close-to-close basis but die when forced into a flat-by-close implementation**: turn-of-the-month, option-expiration week, pre-holiday day, Santa rally, weekday overnight seasonality, payday effect. Each is mostly an overnight/gap phenomenon; the Atlanta Fed futures study found TOTM in S&P futures "disappeared after 1990", and Quantpedia's own 1993-2019 daily versions earn only 2-5%/yr with 7-20% drawdowns. Use these only as *day-selection filters / bias tilts* for a base intraday strategy, never as stand-alone edges.

4. **Flow effects that need data we do not have**: MOC imbalance drift (needs NYSE/Nasdaq imbalance feed published from 15:50; Imperial thesis shows predictability that captures ~30% of the spread for single stocks, not index futures), 0DTE/gamma positioning (needs OI/dealer-gamma; Cboe 2023 found *no* measurable change in last-hour behaviour or in close-to-close vs intraday realised vol from 0DTE), gold London-fix leak (Caminschi-Heaney 2014: GC predictable in the 4 minutes after 10:00 ET fix start, but the fixing moved to an electronic LBMA auction in March 2015 so this is historical).

5. **Gold**: the Copenhagen 2001-2018 5-minute study documents a hat-shaped 24-hour pattern (gold rises ~12.3% annualised 18:00-02:00 ET during Asian hours, falls to ~0.9% by 10:00 ET, -3.7 pp in the 30 min before the 5:30 ET AM fix and -4.2 pp before the 10:00 ET PM fix, then rises to 8.3% by 17:00). Gross Sharpe up to 1.61 (Combo) but after spreads the only profitable sub-sample is 2013-2018 (Combo +7.9%/yr, Long +1.7%/yr), and 2017-2018 were negative. The long leg sits in the 18:00-02:00 ET Globex session (allowed by Lucid's flat-by-4:45pm rule but outside this project's RTH convention and the task's "no overnight" instruction, so flag). The short leg (03:00-10:00 ET, incl. the pre-fix windows) is a daytime trade and is testable on our GC 1-minute data.

6. **Net prop verdict**: nothing in this family is a stand-alone Lucid-passing engine; the calendar edges are too infrequent (8-50 trading days/yr) to produce the 5 x $150 days per cycle, and the time-of-day edges are small per trade (2-3 bp/day on the index for intraday momentum). Their value is as (i) **filters** (skip witching Fridays for mean-reversion, skip 13:55-14:30 on FOMC days, size up on CPI/FOMC-minutes days for momentum, prefer breakout on OPEX), and (ii) **a small, uncorrelated overlay** (pre-FOMC morning long, last-half-hour momentum) on top of an ORB/mean-reversion base. The consistency rule actually favours such many-small-days overlays.

---

## 1. Overnight vs intraday return split (Knuteson; Lou-Polk-Skouras; Quantpedia)

**Evidence.** Knuteson "They Still Haven't Told You" (arXiv 2201.00223, Jan 2022): intraday = open-to-close, overnight = close-to-open; for S&P 500, NASDAQ, TSX 60, CAC 40, DAX, Nikkei 1990-2021 the overnight cumulative return dwarfs the intraday one, which is flat-to-negative (China the exception). Quantpedia ("Are Equity Markets Manipulated?"): all S&P 500 returns 1993-2007 "came at the start of the trading day"; mechanism offered is wider spreads/thinner depth near the open so early aggressive trades move prices more. Applied Economics & Finance 12(3) 2025 (sample 1993-2024 for ETFs): SPY total gain 530.53 pts of which 480.57 (90.6%) overnight; QQQ 92.85%; DIA 71.5%; IWM 211% (intraday negative); GLD only 5.7% overnight (gold's drift is intraday on NY hours, see Section 18). Quantpedia's lunch-effect note adds that the anomaly "is highly sensitive to the start and end of the selected period": nearly gone 2010-2021, strong 2017-2020. Alpha Architect (2020): trading costs wipe out the ETF version (daily round trips). Lou-Polk-Skouras (JFE 2019) "A tug of war" is cross-sectional (overnight momentum persists, intraday reverses) and not index-implementable.

**Implementable rule (standard interpretation).** Long at 15:59 close, exit 09:31 next open. Not allowed for Lucid (overnight). Day-trade corollary: do not run an unconditional long-only intraday hold on ES/NQ; the unconditional open-to-close expectation is ~0 and the 15:30-16:00 unconditional expectation was negative 1993-2013 (-1.11%/yr annualised).

**Prop fit.** Not tradeable (overnight). Use only as a prior: intraday long bias has no structural tailwind; conditional, short-holding rules only. Evidence quality 4 (multiple peer-reviewed/independent, long samples) for the existence of the split; 2 for any claim about 2022-2026 (period-sensitive).

**Data requirements.** Daily open/close only. Note Quantpedia's GDX warning: the reported "open" is the first trade, not the auction; using the 09:31 bar instead of the 09:30 print cut the GDX overnight strategy from 30%/yr to 8.6%/yr. Our 1-minute futures data avoids the auction problem but any backtest must execute at the 09:31 bar, not the 09:30 open.

## 2. Weekday overnight seasonality and day-of-week tilt

**Evidence.** Applied Economics & Finance 2025 (105 assets, 606,989 obs, index ETFs 1993-2024): overnight returns are significantly positive Monday-to-Tuesday and Tuesday-to-Wednesday and negative Friday-to-Monday (p<0.05) for SPY, QQQ, DIA and large caps; crypto ETFs inverted. Their model buys SPY/QQQ/DIA before Monday (and Tuesday) close, sells at next open, skips Wed/Fri. Close-to-close SPY 1993-2026 (TradeQuantix/QuantifiedStrategies): Mon +0.055%, Tue +0.071%, Wed +0.062%, Thu +0.015%, Fri +0.033%; "best day of week ranking shifts around across eras". CXO (VIX calendar effects): VIX rises Monday, falls Tue/Wed; "the S&P 500 Index exhibits no significant day-of-the-week effect". Johnston-Kracaw-McConnell (JFQA 1991) on futures: weekday effects "depend in an important way on the time period studied" and disappeared after 1980/1984 in bond futures. Luxalgo summary: Monday effect "faded or even reversed after it became widely known".

**Implementable rule.** (a) Overnight version: long at Mon 15:59 -> Tue 09:31 and Tue 15:59 -> Wed 09:31; avoid Fri close -> Mon open. Overnight: not allowed. (b) Day-trade tilt: allow long-side signals Tue/Wed, shorts Thu; or just use weekday as a feature. Expected intraday weekday differences are tiny (a few bp) because the effect is overnight.

**Prop fit.** Filter only. Evidence quality 3 for the overnight weekday pattern (large sample, one journal), 1-2 for any intraday-only weekday tilt.

## 3. Turnaround Tuesday (conditional Monday reversal)

**Evidence.** TradeQuantix (SPY 1993-2026): unconditional Tuesday +0.071%/day; Monday-down -> Tuesday positive, Monday-up -> Tuesday negative; **Friday down AND Monday down -> Tuesday +0.33% average**; Friday up and Monday down -> +0.10%; either day up -> -0.03%. Position sizing scales with Monday's drop. Investui/Seasonax: since 1980 Tuesday is the best day (+0.07% avg); dropping Tuesdays reduces S&P cumulative gain from ~2,500% to ~560%; Investui's DAX version buys Monday evening on "technical weakness", sells Wednesday morning, strong since 2008, weak 2007. A 2024 Finance Research Letters paper ("Reversal of Monday returns: it is the afternoon that matters", S1544612324005555) reports that the Monday reversal is concentrated in the afternoon session (paywalled; abstract only).

**Implementable rule (standard).** If Friday close-to-close < 0 and Monday close-to-close < 0 (daily ES settlement or 16:00 bar): long ES/MES at Tue 09:31, exit 15:59, stop = 1x ATR(10d) of daily range or $-limit. Variant: enter Mon 15:00 (afternoon reversal) - but that holds overnight. Expected intraday-only capture is a fraction of the +0.33% because part accrues overnight Mon->Tue (consistent with Section 2).

**Prop fit.** Low frequency (~8-12 qualifying Tuesdays/yr). Fine as an overlay. Evidence quality 2 (practitioner backtests, no peer-reviewed intraday test, era-unstable).

## 4. Turn-of-the-month (TOTM), payday effect, month-end "dash for cash"

**Evidence.** McConnell-Xu / Quantpedia: buy at close of the last trading day (or T-1), sell at close of day +3; 1926-2005: 7.2%/yr, vol 6.9%, Sharpe 1.04, MDD -20.8%; "virtually all of the excess market return is accrued during the four-day TOTM period"; present in 31/35 countries; Carcano-Tornero call it the only persistent calendar effect in S&P 500 *futures*. Counter-evidence: Atlanta Fed WP (fedinprint 13394, S&P 500 futures through 2000): "TOTM effects for S&P 500 futures disappear after 1990", attributed to the shift to indirect (mutual fund) purchases. Quantpedia composite case study 1993-2019 (SPY, buy month-end close -> sell first-day close): 3.01%/yr, MDD 11.97%; payday effect (buy 15th close -> sell next close): 2.08%/yr, MDD 8.62%. CXO: TOTM defined as T-5 close to T+4 close (S&P 1928-2024) - table paywalled. Etula-Rinne-Suominen-Vaittinen "Dash for Cash" (JF 2020) documents weak returns in the days before month-end settlement (roughly T-8 to T-4, around the Treasury/pension cash dates) and strong returns at the turn (T-1..T+3) - could not be fetched here; cited from memory, treat as unverified in this sweep.

**Implementable rule (intraday-only approximation).** Long ES 09:31-15:59 on trading days T-1, T+1, T+2, T+3 of each month (and optionally the 15th/16th); flat otherwise. Expect to capture only the intraday component (a minority).

**Prop fit.** Poor stand-alone (48 days/yr, mostly overnight edge). Use as a long-bias filter for a base strategy. Evidence quality 4 for the close-to-close effect (multiple peer-reviewed), 2 for the intraday-only variant in futures (Atlanta Fed negative).

## 5. Pre-FOMC announcement drift (Lucca-Moench) - intraday version

**Evidence.** NY Fed Staff Report 512 (Lucca & Moench 2013; JF 2015): 131 scheduled meetings Sep 1994-Mar 2011. SPX 2pm (day before) to 2pm (announcement day) excess return **+49 bp** (t>4.5), 98/131 positive, annualised Sharpe 1.14; non-FOMC 2pm-2pm windows <0.5 bp. Close-to-2pm window Sharpe 1.43; close two days prior to 2pm: +54 bp. **Timing: "the SPX rises slightly on the afternoon of the day before the FOMC, and it then drifts sharply higher in the morning of scheduled FOMC announcements"; the excess return between 2 pm and the close on the announcement day "has instead been zero"; next day flat.** Pre-FOMC return is higher when the yield curve slope is low, VIX is high and past pre-FOMC returns were high. 1980-2011: +36 bp; 1960-2011: +16.7 bp. Out-of-sample (r-bloggers, SPY daily, Apr 2011-Jan 2015, 31 meetings): +0.26% vs +0.05% on other days, CI -0.25% to +0.69%, not significant. Applied Economics 57(17) 2025: significant positive drift before FOMC announcements *with press conferences*; the price effect is "short-lived, becoming insignificant shortly after the disclosure"; VIX falls before and after. Quantpedia composite (long SPY on FOMC meeting days close-to-close, 1993-2019): 2.30%/yr, MDD 7.17%. CXO: 24-h pre-announcement +0.49%, FOMC-day close-to-close +0.33%, day after flat. Gao et al.: first-half-hour-to-last-half-hour momentum R2 jumps to 11.0% on FOMC-minutes release days (minutes, not statements).

**Implementable rule.** On scheduled FOMC statement days (8/yr; statement at 14:00 ET since 2013, press conference 14:30): long ES/MES at 09:31 (or 09:35 after the opening auction noise), exit at 13:55 flat. Optional day-before leg 13:00-15:59 (small). Stop: 0.6-0.8% or 1x prior-day ATR; no re-entry after stop. Filter: trade only press-conference meetings (all 8 since 2019). Skip 13:55-14:35 entirely (announcement + press-conference headline risk); post-2pm expectation is zero.

**Prop fit.** Good risk profile (defined window, flat before the event) but only 8 trades/yr, so purely an overlay; average 2pm-2pm move of +49 bp means the intraday morning leg captures perhaps 20-35 bp = $290-500 per ES contract (one $150+ day about half the time). Evidence quality 4 (peer-reviewed, replicated internationally; recent-sample strength lower).

## 6. FOMC-day post-announcement patterns (2:00 pm fade, 2:30 press-conference reversal)

**Evidence.** Lucca-Moench: average return after 14:00 is zero, so any post-announcement rule is a volatility/reversal play, not a drift. Practitioner lore ("fade the first move at 2:00, the real move comes at 2:30/after the presser") appears in CME Excell (page not readable) and countless blogs; no fetched source gives a tested statistic. Applied Economics 2025: FOMC-PC price impact is short-lived -> consistent with reversal of the initial move.

**Implementable rule (most standard interpretation).** On FOMC days, measure the 14:00-14:10 move M (close 14:10 minus close 13:59). If |M| > 0.35% (or > 1.5x the 10-day average 10-min range), enter *against* M at 14:10 with target 50% retrace and stop at 1.25x M beyond the 14:10 extreme; exit by 14:29 (before the presser) or by 15:55. A second variant trades the 14:30-14:45 presser move the same way.

**Prop fit.** High variance, 8 days/yr, risk of a $2,000-drawdown hit on one wrong trade with 4 minis. Only micro size. Evidence quality 1 (anecdote; zero average return post-2pm is the only hard number).

## 7. CPI / NFP release-day patterns (8:30 reaction, first-half-hour carry-over)

**Evidence.** Gao et al. (SPY 1993-2013): on CPI/GDP/MCSI release days the first-half-hour -> last-half-hour R2 roughly doubles (2.6% -> 5.5% for MCSI; similar for CPI, GDP) and timing-strategy gains are ~3x normal days on CPI; FOMC-minutes days 11.0% R2 and 20.04%/yr annualised. Edgeful (YM only, small samples): over 24 months, 71% of red 8:30 reactions led to red closes, 50% of green reactions; over 12 months 80% of green reactions led to *red* closes (n=5) - i.e. noisy, no ES/NQ stats. Bookmap/FundedFast blog guidance: wait 15 minutes, fade retail spike - anecdotal. Shareplanner gap study (5 years, SPY/QQQ): gap-ups >= 1% have average open-to-close drift -0.2% (SPY) / -0.5% (QQQ); gap-downs >= 1% +0.21% (SPY) / +0.1% (QQQ); QQQ 1-1.99% gaps fill same day ~45-47%, 2%+ gaps ~30-33%; Monday gap-ups fade ~60%, mid-week gaps continue more.

**Implementable rules.** (a) *Momentum carry-over on macro days*: on CPI, NFP, GDP, FOMC-minutes days, sign of (10:00 close - prior 16:00 close) -> trade 15:30-15:59 in that direction (Section 8) with 1.5-2x normal size. (b) *Large-gap fade*: if 09:30 open vs prior 16:00 close >= +1% (NQ) or >= +0.7% (ES), short at 09:31, target 50% of gap, stop at 0.5x gap above the open, flat 15:59; mirror for gap-downs with smaller expectation. (c) *8:30 spike fade*: in the 08:30-08:45 window, if the 08:30-08:33 move exceeds 0.4% ES / 0.6% NQ, fade with 50% retrace target, stop beyond the extreme, exit 09:25 - this is pre-RTH and allowed by Lucid (flat rule is only at 16:45) but is high-slippage.

**Prop fit.** (a) is the best-evidenced; (b) is a mean-reversion-family rule with vendor-level evidence; (c) is anecdote. ~12 CPI + 12 NFP + 8 minutes-release days/yr. Evidence quality 3 for (a), 2 for (b), 1 for (c). Data: economic calendar dates needed (BLS archived schedule); no volume needed.

## 8. Market intraday momentum: first half-hour predicts last half-hour (Gao-Han-Li-Zhou)

**Evidence.** SPY 1-min/half-hour data Feb 1993-Dec 2013 (JFE 2018; SSRN 2440866). r1 = return from prior close to 10:00; r12 = 15:00-15:30; r13 = 15:30-16:00. Predictive regression of r13 on r1 significant in- and out-of-sample (OOS R2 1.4% with r1; 0.9% with r12; 2.0% with both). Timing strategy eta(r1): long r13 if r1 > 0 else short: **6.67%/yr, vol 6.19%, Sharpe 1.08, skew +0.90, success 54.37%**; Always-Long-last-half-hour: -1.11%/yr, Sharpe -0.18, success 50.42%; Buy-and-hold 6.04%, Sharpe 0.29. eta(r12): 1.77%/yr, Sharpe 0.29. eta(r1, r12) (trade only when both agree, else flat): 4.39%/yr but **77.05% success rate**. After 3:30 pm bid-ask costs (post-decimalisation 2001-2013): 4.46%/yr (r1), 4.30%/yr (r1+r12); post-2005: 6.52% net vs 7.96% gross. Stronger on high-vol, high-volume, recession and macro-news days (Section 7). Replications: Harbourfront notes the pattern and that a 2021 study found it weakened during the COVID shock; other ETFs and international indices show it; futures-specific tests (Hull repository) could not be read (403). Heston-Korajczyk-Sadka (JF 2010) show same-half-hour return continuation at daily lags up to 40 days in the stock cross-section - the index version is much weaker.

**Implementable rule.** At 15:30: r1 = (close 10:00 bar - prior session 16:00 settle)/prior close. If r1 > 0 go long ES/MES at 15:31, if r1 < 0 go short; exit 15:59 (before the 16:00 cash close; the futures settle at 16:00). Confirmation variant: also require sign(r12 = close 15:30 - close 15:00) to agree, else no trade. Size: fixed contracts; stop 0.35% or none (30-min holding). Skip quad-witching Fridays (Section 10 amplification) or size down.

**Prop fit.** Excellent structurally (always flat by 16:00, one trade/day, defined 29-minute exposure, positive skew) but small per-trade edge: 6.67%/yr on notional = ~2.6 bp/day = ~$75/day/ES contract average, with daily sigma of ~0.39% (~$1,100 per ES). With 2-4 ES the average day is $150-300 but only ~54% of days are positive (77% with the r12 filter but fewer trades). It will not generate 5 x $150 days by itself every cycle; it is a good complement to a morning strategy because it is in the market when the morning strategy is flat. Evidence quality 4 (peer-reviewed, OOS, costs; 2020+ weaker).

## 9. Lunch doldrums / lunch effect (Quantpedia 2024)

**Evidence.** Quantpedia "Lunch Effect in the U.S. Stock Market Indices" (SPY, 6 May 2010-May 2024): typically negative/flat performance before lunch and a positive shift after. Variant 1 (mechanical): short 11:00-12:00, flat->long 12:00-14:00. Long-only 12:00-14:00 leg reported ~5.17%/yr with 8.03% vol (search snippet); the reversed (short then long) version "increases performance, albeit at the expense of return-to-risk". Authors warn the pattern is period-dependent and may vanish with 24/5 trading. No independent replication found; it is an OHLC-based ETF test.

**Implementable rule.** Short ES at 11:00, cover and go long at 12:00, exit 14:00; or long-only 12:00-14:00. Stop 0.4%.

**Prop fit.** Daily, flat by 14:00 - structurally fine, but the edge is ~2 bp/day (5.17%/252) and unverified in futures. Evidence quality 2 (single vendor backtest, no OOS).

## 10. Quad / triple witching day and OPEX week

**Evidence.** Caporale-Plastun (CESifo 9360; DJIA, SPX, Nasdaq daily and weekly, Jan 2000-Sep 2021): the only robust anomaly is **d(0)**, the witching day itself: SPX negative in 57% of cases (7/7 tests positive incl. trading simulation), Nasdaq negative in 67%, DJIA 55%; d(-1), d(+1) and the surrounding weeks are not significant. Seasonax (2006-2021, 59 events): +0.58% average over the 5 trading days before quad witching, 42/59 positive (71%); the witching day itself typically declines. Schaeffer's (Dec 2023): triple-witching weeks average -0.69% SPX vs +0.36% in non-expiration weeks; since 2021 positive <30% of the time, average -0.71%. Stivers-Sun (2013) / Quantpedia: option-expiration *week* (Mon-Thu before the 3rd Friday) is strong for S&P 100 stocks: 1988-2010 9.3%/yr, Sharpe 0.61, MDD -15%; Quantpedia composite SPY version 1993-2019 (buy Friday before 2nd Saturday close, sell Thursday close): 4.93%/yr, MDD 20.4%. SpotGamma: OI collapses on expiration Friday, "sharp moves after 2 PM ET as ITM contracts are exercised"; post-quarterly-OPEX Mondays in bearish regimes have produced some of the largest single-day SPX moves of the decade; gamma of near-the-money strikes 5-10x higher in the final 2-3 days before monthly OPEX.

**Implementable rules.** (a) *Witching-day short*: on the 3rd Friday of Mar/Jun/Sep/Dec, short NQ/MNQ (stronger) or ES at 09:31, exit 15:59, stop 1.0% (NQ) / 0.7% (ES). (b) *Pre-witching long*: long ES 09:31-15:59 on the 5 trading days before quad witching (intraday-only capture is partial). (c) *OPEX-week tilt*: long bias Mon-Thu of monthly expiration week; no new mean-reversion shorts in that week. (d) *Afternoon breakout on expiration Fridays*: after 14:00 ET trade a break of the 13:00-14:00 range in the break direction, exit 15:59.

**Prop fit.** 4 witching days + 12 OPEX Fridays/yr; (a) has the best evidence but is 4 trades/yr; small-sample risk is obvious. Evidence quality 3 for (a) (peer-reviewed 2000-2021 + two independent practitioner counts since 2021), 3 for OPEX-week close-to-close, 1-2 for (d).

## 11. 0DTE / expiration-day amplification vs pinning

**Evidence.** Elms (SSRN 6564078; SPY near-expiry options 2016-2025, 1.6 M contracts, 2,294 days): no evidence of pinning in five tests; high near-expiry ATM open interest -> **~16% wider daily ranges** (p<0.001); interpreted as a regime shift from pinning (documented through 2009) to amplification, driven by retail long gamma leaving dealers short gamma; OI is more informative than IV. Cboe Volatility Insights (2023): 0DTE = ~43-50% of SPX volume in 2023 (61% by May 2025 per Numerix); dealer net gamma is tiny ($170-670 M, 0.04-0.17% of ES liquidity); **no measurable change** in close-to-close vs intraday realised-vol spread (2.7 vol points, equal to the 10-yr average), in 1-minute 2-sigma gap frequency, or in last-hour price action; on 15 Aug 2023 dealers were *long* $2 B gamma at 3 pm. Numerix 2026 white paper: gamma explodes in the last hour but net market impact "thus far" small.

**Implementable rule.** Treat monthly OPEX Fridays, quarterly witching and (weaker) every day's last hour as higher-range regimes: widen stops/targets by ~15% and prefer breakout logic over fades on those days. Without OI data no finer rule is codeable.

**Prop fit.** Filter only. Evidence quality 3 (one peer-reviewed-style study on amplification, one exchange study finding no aggregate effect). Data requirement: options open interest / dealer gamma for anything beyond the calendar flag.

## 12. VIX expiration Wednesday

**Evidence.** CXO (VIX options expiration May 2004-Jul 2015; 130 VIX obs, 77 VXX obs): changes in VIX and VXX are "abnormally negative" on OE-1, the trading day *before* VIX expiration (usually Tuesday): 56/77 VXX close-to-close and 57/77 open-to-close returns negative; but 4 of 77 were +5% or more. On the expiration day itself no clear S&P effect. SpotGamma: VIX settles via a morning SOQ (Wednesday ~9:30 ET) that "can cause intraday dislocations if positioning is extreme". Expiration is the Wednesday 30 days before the next monthly SPX expiration.

**Implementable rule.** Long ES 09:31-15:59 on VIX-expiration-eve (OE-1), on the premise that falling implied vol accompanies rising index; or avoid shorts that day. Direct VIX/VXX trading is not available.

**Prop fit.** 12 days/yr, indirect link (VIX down does not guarantee ES up intraday). Evidence quality 2 (one practitioner study, VIX not ES, sample ends 2015).

## 13. MOC imbalance / closing-auction flows (15:50-16:00)

**Evidence.** NYSE publishes closing imbalances from 15:50 (some sources say 15:45 preliminary) and MOC/LOC orders cannot be cancelled after 15:50; Nasdaq publishes from 15:50/15:55. Imperial College thesis (Morand, S&P 500 and Russell 2000 stocks on NASDAQ/NYSE venues, 10-second data 15:50-16:00): imbalance-based linear models predict forward returns with R2 up to ~0.07 at 2-second horizons, decaying towards zero at longer horizons; "we can earn 30% of the spread"; predictability improves approaching the cutoff; often R2 not significantly different from zero on NYSE/Russell. TradingView/Zeiierman educational piece: buy-heavy imbalances outperform sell-heavy into the bell, "32 bp per trade" momentum claim (equities, unverified) and ~83% of the move reverses within 3-5 days. Luxalgo: drift into the bell "is competed over and can reverse once the imbalance is paired off"; auctions are an equity-exchange feature, not a futures one. Nasdaq 2019 article unreachable (503).

**Implementable rule (approximation only).** Without the feed, the only OHLC proxy is "15:30-15:50 momentum continues to 16:00" - which is essentially Section 8's r12 signal and was weak (Sharpe 0.29). A better proxy: on month-end/quarter-end and index-rebalance days (Russell reconstitution late June, S&P quarterly rebalance on witching Fridays) expect larger 15:50-16:00 moves; widen stops / stay flat.

**Prop fit.** Needs real-time imbalance data (NYSE/Nasdaq feeds) - **flagged**. Evidence quality 2 for index-level tradability.

## 14. Pre-holiday effect

**Evidence.** Classic literature (Ariel 1990; Lakonishok-Smidt 1988) finds the trading day before exchange holidays has 5-10x the average daily return (older US data). CXO's page on it returned 404 in this sweep; Quantpedia carries a "pre-holiday effect" entry (not fetched). Quantpedia's composite seasonal strategy does not include it. No post-2020 statistic was obtainable here; treat the effect as historically well documented, recently unverified, and mostly overnight/close-to-close.

**Implementable rule.** Long ES 09:31-15:59 (or 13:00-15:59 only, since early closes occur before Independence Day, Thanksgiving Friday, Christmas Eve) on the last trading day before NYSE holidays (~9/yr). Flat otherwise.

**Prop fit.** 9 days/yr, filter only; early-close days (13:00 ET) must be handled by the engine. Evidence quality 2 (old peer-reviewed evidence; no recent intraday test found).

## 15. Santa Claus rally and December/January turn

**Evidence.** Stock Trader's Almanac via Wikipedia: last 5 trading days of December + first 2 of January; average +1.3% since 1950, positive 76% of the time. Failures: 2024-25 "reverse Santa rally" (SPX fell every day between Christmas and New Year, a first), also 2015-16 and 1999-2000 historically. Overlaps TOTM (Section 4) and pre-holiday (Section 14).

**Implementable rule.** Long ES/MES intraday 09:31-15:59 on those 7 days (half-days excepted); or simply raise the long-side size of the base strategy in that window. Lucid caveat: late December is thin and holiday-shortened; many prop traders stand down.

**Prop fit.** 7 days/yr; mostly overnight. Evidence quality 3 for close-to-close (long sample, published), 1-2 for intraday-only.

## 16. Month-end / quarter-end rebalancing flows (pension "dash for cash")

**Evidence.** Etula et al. (JF 2020) "Dash for Cash": returns are low in the days before month-end payment dates and high right after, consistent with institutions raising cash (unverified in this sweep: SSRN blocked). CXO VIX calendar study: VIX tends to *rise* more during the TOTM window than typical 8-day windows, "contrary to expectations". Quarter-end pension rebalancing (sell equities after a strong quarter) is widely cited by sell-side desks (e.g., $-billions estimates) but no tested rule was found. SpotGamma: post-quarterly-OPEX Mondays are high-variance.

**Implementable rule (standard interpretation).** (a) Short-bias or no-long days: T-4..T-2 of each month; long-bias T-1..T+3 (Section 4). (b) Quarter-end: if the ES quarter-to-date return through T-5 > +5%, apply short bias 13:00-15:59 on T-3..T-1 of Mar/Jun/Sep/Dec; if < -5%, long bias.

**Prop fit.** Filter only; ~4 days/quarter. Evidence quality 2 (peer-reviewed for the monthly cash cycle in general, no futures intraday test; quarter-end rule is desk lore).

## 17. Keloharju-Linnainmaa-Nyberg return seasonalities (same-calendar-month, same-weekday)

**Evidence.** NBER 20815 / JF 2016: stocks sorted on historical same-calendar-month returns earn 13%/yr (1963-2011); commodities (24 futures, 1970-2011): long-short same-month strategy 0.93%/month (t=1.93) vs -0.22% for other-month (difference 1.15%, t=1.97); country indices 0.48%/month (t=2.20); daily frequency: value-weighted long-short on historical same-weekday returns over 20 years earns 0.11%/day (t=13.3) in stocks, but the authors call the daily strategy infeasible after costs. Kosch-Forsberg (arXiv 2609.12227, 20+ commodity futures incl. gold, rolling 10-yr signals, OOS Jan 2016-Dec 2024 with costs): best long seasonal portfolio cumulative +16.81%, Sharpe 0.19 vs 0.18 for an equal-weight long benchmark; none of 18 paired Sharpe tests rejects; median short-side results negative. Gold-specific month effects (CBS thesis 2001-2018): January has the strongest intraday cumulative pattern (49.6% annualised), winter months (+17.8%) far stronger than summer months (-5.2%) on a close-to-close basis.

**Implementable rule.** Single-instrument version: compute the trailing 10-20-year average return of each calendar month for GC/ES/NQ; allow long-side trades only in months whose historical same-month mean is in the top half (for gold: roughly Jan, Aug-Sep, Nov-Dec; for ES: Nov-Apr), short-side only in the bottom half. Weekday analogue: allow longs on weekdays with positive trailing-5-yr same-weekday mean.

**Prop fit.** Filter only; the cross-sectional edge does not translate to one instrument, and the 2016-2024 OOS commodity test shows no significant gain. Evidence quality 2 for a single-instrument filter (4 for the original cross-sectional finding).

## 18. Gold round-the-clock seasonality ("hat shape") and London fixes

**Evidence.** CBS thesis "Gold Price Dynamics Around the Clock" (GC futures 5-minute, 3 Jan 2001-31 Dec 2018, NY time): average annualised cumulative return rises from 0% at 18:00 to **12.3% by 02:00-02:30** (8.7 pp during Tokyo/Shanghai day sessions), falls through the London OTC/COMEX hours to a **local minimum of 0.9% at 10:00**, then a stretched U-shape rising to **8.3% at 17:00** close-to-close. Two spikes: **-3.7 pp in the 30 min before the 05:30 ET AM fix and -4.2 pp in the 30 min before the 10:00 ET PM fix.** Winter (standard time): peak 21.7% at 02:00-02:30, close-to-close 17.8%; summer (DST): returns drop from 7.4% at 03:00 to -0.2% at 05:30 and close-to-close only 3.1%. Weekday: East (Asian-hours) returns positive and significant every day except Tuesday, Monday largest; West (03:00-17:00) returns negative Mon/Tue/Thu, significantly positive Friday. Sub-periods: East returns >10% almost every year 2001-2010, weaker and less consistent after; AM-fix returns negative in 13/18 years (9 significant). Strategies (gross, 2001-2018 avg/yr): Long 11:00-02:00 (next day) 18.6%, Short 02:00-11:00 10.0%, Combo 28.6% (Sharpe 1.61), Fixing (short 05:05-05:35 and 09:35-10:05) 7.6%; **net of full spreads**: 2001-2006 catastrophic (-48% to -126%/yr), 2007-2012 Long +6.3%, Combo -3.5%, 2013-2018 Long +1.7%, Short +6.2%, Combo +7.9%, Fixing -9.3%; 2017 and 2018 negative for all. Caminschi-Heaney (JFM 2014, GC and GLD): significant volume/volatility spike and **statistically significant return advantage in the 4 minutes after the 10:00 ET PM fix starts**; direction of trades in the fix's opening minutes predicts the fix result >90% in some cases; no effect after publication. LBMA Alchemist (Fertig): large PM-fix moves negative 92% of the time in 2010, >=2/3 in six of 2004-2013; sample ends 2013. Tully-Lucey (COMEX 1982-2002): no robust weekday seasonality in gold futures. The LBMA fix moved to an electronic auction in March 2015 (silver Aug 2014), which plausibly removed the leak. Also GLD: only 5.7% of its 2004-2024 gain came overnight (US close-to-open), i.e. gold's positive drift is during NY hours, the mirror of equities.

**Implementable rules.** (a) *Western-hours short*: short GC/MGC at 03:00 ET (London open), cover 10:00-10:05 ET; stop 0.6%; skip if GC gapped >1% overnight. (b) *Pre-fix fade*: short at 05:00 cover 05:30; short at 09:30 cover 10:00 (30-min windows); stop 0.4%. (c) *Post-PM-fix momentum*: at 10:04 go with the sign of the 10:00-10:04 move, exit 10:30 (Caminschi-Heaney leak, likely dead post-2015). (d) *NY-hours long*: long GC 10:05-16:55 ET (the rising leg of the U) - daytime, Lucid-compatible. (e) *Asian-hours long*: long 18:00-02:00 ET - sits in the evening Globex session; allowed by Lucid (flat only required by 16:45 next day) but violates this project's RTH/no-overnight convention; flag for a decision.

**Prop fit.** (a), (b), (d) are testable on our GC 1-minute data 2010-2026. Expected edge is small (a few bp/day) and spread-sensitive; MGC spreads (~$0.10-0.20) are large relative to it. Evidence quality 3 for the hat shape (single long-sample study, consistent with other academic work on eastern-demand hours), 2 for post-2015 persistence (2017-18 negative), 3 for the pre-2015 fix anomalies (peer-reviewed) but 1 for their continuation.

## 19. First-30-minutes effects (opening gap and opening-range context)

**Evidence.** Shareplanner (5-yr SPY/QQQ, 1%+ gaps on ~15-20% of sessions): SPY gap-up >= 1% -> average open-to-close -0.2% (90% still closed above prior close); SPY gap-down >= 1% -> +0.21%; QQQ gap-up -0.5%, gap-down +0.1%; same-day fill 45-47% for 1-1.99% QQQ gaps, 30-33% for 2%+; Monday gap-ups fade ~60%, Wed/Thu gaps continue more. CXO strong/weak close (S&P 1962-2020): no next-day predictability overall (corr 0.02); post-2000 weak closes (close near the low) show higher next-day returns. Quantpedia GDX note: using the 09:31 bar instead of the 09:30 print matters enormously for anything that enters at the open.

**Implementable rule.** Gap fade (Section 7b) and "weak prior close -> long bias today" (if (C-L)/(H-L) of prior day < 0.2 and range > 1.5%, allow longs only). Both are mean-reversion-family rules with calendar/structural flavour.

**Prop fit.** Vendor-level evidence; daily frequency. Evidence quality 2.

## 20. Last-30-minutes unconditional and "power hour" lore

**Evidence.** Gao et al.: always-long 15:30-16:00 = -1.11%/yr (1993-2013), success 50.4%; Knuteson/A.E.&F. 2025: intraday drift ~0. Luxalgo: power hour is a *volume/volatility* phenomenon, not a return one. 0DTE studies (Section 11): no measurable aggregate change in last-hour price action.

**Implementable rule.** None unconditional. Conditional only (Section 8). Negative result worth recording so the backtest loop does not waste cycles on "buy the last hour".

**Prop fit.** n/a. Evidence quality 4 (negative finding, peer-reviewed).

---

## 21. What the evidence says works in 2022-2026 (and what does not)

**Reasonably supported for the 2022-2026 regime**
- *Witching-day weakness* (SPX 57%, NDX 67% negative 2000-2021; triple-witching weeks -0.71% avg and <30% positive since 2021). Small sample but consistent across three independent counts. Trade: short NQ open-to-close on quad-witching Fridays; at minimum, no longs.
- *Expiration-day range amplification* (2016-2025, +16% range on high-ATM-OI days; no pinning). Trade: breakout logic and wider stops on OPEX/witching; avoid fades after 14:00 those days.
- *Pre-FOMC morning drift for press-conference meetings* (Applied Economics 2025 finds it; Lucca-Moench timing says morning of the day). Trade: long 09:31-13:55 on FOMC days, flat through the announcement.
- *Intraday momentum on macro-news days* (first half-hour sign carries into the last half-hour; effect ~2-4x on CPI/FOMC-minutes days). The base effect weakened around 2020 but no study shows it reversed.
- *Overnight-vs-intraday split* still describes the data (SPY 1993-2024 90.6% overnight) - as a constraint: intraday long-only holds have no tailwind.

**Weak or unverified after 2020**
- Turn-of-the-month, OPEX-week, pre-holiday, Santa rally, weekday tilt: close-to-close effects dominated by the overnight component; TOTM in S&P futures reported dead after 1990 by the Atlanta Fed; Santa failed in 2024-25. Use only as filters.
- Lunch effect: single 2010-2024 ETF backtest, ~2 bp/day, period-sensitive.
- 0DTE "last-hour chaos": Cboe finds no aggregate effect; the measurable effect is range amplification on expiration days, not directional.
- VIX-expiration eve: VXX-based, sample ends 2015, indirect for ES.
- Gold hat-shape / fix anomalies: the pre-fix drops and the post-fix leak are pre-2015 phenomena; Asian-hours drift decayed after 2010 and was negative 2017-18; net-of-spread profitability only in 2013-2018 sub-sample.

**Needs data we lack (flag in the engine)**
- MOC imbalance drift (NYSE/Nasdaq imbalance feed), dealer gamma/0DTE positioning (options OI), VIX-eve mechanics (VIX futures term structure for a proper filter).

**How to use this family inside the Lucid simulator**
1. Calendar flags per session: FOMC (statement/minutes), CPI, NFP, GDP, monthly OPEX, quarterly witching, VIX expiration eve, TOTM window (T-1..T+3), payday (15th/16th), pre-holiday, early-close days, Santa window, month/quarter-end T-3..T-1.
2. Base strategies (ORB / mean reversion / trend families) consume the flags as (a) no-trade or size-down days (FOMC 13:55-14:35, witching for fades, early closes), (b) size-up days (CPI/NFP/minutes for momentum), (c) directional bias (witching short, pre-FOMC long, TOTM long).
3. Overlays that are flat by close and uncorrelated with the morning strategies: pre-FOMC morning long (8/yr), last-half-hour momentum with r1+r12 confirmation (~150-200 trades/yr, 77% success, tiny size), witching-day NQ short (4/yr).
4. Sizing reality: on a $50K Flex with $2,000 EOD-trailing drawdown, a 0.5% adverse ES move is $725/contract; calendar overlays should run 1-2 MES/MNQ-equivalents per $1,000 of drawdown room, and the pre-FOMC/witching trades should be hard-stopped at 0.6-0.8%.

---

## Sources

- Knuteson, "They Still Haven't Told You", arXiv 2201.00223 (ar5iv HTML); Quantpedia "Are Equity Markets Manipulated?" https://quantpedia.com/are-equity-market-manipulated/
- Applied Economics and Finance 12(3) 2025, "Weekly Seasonality in Overnight Effects of the Stock Market" https://redfame.com/journal/index.php/aef/article/download/7705/6965
- Quantpedia, "Lunch Effect in the U.S. Stock Market Indices" https://quantpedia.com/lunch-effect-in-the-u-s-stock-market-indices
- Quantpedia, "Turn of the Month in Equity Indexes" https://quantpedia.com/strategies/turn-of-the-month-in-equity-indexes ; composite seasonal case study https://quantpedia.com/quantpedias-composite-seasonalcalendar-strategy-case-study/ ; option-expiration week https://quantpedia.com/strategies/option-expiration-week-effect ; GDX overnight / open-price warning https://quantpedia.com/dangers-of-relying-on-ohlc-prices-the-case-of-overnight-drift-in-gdx-etf/
- Atlanta Fed WP, "Closing the question on the continuation of turn-of-the-month effects: evidence from the S&P 500 Index futures contract" https://www.fedinprint.org/item/fedawp/13394/original
- CXO Advisory: TOTM persistence https://www.cxoadvisory.com/calendar-effects/turn-of-the-month-effect-persistence/ ; VIX calendar effects https://www.cxoadvisory.com/calendar-effects/vix-calendar-effects/ ; FOMC https://www.cxoadvisory.com/economic-indicators/fomc-drives-global-equity-markets ; strong/weak closes https://www.cxoadvisory.com/technical-trading/are-strong-or-weak-daily-closes-predictive/
- Lucca & Moench, "The Pre-FOMC Announcement Drift", NY Fed Staff Report 512 https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr512.pdf ; NBER conference version https://conference.nber.org/conf_papers/f66717.pdf ; r-bloggers OOS update https://www.r-bloggers.com/2015/03/update-on-the-pre-fomc-announcement-drift/ ; Applied Economics 57(17) 2025 https://ideas.repec.org/a/taf/applec/v57y2025i17p2021-2037.html
- Gao, Han, Li, Zhou, "Market Intraday Momentum" (SSRN 2440866; JFE 2018) https://assets.super.so/e46b77e7-ee08-445e-b43f-4ffd88ae0a0e/files/ee7dac49-530b-4950-b5d0-e0b5eee08f2e.pdf ; Harbourfront note https://harbourfrontquant.substack.com/p/does-intraday-momentum-exist-in-stock
- Heston, Korajczyk, Sadka, "Intraday Patterns in the Cross-section of Stock Returns", JF 2010, arXiv 1005.3535
- Caporale & Plastun, "Witching Days and Abnormal Profits in the US Stock Market", CESifo WP 9360 https://www.ifo.de/DocDL/cesifo1_wp9360.pdf ; Seasonax quad witching https://www.seasonax.com/what-is-happening-with-stocks-on-quadruple-witching-day ; Schaeffer's triple witching weeks https://www.schaeffersresearch.com/content/analysis/2023/12/06/how-to-play-upcoming-triple-witching-expiration-week
- Elms (2026) SSRN 6564078 via Harbourfront "From Pinning to Amplification" https://harbourfrontquant.substack.com/p/from-pinning-to-amplification-evidence ; Cboe "Much Ado About 0DTEs" https://www.cboe.com/insights/posts/volatility-insights-evaluating-the-market-impact-of-spx-0-dte-options ; Numerix 0DTE gamma white paper (2026); SpotGamma OPEX/VIX mechanics https://spotgamma.com/?p=19277
- Morand (Imperial College) "Predicting US stock returns using closing auction imbalance data" https://www.imperial.ac.uk/media/imperial-college/faculty-of-natural-sciences/department-of-mathematics/math-finance/MORAND_CLEA_01805978.pdf ; Luxalgo auction windows https://www.luxalgo.com/library/concept/auction-windows/ ; TradingView/Zeiierman closing auctions
- TradeQuantix Turnaround Tuesday https://www.tradequantixnewsletter.com/p/market-effect-research-turnaround ; Seasonax https://www.seasonax.com/turnaround-tuesday-sp500-seasonal-pattern/ ; Investui https://www.investui.com/en-lu/investing/best-investments-strategies/turnaround-tuesday-effect/buy-dax-index ; Johnston-Kracaw-McConnell JFQA 1991 (financial futures weekday effects)
- Shareplanner gap study https://www.shareplanner.com/blog/strategies-for-trading/fading-the-gap-how-large-overnight-moves-in-spy-and-qqq-play-out-during-the-trading-day.html ; Edgeful CPI guide https://www.edgeful.com/blog/posts/cpi-trading-strategy-guide
- Keloharju, Linnainmaa, Nyberg, "Return Seasonalities", NBER 20815 https://www.nber.org/papers/w20815.pdf ; Kosch & Forsberg, "Seasonal Trading in Commodity Futures", arXiv 2609.12227
- Copenhagen Business School thesis "Gold Price Dynamics Around the Clock" (GC 5-min 2001-2018) https://research-api.cbs.dk/ws/portalfiles/portal/59803241/651553_Thesis_Contract_13383.pdf ; Caminschi & Heaney, "Fixing a Leaky Fixing", JFM 2014 https://api.research-repository.uwa.edu.au/ws/files/4725264/A0205_use_this.pdf ; LBMA Alchemist 73 (Fertig) https://www.lbma.org.uk/alchemist/issue-73/has-there-been-a-decade-of-london-pm-gold-fixing-manipulation ; Tully & Lucey IIIS DP 57 (COMEX gold/silver 1982-2002)
- Santa Claus rally (Stock Trader's Almanac via Wikipedia) https://en.wikipedia.org/wiki/Santa_Claus_rally
