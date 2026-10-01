#!/usr/bin/env python3
"""Analyze DUR duration by part number and cohort."""

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
OUTPUT_DIRECTORY = REPOSITORY_ROOT / "outputs" / "charts" / "part-number-analysis"
DATA_PATH = REPOSITORY_ROOT / "outputs" / "data" / "part-number-analysis.parquet"
GENERATED_SQL_PATH = REPOSITORY_ROOT / "generated" / "create_part_number_analysis.sql"
COHORTS = ("Cohort 1", "Cohort 2", "Cohort 3", "Cohort 4")

AGGREGATE_SQL = f"""
WITH base_tasks AS (
    SELECT
        TASK_ID,
        USER_ID,
        COH,
        TRIM(PART_NUMBER::VARCHAR) AS PART_NUMBER,
        IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS AS DURATION_SECONDS
    FROM {SOURCE_TABLE}
    WHERE TASK_TYPE = 'DUR'
      AND COH <> 'Unknown'
      AND COH IN ('Cohort 1', 'Cohort 2', 'Cohort 3', 'Cohort 4')
      AND LOWER(IS_REFILL) = 'false'
      AND HANDOFF_TYPE IS NULL
      AND PART_NUMBER IS NOT NULL
      AND TRIM(PART_NUMBER::VARCHAR) <> ''
      AND IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS IS NOT NULL
), percentile_bounds AS (
    SELECT APPROX_PERCENTILE(DURATION_SECONDS, 0.95) AS P95_SECONDS
    FROM base_tasks
), filtered_tasks AS (
    SELECT base.*
    FROM base_tasks AS base
    CROSS JOIN percentile_bounds
    WHERE base.DURATION_SECONDS < percentile_bounds.P95_SECONDS
)
SELECT
    COH,
    PART_NUMBER,
    AVG(DURATION_SECONDS) AS AVERAGE_DURATION_SECONDS,
    MEDIAN(DURATION_SECONDS) AS MEDIAN_DURATION_SECONDS,
    STDDEV_SAMP(DURATION_SECONDS) AS STDDEV_DURATION_SECONDS,
    COUNT(DISTINCT TASK_ID) AS UNIQUE_TASK_COUNT,
    COUNT(DISTINCT USER_ID) AS UNIQUE_USER_COUNT
FROM filtered_tasks
GROUP BY COH, PART_NUMBER
ORDER BY COH, PART_NUMBER
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
        "average_duration_seconds",
        "median_duration_seconds",
        "stddev_duration_seconds",
        "unique_task_count",
        "unique_user_count",
    ):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def write_data(frame: pd.DataFrame) -> Path:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(DATA_PATH, index=False)
    return DATA_PATH


def read_data() -> pd.DataFrame:
    return pd.read_parquet(DATA_PATH)


def write_markdown(chart_files: list[tuple[str, str]]) -> Path:
    lines = [
        "# Part-number analysis",
        "",
        "DUR tasks are filtered to known cohorts, non-refill tasks, no handoff, and part numbers that are not null or blank.",
        "Durations at or above the filtered population's approximate 95th percentile are excluded.",
        "The combined boxplot uses product-level mean durations; boxes show the interquartile range and whiskers show the 5th–95th percentiles.",
        "Red points outside the whiskers are labeled with their part numbers.",
        "Tooltips include median duration, distinct task count, and distinct user count.",
        "Cached aggregate data is stored at `outputs/data/part-number-analysis.parquet` for redraw-only runs.",
        "",
    ]
    for title, filename in chart_files:
        lines.extend((f"## {title}", "", f"![{title}]({filename})", ""))
    path = OUTPUT_DIRECTORY / "README.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def create_boxplot(frame: pd.DataFrame) -> alt.Chart:
    chart_frame = frame.copy()
    chart_frame["part_number"] = chart_frame["part_number"].astype(str)
    duration_max = float(chart_frame["average_duration_seconds"].max())
    duration_min = float(chart_frame["average_duration_seconds"].min())
    y_domain = [min(0.0, duration_min), duration_max * 1.1]
    panels: list[alt.Chart] = []
    x_domain = [-0.5, 0.5]
    for cohort in COHORTS:
        cohort_frame = chart_frame.loc[chart_frame["coh"] == cohort].copy()
        if cohort_frame.empty:
            raise ValueError(f"the query returned no rows for {cohort}")

        quantiles = cohort_frame["average_duration_seconds"].quantile([0.05, 0.25, 0.50, 0.75, 0.95])
        summary = pd.DataFrame(
            {
                "x": [0.0],
                "median_lower": [-0.28],
                "median_upper": [0.28],
                "p05": [quantiles.loc[0.05]],
                "q1": [quantiles.loc[0.25]],
                "median": [quantiles.loc[0.50]],
                "q3": [quantiles.loc[0.75]],
                "p95": [quantiles.loc[0.95]],
            }
        )
        whiskers = alt.Chart(summary).mark_rule(size=2, color="#4c78a8").encode(
            x=alt.X("x:Q", axis=None, scale=alt.Scale(domain=x_domain)),
            y=alt.Y(
                "p05:Q",
                title="Product mean DUR duration (seconds)",
                scale=alt.Scale(domain=y_domain),
            ),
            y2="p95:Q",
        )
        boxes = alt.Chart(summary).mark_bar(size=90, color="#4c78a8").encode(
            x=alt.X("x:Q", axis=None, scale=alt.Scale(domain=x_domain)),
            y=alt.Y("q1:Q", scale=alt.Scale(domain=y_domain)),
            y2="q3:Q",
        )
        medians = alt.Chart(summary).mark_rule(size=4, color=MEDIAN_COLOR).encode(
            x=alt.X("median_lower:Q", axis=None, scale=alt.Scale(domain=x_domain)),
            x2="median_upper:Q",
            y=alt.Y("median:Q", scale=alt.Scale(domain=y_domain)),
        )

        outlier_candidates = cohort_frame.loc[
            (cohort_frame["average_duration_seconds"] < quantiles.loc[0.05])
            | (cohort_frame["average_duration_seconds"] > quantiles.loc[0.95])
        ].copy()
        outlier_frame = outlier_candidates.nlargest(5, "average_duration_seconds").copy()
        outlier_frame["point_x"] = 0.0
        outlier_frame["label_x"] = 0.08
        outlier_frame["part_label"] = outlier_frame.apply(
            lambda row: f"{row['part_number']} ({row['average_duration_seconds']:,.1f}s)",
            axis=1,
        )
        label_frame = outlier_frame.sort_values("average_duration_seconds").copy()
        if len(label_frame) > 1:
            label_spacing = max(
                (float(label_frame["average_duration_seconds"].max())
                 - float(label_frame["average_duration_seconds"].min()))
                / (len(label_frame) - 1),
                2.2,
            )
            label_start = float(label_frame["average_duration_seconds"].min())
            label_frame["label_y"] = [
                label_start + index * label_spacing for index in range(len(label_frame))
            ]
        else:
            label_frame["label_y"] = label_frame["average_duration_seconds"]
        outlier_points = alt.Chart(outlier_frame).mark_point(
            color="#d62728", filled=True, size=65, stroke="white", strokeWidth=1
        ).encode(
            x=alt.X("point_x:Q", axis=None, scale=alt.Scale(domain=x_domain)),
            y=alt.Y("average_duration_seconds:Q", scale=alt.Scale(domain=y_domain)),
            tooltip=[
                alt.Tooltip("part_number:N", title="Part number"),
                alt.Tooltip(
                    "average_duration_seconds:Q",
                    title="Product mean seconds",
                    format=",.2f",
                ),
            ],
        )
        outlier_labels = alt.Chart(label_frame).mark_text(
            align="left", dx=5, dy=-5, color="#d62728", fontSize=10
        ).encode(
            x=alt.X("label_x:Q", axis=None, scale=alt.Scale(domain=x_domain)),
            y=alt.Y("label_y:Q", scale=alt.Scale(domain=y_domain)),
            text=alt.Text("part_label:N"),
        )
        panels.append(
            (whiskers + boxes + medians + outlier_points + outlier_labels).properties(
                title=cohort,
                width=300,
                height=520,
            )
        )

    return alt.hconcat(*panels).properties(
        title=alt.TitleParams(
            "Product mean DUR duration boxplots by cohort",
            subtitle="Boxes show the IQR; whiskers show the 5th–95th percentiles; up to five high-duration outliers are labeled by part number",
            anchor="start",
        )
    ).resolve_scale(y="shared").configure(background=FIGURE_BACKGROUND).configure_view(
        stroke=None, fill=FIGURE_BACKGROUND
    )


def create_outputs(frame: pd.DataFrame) -> list[Path]:
    if frame.empty:
        raise ValueError("the filtered task query returned no rows")

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    chart_files: list[tuple[str, str]] = []
    for cohort in COHORTS:
        if frame.loc[frame["coh"] == cohort].empty:
            raise ValueError(f"the query returned no rows for {cohort}")
    for stale_filename in [
        *(f"part-number-analysis-{cohort.lower().replace(' ', '-')}.png" for cohort in COHORTS),
        "part-number-analysis-cohort-violin-plots.png",
    ]:
        (OUTPUT_DIRECTORY / stale_filename).unlink(missing_ok=True)
    boxplot_filename = "part-number-analysis-cohort-boxplots.png"
    boxplot_path = OUTPUT_DIRECTORY / boxplot_filename
    create_boxplot(frame).save(boxplot_path, scale_factor=2)
    outputs.append(boxplot_path)
    chart_files.append(("Product mean duration boxplots", boxplot_filename))
    outputs.append(write_markdown(chart_files))
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
    """Query MY_RXP_TASKS and render one combined part-number chart."""
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
