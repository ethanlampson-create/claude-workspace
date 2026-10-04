# Lucid 50K Flex: strategy research, backtest and account simulation. Final report

Data: 1-minute S&P 500 / Nasdaq 100 / gold proxies (histdata.com) Nov 2010 - Sep 2026, validated against ES/NQ/GC futures. Costs: $1.30 round trip per micro, 1 tick slippage per side on market/stop fills, limit fills only on trade-through. Rules: `research/lucid_rules.md`. Engine and simulator audited (tests/, 98 tests).

## How to read the numbers

- **Walk-forward OOS 2025** = parameters chosen only on the trailing 12 months, traded on the next 3, rolled 2022-2026; the 2025-01..2026-09 slice is the honest estimate. In-sample (MAIN) numbers are shown for reference only.
- **Bootstrap bands** are moving-block bootstraps of the daily P&L (block 20 sessions). Overlapping evaluation starts make the raw start count overstate precision roughly five-fold.
- **Zero-edge control** = the same daily stream with its mean removed. A configuration must beat its control clearly to mean anything.
- **P(pass within 21 sessions)** by start month is what "monthly pass rate" means here: evaluations started in that month that pass within about a month.

## Candidate strategies (per micro contract, after costs)

| id             | contract   |   fixed_main_pf |   fixed_prior_pf |   wf25_trades |   wf25_net |   wf25_pf |   wf25_sharpe |   wf25_pos_months |   wfall_pf |   lb_micros |   exp_net |   lb_exp_net |   zero_edge |   recommended |
|:---------------|:-----------|----------------:|-----------------:|--------------:|-----------:|----------:|--------------:|------------------:|-----------:|------------:|----------:|-------------:|------------:|--------------:|
| mr_wkopen      | MES        |            2.09 |             0.81 |             3 |     182.03 |    inf    |          3.52 |              1    |     inf    |          15 |    nan    |      -146    |      nan    |             0 |
| vb_idtarget    | MGC        |            0.45 |             0.48 |             5 |     511.54 |      8.97 |          3.45 |              1    |       8.97 |           5 |    nan    |      -146    |      nan    |             0 |
| orb_close30    | MNQ        |            1.72 |             1.22 |           140 |    3870.44 |      1.45 |          1.42 |              0.71 |       1.45 |           5 |    444.84 |      -146    |     -146    |             0 |
| orb_onmid      | MGC        |            1.42 |             0.74 |           206 |    3937.26 |      1.27 |          1.07 |              0.52 |       1.12 |           5 |    -91.26 |      -146    |     -137.78 |             0 |
| mr_gapfade     | MNQ        |            1.61 |             1.17 |            65 |    1367.3  |      1.51 |          1.07 |              0.67 |       1.14 |           5 |   -146    |      -146    |     -146    |             0 |
| orb_dbl        | MNQ        |            1.67 |             1.13 |            75 |    2282.45 |      1.46 |          1.02 |              0.62 |       1.18 |           5 |    158.97 |      -146    |     -146    |             0 |
| orb_sma_rr     | MNQ        |            1.15 |             1.15 |           304 |    4684.06 |      1.17 |          0.96 |              0.71 |       1.13 |          10 |    -88.52 |      -134.52 |     -133.84 |             0 |
| orb_reclaim    | MNQ        |            1.33 |             1.18 |           309 |    2669.14 |      1.17 |          0.84 |              0.62 |       1.19 |           5 |     28.6  |      -146    |     -146    |             0 |
| mr_onrev       | MNQ        |            1.06 |             0.92 |           166 |    5918.88 |      1.2  |          0.69 |              0.62 |       1.11 |           5 |    -96.12 |      -146    |     -146    |             0 |
| mr_pdrange     | MNQ        |            1.39 |             1.56 |            12 |     140.8  |      1.31 |          0.58 |              0.14 |       1.24 |           5 |    nan    |      -146    |     -146    |             0 |
| ev_orb75       | MES        |            1.14 |             1.14 |           221 |     839.73 |      1.12 |          0.44 |              0.57 |       1.12 |           5 |   -146    |      -146    |     -146    |             0 |
| orb_crabel     | MNQ        |            1.25 |             1.39 |           225 |     776.77 |      1.03 |          0.15 |              0.48 |       1.21 |           5 |     30.58 |      -146    |       18.74 |             0 |
| mr_volband     | MGC        |            1.43 |             0.78 |           106 |     162.21 |      1.03 |          0.09 |              0.38 |       0.92 |           5 |   -126.29 |      -146    |     -141.07 |             0 |
| orb_ib_c       | MES        |            1.25 |             1.11 |           203 |    -233.21 |      0.97 |         -0.12 |              0.52 |       0.95 |           5 |   -146    |      -146    |     -146    |             0 |
| bot_noise_band | MNQ        |            0.96 |             1.08 |           578 |   -1396.55 |      0.92 |         -0.3  |              0.33 |       1.04 |           5 |    nan    |      -146    |      nan    |             0 |
| mr_ibfail      | MNQ        |            1.04 |             0.79 |           152 |   -1196.36 |      0.87 |         -0.5  |              0.43 |       0.81 |           5 |   -146    |      -146    |     -146    |             0 |
| bot_rsi_dip    | MNQ        |            0.91 |             0.72 |           776 |   -4061.93 |      0.81 |         -1.47 |              0.29 |       0.78 |           5 |    109.38 |      -146    |     1122.65 |             0 |

