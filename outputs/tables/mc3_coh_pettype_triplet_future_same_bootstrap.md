# MC3/cohort/pet-type future-similarity placebo bootstrap

This placebo compares each task with its next task instead of its previous
task. `FUTURE_SAME = 1` when the next task matches the current task's complete
`MC3 + COH + PETTYPE` triplet. The cell is still
`USER_ID + date + MC3 + COH + PETTYPE`.

The analysis keeps the same previous-and-next-neighbor eligibility as the
original analysis, then includes every mixed cell with at least one task in
each `FUTURE_SAME` group. Complete cells are resampled with replacement, and
each bootstrap replicate recomputes the task-weighted pooled delta:

```text
sum(N1 × M1) / sum(N1) − sum(N0 × M0) / sum(N0)
```

The bootstrap uses 10,000 replicates and the fixed NumPy seed `20260930`.

| Metric | Result |
|---|---:|
| Cells | 59,203 |
| Tasks | 2,221,663 |
| Point estimate | 0.508232 seconds |
| Bootstrap SE | 0.228737 seconds |
| 95% percentile CI | [0.073289, 0.958606] seconds |
| 95% normal-approximation CI | [0.059908, 0.956556] seconds |

Cell-level sufficient statistics:
`outputs/data/mc3_coh_pettype_triplet_future_same_cell_stats.parquet`.
