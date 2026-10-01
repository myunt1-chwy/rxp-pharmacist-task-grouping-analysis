# Pooled past/future fixed-effects regression

The model is

`log(SECS)_ic = alpha + beta_past * PAST_SAME_ic + beta_future * FUTURE_SAME_ic + beta_past2 * PAST_2_SAME_ic + beta_past3 * PAST_3_SAME_ic + beta_correction * HAS_CORRECTION_ic + gamma_c + epsilon_ic`.

Cells are `USER_ID + D + COH`. The treatment indicators are included in
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
| `PAST_2_SAME = 1` tasks | 794,244 |
| `PAST_3_SAME = 1` tasks | 401,261 |
| Fraction with `HAS_CORRECTION = 1` | 0.283170 |
| Within R-squared | 0.021791 |
| Within-cell RMSE (log points) | 0.957243 |

| Term | Estimate (log points) | Cell-clustered SE | User/day two-way SE | User/day statistic | User/day p value | User/day 95% CI (log points) |
|---|---:|---:|---:|---:|---:|---:|
| PAST_SAME | -0.042947 | 0.001251 | 0.002538 | -16.919992 | 3.20473e-64 | [-0.047922, -0.037972] |
| FUTURE_SAME | -0.005550 | 0.001065 | 0.001180 | -4.702863 | 2.56539e-06 | [-0.007863, -0.003237] |
| PAST_2_SAME | -0.003041 | 0.001799 | 0.002030 | -1.497694 | 0.134213 | [-0.007021, 0.000939] |
| PAST_3_SAME | -0.014738 | 0.002183 | 0.002077 | -7.096240 | 1.28196e-12 | [-0.018809, -0.010667] |
| HAS_CORRECTION | 0.337976 | 0.001671 | 0.010822 | 31.230608 | 4.09418e-214 | [0.316765, 0.359187] |

The two-way covariance clusters by `USER_ID` and day and uses the user
covariance plus the day covariance minus their user-day intersection
covariance. Its p values and confidence intervals use a normal approximation.
The model includes `HAS_CORRECTION` as a binary task-level covariate. Its coefficient compares tasks with and without a correction.

Input data: `outputs/data/coh_past_future_past3_has_correction_task_data.parquet`
