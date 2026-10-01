# Actual versus predicted duration

The plot shows actual task duration against the model's conditional fitted
duration. Predictions add the cell mean of `log(SECS)` back to the conditional
within-cell fit, then exponentiate to return to seconds. Cells are
`USER_ID + D + COH`. Points are a reproducible random sample of the tasks;
both axes use logarithmic scales.

| Diagnostic | Value |
|---|---:|
| Tasks | 3,527,087 |
| Points plotted | 50,000 |
| Correlation, log actual vs. log predicted | 0.520434 |
| RMSE, log seconds | 0.957188 |
| Median actual duration (seconds) | 17.000000 |
| Median predicted duration (seconds) | 19.266450 |

![Actual versus predicted duration](../charts/user-d-coh-random-slope-fixed-effects/actual_vs_predicted_duration.png)
