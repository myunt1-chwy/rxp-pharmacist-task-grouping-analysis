# Pooled random-slope fixed-effects regression

The model is

`log(SECS)_ic = beta_seq * log(SEQN_i) + beta_future * FUTURE_SAME_ic + beta_correction * HAS_CORRECTION_ic + b_user * log(SEQN_i) + gamma_c + epsilon_ic`,

where `b_user` is a user-specific random slope with mean zero. Cells are
`USER_ID + D + COH + PETTYPE` and their fixed effects are removed by within-cell
demeaning. `FUTURE_SAME` and `HAS_CORRECTION` retain common fixed slopes.
The random-slope fit uses REML and model-based standard errors.

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
| Random user-slope SD (log points) | 0.204601 |
| Residual SD (log points) | 0.940564 |
| Marginal within R-squared | 0.023099 |
| Conditional within R-squared | 0.024135 |
| Conditional within-cell RMSE (log points) | 0.940524 |
| Converged | True |

| Fixed term | Estimate (log points) | Model-based SE | Statistic | p-value | 95% CI (log points) |
|---|---:|---:|---:|---:|---:|
| LOG_SEQN | -0.343787 | 0.013501 | -25.464150 | 4.92141e-143 | [-0.370249, -0.317326] |
| FUTURE_SAME | -0.005506 | 0.002699 | -2.040187 | 0.0413317 | [-0.010796, -0.000216] |
| HAS_CORRECTION | 0.326896 | 0.001346 | 242.820400 | 0 | [0.324257, 0.329534] |

`USER_LOG_SEQN_SLOPE` in the companion user-effects file is the estimated
user-specific sequence slope: the population slope plus that user's random
slope deviation. These estimates are partially pooled toward the population
mean.

Input data: `outputs/data/coh_pet_seqn_future_has_correction_task_data.parquet`
