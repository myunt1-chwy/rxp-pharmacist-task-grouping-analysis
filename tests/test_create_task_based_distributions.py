from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.python import create_task_based_distributions as distributions


def sample_frame() -> pd.DataFrame:
    rows = []
    for dimension, values in (
        ("shift", ("Day", "Night")),
        ("job_title", ("Pharmacist", "Pharmacist in Charge")),
        ("wh_id", ("001", "002")),
        ("day_of_week", distributions.WEEKDAY_ORDER),
    ):
        for cohort_index, cohort in enumerate(("Cohort 1", "Cohort 2"), 1):
            for value_index, value in enumerate(values, 1):
                rows.append(
                    {
                        "dimension_type": dimension,
                        "coh": cohort,
                        "dimension_value": value,
                        "unique_task_count": cohort_index * value_index * 10,
                        "unique_user_count": cohort_index * value_index * 2,
                        "average_duration_seconds": cohort_index * value_index * 5.5,
                        "median_duration_seconds": cohort_index * value_index * 4.25,
                        "stddev_duration_seconds": cohort_index * value_index * 1.25,
                    }
                )
    return pd.DataFrame(rows)


def sample_task_duration_frame() -> pd.DataFrame:
    rows = []
    for cohort_index, cohort in enumerate(
        ("Cohort 1", "Cohort 2", "Cohort 3", "Cohort 4"), 1
    ):
        for title_index, job_title in enumerate(("Pharmacist", "Pharmacist in Charge"), 1):
            for duration_index, duration in enumerate((10, 20, 30, 40), 1):
                rows.append(
                    {
                        "task_id": f"{cohort_index}-{title_index}-{duration_index}",
                        "coh": cohort,
                        "job_title": job_title,
                        "duration_seconds": duration * cohort_index * title_index,
                    }
                )
    return pd.DataFrame(rows)


def test_query_contains_required_filters_and_metrics() -> None:
    sql = distributions.AGGREGATE_SQL

    assert "TASK_TYPE = 'DUR'" in sql
    assert "COH <> 'Unknown'" in sql
    assert "LOWER(IS_REFILL) = 'false'" in sql
    assert "HANDOFF_TYPE IS NULL" in sql
    assert "DAYOFWEEKISO(PROCESS_START_TIME)" in sql
    assert "END AS DAY_OF_WEEK" in sql
    assert "SELECT 'day_of_week'" in sql
    assert "IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS AS DURATION_SECONDS" in sql
    assert "TASK_ID" in distributions.TASK_DURATION_SQL
    assert "COALESCE(JOB_TITLE, '<Missing>') AS JOB_TITLE" in distributions.TASK_DURATION_SQL
    assert "DWELL_IN_PROGRESS_TO_CLOSED_SECONDS AS DURATION_SECONDS" not in sql.replace(
        "IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS AS DURATION_SECONDS", ""
    )
    assert "COUNT(DISTINCT TASK_ID)" in sql
    assert "COUNT(DISTINCT USER_ID)" in sql
    assert "AVG(DURATION_SECONDS)" in sql
    assert "MEDIAN(DURATION_SECONDS)" in sql
    assert "STDDEV_SAMP(DURATION_SECONDS)" in sql


def test_write_generated_sql(monkeypatch, tmp_path: Path) -> None:
    output = tmp_path / "generated" / "create_task_based_distributions.sql"
    monkeypatch.setattr(distributions, "GENERATED_SQL_PATH", output)

    result = distributions.write_generated_sql()

    assert result == output
    assert output.read_text(encoding="utf-8") == distributions.AGGREGATE_SQL + "\n"


def test_weekday_chart_uses_monday_to_sunday_order() -> None:
    weekday_frame = sample_frame().loc[lambda frame: frame["dimension_type"] == "day_of_week"]
    specification = distributions.summary_chart(weekday_frame, "Day of week").to_dict()

    assert specification["layer"][0]["encoding"]["y"]["sort"] == list(
        distributions.WEEKDAY_ORDER
    )
    assert any(
        layer.get("encoding", {}).get("text", {}).get("field") == "user_label"
        for layer in specification["layer"]
    )


