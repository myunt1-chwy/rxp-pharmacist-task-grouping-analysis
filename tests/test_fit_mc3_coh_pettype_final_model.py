from __future__ import annotations

import numpy as np
import pandas as pd

from src.python import fit_mc3_coh_pettype_final_model as final_model


def simulated_frame(seed: int = 53) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n_rows = 9_000
    n_users = 20
    n_dates = 35
    n_cells = 15
    n_parent_parts = 40
    user = rng.integers(n_users, size=n_rows)
    date = rng.integers(n_dates, size=n_rows)
    cell = rng.integers(n_cells, size=n_rows)
    parent = rng.integers(n_parent_parts, size=n_rows)
    treatments = rng.integers(0, 2, size=(n_rows, 3))
    approval = rng.choice(["PH", "FAX"], n_rows, p=[0.7, 0.3])
    source = rng.choice(["PRACTICE_HUB", "FAX"], n_rows, p=[0.75, 0.25])
    dates = pd.date_range("2026-02-01", periods=n_dates)
    weekday = dates[date].strftime("%a")
    weekday_design = np.column_stack(
        [(weekday == day).astype(float) for day in final_model.WEEKDAYS[:-1]]
    )
    transformed_duration = (
        rng.normal(3.0, 0.35, n_cells)[cell]
        + treatments @ np.array([-0.22, 0.07, 0.28])
        + weekday_design @ np.array([0.03, -0.02, 0.04, 0.01, -0.03, 0.02])
        + 0.12 * (approval == "FAX")
        - 0.05 * (source == "FAX")
        + rng.normal(0.0, 0.30, n_users)[user]
        + rng.normal(0.0, 0.18, n_dates)[date]
        + rng.normal(0.0, 0.25, n_parent_parts)[parent]
        + rng.normal(0.0, 0.35, n_rows)
    )
    duration = np.exp(transformed_duration)
    return pd.DataFrame(
        {
            "user_id": [f"user-{value}" for value in user],
            "task_id": [f"task-{value}" for value in range(n_rows)],
            "d": dates[date].date,
            "day_of_week": weekday,
            "coh": [f"Cohort {(value % 3) + 1}" for value in cell],
            "mc3": [f"MC3-{value % 5}" for value in cell],
            "pettype": np.where(cell % 2, "Dog", "Cat"),
            "parent_part_number": [f"part-{value}" for value in parent],
            "approval_channel": approval,
            "prescription_source": source,
            "duration_seconds": duration,
            "p95_seconds": duration.max() + 1.0,
            "same_preceding": treatments[:, 0],
            "same_following": treatments[:, 1],
            "has_correction": treatments[:, 2],
            "boxcox_duration": transformed_duration,
        }
    )


def test_final_sql_pulls_parent_part_number() -> None:
    sql = final_model.render_sql()

    assert f"FROM {final_model.SOURCE_TABLE}" in sql
    assert "PARENT_PART_NUMBER::VARCHAR" in sql
    assert "APPROVAL_CHANNEL::VARCHAR" in sql
    assert "PRESCRIPTION_SOURCE::VARCHAR" in sql
    assert "DURATION_SECONDS < duration_cutoff.P95_SECONDS" in sql


def test_parent_part_random_effect_model_recovers_variance() -> None:
    frame = final_model.normalize_frame(simulated_frame())
    design = final_model.build_fixed_effect_design(frame)

    result = final_model.fit_final_model(design)

    assert result.converged
    assert result.n_parent_parts == 40
    assert len(result.parent_effects) == 40
    np.testing.assert_allclose(result.random_sds[2], 0.25, atol=0.08)
    assert result.random_sd_cis[2][0] > 0
    assert result.prediction_bins["count"].sum() == len(frame)


def test_design_uses_most_frequent_category_references() -> None:
    design = final_model.build_fixed_effect_design(simulated_frame())

    assert design.references == {
        "approval_channel": "PH",
        "prescription_source": "PRACTICE_HUB",
    }
    assert "APPROVAL_CHANNEL[FAX vs PH]" in design.labels
    assert "PRESCRIPTION_SOURCE[FAX vs PRACTICE_HUB]" in design.labels


def test_report_documents_complete_model_formula(tmp_path, monkeypatch) -> None:
    frame = final_model.normalize_frame(simulated_frame().head(100))
    design = final_model.build_fixed_effect_design(frame)
    transformation = final_model.BoxCoxResult(frame=design.frame, lambda_=0.1)
    result = final_model.FinalModelResult(
        fixed_effects=pd.DataFrame(
            {
                "term": ["SAME_PRECEDING"],
                "estimate": [0.1],
                "std_error": [0.01],
                "z_value": [10.0],
                "p_value": [0.0],
                "ci_lower": [0.08],
                "ci_upper": [0.12],
            }
        ),
        user_effects=pd.DataFrame(),
        date_effects=pd.DataFrame(),
        parent_effects=pd.DataFrame(),
        residual_quantiles=pd.DataFrame(),
        prediction_bins=pd.DataFrame(),
        random_sds=(0.1, 0.1, 0.1),
        random_sd_cis=((0.08, 0.12),) * 3,
        residual_sd=0.2,
        residual_sd_ci=(0.18, 0.22),
        conditional_r_squared=0.3,
        conditional_rmse=0.4,
        n_observations=100,
        n_cells=10,
        n_users=5,
        n_dates=7,
        n_parent_parts=9,
        reml_nll=123.0,
        converged=True,
    )
    report_path = tmp_path / "report.md"
    monkeypatch.setattr(final_model, "REPORT_PATH", report_path)

    final_model.write_report(frame, transformation, design, result)

    report = report_path.read_text(encoding="utf-8")
    assert "Complete model formula" in report
    assert "b_u\\sim N(0,\\sigma_u^2)" in report
    assert "r_p\\sim N(0,\\sigma_p^2)" in report
    assert "SAME_PRECEDING" in report
    assert "| Significant |" in report
    assert "| Yes |" in report
    assert "\\[" not in report
    assert "\\(" not in report
    assert "$$" in report
