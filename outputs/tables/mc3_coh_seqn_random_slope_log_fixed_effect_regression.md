# Pooled random-slope fixed-effects regression

The model is

`log(SECS)_ic = beta_seq * log(SEQN_i) + beta_future * FUTURE_SAME_ic + beta_correction * HAS_CORRECTION_ic + b_user * log(SEQN_i) + gamma_c + epsilon_ic`,

where `b_user` is a user-specific random slope with mean zero. Cells are
`USER_ID + D + COH + MC3` and their fixed effects are removed by within-cell
demeaning. `FUTURE_SAME` and `HAS_CORRECTION` retain common fixed slopes.
The random-slope fit uses REML and model-based standard errors.

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
| Random user-slope SD (log points) | 0.026233 |
| Residual SD (log points) | 0.941221 |
| Marginal within R-squared | 0.020991 |
| Conditional within R-squared | 0.021250 |
| Conditional within-cell RMSE (log points) | 0.941194 |
| Converged | True |

| Fixed term | Estimate (log points) | Model-based SE | Statistic | p-value | 95% CI (log points) |
|---|---:|---:|---:|---:|---:|
| LOG_SEQN | -0.058693 | 0.002072 | -28.326110 | 1.64854e-176 | [-0.062754, -0.054631] |
| FUTURE_SAME | -0.004045 | 0.001249 | -3.238595 | 0.0012012 | [-0.006493, -0.001597] |
| HAS_CORRECTION | 0.329228 | 0.001384 | 237.934395 | 0 | [0.326516, 0.331940] |

`USER_LOG_SEQN_SLOPE` in the companion user-effects file is the estimated
user-specific sequence slope: the population slope plus that user's random
slope deviation. These estimates are partially pooled toward the population
mean.

Input data: `outputs/data/mc3_coh_seqn_future_has_correction_task_data.parquet`
