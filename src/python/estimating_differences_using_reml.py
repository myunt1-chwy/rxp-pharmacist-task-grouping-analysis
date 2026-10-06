#!/usr/bin/env python3
"""Estimate user-level cohort differences with a REML random-effects model."""

from __future__ import annotations

from pathlib import Path

import click
import numpy as np
import pandas as pd
from scipy import optimize, stats

from . import santhosh_analysis as task_analysis
from .generate_task_table import REQUIRED_SETTINGS, parse_dotenv

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = (
    REPOSITORY_ROOT
    / "outputs"
    / "reports"
    / "md"
    / "estimating_differences_using_REML.md"
)
DATA_PATH = (
    REPOSITORY_ROOT
    / "outputs"
    / "data"
    / "estimating-differences-using-reml.parquet"
)


def _pooled_variances(task_frame: pd.DataFrame) -> pd.DataFrame:
    """Return cohort/pattern residual variances for sparse user cells."""
    grouped = task_frame.groupby(
        ["cohort", "user_id", "allocation_pattern"], observed=True
    )
    user_stats = grouped["work_min"].agg(
        task_count="size",
        mean_min="mean",
        sum_squared_error=lambda values: ((values - values.mean()) ** 2).sum(),
    ).reset_index()
    pooled = (
        user_stats.groupby(["cohort", "allocation_pattern"], observed=True)
        .agg(
            sum_squared_error=("sum_squared_error", "sum"),
            degrees_of_freedom=("task_count", lambda values: (values - 1).sum()),
        )
        .reset_index()
    )
    pooled["pooled_variance_min2"] = (
        pooled["sum_squared_error"] / pooled["degrees_of_freedom"]
    )
    return pooled[["cohort", "allocation_pattern", "pooled_variance_min2"]]


def aggregate_user_effects(frame: pd.DataFrame) -> pd.DataFrame:
    """Create paired user effects and their estimated sampling variances."""
    task_frame = task_analysis.normalize_frame(frame)
    grouped = task_frame.groupby(
        ["cohort", "user_id", "allocation_pattern"], observed=True
    )
    user_stats = grouped["work_min"].agg(
        task_count="size",
        mean_min="mean",
        variance_min2=lambda values: values.var(ddof=1),
    ).reset_index()
    pooled = _pooled_variances(task_frame)
    user_stats = user_stats.merge(
        pooled, on=["cohort", "allocation_pattern"], how="left"
    )
    user_stats["variance_min2"] = user_stats["variance_min2"].fillna(
        user_stats["pooled_variance_min2"]
    )
    user_stats["variance_source"] = np.where(
        user_stats["task_count"] > 1, "within-user", "pooled cohort-pattern"
    )

    value_wide = user_stats.pivot(
        index=["cohort", "user_id"],
        columns="allocation_pattern",
        values=["mean_min", "variance_min2", "task_count", "variance_source"],
    )
    value_wide.columns = [f"{metric}_{pattern.lower().replace(' ', '_')}" for metric, pattern in value_wide.columns]
    paired = value_wide.reset_index().dropna(
        subset=["mean_min_same_cohort", "mean_min_different_cohort"]
    )
    paired = paired.rename(
        columns={
            "mean_min_same_cohort": "same_mean_min",
            "mean_min_different_cohort": "different_mean_min",
            "variance_min2_same_cohort": "same_variance_min2",
            "variance_min2_different_cohort": "different_variance_min2",
            "task_count_same_cohort": "same_task_count",
            "task_count_different_cohort": "different_task_count",
            "variance_source_same_cohort": "same_variance_source",
            "variance_source_different_cohort": "different_variance_source",
        }
    )
    paired["difference_min"] = (
        paired["same_mean_min"] - paired["different_mean_min"]
    )
    paired["sampling_variance_min2"] = (
        paired["same_variance_min2"] / paired["same_task_count"]
        + paired["different_variance_min2"] / paired["different_task_count"]
    )
    if paired["sampling_variance_min2"].isna().any() or (
        paired["sampling_variance_min2"] <= 0
    ).any():
        raise ValueError("all paired users need positive sampling variance")
    return paired


