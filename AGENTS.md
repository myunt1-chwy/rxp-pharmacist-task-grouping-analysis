## Agent Instructions
Keep changes small, boring, and reversible. Prefer existing package patterns over new abstractions
## Development Loop
- Read before editing. Use rg/sed for fast context and avoid broad rewrites.
- Run make setup when dependencies or hooks are missing. Do not use global Python tools for repo commands; the project sandbox is .venv.
- Keep generated output out of Git. dist/, build/, caches, .sandbox/, .uv/, .venv, and .env are ignored.
## Commits And Branches
- Work on short-lived feature branches, not trunk.
- Use Conventional Commits: feat: for minor, fix:/perf: for patch or hotfix, and ! or BREAKING CHANGE: for major.
## Repo Structure
- Any data we download should be put under the data directory
- Any charts/plots should be under the outputs/charts directory. Export data used to markdown tables for further analysis if required.
- Any tables should be in markdown and saved under outputs/tables directory
- Any PDF reports should be under   outputs/reports/pdf
- Any Word reports should be under  outputs/reports/xlsx
- Any Mardown reports should be under outputs/reports/md
## Preferences
- For charts; use the altair package in python and generate the outputs as png by default.
