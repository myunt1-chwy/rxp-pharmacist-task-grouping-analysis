# Pooled past/future fixed-effects regression

The model is

`log(SECS)_ic = alpha + beta_past * PAST_SAME_ic + beta_future * FUTURE_SAME_ic + beta_past2 * PAST_2_SAME_ic + beta_correction * HAS_CORRECTION_ic + gamma_c + epsilon_ic`.

Cells are `USER_ID + D + COH`. Both treatment indicators are included in
the same regression, so the `FUTURE_SAME` coefficient is estimated while
controlling for the original `PAST_SAME` treatment and the cell fixed effects.
The sample uses the original mixed-`PAST_SAME` cells. The fixed effects are
absorbed by within-cell demeaning.

| Quantity | Value |
|---|---:|
| Cells | 47,609 |
| Outcome | `log(SECS)` |
| Input tasks before duration filter | 3,527,212 |
| Nonpositive-duration tasks removed | 125 |
| Tasks | 3,527,087 |
| Users | 334 |
| Days | 182 |
| `PAST_SAME = 1` tasks | 1,630,118 |
| `FUTURE_SAME = 1` tasks | 1,630,175 |
| `PAST_2_SAME = 1` tasks | 794,244 |
| Fraction with `HAS_CORRECTION = 1` | 0.283170 |
| Within R-squared | 0.021779 |
| Within-cell RMSE (log points) | 0.957250 |

| Term | Estimate (log points) | Cell-clustered SE | User/day two-way SE | User/day statistic | User/day p value | User/day 95% CI (log points) |
|---|---:|---:|---:|---:|---:|---:|
| PAST_SAME | -0.042907 | 0.001251 | 0.002538 | -16.907344 | 3.97209e-64 | [-0.047881, -0.037933] |
| FUTURE_SAME | -0.005533 | 0.001065 | 0.001179 | -4.692880 | 2.69385e-06 | [-0.007844, -0.003222] |
| PAST_2_SAME | -0.010339 | 0.001531 | 0.001796 | -5.757204 | 8.55184e-09 | [-0.013859, -0.006819] |
| HAS_CORRECTION | 0.337983 | 0.001671 | 0.010822 | 31.230952 | 4.05034e-214 | [0.316772, 0.359194] |

The two-way covariance clusters by `USER_ID` and day and uses the user
covariance plus the day covariance minus their user-day intersection
covariance. Its p values and confidence intervals use a normal approximation.
The model includes `HAS_CORRECTION` as a binary task-level covariate. Its coefficient compares tasks with and without a correction.

Input data: `outputs/data/coh_past_future_past2_has_correction_task_data.parquet`
