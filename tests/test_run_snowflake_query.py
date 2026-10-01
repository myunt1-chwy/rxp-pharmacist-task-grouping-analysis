from __future__ import annotations

import importlib.util
from pathlib import Path

from click.testing import CliRunner
import pytest

RUNNER_PATH = Path(__file__).resolve().parents[1] / "skills" / "rxp-sql" / "scripts" / "run_snowflake_query.py"
RUNNER_SPEC = importlib.util.spec_from_file_location("run_snowflake_query", RUNNER_PATH)
assert RUNNER_SPEC is not None and RUNNER_SPEC.loader is not None
run_snowflake_query = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(run_snowflake_query)


@pytest.fixture(autouse=True)
def skip_duckdb_version_check(monkeypatch) -> None:
    monkeypatch.setattr(run_snowflake_query, "verify_duckdb", lambda: None)


def write_env(path: Path) -> None:
    path.write_text(
        "\n".join(
            (
                "RXP_SNOWFLAKE_ACCOUNT=account",
                "RXP_SNOWFLAKE_USER=user@example.com",
                "RXP_SNOWFLAKE_DATABASE=database",
                "RXP_SNOWFLAKE_WAREHOUSE=warehouse",
                "RXP_SNOWFLAKE_SCHEMA=schema",
            )
        ),
        encoding="utf-8",
    )


def test_source_is_required_and_mutually_exclusive(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    query_file = tmp_path / "query.sql"
    write_env(env_file)
    query_file.write_text("SELECT 1", encoding="utf-8")
    runner = CliRunner()

    missing = runner.invoke(run_snowflake_query.main, ["--env-file", str(env_file)])
    both = runner.invoke(
        run_snowflake_query.main,
        [str(query_file), "--query", "SELECT 1", "--env-file", str(env_file)],
    )

    assert missing.exit_code == 2
    assert both.exit_code == 2
    assert "exactly one" in missing.output
    assert "exactly one" in both.output


@pytest.mark.parametrize("sql", ["DELETE FROM x", "SELECT 1; SELECT 2"])
def test_read_only_validation_is_cli_error(tmp_path: Path, sql: str) -> None:
    env_file = tmp_path / ".env"
    write_env(env_file)
    result = CliRunner().invoke(
        run_snowflake_query.main,
        ["--query", sql, "--env-file", str(env_file)],
    )
    assert result.exit_code == 2


def test_missing_env_and_settings_are_cli_errors(tmp_path: Path) -> None:
    runner = CliRunner()
    missing_file = runner.invoke(
        run_snowflake_query.main,
        ["--query", "SELECT 1", "--env-file", str(tmp_path / "missing")],
    )
    incomplete = tmp_path / ".env"
    incomplete.write_text("RXP_SNOWFLAKE_ACCOUNT=account\n", encoding="utf-8")
    missing_settings = runner.invoke(
        run_snowflake_query.main,
        ["--query", "SELECT 1", "--env-file", str(incomplete)],
    )
    assert missing_file.exit_code == 2
    assert missing_settings.exit_code == 2


def test_output_and_log_paths_must_remain_in_workspace(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    write_env(env_file)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    absolute_output = runner.invoke(
        run_snowflake_query.main,
        ["--query", "SELECT 1", "--env-file", str(env_file), "--output-parquet", "/tmp/result.parquet"],
    )
    wrong_suffix = runner.invoke(
        run_snowflake_query.main,
        ["--query", "SELECT 1", "--env-file", str(env_file), "--output-parquet", "data/result.csv"],
    )
    absolute_log = runner.invoke(
        run_snowflake_query.main,
        ["--query", "SELECT 1", "--env-file", str(env_file), "--sql-log-dir", "/tmp/logs"],
    )

    assert absolute_output.exit_code == 2
    assert wrong_suffix.exit_code == 2
    assert absolute_log.exit_code == 2


def test_query_file_and_all_options_execute(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    query_file = tmp_path / "query.sql"
    write_env(env_file)
    query_file.write_text("select 1 as value", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    statements: list[str] = []

    class Result:
        description = None

    class Connection:
        def execute(self, sql: str) -> Result:
            statements.append(sql)
            return Result()

        def close(self) -> None:
            pass

    class DuckDB:
        @staticmethod
        def connect(database: str) -> Connection:
            assert database == ":memory:"
            return Connection()

    monkeypatch.setitem(__import__("sys").modules, "duckdb", DuckDB())
    result = CliRunner().invoke(
        run_snowflake_query.main,
        [
            str(query_file),
            "--env-file",
            str(env_file),
            "--output-parquet",
            "data/result.parquet",
            "--sql-log-dir",
            "sql-log",
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(statements) == 1
    assert "COPY (SELECT * FROM snowflake_query(" in statements[0]
    assert (tmp_path / "sql-log").is_dir()
    assert len(list((tmp_path / "sql-log").glob("*.sql"))) == 1
    assert "Wrote Parquet file: data/result.parquet" in result.output
