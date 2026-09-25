# Running Make Targets

Run Make commands from the repository root:

```bash
cd /path/to/rxp-pharmacist-task-grouping-analysis
make <target>
```

Each target performs a specific repository task. As more targets are added, use the target name shown in the `Makefile` in place of `<target>`.

## Initial setup

Install and synchronize the project dependencies:

```bash
make setup
```

This project uses `uv` and the repository's `.venv`; global Python packages are not required.

## Generate the pharmacist task table

Before running the generator, create a local `.env` containing the Snowflake connection settings:

```dotenv
RXP_SNOWFLAKE_ACCOUNT=your-account
RXP_SNOWFLAKE_USER=your-user
RXP_SNOWFLAKE_DATABASE=EDLDB_DEV
RXP_SNOWFLAKE_WAREHOUSE=your-warehouse
RXP_SNOWFLAKE_SCHEMA=PET_HEALTH_ANALYTICS_SANDBOX
RXP_SNOWFLAKE_ROLE=your-role
```

`RXP_SNOWFLAKE_ROLE` is optional. Do not commit `.env` or credentials.

Create or replace `EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASKS` with the default date window, from February 1, 2026 through August 1, 2026 (exclusive):

```bash
make generate-task-table
```

The command opens a browser for Snowflake authentication. Complete the sign-in flow and return to the terminal while the table is built.

Each run writes the rendered statement to `generated/generate_task_table.sql` before connecting to Snowflake. The `generated` directory is ignored by Git because its contents can be reproduced from the template and date arguments.

The generated table retains the source
`DWELL_IN_PROGRESS_TO_CLOSED_SECONDS` and adds
`IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS`, which replaces a missing dwell
value with one second. `PROCESS_START_TIME` is calculated in UTC by subtracting
the imputed dwell value from `CLOSED_AT`, and `PROCESS_START_DATE` is its UTC
date. The former `STARTED_DATE` field is not included; `STARTED_AT` remains
available as the source task timestamp.

Override either date by passing Make variables. The start date is inclusive and the end date is exclusive:

```bash
make generate-task-table START_DATE=2026-03-01 END_DATE=2026-04-01
```

Dates must use `YYYY-MM-DD`, and `START_DATE` must be earlier than `END_DATE`.

## Generate the task-intersection inspection table

Create or replace `EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASK_INTERSECTIONS`
for the default user, `319402689`:

```bash
make generate-task-intersection-table
```

The table contains one directed row for each intersecting task relationship,
including `USER_ID`, `TASK_ID`, `INTERSECTING_TASK_ID`, both tasks' intervals,
and the intersection bounds. Intervals are closed, so tasks that touch at one
endpoint count as intersecting. The target writes the rendered CTAS statement
to `generated/generate_task_intersection_table.sql` before connecting to
Snowflake through external-browser authentication.

To inspect another user later, override `USER_ID`:

```bash
make generate-task-intersection-table USER_ID=123456789
```

## Generate the task sequence table

Create or replace `EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASKS_WITH_SEQUENCE`:

```bash
make generate-task-sequence-table
```

The table contains one row per usable `USER_ID` and `TASK_ID`, including the
nearest preceding task, nearest following task, each gap in seconds, and the
number of other tasks intersecting the closed interval from `PROCESS_START_TIME`
through `CLOSED_AT`. All task types participate. Preceding and following
matches use strict inequalities, and tied event timestamps use the smallest
task ID deterministically. The generated CTAS is written to
`generated/generate_task_sequence_table.sql` before external-browser
authentication.

## Drop the pharmacist task table

To remove `EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASKS` from Snowflake:

```bash
make drop-task-table
```

This is a destructive operation. The target opens the external-browser authentication flow and executes `DROP TABLE IF EXISTS`, so it succeeds safely when the table is already absent. Recreate the table with `make generate-task-table`.

## Create the causal diagram

Render `src/mermaid/DUR.mmd` as a 2400×1600 PNG:

```bash
make create-causal-diagram
```

The target runs the Dockerized Mermaid CLI from `minlag/mermaid-cli`; a local Node.js or Mermaid installation is not required. It mounts the repository at `/mermaid` inside the container and writes the result to `outputs/charts/DUR_detailed.png`.

Docker must be installed and its daemon must be running. The image is downloaded automatically if it is not already available locally.

The source and output paths can be overridden when another Mermaid figure is added:

```bash
make create-causal-diagram \
  CAUSAL_DIAGRAM_SOURCE=src/mermaid/another-diagram.mmd \
  CAUSAL_DIAGRAM_OUTPUT=outputs/charts/another-diagram.png
```

## Create task-based distribution charts

Query `EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASKS` and generate four cohort summary charts:

```bash
make create-task-based-distributions
```

The command opens the external-browser Snowflake authentication flow and runs one read-only aggregate query. It filters to non-refill DUR tasks with a known cohort and no handoff, then creates heatmaps for shift, job title, warehouse, and UTC process-start day of week. Weekday rows use Monday-through-Sunday order. Every cell contains unique task and user counts plus the mean, median, and standard deviation of `IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS`; cell color represents unique task count.

Duration values at or above the filtered population's approximate 95th percentile are excluded. The aggregate chart data is cached as `outputs/data/task-based-distributions.parquet`, so aesthetic changes can be rendered without another Snowflake query:

```bash
make create-task-based-distributions REDRAW_ONLY=1
```

Use `make create-task-based-distributions` without `REDRAW_ONLY=1` to refresh the cache from Snowflake.

Before connecting to Snowflake, each run writes the aggregate query to `generated/create_task_based_distributions.sql`. The reproducible `generated` directory is ignored by Git.

Outputs are written to `outputs/charts/tasks-based-distributions/`. Open its `README.md` to view all four PNGs together.

The same directory also contains `task-duration-by-cohort-boxplots.png`, a
single PNG with four boxplots on one axis. Each boxplot summarizes individual
filtered DUR task durations for one cohort. The task-level durations are cached
at `outputs/data/task-based-distributions-task-durations.parquet` for redraws.
It also contains `task-duration-by-cohort-violin-plots.png`, a shared-y-axis
four-cohort density visualization of those same task durations.

- `task-summary-by-shift-and-cohort.png`
- `task-summary-by-job_title-and-cohort.png`
- `task-summary-by-wh_id-and-cohort.png`
- `task-summary-by-day_of_week-and-cohort.png`

Each refresh removes the obsolete separate count and duration PNGs before writing the four combined charts.

## Create the two-hour task distribution chart

Generate separate charts that group DUR tasks into twelve two-hour UTC process-start buckets:

```bash
make create-task-time-bucket-distribution
```

The target buckets tasks using `PROCESS_START_TIME`, creates one four-cohort
chart for the overall population, and creates a separate four-cohort chart for
every warehouse. Each cell shows unique task count, unique user count, and the
mean, median, and standard deviation of
`IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS`. Empty
cohort/bucket combinations are retained as zero-count cells.

Duration values at or above the filtered population's approximate 95th percentile are excluded. Aggregate chart data is cached as `outputs/data/task-time-bucket-distribution.parquet`, so the charts can be redrawn without querying Snowflake:

```bash
make create-task-time-bucket-distribution REDRAW_ONLY=1
```

Use `make create-task-time-bucket-distribution` without `REDRAW_ONLY=1` to refresh the cache from Snowflake.

The command runs one read-only Snowflake aggregate query through external-browser authentication. It writes the exact query to `generated/create_task_time_bucket_distribution.sql` before connecting.

PNGs and an embedding `README.md` are written to `outputs/charts/task-time-bucket-distribution/`. The obsolete single large PNG is removed during refresh.

## Create DUR duration distributions by task intersection

Generate the combined density chart from the task sequence and task tables:

```bash
make create-task-intersection-duration-distributions
```

The command filters to DUR tasks with a known cohort, `IS_REFILL = false`, and
no handoff. It uses
`IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS`, classifying tasks with
`N_INTERSECTING_TASKS > 0` as intersecting and tasks with zero as
non-intersecting. Durations at or above the filtered population's approximate
95th percentile are excluded from the visualization. The status-specific
chart has a separate shaded density panel for Cohorts 1–4, using 100 duration
bins and a shared x-axis range. Density is normalized per second within each
cohort/classification group. The intersecting distribution is labeled
`multitasking`; the non-intersecting distribution is labeled
`singletasking`. Each panel includes the mean and median duration for both
classifications. Each annotation includes the task count, mean, and median.
Its y-axis starts at zero and ends at that panel's maximum plotted density.

The read-only query is written to
`generated/create_task_intersection_duration_distributions.sql`. The PNGs and
an embedding `README.md` are written to
`outputs/charts/task-intersection-duration-distributions/`:

- `intersecting-and-non-intersecting.png`

