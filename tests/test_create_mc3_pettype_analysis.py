from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.python import create_mc3_pettype_analysis as analysis


def sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "mc3": ["10", "10", "2", "2", "10", "2"],
            "pettype": [
                "Dog",
                "Cat",
                "Dog",
                "Cat",
                analysis.OVERALL_PETTYPE,
                analysis.OVERALL_PETTYPE,
            ],
            "task_count": [100, 20, 40, 10, 120, 50],
            "median_duration_seconds": [12.0, 20.0, 18.0, 24.0, 13.0, 19.0],
        }
    )


def cohort_sample_frame() -> pd.DataFrame:
    frames = [sample_frame().assign(cohort=analysis.ALL_COHORT)]
    for cohort in analysis.COHORTS:
        cohort_frame = sample_frame().copy()
        cohort_frame["cohort"] = cohort
        frames.append(cohort_frame)
    return pd.concat(frames, ignore_index=True)


def test_query_aggregates_mc3_pettype_and_overall_column() -> None:
    sql = analysis.MC3_PETTYPE_SQL

    assert f"FROM {analysis.SOURCE_TABLE}" in sql
    assert "COH IN ('Cohort 1', 'Cohort 2', 'Cohort 3', 'Cohort 4')" in sql
    assert "COH AS COHORT" in sql
    assert "COALESCE(NULLIF(TRIM(MC3::VARCHAR), ''), '<Missing>') AS MC3" in sql
    assert "COALESCE(NULLIF(TRIM(PETTYPE::VARCHAR), ''), '<Missing>') AS PETTYPE" in sql
    assert "APPROX_PERCENTILE(DURATION_SECONDS, 0.95)" in sql
    assert "base.DURATION_SECONDS < percentile_bounds.P95_SECONDS" in sql
    assert "COUNT(*) AS TASK_COUNT" in sql
    assert "MEDIAN(DURATION_SECONDS) AS MEDIAN_DURATION_SECONDS" in sql
    assert "'All PETTYPEs' AS PETTYPE" in sql
    assert "'All cohorts' AS COHORT" in sql
    assert "GROUP BY COHORT, MC3, PETTYPE" in sql
    assert "UNION ALL" in sql


def test_write_generated_sql(monkeypatch, tmp_path: Path) -> None:
    output = tmp_path / "generated" / "create_mc3_pettype_analysis.sql"
    monkeypatch.setattr(analysis, "GENERATED_SQL_PATH", output)

    assert analysis.write_generated_sql() == output
    assert output.read_text(encoding="utf-8") == analysis.MC3_PETTYPE_SQL + "\n"


