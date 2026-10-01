#!/usr/bin/env python3
"""Analyze DUR duration by prior approved non-vet-diet prescription count."""

from __future__ import annotations

from pathlib import Path

import click
import pandas as pd

from .create_initiation_channel_analysis import (
    COHORTS,
    boxplot_chart as shared_boxplot_chart,
)
from .generate_task_table import REQUIRED_SETTINGS, connect_to_snowflake, parse_dotenv

SOURCE_TABLE = "EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_VALID_DUR_TASKS"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIRECTORY = (
    REPOSITORY_ROOT / "outputs" / "charts" / "prior-approved-non-vet-diet-rx-analysis"
)
DATA_PATH = (
    REPOSITORY_ROOT
    / "outputs"
    / "data"
    / "prior-approved-non-vet-diet-rx-analysis.parquet"
)
GENERATED_SQL_PATH = (
    REPOSITORY_ROOT
    / "generated"
    / "create_prior_approved_non_vet_diet_rx_analysis.sql"
)

PRIOR_APPROVED_NON_VET_DIET_RX_SQL = f"""
WITH base_tasks AS (
    SELECT
        TASK_ID,
        COH,
        COALESCE(N_PRIOR_APPROVED_NON_VET_DIET_RX_IDS, 0)
            AS N_PRIOR_APPROVED_NON_VET_DIET_RX_IDS,
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
    N_PRIOR_APPROVED_NON_VET_DIET_RX_IDS,
    CASE
        WHEN N_PRIOR_APPROVED_NON_VET_DIET_RX_IDS >= 10 THEN '10+'
        ELSE TO_VARCHAR(N_PRIOR_APPROVED_NON_VET_DIET_RX_IDS)
    END AS N_PRIOR_APPROVED_NON_VET_DIET_RX_IDS_BUCKET,
    DURATION_SECONDS
FROM filtered_tasks
ORDER BY COH, N_PRIOR_APPROVED_NON_VET_DIET_RX_IDS, DURATION_SECONDS
""".strip()


def write_generated_sql() -> Path:
    GENERATED_SQL_PATH.parent.mkdir(parents=True, exist_ok=True)
    GENERATED_SQL_PATH.write_text(
        PRIOR_APPROVED_NON_VET_DIET_RX_SQL + "\n", encoding="utf-8"
    )
    return GENERATED_SQL_PATH


def normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    normalized["duration_seconds"] = pd.to_numeric(
        normalized["duration_seconds"], errors="coerce"
    )
    bucket_column = "n_prior_approved_non_vet_diet_rx_ids_bucket"
    buckets = (
        normalized[bucket_column]
        .astype("string")
        .str.strip()
        .replace("", pd.NA)
        .fillna("0")
    )
    numeric_buckets = pd.to_numeric(buckets, errors="coerce")
    numeric_mask = numeric_buckets.notna()
    buckets.loc[numeric_mask] = numeric_buckets.loc[numeric_mask].astype(int).map(
        lambda value: "10+" if value >= 10 else str(value)
    )
    normalized[bucket_column] = buckets.astype(str)
    return normalized


def fetch_data(settings: dict[str, str]) -> pd.DataFrame:
    connection = connect_to_snowflake(settings)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(PRIOR_APPROVED_NON_VET_DIET_RX_SQL)
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


def boxplot_chart(frame: pd.DataFrame, cohort: str):
    """Create one horizontal non-vet-diet prior-count boxplot chart."""
    chart_frame = normalize_frame(frame).rename(
        columns={
            "n_prior_approved_non_vet_diet_rx_ids_bucket": "initiation_channel"
        }
    )
    return shared_boxplot_chart(
        chart_frame,
        cohort,
        grouping_column="initiation_channel",
        grouping_title="Number of prior approved non-vet-diet RX IDs",
    )


def write_markdown(chart_files: list[tuple[str, str]]) -> Path:
    lines = [
        "# Prior approved non-vet-diet prescription analysis",
        "",
        "Valid DUR tasks are selected from `MY_RXP_VALID_DUR_TASKS` for Cohorts 1–4.",
        "Durations at or above the global approximate 95th percentile are excluded.",
        "`N_PRIOR_APPROVED_NON_VET_DIET_RX_IDS` is bucketed as `0` through `9` and `10+`; null values are represented as `0`.",
        "Each chart contains a horizontal boxplot for every bucket plus a final `Whole cohort` reference boxplot. Labels show filtered task counts, and dark-red lines show medians.",
        "Cached task-level data is stored at `outputs/data/prior-approved-non-vet-diet-rx-analysis.parquet` for redraw-only runs.",
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
    for cohort in COHORTS:
        filename = (
            "prior-approved-non-vet-diet-rx-analysis-"
            f"{cohort.lower().replace(' ', '-')}.png"
        )
        path = OUTPUT_DIRECTORY / filename
        boxplot_chart(normalized, cohort).save(path, scale_factor=2)
        outputs.append(path)
        chart_files.append((cohort, filename))
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
    """Query valid DUR durations and render one non-vet-diet chart per cohort."""
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
