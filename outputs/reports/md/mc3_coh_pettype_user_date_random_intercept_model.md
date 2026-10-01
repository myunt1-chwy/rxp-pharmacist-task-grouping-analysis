# MC3/COH/PETTYPE user and date random-intercept model

## Model

\[
Z_{icut} = \gamma_c
+ X_{icut}\beta
+ \delta_{weekday(t)}
+ b_u + a_t + \epsilon_{icut},
\]

where the globally Box-Cox-transformed outcome uses
\(\lambda=-0.08159843\), cells are MC3 + COH + PETTYPE,
\(b_u \sim N(0,\sigma_u^2)\), \(a_t \sim N(0,\sigma_d^2)\), and
\(\epsilon_{icut} \sim N(0,\sigma_e^2)\). Sunday is the weekday reference.

## Sample and fit

| Quantity | Value |
|---|---:|
| Tasks | 3,433,218 |
| MC3/COH/PETTYPE cells | 265 |
| Users | 340 |
| Dates | 182 |
| Global approximate P95 cutoff (seconds) | 156.628314 |
| Box-Cox lambda | -0.08159843 |
| Conditional R-squared | 0.286931 |
| Conditional RMSE (Box-Cox scale) | 0.613142 |
| REML negative log-likelihood | 3194630.238240 |
| Converged | True |

## Fixed effects

| Term | Estimate | SE | z | p-value | 95% CI |
|---|---:|---:|---:|---:|---:|
| SAME_PRECEDING | -0.049979 | 0.000847 | -59.0336 | <1e-300 | [-0.051638, -0.048320] |
| SAME_FOLLOWING | -0.002509 | 0.000847 | -2.9620 | 0.00305629 | [-0.004170, -0.000849] |
| HAS_CORRECTION | 0.253823 | 0.000782 | 324.7740 | <1e-300 | [0.252291, 0.255355] |
| WEEKDAY_MON | 0.013690 | 0.016530 | 0.8282 | 0.407569 | [-0.018709, 0.046089] |
| WEEKDAY_TUE | 0.024027 | 0.016526 | 1.4538 | 0.145989 | [-0.008364, 0.056418] |
| WEEKDAY_WED | 0.021760 | 0.016532 | 1.3163 | 0.188085 | [-0.010642, 0.054162] |
| WEEKDAY_THU | 0.017651 | 0.016534 | 1.0676 | 0.285722 | [-0.014755, 0.050057] |
| WEEKDAY_FRI | 0.014142 | 0.016533 | 0.8554 | 0.392334 | [-0.018261, 0.046545] |
| WEEKDAY_SAT | 0.007374 | 0.016551 | 0.4455 | 0.655942 | [-0.025066, 0.039814] |

## Variance components

| Component | SD | Approximate 95% CI |
|---|---:|---:|
| User random intercept | 0.419057 | [0.387478, 0.453210] |
| Date random intercept | 0.059314 | [0.053364, 0.065927] |
| Residual | 0.613212 | [0.612754, 0.613671] |

The user and date intervals use a numerical observed-information Wald
approximation on the log-SD scale.

## Diagnostics

![User random-intercept Q–Q plot](../../charts/mc3-coh-pettype-user-date-random-intercept-model/user_random_intercepts_qq.png)

![Date random-intercept Q–Q plot](../../charts/mc3-coh-pettype-user-date-random-intercept-model/date_random_intercepts_qq.png)

![Conditional residual Q–Q plot](../../charts/mc3-coh-pettype-user-date-random-intercept-model/conditional_residuals_qq.png)

![Conditional predictions versus Box-Cox outcomes](../../charts/mc3-coh-pettype-user-date-random-intercept-model/predicted_vs_boxcox_actual.png)

## Artifacts

- [Generated SQL](../../../generated/mc3_coh_pettype_user_date_random_intercept_model.sql)
- [Raw Snowflake data](../../data/mc3_coh_pettype_user_date_random_intercept_task_data.parquet)
- [Box-Cox model data](../../data/mc3_coh_pettype_user_date_random_intercept_boxcox_data.parquet)
- [Fixed-effect table](../../tables/mc3_coh_pettype_user_date_random_intercept_fixed_effects.md)
- [User random intercepts](../../tables/mc3_coh_pettype_user_date_random_intercept_user_effects.md)
- [Date random intercepts](../../tables/mc3_coh_pettype_user_date_random_intercept_date_effects.md)
