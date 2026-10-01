# Joint log-duration residual diagnostics

Residuals are from the fixed-effects regression with `PAST_SAME` and
`FUTURE_SAME`, after removing nonpositive durations and modeling `log(SECS)`.

| Diagnostic | Value |
|---|---:|
| Residuals | 3,527,087 |
| Nonpositive durations removed | 125 |
| Mean | 0.000000 |
| Sample standard deviation | 0.967567 |
| Skewness | 1.181972 |
| Excess kurtosis | 2.400379 |

![Residual Q-Q plot](../charts/coh-past-future-fixed-effects/past_future_log_duration_residuals_qq.png)
