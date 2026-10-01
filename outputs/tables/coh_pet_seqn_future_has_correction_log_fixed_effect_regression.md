# Pooled log-sequence fixed-effects regression

The model is

`log(SECS)_ic = alpha + beta_seq * log(SEQN_i) + beta_future * FUTURE_SAME_ic + beta_correction * HAS_CORRECTION_ic + gamma_c + epsilon_ic`.

Cells are `USER_ID + D + COH + PETTYPE`. The sequence effect is modeled continuously
as `log(SEQN)`, while `FUTURE_SAME` and `HAS_CORRECTION` are retained as
task-level covariates. The fixed effects are absorbed by within-cell
demeaning. The input SQL retains the mixed-cell sample used in the prior
COH-PETTYPE analysis.

| Quantity | Value |
|---|---:|
| Cells | 36,926 |
| Outcome | `log(SECS)` |
| Input tasks before duration filter | 2,724,850 |
| Nonpositive-duration tasks removed | 0 |
| Tasks | 2,724,850 |
| Users | 324 |
| Days | 181 |
| Minimum SEQN | 1 |
| Maximum SEQN | 7 |
| `FUTURE_SAME = 1` tasks | 130,813 |
| Fraction with `HAS_CORRECTION = 1` | 0.291604 |
| Within R-squared | 0.023175 |
| Within-cell RMSE (log points) | 0.940987 |

| Term | Estimate (log points) | Cell-clustered SE | User/day two-way SE | User/day statistic | User/day p value | User/day 95% CI (log points) |
|---|---:|---:|---:|---:|---:|---:|
| LOG_SEQN | -0.289022 | 0.003959 | 0.015949 | -18.122029 | 2.13572e-73 | [-0.320281, -0.257763] |
| FUTURE_SAME | -0.004482 | 0.002727 | 0.003983 | -1.125173 | 0.260516 | [-0.012289, 0.003325] |
| HAS_CORRECTION | 0.326913 | 0.001825 | 0.011182 | 29.235607 | 6.84338e-188 | [0.304996, 0.348829] |

The two-way covariance clusters by `USER_ID` and day and uses the user
covariance plus the day covariance minus their user-day intersection
covariance. Its p values and confidence intervals use a normal approximation.

Input data: `outputs/data/coh_pet_seqn_future_has_correction_task_data.parquet`
