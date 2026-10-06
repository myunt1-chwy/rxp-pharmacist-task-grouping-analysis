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

Before rebuilding `MY_RXP_TASKS`, the generator also creates or replaces the
transient `EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_RX_USAGE_TO_RX`
mapping from `EDLDB.BT_HCA_HCDM.RXP_RX_USAGE_ACTIONS`, grouped to one
deterministic `RX_ID` per `RX_USAGE_ID`. The mapping CTAS is written to
`generated/create_rx_usage_to_rx_mapping.sql` and runs before the task-table
CTAS. `MY_RXP_TASKS.PRESCRIPTION_ID` uses the mapped `RX_ID` when available,
falling back to the lifecycle value otherwise. Rebuild the valid DUR table
after changing this mapping so its prescription IDs are refreshed as well.

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

## Generate the valid DUR task sequence table

Create or replace `EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_VALID_DUR_TASKS`:

```bash
make generate-valid-dur-task-table
```

The table keeps non-intersecting DUR tasks with `IS_REFILL = 'false'` and a
null `HANDOFF_TYPE`. It joins `EDLDB.PDM.PRODUCT` to add parent part number,
MC3, and purchase brand. It includes global and valid-task ordering, the
previous-task validity flag, and independent contiguous sequence and batch
identifiers for cohort, MC3, purchase brand, and parent part number. A new
sequence starts when the global task order is not adjacent, the prior valid
task is more than 3,600 seconds away, or the relevant grouping value changes.
The table also includes `MC3_PET_SEQN` and `MC3_PET_BATCH_ID`, which apply the
same sequence rules as the MC3 sequence while requiring the same `PETTYPE` and
MC3 for a user. Missing or blank pet types are normalized to `<Missing>` for
sequence comparison.
It also includes `MC3_COH_PETTYPE_SEQN`, `MC3_COH_PETTYPE_BATCH_ID`, and
`MC3_COH_PETTYPE_BATCH_LEN`, which require the same MC3, cohort, and pet type
for the same user while applying the same contiguous sequence rules.
It also includes `COHORT_PET_SEQN` and `COHORT_PET_BATCH_ID`, which apply the
cohort sequence rules while requiring the same `PET_ID` for the same user and
cohort. Missing pet IDs start a new cohort-pet sequence.
Within each contiguous cohort batch, `COHORT_SEQN` is the task position
starting at 1 in increasing `PROCESS_START_TIME`; `COHORT_BATCH_ID` identifies
the batch itself. Cohort values are normalized before comparison so a change
from one cohort to another always starts a new cohort batch.

The table also adds `ORIGINATION`, `INITIATION_CHANNEL`, `INITIATION_REASON`,
`PRESCRIPTION_SOURCE`, `APPROVAL_CHANNEL`, and `PET_ID` from
`EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS`, plus `PETTYPE` from
`CHEWYBI.CUSTOMER_PETPROFILES.PETPROFILE_PETTYPE_DESCRIPTION` through the
`PETPROFILE_ID = RXP_PRESCRIPTIONS.PET_ID` join. Pet profiles are reduced to
one row per `PETPROFILE_ID` using the latest available profile timestamps before
the join. `NPET_CONDITIONS` is `0` for an unmatched profile, a null, blank, or
`none` medical-condition list; otherwise it is the number of comma-separated
entries in `PETPROFILE_MED_CONDITION_LIST`. The action-level
`EDLDB.BT_HCA_HCDM.RXP_RX_USAGE_ACTIONS` rows are restricted to usage IDs in
the valid task result and grouped by `RX_USAGE_ID`; `MIN(RX_ID)` provides a
deterministic single prescription ID if an action history contains more than
one. Left joins preserve valid tasks when any mapping is missing, leaving
the enrichment fields null, and avoid multiplying task rows.

The table also adds `CORRECTION_FIELD_NAMES`, an ordered array of distinct
fields changed during matching correction actions, and `NCORRECTION_FIELDS`,
its distinct-field count. Correction records are limited to the supported
prescription fields, non-system users, matching DUR tasks, and correction
timestamps between each task's `STARTED_AT` and `TRANSITION_ENDED_AT` values.
The correction-to-usage mapping uses `ORDER_ID`, `ORDER_ITEM_ID`, and `RX_ID`
without an action-name equality constraint. Tasks with
no matching correction have an empty array and a count of `0`.
The source `LAST_ACTION_NAME` values are retained as the distinct
`CORRECTION_ACTION_NAMES` array, and source `LAST_ACTION_ID` values are
retained as the distinct `CORRECTION_ACTION_IDS` array for each task.

