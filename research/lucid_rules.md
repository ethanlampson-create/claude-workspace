# Lucid Trading 50K LucidFlex — rules as encoded in `backtest/lucid.py`

Cross-checked 2026-10-03 across: proptradingvibes.com (payout rules, 50K rules, consistency, LucidFlex account),
spicyfutures.com (payout rules), funded.now (50K LucidFlex page), mytradingbuddy.ai (Flex rules),
fundedfuturesfamily.com (consistency rule), imantrading.org, pipback.com, tradetanto.com. Lucid's own site blocks
automated fetches, so these are secondary sources; where they disagreed the more conservative reading was encoded.

| Item | Encoded value | Notes / disagreement |
|---|---|---|
| Price | $146 list (frequently ~50% off) | reset $90, no activation fee |
| Start balance | $50,000 | |
| Profit target (eval) | $3,000 (6%) | balance >= $53,000 |
| Max Loss Limit (MLL) | $2,000, **end-of-day trailing** | MLL = highest EOD balance - 2,000; moves only at session close |
| MLL lock | once EOD balance > $52,100, MLL locks at $50,100 | applies eval and funded |
| Breach check | **intraday**, including open P&L | "the account breaches the moment the balance reaches it, intraday included" |
| Daily loss limit | none (optional $1,200 self-set at checkout) | encoded as none |
| Consistency (eval) | largest single day profit <= 50% of total profit at the moment of passing; keep trading until satisfied | total profit = balance - 50,000 |
| Consistency (funded) | none | all sources agree |
| Minimum trading days | 2 | one source says none; 2 encoded (conservative) |
| Time limit | none | activity rule: 1 trade per 30 days |
| Contracts (eval) | 4 minis / 40 micros | |
| Contracts (funded) | 2 minis/20 micros at start; 3 minis at +$1,000; 4 minis at +$2,000 (EOD profit) | one source says 4 minis only at +$4,500; conservative table encoded |
| Flat-by | 4:45 PM ET; reopen 6:00 PM ET | strategies here are flat by 15:55 ET anyway |
| News trading | allowed on Flex | one aggregator says "limited" |
| Micro-scalping | >= 50% of profit from trades held > 5 s | irrelevant for bar-based systems |
| Payout eligibility | >= 5 separate days with EOD profit >= $150 in the cycle AND cycle net positive (>= $1) | |
| Payout size | 50% of profit, min $500, max $2,000 per request | so first full payout needs >= $4,000 profit |
| Split | 90% trader / 10% Lucid | |
| Payouts before live | 5 (max $10,000 gross) | |
| Effect of payout on MLL | MLL set to max(MLL, $50,100) at the request; balance drops by the payout, MLL does not follow | the "Lucid trap": request too early and only a few hundred dollars of room remain |
| Buffer | none | |
| Max accounts | 10 | |

## Modelling consequences
- Risk per day must respect an **intraday** hard floor $2,000 below the highest EOD close (less once locked).
- Because the eval needs largest-day <= 50% of total, a strategy that passes in one monster day cannot pass; the
  simulator keeps trading until the ratio is satisfied, which means the big-day account then has to grind.
- Funded: the sensible payout policy is to wait until profit >= $4,000 (full $2,000 payout) so that after the lock
  at $50,100 the balance ($52,000) still has ~$1,900 of room. `min_profit_to_request` is a simulator parameter.
