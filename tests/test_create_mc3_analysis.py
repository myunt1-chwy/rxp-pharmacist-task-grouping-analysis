from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.python import create_mc3_analysis as analysis


def sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "coh": [
                "Cohort 1",
                "Cohort 1",
                "Cohort 2",
                "Cohort 2",
                "Cohort 3",
                "Cohort 3",
                "Cohort 4",
                "Cohort 4",
            ],
            "mc3": ["10", "2", "10", "2", "10", "2", "10", "2"],
            "part_number": ["A", "B", "A", "C", "A", "D", "E", "F"],
            "duration_seconds": [10, 20, 30, 40, 50, 60, 70, 80],
        }
    )


def test_query_contains_filters_join_and_missing_mc3_handling() -> None:
    sql = analysis.MC3_SQL

    assert "TASK_TYPE = 'DUR'" in sql
    assert "COH IN ('Cohort 1', 'Cohort 2', 'Cohort 3', 'Cohort 4')" in sql
    assert "LOWER(IS_REFILL) = 'false'" in sql
    assert "HANDOFF_TYPE IS NULL" in sql
    assert "APPROX_PERCENTILE(DURATION_SECONDS, 0.95)" in sql
    assert "IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS AS DURATION_SECONDS" in sql
    assert "filtered.PART_NUMBER" in sql
    assert "LEFT JOIN EDLDB.PDM.PRODUCT" in sql
    assert "product.PART_NUMBER = filtered.PART_NUMBER" in sql
    assert "MERCH_CLASSIFICATION3" in sql
    assert "'<Missing>'" in sql


def test_write_generated_sql(monkeypatch, tmp_path: Path) -> None:
    output = tmp_path / "generated" / "create_mc3_analysis.sql"
    monkeypatch.setattr(analysis, "GENERATED_SQL_PATH", output)

    assert analysis.write_generated_sql() == output
    assert output.read_text(encoding="utf-8") == analysis.MC3_SQL + "\n"


def test_boxplot_chart_uses_mc3_categories_and_whole_cohort() -> None:
    specification = analysis.boxplot_chart(sample_frame(), "Cohort 1").to_dict()

    label_specification, boxplot_specification = specification["hconcat"]
    assert len(boxplot_specification["layer"]) == 3
    whiskers, boxes, medians = boxplot_specification["layer"]
    assert whiskers["mark"]["type"] == "rule"
    assert whiskers["encoding"]["x"]["field"] == "p05"
    assert whiskers["encoding"]["x"]["title"] == "DUR duration (seconds)"
    assert whiskers["encoding"]["x2"]["field"] == "p95"
    assert boxes["mark"]["type"] == "bar"
    assert boxes["encoding"]["x"]["field"] == "q1"
    assert boxes["encoding"]["x2"]["field"] == "q3"
    assert boxes["encoding"]["y"]["field"] == "category_label"
    assert medians["mark"]["type"] == "bar"
    assert medians["mark"]["color"] == "#8b0000"
    assert medians["encoding"]["x"]["field"] == "median_lower"
    assert medians["encoding"]["x2"]["field"] == "median_upper"
    assert label_specification["encoding"]["text"]["field"] == "category_label"
    assert label_specification["mark"]["align"] == "left"
    assert label_specification["encoding"]["x"]["value"] == 4


def test_mc3_median_histogram_uses_two_second_bins() -> None:
    chart = analysis.mc3_median_histogram_chart(sample_frame())

    spec = chart.to_dict()
    assert spec["vconcat"][0]["hconcat"][0]["encoding"]["x"]["bin"]["step"] == 2


def test_create_outputs_writes_four_pngs_and_markdown(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(analysis, "OUTPUT_DIRECTORY", tmp_path)

    outputs = analysis.create_outputs(sample_frame())

    pngs = [path for path in outputs if path.suffix == ".png"]
    assert [path.name for path in pngs] == [
        "mc3-analysis-cohort-1.png",
        "mc3-analysis-cohort-2.png",
        "mc3-analysis-cohort-3.png",
        "mc3-analysis-cohort-4.png",
        "mc3-analysis-category-median-histogram.png",
    ]
    assert all(path.is_file() and path.stat().st_size > 0 for path in pngs)
    markdown = tmp_path / "README.md"
    contents = markdown.read_text(encoding="utf-8")
    assert contents.count("![") == 5
    assert all(path.name in contents for path in pngs)
