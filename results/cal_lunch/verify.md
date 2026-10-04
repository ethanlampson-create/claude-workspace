# cal_lunch - adversarial verification (2026-10-04)

Contract MNQ, fixed params from `final.json` (`variant long_only, 12:00 -> 14:00, stop_mode pct, stop_pct 0.4, skip_macro True,
skip_opex False, max_trades 2, dls_mult 1.0`). All numbers per ONE micro contract after costs ($1.30 RT + 1 tick/side).
Runs: `python3 -m backtest.run --strategy cal_lunch --contract MNQ --start .. --end .. --params '<final.json params>'`, run two
at a time; logs and trade tables in the session scratchpad. Walk-forward numbers are taken from `walkforward.json` (not re-run).

**Verdict: dead.** No look-ahead, WF OOS 2025 PF 1.185 (pass), plateau 1.0 (pass), slippage-2 PF 1.298 (pass), but the
2015-2022 history is PF 0.866 (0.804 ex-2020, six of eight years negative): a large miss, not a narrow one. The MAIN result is
also one afternoon (2025-04-09, 45% of net), the top-10 days are 110% of net (ex-top-10 PF 0.967), April 2025 is 44% of net,
2026 OOS is PF 0.997 and the Lucid lower bound equals the zero-edge control.

## 1. Look-ahead audit (`strategies/cal_lunch.py`, `strategies/_cal_flags.py`, `strategies/common.py`, `backtest/engine.py`)

