# DUR processing time by intersection status, NULL handoff type

| Intersection status | DUR tasks | Processing time (seconds) | Hours |
|---|---:|---:|---:|
| Intersecting | 332,599 | 16,046,580 | 4,457.38 |
| Not intersecting | 3,668,159 | 181,510,958 | 50,419.71 |
| **All DURs with NULL handoff type** | **4,000,758** | **197,557,538** | **54,877.09** |

An intersecting task has `N_INTERSECTING_TASKS > 0` in
`MY_RXP_TASKS_WITH_SEQUENCE`. The [read-only query](../../src/sql/dur_null_handoff_processing_time_by_intersection.sql)
filters `MY_RXP_TASKS` to DUR rows with `HANDOFF_TYPE IS NULL` and applies no
other validity or duration-cutoff filters. Every selected DUR had a sequence
record.
