# Pooled past/future COH fixed-effects regression

The model is

`log(SECS)_ic = alpha + beta_past * PAST_SAME_ic + beta_future * FUTURE_SAME_ic + beta_corrections * NCORRECTIONS_ic + gamma_(USER_ID,date,COH) + epsilon_ic`.

Cells are `USER_ID + date + COH`. Both treatment indicators are included in
the same regression, so the `FUTURE_SAME` coefficient is estimated while
controlling for the original `PAST_SAME` treatment and the cell fixed effects.
The sample uses the original mixed-`PAST_SAME` cells. The fixed effects are
absorbed by within-cell demeaning.

| Quantity | Value |
|---|---:|
| Cells | 47,609 |
| Outcome | `log(SECS)` |
| Input tasks before duration filter | 3,527,212 |
| Nonpositive-duration tasks removed | 125 |
| Tasks | 3,527,087 |
| Users | 334 |
| Days | 182 |
| `PAST_SAME = 1` tasks | 1,630,118 |
| `FUTURE_SAME = 1` tasks | 1,630,175 |
| Mean `NCORRECTIONS` | 0.299765 |
| Within R-squared | 0.026351 |
| Within-cell RMSE (log points) | 0.955010 |

| Term | Estimate (log points) | Cell-clustered SE | User/day two-way SE | User/day statistic | User/day p value | User/day 95% CI (log points) |
|---|---:|---:|---:|---:|---:|---:|
| PAST_SAME | -0.047727 | 0.001092 | 0.002509 | -19.023178 | 1.09632e-80 | [-0.052644, -0.042810] |
| FUTURE_SAME | -0.005453 | 0.001063 | 0.001166 | -4.676867 | 2.91291e-06 | [-0.007738, -0.003168] |
| NCORRECTIONS | 0.337201 | 0.001482 | 0.009401 | 35.868158 | 9.58514e-282 | [0.318775, 0.355627] |

The two-way covariance clusters by `USER_ID` and day and uses the user
covariance plus the day covariance minus their user-day intersection
covariance. Its p values and confidence intervals use a normal approximation.
The model includes `NCORRECTIONS` as a task-level covariate. Its coefficient is the change per additional correction field.

Input data: `outputs/data/coh_past_future_ncorrections_task_data.parquet`
