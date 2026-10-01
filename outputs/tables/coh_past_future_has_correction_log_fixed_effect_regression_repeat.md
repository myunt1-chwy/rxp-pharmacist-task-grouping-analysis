# Pooled past/future fixed-effects regression

The model is

`log(SECS)_ic = alpha + beta_past * PAST_SAME_ic + beta_future * FUTURE_SAME_ic + beta_correction * HAS_CORRECTION_ic + gamma_c + epsilon_ic`.

Cells are `USER_ID + D + COH`. Both treatment indicators are included in
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
| Fraction with `HAS_CORRECTION = 1` | 0.283170 |
| Within R-squared | 0.021766 |
| Within-cell RMSE (log points) | 0.957256 |

| Term | Estimate (log points) | Cell-clustered SE | User/day two-way SE | User/day statistic | User/day p value | User/day 95% CI (log points) |
|---|---:|---:|---:|---:|---:|---:|
| PAST_SAME | -0.047748 | 0.001094 | 0.002508 | -19.040523 | 7.87376e-81 | [-0.052663, -0.042832] |
| FUTURE_SAME | -0.005513 | 0.001065 | 0.001178 | -4.679980 | 2.86903e-06 | [-0.007822, -0.003204] |
| HAS_CORRECTION | 0.337980 | 0.001671 | 0.010821 | 31.232683 | 3.83697e-214 | [0.316770, 0.359190] |

The two-way covariance clusters by `USER_ID` and day and uses the user
covariance plus the day covariance minus their user-day intersection
covariance. Its p values and confidence intervals use a normal approximation.
The model includes `HAS_CORRECTION` as a binary task-level covariate. Its coefficient compares tasks with and without a correction.

Input data: `outputs/data/coh_past_future_has_correction_task_data_repeat.parquet`
