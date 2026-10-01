# Pooled past/future fixed-effects regression

The model is

`log(SECS)_ic = alpha + beta_past * PAST_SAME_ic + beta_future * FUTURE_SAME_ic + beta_correction * HAS_CORRECTION_ic + gamma_c + epsilon_ic`.

Cells are `USER_ID + D + COH + PETTYPE`. Both treatment indicators are included in
the same regression, so the `FUTURE_SAME` coefficient is estimated while
controlling for the original `PAST_SAME` treatment and the cell fixed effects.
The sample uses the original mixed-`PAST_SAME` cells. The fixed effects are
absorbed by within-cell demeaning.

| Quantity | Value |
|---|---:|
| Cells | 36,926 |
| Outcome | `log(SECS)` |
| Input tasks before duration filter | 2,724,850 |
| Nonpositive-duration tasks removed | 0 |
| Tasks | 2,724,850 |
| Users | 324 |
| Days | 181 |
| `PAST_SAME = 1` tasks | 130,787 |
| `FUTURE_SAME = 1` tasks | 130,813 |
| Fraction with `HAS_CORRECTION = 1` | 0.291604 |
| Within R-squared | 0.023194 |
| Within-cell RMSE (log points) | 0.940978 |

| Term | Estimate (log points) | Cell-clustered SE | User/day two-way SE | User/day statistic | User/day p value | User/day 95% CI (log points) |
|---|---:|---:|---:|---:|---:|---:|
| PAST_SAME | -0.207806 | 0.002804 | 0.011292 | -18.402833 | 1.24674e-75 | [-0.229938, -0.185674] |
| FUTURE_SAME | -0.004708 | 0.002727 | 0.003982 | -1.182436 | 0.237033 | [-0.012513, 0.003096] |
| HAS_CORRECTION | 0.326909 | 0.001825 | 0.011181 | 29.238846 | 6.22438e-188 | [0.304995, 0.348823] |

The two-way covariance clusters by `USER_ID` and day and uses the user
covariance plus the day covariance minus their user-day intersection
covariance. Its p values and confidence intervals use a normal approximation.
The model includes `HAS_CORRECTION` as a binary task-level covariate. Its coefficient compares tasks with and without a correction.

Input data: `outputs/data/coh_pet_past_future_has_correction_task_data.parquet`
