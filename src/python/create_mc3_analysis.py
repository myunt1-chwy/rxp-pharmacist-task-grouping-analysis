#!/usr/bin/env python3
"""Analyze filtered DUR duration distributions by MC3 and cohort."""

from __future__ import annotations

from pathlib import Path
import re

import altair as alt
import click
import pandas as pd

from .generate_task_table import REQUIRED_SETTINGS, connect_to_snowflake, parse_dotenv
from .plot_style import FIGURE_BACKGROUND, MEDIAN_COLOR

SOURCE_TABLE = "EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASKS"
PRODUCT_TABLE = "EDLDB.PDM.PRODUCT"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIRECTORY = REPOSITORY_ROOT / "outputs" / "charts" / "mc3-analysis"
DATA_PATH = REPOSITORY_ROOT / "outputs" / "data" / "mc3-analysis.parquet"
GENERATED_SQL_PATH = REPOSITORY_ROOT / "generated" / "create_mc3_analysis.sql"
MEDIAN_HISTOGRAM_PATH = OUTPUT_DIRECTORY / "mc3-analysis-category-median-histogram.png"
COHORTS = ("Cohort 1", "Cohort 2", "Cohort 3", "Cohort 4")

MC3_SQL = f"""
WITH base_tasks AS (
    SELECT
        TASK_ID,
        COH,
        TRIM(PART_NUMBER::VARCHAR) AS PART_NUMBER,
        IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS AS DURATION_SECONDS
    FROM {SOURCE_TABLE}
    WHERE TASK_TYPE = 'DUR'
      AND COH IN ('Cohort 1', 'Cohort 2', 'Cohort 3', 'Cohort 4')
      AND COH <> 'Unknown'
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
    filtered.COH,
    COALESCE(NULLIF(TRIM(product.MERCH_CLASSIFICATION3), ''), '<Missing>') AS MC3,
    filtered.PART_NUMBER,
    filtered.DURATION_SECONDS
FROM filtered_tasks AS filtered
LEFT JOIN {PRODUCT_TABLE} AS product
    ON product.PART_NUMBER = filtered.PART_NUMBER
ORDER BY filtered.COH, MC3, filtered.DURATION_SECONDS
""".strip()


def natural_sort_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def write_generated_sql() -> Path:
    GENERATED_SQL_PATH.parent.mkdir(parents=True, exist_ok=True)
    GENERATED_SQL_PATH.write_text(MC3_SQL + "\n", encoding="utf-8")
    return GENERATED_SQL_PATH


def fetch_data(settings: dict[str, str]) -> pd.DataFrame:
    connection = connect_to_snowflake(settings)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(MC3_SQL)
            columns = [column[0].lower() for column in cursor.description]
            rows = cursor.fetchall()
        finally:
            cursor.close()
    finally:
        connection.close()

    frame = pd.DataFrame(rows, columns=columns)
    frame["duration_seconds"] = pd.to_numeric(frame["duration_seconds"], errors="coerce")
    frame["mc3"] = frame["mc3"].fillna("<Missing>").astype(str)
    return frame


def write_data(frame: pd.DataFrame) -> Path:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(DATA_PATH, index=False)
    return DATA_PATH


def read_data() -> pd.DataFrame:
    return pd.read_parquet(DATA_PATH)


def boxplot_chart(
    frame: pd.DataFrame,
    cohort: str,
    category_title: str = "MC3",
    chart_title: str = "MC3",
) -> alt.Chart:
    chart_frame = frame.loc[frame["coh"] == cohort].copy()
    if chart_frame.empty:
        raise ValueError(f"the query returned no rows for {cohort}")

    mc3_order = sorted(chart_frame["mc3"].dropna().unique().tolist(), key=natural_sort_key)
    whole_cohort = chart_frame.assign(plot_category="Whole cohort")
    chart_frame["plot_category"] = chart_frame["mc3"]
    boxplot_frame = pd.concat([chart_frame, whole_cohort], ignore_index=True)
    category_order = mc3_order + ["Whole cohort"]
    summaries = []
    for category in category_order:
        durations = boxplot_frame.loc[
            boxplot_frame["plot_category"] == category, "duration_seconds"
        ]
        summaries.append(
            {
                "plot_category": category,
                "p05": durations.quantile(0.05),
                "q1": durations.quantile(0.25),
                "median": durations.quantile(0.50),
                "q3": durations.quantile(0.75),
                "p95": durations.quantile(0.95),
                "task_count": len(durations),
                "part_number_count": boxplot_frame.loc[
                    boxplot_frame["plot_category"] == category, "part_number"
                ].nunique(),
            }
        )
    category_summary = pd.DataFrame(summaries)
    category_summary["category_label"] = category_summary.apply(
        lambda row: (
            f"{row['plot_category']} | Tasks: {row['task_count']:,}"
            f" | PN: {row['part_number_count']:,}"
        ),
        axis=1,
    )
    median_half_width = max(
        (float(boxplot_frame["duration_seconds"].max())
         - float(boxplot_frame["duration_seconds"].min()))
        * 0.004,
        0.5,
    )
    category_summary["median_lower"] = category_summary["median"] - median_half_width
    category_summary["median_upper"] = category_summary["median"] + median_half_width
    x_domain = [0, float(boxplot_frame["duration_seconds"].max()) * 1.05]
    category_labels = category_summary["category_label"].tolist()
    base = alt.Chart(category_summary).encode(
        y=alt.Y(
            "category_label:N",
            title=category_title,
            sort=category_labels,
            axis=alt.Axis(labels=False, ticks=False, title=None),
        ),
        color=alt.Color(
            "plot_category:N",
            title="Category",
            sort=category_order,
            legend=None,
            scale=alt.Scale(scheme="tableau20"),
        ),
    )
    whiskers = base.mark_rule(size=2).encode(
        x=alt.X(
            "p05:Q",
            title="DUR duration (seconds)",
            scale=alt.Scale(domain=x_domain),
        ),
        x2="p95:Q",
    )
    boxes = base.mark_bar(size=70).encode(
        x=alt.X("q1:Q", scale=alt.Scale(domain=x_domain)),
        x2="q3:Q",
    )
    median_base = alt.Chart(category_summary).encode(
        y=alt.Y("category_label:N", sort=category_labels, axis=None),
    )
    medians = median_base.mark_bar(size=70, color=MEDIAN_COLOR).encode(
        x=alt.X("median_lower:Q", scale=alt.Scale(domain=x_domain)),
        x2="median_upper:Q",
    )
    boxplots = whiskers + boxes + medians
    boxplots = boxplots.properties(
        title=alt.TitleParams(
            f"DUR duration boxplots by {chart_title} — {cohort}",
            subtitle=f"{len(chart_frame):,} filtered DUR tasks; boxes show IQR and whiskers show the 5th–95th percentiles",
            anchor="start",
        ),
        width=1200,
        height=max(500, len(category_order) * 85),
    )
    chart_height = max(500, len(category_order) * 85)
    label_panel = (
        alt.Chart(category_summary)
        .mark_text(align="left", fontSize=22)
        .encode(
            x=alt.value(4),
            y=alt.Y("category_label:N", sort=category_labels, axis=None),
            text=alt.Text("category_label:N"),
        )
        .properties(width=380, height=chart_height)
    )
    return (
        alt.hconcat(label_panel, boxplots)
        .resolve_scale(y="shared")
        .configure(background=FIGURE_BACKGROUND)
        .configure_view(stroke=None, fill=FIGURE_BACKGROUND)
    )


