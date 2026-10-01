#!/usr/bin/env python3
"""Analyze DUR duration distributions by initiation channel and reason."""

from __future__ import annotations

from pathlib import Path
import re

import altair as alt
import click
import pandas as pd

from .generate_task_table import REQUIRED_SETTINGS, connect_to_snowflake, parse_dotenv
from .plot_style import FIGURE_BACKGROUND, MEDIAN_COLOR

SOURCE_TABLE = "EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_VALID_DUR_TASKS"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIRECTORY = REPOSITORY_ROOT / "outputs" / "charts" / "initiation-channel-analysis"
DATA_PATH = REPOSITORY_ROOT / "outputs" / "data" / "initiation-channel-analysis.parquet"
GENERATED_SQL_PATH = REPOSITORY_ROOT / "generated" / "create_initiation_channel_analysis.sql"
COHORTS = ("Cohort 1", "Cohort 2", "Cohort 3", "Cohort 4")

INITIATION_CHANNEL_SQL = f"""
WITH base_tasks AS (
    SELECT
        TASK_ID,
        COH,
        COALESCE(NULLIF(TRIM(INITIATION_CHANNEL::VARCHAR), ''), '<Missing>') AS INITIATION_CHANNEL,
        COALESCE(NULLIF(TRIM(INITIATION_REASON::VARCHAR), ''), '<Missing>') AS INITIATION_REASON,
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
)
SELECT
    TASK_ID,
    COH,
    INITIATION_CHANNEL,
    INITIATION_REASON,
    DURATION_SECONDS
FROM filtered_tasks
ORDER BY COH, INITIATION_CHANNEL, INITIATION_REASON, DURATION_SECONDS
""".strip()


def natural_sort_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def write_generated_sql() -> Path:
    GENERATED_SQL_PATH.parent.mkdir(parents=True, exist_ok=True)
    GENERATED_SQL_PATH.write_text(INITIATION_CHANNEL_SQL + "\n", encoding="utf-8")
    return GENERATED_SQL_PATH


def normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    normalized["duration_seconds"] = pd.to_numeric(
        normalized["duration_seconds"], errors="coerce"
    )
    for column in ("initiation_channel", "initiation_reason"):
        if column not in normalized:
            normalized[column] = "<Missing>"
        else:
            normalized[column] = (
                normalized[column]
                .astype("string")
                .str.strip()
                .replace("", pd.NA)
                .fillna("<Missing>")
                .astype(str)
            )
    return normalized


def fetch_data(settings: dict[str, str]) -> pd.DataFrame:
    connection = connect_to_snowflake(settings)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(INITIATION_CHANNEL_SQL)
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
    return normalize_frame(pd.read_parquet(DATA_PATH))


def boxplot_chart(
    frame: pd.DataFrame,
    cohort: str,
    grouping_column: str = "initiation_channel",
    grouping_title: str = "Initiation channel",
    sort_categories_by_count: bool = False,
) -> alt.Chart:
    """Create one horizontal boxplot chart for a cohort and grouping field."""
    chart_frame = normalize_frame(frame.loc[frame["coh"] == cohort])
    if chart_frame.empty:
        raise ValueError(f"the query returned no rows for {cohort}")

    category_order = chart_frame[grouping_column].dropna().unique().tolist()
    if sort_categories_by_count:
        category_counts = chart_frame[grouping_column].value_counts()
        category_order = sorted(
            category_order,
            key=lambda category: (
                -int(category_counts[category]),
                natural_sort_key(category),
            ),
        )
    else:
        category_order = sorted(category_order, key=natural_sort_key)
    whole_cohort = chart_frame.assign(plot_category="Whole cohort")
    chart_frame["plot_category"] = chart_frame[grouping_column]
    boxplot_frame = pd.concat([chart_frame, whole_cohort], ignore_index=True)
    category_order = category_order + ["Whole cohort"]

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
            }
        )
    category_summary = pd.DataFrame(summaries)
    category_summary["category_label"] = category_summary.apply(
        lambda row: f"{row['plot_category']} | Tasks: {row['task_count']:,}", axis=1
    )
    median_half_width = max(
        (
            float(boxplot_frame["duration_seconds"].max())
            - float(boxplot_frame["duration_seconds"].min())
        )
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
            title=grouping_title,
            sort=category_labels,
            axis=alt.Axis(labels=False, ticks=False, title=None),
        ),
        color=alt.Color(
            "plot_category:N",
            title=grouping_title,
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
    boxplots = (whiskers + boxes + medians).properties(
        title=alt.TitleParams(
            f"DUR duration boxplots by {grouping_title.lower()} — {cohort}",
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
        "# Initiation channel and reason analysis",
        "",
        "Valid DUR tasks are selected from `MY_RXP_VALID_DUR_TASKS` for Cohorts 1–4.",
        "Durations at or above the global approximate 95th percentile are excluded.",
        "Null or blank `INITIATION_CHANNEL` and `INITIATION_REASON` values are shown as `<Missing>`.",
        "Each chart contains a horizontal boxplot for every grouping value plus a final `Whole cohort` reference boxplot. Labels show filtered task counts, dark-red lines show medians, and whiskers show the 5th–95th percentiles.",
        "Cached task-level data is stored at `outputs/data/initiation-channel-analysis.parquet` for redraw-only runs.",
        "",
    ]
    for title, filename in chart_files:
        lines.extend((f"## {title}", "", f"![{title}]({filename})", ""))
    path = OUTPUT_DIRECTORY / "README.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def create_outputs(frame: pd.DataFrame) -> list[Path]:
    normalized = normalize_frame(frame)
    if normalized.empty:
        raise ValueError("the filtered task query returned no rows")

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    chart_files: list[tuple[str, str]] = []
    for grouping_column, grouping_title, filename_prefix in (
        ("initiation_channel", "Initiation channel", "initiation-channel-analysis"),
        ("initiation_reason", "Initiation reason", "initiation-reason-analysis"),
    ):
        for cohort in COHORTS:
            filename = f"{filename_prefix}-{cohort.lower().replace(' ', '-')}.png"
            path = OUTPUT_DIRECTORY / filename
            boxplot_chart(
                normalized,
                cohort,
                grouping_column=grouping_column,
                grouping_title=grouping_title,
            ).save(path, scale_factor=2)
            outputs.append(path)
            chart_files.append((f"{grouping_title} — {cohort}", filename))
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
    """Query valid DUR durations and render channel and reason charts per cohort."""
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
