#!/usr/bin/env python3
"""Create DUR-duration histograms split by task intersection status."""

from __future__ import annotations

from pathlib import Path
import re

import altair as alt
import click
import pandas as pd

from .generate_task_table import REQUIRED_SETTINGS, connect_to_snowflake, parse_dotenv

TASK_TABLE = "EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASKS"
SEQUENCE_TABLE = "EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASKS_WITH_SEQUENCE"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIRECTORY = REPOSITORY_ROOT / "outputs" / "charts" / "task-intersection-duration-distributions"
DATA_PATH = REPOSITORY_ROOT / "outputs" / "data" / "task-intersection-duration-distributions.parquet"
GENERATED_SQL_PATH = REPOSITORY_ROOT / "generated" / "create_task_intersection_duration_distributions.sql"
BIN_COUNT = 100
STATUS_ORDER = ("singletasking", "multitasking")

AGGREGATE_SQL = f"""
WITH joined_tasks AS (
    SELECT
        t.USER_ID,
        t.TASK_ID,
        t.COH,
        t.IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS AS DURATION_SECONDS,
        CASE
            WHEN s.N_INTERSECTING_TASKS > 0 THEN 'multitasking'
            ELSE 'singletasking'
        END AS INTERSECTION_STATUS
    FROM {TASK_TABLE} AS t
    INNER JOIN {SEQUENCE_TABLE} AS s
        ON s.USER_ID = t.USER_ID
       AND s.TASK_ID = t.TASK_ID
    WHERE t.TASK_TYPE = 'DUR'
      AND t.COH <> 'Unknown'
      AND LOWER(t.IS_REFILL) = 'false'
      AND t.HANDOFF_TYPE IS NULL
      AND t.IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY t.USER_ID, t.TASK_ID
        ORDER BY t.CLOSED_AT DESC NULLS LAST
    ) = 1
), percentile_bounds AS (
    SELECT APPROX_PERCENTILE(DURATION_SECONDS, 0.95) AS P95_SECONDS
    FROM joined_tasks
), filtered_tasks AS (
    SELECT task.*
    FROM joined_tasks AS task
    CROSS JOIN percentile_bounds
    WHERE task.DURATION_SECONDS < percentile_bounds.P95_SECONDS
), bounds AS (
    SELECT
        MIN(DURATION_SECONDS) AS MIN_SECONDS,
        MAX(DURATION_SECONDS) AS MAX_SECONDS
    FROM filtered_tasks
), numbered AS (
    SELECT
        task.INTERSECTION_STATUS,
        task.COH,
        CASE
            WHEN bounds.MAX_SECONDS = bounds.MIN_SECONDS THEN 1
            ELSE LEAST(
                {BIN_COUNT},
                FLOOR(
                    (task.DURATION_SECONDS - bounds.MIN_SECONDS)
                    / NULLIF(bounds.MAX_SECONDS - bounds.MIN_SECONDS, 0)
                    * {BIN_COUNT}
                ) + 1
            )
        END AS BIN_NUMBER
    FROM filtered_tasks AS task
    CROSS JOIN bounds
), aggregates AS (
    SELECT
        INTERSECTION_STATUS,
        COH,
        BIN_NUMBER,
        COUNT(*) AS TASK_COUNT
    FROM numbered
    GROUP BY INTERSECTION_STATUS, COH, BIN_NUMBER
), group_stats AS (
    SELECT
        INTERSECTION_STATUS,
        COH,
        AVG(DURATION_SECONDS) AS AVERAGE_DURATION_SECONDS,
        MEDIAN(DURATION_SECONDS) AS MEDIAN_DURATION_SECONDS
    FROM filtered_tasks
    GROUP BY INTERSECTION_STATUS, COH
), statuses AS (
    SELECT COLUMN1::VARCHAR AS INTERSECTION_STATUS
    FROM VALUES ('singletasking'), ('multitasking')
), cohorts AS (
    SELECT DISTINCT COH
    FROM filtered_tasks
), bins AS (
    SELECT SEQ4() + 1 AS BIN_NUMBER
    FROM TABLE(GENERATOR(ROWCOUNT => {BIN_COUNT}))
), grid AS (
    SELECT
        statuses.INTERSECTION_STATUS,
        cohorts.COH,
        bins.BIN_NUMBER
    FROM statuses
    CROSS JOIN cohorts
    CROSS JOIN bins
)
SELECT
    grid.INTERSECTION_STATUS,
    grid.COH,
    grid.BIN_NUMBER,
    COALESCE(aggregates.TASK_COUNT, 0) AS TASK_COUNT,
    group_stats.AVERAGE_DURATION_SECONDS,
    group_stats.MEDIAN_DURATION_SECONDS,
    bounds.MIN_SECONDS,
    bounds.MAX_SECONDS,
    CASE
        WHEN bounds.MAX_SECONDS = bounds.MIN_SECONDS THEN bounds.MIN_SECONDS
        ELSE bounds.MIN_SECONDS
             + (grid.BIN_NUMBER - 1)
             * (bounds.MAX_SECONDS - bounds.MIN_SECONDS) / {BIN_COUNT}
    END AS BIN_START_SECONDS,
    CASE
        WHEN bounds.MAX_SECONDS = bounds.MIN_SECONDS THEN bounds.MAX_SECONDS + 1
        ELSE bounds.MIN_SECONDS
             + grid.BIN_NUMBER
             * (bounds.MAX_SECONDS - bounds.MIN_SECONDS) / {BIN_COUNT}
    END AS BIN_END_SECONDS
FROM grid
LEFT JOIN aggregates
    ON aggregates.INTERSECTION_STATUS = grid.INTERSECTION_STATUS
   AND aggregates.COH = grid.COH
   AND aggregates.BIN_NUMBER = grid.BIN_NUMBER
LEFT JOIN group_stats
    ON group_stats.INTERSECTION_STATUS = grid.INTERSECTION_STATUS
   AND group_stats.COH = grid.COH
CROSS JOIN bounds
ORDER BY grid.INTERSECTION_STATUS, grid.COH, grid.BIN_NUMBER
""".strip()


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
    for column in (
        "bin_number",
        "task_count",
        "min_seconds",
        "max_seconds",
        "bin_start_seconds",
        "bin_end_seconds",
        "average_duration_seconds",
        "median_duration_seconds",
    ):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def write_data(frame: pd.DataFrame) -> Path:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(DATA_PATH, index=False)
    return DATA_PATH


