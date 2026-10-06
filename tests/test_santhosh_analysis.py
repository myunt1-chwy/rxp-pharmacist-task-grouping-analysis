from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.python import santhosh_analysis as analysis


def sample_frame() -> pd.DataFrame:
    records = []
    task_number = 0
    for cohort_number in range(1, 5):
        for pattern, values in (
            ("Same Cohort", [1.0, 2.0, 3.0]),
            ("Different Cohort", [4.0, 5.0, 7.0]),
        ):
            for value in values:
                task_number += 1
                records.append(
                    {
                        "task_id": f"task-{task_number}",
                        "user_id": f"user-{task_number}",
                        "dt": pd.Timestamp("2026-08-01"),
                        "cohort": f"Cohort {cohort_number}",
                        "allocation_pattern": pattern,
                        "work_min": value,
                    }
                )
    return pd.DataFrame(records)


def test_welch_test_reports_same_minus_different_with_independent_expected_values() -> None:
    result = analysis.welch_test(sample_frame(), cohort="Cohort 1")

    assert result["same_n"] == 3
    assert result["different_n"] == 3
    assert result["mean_difference"] == pytest.approx(-3.3333333333)
    assert result["t_statistic"] == pytest.approx(-3.1622776602)
    assert result["degrees_of_freedom"] == pytest.approx(3.4482758621)
    assert result["p_value"] == pytest.approx(0.0419145175)
    assert result["ci_low"] < result["mean_difference"] < result["ci_high"]


def test_welch_test_rejects_missing_allocation_group() -> None:
    frame = sample_frame().loc[
        lambda value: value["allocation_pattern"] == "Same Cohort"
    ]

    with pytest.raises(ValueError, match="both allocation groups"):
        analysis.welch_test(frame)


def test_analysis_sql_preserves_source_filters_and_returns_task_level_rows() -> None:
    sql = analysis.read_sql()

    assert "FCT__TASKS_LIFECYCLE" in sql
    assert "TRANSITION_STARTED_AT >= '2026-08-01'" in sql
    assert "TASK_TYPE = 'DUR'" in sql
    assert "FINAL_STATUS = 'CLOSED'" in sql
    assert "DWELL_IN_PROGRESS_TO_CLOSED_MINUTES BETWEEN 0.01 AND 30" in sql
    assert "LAG(ITEM_COHORT)" in sql
    assert "TASK_ID AS task_id" in sql
    assert "work_min" in sql
    assert "COUNT(*)" not in sql
    assert "ITEM_COHORT AS cohort" in sql


def test_distribution_chart_uses_two_second_bins_and_allocation_pattern() -> None:
    specification = analysis.distribution_chart(sample_frame(), "Cohort 1").to_dict()

    assert specification["title"]["text"] == (
        "DUR work-time distribution by allocation pattern — Cohort 1"
    )
    assert specification["encoding"]["x"]["field"] == "work_seconds"
    assert specification["encoding"]["x"]["bin"]["step"] == 2
    assert specification["encoding"]["x"]["title"] == "Work time (seconds)"
    assert specification["encoding"]["color"]["field"] == "allocation_pattern"


def test_write_report_contains_results_query_and_chart(tmp_path: Path) -> None:
    report_path = tmp_path / "santosh_analysis.md"
    query = "SELECT allocation_pattern, work_min FROM source"

    result = analysis.write_report(
        sample_frame(),
        report_path,
        query,
        chart_paths={
            f"Cohort {number}": (
                f"../charts/santhosh-analysis/santosh-analysis-cohort-{number}.png"
            )
            for number in range(1, 5)
        },
    )

    contents = result.read_text(encoding="utf-8")
    assert "# Santhosh Query Analysis" in contents
    assert "Welch two-sample t-test" in contents
    assert "Same Cohort − Different Cohort" in contents
    assert "## Cohort 1" in contents
    assert "SELECT allocation_pattern, work_min FROM source" in contents
    assert "![Work-time distribution — Cohort 1]" in contents


def test_create_outputs_writes_chart_and_report(monkeypatch, tmp_path: Path) -> None:
    chart_directory = tmp_path / "charts"
    report_path = tmp_path / "reports" / "santosh_analysis.md"
    monkeypatch.setattr(analysis, "OUTPUT_DIRECTORY", chart_directory)
    monkeypatch.setattr(analysis, "REPORT_PATH", report_path)

    outputs = analysis.create_outputs(sample_frame())

    assert outputs == [
        chart_directory / "santosh-analysis-cohort-1.png",
        chart_directory / "santosh-analysis-cohort-2.png",
        chart_directory / "santosh-analysis-cohort-3.png",
        chart_directory / "santosh-analysis-cohort-4.png",
        report_path,
    ]
    assert all(path.is_file() and path.stat().st_size > 0 for path in outputs)
