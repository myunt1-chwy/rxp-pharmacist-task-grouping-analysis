from __future__ import annotations

import numpy as np
import pandas as pd

from src.python import fit_cohort_user_date_model as fixed_user
from src.python import fit_mc3_coh_pettype_final_model as core
from src.python import fit_test_model as model


def simulated_frame(seed: int = 74) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = 3_000
    user = rng.integers(10, size=n)
    date = rng.integers(14, size=n)
    cohort = rng.integers(3, size=n)
    pettype = rng.integers(2, size=n)
    treatments = rng.integers(0, 2, size=(n, 3))
    dates = pd.date_range("2026-02-01", periods=14)
    user_effect = rng.normal(0, 0.30, 10)[user]
    date_effect = rng.normal(0, 0.18, 14)[date]
    log_duration = (
        3.0 + 0.13 * cohort + 0.09 * pettype + user_effect + date_effect
        - 0.25 * treatments[:, 0] + 0.05 * treatments[:, 1]
        + 0.12 * treatments[:, 2] + rng.normal(0, 0.28, n)
    )
    duration = np.exp(log_duration)
    return pd.DataFrame({
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
        "same_preceding": treatments[:, 0],
        "same_following": treatments[:, 1],
        "has_correction": treatments[:, 2],
        "boxcox_duration": log_duration,
    })


def test_no_cell_model_recovers_effect_and_reports_formula(tmp_path, monkeypatch) -> None:
    frame = fixed_user.prepare_frame(simulated_frame())
    design = core.build_fixed_effect_design(
        frame,
        categorical_effects=model.CATEGORICAL_EFFECTS,
        base_fixed_columns=core.BASE_FIXED_EFFECT_COLUMNS,
    )
    result = core.fit_final_model(
        design, cell_columns=model.CELL_COLUMNS, random_columns=model.RANDOM_COLUMNS
    )

    assert result.converged
    assert result.n_cells == 0
    assert len(result.user_effects) == 10
    assert len(result.date_effects) == 14
    assert len(result.random_sds) == 2
    assert all(sd > 0.05 for sd in result.random_sds)
    labels = result.fixed_effects["term"].tolist()
    assert any(label.startswith("COH[") for label in labels)
    assert any(label.startswith("PETTYPE[") for label in labels)
    assert any(label.startswith("WEEKDAY_") for label in labels)
    preceding = result.fixed_effects.set_index("term").loc["SAME_PRECEDING"]
    assert abs(preceding["estimate"] + 0.25) < 0.06
    assert preceding["ci_upper"] < 0

    single_intercept = design.frame.copy()
    single_intercept["global_intercept"] = "all"
    equivalent = core.fit_final_model(
        core.FixedEffectDesign(
            frame=single_intercept,
            columns=design.columns,
            labels=design.labels,
            references=design.references,
            levels=design.levels,
        ),
        cell_columns=("global_intercept",),
        random_columns=model.RANDOM_COLUMNS,
    )
    np.testing.assert_allclose(
        result.fixed_effects["estimate"],
        equivalent.fixed_effects["estimate"],
        atol=1e-8,
    )
    intercept = model.global_intercept(design, result)
    users = result.user_effects.set_index("user_id")["random_intercept"]
    dates = result.date_effects.set_index("d")["random_intercept"]
    direct_intercept = np.mean(
        design.frame["boxcox_duration"].to_numpy()
        - design.frame.loc[:, design.columns].to_numpy()
        @ result.fixed_effects["estimate"].to_numpy()
        - design.frame["user_id"].map(users).to_numpy()
        - design.frame["d"].astype(str).map(dates).to_numpy()
    )
    assert abs(intercept - direct_intercept) < 1e-10

    monkeypatch.setattr(model, "REPORT_PATH", tmp_path / "report.md")
    model.write_report(design.frame, core.BoxCoxResult(frame, 0.0), design, result)
    report = (tmp_path / "report.md").read_text()
    assert report.startswith("# test-model")
    assert "There are no fixed cells" in report
    assert "| Fixed cells | 0 |" in report
    assert f"| Global intercept (Box-Cox scale) | {intercept:.6f} |" in report
    assert "COHORT_PET_SEQN" in report
    assert "COHORT_PET_BATCH_LEN" in report
    assert "User random intercept" in report
    assert "Date random intercept" in report
    assert "adjusted observational association" in report
