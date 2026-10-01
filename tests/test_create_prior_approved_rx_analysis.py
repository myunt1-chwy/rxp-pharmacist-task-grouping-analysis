from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.python import create_prior_approved_rx_analysis as analysis


def sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "task_id": range(1, 9),
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
            "n_prior_approved_rx_ids": [0, 1, 1, 2, 0, 2, 1, 2],
            "duration_seconds": [10, 20, 30, 40, 50, 60, 70, 80],
        }
    )


def test_query_uses_valid_dur_source_and_global_percentile_filter() -> None:
    sql = analysis.PRIOR_APPROVED_RX_SQL

    assert f"FROM {analysis.SOURCE_TABLE}" in sql
    assert "TASK_ID" in sql
    assert "COH IN ('Cohort 1', 'Cohort 2', 'Cohort 3', 'Cohort 4')" in sql
    assert "COALESCE(N_PRIOR_APPROVED_RX_IDS, 0) AS N_PRIOR_APPROVED_RX_IDS" in sql
    assert "IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS AS DURATION_SECONDS" in sql
    assert "APPROX_PERCENTILE(DURATION_SECONDS, 0.95)" in sql
    assert "base.DURATION_SECONDS < percentile_bounds.P95_SECONDS" in sql


def test_write_generated_sql(monkeypatch, tmp_path: Path) -> None:
    output = tmp_path / "generated" / "create_prior_approved_rx_analysis.sql"
    monkeypatch.setattr(analysis, "GENERATED_SQL_PATH", output)

    assert analysis.write_generated_sql() == output
    assert output.read_text(encoding="utf-8") == analysis.PRIOR_APPROVED_RX_SQL + "\n"


def test_normalize_frame_maps_missing_counts_to_zero() -> None:
    frame = sample_frame()
    frame.loc[0, "n_prior_approved_rx_ids"] = None

    normalized = analysis.normalize_frame(frame)

    assert normalized["n_prior_approved_rx_ids"].tolist() == [
        "0",
        "1",
        "1",
        "2",
        "0",
        "2",
        "1",
        "2",
    ]


def test_boxplot_chart_contains_three_layers_and_whole_cohort() -> None:
    specification = analysis.boxplot_chart(sample_frame(), "Cohort 1").to_dict()

    label_specification, boxplot_specification = specification["hconcat"]
    assert len(boxplot_specification["layer"]) == 3
    whiskers, boxes, medians = boxplot_specification["layer"]
    assert whiskers["mark"]["type"] == "rule"
    assert whiskers["encoding"]["x"]["field"] == "p05"
    assert whiskers["encoding"]["x2"]["field"] == "p95"
    assert boxes["encoding"]["x"]["field"] == "q1"
    assert boxes["encoding"]["x2"]["field"] == "q3"
    assert medians["mark"]["color"] == "#8b0000"
    assert label_specification["encoding"]["text"]["field"] == "category_label"
    assert boxplot_specification["title"]["text"] == (
        "DUR duration boxplots by number of prior approved rx ids — Cohort 1"
    )

    summary_values = next(iter(specification["datasets"].values()))
    categories = {value["plot_category"] for value in summary_values}
    assert categories == {"0", "1", "Whole cohort"}


def test_create_outputs_writes_four_pngs_and_readme(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(analysis, "OUTPUT_DIRECTORY", tmp_path)

    outputs = analysis.create_outputs(sample_frame())

    pngs = [path for path in outputs if path.suffix == ".png"]
    assert [path.name for path in pngs] == [
        "prior-approved-rx-analysis-cohort-1.png",
        "prior-approved-rx-analysis-cohort-2.png",
        "prior-approved-rx-analysis-cohort-3.png",
        "prior-approved-rx-analysis-cohort-4.png",
    ]
    assert all(path.is_file() and path.stat().st_size > 0 for path in pngs)
    readme = tmp_path / "README.md"
    contents = readme.read_text(encoding="utf-8")
    assert contents.count("![") == 4
    assert "Whole cohort" in contents
    assert all(path.name in contents for path in pngs)
