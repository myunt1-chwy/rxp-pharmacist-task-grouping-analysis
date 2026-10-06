#!/usr/bin/env python3
"""Compare same- and different-cohort DUR work time within users."""

from __future__ import annotations

from pathlib import Path

import altair as alt
import click
import pandas as pd
from scipy import stats

from . import santhosh_analysis as task_analysis
from .generate_task_table import REQUIRED_SETTINGS, parse_dotenv

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIRECTORY = REPOSITORY_ROOT / "outputs" / "charts" / "santhosh-analysis-user"
DATA_PATH = REPOSITORY_ROOT / "outputs" / "data" / "santhosh-analysis-user.parquet"
REPORT_PATH = REPOSITORY_ROOT / "outputs" / "reports" / "md" / "santosh_analysis_user.md"
ONE_SIDED_REPORT_PATH = (
    REPOSITORY_ROOT
    / "outputs"
    / "reports"
    / "md"
    / "santosh_analysis_user_one_sided.md"
)
CHART_FILENAME_PREFIX = "santosh-analysis-user"


def normalize_user_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    normalized.columns = [str(column).lower() for column in normalized.columns]
    required = {
        "cohort",
        "user_id",
        "same_mean_min",
        "different_mean_min",
        "difference_min",
    }
    missing = required.difference(normalized.columns)
    if missing:
        raise ValueError(
            "user-level data is missing columns: " + ", ".join(sorted(missing))
        )
    normalized["cohort"] = normalized["cohort"].astype(str)
    normalized["user_id"] = normalized["user_id"].astype(str)
    for column in ("same_mean_min", "different_mean_min", "difference_min"):
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    normalized = normalized.dropna(
        subset=["same_mean_min", "different_mean_min", "difference_min"]
    )
    normalized = normalized.loc[
        normalized["cohort"].isin(task_analysis.COHORT_ORDER)
    ].copy()
    if normalized.empty:
        raise ValueError("user-level data contains no paired cohort rows")
    return normalized


def aggregate_user_means(frame: pd.DataFrame) -> pd.DataFrame:
    task_frame = task_analysis.normalize_frame(frame)
    grouped = (
        task_frame.groupby(["cohort", "user_id", "allocation_pattern"], as_index=False)
        .agg(
            work_min=("work_min", "mean"),
            task_count=("work_min", "size"),
        )
    )
    user_means = (
        grouped.pivot_table(
            index=["cohort", "user_id"],
            columns="allocation_pattern",
            values="work_min",
            aggfunc="first",
        )
        .rename(
            columns={
                "Same Cohort": "same_mean_min",
                "Different Cohort": "different_mean_min",
            }
        )
    )
    user_counts = (
        grouped.pivot_table(
            index=["cohort", "user_id"],
            columns="allocation_pattern",
            values="task_count",
            aggfunc="first",
        )
        .rename(
            columns={
                "Same Cohort": "same_task_count",
                "Different Cohort": "different_task_count",
            }
        )
    )
    paired = user_means.join(user_counts, how="inner").dropna(
        subset=["same_mean_min", "different_mean_min"]
    )
    paired["difference_min"] = (
        paired["same_mean_min"] - paired["different_mean_min"]
    )
    return paired.reset_index()


def write_data(frame: pd.DataFrame) -> Path:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    normalize_user_frame(frame).to_parquet(DATA_PATH, index=False)
    return DATA_PATH


def read_data() -> pd.DataFrame:
    return normalize_user_frame(pd.read_parquet(DATA_PATH))


def cohort_frame(frame: pd.DataFrame, cohort: str) -> pd.DataFrame:
    normalized = normalize_user_frame(frame)
    if cohort not in task_analysis.COHORT_ORDER:
        raise ValueError(f"unknown cohort: {cohort}")
    selected = normalized.loc[normalized["cohort"] == cohort].copy()
    if selected.empty:
        raise ValueError(f"no paired users found for {cohort}")
    return selected


