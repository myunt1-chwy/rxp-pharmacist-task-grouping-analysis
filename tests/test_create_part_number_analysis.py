from pathlib import Path

import pandas as pd

from src.python import create_part_number_analysis as analysis


def sample_frame() -> pd.DataFrame:
    rows = []
    for cohort_index in range(1, 5):
        cohort = f"Cohort {cohort_index}"
        for part_index, duration in enumerate([10, 12, 13, 14, 15, 100], start=1):
            rows.append(
                {
                    "coh": cohort,
                    "part_number": str(cohort_index * 100 + part_index),
                    "average_duration_seconds": duration,
                    "median_duration_seconds": duration,
                    "stddev_duration_seconds": 1.0,
                    "unique_task_count": 10,
                    "unique_user_count": 5,
                }
            )
    return pd.DataFrame(rows)


def test_boxplot_chart_has_one_panel_per_cohort_and_labeled_outliers() -> None:
    specification = analysis.create_boxplot(sample_frame()).to_dict()

    assert len(specification["hconcat"]) == 4
    assert "boxplots by cohort" in specification["title"]["text"]
    first_panel = specification["hconcat"][0]
    assert [layer["mark"]["type"] for layer in first_panel["layer"]] == [
        "rule",
        "bar",
        "rule",
        "point",
        "text",
    ]
    assert first_panel["layer"][0]["encoding"]["y"]["field"] == "p05"
    assert first_panel["layer"][0]["encoding"]["y"]["title"] == (
        "Product mean DUR duration (seconds)"
    )
    assert first_panel["layer"][0]["encoding"]["y2"]["field"] == "p95"
    assert first_panel["layer"][1]["encoding"]["y"]["field"] == "q1"
    assert first_panel["layer"][1]["encoding"]["y2"]["field"] == "q3"
    assert first_panel["layer"][2]["encoding"]["x"]["field"] == "median_lower"
    assert first_panel["layer"][2]["encoding"]["x2"]["field"] == "median_upper"
    assert first_panel["layer"][2]["mark"]["color"] == "#8b0000"
    assert first_panel["layer"][2]["encoding"]["y"]["field"] == "median"
    assert first_panel["layer"][3]["encoding"]["y"]["field"] == (
        "average_duration_seconds"
    )
    assert first_panel["layer"][4]["encoding"]["text"]["field"] == "part_label"


def test_create_outputs_writes_one_boxplot_png_and_removes_old_pngs(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(analysis, "OUTPUT_DIRECTORY", tmp_path)
    stale_files = [
        "part-number-analysis-cohort-1.png",
        "part-number-analysis-cohort-2.png",
        "part-number-analysis-cohort-3.png",
        "part-number-analysis-cohort-4.png",
        "part-number-analysis-cohort-violin-plots.png",
    ]
    for filename in stale_files:
        (tmp_path / filename).write_bytes(b"stale")

    outputs = analysis.create_outputs(sample_frame())

    pngs = [path for path in outputs if path.suffix == ".png"]
    assert [path.name for path in pngs] == ["part-number-analysis-cohort-boxplots.png"]
    assert pngs[0].is_file() and pngs[0].stat().st_size > 0
    assert all(not (tmp_path / filename).exists() for filename in stale_files)
    contents = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert contents.count("![") == 1
    assert "part-number-analysis-cohort-boxplots.png" in contents
