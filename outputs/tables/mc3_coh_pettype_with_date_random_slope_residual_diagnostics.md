# Random-slope residual diagnostics

Residuals are conditional residuals from the REML random-slope model with
cells defined as `USER_ID + D + COH + MC3 + PETTYPE`. They account for the cell fixed effects
and each user's estimated random `log(SEQN)` slope.

| Diagnostic | Value |
|---|---:|
| Residuals | 2,578,564 |
| Mean | -0.000000 |
| Sample standard deviation | 0.934747 |
| Skewness | 1.308275 |
| Excess kurtosis | 2.896719 |

![Residual Q-Q plot](../charts/mc3-coh-pettype-random-slope-fixed-effects/log_duration_residuals_qq.png)
