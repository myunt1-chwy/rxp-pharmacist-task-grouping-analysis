# Pooled past/future fixed-effects regression

The model is

`log(SECS)_ic = alpha + beta_past * PAST_SAME_ic + beta_future * FUTURE_SAME_ic + beta_correction * HAS_CORRECTION_ic + gamma_c + epsilon_ic`.

Cells are `USER_ID + D + MC3 + COH + PETTYPE`. Both treatment indicators are included in
the same regression, so the `FUTURE_SAME` coefficient is estimated while
controlling for the original `PAST_SAME` treatment and the cell fixed effects.
The sample uses the original mixed-`PAST_SAME` cells. The fixed effects are
absorbed by within-cell demeaning.

| Quantity | Value |
|---|---:|
| Cells | 83,953 |
| Outcome | `log(SECS)` |
| Input tasks before duration filter | 2,578,564 |
| Nonpositive-duration tasks removed | 0 |
| Tasks | 2,578,564 |
| Users | 332 |
| Days | 182 |
| `PAST_SAME = 1` tasks | 997,940 |
| `FUTURE_SAME = 1` tasks | 997,973 |
| Fraction with `HAS_CORRECTION = 1` | 0.277826 |
| Within R-squared | 0.020239 |
| Within-cell RMSE (log points) | 0.934824 |

| Term | Estimate (log points) | Cell-clustered SE | User/day two-way SE | User/day statistic | User/day p value | User/day 95% CI (log points) |
|---|---:|---:|---:|---:|---:|---:|
| PAST_SAME | -0.074898 | 0.001353 | 0.003502 | -21.386192 | 1.79637e-101 | [-0.081762, -0.068033] |
| FUTURE_SAME | -0.002924 | 0.001324 | 0.001533 | -1.906642 | 0.056567 | [-0.005929, 0.000082] |
| HAS_CORRECTION | 0.319620 | 0.001919 | 0.011366 | 28.120948 | 5.43243e-174 | [0.297343, 0.341897] |

The two-way covariance clusters by `USER_ID` and day and uses the user
covariance plus the day covariance minus their user-day intersection
covariance. Its p values and confidence intervals use a normal approximation.
The model includes `HAS_CORRECTION` as a binary task-level covariate. Its coefficient compares tasks with and without a correction.

Input data: `outputs/data/mc3_coh_pettype_past_future_has_correction_task_data.parquet`
