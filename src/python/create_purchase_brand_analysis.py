#!/usr/bin/env python3
"""Analyze filtered DUR duration distributions by purchase brand and cohort."""

from __future__ import annotations

from pathlib import Path

import click
import altair as alt
import pandas as pd

from .create_mc3_analysis import COHORTS, boxplot_chart
from .generate_task_table import REQUIRED_SETTINGS, connect_to_snowflake, parse_dotenv
from .plot_style import FIGURE_BACKGROUND

SOURCE_TABLE = "EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASKS"
PRODUCT_TABLE = "EDLDB.PDM.PRODUCT"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIRECTORY = REPOSITORY_ROOT / "outputs" / "charts" / "purchase-brand-analysis"
DATA_PATH = REPOSITORY_ROOT / "outputs" / "data" / "purchase-brand-analysis.parquet"
GENERATED_SQL_PATH = REPOSITORY_ROOT / "generated" / "create_purchase_brand_analysis.sql"
TABLE_PATH = REPOSITORY_ROOT / "outputs" / "tables" / "purchase-brand-analysis-top-10-by-median.md"
TABLE_CHART_PATH = OUTPUT_DIRECTORY / "purchase-brand-analysis-top-10-table.png"
MEDIAN_HISTOGRAM_PATH = OUTPUT_DIRECTORY / "purchase-brand-analysis-brand-median-histogram.png"

PURCHASE_BRAND_SQL = f"""
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
    COALESCE(NULLIF(TRIM(product.PURCHASE_BRAND), ''), '<Missing>') AS PURCHASE_BRAND,
    filtered.PART_NUMBER,
    filtered.DURATION_SECONDS
FROM filtered_tasks AS filtered
LEFT JOIN {PRODUCT_TABLE} AS product
    ON product.PART_NUMBER = filtered.PART_NUMBER
ORDER BY filtered.COH, PURCHASE_BRAND, filtered.DURATION_SECONDS
""".strip()


def write_generated_sql() -> Path:
    GENERATED_SQL_PATH.parent.mkdir(parents=True, exist_ok=True)
    GENERATED_SQL_PATH.write_text(PURCHASE_BRAND_SQL + "\n", encoding="utf-8")
    return GENERATED_SQL_PATH


def fetch_data(settings: dict[str, str]) -> pd.DataFrame:
    connection = connect_to_snowflake(settings)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(PURCHASE_BRAND_SQL)
            columns = [column[0].lower() for column in cursor.description]
            rows = cursor.fetchall()
        finally:
            cursor.close()
    finally:
        connection.close()

    frame = pd.DataFrame(rows, columns=columns)
    frame["duration_seconds"] = pd.to_numeric(frame["duration_seconds"], errors="coerce")
    frame["purchase_brand"] = frame["purchase_brand"].fillna("<Missing>").astype(str)
    return frame


def write_data(frame: pd.DataFrame) -> Path:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(DATA_PATH, index=False)
    return DATA_PATH


def read_data() -> pd.DataFrame:
    return pd.read_parquet(DATA_PATH)


