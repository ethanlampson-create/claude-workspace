# Graded setups (A+ .. F) for the Sentinel legs: does taking only B-and-better setups help the Lucid accounts?

Scope: the three legs the two final configurations trade (orb_close30, mr_gapfade, orb_dbl on MNQ), 1-minute Nasdaq proxy Nov 2010 - Sep 2026, same engine, costs and Lucid simulator as `reports/final_report.md`. Nothing here is wired into any live/bot code.

## Verdict

**Taking only B-and-better setups makes both accounts worse, not better.** On the 2025-01..2026-09 stream the honest (walk-forward) grader keeps 116 of 283 setups. Aggressive: P(first payout) 39% -> 9%, expected net per campaign $2,128 -> $18. Safe: P(first payout) 65% -> 0%, expected net $2,442 -> $-190. A grader fitted on shuffled outcomes (no information) produces almost the same damage (Aggressive P(first payout) 9%, Safe 0%), so the loss comes from trading less, not from picking worse. The grader fitted on the answers (in-sample) shows Aggressive P(first payout) 68% and expected net $3,909: that is the number a non-walk-forward backtest would have reported, and it is not achievable.

Why: the Lucid rules pay for frequency given a positive expectancy per trade. A payout needs 5 qualifying days (>= $150) and >= $4,000 of profit while the account sits within $2,000 of an end-of-day trailing floor; halving the trade count halves the speed at which cushion builds but leaves every remaining trade's loss the same size, so funded accounts are blown before their first payout far more often (36% -> 75% for Aggressive). The confluences themselves (time of day, FVG/CISD proxies, sweeps, trend, VIX, ATR regime, the strategy's own memory) carry a rank correlation of about 0.1 with the outcome out of sample, which is far too little to pay for the lost frequency.

## Method

1. **Setup log.** Every signal the strategies would take is logged with what a trader could see at that moment (bars strictly before the entry bar): time of day, weekday, month; opening-range size/direction/position; gap, overnight range and direction; prior-day range, direction, position in the prior-day range, distance to prior-day high/low/close and overnight high/low; liquidity sweeps of PDH/PDL (with and against the trade); 5-, 15-, 30-minute momentum, realised volatility; fair-value-gap counts and whether the entry sits in a same-/opposite-direction FVG; a change-in-state-of-delivery (CISD) proxy and displacement of the last 5-minute candle; daily trend vs SMA20/50/200; 3- and 10-day returns; ATR regime (ATR vs its 60-day mean), VIX and its 100-day percentile; planned risk and target in ATR and the planned R:R; and the strategy's own memory (mean R and win rate of its last 20/50 setups, loss streak, expanding win rate in the same half-hour, weekday and side). 69 features in total. Outcome = realised R multiple (P&L / planned risk), winsorised to [-3, 3]. No volume exists in the data, so volume confluences are not available.

2. **Grader.** A model predicts the expected R of a setup from those features. Grades are bands of the prediction with thresholds fixed at fit time from the training setups: A+ = top 10%, A = next 15%, B = next 25%, C = next 25%, D = next 15%, F = bottom 10%. "B and up" = the better half of the setups the grader had seen when it was fitted.

3. **Walk-forward.** The grader used for year Y was fitted on setups before Y-01-01 only, refitted every January (first fit 2014). Model choice (type, target, feature set, recency weighting, pooled vs per-strategy) was made on 2014-2024 results only; 2025-26 was scored once with the chosen grader.

4. **Account re-run.** For each variant the engine is re-run with the rejected signals removed (exact intraday equity), the three legs are combined one micro each, and the two configurations are simulated as in the final report: Aggressive = 15 micros (5 units), one attempt; Safe = 9 micros (3 units), up to three attempts; funded book cut to 1 unit when the room to the MLL is under $900.

5. **Controls.** An *in-sample* grader (fitted on 2010-2026 including the test years) shows what a grader that has seen the answers reports; a *shuffled-label* grader (same model, outcomes permuted) shows what a grader with no information reports. Both filters are run through the same account simulation.

## 1. Does the grader know anything? (walk-forward, 2014-2024, fixed-parameter stream)

Rank correlation between predicted and realised R, share kept at "B and up", mean R kept vs dropped, profit factor of all vs kept setups.

