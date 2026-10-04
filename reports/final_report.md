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
| cal_window     | MNQ        |            1.93 |             1.21 |            80 |    5889.59 |      1.49 |          1.1  |              0.48 |       1.11 |           5 |    131.99 |      -146    |     -146    |             0 |
| orb_onmid      | MGC        |            1.42 |             0.74 |           206 |    3937.26 |      1.27 |          1.07 |              0.52 |       1.12 |           5 |    -91.26 |      -146    |     -137.78 |             0 |
| mr_gapfade     | MNQ        |            1.61 |             1.17 |            65 |    1367.3  |      1.51 |          1.07 |              0.67 |       1.14 |           5 |   -146    |      -146    |     -146    |             0 |
| orb_dbl        | MNQ        |            1.67 |             1.13 |            75 |    2282.45 |      1.46 |          1.02 |              0.62 |       1.18 |           5 |    158.97 |      -146    |     -146    |             0 |
| orb_sma_rr     | MNQ        |            1.15 |             1.15 |           304 |    4684.06 |      1.17 |          0.96 |              0.71 |       1.13 |          10 |    -88.52 |      -134.52 |     -133.84 |             0 |
| orb_reclaim    | MNQ        |            1.33 |             1.18 |           309 |    2669.14 |      1.17 |          0.84 |              0.62 |       1.19 |           5 |     28.6  |      -146    |     -146    |             0 |
| vb_orbp        | MNQ        |            1.15 |             1.17 |           270 |    4100.43 |      1.16 |          0.81 |              0.57 |       1.27 |           5 |    192.78 |       -80.89 |      -15.39 |             0 |
| cal_lunch      | MNQ        |            1.31 |             1.05 |           401 |    4379.15 |      1.19 |          0.76 |              0.67 |       1.07 |           5 |   -118.06 |      -146    |     -146    |             0 |
| mr_onrev       | MNQ        |            1.06 |             0.92 |           166 |    5918.88 |      1.2  |          0.69 |              0.62 |       1.11 |           5 |    -96.12 |      -146    |     -146    |             0 |
| mr_pdrange     | MNQ        |            1.39 |             1.56 |            12 |     140.8  |      1.31 |          0.58 |              0.14 |       1.24 |           5 |    nan    |      -146    |     -146    |             0 |
| tm_trendday    | MES        |            0.98 |             1.01 |           186 |    1230.06 |      1.15 |          0.57 |              0.62 |       1.2  |           5 |   -146    |      -146    |     -146    |             0 |
| tm_gold_donch  | MGC        |            0.96 |             0.96 |           171 |    2042.76 |      1.15 |          0.53 |              0.43 |       0.98 |           5 |    369.87 |      -146    |       15.85 |             0 |
| ev_orb75       | MES        |            1.14 |             1.14 |           221 |     839.73 |      1.12 |          0.44 |              0.57 |       1.12 |           5 |   -146    |      -146    |     -146    |             0 |
| orb_crabel     | MNQ        |            1.25 |             1.39 |           225 |     776.77 |      1.03 |          0.15 |              0.48 |       1.21 |           5 |     30.58 |      -146    |       18.74 |             0 |
| mr_volband     | MGC        |            1.43 |             0.78 |           106 |     162.21 |      1.03 |          0.09 |              0.38 |       0.92 |           5 |   -126.29 |      -146    |     -141.07 |             0 |
| cal_gold_clock | MGC        |            1.11 |             0.83 |           289 |     -76.05 |      1    |         -0.02 |              0.43 |       0.96 |           5 |     78.32 |      -146    |       94.73 |             0 |
| orb_ib_c       | MES        |            1.25 |             1.11 |           203 |    -233.21 |      0.97 |         -0.12 |              0.52 |       0.95 |           5 |   -146    |      -146    |     -146    |             0 |
| cal_macro_pm   | MNQ        |            1.16 |             1.19 |           234 |    -497.79 |      0.95 |         -0.22 |              0.52 |       0.93 |           5 |   -146    |      -146    |     -146    |             0 |
| bot_noise_band | MNQ        |            0.96 |             1.08 |           578 |   -1396.55 |      0.92 |         -0.3  |              0.33 |       1.04 |           5 |    nan    |      -146    |      nan    |             0 |
| tm_hg_pull     | MNQ        |            1.12 |             0.73 |           167 |   -1036.35 |      0.91 |         -0.34 |              0.43 |       0.89 |           5 |    -62.83 |      -146    |      -42.67 |             0 |
| mr_ibfail      | MNQ        |            1.04 |             0.79 |           152 |   -1196.36 |      0.87 |         -0.5  |              0.43 |       0.81 |           5 |   -146    |      -146    |     -146    |             0 |
| tm_gapgo       | MNQ        |            0.81 |             1.41 |            68 |   -1322.31 |      0.81 |         -0.56 |              0.38 |       0.9  |           5 |   -146    |      -146    |     -146    |             0 |
| bot_rsi_dip    | MNQ        |            0.91 |             0.72 |           776 |   -4061.93 |      0.81 |         -1.47 |              0.29 |       0.78 |           5 |    109.38 |      -146    |     1122.65 |             0 |