def write_markdown(chart_files: list[tuple[str, str]]) -> Path:
    lines = [
        "# Purchase Brand analysis",
        "",
        "DUR tasks use the same known-cohort, non-refill, no-handoff, part-number, and approximate 95th-percentile filters as the MC3 analysis.",
        "Product rows are joined by `PART_NUMBER`; missing or blank `PURCHASE_BRAND` values are shown as `<Missing>`.",
        "Each chart contains vertically stacked horizontal boxplots, one per purchase brand plus a final `Whole cohort` boxplot. Adjacent labels show task and PN counts; dark-red lines show medians.",
        "The median-duration histogram counts purchase brands in two-second bins separately for each cohort.",
        "Cached task-level data is stored at `outputs/data/purchase-brand-analysis.parquet` for redraw-only runs.",
        "",
    ]
    for title, filename in chart_files:
        lines.extend((f"## {title}", "", f"![{title}]({filename})", ""))
    path = OUTPUT_DIRECTORY / "README.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_top_brands_table(frame: pd.DataFrame) -> Path:
    summary = (
        frame.groupby(["coh", "purchase_brand"], as_index=False)
        .agg(
            number_of_part_numbers=("part_number", "nunique"),
            number_of_tasks=("duration_seconds", "size"),
            median_dur_duration_seconds=("duration_seconds", "median"),
            average_dur_duration_seconds=("duration_seconds", "mean"),
        )
    )
    top_brands = (
        summary.sort_values(
            ["coh", "median_dur_duration_seconds", "purchase_brand"],
            ascending=[True, False, True],
        )
        .groupby("coh", sort=False, group_keys=False)
        .head(10)
    )
    table = top_brands.rename(
        columns={
            "coh": "Cohort",
            "purchase_brand": "Brand Name",
            "number_of_part_numbers": "Number of Part Numbers",
            "number_of_tasks": "Number of Tasks",
            "median_dur_duration_seconds": "Median DUR Duration (seconds)",
            "average_dur_duration_seconds": "Average DUR Duration (seconds)",
        }
    )
    for column in ("Median DUR Duration (seconds)", "Average DUR Duration (seconds)"):
        table[column] = table[column].map(lambda value: f"{value:,.2f}")
    headers = table.columns.tolist()
    markdown_lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    markdown_lines.extend(
        "| " + " | ".join(str(value) for value in row) + " |"
        for row in table.itertuples(index=False, name=None)
    )
    TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TABLE_PATH.write_text(
        "# Top 10 Purchase Brands by Median DUR Duration\n\n"
        "Top 10 brands within each cohort, ordered by descending median duration.\n\n"
        + "\n".join(markdown_lines)
        + "\n",
        encoding="utf-8",
    )
    return TABLE_PATH


def table_panel(frame: pd.DataFrame, cohort: str) -> alt.Chart:
    cohort_frame = frame.loc[frame["coh"] == cohort].copy()
    summary = (
        cohort_frame.groupby("purchase_brand", as_index=False)
        .agg(
            part_numbers=("part_number", "nunique"),
            tasks=("duration_seconds", "size"),
            median_seconds=("duration_seconds", "median"),
            average_seconds=("duration_seconds", "mean"),
        )
        .sort_values(["median_seconds", "purchase_brand"], ascending=[False, True])
        .head(10)
    )
    overall = pd.DataFrame(
        {
            "purchase_brand": ["Whole cohort"],
            "part_numbers": [cohort_frame["part_number"].nunique()],
            "tasks": [len(cohort_frame)],
            "median_seconds": [cohort_frame["duration_seconds"].median()],
            "average_seconds": [cohort_frame["duration_seconds"].mean()],
        }
    )
    rows = pd.concat([overall, summary], ignore_index=True)
    rows.insert(0, "row", range(1, len(rows) + 1))
    rows["brand_label"] = rows["purchase_brand"]
    rows["part_numbers_label"] = rows["part_numbers"].map(lambda value: f"{value:,}")
    rows["tasks_label"] = rows["tasks"].map(lambda value: f"{value:,}")
    rows["median_label"] = rows["median_seconds"].map(lambda value: f"{value:,.2f}")
    rows["average_label"] = rows["average_seconds"].map(lambda value: f"{value:,.2f}")
    header = {
        "row": 0,
        "brand_label": "Brand",
        "part_numbers_label": "PNs",
        "tasks_label": "Tasks",
        "median_label": "Median (s)",
        "average_label": "Average (s)",
    }
    rows = pd.concat([pd.DataFrame([header]), rows], ignore_index=True)
    columns = (
        ("brand_label", "Brand", 0, 360),
        ("part_numbers_label", "PNs", 360, 500),
        ("tasks_label", "Tasks", 500, 660),
        ("median_label", "Median (s)", 660, 820),
        ("average_label", "Average (s)", 820, 1000),
    )
    records = []
    for _, row in rows.iterrows():
        for field, column_title, x_start, x_end in columns:
            records.append(
                {
                    "row": str(int(row["row"])),
                    "value": row[field],
                    "x_start": x_start,
                    "x_end": x_end,
                    "x_center": (x_start + x_end) / 2,
                    "is_header": int(row["row"]) == 0,
                    "is_overall": int(row["row"]) == 1,
                    "cell_color": "#4c78a8"
                    if int(row["row"]) == 0
                    else "#fff2cc"
                    if int(row["row"]) == 1
                    else "white",
                    "text_color": "white" if int(row["row"]) == 0 else "#111111",
                }
            )
    table_frame = pd.DataFrame(records)
    row_order = [str(index) for index in range(len(rows))]
    base = alt.Chart(table_frame).encode(
        y=alt.Y("row:N", sort=row_order, axis=None),
    )
    background = base.mark_rect(stroke="#d0d0d0").encode(
        x=alt.X("x_start:Q", scale=alt.Scale(domain=[0, 1000]), axis=None),
        x2="x_end:Q",
        color=alt.Color("cell_color:N", scale=None, legend=None)
    )
    text = base.mark_text(fontSize=11).encode(
        x=alt.X("x_center:Q", scale=alt.Scale(domain=[0, 1000]), axis=None),
        text="value:N",
        color=alt.Color("text_color:N", scale=None, legend=None),
    )
    return (background + text).properties(title=cohort, width=1000, height=300)


