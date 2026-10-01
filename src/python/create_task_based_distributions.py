#!/usr/bin/env python3
"""Create cohort-based task distribution charts from MY_RXP_TASKS."""

from __future__ import annotations

from pathlib import Path
import re

import altair as alt
import click
import pandas as pd

from .generate_task_table import REQUIRED_SETTINGS, connect_to_snowflake, parse_dotenv
from .plot_style import FIGURE_BACKGROUND, MEDIAN_COLOR

SOURCE_TABLE = "EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASKS"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIRECTORY = REPOSITORY_ROOT / "outputs" / "charts" / "tasks-based-distributions"
DATA_PATH = REPOSITORY_ROOT / "outputs" / "data" / "task-based-distributions.parquet"
TASK_DURATION_DATA_PATH = REPOSITORY_ROOT / "outputs" / "data" / "task-based-distributions-task-durations.parquet"
GENERATED_SQL_PATH = REPOSITORY_ROOT / "generated" / "create_task_based_distributions.sql"
TASK_DURATION_SQL_PATH = REPOSITORY_ROOT / "generated" / "create_task_based_distributions_task_durations.sql"

AGGREGATE_SQL = f"""
WITH base_tasks AS (
    SELECT
        TASK_ID,
        USER_ID,
        COH,
        SHIFT,
        JOB_TITLE,
        WH_ID,
        CASE DAYOFWEEKISO(PROCESS_START_TIME)
            WHEN 1 THEN 'Monday'
            WHEN 2 THEN 'Tuesday'
            WHEN 3 THEN 'Wednesday'
            WHEN 4 THEN 'Thursday'
            WHEN 5 THEN 'Friday'
            WHEN 6 THEN 'Saturday'
            WHEN 7 THEN 'Sunday'
        END AS DAY_OF_WEEK,
        IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS AS DURATION_SECONDS
    FROM {SOURCE_TABLE}
    WHERE TASK_TYPE = 'DUR'
      AND COH <> 'Unknown'
      AND LOWER(IS_REFILL) = 'false'
      AND HANDOFF_TYPE IS NULL
), percentile_bounds AS (
    SELECT APPROX_PERCENTILE(DURATION_SECONDS, 0.95) AS P95_SECONDS
    FROM base_tasks
), filtered_tasks AS (
    SELECT base.*
    FROM base_tasks AS base
    CROSS JOIN percentile_bounds
    WHERE base.DURATION_SECONDS < percentile_bounds.P95_SECONDS
), dimensions AS (
    SELECT 'shift' AS DIMENSION_TYPE,
           COH,
           COALESCE(SHIFT, '<Missing>') AS DIMENSION_VALUE,
           TASK_ID,
           USER_ID,
           DURATION_SECONDS
    FROM filtered_tasks
    UNION ALL
    SELECT 'job_title',
           COH,
           COALESCE(JOB_TITLE, '<Missing>'),
           TASK_ID,
           USER_ID,
           DURATION_SECONDS
    FROM filtered_tasks
    UNION ALL
    SELECT 'wh_id',
           COH,
           COALESCE(WH_ID, '<Missing>'),
           TASK_ID,
           USER_ID,
           DURATION_SECONDS
    FROM filtered_tasks
    UNION ALL
    SELECT 'day_of_week',
           COH,
           COALESCE(DAY_OF_WEEK, '<Missing>'),
           TASK_ID,
           USER_ID,
           DURATION_SECONDS
    FROM filtered_tasks
)
SELECT
    DIMENSION_TYPE,
    COH,
    DIMENSION_VALUE,
    COUNT(DISTINCT TASK_ID) AS UNIQUE_TASK_COUNT,
    COUNT(DISTINCT USER_ID) AS UNIQUE_USER_COUNT,
    AVG(DURATION_SECONDS) AS AVERAGE_DURATION_SECONDS,
    MEDIAN(DURATION_SECONDS) AS MEDIAN_DURATION_SECONDS,
    STDDEV_SAMP(DURATION_SECONDS) AS STDDEV_DURATION_SECONDS
FROM dimensions
GROUP BY DIMENSION_TYPE, COH, DIMENSION_VALUE
ORDER BY DIMENSION_TYPE, DIMENSION_VALUE, COH
""".strip()

