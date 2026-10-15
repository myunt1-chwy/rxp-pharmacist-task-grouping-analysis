# Valid DUR processing time by handoff reason

| Handoff reason | Valid DUR tasks | Processing time (seconds) | Hours |
|---|---:|---:|---:|
| Missing | 3,614,021 | 178,089,090 | 49,469.19 |

`MY_RXP_VALID_DUR_TASKS` does not store `HANDOFF_REASON`, so the
[read-only query](../../src/sql/valid_dur_time_by_handoff_reason.sql) joins it
from `MY_RXP_TASKS` by user and task. Every valid task matched one source task;
no source task key was duplicated or had conflicting reasons. All joined
handoff reasons are null or blank. The valid-DUR definition excludes tasks
with a non-null `HANDOFF_TYPE`.
