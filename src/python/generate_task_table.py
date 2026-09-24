#!/usr/bin/env python3
"""Create the pharmacist task table in Snowflake."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import re

import click
from jinja2 import Environment, FileSystemLoader, StrictUndefined

TARGET_TABLE = "EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASKS"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIRECTORY = Path(__file__).resolve().parents[1] / "sql"
TEMPLATE_NAME = "create_task_table.sql.j2"
GENERATED_SQL_PATH = REPOSITORY_ROOT / "generated" / "generate_task_table.sql"
REQUIRED_SETTINGS = (
    "RXP_SNOWFLAKE_ACCOUNT",
    "RXP_SNOWFLAKE_USER",
    "RXP_SNOWFLAKE_DATABASE",
    "RXP_SNOWFLAKE_WAREHOUSE",
    "RXP_SNOWFLAKE_SCHEMA",
)
OPTIONAL_SETTINGS = ("RXP_SNOWFLAKE_ROLE",)
SAFE_SETTING = re.compile(r"^[A-Za-z0-9_.-]+$")
SAFE_USER = re.compile(r"^[A-Za-z0-9_.@-]+$")
ISO_DATE = click.DateTime(formats=["%Y-%m-%d"])


def parse_dotenv(path: Path) -> dict[str, str]:
    """Read the Snowflake settings used by this command without executing shell code."""
    values: dict[str, str] = {}
    allowed = set(REQUIRED_SETTINGS + OPTIONAL_SETTINGS)
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if not separator or key not in allowed:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if not value:
            continue
        validator = SAFE_USER if key == "RXP_SNOWFLAKE_USER" else SAFE_SETTING
        if not validator.fullmatch(value):
            raise ValueError(f"{path}:{line_number}: {key} contains unsupported characters")
        values[key] = value
    return values


def render_sql(start_date: date, end_date: date) -> str:
    environment = Environment(
        loader=FileSystemLoader(TEMPLATE_DIRECTORY),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )
    return environment.get_template(TEMPLATE_NAME).render(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )


def write_generated_sql(sql: str) -> None:
    GENERATED_SQL_PATH.parent.mkdir(parents=True, exist_ok=True)
    GENERATED_SQL_PATH.write_text(sql, encoding="utf-8")


def connect_to_snowflake(settings: dict[str, str]):
    import snowflake.connector

    connection_options = {
        "account": settings["RXP_SNOWFLAKE_ACCOUNT"],
        "user": settings["RXP_SNOWFLAKE_USER"],
        "database": settings["RXP_SNOWFLAKE_DATABASE"],
        "warehouse": settings["RXP_SNOWFLAKE_WAREHOUSE"],
        "schema": settings["RXP_SNOWFLAKE_SCHEMA"],
        "authenticator": "externalbrowser",
    }
    if role := settings.get("RXP_SNOWFLAKE_ROLE"):
        connection_options["role"] = role
    return snowflake.connector.connect(**connection_options)


@click.command()
@click.option("--start-date", required=True, type=ISO_DATE, help="Inclusive TASK_CREATED_AT date (YYYY-MM-DD).")
@click.option("--end-date", required=True, type=ISO_DATE, help="Exclusive TASK_CREATED_AT date (YYYY-MM-DD).")
@click.option("--env-file", type=click.Path(path_type=Path, dir_okay=False), default=Path(".env"), show_default=True)
@click.option("--dry-run", is_flag=True, help="Print rendered SQL without connecting to Snowflake.")
def main(start_date: datetime, end_date: datetime, env_file: Path, dry_run: bool) -> None:
    """Build MY_RXP_TASKS for a half-open TASK_CREATED_AT date window."""
    start = start_date.date()
    end = end_date.date()
    if start >= end:
        raise click.UsageError("--start-date must be earlier than --end-date")

    sql = render_sql(start, end)
    try:
        write_generated_sql(sql)
    except OSError as error:
        raise click.UsageError(f"could not write generated SQL: {error}") from error
    click.echo(f"Wrote generated SQL: {GENERATED_SQL_PATH}")

    if dry_run:
        click.echo(sql, nl=False)
        return

    if not env_file.is_file():
        raise click.UsageError(f"environment file not found: {env_file}")
    try:
        settings = parse_dotenv(env_file)
        missing = [key for key in REQUIRED_SETTINGS if key not in settings]
        if missing:
            raise ValueError("missing required settings: " + ", ".join(missing))
    except (OSError, ValueError) as error:
        raise click.UsageError(str(error)) from error

    connection = connect_to_snowflake(settings)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(sql)
            cursor.execute(f"SELECT COUNT(*) FROM {TARGET_TABLE}")
            row_count = cursor.fetchone()[0]
        finally:
            cursor.close()
    finally:
        connection.close()

    click.echo(f"Created {TARGET_TABLE} with {row_count:,} rows.")


if __name__ == "__main__":
    main()
