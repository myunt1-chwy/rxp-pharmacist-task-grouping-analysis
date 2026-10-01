# MC3/cohort/pet-type reverse-time placebo bootstrap

This placebo assumes time runs in reverse. Tasks are ordered by
`PROCESS_START_TIME DESC, TASK_ID DESC`, and the ordinary `PAST_SAME` flag is
then calculated from the previous task in that reversed order. Therefore, the
reversed-time past task is the original future task.

`PAST_SAME = 1` means the reversed-time previous task matches the current
task's complete `MC3 + COH + PETTYPE` triplet. The cell is
`USER_ID + date + MC3 + COH + PETTYPE`. Cells with at least one observation in
each `PAST_SAME` group are included.

Complete cells are resampled with replacement. Each bootstrap replicate
recomputes the task-weighted pooled delta:

```text
sum(N1 × M1) / sum(N1) − sum(N0 × M0) / sum(N0)
```

The bootstrap uses 10,000 replicates and the fixed NumPy seed `20260930`.

| Metric | Result |
|---|---:|
| Cells | 59,203 |
| Tasks | 2,221,663 |
| Point estimate | 0.508232 seconds |
| Bootstrap SE | 0.227201 seconds |
| 95% percentile CI | [0.063468, 0.953249] seconds |
| 95% normal-approximation CI | [0.062919, 0.953546] seconds |

Cell-level sufficient statistics:
`outputs/data/mc3_coh_pettype_triplet_reverse_time_past_same_cell_stats.parquet`.
