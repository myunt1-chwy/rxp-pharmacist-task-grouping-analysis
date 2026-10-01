# MC3/cohort/pet-type pooled delta cluster bootstrap — all mixed cells

This bootstrap includes every cell with at least one observation in each
`PAST_SAME` group. It does not require two observations per group because the
bootstrap uses cell counts and means; within-cell `STDDEV_SAMP` values are not
calculated in this variant.

Complete cells are resampled with replacement. Each replicate recomputes the
task-weighted pooled delta:

```text
sum(N1 × M1) / sum(N1) − sum(N0 × M0) / sum(N0)
```

The bootstrap uses 10,000 replicates and the fixed NumPy seed `20260930`.

| Metric | Result |
|---|---:|
| Cells | 59,183 |
| Tasks | 2,221,682 |
| Point estimate | -0.770196 seconds |
| Bootstrap SE | 0.223571 seconds |
| 95% percentile CI | [-1.208580, -0.321773] seconds |
| 95% normal-approximation CI | [-1.208396, -0.331996] seconds |

Cell-level sufficient statistics:
`outputs/data/mc3_coh_pettype_triplet_cell_stats_all_mixed.parquet`.