def user_distribution_frame(frame: pd.DataFrame, cohort: str) -> pd.DataFrame:
    selected = cohort_frame(frame, cohort)
    same = selected[["user_id", "cohort", "same_mean_min"]].rename(
        columns={"same_mean_min": "work_min"}
    )
    same["allocation_pattern"] = "Same Cohort"
    different = selected[["user_id", "cohort", "different_mean_min"]].rename(
        columns={"different_mean_min": "work_min"}
    )
    different["allocation_pattern"] = "Different Cohort"
    return pd.concat([same, different], ignore_index=True)


def paired_test(
    frame: pd.DataFrame,
    cohort: str,
    alpha: float = 0.05,
    alternative: str = "two-sided",
) -> dict[str, float | int]:
    if alternative not in {"two-sided", "less"}:
        raise ValueError("alternative must be 'two-sided' or 'less'")
    selected = cohort_frame(frame, cohort)
    differences = selected["difference_min"].to_numpy()
    n_users = len(differences)
    if n_users < 2:
        raise ValueError("a paired test needs at least two users")
    mean_difference = float(differences.mean())
    std_difference = float(differences.std(ddof=1))
    standard_error = std_difference / n_users**0.5
    degrees_of_freedom = n_users - 1
    if standard_error == 0:
        t_statistic = (
            float("inf")
            if mean_difference > 0
            else float("-inf")
            if mean_difference < 0
            else 0.0
        )
        if mean_difference == 0:
            p_value = 1.0
        elif alternative == "less":
            p_value = 0.0 if mean_difference < 0 else 1.0
        else:
            p_value = 0.0
        ci_low = float("-inf") if alternative == "less" else mean_difference
        ci_high = mean_difference
    else:
        t_statistic = mean_difference / standard_error
        p_value = (
            float(2 * stats.t.sf(abs(t_statistic), degrees_of_freedom))
            if alternative == "two-sided"
            else float(stats.t.cdf(t_statistic, degrees_of_freedom))
        )
        critical_probability = 1 - alpha / 2 if alternative == "two-sided" else 1 - alpha
        critical_value = float(stats.t.ppf(critical_probability, degrees_of_freedom))
        ci_low = (
            mean_difference - critical_value * standard_error
            if alternative == "two-sided"
            else float("-inf")
        )
        ci_high = mean_difference + critical_value * standard_error
    return {
        "n_users": n_users,
        "same_mean": float(selected["same_mean_min"].mean()),
        "different_mean": float(selected["different_mean_min"].mean()),
        "mean_difference": mean_difference,
        "standard_error": standard_error,
        "degrees_of_freedom": degrees_of_freedom,
        "t_statistic": t_statistic,
        "p_value": p_value,
        "ci_low": ci_low,
        "ci_high": ci_high,
    }


def user_distribution_chart(frame: pd.DataFrame, cohort: str) -> alt.Chart:
    chart_frame = user_distribution_frame(frame, cohort)
    chart_frame["work_seconds"] = chart_frame["work_min"] * 60
    return (
        alt.Chart(chart_frame)
        .transform_density(
            "work_seconds",
            as_=["work_seconds", "density"],
            groupby=["allocation_pattern"],
            extent=[1, 300],
            steps=150,
        )
        .mark_line(strokeWidth=3)
        .encode(
            x=alt.X(
                "work_seconds:Q",
                scale=alt.Scale(type="log", base=10),
                title="User mean work time (seconds, log10 scale)",
            ),
            y=alt.Y("density:Q", title="Density", scale=alt.Scale(domainMin=0)),
            color=alt.Color(
                "allocation_pattern:N",
                title="Allocation pattern",
                sort=list(task_analysis.ALLOCATION_ORDER),
            ),
            tooltip=[
                alt.Tooltip("allocation_pattern:N", title="Pattern"),
                alt.Tooltip("work_seconds:Q", title="User mean (seconds)"),
                alt.Tooltip("density:Q", title="Density"),
            ],
        )
        .properties(
            title=alt.TitleParams(
                f"User-level mean DUR work-time density — {cohort}",
                subtitle="Users with both allocation patterns; DUR work time limited to five minutes",
                anchor="start",
            ),
            width=900,
            height=500,
        )
        .configure(background=task_analysis.FIGURE_BACKGROUND)
        .configure_view(stroke=None, fill=task_analysis.FIGURE_BACKGROUND)
    )


