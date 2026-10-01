from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from click.testing import CliRunner

from src.python import generate_valid_dur_task_table as generator


def test_rendered_sql_contains_valid_task_and_sequence_logic() -> None:
    sql = generator.render_sql()

    assert sql.startswith(
        "CREATE OR REPLACE TRANSIENT TABLE "
        "EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_VALID_DUR_TASKS AS"
    )
    assert "TASK_TYPE = 'DUR'" in sql
    assert "LOWER(IS_REFILL) = 'false'" in sql
    assert "HANDOFF_TYPE IS NULL" in sql
    assert "N_INTERSECTING_TASKS = 0" in sql
    assert "EDLDB.PDM.PRODUCT" in sql
    assert "product.PARENT_PART_NUMBER" in sql
    assert "product.MERCH_CLASSIFICATION3" in sql
    assert "product.PURCHASE_BRAND" in sql
    assert "task.IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS" in sql
    assert "DWELL_IN_PROGRESS_TO_CLOSED_SECONDS IS NOT NULL" in sql
    assert "DWELL_IN_PROGRESS_TO_CLOSED_SECONDS > 0" in sql
    assert "IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS,\n    GLOBAL_TASK_SEQN" in sql
    assert "ROW_NUMBER() OVER" in sql
    assert "GLOBAL_TASK_SEQN" in sql
    assert "VALID_TASK_SEQN" in sql
    assert "PREVIOUS_TASK_INVALID" in sql
    assert "COHORT_SEQN" in sql
    assert "COHORT_BATCH_SEQN" in sql
    assert "COHORT_BATCH_ID" in sql
    assert "COHORT_BATCH_LEN" in sql
    assert "COHORT_PET_SEQUENCE_START" in sql
    assert "COHORT_PET_BATCH_SEQN" in sql
    assert "COHORT_PET_SEQN" in sql
    assert "COHORT_PET_BATCH_ID" in sql
    assert "COHORT_PET_BATCH_LEN" in sql
    assert "MC3_SEQN" in sql
    assert "MC3_BATCH_ID" in sql
    assert "MC3_BATCH_LEN" in sql
    assert "SEQUENCE_PETTYPE" in sql
    assert "PETPROFILE_PETTYPE_DESCRIPTION" in sql
    assert "AS SEQUENCE_PETTYPE" in sql
    assert "PREVIOUS_VALID_SEQUENCE_PETTYPE" in sql
    assert "MC3_PET_SEQUENCE_START" in sql
    assert "MC3_PET_BATCH_SEQN" in sql
    assert "MC3_PET_SEQN" in sql
    assert "MC3_PET_BATCH_ID" in sql
    assert "MC3_PET_BATCH_LEN" in sql
    assert "MC3_COH_PETTYPE_SEQUENCE_START" in sql
    assert "MC3_COH_PETTYPE_BATCH_SEQN" in sql
    assert "MC3_COH_PETTYPE_SEQN" in sql
    assert "MC3_COH_PETTYPE_BATCH_ID" in sql
    assert "MC3_COH_PETTYPE_BATCH_LEN" in sql
    assert "BRAND_SEQN" in sql
    assert "BRAND_BATCH_ID" in sql
    assert "BRAND_BATCH_LEN" in sql
    assert "PP_SEQN" in sql
    assert "PP_BATCH_ID" in sql
    assert "PP_BATCH_LEN" in sql
    assert "DATEDIFF('second', PREVIOUS_VALID_CLOSED_AT, PROCESS_START_TIME) >= 3600" in sql
    assert "GLOBAL_TASK_SEQN <> PREVIOUS_VALID_GLOBAL_TASK_SEQN + 1" in sql
    assert "LAG(GLOBAL_TASK_SEQN) OVER" in sql
    assert "PARTITION BY USER_ID, COHORT_BATCH_SEQN" in sql
    assert "PARTITION BY USER_ID, COHORT_PET_BATCH_SEQN" in sql
    assert "PARTITION BY USER_ID, MC3_PET_BATCH_SEQN" in sql
    assert "PARTITION BY USER_ID, MC3_COH_PETTYPE_BATCH_SEQN" in sql
    assert "OR COH <> PREVIOUS_VALID_COH" in sql
    assert "OR SEQUENCE_PET_ID IS NULL" in sql
    assert "OR PREVIOUS_VALID_SEQUENCE_PET_ID IS NULL" in sql
    assert "OR SEQUENCE_PET_ID <> PREVIOUS_VALID_SEQUENCE_PET_ID" in sql
    assert "OR SEQUENCE_PETTYPE <> PREVIOUS_VALID_SEQUENCE_PETTYPE" in sql
    assert "OR NOT (COH IS NOT DISTINCT FROM PREVIOUS_COH)" not in sql
    assert "task.TASK_CREATED_AT" not in sql