def test_duration_boxplot_uses_fifth_and_ninety_fifth_percentile_whiskers() -> None:
    duration_frame = pd.DataFrame(
        {
            "coh": ["Cohort 1"] * 5 + ["Cohort 2"] * 5,
            "duration_seconds": [1, 2, 3, 4, 100, 2, 3, 4, 5, 120],
        }
    )

    specification = distributions.boxplot_chart(duration_frame).to_dict()

    boxplots, table = specification["vconcat"]
    whiskers, boxes, medians = boxplots["layer"]
    assert whiskers["encoding"]["y"]["field"] == "p05"
    assert whiskers["encoding"]["y2"]["field"] == "p95"
    assert boxes["encoding"]["y"]["field"] == "q1"
    assert boxes["encoding"]["y2"]["field"] == "q3"
    assert medians["mark"]["type"] == "tick"
    assert medians["mark"]["orient"] == "horizontal"
    assert medians["mark"]["color"] == "#8b0000"
    assert medians["encoding"]["y"]["field"] == "median"
    table_columns = table["hconcat"]
    assert [column["title"]["text"] for column in table_columns] == [
        "Cohort",
        "DUR count",
        "Median (s)",
        "Maximum (s)",
        "Minimum (s)",
        "Average (s)",
        "Std dev (s)",
    ]
    assert all(column["title"]["anchor"] == "middle" for column in table_columns)
    assert table_columns[1]["encoding"]["text"]["field"] == "task_count_label"
    assert table_columns[5]["encoding"]["text"]["field"] == "average_label"


def test_job_title_boxplot_and_count_strip_use_task_level_data() -> None:
    duration_frame = sample_task_duration_frame()

    boxplot_specification = distributions.job_title_boxplot_chart(
        duration_frame, "Cohort 1"
    ).to_dict()
    boxplot_layout, table = boxplot_specification["vconcat"]
    _, boxplot = boxplot_layout["hconcat"]
    whiskers, boxes, medians = boxplot["layer"]
    assert whiskers["encoding"]["x"]["field"] == "p05"
    assert whiskers["encoding"]["y"]["field"] == "job_title"
    assert boxes["encoding"]["x"]["field"] == "q1"
    assert boxes["mark"]["size"] == 50
    assert whiskers["encoding"]["y"]["scale"]["paddingInner"] == 0.4
    assert medians["mark"]["color"] == "#8b0000"
    assert boxplot["title"]["text"] == (
        "DUR duration by job title — Cohort 1"
    )
    table_columns = table["hconcat"]
    assert [column["title"]["text"] for column in table_columns] == [
        "Job title",
        "DUR count",
        "Median (s)",
        "Maximum (s)",
        "Average (s)",
        "Std dev (s)",
    ]
    assert all(column["title"]["anchor"] == "middle" for column in table_columns)
    assert table_columns[1]["encoding"]["text"]["field"] == "task_count_label"
    assert table_columns[2]["encoding"]["text"]["field"] == "median_label"
    assert table_columns[3]["encoding"]["text"]["field"] == "maximum_label"
    assert table_columns[4]["encoding"]["text"]["field"] == "average_label"
    assert table_columns[5]["encoding"]["text"]["field"] == "stddev_label"

    strip_specification = distributions.job_title_count_strip_chart(
        duration_frame
    ).to_dict()
    assert len(strip_specification["layer"]) == 2
    assert strip_specification["layer"][0]["encoding"]["x"]["field"] == "task_count"
    assert strip_specification["layer"][1]["encoding"]["text"]["field"] == "count_label"


def test_create_outputs_writes_four_pngs_and_markdown(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(distributions, "OUTPUT_DIRECTORY", tmp_path)
    for filename in distributions.LEGACY_OUTPUT_FILENAMES:
        (tmp_path / filename).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / filename).write_bytes(b"old")

    outputs = distributions.create_outputs(sample_frame())

    pngs = [path for path in outputs if path.suffix == ".png"]
    assert [path.name for path in pngs] == [
        "task-summary-by-shift-and-cohort.png",
        "task-summary-by-job_title-and-cohort.png",
        "task-summary-by-wh_id-and-cohort.png",
        "task-summary-by-day_of_week-and-cohort.png",
    ]
    assert all(path.is_file() and path.stat().st_size > 0 for path in pngs)
    assert not any((tmp_path / filename).exists() for filename in distributions.LEGACY_OUTPUT_FILENAMES)
    markdown = tmp_path / "README.md"
    contents = markdown.read_text(encoding="utf-8")
    assert contents.count("![") == 4
    assert all(path.name in contents for path in pngs)


def test_create_outputs_writes_job_title_charts(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(distributions, "OUTPUT_DIRECTORY", tmp_path)

    outputs = distributions.create_outputs(sample_frame(), sample_task_duration_frame())

    pngs = [path for path in outputs if path.suffix == ".png"]
    assert len(pngs) == 12
    assert "task-duration-by-job-title-cohort-1-boxplots.png" in {
        path.name for path in pngs
    }
    assert "task-duration-by-job-title-cohort-4-boxplots.png" in {
        path.name for path in pngs
    }
    assert "task-duration-by-job-title-all-cohorts-boxplots.png" in {
        path.name for path in pngs
    }
    assert "task-dur-count-by-job-title-strip.png" in {path.name for path in pngs}
    assert (tmp_path / "README.md").read_text(encoding="utf-8").count("![") == 12
