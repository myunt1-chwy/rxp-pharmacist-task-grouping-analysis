# Pooled random-slope fixed-effects regression

The model is

`log(SECS)_ic = beta_seq * log(SEQN_i) + beta_future * FUTURE_SAME_ic + beta_correction * HAS_CORRECTION_ic + b_user * log(SEQN_i) + gamma_c + epsilon_ic`,

where `b_user` is a user-specific random slope with mean zero. Cells are
`USER_ID + D + COH` and their fixed effects are removed by within-cell
demeaning. `FUTURE_SAME` and `HAS_CORRECTION` retain common fixed slopes.
The random-slope fit uses REML and model-based standard errors.

| Quantity | Value |
|---|---:|
| Cells | 47,609 |
| Outcome | `log(SECS)` |
| Input tasks before duration filter | 3,527,087 |
| Nonpositive-duration tasks removed | 0 |
| Tasks | 3,527,087 |
| Users | 334 |
| Days | 182 |
| Minimum SEQN | 1 |
| Maximum SEQN | 31 |
| `FUTURE_SAME = 1` tasks | 1,630,175 |
| Fraction with `HAS_CORRECTION = 1` | 0.283170 |
| Random user-slope SD (log points) | 0.019456 |
| Residual SD (log points) | 0.957208 |
| Marginal within R-squared | 0.021741 |
| Conditional within R-squared | 0.021903 |
| Conditional within-cell RMSE (log points) | 0.957189 |
| Converged | True |

| Fixed term | Estimate (log points) | Model-based SE | Statistic | p-value | 95% CI (log points) |
|---|---:|---:|---:|---:|---:|
| LOG_SEQN | -0.044353 | 0.001628 | -27.243796 | 1.96837e-163 | [-0.047544, -0.041162] |
| FUTURE_SAME | -0.005586 | 0.001052 | -5.307926 | 1.10879e-07 | [-0.007649, -0.003523] |
| HAS_CORRECTION | 0.337996 | 0.001223 | 276.419818 | 0 | [0.335599, 0.340393] |

`USER_LOG_SEQN_SLOPE` in the companion user-effects file is the estimated
user-specific sequence slope: the population slope plus that user's random
slope deviation. These estimates are partially pooled toward the population
mean.

Input data: `outputs/data/user_d_coh_seqn_future_has_correction_task_data.parquet`