TASK_DURATION_SQL = f"""
WITH base_tasks AS (
    SELECT
        TASK_ID,
        COH,
        COALESCE(JOB_TITLE, '<Missing>') AS JOB_TITLE,
        IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS AS DURATION_SECONDS
    FROM {SOURCE_TABLE}
    WHERE TASK_TYPE = 'DUR'
      AND COH <> 'Unknown'
      AND LOWER(IS_REFILL) = 'false'
      AND HANDOFF_TYPE IS NULL
      AND IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS IS NOT NULL
), percentile_bounds AS (
    SELECT APPROX_PERCENTILE(DURATION_SECONDS, 0.95) AS P95_SECONDS
    FROM base_tasks
)
SELECT
    base.TASK_ID,
    base.COH,
    base.JOB_TITLE,
    base.DURATION_SECONDS
FROM base_tasks AS base
CROSS JOIN percentile_bounds
WHERE base.DURATION_SECONDS < percentile_bounds.P95_SECONDS
ORDER BY base.COH, base.DURATION_SECONDS
""".strip()

DIMENSIONS = (
    ("shift", "Shift"),
    ("job_title", "Job title"),
    ("wh_id", "Warehouse"),
    ("day_of_week", "Day of week"),
)

WEEKDAY_ORDER = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

LEGACY_OUTPUT_FILENAMES = tuple(
    f"{metric}-by-{dimension}-and-cohort.png"
    for dimension, _ in DIMENSIONS
    for metric in ("unique-task-count", "duration")
)


def natural_sort_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def write_generated_sql() -> Path:
    GENERATED_SQL_PATH.parent.mkdir(parents=True, exist_ok=True)
    GENERATED_SQL_PATH.write_text(AGGREGATE_SQL + "\n", encoding="utf-8")
    TASK_DURATION_SQL_PATH.write_text(TASK_DURATION_SQL + "\n", encoding="utf-8")
    return GENERATED_SQL_PATH


def fetch_aggregates(settings: dict[str, str]) -> pd.DataFrame:
    connection = connect_to_snowflake(settings)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(AGGREGATE_SQL)
            columns = [column[0].lower() for column in cursor.description]
            rows = cursor.fetchall()
        finally:
            cursor.close()
    finally:
        connection.close()

    frame = pd.DataFrame(rows, columns=columns)
    for column in (
        "unique_task_count",
        "unique_user_count",
        "average_duration_seconds",
        "median_duration_seconds",
        "stddev_duration_seconds",
    ):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def fetch_task_durations(settings: dict[str, str]) -> pd.DataFrame:
    connection = connect_to_snowflake(settings)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(TASK_DURATION_SQL)
            columns = [column[0].lower() for column in cursor.description]
            rows = cursor.fetchall()
        finally:
            cursor.close()
    finally:
        connection.close()

    return normalize_task_duration_frame(pd.DataFrame(rows, columns=columns))


def write_data(frame: pd.DataFrame) -> Path:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(DATA_PATH, index=False)
    return DATA_PATH


def read_data() -> pd.DataFrame:
    return pd.read_parquet(DATA_PATH)


def write_task_duration_data(frame: pd.DataFrame) -> Path:
    TASK_DURATION_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    normalize_task_duration_frame(frame).to_parquet(TASK_DURATION_DATA_PATH, index=False)
    return TASK_DURATION_DATA_PATH


def read_task_duration_data() -> pd.DataFrame:
    return normalize_task_duration_frame(pd.read_parquet(TASK_DURATION_DATA_PATH))


def normalize_task_duration_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if "job_title" not in frame.columns:
        raise ValueError(
            "cached task-duration data does not include job_title; rerun without REDRAW_ONLY=1 to refresh it"
        )
    normalized = frame.copy()
    normalized["job_title"] = (
        normalized["job_title"]
        .astype("string")
        .str.strip()
        .replace("", pd.NA)
        .fillna("<Missing>")
        .astype(str)
    )
    normalized["duration_seconds"] = pd.to_numeric(
        normalized["duration_seconds"], errors="coerce"
    )
    return normalized.dropna(subset=["duration_seconds"])


