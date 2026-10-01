# MC3/cohort/pet-type pooled delta cluster bootstrap

The bootstrap resamples complete user/date/MC3/cohort/pet-type cells with
replacement. Each sampled replicate recomputes the task-weighted pooled delta:

```text
sum(N1 × M1) / sum(N1) − sum(N0 × M0) / sum(N0)
```

The bootstrap uses 10,000 replicates and the fixed NumPy seed `20260930`.
Cells were restricted to those with at least two observations in both
`PAST_SAME = 1` and `PAST_SAME = 0` groups.

| Metric | Result |
|---|---:|
| Cells | 32,052 |
| Point estimate | -0.003992 seconds |
| Bootstrap SE | 0.224188 seconds |
| 95% percentile CI | [-0.445549, 0.438406] seconds |
| 95% normal-approximation CI | [-0.443400, 0.435417] seconds |

Cell-level sufficient statistics: `outputs/data/mc3_coh_pettype_triplet_cell_stats.parquet`.
