#!/usr/bin/env python3
"""Analyze valid DUR duration by MC3 and PETTYPE."""

from __future__ import annotations

from pathlib import Path
import re

import altair as alt
import click
import pandas as pd

from .generate_task_table import REQUIRED_SETTINGS, connect_to_snowflake, parse_dotenv
from .plot_style import FIGURE_BACKGROUND

SOURCE_TABLE = "EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_VALID_DUR_TASKS"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIRECTORY = REPOSITORY_ROOT / "outputs" / "charts" / "mc3-pettype-analysis"
DATA_PATH = REPOSITORY_ROOT / "outputs" / "data" / "mc3-pettype-analysis.parquet"
GENERATED_SQL_PATH = REPOSITORY_ROOT / "generated" / "create_mc3_pettype_analysis.sql"
OVERALL_PETTYPE = "All PETTYPEs"
ALL_COHORT = "All cohorts"
COHORTS = ("Cohort 1", "Cohort 2", "Cohort 3", "Cohort 4")
MIN_COLOR_TASK_COUNT = 10
DURATION_COLOR_RANGE = ["#2166ac", "#bdbdbd", "#b2182b"]

MC3_PETTYPE_SQL = f"""
WITH base_tasks AS (
    SELECT
        COH AS COHORT,
        COALESCE(NULLIF(TRIM(MC3::VARCHAR), ''), '<Missing>') AS MC3,
        COALESCE(NULLIF(TRIM(PETTYPE::VARCHAR), ''), '<Missing>') AS PETTYPE,
        IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS AS DURATION_SECONDS
    FROM {SOURCE_TABLE}
    WHERE COH IN ('Cohort 1', 'Cohort 2', 'Cohort 3', 'Cohort 4')
      AND IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS IS NOT NULL
), percentile_bounds AS (
    SELECT APPROX_PERCENTILE(DURATION_SECONDS, 0.95) AS P95_SECONDS
    FROM base_tasks
), filtered_tasks AS (
    SELECT base.*
    FROM base_tasks AS base
    CROSS JOIN percentile_bounds
    WHERE base.DURATION_SECONDS < percentile_bounds.P95_SECONDS
), by_cohort_pettype AS (
    SELECT
        COHORT,
        MC3,
        PETTYPE,
        COUNT(*) AS TASK_COUNT,
        MEDIAN(DURATION_SECONDS) AS MEDIAN_DURATION_SECONDS
    FROM filtered_tasks
    GROUP BY COHORT, MC3, PETTYPE
), overall_cohort_pettypes AS (
    SELECT
        COHORT,
        MC3,
        '{OVERALL_PETTYPE}' AS PETTYPE,
        COUNT(*) AS TASK_COUNT,
        MEDIAN(DURATION_SECONDS) AS MEDIAN_DURATION_SECONDS
    FROM filtered_tasks
    GROUP BY COHORT, MC3
), by_all_cohorts_pettype AS (
    SELECT
        '{ALL_COHORT}' AS COHORT,
        MC3,
        PETTYPE,
        COUNT(*) AS TASK_COUNT,
        MEDIAN(DURATION_SECONDS) AS MEDIAN_DURATION_SECONDS
    FROM filtered_tasks
    GROUP BY MC3, PETTYPE
), overall_all_cohort_pettypes AS (
    SELECT
        '{ALL_COHORT}' AS COHORT,
        MC3,
        '{OVERALL_PETTYPE}' AS PETTYPE,
        COUNT(*) AS TASK_COUNT,
        MEDIAN(DURATION_SECONDS) AS MEDIAN_DURATION_SECONDS
    FROM filtered_tasks
    GROUP BY MC3
)
SELECT COHORT, MC3, PETTYPE, TASK_COUNT, MEDIAN_DURATION_SECONDS
FROM by_cohort_pettype
UNION ALL
SELECT COHORT, MC3, PETTYPE, TASK_COUNT, MEDIAN_DURATION_SECONDS
FROM overall_cohort_pettypes
UNION ALL
SELECT COHORT, MC3, PETTYPE, TASK_COUNT, MEDIAN_DURATION_SECONDS
FROM by_all_cohorts_pettype
UNION ALL
SELECT COHORT, MC3, PETTYPE, TASK_COUNT, MEDIAN_DURATION_SECONDS
FROM overall_all_cohort_pettypes
ORDER BY COHORT, MC3, PETTYPE
""".strip()


def natural_sort_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def write_generated_sql() -> Path:
    GENERATED_SQL_PATH.parent.mkdir(parents=True, exist_ok=True)
    GENERATED_SQL_PATH.write_text(MC3_PETTYPE_SQL + "\n", encoding="utf-8")
    return GENERATED_SQL_PATH


def normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    if "cohort" not in normalized.columns:
        normalized["cohort"] = ALL_COHORT
    normalized["cohort"] = (
        normalized["cohort"]
        .astype("string")
        .str.strip()
        .replace("", pd.NA)
        .fillna(ALL_COHORT)
        .astype(str)
    )
    normalized["mc3"] = (
        normalized["mc3"]
        .astype("string")
        .str.strip()
        .replace("", pd.NA)
        .fillna("<Missing>")
        .astype(str)
    )
    normalized["pettype"] = (
        normalized["pettype"]
        .astype("string")
        .str.strip()
        .replace("", pd.NA)
        .fillna("<Missing>")
        .astype(str)
    )
    normalized["task_count"] = pd.to_numeric(
        normalized["task_count"], errors="coerce"
    ).fillna(0)
    normalized["median_duration_seconds"] = pd.to_numeric(
        normalized["median_duration_seconds"], errors="coerce"
    )
    return normalized


def fetch_data(settings: dict[str, str]) -> pd.DataFrame:
    connection = connect_to_snowflake(settings)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(MC3_PETTYPE_SQL)
            columns = [column[0].lower() for column in cursor.description]
            rows = cursor.fetchall()
        finally:
            cursor.close()
    finally:
        connection.close()

    return normalize_frame(pd.DataFrame(rows, columns=columns))


def write_data(frame: pd.DataFrame) -> Path:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    normalize_frame(frame).to_parquet(DATA_PATH, index=False)
    return DATA_PATH


def read_data() -> pd.DataFrame:
    frame = pd.read_parquet(DATA_PATH)
    if "cohort" not in frame.columns:
        raise ValueError(
            f"cached Parquet data is missing cohort aggregates; rerun without REDRAW=1: {DATA_PATH}"
        )
    return normalize_frame(frame)


def prepare_chart_frame(
    frame: pd.DataFrame, cohort: str = ALL_COHORT
) -> tuple[pd.DataFrame, list[str], list[str]]:
    normalized = normalize_frame(frame)
    normalized = normalized.loc[normalized["cohort"] == cohort].copy()
    if normalized.empty:
        raise ValueError(f"the aggregate query returned no rows for {cohort}")

    mc3_order = sorted(normalized["mc3"].unique().tolist(), key=natural_sort_key)
    pettype_totals = (
        normalized.loc[normalized["pettype"] != OVERALL_PETTYPE]
        .groupby("pettype", as_index=True)["task_count"]
        .sum()
    )
    pettype_order = [OVERALL_PETTYPE] + sorted(
        pettype_totals.index.tolist(),
        key=lambda value: (-pettype_totals[value], natural_sort_key(value)),
    )
    grid = pd.MultiIndex.from_product(
        [mc3_order, pettype_order], names=["mc3", "pettype"]
    ).to_frame(index=False)
    chart_frame = grid.merge(normalized, on=["mc3", "pettype"], how="left")
    chart_frame["task_count"] = chart_frame["task_count"].fillna(0)
    chart_frame["cell_label"] = chart_frame.apply(
        lambda row: (
            ""
            if row["task_count"] == 0
            else (
                f"n={row['task_count']:,.0f}\n"
                + (
                    f"median={row['median_duration_seconds']:,.1f}s"
                    if pd.notna(row["median_duration_seconds"])
                    else "median=—"
                )
            )
        ),
        axis=1,
    )
    chart_frame["count_label"] = chart_frame["task_count"].map(
        lambda value: "" if value == 0 else f"n={value:,.0f}"
    )
    chart_frame["median_label"] = chart_frame.apply(
        lambda row: (
            ""
            if row["task_count"] == 0
            else (
                f"median={row['median_duration_seconds']:,.1f}s"
                if pd.notna(row["median_duration_seconds"])
                else "median=—"
            )
        ),
        axis=1,
    )
    return chart_frame, mc3_order, pettype_order