| model              |    n |   spearman |   kept_share |   R_all |   R_kept |   R_dropped |   wr_all |   wr_kept |   pf_all |   pf_kept |   net_all |   net_kept |   net_dropped |
|:-------------------|-----:|-----------:|-------------:|--------:|---------:|------------:|---------:|----------:|---------:|----------:|----------:|-----------:|--------------:|
| gbm                | 2059 |      0.067 |        0.531 |  -0.038 |   -0.029 |      -0.048 |    0.558 |     0.566 |    1.047 |     1.065 |  2534.36  |   1907.2   |       627.159 |
| gbm/mr_gapfade     |  743 |      0.101 |        0.482 |  -0.05  |   -0.035 |      -0.065 |    0.509 |     0.522 |    1.038 |     1.033 |   473.604 |    221.618 |       251.986 |
| gbm/orb_close30    |  862 |      0.057 |        0.536 |  -0.03  |    0     |      -0.065 |    0.6   |     0.623 |    1.038 |     1.147 |  1106.28  |   2044.95  |      -938.665 |
| gbm/orb_dbl        |  454 |      0.013 |        0.601 |  -0.031 |   -0.071 |       0.028 |    0.557 |     0.527 |    1.076 |     0.958 |   954.473 |   -359.365 |      1313.84  |
| bucket             | 2059 |      0.063 |        0.506 |  -0.038 |   -0.05  |      -0.025 |    0.558 |     0.551 |    1.047 |     1.024 |  2534.36  |    727.981 |      1806.38  |
| bucket/mr_gapfade  |  743 |      0.002 |        0.486 |  -0.05  |   -0.055 |      -0.046 |    0.509 |     0.515 |    1.038 |     1.103 |   473.604 |    526.242 |       -52.638 |
| bucket/orb_close30 |  862 |      0.111 |        0.481 |  -0.03  |   -0.046 |      -0.015 |    0.6   |     0.588 |    1.038 |     0.994 |  1106.28  |   -108.535 |      1214.82  |
| bucket/orb_dbl     |  454 |      0.144 |        0.586 |  -0.031 |   -0.048 |      -0.008 |    0.557 |     0.541 |    1.076 |     1.038 |   954.473 |    310.274 |       644.199 |
| ridge              | 2059 |      0.076 |        0.527 |  -0.038 |   -0.008 |      -0.071 |    0.558 |     0.575 |    1.047 |     1.129 |  2534.36  |   3675.1   |     -1140.74  |
| ridge/mr_gapfade   |  743 |      0.118 |        0.498 |  -0.05  |   -0.003 |      -0.097 |    0.509 |     0.532 |    1.038 |     1.052 |   473.604 |    346.052 |       127.552 |
| ridge/orb_close30  |  862 |      0.075 |        0.503 |  -0.03  |    0.023 |      -0.084 |    0.6   |     0.636 |    1.038 |     1.241 |  1106.28  |   3195.35  |     -2089.07  |
| ridge/orb_dbl      |  454 |     -0.029 |        0.619 |  -0.031 |   -0.063 |       0.019 |    0.557 |     0.537 |    1.076 |     1.016 |   954.473 |    133.701 |       820.772 |

Chosen grader: **gbm_small / target R / features compact / half-life 3.0 / per-strategy False** (highest pooled rank correlation on 2014-2024).

Development search over 72 variants (model x target x feature set x recency half-life x pooled/per-strategy), best 12 by rank correlation on 2014-2024:

|    | model     | target   | features   |   halflife | per_strategy   |   spearman |   gap |   years_gap_pos |   kept_share |   pf_all |   pf_kept |
|---:|:----------|:---------|:-----------|-----------:|:---------------|-----------:|------:|----------------:|-------------:|---------:|----------:|
|  0 | gbm_small | R        | compact    |          3 | False          |      0.128 | 0.064 |           0.818 |        0.489 |    1.047 |     1.084 |
|  1 | gbm_small | R        | all        |          3 | False          |      0.123 | 0.068 |           0.636 |        0.53  |    1.047 |     1.167 |
|  2 | gbm_small | R        | all        |        nan | False          |      0.113 | 0.032 |           0.727 |        0.535 |    1.047 |     1.049 |
|  3 | gbm_small | R        | compact    |        nan | False          |      0.106 | 0.038 |           0.545 |        0.511 |    1.047 |     1.072 |
|  4 | linear    | R        | compact    |        nan | True           |      0.105 | 0.093 |           0.818 |        0.494 |    1.047 |     1.101 |
|  5 | linear    | R        | compact    |          3 | False          |      0.103 | 0.065 |           0.455 |        0.523 |    1.047 |     1.089 |
|  6 | linear    | R        | compact    |        nan | False          |      0.096 | 0.09  |           0.727 |        0.533 |    1.047 |     1.131 |
|  7 | linear    | R        | compact    |          3 | True           |      0.096 | 0.056 |           0.727 |        0.478 |    1.047 |     1.045 |
|  8 | gbm_small | R        | compact    |        nan | True           |      0.082 | 0.034 |           0.636 |        0.493 |    1.047 |     0.99  |
|  9 | linear    | R        | all        |        nan | False          |      0.076 | 0.063 |           0.636 |        0.527 |    1.047 |     1.129 |
| 10 | linear    | R        | memory     |          3 | False          |      0.074 | 0.008 |           0.545 |        0.644 |    1.047 |     1.052 |
| 11 | gbm       | R        | all        |        nan | False          |      0.072 | 0.023 |           0.636 |        0.541 |    1.047 |     1.071 |

