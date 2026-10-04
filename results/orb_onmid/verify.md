# orb_onmid - adversarial verification (MGC, fixed params from final.json)

Verifier run 2026-10-04. Contract MGC, params = `final.json` (levels on, last_entry 11:00, exit_time 12:00, stop_mode mid,
max_stop_atr 0.4, tgt_frac 0.5, buffer_ticks 2, min_atr 0.25, max_atr 1.2, exhaust_frac 1.0, outside_mode skip, gap_min 0,
max_trades 1). All numbers per ONE micro contract after costs ($1.30 RT + 1 tick slippage per side on stop/market fills).
MAIN = 2025-01-01..2026-09-30, PRIOR = 2023-01-01..2024-12-31. Walk-forward numbers are taken from `walkforward.json`
(not re-run). No file under backtest/, tests/ or strategies/ was modified.

## 1. Look-ahead review of `strategies/orb_onmid.py` (line by line)

| item | finding |
|---|---|
| Overnight levels (`overnight_range(df1, rth_open)`) | bars with tod >= 18:00 or tod < rth_open of the SAME day_id (session = 18:00 -> next 17:00). For MGC rth_open = 08:20 so the window is 18:00 -> 08:19, entirely before the first RTH bar. The window is complete before the order index `i0` (first RTH bar). OK. |
| London levels (`london_range`, not used by the fixed params) | tod in [02:00, 08:00), pre-session check over [08:00, rth_open). Both strictly before `i0`. OK. |
| ATR (`daily_atr(df1, 14, rth_only=True, rth)`) | Wilder ATR on daily RTH bars, `.shift(1)` -> day d uses days < d. `min_periods=n`, NaN rows excluded by `lv['atr'].notna()`. OK. |
| Gap filter (`gap_min`, off) | `daily_bars(...)['close'].shift(1)` -> prior RTH close. OK. |
| Bias `o0` = OPEN of the first RTH bar `i0` | The order is placed at index `i0` and is live from the open of bar `i0`. Strictly, the guide says a decision at index i may use information only up to the close of bar i-1; here the decision uses the open print of bar i itself. This is the open price that a trader sees at 08:20:00 before placing the stop order, and it cannot produce a fill advantage: the entry is a stop at level +/- 2 ticks filled at max(open, level)+slip; days where o0 is already beyond the biased level are skipped (`outside_mode skip`), so no "fill at the open below the level" is possible. Quantified below (1b): replacing o0 with the close of bar i0-1 moves MAIN PF 1.422 -> 1.411 and leaves PRIOR identical. Not a P&L-generating look-ahead. |
| Session's own high/low/close | not used anywhere in the entry decision (only ON range and `o0`). OK. |
| `i_next` | not used (1-minute index, order placed at `i0`). OK. |
| `valid_bars = last_entry - rth_open` (160 min) + `set_session(rth_open, last_entry, exit_time)` | entries limited to [08:20, 11:00), flat at 12:00 (clamped to 13:25 for MGC). OK. |
| `first = first[first['tod0'] <= o_tod + 5]` | uses the first RTH bar's tod; known at that bar. OK. |
| Thin sessions | `backtest.run.prepare` removes sessions with < 80% of typical RTH bars by default; the strategy does not override this. OK. |
| Dates / regime switches encoding 2025-26 knowledge | none; all parameters are time-of-day / fractions of range / ATR multiples. OK. |

**lookahead_found = false.** The only technical deviation is the same-bar open used for the bias. If the project wants
strict compliance, the fix is: in `generate`, replace `'o0': g['open'].first()` by the close of the bar before `i0`
(`df1['close'].values[i0 - 1]`, checking `df1['day_id'].values[i0 - 1] == day_id`) and keep the order at `i0`. It costs
~0.01 PF on MAIN (see 1b) and changes nothing on PRIOR; the module docstring already documents the choice.

### 1b. Adversarial variant: bias from the close of bar i0-1 (scratch reimplementation, module untouched)
| period | original (open of i0) | prev-close bias |
|---|---|---|
| MAIN | 210 trades, net +5,959, PF 1.422 | 211 trades, net +5,851, PF 1.411 |
| PRIOR | 252 trades, net -2,448, PF 0.744 | 252 trades, net -2,448, PF 0.744 |

## 2. Fixed-params re-runs
| period | trades | net $ | win | PF | Sharpe | maxDD intra | largest_day_share |
|---|---|---|---|---|---|---|---|
| MAIN 2025-01-01..2026-09-30 | 210 | +5,959 | 57.1% | **1.422** | 1.59 | -2,025 | 0.098 |
| PRIOR 2023-01-01..2024-12-31 | 252 | -2,448 | 42.1% | **0.744** | -1.46 | -3,189 | n/a (net < 0) |

Matches `walkforward.json.fixed_main` / `fixed_prior` exactly (final.json's 211 / PF 1.435 came from an earlier engine build;
the difference is one trade). MAIN by year: 2025 = 114 trades, net +662, PF 1.10; 2026 (to Sep) = 96 trades, net +5,297,
PF 1.69. 89% of the MAIN net is 2026.

## 3. Plateau (MAIN, one neighbour up and down per parameter, everything else fixed)
GRID (`levels`, `tgt_frac`, `stop_mode`, `exit_time`, `last_entry`) has one numeric parameter (`tgt_frac`) and two ordered
time parameters; the grid step for `tgt_frac` down would be 0.0 (degenerate), so 0.25 was used. Non-GRID numeric PARAMS were
also perturbed as a supplement.