Columns: fixed_* = in-sample profit factor with the final parameters (MAIN 2025-26, PRIOR 2023-24); wf25_* = walk-forward OOS 2025-26; wfall_pf = walk-forward OOS 2022-26; lb_micros/exp_net/lb_exp_net = size chosen by bootstrap lower bound, point and 5th-percentile expected net per evaluation; zero_edge = control; recommended = lower bound > 0 and beats control.

## Portfolio legs

Legs: orb_close30, mr_gapfade, orb_dbl, vb_orbp, orb_sma_rr, orb_reclaim

Daily P&L correlation (walk-forward OOS 2025):

|             |   orb_close30 |   mr_gapfade |   orb_dbl |   vb_orbp |   orb_sma_rr |   orb_reclaim |
|:------------|--------------:|-------------:|----------:|----------:|-------------:|--------------:|
| orb_close30 |          1    |         0    |     -0.09 |      0.09 |         0.53 |          0.1  |
| mr_gapfade  |          0    |         1    |      0.02 |     -0.05 |        -0.06 |         -0.12 |
| orb_dbl     |         -0.09 |         0.02 |      1    |     -0.02 |        -0.1  |         -0.05 |
| vb_orbp     |          0.09 |        -0.05 |     -0.02 |      1    |         0.2  |          0.19 |
| orb_sma_rr  |          0.53 |        -0.06 |     -0.1  |      0.2  |         1    |          0.2  |
| orb_reclaim |          0.1  |        -0.12 |     -0.05 |      0.19 |         0.2  |          1    |

### Sizing candidates examined

