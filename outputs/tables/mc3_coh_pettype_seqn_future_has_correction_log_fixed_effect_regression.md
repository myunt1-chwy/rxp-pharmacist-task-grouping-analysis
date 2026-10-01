# Pooled log-sequence fixed-effects regression

The model is

`log(SECS)_ic = alpha + beta_seq * log(SEQN_i) + beta_future * FUTURE_SAME_ic + beta_correction * HAS_CORRECTION_ic + gamma_c + epsilon_ic`.

Cells are `USER_ID + D + MC3 + COH + PETTYPE`. The sequence effect is modeled continuously
as `log(SEQN)`, while `FUTURE_SAME` and `HAS_CORRECTION` are retained as
task-level covariates. The fixed effects are absorbed by within-cell
demeaning. The input SQL retains the mixed-cell sample used in the prior
COH-PETTYPE analysis.

| Quantity | Value |
|---|---:|
| Cells | 83,953 |
| Outcome | `log(SECS)` |
| Input tasks before duration filter | 2,578,564 |
| Nonpositive-duration tasks removed | 0 |
| Tasks | 2,578,564 |
| Users | 332 |
| Days | 182 |
| Minimum SEQN | 1 |
| Maximum SEQN | 21 |
| `FUTURE_SAME = 1` tasks | 997,973 |
| Fraction with `HAS_CORRECTION = 1` | 0.277826 |
| Within R-squared | 0.020080 |
| Within-cell RMSE (log points) | 0.934900 |

| Term | Estimate (log points) | Cell-clustered SE | User/day two-way SE | User/day statistic | User/day p value | User/day 95% CI (log points) |
|---|---:|---:|---:|---:|---:|---:|
| LOG_SEQN | -0.064381 | 0.001306 | 0.002903 | -22.180512 | 5.29721e-109 | [-0.070070, -0.058692] |
| FUTURE_SAME | -0.002339 | 0.001324 | 0.001546 | -1.512307 | 0.130456 | [-0.005370, 0.000692] |
| HAS_CORRECTION | 0.319658 | 0.001919 | 0.011367 | 28.122202 | 5.2439e-174 | [0.297379, 0.341937] |

The two-way covariance clusters by `USER_ID` and day and uses the user
covariance plus the day covariance minus their user-day intersection
covariance. Its p values and confidence intervals use a normal approximation.

Input data: `outputs/data/mc3_coh_pettype_seqn_future_has_correction_task_data.parquet`
