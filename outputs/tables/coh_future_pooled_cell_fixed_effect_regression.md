# Pooled COH fixed-effects regression

The model is

`SECS_ic = alpha + beta * FUTURE_SAME_ic + gamma_(USER_ID,date,COH) + epsilon_ic`.

Cells are `USER_ID + date + COH`. Only mixed cells are included, so every
cell contains at least one `FUTURE_SAME = 1` and one `FUTURE_SAME = 0` task. The
cell effects are absorbed by within-cell demeaning. The report compares
one-way cell-clustered inference with two-way clustering by user and day.

| Quantity | Value |
|---|---:|
| Cells | 47,609 |
| Tasks | 3,527,235 |
| `FUTURE_SAME = 1` tasks | 1,630,255 |
| `FUTURE_SAME = 0` tasks | 1,896,980 |
| Treatment coefficient (`beta`, sec) | -0.667426 |
| Users | 334 |
| Days | 182 |
| Within R-squared | 0.000004 |
| Within-cell RMSE (sec) | 170.438693 |

The intercept and individual cell effects are not reported separately because
their levels depend on the fixed-effect normalization; `beta` is identified
by within-cell treated-versus-untreated variation.

| Inference | Standard error (sec) | Statistic | p value | 95% CI for `beta` (sec) |
|---|---:|---:|---:|---:|
| Clustered by cell | 0.210863 | -3.165214 | 0.00155066 | [-1.080719, -0.254132] |
| Two-way clustered by `USER_ID` and day | 0.214530 | -3.111108 | 0.00186386 | [-1.087904, -0.246947] |

The two-way covariance uses the user covariance plus the day covariance minus
their user-day intersection covariance. Its p value and confidence interval
use a normal approximation.

Input data: `outputs/data/coh_future_task_data.parquet`