| w                     | objective   |   size_mult |   eval_micros |   attempts |   p_pass |   p_pass_21 |   p_funded |   p_funded_lb |   p_first_payout |   expected_net |   net_lb |   p_net_pos |   min_monthly |   median_days_funded |
|:----------------------|:------------|------------:|--------------:|-----------:|---------:|------------:|-----------:|--------------:|-----------------:|---------------:|---------:|------------:|--------------:|---------------------:|
| [5, 5, 5, 0, 0, 0]    | aggressive  |        1    |            15 |          1 |     0.6  |        0.32 |       0.6  |          0.34 |             0.36 |        1903.42 |   -22.13 |        0.94 |          0    |                 20   |
| [5, 5, 5, 0, 0, 0]    | aggressive  |        1.5  |            24 |          1 |     0.32 |        0.31 |       0.32 |          0.21 |             0.17 |         822.34 |   -57.21 |        0.92 |          0    |                  8   |
| [5, 5, 5, 0, 0, 0]    | aggressive  |        2    |            30 |          1 |     0.31 |        0.3  |       0.31 |          0.21 |             0.19 |        1056.72 |   -22.36 |        0.93 |          0    |                  7   |
| [5, 5, 5, 0, 0, 0]    | safe        |        1    |            15 |          3 |     0.6  |        0.32 |       0.85 |          0.58 |             0.51 |        2438.9  |    61.52 |        0.95 |          0.1  |                 23   |
| [5, 5, 5, 0, 0, 0]    | safe        |        0.5  |             6 |          3 |     0.65 |        0.02 |       0.89 |          0.66 |             0.27 |         752.04 |  -103.14 |        0.94 |          0.1  |                 69   |
| [5, 5, 5, 0, 0, 0]    | safe        |        0.34 |             6 |          3 |     0.65 |        0.02 |       0.89 |          0.66 |             0.27 |         752.04 |  -103.14 |        0.94 |          0.1  |                 69   |
| [5, 0, 5, 0, 0, 0]    | aggressive  |        1    |            10 |          1 |     0.6  |        0.3  |       0.6  |          0.31 |             0.35 |        1612.43 |   -79.94 |        0.9  |          0    |                 22   |
| [5, 0, 5, 0, 0, 0]    | aggressive  |        1.5  |            16 |          1 |     0.38 |        0.32 |       0.38 |          0.21 |             0.19 |         926.69 |   -78.43 |        0.84 |          0    |                 11   |
| [5, 0, 5, 0, 0, 0]    | aggressive  |        2    |            20 |          1 |     0.38 |        0.33 |       0.38 |          0.21 |             0.2  |        1057.53 |   -73.24 |        0.88 |          0    |                 10   |
| [5, 0, 5, 0, 0, 0]    | safe        |        1    |            10 |          3 |     0.6  |        0.3  |       0.88 |          0.63 |             0.48 |        2456.21 |   -68    |        0.92 |          0    |                 23   |
| [5, 0, 5, 0, 0, 0]    | safe        |        0.5  |             4 |          3 |     0.53 |        0.01 |       0.89 |          0.51 |             0.27 |         536.78 |  -212.59 |        0.8  |          0.38 |                 62   |
| [5, 0, 5, 0, 0, 0]    | safe        |        0.34 |             4 |          3 |     0.53 |        0.01 |       0.89 |          0.51 |             0.27 |         536.78 |  -212.59 |        0.8  |          0.38 |                 62   |
| [10, 0, 5, 0, 0, 0]   | aggressive  |        1    |            15 |          1 |     0.41 |        0.31 |       0.41 |          0.2  |             0.23 |        1201.63 |   -80.81 |        0.85 |          0    |                 12   |
| [10, 0, 5, 0, 0, 0]   | aggressive  |        1.5  |            24 |          1 |     0.32 |        0.28 |       0.32 |          0.17 |             0.08 |         414.16 |   -95.47 |        0.78 |          0    |                  8   |
| [10, 0, 5, 0, 0, 0]   | aggressive  |        2    |            30 |          1 |     0.3  |        0.25 |       0.3  |          0.16 |             0.07 |         366.56 |  -117.96 |        0.78 |          0    |                  8   |
| [10, 0, 5, 0, 0, 0]   | safe        |        1    |            15 |          3 |     0.41 |        0.31 |       0.74 |          0.53 |             0.32 |        1767.38 |   -86.26 |        0.92 |          0    |                 15.5 |
| [10, 0, 5, 0, 0, 0]   | safe        |        0.5  |             6 |          3 |     0.58 |        0.16 |       0.9  |          0.52 |             0.5  |        1367.72 |  -241.66 |        0.82 |          0    |                 49   |
| [10, 0, 5, 0, 0, 0]   | safe        |        0.34 |             6 |          3 |     0.58 |        0.16 |       0.9  |          0.52 |             0.5  |        1367.72 |  -241.66 |        0.82 |          0    |                 49   |
| [15, 10, 10, 0, 0, 0] | aggressive  |        1    |            35 |          1 |     0.27 |        0.27 |       0.27 |          0.18 |             0.21 |        1172.71 |   -64.94 |        0.91 |          0    |                  7   |
| [15, 10, 10, 0, 0, 0] | aggressive  |        1.5  |            35 |          1 |     0.27 |        0.27 |       0.27 |          0.18 |             0.21 |        1172.71 |   -64.94 |        0.91 |          0    |                  7   |
| [15, 10, 10, 0, 0, 0] | aggressive  |        2    |            35 |          1 |     0.27 |        0.27 |       0.27 |          0.18 |             0.21 |        1172.71 |   -64.94 |        0.91 |          0    |                  7   |
| [15, 10, 10, 0, 0, 0] | safe        |        1    |            35 |          3 |     0.27 |        0.27 |       0.62 |          0.43 |             0.41 |        2126.6  |   -25.48 |        0.94 |          0    |                 12   |
| [15, 10, 10, 0, 0, 0] | safe        |        0.5  |            14 |          3 |     0.59 |        0.33 |       0.86 |          0.55 |             0.51 |        2123.55 |     7.58 |        0.95 |          0.19 |                 25   |
| [15, 10, 10, 0, 0, 0] | safe        |        0.34 |            14 |          3 |     0.59 |        0.33 |       0.86 |          0.55 |             0.51 |        2123.55 |     7.58 |        0.95 |          0.19 |                 25   |
| [15, 10, 15, 0, 0, 0] | aggressive  |        1    |            40 |          1 |     0.28 |        0.28 |       0.28 |          0.18 |             0.2  |        1145.14 |   -37.35 |        0.92 |          0    |                  7   |
| [15, 10, 15, 0, 0, 0] | aggressive  |        1.5  |            40 |          1 |     0.28 |        0.28 |       0.28 |          0.18 |             0.2  |        1145.14 |   -37.35 |        0.92 |          0    |                  7   |
| [15, 10, 15, 0, 0, 0] | aggressive  |        2    |            40 |          1 |     0.28 |        0.28 |       0.28 |          0.18 |             0.2  |        1145.14 |   -37.35 |        0.92 |          0    |                  7   |
| [15, 10, 15, 0, 0, 0] | safe        |        1    |            40 |          3 |     0.28 |        0.28 |       0.64 |          0.48 |             0.44 |        2246.28 |    68.05 |        0.97 |          0    |                 10   |
| [15, 10, 15, 0, 0, 0] | safe        |        0.5  |            16 |          3 |     0.54 |        0.36 |       0.85 |          0.56 |             0.54 |        2336.08 |    34.77 |        0.96 |          0.19 |                 21   |
| [15, 10, 15, 0, 0, 0] | safe        |        0.34 |            16 |          3 |     0.54 |        0.36 |       0.85 |          0.56 |             0.54 |        2336.08 |    34.77 |        0.96 |          0.19 |                 21   |
| [10, 5, 15, 5, 0, 0]  | aggressive  |        1    |            35 |          1 |     0.34 |        0.34 |       0.34 |          0.22 |             0.18 |        1120.18 |    23.01 |        0.96 |          0    |                  6   |
| [10, 5, 15, 5, 0, 0]  | aggressive  |        1.5  |            35 |          1 |     0.34 |        0.34 |       0.34 |          0.22 |             0.18 |        1120.18 |    23.01 |        0.96 |          0    |                  6   |
| [10, 5, 15, 5, 0, 0]  | aggressive  |        2    |            35 |          1 |     0.34 |        0.34 |       0.34 |          0.22 |             0.18 |        1120.18 |    23.01 |        0.96 |          0    |                  6   |
| [10, 5, 15, 5, 0, 0]  | safe        |        1    |            35 |          3 |     0.34 |        0.34 |       0.73 |          0.56 |             0.33 |        1902.45 |   167.92 |        0.98 |          0    |                  8   |
| [10, 5, 15, 5, 0, 0]  | safe        |        0.5  |            14 |          3 |     0.63 |        0.45 |       0.83 |          0.64 |             0.3  |        1570.78 |   171.22 |        0.97 |          0.06 |                 17   |
| [10, 5, 15, 5, 0, 0]  | safe        |        0.34 |            14 |          3 |     0.63 |        0.45 |       0.83 |          0.64 |             0.3  |        1570.78 |   171.22 |        0.97 |          0.06 |                 17   |
| [15, 5, 15, 0, 0, 0]  | aggressive  |        1    |            35 |          1 |     0.28 |        0.27 |       0.28 |          0.18 |             0.2  |        1107.26 |   -25.5  |        0.92 |          0    |                  7   |
| [15, 5, 15, 0, 0, 0]  | aggressive  |        1.5  |            35 |          1 |     0.28 |        0.27 |       0.28 |          0.18 |             0.2  |        1107.26 |   -25.5  |        0.92 |          0    |                  7   |
| [15, 5, 15, 0, 0, 0]  | aggressive  |        2    |            35 |          1 |     0.28 |        0.27 |       0.28 |          0.18 |             0.2  |        1107.26 |   -25.5  |        0.92 |          0    |                  7   |
| [15, 5, 15, 0, 0, 0]  | safe        |        1    |            35 |          3 |     0.28 |        0.27 |       0.67 |          0.48 |             0.44 |        2387.18 |    60.99 |        0.96 |          0    |                 10   |
| [15, 5, 15, 0, 0, 0]  | safe        |        0.5  |            14 |          3 |     0.55 |        0.34 |       0.82 |          0.53 |             0.57 |        2617.44 |    22.23 |        0.96 |          0    |                 21   |
| [15, 5, 15, 0, 0, 0]  | safe        |        0.34 |            14 |          3 |     0.55 |        0.34 |       0.82 |          0.53 |             0.57 |        2617.44 |    22.23 |        0.96 |          0    |                 21   |
| [15, 0, 15, 5, 0, 0]  | aggressive  |        1    |            35 |          1 |     0.32 |        0.32 |       0.32 |          0.21 |             0.17 |        1075.19 |    -8.19 |        0.94 |          0    |                  6   |
| [15, 0, 15, 5, 0, 0]  | aggressive  |        1.5  |            35 |          1 |     0.32 |        0.32 |       0.32 |          0.21 |             0.17 |        1075.19 |    -8.19 |        0.94 |          0    |                  6   |
| [15, 0, 15, 5, 0, 0]  | aggressive  |        2    |            35 |          1 |     0.32 |        0.32 |       0.32 |          0.21 |             0.17 |        1075.19 |    -8.19 |        0.94 |          0    |                  6   |
| [15, 0, 15, 5, 0, 0]  | safe        |        1    |            35 |          3 |     0.32 |        0.32 |       0.68 |          0.52 |             0.32 |        1801.49 |   139.88 |        0.97 |          0    |                  8   |
| [15, 0, 15, 5, 0, 0]  | safe        |        0.5  |            14 |          3 |     0.52 |        0.44 |       0.77 |          0.6  |             0.33 |        1889    |   141.62 |        0.98 |          0.05 |                 15   |
| [15, 0, 15, 5, 0, 0]  | safe        |        0.34 |            14 |          3 |     0.52 |        0.44 |       0.77 |          0.6  |             0.33 |        1889    |   141.62 |        0.98 |          0.05 |                 15   |
| [10, 0, 10, 0, 0, 0]  | aggressive  |        1    |            20 |          1 |     0.38 |        0.33 |       0.38 |          0.21 |             0.2  |        1057.53 |   -73.24 |        0.88 |          0    |                 10   |
| [10, 0, 10, 0, 0, 0]  | aggressive  |        1.5  |            30 |          1 |     0.28 |        0.28 |       0.28 |          0.18 |             0.14 |         777.03 |   -64.94 |        0.87 |          0    |                  7   |
| [10, 0, 10, 0, 0, 0]  | aggressive  |        2    |            40 |          1 |     0.25 |        0.25 |       0.25 |          0.16 |             0.13 |         705.57 |   -78.2  |        0.86 |          0    |                  7   |
| [10, 0, 10, 0, 0, 0]  | safe        |        1    |            20 |          3 |     0.38 |        0.33 |       0.76 |          0.49 |             0.32 |        1831.77 |   -35.12 |        0.93 |          0.13 |                 15   |
| [10, 0, 10, 0, 0, 0]  | safe        |        0.5  |            10 |          3 |     0.6  |        0.3  |       0.88 |          0.63 |             0.48 |        2456.21 |   -68    |        0.92 |          0    |                 23   |
| [10, 0, 10, 0, 0, 0]  | safe        |        0.34 |             6 |          3 |     0.63 |        0.14 |       0.91 |          0.58 |             0.51 |        1499.98 |  -224.48 |        0.84 |          0.29 |                 50.5 |
| [10, 10, 10, 0, 0, 0] | aggressive  |        1    |            30 |          1 |     0.31 |        0.3  |       0.31 |          0.21 |             0.19 |        1056.72 |   -22.36 |        0.93 |          0    |                  7   |
| [10, 10, 10, 0, 0, 0] | aggressive  |        1.5  |            39 |          1 |     0.27 |        0.26 |       0.27 |          0.18 |             0.16 |         839.25 |   -54.13 |        0.92 |          0    |                  7   |
| [10, 10, 10, 0, 0, 0] | aggressive  |        2    |            39 |          1 |     0.27 |        0.26 |       0.27 |          0.18 |             0.16 |         839.25 |   -54.13 |        0.92 |          0    |                  7   |
| [10, 10, 10, 0, 0, 0] | safe        |        1    |            30 |          3 |     0.31 |        0.3  |       0.78 |          0.58 |             0.43 |        1928.1  |   174.69 |        0.96 |          0.13 |                 13   |
| [10, 10, 10, 0, 0, 0] | safe        |        0.5  |            15 |          3 |     0.6  |        0.32 |       0.85 |          0.58 |             0.51 |        2438.9  |    61.52 |        0.95 |          0.1  |                 23   |
| [10, 10, 10, 0, 0, 0] | safe        |        0.34 |             9 |          3 |     0.76 |        0.14 |       0.93 |          0.68 |             0.64 |        2413.21 |   -59.18 |        0.92 |          0.29 |                 46   |

