# Direct lifecycle fact DUR total above the model cutoff

Read-only Snowflake query run on 2026-10-14. This uses only
`EDLDB.PET_HEALTH_ANALYTICS_SANDBOX.FCT__TASKS_LIFECYCLE`: task creation
from 2026-02-01 inclusive to 2026-08-01 exclusive, `TASK_TYPE = 'DUR'`,
`HANDOFF_TYPE IS NULL`, and raw
`DWELL_IN_PROGRESS_TO_CLOSED_SECONDS > 156.608019` (integer durations of at
least 157 seconds). No employee, sequence, or valid-DUR joins or filters.

| Fact rows | Distinct user/task keys | Raw dwell seconds | Raw dwell hours |
|---:|---:|---:|---:|
| 200,468 | 200,468 | 99,126,769 | 27,535.21 |

This is 46 tasks and 22,768 seconds (6.32 hours) above the analogous
pharmacist-filtered null-handoff group. It also includes DURs that fail the
non-refill or no-overlap validity filters, so it has a broader population
than the 180,803 valid above-cutoff DURs.

[Exact SQL](../../src/sql/fact_lifecycle_dur_null_handoff_above_cutoff_total.sql)
