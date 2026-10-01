# Random-slope residual diagnostics

Residuals are conditional residuals for `Box-Cox(SECS)` from the REML
random-slope model with
cells defined as `USER_ID + D + COH`. They account for the cell fixed effects
and each user's estimated random `log(SEQN)` slope.

| Diagnostic | Value |
|---|---:|
| Residuals | 3,351,569 |
| Mean | -0.000000 |
| Sample standard deviation | 0.586983 |
| Skewness | 0.505550 |
| Excess kurtosis | 0.225295 |

![Residual Q-Q plot](../charts/user-d-coh-random-slope-fixed-effects/boxcox_duration_residuals_qq.png)
