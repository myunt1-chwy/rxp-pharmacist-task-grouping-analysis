from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.python import create_task_time_bucket_distribution as distribution


def sample_frame() -> pd.DataFrame:
    rows = []
    for scope_order, scope_name in ((0, "All warehouses"), (1, "AVP4")):
        for cohort_index, cohort in enumerate(("Cohort 1", "Cohort 2"), 1):
            for bucket_start_hour in (0, 4, 8, 12, 16, 20):
                rows.append(
                    {
                        "scope_order": scope_order,
                        "scope_name": scope_name,
                        "coh": cohort,
                        "bucket_start_hour": bucket_start_hour,
                        "unique_task_count": cohort_index * 100 + bucket_start_hour,
                        "unique_user_count": cohort_index * 10,
                        "average_duration_seconds": 40.5 + bucket_start_hour,
                        "median_duration_seconds": 20.0 + bucket_start_hour,
                        "stddev_duration_seconds": 12.5 + bucket_start_hour,
                    }
                )
    return pd.DataFrame(rows)


def test_query_contains_required_filters_buckets_and_metrics() -> None:
    sql = distribution.AGGREGATE_SQL

    assert "TASK_TYPE = 'DUR'" in sql
    assert "COH <> 'Unknown'" in sql
    assert "LOWER(IS_REFILL) = 'false'" in sql
    assert "HANDOFF_TYPE IS NULL" in sql
    assert "IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS AS DURATION_SECONDS" in sql
    assert "DWELL_IN_PROGRESS_TO_CLOSED_SECONDS AS DURATION_SECONDS" not in sql.replace(
        "IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS AS DURATION_SECONDS", ""
    )
    assert "DATE_PART('HOUR', PROCESS_START_TIME)" in sql
    assert "PROCESS_START_TIME IS NOT NULL" in sql
    assert "DATE_PART('HOUR', CONVERT_TIMEZONE('UTC', STARTED_AT))" not in sql
    assert ") * 4 AS BUCKET_START_HOUR" in sql
    assert "COUNT(DISTINCT TASK_ID)" in sql
    assert "COUNT(DISTINCT USER_ID)" in sql
    assert "AVG(DURATION_SECONDS)" in sql
    assert "MEDIAN(DURATION_SECONDS)" in sql
    assert "STDDEV_SAMP(DURATION_SECONDS)" in sql
    assert "DAY_TASK_COUNT" not in sql
    assert "NIGHT_TASK_COUNT" not in sql
    assert "CROSS JOIN cohorts" in sql
    assert "CROSS JOIN bucket_hours" in sql
    assert "LEFT JOIN aggregates" in sql


def test_chart_labels_describe_process_start_time() -> None:
    specification = distribution.create_chart(sample_frame(), "All warehouses").to_dict()
    first_layer = specification["layer"][0]

    assert first_layer["encoding"]["x"]["title"] == "Process start time (UTC)"
    assert "process-start bucket" in first_layer["title"]["text"]


def test_write_generated_sql(monkeypatch, tmp_path: Path) -> None:
    output = tmp_path / "generated" / "create_task_time_bucket_distribution.sql"
    monkeypatch.setattr(distribution, "GENERATED_SQL_PATH", output)

    result = distribution.write_generated_sql()

    assert result == output
    assert output.read_text(encoding="utf-8") == distribution.AGGREGATE_SQL + "\n"


def test_create_outputs_write_overall_and_warehouse_pngs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(distribution, "OUTPUT_DIRECTORY", tmp_path)
    legacy_output = tmp_path / "task-time-bucket-distribution.png"
    legacy_output.write_bytes(b"old")

    outputs = distribution.create_outputs(sample_frame())

    pngs = [path for path in outputs if path.suffix == ".png"]
    assert [path.name for path in pngs] == [
        "task-time-bucket-distribution-overall.png",
        "task-time-bucket-distribution-avp4.png",
    ]
    assert all(path.is_file() and path.stat().st_size > 0 for path in pngs)
    assert not legacy_output.exists()
    markdown = tmp_path / "README.md"
    contents = markdown.read_text(encoding="utf-8")
    assert contents.count("![") == 2
    assert all(path.name in contents for path in pngs)
