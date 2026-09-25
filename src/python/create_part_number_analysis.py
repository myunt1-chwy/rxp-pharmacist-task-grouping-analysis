#!/usr/bin/env python3
"""Analyze imputed DUR duration by part number and cohort."""

from __future__ import annotations

from pathlib import Path
import re

import altair as alt
import click
import pandas as pd

from .generate_task_table import REQUIRED_SETTINGS, connect_to_snowflake, parse_dotenv

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


def create_chart(frame: pd.DataFrame, cohort: str) -> alt.Chart:
    chart_frame = frame.copy()
    chart_frame["part_number"] = chart_frame["part_number"].astype(str)
    chart_frame["part_number_sort"] = chart_frame["part_number"]
    chart_frame["lower_duration_seconds"] = (
        chart_frame["average_duration_seconds"] - chart_frame["stddev_duration_seconds"].fillna(0)
    )
    chart_frame["upper_duration_seconds"] = (
        chart_frame["average_duration_seconds"] + chart_frame["stddev_duration_seconds"].fillna(0)
    )

    base = alt.Chart(chart_frame).encode(
        x=alt.X(
            "part_number:N",
            title="Part number",
            sort=alt.SortField(field="part_number_sort", order="ascending"),
            axis=alt.Axis(labelAngle=-45, labelOverlap="greedy", labelLimit=90),
        ),
        tooltip=[
            alt.Tooltip("coh:N", title="Cohort"),
            alt.Tooltip("part_number:N", title="Part number"),
            alt.Tooltip("average_duration_seconds:Q", title="Average seconds", format=",.2f"),
            alt.Tooltip("median_duration_seconds:Q", title="Median seconds", format=",.2f"),
            alt.Tooltip("stddev_duration_seconds:Q", title="SD seconds", format=",.2f"),
            alt.Tooltip("unique_task_count:Q", title="DUR tasks", format=",.0f"),
            alt.Tooltip("unique_user_count:Q", title="Distinct users", format=",.0f"),
        ],
    )
    error_bars = base.mark_rule(color="#4c78a8", size=3).encode(
        y=alt.Y("lower_duration_seconds:Q", title="Average imputed DUR duration (seconds)"),
        y2="upper_duration_seconds:Q",
    )
    points = base.mark_point(color="#f58518", filled=True, size=70).encode(
        y=alt.Y("average_duration_seconds:Q", title="Average imputed DUR duration (seconds)")
    )
    median_points = base.mark_point(color="#d62728", filled=True, size=38).encode(
        y=alt.Y("median_duration_seconds:Q", title="Average imputed DUR duration (seconds)")
    )
    return (error_bars + points + median_points).properties(
        title=alt.TitleParams(
            f"Average imputed DUR duration by part number — {cohort}",
            subtitle="Orange dots show the mean; red dots show the median; error bars show ± one sample standard deviation",
            anchor="start",
        ),
        width=min(2400, max(900, len(chart_frame) * 3)),
        height=430,
    ).configure_view(stroke=None)


