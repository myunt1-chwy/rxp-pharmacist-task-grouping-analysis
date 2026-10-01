# MC3/pet-type forward and reverse bootstrap analysis

This analysis uses `MC3 + PETTYPE` as the similarity key and defines cells as
`USER_ID + date + MC3 + PETTYPE`; cohort is not part of the match or cell key.
Each cell has at least one observation in both the same and different groups.

The forward analysis uses ascending time and ordinary `PAST_SAME`. The reverse
analysis assumes time runs backward by ordering tasks with
`PROCESS_START_TIME DESC, TASK_ID DESC`, then also uses ordinary `PAST_SAME`.
Complete cells are resampled with replacement for 10,000 bootstrap replicates,
using NumPy seed `20260930` separately for each direction.

| Direction | Cells | Tasks | Pooled delta (sec) | Bootstrap SE (sec) | 95% percentile CI (sec) |
|---|---:|---:|---:|---:|---:|
| Forward | 63,153 | 2,295,731 | -0.920754 | 0.221604 | [-1.351101, -0.488118] |
| Reverse time | 63,173 | 2,295,736 | 0.316352 | 0.227195 | [-0.123961, 0.768401] |

The forward interval excludes zero; the reverse-time interval includes zero.

Cell-level sufficient statistics:

- `outputs/data/mc3_pettype_forward_cell_stats.parquet`
- `outputs/data/mc3_pettype_reverse_time_cell_stats.parquet`
