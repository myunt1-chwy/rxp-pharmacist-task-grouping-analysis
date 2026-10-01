#!/usr/bin/env python3
"""Create the valid DUR task sequence table in Snowflake."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import click
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .generate_task_table import REQUIRED_SETTINGS, connect_to_snowflake, parse_dotenv

TARGET_TABLE = "EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_VALID_DUR_TASKS"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIRECTORY = Path(__file__).resolve().parents[1] / "sql"
TEMPLATE_NAME = "create_valid_dur_task_table.sql.j2"
GENERATED_SQL_PATH = REPOSITORY_ROOT / "generated" / "generate_valid_dur_task_table.sql"
DEFAULT_START_DATE = date(2026, 2, 1)
DEFAULT_END_DATE = date(2026, 8, 1)
ISO_DATE = click.DateTime(formats=["%Y-%m-%d"])


def render_sql(
    start_date: date = DEFAULT_START_DATE,
    end_date: date = DEFAULT_END_DATE,
) -> str:
    if start_date >= end_date:
        raise ValueError("start_date must be earlier than end_date")
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


@click.command()
@click.option(
    "--start-date",
    type=ISO_DATE,
    default=DEFAULT_START_DATE.isoformat(),
    show_default=True,
    help="Inclusive TASK_CREATED_AT and correction-change date (YYYY-MM-DD).",
)
@click.option(
    "--end-date",
    type=ISO_DATE,
    default=DEFAULT_END_DATE.isoformat(),
    show_default=True,
    help="Exclusive TASK_CREATED_AT and correction-change date (YYYY-MM-DD).",
)
@click.option(
    "--env-file",
    type=click.Path(path_type=Path, dir_okay=False),
    default=Path(".env"),
    show_default=True,
)
@click.option("--dry-run", is_flag=True, help="Print rendered SQL without connecting to Snowflake.")
def main(
    start_date: datetime,
    end_date: datetime,
    env_file: Path,
    dry_run: bool,
) -> None:
    """Build MY_RXP_VALID_DUR_TASKS from the task and product tables."""
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
