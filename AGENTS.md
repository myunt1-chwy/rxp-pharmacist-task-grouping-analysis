## Agent Instructions
Keep changes small, boring, and reversible. Prefer existing package patterns over new abstractions
## Development Loop
- Log what is done in LOG.org
- TODO.org contains the tasks that need to get done.
- Once a task is done, stop so that the user can check the work.
- Read before editing. Use rg/sed for fast context and avoid broad rewrites.
- Run make setup when dependencies or hooks are missing. Do not use global Python tools for repo commands; the project sandbox is .venv.
- Keep generated output out of Git. dist/, build/, caches, .sandbox/, .uv/, .venv, and .env are ignored.
## Duration Models
- For each new model with a SAME_PRECEDING effect, retain PROCESS_START_TIME and use src/python/model_counterfactual.py to report original and adjusted duration totals by user-day, cohort, and overall. Keep the first retained task per user-day unchanged; convert the fitted effect to seconds using that model's outcome scale.
## Commits And Branches
- Work on short-lived feature branches, not trunk.
- Use Conventional Commits: feat: for minor, fix:/perf: for patch or hotfix, and ! or BREAKING CHANGE: for major.
- After a task is done ask for approval to commit and make a commit.
## Repo Structure
- Any data we download should be put under the data directory
- Any charts/plots should be under the outputs/charts directory. Export data used to markdown tables for further analysis if required.
- Any tables should be in markdown and saved under outputs/tables directory
- Any PDF reports should be under   outputs/reports/pdf
- Any Word reports should be under  outputs/reports/xlsx
- Any Mardown reports should be under outputs/reports/md
## Preferences
- For charts, use Altair in Python and export PNGs with transparent backgrounds by default.
