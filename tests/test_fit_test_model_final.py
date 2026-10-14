from __future__ import annotations

import numpy as np
import pandas as pd

from src.python import fit_cohort_user_date_model as fixed_user
from src.python import fit_mc3_coh_pettype_final_model as core
from src.python import fit_test_model_exp as exp_model
from src.python import fit_test_model_final as model


def test_final_model_uses_cohort_only_indicators() -> None:
    sql = fixed_user.render_sql()
    assert "PROCESS_START_TIME" in sql
    assert "COHORT_SEQN AS SEQN" in sql
    assert "COHORT_BATCH_LEN AS BATCH_LEN" in sql
    assert "IFF(BATCH_LEN > 1 AND SEQN > 1, 1, 0) AS SAME_PRECEDING" in sql
    assert "IFF(BATCH_LEN > 1 AND SEQN < BATCH_LEN, 1, 0) AS SAME_FOLLOWING" in sql
    assert "COHORT_PET_SEQN" not in sql
    assert "PARENT_PART_NUMBER" in sql


def test_final_model_recovers_effect_and_describes_cohort_batch(tmp_path, monkeypatch) -> None:
    rng = np.random.default_rng(93)
    n = 2_000
    user = rng.integers(8, size=n)
    date = rng.integers(14, size=n)
    cohort = rng.integers(3, size=n)
    pettype = rng.integers(2, size=n)
    parent = rng.integers(24, size=n)
    indicators = rng.integers(0, 2, size=(n, 3))
    dates = pd.date_range("2026-02-01", periods=14)
    log_duration = (
        2.8 + 0.10 * cohort + 0.07 * pettype
        + rng.normal(0, 0.23, 8)[user]
        + rng.normal(0, 0.16, 14)[date]
        + rng.normal(0, 0.19, 24)[parent]
        - 0.21 * indicators[:, 0] + 0.04 * indicators[:, 1]
        + 0.11 * indicators[:, 2] + rng.normal(0, 0.28, n)
    )
    duration = np.exp(log_duration)
    frame = fixed_user.prepare_frame(pd.DataFrame({
        "user_id": [f"user-{value}" for value in user],
        "task_id": [f"task-{value}" for value in range(n)],
        "d": dates[date].date,
        "process_start_time": dates[date] + pd.to_timedelta(np.arange(n) % 86400, unit="s"),
        "day_of_week": dates[date].strftime("%a"),
        "coh": [f"coh-{value}" for value in cohort],
        "pettype": np.where(pettype, "Cat", "Dog"),
        "parent_part_number": [f"part-{value}" for value in parent],
        "approval_channel": "PH",
        "prescription_source": "HUB",
        "duration_seconds": duration,
        "p95_seconds": duration.max() + 1,
        "same_preceding": indicators[:, 0],
        "same_following": indicators[:, 1],
        "has_correction": indicators[:, 2],
    }))
    design = core.build_fixed_effect_design(
        exp_model.log_duration(frame),
        categorical_effects=model.CATEGORICAL_EFFECTS,
        base_fixed_columns=core.BASE_FIXED_EFFECT_COLUMNS,
    )
    result = core.fit_final_model(
        design, cell_columns=model.CELL_COLUMNS, random_columns=model.RANDOM_COLUMNS
    )
    assert result.converged and result.n_cells == 0
    assert len(result.random_sds) == 3
    assert result.n_parent_parts == 24
    assert len(result.parent_effects) == 24
    preceding = result.fixed_effects.set_index("term").loc["SAME_PRECEDING"]
    assert abs(preceding["estimate"] + 0.21) < 0.07

    monkeypatch.setattr(model, "REPORT_PATH", tmp_path / "report.md")
    monkeypatch.setattr(model, "DUR_POPULATION_TABLE_PATH", tmp_path / "dur_population_totals.md")
    counterfactual = model.same_preceding_totals(
        design.frame, log_coefficient=float(preceding["estimate"])
    )
    model.write_report(design, result, counterfactual)
    report = (tmp_path / "report.md").read_text()
    assert report.startswith("# test-model-final")
    assert "COHORT_SEQN" in report and "COHORT_BATCH_LEN" in report
    assert "COHORT_PET_SEQN" not in report
    assert "\\log(Y_i)=" in report
    assert "Global intercept (log seconds)" in report
    assert "user_random_intercepts_density.png" in report
    assert "date_random_intercepts_density.png" in report
    assert "parent_random_intercepts_density.png" in report
    assert "q_{r(i)}" in report
    assert "Parent part numbers | 24" in report
    assert "First retained process date | 2026-02-01" in report
    assert "Last retained process date | 2026-02-14" in report
    assert "Pharmacist cost per hour | $95.00" in report
    expected_value = (
        (counterfactual.original_seconds - counterfactual.adjusted_seconds)
        / 3600 * model.PHARMACIST_COST_PER_HOUR
    )
    assert f"Implied labor value | {model.USD}{expected_value:,.2f}" in report
    assert "All DUR task processing time" in report
    assert "4,128,486 tasks" in report
    assert "58,915.45 hours" in report
    assert "total_dur_processing_time.sql" in report
    assert "### Handoff type distribution for all DUR tasks" in report
    assert "| `NULL` | 4,000,758 | 197,557,538 | 54,877.09 |" in report
    assert "| `PHARMACIST_FOLLOW_UP` | 117,503 | 13,334,300 | 3,703.97 |" in report
    assert "| `TECHNICIAN_FOLLOW_UP` | 6,736 | 820,191 | 227.83 |" in report
    assert "| `LEAD_FOLLOW_UP` | 3,489 | 383,589 | 106.55 |" in report
    assert "my_rxp_tasks_handoff_type.sql" in report
    assert "| Valid DURs below 156.608019 seconds | 3,433,218 | 89,130,671 | 24,758.52 |" in report
    assert "| Valid DURs at or above 156.608019 seconds | 180,803 | 88,958,419 | 24,710.67 |" in report
    assert "| **All valid DURs** in `MY_RXP_VALID_DUR_TASKS` | **3,614,021** | **178,089,090** | **49,469.19** |" in report
    assert "| All DURs below 156.608019 seconds in `MY_RXP_TASKS` | 3,905,692 | 104,384,954 | 28,995.82 |" in report
    assert "| **All DURs** in `MY_RXP_TASKS` | **4,128,486** | **212,095,618** | **58,915.45** |" in report
    assert report.index("| DUR population |") < report.index("Within each user and process date")
    assert report.index("| **All DURs** in `MY_RXP_TASKS`") > report.index(
        "| All DURs below 156.608019 seconds in `MY_RXP_TASKS`"
    )
    assert "472,474" in report and "15,254,283" in report
    assert "| **All valid DURs** in `MY_RXP_VALID_DUR_TASKS` |" in (
        tmp_path / "dur_population_totals.md"
    ).read_text()
    assert report.rfind("## All-eligible same-preceding counterfactual") > report.rfind(
        "## Diagnostics and artifacts"
    )
    assert report.rstrip().endswith("Realizing cash savings would depend on staffing decisions.")