`gap` = mean R of kept minus dropped setups; `years_gap_pos` = share of the 11 development years in which the kept setups did better than the dropped ones.

Per year, chosen grader (OOS, fixed stream):

|   year |   n |   spearman |   kept_share |   R_all |   R_kept |   R_dropped |   pf_all |   pf_kept |   net_all |   net_kept |
|-------:|----:|-----------:|-------------:|--------:|---------:|------------:|---------:|----------:|----------:|-----------:|
|   2014 | 216 |      0.173 |        0.565 |  -0.105 |   -0.021 |      -0.214 |    0.732 |     0.897 |  -570.639 |   -125.084 |
|   2015 | 204 |      0.014 |        0.505 |  -0.119 |   -0.088 |      -0.152 |    0.665 |     0.761 |  -962.055 |   -357.165 |
|   2016 | 208 |     -0.056 |        0.466 |  -0.148 |   -0.226 |      -0.08  |    0.77  |     0.719 |  -582.469 |   -339.479 |
|   2017 | 227 |      0.086 |        0.344 |  -0.008 |   -0.005 |      -0.01  |    1.117 |     1.122 |   249.821 |     89.281 |
|   2018 | 197 |      0.033 |        0.594 |  -0.014 |   -0.014 |      -0.014 |    1.066 |     0.971 |   265.178 |    -74.952 |
|   2019 | 170 |      0.164 |        0.482 |  -0.11  |    0.027 |      -0.239 |    0.906 |     1.211 |  -278.195 |    268.826 |
|   2020 | 194 |      0.145 |        0.51  |  -0.052 |    0.03  |      -0.138 |    0.857 |     0.908 | -1211.82  |   -473.978 |
|   2021 | 203 |      0.175 |        0.621 |   0.043 |    0.125 |      -0.09  |    1.214 |     1.417 |  1583.95  |   1855.07  |
|   2022 | 147 |      0.15  |        0.422 |   0.061 |    0.091 |       0.038 |    1.191 |     1.091 |  1792.02  |    439.892 |
|   2023 |  92 |      0.011 |        0.348 |   0.043 |   -0.063 |       0.099 |    1.204 |     0.86  |   725.349 |   -239.106 |
|   2024 | 201 |      0.026 |        0.443 |   0.06  |    0.069 |       0.053 |    1.174 |     1.385 |  1523.22  |   1308.82  |
|   2025 | 198 |      0.109 |        0.313 |   0.137 |    0.246 |       0.088 |    1.711 |     1.979 |  5973.73  |   2644.42  |
|   2026 | 126 |      0.15  |        0.365 |   0.169 |    0.108 |       0.204 |    1.577 |     1.147 |  4548.59  |    554.098 |

Grade table 2014-2024 (OOS, fixed stream):

| grade   |   n |   win_rate |   mean_R |      net |   avg_pnl |    pf |
|:--------|----:|-----------:|---------:|---------:|----------:|------:|
| A+      | 217 |      0.535 |   -0.048 |  787.152 |     3.627 | 1.134 |
| A       | 306 |      0.598 |    0.055 | 1128.38  |     3.688 | 1.141 |
| B       | 484 |      0.576 |   -0.024 |  436.6   |     0.902 | 1.031 |
| C       | 505 |      0.57  |   -0.049 |   53.8   |     0.107 | 1.004 |
| D       | 327 |      0.581 |   -0.027 |  478.305 |     1.463 | 1.065 |
| F       | 220 |      0.418 |   -0.177 | -349.875 |    -1.59  | 0.902 |

## 2. The 2025-26 test (the stream the final report is based on)

Grade table, walk-forward grader on the 2025-01..2026-09 walk-forward parameter stream:

| grade   |   n |   win_rate |   mean_R |      net |   avg_pnl |    pf |
|:--------|----:|-----------:|---------:|---------:|----------:|------:|
| A+      |  27 |      0.593 |    0.255 | 1364.98  |    50.555 | 2.149 |
| A       |  28 |      0.643 |    0.169 |  711.813 |    25.422 | 1.364 |
| B       |  61 |      0.672 |    0.118 | 1358.12  |    22.264 | 1.367 |
| C       |  44 |      0.705 |    0.195 | 1875.06  |    42.615 | 1.844 |
| D       |  41 |      0.707 |    0.135 | 1212.68  |    29.578 | 1.433 |
| F       |  82 |      0.634 |    0.074 | 1212.83  |    14.791 | 1.273 |

