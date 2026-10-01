# Task-based distributions

Filters: `TASK_TYPE = 'DUR'`, `COH <> 'Unknown'`, `LOWER(IS_REFILL) = 'false'`, and `HANDOFF_TYPE IS NULL`.
Duration statistics use `IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS`.
Values at or above the filtered population's approximate 95th percentile are excluded.
Each cell includes distinct task and user counts.
Job-title boxplots use the task-level cache and include one PNG for each cohort plus one all-cohort PNG. Each boxplot includes a summary table with DUR count, median, maximum, average, and standard deviation by job title. The job-title count strip shows filtered DUR task counts across all cohorts.
Cached aggregate data is stored at `outputs/data/task-based-distributions.parquet` for redraw-only runs.

## Task summary by shift and cohort

![Task summary by shift and cohort](task-summary-by-shift-and-cohort.png)

## Task summary by job title and cohort

![Task summary by job title and cohort](task-summary-by-job_title-and-cohort.png)

## Task summary by warehouse and cohort

![Task summary by warehouse and cohort](task-summary-by-wh_id-and-cohort.png)

## Task summary by day of week and cohort

![Task summary by day of week and cohort](task-summary-by-day_of_week-and-cohort.png)

## DUR task duration by cohort boxplots

![DUR task duration by cohort boxplots](task-duration-by-cohort-boxplots.png)

## DUR task duration by cohort violin plots

![DUR task duration by cohort violin plots](task-duration-by-cohort-violin-plots.png)

## DUR duration by job title — Cohort 1

![DUR duration by job title — Cohort 1](task-duration-by-job-title-cohort-1-boxplots.png)

## DUR duration by job title — Cohort 2

![DUR duration by job title — Cohort 2](task-duration-by-job-title-cohort-2-boxplots.png)

## DUR duration by job title — Cohort 3

![DUR duration by job title — Cohort 3](task-duration-by-job-title-cohort-3-boxplots.png)

## DUR duration by job title — Cohort 4

![DUR duration by job title — Cohort 4](task-duration-by-job-title-cohort-4-boxplots.png)

## DUR duration by job title — All cohorts

![DUR duration by job title — All cohorts](task-duration-by-job-title-all-cohorts-boxplots.png)

## Filtered DUR task counts by job title

![Filtered DUR task counts by job title](task-dur-count-by-job-title-strip.png)
