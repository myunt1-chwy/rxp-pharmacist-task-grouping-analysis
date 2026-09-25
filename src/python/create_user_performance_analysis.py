#!/usr/bin/env python3
"""Create user-level DUR performance scatter matrices by cohort."""

from __future__ import annotations

from pathlib import Path
import re

import altair as alt
import click
import pandas as pd

from .generate_task_table import REQUIRED_SETTINGS, connect_to_snowflake, parse_dotenv

SOURCE_TABLE = "EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASKS"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIRECTORY = REPOSITORY_ROOT / "outputs" / "charts" / "user-performance-analysis"
DATA_PATH = REPOSITORY_ROOT / "outputs" / "data" / "user-performance-analysis.parquet"
GENERATED_SQL_PATH = REPOSITORY_ROOT / "generated" / "create_user_performance_analysis.sql"
MIN_TASKS_PER_COHORT = 30

AGGREGATE_SQL = f"""
WITH base_tasks AS (
    SELECT
        USER_ID,
        COH,
        COALESCE(JOB_TITLE, '<Missing>') AS JOB_TITLE,
        COALESCE(WH_ID, '<Missing>') AS WH_ID,
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
), filtered_tasks AS (
    SELECT base.*
    FROM base_tasks AS base
    CROSS JOIN percentile_bounds
    WHERE base.DURATION_SECONDS < percentile_bounds.P95_SECONDS
), user_cohort_stats AS (
    SELECT
        USER_ID,
        COH,
        COUNT(*) AS TASK_COUNT,
        AVG(DURATION_SECONDS) AS MEAN_DURATION_SECONDS,
        MEDIAN(DURATION_SECONDS) AS MEDIAN_DURATION_SECONDS,
        STDDEV_SAMP(DURATION_SECONDS) AS STDDEV_DURATION_SECONDS
    FROM filtered_tasks
    GROUP BY USER_ID, COH
), user_job_titles AS (
    SELECT
        USER_ID,
        MODE(JOB_TITLE) AS JOB_TITLE
    FROM filtered_tasks
    GROUP BY USER_ID
), user_warehouses AS (
    SELECT
        USER_ID,
        MODE(WH_ID) AS WH_ID
    FROM filtered_tasks
    GROUP BY USER_ID
), users AS (
    SELECT DISTINCT USER_ID
    FROM filtered_tasks
), cohorts AS (
    SELECT DISTINCT COH
    FROM filtered_tasks
), complete_grid AS (
    SELECT
        users.USER_ID,
        cohorts.COH
    FROM users
    CROSS JOIN cohorts
)
SELECT
    complete_grid.USER_ID,
    complete_grid.COH,
    user_job_titles.JOB_TITLE,
    user_warehouses.WH_ID,
    user_cohort_stats.TASK_COUNT,
    user_cohort_stats.MEAN_DURATION_SECONDS,
    user_cohort_stats.MEDIAN_DURATION_SECONDS,
    user_cohort_stats.STDDEV_DURATION_SECONDS
FROM complete_grid
LEFT JOIN user_cohort_stats
    ON user_cohort_stats.USER_ID = complete_grid.USER_ID
   AND user_cohort_stats.COH = complete_grid.COH
LEFT JOIN user_job_titles
    ON user_job_titles.USER_ID = complete_grid.USER_ID
LEFT JOIN user_warehouses
    ON user_warehouses.USER_ID = complete_grid.USER_ID
ORDER BY complete_grid.USER_ID, complete_grid.COH
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
        "task_count",
        "mean_duration_seconds",
        "median_duration_seconds",
        "stddev_duration_seconds",
    ):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def write_data(frame: pd.DataFrame) -> Path:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(DATA_PATH, index=False)
    return DATA_PATH


def read_data() -> pd.DataFrame:
    return pd.read_parquet(DATA_PATH)


def scatter_cell(
    frame: pd.DataFrame,
    x_cohort: str,
    y_cohort: str,
    metric: str,
) -> alt.Chart:
    wide = frame.pivot(index="user_id", columns="coh")
    wide.columns = [f"{field}__{cohort}" for field, cohort in wide.columns]
    wide = wide.reset_index()
    x_count = f"task_count__{x_cohort}"
    y_count = f"task_count__{y_cohort}"
    x_field = f"{metric}__{x_cohort}"
    y_field = f"{metric}__{y_cohort}"
    x_stddev = f"stddev_duration_seconds__{x_cohort}"
    y_stddev = f"stddev_duration_seconds__{y_cohort}"
    x_job_title = f"job_title__{x_cohort}"
    x_warehouse = f"wh_id__{x_cohort}"
    eligible = wide.loc[
        wide[x_count].ge(MIN_TASKS_PER_COHORT)
        & wide[y_count].ge(MIN_TASKS_PER_COHORT)
        & wide[x_field].notna()
        & wide[y_field].notna()
    ].copy()
    points = (
        alt.Chart(eligible)
        .mark_point(filled=True, opacity=0.45, size=28)
        .encode(
            x=alt.X(
                f"{x_field}:Q",
                title=f"{x_cohort} (n={len(eligible):,} users)",
                scale=alt.Scale(zero=False),
            ),
            y=alt.Y(
                f"{y_field}:Q",
                title=f"{y_cohort} (n={len(eligible):,} users)",
                scale=alt.Scale(zero=False),
            ),
            color=alt.Color(
                f"{x_job_title}:N",
                title="Job title",
                scale=alt.Scale(scheme="tableau20"),
            ),
            shape=alt.Shape(f"{x_warehouse}:N", title="Warehouse"),
            tooltip=[
                alt.Tooltip("user_id:N", title="User ID"),
                alt.Tooltip(f"{x_job_title}:N", title="Job title"),
                alt.Tooltip(f"{x_warehouse}:N", title="Warehouse"),
                alt.Tooltip(f"{x_count}:Q", title=f"{x_cohort} tasks", format=",.0f"),
                alt.Tooltip(f"{y_count}:Q", title=f"{y_cohort} tasks", format=",.0f"),
                alt.Tooltip(f"{x_stddev}:Q", title=f"{x_cohort} SD", format=",.2f"),
                alt.Tooltip(f"{y_stddev}:Q", title=f"{y_cohort} SD", format=",.2f"),
            ],
        )
        .properties(width=190, height=190)
    )
    if eligible.empty:
        return points
    correlation = eligible[x_field].corr(eligible[y_field])
    correlation_label = (
        f"r = —; n = {len(eligible):,}"
        if pd.isna(correlation)
        else f"r = {correlation:.2f}; n = {len(eligible):,}"
    )
    annotation = (
        alt.Chart(
            pd.DataFrame(
                {
                    x_field: [eligible[x_field].max()],
                    y_field: [eligible[y_field].max()],
                    "correlation_label": [correlation_label],
                }
            )
        )
        .mark_text(align="right", baseline="top", dx=-6, dy=6, fontSize=12, fontWeight="bold")
        .encode(
            x=alt.X(f"{x_field}:Q", scale=alt.Scale(zero=False)),
            y=alt.Y(f"{y_field}:Q", scale=alt.Scale(zero=False)),
            text="correlation_label:N",
        )
        .properties(width=190, height=190)
    )
    return points + annotation


def create_matrix(frame: pd.DataFrame, metric: str, title: str) -> alt.Chart:
    if frame.empty:
        raise ValueError("the filtered task query returned no rows")
    cohorts = sorted(frame["coh"].dropna().unique().tolist(), key=natural_sort_key)
    if len(cohorts) < 2:
        raise ValueError("at least two cohorts are required for a scatter matrix")

    rows: list[alt.Chart] = []
    for row_index, y_cohort in enumerate(cohorts):
        cells: list[alt.Chart] = []
        for column_index, x_cohort in enumerate(cohorts):
            if column_index > row_index:
                cells.append(scatter_cell(frame, x_cohort, y_cohort, metric))
        if cells:
            rows.append(alt.hconcat(*cells, spacing=8))
    return alt.vconcat(*rows, spacing=8).properties(
        title=alt.TitleParams(title, anchor="start")
    ).configure_view(stroke="#d0d0d0")


def complete_cohort_users(frame: pd.DataFrame, cohorts: list[str]) -> pd.DataFrame:
    eligible_users = frame["user_id"].drop_duplicates()
    for cohort in cohorts:
        cohort_rows = frame.loc[frame["coh"] == cohort]
        eligible = cohort_rows.loc[
            cohort_rows["task_count"].ge(MIN_TASKS_PER_COHORT)
            & cohort_rows["mean_duration_seconds"].notna()
            & cohort_rows["median_duration_seconds"].notna()
        ]["user_id"]
        eligible_users = eligible_users[eligible_users.isin(eligible)]
    return frame.loc[frame["user_id"].isin(eligible_users)].copy()


def create_performance_heatmaps(
    frame: pd.DataFrame,
    metric: str,
    aggregation: str,
    title: str,
) -> alt.Chart:
    summary = (
        frame.loc[frame["task_count"].ge(MIN_TASKS_PER_COHORT)]
        .dropna(subset=["coh", "job_title", "wh_id", metric])
        .groupby(["coh", "wh_id", "job_title"], as_index=False)
        .agg(
            heatmap_value=(metric, aggregation),
            user_count=("user_id", "nunique"),
        )
    )
    if summary.empty:
        raise ValueError("no user performance data is available for the heatmaps")
    cohort_order = sorted(summary["coh"].unique().tolist(), key=natural_sort_key)
    warehouse_order = sorted(summary["wh_id"].unique().tolist(), key=natural_sort_key)
    job_title_order = sorted(summary["job_title"].unique().tolist(), key=natural_sort_key)
    cohort_user_counts = (
        frame.loc[frame["task_count"].ge(MIN_TASKS_PER_COHORT)]
        .dropna(subset=[metric])
        .groupby("coh")["user_id"]
        .nunique()
        .to_dict()
    )
    color_domain = [
        float(summary["heatmap_value"].min()),
        float(summary["heatmap_value"].max()),
    ]
    summary["cell_label"] = summary.apply(
        lambda row: f"{row['heatmap_value']:.1f}\n(n={row['user_count']:,})",
        axis=1,
    )
    threshold = float(summary["heatmap_value"].max()) * 0.55

    def panel(cohort: str) -> alt.Chart:
        panel_summary = summary.loc[summary["coh"] == cohort]
        base = alt.Chart(panel_summary).encode(
            x=alt.X("job_title:N", title="Job title", sort=job_title_order, axis=alt.Axis(labelAngle=-45)),
            y=alt.Y("wh_id:N", title="Warehouse", sort=warehouse_order),
            tooltip=[
                alt.Tooltip("coh:N", title="Cohort"),
                alt.Tooltip("wh_id:N", title="Warehouse"),
                alt.Tooltip("job_title:N", title="Job title"),
                alt.Tooltip("heatmap_value:Q", title="Duration statistic (seconds)", format=",.2f"),
                alt.Tooltip("user_count:Q", title="Users", format=",.0f"),
            ],
        )
        rectangles = base.mark_rect().encode(
            color=alt.Color(
                "heatmap_value:Q",
                title="Duration statistic (seconds)",
                scale=alt.Scale(
                    domain=color_domain,
                    range=["#2166ac", "#bdbdbd", "#b2182b"],
                ),
            )
        )
        labels = base.mark_text(fontSize=11, fontWeight="bold").encode(
            text="cell_label:N",
            color=alt.condition(
                f"datum.heatmap_value > {threshold}",
                alt.value("white"),
                alt.value("#111111"),
            ),
        )
        heatmap = (rectangles + labels).properties(
            width=600,
            height=340,
            title=alt.TitleParams(cohort, anchor="start"),
        )
        footer = alt.Chart(
            pd.DataFrame(
                {"label": [f"Pharmacists/users: {cohort_user_counts.get(cohort, 0):,}"]}
            )
        ).mark_text(fontWeight="bold", fontSize=13).encode(text="label:N").properties(
            width=600, height=24
        )
        return alt.vconcat(heatmap, footer, spacing=2)

    panels = [panel(cohort) for cohort in cohort_order]
    return alt.vconcat(
        alt.hconcat(panels[0], panels[1], spacing=12),
        alt.hconcat(panels[2], panels[3], spacing=12),
        spacing=12,
    ).properties(
        title=alt.TitleParams(
            title,
            anchor="start",
        )
    ).configure_view(stroke=None)


def create_user_task_count_distribution(frame: pd.DataFrame) -> alt.Chart:
    cohort_order = sorted(frame["coh"].dropna().unique().tolist(), key=natural_sort_key)
    panels: list[alt.Chart] = []
    for cohort in cohort_order:
        cohort_frame = frame.loc[
            (frame["coh"] == cohort) & frame["task_count"].notna()
        ].copy()
        histogram = (
            alt.Chart(cohort_frame)
            .mark_bar()
            .encode(
                x=alt.X(
                    "task_count:Q",
                    bin=alt.Bin(maxbins=50),
                    title="DUR tasks per user (binned)",
                ),
                y=alt.Y("count():Q", title="Users"),
                tooltip=[
                    alt.Tooltip("task_count:Q", bin=alt.Bin(maxbins=50), title="DUR tasks"),
                    alt.Tooltip("count():Q", title="Users", format=",.0f"),
                ],
            )
            .properties(width=520, height=300, title=alt.TitleParams(cohort, anchor="start"))
        )
        panels.append(histogram)
    return alt.vconcat(
        alt.hconcat(panels[0], panels[1], spacing=12),
        alt.hconcat(panels[2], panels[3], spacing=12),
        spacing=12,
    ).properties(
        title=alt.TitleParams("Distribution of DUR tasks completed per user", anchor="start")
    ).configure_view(stroke=None)


def create_user_median_duration_distribution(frame: pd.DataFrame) -> alt.Chart:
    cohort_order = sorted(frame["coh"].dropna().unique().tolist(), key=natural_sort_key)
    panels: list[alt.Chart] = []
    for cohort in cohort_order:
        cohort_frame = frame.loc[
            (frame["coh"] == cohort) & frame["median_duration_seconds"].notna()
        ].copy()
        histogram = (
            alt.Chart(cohort_frame)
            .mark_bar()
            .encode(
                x=alt.X(
                    "median_duration_seconds:Q",
                    bin=alt.Bin(maxbins=50),
                    title="Median DUR duration per user (seconds, binned)",
                ),
                y=alt.Y("count():Q", title="Users"),
                tooltip=[
                    alt.Tooltip(
                        "median_duration_seconds:Q",
                        bin=alt.Bin(maxbins=50),
                        title="Median duration (seconds)",
                    ),
                    alt.Tooltip("count():Q", title="Users", format=",.0f"),
                ],
            )
            .properties(width=520, height=300, title=alt.TitleParams(cohort, anchor="start"))
        )
        panels.append(histogram)
    return alt.vconcat(
        alt.hconcat(panels[0], panels[1], spacing=12),
        alt.hconcat(panels[2], panels[3], spacing=12),
        spacing=12,
    ).properties(
        title=alt.TitleParams("Distribution of median DUR duration per user", anchor="start")
    ).configure_view(stroke=None)


def write_markdown(chart_files: list[tuple[str, str]]) -> Path:
    lines = [
        "# User performance by cohort",
        "",
        "Durations at or above the filtered population's approximate 95th percentile are excluded.",
        f"Each pairwise scatter cell includes users with at least {MIN_TASKS_PER_COHORT} tasks in both compared cohorts, displays Pearson's r and the eligible-user count, colors points by job title, and shapes them by warehouse.",
        "",
    ]
    for title, filename in chart_files:
        lines.extend((f"## {title}", "", f"![{title}]({filename})", ""))
    path = OUTPUT_DIRECTORY / "README.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def create_outputs(frame: pd.DataFrame) -> list[Path]:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for stale_output in OUTPUT_DIRECTORY.glob("*.png"):
        stale_output.unlink()
    outputs: list[Path] = []
    chart_files: list[tuple[str, str]] = []
    cohorts = sorted(frame["coh"].dropna().unique().tolist(), key=natural_sort_key)
    for metric, label, filename in (
        ("mean_duration_seconds", "Mean duration", "user-performance-mean-scatter-matrix.png"),
        ("median_duration_seconds", "Median duration", "user-performance-median-scatter-matrix.png"),
    ):
        path = OUTPUT_DIRECTORY / filename
        create_matrix(frame, metric, f"User DUR {label.lower()} by cohort").save(path, scale_factor=2)
        outputs.append(path)
        chart_files.append((label, filename))
    complete_frame = complete_cohort_users(frame, cohorts)
    for metric, label, filename in (
        (
            "mean_duration_seconds",
            "Mean duration — users with all four cohorts",
            "user-performance-mean-all-cohorts-scatter-matrix.png",
        ),
        (
            "median_duration_seconds",
            "Median duration — users with all four cohorts",
            "user-performance-median-all-cohorts-scatter-matrix.png",
        ),
    ):
        path = OUTPUT_DIRECTORY / filename
        create_matrix(
            complete_frame,
            metric,
            f"User DUR {label.lower()} (at least {MIN_TASKS_PER_COHORT} tasks per cohort)",
        ).save(path, scale_factor=2)
        outputs.append(path)
        chart_files.append((label, filename))
    heatmap_path = OUTPUT_DIRECTORY / "user-performance-average-of-user-means-heatmaps.png"
    create_performance_heatmaps(
        frame,
        "mean_duration_seconds",
        "mean",
        "Average of per-user mean DUR duration by warehouse and job title",
    ).save(heatmap_path, scale_factor=2)
    outputs.append(heatmap_path)
    chart_files.append(("Average of per-user means by warehouse and job title", heatmap_path.name))
    median_heatmap_path = OUTPUT_DIRECTORY / "user-performance-median-of-user-medians-heatmaps.png"
    create_performance_heatmaps(
        frame,
        "median_duration_seconds",
        "median",
        "Median of per-user median DUR duration by warehouse and job title",
    ).save(median_heatmap_path, scale_factor=2)
    outputs.append(median_heatmap_path)
    chart_files.append(("Median of per-user medians by warehouse and job title", median_heatmap_path.name))
    task_count_path = OUTPUT_DIRECTORY / "user-dur-count-distributions.png"
    create_user_task_count_distribution(frame).save(task_count_path, scale_factor=2)
    outputs.append(task_count_path)
    chart_files.append(("Distribution of DUR tasks per user", task_count_path.name))
    median_duration_path = OUTPUT_DIRECTORY / "user-median-dur-duration-distributions.png"
    create_user_median_duration_distribution(frame).save(median_duration_path, scale_factor=2)
    outputs.append(median_duration_path)
    chart_files.append(("Distribution of median DUR duration per user", median_duration_path.name))
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
    """Render mean and median user-performance scatter matrices."""
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