def heatmap_base(frame: pd.DataFrame, row_title: str, title: str) -> alt.Chart:
    cohort_order = sorted(frame["coh"].dropna().unique().tolist(), key=natural_sort_key)
    row_values = frame["dimension_value"].dropna().unique().tolist()
    if row_title == "Day of week":
        known_weekdays = [day for day in WEEKDAY_ORDER if day in row_values]
        other_values = sorted(set(row_values) - set(WEEKDAY_ORDER), key=natural_sort_key)
        row_order = known_weekdays + other_values
    else:
        row_order = sorted(row_values, key=natural_sort_key)
    return (
        alt.Chart(frame)
        .encode(
            x=alt.X("coh:N", title="Cohort", sort=cohort_order, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("dimension_value:N", title=row_title, sort=row_order),
        )
        .properties(
            title=alt.TitleParams(title, anchor="start"),
            width=alt.Step(150),
            height=alt.Step(88),
        )
    )


def summary_chart(frame: pd.DataFrame, row_title: str) -> alt.Chart:
    chart_frame = frame.copy()
    chart_frame["count_label"] = chart_frame["unique_task_count"].map(
        lambda value: "N —" if pd.isna(value) else f"N {value:,.0f}"
    )
    chart_frame["user_label"] = chart_frame["unique_user_count"].map(
        lambda value: "Users —" if pd.isna(value) else f"Users {value:,.0f}"
    )
    chart_frame["mean_label"] = chart_frame["average_duration_seconds"].map(
        lambda value: "Mean —" if pd.isna(value) else f"Mean {value:,.1f}s"
    )
    chart_frame["median_label"] = chart_frame["median_duration_seconds"].map(
        lambda value: "Median —" if pd.isna(value) else f"Median {value:,.1f}s"
    )
    chart_frame["stddev_label"] = chart_frame["stddev_duration_seconds"].map(
        lambda value: "SD —" if pd.isna(value) else f"SD {value:,.1f}s"
    )
    chart = heatmap_base(
        chart_frame,
        row_title,
        f"DUR task summary by {row_title.lower()} and cohort",
    )
    threshold = float(chart_frame["unique_task_count"].max()) * 0.55
    text_color = alt.condition(
        f"datum.unique_task_count > {threshold}",
        alt.value("white"),
        alt.value("#111111"),
    )
    rectangles = chart.mark_rect().encode(
        color=alt.Color(
            "unique_task_count:Q",
            title="Unique tasks",
            scale=alt.Scale(scheme="blues"),
        ),
        tooltip=[
            alt.Tooltip("coh:N", title="Cohort"),
            alt.Tooltip("dimension_value:N", title=row_title),
            alt.Tooltip("unique_task_count:Q", title="Unique tasks", format=",.0f"),
            alt.Tooltip("unique_user_count:Q", title="Unique users", format=",.0f"),
            alt.Tooltip("average_duration_seconds:Q", title="Mean seconds", format=",.2f"),
            alt.Tooltip("median_duration_seconds:Q", title="Median seconds", format=",.2f"),
            alt.Tooltip("stddev_duration_seconds:Q", title="SD seconds", format=",.2f"),
        ],
    )
    count_labels = chart.mark_text(dy=-32, fontSize=12, fontWeight="bold").encode(
        text="count_label:N",
        color=text_color,
    )
    user_labels = chart.mark_text(dy=-16, fontSize=11, fontWeight="bold").encode(
        text="user_label:N",
        color=text_color,
    )
    mean_labels = chart.mark_text(dy=0, fontSize=11).encode(
        text="mean_label:N",
        color=text_color,
    )
    median_labels = chart.mark_text(dy=16, fontSize=11).encode(
        text="median_label:N",
        color=text_color,
    )
    stddev_labels = chart.mark_text(dy=32, fontSize=11).encode(
        text="stddev_label:N",
        color=text_color,
    )
    return (
        rectangles
        + count_labels
        + user_labels
        + mean_labels
        + median_labels
        + stddev_labels
    ).configure(background=FIGURE_BACKGROUND).configure_view(
        stroke=None, fill=FIGURE_BACKGROUND
    )


def write_markdown(chart_files: list[tuple[str, str]]) -> Path:
    lines = [
        "# Task-based distributions",
        "",
        "Filters: `TASK_TYPE = 'DUR'`, `COH <> 'Unknown'`, "
        "`LOWER(IS_REFILL) = 'false'`, and `HANDOFF_TYPE IS NULL`.",
        "Duration statistics use `IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS`.",
        "Values at or above the filtered population's approximate 95th percentile are excluded.",
        "Each cell includes distinct task and user counts.",
        "Job-title boxplots use the task-level cache and include one PNG for each cohort plus one all-cohort PNG. Each boxplot includes a summary table with DUR count, median, maximum, average, and standard deviation by job title. The job-title count strip shows filtered DUR task counts across all cohorts.",
        "Cached aggregate data is stored at `outputs/data/task-based-distributions.parquet` for redraw-only runs.",
        "",
    ]
    for title, filename in chart_files:
        lines.extend((f"## {title}", "", f"![{title}]({filename})", ""))
    path = OUTPUT_DIRECTORY / "README.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def boxplot_chart(frame: pd.DataFrame) -> alt.Chart:
    chart_frame = frame.copy()
    cohort_order = sorted(
        chart_frame["coh"].dropna().unique().tolist(), key=natural_sort_key
    )
    summary = (
        chart_frame.groupby("coh", as_index=False)
        .agg(
            task_count=("duration_seconds", "size"),
            p05=("duration_seconds", lambda values: values.quantile(0.05)),
            q1=("duration_seconds", lambda values: values.quantile(0.25)),
            median=("duration_seconds", "median"),
            q3=("duration_seconds", lambda values: values.quantile(0.75)),
            p95=("duration_seconds", lambda values: values.quantile(0.95)),
            maximum=("duration_seconds", "max"),
            minimum=("duration_seconds", "min"),
            average=("duration_seconds", "mean"),
            stddev=("duration_seconds", lambda values: values.std(ddof=1)),
        )
    )
    base = alt.Chart(summary)
    x_encoding = alt.X("coh:N", title="Cohort", sort=cohort_order)
    whiskers = base.mark_rule(size=2, color="#4c78a8").encode(
        x=x_encoding,
        y=alt.Y("p05:Q", title="DUR task duration (seconds)"),
        y2="p95:Q",
    )
    boxes = base.mark_bar(size=70, color="#4c78a8").encode(
        x=x_encoding,
        y=alt.Y("q1:Q"),
        y2="q3:Q",
    )
    medians = base.mark_tick(
        orient="horizontal", size=70, thickness=4, color=MEDIAN_COLOR
    ).encode(
        x=x_encoding,
        y=alt.Y("median:Q"),
    )
    boxplots = (whiskers + boxes + medians).properties(
        title=alt.TitleParams(
            "DUR task duration by cohort",
            subtitle="Boxes show IQR and whiskers show the 5th–95th percentiles; summary statistics are in the table below",
            anchor="start",
        ),
        width=900,
        height=500,
    )

    def format_seconds(value: float) -> str:
        return "—" if pd.isna(value) else f"{value:,.1f}"

    summary["task_count_label"] = summary["task_count"].map(
        lambda value: f"{int(value):,}"
    )
    for field in ("median", "maximum", "minimum", "average", "stddev"):
        summary[f"{field}_label"] = summary[field].map(format_seconds)

    table_height = max(135, len(cohort_order) * 42)
    table_y_scale = alt.Scale(paddingInner=0.25, paddingOuter=0.15)

    def table_column(
        field: str, title: str, width: int, align: str
    ) -> alt.Chart:
        return (
            alt.Chart(summary)
            .mark_text(align=align, baseline="middle", fontSize=15)
            .encode(
                x=alt.value(0 if align == "left" else width - 10),
                y=alt.Y(
                    "coh:N",
                    sort=cohort_order,
                    scale=table_y_scale,
                    axis=None,
                ),
                text=alt.Text(f"{field}:N"),
            )
            .properties(
                title=alt.TitleParams(title, anchor="middle"),
                width=width,
                height=table_height,
            )
        )

    table = alt.hconcat(
        table_column("coh", "Cohort", 190, "left"),
        table_column("task_count_label", "DUR count", 170, "right"),
        table_column("median_label", "Median (s)", 170, "right"),
        table_column("maximum_label", "Maximum (s)", 170, "right"),
        table_column("minimum_label", "Minimum (s)", 170, "right"),
        table_column("average_label", "Average (s)", 170, "right"),
        table_column("stddev_label", "Std dev (s)", 170, "right"),
    ).resolve_scale(y="shared")

    return alt.vconcat(boxplots, table).configure(
        background=FIGURE_BACKGROUND
    ).configure_view(
        stroke=None, fill=FIGURE_BACKGROUND
    )


def job_title_boxplot_chart(
    frame: pd.DataFrame, cohort: str | None = None
) -> alt.Chart:
    chart_frame = normalize_task_duration_frame(frame)
    cohort_title = "All cohorts" if cohort is None else cohort
    if cohort is not None:
        chart_frame = chart_frame.loc[chart_frame["coh"] == cohort].copy()
    if chart_frame.empty:
        raise ValueError(f"the query returned no rows for {cohort_title}")

    category_counts = chart_frame["job_title"].value_counts()
    category_order = sorted(
        category_counts.index.tolist(),
        key=lambda value: (-int(category_counts[value]), natural_sort_key(value)),
    )
    summaries = []
    for job_title in category_order:
        durations = chart_frame.loc[
            chart_frame["job_title"] == job_title, "duration_seconds"
        ]
        summaries.append(
            {
                "job_title": job_title,
                "p05": durations.quantile(0.05),
                "q1": durations.quantile(0.25),
                "median": durations.quantile(0.50),
                "q3": durations.quantile(0.75),
                "p95": durations.quantile(0.95),
                "maximum": durations.max(),
                "average": durations.mean(),
                "stddev": durations.std(ddof=1),
                "task_count": len(durations),
            }
        )
    summary = pd.DataFrame(summaries)
    median_half_width = max(
        (
            float(chart_frame["duration_seconds"].max())
            - float(chart_frame["duration_seconds"].min())
        )
        * 0.004,
        0.5,
    )
    summary["median_lower"] = summary["median"] - median_half_width
    summary["median_upper"] = summary["median"] + median_half_width
    summary["task_count_label"] = summary["task_count"].map(
        lambda value: f"{int(value):,}"
    )

    def format_seconds(value: float) -> str:
        return "—" if pd.isna(value) else f"{value:,.1f}"

    summary["median_label"] = summary["median"].map(format_seconds)
    summary["maximum_label"] = summary["maximum"].map(format_seconds)
    summary["average_label"] = summary["average"].map(format_seconds)
    summary["stddev_label"] = summary["stddev"].map(format_seconds)
    category_labels = summary["job_title"].tolist()
    x_domain = [
        0,
        max(float(chart_frame["duration_seconds"].max()) * 1.05, 1.0),
    ]
    y_scale = alt.Scale(paddingInner=0.4, paddingOuter=0.2)
    base = alt.Chart(summary).encode(
        y=alt.Y(
            "job_title:N",
            title="Job title",
            sort=category_labels,
            scale=y_scale,
            axis=alt.Axis(labels=False, ticks=False, title=None),
        ),
        tooltip=[
            alt.Tooltip("job_title:N", title="Job title"),
            alt.Tooltip("task_count:Q", title="DUR tasks", format=",.0f"),
            alt.Tooltip("p05:Q", title="5th percentile seconds", format=",.2f"),
            alt.Tooltip("q1:Q", title="25th percentile seconds", format=",.2f"),
            alt.Tooltip("median:Q", title="Median seconds", format=",.2f"),
            alt.Tooltip("q3:Q", title="75th percentile seconds", format=",.2f"),
            alt.Tooltip("p95:Q", title="95th percentile seconds", format=",.2f"),
        ],
    )
    whiskers = base.mark_rule(size=2, color="#4c78a8").encode(
        x=alt.X(
            "p05:Q",
            title="DUR duration (seconds)",
            scale=alt.Scale(domain=x_domain),
        ),
        x2="p95:Q",
    )
    boxes = base.mark_bar(size=50, color="#4c78a8").encode(
        x=alt.X("q1:Q", scale=alt.Scale(domain=x_domain)),
        x2="q3:Q",
    )
    medians = base.mark_bar(size=50, color=MEDIAN_COLOR).encode(
        x=alt.X("median_lower:Q", scale=alt.Scale(domain=x_domain)),
        x2="median_upper:Q",
    )
    chart_height = max(500, len(category_order) * 85)
    boxplots = (whiskers + boxes + medians).properties(
        title=alt.TitleParams(
            f"DUR duration by job title — {cohort_title}",
            subtitle="Boxes show the IQR and whiskers show the 5th–95th percentiles; summary statistics are in the table below",
            anchor="start",
        ),
        width=1100,
        height=chart_height,
    )
    label_panel = (
        alt.Chart(summary)
        .mark_text(align="left", fontSize=18)
        .encode(
            x=alt.value(4),
            y=alt.Y(
                "job_title:N",
                sort=category_labels,
                scale=y_scale,
                axis=None,
            ),
            text=alt.Text("job_title:N"),
        )
        .properties(width=360, height=chart_height)
    )
    boxplot_layout = alt.hconcat(label_panel, boxplots).resolve_scale(y="shared")

    table_height = max(190, len(category_order) * 34)
    table_y_scale = alt.Scale(paddingInner=0.25, paddingOuter=0.15)

    def table_column(
        field: str, title: str, width: int, align: str
    ) -> alt.Chart:
        return (
            alt.Chart(summary)
            .mark_text(align=align, baseline="middle", fontSize=15)
            .encode(
                x=alt.value(0 if align == "left" else width - 10),
                y=alt.Y(
                    "job_title:N",
                    sort=category_labels,
                    scale=table_y_scale,
                    axis=None,
                ),
                text=alt.Text(f"{field}:N"),
            )
            .properties(
                title=alt.TitleParams(title, anchor="middle"),
                width=width,
                height=table_height,
            )
        )

    table = alt.hconcat(
        table_column("job_title", "Job title", 600, "left"),
        table_column("task_count_label", "DUR count", 200, "right"),
        table_column("median_label", "Median (s)", 200, "right"),
        table_column("maximum_label", "Maximum (s)", 200, "right"),
        table_column("average_label", "Average (s)", 200, "right"),
        table_column("stddev_label", "Std dev (s)", 200, "right"),
    ).resolve_scale(y="shared")
    return (
        alt.vconcat(boxplot_layout, table)
        .configure(background=FIGURE_BACKGROUND)
        .configure_view(stroke=None, fill=FIGURE_BACKGROUND)
    )


def job_title_count_strip_chart(frame: pd.DataFrame) -> alt.Chart:
    chart_frame = normalize_task_duration_frame(frame)
    if chart_frame.empty:
        raise ValueError("the query returned no task-duration rows")
    if "task_id" in chart_frame.columns:
        counts = (
            chart_frame.groupby("job_title", as_index=False)["task_id"]
            .nunique()
            .rename(columns={"task_id": "task_count"})
        )
    else:
        counts = (
            chart_frame.groupby("job_title", as_index=False)
            .size()
            .rename(columns={"size": "task_count"})
        )
    category_order = sorted(
        counts["job_title"].tolist(),
        key=lambda value: (-int(counts.loc[counts["job_title"] == value, "task_count"].iloc[0]), natural_sort_key(value)),
    )
    counts["count_label"] = counts["task_count"].map(lambda value: f"{value:,}")
    x_domain = [0, max(float(counts["task_count"].max()) * 1.15, 1.0)]
    base = alt.Chart(counts).encode(
        y=alt.Y("job_title:N", title="Job title", sort=category_order),
        x=alt.X(
            "task_count:Q",
            title="Filtered DUR tasks",
            scale=alt.Scale(domain=x_domain),
        ),
        tooltip=[
            alt.Tooltip("job_title:N", title="Job title"),
            alt.Tooltip("task_count:Q", title="DUR tasks", format=",.0f"),
        ],
    )
    bars = base.mark_bar(size=24, color="#4c78a8")
    labels = base.mark_text(align="left", dx=5, fontSize=14).encode(
        text=alt.Text("count_label:N")
    )
    return (bars + labels).properties(
        title=alt.TitleParams(
            "Filtered DUR tasks by job title — All cohorts",
            subtitle="Counts are based on the same global approximate 95th-percentile duration filter as the boxplots",
            anchor="start",
        ),
        width=1100,
        height=max(300, len(category_order) * 45),
    ).configure(background=FIGURE_BACKGROUND).configure_view(
        stroke=None, fill=FIGURE_BACKGROUND
    )


def violin_chart(frame: pd.DataFrame) -> alt.Chart:
    chart_frame = frame.copy()
    cohort_order = sorted(chart_frame["coh"].dropna().unique().tolist(), key=natural_sort_key)
    duration_max = float(chart_frame["duration_seconds"].max())
    panels = []
    for cohort in cohort_order:
        cohort_frame = chart_frame.loc[chart_frame["coh"] == cohort].copy()
        cohort_frame["density"] = 0.0
        density = (
            alt.Chart(cohort_frame)
            .transform_density(
                "duration_seconds",
                as_=["duration_seconds", "density"],
                extent=[0, duration_max],
                steps=200,
            )
            .transform_calculate(density_negative="-datum.density")
            .mark_area(orient="horizontal", interpolate="monotone", opacity=0.8)
            .encode(
                y=alt.Y("duration_seconds:Q", title="DUR task duration (seconds)"),
                x=alt.X(
                    "density_negative:Q",
                    title=None,
                    axis=None,
                    scale=alt.Scale(domain=[-0.15, 0.15]),
                ),
                x2="density:Q",
                color=alt.value("#4c78a8"),
            )
        )
        quartile_values = cohort_frame["duration_seconds"].quantile([0.25, 0.50, 0.75])
        quartile_frame = pd.DataFrame(
            {
                "quartile": ["25th percentile", "50th percentile (median)", "75th percentile"],
                "quartile_seconds": [
                    quartile_values.loc[0.25],
                    quartile_values.loc[0.50],
                    quartile_values.loc[0.75],
                ],
            }
        )
        quartile_frame["label_x"] = -0.145
        quartile_frame["quartile_label"] = quartile_frame.apply(
            lambda row: f"{row['quartile']}: {row['quartile_seconds']:,.1f}s",
            axis=1,
        )
        quartile_rules = (
            alt.Chart(quartile_frame)
            .mark_rule(color="#d62728", size=2)
            .encode(
                y=alt.Y("quartile_seconds:Q", title="DUR task duration (seconds)"),
                tooltip=[
                    alt.Tooltip("quartile:N", title="Statistic"),
                    alt.Tooltip("quartile_seconds:Q", title="Seconds", format=",.2f"),
                ],
            )
        )
        quartile_labels = (
            alt.Chart(quartile_frame)
            .mark_text(color="#d62728", align="left", dx=4, dy=-6, fontSize=10)
            .encode(
                x=alt.X(
                    "label_x:Q",
                    axis=None,
                    scale=alt.Scale(domain=[-0.15, 0.15]),
                ),
                y=alt.Y("quartile_seconds:Q"),
                text=alt.Text("quartile_label:N"),
            )
        )
        panels.append(
            (density + quartile_rules + quartile_labels)
            .properties(title=cohort, width=220, height=500)
            .resolve_scale(y="shared")
        )
    return alt.hconcat(*panels).properties(
            title=alt.TitleParams(
                "DUR task duration violin plots by cohort",
                subtitle="Red horizontal lines mark the 25th percentile, median (50th percentile), and 75th percentile",
                anchor="start",
            )
        ).resolve_scale(y="shared").configure(background=FIGURE_BACKGROUND).configure_view(
            stroke=None, fill=FIGURE_BACKGROUND
        )


def create_outputs(frame: pd.DataFrame, task_duration_frame: pd.DataFrame | None = None) -> list[Path]:
    if frame.empty:
        raise ValueError("the filtered task query returned no rows")

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for filename in LEGACY_OUTPUT_FILENAMES:
        (OUTPUT_DIRECTORY / filename).unlink(missing_ok=True)
    outputs: list[Path] = []
    markdown_charts: list[tuple[str, str]] = []
    for dimension, row_title in DIMENSIONS:
        dimension_frame = frame.loc[frame["dimension_type"] == dimension].copy()
        if dimension_frame.empty:
            raise ValueError(f"the query returned no rows for dimension: {dimension}")

        filename = f"task-summary-by-{dimension}-and-cohort.png"
        path = OUTPUT_DIRECTORY / filename
        summary_chart(dimension_frame, row_title).save(path, scale_factor=2)
        outputs.append(path)
        markdown_charts.append((f"Task summary by {row_title.lower()} and cohort", filename))

    if task_duration_frame is not None and not task_duration_frame.empty:
        task_duration_frame = normalize_task_duration_frame(task_duration_frame)
        filename = "task-duration-by-cohort-boxplots.png"
        path = OUTPUT_DIRECTORY / filename
        boxplot_chart(task_duration_frame).save(path, scale_factor=2)
        outputs.append(path)
        markdown_charts.append(("DUR task duration by cohort boxplots", filename))
        filename = "task-duration-by-cohort-violin-plots.png"
        path = OUTPUT_DIRECTORY / filename
        violin_chart(task_duration_frame).save(path, scale_factor=2)
        outputs.append(path)
        markdown_charts.append(("DUR task duration by cohort violin plots", filename))
        for cohort in ("Cohort 1", "Cohort 2", "Cohort 3", "Cohort 4"):
            filename = (
                f"task-duration-by-job-title-{cohort.lower().replace(' ', '-')}-boxplots.png"
            )
            path = OUTPUT_DIRECTORY / filename
            job_title_boxplot_chart(task_duration_frame, cohort).save(path, scale_factor=2)
            outputs.append(path)
            markdown_charts.append((f"DUR duration by job title — {cohort}", filename))

        filename = "task-duration-by-job-title-all-cohorts-boxplots.png"
        path = OUTPUT_DIRECTORY / filename
        job_title_boxplot_chart(task_duration_frame).save(path, scale_factor=2)
        outputs.append(path)
        markdown_charts.append(("DUR duration by job title — All cohorts", filename))

        filename = "task-dur-count-by-job-title-strip.png"
        path = OUTPUT_DIRECTORY / filename
        job_title_count_strip_chart(task_duration_frame).save(path, scale_factor=2)
        outputs.append(path)
        markdown_charts.append(("Filtered DUR task counts by job title", filename))

    outputs.append(write_markdown(markdown_charts))
    return outputs


@click.command()
@click.option(
    "--env-file",
    type=click.Path(path_type=Path, dir_okay=False),
    default=Path(".env"),
    show_default=True,
    help="Local Snowflake connection settings.",
)
@click.option(
    "--redraw-only",
    is_flag=True,
    help="Redraw from cached Parquet data without connecting to Snowflake.",
)
def main(env_file: Path, redraw_only: bool) -> None:
    """Query MY_RXP_TASKS and render task-distribution PNGs."""
    try:
        if redraw_only:
            if not DATA_PATH.is_file():
                raise ValueError(f"cached Parquet data not found: {DATA_PATH}")
            if not TASK_DURATION_DATA_PATH.is_file():
                raise ValueError(f"cached task-duration data not found: {TASK_DURATION_DATA_PATH}")
            frame = read_data()
            task_duration_frame = read_task_duration_data()
            click.echo(f"Loaded cached chart data: {DATA_PATH}")
        else:
            sql_path = write_generated_sql()
            click.echo(f"Wrote generated SQL: {sql_path}")
            if not env_file.is_file():
                raise ValueError(f"environment file not found: {env_file}")
            settings = parse_dotenv(env_file)
            missing = [key for key in REQUIRED_SETTINGS if key not in settings]
            if missing:
                raise ValueError("missing required settings: " + ", ".join(missing))
            frame = fetch_aggregates(settings)
            task_duration_frame = fetch_task_durations(settings)
            data_path = write_data(frame)
            task_duration_data_path = write_task_duration_data(task_duration_frame)
            click.echo(f"Saved chart data: {data_path}")
            click.echo(f"Saved task-duration data: {task_duration_data_path}")
        outputs = create_outputs(frame, task_duration_frame)
    except (ImportError, OSError, ValueError) as error:
        raise click.ClickException(str(error)) from error

    click.echo(f"Created {len(outputs) - 1} PNG charts and {outputs[-1]}.")


if __name__ == "__main__":
    main()