def heatmap_chart(frame: pd.DataFrame, cohort: str = ALL_COHORT) -> alt.Chart:
    chart_frame, mc3_order, pettype_order = prepare_chart_frame(frame, cohort)
    base = alt.Chart(chart_frame).encode(
        x=alt.X(
            "pettype:N",
            title="PETTYPE",
            sort=pettype_order,
            axis=alt.Axis(labelAngle=-35, labelFontSize=22, titleFontSize=22),
        ),
        y=alt.Y(
            "mc3:N",
            title="MC3",
            sort=mc3_order,
            axis=alt.Axis(labelFontSize=22, titleFontSize=22, labelLimit=500),
        ),
        tooltip=[
            alt.Tooltip("mc3:N", title="MC3"),
            alt.Tooltip("pettype:N", title="PETTYPE"),
            alt.Tooltip("task_count:Q", title="Valid DUR tasks", format=",.0f"),
            alt.Tooltip(
                "median_duration_seconds:Q",
                title="Median DUR seconds",
                format=",.1f",
            ),
        ],
    )
    rectangles = base.mark_rect(strokeWidth=0.5).encode(
        stroke=alt.condition(
            "datum.task_count > 0",
            alt.value("black"),
            alt.value("transparent"),
        ),
        color=alt.condition(
            f"datum.task_count >= {MIN_COLOR_TASK_COUNT}",
            alt.Color(
                "median_duration_seconds:Q",
                title="Median DUR seconds (log10 scale)",
                scale=alt.Scale(
                    type="log",
                    base=10,
                    range=DURATION_COLOR_RANGE,
                    interpolate="lab",
                ),
            ),
            alt.value("white"),
        )
    )
    label_color = alt.condition(
        f"datum.task_count < {MIN_COLOR_TASK_COUNT} || datum.median_duration_seconds <= 30",
        alt.value("#111111"),
        alt.value("white"),
    )
    label_x = alt.X("pettype:N", sort=pettype_order, axis=None)
    count_labels = base.mark_text(fontSize=22, fontWeight="bold", dy=-14).encode(
        x=label_x,
        text="count_label:N",
        color=label_color,
    )
    median_labels = base.mark_text(fontSize=22, fontWeight="bold", dy=14).encode(
        x=label_x,
        text="median_label:N",
        color=label_color,
    )
    top_pettype_axis = alt.Chart(chart_frame).mark_point(opacity=0).encode(
        x=alt.X(
            "pettype:N",
            title="PETTYPE",
            sort=pettype_order,
            axis=alt.Axis(
                orient="top",
                labelAngle=-35,
                labelFontSize=22,
                titleFontSize=22,
            ),
        ),
        y=alt.value(0),
    )
    title = "Median DUR duration by MC3 and PETTYPE"
    if cohort != ALL_COHORT:
        title += f" — {cohort}"
    return (rectangles + count_labels + median_labels + top_pettype_axis).properties(
        title=alt.TitleParams(
            title,
            subtitle="Each cell shows valid DUR task count (n) and median duration; All PETTYPEs is the overall column",
            anchor="start",
        ),
        width=alt.Step(250),
        height=alt.Step(90),
    ).resolve_axis(x="independent").configure(
        background=FIGURE_BACKGROUND,
    ).configure_view(stroke=None, fill=FIGURE_BACKGROUND)


def write_markdown(chart_files: list[tuple[str, Path]]) -> Path:
    lines = [
        "# MC3 and PETTYPE analysis",
        "",
        "Valid DUR tasks from Cohorts 1–4 are filtered to durations strictly below one global approximate 95th-percentile cutoff.",
        "Rows are MC3 categories and columns are PETTYPE values ordered by descending valid DUR task count, with `All PETTYPEs` first. Each cell shows the valid DUR task count (`n`) and median duration. Cell colors use a log10 duration scale for cells with `n >= 10`: blue is lowest, gray is mid-range, and red is highest. Cells with fewer than 10 tasks are white.",
        "The all-cohort chart and one chart per cohort are generated from cached aggregate data stored at `outputs/data/mc3-pettype-analysis.parquet` for redraw-only runs.",
    ]
    for cohort, chart_path in chart_files:
        title = "All cohorts" if cohort == ALL_COHORT else cohort
        lines.extend(
            [
                "",
                f"## {title}",
                "",
                f"![MC3 and PETTYPE heatmap — {title}]({chart_path.name})",
                "",
            ]
        )
    path = OUTPUT_DIRECTORY / "README.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def create_outputs(frame: pd.DataFrame) -> list[Path]:
    normalized = normalize_frame(frame)
    if normalized.empty:
        raise ValueError("the aggregate query returned no rows")

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for stale_output in OUTPUT_DIRECTORY.glob("mc3-pettype-analysis*.png"):
        stale_output.unlink()
    chart_files: list[tuple[str, Path]] = []
    for cohort in (ALL_COHORT, *COHORTS):
        filename = (
            "mc3-pettype-analysis.png"
            if cohort == ALL_COHORT
            else f"mc3-pettype-analysis-{cohort.lower().replace(' ', '-')}.png"
        )
        chart_path = OUTPUT_DIRECTORY / filename
        heatmap_chart(normalized, cohort).save(chart_path, scale_factor=2)
        chart_files.append((cohort, chart_path))

    return [path for _, path in chart_files] + [write_markdown(chart_files)]


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
    """Query aggregate DUR statistics and render the MC3/PETTYPE heatmap."""
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
            frame = fetch_data(settings)
            data_path = write_data(frame)
            click.echo(f"Saved chart data: {data_path}")
        outputs = create_outputs(frame)
    except (ImportError, OSError, ValueError) as error:
        raise click.ClickException(str(error)) from error

    click.echo(f"Created {len(outputs) - 1} heatmaps and {outputs[-1]}.")


if __name__ == "__main__":
    main()