Walk-forward grader vs the two controls on the same 283 setups:

|                        |   n |   spearman |   kept_share |   R_all |   R_kept |   R_dropped |   wr_all |   wr_kept |   pf_all |   pf_kept |   net_all |   net_kept |   net_dropped |
|:-----------------------|----:|-----------:|-------------:|--------:|---------:|------------:|---------:|----------:|---------:|----------:|----------:|-----------:|--------------:|
| walk_forward_wf2025    | 283 |      0.075 |        0.41  |   0.138 |    0.162 |       0.121 |    0.661 |     0.647 |    1.475 |     1.502 |   7735.48 |    3434.91 |       4300.56 |
| insample_wf2025        | 283 |      0.293 |        0.519 |   0.138 |    0.335 |      -0.075 |    0.661 |     0.776 |    1.475 |     2.703 |   7735.48 |    9530.99 |      -1795.51 |
| shuffled_wf2025        | 283 |     -0.04  |        0.378 |   0.138 |    0.137 |       0.139 |    0.661 |     0.664 |    1.475 |     1.328 |   7735.48 |    2394.67 |       5340.81 |
| walk_forward_fixed2025 | 324 |      0.134 |        0.333 |   0.15  |    0.187 |       0.131 |    0.657 |     0.657 |    1.646 |     1.495 |  10522.3  |    3198.52 |       7323.8  |
| insample_fixed2025     | 324 |      0.473 |        0.543 |   0.15  |    0.466 |      -0.227 |    0.657 |     0.824 |    1.646 |     3.997 |  10522.3  |   14074.7  |      -3552.38 |

Most useful features of the chosen grader fitted on 2010-2024, measured on the 2025-26 fixed stream (permutation importance in MSE units; negative = the feature hurt out of sample):

|                 |   importance |
|:----------------|-------------:|
| day_move        |      0.01297 |
| risk_atr        |      0.00791 |
| rr              |      0.00711 |
| mem_wr_hour     |      0.0061  |
| pos_in_pd_range |      0.00206 |
| trend200_dir    |      0.002   |
| day_range       |      0.00107 |
| gap_dir         |      0.00091 |
| atr_ratio       |      0.00091 |
| dow             |      0.00085 |
| dist_pdh        |      0.00036 |
| is_mr_gapfade   |      0       |

## 3. Account results 2025-01..2026-09, one account at a time

Baseline = every signal (what the final report simulates; small differences from that report come from indicators warmed on the full history instead of 45 days). B_and_up = walk-forward grader, grades A+/A/B taken (thresholds fixed at the January refit; it kept only 41% of 2025-26 setups because many looked unlike 2010-2024 setups, and it graded most orb_close30 signals F). B_and_up_trailing_thresholds = same predictions, but each setup is graded against the predictions of the previous 250 setups (causal), which keeps 57%. A_and_up and C_and_up for reference. The two control columns use the same B-and-up rule with the in-sample and the shuffled grader.

### Aggressive configuration (15 micros, one attempt)

