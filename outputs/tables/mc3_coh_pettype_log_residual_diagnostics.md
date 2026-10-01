# Joint log-duration residual diagnostics

Residuals are from the fixed-effects regression with `PAST_SAME` and
`FUTURE_SAME`, using cells defined as `USER_ID + D + MC3 + COH + PETTYPE`, after removing
nonpositive durations and modeling `log(SECS)`.

| Diagnostic | Value |
|---|---:|
| Residuals | 2,578,564 |
| Nonpositive durations removed | 0 |
| Mean | -0.000000 |
| Sample standard deviation | 0.943818 |
| Skewness | 1.250829 |
| Excess kurtosis | 2.711467 |

![Residual Q-Q plot](../charts/mc3-coh-pettype-fixed-effects/past_future_log_duration_residuals_qq.png)