| item | finding |
|---|---|
| entry decision | `i(12:00)` = first bar with `720 <= tod < 725`; market order placed at that index fills at its OPEN + 1 tick. Nothing of bar i is used. OK |
| stop size | `0.4% x close of bar i-1`, `_ref_close` requires that bar to belong to the same session (NaN otherwise -> day skipped). OK |
| ATR14d | `daily_atr(..).shift(1)`; only gates `day_ok` (non-NaN) in `pct` mode. Shifted to strictly prior days. OK |
| macro_day | `rel0830 = range(08:30-08:31 bars) / rolling median of the PRIOR 60 sessions (shift(1))`, known at 08:32 < 12:00. OK |
| fomc | hard-coded FOMC statement dates (published schedule, known a year ahead; 2025-26 dates are the Fed's calendar, not fitted). OK |
| opex | 3rd Friday calendar arithmetic (off by default). OK |
| exit | `exit_at(i(14:00), which=2)` = market at the 14:00 open; `set_session(12:00, 12:02, 14:00)` force-flat from 14:00. OK |
| i_next misuse | none (no resampling). session_vwap / opening_range / overnight_range not used. VIX / SMA not used. |
| 2025-26 knowledge in params | none: 12:00/14:00 and the 0.4% stop come from the 2024 Quantpedia paper; defaults = published rule. |
| forward-looking filter | `day_ok` requires that a 14:00 bar EXISTS in the session (`i_exit.notna()`, `i_long < i_exit`), which is not knowable at 12:00. Effect on MAIN: exactly ONE non-thin session excluded (2026-03-12, a 14:00-14:59 feed gap; the position was -$85 unrealised at 13:59). Immaterial and not favourable. Early-close days are also excluded by it, but those are calendar facts and `backtest.run` skips thin sessions anyway. |

Fill audit over the 364 MAIN trades (scratch script): every entry at tod 12:00 with fill == bar open + tick; `ref` bar in the same
session on 364/364; 83 stops, 82 exit exactly at `entry - 0.4% x ref - tick`, 1 gap-through at the bar open (engine's worst-case
rule), 0 better than the level; 281 clock exits all at the 14:00 open - tick; latest exit tod 14:00; 0 trades on macro/FOMC days.

**lookahead_found = false.** No fix required.

Harness artefact worth recording (not look-ahead, the opposite): `backtest.run` loads a 45-calendar-day warm-up (~31 sessions)
while the 08:30 median needs 48 of 60 prior sessions, so `macro0830` is unarmed (NaN -> False) until **2025-01-28** in the MAIN run.
A fully armed detector flags 2025-01-08, 01-10 (NFP), 01-14 (PPI), 01-15 (CPI); the fixed-params MAIN run traded all four
(-171, +527, +345, +214 = **+$915**, 13% of MAIN net; 2025-01-10 is the 3rd-best day of the run). Applying the rule as written,
MAIN would be ~+$5,950 / PF ~1.27. The same warm-up effect applies to every strategy using `_cal_flags` through `backtest.run`.

## 2. Fixed-parameter re-runs

| run | trades | net $ | PF | Sharpe | maxDD intra | largest day | largest_day_share | pos months |
|---|---|---|---|---|---|---|---|---|
| MAIN 2025-01-01..2026-09-30 | 364 | +6,867.5 | **1.315** | 1.17 | -1,516 | +3,089 (2025-04-09) | **0.450** | 15/21 |
| PRIOR 2023-01-01..2024-12-31 | 304 | +649.9 | **1.045** | 0.22 | -1,845 | +437 | 0.672 | 13/24 |

Both reproduce `final.json` / `walkforward.json` (`fixed_main` 1.3148, `fixed_prior` 1.0453) exactly.

## 3. Plateau (MAIN, one grid step up / down, everything else fixed)

The only numeric parameter in `GRID` is `stop_pct` [0.3, 0.5] around the fixed 0.4:

| neighbour | trades | net $ | PF | PF ex 2025-04-09 | >= 1.05 |
|---|---|---|---|---|---|
| stop_pct 0.3 | 364 | +6,618 | 1.312 | 1.166 | yes |
| stop_pct 0.5 | 364 | +5,589 | 1.239 | 1.107 | yes |

**plateau_frac = 2/2 = 1.00.** Extended to the non-numeric grid axes for context: `long_exit 13:30` PF 1.252 (ex-day 1.149),
`skip_macro False` PF 1.170 (ex-day 1.059), `variant short_then_long` PF 0.978 -> 4/5 = 0.80. The plateau is real on MAIN but
every cell shares the same 2025-04-09 afternoon; on PRIOR the README's grid has 3/16 cells PF > 1 on both periods and on 2015-2024 none.

## 4. History

| run | trades | net $ | PF | Sharpe | pos months |
|---|---|---|---|---|---|
| 2015-01-01..2022-12-31 | 1,671 | -5,390 | **0.866** | -0.71 | 42% |
| 2015-2022 ex 2020 | 1,461 | -6,560 | **0.804** | | |
| 2020-01-01..2020-12-31 | 211 | +1,159 | **1.174** | 0.96 | 8/12 |

By year (PF / net): 2015 0.83 / -453, 2016 0.70 / -714, 2017 1.04 / +79, 2018 0.68 / -1,471, 2019 0.93 / -255, 2020 1.18 / +1,170,
2021 0.84 / -1,219, 2022 0.77 / -2,526. Six of eight years lose; the rule needs PF >= 1.0 ex-2020 and gets 0.80. **Fails, not narrowly.**

## 5. Slippage

MAIN with `--slip 2`: 364 trades, net +6,545, **PF 1.298**, Sharpe 1.11, maxDD -1,554 (ex 2025-04-09 PF 1.157). Passes >= 1.0;
costs are not what kills this strategy (1 trade/day, 120-minute hold).

## 6. Thin-session / concentration dependence (MAIN trades table)

- Top-10 days: +$7,585 = **110.4% of net**; ex-top-10 the remaining 354 trades net -$717, PF 0.967.
- Single day 2025-04-09 (tariff-pause rally, 12:00 -> 14:00 long +$3,089) = 45.0% of net; ex that day PF 1.173.
- Months: 2025-04 = **43.9% of net (> 40%)**; one month over the 40% line. Worst month 2026-02 -$673.
- Walk-forward OOS stream (from `walkforward.json`): `largest_day_share` 0.705, 2025 PF 1.351 vs 2026-01..09 PF 0.997 (net -$38),
  2023-24 OOS folds 7/8 negative (net -$1,339); whole OOS 2023-26 PF 1.072 with `largest_day_share` 1.016.
- Lucid on the OOS stream: best 5 micros, expected net -$118 / eval, lower bound -$146 = zero-edge control, not recommended at any size.

## Criteria

| criterion | value | threshold | result |
|---|---|---|---|
| look-ahead | none | none | pass |
| WF OOS 2025 PF (`walkforward.json`) | 1.185 | >= 1.1 | pass (but 2026 portion 0.997, 70% of OOS net from one day) |
| plateau_frac | 1.00 | >= 0.5 | pass |
| history 2015-2022 PF ex-2020 | 0.804 (0.866 incl. 2020) | >= 1.0 | **fail (large)** |
| slippage-2 MAIN PF | 1.298 | >= 1.0 | pass |

One criterion fails and the miss is wide (PF 0.80 over eight years, 6/8 years negative), so the mechanical rule gives **dead**, not
marginal. The qualitative evidence agrees: the 12:00-14:00 return is 0.0 bp/day on SPX 2010-2024, the paper's instrument (MES) loses
in every period, the MAIN/OOS profit is one afternoon plus the 2025 long-biased tape, January 2025 adds $915 the rule would not have
taken, and the Lucid Monte Carlo cannot distinguish the OOS stream from zero edge.
