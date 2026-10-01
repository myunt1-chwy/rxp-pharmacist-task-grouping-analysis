# Pooled random-slope fixed-effects regression

The model is

`Box-Cox(SECS), lambda=-0.256993_ic = beta_seq * log(SEQN_i) + beta_future * FUTURE_SAME_ic + beta_correction * HAS_CORRECTION_ic + b_user * log(SEQN_i) + gamma_c + epsilon_ic`,

where `b_user` is a user-specific random slope with mean zero. Cells are
`USER_ID + D + COH + MC3 + PETTYPE` and their fixed effects are removed by within-cell
demeaning. `FUTURE_SAME` and `HAS_CORRECTION` retain common fixed slopes.
The random-slope fit uses REML and model-based standard errors.

| Quantity | Value |
|---|---:|
| Cells | 83,953 |
| Outcome | `Box-Cox(SECS), lambda=-0.256993` |
| Input tasks before duration filter | 2,578,564 |
| Nonpositive-duration tasks removed | 0 |
| Tasks | 2,578,564 |
| Users | 332 |
| Days | 182 |
| Minimum SEQN | 1 |
| Maximum SEQN | 21 |
| `FUTURE_SAME = 1` tasks | 997,973 |
| Fraction with `HAS_CORRECTION = 1` | 0.277826 |
| Random user-slope SD (Box-Cox points) | 0.013907 |
| Residual SD (Box-Cox points) | 0.407125 |
| Marginal within R-squared | 0.027945 |
| Conditional within R-squared | 0.028283 |
| Conditional within-cell RMSE (Box-Cox points) | 0.407112 |
| Converged | True |

| Fixed term | Estimate (Box-Cox points) | Model-based SE | Statistic | p-value | 95% CI (Box-Cox points) |
|---|---:|---:|---:|---:|---:|
| LOG_SEQN | -0.030820 | 0.001060 | -29.086722 | 5.28509e-186 | [-0.032897, -0.028743] |
| FUTURE_SAME | -0.000471 | 0.000560 | -0.839796 | 0.401023 | [-0.001569, 0.000628] |
| HAS_CORRECTION | 0.165966 | 0.000623 | 266.219122 | 0 | [0.164744, 0.167188] |

`USER_LOG_SEQN_SLOPE` in the companion user-effects file is the estimated
user-specific sequence slope: the population slope plus that user's random
slope deviation. These estimates are partially pooled toward the population
mean.

Input data: `outputs/data/mc3_coh_pettype_boxcox_duration_task_data.parquet`
