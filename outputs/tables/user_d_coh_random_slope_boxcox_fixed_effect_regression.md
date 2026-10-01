# Pooled random-slope fixed-effects regression

The model is

`Box-Cox(SECS)_ic = beta_seq * log(SEQN_i) + beta_future * FUTURE_SAME_ic + beta_correction * HAS_CORRECTION_ic + b_user * log(SEQN_i) + gamma_c + epsilon_ic`,

where `b_user` is a user-specific random slope with mean zero. Cells are
`USER_ID + D + COH` and their fixed effects are removed by within-cell
demeaning. `FUTURE_SAME` and `HAS_CORRECTION` retain common fixed slopes.
The random-slope fit uses REML and model-based standard errors.

| Quantity | Value |
|---|---:|
| Cells | 46,745 |
| Outcome | `Box-Cox(SECS)` |
| Input tasks before duration filter | 3,351,569 |
| Nonpositive-duration tasks removed | 0 |
| Tasks | 3,351,569 |
| Users | 331 |
| Days | 182 |
| Minimum SEQN | 1 |
| Maximum SEQN | 31 |
| `FUTURE_SAME = 1` tasks | 1,553,779 |
| Fraction with `HAS_CORRECTION = 1` | 0.281380 |
| Random user-slope SD (Box-Cox points) | 0.012172 |
| Residual SD (Box-Cox points) | 0.586995 |
| Marginal within R-squared | 0.034406 |
| Conditional within R-squared | 0.034579 |
| Conditional within-cell RMSE (Box-Cox points) | 0.586983 |
| Converged | True |

| Fixed term | Estimate (Box-Cox points) | Model-based SE | Statistic | p-value | 95% CI (Box-Cox points) |
|---|---:|---:|---:|---:|---:|
| LOG_SEQN | -0.026226 | 0.001020 | -25.705788 | 1.00707e-145 | [-0.028226, -0.024226] |
| FUTURE_SAME | -0.001878 | 0.000662 | -2.838343 | 0.00453484 | [-0.003176, -0.000581] |
| HAS_CORRECTION | 0.264260 | 0.000771 | 342.959563 | 0 | [0.262749, 0.265770] |

`USER_LOG_SEQN_SLOPE` in the companion user-effects file is the estimated
user-specific sequence slope: the population slope plus that user's random
slope deviation. These estimates are partially pooled toward the population
mean.

Input data: `outputs/data/user_d_coh_boxcox_duration_task_data.parquet`
