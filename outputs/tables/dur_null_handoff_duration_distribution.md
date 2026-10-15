# DUR processing-time distribution with NULL handoff type

Read-only Snowflake queries run on 2026-10-14. Processing time is
`IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS` in
`EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASKS`, where a missing raw
duration is replaced with one second. The 156.608019-second boundary is the
model's approximate P95 cutoff; durations are integer seconds, so the first
above-cutoff bucket begins at 157 seconds.

## All DURs with `HANDOFF_TYPE IS NULL` in `MY_RXP_TASKS`

| Processing time | DURs | Total seconds | Total hours | Share of hours |
|---|---:|---:|---:|---:|
| 0 seconds | 169 | 0 | 0.00 | 0.00% |
| 1–29 seconds | 2,755,763 | 35,373,847 | 9,826.07 | 17.91% |
| 30–59 seconds | 648,580 | 26,838,581 | 7,455.16 | 13.59% |
| 60–119 seconds | 326,931 | 26,858,473 | 7,460.69 | 13.60% |
| 120–156 seconds | 68,893 | 9,382,636 | 2,606.29 | 4.75% |
| 157–299 seconds | 99,288 | 21,106,853 | 5,863.01 | 10.68% |
| 300–599 seconds | 57,294 | 23,939,889 | 6,649.97 | 12.12% |
| 600–1,799 seconds | 36,085 | 34,057,552 | 9,460.43 | 17.24% |
| 1,800–3,599 seconds | 7,702 | 19,283,449 | 5,356.51 | 9.76% |
| 3,600–14,399 seconds | 47 | 320,125 | 88.92 | 0.16% |
| 14,400+ seconds | 6 | 396,133 | 110.04 | 0.20% |
| **Total** | **4,000,758** | **197,557,538** | **54,877.09** | **100%** |

The 200,422 null-handoff DURs at or above the cutoff contribute 99,104,001
seconds (27,528.89 hours). They are 5.01% of tasks and 50.16% of hours in
this full null-handoff population. There are 8,427 imputed raw durations,
169 zero-second durations, and 4,000,758 distinct `(USER_ID, TASK_ID)` keys.
The overall median is 17 seconds; mean 49.38 seconds; approximate P95
156.82 seconds; maximum 159,582 seconds.

## Valid DURs at or above the model cutoff

This is the narrower population behind the report's 180,803-task,
24,710.67-hour figure. Validity also requires positive non-null raw dwell,
no refill, and no intersecting task. The buckets sum exactly to the reported
88,958,419 seconds. The median is 302 seconds; mean 492.02 seconds;
approximate P90 999.42 seconds; approximate P95 1,508.45 seconds;
maximum 159,582 seconds. All 180,803 task keys are distinct.

| Processing time | DURs | Total seconds | Total hours | Share of hours |
|---|---:|---:|---:|---:|
| 157–299 seconds | 89,445 | 19,020,675 | 5,283.52 | 21.38% |
| 300–599 seconds | 51,808 | 21,634,355 | 6,009.54 | 24.32% |
| 600–1,799 seconds | 32,675 | 30,788,816 | 8,552.45 | 34.61% |
| 1,800–3,599 seconds | 6,838 | 17,114,397 | 4,754.00 | 19.24% |
| 3,600–14,399 seconds | 35 | 222,182 | 61.72 | 0.25% |
| 14,400+ seconds | 2 | 177,994 | 49.44 | 0.20% |
| **Total** | **180,803** | **88,958,419** | **24,710.67** | **100%** |

## Cohort breakdown of the above-cutoff groups

| Cohort | Valid DURs | Valid seconds | Valid hours | Share of valid hours | All null-handoff DURs | All null-handoff hours |
|---|---:|---:|---:|---:|---:|---:|
| Cohort 1 | 85,128 | 43,150,499 | 11,986.25 | 48.51% | 94,248 | 13,356.18 |
| Cohort 2 | 77,361 | 37,781,018 | 10,494.73 | 42.47% | 83,776 | 11,399.81 |
| Cohort 3 | 13,927 | 6,173,636 | 1,714.90 | 6.94% | 14,756 | 1,828.91 |
| Cohort 4 | 2,157 | 844,316 | 234.53 | 0.95% | 3,935 | 447.01 |
| Unknown | 2,230 | 1,008,950 | 280.26 | 1.13% | 3,707 | 496.98 |
| **Total** | **180,803** | **88,958,419** | **24,710.67** | **100%** | **200,422** | **27,528.89** |

Cohort 1 is boxed parasiticides; Cohort 2 is non-controlled, non-boxed
medications; Cohort 3 is non-controlled compounded medications; Cohort 4 is
the gabapentin workflow. These definitions come from the
[report appendix](../../src/latex/appendix/cohort_definitions.tex).

These are summed in-progress-to-closed dwell durations. The queries establish
the arithmetic and task-key uniqueness; they do not establish that every
elapsed second was active pharmacist work.

## Reproduction from the original lifecycle fact

The [fact histogram query](../../src/sql/fact_lifecycle_dur_null_handoff_duration_distribution.sql)
reads `EDLDB.PET_HEALTH_ANALYTICS_SANDBOX.FCT__TASKS_LIFECYCLE` directly. It
uses the same latest-employee pharmacist filter and task-created date window
(`2026-02-01` inclusive through `2026-08-01` exclusive) as the
`MY_RXP_TASKS` build, with `TASK_TYPE = 'DUR'`, `HANDOFF_TYPE IS NULL`, and
`COALESCE(raw dwell seconds, 1)`. Its 11 bucket counts and second totals
match the full-population table above exactly. The
[fact cohort query](../../src/sql/fact_lifecycle_dur_null_handoff_by_cohort.sql)
also reproduces the above-cutoff cohort totals exactly: 200,422 tasks and
99,104,001 seconds (27,528.89 hours).

The [valid-filter fact query](../../src/sql/fact_lifecycle_valid_dur_tail_by_cohort_filters.sql)
uses raw lifecycle durations, null handoff, non-refill status, and the existing
task-overlap summary to select the narrower valid above-cutoff group. It
reproduces each cohort in the valid table above exactly: 180,803 distinct
tasks and 88,958,419 raw seconds (24,710.67 hours). It does not use the
valid-DUR table for membership. A separate
[task-key cross-check](../../src/sql/fact_lifecycle_valid_dur_tail_by_cohort.sql)
matched all 180,803 valid task keys to lifecycle facts, with zero null raw
durations, zero duration mismatches, and zero cohort mismatches. The overlap
summary is derived from the task table, so that part of the validity check is
not independent of the task pipeline.

Sources: [duration buckets](../../src/sql/dur_null_handoff_duration_distribution.sql),
[summary and task-key check](../../src/sql/dur_null_handoff_duration_summary.sql),
and [cohort breakdown](../../src/sql/dur_null_handoff_above_cutoff_by_cohort.sql).
