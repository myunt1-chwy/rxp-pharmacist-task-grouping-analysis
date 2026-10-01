from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.python import create_purchase_brand_analysis as analysis


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
            "purchase_brand": ["Brand A", "Brand B", "Brand A", "Brand B", "Brand A", "Brand B", "Brand A", "Brand B"],
            "part_number": ["A", "B", "A", "C", "A", "D", "E", "F"],
            "duration_seconds": [10, 20, 30, 40, 50, 60, 70, 80],
        }
    )


def test_query_contains_required_filters_and_purchase_brand_join() -> None:
    sql = analysis.PURCHASE_BRAND_SQL

    assert "TASK_TYPE = 'DUR'" in sql
    assert "COH IN ('Cohort 1', 'Cohort 2', 'Cohort 3', 'Cohort 4')" in sql
    assert "LOWER(IS_REFILL) = 'false'" in sql
    assert "HANDOFF_TYPE IS NULL" in sql
    assert "APPROX_PERCENTILE(DURATION_SECONDS, 0.95)" in sql
    assert "IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS AS DURATION_SECONDS" in sql
    assert "LEFT JOIN EDLDB.PDM.PRODUCT" in sql
    assert "product.PART_NUMBER = filtered.PART_NUMBER" in sql
    assert "PURCHASE_BRAND" in sql
    assert "'<Missing>'" in sql


def test_write_generated_sql(monkeypatch, tmp_path: Path) -> None:
    output = tmp_path / "generated" / "create_purchase_brand_analysis.sql"
    monkeypatch.setattr(analysis, "GENERATED_SQL_PATH", output)

    assert analysis.write_generated_sql() == output
    assert output.read_text(encoding="utf-8") == analysis.PURCHASE_BRAND_SQL + "\n"


def test_create_outputs_writes_four_pngs_and_markdown(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(analysis, "OUTPUT_DIRECTORY", tmp_path)
    table_path = tmp_path / "tables" / "top-10.md"
    monkeypatch.setattr(analysis, "TABLE_PATH", table_path)

    outputs = analysis.create_outputs(sample_frame())

    pngs = [path for path in outputs if path.suffix == ".png"]
    assert [path.name for path in pngs] == [
        "purchase-brand-analysis-cohort-1.png",
        "purchase-brand-analysis-cohort-2.png",
        "purchase-brand-analysis-cohort-3.png",
        "purchase-brand-analysis-cohort-4.png",
        "purchase-brand-analysis-top-10-table.png",
        "purchase-brand-analysis-brand-median-histogram.png",
    ]
    assert all(path.is_file() and path.stat().st_size > 0 for path in pngs)
    contents = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert contents.count("![") == 6
    assert all(path.name in contents for path in pngs)
    table_contents = table_path.read_text(encoding="utf-8")
    assert "Number of Part Numbers" in table_contents
    assert "Median DUR Duration (seconds)" in table_contents
    assert table_contents.count("Cohort") >= 5


def test_brand_median_histogram_uses_two_second_bins() -> None:
    chart = analysis.brand_median_histogram_chart(sample_frame())

    spec = chart.to_dict()
    assert spec["vconcat"][0]["hconcat"][0]["encoding"]["x"]["bin"]["step"] == 2


def test_top_brands_table_keeps_ten_brands_per_cohort(monkeypatch, tmp_path: Path) -> None:
    frame = pd.concat(
        [
            sample_frame(),
            pd.DataFrame(
                {
                    "coh": ["Cohort 1"] * 10,
                    "purchase_brand": [f"Brand {index}" for index in range(10)],
                    "part_number": [f"PN {index}" for index in range(10)],
                    "duration_seconds": list(range(100, 110)),
                }
            ),
        ],
        ignore_index=True,
    )
    output = tmp_path / "top-10.md"
    monkeypatch.setattr(analysis, "TABLE_PATH", output)

    analysis.write_top_brands_table(frame)

    table_rows = [
        line
        for line in output.read_text(encoding="utf-8").splitlines()
        if line.startswith("| Cohort 1")
    ]
    assert len(table_rows) == 10