| parameter | down -> PF | up -> PF |
|---|---|---|
| tgt_frac 0.5 | 0.25 -> 1.514 | 1.0 -> 1.389 |
| exit_time 12:00 | 11:30 -> 1.435 | 13:00 -> 1.223 |
| last_entry 11:00 | 10:30 -> 1.396 | 11:30 -> 1.420 |
| (supplement) max_stop_atr 0.4 | 0.3 -> 1.300 | 0.5 -> 1.369 |
| (supplement) buffer_ticks 2 | 1 -> 1.403 | 3 -> 1.411 |
| (supplement) min_atr 0.25 | 0.15 -> 1.422 | 0.35 -> 1.412 |
| (supplement) max_atr 1.2 | 1.0 -> 1.388 | 1.5 -> 1.368 |

GRID neighbours >= 1.05: 6/6 -> **plateau_frac = 1.00** (supplement 8/8; all 14 >= 1.05). The existing 32-cell MAIN grid
(`grid_main_MGC.csv`) is also 32/32 positive (PF 1.08-1.44). BUT the same 32 cells are 0/32 positive on PRIOR
(`grid_prior_MGC.csv`, PF 0.60-0.92): the plateau is a property of the 2025-26 gold regime, not of the parameters.

## 4. History
| period | trades | net $ | PF |
|---|---|---|---|
| 2015-01-01..2022-12-31 | 1,126 | -3,544 | **0.861** |
| same, ex-2020 (from the trades table) | 998 | -4,348 | **0.800** |
| 2020-01-01..2020-12-31 | 128 | +804 | **1.213** |

By year: 2015 0.76, 2016 0.70, 2017 0.60, 2018 0.89, 2019 0.76, 2020 1.21, 2021 0.87, 2022 0.97 (then 2023-24 PF 0.74).
Only 2020 and 2025-26 are profitable in 12 years.

## 5. Slippage
MAIN with `--slip 2`: 210 trades, net +5,612, **PF 1.392**, Sharpe 1.50. The extra tick costs ~$350 over 210 trades
(gold tick = $1 on MGC), so slippage is not the issue.

## 6. Thin-session / concentration dependence (MAIN trades table)
- Net +5,959 over 210 trading days. The 10 best days sum to +4,098 = **68.8% of net** (20% of gross positive days; the
  distribution is 73 targets at +$209 avg, 54 stops at -$198, 83 noon flats at +$17, so the net is a thin residual of large
  gross flows: gross wins $16,661 vs gross losses $10,702).
- Largest day 586.6 = 9.8% of net. Largest month 2026-07 (+1,720) = **28.9% of net** (< 40%); 2026-03 (+1,126) 18.9%,
  2026-09 (+1,091) 18.3%. No month > 40%.
- 2026 alone = 89% of net; 2025 alone PF 1.10 on 114 trades.
- Entry hour: 08:20-08:59 entries 114 trades +6,580; 09:xx 65 trades -19; 10:xx 31 trades -602. The entire edge sits in
  the first 40 minutes after the gold pit open, and the README shows that hour was negative in 9 of the 10 years before 2025.
- Walk-forward: `wf_2025` PF 1.266 (206 trades, net +3,937, Sharpe 1.07); `wf_all` 2023-2026 PF 1.117 with 2023-24 OOS
  quarters mostly negative. The Lucid MC on the walk-forward OOS stream is not `recommended` at any size (exp_net_lb -146,
  best point estimate +13.5 at 10 micros vs zero-edge control -101; pass_within_21 0.195).

## Criteria
| criterion | value | pass? |
|---|---|---|
| no look-ahead | none material (same-bar open for bias, quantified at 0.01 PF) | yes |
| walk-forward OOS 2025 PF >= 1.1 | 1.266 | yes |
| plateau_frac >= 0.5 | 1.00 (MAIN only; 0/32 cells positive on PRIOR) | yes |
| history 2015-2022 PF >= 1.0 ex-2020 | 0.800 (all 7 non-2020 years losing; 2023-24 0.744) | **no, and not narrowly** |
| slippage-2 MAIN PF >= 1.0 | 1.392 | yes |

## Verdict: dead
The implementation is honest and the MAIN result reproduces (PF 1.42, 210 trades, Sharpe 1.59, robust to slippage and to
every single-parameter perturbation). But the fixed rule loses money in 9 of the 10 years before 2025 (2015-2022 PF 0.80
ex-2020, 2023-24 PF 0.74), the whole MAIN edge is 2026 gold volatility in the first 40 minutes after the pit open, the 10 best
days are 69% of the net, and the Lucid Monte Carlo (both on MAIN and on the walk-forward OOS stream) has a negative
lower-bound expected net at every size with no recommended size. One hard criterion (history) is missed by a wide margin,
so the verdict stays 'dead', in agreement with the strategy README.

Scratch outputs: `/tmp/claude-0/-home-user-claude-workspace/1cc73676-89d9-5a1b-9d6f-8a4e4b0e81e2/scratchpad/v_onmid_*.txt`
(+ `_trades.csv`, `_daily.csv`, `_metrics.json`), variant script `v_onmid_prevclose.py`.
