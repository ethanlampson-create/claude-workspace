# Family: Prop-firm evaluation passing and funded-account payout tactics (risk-management layer)

Research sweep date: 2026-10-03. Target: Lucid Trading 50K LucidFlex. All times ET, all dollars are account dollars.

Method note. The session's web-search budget was exhausted before this sweep began, so the sweep was done by direct fetches of canonical pages: Lucid's own help centre (8 LucidFlex / rules articles), Topstep's help centre and 2025 disclosure, Tradeify / MyFundedFutures / Take Profit Trader / Earn2Trade disclosures, the Hall (2026) working paper "Gate Design and Stage-Dependent Incentives in Retail Proprietary-Trading Evaluations" (arXiv 2609.14859, 40 pages read in full, code public), two independent GitHub eval simulators, the FPFX/Finance Magnates dataset, Funded Futures Family and Prop Trading Vibes practitioner pages, the arXiv drawdown-constrained-Kelly literature, and a Reddit archive (most Lucid threads were removed by moderators; only titles survive). Reddit.com, SSRN, Apex, Quantpedia and lucidtrading.com's main site block automated fetches. Where the web is thin, numbers were **computed directly** with a Monte Carlo of the exact Lucid rules (`scratchpad/lucid_mc.py`, 20,000 paths per cell; the full output is reproduced in section 3). Evidence quality is rated 1 (anecdote) to 5 (peer-reviewed + multiple independent OOS tests).

---

## 0. Executive summary

1. **The rules, verified against Lucid's own help centre (support.lucidtrading.com, articles 12945790/95/96/805/808/815, 16226050, 11404728/29/42):** 50K Flex eval target $3,000; Max Loss Limit $2,000 end-of-day trailing; "Initial Trail Balance" $52,100, "Locked MLL Balance" $50,100 (MLL locks at starting balance + $100 once an EOD close exceeds $52,100); consistency = largest single-day profit / account profit <= 50% **with a built-in cushion "so you can pass in two days"**; no scaling plan in eval (full 4 minis / 40 micros); funded starts at 2 minis / 20 micros, +1 tier at $1,000 EOD profit, +2 at $2,000, +3 at $3,000-4,499, max at $4,500 (for 50K the cap is 4 minis, reached at $2,000), scaling updates at session end; payout needs 5 separate days with EOD profit >= $150 **and** positive net profit in the cycle (even $1), min $500, max 50% of profit up to $2,000, 90/10, no fixed window, deducted within minutes, paid within 2 business days, 5 payouts then live; **"Once you request a payout from LucidFlex, your MLL automatically adjusts to the Locked MLL Balance"** ($50,100); optional Daily Loss Limit chosen at checkout (soft breach = locked out until next session; cheaper price; cannot be changed later); flat by 4:45 PM ET, reopen 6:00 PM ET; news trading allowed on Flex; trade copiers and automated systems permitted; DCA/scaling-in allowed; hedging and HFT prohibited; microscalping = > 50% of profit from trades held <= 5 s. These match `research/lucid_rules.md` and `backtest/lucid.py`; the two refinements are the consistency cushion (unquantified, "a percentage of actual profits") and the funded scaling table (already encoded).

2. **Published funnel statistics (firm disclosures, quality 4):** Topstep CY2025: 16.8% of Combines completed (per account), 51.8% of persons funded at least once, 33.3% of funded persons paid, 0.71% called to live. Tradeify Aug 2025-Jul 2026: 17.2% of evals completed, 40.3% of persons funded, 28.5% of funded paid, 3.0% to live, median 3 evals bought per person. MyFundedFutures (Aug 2026 site): 19.97% of eval participants advanced, 39.2% of funded earned >= 1 payout, 4.2% promoted to live. Take Profit Trader CY2025: 36.22% of tests passed (20.37% in Jan-Aug 2023). Earn2Trade 2025: 8.89% pass, 18% of funded accounts had a withdrawal. FPFX (300,000+ accounts, 100,000 traders, 10 mostly FX/CFD firms, 2024): 14% pass, 45% of those paid, 7% of all buyers paid, average $800 of challenge fees over ~3 challenges, average payout 4% of account size. Swiset (10,000 traders): one-phase evals pass 20.3%, two-phase 11.8%. Failure attribution: ~70% of failures are loss-limit breaches (50% max drawdown, 20% daily), not missed targets. **Lucid publishes no funnel statistics.** Person-level joint "ever paid" rates run 7-17% across every dataset.

3. **The one rigorous study of this exact geometry (Hall 2026, arXiv 2609.14859, working paper, code public, quality 3):** with T=$3,000, d=$2,000, EOD trailing, (i) the driftless fixed-barrier pass probability is d/(d+T) = 0.40 and the trailing ratchet costs a further 14-17 percentage points; (ii) a zero-skill participant who optimises size alone passes 36-47% of evals, so pass rate confounds skill and sizing at roughly equal weight (fixed-size zero-skill 0.10 -> q=0.05 edge 0.39; zero-skill sizing-optimised 0.43); (iii) **the eval and the funded stage want opposite cadences**: eval pass rate is flat in trades/day (23.4-25.4% at 40% WR) while days-to-resolve fall from 11.4 to 1.4; funded payout rate at 1/3/5/10/20 trades per day is 34.8/29.9/23.4/11.7/3.9% -> fast-and-lumpy in eval, slow-and-steady funded gives a joint gate 8.8% vs 1.0% (factor nine); (iv) break-even win rate at 1:1.5 net of costs on Lucid Flex is 40.9-41.5% (driftless 40.0%), i.e. the product needs ~1-1.5 points of genuine edge after costs; (v) a 20% consistency cap halves payout probability at lumpy sizing but costs nothing at one steady trade/day (largest day ~18% of profit); (vi) the simulated funded payout rate (34.6-34.8% for EOD trailing + 5 qualifying days, no binding consistency) lands within 1.5 pp of Topstep's published 33.3%; (vii) the symmetric hedged pair across two accounts doubles P(funded) and doubles cost: cost per funded account is unchanged ($267-$465 across sizings), and at the observed $1,000 ceiling the pair nets +$9 per $196; (viii) at the measured strategy drifts nothing clears break-even, and 190 of 576 ORB configurations survived without costs and zero with them.

