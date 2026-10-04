# mr_onrev - adversarial verification (MNQ, fixed params = module defaults)

Fixed params from final.json: `{}` -> PARAMS defaults: thresh 0.30, universe all3, stop_atr 1.0, entry 09:31, flat 15:55,
sides both, max_trades 1. All numbers per 1 MNQ micro, after costs (1 tick slip/side, $1.30 RT), `backtest.run`.
Run logs / trade tables: scratchpad `onrev_v/` (main, prior, slip2, th020, th050, sa075, sa150, h2020, hist).

## 1. Look-ahead review of strategies/mr_onrev.py (line by line) -> none found
- `inst_table`: `close16` = last 1-min close with tod < 16:00 per session; `prior_close = close16.shift(1)` and
  `prior_session` = previous session date. Only the shifted value is used -> the session's own close never enters.
  `open_0930` = open of the 09:30 bar; r uses only open_0930 and prior_close.
- `cross_section`: other universe members loaded via `load_1m` for the same session span, joined on session date;
  sessions whose members' prior sessions differ are dropped (alignment filter uses only past dates). Demeaned x, spread,
  is_min / is_max all computed from the 09:30 opens and prior closes only.
- `generate`: order placed at the index of the 09:31 bar (`tod == entry_time`) as a market order (entry_px NaN ->
  fill at the open of that bar + slip). The engine rule "signal at i may use info to close of i-1" is satisfied: the
  decision uses the 09:30 *open*, known before the 09:30 bar even closes. Not a resampled strategy -> no i_next.
- Stop: `daily_atr(df1, 14, rth_only=True)` = `atr(daily_bars).shift(1)`; `daily_bars` groups by day_id, `atr` uses
  `min_periods=14`; NaN / non-positive ATR days are skipped. Day d's stop uses days < d only. Mapped by day_id ->
  session via `groupby('day_id')['session'].first()`.
- `set_session('09:31','09:32','15:55')` restricts entries to the 09:31 bar and forces flat at 15:55. `prepare()` adds
  the thin-session filter and forbids entries before `start` (warm-up loaded).
- No VIX, no opening_range / overnight_range / session_vwap, no date or regime constants. Defaults are the published
  rule (thresh 0.30, all3, stop 1.0 ATR) and nothing encodes 2025-2026 knowledge.
- Re-run of the fixed params reproduces final.json exactly (MAIN PF 1.0605, 221 trades; PRIOR PF 0.918, 206 trades).

## 2. Fixed params re-run
| window | trades | net $ | PF | Sharpe | maxDD intra | largest_day_share |
|---|---|---|---|---|---|---|
| MAIN 2025-01-01..2026-09-30 | 221 | +2509 | 1.061 | 0.25 | -5181 | 0.826 |
| PRIOR 2023-01-01..2024-12-31 | 206 | -2055 | 0.918 | -0.34 | -6337 | n/a (net < 0) |

## 3. Plateau (MAIN, one grid step up/down per numeric GRID parameter, others fixed)
| run | trades | net $ | PF | >= 1.05 |
|---|---|---|---|---|
| thresh 0.20 | 243 | +2535 | 1.056 | yes |
| thresh 0.50 | 176 | +5519 | 1.169 | yes |
| stop_atr 0.75 | 221 | +4772 | 1.122 | yes |
| stop_atr 1.5 | 221 | +3842 | 1.096 | yes |
plateau_frac = 4/4 = **1.00**. The default sits at the *bottom* of its neighbourhood (every neighbour is better),
and every neighbour shares the same best day (2025-11-20, +2073) -> the "plateau" is a plateau of tail-driven,
noise-level PFs (1.05-1.17 with Sharpe 0.25-0.60), not evidence of an edge.

## 4. History with fixed params
| window | trades | net $ | PF | Sharpe |
|---|---|---|---|---|
| 2015-01-01..2022-12-31 | 936 | -6316 | 0.915 | -0.31 |
| 2015-2022 ex-2020 | 818 | -5826 | **0.905** | |
| 2020-01-01..2020-12-31 | 118 | -490 | 0.960 | -0.17 |
Per year PF: 2015 1.42, 2016 0.94, 2017 0.76, 2018 0.95, 2019 0.94, 2020 0.96, 2021 0.77, 2022 0.90. Seven of eight
years are losing; PRIOR 2023-24 is losing too. Only 2025-26 is positive, and that only via a handful of days.

## 5. Slippage
MAIN with --slip 2: 221 trades, net +2298, PF **1.055**, largest_day_share 0.90. Passes the >= 1.0 bar only because
MNQ's extra tick is $0.50 and the average trade is $11; the edge was never cost-driven, it is tail-driven.

## 6. Thin-session / tail dependence (MAIN trades table)
- Top 10 days sum to +11,753 = **468% of net** (+2509). Net ex-top-10 days = -9,244. PF ex the single best day 1.011.
- Largest day 2025-11-20 +2073 = 83% of net. Best month 2025-02 (+2790) = **111% of net**; six months each exceed 40%
  of net (2025-02 +2790, 2026-02 +1617, 2025-10 +1598, 2026-06 +1343, 2025-11 +1126, 2025-05 +1044) because net is so
  small relative to monthly swings (worst month 2025-03 -4204, 8 of 21 months negative).
- Exit mix: 202 time exits +18,553 vs 19 disaster stops -16,044; shorts +2351 vs longs +158.

## Walk-forward (from walkforward.json, not re-run)
OOS 2025-01..2026-09 concatenated: 166 trades, net +5919, PF 1.197, Sharpe 0.69, maxDD intra -4069; wf_all (2023-26)
PF 1.106. The WF path flips params nearly every fold (thresh 0.2/0.5, universe eq/all3, sides long/both), i.e. it is
selecting noise; the 2025 OOS result still contains the same +2073 day (35% of its net). Lucid WF 2025: pass rate 0.19,
expected net per eval -96, recommended size 0.

## Criteria
| criterion | value | pass |
|---|---|---|
| no look-ahead | none found | yes |
| WF OOS 2025 PF >= 1.1 | 1.197 | yes |
| plateau_frac >= 0.5 | 1.00 | yes |
| history 2015-2022 PF >= 1.0 ex-2020 | 0.905 (0.915 incl. 2020) | **no** |
| slippage-2 MAIN PF >= 1.0 | 1.055 | yes |

## Verdict: dead
The history criterion is missed by a wide margin (PF 0.905 over 818 trades, 7 of 8 years losing, -$5.8k), and the
2023-24 PRIOR window is also losing (PF 0.918). The in-window MAIN result (PF 1.06, Sharpe 0.25) is entirely tail
dependent: the 10 best days are 4.7x the net, the best month is 111% of net, and PF ex-best-day is 1.01. Nothing a
2-tick slippage test or a 4-neighbour plateau says can rescue a strategy whose edge is absent in 10 of 12 years;
this is not a "narrow miss". Confirms the original author's dead verdict. Intraday DD -5181 per micro is also
incompatible with the $2,000 trailing limit at any size.
