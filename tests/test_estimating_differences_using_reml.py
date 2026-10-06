from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.python import estimating_differences_using_reml as analysis


def sample_task_frame() -> pd.DataFrame:
    records = []
    task_number = 0
    for cohort_number in range(1, 5):
        for user_number, same_values, different_values in (
            (1, [1.0, 3.0], [5.0, 7.0]),
            (2, [2.0, 4.0, 6.0], [7.0, 9.0, 11.0]),
        ):
            for pattern, values in (
                ("Same Cohort", same_values),
                ("Different Cohort", different_values),
            ):
                for value in values:
                    task_number += 1
                    records.append(
                        {
                            "task_id": f"task-{task_number}",
                            "user_id": f"user-{cohort_number}-{user_number}",
                            "dt": pd.Timestamp("2026-08-01"),
                            "cohort": f"Cohort {cohort_number}",
                            "allocation_pattern": pattern,
                            "work_min": value,
                        }
                    )
    return pd.DataFrame(records)


def test_aggregate_user_effects_calculates_sampling_variance() -> None:
    effects = analysis.aggregate_user_effects(sample_task_frame())
    user = effects.loc[effects["user_id"] == "user-1-1"].iloc[0]

    assert len(effects) == 8
    assert user["same_task_count"] == 2
    assert user["different_task_count"] == 2
    assert user["difference_min"] == pytest.approx(-4.0)
    assert user["sampling_variance_min2"] == pytest.approx(2.0)


def test_reml_test_estimates_between_user_variance_and_lower_tail_result() -> None:
    frame = pd.DataFrame(
        {
            "cohort": ["Cohort 1"] * 4,
            "difference_min": [-1.0, -2.0, -3.0, -4.0],
            "sampling_variance_min2": [0.01] * 4,
        }
    )

    result = analysis.reml_test(frame, "Cohort 1")

    assert result["tau_squared"] > 0
    assert result["tau"] == pytest.approx(result["tau_squared"] ** 0.5)
    assert result["mean_difference"] == pytest.approx(-2.5, abs=0.01)
    assert result["p_value"] < 0.05
    assert result["ci_high"] < 0


def test_one_task_cell_uses_pooled_variance_fallback() -> None:
    frame = sample_task_frame()
    frame = frame.loc[
        ~(
            (frame["user_id"] == "user-1-1")
            & (frame["allocation_pattern"] == "Same Cohort")
        )
    ].copy()
    frame.loc[len(frame)] = {
        "task_id": "single-task",
        "user_id": "user-1-1",
        "dt": pd.Timestamp("2026-08-01"),
        "cohort": "Cohort 1",
        "allocation_pattern": "Same Cohort",
        "work_min": 2.0,
    }

    effects = analysis.aggregate_user_effects(frame)
    user = effects.loc[effects["user_id"] == "user-1-1"].iloc[0]

    assert user["same_task_count"] == 1
    assert user["same_variance_source"] == "pooled cohort-pattern"
    assert user["sampling_variance_min2"] > 0


def test_write_report_contains_reml_method_and_results(tmp_path: Path) -> None:
    report_path = tmp_path / "estimating_differences_using_REML.md"
    analysis.write_report(
        analysis.aggregate_user_effects(sample_task_frame()),
        report_path,
        "SELECT 1",
    )

    contents = report_path.read_text(encoding="utf-8")
    assert "# Estimating Differences Using REML" in contents
    assert "Between-user SD, tau" in contents
    assert "One-sided p-value" in contents
    assert "## Cohort 4" in contents
    assert "SELECT 1" in contents
