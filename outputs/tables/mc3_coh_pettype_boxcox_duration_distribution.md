# Box-Cox duration transformation

The positive duration outcome was transformed as

`(SECS^lambda - 1) / lambda`

with estimated `lambda = -0.25699295`. The transformed data are saved
with the original task fields and the `BOXCOX_SECS` column.

| Diagnostic | Value |
|---|---:|
| Tasks | 2,578,564 |
| Box-Cox lambda | -0.25699295 |
| Mean | 1.961155 |
| Median | 1.951024 |
| Standard deviation | 0.493951 |
| Skewness | 0.010417 |
| Excess kurtosis | -0.045158 |
| 1st percentile | 0.957145 |
| 25th percentile | 1.610862 |
| 75th percentile | 2.294301 |
| 99th percentile | 3.130047 |

![Box-Cox transformed duration distribution](../charts/mc3-coh-pettype-random-slope-fixed-effects/boxcox_duration_distribution.png)

Input data: `outputs/data/mc3_coh_pettype_seqn_future_has_correction_task_data.parquet`
Transformed data: `outputs/data/mc3_coh_pettype_boxcox_duration_task_data.parquet`
