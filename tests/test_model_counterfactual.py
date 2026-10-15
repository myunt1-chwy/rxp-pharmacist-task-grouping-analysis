from __future__ import annotations

import numpy as np
import pandas as pd

from src.python.model_counterfactual import same_preceding_totals


def test_first_task_per_user_day_cohort_stays_unchanged() -> None:
    frame = pd.DataFrame(
        {
            "user_id": ["u1", "u1", "u1", "u1", "u2"],
            "task_id": ["b", "a", "c", "d", "e"],
            "d": ["2026-02-01"] * 4 + ["2026-02-02"],
            "coh": ["C2", "C1", "C1", "C2", "C1"],
            "process_start_time": [
                "2026-02-01 09:00:00",
                "2026-02-01 09:00:00",
                "2026-02-01 10:00:00",
                "2026-02-01 09:00:00",
                "2026-02-02 08:00:00",
            ],
            "duration_seconds": [100, 200, 300, 400, 500],
            "same_preceding": [0, 0, 1, 0, 0],
        }
    )
    totals = same_preceding_totals(frame, log_coefficient=np.log(0.9))

    # Both cohorts retain a first task; task ID breaks the C2 timestamp tie.
    assert totals.first_tasks == 3
    assert totals.adjusted_tasks == 1
    assert totals.original_seconds == 1500
    assert totals.adjusted_seconds == 1460
    u1 = totals.by_user_day.query("user_id == 'u1'").iloc[0]
    assert u1["original_seconds"] == 1000
    assert u1["adjusted_seconds"] == 960
    cohort = totals.by_cohort.set_index("coh")
    assert cohort.loc["C1", "adjusted_seconds"] == 1000
    assert cohort.loc["C2", "adjusted_seconds"] == 460


def test_precomputed_duration_adjusts_zeros_after_first_true_task() -> None:
    frame = pd.DataFrame(
        {
            "user_id": ["u", "u", "u", "u"],
            "task_id": ["a", "b", "c", "d"],
            "d": ["2026-03-01"] * 4,
            "coh": ["C1", "C2", "C2", "C2"],
            "process_start_time": [
                "2026-03-01 08:00:00",
                "2026-03-01 09:00:00",
                "2026-03-01 10:00:00",
                "2026-03-01 11:00:00",
            ],
            "duration_seconds": [10, 20, 30, 40],
            "same_preceding": [0, 1, 0, 0],
        }
    )
    totals = same_preceding_totals(
        frame, adjusted_duration_seconds=np.array([1, 1, 12, 20])
    )
    assert totals.duration_ratio is None
    assert totals.first_tasks == 2
    assert totals.adjusted_tasks == 2
    assert totals.adjusted_seconds == 62
