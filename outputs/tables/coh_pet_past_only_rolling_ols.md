# Pooled past-only rolling OLS

The model uses

`log(SECS)_ic = beta_seq * log(SEQN_i) + beta_future * FUTURE_SAME_ic + beta_correction * HAS_CORRECTION_ic + epsilon_ic`.

For each cell, every variable is transformed by subtracting its expanding
mean over strictly prior tasks in that cell, ordered by
`PROCESS_START_TIME, TASK_ID`. The first task in each cell is excluded because
it has no past-only mean. This is a sequential baseline transformation rather
than standard full-sample fixed-effects demeaning, so no future task values
enter a current task's rolling means. `FUTURE_SAME` remains as an intentionally
future-derived placebo covariate.

Cells are `USER_ID + D + COH + PETTYPE`. The two-way covariance clusters by `USER_ID`
and day and uses the user covariance plus the day covariance minus their
user-day intersection covariance. Its p values and confidence intervals use
a normal approximation.

| Quantity | Value |
|---|---:|
| Cells before first-task exclusion | 36,926 |
| Cells used | 36,926 |
| Outcome | `log(SECS)` |
| Input tasks before duration filter | 2,724,850 |
| Nonpositive-duration tasks removed | 0 |
| First tasks excluded | 36,926 |
| Tasks used | 2,687,924 |
| Users | 324 |
| Days | 181 |
| Minimum SEQN | 1 |
| Maximum SEQN | 7 |
| `FUTURE_SAME = 1` tasks | 127,521 |
| Fraction with `HAS_CORRECTION = 1` | 0.291558 |
| Within R-squared | 0.023236 |
| Within-cell RMSE (log points) | 0.976912 |

| Term | Estimate (log points) | Cell-clustered SE | User/day two-way SE | User/day statistic | User/day p value | User/day 95% CI (log points) |
|---|---:|---:|---:|---:|---:|---:|
| LOG_SEQN | -0.294113 | 0.003993 | 0.015802 | -18.611780 | 2.57906e-77 | [-0.325085, -0.263140] |
| FUTURE_SAME | -0.004574 | 0.002775 | 0.004068 | -1.124193 | 0.260931 | [-0.012548, 0.003400] |
| HAS_CORRECTION | 0.327345 | 0.001819 | 0.011076 | 29.553521 | 5.91733e-192 | [0.305635, 0.349055] |

Input data: `outputs/data/coh_pet_seqn_future_has_correction_with_start_time.parquet`

Transformed data: `outputs/data/coh_pet_past_only_rolling_transformed_task_data.parquet`