def _reml_objective(log_scale: float, effects: np.ndarray, variances: np.ndarray) -> float:
    scale = max(float(np.var(effects, ddof=1)), float(np.median(variances)), 1e-12)
    tau_squared = scale * np.expm1(log_scale)
    total_variance = variances + tau_squared
    weights = 1 / total_variance
    weighted_mean = float(np.sum(weights * effects) / np.sum(weights))
    residual = effects - weighted_mean
    return float(
        np.log(total_variance).sum()
        + np.log(weights.sum())
        + np.sum(weights * residual**2)
    )


def reml_test(
    frame: pd.DataFrame,
    cohort: str,
    alpha: float = 0.05,
    alternative: str = "less",
) -> dict[str, float | int]:
    """Fit a one-intercept random-effects model by REML for one cohort."""
    if alternative not in {"two-sided", "less"}:
        raise ValueError("alternative must be 'two-sided' or 'less'")
    selected = frame.loc[frame["cohort"] == cohort].copy()
    if selected.empty:
        raise ValueError(f"no paired users found for {cohort}")
    effects = selected["difference_min"].to_numpy(dtype=float)
    variances = selected["sampling_variance_min2"].to_numpy(dtype=float)
    if len(effects) < 2:
        raise ValueError("REML needs at least two paired users")

    objective_at_zero = _reml_objective(0.0, effects, variances)
    optimized = optimize.minimize_scalar(
        _reml_objective,
        args=(effects, variances),
        bounds=(0.0, 20.0),
        method="bounded",
        options={"xatol": 1e-10},
    )
    log_scale = 0.0 if objective_at_zero <= optimized.fun else float(optimized.x)
    scale = max(float(np.var(effects, ddof=1)), float(np.median(variances)), 1e-12)
    tau_squared = float(scale * np.expm1(log_scale))
    total_variance = variances + tau_squared
    weights = 1 / total_variance
    mean_difference = float(np.sum(weights * effects) / np.sum(weights))
    standard_error = float((1 / np.sum(weights)) ** 0.5)
    z_statistic = mean_difference / standard_error
    p_value = (
        float(stats.norm.cdf(z_statistic))
        if alternative == "less"
        else float(2 * stats.norm.sf(abs(z_statistic)))
    )
    critical_probability = 1 - alpha if alternative == "less" else 1 - alpha / 2
    critical_value = float(stats.norm.ppf(critical_probability))
    ci_low = float("-inf") if alternative == "less" else mean_difference - critical_value * standard_error
    ci_high = mean_difference + critical_value * standard_error
    return {
        "n_users": len(effects),
        "mean_difference": mean_difference,
        "standard_error": standard_error,
        "tau_squared": tau_squared,
        "tau": tau_squared**0.5,
        "z_statistic": z_statistic,
        "p_value": p_value,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "sum_weights": float(weights.sum()),
    }


def _format(value: float, digits: int = 4) -> str:
    return f"{value:.{digits}f}"


def _format_p_value(value: float) -> str:
    return "<1e-300" if value == 0 else f"{value:.6g}"


def _summary(frame: pd.DataFrame, cohort: str) -> dict[str, float | int]:
    selected = frame.loc[frame["cohort"] == cohort]
    return {
        "n_users": len(selected),
        "mean_difference": float(selected["difference_min"].mean()),
        "median_same_tasks": float(selected["same_task_count"].median()),
        "median_different_tasks": float(selected["different_task_count"].median()),
        "pooled_variance_fallback_cells": int(
            (selected["same_variance_source"] == "pooled cohort-pattern").sum()
            + (selected["different_variance_source"] == "pooled cohort-pattern").sum()
        ),
    }


