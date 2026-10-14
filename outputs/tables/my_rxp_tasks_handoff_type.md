# Handoff types for DUR tasks in MY_RXP_TASKS

| Handoff type | DUR tasks | Processing time (seconds) | Hours |
|---|---:|---:|---:|
| NULL | 4,000,758 | 197,557,538 | 54,877.09 |
| PHARMACIST_FOLLOW_UP | 117,503 | 13,334,300 | 3,703.97 |
| TECHNICIAN_FOLLOW_UP | 6,736 | 820,191 | 227.83 |
| LEAD_FOLLOW_UP | 3,489 | 383,589 | 106.55 |
| **All DURs** | **4,128,486** | **212,095,618** | **58,915.45** |

The [read-only query](../../src/sql/my_rxp_tasks_handoff_type.sql) also
includes the 17 non-DUR rows in `MY_RXP_TASKS`. The valid-DUR definition
requires `HANDOFF_TYPE IS NULL`, so its handoff-type breakdown has only a
missing-value group. A separate check found no blank handoff types among DURs.