def read_data() -> pd.DataFrame:
    return pd.read_parquet(DATA_PATH)


def add_density(frame: pd.DataFrame) -> pd.DataFrame:
    chart_frame = frame.copy()
    group_columns = ["intersection_status", "coh"]
    totals = chart_frame.groupby(group_columns)["task_count"].transform("sum")
    widths = chart_frame["bin_end_seconds"] - chart_frame["bin_start_seconds"]
    chart_frame["density"] = chart_frame["task_count"] / totals / widths
    chart_frame["bin_midpoint_seconds"] = (
        chart_frame["bin_start_seconds"] + chart_frame["bin_end_seconds"]
    ) / 2
    return chart_frame


def create_chart(frame: pd.DataFrame, status: str, x_domain: list[float]) -> alt.Chart:
    chart_frame = add_density(frame.loc[frame["intersection_status"] == status])
    if chart_frame.empty:
        raise ValueError(f"the query returned no rows for {status} tasks")
    cohort_order = sorted(chart_frame["coh"].dropna().unique().tolist(), key=natural_sort_key)
    return (
        alt.Chart(chart_frame)
        .mark_area(interpolate="step-after", opacity=0.55)
        .encode(
            x=alt.X(
                "bin_midpoint_seconds:Q",
                title="Imputed DUR duration (seconds)",
                scale=alt.Scale(domain=x_domain),
                axis=alt.Axis(grid=True, gridColor="#b0b0b0", gridOpacity=1, gridWidth=1),
            ),
            y=alt.Y(
                "density:Q",
                title="Density (per second)",
                scale=alt.Scale(zero=True),
                axis=alt.Axis(grid=True, gridColor="#b0b0b0", gridOpacity=1, gridWidth=1),
            ),
            tooltip=[
                alt.Tooltip("coh:N", title="Cohort"),
                alt.Tooltip("bin_start_seconds:Q", title="Bin start (seconds)", format=",.1f"),
                alt.Tooltip("bin_end_seconds:Q", title="Bin end (seconds)", format=",.1f"),
                alt.Tooltip("task_count:Q", title="DUR tasks", format=",.0f"),
                alt.Tooltip("density:Q", title="Density", format=".6f"),
            ],
        )
        .properties(width=900, height=150)
        .facet(
            row=alt.Row("coh:N", title="Cohort", sort=cohort_order),
        )
        .resolve_scale(x="shared", y="independent")
        .properties(
            title=alt.TitleParams(
                f"DUR duration distribution — {status}",
                subtitle="One shaded 100-bin density distribution per cohort; panels share the x-axis and use independent y-scales",
                anchor="start",
            ),
        )
        .configure_view(stroke=None)
    )


