# Pooled sequence fixed-effects regression

The model is

`log(SECS)_ic = alpha + beta_seq * log(SEQN)_i + beta_future * FUTURE_SAME_ic + beta_correction * HAS_CORRECTION_ic + gamma_c + epsilon_ic`.

Cells are `USER_ID + D + COH + MC3`. The sequence effect is modeled continuously
as `log(SEQN)`, while `FUTURE_SAME` and `HAS_CORRECTION` are retained as
task-level covariates. The fixed effects are absorbed by within-cell
demeaning. The input SQL retains the mixed-cell sample used for this analysis.

| Quantity | Value |
|---|---:|
| Cells | 78,714 |
| Outcome | `log(SECS)` |
| Input tasks before duration filter | 2,761,932 |
| Nonpositive-duration tasks removed | 0 |
| Tasks | 2,761,932 |
| Users | 333 |
| Days | 182 |
| Minimum SEQN | 1 |
| Maximum SEQN | 23 |
| `FUTURE_SAME = 1` tasks | 1,164,962 |
| Fraction with `HAS_CORRECTION = 1` | 0.279148 |
| Within R-squared | 0.020995 |
| Within-cell RMSE (log points) | 0.941316 |

| Term | Estimate (log points) | Cell-clustered SE | User/day two-way SE | User/day statistic | User/day p value | User/day 95% CI (log points) |
|---|---:|---:|---:|---:|---:|---:|
| LOG_SEQN | -0.0550512 | 0.00118677 | 0.0025284 | -21.773145 | 4.17011e-105 | [-0.0600069, -0.0500956] |
| FUTURE_SAME | -0.00396488 | 0.00127916 | 0.00144153 | -2.750468 | 0.00595102 | [-0.00679028, -0.00113948] |
| HAS_CORRECTION | 0.329204 | 0.00191186 | 0.0113668 | 28.961949 | 1.98464e-184 | [0.306925, 0.351482] |

The two-way covariance clusters by `USER_ID` and day and uses the user
covariance plus the day covariance minus their user-day intersection
covariance. Its p values and confidence intervals use a normal approximation.

Input data: `outputs/data/mc3_coh_seqn_future_has_correction_task_data.parquet`
