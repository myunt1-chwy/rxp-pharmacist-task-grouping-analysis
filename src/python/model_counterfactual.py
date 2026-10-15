"""Aggregate a same-preceding duration counterfactual for log-duration models."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CounterfactualTotals:
    by_user_day_cohort: pd.DataFrame
    by_user_day: pd.DataFrame
    by_cohort: pd.DataFrame
    original_seconds: float
    adjusted_seconds: float
    adjusted_tasks: int
    first_tasks: int
    duration_ratio: float | None


def same_preceding_totals(
    frame: pd.DataFrame,
    *,
    log_coefficient: float | None = None,
    adjusted_duration_seconds: np.ndarray | None = None,
) -> CounterfactualTotals:
    """Apply model-implied durations except to each user-day-cohort's first task.

    Process start time orders all retained tasks, regardless of same_preceding,
    within each user, process date, and cohort. Task ID resolves an exact
    timestamp tie. Log models may pass their coefficient; other outcome scales
    may pass back-transformed seconds.
    """
    columns = (
        "user_id", "task_id", "d", "coh", "process_start_time",
        "duration_seconds", "same_preceding",
    )
    missing = set(columns).difference(frame.columns)
    if missing:
        raise ValueError("counterfactual data is missing columns: " + ", ".join(sorted(missing)))
    if frame.empty:
        raise ValueError("counterfactual data is empty")
    if (log_coefficient is None) == (adjusted_duration_seconds is None):
        raise ValueError("provide exactly one model-implied duration adjustment")
    if log_coefficient is not None and not np.isfinite(log_coefficient):
        raise ValueError("log coefficient must be finite")

    tasks = frame.loc[:, columns].copy().reset_index(drop=True)
    if tasks.isna().any().any():
        raise ValueError("counterfactual data contains missing values")
    tasks["process_start_time"] = pd.to_datetime(tasks["process_start_time"], errors="coerce")
    if tasks["process_start_time"].isna().any():
        raise ValueError("process start time contains invalid values")
    tasks["d"] = pd.to_datetime(tasks["d"], errors="coerce").dt.date
    if tasks["d"].isna().any():
        raise ValueError("process date contains invalid values")
    if not (tasks["d"] == tasks["process_start_time"].dt.date).all():
        raise ValueError("process date does not match process start time")
    duration = pd.to_numeric(tasks["duration_seconds"], errors="coerce")
    if not np.isfinite(duration).all() or (duration <= 0).any():
        raise ValueError("duration must be finite and positive")
    if not tasks["same_preceding"].isin((0, 1)).all():
        raise ValueError("same_preceding must be zero or one")

    first_indices = (
        tasks.sort_values(
            ["user_id", "d", "coh", "process_start_time", "task_id"], kind="stable"
        )
        .drop_duplicates(["user_id", "d", "coh"])
        .index
    )
    first = tasks.index.isin(first_indices)
    adjusted = (tasks["same_preceding"].to_numpy() == 0) & ~first
    tasks["original_seconds"] = duration.to_numpy(dtype=float)
    ratio = float(np.exp(log_coefficient)) if log_coefficient is not None else None
    if ratio is not None:
        potential_seconds = tasks["original_seconds"].to_numpy() * ratio
    else:
        potential_seconds = np.asarray(adjusted_duration_seconds, dtype=float)
        if (
            potential_seconds.shape != (len(tasks),)
            or not np.isfinite(potential_seconds).all()
            or (potential_seconds <= 0).any()
        ):
            raise ValueError("model-implied durations must be finite, positive, and task-aligned")
    tasks["adjusted_seconds"] = np.where(
        adjusted, potential_seconds, tasks["original_seconds"]
    )
    tasks["adjusted_tasks"] = adjusted.astype(int)
    measures = {
        "tasks": ("task_id", "size"),
        "adjusted_tasks": ("adjusted_tasks", "sum"),
        "original_seconds": ("original_seconds", "sum"),
        "adjusted_seconds": ("adjusted_seconds", "sum"),
    }
    by_user_day_cohort = (
        tasks.groupby(["user_id", "d", "coh"], sort=True)
        .agg(**measures).reset_index()
    )
    by_user_day = (
        by_user_day_cohort.groupby(["user_id", "d"], sort=True)
        [["tasks", "adjusted_tasks", "original_seconds", "adjusted_seconds"]]
        .sum().reset_index()
    )
    by_cohort = (
        by_user_day_cohort.groupby("coh", sort=True)
        [["tasks", "adjusted_tasks", "original_seconds", "adjusted_seconds"]]
        .sum().reset_index()
    )
    return CounterfactualTotals(
        by_user_day_cohort=by_user_day_cohort,
        by_user_day=by_user_day,
        by_cohort=by_cohort,
        original_seconds=float(by_user_day["original_seconds"].sum()),
        adjusted_seconds=float(by_user_day["adjusted_seconds"].sum()),
        adjusted_tasks=int(adjusted.sum()),
        first_tasks=len(first_indices),
        duration_ratio=ratio,
    )
