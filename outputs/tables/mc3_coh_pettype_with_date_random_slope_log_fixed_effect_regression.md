# Pooled random-slope fixed-effects regression

The model is

`log(SECS)_ic = beta_seq * log(SEQN_i) + beta_future * FUTURE_SAME_ic + beta_correction * HAS_CORRECTION_ic + b_user * log(SEQN_i) + gamma_c + epsilon_ic`,

where `b_user` is a user-specific random slope with mean zero. Cells are
`USER_ID + D + COH + MC3 + PETTYPE` and their fixed effects are removed by within-cell
demeaning. `FUTURE_SAME` and `HAS_CORRECTION` retain common fixed slopes.
The random-slope fit uses REML and model-based standard errors.

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
| Random user-slope SD (log points) | 0.032203 |
| Residual SD (log points) | 0.934779 |
| Marginal within R-squared | 0.020073 |
| Conditional within R-squared | 0.020398 |
| Conditional within-cell RMSE (log points) | 0.934748 |
| Converged | True |

| Fixed term | Estimate (log points) | Model-based SE | Statistic | p-value | 95% CI (log points) |
|---|---:|---:|---:|---:|---:|
| LOG_SEQN | -0.069435 | 0.002455 | -28.279286 | 6.21406e-176 | [-0.074247, -0.064622] |
| FUTURE_SAME | -0.002436 | 0.001287 | -1.893717 | 0.0582625 | [-0.004958, 0.000085] |
| HAS_CORRECTION | 0.319685 | 0.001431 | 223.337791 | 0 | [0.316880, 0.322491] |

`USER_LOG_SEQN_SLOPE` in the companion user-effects file is the estimated
user-specific sequence slope: the population slope plus that user's random
slope deviation. These estimates are partially pooled toward the population
mean.

Input data: `outputs/data/mc3_coh_pettype_seqn_future_has_correction_task_data.parquet`