4. **Monte Carlo on the exact Lucid rules (this report, section 3).** With a Bernoulli strategy (45% win at 1:1.5, +0.125R expectancy, $2 cost/trade) the eval pass rate within 90 days is 77-84% at $100 risk per trade with 5-10 trades/day (median 22-42 days), 64-65% at $200, 44% at $400 (median 6-8 days, 67-80% of passes are delayed by the consistency rule). At zero edge (40% win, slightly negative after costs) the hump peaks at 23% around $150-300 risk; the consistency rule cuts the big-size pass rate from 27% to 16%. A two-day pass (two ~$1,500 days) has ~20% probability even with the edge and costs ~30 pp of pass probability versus patient sizing. Daily loss stops and daily profit caps change the pass rate by < 1 pp under i.i.d. trades (their value is behavioural / autocorrelation, not geometric). In the funded stage the payout-timing policy is the dominant lever: requesting as soon as $1,000 profit is available gives P(first payout within 120 days) 73-92% but 68-86% of those accounts then breach (the "Lucid trap"), while waiting until profit >= $4,000 gives 55-77% with only 7-37% post-payout breach and 1.5-2x the expected dollars paid over 120 days at 5 trades/day; scaling risk down by half after the lock cuts post-payout breach to 2.6%. The $150 qualifying-day threshold imposes a sizing floor: at one trade/day and 1:1.5 the risk must be >= $102 or no day ever qualifies.

5. **What this means for the backtest (actionable):** (a) size the eval so that the *best* single day is <= ~$750 and the median day is $100-250, i.e. $100-150 risk per trade at 5-10 trades/day for a +0.1R strategy, which keeps the consistency rule non-binding and pass probability near its maximum; (b) do not try to pass in two days unless the aim is a lottery ticket (the aggressive config): it costs ~30 pp of pass probability for a saving of ~20 calendar days; (c) in the funded stage trade 1-2 setups/day at $100-150 risk, bank qualifying days (>= $150 EOD) and accumulate to >= $4,000 before the first request (full $2,000 payout, $1,900 of room after the lock), then halve size; (d) the "aggressive" config should request the first payout at the $500 minimum as soon as 5 qualifying days exist if the objective is to *guarantee* one payout, accepting a ~70-85% chance of losing the account afterwards; (e) model resets: expected cost to funded = fee / P(pass); at $146 list ($73 at the usual 50% discount) and P(pass) 0.6-0.8 that is $90-245, so one eval fee buys roughly 0.6-0.8 funded accounts, versus 0.17-0.2 for the published population.

---

## 1. Sources fetched (with what each contributed)

| Source | Type | Contribution |
|---|---|---|
| support.lucidtrading.com articles 12945790 (eval), 12945795 (funded), 12945796 (payouts), 12945805 (consistency), 12945808 (scaling), 12945815 (drawdown), 16226050 (customization/DLL), 11404728 (other activities), 11404729 (trading times), 11404742 (microscalping) | Firm rules | Exact rules in sec. 0.1 |
| topstep.com (footer disclosure CY2025), help.topstep.com 8284208 (consistency), 8284233 (payout policy), 8284197 (Combine parameters), topstep.com/blog/static-vs-trailing-drawdown | Firm rules/stats | Topstep Combine consistency is 55% of target (not 50%); XFA payout = 5 winning days of $150+, max 50% of balance, $2,000 cap at 50K, MLL resets to $0 (locks at start) permanently after first payout; 2025 funnel |
| tradeify.co (performance disclosure), myfundedfutures.com, takeprofittrader.com, earn2trade.com | Firm stats | Funnels in sec. 0.2 |
| Hall, N. (2026) arXiv 2609.14859 v23, github.com/nicholasbhall/gate-design-prop-evals (breakeven.py read) | Working paper + code | Secs 0.3, 2, 4 |
| github.com/shurugiken/prop-firm-eval-simulator (README + eval_sim.py) | Independent MC | Hump result; Apex/Topstep/Lucid rule table (its Lucid row describes LucidPro-style 5-day/DLL rules, not Flex) |
| github.com/oriolakolawole/Monte-Carlo-Pricing-Framework-for-Prop-Firm | Independent MC | Eval as down-and-out cash-or-nothing call; zero-edge FX challenge 36% pass, +EV at $95 fee because of 105x leverage on fee |
| github.com/MCOSK/End-to-End-Propfirm-Pricing-Engine | Code | Frames EOD-trailing eval as lookback/trailing barrier option, HJB "asymmetric risk scaling"; no numbers |
| financemagnates.com "only 7% of 300,000 prop trading accounts achieved payouts" (FPFX, Sept 2024) | Industry data | Sec. 0.2 |
| fundedfuturesfamily.com (Lucid consistency rule; FFF Premier+ vs Lucid Flex; Apex consistency rule; Apex hidden rules; Lucid payouts analysis) | Practitioner | Lucid worked example ($750/$3,000 = 25%); Apex 50% rule from 1 Mar 2026 (30% legacy), losing days count, "largest day / 0.5 = profit needed"; Apex funded swaps to EOD trailing, $2,000 early cap, 5 days between requests |
| proptradingvibes.com/prop-firms/lucid-trading (author with 30+ Lucid payout cycles) | Practitioner | Personal risk rules: max $400 per trade, stop the session at -$600, 1 NQ or MNQ; request payout as soon as eligible to cut firm risk; breached an account during FOMC despite EOD trailing; "build several profitable days rather than one large session"; payout approvals ~15 min |
| proptradingvibes.com/blog/maven-trading-consistency-rule | Practitioner | Daily cap = target / N days rule; losses worsen the ratio |
| arXiv 1603.06183 (Busseti, Ryu, Boyd), 1710.01503 (drawdown-modulated control), export.arxiv.org listing | Academic | Risk-constrained Kelly; drawdown-modulation lemma |
| Wikipedia gambler's ruin / risk of ruin | Reference | Closed forms in sec. 4 |
| arctic-shift Reddit archive (r/FuturesTrading) | Community | Consistency-rule war stories (40% rule turning a $2,500 target into $12,000); "fail evals to pass eval" one-day pass with 7 trades; most Lucid threads removed, titles only ($10K payout dispute, IP-match ban, Tradovate glitch) |

