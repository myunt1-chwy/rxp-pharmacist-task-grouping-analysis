from __future__ import annotations

from datetime import date
from pathlib import Path

from click.testing import CliRunner
import pytest

from src.python import generate_task_table


@pytest.fixture(autouse=True)
def generated_sql_path(monkeypatch, tmp_path: Path) -> Path:
    path = tmp_path / "generated" / "generate_task_table.sql"
    monkeypatch.setattr(generate_task_table, "GENERATED_SQL_PATH", path)
    return path


def write_env(path: Path, *, complete: bool = True) -> None:
    values = {
        "RXP_SNOWFLAKE_ACCOUNT": "account",
        "RXP_SNOWFLAKE_USER": "user@example.com",
        "RXP_SNOWFLAKE_DATABASE": "EDLDB_DEV",
        "RXP_SNOWFLAKE_WAREHOUSE": "warehouse",
        "RXP_SNOWFLAKE_SCHEMA": "PET_HEALTH_ANALYTICS_SANDBOX",
        "RXP_SNOWFLAKE_ROLE": "role",
    }
    if not complete:
        values.pop("RXP_SNOWFLAKE_WAREHOUSE")
    path.write_text("\n".join(f"{key}={value}" for key, value in values.items()), encoding="utf-8")


def test_rendered_sql_contains_required_shape() -> None:
    sql = generate_task_table.render_sql(date(2026, 2, 1), date(2026, 8, 1))

    assert sql.startswith("CREATE OR REPLACE TRANSIENT TABLE EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASKS AS")
    assert "PARTITION BY EMPLOYEE_KYRIOS_ID" in sql
    assert "REPORT_DATE DESC NULLS LAST" in sql
    assert "LAST_UPDATE_TIME DESC NULLS LAST" in sql
    assert "EMPLOYEE_KEY DESC NULLS LAST" in sql
    assert "l.ITEM_COHORT AS COH" in sql
    assert "CONVERT_TIMEZONE('UTC', l.CLOSED_AT)" in sql
    assert ") AS IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS" in sql
    assert "-l.IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS" in sql
    assert ") AS PROCESS_START_TIME" in sql
    assert ") AS PROCESS_START_DATE" in sql
    assert "STARTED_DATE" not in sql
    assert "l.STARTED_AT" in sql
    assert "l.USER_ID = CAST(e.EMPLOYEE_KYRIOS_ID AS VARCHAR)" in sql
    assert "'Area Manager, Pharmacist II'" in sql
    assert "l.TASK_CREATED_AT >= '2026-02-01'" in sql
    assert "l.TASK_CREATED_AT < '2026-08-01'" in sql


def test_dry_run_prints_and_writes_sql_without_env_or_connection(monkeypatch, generated_sql_path: Path) -> None:
    monkeypatch.setattr(
        generate_task_table,
        "connect_to_snowflake",
        lambda settings: (_ for _ in ()).throw(AssertionError("must not connect")),
    )
    result = CliRunner().invoke(
        generate_task_table.main,
        ["--start-date", "2026-02-01", "--end-date", "2026-08-01", "--dry-run"],
    )

    assert result.exit_code == 0
    assert "CREATE OR REPLACE TRANSIENT TABLE" in result.output
    assert generated_sql_path.read_text(encoding="utf-8").startswith("CREATE OR REPLACE TRANSIENT TABLE")


def test_malformed_date_is_cli_error() -> None:
    result = CliRunner().invoke(
        generate_task_table.main,
        ["--start-date", "not-a-date", "--end-date", "2026-08-01", "--dry-run"],
    )
    assert result.exit_code == 2
    assert "does not match the format" in result.output


def test_equal_and_reversed_dates_are_cli_errors() -> None:
    runner = CliRunner()
    for start, end in (("2026-02-01", "2026-02-01"), ("2026-08-01", "2026-02-01")):
        result = runner.invoke(
            generate_task_table.main,
            ["--start-date", start, "--end-date", end, "--dry-run"],
        )
        assert result.exit_code == 2
        assert "--start-date must be earlier" in result.output


def test_missing_connection_setting_is_cli_error(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    write_env(env_file, complete=False)
    result = CliRunner().invoke(
        generate_task_table.main,
        ["--start-date", "2026-02-01", "--end-date", "2026-08-01", "--env-file", str(env_file)],
    )
    assert result.exit_code == 2
    assert "RXP_SNOWFLAKE_WAREHOUSE" in result.output


def test_executes_exactly_one_ctas(monkeypatch, tmp_path: Path, generated_sql_path: Path) -> None:
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

    monkeypatch.setattr(generate_task_table, "connect_to_snowflake", lambda settings: Connection())
    result = CliRunner().invoke(
        generate_task_table.main,
        ["--start-date", "2026-02-01", "--end-date", "2026-08-01", "--env-file", str(env_file)],
    )

    assert result.exit_code == 0
    assert len(executed) == 2
    assert executed[0].startswith("CREATE OR REPLACE TRANSIENT TABLE")
    assert executed[1] == f"SELECT COUNT(*) FROM {generate_task_table.TARGET_TABLE}"
    assert sum(statement.startswith("CREATE OR REPLACE TRANSIENT TABLE") for statement in executed) == 1
    assert generated_sql_path.read_text(encoding="utf-8") == executed[0]
    assert "with 42 rows" in result.output
