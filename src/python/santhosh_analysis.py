#!/usr/bin/env python3
"""Compare DUR work-time distributions for same and different cohorts."""

from __future__ import annotations

from pathlib import Path

import altair as alt
import click
import pandas as pd
from scipy import stats

from .generate_task_table import REQUIRED_SETTINGS, connect_to_snowflake, parse_dotenv
from .plot_style import FIGURE_BACKGROUND

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SQL_PATH = REPOSITORY_ROOT / "src" / "sql" / "santhosh_analysis.sql"
OUTPUT_DIRECTORY = REPOSITORY_ROOT / "outputs" / "charts" / "santhosh-analysis"
DATA_PATH = REPOSITORY_ROOT / "outputs" / "data" / "santhosh-analysis.parquet"
REPORT_PATH = REPOSITORY_ROOT / "outputs" / "reports" / "md" / "santosh_analysis.md"
CHART_FILENAME = "santosh-analysis-distribution.png"
ALLOCATION_ORDER = ("Same Cohort", "Different Cohort")
COHORT_ORDER = ("Cohort 1", "Cohort 2", "Cohort 3", "Cohort 4")


def read_sql() -> str:
    return SQL_PATH.read_text(encoding="utf-8").strip()


def normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    normalized.columns = [str(column).lower() for column in normalized.columns]
    required = {"allocation_pattern", "cohort", "work_min"}
    missing = required.difference(normalized.columns)
    if missing:
        raise ValueError("query result is missing columns: " + ", ".join(sorted(missing)))
    normalized["allocation_pattern"] = normalized["allocation_pattern"].astype(str)
    normalized["cohort"] = normalized["cohort"].astype(str)
    normalized["work_min"] = pd.to_numeric(normalized["work_min"], errors="coerce")
    normalized = normalized.dropna(subset=["work_min"])
    normalized = normalized.loc[normalized["allocation_pattern"].isin(ALLOCATION_ORDER)].copy()
    normalized = normalized.loc[normalized["cohort"].isin(COHORT_ORDER)].copy()
    if normalized.empty:
        raise ValueError("query returned no valid allocation rows")
    return normalized


def fetch_data(settings: dict[str, str]) -> pd.DataFrame:
    connection = connect_to_snowflake(settings)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(read_sql())
            columns = [column[0].lower() for column in cursor.description]
            rows = cursor.fetchall()
        finally:
            cursor.close()
    finally:
        connection.close()
    return normalize_frame(pd.DataFrame(rows, columns=columns))


def write_data(frame: pd.DataFrame) -> Path:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(DATA_PATH, index=False)
    return DATA_PATH


def read_data() -> pd.DataFrame:
    return normalize_frame(pd.read_parquet(DATA_PATH))


def cohort_frame(frame: pd.DataFrame, cohort: str) -> pd.DataFrame:
    if cohort not in COHORT_ORDER:
        raise ValueError(f"unknown cohort: {cohort}")
    normalized = normalize_frame(frame)
    selected = normalized.loc[normalized["cohort"] == cohort].copy()
    if selected.empty:
        raise ValueError(f"query returned no rows for {cohort}")
    return selected


def descriptive_summary(frame: pd.DataFrame, cohort: str | None = None) -> pd.DataFrame:
    normalized = normalize_frame(frame)
    if cohort is not None:
        normalized = cohort_frame(normalized, cohort)
    summary = (
        normalized.groupby("allocation_pattern", sort=False)["work_min"]
        .agg(
            n="size",
            mean_min="mean",
            std_min="std",
            median_min="median",
            p25_min=lambda values: values.quantile(0.25),
            p75_min=lambda values: values.quantile(0.75),
        )
        .reindex(ALLOCATION_ORDER)
        .reset_index()
    )
    if summary["n"].isna().any():
        raise ValueError("both allocation groups are required")
    return summary