def test_heatmap_contains_counts_medians_and_overall_column() -> None:
    chart_frame, mc3_order, pettype_order = analysis.prepare_chart_frame(sample_frame())

    assert mc3_order == ["2", "10"]
    assert pettype_order == ["All PETTYPEs", "Dog", "Cat"]
    assert set(chart_frame["cell_label"]) >= {
        "n=100\nmedian=12.0s",
        "n=120\nmedian=13.0s",
    }
    assert chart_frame.loc[
        (chart_frame["mc3"] == "2") & (chart_frame["pettype"] == "Dog"),
        "count_label",
    ].tolist() == ["n=40"]
    assert chart_frame.loc[
        (chart_frame["mc3"] == "2") & (chart_frame["pettype"] == "Dog"),
        "median_label",
    ].tolist() == ["median=18.0s"]

    sparse_frame = sample_frame().loc[
        ~((sample_frame()["mc3"] == "10") & (sample_frame()["pettype"] == "Cat"))
    ]
    sparse_chart_frame, _, _ = analysis.prepare_chart_frame(sparse_frame)
    missing_cell = sparse_chart_frame.loc[
        (sparse_chart_frame["mc3"] == "10")
        & (sparse_chart_frame["pettype"] == "Cat"),
        "cell_label",
    ]
    assert missing_cell.tolist() == [""]

    specification = analysis.heatmap_chart(sample_frame()).to_dict()
    assert len(specification["layer"]) == 4
    rectangles, count_labels, median_labels, top_pettype_axis = specification["layer"]
    assert rectangles["mark"]["type"] == "rect"
    assert rectangles["mark"]["strokeWidth"] == 0.5
    assert rectangles["encoding"]["stroke"]["condition"]["test"] == "datum.task_count > 0"
    assert rectangles["encoding"]["stroke"]["condition"]["value"] == "black"
    assert rectangles["encoding"]["stroke"]["value"] == "transparent"
    color_encoding = rectangles["encoding"]["color"]
    assert color_encoding["condition"]["test"] == "datum.task_count >= 10"
    assert color_encoding["condition"]["field"] == "median_duration_seconds"
    assert color_encoding["condition"]["scale"]["range"] == analysis.DURATION_COLOR_RANGE
    assert color_encoding["condition"]["scale"]["type"] == "log"
    assert color_encoding["condition"]["scale"]["base"] == 10
    assert color_encoding["condition"]["scale"]["interpolate"] == "lab"
    assert color_encoding["value"] == "white"
    assert rectangles["encoding"]["x"]["axis"]["labelFontSize"] == 22
    assert rectangles["encoding"]["x"]["axis"]["titleFontSize"] == 22
    assert rectangles["encoding"]["y"]["axis"]["labelFontSize"] == 22
    assert rectangles["encoding"]["y"]["axis"]["titleFontSize"] == 22
    assert rectangles["encoding"]["y"]["axis"]["labelLimit"] == 500
    assert count_labels["mark"]["type"] == "text"
    assert count_labels["mark"]["fontSize"] == 22
    assert count_labels["mark"]["dy"] == -14
    assert count_labels["encoding"]["text"]["field"] == "count_label"
    assert count_labels["encoding"]["x"]["axis"] is None
    assert count_labels["encoding"]["color"]["condition"]["test"] == (
        "datum.task_count < 10 || datum.median_duration_seconds <= 30"
    )
    assert count_labels["encoding"]["color"]["condition"]["value"] == "#111111"
    assert count_labels["encoding"]["color"]["value"] == "white"
    assert median_labels["mark"]["fontSize"] == 22
    assert median_labels["mark"]["dy"] == 14
    assert median_labels["encoding"]["text"]["field"] == "median_label"
    assert median_labels["encoding"]["x"]["axis"] is None
    assert top_pettype_axis["encoding"]["x"]["axis"]["orient"] == "top"
    assert top_pettype_axis["encoding"]["x"]["axis"]["labelFontSize"] == 22
    assert top_pettype_axis["encoding"]["x"]["title"] == "PETTYPE"
    assert specification["resolve"]["axis"]["x"] == "independent"
    assert specification["config"]["background"] == analysis.FIGURE_BACKGROUND
    assert specification["config"]["view"]["fill"] == analysis.FIGURE_BACKGROUND
    assert specification["title"]["text"] == "Median DUR duration by MC3 and PETTYPE"

    cohort_specification = analysis.heatmap_chart(
        sample_frame().assign(cohort="Cohort 1"), "Cohort 1"
    ).to_dict()
    assert cohort_specification["title"]["text"] == (
        "Median DUR duration by MC3 and PETTYPE — Cohort 1"
    )


def test_create_outputs_writes_heatmap_and_readme(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(analysis, "OUTPUT_DIRECTORY", tmp_path)

    outputs = analysis.create_outputs(cohort_sample_frame())

    assert [path.name for path in outputs] == [
        "mc3-pettype-analysis.png",
        "mc3-pettype-analysis-cohort-1.png",
        "mc3-pettype-analysis-cohort-2.png",
        "mc3-pettype-analysis-cohort-3.png",
        "mc3-pettype-analysis-cohort-4.png",
        "README.md",
    ]
    assert all(path.is_file() and path.stat().st_size > 0 for path in outputs)
    contents = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert contents.count("![") == 5
    assert "All cohorts" in contents
    for cohort in analysis.COHORTS:
        assert cohort in contents
    assert "All PETTYPEs" in contents
