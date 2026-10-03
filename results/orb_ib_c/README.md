# orb_ib_c - Initial Balance C-period confirmation / narrow-IB breakout (family orb_session)

Module: `strategies/orb_ib_c.py`. Research: `research/families/orb_session.md` (tradingstats IB statistics, ES 2,686 / NQ 2,833 days
2015-2025: a C-period close outside the IB raises the 100%-extension hit rate from ~19% to 45-50%; IBs narrower than 0.5 ATR break
98.7% with a 74.8% median extension). Periods: MAIN = 2025-01-01..2026-09-30, PRIOR = 2023-01-01..2024-12-31. All numbers are per
ONE micro contract after costs (engine: $1.30 RT commission + 1 tick slippage per side on market/stop fills).

## Rules as implemented (all times ET)
- IB = high/low of the 1-min bars in [rth_open, rth_open+60) (09:30-10:30 MES/MNQ; 08:20-09:20 MGC). `ib_rng`, `ib_mid`.
  ATR = Wilder ATR(14) of daily RTH bars, shifted one day. Skip if ATR NaN, `ib_rng < ib_min_atr*ATR` (0.2), `ib_rng > ib_max_atr*ATR`
  (1.5), or the IB has < 80% of its bars. `narrow_only` additionally requires `ib_rng < narrow_atr*ATR` (0.5).
- `mode='c_confirm'` (default, the published rule): C period = [IB end, IB end+30) built from the 1-min bars (10:30-11:00; 09:20-09:50
  gold). At its close: C close > ib_high -> long, < ib_low -> short, else no trade. Reject if the C close is already more than
  `max_ext_entry*ib_rng` (0.5) beyond the broken edge. Entry = market at the open of the first 1-min bar after the C period (11:00).