### Per-leg walk-forward OOS monthly P&L (per micro, $)

| m       |   orb_close30 |   mr_gapfade |   orb_dbl |   vb_orbp |   orb_sma_rr |   orb_reclaim |
|:--------|--------------:|-------------:|----------:|----------:|-------------:|--------------:|
| 2025-01 |            71 |          135 |        55 |       385 |         -122 |          -466 |
| 2025-02 |            96 |         -105 |       398 |      1038 |          -54 |            62 |
| 2025-03 |           341 |         -325 |        68 |      -641 |          877 |           288 |
| 2025-04 |            76 |          374 |       817 |      -621 |         -837 |           404 |
| 2025-05 |           409 |           89 |       457 |      -594 |          268 |           481 |
| 2025-06 |           231 |          124 |      -139 |     -2472 |          225 |          -363 |
| 2025-07 |           -35 |           51 |      -287 |       835 |          125 |            11 |
| 2025-08 |           280 |          230 |       -56 |      1194 |          619 |           223 |
| 2025-09 |          -169 |           59 |       271 |       -73 |          409 |           145 |
| 2025-10 |           595 |            0 |       284 |       138 |          124 |           157 |
| 2025-11 |          -481 |          -46 |        47 |      -200 |          348 |          1042 |
| 2025-12 |           -72 |          220 |       -56 |      -226 |         -737 |          -511 |
| 2026-01 |           493 |         -110 |       141 |      1149 |          678 |           649 |
| 2026-02 |             0 |          105 |         0 |      1262 |          686 |          1158 |
| 2026-03 |           573 |         -110 |       476 |      -258 |         1030 |          -988 |
| 2026-04 |           646 |           75 |       146 |      1119 |          802 |           779 |
| 2026-05 |           395 |         -295 |      -923 |       406 |         1274 |          1068 |
| 2026-06 |          1084 |            9 |       570 |      1043 |          854 |          -491 |
| 2026-07 |          -926 |          361 |       301 |       178 |        -1107 |          -360 |
| 2026-08 |           142 |          310 |      -217 |       676 |         -812 |          -414 |
| 2026-09 |           122 |          217 |       -70 |      -237 |           36 |          -205 |

