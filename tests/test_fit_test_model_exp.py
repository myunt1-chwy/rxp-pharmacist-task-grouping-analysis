from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.python import fit_cohort_user_date_model as fixed_user
from src.python import fit_mc3_coh_pettype_final_model as core
from src.python import fit_test_model_exp as model


def test_log_duration_is_natural_log_and_requires_positive_values() -> None:
    frame = pd.DataFrame({"duration_seconds": [1.0, np.e, np.e**2]})
    np.testing.assert_allclose(
        model.log_duration(frame)["boxcox_duration"], [0.0, 1.0, 2.0]
    )
    with pytest.raises(ValueError, match="strictly positive"):
        model.log_duration(pd.DataFrame({"duration_seconds": [0.0]}))


def test_log_model_recovers_effect_and_reports_log_formula(tmp_path, monkeypatch) -> None:
    rng = np.random.default_rng(89)
    n = 2_500
    user = rng.integers(9, size=n)
    date = rng.integers(14, size=n)
    cohort = rng.integers(3, size=n)
    pettype = rng.integers(2, size=n)
    indicators = rng.integers(0, 2, size=(n, 3))
    dates = pd.date_range("2026-02-01", periods=14)
    log_duration = (
        2.7 + 0.1 * cohort + 0.08 * pettype
        + rng.normal(0, 0.25, 9)[user]
        + rng.normal(0, 0.18, 14)[date]
        - 0.22 * indicators[:, 0] + 0.04 * indicators[:, 1]
        + 0.12 * indicators[:, 2] + rng.normal(0, 0.27, n)
    )
    duration = np.exp(log_duration)
    frame = fixed_user.prepare_frame(pd.DataFrame({
        "user_id": [f"user-{value}" for value in user],
        "task_id": [f"task-{value}" for value in range(n)],
        "d": dates[date].date,
        "day_of_week": dates[date].strftime("%a"),
        "coh": [f"coh-{value}" for value in cohort],
        "pettype": np.where(pettype, "Cat", "Dog"),
        "approval_channel": "PH",
        "prescription_source": "HUB",
        "duration_seconds": duration,
        "p95_seconds": duration.max() + 1,
        "same_preceding": indicators[:, 0],
        "same_following": indicators[:, 1],
        "has_correction": indicators[:, 2],
    }))
    design = core.build_fixed_effect_design(
        model.log_duration(frame),
        categorical_effects=model.CATEGORICAL_EFFECTS,
        base_fixed_columns=core.BASE_FIXED_EFFECT_COLUMNS,
    )
    result = core.fit_final_model(
        design, cell_columns=model.CELL_COLUMNS, random_columns=model.RANDOM_COLUMNS
    )
    assert result.converged and result.n_cells == 0
    assert len(result.random_sds) == 2
    assert any(term.startswith("COH[") for term in result.fixed_effects["term"])
    assert any(term.startswith("PETTYPE[") for term in result.fixed_effects["term"])
    assert any(term.startswith("WEEKDAY_") for term in result.fixed_effects["term"])
    preceding = result.fixed_effects.set_index("term").loc["SAME_PRECEDING"]
    assert abs(preceding["estimate"] + 0.22) < 0.06
    assert preceding["ci_upper"] < 0

    monkeypatch.setattr(model, "REPORT_PATH", tmp_path / "report.md")
    model.write_report(design, result)
    report = (tmp_path / "report.md").read_text()
    assert report.startswith("# test-model-exp")
    assert "\\log(Y_i)=" in report
    assert "Box-Cox lambda" not in report
    assert "Global intercept (log seconds)" in report
    assert "There are no fixed cells" in report
    assert "COHORT_PET_SEQN" in report
    assert "adjusted duration ratio" in report
    assert "user_random_intercepts_density.png" in report
    assert "date_random_intercepts_density.png" in report
    assert "one fitted intercept equal weight per user or date" in report