The aggregate chart data is cached as
`outputs/data/task-intersection-duration-distributions.parquet`. After the
cache exists, redraw the PNGs without connecting to Snowflake:

```bash
make create-task-intersection-duration-distributions REDRAW_ONLY=1
```

Use the normal target without `REDRAW_ONLY=1` to refresh the Parquet cache from
Snowflake before rendering.

## Analyze cohort composition by part number

Generate one chart for each of the four cohorts, with part numbers on the x-axis,
average imputed DUR duration as points, and one sample standard deviation as
error bars:

```bash
make create-part-number-analysis
```

The read-only aggregate query filters to known, non-refill DUR tasks with no
handoff and excludes null or blank part numbers. Durations at or above the
filtered population's approximate 95th percentile are excluded. Each aggregate
includes the mean, median, sample standard deviation, distinct task count, and
distinct user count. The query is written to
`generated/create_part_number_analysis.sql` before external-browser
authentication.

Aggregate data is cached at `outputs/data/part-number-analysis.parquet`.
Regenerate all four PNGs without Snowflake access with:

```bash
make create-part-number-analysis REDRAW=1
```

PNGs and an embedding `README.md` are written to
`outputs/charts/part-number-analysis/`.
The directory also contains `part-number-analysis-cohort-violin-plots.png`, a
single figure with four violins summarizing the product-level mean duration
for Cohorts 1–4. Red dots and labels identify the 5 part numbers with the
longest average duration in each cohort; the dashed red percentile lines are
also labeled.

## Analyze user performance by cohort

Generate separate upper-triangle scatter matrices for per-user mean and median
DUR duration by cohort:

```bash
make user-performance-analysis
```

The query filters to known, non-refill DUR tasks with no handoff and excludes
durations at or above the filtered population's approximate 95th percentile.
It computes each user's task count, mean, median, and standard deviation per
cohort. Each pairwise panel includes only users with at least 30 tasks in both
cohorts being compared, colors points by job title, shapes them by warehouse,
and shows Pearson's r and the eligible-user count.

The aggregate data is cached at
`outputs/data/user-performance-analysis.parquet`. Redraw both PNGs without
querying Snowflake:

```bash
make user-performance-analysis REDRAW=1
```

The generated query is written to
`generated/create_user_performance_analysis.sql`; the PNGs and embedding
README are written to `outputs/charts/user-performance-analysis/`.
In addition to the pairwise-eligibility matrices, the directory contains mean
and median matrices restricted to users with at least 30 tasks in all four
cohorts.
The same output directory also contains one PNG with four cohort heatmaps by
warehouse and job title; each cell is the average of the per-user mean DUR
duration, displays the user count, uses a blue-to-red gradient, and includes a
footer with the distinct pharmacist/user count for each cohort. The heatmap
cells use only user/cohort statistics based on at least 30 tasks and are sized
for readability. A second heatmap repeats the layout using the median of the
per-user median durations.
The directory also contains `user-dur-count-distributions.png`, a 2×2 cohort
chart showing the distribution of DUR tasks completed per user. Its x-axis is
binned DUR count and its y-axis is the number of users.
`user-median-dur-duration-distributions.png` provides the corresponding
distribution of each user's median DUR duration by cohort.

## Run tests

Run the repository test suite with:

```bash
make test
```

## Available targets

The current targets are:

| Target | Purpose |
| --- | --- |
| `setup` | Synchronize dependencies with `uv`. |
| `generate-task-table` | Create or replace the pharmacist task table in Snowflake. |
| `generate-task-intersection-table` | Create or replace the task-intersection inspection table for one user. |
| `generate-task-sequence-table` | Create or replace the task sequence and intersection summary table. |
| `drop-task-table` | Drop the generated pharmacist task table from Snowflake. |
| `create-causal-diagram` | Render the Mermaid causal diagram as a PNG with Docker. |
| `create-task-based-distributions` | Query Snowflake and render four task-summary PNGs. |
| `create-task-time-bucket-distribution` | Render the warehouse/cohort statistics chart in two-hour UTC buckets. |
| `create-task-intersection-duration-distributions` | Render intersecting and non-intersecting DUR duration histograms. |
| `create-part-number-analysis` | Query Snowflake and render four cohort part-number duration charts. |
| `user-performance-analysis` | Render mean and median user-performance scatter matrices by cohort. |
| `test` | Run the test suite. |

Refer to the root `Makefile` for the authoritative target definitions and defaults.
