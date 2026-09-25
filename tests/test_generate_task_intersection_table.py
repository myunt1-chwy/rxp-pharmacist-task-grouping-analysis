from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner
import pytest

from src.python import generate_task_intersection_table


@pytest.fixture(autouse=True)
def generated_sql_path(monkeypatch, tmp_path: Path) -> Path:
    path = tmp_path / "generated" / "generate_task_intersection_table.sql"
    monkeypatch.setattr(generate_task_intersection_table, "GENERATED_SQL_PATH", path)
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


def test_rendered_sql_contains_requested_user_and_closed_interval_join() -> None:
    sql = generate_task_intersection_table.render_sql(319402689)

    assert sql.startswith(
        "CREATE OR REPLACE TRANSIENT TABLE "
        "EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASK_INTERSECTIONS AS"
    )
    assert "USER_ID = '319402689'" in sql
    assert "a.STARTED_AT <= b.CLOSED_AT" in sql
    assert "b.STARTED_AT <= a.CLOSED_AT" in sql
    assert "TASK_ID_B AS INTERSECTING_TASK_ID" in sql
    assert "UNION ALL" in sql


def test_user_id_must_be_positive_integer() -> None:
    result = CliRunner().invoke(
        generate_task_intersection_table.main,
        ["--user-id", "not-an-id", "--dry-run"],
    )

    assert result.exit_code == 2
    assert "not a valid integer" in result.output


def test_dry_run_writes_sql_without_connecting(monkeypatch, generated_sql_path: Path) -> None:
    monkeypatch.setattr(
        generate_task_intersection_table,
        "connect_to_snowflake",
        lambda settings: (_ for _ in ()).throw(AssertionError("must not connect")),
    )
    result = CliRunner().invoke(
        generate_task_intersection_table.main,
        ["--user-id", "319402689", "--dry-run"],
    )

    assert result.exit_code == 0
    assert "CREATE OR REPLACE TRANSIENT TABLE" in result.output
    assert generated_sql_path.read_text(encoding="utf-8") == generate_task_intersection_table.render_sql(319402689)


def test_missing_connection_setting_is_cli_error(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    write_env(env_file, complete=False)
    result = CliRunner().invoke(
        generate_task_intersection_table.main,
        ["--user-id", "319402689", "--env-file", str(env_file)],
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
            return (12,)

        def close(self) -> None:
            pass

    class Connection:
        def cursor(self) -> Cursor:
            return Cursor()

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        generate_task_intersection_table,
        "connect_to_snowflake",
        lambda settings: Connection(),
    )
    result = CliRunner().invoke(
        generate_task_intersection_table.main,
        ["--user-id", "319402689", "--env-file", str(env_file)],
    )

    assert result.exit_code == 0
    assert executed == [
        generate_task_intersection_table.render_sql(319402689),
        f"SELECT COUNT(*) FROM {generate_task_intersection_table.TARGET_TABLE}",
    ]
    assert generated_sql_path.read_text(encoding="utf-8") == executed[0]
    assert "with 12 rows for USER_ID 319402689" in result.output