Columns: fixed_* = in-sample profit factor with the final parameters (MAIN 2025-26, PRIOR 2023-24); wf25_* = walk-forward OOS 2025-26; wfall_pf = walk-forward OOS 2022-26; lb_micros/exp_net/lb_exp_net = size chosen by bootstrap lower bound, point and 5th-percentile expected net per evaluation; zero_edge = control; recommended = lower bound > 0 and beats control.

## Portfolio legs

Legs: orb_close30, mr_gapfade, ev_orb75

Daily P&L correlation (walk-forward OOS 2025):

|             |   orb_close30 |   mr_gapfade |   ev_orb75 |
|:------------|--------------:|-------------:|-----------:|
| orb_close30 |          1    |         0    |       0.15 |
| mr_gapfade  |          0    |         1    |       0.02 |
| ev_orb75    |          0.15 |         0.02 |       1    |

### Sizing candidates examined

| w          | objective   |   size_mult |   eval_micros |   attempts |   p_pass |   p_pass_21 |   p_funded |   p_funded_lb |   p_first_payout |   expected_net |   net_lb |   p_net_pos |   min_monthly |   median_days_funded |
|:-----------|:------------|------------:|--------------:|-----------:|---------:|------------:|-----------:|--------------:|-----------------:|---------------:|---------:|------------:|--------------:|---------------------:|
| [5, 0, 5]  | aggressive  |        1    |            10 |          1 |     0.46 |        0.19 |       0.46 |          0.25 |             0.28 |         640.73 |   -26.64 |        0.9  |             0 |                   25 |
| [5, 0, 5]  | aggressive  |        1.5  |            16 |          1 |     0.37 |        0.3  |       0.37 |          0.2  |             0.21 |         636.76 |   -44.83 |        0.9  |             0 |                   13 |
| [5, 0, 5]  | aggressive  |        2    |            20 |          1 |     0.33 |        0.28 |       0.33 |          0.15 |             0.1  |          46.14 |   -80.64 |        0.75 |             0 |                   11 |
| [5, 0, 5]  | safe        |        1    |            10 |          3 |     0.46 |        0.19 |       0.69 |          0.61 |             0.39 |         938.63 |   -97.38 |        0.9  |             0 |                   25 |
| [5, 0, 5]  | safe        |        0.5  |             4 |          3 |     0.47 |        0.02 |       0.57 |          0.52 |             0.08 |          -7.41 |  -250.85 |        0.55 |             0 |                   58 |
| [5, 0, 5]  | safe        |        0.34 |             4 |          3 |     0.47 |        0.02 |       0.57 |          0.52 |             0.08 |          -7.41 |  -250.85 |        0.55 |             0 |                   58 |
| [5, 0, 10] | aggressive  |        1    |            15 |          1 |     0.36 |        0.28 |       0.36 |          0.19 |             0.18 |         638.93 |  -130.35 |        0.8  |             0 |                   15 |
| [5, 0, 10] | aggressive  |        1.5  |            24 |          1 |     0.33 |        0.3  |       0.33 |          0.17 |             0.15 |         486.65 |  -146    |        0.6  |             0 |                   11 |
| [5, 0, 10] | aggressive  |        2    |            30 |          1 |     0.28 |        0.26 |       0.28 |          0.15 |             0.13 |         254    |  -142.1  |        0.7  |             0 |                   11 |
| [5, 0, 10] | safe        |        1    |            15 |          3 |     0.36 |        0.28 |       0.62 |          0.52 |             0.23 |         667.07 |  -224.68 |        0.85 |             0 |                   17 |
| [5, 0, 10] | safe        |        0.5  |             6 |          3 |     0.5  |        0.07 |       0.84 |          0.63 |             0.02 |        -149.41 |  -264.73 |        0.7  |             0 |                   70 |
| [5, 0, 10] | safe        |        0.34 |             6 |          3 |     0.5  |        0.07 |       0.84 |          0.63 |             0.02 |        -149.41 |  -264.73 |        0.7  |             0 |                   70 |

