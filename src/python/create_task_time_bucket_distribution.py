#!/usr/bin/env python3
"""Create a UTC two-hour task distribution chart from MY_RXP_TASKS."""

from __future__ import annotations

from pathlib import Path
import re

import altair as alt
import click
import pandas as pd

from .generate_task_table import REQUIRED_SETTINGS, connect_to_snowflake, parse_dotenv

SOURCE_TABLE = "EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASKS"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIRECTORY = REPOSITORY_ROOT / "outputs" / "charts" / "task-time-bucket-distribution"
DATA_PATH = REPOSITORY_ROOT / "outputs" / "data" / "task-time-bucket-distribution.parquet"
GENERATED_SQL_PATH = REPOSITORY_ROOT / "generated" / "create_task_time_bucket_distribution.sql"

AGGREGATE_SQL = f"""
WITH base_tasks AS (
    SELECT
        TASK_ID,
        USER_ID,
        COH,
        COALESCE(WH_ID, '<Missing>') AS WH_ID,
        IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS AS DURATION_SECONDS,
        FLOOR(
            DATE_PART('HOUR', PROCESS_START_TIME) / 2
        ) * 2 AS BUCKET_START_HOUR
    FROM {SOURCE_TABLE}
    WHERE TASK_TYPE = 'DUR'
      AND COH <> 'Unknown'
      AND LOWER(IS_REFILL) = 'false'
      AND HANDOFF_TYPE IS NULL
      AND PROCESS_START_TIME IS NOT NULL
), percentile_bounds AS (
    SELECT APPROX_PERCENTILE(DURATION_SECONDS, 0.95) AS P95_SECONDS
    FROM base_tasks
), filtered_tasks AS (
    SELECT base.*
    FROM base_tasks AS base
    CROSS JOIN percentile_bounds
    WHERE base.DURATION_SECONDS < percentile_bounds.P95_SECONDS
), scopes AS (
    SELECT
        0 AS SCOPE_ORDER,
        'All warehouses' AS SCOPE_NAME,
        COH,
        BUCKET_START_HOUR,
        TASK_ID,
        USER_ID,
        DURATION_SECONDS
    FROM filtered_tasks
    UNION ALL
    SELECT
        1 AS SCOPE_ORDER,
        WH_ID AS SCOPE_NAME,
        COH,
        BUCKET_START_HOUR,
        TASK_ID,
        USER_ID,
        DURATION_SECONDS
    FROM filtered_tasks
), aggregates AS (
    SELECT
        SCOPE_ORDER,
        SCOPE_NAME,
        COH,
        BUCKET_START_HOUR,
        COUNT(DISTINCT TASK_ID) AS UNIQUE_TASK_COUNT,
        COUNT(DISTINCT USER_ID) AS UNIQUE_USER_COUNT,
        AVG(DURATION_SECONDS) AS AVERAGE_DURATION_SECONDS,
        MEDIAN(DURATION_SECONDS) AS MEDIAN_DURATION_SECONDS,
        STDDEV_SAMP(DURATION_SECONDS) AS STDDEV_DURATION_SECONDS
    FROM scopes
    GROUP BY SCOPE_ORDER, SCOPE_NAME, COH, BUCKET_START_HOUR
), scope_names AS (
    SELECT 0 AS SCOPE_ORDER, 'All warehouses' AS SCOPE_NAME
    UNION ALL
    SELECT DISTINCT 1, WH_ID
    FROM filtered_tasks
), cohorts AS (
    SELECT DISTINCT COH
    FROM filtered_tasks
), bucket_hours AS (
    SELECT COLUMN1::NUMBER AS BUCKET_START_HOUR
    FROM VALUES (0), (2), (4), (6), (8), (10), (12), (14), (16), (18), (20), (22)
), complete_grid AS (
    SELECT
        s.SCOPE_ORDER,
        s.SCOPE_NAME,
        c.COH,
        b.BUCKET_START_HOUR
    FROM scope_names AS s
    CROSS JOIN cohorts AS c
    CROSS JOIN bucket_hours AS b
)
SELECT
    g.SCOPE_ORDER,
    g.SCOPE_NAME,
    g.COH,
    g.BUCKET_START_HOUR,
    COALESCE(a.UNIQUE_TASK_COUNT, 0) AS UNIQUE_TASK_COUNT,
    COALESCE(a.UNIQUE_USER_COUNT, 0) AS UNIQUE_USER_COUNT,
    a.AVERAGE_DURATION_SECONDS,
    a.MEDIAN_DURATION_SECONDS,
    a.STDDEV_DURATION_SECONDS
FROM complete_grid AS g
LEFT JOIN aggregates AS a
    ON a.SCOPE_ORDER = g.SCOPE_ORDER
   AND a.SCOPE_NAME = g.SCOPE_NAME
   AND a.COH = g.COH
   AND a.BUCKET_START_HOUR = g.BUCKET_START_HOUR
ORDER BY g.SCOPE_ORDER, g.SCOPE_NAME, g.COH, g.BUCKET_START_HOUR
""".strip()

