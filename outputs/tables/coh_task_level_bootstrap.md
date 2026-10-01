# COH-only mixed-cell task-level bootstrap

This analysis uses only tasks from mixed `USER_ID + date + COH` cells. A mixed
cell has at least one task in each `PAST_SAME` group. For each direction, tasks
are resampled with replacement separately within the `PAST_SAME = 1` and
`PAST_SAME = 0` groups. This is a task-level bootstrap and treats task rows as
the sampling units; it does not resample cells.

The bootstrap uses 1,000 replicates and the fixed NumPy seed `20260930`.

| Direction | Mixed cells | Tasks | Same tasks | Different tasks | Point delta (sec) | Bootstrap SE (sec) | 95% percentile CI (sec) |
|---|---:|---:|---:|---:|---:|---:|
| Forward | 46,930 | 3,263,096 | 1,544,934 | 1,718,162 | -2.332108 | 0.197506 | [-2.717766, -1.956542] |
| Reverse time | 46,936 | 3,263,047 | 1,544,940 | 1,718,107 | -1.442142 | 0.210106 | [-1.848068, -1.036477] |

Task-level input data:

- `outputs/data/coh_forward_task_data_mixed.parquet`
- `outputs/data/coh_reverse_task_data_mixed.parquet`
