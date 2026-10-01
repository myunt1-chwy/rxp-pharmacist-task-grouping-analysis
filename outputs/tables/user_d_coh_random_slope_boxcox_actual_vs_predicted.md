# Actual versus predicted duration

The plot shows actual task duration against the model's conditional fitted
duration for `Box-Cox(SECS)`. Predictions add the cell mean of the modeled outcome back to the
conditional within-cell fit, then back-transform to seconds. Cells are
`USER_ID + D + COH`. Points are a reproducible random sample of the tasks;
both axes use logarithmic scales.

| Diagnostic | Value |
|---|---:|
| Tasks | 3,351,569 |
| Points plotted | 50,000 |
| Correlation, log actual vs. log predicted | 0.558477 |
| RMSE, log seconds | 0.758474 |
| Median actual duration (seconds) | 16.000000 |
| Median predicted duration (seconds) | 16.366452 |

![Actual versus predicted duration](../charts/user-d-coh-random-slope-fixed-effects/boxcox_actual_vs_predicted_duration.png)