| Metric | baseline | B_and_up | B_and_up_trailing_thresholds | A_and_up | C_and_up | B_and_up_insample_grader | B_and_up_shuffled_grader |
|---|---|---|---|---|---|---|---|
| Trades taken (3 legs) | 283 | 116 | 162 | 55 | 160 | 147 | 107 |
| Net per unit book (1 micro each), $ | 7,735 | 3,435 | 4,809 | 2,077 | 5,310 | 9,531 | 2,395 |
| P(pass) single attempt | 60% | 36% | 51% | 48% | 43% | 83% | 30% |
| P(pass within 21 sessions) | 33% | 7% | 16% | 6% | 15% | 31% | 5% |
| Median sessions to pass | 20 | 42 | 32 | 49 | 28 | 26 | 46 |
| P(lose the fee) per attempt | 40% | 64% | 49% | 52% | 57% | 17% | 70% |
| P(funded) within attempts | 60% | 36% | 51% | 48% | 43% | 83% | 30% |
| P(funded) bootstrap 5%..95% | 35%..67% | 12%..60% | 22%..68% | 6%..71% | 23%..67% | 58%..95% | 8%..53% |
| Worst start month P(funded) | 0% | 0% | 0% | 0% | 0% | 35% | 0% |
| P(first payout | funded) | 64% | 25% | 22% | 76% | 33% | 82% | 29% |
| P(first payout) overall | 39% | 9% | 11% | 36% | 14% | 68% | 9% |
| P(first payout) bootstrap 5%..95% | 6%..43% | 0%..35% | 0%..40% | 0%..58% | 0%..46% | 37%..89% | 0%..31% |
| P(funded account blown before any payout | pass) | 36% | 75% | 78% | 24% | 67% | 18% | 71% |
| Median sessions funded -> first payout | 26 | 135 | 14 | 133 | 18 | 20 | 30 |
| Mean payouts per funded account | 2.10 | 0.25 | 0.69 | 1.31 | 0.88 | 2.73 | 0.55 |
| Mean paid | funded (90% split), $ | 3,772 | 450 | 1,233 | 2,366 | 1,590 | 4,905 | 991 |
| Expected net per campaign, $ | 2,128 | 18 | 481 | 994 | 531 | 3,909 | 149 |
| Expected net bootstrap 5% / 50% / 95%, $ | -1 / 914 / 2,505 | -146 / 9 / 1,520 | -146 / 397 / 2,069 | -146 / -29 / 2,100 | -133 / 526 / 2,723 | 1,667 / 4,301 / 6,693 | -146 / -108 / 867 |
| P(expected net > 0) bootstrap | 94% | 52% | 80% | 46% | 79% | 100% | 35% |
| Zero-edge control expected net, $ | -134 | -146 | -129 | -146 | -96 | -132 | -146 |
| Avg sessions to pass (passed evals) | 22.2 | 42.8 | 34.6 | 65.6 | 34.3 | 26.5 | 76.4 |
| Avg sessions a failed eval lasted | 9.0 | 31.0 | 18.4 | 54.1 | 24.5 | 16.4 | 37.1 |
| Share of starts reaching a payout before data end | 70% | 9% | 53% | 30% | 82% | 85% | 61% |
| Avg calendar sessions start -> first payout | 85.2 | 142.5 | 142.3 | 176.4 | 148.9 | 67.9 | 198.0 |
| Median calendar sessions start -> first payout | 78.0 | 166.0 | 145.0 | 175.5 | 139.0 | 64.0 | 198.5 |
| Avg evals failed before first payout | 0.89 | 0.00 | 1.08 | 0.00 | 1.23 | 0.30 | 0.91 |
| Avg funded accounts blown before first payout | 0.21 | 0.00 | 0.50 | 0.00 | 0.88 | 0.08 | 0.43 |
| Avg accounts lost (evals + funded) before first payout | 1.10 | 0.00 | 1.59 | 0.00 | 2.12 | 0.38 | 1.34 |
| Avg fees paid until first payout, $ | 257 | 146 | 317 | 146 | 386 | 184 | 291 |
| Avg payouts per funded account (to breach/live) | 2.10 | 0.25 | 0.69 | 1.67 | 0.88 | 2.70 | 0.49 |
| Avg gross paid per funded account, $ | 4,192 | 500 | 1,370 | 3,333 | 1,754 | 5,395 | 971 |


### Safe configuration (9 micros, up to three attempts)

