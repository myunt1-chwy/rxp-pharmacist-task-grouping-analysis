from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner
import pytest

from src.python import generate_task_sequence_table


@pytest.fixture(autouse=True)
def generated_sql_path(monkeypatch, tmp_path: Path) -> Path:
    path = tmp_path / "generated" / "generate_task_sequence_table.sql"
    monkeypatch.setattr(generate_task_sequence_table, "GENERATED_SQL_PATH", path)
    return path


def write_env(path: Path, *, complete: bool = True) -> None:
    values = {
        "RXP_SNOWFLAKE_ACCOUNT": "account",
        "RXP_SNOWFLAKE_USER": "user@example.com",
        "RXP_SNOWFLAKE_DATABASE": "EDLDB_DEV",
        "RXP_SNOWFLAKE_WAREHOUSE": "warehouse",
        "RXP_SNOWFLAKE_SCHEMA": "PET_HEALTH_ANALYTICS_SANDBOX",
    }
    if not complete:
        values.pop("RXP_SNOWFLAKE_WAREHOUSE")
    path.write_text("\n".join(f"{key}={value}" for key, value in values.items()), encoding="utf-8")


def test_rendered_sql_contains_sequence_and_intersection_logic() -> None:
    sql = generate_task_sequence_table.render_sql()

    assert sql.startswith(
        "CREATE OR REPLACE TRANSIENT TABLE "
        "EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASKS_WITH_SEQUENCE AS"
    )
    assert "PARTITION BY USER_ID, TASK_ID" in sql
    assert "MIN(TASK_ID) AS TASK_ID" in sql
    assert "MATCH_CONDITION(current_task.PROCESS_START_TIME > preceding.CLOSED_AT)" in sql
    assert "MATCH_CONDITION(current_task.CLOSED_AT < next_event.PROCESS_START_TIME)" in sql
    assert "AS following" not in sql
    assert "AS DELTA_T_WITH_PRECEDING" in sql
    assert "AS DELTA_T_WITH_FOLLOWING" in sql
    assert "AS N_INTERSECTING_TASKS" in sql
    assert "STARTS_THROUGH_EVENT" in sql
    assert "ENDS_BEFORE_EVENT" in sql
    assert "TASK_TYPE = 'DUR'" not in sql
    assert "PRECEEDING" not in sql
    assert "PREECEDING" not in sql


def test_dry_run_writes_sql_without_connecting(monkeypatch, generated_sql_path: Path) -> None:
    monkeypatch.setattr(
        generate_task_sequence_table,
        "connect_to_snowflake",
        lambda settings: (_ for _ in ()).throw(AssertionError("must not connect")),
    )
    result = CliRunner().invoke(generate_task_sequence_table.main, ["--dry-run"])

    assert result.exit_code == 0
    assert "CREATE OR REPLACE TRANSIENT TABLE" in result.output
    assert generated_sql_path.read_text(encoding="utf-8") == generate_task_sequence_table.render_sql()


def test_missing_connection_setting_is_cli_error(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    write_env(env_file, complete=False)
    result = CliRunner().invoke(
        generate_task_sequence_table.main,
        ["--env-file", str(env_file)],
    )

    assert result.exit_code == 2
    assert "RXP_SNOWFLAKE_WAREHOUSE" in result.output


def test_executes_one_ctas_and_row_count(monkeypatch, tmp_path: Path, generated_sql_path: Path) -> None:
    env_file = tmp_path / ".env"
    write_env(env_file)
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

    monkeypatch.setattr(
        generate_task_sequence_table,
        "connect_to_snowflake",
        lambda settings: Connection(),
    )
    result = CliRunner().invoke(
        generate_task_sequence_table.main,
        ["--env-file", str(env_file)],
    )

    assert result.exit_code == 0
    assert executed == [
        generate_task_sequence_table.render_sql(),
        f"SELECT COUNT(*) FROM {generate_task_sequence_table.TARGET_TABLE}",
    ]
    assert generated_sql_path.read_text(encoding="utf-8") == executed[0]
    assert "with 42 rows" in result.output