def create_combined_chart(frame: pd.DataFrame, x_domain: list[float]) -> alt.Chart:
    chart_frame = add_density(frame)
    cohort_order = sorted(chart_frame["coh"].dropna().unique().tolist(), key=natural_sort_key)
    group_max_density = chart_frame.groupby("coh")["density"].max()
    group_task_count = chart_frame.groupby(["intersection_status", "coh"])["task_count"].transform("sum")
    chart_frame["label_density"] = chart_frame["coh"].map(group_max_density)
    chart_frame["group_task_count"] = group_task_count
    chart_frame["label_x"] = max(
        80.0,
        x_domain[0] + (x_domain[1] - x_domain[0]) * 0.72,
    )
    chart_frame["summary_label"] = chart_frame.apply(
        lambda row: (
            f"{row['intersection_status']}: "
            f"n {row['group_task_count']:,.0f}; "
            f"mean {row['average_duration_seconds']:.1f}s; "
            f"median {row['median_duration_seconds']:.1f}s"
        ),
        axis=1,
    )
    area = (
        alt.Chart(chart_frame)
        .mark_area(interpolate="step-after", opacity=0.45)
        .encode(
            x=alt.X(
                "bin_midpoint_seconds:Q",
                title="Imputed DUR duration (seconds)",
                scale=alt.Scale(domain=x_domain),
                axis=alt.Axis(grid=True, gridColor="#b0b0b0", gridOpacity=1, gridWidth=1),
            ),
            y=alt.Y(
                "density:Q",
                title="Density (per second)",
                scale=alt.Scale(zero=True),
                axis=alt.Axis(grid=True, gridColor="#b0b0b0", gridOpacity=1, gridWidth=1),
            ),
            color=alt.Color(
                "intersection_status:N",
                title="Task type",
                sort=list(STATUS_ORDER),
                scale=alt.Scale(range=["#4C78A8", "#F58518"]),
            ),
            detail=alt.Detail("intersection_status:N"),
            tooltip=[
                alt.Tooltip("coh:N", title="Cohort"),
                alt.Tooltip("intersection_status:N", title="Task type"),
                alt.Tooltip("bin_start_seconds:Q", title="Bin start (seconds)", format=",.1f"),
                alt.Tooltip("bin_end_seconds:Q", title="Bin end (seconds)", format=",.1f"),
                alt.Tooltip("task_count:Q", title="DUR tasks", format=",.0f"),
                alt.Tooltip("density:Q", title="Density", format=".6f"),
            ],
        )
        .properties(width=900, height=150)
    )
    def label_layer(status: str, dy: int) -> alt.Chart:
        return (
            alt.Chart(chart_frame)
            .transform_filter(
                f"datum.bin_number == 1 && datum.intersection_status == '{status}'"
            )
            .mark_text(align="left", baseline="bottom", dy=dy, fontSize=11)
            .encode(
                x=alt.X("label_x:Q", scale=alt.Scale(domain=x_domain), axis=None),
                y=alt.Y("label_density:Q", scale=alt.Scale(zero=True), axis=None),
                text=alt.Text("summary_label:N"),
                color=alt.value("#4C78A8" if status == STATUS_ORDER[0] else "#F58518"),
            )
        )

    labels = label_layer(STATUS_ORDER[0], -8) + label_layer(STATUS_ORDER[1], -24)
    grid = (
        alt.Chart(chart_frame)
        .transform_filter(
            f"datum.bin_number % 10 == 1 && datum.intersection_status == '{STATUS_ORDER[0]}'"
        )
        .mark_rule(color="#b0b0b0", opacity=0.45)
        .encode(x=alt.X("bin_midpoint_seconds:Q", scale=alt.Scale(domain=x_domain)))
    )
    return (
        (grid + area + labels)
        .facet(row=alt.Row("coh:N", title="Cohort", sort=cohort_order))
        .resolve_scale(x="shared", y="independent")
        .properties(
            title=alt.TitleParams(
                "DUR duration distribution by task classification",
                subtitle="Each cohort panel compares singletasking and multitasking density distributions; panels share the x-axis and use independent y-scales",
                anchor="start",
            ),
        )
        .configure_view(stroke=None)
        .configure_axis(grid=True, gridColor="#b0b0b0", gridOpacity=1, gridWidth=1)
    )