def create_table_chart(frame: pd.DataFrame) -> alt.Chart:
    panels = [table_panel(frame, cohort) for cohort in COHORTS]
    return alt.vconcat(
        alt.hconcat(panels[0], panels[1], spacing=18),
        alt.hconcat(panels[2], panels[3], spacing=18),
        spacing=24,
    ).properties(
        title=alt.TitleParams(
            "Top 10 Purchase Brands by Median DUR Duration",
            subtitle="Each panel includes the whole-cohort statistics row",
            anchor="start",
        )
    ).configure(background=FIGURE_BACKGROUND).configure_view(
        stroke=None, fill=FIGURE_BACKGROUND
    )


def brand_median_histogram_chart(frame: pd.DataFrame) -> alt.Chart:
    """Plot the distribution of one median DUR duration per brand and cohort."""
    summary = (
        frame.groupby(["coh", "purchase_brand"], as_index=False)
        .agg(median_seconds=("duration_seconds", "median"))
    )
    panels = []
    for cohort in COHORTS:
        cohort_summary = summary.loc[summary["coh"] == cohort]
        chart = alt.Chart(cohort_summary).mark_bar().encode(
            x=alt.X(
                "median_seconds:Q",
                bin=alt.Bin(step=2),
                title="Brand median DUR duration (seconds)",
            ),
            y=alt.Y("count():Q", title="Number of brands"),
            tooltip=[
                alt.Tooltip("median_seconds:Q", bin=alt.Bin(step=2), title="Median DUR bin"),
                alt.Tooltip("count():Q", title="Brands"),
            ],
        ).properties(title=cohort, width=400, height=280)
        panels.append(chart)
    return alt.vconcat(
        alt.hconcat(panels[0], panels[1], spacing=20),
        alt.hconcat(panels[2], panels[3], spacing=20),
        spacing=28,
    ).properties(
        title=alt.TitleParams(
            "Purchase Brand Median DUR Duration Distribution",
            subtitle="Each brand contributes one median duration; bins are two seconds wide",
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
    chart_frame = frame.rename(columns={"purchase_brand": "mc3"})
    for cohort in COHORTS:
        filename = f"purchase-brand-analysis-{cohort.lower().replace(' ', '-')}.png"
        path = OUTPUT_DIRECTORY / filename
        boxplot_chart(
            chart_frame,
            cohort,
            category_title="Purchase brand",
            chart_title="Purchase brand",
        ).save(path, scale_factor=2)
        outputs.append(path)
        chart_files.append((cohort, filename))
    table_chart_path = OUTPUT_DIRECTORY / TABLE_CHART_PATH.name
    create_table_chart(frame).save(table_chart_path, scale_factor=2)
    outputs.append(table_chart_path)
    chart_files.append(("Top 10 Purchase Brand statistics table", table_chart_path.name))
    histogram_path = OUTPUT_DIRECTORY / MEDIAN_HISTOGRAM_PATH.name
    brand_median_histogram_chart(frame).save(histogram_path, scale_factor=2)
    outputs.append(histogram_path)
    chart_files.append(("Purchase Brand median DUR histogram", histogram_path.name))
    outputs.append(write_top_brands_table(frame))
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
    """Query task durations and render one purchase-brand chart per cohort."""
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

    png_count = sum(path.suffix == ".png" for path in outputs)
    click.echo(f"Created {png_count} PNG charts, {TABLE_PATH}, and {outputs[-1]}.")


if __name__ == "__main__":
    main()