---

## 2. Strategy / tactic catalogue

Each entry: objective rule(s) as they should be coded, parameters, evidence, prop-fit for Lucid 50K Flex, data requirements, sources. "Standard interpretation" flags where the source is vague.

### 2.1 Fixed-fraction-of-drawdown risk per trade

- **Rule.** risk_per_trade = k x MLL_distance with k in [0.05, 0.10] ($100-200 on a $2,000 MLL); daily_loss_stop = 0.20-0.30 x MLL_distance ($400-600); never let (balance + open P&L) within 0.25 x MLL_distance of the MLL (i.e. stop opening trades once room < $500). Contracts = floor(risk_per_trade / (stop_points x point_value)).
- **Parameters.** k = 0.05-0.075 for the eval grind, 0.10 only for the aggressive config. PTV practitioner (30+ Lucid cycles): $400 max per trade (0.20 x MLL), session stop at -$600 (0.30 x MLL), 1 NQ.
- **Evidence.** MC (sec. 3): with +0.125R edge, $100/trade at 5-10 trades/day gives 77-84% pass vs 44% at $400; shurugiken's hump peaks at 6-8 micros on a $25k-type account; Hall Table 7: fixed moderate size + edge is the only regime where pass rate carries skill information. Quality 3 (independent simulations agree; no live cohort data by sizing).
- **Prop fit.** Core rule for both configs. The daily stop barely changes P(pass) under i.i.d. trades (sec. 3C) but it bounds the worst case against the *intraday* breach check and against autocorrelated losing streaks (Hall's regime-switching robustness: clustered vol hurts at high size).
- **Data.** OHLC only.

### 2.2 Sizing-hump search (choose contracts to maximise P(pass) under the consistency rule)

- **Rule.** For the candidate strategy's daily P&L distribution (from the backtest), run the Lucid eval simulator over contract counts m = 1..40 micros and pick argmax P(pass within H days), subject to P(largest_day > 0.5 x 3,000) small. Expect a hump: rising with m while the target becomes reachable, falling when a single stop or losing day can reach the $2,000 floor or when the best day exceeds $1,500.
- **Parameters.** H = 60-90 trading days (Flex has no time limit; H is a planning horizon). Report pass rate, fail rate, median days, consistency-blocked share.
- **Evidence.** shurugiken self-tests: 53% win/+1.3R, Apex 50K peak at 8-16 micros (45-55%), < 15% at 60 micros; "75-96% headline pass rates are an oversizing + idealised DLL artefact" collapsing toward ~50% with realistic stop fills. Hall sec. 5.3: zero-skill optimum 0.36-0.47. This report sec. 3A/3B. Quality 3.
- **Prop fit.** This is exactly `monte_carlo_fast` in `backtest/lucid.py`; the catalogue entry is the reminder to search m rather than fix it, and to include the consistency rule in the objective (it moves the optimum from ~$800 risk to ~$150-300 at zero edge).
- **Data.** Backtest daily P&L and intraday minimum equity per contract.

### 2.3 Fast-eval / slow-funded cadence split (Hall's frequency asymmetry)

- **Rule.** Eval: allow the full set of setups (5-20 trades/day) at the hump size. Funded: restrict to the 1-2 highest-expectancy setups per day, stop after the first winner that makes the day >= $150, keep the day's loss <= $300.
- **Evidence.** Hall Tables 10-11: eval pass rate 23.4/24.9/25.4/25.0% at 1/5/20/30 trades per day (days 11.4/3.6/1.6/1.4); funded payout rate 34.8/29.9/23.4/11.7/3.9% at 1/3/5/10/20 trades per day; joint gate 8.8% (split) vs 1.0% (20/day both stages). Mechanism: under EOD trailing the floor is static within a session so extra intraday trades don't compound drawdown in the eval, whereas the funded 5-day minimum multiplies floor-touch opportunities. Quality 3 (single working paper, but mechanism is transparent and reproduced in this report's MC: at p=0.45 funded breach rate rises from 14% at 2 trades/day/$100 to 23% at 5/day).
- **Prop fit.** Directly usable: the backtest should expose a "trade budget per day" parameter and set it separately for eval and funded simulations. Caveat: our MC shows that with a *positive* edge more funded trades/day raise P(first payout) within 120 days (sec. 3D), because reaching $4,000 faster matters; the asymmetry is strongest near zero edge.
- **Data.** OHLC.

### 2.4 Two-day pass (consistency-cushion exploit)

- **Rule.** Lucid's own eval page: "50% consistency with built-in cushion, so you can pass in two days." Two days of >= $1,500 each (day1/day2 both <= 50% of total) pass; the cushion lets one be slightly larger. Required daily P&L scale: daily sd ~ $1,000-1,200, i.e. ~$400 risk/trade at 5 trades/day or 4 minis with 20-25 pt NQ stops.
- **Evidence.** MC sec. 3B: at p=0.45, $400/trade, 5/day: P(pass) 44%, P(pass within 5 days) 22%, 67% of passes are held up by the consistency rule, median largest day $1,990 (so most "two-day" attempts must grind extra days anyway). Reddit "fail evals to pass eval" (Oct 2023, 33 upvotes): passed a 50K in one day with 7 trades after blowing several accounts. Quality 2.
- **Prop fit.** Only for the aggressive configuration, and only if the user accepts cost-to-funded roughly 1.7x higher ($146/0.44 = $332 vs $146/0.77 = $190). Note the eval has no time limit, so speed buys nothing except the trader's time.
- **Data.** OHLC.