The table also adds `N_PRIOR_APPROVED_RX_IDS`,
`N_PRIOR_APPROVED_VET_DIET_RX_IDS`, and
`N_PRIOR_APPROVED_NON_VET_DIET_RX_IDS`. These count distinct prescriptions
for each task's pet whose approval occurred strictly before
`PROCESS_START_TIME`, excluding the prescription attached to the current DUR
task. Approval uses `TO_STATE = 'APPROVED'`, with
`STATE_CHANGED_DATETIME` and an `ACTION_CREATION_DATETIME` fallback; a
prescription is classified as vet diet when any approved action row has
`IS_VET_DIET_FLAG = TRUE`.

Override the default inclusive start date and exclusive end date when building
the table:

```bash
make generate-valid-dur-task-table START_DATE=2026-03-01 END_DATE=2026-04-01
```

The generated CTAS is written to
`generated/generate_valid_dur_task_table.sql` before external-browser
authentication. To remove the transient table:

```bash
make drop-valid-dur-task-table
```

## Use the prescription usage-actions schema

The `rxp-sql` skill documents the nullable columns and Snowflake types for
`EDLDB.BT_HCA_HCDM.RXP_RX_USAGE_ACTIONS` in
`skills/rxp-sql/references/rxp-rx-usage-actions-schema.md`. The view is at
action grain: use `ACTION_ID` for action records, `RX_USAGE_ID` to join to
usage-level records, and `RX_ID` to join back to
`EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS`. Aggregate its rows before calculating
usage- or prescription-level metrics.

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

Outputs are written to `outputs/charts/tasks-based-distributions/`. Open its `README.md` to view all generated PNGs together.

The same directory also contains `task-duration-by-cohort-boxplots.png`, a
single PNG with four boxplots on one axis. Each boxplot summarizes individual
filtered DUR task durations for one cohort and has a table below it with cohort,
DUR count, median, maximum, minimum, average, and standard deviation. The
task-level durations are cached at
`outputs/data/task-based-distributions-task-durations.parquet` for redraws.
It also contains `task-duration-by-cohort-violin-plots.png`, a shared-y-axis
four-cohort density visualization of those same task durations.
The same run now also writes four job-title boxplot PNGs, one for each cohort,
`task-duration-by-job-title-all-cohorts-boxplots.png` with all cohorts pooled,
and `task-dur-count-by-job-title-strip.png` showing filtered DUR task counts by
job title. Each job-title boxplot includes a summary table below the duration
distributions with DUR count, median, maximum, average, and standard deviation. These
figures use the task-level cache and the same global approximate 95th-percentile
duration filter.

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

Generate one combined four-panel boxplot figure showing product-level mean
DUR duration by cohort:

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

PNG and an embedding `README.md` are written to
`outputs/charts/part-number-analysis/`. The figure is
`part-number-analysis-cohort-boxplots.png`, with one boxplot per cohort.
Boxes show the interquartile range, whiskers show the 5th–95th percentiles,
and up to five high-duration values outside the whiskers are marked and labeled
with their part numbers in each cohort.

## Analyze MC3 distributions

Generate one categorical MC3 boxplot for each cohort. Each chart includes one
boxplot per MC3 plus a final boxplot for the whole cohort:

```bash
make create-mc3-analysis
```

The query filters to known, non-refill DUR tasks with no handoff and excludes
durations at or above the filtered population's approximate 95th percentile.
It joins `EDLDB.PDM.PRODUCT` on `PART_NUMBER` and uses
`MERCH_CLASSIFICATION3` as MC3. Missing or blank MC3 values are shown as
`<Missing>`.

Task-level joined data is cached at `outputs/data/mc3-analysis.parquet`, and
the generated query is written to `generated/create_mc3_analysis.sql`. Rebuild
the four PNGs without Snowflake access with:

```bash
make create-mc3-analysis REDRAW=1
```