- `mode='narrow_break'`: only when `ib_rng < narrow_atr*ATR`: buy stop at ib_high + 1 tick, sell stop at ib_low - 1 tick, live from the
  first bar after the IB (10:30) until `last_entry` (12:00). OCO emulated as in `strategies/orb.py` (first touch on the 1-min data
  decides the side; both in one bar -> the side nearer that bar's open). Entry tod distribution: 10:30 (14%), then spread to 12:00.
- Stop: `stop_mode='mid'` = IB midpoint, or `'atr'` = fill -/+ `stop_atr*ATR` (0.25). Distance capped at `max_stop_atr*ATR` (0.5) from
  the fill. Target = ib_high + `tgt_ext*ib_rng` (long) / ib_low - `tgt_ext*ib_rng` (short); `tgt_ext` 0.5 default, 1.0 in the grid.
- `retrace_exit` (optional, implemented with the engine's side-specific `exit_flag`): after entry, the first 1-min close more than
  `retrace_frac*ib_rng` (0.5) back inside the IB exits at the next open. NOTE: with the midpoint stop and 0.5 the retrace level equals
  the stop, so it is a no-op (verified identical results); it only matters with `stop_mode='atr'` or a smaller `retrace_frac`.
- Exits: stop, target, retrace signal, forced flat 15:55 (13:25 gold). One trade per day. Session: c_confirm entries [11:00, 11:01);
  narrow_break entries [10:30, 12:00).
- Look-ahead: the C bar is fully closed before the 11:00 order; the IB is only used after its last bar; ATR shifted; the narrow_break
  scan only decides which pending stop fills first (verified by hand on 2025-01-14: C close 5839.06 < IB low 5840.85 -> short filled
  at the 11:00 open 5839.18 - 1 tick).

Defaults (`PARAMS`, kept at the published rule): mode c_confirm, ib_min_atr 0.2, ib_max_atr 1.5, narrow_only False, narrow_atr 0.5,
max_ext_entry 0.5, stop_mode mid, stop_atr 0.25, max_stop_atr 0.5, tgt_ext 0.5, retrace_exit False, buffer 1 tick, last_entry
auto (11:01 / 12:00), flat 15:55.

## Headline results (per micro, after costs)

Default rule (c_confirm, mid stop, 0.5x target):

| contract | period | trades | net $ | win | PF | Sharpe | maxDD intra | pos months |
|---|---|---|---|---|---|---|---|---|
| MES | MAIN | 132 | -642 | 67% | 0.87 | -0.47 | -1,385 | 38% |
| MES | PRIOR | 131 | +305 | 70% | 1.12 | 0.35 | -655 | 46% |
| MNQ | MAIN | 122 | -2,272 | 62% | 0.78 | -0.84 | -3,252 | 38% |
| MNQ | PRIOR | 120 | +1,351 | 70% | 1.28 | 0.77 | -1,175 | 46% |
| MGC | MAIN | 109 | -1,184 | 69% | 0.80 | -0.64 | -1,950 | 38% |
| MGC | PRIOR | 96 | -232 | 62% | 0.90 | -0.30 | -883 | 46% |

Best configuration (MES, `mode=narrow_break`, mid stop capped 0.5 ATR, `tgt_ext=1.0`, IB < 0.5 ATR, entries 10:30-12:00, flat 15:55):

| period | trades | net $ | win | avg trade | avg win / loss | PF | Sharpe | maxDD intra | pos days | pos months | worst day | worst month | largest day share |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MAIN | 221 | +2,117 | 43.4% | +9.6 | +111 / -69 | 1.25 | 1.06 | -1,064 | 43% | 13/21 | -219 | -559 | 17% |
| PRIOR | 213 | +648 | 43.2% | +3.0 | +72 / -49 | 1.11 | 0.47 | -868 | 43% | 11/24 | -104 | -363 | 27% |

Lucid 50K Flex Monte Carlo on MAIN (`lucid_scan`, `lucid_scan_MES_main.csv`): best row 5 micros -> pass rate 0.335 (median 23.5 trading
days, P(pass within 21 days) 0.14), P(first payout | pass) 0.57, P(first payout) unconditional 0.19, expected net +$199 per evaluation
(point estimate), bootstrap 5th-percentile of expected net = -$146 (the fee), P(expected net > 0) 0.62, P(losing the fee) 0.67.
Zero-edge control at 5 micros passes 0.315 vs 0.335 for the strategy, so the simulator does NOT recommend it (`recommended=False`).
10 micros: pass 0.31, exp net +$145; 15+: ~0 or negative. The avg trade is only ~2.5x costs ($9.6 vs ~$3.80 per micro) and the
43% win rate with 9-10 consecutive losing trades keeps the eval pass rate near the no-edge baseline.

## Diagnostics (MES, best config, MAIN)
- Exit mix: 60 targets (+$136 avg), 118 stops (-$70.5 avg), 43 flat-at-15:55 (+$53 avg, 27% of gross profit comes from unresolved
  trades held to the close). Median stop distance 13 pts, median target 24.5 pts. Winners' median MAE 4.8 pts; losers' median MFE
  5.8 pts (no obvious tighter target/stop that would not also be a window fit).
- Sides: 118 longs +$910 (45% win), 103 shorts +$1,206 (42%). Unlike the c_confirm mode and the family's close-confirmed ORBs, shorts
  are not the problem here (PRIOR: longs +$384, shorts +$263).
- Entry hour: 10:xx 163 trades +$1,171; 11:xx 58 trades +$946 (11:30 cutoff is not better; pass 2).
- Weekday: Mon +$970, Tue +$473, Wed +$986, Thu +$568, Fri -$879 (31% win). On PRIOR Friday is +$124 and Thursday -$120 -> noise,
  no filter applied.
- VIX (lag): <15 -$736 (20 trades, 20% win), 15-20 +$2,056 (160), 20-25 -$141, 25-35 +$799. On PRIOR <15 is +$354 (105 trades) -> no
  regime filter applied.
- Months: 13/21 positive; April 2025 +$1,085 = 51% of MAIN net (the tariff-crash expansion after narrow IBs); losers Jan-25 -262,
  May-25 -560, Jun-25 -146, Dec-25 -144, Jan-26 -359, Mar-26 -134, Sep-26 -440. Fails the "no month > 40% of net" guideline.
- Streaks: max 9 consecutive losing trades (10 on PRIOR), 5 consecutive losing days (7 on PRIOR).
- Days with a trade: 221 of 448 (49%): roughly half of all sessions have an IB narrower than 0.5 ATR and nearly all of them break.

## Diagnosis of the published rule (c_confirm)
- Payoff is structurally wrong for the 0.5x target: after a C close `ext` beyond the edge, the target is 0.5*rng - ext away and the
  midpoint stop 0.5*rng + ext (MES median stop 24 pts vs target 9 pts = 1:2.6). Break-even win rate ~72%, realised 67% (MES) / 61%
  (MNQ): 86 targets at +$50 cannot pay for 40 stops at -$121. The `atr` stop (0.25 ATR) halves the loss but PF stays ~1.0.
- With `tgt_ext=1.0` (the 45-50% extension statistic) the payoff is ~1:1 at a 47-53% win rate: PF 1.02-1.06 on MES MAIN, 1.00-1.13
  PRIOR; MNQ MAIN 0.86-0.99 vs PRIOR 1.22-1.39. No c_confirm cell is >= 1.1 on both periods.
- Shorts lose in c_confirm on MAIN (MES -$991 / MNQ -$2,037 of the total), consistent with the family finding (Mesfin 2026).
- `narrow_only=True` makes c_confirm profitable on MAIN (MES PF 1.27-1.34, 84-85 trades) but PRIOR is 0.85-1.05 and the Lucid pass
  rate is 0 (too few, too small trades).

## Attempts log
1. Smoke tests, all instruments, both modes, both periods (table above + narrow_break: MES MAIN PF 1.16 / PRIOR 1.06, MNQ 0.88 / 1.10,
   MGC 0.80 / 0.79). Bug found and fixed: the 30-min resample buckets align to :00/:30, so the gold C period (09:20-09:50) never
   matched a bar -> the C period is now built from the 1-min bars (`opening_range` anchored at the IB end); MES/MNQ results unchanged.
2. `retrace_exit=True` on the default: identical results (retrace level == midpoint stop). With `retrace_frac=0.25`: 49 signal exits,
   MES MAIN PF 0.87 -> 0.91; with the `atr` stop PF 0.97 -> 0.95. Not adopted.
3. Module grid (32 combos, 20 effective after removing redundant cells) on MAIN and PRIOR for MES and MNQ (`grid_main_*.csv`,
   `grid_prior_*.csv`):
   - MES: all 4 narrow_break cells positive on both periods (MAIN PF 1.13-1.25, PRIOR 1.06-1.15) -> plateau; best mid/1.0
     (MAIN 1.25, PRIOR 1.11) and atr/1.0 (1.20 / 1.15). c_confirm: see diagnosis; nothing >= 1.1 on both periods.
   - MNQ: 20/20 cells positive on PRIOR (PF 1.09-1.45), 17/20 negative on MAIN (regime shift). The only MAIN cells > 1.05
     (c_confirm/atr/0.5/ib_max 1.0: 1.12) are <= 0.97 on PRIOR. MNQ = dead for this rule.
   - MGC: both modes PF 0.79-0.90 on both periods; tgt_ext 1.0 c_confirm MAIN 1.13 but PRIOR 0.83. MGC = dead.
4. Pass 2 on MES narrow_break (12 combos, both periods, `grid_pass2_MES.csv`): tgt_ext 0.75/1.0 x narrow_atr 0.4/0.5/0.6 x last_entry
   11:30/12:00. narrow_atr 0.6 adds ~25% trades but PRIOR falls to 0.98-1.03; 0.4 starves MAIN (PF 0.99-1.10); 0.75x is equal on MAIN
   and worse on PRIOR; 11:30 cutoff slightly worse. The published cell (0.5 ATR, 1.0x, 12:00) stays. Every cell's bootstrap lower
   bound of expected net per evaluation is -$146 (the fee) -> no cell is Lucid-recommended.

## Verdict: marginal
MES narrow-IB breakout is a real but thin edge (MAIN PF 1.25 on 221 trades, Sharpe 1.06; PRIOR PF 1.11; 4-cell plateau; no filters
fitted), but the avg trade is ~2.5x costs, the win rate 43%, and half of MAIN's net comes from April 2025. Under the Lucid rules it
passes 34% of the time at 5 micros with an expected net that is positive only as a point estimate and not distinguishable from the
zero-edge control. The published C-period confirmation rule (c_confirm) is dead on 2025-26 for all three instruments (target/stop
payoff inverted). Possible use: a small, time-diversified portfolio leg (entries 10:30-12:00, uncorrelated with 09:30 ORB legs), not a
standalone evaluation strategy. MNQ and MGC dead.

## Walk-forward assessment (2026-10-03, the honest yardstick) -> verdict: DEAD

`python3 -m backtest.final_select --ids orb_ib_c --jobs 2 --wf_start 2022-01-01 --max_combos 16` (`walkforward.json`, `wf_oos_2025_daily.csv`).
Parameters are re-selected every quarter on the trailing 12 months (base = `final.json` params, search = module GRID: mode x stop_mode x
tgt_ext x ib_max_atr x narrow_only, 32 cells capped at 16) and traded on the next 3 months. MES, per micro, after costs.

| stream | trades | net $ | win | PF | Sharpe | maxDD intra | pos months |
|---|---|---|---|---|---|---|---|
| WF OOS 2025-01..2026-09 | 203 | -233 | 47.8% | 0.97 | -0.12 | -1,344 | 11/21 |
| WF OOS 2023-01..2026-09 | 348 | -589 | 48.6% | 0.95 | -0.19 | -1,508 | 24/45 |
| fixed final.json cell MAIN (in-sample) | 221 | +2,117 | 43.4% | 1.25 | 1.06 | -1,064 | 13/21 |
| fixed final.json cell PRIOR | 213 | +648 | 43.2% | 1.11 | 0.47 | -868 | 11/24 |

Lucid 50K Flex on the OOS 2025 stream (`lucid_wf_2025`): 5 micros pass rate 0.045 (zero-edge control 0.071), pass within 21 sessions 0.018,
P(first payout) 0.00, expected net -$146 = the fee, bootstrap lower bound -$146, P(exp net > 0) 0.02; 10-40 micros expected net -$121..-$142,
never beating the control. `recommended=False` at every size.

What the walk-forward says:
- The selector is unstable: the 7 folds covering 2025-26 pick 5 different cells (c_confirm/mid/0.5, narrow_break/atr/1.0/narrow_only,
  narrow_break/mid/1.0/ib_max 1.0 (x3), c_confirm/mid/0.5/narrow_only, narrow_break/mid/0.5/narrow_only). In-sample Sharpe of the pick
  (0.45-1.63) does not predict its OOS quarter (-$454..+$244). This is the signature of a grid with no persistent best cell, i.e. the MAIN
  "plateau" was fitted on the window it was measured on.
- Where the OOS P&L comes from: April 2025 alone is +$935; the other 20 months sum to -$1,168. Every quarter outside the tariff-crash
  expansion is within +/- $450 of zero at 17-36 trades, which is noise at a $80 avg win / $80 avg loss payoff.
- Structural flaws unchanged from the diagnosis above: avg trade is ~1-2.5x costs on the best in-sample cell and negative OOS; the
  midpoint stop vs 0.5x target payoff of the published rule is inverted; the narrow-IB breakout only pays when range expansion follows
  compression, which clusters in a few volatility events, so monthly consistency (the evaluation requirement) is impossible.
- Gates: wf_2025 PF 0.97 < 1.03 (fails); fixed MAIN PF 1.25 < 1.3 (fails even though PRIOR 1.11 >= 1.1 and trades >= 60). proceed = False.

Previous verdict 'marginal' is superseded: it rested on the in-sample MAIN cell. No further parameter work is warranted on this rule; the
only positive OOS quarter outside April 2025 (Q3 2026, +$244, PF 1.25 on 34 trades) is not enough to reopen it.