| Metric | baseline | B_and_up | B_and_up_trailing_thresholds | A_and_up | C_and_up | B_and_up_insample_grader | B_and_up_shuffled_grader |
|---|---|---|---|---|---|---|---|
| Trades taken (3 legs) | 283 | 116 | 162 | 55 | 160 | 147 | 107 |
| Net per unit book (1 micro each), $ | 7,735 | 3,435 | 4,809 | 2,077 | 5,310 | 9,531 | 2,395 |
| P(pass) single attempt | 76% | 27% | 42% | 48% | 43% | 94% | 28% |
| P(pass within 21 sessions) | 16% | 3% | 6% | 1% | 9% | 19% | 1% |
| Median sessions to pass | 43 | 43 | 52 | 74 | 47 | 42 | 49 |
| P(lose the fee) per attempt | 24% | 73% | 58% | 52% | 57% | 6% | 72% |
| P(funded) within attempts | 93% | 84% | 97% | 66% | 97% | 100% | 43% |
| P(funded) bootstrap 5%..95% | 70%..100% | 30%..100% | 61%..100% | 0%..73% | 67%..100% | 90%..100% | 6%..98% |
| Worst start month P(funded) | 29% | 5% | 57% | 0% | 67% | 100% | 0% |
| P(first payout | funded) | 69% | 0% | 8% | 100% | 27% | 82% | 0% |
| P(first payout) overall | 65% | 0% | 8% | 66% | 26% | 82% | 0% |
| P(first payout) bootstrap 5%..95% | 2%..85% | 0%..92% | 0%..89% | 0%..66% | 0%..95% | 67%..100% | 0%..75% |
| P(funded account blown before any payout | pass) | 32% | 100% | 81% | 0% | 54% | 20% | 100% |
| Median sessions funded -> first payout | 42 | n/a | 123 | 156 | 114 | 53 | n/a |
| Mean payouts per funded account | 1.57 | 0.00 | 0.33 | 1.00 | 0.65 | 2.51 | 0.00 |
| Mean paid | funded (90% split), $ | 2,809 | 0 | 258 | 1,800 | 696 | 4,821 | 0 |
| Expected net per campaign, $ | 2,442 | -190 | 27 | 1,038 | 474 | 4,670 | -162 |
| Expected net bootstrap 5% / 50% / 95%, $ | -168 / 2,008 / 5,763 | -247 / 623 / 4,104 | -245 / 1,155 / 5,100 | -209 / -146 / 1,241 | -220 / 2,078 / 5,937 | 2,559 / 6,017 / 7,831 | -283 / -162 / 2,350 |
| P(expected net > 0) bootstrap | 92% | 57% | 82% | 22% | 87% | 100% | 40% |
| Zero-edge control expected net, $ | -146 | -146 | -146 | -146 | -146 | -146 | -146 |
| Avg sessions to pass (passed evals) | 44.5 | 62.4 | 56.9 | 87.4 | 58.6 | 42.6 | 157.9 |
| Avg sessions a failed eval lasted | 19.4 | 67.9 | 43.6 | 91.3 | 51.3 | 15.1 | 24.5 |
| Share of starts reaching a payout before data end | 61% | 1% | 7% | 15% | 15% | 79% | 18% |
| Avg calendar sessions start -> first payout | 143.1 | 319.0 | 174.2 | 225.9 | 129.3 | 123.3 | 309.0 |
| Median calendar sessions start -> first payout | 134.5 | 319.0 | 179.0 | 226.0 | 145.0 | 122.0 | 305.0 |
| Avg evals failed before first payout | 0.17 | 0.00 | 0.00 | 0.00 | 0.00 | 0.07 | 0.00 |
| Avg funded accounts blown before first payout | 0.10 | 0.00 | 0.00 | 0.00 | 0.00 | 0.16 | 0.00 |
| Avg accounts lost (evals + funded) before first payout | 0.27 | 0.00 | 0.00 | 0.00 | 0.00 | 0.23 | 0.00 |
| Avg fees paid until first payout, $ | 176 | 146 | 146 | 146 | 146 | 175 | 146 |
| Avg payouts per funded account (to breach/live) | 1.70 | 0.00 | 0.49 | 0.86 | 0.47 | 2.49 | 0.02 |
| Avg gross paid per funded account, $ | 3,401 | 0 | 982 | 1,714 | 940 | 4,975 | 47 |


Per-leg trade statistics 2025-26 (per micro, after costs):

| variant                      | leg         |   trades |   net |   win_rate |   pf |   max_dd_intraday |   sharpe |
|:-----------------------------|:------------|---------:|------:|-----------:|-----:|------------------:|---------:|
| baseline                     | orb_close30 |      142 |  4231 |      0.718 | 1.49 |             -1076 |     1.53 |
| baseline                     | mr_gapfade  |       66 |  1223 |      0.53  | 1.43 |              -587 |     0.94 |
| baseline                     | orb_dbl     |       75 |  2282 |      0.667 | 1.46 |             -1251 |     1.01 |
| B_and_up                     | orb_close30 |       39 |  -252 |      0.59  | 0.93 |             -1504 |    -0.15 |
| B_and_up                     | mr_gapfade  |       40 |   877 |      0.6   | 1.51 |              -431 |     0.86 |
| B_and_up                     | orb_dbl     |       37 |  2809 |      0.757 | 2.91 |              -516 |     2.01 |
| B_and_up_trailing_thresholds | orb_close30 |       53 |  1629 |      0.698 | 1.45 |             -1087 |     0.87 |
| B_and_up_trailing_thresholds | mr_gapfade  |       49 |  1141 |      0.612 | 1.5  |              -633 |     0.95 |
| B_and_up_trailing_thresholds | orb_dbl     |       60 |  2039 |      0.667 | 1.5  |             -1251 |     0.97 |
| A_and_up                     | orb_close30 |        6 |    81 |      0.667 | 1.14 |              -590 |     0.11 |
| A_and_up                     | mr_gapfade  |       27 |   572 |      0.519 | 1.41 |              -472 |     0.61 |
| A_and_up                     | orb_dbl     |       22 |  1424 |      0.727 | 2.19 |              -535 |     1.19 |
| C_and_up                     | orb_close30 |       55 |  1518 |      0.709 | 1.42 |             -1124 |     0.83 |
| C_and_up                     | mr_gapfade  |       48 |  1031 |      0.604 | 1.45 |              -633 |     0.86 |
| C_and_up                     | orb_dbl     |       57 |  2761 |      0.667 | 1.88 |              -885 |     1.54 |
| B_and_up_insample_grader     | orb_close30 |       71 |  6229 |      0.859 | 4.01 |              -644 |     3.41 |
| B_and_up_insample_grader     | mr_gapfade  |       36 |   669 |      0.611 | 1.4  |              -654 |     0.67 |
| B_and_up_insample_grader     | orb_dbl     |       40 |  2633 |      0.775 | 2.42 |              -624 |     1.74 |
| B_and_up_shuffled_grader     | orb_close30 |       44 |  1287 |      0.75  | 1.44 |              -748 |     0.76 |
| B_and_up_shuffled_grader     | mr_gapfade  |       20 |   628 |      0.6   | 1.88 |              -268 |     0.91 |
| B_and_up_shuffled_grader     | orb_dbl     |       43 |   480 |      0.605 | 1.13 |              -871 |     0.26 |