Each x-axis label has the MC3 name on the first line and `Task Count` plus `PN`
(distinct part-number count) on the second line. The median is shown as a white
horizontal line. PNGs and an embedding `README.md` are written to
`outputs/charts/mc3-analysis/`.
The same run writes `mc3-analysis-category-median-histogram.png`, a four-panel
Altair histogram of MC3 median DUR durations using two-second bins.

## Analyze Purchase Brand distributions

Generate one categorical Purchase Brand boxplot for each cohort. Each chart
contains one boxplot per `PURCHASE_BRAND` plus a `Whole cohort` boxplot:

```bash
make create-purchase-brand-analysis
```

The query uses the same known-cohort, non-refill, no-handoff DUR filters and
approximate 95th-percentile duration cutoff as the MC3 analysis. It joins
`EDLDB.PDM.PRODUCT` on `PART_NUMBER`. The vertically stacked boxplots have
adjacent labels showing the Purchase Brand name, task count, and distinct
part-number count; dark-red lines show medians.

Task-level data is cached at
`outputs/data/purchase-brand-analysis.parquet`, and the generated query is
written to `generated/create_purchase_brand_analysis.sql`. Redraw without
Snowflake access with:

```bash
make create-purchase-brand-analysis REDRAW=1
```

PNGs and an embedding `README.md` are written to
`outputs/charts/purchase-brand-analysis/`.
The same run writes `purchase-brand-analysis-top-10-table.png`, an Altair 2×2
grid with one table per cohort and a highlighted whole-cohort statistics row.
The same run writes `outputs/tables/purchase-brand-analysis-top-10-by-median.md`,
containing the 10 brands with the highest median DUR duration in each cohort,
along with task counts, distinct part-number counts, medians, and averages.
It also writes `purchase-brand-analysis-brand-median-histogram.png`, a four-panel
Altair histogram of brand median DUR durations using two-second bins.

## Analyze initiation-channel and initiation-reason distributions

Generate horizontal categorical boxplots for each cohort, using the enriched
valid DUR task table. The target writes one four-chart set grouped by
`INITIATION_CHANNEL` and one four-chart set grouped by `INITIATION_REASON`; each
chart includes a `Whole cohort` reference boxplot:

```bash
make create-initiation-channel-analysis
```

The read-only query selects Cohorts 1–4 from
`EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_VALID_DUR_TASKS` and uses
`IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS` as the duration. Durations at or
above one global approximate 95th-percentile cutoff are excluded. Null or blank
initiation channels and reasons are displayed as `<Missing>`. Labels beside each
boxplot show the filtered task count, and dark-red lines show medians.

Task-level data, including both grouping fields, is cached at
`outputs/data/initiation-channel-analysis.parquet`, and the generated query is
written to `generated/create_initiation_channel_analysis.sql`. Redraw all eight
PNGs without Snowflake access with:

```bash
make create-initiation-channel-analysis REDRAW=1
```

PNGs and an embedding `README.md` are written to
`outputs/charts/initiation-channel-analysis/`. Channel plots use the
`initiation-channel-analysis-cohort-*.png` names; reason plots use
`initiation-reason-analysis-cohort-*.png`.

## Analyze prescription-source distributions

Generate four horizontal `PRESCRIPTION_SOURCE` boxplot figures by cohort, each
with a `Whole cohort` reference boxplot, using the same valid-DUR task
population as the initiation-channel and initiation-reason analysis:

```bash
make create-prescription-source-analysis
```

The read-only query selects Cohorts 1–4 from
`EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_VALID_DUR_TASKS` and uses
`IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS` as the duration. Durations at or
above one global approximate 95th-percentile cutoff are excluded. Null or blank
prescription sources are displayed as `<Missing>`. Labels show filtered task
counts, and dark-red lines show medians.

Task-level data is cached at
`outputs/data/prescription-source-analysis.parquet`, and the generated query is
written to `generated/create_prescription_source_analysis.sql`. Regenerate the
four PNGs without Snowflake access with:

```bash
make create-prescription-source-analysis REDRAW=1
```

PNGs and an embedding `README.md` are written to
`outputs/charts/prescription-source-analysis/`.

## Analyze approval-channel distributions