def _format(value: float, digits: int = 4) -> str:
    return f"{value:.{digits}f}"


def _format_p_value(value: float) -> str:
    return "<1e-300" if value == 0 else f"{value:.6g}"


def _user_summary(frame: pd.DataFrame, cohort: str) -> list[dict[str, float | int | str]]:
    selected = cohort_frame(frame, cohort)
    rows = []
    for pattern, column in (
        ("Same Cohort", "same_mean_min"),
        ("Different Cohort", "different_mean_min"),
    ):
        values = selected[column]
        rows.append(
            {
                "allocation_pattern": pattern,
                "n_users": len(values),
                "mean_min": float(values.mean()),
                "std_min": float(values.std(ddof=1)),
                "median_min": float(values.median()),
                "p25_min": float(values.quantile(0.25)),
                "p75_min": float(values.quantile(0.75)),
            }
        )
    return rows


def write_report(
    frame: pd.DataFrame,
    report_path: Path,
    query: str,
    chart_paths: dict[str, str],
    alternative: str = "two-sided",
) -> Path:
    if alternative not in {"two-sided", "less"}:
        raise ValueError("alternative must be 'two-sided' or 'less'")
    normalized = normalize_user_frame(frame)
    p_value_label = "One-sided p-value" if alternative == "less" else "Two-sided p-value"
    interval_label = (
        "95% one-sided upper bound"
        if alternative == "less"
        else "95% CI for paired difference"
    )
    sections = []
    for cohort in task_analysis.COHORT_ORDER:
        result = paired_test(normalized, cohort, alternative=alternative)
        summary_rows = "\n".join(
            "| {allocation_pattern} | {n_users:,} | {mean_min:.4f} | {std_min:.4f} | "
            "{median_min:.4f} | {p25_min:.4f} | {p75_min:.4f} |".format(**row)
            for row in _user_summary(normalized, cohort)
        )
        significance = "reject" if result["p_value"] < 0.05 else "do not reject"
        interval_text = (
            f"(-∞, {_format(result['ci_high'])}]"
            if alternative == "less"
            else f"[{_format(result['ci_low'])}, {_format(result['ci_high'])}]"
        )
        sections.append(
            f"""## {cohort}

![User-level work-time density — {cohort}]({chart_paths[cohort]})

| Allocation pattern | Users | Mean user mean (min) | SD | Median | P25 | P75 |
|---|---:|---:|---:|---:|---:|---:|
{summary_rows}

The paired comparison uses the within-user difference
**Same Cohort − Different Cohort** for the {result['n_users']:,} users who have
observations in both allocation patterns.

| Quantity | Result |
|---|---:|
| Mean paired difference (minutes) | {_format(result["mean_difference"])} |
| {interval_label} | {interval_text} |
| Paired t-statistic | {_format(result["t_statistic"])} |
| Degrees of freedom | {result["degrees_of_freedom"]} |
| {p_value_label} | {_format_p_value(result["p_value"])} |

At the 0.05 level, we **{significance}** the null hypothesis for {cohort}.
"""
        )
    hypothesis_text = (
        "The paired test is a one-sided paired t-test. The null hypothesis is "
        "that Same Cohort is not faster than Different Cohort "
        "(Same Cohort − Different Cohort ≥ 0); the alternative is that this "
        "difference is less than zero, with alpha = 0.05.\nThe density plots "
        "show the two distributions of user-level means on a base-10 "
        "logarithmic x-axis."
        if alternative == "less"
        else "The paired test is a two-sided paired t-test on the within-user difference\n"
        "**Same Cohort − Different Cohort**, with alpha = 0.05. The density plots show\n"
        "the two distributions of user-level means on a base-10 logarithmic x-axis."
    )
    report = f"""# Santhosh User-Level Analysis

## Purpose and method

This analysis compares Same Cohort and Different Cohort DUR work time within
users, separately for Cohorts 1–4. Task durations are first averaged within
each user, cohort, and allocation pattern. Only users with both allocation
patterns in the same cohort are retained, so the comparison is paired by user.

{hypothesis_text}

The source query keeps transitions on or after 2026-08-01, DUR tasks with final
status `CLOSED`, non-null user and start time, work time between 0.01 and 5
minutes, and known item cohorts. Rows without a previous cohort are excluded.

{chr(10).join(sections)}

## Limitations

The unit of inference is the user within cohort, not the individual task. Users
with only one allocation pattern are excluded from each paired comparison, and
the resulting estimates describe the matched-user population. The analysis is
observational and does not establish that cohort allocation causes a difference.

## Query used

```sql
{query}
```
"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    return report_path


def create_outputs(
    frame: pd.DataFrame,
    report_path: Path | None = None,
    alternative: str = "two-sided",
) -> list[Path]:
    normalized = normalize_user_frame(frame)
    if report_path is None:
        report_path = REPORT_PATH
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    chart_paths: dict[str, str] = {}
    output_paths: list[Path] = []
    for cohort in task_analysis.COHORT_ORDER:
        filename = f"{CHART_FILENAME_PREFIX}-{cohort.lower().replace(' ', '-')}.png"
        chart_path = OUTPUT_DIRECTORY / filename
        user_distribution_chart(normalized, cohort).save(chart_path, scale_factor=2)
        output_paths.append(chart_path)
        chart_paths[cohort] = f"../../charts/{OUTPUT_DIRECTORY.name}/{filename}"
    output_paths.append(
        write_report(
            normalized,
            report_path,
            task_analysis.read_sql(),
            chart_paths,
            alternative=alternative,
        )
    )
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
    help="Redraw from the cached user-level Parquet data without connecting to Snowflake.",
)
@click.option(
    "--one-sided",
    is_flag=True,
    help="Use the directional alternative Same Cohort < Different Cohort and write a separate report.",
)
def main(env_file: Path, redraw_only: bool, one_sided: bool) -> None:
    """Run the paired user-level Santhosh cohort analysis."""
    try:
        if redraw_only:
            if not DATA_PATH.is_file():
                raise ValueError(f"cached user-level data not found: {DATA_PATH}")
            frame = read_data()
            click.echo(f"Loaded cached user-level data: {DATA_PATH}")
        else:
            if task_analysis.DATA_PATH.is_file():
                task_frame = task_analysis.read_data()
                click.echo(f"Loaded task-level data: {task_analysis.DATA_PATH}")
            else:
                if not env_file.is_file():
                    raise ValueError(f"environment file not found: {env_file}")
                settings = parse_dotenv(env_file)
                missing = [key for key in REQUIRED_SETTINGS if key not in settings]
                if missing:
                    raise ValueError("missing required settings: " + ", ".join(missing))
                task_frame = task_analysis.fetch_data(settings)
            frame = aggregate_user_means(task_frame)
            data_path = write_data(frame)
            click.echo(f"Saved user-level analysis data: {data_path}")
        outputs = create_outputs(
            frame,
            report_path=ONE_SIDED_REPORT_PATH if one_sided else REPORT_PATH,
            alternative="less" if one_sided else "two-sided",
        )
    except (ImportError, OSError, ValueError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(f"Created {len(outputs) - 1} user-level charts and report: {outputs[-1]}")


if __name__ == "__main__":
    main()