def test_rendered_sql_enriches_valid_tasks_through_deduplicated_usage_mapping() -> None:
    sql = generator.render_sql()
    usage_mapping = re.search(
        r"usage_to_rx AS \(.*?enriched_rows AS \(",
        sql,
        flags=re.DOTALL,
    )

    assert "EDLDB.BT_HCA_HCDM.RXP_RX_USAGE_ACTIONS" in sql
    assert "EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS" in sql
    assert "valid_task_usage_ids AS (" in sql
    assert "SELECT DISTINCT\n        RX_USAGE_ID" in sql
    assert usage_mapping is not None
    assert "actions.RX_USAGE_ID" in usage_mapping.group()
    assert "MIN(actions.RX_ID) AS RX_ID" in usage_mapping.group()
    assert "GROUP BY actions.RX_USAGE_ID" in usage_mapping.group()
    assert "valid_task_usage_ids.RX_USAGE_ID = actions.RX_USAGE_ID" in usage_mapping.group()
    assert "usage_to_rx.RX_USAGE_ID = sequenced_rows.RX_USAGE_ID" in sql
    assert "approved_rx_by_pet AS (" in sql
    assert "UPPER(TO_STATE) = 'APPROVED'" in sql
    assert "MAX(IFF(COALESCE(IS_VET_DIET_FLAG, FALSE), 1, 0)) AS IS_VET_DIET_RX" in sql
    assert "current_task_rx_ids AS (" in sql
    assert "usage_to_rx.RX_ID AS CURRENT_RX_ID" in sql
    assert "prior_approved_rx_counts_by_task AS (" in sql
    assert "COUNT(DISTINCT approved_rx.RX_ID) AS N_PRIOR_APPROVED_RX_IDS" in sql
    assert "DISTINCT IFF(" in sql
    assert "N_PRIOR_APPROVED_VET_DIET_RX_IDS" in sql
    assert "N_PRIOR_APPROVED_NON_VET_DIET_RX_IDS" in sql
    assert "approved_rx.APPROVED_AT < current_task.PROCESS_START_TIME" in sql
    assert "approved_rx.RX_ID <> current_task.CURRENT_RX_ID" in sql
    assert "prescriptions.RX_ID = usage_to_rx.RX_ID" in sql
    assert "prescriptions.ORIGINATION" in sql
    assert "prescriptions.INITIATION_CHANNEL" in sql
    assert "prescriptions.INITIATION_REASON" in sql
    assert "prescriptions.PRESCRIPTION_SOURCE" in sql
    assert "prescriptions.APPROVAL_CHANNEL" in sql
    assert "prescriptions.PET_ID" in sql
    assert "FROM CHEWYBI.CUSTOMER_PETPROFILES" in sql
    assert "PETPROFILE_PETTYPE_DESCRIPTION" in sql
    assert "PETPROFILE_MED_CONDITION_LIST" in sql
    assert "PARTITION BY PETPROFILE_ID" in sql
    assert "pet_profiles.PETPROFILE_ID = prescriptions.PET_ID" in sql
    assert "pet_profiles.PETPROFILE_PETTYPE_DESCRIPTION AS PETTYPE" in sql
    assert "LOWER(TRIM(pet_profiles.PETPROFILE_MED_CONDITION_LIST)) = 'none'" in sql
    assert "ARRAY_SIZE(SPLIT(TRIM(pet_profiles.PETPROFILE_MED_CONDITION_LIST), ','))" in sql
    assert "END AS NPET_CONDITIONS" in sql
    assert "FCT__RX_RESULT_FIELD_CHANGE_SUMMARY" in sql
    assert "LOWER(last_action_name) = 'approvedrugutilizationreview'" not in sql
    assert "last_action_id" in sql
    assert "corrections.LAST_ACTION_ID AS ACTION_ID" in sql
    assert "last_changed_by_role <> 'SYSTEM'" in sql
    assert "last_changed_dttm >= '2026-02-01'" in sql
    assert "last_changed_dttm < '2026-08-01'" in sql
    assert "ARRAY_AGG(DISTINCT correction.FIELD_NAME)" in sql
    assert "WITHIN GROUP (ORDER BY correction.FIELD_NAME)" in sql
    assert "COUNT(DISTINCT correction.FIELD_NAME) AS NCORRECTION_FIELDS" in sql
    assert "ARRAY_AGG(DISTINCT correction.ACTION_NAME)" in sql
    assert "WITHIN GROUP (ORDER BY correction.ACTION_NAME) AS CORRECTION_ACTION_NAMES" in sql
    assert "corrections.ACTION_NAME = actions.ACTION_NAME" not in sql
    assert "ARRAY_AGG(DISTINCT correction.ACTION_ID)" in sql
    assert "WITHIN GROUP (ORDER BY correction.ACTION_ID) AS CORRECTION_ACTION_IDS" in sql
    assert "correction.LAST_CHANGED_DTTM BETWEEN lifecycle.STARTED_AT AND lifecycle.TRANSITION_ENDED_AT" in sql
    assert "correction.LAST_CHANGED_DTTM BETWEEN lifecycle.TRANSITION_STARTED_AT AND lifecycle.TRANSITION_ENDED_AT" not in sql
    assert "ARRAY_CONTAINS(correction.USER_ID::VARIANT, lifecycle.USER_HISTORY)" not in sql
    assert "CORRECTION_FIELD_NAMES" in sql
    assert "NCORRECTION_FIELDS" in sql
    assert "RX_USAGE_ID,\n    ORIGINATION,\n    INITIATION_CHANNEL,\n    INITIATION_REASON,\n    PRESCRIPTION_SOURCE,\n    APPROVAL_CHANNEL,\n    PET_ID," in sql
    assert (
        "PETTYPE,\n"
        "    NPET_CONDITIONS,\n"
        "    CORRECTION_FIELD_NAMES,\n"
        "    NCORRECTION_FIELDS,\n"
        "    CORRECTION_ACTION_NAMES,\n"
        "    CORRECTION_ACTION_IDS,\n"
        "    PROCESS_START_TIME,"
    ) in sql
    assert (
        "    N_PRIOR_APPROVED_RX_IDS,\n"
        "    N_PRIOR_APPROVED_VET_DIET_RX_IDS,\n"
        "    N_PRIOR_APPROVED_NON_VET_DIET_RX_IDS,\n"
        "    PETTYPE,"
    ) in sql
    assert (
        "    PETTYPE,\n"
        "    NPET_CONDITIONS,\n"
        "    CORRECTION_FIELD_NAMES,\n"
        "    NCORRECTION_FIELDS,\n"
        "    CORRECTION_ACTION_NAMES,\n"
        "    CORRECTION_ACTION_IDS,\n"
        "    PROCESS_START_TIME,"
    ) in sql
    assert "LEFT JOIN EDLDB.BT_HCA_HCDM.RXP_RX_USAGE_ACTIONS" not in sql
    assert sql.index("valid_task_usage_ids AS (") > sql.index("WHERE IS_VALID_TASK")


