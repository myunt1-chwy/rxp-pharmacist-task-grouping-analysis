# DUR processing time by intersection status

| Intersection status | DUR tasks | Processing time (seconds) | Hours |
|---|---:|---:|---:|
| Intersecting | 343,431 | 17,333,579 | 4,814.88 |
| Not intersecting | 3,785,055 | 194,762,039 | 54,100.57 |
| **All DURs** | **4,128,486** | **212,095,618** | **58,915.45** |

An intersecting DUR has `N_INTERSECTING_TASKS > 0` in
`MY_RXP_TASKS_WITH_SEQUENCE`: its processing interval overlaps at least one
other task for the same user. The [read-only query](../../src/sql/dur_processing_time_by_intersection.sql)
includes every DUR in `MY_RXP_TASKS`, without the model's validity or
duration-cutoff filters. Every DUR had a sequence record.