def write_markdown(chart_files: list[tuple[str, str]]) -> Path:
    lines = [
        "# MC3 analysis",
        "",
        "DUR tasks are filtered to Cohort 1–4, non-refill tasks, no handoff, and non-null part numbers.",
        "Durations at or above the filtered population's approximate 95th percentile are excluded.",
        "Product rows are joined by `PART_NUMBER`; missing or blank `MERCH_CLASSIFICATION3` values are shown as `<Missing>`.",
        "Each chart contains vertically stacked horizontal boxplots, one per MC3 plus a final `Whole cohort` boxplot; adjacent labels show task and PN counts, dark-red lines show medians, and whiskers show the 5th–95th percentiles.",
        "The median-duration histogram counts MC3 categories in two-second bins separately for each cohort.",
        "Cached task-level data is stored at `outputs/data/mc3-analysis.parquet` for redraw-only runs.",
        "",
    ]
    for title, filename in chart_files:
        lines.extend((f"## {title}", "", f"![{title}]({filename})", ""))
    path = OUTPUT_DIRECTORY / "README.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def mc3_median_histogram_chart(frame: pd.DataFrame) -> alt.Chart:
    """Plot the distribution of one median DUR duration per MC3 and cohort."""
    summary = (
        frame.groupby(["coh", "mc3"], as_index=False)
        .agg(median_seconds=("duration_seconds", "median"))
    )
    panels = []
    for cohort in COHORTS:
        cohort_summary = summary.loc[summary["coh"] == cohort]
        chart = alt.Chart(cohort_summary).mark_bar().encode(
            x=alt.X(
                "median_seconds:Q",
                bin=alt.Bin(step=2),
                title="MC3 median DUR duration (seconds)",
            ),
            y=alt.Y("count():Q", title="Number of MC3 categories"),
            tooltip=[
                alt.Tooltip("median_seconds:Q", bin=alt.Bin(step=2), title="Median DUR bin"),
                alt.Tooltip("count():Q", title="MC3 categories"),
            ],
        ).properties(title=cohort, width=400, height=280)
        panels.append(chart)
    return alt.vconcat(
        alt.hconcat(panels[0], panels[1], spacing=20),
        alt.hconcat(panels[2], panels[3], spacing=20),
        spacing=28,
    ).properties(
        title=alt.TitleParams(
            "MC3 Median DUR Duration Distribution",
            subtitle="Each MC3 category contributes one median duration; bins are two seconds wide",
            anchor="start",
        )
    ).configure(background=FIGURE_BACKGROUND).configure_view(
        stroke=None, fill=FIGURE_BACKGROUND
    )


def create_outputs(frame: pd.DataFrame) -> list[Path]:
    if frame.empty:
        raise ValueError("the filtered task query returned no rows")

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    chart_files: list[tuple[str, str]] = []
    for cohort in COHORTS:
        filename = f"mc3-analysis-{cohort.lower().replace(' ', '-')}.png"
        path = OUTPUT_DIRECTORY / filename
        boxplot_chart(frame, cohort).save(path, scale_factor=2)
        outputs.append(path)
        chart_files.append((cohort, filename))
    histogram_path = OUTPUT_DIRECTORY / MEDIAN_HISTOGRAM_PATH.name
    mc3_median_histogram_chart(frame).save(histogram_path, scale_factor=2)
    outputs.append(histogram_path)
    chart_files.append(("MC3 median DUR histogram", histogram_path.name))
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
    """Query task durations and render one MC3 boxplot chart per cohort."""
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

    click.echo(f"Created {len(outputs) - 1} PNG charts and {outputs[-1]}.")


if __name__ == "__main__":
    main()
