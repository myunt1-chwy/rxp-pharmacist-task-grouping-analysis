from __future__ import annotations

import numpy as np
import pandas as pd

from src.python import fit_cohort_user_date_pettype_cell_model as model
from src.python import fit_cohort_user_date_model as fixed_user
from src.python import fit_mc3_coh_pettype_final_model as core


def simulated_frame(seed: int = 47) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = 4_000
    user = rng.integers(12, size=n)
    cohort = rng.integers(3, size=n)
    pettype = rng.integers(2, size=n)
    date = rng.integers(20, size=n)
    dates = pd.date_range("2026-02-01", periods=20)
    treatments = rng.integers(0, 2, size=(n, 3))
    cell_effect = rng.normal(3.0, 0.18, (3, 2, 20))[cohort, pettype, date]
    user_effect = rng.normal(0, 0.28, 12)[user]
    log_duration = (
        cell_effect + user_effect
        + treatments @ np.array([-0.27, 0.06, 0.14])
        + rng.normal(0, 0.30, n)
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


def test_count_cells_requires_two_tasks_with_each_indicator_value() -> None:
    frame = pd.DataFrame({
        "coh": ["A"] * 4 + ["B"] * 3 + ["C"] * 3,
        "pettype": ["Dog"] * 10,
        "d": ["2026-02-01"] * 10,
        "same_preceding": [0, 0, 1, 1, 0, 1, 1, 1, 1, 1],
    })
    assert model.count_cells_with_two_each(frame) == (1, 3)


def test_sql_uses_cohort_pet_batch_position_and_length() -> None:
    sql = fixed_user.render_sql(
        sequence_field=model.SEQUENCE_FIELD, length_field=model.LENGTH_FIELD
    )
    assert "COHORT_PET_SEQN AS SEQN" in sql
    assert "COHORT_PET_BATCH_LEN AS BATCH_LEN" in sql
    assert "COHORT_PET_SEQN <= COHORT_PET_BATCH_LEN" in sql
    assert "IFF(BATCH_LEN > 1 AND SEQN > 1, 1, 0) AS SAME_PRECEDING" in sql
    assert "IFF(BATCH_LEN > 1 AND SEQN < BATCH_LEN, 1, 0) AS SAME_FOLLOWING" in sql
    assert "COHORT_SEQN" not in sql


def test_user_random_model_uses_cohort_pettype_date_cells(tmp_path, monkeypatch) -> None:
    frame = fixed_user.prepare_frame(simulated_frame())
    design = core.build_fixed_effect_design(
        frame,
        categorical_effects=fixed_user.CATEGORICAL_EFFECTS,
        base_fixed_columns=fixed_user.BASE_FIXED_COLUMNS,
    )
    result = core.fit_final_model(
        design, cell_columns=model.CELL_COLUMNS, random_columns=model.RANDOM_COLUMNS
    )

    assert result.converged
    assert result.n_cells == 3 * 2 * 20
    assert len(result.user_effects) == 12
    assert result.date_effects.empty and result.parent_effects.empty
    assert len(result.random_sds) == 1
    assert result.random_sds[0] > 0.05
    assert result.random_sd_cis[0][0] > 0
    assert not any(term.startswith("WEEKDAY_") for term in result.fixed_effects["term"])
    preceding = result.fixed_effects.set_index("term").loc["SAME_PRECEDING"]
    assert abs(preceding["estimate"] + 0.27) < 0.08
    assert preceding["ci_upper"] < 0

    monkeypatch.setattr(model, "REPORT_PATH", tmp_path / "report.md")
    model.write_report(frame, core.BoxCoxResult(frame, 0.0), design, result)
    report = (tmp_path / "report.md").read_text()
    assert report.startswith("# cohort_user_date_pettype_cell_model")
    assert "(\\mathrm{COH}_i,\\mathrm{PETTYPE}_i,D_i)" in report
    assert "b_{u(i)}+\\epsilon_i" in report
    assert "h_{d(i)}" not in report
    assert "no weekday contrast is fitted" in report
    assert "User random intercept" in report
    assert "adjusted observational association" in report
    assert "distribution among the 4,000 tasks" in report
    assert "COHORT_PET_SEQN" in report
    assert "COHORT_PET_BATCH_LEN" in report
    assert "COHORT_PET_BATCH_SEQN` is an intermediate batch identifier" in report
    both = int(((frame["same_preceding"] == 1) &
                (frame["same_following"] == 1)).sum())
    assert f"both indicators to {both:,} ({both / len(frame):.2%})" in report.replace("\n", " ")
    assert "| Indicator | Value | Tasks | Percent |" in report
    assert "| SAME_PRECEDING | SAME_FOLLOWING | Tasks | Percent |" in report
    eligible, total = model.count_cells_with_two_each(frame)
    assert f"{eligible:,} ({eligible / total:.2%}) contain at least two" in report.replace("\n", " ")
    for column, label in (
        ("same_preceding", "SAME_PRECEDING"),
        ("same_following", "SAME_FOLLOWING"),
    ):
        for value in (0, 1):
            count = int((frame[column] == value).sum())
            assert f"| {label} | {value} | {count:,} | {count / len(frame):.2%} |" in report
    for preceding in (0, 1):
        for following in (0, 1):
            count = int(
                ((frame["same_preceding"] == preceding) &
                 (frame["same_following"] == following)).sum()
            )
            assert (
                f"| {preceding} | {following} | {count:,} | {count / len(frame):.2%} |"
                in report
            )
