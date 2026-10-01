# Pooled random-slope fixed-effects regression

The model is

`log(SECS)_ic = beta_seq * log(SEQN_i) + beta_future * FUTURE_SAME_ic + beta_correction * HAS_CORRECTION_ic + b_user * log(SEQN_i) + gamma_c + epsilon_ic`,

where `b_user` is a user-specific random slope with mean zero. Cells are
`USER_ID + COH + MC3 + PETTYPE` and their fixed effects are removed by within-cell
demeaning. `FUTURE_SAME` and `HAS_CORRECTION` retain common fixed slopes.
The random-slope fit uses REML and model-based standard errors.

| Quantity | Value |
|---|---:|
| Cells | 8,491 |
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
| Random user-slope SD (log points) | 0.031065 |
| Residual SD (log points) | 0.974980 |
| Marginal within R-squared | 0.016958 |
| Conditional within R-squared | 0.017260 |
| Conditional within-cell RMSE (log points) | 0.974949 |
| Converged | True |

| Fixed term | Estimate (log points) | Model-based SE | Statistic | p-value | 95% CI (log points) |
|---|---:|---:|---:|---:|---:|
| LOG_SEQN | -0.069305 | 0.002413 | -28.720651 | 2.10724e-181 | [-0.074035, -0.064575] |
| FUTURE_SAME | -0.001997 | 0.001329 | -1.503032 | 0.132831 | [-0.004601, 0.000607] |
| HAS_CORRECTION | 0.289177 | 0.001415 | 204.357879 | 0 | [0.286404, 0.291951] |

`USER_LOG_SEQN_SLOPE` in the companion user-effects file is the estimated
user-specific sequence slope: the population slope plus that user's random
slope deviation. These estimates are partially pooled toward the population
mean.

Input data: `outputs/data/mc3_coh_pettype_seqn_future_has_correction_task_data.parquet`