def welch_test(
    frame: pd.DataFrame,
    alpha: float = 0.05,
    cohort: str | None = None,
) -> dict[str, float | int]:
    normalized = normalize_frame(frame)
    if cohort is not None:
        normalized = cohort_frame(normalized, cohort)
    same = normalized.loc[
        normalized["allocation_pattern"] == "Same Cohort", "work_min"
    ].to_numpy()
    different = normalized.loc[
        normalized["allocation_pattern"] == "Different Cohort", "work_min"
    ].to_numpy()
    if len(same) < 2 or len(different) < 2:
        raise ValueError("both allocation groups need at least two observations")

    same_mean = float(same.mean())
    different_mean = float(different.mean())
    same_variance = float(same.var(ddof=1))
    different_variance = float(different.var(ddof=1))
    same_n = len(same)
    different_n = len(different)
    standard_error = (same_variance / same_n + different_variance / different_n) ** 0.5
    degrees_of_freedom = (
        (same_variance / same_n + different_variance / different_n) ** 2
        / (
            (same_variance / same_n) ** 2 / (same_n - 1)
            + (different_variance / different_n) ** 2 / (different_n - 1)
        )
    )
    mean_difference = same_mean - different_mean
    critical_value = float(stats.t.ppf(1 - alpha / 2, degrees_of_freedom))
    t_statistic = mean_difference / standard_error
    p_value = float(2 * stats.t.sf(abs(t_statistic), degrees_of_freedom))
    return {
        "same_n": same_n,
        "different_n": different_n,
        "same_mean": same_mean,
        "different_mean": different_mean,
        "mean_difference": mean_difference,
        "standard_error": standard_error,
        "degrees_of_freedom": float(degrees_of_freedom),
        "t_statistic": float(t_statistic),
        "p_value": p_value,
        "ci_low": mean_difference - critical_value * standard_error,
        "ci_high": mean_difference + critical_value * standard_error,
    }


def distribution_chart(frame: pd.DataFrame, cohort: str) -> alt.Chart:
    chart_frame = cohort_frame(frame, cohort)[["allocation_pattern", "work_min"]].copy()
    chart_frame["work_seconds"] = chart_frame["work_min"] * 60
    return (
        alt.Chart(chart_frame)
        .mark_bar(opacity=0.55)
        .encode(
            x=alt.X(
                "work_seconds:Q",
                bin=alt.Bin(step=2),
                title="Work time (seconds)",
            ),
            y=alt.Y("count():Q", title="Tasks", stack=None),
            color=alt.Color(
                "allocation_pattern:N",
                title="Allocation pattern",
                sort=list(ALLOCATION_ORDER),
            ),
            tooltip=[
                alt.Tooltip("allocation_pattern:N", title="Pattern"),
                alt.Tooltip("count():Q", title="Tasks"),
            ],
        )
        .properties(
            title=alt.TitleParams(
                f"DUR work-time distribution by allocation pattern — {cohort}",
                subtitle="Task-level work time with two-second bins",
                anchor="start",
            ),
            width=900,
            height=500,
        )
        .configure(background=FIGURE_BACKGROUND)
        .configure_view(stroke=None, fill=FIGURE_BACKGROUND)
    )


def _format(value: float, digits: int = 4) -> str:
    return f"{value:.{digits}f}"


def _format_p_value(value: float) -> str:
    return "<1e-300" if value == 0 else f"{value:.6g}"