## 4. Full history 2011-06..2026-09, risk-normalised (fixed parameters)

The same account simulation on the whole history, with each session's P&L scaled by ATR$(2025 median) / ATR$(then) so that one "unit" carries 2025-like dollar risk in every year (scale factor range 0.6..16.1). Not literal micro counts; it answers "would the filter have helped across regimes", not "what would the account have paid in 2013". Starts every 5th session for the calendar statistics. Note the strategies as a group were roughly flat-to-negative before 2021 (see per-year table above), so these pass rates are far below the 2025-26 ones.

Over the full history none of the variants beats its zero-edge control (the strategies as a group had no edge before 2021), so this section only says whether the filter changed anything relative to taking every signal: it did not, in either direction, beyond noise.

### Aggressive

| Metric | baseline | B_and_up | A_and_up |
|---|---|---|---|
| Trades taken (3 legs) | 3,027 | 1,759 | 1,210 |
| Net per unit book (1 micro each), $ | 11,868 | 4,362 | 3,138 |
| P(pass) single attempt | 23% | 24% | 28% |
| P(pass within 21 sessions) | 19% | 11% | 6% |
| Median sessions to pass | 13 | 23 | 46 |
| P(lose the fee) per attempt | 77% | 76% | 72% |
| P(funded) within attempts | 23% | 24% | 28% |
| P(funded) bootstrap 5%..95% | 19%..27% | 17%..28% | 16%..29% |
| Worst start month P(funded) | 0% | 0% | 0% |
| P(first payout | funded) | 29% | 25% | 31% |
| P(first payout) overall | 7% | 6% | 9% |
| P(first payout) bootstrap 5%..95% | 3%..7% | 1%..8% | 0%..7% |
| P(funded account blown before any payout | pass) | 71% | 75% | 68% |
| Median sessions funded -> first payout | 17 | 32 | 98 |
| Mean payouts per funded account | 0.92 | 0.92 | 0.70 |
| Mean paid | funded (90% split), $ | 1,657 | 1,648 | 1,269 |
| Expected net per campaign, $ | 231 | 255 | 211 |
| Expected net bootstrap 5% / 50% / 95%, $ | -71 / 4 / 186 | -117 / -30 / 118 | -137 / -69 / 100 |
| P(expected net > 0) bootstrap | 52% | 37% | 23% |
| Zero-edge control expected net, $ | 256 | 317 | 253 |
| Avg sessions to pass (passed evals) | 15.3 | 28.7 | 64.1 |
| Avg sessions a failed eval lasted | 12.4 | 19.3 | 37.7 |
| Share of starts reaching a payout before data end | 97% | 90% | 90% |
| Avg calendar sessions start -> first payout | 320.0 | 375.3 | 444.8 |
| Median calendar sessions start -> first payout | 234.0 | 306.0 | 392.0 |
| Avg evals failed before first payout | 22.25 | 13.61 | 8.72 |
| Avg funded accounts blown before first payout | 3.59 | 2.64 | 2.39 |
| Avg accounts lost (evals + funded) before first payout | 25.83 | 16.25 | 11.11 |
| Avg fees paid until first payout, $ | 2,672 | 1,756 | 1,280 |
| Avg payouts per funded account (to breach/live) | 0.86 | 0.90 | 0.54 |
| Avg gross paid per funded account, $ | 1,713 | 1,794 | 1,083 |


### Safe