## Configuration A: Aggressive (fast pass, first payout)

Weights per leg (micros): {'orb_close30': 10, 'mr_gapfade': 5, 'orb_dbl': 15, 'vb_orbp': 5, 'orb_sma_rr': 0, 'orb_reclaim': 0}

| Item | Value |
|---|---|
| Evaluation size | 35 micros total (unit [2, 1, 3, 1, 0, 0] x 5) |
| Funded size | 14 micros, cut to 7 when room to the MLL < $900, scaling cap respected |
| Attempts modelled | 1 |
| P(pass) per attempt | 34% |
| P(pass within 21 sessions) | 34% |
| P(pass within 42 sessions) | 34% |
| Median sessions to pass | 6.0 |
| P(lose the fee) per attempt | 66% |
| P(funded) within attempts | 34% (bootstrap 5-95%: 22% - 41%) |
| Median sessions to funded | 6.0 |
| P(first payout | funded) | 55% |
| P(first payout) overall | 18% (bootstrap: 5% - 25%) |
| Median sessions funded -> first payout | 23.0 |
| Mean paid | funded (90% split) | $3,765 |
| Mean fees per campaign | $146 |
| Expected net per campaign | $1,120 (bootstrap 5/50/95%: $23 / $494 / $1,339; P(net>0) 96%) |
| Zero-edge control (same stream demeaned) | expected net $-86, pass rate 12% |
| Minimum monthly P(funded) | 0% |