### Per-leg walk-forward OOS monthly P&L (per micro, $)

| m       |   orb_close30 |   mr_gapfade |   ev_orb75 |
|:--------|--------------:|-------------:|-----------:|
| 2025-01 |            71 |          135 |        -30 |
| 2025-02 |            96 |         -105 |        487 |
| 2025-03 |           341 |         -325 |        216 |
| 2025-04 |            76 |          374 |        211 |
| 2025-05 |           409 |           89 |        144 |
| 2025-06 |           231 |          124 |        153 |
| 2025-07 |           -35 |           51 |        -33 |
| 2025-08 |           280 |          230 |          0 |
| 2025-09 |          -169 |           59 |        -77 |
| 2025-10 |           595 |            0 |       -362 |
| 2025-11 |          -481 |          -46 |         65 |
| 2025-12 |           -72 |          220 |       -140 |
| 2026-01 |           493 |         -110 |        220 |
| 2026-02 |             0 |          105 |        255 |
| 2026-03 |           573 |         -110 |       -223 |
| 2026-04 |           646 |           75 |        130 |
| 2026-05 |           395 |         -295 |        132 |
| 2026-06 |          1084 |            9 |       -328 |
| 2026-07 |          -926 |          361 |        -23 |
| 2026-08 |           142 |          310 |        102 |
| 2026-09 |           122 |          217 |        -59 |

## Configuration A: Aggressive (fast pass, first payout)

Weights per leg (micros): {'orb_close30': 5, 'mr_gapfade': 0, 'ev_orb75': 5}

| Item | Value |
|---|---|
| Evaluation size | 10 micros total (unit [1, 0, 1] x 5) |
| Funded size | 10 micros, cut to 2 when room to the MLL < $900, scaling cap respected |
| Attempts modelled | 1 |
| P(pass) per attempt | 46% |
| P(pass within 21 sessions) | 19% |
| P(pass within 42 sessions) | 40% |
| Median sessions to pass | 25.0 |
| P(lose the fee) per attempt | 54% |
| P(funded) within attempts | 46% (bootstrap 5-95%: 25% - 59%) |
| Median sessions to funded | 25.0 |
| P(first payout | funded) | 60% |
| P(first payout) overall | 28% (bootstrap: 7% - 46%) |
| Median sessions funded -> first payout | 12.0 |
| Mean paid | funded (90% split) | $1,694 |
| Mean fees per campaign | $146 |
| Expected net per campaign | $641 (bootstrap 5/50/95%: $-27 / $397 / $2,313; P(net>0) 90%) |
| Zero-edge control (same stream demeaned) | expected net $-18, pass rate 25% |
| Minimum monthly P(funded) | 0% |

Monthly view (start month of the evaluation):

| Start month | starts | P(pass within 21 sessions) | P(funded within attempts) |
|---|---|---|---|
| 2025-01 | 22 | 23% | 100% |
| 2025-02 | 20 | 5% | 100% |
| 2025-03 | 21 | 86% | 90% |
| 2025-04 | 21 | 5% | 5% |
| 2025-05 | 22 | 41% | 100% |
| 2025-06 | 21 | 0% | 48% |
| 2025-07 | 23 | 0% | 0% |
| 2025-08 | 21 | 0% | 0% |
| 2025-09 | 22 | 0% | 0% |
| 2025-10 | 23 | 0% | 0% |
| 2025-11 | 20 | 0% | 0% |
| 2025-12 | 22 | 14% | 91% |
| 2026-01 | 21 | 43% | 100% |
| 2026-02 | 20 | 0% | 100% |
| 2026-03 | 22 | 82% | 100% |
| 2026-04 | 21 | 43% | 43% |
| 2026-05 | 21 | 33% | 33% |
| 2026-06 | 22 | 5% | 5% |
| 2026-07 | 23 | 0% | 39% |
| 2026-08 | 21 | 0% | 0% |
| 2026-09 | 8 | 0% | 0% |

## Configuration B: Safe (one evaluation reaches funded)

Weights per leg (micros): {'orb_close30': 5, 'mr_gapfade': 0, 'ev_orb75': 10}

