#!/usr/bin/env python3
"""Create a task-intersection inspection table in Snowflake."""

from __future__ import annotations

from pathlib import Path

import click
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from src.python.generate_task_table import (
    REQUIRED_SETTINGS,
    connect_to_snowflake,
    parse_dotenv,
)

TARGET_TABLE = "EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASK_INTERSECTIONS"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIRECTORY = Path(__file__).resolve().parents[1] / "sql"
TEMPLATE_NAME = "create_task_intersection_table.sql.j2"
GENERATED_SQL_PATH = REPOSITORY_ROOT / "generated" / "generate_task_intersection_table.sql"


def render_sql(user_id: int) -> str:
    environment = Environment(
        loader=FileSystemLoader(TEMPLATE_DIRECTORY),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )
    return environment.get_template(TEMPLATE_NAME).render(user_id=user_id)


def write_generated_sql(sql: str) -> None:
    GENERATED_SQL_PATH.parent.mkdir(parents=True, exist_ok=True)
    GENERATED_SQL_PATH.write_text(sql, encoding="utf-8")


@click.command()
@click.option("--user-id", required=True, type=click.IntRange(min=1), help="USER_ID to inspect.")
@click.option(
    "--env-file",
    type=click.Path(path_type=Path, dir_okay=False),
    default=Path(".env"),
    show_default=True,
)
@click.option("--dry-run", is_flag=True, help="Print rendered SQL without connecting to Snowflake.")
def main(user_id: int, env_file: Path, dry_run: bool) -> None:
    """Build MY_RXP_TASK_INTERSECTIONS for one user."""
    sql = render_sql(user_id)
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

    click.echo(f"Created {TARGET_TABLE} with {row_count:,} rows for USER_ID {user_id}.")


if __name__ == "__main__":
    main()