def write_markdown(chart_files: list[tuple[str, str]]) -> Path:
    lines = [
        "# Part-number analysis",
        "",
        "DUR tasks are filtered to known cohorts, non-refill tasks, no handoff, and part numbers that are not null or blank.",
        "Durations at or above the filtered population's approximate 95th percentile are excluded.",
        "Orange points show average and red points show median `IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS`; error bars show one sample standard deviation.",
        "The combined violin plot uses product-level mean durations; labeled red dots identify the 5 part numbers with the longest mean in each cohort, and labeled dashed red lines show the quartiles.",
        "Tooltips include median duration, distinct task count, and distinct user count.",
        "Cached aggregate data is stored at `outputs/data/part-number-analysis.parquet` for redraw-only runs.",
        "",
    ]
    for title, filename in chart_files:
        lines.extend((f"## {title}", "", f"![{title}]({filename})", ""))
    path = OUTPUT_DIRECTORY / "README.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def create_violin_plot(frame: pd.DataFrame) -> alt.Chart:
    chart_frame = frame.copy()
    duration_max = float(chart_frame["average_duration_seconds"].max())
    panels: list[alt.Chart] = []
    x_domain = [-0.15, 0.15]
    for cohort in COHORTS:
        cohort_frame = chart_frame.loc[chart_frame["coh"] == cohort].copy()
        if cohort_frame.empty:
            raise ValueError(f"the query returned no rows for {cohort}")

        density = (
            alt.Chart(cohort_frame)
            .transform_density(
                "average_duration_seconds",
                as_=["average_duration_seconds", "density"],
                extent=[0, duration_max],
                steps=200,
            )
            .transform_calculate(density_negative="-datum.density")
            .mark_area(orient="horizontal", interpolate="monotone", opacity=0.8)
            .encode(
                y=alt.Y(
                    "average_duration_seconds:Q",
                    title="Product mean imputed DUR duration (seconds)",
                ),
                x=alt.X(
                    "density_negative:Q",
                    title=None,
                    axis=None,
                    scale=alt.Scale(domain=x_domain),
                ),
                x2="density:Q",
                color=alt.value("#4c78a8"),
            )
        )

        top_frame = (
            cohort_frame.nlargest(5, "average_duration_seconds")
            .sort_values("average_duration_seconds", ascending=False)
            .copy()
        )
        top_frame["dot_x"] = 0.0
        top_frame["label_x"] = 0.012
        label_frame = top_frame.sort_values("average_duration_seconds").copy()
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
        label_frame["label_x"] = 0.012
        label_frame["part_label"] = label_frame.apply(
            lambda row: f"{row['part_number']} ({row['average_duration_seconds']:,.1f}s)",
            axis=1,
        )
        top_dots = (
            alt.Chart(top_frame)
            .mark_point(color="#d62728", filled=True, size=65, stroke="white", strokeWidth=1)
            .encode(
                x=alt.X("dot_x:Q", axis=None, scale=alt.Scale(domain=x_domain)),
                y=alt.Y("average_duration_seconds:Q"),
                tooltip=[
                    alt.Tooltip("part_number:N", title="Top part number"),
                    alt.Tooltip(
                        "average_duration_seconds:Q",
                        title="Product mean seconds",
                        format=",.2f",
                    ),
                ],
            )
        )
        top_labels = (
            alt.Chart(label_frame)
            .mark_text(align="left", dx=5, dy=-5, color="#d62728", fontSize=10)
            .encode(
                x=alt.X("label_x:Q", axis=None, scale=alt.Scale(domain=x_domain)),
                y=alt.Y("label_y:Q"),
                text=alt.Text("part_label:N"),
            )
        )
        quartile_values = cohort_frame["average_duration_seconds"].quantile([0.25, 0.50, 0.75])
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
            .mark_rule(color="#d62728", strokeDash=[6, 4], size=2)
            .encode(
                y=alt.Y("quartile_seconds:Q"),
                tooltip=[
                    alt.Tooltip("quartile:N", title="Statistic"),
                    alt.Tooltip("quartile_seconds:Q", title="Seconds", format=",.2f"),
                ],
            )
        )
        quartile_labels = (
            alt.Chart(quartile_frame)
            .mark_text(align="left", dx=3, dy=-5, color="#d62728", fontSize=9)
            .encode(
                x=alt.X("label_x:Q", axis=None, scale=alt.Scale(domain=x_domain)),
                y=alt.Y("quartile_seconds:Q"),
                text=alt.Text("quartile_label:N"),
            )
        )
        panels.append(
            (density + quartile_rules + quartile_labels + top_dots + top_labels).properties(
                title=cohort,
                width=300,
                height=520,
            )
        )

    return alt.hconcat(*panels).properties(
        title=alt.TitleParams(
            "Product mean DUR duration violin plots by cohort",
            subtitle="Dashed red lines are labeled with quartiles; red dots and labels identify the 5 longest product means",
            anchor="start",
        )
    ).resolve_scale(y="shared").configure_view(stroke=None)


def create_outputs(frame: pd.DataFrame) -> list[Path]:
    if frame.empty:
        raise ValueError("the filtered task query returned no rows")

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    chart_files: list[tuple[str, str]] = []
    for cohort in COHORTS:
        cohort_frame = frame.loc[frame["coh"] == cohort].copy()
        if cohort_frame.empty:
            raise ValueError(f"the query returned no rows for {cohort}")
        filename = f"part-number-analysis-{cohort.lower().replace(' ', '-')}.png"
        path = OUTPUT_DIRECTORY / filename
        create_chart(cohort_frame, cohort).save(path, scale_factor=2)
        outputs.append(path)
        chart_files.append((cohort, filename))
    old_boxplot_path = OUTPUT_DIRECTORY / "part-number-analysis-cohort-boxplots.png"
    old_boxplot_path.unlink(missing_ok=True)
    violin_filename = "part-number-analysis-cohort-violin-plots.png"
    violin_path = OUTPUT_DIRECTORY / violin_filename
    create_violin_plot(frame).save(violin_path, scale_factor=2)
    outputs.append(violin_path)
    chart_files.append(("Product mean duration violin plots", violin_filename))
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
    """Query MY_RXP_TASKS and render one part-number chart per cohort."""
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