NUMERIC_COLUMNS = (
    "scope_order",
    "bucket_start_hour",
    "unique_task_count",
    "unique_user_count",
    "average_duration_seconds",
    "median_duration_seconds",
    "stddev_duration_seconds",
)


def natural_sort_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def write_generated_sql() -> Path:
    GENERATED_SQL_PATH.parent.mkdir(parents=True, exist_ok=True)
    GENERATED_SQL_PATH.write_text(AGGREGATE_SQL + "\n", encoding="utf-8")
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
    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def write_data(frame: pd.DataFrame) -> Path:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(DATA_PATH, index=False)
    return DATA_PATH


def read_data() -> pd.DataFrame:
    return pd.read_parquet(DATA_PATH)


def bucket_label(hour: int) -> str:
    end_hour = hour + 1
    return f"{hour:02d}:00–{end_hour:02d}:59"


def prepare_chart_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    chart_frame = frame.copy()
    chart_frame["bucket_label"] = chart_frame["bucket_start_hour"].map(
        lambda value: bucket_label(int(value))
    )
    chart_frame["row_label"] = chart_frame["coh"]
    chart_frame["count_label"] = chart_frame["unique_task_count"].map(
        lambda value: f"Tasks {value:,.0f}"
    )
    chart_frame["user_label"] = chart_frame["unique_user_count"].map(
        lambda value: f"Users {value:,.0f}"
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

    rows = chart_frame[["scope_order", "scope_name", "coh", "row_label"]].drop_duplicates()
    ordered_rows = sorted(
        rows.itertuples(index=False),
        key=lambda row: (
            row.scope_order,
            natural_sort_key(row.scope_name),
            natural_sort_key(row.coh),
        ),
    )
    row_order = [row.row_label for row in ordered_rows]
    return chart_frame, row_order


def create_chart(frame: pd.DataFrame, scope_name: str) -> alt.Chart:
    if frame.empty:
        raise ValueError("the filtered task query returned no rows")

    chart_frame, row_order = prepare_chart_frame(frame)
    bucket_order = [bucket_label(hour) for hour in range(0, 24, 2)]
    threshold = float(chart_frame["unique_task_count"].max()) * 0.55
    text_color = alt.condition(
        f"datum.unique_task_count > {threshold}",
        alt.value("white"),
        alt.value("#111111"),
    )
    base = (
        alt.Chart(chart_frame)
        .encode(
            x=alt.X(
                "bucket_label:N",
                title="Process start time (UTC)",
                sort=bucket_order,
                axis=alt.Axis(labelAngle=0),
            ),
            y=alt.Y("row_label:N", title="Cohort", sort=row_order),
        )
        .properties(
            title=alt.TitleParams(
                f"DUR task statistics by two-hour UTC process-start bucket — {scope_name}",
                subtitle="One row per cohort; cell color represents unique task count",
                anchor="start",
            ),
            width=alt.Step(155),
            height=alt.Step(68),
        )
    )
    rectangles = base.mark_rect().encode(
        color=alt.Color(
            "unique_task_count:Q",
            title="Unique tasks",
            scale=alt.Scale(scheme="blues"),
        ),
        tooltip=[
            alt.Tooltip("scope_name:N", title="Warehouse"),
            alt.Tooltip("coh:N", title="Cohort"),
            alt.Tooltip("bucket_label:N", title="UTC bucket"),
            alt.Tooltip("unique_task_count:Q", title="Unique tasks", format=",.0f"),
            alt.Tooltip("unique_user_count:Q", title="Unique users", format=",.0f"),
            alt.Tooltip("average_duration_seconds:Q", title="Mean seconds", format=",.2f"),
            alt.Tooltip("median_duration_seconds:Q", title="Median seconds", format=",.2f"),
            alt.Tooltip("stddev_duration_seconds:Q", title="SD seconds", format=",.2f"),
        ],
    )
    label_specs = (
        ("count_label:N", -24, 10, "bold"),
        ("user_label:N", -12, 9, "bold"),
        ("mean_label:N", 0, 9, "normal"),
        ("median_label:N", 12, 9, "normal"),
        ("stddev_label:N", 24, 9, "normal"),
    )
    layers: list[alt.Chart] = [rectangles]
    for field, dy, font_size, font_weight in label_specs:
        layers.append(
            base.mark_text(dy=dy, fontSize=font_size, fontWeight=font_weight).encode(
                text=field,
                color=text_color,
            )
        )
    return alt.layer(*layers).configure_view(stroke=None)


def filename_for_scope(scope_name: str) -> str:
    if scope_name == "All warehouses":
        return "task-time-bucket-distribution-overall.png"
    slug = re.sub(r"[^a-z0-9]+", "-", scope_name.lower()).strip("-") or "missing"
    return f"task-time-bucket-distribution-{slug}.png"


def write_markdown(chart_files: list[tuple[str, str]]) -> Path:
    lines = [
        "# Task time-bucket distributions",
        "",
        "Each chart groups DUR tasks into twelve two-hour UTC process-start buckets and shows unique task count, unique user count, and imputed-dwell mean, median, and standard deviation.",
        "Values at or above the filtered population's approximate 95th percentile are excluded.",
        "Cached aggregate data is stored at `outputs/data/task-time-bucket-distribution.parquet` for redraw-only runs.",
        "",
    ]
    for scope_name, filename in chart_files:
        lines.extend((f"## {scope_name}", "", f"![{scope_name}]({filename})", ""))
    path = OUTPUT_DIRECTORY / "README.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def create_outputs(frame: pd.DataFrame) -> list[Path]:
    if frame.empty:
        raise ValueError("the filtered task query returned no rows")

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIRECTORY / "task-time-bucket-distribution.png").unlink(missing_ok=True)
    for stale_output in OUTPUT_DIRECTORY.glob("task-time-bucket-distribution-*.png"):
        stale_output.unlink()

    scope_rows = frame[["scope_order", "scope_name"]].drop_duplicates()
    ordered_scopes = sorted(
        scope_rows.itertuples(index=False),
        key=lambda row: (row.scope_order, natural_sort_key(row.scope_name)),
    )
    outputs: list[Path] = []
    markdown_charts: list[tuple[str, str]] = []
    for scope in ordered_scopes:
        scope_frame = frame.loc[frame["scope_name"] == scope.scope_name].copy()
        filename = filename_for_scope(scope.scope_name)
        path = OUTPUT_DIRECTORY / filename
        create_chart(scope_frame, scope.scope_name).save(path, scale_factor=2)
        outputs.append(path)
        markdown_charts.append((scope.scope_name, filename))

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
    """Render overall and per-warehouse charts using two-hour UTC buckets."""
    try:
        if redraw_only:
            if not DATA_PATH.is_file():
                raise ValueError(f"cached Parquet data not found: {DATA_PATH}")
            frame = read_data()
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
            data_path = write_data(frame)
            click.echo(f"Saved chart data: {data_path}")
        outputs = create_outputs(frame)
    except (ImportError, OSError, ValueError) as error:
        raise click.ClickException(str(error)) from error

    click.echo(f"Created {len(outputs) - 1} PNG charts and {outputs[-1]}.")


if __name__ == "__main__":
    main()