Generate four horizontal `APPROVAL_CHANNEL` boxplot figures by cohort, each
with a `Whole cohort` reference boxplot, using the valid-DUR task table:

```bash
make create-approval-channel-analysis
```

The read-only query selects Cohorts 1–4 from
`EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_VALID_DUR_TASKS` and uses
`IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS` as the duration. Durations at or
above one global approximate 95th-percentile cutoff are excluded. Null or blank
approval channels are displayed as `<Missing>`. Labels show filtered task
counts, and dark-red lines show medians.

Task-level data is cached at
`outputs/data/approval-channel-analysis.parquet`, and the generated query is
written to `generated/create_approval_channel_analysis.sql`. Regenerate the
four PNGs without Snowflake access with:

```bash
make create-approval-channel-analysis REDRAW=1
```

PNGs and an embedding `README.md` are written to
`outputs/charts/approval-channel-analysis/`.

## Analyze DUR duration by PETTYPE

Generate four horizontal `PETTYPE` boxplot figures by cohort, each with a
`Whole cohort` reference boxplot, using the valid-DUR task table:

```bash
make create-pettype-analysis
```

The read-only query selects Cohorts 1–4 from
`EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_VALID_DUR_TASKS` and uses
`IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS` as the duration. The source
table contains valid DUR tasks; durations at or above one global approximate
95th-percentile DUR-duration cutoff are excluded. Null or blank `PETTYPE`
values are displayed as `<Missing>`. Labels show filtered task counts, and
dark-red lines show medians.

Task-level data is cached at `outputs/data/pettype-analysis.parquet`, and the
generated query is written to `generated/create_pettype_analysis.sql`.
Regenerate the four PNGs without Snowflake access with:

```bash
make create-pettype-analysis REDRAW=1
```

PNGs and an embedding `README.md` are written to
`outputs/charts/pettype-analysis/`.

## Analyze DUR duration by medical-condition count

Generate four horizontal `NPET_CONDITIONS` boxplot figures by cohort, each with
a `Whole cohort` reference boxplot, using the valid-DUR task table:

```bash
make create-npet-conditions-analysis
```

The read-only query selects Cohorts 1–4 from
`EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_VALID_DUR_TASKS` and uses
`IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS` as the duration. Durations at or
above one global approximate 95th-percentile DUR-duration cutoff are excluded.
`NPET_CONDITIONS` is grouped as the number of medical conditions, with
unmatched or empty profiles represented as `0`. Labels show filtered task
counts, and dark-red lines show medians.

Task-level data is cached at
`outputs/data/npet-conditions-analysis.parquet`, and the generated query is
written to `generated/create_npet_conditions_analysis.sql`. Regenerate the
four PNGs without Snowflake access with:

```bash
make create-npet-conditions-analysis REDRAW=1
```

PNGs and an embedding `README.md` are written to
`outputs/charts/npet-conditions-analysis/`.

## Analyze DUR duration by number of correction fields

Generate four horizontal boxplot figures by `NCORRECTION_FIELDS`, one per
cohort, each with a `Whole cohort` reference boxplot:

```bash
make create-ncorrection-fields-analysis
```

The read-only query selects valid DUR tasks from
`EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_VALID_DUR_TASKS` for Cohorts
1–4 and uses `IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS` as the duration.
Durations at or above one global approximate 95th-percentile cutoff are
excluded. `NCORRECTION_FIELDS` is grouped as the number of distinct correction
fields matched to each task, with null values represented as `0`. Labels show
filtered task counts, and dark-red lines show medians.

Task-level data is cached at
`outputs/data/ncorrection-fields-analysis.parquet`, and the generated query is
written to `generated/create_ncorrection_fields_analysis.sql`. Regenerate the
four PNGs without Snowflake access with:

```bash
make create-ncorrection-fields-analysis REDRAW=1
```

PNGs and an embedding `README.md` are written to
`outputs/charts/ncorrection-fields-analysis/`.

## Analyze DUR duration by prior approved prescription count

Generate four horizontal boxplot figures by `N_PRIOR_APPROVED_RX_IDS`, one per
cohort, each with a `Whole cohort` reference boxplot:

```bash
make create-prior-approved-rx-analysis
```