def write_report(frame: pd.DataFrame, report_path: Path, query: str) -> Path:
    fallback_cells = int(
        (frame["same_variance_source"] == "pooled cohort-pattern").sum()
        + (frame["different_variance_source"] == "pooled cohort-pattern").sum()
    )
    sections = []
    for cohort in task_analysis.COHORT_ORDER:
        result = reml_test(frame, cohort)
        summary = _summary(frame, cohort)
        significance = "reject" if result["p_value"] < 0.05 else "do not reject"
        sections.append(
            f"""## {cohort}

| Quantity | Result |
|---|---:|
| Paired users | {result["n_users"]:,} |
| Median Same Cohort tasks per user | {_format(summary["median_same_tasks"], 1)} |
| Median Different Cohort tasks per user | {_format(summary["median_different_tasks"], 1)} |
| Mean unweighted difference (minutes) | {_format(summary["mean_difference"])} |
| REML weighted difference (minutes) | {_format(result["mean_difference"])} |
| REML standard error (minutes) | {_format(result["standard_error"])} |
| Between-user variance, tau² (minutes²) | {_format(result["tau_squared"])} |
| Between-user SD, tau (minutes) | {_format(result["tau"])} |
| REML z-statistic | {_format(result["z_statistic"])} |
| 95% one-sided upper bound (minutes) | (-∞, {_format(result["ci_high"])}] |
| One-sided p-value | {_format_p_value(result["p_value"])} |
| Cells using pooled variance fallback | {summary["pooled_variance_fallback_cells"]} |

At the 0.05 level, we **{significance}** the null hypothesis for {cohort}.
"""
        )
    report = f"""# Estimating Differences Using REML

## Question and estimand

This analysis estimates the difference in DUR work time between Same Cohort and
Different Cohort for users with observations in both allocation patterns. The
effect for user *i* is `d_i = mean_same_i - mean_different_i`.

The directional hypothesis is **Same Cohort − Different Cohort < 0**. A negative
effect means that Same Cohort tasks are faster for that user on average.

## Why REML is used

Users contribute different numbers of tasks, so their user means have different
precision. For each user, the sampling variance of the paired difference is
estimated as `v_i = s_same_i^2 / n_same_i + s_different_i^2 / n_different_i`.

The random-effects model is `d_i = mu + u_i + e_i`, where
`u_i ~ N(0, tau^2)` captures between-user heterogeneity and
`e_i ~ N(0, v_i)` captures sampling error.

REML estimates `tau^2`, the residual between-user variance after accounting
for each user's sampling variance. The random-effects weight is
`1 / (v_i + tau^2)`, so users with more precise means receive more weight,
while genuine user-to-user heterogeneity prevents any single precise user from
dominating.

The reported p-value is a lower-tail normal/Wald test of `H0: mu >= 0`
against `H1: mu < 0`. The interval is the corresponding one-sided 95%
upper bound. This is an asymptotic random-effects inference; uncertainty in the
estimated `tau` is not separately included in the Wald standard error.

## Handling users with one task in an allocation pattern

The task-level extract contains {len(frame):,} paired users. {fallback_cells}
user-pattern cells contain one task, so a within-user variance cannot be computed for those cells.
For those cells only, the analysis uses the pooled residual variance for the
same cohort and allocation pattern. The actual user task count remains in the
denominator of `v_i`. All other cells use the user's own sample variance.

This fallback retains the paired users while making the sparse-cell assumption
explicit. The pooled variance fallback counts are reported by cohort below.

{chr(10).join(sections)}

## Interpretation and limitations

The REML weighted difference estimates the average difference for the paired-user
population under precision weighting. It is not identical to the unweighted
average difference from the paired t-test, which targets the typical user more
directly. The two estimates are shown together so that changes in estimand are
visible.

The source query limits observations to DUR tasks with final status `CLOSED`,
known cohorts, transitions on or after 2026-08-01, and work time between 0.01
and 5 minutes. The analysis is observational. Task durations within a user may
also be correlated beyond the variance formula above; a task-level mixed model
or cluster bootstrap would be a useful sensitivity analysis.

## Query used

```sql
{query}
```
"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    return report_path


def write_data(frame: pd.DataFrame) -> Path:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(DATA_PATH, index=False)
    return DATA_PATH


def read_data() -> pd.DataFrame:
    return pd.read_parquet(DATA_PATH)


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
    help="Build the report from the cached REML input data without querying Snowflake.",
)
def main(env_file: Path, redraw_only: bool) -> None:
    """Run the REML user-difference analysis."""
    try:
        if redraw_only:
            if not DATA_PATH.is_file():
                raise ValueError(f"cached REML data not found: {DATA_PATH}")
            frame = read_data()
        else:
            if task_analysis.DATA_PATH.is_file():
                task_frame = task_analysis.read_data()
            else:
                if not env_file.is_file():
                    raise ValueError(f"environment file not found: {env_file}")
                settings = parse_dotenv(env_file)
                missing = [key for key in REQUIRED_SETTINGS if key not in settings]
                if missing:
                    raise ValueError("missing required settings: " + ", ".join(missing))
                task_frame = task_analysis.fetch_data(settings)
            frame = aggregate_user_effects(task_frame)
            write_data(frame)
        write_report(frame, REPORT_PATH, task_analysis.read_sql())
    except (ImportError, OSError, ValueError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(f"Created REML report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
