#!/usr/bin/env python3
"""Drop the generated pharmacist task table from Snowflake."""

from __future__ import annotations

from pathlib import Path

import click

from .generate_task_table import REQUIRED_SETTINGS, TARGET_TABLE, connect_to_snowflake, parse_dotenv

DROP_SQL = f"DROP TABLE IF EXISTS {TARGET_TABLE}"


@click.command()
@click.option(
    "--env-file",
    type=click.Path(path_type=Path, dir_okay=False),
    default=Path(".env"),
    show_default=True,
    help="Local Snowflake connection settings.",
)
def main(env_file: Path) -> None:
    """Drop MY_RXP_TASKS if it exists."""
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
            cursor.execute(DROP_SQL)
        finally:
            cursor.close()
    finally:
        connection.close()

    click.echo(f"Drop command completed for {TARGET_TABLE}.")


if __name__ == "__main__":
    main()
