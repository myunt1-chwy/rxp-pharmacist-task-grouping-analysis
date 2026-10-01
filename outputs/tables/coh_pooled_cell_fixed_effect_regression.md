# Pooled COH fixed-effects regression

The model is

`SECS_ic = alpha + beta * PAST_SAME_ic + gamma_(USER_ID,date,COH) + epsilon_ic`.

Cells are `USER_ID + date + COH`. Only mixed cells are included, so every
cell contains at least one `PAST_SAME = 1` and one `PAST_SAME = 0` task. The
cell effects are absorbed by within-cell demeaning. The report compares
one-way cell-clustered inference with two-way clustering by user and day.

| Quantity | Value |
|---|---:|
| Cells | 47,609 |
| Tasks | 3,527,212 |
| `PAST_SAME = 1` tasks | 1,630,208 |
| `PAST_SAME = 0` tasks | 1,897,004 |
| Treatment coefficient (`beta`, sec) | -3.023922 |
| Users | 334 |
| Days | 182 |
| Within R-squared | 0.000074 |
| Within-cell RMSE (sec) | 170.431239 |

The intercept and individual cell effects are not reported separately because
their levels depend on the fixed-effect normalization; `beta` is identified
by within-cell treated-versus-untreated variation.

| Inference | Standard error (sec) | Statistic | p value | 95% CI for `beta` (sec) |
|---|---:|---:|---:|---:|
| Clustered by cell | 0.173537 | -17.425196 | 8.63086e-68 | [-3.364058, -2.683787] |
| Two-way clustered by `USER_ID` and day | 0.223364 | -13.538105 | 9.31619e-42 | [-3.461715, -2.586129] |

The two-way covariance uses the user covariance plus the day covariance minus
their user-day intersection covariance. Its p value and confidence interval
use a normal approximation.

Input data: `outputs/data/coh_forward_task_data_cohort_batch_len.parquet`
