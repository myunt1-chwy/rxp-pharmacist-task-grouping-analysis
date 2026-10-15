# DUR population totals

| DUR population | Number of DURs | Total processing time (seconds) | Hours |
|---|---:|---:|---:|
| Valid DURs below 156.608019 seconds | 3,433,218 | 89,130,671 | 24,758.52 |
| Valid DURs at or above 156.608019 seconds | 180,803 | 88,958,419 | 24,710.67 |
| **All valid DURs** in `MY_RXP_VALID_DUR_TASKS` | **3,614,021** | **178,089,090** | **49,469.19** |
| Other non-intersecting DURs excluded by validity checks | 54,138 | 3,421,868 | 950.52 |
| **All non-intersecting DURs with NULL handoff type** | **3,668,159** | **181,510,958** | **50,419.71** |
| All DURs below 156.608019 seconds in `MY_RXP_TASKS` | 3,905,692 | 104,384,954 | 28,995.82 |
| **All DURs** in `MY_RXP_TASKS` | **4,128,486** | **212,095,618** | **58,915.45** |

The first two rows partition the valid-DUR table at the model cutoff;
the valid tasks below it are the 3,433,218-task model sample.
The 54,138 other non-intersecting tasks and 3,421,868 seconds are the difference
between the null-handoff non-intersecting population
and the valid-DUR table; the available aggregate does not
separate their individual exclusion reasons. The full-table
below-cutoff row also includes 472,474 other DUR tasks totaling
15,254,283 seconds that did not meet the valid-DUR criteria.

[Null-handoff intersection source query](../../src/sql/dur_null_handoff_processing_time_by_intersection.sql)
