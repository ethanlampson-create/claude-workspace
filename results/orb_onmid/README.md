# orb_onmid - Session-range (overnight / London) breakout with midpoint bias, noon time stop (family orb_session)

Module: `strategies/orb_onmid.py`. Research: `research/families/orb_session.md` section 5.1-5.2 (tradingstats NQ 2015-2025:
RTH open above the overnight midpoint -> ON high breaks first 76%; above the London midpoint -> London high first 83%).
Periods: MAIN = 2025-01-01..2026-09-30, PRIOR = 2023-01-01..2024-12-31. All numbers per ONE micro contract after costs
(engine: $1.30 RT commission + 1 tick slippage per side on stop/market fills).

## Rules as implemented
- Levels (`levels`): `on` = overnight range 18:00 -> rth_open (`strategies.common.overnight_range`); `london` = high/low of
  the bars with tod in [02:00, 08:00) of the same session (>= 200 bars required). `mid = (high+low)/2`, `rng = high-low`.
  ATR = Wilder ATR(14) of daily RTH bars, shifted one day. Skip if `rng < min_atr*ATR`, `rng > max_atr*ATR` or ATR NaN.
  For `london` also skip when the biased level was already broken between 08:00 and rth_open (08:20 for MGC).
- Bias at the RTH open from the first RTH bar's OPEN `o0` (session must open within 5 min of rth_open): long if `o0 > mid`,
  short if `o0 < mid`, none if equal. Optional `gap_min`: `|o0 - prior RTH close| / prior close >= gap_min`.
- If `o0` is already beyond the biased level: skip when `(o0 - level) > exhaust_frac*rng`, else `outside_mode` `skip`
  (default) or `pullback` (limit order at the level, valid until last_entry, same stop/target).
- Entry: stop order at `level +/- buffer_ticks*tick` placed at the first RTH bar index (live from that open; fills at
  max(open, level)+slip), valid until `last_entry`. Only the biased side. One trade per day.
- Stop: `stop_mode` `mid` = session midpoint, `frac(x)` = entry -/+ x*rng; both capped at `max_stop_atr*ATR` from the entry.
  Target = entry +/- `tgt_frac*rng`. Exits: stop, target, forced flat at `exit_time` (clamped to 15:55; 13:25 for MGC).
- Session: `set_session(rth_open, last_entry, exit_time)`, `max_trades_day = 1`. MGC: overnight 18:00 -> 08:20, entries
  08:20-11:00, London levels 02:00-08:00 with the pre-session check over 08:00-08:20.
- Look-ahead: levels and ATR use bars strictly before rth_open; the bias uses the first RTH bar's open only; fills were
  spot-checked against the levels (entry = on_high + 0.5 buffer + 0.25 slip on MNQ).

Defaults (`PARAMS`, the published rule): levels on, last_entry 11:00, exit_time 12:00, stop_mode mid, stop_frac 0.5,
max_stop_atr 0.4, tgt_frac 0.5, buffer_ticks 2, min_atr 0.25, max_atr 1.2, exhaust_frac 1.0, outside_mode skip, gap_min 0,
max_trades 1. Grid (32): levels on/london x tgt_frac 0.5/1.0 x stop_mode mid/frac(0.5) x exit_time 12:00/15:55 x
last_entry 10:30/11:00. Pass 2 (8): gap_min 0/0.003 x outside_mode skip/pullback x last_entry 10:00/11:00.

## Headline results, default rule (per micro, after costs)

| contract | period | trades | net $ | win | PF | Sharpe | maxDD intra | pos days | pos months |
|---|---|---|---|---|---|---|---|---|---|
| MNQ | MAIN | 276 | -4,590 | 44.6% | 0.84 | -0.94 | -6,027 | 45% | 43% |
| MNQ | PRIOR | 303 | -3,315 | 45.2% | 0.83 | -1.03 | -4,255 | 45% | 29% |
| MES | MAIN | 250 | -3,401 | 47.2% | 0.74 | -1.53 | -4,520 | 47% | 38% |
| MES | PRIOR | 268 | -1,937 | 48.9% | 0.79 | -1.14 | -2,394 | 49% | 33% |
| MGC | MAIN | 211 | +6,149 | 57.3% | 1.44 | 1.64 | -1,835 | 57% | 71% |
| MGC | PRIOR | 290 | -2,240 | 44.8% | 0.79 | -1.24 | -2,982 | 45% | 29% |

MGC default rule by year (2015-2026): net -695, -974, -1084, -217, -686, +804, -581, -110, -1517, -727, +849, +5,297 (2026 to
Sep). PF >= 1.0 in 3 of 12 years; 2026 alone is 86% of the MAIN net.

Lucid 50K Flex Monte Carlo (MGC, MAIN daily P&L, constant micros): 5 micros pass 0.31 / exp net -$84; **10 micros pass 0.21,
P(first payout) 0.03 unconditional, expected net -$44 per evaluation, median 8 days to pass**; 15+ micros worse. Monthly pass
rate is 0 in 8 of 21 start months. Negative expected net at every size even on the favourable window.

