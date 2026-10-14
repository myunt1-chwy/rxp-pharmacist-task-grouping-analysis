# DUR processing time Sankey values

Flow widths use imputed processing seconds. Node labels show hours rounded to
two decimal places. The first four stages use the existing
[handoff](my_rxp_tasks_handoff_type.md),
[intersection](dur_null_handoff_processing_time_by_intersection.md), and
[valid-DUR cutoff](test_model_final_dur_population_totals.md) aggregates.
The final split sums `duration_seconds` by `same_preceding` in
`data/test_model_final_log_data.parquet` (3,433,218 eligible tasks).

| Stage | Group | Processing time (seconds) | Hours |
|---|---|---:|---:|
| All DURs | All DURs | 212,095,618 | 58,915.45 |
| Handoff type | No handoff | 197,557,538 | 54,877.09 |
| Handoff type | Pharmacist follow-up | 13,334,300 | 3,703.97 |
| Handoff type | Technician follow-up | 820,191 | 227.83 |
| Handoff type | Lead follow-up | 383,589 | 106.55 |
| Simultaneous work among no-handoff DURs | Possible multitasking | 16,046,580 | 4,457.38 |
| Simultaneous work among no-handoff DURs | Singletasking | 181,510,958 | 50,419.71 |
| Non-overlapping no-handoff DURs | Other validity exclusions | 3,421,868 | 950.52 |
| Non-overlapping no-handoff DURs | At or above 156.608019-second cutoff | 88,958,419 | 24,710.67 |
| Non-overlapping no-handoff DURs | Below 156.608019-second cutoff | 89,130,671 | 24,758.52 |
| Below-cutoff model sample | SAME_PRECEDING = 1 | 37,917,597 | 10,532.67 |
| Below-cutoff model sample | SAME_PRECEDING = 0 | 51,213,074 | 14,225.85 |

`Possible multitasking` means a DUR overlaps another task for the same user;
that task need not be a DUR. `Singletasking` means no such overlap was
recorded. All stage sums reconcile in seconds.