Monthly view (start month of the evaluation):

| Start month | starts | P(pass within 21 sessions) | P(funded within attempts) |
|---|---|---|---|
| 2025-01 | 22 | 77% | 77% |
| 2025-02 | 20 | 35% | 35% |
| 2025-03 | 21 | 29% | 29% |
| 2025-04 | 21 | 5% | 5% |
| 2025-05 | 22 | 59% | 59% |
| 2025-06 | 21 | 0% | 0% |
| 2025-07 | 23 | 17% | 17% |
| 2025-08 | 21 | 71% | 71% |
| 2025-09 | 22 | 36% | 36% |
| 2025-10 | 23 | 13% | 13% |
| 2025-11 | 20 | 0% | 0% |
| 2025-12 | 22 | 64% | 64% |
| 2026-01 | 21 | 67% | 67% |
| 2026-02 | 20 | 60% | 60% |
| 2026-03 | 22 | 27% | 27% |
| 2026-04 | 21 | 29% | 29% |
| 2026-05 | 21 | 10% | 10% |
| 2026-06 | 22 | 18% | 18% |
| 2026-07 | 23 | 26% | 26% |
| 2026-08 | 21 | 19% | 19% |
| 2026-09 | 17 | 47% | 47% |

## Configuration B: Safe (one evaluation reaches funded)