| Item | Value |
|---|---|
| Evaluation size | 6 micros total (unit [1, 0, 2] x 2) |
| Funded size | 6 micros, cut to 3 when room to the MLL < $900, scaling cap respected |
| Attempts modelled | 3 |
| P(pass) per attempt | 50% |
| P(pass within 21 sessions) | 7% |
| P(pass within 42 sessions) | 21% |
| Median sessions to pass | 48.0 |
| P(lose the fee) per attempt | 50% |
| P(funded) within attempts | 84% (bootstrap 5-95%: 63% - 100%) |
| Median sessions to funded | 70.0 |
| P(first payout | funded) | 3% |
| P(first payout) overall | 2% (bootstrap: 0% - 91%) |
| Median sessions funded -> first payout | 236.0 |
| Mean paid | funded (90% split) | $52 |
| Mean fees per campaign | $193 |
| Expected net per campaign | $-149 (bootstrap 5/50/95%: $-265 / $281 / $6,790; P(net>0) 70%) |
| Zero-edge control (same stream demeaned) | expected net $-146, pass rate 30% |
| Minimum monthly P(funded) | 0% |

Monthly view (start month of the evaluation):

| Start month | starts | P(pass within 21 sessions) | P(funded within attempts) |
|---|---|---|---|
| 2025-01 | 22 | 0% | 100% |
| 2025-02 | 20 | 0% | 100% |
| 2025-03 | 21 | 43% | 100% |
| 2025-04 | 21 | 0% | 81% |
| 2025-05 | 22 | 0% | 32% |
| 2025-06 | 21 | 0% | 100% |
| 2025-07 | 23 | 0% | 100% |
| 2025-08 | 21 | 0% | 100% |
| 2025-09 | 22 | 0% | 100% |
| 2025-10 | 23 | 0% | 91% |
| 2025-11 | 20 | 0% | 100% |
| 2025-12 | 22 | 0% | 100% |
| 2026-01 | 21 | 0% | 100% |
| 2026-02 | 20 | 0% | 100% |
| 2026-03 | 22 | 45% | 100% |
| 2026-04 | 21 | 24% | 29% |
| 2026-05 | 21 | 10% | 14% |
| 2026-06 | 22 | 0% | 0% |
| 2026-07 | 2 | 0% | n/a |

## Strategy rules

### orb_close30 (MNQ)

Parameters: `{"or_minutes": 15, "direction": "trend", "trend_len": 200, "trend_fast": 50, "or_dir_filter": false, "last_entry": "10:30", "stop_mode": "opposite", "max_stop_atr": 0.6, "tgt_frac": 0.75, "min_range_atr": 0.1, "max_range_atr": 0.5, "flat": "15:55", "max_trades": 1, "bar": 5, "min_on_range_atr": 0.0, "be_act_frac": 0.0, "trail_frac": 0.0, "max_hold_min": 0, "reentry": false}`

Module: `strategies/orb_close30.py`. Details and attempt log: `results/orb_close30/README.md`; verification: `results/orb_close30/verify.md` (if present).

### mr_gapfade (MNQ)

Parameters: `{"gap_max": 0.35, "entry_delay": 1}`

Module: `strategies/mr_gapfade.py`. Details and attempt log: `results/mr_gapfade/README.md`; verification: `results/mr_gapfade/verify.md` (if present).

### ev_orb75 (MES)

Parameters: `{"or_start": "09:30", "or_minutes": 25, "hold_min": 75, "trend_filter": "none", "stop_mode": "none", "stop_atr": 0.5, "last_entry": "11:30", "max_trades": 1, "skip_vvg": false, "flat": "15:55", "dls_mult": 1.0, "dps_mult": 2.0, "delay": 0}`

Module: `strategies/ev_orb75.py`. Details and attempt log: `results/ev_orb75/README.md`; verification: `results/ev_orb75/verify.md` (if present).

## Caveats that matter

- Proxy data: index CFD prices, not the futures contract; intraday returns correlate 0.87-0.89 hourly with ES/NQ/GC, but fills, spreads and overnight sessions differ. Early-close (holiday) sessions are skipped.
- Rule interpretations encoded conservatively but unconfirmed with Lucid directly: payout base (50% of total profit vs cycle profit), MLL lock at $50,100 on payout request, one-time evaluation fee. See `research/lucid_rules.md`.
- Selection effects: many strategies and parameters were examined; walk-forward and bootstrap bands reduce but do not remove the optimism. Treat lower bounds as the planning numbers.
- 2025-2026 included an unusual volatility regime (April 2025 tariff crash, record gold run). Monthly tables show where the strategies did not work.
