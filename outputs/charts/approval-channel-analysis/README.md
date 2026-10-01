# Approval channel analysis

Valid DUR tasks are selected from `MY_RXP_VALID_DUR_TASKS` for Cohorts 1–4.
Durations at or above the global approximate 95th percentile are excluded.
Null or blank `APPROVAL_CHANNEL` values are shown as `<Missing>`.
Each chart contains a horizontal boxplot for every approval channel plus a final `Whole cohort` reference boxplot. Labels show filtered task counts, and dark-red lines show medians.
Cached task-level data is stored at `outputs/data/approval-channel-analysis.parquet` for redraw-only runs.

## Cohort 1

![Cohort 1](approval-channel-analysis-cohort-1.png)

## Cohort 2

![Cohort 2](approval-channel-analysis-cohort-2.png)

## Cohort 3

![Cohort 3](approval-channel-analysis-cohort-3.png)

## Cohort 4

![Cohort 4](approval-channel-analysis-cohort-4.png)
