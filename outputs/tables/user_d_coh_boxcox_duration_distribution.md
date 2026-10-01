# Box-Cox duration transformation

The positive duration outcome was transformed as

`(SECS^lambda - 1) / lambda`

with estimated `lambda = -0.08721436`. The transformed data are saved
with the original task fields and the `BOXCOX_SECS` column.

| Diagnostic | Value |
|---|---:|
| Tasks | 3,351,569 |
| Box-Cox lambda | -0.08721436 |
| Mean | 2.467210 |
| Median | 2.462832 |
| Standard deviation | 0.712219 |
| Skewness | 0.013237 |
| Excess kurtosis | -0.481799 |
| 1st percentile | 1.047622 |
| 25th percentile | 1.999525 |
| 75th percentile | 2.967471 |
| 99th percentile | 3.981177 |

![Box-Cox transformed duration distribution](../charts/user-d-coh-random-slope-fixed-effects/boxcox_duration_distribution.png)

Input data: `outputs/data/user_d_coh_seqn_future_has_correction_task_data.parquet`
Transformed data: `outputs/data/user_d_coh_boxcox_duration_task_data.parquet`
