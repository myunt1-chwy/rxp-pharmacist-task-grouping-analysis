# Pooled past/future COH fixed-effects regression

The model is

`SECS_ic = alpha + beta_past * PAST_SAME_ic + beta_future * FUTURE_SAME_ic + gamma_(USER_ID,date,COH) + epsilon_ic`.

Cells are `USER_ID + date + COH`. Both treatment indicators are included in
the same regression, so the `FUTURE_SAME` coefficient is estimated while
controlling for the original `PAST_SAME` treatment and the cell fixed effects.
The sample uses the original mixed-`PAST_SAME` cells. The fixed effects are
absorbed by within-cell demeaning.

| Quantity | Value |
|---|---:|
| Cells | 47,609 |
| Tasks | 3,527,212 |
| Users | 334 |
| Days | 182 |
| `PAST_SAME = 1` tasks | 1,630,208 |
| `FUTURE_SAME = 1` tasks | 1,630,220 |
| Within R-squared | 0.000078 |
| Within-cell RMSE (sec) | 170.430926 |

| Term | Estimate (sec) | Cell-clustered SE | User/day two-way SE | User/day statistic | User/day p value | User/day 95% CI (sec) |
|---|---:|---:|---:|---:|---:|---:|
| PAST_SAME | -3.031028 | 0.173180 | 0.223859 | -13.539906 | 9.09056e-42 | [-3.469792, -2.592265] |
| FUTURE_SAME | -0.700036 | 0.210568 | 0.214502 | -3.263535 | 0.00110032 | [-1.120461, -0.279611] |

The two-way covariance clusters by `USER_ID` and day and uses the user
covariance plus the day covariance minus their user-day intersection
covariance. Its p values and confidence intervals use a normal approximation.

Input data: `outputs/data/coh_past_future_task_data.parquet`