The read-only query selects valid DUR tasks from
`EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_VALID_DUR_TASKS` for Cohorts
1–4 and uses `IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS` as the duration.
Durations at or above one global approximate 95th-percentile cutoff are
excluded. `N_PRIOR_APPROVED_RX_IDS` is the number of distinct prescriptions
approved before the task's process start time, excluding the current task
prescription; null values are represented as `0`. Labels show filtered task
counts, and dark-red lines show medians.

Task-level data is cached at
`outputs/data/prior-approved-rx-analysis.parquet`, and the generated query is
written to `generated/create_prior_approved_rx_analysis.sql`. Regenerate the
four PNGs without Snowflake access with:

```bash
make create-prior-approved-rx-analysis REDRAW=1
```

PNGs and an embedding `README.md` are written to
`outputs/charts/prior-approved-rx-analysis/`.

## Analyze DUR duration by prior approved non-vet-diet prescription count

Generate four horizontal boxplot figures by
`N_PRIOR_APPROVED_NON_VET_DIET_RX_IDS`, one per cohort, each with a `Whole
cohort` reference boxplot:

```bash
make create-prior-approved-non-vet-diet-rx-analysis
```

The read-only query selects valid DUR tasks from
`EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_VALID_DUR_TASKS` for Cohorts
1–4 and uses `IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS` as the duration.
Durations at or above one global approximate 95th-percentile cutoff are
excluded. The non-vet-diet prescription count is bucketed as `0`, `1`, `2`,
`3`, `4`, `5`, `6`, `7`, `8`, `9`, and `10+`; null values are represented as
`0`. Labels show filtered task counts, and dark-red lines show medians.

Task-level data is cached at
`outputs/data/prior-approved-non-vet-diet-rx-analysis.parquet`, and the
generated query is written to
`generated/create_prior_approved_non_vet_diet_rx_analysis.sql`. Regenerate the
four PNGs without Snowflake access with:

```bash
make create-prior-approved-non-vet-diet-rx-analysis REDRAW=1
```

PNGs and an embedding `README.md` are written to
`outputs/charts/prior-approved-non-vet-diet-rx-analysis/`.

## Analyze DUR duration by correction field name

Generate four horizontal boxplot figures by correction field name, one per
cohort, each with a `Whole cohort` reference boxplot:

```bash
make create-correction-field-analysis
```

The read-only query selects valid DUR tasks from
`EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_VALID_DUR_TASKS` for Cohorts
1–4 and uses `IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS` as the duration.
Durations at or above one global approximate 95th-percentile cutoff are
excluded. The distinct values in `CORRECTION_FIELD_NAMES` are used as the
categories; tasks with no correction fields are shown as `<No correction>`.
Labels show filtered task counts, and dark-red lines show medians.

Task-level data is cached at
`outputs/data/correction-field-analysis.parquet`, and the generated query is
written to `generated/create_correction_field_analysis.sql`. Regenerate the
four PNGs without Snowflake access with:

```bash
make create-correction-field-analysis REDRAW=1
```

PNGs and an embedding `README.md` are written to
`outputs/charts/correction-field-analysis/`.

## Analyze DUR duration by MC3 and PETTYPE

Generate one all-cohort heatmap plus one heatmap for each of Cohorts 1–4, with
MC3 categories as rows and PETTYPE values as columns:

```bash
make create-mc3-pettype-analysis
```

The read-only query uses valid DUR tasks from Cohorts 1–4 in
`EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_VALID_DUR_TASKS`, excludes
durations at or above one global approximate 95th-percentile cutoff, and
aggregates task count and median DUR duration in each MC3/PETTYPE cell.
The `All PETTYPEs` column provides the overall task count and median for each
MC3 row. Each heatmap label shows `n` and the median duration in seconds.

Aggregate data is cached at `outputs/data/mc3-pettype-analysis.parquet`, and
the generated query is written to
`generated/create_mc3_pettype_analysis.sql`. Regenerate the heatmap without
Snowflake access with:

```bash
make create-mc3-pettype-analysis REDRAW=1
```

The five PNGs and embedding `README.md` are written to
`outputs/charts/mc3-pettype-analysis/`.

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

## Fit the final MC3/COH/PETTYPE model

Pull fresh Snowflake data and fit the final crossed random-intercept model:

```bash
make create-mc3-coh-pettype-final-model
```