def test_render_sql_uses_parameterized_date_window() -> None:
    sql = generator.render_sql(date(2026, 3, 1), date(2026, 4, 1))

    assert "'2026-03-01'" in sql
    assert "'2026-04-01'" in sql
    assert "'2026-02-01'" not in sql
    assert "'2026-08-01'" not in sql


def test_render_sql_rejects_reversed_date_window() -> None:
    try:
        generator.render_sql(date(2026, 4, 1), date(2026, 3, 1))
    except ValueError as error:
        assert str(error) == "start_date must be earlier than end_date"
    else:
        raise AssertionError("reversed date windows must be rejected")


def test_dry_run_writes_sql_without_connecting(monkeypatch, tmp_path: Path) -> None:
    output = tmp_path / "generated" / "generate_valid_dur_task_table.sql"
    monkeypatch.setattr(generator, "GENERATED_SQL_PATH", output)
    monkeypatch.setattr(
        generator,
        "connect_to_snowflake",
        lambda settings: (_ for _ in ()).throw(AssertionError("must not connect")),
    )

    result = CliRunner().invoke(generator.main, ["--dry-run"])

    assert result.exit_code == 0
    assert output.read_text(encoding="utf-8") == generator.render_sql()


def test_executes_ctas_and_row_count(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            (
                "RXP_SNOWFLAKE_ACCOUNT=account",
                "RXP_SNOWFLAKE_USER=user@example.com",
                "RXP_SNOWFLAKE_DATABASE=EDLDB_DEV",
                "RXP_SNOWFLAKE_WAREHOUSE=warehouse",
                "RXP_SNOWFLAKE_SCHEMA=PET_HEALTH_ANALYTICS_SANDBOX",
            )
        ),
        encoding="utf-8",
    )
    executed: list[str] = []

    class Cursor:
        def execute(self, sql: str) -> None:
            executed.append(sql)

        def fetchone(self) -> tuple[int]:
            return (42,)

        def close(self) -> None:
            pass

    class Connection:
        def cursor(self) -> Cursor:
            return Cursor()

        def close(self) -> None:
            pass

    monkeypatch.setattr(generator, "connect_to_snowflake", lambda settings: Connection())
    monkeypatch.setattr(generator, "GENERATED_SQL_PATH", tmp_path / "generated.sql")

    result = CliRunner().invoke(generator.main, ["--env-file", str(env_file)])

    assert result.exit_code == 0
    assert len(executed) == 2
    assert executed[0] == generator.render_sql()
    assert executed[1] == f"SELECT COUNT(*) FROM {generator.TARGET_TABLE}"
    assert "42" in result.output