Weights per leg (micros): {'orb_close30': 15, 'mr_gapfade': 10, 'orb_dbl': 10, 'vb_orbp': 0, 'orb_sma_rr': 0, 'orb_reclaim': 0}

| Item | Value |
|---|---|
| Evaluation size | 14 micros total (unit [3, 2, 2, 0, 0, 0] x 2) |
| Funded size | 14 micros, cut to 7 when room to the MLL < $900, scaling cap respected |
| Attempts modelled | 3 |
| P(pass) per attempt | 59% |
| P(pass within 21 sessions) | 33% |
| P(pass within 42 sessions) | 56% |
| Median sessions to pass | 19.0 |
| P(lose the fee) per attempt | 41% |
| P(funded) within attempts | 86% (bootstrap 5-95%: 55% - 95%) |
| Median sessions to funded | 25.0 |
| P(first payout | funded) | 59% |
| P(first payout) overall | 51% (bootstrap: 10% - 56%) |
| Median sessions funded -> first payout | 27.5 |
| Mean paid | funded (90% split) | $2,695 |
| Mean fees per campaign | $201 |
| Expected net per campaign | $2,124 (bootstrap 5/50/95%: $8 / $1,318 / $3,549; P(net>0) 95%) |
| Zero-edge control (same stream demeaned) | expected net $-113, pass rate 22% |
| Minimum monthly P(funded) | 19% |

Monthly view (start month of the evaluation):

| Start month | starts | P(pass within 21 sessions) | P(funded within attempts) |
|---|---|---|---|
| 2025-01 | 22 | 0% | 100% |
| 2025-02 | 20 | 0% | 100% |
| 2025-03 | 21 | 76% | 100% |
| 2025-04 | 21 | 48% | 100% |
| 2025-05 | 22 | 77% | 77% |
| 2025-06 | 21 | 0% | 81% |
| 2025-07 | 23 | 4% | 100% |
| 2025-08 | 21 | 19% | 100% |
| 2025-09 | 22 | 32% | 100% |
| 2025-10 | 23 | 48% | 48% |
| 2025-11 | 20 | 0% | 70% |
| 2025-12 | 22 | 73% | 100% |
| 2026-01 | 21 | 14% | 100% |
| 2026-02 | 20 | 5% | 100% |
| 2026-03 | 22 | 100% | 100% |
| 2026-04 | 21 | 86% | 100% |
| 2026-05 | 21 | 19% | 19% |
| 2026-06 | 22 | 18% | 45% |
| 2026-07 | 23 | 0% | 91% |
| 2026-08 | 21 | 14% | 100% |
| 2026-09 | 10 | 60% | 100% |

## Strategy rules

### orb_close30 (MNQ)

