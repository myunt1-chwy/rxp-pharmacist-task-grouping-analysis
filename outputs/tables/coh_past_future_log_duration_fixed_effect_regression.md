# Pooled past/future COH fixed-effects regression

The model is

`log(SECS)_ic = alpha + beta_past * PAST_SAME_ic + beta_future * FUTURE_SAME_ic + gamma_(USER_ID,date,COH) + epsilon_ic`.

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
| Within R-squared | 0.000577 |
| Within-cell RMSE (log points) | 0.967567 |

| Term | Estimate (log points) | Cell-clustered SE | User/day two-way SE | User/day statistic | User/day p value | User/day 95% CI (log points) |
|---|---:|---:|---:|---:|---:|---:|
| PAST_SAME | -0.047747 | 0.001105 | 0.002482 | -19.233972 | 1.92318e-82 | [-0.052612, -0.042881] |
| FUTURE_SAME | -0.005522 | 0.001075 | 0.001209 | -4.567165 | 4.94365e-06 | [-0.007892, -0.003152] |

The two-way covariance clusters by `USER_ID` and day and uses the user
covariance plus the day covariance minus their user-day intersection
covariance. Its p values and confidence intervals use a normal approximation.

Input data: `outputs/data/coh_past_future_task_data.parquet`