The model uses MC3 + COH + PETTYPE fixed-effect cells; treatment, correction,
weekday, approval-channel, and prescription-source fixed effects; and crossed
normally distributed random intercepts for user, process date, and parent part
number. It applies one strict global approximate 95th-percentile duration
filter and one global Box-Cox transformation before fitting by REML. The most
frequent approval-channel and prescription-source levels are the references.

The generated report at
`outputs/reports/md/mc3_coh_pettype_final_model.md` is self-contained: it
documents sample construction, all derived indicators, the Box-Cox equation,
the complete mixed-model formula, distribution assumptions, prediction and
residual formulas, confidence intervals, p-values, and fit statistics. The
target also writes its generated SQL, raw and transformed Parquet caches,
fixed- and random-effect Markdown tables, and five diagnostic PNGs.

Rerun the complete analysis from the cached Snowflake extract with:

```bash
make create-mc3-coh-pettype-final-model REDRAW=1
```

## Analyze same-cohort versus different-cohort work time

Run the Santhosh query analysis and compare task work time for consecutive DUR
tasks whose previous task has the same or a different cohort:

```bash
make create-santhosh-analysis
```

The task-level query is stored at `src/sql/santhosh_analysis.sql`, the cached
extract is stored at `outputs/data/santhosh-analysis.parquet`, and the
four cohort distribution charts are written to
`outputs/charts/santhosh-analysis/`. The report at
`outputs/reports/md/santosh_analysis.md` contains separate descriptive
statistics and Welch two-sample tests with confidence intervals for Cohorts 1–4,
limits DUR work time to five minutes, uses a base-10 logarithmic x-axis with
two-second bins, and includes the query, limitations, and all four charts.

Redraw the four charts and report without querying Snowflake with:

```bash
make create-santhosh-analysis REDRAW=1
```

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
| `generate-valid-dur-task-table` | Create or replace the valid DUR task sequence and correction-field table. |
| `drop-valid-dur-task-table` | Drop the valid DUR task sequence table. |
| `drop-task-table` | Drop the generated pharmacist task table from Snowflake. |
| `create-causal-diagram` | Render the Mermaid causal diagram as a PNG with Docker. |
| `create-task-based-distributions` | Query Snowflake and render four task-summary PNGs. |
| `create-task-time-bucket-distribution` | Render the warehouse/cohort statistics chart in two-hour UTC buckets. |
| `create-task-intersection-duration-distributions` | Render intersecting and non-intersecting DUR duration histograms. |
| `create-part-number-analysis` | Query Snowflake and render four cohort part-number duration charts. |
| `create-mc3-analysis` | Query Snowflake and render four cohort MC3 duration boxplot charts. |
| `create-purchase-brand-analysis` | Query Snowflake and render four cohort Purchase Brand duration boxplot charts. |
| `create-initiation-channel-analysis` | Query Snowflake and render four cohort initiation-channel duration boxplot charts. |
| `create-prescription-source-analysis` | Query Snowflake and render four cohort prescription-source duration boxplot charts. |
| `create-approval-channel-analysis` | Query Snowflake and render four cohort approval-channel duration boxplot charts. |
| `create-ncorrection-fields-analysis` | Query Snowflake and render four cohort NCORRECTION_FIELDS duration boxplot charts. |
| `create-prior-approved-rx-analysis` | Query Snowflake and render four cohort N_PRIOR_APPROVED_RX_IDS duration boxplot charts. |
| `create-prior-approved-non-vet-diet-rx-analysis` | Query Snowflake and render four cohort bucketed N_PRIOR_APPROVED_NON_VET_DIET_RX_IDS duration boxplot charts. |
| `create-correction-field-analysis` | Query Snowflake and render four cohort correction-field-name duration boxplot charts. |
| `create-mc3-coh-pettype-final-model` | Fit the final fixed-effects model with crossed user, date, and parent-part-number random intercepts. |
| `create-santhosh-analysis` | Compare same-cohort and different-cohort DUR work-time distributions with a Welch two-sample test. |
| `user-performance-analysis` | Render mean and median user-performance scatter matrices by cohort. |
| `test` | Run the test suite. |

Refer to the root `Makefile` for the authoritative target definitions and defaults.
