# Running Make Targets

Run Make commands from the repository root:

```bash
cd /path/to/rxp-pharmacist-task-grouping-analysis
make <target>
```

Each target performs a specific repository task. As more targets are added, use the target name shown in the `Makefile` in place of `<target>`.

## Initial setup

Install and synchronize the project dependencies:

```bash
make setup
```

This project uses `uv` and the repository's `.venv`; global Python packages are not required.

## Generate the pharmacist task table

Before running the generator, create a local `.env` containing the Snowflake connection settings:

```dotenv
RXP_SNOWFLAKE_ACCOUNT=your-account
RXP_SNOWFLAKE_USER=your-user
RXP_SNOWFLAKE_DATABASE=EDLDB_DEV
RXP_SNOWFLAKE_WAREHOUSE=your-warehouse
RXP_SNOWFLAKE_SCHEMA=PET_HEALTH_ANALYTICS_SANDBOX
RXP_SNOWFLAKE_ROLE=your-role
```

`RXP_SNOWFLAKE_ROLE` is optional. Do not commit `.env` or credentials.

Create or replace `EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASKS` with the default date window, from February 1, 2026 through August 1, 2026 (exclusive):

```bash
make generate-task-table
```

The command opens a browser for Snowflake authentication. Complete the sign-in flow and return to the terminal while the table is built.

Each run writes the rendered statement to `generated/generate_task_table.sql` before connecting to Snowflake. The `generated` directory is ignored by Git because its contents can be reproduced from the template and date arguments.

Override either date by passing Make variables. The start date is inclusive and the end date is exclusive:

```bash
make generate-task-table START_DATE=2026-03-01 END_DATE=2026-04-01
```

Dates must use `YYYY-MM-DD`, and `START_DATE` must be earlier than `END_DATE`.

## Create the causal diagram

Render `src/mermaid/DUR.mmd` as a 2400×1600 PNG:

```bash
make create-causal-diagram
```

The target runs the Dockerized Mermaid CLI from `minlag/mermaid-cli`; a local Node.js or Mermaid installation is not required. It mounts the repository at `/mermaid` inside the container and writes the result to `outputs/charts/DUR_detailed.png`.

Docker must be installed and its daemon must be running. The image is downloaded automatically if it is not already available locally.

The source and output paths can be overridden when another Mermaid figure is added:

```bash
make create-causal-diagram \
  CAUSAL_DIAGRAM_SOURCE=src/mermaid/another-diagram.mmd \
  CAUSAL_DIAGRAM_OUTPUT=outputs/charts/another-diagram.png
```

## Run tests

Run the repository test suite with:

```bash
make test
```

## Available targets

The current targets are:

| Target | Purpose |
| --- | --- |
| `setup` | Synchronize dependencies with `uv`. |
| `generate-task-table` | Create or replace the pharmacist task table in Snowflake. |
| `create-causal-diagram` | Render the Mermaid causal diagram as a PNG with Docker. |
| `test` | Run the test suite. |

Refer to the root `Makefile` for the authoritative target definitions and defaults.
