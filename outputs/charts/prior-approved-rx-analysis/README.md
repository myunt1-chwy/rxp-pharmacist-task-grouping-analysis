# Prior approved prescription analysis

Valid DUR tasks are selected from `MY_RXP_VALID_DUR_TASKS` for Cohorts 1–4.
Durations at or above the global approximate 95th percentile are excluded.
`N_PRIOR_APPROVED_RX_IDS` is grouped as the number of distinct prescriptions approved before the task's process start time, excluding the current task prescription.
Each chart contains a horizontal boxplot for every count plus a final `Whole cohort` reference boxplot. Labels show filtered task counts, and dark-red lines show medians.
Cached task-level data is stored at `outputs/data/prior-approved-rx-analysis.parquet` for redraw-only runs.

## Cohort 1

![Cohort 1](prior-approved-rx-analysis-cohort-1.png)

## Cohort 2

![Cohort 2](prior-approved-rx-analysis-cohort-2.png)

## Cohort 3

![Cohort 3](prior-approved-rx-analysis-cohort-3.png)

## Cohort 4

![Cohort 4](prior-approved-rx-analysis-cohort-4.png)
