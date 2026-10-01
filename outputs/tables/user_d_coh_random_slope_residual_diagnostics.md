# Random-slope residual diagnostics

Residuals are conditional residuals for `log(SECS)` from the REML
random-slope model with
cells defined as `USER_ID + D + COH`. They account for the cell fixed effects
and each user's estimated random `log(SEQN)` slope.

| Diagnostic | Value |
|---|---:|
| Residuals | 3,527,087 |
| Mean | 0.000000 |
| Sample standard deviation | 0.957188 |
| Skewness | 1.243491 |
| Excess kurtosis | 2.588811 |

![Residual Q-Q plot](../charts/user-d-coh-random-slope-fixed-effects/log_duration_residuals_qq.png)
