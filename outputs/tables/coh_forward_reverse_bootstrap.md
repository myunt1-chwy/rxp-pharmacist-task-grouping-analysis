# Coh-only forward and reverse bootstrap analysis

This analysis uses only `COH` as the similarity key and ignores `MC3` and
`PETTYPE`. Cells are `USER_ID + date + COH`. Each cell has at least one task in
both the same and different groups.

The forward analysis uses ascending time and ordinary `PAST_SAME`. The reverse
analysis assumes time runs backward by ordering tasks with
`PROCESS_START_TIME DESC, TASK_ID DESC`, then also uses ordinary `PAST_SAME`.
Complete cells are resampled with replacement for 10,000 bootstrap replicates,
using NumPy seed `20260930` separately for each direction.

| Direction | Cells | Tasks | Pooled delta (sec) | Bootstrap SE (sec) | 95% percentile CI (sec) |
|---|---:|---:|---:|---:|---:|
| Forward | 46,930 | 3,263,096 | -2.332108 | 0.204765 | [-2.742733, -1.939263] |
| Reverse time | 46,936 | 3,263,047 | -1.442142 | 0.212725 | [-1.848639, -1.013377] |

Both intervals exclude zero.

Cell-level sufficient statistics:

- `outputs/data/coh_forward_cell_stats.parquet`
- `outputs/data/coh_reverse_time_cell_stats.parquet`
