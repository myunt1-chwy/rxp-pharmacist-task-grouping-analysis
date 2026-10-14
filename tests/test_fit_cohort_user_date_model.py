from __future__ import annotations

import numpy as np
import pandas as pd

from src.python import fit_cohort_user_date_model as model
from src.python import fit_mc3_coh_pettype_final_model as core


def simulated_frame(seed: int = 31) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = 3_500
    user = rng.integers(8, size=n)
    cohort = rng.integers(3, size=n)
    date = rng.integers(28, size=n)
    dates = pd.date_range("2026-02-01", periods=28)
    preceding = rng.integers(0, 2, size=n)
    following = rng.integers(0, 2, size=n)
    correction = rng.integers(0, 2, size=n)
    pettype = rng.choice(["Dog", "Cat", "Bird"], n, p=[0.5, 0.4, 0.1])
    cell_effect = rng.normal(3.0, 0.2, (3, 8))[cohort, user]
    date_effect = rng.normal(0.0, 0.22, 28)[date]
    log_duration = (
        cell_effect - 0.30 * preceding + 0.08 * following
        + 0.13 * correction + date_effect
        + 0.15 * (pettype == "Cat") - 0.10 * (pettype == "Bird")
        + rng.normal(0, 0.28, n)
    )
    return pd.DataFrame({
        "user_id": [f"user-{value}" for value in user],
        "task_id": [f"task-{value}" for value in range(n)],
        "d": dates[date].date,
        "day_of_week": dates[date].strftime("%a"),
        "coh": [f"coh-{value}" for value in cohort],
        "pettype": pettype,
        "approval_channel": "PH",
        "prescription_source": "HUB",
        "duration_seconds": np.exp(log_duration),
        "p95_seconds": np.exp(log_duration).max() + 1,
        "same_preceding": preceding,
        "same_following": following,
        "has_correction": correction,
        "boxcox_duration": log_duration,
    })


def test_cohort_sql_uses_valid_dur_batch_fields() -> None:
    sql = model.render_sql()
    assert "COHORT_SEQN AS SEQN" in sql
    assert "COHORT_BATCH_LEN AS BATCH_LEN" in sql
    assert "IFF(BATCH_LEN > 1 AND SEQN > 1, 1, 0) AS SAME_PRECEDING" in sql
    assert "IFF(BATCH_LEN > 1 AND SEQN < BATCH_LEN, 1, 0) AS SAME_FOLLOWING" in sql
    assert "PETTYPE::VARCHAR" in sql
    assert "DURATION_SECONDS < duration_cutoff.P95_SECONDS" in sql
    assert "MC3_COH_PETTYPE_SEQN" not in sql


def test_fixed_only_model_recovers_treatment_effects() -> None:
    design = core.build_fixed_effect_design(
        model.prepare_frame(simulated_frame()),
        categorical_effects=model.CATEGORICAL_EFFECTS,
        base_fixed_columns=model.BASE_FIXED_COLUMNS,
    )
    result = core.fit_final_model(
        design, cell_columns=model.CELL_COLUMNS, random_columns=()
    )
    assert result.converged
    assert result.n_cells == len(
        design.frame.loc[:, model.CELL_COLUMNS].drop_duplicates()
    )
    assert result.date_effects.empty
    assert result.user_effects.empty and result.parent_effects.empty
    assert len(result.random_sds) == 0
    assert len(result.random_sd_cis) == 0
    preceding = result.fixed_effects.set_index("term").loc["SAME_PRECEDING"]
    assert abs(preceding["estimate"] + 0.30) < 0.10
    assert preceding["ci_upper"] < 0
    weekday_terms = [t for t in result.fixed_effects["term"] if "WEEKDAY" in t]
    assert len(weekday_terms) == 0


def test_report_documents_fixed_only_formula(tmp_path, monkeypatch) -> None:
    frame = model.prepare_frame(simulated_frame().head(200))
    design = core.build_fixed_effect_design(
        frame,
        categorical_effects=model.CATEGORICAL_EFFECTS,
        base_fixed_columns=model.BASE_FIXED_COLUMNS,
    )
    result = core.fit_final_model(
        core.build_fixed_effect_design(
            model.prepare_frame(simulated_frame()),
            categorical_effects=model.CATEGORICAL_EFFECTS,
            base_fixed_columns=model.BASE_FIXED_COLUMNS,
        ),
        cell_columns=model.CELL_COLUMNS, random_columns=(),
    )
    monkeypatch.setattr(model, "REPORT_PATH", tmp_path / "report.md")
    model.write_report(frame, core.BoxCoxResult(frame, 0.0), design, result)
    report = (tmp_path / "report.md").read_text()
    assert "(\\mathrm{COH}_i,\\mathrm{PETTYPE}_i,\\mathrm{USER\\_ID}_i,D_i)" in report
    assert "h_{d(i)}" not in report
    assert "b_{u(i)}" not in report
    assert "r_{p(i)}" not in report
    assert "\\delta_w" not in report
    assert "Weekday contrasts are determined by date" in report
    assert "no random" in report.lower()
    assert "SAME_FOLLOWING" in report
    assert "adjusted observational association" in report
    assert "The paired t-test is\nalso observational" in report
    assert "neither analysis identifies a causal effect" in report
    assert "estimates are not directly comparable" in report
    assert "Date random intercept" not in report
    assert "date_random_intercepts_qq" not in report