## Diagnostics
MNQ MAIN default: 117 stops at -$223 avg vs 89 targets at +$225 avg, 70 noon flats at +$20: a 1:1 payoff at 43% resolved
win rate. Entries after 10:00 are worse (-$34/trade vs -$13 for 09:xx). Both sides lose (longs -$2,405 / 163, shorts -$2,186 /
113). VIX 20-25 is the worst bucket (-$60/trade); no bucket is positive except >35 (n=2). Mon and Fri are the worst weekdays.
Winners' median MAE 38 pts vs losers' median MFE 32 pts - no stop/target asymmetry to exploit. Max 8 consecutive losing trades.

Direct check of the research statistic on our NQ data (RTH open vs overnight midpoint, bias set, sessions with a valid range):
biased ON level breaks first 70.2% (MAIN, n=446), 75.1% (PRIOR, n=515), 72.2% (2015-2022, n=2,055) - the directional claim
holds. But conditional on the biased level breaking before 11:00, the excursion beyond the level reaches 0.5x range only 40%
(MAIN) / 45% (PRIOR) / 48% (2015-22) of the time, reaches 1.0x range 19-25%, and price revisits the midpoint afterwards
53-57% of the time. "Which side breaks first" is a shallow-break statistic (a third of the breaks happen in the first 5
minutes by a few ticks); a mid stop with a 0.5x-range target is close to a coin flip before costs.

MGC MAIN default: hour 08 entries (08:20-09:00) made +$6,770 on 115 trades (63% win); 09:xx -$19 (65), 10:xx -$602 (31).
Exits: 74 targets +$209, 54 stops -$198, 83 noon flats +$17. Both sides positive on MAIN (longs +$3,049 / 127, shorts
+$3,100 / 84), both sides negative on PRIOR. Dec-25 (-1,088) and Aug-26 (-539) are the losing months; Jul-26 +1,720,
Mar-26 +1,126, Sep-26 +1,091. The 08:xx hour that carries MAIN was negative in 9 of the 10 years before 2025.

## Attempts log
1. Default rule, three instruments, both periods (table above). MNQ/MES negative in both periods; MGC positive on MAIN only.
2. MAIN grid, 32 combos per instrument (`grid_main_{MNQ,MES,MGC}.csv`):
   - MNQ: 4/32 cells positive, all `levels=on, tgt_frac=1.0, exit 15:55` (PF 1.05-1.08, 39% win, largest day 53-84% of
     net). The best cell is PF 1.00 on PRIOR and 1.08 on 2015-2022 - noise. The noon time stop (the research's point)
     makes every MNQ cell worse than the 15:55 exit (median PF 0.85 vs 0.96): the breakouts that survive to noon are the
     ones that keep going. `london` levels: 102 trades, PF 0.78-0.96. Stop mode mid vs frac(0.5) is immaterial.
   - MES: 0/32 cells positive (best PF 0.96 london/1.0/15:55; all `on` cells PF 0.74-0.93).
   - MGC: 32/32 cells positive, PF 1.08-1.44, best = defaults (on/0.5/mid/12:00/11:00). Here the noon exit helps (PF 1.44 vs
     1.21 at 15:55) and `on` beats `london`.
3. MGC PRIOR grid, 32 combos (`grid_prior_MGC.csv`): 0/32 cells positive (PF 0.60-0.92); rank correlation of net MAIN vs
   PRIOR 0.60 only because `on` beats `london` in both. No parameter set holds across the two periods.
4. Pass 2 (`grid_pass2_{MNQ,MGC}.csv`, both periods; base = defaults): `gap_min 0.003` raises MNQ PF 0.84 -> 0.87-0.90
   (MAIN) and 0.83 -> 0.84 (PRIOR) - still losing. `outside_mode pullback` is slightly worse everywhere (the retest entry
   adds 1-3 trades with negative average, consistent with Mesfin 2026). `last_entry 10:00` helps MGC MAIN (PF 1.58; with gap
   0.003: PF 1.82, 124 trades) but PRIOR stays PF 0.77-0.83. Not adopted: nothing holds on PRIOR, and the default is kept
   as the published rule.
5. Year-by-year MGC 2015-2026 (above): the strategy lost in 9 of 12 years; the MAIN profit is a 2025-26 gold-volatility regime.

Not tried (would be different strategies): close-confirmed entries, trend filter, fading the shallow breaks back to the
midpoint (the 53-57% midpoint-revisit statistic points to a mean-reversion rule rather than a breakout).

## Verdict: dead
The midpoint-bias statistic replicates (70-75% first-break direction on NQ 2015-2026) but it does not convert into a
tradable breakout: the biased break is usually shallow and the midpoint is revisited more often than a 0.5x-range target
is reached, so MNQ (PF 0.84 / 0.83) and MES (0.74 / 0.79) lose in both periods across all 32 grid cells. MGC is positive
on every MAIN cell (default PF 1.44, 211 trades, Sharpe 1.64) but negative on every PRIOR cell and in 9 of 12 years, and
even on MAIN the Lucid Monte Carlo has negative expected net per evaluation at every size (pass rate 0.21 at 10 micros).
No fixable flaw within this rule set was found; the useful by-product is the measured statistic (shallow breaks, 53-57%
midpoint revisit) for a future session-level mean-reversion candidate.

Files: `final.json` (MGC, default params), `final_MGC_{main,prior}_{trades,daily}.csv`, `grid_main_{MNQ,MES,MGC}.csv`,
`grid_prior_MGC.csv`, `grid_pass2_{MNQ,MGC}.csv` (+ `.log`), `report_{MNQ,MGC}_main_default.json`.
