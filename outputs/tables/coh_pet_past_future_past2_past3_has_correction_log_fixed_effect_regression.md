# Pooled past/future fixed-effects regression

The model is

`log(SECS)_ic = alpha + beta_past * PAST_SAME_ic + beta_future * FUTURE_SAME_ic + beta_past2 * PAST_2_SAME_ic + beta_past3 * PAST_3_SAME_ic + beta_correction * HAS_CORRECTION_ic + gamma_c + epsilon_ic`.

Cells are `USER_ID + D + COH + PETTYPE`. The treatment indicators are included in
the same regression, so the `FUTURE_SAME` coefficient is estimated while
controlling for the original `PAST_SAME` treatment and the cell fixed effects.
The sample uses the original mixed-`PAST_SAME` cells. The fixed effects are
absorbed by within-cell demeaning.

| Quantity | Value |
|---|---:|
| Cells | 36,926 |
| Outcome | `log(SECS)` |
| Input tasks before duration filter | 2,724,850 |
| Nonpositive-duration tasks removed | 0 |
| Tasks | 2,724,850 |
| Users | 324 |
| Days | 181 |
| `PAST_SAME = 1` tasks | 130,787 |
| `FUTURE_SAME = 1` tasks | 130,813 |
| `PAST_2_SAME = 1` tasks | 5,249 |
| `PAST_3_SAME = 1` tasks | 566 |
| Fraction with `HAS_CORRECTION = 1` | 0.291604 |
| Within R-squared | 0.023197 |
| Within-cell RMSE (log points) | 0.940977 |

| Term | Estimate (log points) | Cell-clustered SE | User/day two-way SE | User/day statistic | User/day p value | User/day 95% CI (log points) |
|---|---:|---:|---:|---:|---:|---:|
| PAST_SAME | -0.206901 | 0.002821 | 0.011095 | -18.648301 | 1.30354e-77 | [-0.228647, -0.185155] |
| FUTURE_SAME | -0.004687 | 0.002726 | 0.003982 | -1.177087 | 0.239161 | [-0.012491, 0.003117] |
| PAST_2_SAME | -0.014752 | 0.014054 | 0.014567 | -1.012719 | 0.311194 | [-0.043304, 0.013799] |
| PAST_3_SAME | -0.082547 | 0.041148 | 0.043524 | -1.896592 | 0.0578817 | [-0.167854, 0.002760] |
| HAS_CORRECTION | 0.326910 | 0.001825 | 0.011181 | 29.238110 | 6.36009e-188 | [0.304995, 0.348825] |

The two-way covariance clusters by `USER_ID` and day and uses the user
covariance plus the day covariance minus their user-day intersection
covariance. Its p values and confidence intervals use a normal approximation.
The model includes `HAS_CORRECTION` as a binary task-level covariate. Its coefficient compares tasks with and without a correction.

Input data: `outputs/data/coh_pet_past_future_past2_past3_has_correction_task_data.parquet`