def write_report(
    frame: pd.DataFrame,
    report_path: Path,
    query: str,
    chart_paths: dict[str, str],
) -> Path:
    normalized = normalize_frame(frame)
    cohort_sections = []
    for cohort in COHORT_ORDER:
        summary = descriptive_summary(normalized, cohort)
        result = welch_test(normalized, cohort=cohort)
        summary_rows = "\n".join(
            "| {allocation_pattern} | {n:,} | {mean_min:.4f} | {std_min:.4f} | "
            "{median_min:.4f} | {p25_min:.4f} | {p75_min:.4f} |".format(**row)
            for row in summary.to_dict(orient="records")
        )
        significance = "reject" if result["p_value"] < 0.05 else "do not reject"
        cohort_sections.append(
            f"""## {cohort}

![Work-time distribution — {cohort}]({chart_paths[cohort]})

| Allocation pattern | Tasks | Mean (min) | SD (min) | Median (min) | P25 (min) | P75 (min) |
|---|---:|---:|---:|---:|---:|---:|
{summary_rows}

| Quantity | Result |
|---|---:|
| Same Cohort mean (minutes) | {_format(result["same_mean"])} |
| Different Cohort mean (minutes) | {_format(result["different_mean"])} |
| Mean difference (minutes) | {_format(result["mean_difference"])} |
| 95% CI for mean difference | [{_format(result["ci_low"])}, {_format(result["ci_high"])}] |
| Welch t-statistic | {_format(result["t_statistic"])} |
| Welch degrees of freedom | {_format(result["degrees_of_freedom"])} |
| Two-sided p-value | {_format_p_value(result["p_value"])} |

At the 0.05 level, we **{significance}** the null hypothesis for {cohort}.
"""
        )
    cohort_report = "\n".join(cohort_sections)
    report = f"""# Santhosh Query Analysis

## Purpose

This analysis compares task work time for consecutive DUR tasks allocated to the
same cohort versus a different cohort, separately for Cohorts 1–4. Work time is
`DWELL_IN_PROGRESS_TO_CLOSED_MINUTES`, measured in minutes.

The source query keeps the original filters: transitions on or after
2026-08-01, DUR tasks with final status `CLOSED`, non-null user and start time,
work time between 0.01 and 30 minutes, and known item cohorts. The previous
cohort is calculated within user and transition date, ordered by `STARTED_AT`.
Rows without a previous cohort are excluded. Distribution charts use two-second
bins after converting work time from minutes to seconds.

## Hypothesis test

The primary test is a two-sided Welch two-sample t-test. The null hypothesis is
that the two population means are equal; the alternative is that they differ.
The reported contrast is **Same Cohort − Different Cohort**, with alpha = 0.05.

{cohort_report}

Each result is an observational comparison of task means and does not establish
that cohort allocation causes the difference.

## Limitations

Welch's test allows unequal variances but treats task rows as independent.
Users and transition dates can contribute multiple tasks, so the p-value and
confidence interval should be interpreted as the requested row-level analysis,
not as a dependence-adjusted estimate. The cohort comparison also inherits the
source query's ordering and filtering choices.

## Query used

```sql
{query}
```
"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    return report_path


def create_outputs(frame: pd.DataFrame) -> list[Path]:
    normalized = normalize_frame(frame)
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    chart_paths: dict[str, str] = {}
    output_paths: list[Path] = []
    for cohort in COHORT_ORDER:
        cohort_filename = f"santosh-analysis-{cohort.lower().replace(' ', '-')}.png"
        chart_path = OUTPUT_DIRECTORY / cohort_filename
        distribution_chart(normalized, cohort).save(chart_path, scale_factor=2)
        output_paths.append(chart_path)
        chart_paths[cohort] = f"../../charts/{OUTPUT_DIRECTORY.name}/{cohort_filename}"
    output_paths.append(write_report(normalized, REPORT_PATH, read_sql(), chart_paths))
    return output_paths


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
    """Run the Santhosh cohort-allocation analysis."""
    try:
        if redraw_only:
            if not DATA_PATH.is_file():
                raise ValueError(f"cached Parquet data not found: {DATA_PATH}")
            frame = read_data()
            click.echo(f"Loaded cached analysis data: {DATA_PATH}")
        else:
            if not env_file.is_file():
                raise ValueError(f"environment file not found: {env_file}")
            settings = parse_dotenv(env_file)
            missing = [key for key in REQUIRED_SETTINGS if key not in settings]
            if missing:
                raise ValueError("missing required settings: " + ", ".join(missing))
            frame = fetch_data(settings)
            data_path = write_data(frame)
            click.echo(f"Saved analysis data: {data_path}")
        outputs = create_outputs(frame)
    except (ImportError, OSError, ValueError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(f"Created {len(outputs) - 1} cohort charts and report: {outputs[-1]}")


if __name__ == "__main__":
    main()
