# Correction field analysis

Valid DUR tasks are selected from `MY_RXP_VALID_DUR_TASKS` for Cohorts 1–4.
Durations at or above the global approximate 95th percentile are excluded.
The distinct values in `CORRECTION_FIELD_NAMES` are used as categories; tasks with no correction fields are shown as `<No correction>`.
Each chart contains a horizontal boxplot for every field-name category plus a final `Whole cohort` reference boxplot. Labels show filtered task counts, and dark-red lines show medians.
Cached task-level data is stored at `outputs/data/correction-field-analysis.parquet` for redraw-only runs.

## Cohort 1

![Cohort 1](correction-field-analysis-cohort-1.png)

## Cohort 2

![Cohort 2](correction-field-analysis-cohort-2.png)

## Cohort 3

![Cohort 3](correction-field-analysis-cohort-3.png)

## Cohort 4

![Cohort 4](correction-field-analysis-cohort-4.png)
