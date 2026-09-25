from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from src.python import drop_task_table


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


def test_missing_env_file_is_cli_error(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        drop_task_table.main,
        ["--env-file", str(tmp_path / "missing.env")],
    )

    assert result.exit_code == 2
    assert "environment file not found" in result.output


def test_missing_connection_setting_is_cli_error(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    write_env(env_file, complete=False)
    result = CliRunner().invoke(drop_task_table.main, ["--env-file", str(env_file)])

    assert result.exit_code == 2
    assert "RXP_SNOWFLAKE_WAREHOUSE" in result.output


def test_executes_one_drop_statement(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    write_env(env_file)
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

    monkeypatch.setattr(drop_task_table, "connect_to_snowflake", lambda settings: Connection())
    result = CliRunner().invoke(drop_task_table.main, ["--env-file", str(env_file)])

    assert result.exit_code == 0
    assert executed == [
        "DROP TABLE IF EXISTS EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASKS"
    ]
    assert "Drop command completed" in result.output