### 2.5 Consistency-managed grind (daily profit cap = target / N)

- **Rule.** Choose N >= 4 planned winning days; cap_day = 3,000 / N (N=4: $750, N=5: $600). Once realised day P&L >= cap_day, close and stop for the day. Keep trading until profit >= 3,000 and largest_day <= 0.5 x profit. Equivalent "repair" rule when a big day happens: additional profit needed = 2 x largest_day - current_profit (e.g. a $1,800 day on $3,000 total needs $600 more; Apex's "largest day / 0.5" shortcut).
- **Evidence.** Lucid worked example ($750 largest on $3,000 = 25%); Maven/PTV "cap = target / 5"; Apex rule notes that losing days reduce total profit and worsen the ratio; Reddit cases where a 40% rule turned a $2,500 target into $12,000 after a $4,700 day. MC sec. 3C: a $750 cap at $200 risk changes P(pass) by +0.3 pp and leaves zero consistency blocks (the cap costs nothing when sizing is already moderate). Quality 3.
- **Prop fit.** Mandatory in eval; irrelevant funded (no consistency on Flex). Implement as a hard daily profit stop in the simulator's eval mode.
- **Data.** None beyond P&L.

### 2.6 Room-aware dynamic sizing (fraction of remaining drawdown room)

- **Rule.** room = balance - MLL - buffer (buffer $300-500). micros_today = clamp(floor(room x g / risk_per_micro), 0, cap) with g = 0.10-0.25; when room < buffer, do not trade (wait: nothing recovers room on Flex except profit, so a day off costs nothing). After an EOD peak, room resets to $2,000 (pre-lock) or balance - 50,100 (post-lock).
- **Evidence.** Continuous-time analogue: drawdown-modulated feedback control (arXiv 1710.01503) guarantees drawdown <= d_max w.p.1 by scaling exposure with distance to the floor; Busseti-Ryu-Boyd risk-constrained Kelly bounds P(drawdown) with a single risk-aversion parameter and beats fractional Kelly at equal drawdown risk. Hall: ratchet penalty 14-17 pp, i.e. the trailing floor is the parameter to respect. Quality 3 for the mathematics (peer-reviewed in the control/Kelly literature), 2 for prop-specific calibration.
- **Prop fit.** Encode as `funded_min_room` / `funded_reduced` (already in `monte_carlo_fast`) and as an eval schedule. Because the breach check is intraday including open P&L, the buffer must exceed the worst intraday adverse excursion of one day's planned trades.
- **Data.** Backtest MAE per trade.

### 2.7 Lock-the-MLL-early (push an EOD close above $52,100)

- **Rule.** The MLL stops trailing once an EOD balance exceeds $52,100 and is fixed at $50,100. In the eval this happens at pass (target $53,000 > $52,100), so the first funded sessions start with a fresh $48,000 floor; in the funded account, treat "EOD balance > $52,100" as a milestone: until then room is capped at $2,000 below the running EOD peak; after it, every dollar above $50,100 is permanent room. Tactic: do not take payouts before this milestone (see 2.9), and size up only after it.
- **Evidence.** Lucid drawdown article (table of Initial Trail Balance / Locked MLL Balance); Topstep XFA equivalent ("MLL resets to $0 permanently" after first payout). Hall sec. 9.1 models exactly this geometry. Quality 4 for the rule, 2 for the tactic.
- **Prop fit.** Already encoded (`lock_trigger`, `lock_level`).

### 2.8 Daily loss stop and intraday breach buffer

- **Rule.** Stop trading for the day when realised + open day P&L <= -L, L = $400-600 in eval ($300-400 funded), and never hold a position whose stop would bring balance + open P&L within $100 of the MLL. Optional: buy the DLL version of Flex (cheaper; soft breach = lockout to next session) if the bot cannot be trusted to self-enforce.
- **Evidence.** PTV practitioner: -$600 session stop; Topstep's 50K Daily Loss Limit is $1,000 (50% of the $2,000 MLL) and Tradeify's is $600 (30%); Hall: adding a $1,000 EOD-checked DLL lowers the zero-skill optimum from 0.36-0.47 to 0.25-0.46 (it only hurts the variance-farmer). MC sec. 3C: $400/$600 stops change P(pass) by < 1 pp under i.i.d. P&L and lengthen median days by 1-3. Quality 3.
- **Prop fit.** Keep L small enough that 3-4 consecutive max-loss days cannot reach the floor from a fresh peak (3 x $600 = $1,800 < $2,000). The intraday breach rule makes "distance of the stop to the floor" the binding quantity, not the EOD number.

### 2.9 Payout-timing policy and the "Lucid trap"

- **Rule.** Request only when (a) >= 5 qualifying days (EOD >= $150) in the cycle, (b) cycle net positive, (c) profit P >= P_min. On request the MLL jumps to $50,100 and the balance drops by the payout, so room after = P - payout - 100:

| Profit at request P | Payout (50%, cap $2,000) | Balance after | Room after (MLL $50,100) | Room before request |
|---|---|---|---|---|
| $1,000 | $500 | $50,500 | $400 | ~$2,000 |
| $1,500 | $750 | $50,750 | $650 | ~$2,000 |
| $2,000 | $1,000 | $51,000 | $900 | ~$2,000 |
| $3,000 | $1,500 | $51,500 | $1,400 | $2,900 |
| $4,000 | $2,000 | $52,000 | $1,900 | $3,900 |
| $5,000 | $2,000 | $53,000 | $2,900 | $4,900 |

  Below $2,100 of profit the request costs (2,100 - P) of room *in addition to* the payout, because the floor jumps from (peak - 2,000) to 50,100. Standard objective policy: P_min = $4,000 (first payout is the full $2,000 and leaves $1,900 of room, almost a fresh account) for the safe config; P_min = $1,000 (first payout $500 at the minimum) for the "guarantee a first payout" config.
- **Evidence.** Rule text: Lucid drawdown article; PTV practitioner prefers "a comfortable withdrawal over the theoretical maximum" and requests as soon as eligible. MC sec. 3D (p=0.45, 120-day horizon): at 2 trades/day, $150 risk: P_min $1,000 -> P(first payout) 84%, post-payout breach 74%, mean paid $1,827; P_min $4,000 -> 56%, post-payout breach 9%, mean paid $1,753; at 5 trades/day, $150: 83%/71%/$2,383 vs 70%/27%/$4,649. Quality 3 (rule is certain; policy numbers are this report's simulation).
- **Prop fit.** The single most important funded-stage parameter. `min_profit_to_request` already exists in `backtest/lucid.py`; the two final configs should differ here.

### 2.10 Scale-down after the lock / after payout

- **Rule.** After any payout request set risk_per_trade to the lesser of its previous value and room_after x g (g = 0.10-0.15), e.g. $1,900 x 0.1 = $190 -> keep $150; $400 x 0.1 = $40 -> trade 1-2 micros or stop until a new peak. Resume full size when room >= $1,500.
- **Evidence.** MC sec. 3D2 (p=0.45, 2 trades/day, $200 -> $100 after the first payout): post-payout breach 2.6% (vs 23% without scale-down) at P_min $4,000; at P_min $1,000 it only improves 73% -> 65% because $400 of room cannot be made safe at any tradable size. Quality 2-3.
- **Prop fit.** Encode as `funded_reduced` triggered by payouts, not only by room.

### 2.11 Qualifying-day engineering ($150 EOD days)

- **Rule.** A day counts only if EOD P&L >= $150, so (a) per-trade win must be able to exceed $150 + costs at 1 trade/day (at 1:1.5 that means risk >= $102; at 1:1 risk >= $152), (b) once the day is >= $150 + buffer ($50-100), do not let it fall below $150: either stop for the day ("bank the day") or trade on with a hard stop at +$150 realised. Need 5 such days per cycle; losing days do not reset the count but the cycle must be net positive.
- **Evidence.** Lucid payouts article (per-size thresholds $100/$150/$200/$250); Topstep XFA identical "5 winning days of $150+"; Hall: minimum-days gate accounts for roughly half of the joint-gate compression. MC sec. 3D: 1 trade/day at $100 risk never pays out (0%) because no day qualifies, 1 trade/day at $150 risk pays out 83% (ASAP policy). Quality 4 for the rule, 3 for the sizing implication.
- **Prop fit.** Add a "bank-the-day" exit mode to the funded simulation and a check that the strategy's typical winning day clears $150 at the chosen size.

### 2.12 Eval-fee expected value, resets and cost-to-funded

- **Rule.** cost_to_funded = fee / P(pass) (+ reset fee x expected resets if resets are used instead of new evals; Lucid reset $90 vs list $146, ~$73 at the usual 50% promotions). EV per eval = P(pass) x P(payout | funded) x E[paid] - cost_to_funded. Use the simulator's P(pass) for the actual strategy, never the population figure.
- **Evidence.** Hall sec. 3.5-3.7 and Table 12: at 1:1.5, 40/42/44/46/48% win rates give Lucid Flex EV -$10/+$42/+$106/+$181/+$265 per $98 eval; break-even 40.9-41.5%; the fee is "close to irrelevant to the sign" because the joint gate is 1-3% at measured drifts; at published pass rates (10-20%) cost-to-funded is $490-980 vs a $1,000 modelled first payout. oriolakolawole: even a zero-edge FX challenge is +EV at $95 because of ~105x leverage on the fee (36% pass, $618 expected 12-month withdrawal, break-even fee $222). FPFX: $800 average fees over 3 challenges per trader. Quality 3.
- **Prop fit.** Report both cost-to-funded and EV per eval for each final config; monthly-pass-rate validity should be judged with the 2.5-97.5% bootstrap band (already in `bootstrap_summary`).

### 2.13 Multi-account replication and copy trading

- **Rule.** Lucid allows trade copiers and automated systems (article 11404728) and up to 10 accounts; it prohibits hedging (opposite positions across accounts) and HFT. Replicating the *same* strategy on N accounts scales EV linearly and reduces nothing but idiosyncratic execution noise (outcomes are near-perfectly correlated); it does not raise P(pass) per account. The opposite-side "hedged pair" is prohibited and, per simulation, is EV-neutral anyway.
- **Evidence.** Hall sec. 12: symmetric pair P(>= 1 passes) = 2 x single, P(both) = 0, cost per funded unchanged ($267-$465); 4:1 asymmetric pair cuts cost per funded 17%; baskets of 3+ are worse; at a $1,000 payout ceiling the pair nets +$9 per $196 (+$215 at a $2,000 ceiling) and -$93 under a 20% consistency cap; 55% of funded participants in FPFX data never received a payout. Hall also notes retry correlation: same strategy, same regime -> correlated outcomes across accounts, wider dispersion than independent draws. Quality 3.
- **Prop fit.** Model N copies as the same path (not independent draws). The practical use is to run the safe config on 2-3 accounts and the aggressive config on 1, not to "diversify" a single strategy.
- **Data.** None.

### 2.14 Time-to-pass and risk-of-ruin arithmetic

- **Rules (closed forms for planning; the simulator is the real answer).**
  - Driftless fixed barriers: P(hit +T before -d) = d/(d+T) = 0.40 for T=3,000, d=2,000.
  - With drift: P = (e^{θd} - 1)/(e^{θd} - e^{-θT}), θ = 2μ_d/σ_d² with daily mean μ_d and daily sd σ_d (Hall Prop. 3 / gambler's ruin). Trailing ratchet subtracts 14-17 pp (Hall Table 5).
  - Expected days to target ignoring ruin ~ T / μ_d; with μ_d = $75 (e.g. 5 trades x (0.125 x $150 - $2)) ~ 40 days; MC median 23 days at $150 because passes are selected from the faster paths.
  - Required net edge per trade for P(pass) ~ 0.5 at moderate σ: $31-34 at 1 trade/day, $5.4-5.8 at 5/day, $2.0-3.4 at 20/day (Hall Table 6).
  - Daily sd for a Bernoulli strategy: σ_d ~ sqrt(f) x risk x sqrt(p(1-p)) x (RR+1) (= 1.24 x risk x sqrt(f) at p=0.45, RR=1.5).
- **Evidence.** Standard probability (quality 5 for the formulas); Hall for the ratchet penalty (3).
- **Prop fit.** Use to sanity-check simulator output and to size the two-day config.

### 2.15 Event and time-of-day gates (flat-by, FOMC, data releases)

- **Rule.** No new positions after 15:45 ET; all flat by 15:55 ET (Lucid auto-flattens at 16:45 ET; holidays close earlier). Standard objective interpretation of "avoid news": no open position from 5 minutes before to 5 minutes after 08:30, 10:00 and 14:00 ET scheduled releases, and no trades 13:55-14:45 ET on FOMC decision days (8 per year, calendar known in advance).
- **Evidence.** Lucid allowed-trading-times article; PTV practitioner breached an account on an FOMC spike despite EOD trailing ("EOD trailing does not protect you intraday"). Quality 2 (anecdote + rule text); the ES/NQ realised-vol spikes at those times are documented in `evidence_and_failures.md`.
- **Prop fit.** Cheap insurance against the intraday breach; costs little expectancy for a system that holds 60-120 minutes.
- **Data.** Economic calendar (dates/times only).

### 2.16 Volatility-scaled contract sizing

- **Rule.** micros = floor(risk_per_trade / (stop_distance_points x $ per point per micro)), with stop_distance = k x ATR(14, 5-min) or the strategy's structural stop; cap at the Lucid contract limit (40 micros eval; 20/30/40 funded by profit tier). Re-evaluate daily so the dollar risk, not the contract count, is constant across the 2025 vol regimes (ES realised vol 8.9-30%).
- **Evidence.** Standard practice; Hall's regime-switching check shows clustered vol hurts at high size and helps at low size, which constant-dollar sizing neutralises. Quality 2 (no prop-specific test found).
- **Prop fit.** Needed because the 2025-Q2 tariff spike roughly tripled NQ daily ranges vs 2025-Q3.

### 2.17 "Bank and stop" daily profit stop in the funded stage

- **Rule.** Stop trading for the day when realised day P&L >= G (G = $300-500, roughly 2-3 qualifying days' worth), or after the first winner if it already clears $150.
- **Evidence.** PTV: "build several profitable days rather than rely on one large session"; Hall's funded-stage cadence result; MC sec. 3C shows profit caps are geometrically neutral under i.i.d. P&L (the benefit is lower day-level variance -> more days >= $150 for the same mean). Quality 2.
- **Prop fit.** Secondary to 2.9/2.11; test in the funded simulator as a daily cap.

### 2.18 Eval-with-DLL vs no-DLL purchase choice

- **Rule.** Flex can be bought with a Daily Loss Limit (cheaper) or without. The DLL is a soft breach (lockout until next session) and applies in eval and funded. A self-enforcing bot gets the same protection for free, so buy the no-DLL version only if the bot's own daily stop might legitimately need to be exceeded (it should not); otherwise take the discount.
- **Evidence.** Lucid customization article; shurugiken's finding that an idealised DLL inflates simulated pass rates (so do not model the DLL as a perfect flatten at exactly -L: model the last trade's full loss). Quality 3 for the rule.
- **Prop fit.** Simulator should apply the day stop *after* the losing trade completes (no magic flatten).

### 2.19 Instant-funded (LucidDirect) vs evaluation route

- **Rule.** Compare cost per funded account: eval = fee / P(pass) vs instant = ~$364 (Hall's July 2026 retrieval) with a 20% consistency cap and $1,200 DLL on Direct. For a strategy with P(pass) >= 0.4 the eval route is cheaper and lands on the more permissive Flex funded rules.
- **Evidence.** Hall Table 4 and sec. 3.1; Lucid product pages. Quality 3.
- **Prop fit.** Decision only; no simulation needed beyond P(pass).

### 2.20 Prohibited-behaviour guards (what gets a payout denied)

- **Rule.** Enforce in the bot: average hold > 5 s and < 50% of profit from trades <= 5 s; no opposing positions across the user's accounts; no order spam (HFT); no martingale beyond the strategy's defined scale-in; keep 1 trade per 30 days (inactivity). Keep logs: Lucid adjudicates its own payouts (δ in Hall's model), and documented sector cases include a two-day screen-recording demand (Apex, 2024) and removed Reddit threads titled "Lucid $10K payout dispute" and "false-positive IP match ban".
- **Evidence.** Lucid rules articles; Hall sec. 13.5; Reddit titles. Quality 3 for rules, 1-2 for enforcement frequency.
- **Prop fit.** Bar-based systems with 60-120 minute holds are far from every threshold; the guard is a compliance check, not a strategy change.

---

## 3. Monte Carlo on the exact Lucid 50K Flex rules (this report)

Model: f trades/day, win prob p, win = +1.5 x risk, loss = -risk, $2 cost per trade; intraday breach checked on the running intraday path; EOD trailing MLL with the $52,100 / $50,100 lock; 50% consistency with no cushion; min 2 days; 90-day eval horizon (Flex has no limit; "incomplete" = not resolved in 90 days); funded 120-day horizon, 5 x $150 qualifying days, 50% / $2,000 cap, lock on request, up to 5 payouts; 20,000 paths. Script: `scratchpad/lucid_mc.py` (session scratchpad).

**A. Zero edge (p = 0.40, i.e. -$2/trade after cost), 5 trades/day, with the 50% consistency rule**

| risk/trade | P(pass 90d) | P(fail) | median days | P(pass <= 5 d) | passes delayed by consistency |
|---|---|---|---|---|---|
| $50 | 0.3% | 43% | 71 | 0 | 0 |
| $100 | 12.9% | 77% | 48 | 0 | 0 |
| $150 | 21.1% | 79% | 27 | 0 | 0 |
| $200 | 22.7% | 77% | 17 | 2% | 0 |
| $300 | 22.6% | 77% | 10 | 13% | 17% |
| $400 | 18.8% | 81% | 9 | 20% | 65% |
| $600 | 17.0% | 83% | 7 | 36% | 64% |
| $800 | 16.0% | 84% | 5 | 57% | 63% |

Without the consistency rule the $400 / $800 rows become 23.8% / 26.6% (median 6 / 2 days): the rule is what removes the variance-farmer's advantage on Flex, exactly as Hall's Table 16 note ("payout eligibility collapses ... under a 50% consistency rule") suggests. The zero-edge ceiling of ~23% is below Hall's 36-47% because this model carries -$2/trade of cost and a 90-day cutoff.

**B. Modest edge (p = 0.45 at 1:1.5, +0.125R, +$16.75 per trade at $150 risk)**

| trades/day | risk | P(pass) | P(fail) | incomplete @90d | median days | P(pass <= 5 d) | delayed by consistency |
|---|---|---|---|---|---|---|---|
| 2 | $100 | 32.8% | 10.5% | 56.7% | 66 | 0 | 0 |
| 2 | $150 | 59.2% | 26.4% | 14.4% | 48 | 0 | 0 |
| 2 | $200 | 60.4% | 37.7% | 2.0% | 32 | 0 | 0 |
| 2 | $300 | 53.4% | 46.6% | 0 | 17 | 1% | 0 |
| 5 | $100 | 77.0% | 16.4% | 6.6% | 42 | 0 | 0 |
| 5 | $150 | 71.6% | 28.2% | 0.2% | 23 | 0.2% | 0 |
| 5 | $200 | 63.7% | 36.3% | 0 | 16 | 3% | 0 |
| 5 | $300 | 53.4% | 46.6% | 0 | 10 | 15% | 21% |
| 5 | $400 | 43.7% | 56.3% | 0 | 8 | 22% | 67% |
| 10 | $100 | 83.6% | 16.3% | 0.1% | 22 | 0.3% | 0 |
| 10 | $150 | 73.0% | 27.0% | 0 | 12 | 6% | 5% |
| 10 | $200 | 65.2% | 34.8% | 0 | 9 | 16% | 24% |
| 10 | $400 | 44.1% | 55.9% | 0 | 6 | 40% | 80% |

Stronger edge (p = 0.50, +0.25R): 5/day at $100 -> 98.9% pass, median 24 days; at $200 -> 89.8%, 12 days; at $400 -> 68.9%, 7 days.

**C. Daily loss stop / daily profit cap (p = 0.45, 5/day, $200 risk):** none 63.9%; stop -$400 64.0%; stop -$600 63.4%; cap +$750 64.2%; stop -$400 & cap +$750 63.8%; stop -$600 & cap +$1,000 64.8%. Under i.i.d. trades these rules are geometrically neutral (+/- 1 pp); median days lengthen by 1-3.

**D. Funded stage (p = 0.45, 120-day horizon), payout policy P_min = request as soon as profit >= $1,000 ("ASAP") vs >= $4,000 ("wait")**

| trades/day | risk | policy | P(first payout) | breach after 1st payout | median day of 1st payout | mean $ paid (x0.9 split) | P(>= 2 payouts) |
|---|---|---|---|---|---|---|---|
| 1 | $100 | either | 0% | - | - | $0 | 0 (no day reaches $150) |
| 1 | $150 | ASAP | 82.7% | 82.9% | 27 | $977 | 48% |
| 1 | $150 | wait | 22.8% | 1.7% | 89 | $481 | 4% |
| 2 | $100 | ASAP | 87.9% | 69.2% | 30 | $1,320 | 51% |
| 2 | $100 | wait | 28.9% | 0.8% | 93 | $613 | 5% |
| 2 | $150 | ASAP | 83.6% | 73.8% | 24 | $1,827 | 47% |
| 2 | $150 | wait | 55.5% | 9.1% | 68 | $1,753 | 29% |
| 2 | $200 | ASAP | 73.7% | 73.4% | 21 | $2,129 | 41% |
| 2 | $200 | wait | 57.1% | 23.3% | 47 | $2,524 | 42% |
| 5 | $100 | ASAP | 91.7% | 72.8% | 14 | $1,821 | 57% |
| 5 | $100 | wait | 76.8% | 6.8% | 58 | $3,340 | 58% |
| 5 | $150 | ASAP | 83.0% | 71.1% | 11 | $2,383 | 51% |
| 5 | $150 | wait | 70.0% | 27.0% | 33 | $4,649 | 62% |
| 5 | $200 | ASAP | 72.8% | 68.0% | 11 | $2,729 | 44% |
| 5 | $200 | wait | 61.4% | 37.2% | 21 | $4,306 | 53% |

Scale-down after the first payout (2/day, $200 -> $100): ASAP 73.4% first payout, 64.5% post-payout breach, $1,793 paid; wait 57.3%, **2.6%** post-payout breach, $1,662 paid (120-day horizon truncates the slower policy). Zero edge (p = 0.40, 2/day, wait policy): P(first payout) 1.8% / 15.9% / 19.7% at $100 / $200 / $300 risk, overall breach 59-96%.

Reading: "ASAP" maximises the chance of *a* payout and destroys the account; "wait for $4,000" keeps the account and, with 5 trades/day, roughly doubles the money over 120 days. Both final configurations are therefore legitimate and should be reported side by side.

---

## 4. Published statistics, consolidated

| Firm / dataset | Period | Eval pass | Persons funded | Funded persons paid | To live | Notes |
|---|---|---|---|---|---|---|
| Topstep | CY2025 | 16.8% (accounts) | 51.8% | 33.3% | 0.71% | 50K: $3,000 target, $2,000 EOD MLL, 55% best-day consistency in Combine, 40% in XFA, 5 x $150 winning days |
| Tradeify | Aug 2025-Jul 2026 | 17.2% (accounts) | 40.3% | 28.5% | 3.0% | median 3 evals per person; 50K funded: EOD trailing, $600 DLL, 35% consistency |
| MyFundedFutures | to Aug 2026 | 19.97% | 19.95% | 39.2% (28.6% earlier in 2026) | 4.2% | $250M+ cumulative payouts (numerator only) |
| Take Profit Trader | CY2025 | 36.22% | - | - | - | 20.37% in Jan-Aug 2023 |
| Earn2Trade | 2025 | 8.89% | - | 18.0-18.2% (accounts w/ withdrawal) | 5.2% of passers traded live | two-step style |
| Apex | unaudited claim | 15-20% first attempt, ~40% with resets | - | - | - | 50% consistency on new PAs from 1 Mar 2026 (30% legacy), safety net traps first $2,100 of profit, 5 days between requests |
| FPFX (10 firms, 300k accts) | 2024 | 14% (persons) | - | 45% | - | 7% of buyers paid; $800 fees / 3 challenges; avg payout 4% of account |
| Swiset (10k traders) | Aug 2024-Apr 2025 | 20.3% one-phase / 11.8% two-phase | - | - | - | architecture effect ~1.7x |
| Velotrade rulebook review (6 firms) | 2026 | - | - | 7% of buyers paid | - | |
| Lucid | - | not published | - | - | - | PTV author: 30+ payout cycles, approvals ~15 min, no rejected withdrawal |

Hall's simulation of the Lucid/Topstep geometry gives funded payout probability 34.6-34.8% at break-even drift, i.e. the published 28.5-39.2% are consistent with a near-zero-edge population under these rules.

---

## 5. What the evidence says works in 2022-2026

1. **Geometry beats cleverness.** Across every source the account's rules (T, d, trailing type, consistency, qualifying days, payout cap) move expected value more than any plausible range of trader skill. On Lucid Flex the eval is the permeable gate (no time limit, no DLL unless chosen, 50% consistency with a cushion, 40 micros) and the funded gate is where accounts die (5 x $150 days, the lock on request, no buffer). Plan the whole lifecycle, not the eval.
2. **Size for the hump, not for speed.** With a +0.1R-per-trade strategy, $100-150 risk per trade and 5-10 trades per day maximises P(pass) (77-84% in 90 days) and makes the consistency rule irrelevant (best day ~$750-1,100). Every doubling of size from there costs 10-20 pp of pass probability and buys only calendar time, which Flex does not charge for.
3. **The consistency rule is a sizing rule in disguise.** It removes the variance-farmer's edge (zero-skill pass ceiling ~23% instead of ~27-47%) and penalises exactly the lumpy behaviour that passes fastest. Cap the day at target/4 to target/5 and it never binds.
4. **Split the cadence.** Trade the full setup list in the eval; in the funded account trade the one or two best setups, bank days >= $150, and keep day losses <= $300. Both Hall's two-stage simulation and this report's MC show funded survival is dominated by trades-per-day and size, not by expectancy.
5. **The first payout decision is the biggest single lever in the funded stage.** Requesting at $1,000-2,000 of profit leaves $400-900 of room and a 65-85% chance of losing the account; waiting to $4,000 leaves $1,900 and a 3-30% chance, and pays more within 120 days once trade frequency is >= 5/day. Scale size down to ~10% of remaining room after any request.
6. **Daily stops and profit caps are not where the edge is**, but they are free insurance against the intraday breach check and against clustered losses (FOMC, 08:30 data, 2025-Q2 tariff regime). Keep them.
7. **Multi-account tricks do not create value.** Hedged pairs are prohibited and EV-neutral; copying one strategy to N accounts multiplies both EV and correlated ruin. Use extra accounts only to run the safe and aggressive configs in parallel.
8. **The honest bar is low but real.** Break-even is ~41% win rate at 1:1.5 net of costs (driftless 40%); everything in this family assumes the strategy layer delivers at least +0.1R net per trade. If it does not, no tactic in this document rescues it (Hall's 190-without-costs / 0-with-costs ORB sweep; sec. 8.4: the only durable configurations pay out 0%). The companion families' reports (`evidence_and_failures.md`) say the 2025-26 tape makes that edge hard to find in OHLC-only intraday ES/NQ rules; the risk layer here is necessary, not sufficient.

---

## 6. Open items the backtest should settle

- Quantify Lucid's consistency "cushion" empirically (not published); treat it as zero in the simulator (conservative).
- Confirm whether the 50%-of-profit payout base is total profit or cycle profit (Lucid's wording is "50% of Profit"; `payout_base='total'` is encoded; the alternative only matters from the second payout).
- Model N copied accounts as one correlated path with per-account execution noise, not as independent draws.
- Replace the i.i.d. Bernoulli model in sec. 3 with the real strategy's daily P&L and MAE series (block bootstrap by month, 2025-01 to 2026-09) before choosing the two final configurations.
