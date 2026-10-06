from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.python import santhosh_analysis_user as analysis


def sample_task_frame() -> pd.DataFrame:
    records = []
    task_number = 0
    for cohort_number in range(1, 5):
        for user_number, same_values, different_values in (
            (1, [1.0, 3.0], [5.0, 7.0]),
            (2, [3.0, 5.0], [8.0, 10.0]),
            (3, [2.0], []),
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


def test_aggregate_user_means_retains_only_paired_users() -> None:
    paired = analysis.aggregate_user_means(sample_task_frame())

    assert len(paired) == 8
    assert set(paired.columns) >= {
        "cohort",
        "user_id",
        "same_mean_min",
        "different_mean_min",
        "difference_min",
    }
    cohort_one = paired.loc[paired["cohort"] == "Cohort 1"].sort_values("user_id")
    assert cohort_one["same_mean_min"].tolist() == [2.0, 4.0]
    assert cohort_one["different_mean_min"].tolist() == [6.0, 9.0]
    assert cohort_one["difference_min"].tolist() == [-4.0, -5.0]


def test_paired_test_uses_within_user_differences() -> None:
    result = analysis.paired_test(
        analysis.aggregate_user_means(sample_task_frame()), "Cohort 1"
    )

    assert result["n_users"] == 2
    assert result["mean_difference"] == pytest.approx(-4.5)
    assert result["t_statistic"] == pytest.approx(-9.0)
    assert result["degrees_of_freedom"] == 1
    assert result["p_value"] == pytest.approx(0.07044657495455442)
    assert result["ci_low"] < result["mean_difference"] < result["ci_high"]


def test_paired_test_supports_same_cohort_less_than_different_cohort() -> None:
    frame = analysis.aggregate_user_means(sample_task_frame())
    two_sided = analysis.paired_test(frame, "Cohort 1")
    one_sided = analysis.paired_test(frame, "Cohort 1", alternative="less")

    assert one_sided["p_value"] == pytest.approx(two_sided["p_value"] / 2)
    assert one_sided["ci_low"] == float("-inf")
    assert one_sided["ci_high"] < 0


def test_user_distribution_chart_has_density_transform_and_log_axis() -> None:
    specification = analysis.user_distribution_chart(
        analysis.aggregate_user_means(sample_task_frame()), "Cohort 1"
    ).to_dict()

    assert specification["mark"]["type"] == "line"
    assert specification["transform"][0]["density"] == "work_seconds"
    assert specification["transform"][0]["groupby"] == ["allocation_pattern"]
    assert specification["encoding"]["x"]["field"] == "work_seconds"
    assert specification["encoding"]["x"]["scale"] == {"base": 10, "type": "log"}
    assert specification["encoding"]["y"]["field"] == "density"


def test_write_report_contains_paired_results_and_chart(tmp_path: Path) -> None:
    report_path = tmp_path / "santosh_analysis_user.md"
    chart_paths = {
        f"Cohort {number}": f"cohort-{number}.png" for number in range(1, 5)
    }

    result = analysis.write_report(
        analysis.aggregate_user_means(sample_task_frame()),
        report_path,
        "SELECT task_id, user_id, cohort, allocation_pattern, work_min FROM source",
        chart_paths,
    )

    contents = result.read_text(encoding="utf-8")
    assert "# Santhosh User-Level Analysis" in contents
    assert "paired t-test" in contents
    assert "within-user difference" in contents
    assert "## Cohort 4" in contents
    assert "SELECT task_id, user_id, cohort, allocation_pattern, work_min FROM source" in contents


def test_write_report_can_emit_one_sided_results(tmp_path: Path) -> None:
    report_path = tmp_path / "santosh_analysis_user_one_sided.md"
    chart_paths = {
        f"Cohort {number}": f"cohort-{number}.png" for number in range(1, 5)
    }

    analysis.write_report(
        analysis.aggregate_user_means(sample_task_frame()),
        report_path,
        "SELECT 1",
        chart_paths,
        alternative="less",
    )

    contents = report_path.read_text(encoding="utf-8")
    assert "one-sided paired t-test" in contents
    assert "One-sided p-value" in contents
    assert "95% one-sided upper bound" in contents


def test_create_outputs_writes_four_user_charts_and_report(
    monkeypatch, tmp_path: Path
) -> None:
    chart_directory = tmp_path / "charts"
    report_path = tmp_path / "reports" / "santosh_analysis_user.md"
    monkeypatch.setattr(analysis, "OUTPUT_DIRECTORY", chart_directory)
    monkeypatch.setattr(analysis, "REPORT_PATH", report_path)

    outputs = analysis.create_outputs(
        analysis.aggregate_user_means(sample_task_frame())
    )

    assert outputs == [
        chart_directory / "santosh-analysis-user-cohort-1.png",
        chart_directory / "santosh-analysis-user-cohort-2.png",
        chart_directory / "santosh-analysis-user-cohort-3.png",
        chart_directory / "santosh-analysis-user-cohort-4.png",
        report_path,
    ]
    assert all(path.is_file() and path.stat().st_size > 0 for path in outputs)
