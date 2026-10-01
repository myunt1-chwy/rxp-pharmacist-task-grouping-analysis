# Pooled sequence fixed-effects regression

The model is

`log(SECS)_ic = alpha + beta_seq * exp(SEQN)_i + beta_future * FUTURE_SAME_ic + beta_correction * HAS_CORRECTION_ic + gamma_c + epsilon_ic`.

Cells are `USER_ID + D + COH + MC3`. The sequence effect is modeled continuously
as `exp(SEQN)`, while `FUTURE_SAME` and `HAS_CORRECTION` are retained as
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
| Within R-squared | 0.020069 |
| Within-cell RMSE (log points) | 0.941761 |

| Term | Estimate (log points) | Cell-clustered SE | User/day two-way SE | User/day statistic | User/day p value | User/day 95% CI (log points) |
|---|---:|---:|---:|---:|---:|---:|
| EXP_SEQN | -6.63432e-12 | 5.26998e-11 | 5.34055e-11 | -0.124225 | 0.901137 | [-1.11309e-10, 9.80405e-11] |
| FUTURE_SAME | -0.00265099 | 0.0012765 | 0.00145353 | -1.823830 | 0.0681778 | [-0.0054999, 0.000197927] |
| HAS_CORRECTION | 0.329248 | 0.00191221 | 0.0113647 | 28.971067 | 1.52351e-184 | [0.306973, 0.351523] |

The two-way covariance clusters by `USER_ID` and day and uses the user
covariance plus the day covariance minus their user-day intersection
covariance. Its p values and confidence intervals use a normal approximation.

Input data: `outputs/data/mc3_coh_seqn_future_has_correction_task_data.parquet`