def test_drop_executes_expected_statement(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "RXP_SNOWFLAKE_ACCOUNT=account\n"
        "RXP_SNOWFLAKE_USER=user@example.com\n"
        "RXP_SNOWFLAKE_DATABASE=EDLDB_DEV\n"
        "RXP_SNOWFLAKE_WAREHOUSE=warehouse\n"
        "RXP_SNOWFLAKE_SCHEMA=PET_HEALTH_ANALYTICS_SANDBOX\n",
        encoding="utf-8",
    )
    executed: list[str] = []

    class Cursor:
        def execute(self, sql: str) -> None:
            executed.append(sql)

        def close(self) -> None:
            pass

    class Connection:
        def cursor(self) -> Cursor:
            return Cursor()

        def close(self) -> None:
            pass

    monkeypatch.setattr(generator, "connect_to_snowflake", lambda settings: Connection())

    # Import locally so the test keeps the generator's settings fixtures simple.
    from src.python import drop_valid_dur_task_table as dropper

    monkeypatch.setattr(dropper, "connect_to_snowflake", lambda settings: Connection())
    result = CliRunner().invoke(dropper.main, ["--env-file", str(env_file)])

    assert result.exit_code == 0
    assert executed == [f"DROP TABLE IF EXISTS {dropper.TARGET_TABLE}"]