Parameters: `{"or_minutes": 15, "direction": "trend", "trend_len": 200, "trend_fast": 50, "or_dir_filter": false, "last_entry": "10:30", "stop_mode": "opposite", "max_stop_atr": 0.6, "tgt_frac": 0.75, "min_range_atr": 0.1, "max_range_atr": 0.5, "flat": "15:55", "max_trades": 1, "bar": 5, "min_on_range_atr": 0.0, "be_act_frac": 0.0, "trail_frac": 0.0, "max_hold_min": 0, "reentry": false}`

Module: `strategies/orb_close30.py`. Details and attempt log: `results/orb_close30/README.md`; verification: `results/orb_close30/verify.md` (if present).

### mr_gapfade (MNQ)

Parameters: `{"gap_max": 0.35, "entry_delay": 1}`

Module: `strategies/mr_gapfade.py`. Details and attempt log: `results/mr_gapfade/README.md`; verification: `results/mr_gapfade/verify.md` (if present).

### orb_dbl (MNQ)

Parameters: `{"or_minutes": 30, "require_fail": true, "stop_mode": "mid", "max_stop_atr": 0.6, "tgt_frac": 0.5, "skip_ext": 0.5, "last_entry": "13:30", "min_range_atr": 0.1, "max_range_atr": 0.8, "flat": "15:55", "max_trades": 1, "bar": 5}`

Module: `strategies/orb_dbl.py`. Details and attempt log: `results/orb_dbl/README.md`; verification: `results/orb_dbl/verify.md` (if present).

### vb_orbp (MNQ)

Parameters: `{"unit": "range", "k": 0.25, "sides": "both", "bias": "none", "stop_mode": "frac", "stop_frac": 0.5, "tgt_mode": "frac", "tgt_frac": 0.5, "tgt_cap_atr": 0.0, "max_stop_atr": 0.6, "min_stop_pts": {"MES": 4.0, "MNQ": 6.0, "MGC": 2.0}, "min_unit_atr": 0.05, "max_unit_atr": 1.0, "ws_skip": 0.0, "gap_skip_atr": 0.0, "entry_cutoff": {"MES": "15:55", "MNQ": "15:55", "MGC": "13:25"}, "cancel_on_opposite": true, "buffer_ticks": 1, "flat": {"MES": "15:55", "MNQ": "15:55", "MGC": "13:25"}, "max_trades": 1}`

Module: `strategies/vb_orbp.py`. Details and attempt log: `results/vb_orbp/README.md`; verification: `results/vb_orbp/verify.md` (if present).

### orb_sma_rr (MNQ)

Parameters: `{"or_minutes": 15, "sma_len": 200, "rr": 2.0, "stop_cap_pts": 1000000000.0, "max_stop_atr": 0.15, "buffer_ticks": 1, "last_entry": "12:00", "min_range_atr": 0.1, "max_trades": 1, "flat": "15:55", "reentry": false}`

Module: `strategies/orb_sma_rr.py`. Details and attempt log: `results/orb_sma_rr/README.md`; verification: `results/orb_sma_rr/verify.md` (if present).

### orb_reclaim (MNQ)

Parameters: `{"windows": "am_only", "use_pd_levels": false, "max_stop_pts": 60, "rr": 3.5, "valid_minutes": 60, "max_trades": 4, "flat": "15:55", "use_london": true}`

Module: `strategies/orb_reclaim.py`. Details and attempt log: `results/orb_reclaim/README.md`; verification: `results/orb_reclaim/verify.md` (if present).

## Caveats that matter

- Proxy data: index CFD prices, not the futures contract; intraday returns correlate 0.87-0.89 hourly with ES/NQ/GC, but fills, spreads and overnight sessions differ. Early-close (holiday) sessions are skipped.
- Rule interpretations encoded conservatively but unconfirmed with Lucid directly: payout base (50% of total profit vs cycle profit), MLL lock at $50,100 on payout request, one-time evaluation fee. See `research/lucid_rules.md`.
- Selection effects: many strategies and parameters were examined; walk-forward and bootstrap bands reduce but do not remove the optimism. Treat lower bounds as the planning numbers.
- 2025-2026 included an unusual volatility regime (April 2025 tariff crash, record gold run). Monthly tables show where the strategies did not work.