def write_markdown(paths: list[tuple[str, str]]) -> Path:
    lines = [
        "# DUR duration distributions by task classification",
        "",
        "Filters: `TASK_TYPE = 'DUR'`, `COH <> 'Unknown'`, "
        "`LOWER(IS_REFILL) = 'false'`, and `HANDOFF_TYPE IS NULL`.",
        "Durations use `IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS`; values at or above the filtered population's approximate 95th percentile are excluded. The combined chart shows per-cohort density distributions using a shared x-axis, independent y-scales from zero, and 100 bins.",
        "Each cohort panel is annotated with task count, mean, and median duration for both classifications.",
        "The cached aggregate data is stored at `outputs/data/task-intersection-duration-distributions.parquet` for redraw-only runs.",
        "",
    ]
    for title, filename in paths:
        lines.extend((f"## {title}", "", f"![{title}]({filename})", ""))
    path = OUTPUT_DIRECTORY / "README.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def create_outputs(frame: pd.DataFrame) -> list[Path]:
    if frame.empty:
        raise ValueError("the filtered task query returned no rows")
    if frame["coh"].dropna().nunique() != 4:
        raise ValueError("expected four non-Unknown cohorts in the filtered task query")

    min_seconds = float(frame["min_seconds"].min())
    max_seconds = float(frame["max_seconds"].max())
    x_domain = [min_seconds, max_seconds if max_seconds > min_seconds else min_seconds + 1]

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for path in OUTPUT_DIRECTORY.glob("*.png"):
        path.unlink()
    outputs: list[Path] = []
    markdown_paths: list[tuple[str, str]] = []
    combined_path = OUTPUT_DIRECTORY / "intersecting-and-non-intersecting.png"
    create_combined_chart(frame, x_domain).save(combined_path, scale_factor=2)
    outputs.append(combined_path)
    markdown_paths.insert(
        0,
        ("Singletasking and multitasking", combined_path.name),
    )
    outputs.append(write_markdown(markdown_paths))
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
    help="Redraw from the cached Parquet data without connecting to Snowflake.",
)
def main(env_file: Path, redraw_only: bool) -> None:
    """Render DUR duration histograms for intersecting and non-intersecting tasks."""
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