| Metric | baseline | B_and_up | A_and_up |
|---|---|---|---|
| Trades taken (3 legs) | 3,027 | 1,759 | 1,210 |
| Net per unit book (1 micro each), $ | 11,868 | 4,362 | 3,138 |
| P(pass) single attempt | 23% | 24% | 20% |
| P(pass within 21 sessions) | 9% | 3% | 1% |
| Median sessions to pass | 26 | 52 | 68 |
| P(lose the fee) per attempt | 77% | 76% | 80% |
| P(funded) within attempts | 56% | 50% | 36% |
| P(funded) bootstrap 5%..95% | 43%..63% | 36%..59% | 25%..55% |
| Worst start month P(funded) | 0% | 0% | 0% |
| P(first payout | funded) | 25% | 33% | 24% |
| P(first payout) overall | 14% | 16% | 9% |
| P(first payout) bootstrap 5%..95% | 3%..18% | 1%..16% | 0%..13% |
| P(funded account blown before any payout | pass) | 64% | 60% | 58% |
| Median sessions funded -> first payout | 34 | 63 | 166 |
| Mean payouts per funded account | 0.85 | 1.13 | 0.42 |
| Mean paid | funded (90% split), $ | 1,153 | 1,562 | 555 |
| Expected net per campaign, $ | 383 | 523 | -33 |
| Expected net bootstrap 5% / 50% / 95%, $ | -194 / 39 / 489 | -255 / -48 / 345 | -272 / -173 / 137 |
| P(expected net > 0) bootstrap | 61% | 40% | 16% |
| Zero-edge control expected net, $ | 306 | 452 | 99 |
| Avg sessions to pass (passed evals) | 31.5 | 58.7 | 104.4 |
| Avg sessions a failed eval lasted | 24.0 | 44.7 | 71.9 |
| Share of starts reaching a payout before data end | 96% | 90% | 90% |
| Avg calendar sessions start -> first payout | 636.9 | 640.6 | 771.6 |
| Median calendar sessions start -> first payout | 543.0 | 575.0 | 723.0 |
| Avg evals failed before first payout | 17.85 | 11.54 | 7.84 |
| Avg funded accounts blown before first payout | 3.32 | 1.51 | 1.76 |
| Avg accounts lost (evals + funded) before first payout | 21.17 | 13.05 | 9.59 |
| Avg fees paid until first payout, $ | 2,238 | 1,405 | 1,108 |
| Avg payouts per funded account (to breach/live) | 0.79 | 1.08 | 0.06 |
| Avg gross paid per funded account, $ | 1,578 | 2,169 | 129 |


By two-year window (unit book, single attempt / three attempts as per configuration):

| period    |   baseline AGG p_funded |   baseline AGG net |   baseline SAFE p_funded |   baseline SAFE net |   B_and_up AGG p_funded |   B_and_up AGG net |   B_and_up SAFE p_funded |   B_and_up SAFE net |   A_and_up AGG p_funded |   A_and_up AGG net |   A_and_up SAFE p_funded |   A_and_up SAFE net |
|:----------|------------------------:|-------------------:|-------------------------:|--------------------:|------------------------:|-------------------:|-------------------------:|--------------------:|------------------------:|-------------------:|-------------------------:|--------------------:|
| 2011-2012 |                    0.09 |                -82 |                     0.14 |                -311 |                    0.09 |                -82 |                     0.14 |                -311 |                    0.09 |                -82 |                     0.14 |                -311 |
| 2013-2014 |                    0.1  |               -142 |                     0.3  |                -305 |                    0.11 |               -142 |                     0.32 |                -303 |                    0.17 |               -142 |                     0.55 |                -293 |
| 2015-2016 |                    0.17 |               -146 |                     0.16 |                -311 |                    0.15 |               -146 |                     0.07 |                -275 |                    0.22 |               -107 |                     0.22 |                -292 |
| 2017-2018 |                    0.27 |                 45 |                     0.84 |                 311 |                    0.3  |                 33 |                     0.82 |                1663 |                    0.5  |                284 |                     0.71 |                 135 |
| 2019-2020 |                    0.25 |                263 |                     0.56 |                 136 |                    0.21 |                -77 |                     0.93 |                -228 |                    0.19 |               -146 |                     0.6  |                -211 |
| 2021-2022 |                    0.23 |                -31 |                     0.91 |                -104 |                    0.27 |                -41 |                     0.89 |                 335 |                    0.52 |                 10 |                     0.59 |                 288 |
| 2023-2024 |                    0.19 |               -139 |                     0.75 |                -247 |                    0.25 |                -16 |                     0.39 |                 456 |                    0.25 |               -146 |                     0.08 |                -221 |
| 2025-2026 |                    0.54 |               2579 |                     0.96 |                3332 |                    0.58 |                529 |                     0.86 |                 113 |                    0.31 |                434 |                     0.3  |                 210 |

## Files

`grading/stream.py` (setup log + features), `grading/grader.py` (walk-forward grader, controls), `grading/dev_search.py` (model selection on 2014-2024), `grading/account.py` (engine re-run and account simulation), `grading/trailing.py` (causal trailing-threshold variant), `results/grading/` (graded setup tables, per-variant daily streams, JSON results).
