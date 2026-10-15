#!/usr/bin/env python3
"""Fit test-model-final with log duration and crossed random intercepts."""

from __future__ import annotations

import os
from pathlib import Path

import click
import numpy as np
import pandas as pd

from . import fit_cohort_user_date_model as fixed_user
from . import fit_mc3_coh_pettype_final_model as core
from . import fit_test_model as base_model
from . import fit_test_model_exp as exp_model
from .model_counterfactual import CounterfactualTotals, same_preceding_totals

ROOT = Path(__file__).resolve().parents[2]
NAME = "test-model-final"
STEM = "test_model_final"
MODEL_PATH = ROOT / "data" / f"{STEM}_log_data.parquet"
USER_DATA_PATH = ROOT / "data" / f"{STEM}_user_effects.parquet"
DATE_DATA_PATH = ROOT / "data" / f"{STEM}_date_effects.parquet"
PARENT_DATA_PATH = ROOT / "data" / f"{STEM}_parent_effects.parquet"
FIXED_TABLE_PATH = ROOT / "outputs" / "tables" / f"{STEM}_fixed_effects.md"
USER_TABLE_PATH = ROOT / "outputs" / "tables" / f"{STEM}_user_effects.md"
DATE_TABLE_PATH = ROOT / "outputs" / "tables" / f"{STEM}_date_effects.md"
PARENT_TABLE_PATH = ROOT / "outputs" / "tables" / f"{STEM}_parent_effects.md"
COUNTERFACTUAL_DAY_TABLE_PATH = ROOT / "outputs" / "tables" / f"{STEM}_counterfactual_user_day.md"
COUNTERFACTUAL_COHORT_DAY_TABLE_PATH = ROOT / "outputs" / "tables" / f"{STEM}_counterfactual_user_day_cohort.md"
COUNTERFACTUAL_COHORT_TABLE_PATH = ROOT / "outputs" / "tables" / f"{STEM}_counterfactual_cohort.md"
DUR_POPULATION_TABLE_PATH = ROOT / "outputs" / "tables" / f"{STEM}_dur_population_totals.md"
ALL_DUR_SQL_PATH = ROOT / "src" / "sql" / "total_dur_processing_time.sql"
BELOW_P95_DUR_SQL_PATH = ROOT / "src" / "sql" / "total_dur_below_model_p95.sql"
VALID_DUR_SQL_PATH = ROOT / "src" / "sql" / "total_valid_dur_processing_time.sql"
VALID_DUR_P95_BREAKDOWN_SQL_PATH = ROOT / "src" / "sql" / "valid_dur_model_p95_breakdown.sql"
HANDOFF_TYPE_SQL_PATH = ROOT / "src" / "sql" / "my_rxp_tasks_handoff_type.sql"
INTERSECTION_SQL_PATH = ROOT / "src" / "sql" / "dur_null_handoff_processing_time_by_intersection.sql"
REPORT_PATH = ROOT / "outputs" / "reports" / "md" / f"{NAME}.md"
CHART_DIR = ROOT / "outputs" / "charts" / NAME
USER_QQ_PATH = CHART_DIR / "user_random_intercepts_qq.png"
DATE_QQ_PATH = CHART_DIR / "date_random_intercepts_qq.png"
PARENT_QQ_PATH = CHART_DIR / "parent_random_intercepts_qq.png"
USER_DENSITY_PATH = CHART_DIR / "user_random_intercepts_density.png"
DATE_DENSITY_PATH = CHART_DIR / "date_random_intercepts_density.png"
PARENT_DENSITY_PATH = CHART_DIR / "parent_random_intercepts_density.png"
RESIDUAL_QQ_PATH = CHART_DIR / "conditional_residuals_qq.png"
PREDICTION_PATH = CHART_DIR / "predicted_vs_log_actual.png"

CELL_COLUMNS = base_model.CELL_COLUMNS
RANDOM_COLUMNS = ("user_id", "d", "parent_part_number")
CATEGORICAL_EFFECTS = base_model.CATEGORICAL_EFFECTS
PHARMACIST_COST_PER_HOUR = 90.0
USD = "$"
ALL_DUR_TASKS = 4_128_486
ALL_DUR_SECONDS = 212_095_618
ALL_DUR_NULL_RAW_DURATIONS = 19_550
ALL_DUR_FIRST_DATE = "2026-02-01"
ALL_DUR_LAST_DATE = "2026-08-04"
ALL_DUR_QUERY_DATE = "2026-10-14"
BELOW_P95_DUR_TASKS = 3_905_692
BELOW_P95_DUR_SECONDS = 104_384_954
BELOW_P95_CUTOFF_SECONDS = 156.608019
VALID_DUR_TASKS = 3_614_021
VALID_DUR_SECONDS = 178_089_090
VALID_DUR_AT_OR_ABOVE_P95_TASKS = 180_803
VALID_DUR_AT_OR_ABOVE_P95_SECONDS = 88_958_419
NULL_HANDOFF_DUR_TASKS = 4_000_758
NULL_HANDOFF_DUR_SECONDS = 197_557_538
HANDOFF_TYPE_DUR_TOTALS = (
    ("NULL", NULL_HANDOFF_DUR_TASKS, NULL_HANDOFF_DUR_SECONDS),
    ("PHARMACIST_FOLLOW_UP", 117_503, 13_334_300),
    ("TECHNICIAN_FOLLOW_UP", 6_736, 820_191),
    ("LEAD_FOLLOW_UP", 3_489, 383_589),
)
INTERSECTION_DUR_TOTALS = (
    ("Intersecting", 332_599, 16_046_580),
    ("Not intersecting", 3_668_159, 181_510_958),
)


def write_counterfactual_tables(totals: CounterfactualTotals) -> None:
    """Save the user-day and user-day-cohort aggregates as Markdown."""
    start_date = totals.by_user_day["d"].min()
    end_date = totals.by_user_day["d"].max()
    for path, frame, columns in (
        (
            COUNTERFACTUAL_DAY_TABLE_PATH,
            totals.by_user_day,
            ("user_id", "d", "tasks", "adjusted_tasks", "original_seconds", "adjusted_seconds"),
        ),
        (
            COUNTERFACTUAL_COHORT_DAY_TABLE_PATH,
            totals.by_user_day_cohort,
            ("user_id", "d", "coh", "tasks", "adjusted_tasks", "original_seconds", "adjusted_seconds"),
        ),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# {NAME} counterfactual: {' / '.join(columns[:3])}\n",
            "| " + " | ".join(columns) + " |",
            "| " + " | ".join("---:" if column in ("tasks", "adjusted_tasks", "original_seconds", "adjusted_seconds") else "---" for column in columns) + " |",
        ]
        for row in frame.loc[:, columns].itertuples(index=False, name=None):
            values = [
                f"{value:,.3f}" if column in ("original_seconds", "adjusted_seconds")
                else f"{value:,}" if column in ("tasks", "adjusted_tasks")
                else str(value)
                for column, value in zip(columns, row, strict=True)
            ]
            lines.append("| " + " | ".join(values) + " |")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cohort_lines = [
        f"# {NAME} counterfactual by cohort\n",
        f"Retained process dates: {start_date} through {end_date}. "
        f"Labor value assumes {USD}{PHARMACIST_COST_PER_HOUR:,.0f} per pharmacist hour.\n",
        "| Cohort | Tasks | Adjusted tasks | Original seconds | Adjusted seconds | Difference seconds | Change | Labor value |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in totals.by_cohort.itertuples(index=False):
        difference = row.original_seconds - row.adjusted_seconds
        cohort_lines.append(
            f"| {row.coh} | {row.tasks:,} | {row.adjusted_tasks:,} | "
            f"{row.original_seconds:,.3f} | {row.adjusted_seconds:,.3f} | "
            f"{difference:,.3f} | {-100 * difference / row.original_seconds:.2f}% | "
            f"{USD}{difference / 3600 * PHARMACIST_COST_PER_HOUR:,.2f} |"
        )
    COUNTERFACTUAL_COHORT_TABLE_PATH.write_text(
        "\n".join(cohort_lines) + "\n", encoding="utf-8"
    )


def write_report(
    design: core.FixedEffectDesign,
    result: core.FinalModelResult,
    counterfactual: CounterfactualTotals | None = None,
) -> Path:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame = design.frame
    intercept = base_model.global_intercept(design, result)
    preceding = result.fixed_effects.set_index("term").loc["SAME_PRECEDING"]
    percent_change = 100.0 * np.expm1(preceding["estimate"])
    percent_ci_lower = 100.0 * np.expm1(preceding["ci_lower"])
    percent_ci_upper = 100.0 * np.expm1(preceding["ci_upper"])

    def link(path: Path) -> str:
        return os.path.relpath(path, REPORT_PATH.parent)

    handoff_type_rows = "\n".join(
        f"| `{handoff_type}` | {tasks:,} | {seconds:,} | {seconds / 3600:,.2f} |"
        for handoff_type, tasks, seconds in HANDOFF_TYPE_DUR_TOTALS
    )
    intersection_rows = "\n".join(
        f"| {status} | {tasks:,} | {seconds:,} | {seconds / 3600:,.2f} |"
        for status, tasks, seconds in INTERSECTION_DUR_TOTALS
    )

    counterfactual_section = ""
    if counterfactual is not None:
        non_intersecting_tasks, non_intersecting_seconds = INTERSECTION_DUR_TOTALS[1][1:]
        other_excluded_tasks = non_intersecting_tasks - VALID_DUR_TASKS
        other_excluded_seconds = non_intersecting_seconds - VALID_DUR_SECONDS
        dur_population_table = f"""| DUR population | Number of DURs | Total processing time (seconds) | Hours |
|---|---:|---:|---:|
| Valid DURs below {BELOW_P95_CUTOFF_SECONDS:.6f} seconds | {VALID_DUR_TASKS - VALID_DUR_AT_OR_ABOVE_P95_TASKS:,} | {VALID_DUR_SECONDS - VALID_DUR_AT_OR_ABOVE_P95_SECONDS:,} | {(VALID_DUR_SECONDS - VALID_DUR_AT_OR_ABOVE_P95_SECONDS) / 3600:,.2f} |
| Valid DURs at or above {BELOW_P95_CUTOFF_SECONDS:.6f} seconds | {VALID_DUR_AT_OR_ABOVE_P95_TASKS:,} | {VALID_DUR_AT_OR_ABOVE_P95_SECONDS:,} | {VALID_DUR_AT_OR_ABOVE_P95_SECONDS / 3600:,.2f} |
| **All valid DURs** in `MY_RXP_VALID_DUR_TASKS` | **{VALID_DUR_TASKS:,}** | **{VALID_DUR_SECONDS:,}** | **{VALID_DUR_SECONDS / 3600:,.2f}** |
| Other non-intersecting DURs excluded by validity checks | {other_excluded_tasks:,} | {other_excluded_seconds:,} | {other_excluded_seconds / 3600:,.2f} |
| **All non-intersecting DURs with NULL handoff type** | **{non_intersecting_tasks:,}** | **{non_intersecting_seconds:,}** | **{non_intersecting_seconds / 3600:,.2f}** |
| All DURs below {BELOW_P95_CUTOFF_SECONDS:.6f} seconds in `MY_RXP_TASKS` | {BELOW_P95_DUR_TASKS:,} | {BELOW_P95_DUR_SECONDS:,} | {BELOW_P95_DUR_SECONDS / 3600:,.2f} |
| **All DURs** in `MY_RXP_TASKS` | **{ALL_DUR_TASKS:,}** | **{ALL_DUR_SECONDS:,}** | **{ALL_DUR_SECONDS / 3600:,.2f}** |"""
        dur_population_explanation = f"""The first two rows partition the valid-DUR table at the model cutoff;
the valid tasks below it are the {VALID_DUR_TASKS - VALID_DUR_AT_OR_ABOVE_P95_TASKS:,}-task model sample.
The {other_excluded_tasks:,} other non-intersecting tasks and {other_excluded_seconds:,} seconds are the difference
between the null-handoff non-intersecting population
and the valid-DUR table; the available aggregate does not
separate their individual exclusion reasons. The full-table
below-cutoff row also includes {BELOW_P95_DUR_TASKS - (VALID_DUR_TASKS - VALID_DUR_AT_OR_ABOVE_P95_TASKS):,} other DUR tasks totaling
{BELOW_P95_DUR_SECONDS - (VALID_DUR_SECONDS - VALID_DUR_AT_OR_ABOVE_P95_SECONDS):,} seconds that did not meet the valid-DUR criteria."""
        DUR_POPULATION_TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        DUR_POPULATION_TABLE_PATH.write_text(
            f"# DUR population totals\n\n{dur_population_table}\n\n"
            f"{dur_population_explanation}\n\n"
            f"[Null-handoff intersection source query]"
            f"({os.path.relpath(INTERSECTION_SQL_PATH, DUR_POPULATION_TABLE_PATH.parent)})\n",
            encoding="utf-8",
        )
        start_date = counterfactual.by_user_day["d"].min()
        end_date = counterfactual.by_user_day["d"].max()
        original = counterfactual.original_seconds
        adjusted = counterfactual.adjusted_seconds
        saved = original - adjusted
        cohort_rows = []
        for row in counterfactual.by_cohort.itertuples(index=False):
            cohort_saved = row.original_seconds - row.adjusted_seconds
            cohort_rows.append(
                f"| {row.coh} | {row.tasks:,} | {row.adjusted_tasks:,} | "
                f"{row.original_seconds:,.1f} | {row.adjusted_seconds:,.1f} | "
                f"{cohort_saved:,.1f} | {-100 * cohort_saved / row.original_seconds:.2f}% | "
                f"{USD}{cohort_saved / 3600 * PHARMACIST_COST_PER_HOUR:,.2f} |"
            )
        counterfactual_section = f"""## All-eligible same-preceding counterfactual

{dur_population_table}

These are imputed processing durations from the [all-DUR]({link(ALL_DUR_SQL_PATH)}),
[below-cutoff]({link(BELOW_P95_DUR_SQL_PATH)}), and
[valid-DUR]({link(VALID_DUR_SQL_PATH)}) read-only queries on {ALL_DUR_QUERY_DATE}.
The cutoff comes from the model's eligible sample and is applied here to all
DURs in `MY_RXP_TASKS` as well as to the valid-DUR breakdown.
The [valid-DUR cutoff breakdown]({link(VALID_DUR_P95_BREAKDOWN_SQL_PATH)})
shows why the totals differ. {dur_population_explanation}

Within each user, process date, and cohort, all retained tasks are ordered by
PROCESS_START_TIME (TASK_ID resolves an exact timestamp tie). The first task
in each list keeps its original duration, whether SAME_PRECEDING is 0 or 1.
Later tasks with SAME_PRECEDING = 0 receive the fitted duration ratio
exp(beta_P) = {counterfactual.duration_ratio:.6f}; tasks already marked 1 are
unchanged. This is an arithmetic scenario using observed durations and a
single fitted association, not a causal estimate or a prediction of how task
ordering would change.

| Quantity | Value |
|---|---:|
| First retained process date | {start_date} |
| Last retained process date | {end_date} |
| User-day-cohorts / unchanged first tasks | {counterfactual.first_tasks:,} |
| Additional tasks adjusted | {counterfactual.adjusted_tasks:,} |
| Original total (seconds) | {original:,.1f} |
| Adjusted total (seconds) | {adjusted:,.1f} |
| Difference (hours) | {saved / 3600:,.1f} |
| Change from original | {-100 * saved / original:.2f}% |
| Pharmacist cost per hour | {USD}{PHARMACIST_COST_PER_HOUR:,.2f} |
| Implied labor value | {USD}{saved / 3600 * PHARMACIST_COST_PER_HOUR:,.2f} |

| Cohort | Tasks | Adjusted tasks | Original seconds | Adjusted seconds | Difference seconds | Change | Labor value |
|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(cohort_rows)}

The [cohort totals]({link(COUNTERFACTUAL_COHORT_TABLE_PATH)}),
[user-day totals]({link(COUNTERFACTUAL_DAY_TABLE_PATH)}), and
[user-day-cohort totals]({link(COUNTERFACTUAL_COHORT_DAY_TABLE_PATH)})
give the underlying aggregates.

The implied labor value is
({original:,.1f} - {adjusted:,.1f}) / 3,600 × {USD}{PHARMACIST_COST_PER_HOUR:,.2f}
= {USD}{saved / 3600 * PHARMACIST_COST_PER_HOUR:,.2f}.
Realizing cash savings would depend on staffing decisions.

"""

    all_dur_section = f"""## All DUR task processing time

A read-only query of all TASK_TYPE = 'DUR' rows in
EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASKS on
{ALL_DUR_QUERY_DATE} returned {ALL_DUR_TASKS:,} tasks and
{ALL_DUR_SECONDS:,} imputed processing seconds
({ALL_DUR_SECONDS / 3600:,.2f} hours). Their process dates span
{ALL_DUR_FIRST_DATE} through {ALL_DUR_LAST_DATE}.
The imputed duration is COALESCE(DWELL_IN_PROGRESS_TO_CLOSED_SECONDS, 1);
{ALL_DUR_NULL_RAW_DURATIONS:,} DUR rows have a null raw duration.
This full-table total includes tasks outside the filtered model sample.

### Handoff type distribution for all DUR tasks

| Handoff type | DUR tasks | Processing time (seconds) | Hours |
|---|---:|---:|---:|
{handoff_type_rows}
| **All DURs** | **{ALL_DUR_TASKS:,}** | **{ALL_DUR_SECONDS:,}** | **{ALL_DUR_SECONDS / 3600:,.2f}** |

The `NULL` row includes tasks without a handoff type. No DUR row has a blank
handoff type. These totals
come from the [read-only handoff-type query]({link(HANDOFF_TYPE_SQL_PATH)}).
The valid-DUR sample requires `HANDOFF_TYPE IS NULL`.

### Intersection status for DUR tasks with NULL handoff type

| Intersection status | DUR tasks | Processing time (seconds) | Hours |
|---|---:|---:|---:|
{intersection_rows}
| **All DURs with NULL handoff type** | **{NULL_HANDOFF_DUR_TASKS:,}** | **{NULL_HANDOFF_DUR_SECONDS:,}** | **{NULL_HANDOFF_DUR_SECONDS / 3600:,.2f}** |

An intersecting DUR has `N_INTERSECTING_TASKS > 0` in
`MY_RXP_TASKS_WITH_SEQUENCE`: its processing interval overlaps another task
for the same user. The [read-only intersection query]({link(INTERSECTION_SQL_PATH)})
uses DUR tasks with `HANDOFF_TYPE IS NULL`, without the model's other validity
or duration-cutoff filters. Every such DUR task had a sequence record.

To regenerate the aggregate, run the
[read-only SQL]({link(ALL_DUR_SQL_PATH)}) from the repository root:

    .venv/bin/python skills/rxp-sql/scripts/run_snowflake_query.py src/sql/total_dur_processing_time.sql

"""

    n_tasks = len(frame)
    indicator_rows = []
    for column, label in (
        ("same_preceding", "SAME_PRECEDING"),
        ("same_following", "SAME_FOLLOWING"),
    ):
        counts = frame[column].value_counts()
        for value in (0, 1):
            count = int(counts.get(value, 0))
            indicator_rows.append(
                f"| {label} | {value} | {count:,} | {count / n_tasks:.2%} |"
            )

    REPORT_PATH.write_text(
        rf"""# test-model-final

This model keeps the natural log outcome, no-cell specification, fixed effects,
and user/date random intercepts of [test-model-exp]({link(exp_model.REPORT_PATH)}),
and adds a parent-part-number random intercept.
It changes the sequence indicators from cohort-and-pet batches to cohort-only
batches.

## Sample and indicators

The source is `{core.SOURCE_TABLE}` through the
[cohort-only extract]({link(fixed_user.RAW_PATH)}). Missing parent part numbers
form a `<Missing>` level. The strict global
P95 filter retains {n_tasks:,} positive-duration tasks. For within-batch task
position $S_i=$ `COHORT_SEQN` and batch length $L_i=$
`COHORT_BATCH_LEN`, `SAME_PRECEDING` is
$P_i=\mathbf{{1}}(L_i>1\land S_i>1)$ and `SAME_FOLLOWING` is
$F_i=\mathbf{{1}}(L_i>1\land S_i<L_i)$. `HAS_CORRECTION` is
$C_i=\mathbf{{1}}(N_i>0)$ for correction count $N_i$.

| Indicator | Value | Tasks | Percent of retained tasks |
|---|---:|---:|---:|
{chr(10).join(indicator_rows)}

## Model formula

With cohort $c_i$, pet type $p_i$, weekday $w_i$, approval channel $a_i$,
prescription source $s_i$, user $u(i)$, date $d(i)$, and parent part number $r(i)$:

$$
\log(Y_i)=\alpha+\beta_P P_i+\beta_F F_i+\beta_C C_i
 +\gamma_{{c_i}}+\delta_{{p_i}}+\theta_{{w_i}}
 +\phi_{{a_i}}+\psi_{{s_i}}+b_{{u(i)}}+h_{{d(i)}}+q_{{r(i)}}+\epsilon_i.
$$

There are no fixed cells. Cohort, pet type, weekday, approval channel, and
prescription source are additive fixed effects. Their reference levels are
`{design.references['coh']}`, `{design.references['pettype']}`, Sunday,
`{design.references['approval_channel']}`, and
`{design.references['prescription_source']}`, respectively. User, date, and
parent part number have independent random intercepts:
$b_u\sim N(0,\sigma_u^2)$, $h_d\sim N(0,\sigma_d^2)$, and
$q_r\sim N(0,\sigma_r^2)$, independently of
$\epsilon_i\sim N(0,\sigma_e^2)$. REML estimates the model. Fixed-effect
intervals and p-values use normal Wald approximations; random SD intervals
use observed information on the log-SD scale, and the residual SD interval
uses a chi-square approximation. The global intercept
$\widehat{{\alpha}}={intercept:.6f}$ applies to reference categories, zero
indicator values, and zero random intercepts.

## Sample and fit

| Quantity | Value |
|---|---:|
| Tasks | {result.n_observations:,} |
| Fixed cells | {result.n_cells:,} |
| Global intercept (log seconds) | {intercept:.6f} |
| Users | {result.n_users:,} |
| Dates | {result.n_dates:,} |
| Parent part numbers | {result.n_parent_parts:,} |
| Global approximate P95 cutoff (seconds) | {frame['p95_seconds'].iloc[0]:.6f} |
| Conditional R-squared (log scale) | {result.conditional_r_squared:.6f} |
| Conditional RMSE (log seconds) | {result.conditional_rmse:.6f} |
| REML negative log-likelihood | {result.reml_nll:.6f} |
| Converged | {result.converged} |

## Fixed effects

{core._fixed_effects_markdown(result.fixed_effects)}

The `SAME_PRECEDING` estimate corresponds to an adjusted duration ratio of
$\exp(\widehat{{\beta}}_P)={np.exp(preceding['estimate']):.6f}$, or
{percent_change:.2f}% (95% CI [{percent_ci_lower:.2f}%, {percent_ci_upper:.2f}%]).
This is a conditional log-scale association, not a causal effect.

{all_dur_section}## Variance components

| Component | SD (log scale) | Approximate 95% CI |
|---|---:|---:|
| User random intercept | {result.random_sds[0]:.6f} | [{result.random_sd_cis[0][0]:.6f}, {result.random_sd_cis[0][1]:.6f}] |
| Date random intercept | {result.random_sds[1]:.6f} | [{result.random_sd_cis[1][0]:.6f}, {result.random_sd_cis[1][1]:.6f}] |
| Parent-part-number random intercept | {result.random_sds[2]:.6f} | [{result.random_sd_cis[2][0]:.6f}, {result.random_sd_cis[2][1]:.6f}] |
| Residual | {result.residual_sd:.6f} | [{result.residual_sd_ci[0]:.6f}, {result.residual_sd_ci[1]:.6f}] |

## Interpretation and assumptions

The model assumes additive effects, independent normally distributed user,
date, and parent-part-number intercepts and residuals, and a common log-scale
residual variance. Unmodeled user, date, and parent-part differences must be
unrelated to the included predictors after adjustment for the random-intercept
interpretation. This
remains an observational association. It is not directly comparable to the
paired t-test, which uses a different task population and preceding-task rule.
Coefficients and fit measures on the log scale are not directly comparable to
those on the Box-Cox scale in `test-model`. This model and `test-model-exp`
also estimate different sequence associations because their preceding and
following indicators use different batch definitions.

## Diagnostics and artifacts

The date random-intercept Q–Q plot departs strongly from a normal line, and
the date intercept density shows a second positive peak. The residual Q–Q
plot curves in both tails. The parent-part-number Q–Q plot is broadly aligned
with the normal line except for a few tail values. The reported confidence
intervals are model-based approximations under the stated distributional
assumptions.

![User random-intercept Q–Q plot]({link(USER_QQ_PATH)})

![Date random-intercept Q–Q plot]({link(DATE_QQ_PATH)})

Each density plot gives one fitted intercept equal weight per user, date, or
parent part number; the dashed vertical line marks zero.

![User random-intercept density]({link(USER_DENSITY_PATH)})

![Date random-intercept density]({link(DATE_DENSITY_PATH)})

![Parent-part-number random-intercept Q–Q plot]({link(PARENT_QQ_PATH)})

![Parent-part-number random-intercept density]({link(PARENT_DENSITY_PATH)})

![Conditional residual Q–Q plot]({link(RESIDUAL_QQ_PATH)})

![Predicted versus outcome]({link(PREDICTION_PATH)})

- [Shared generated SQL]({link(fixed_user.SQL_PATH)})
- [Shared raw task data]({link(fixed_user.RAW_PATH)})
- [Log-transformed model data]({link(MODEL_PATH)})
- [Fixed-effect table]({link(FIXED_TABLE_PATH)})
- [User-effect table]({link(USER_TABLE_PATH)})
- [Date-effect table]({link(DATE_TABLE_PATH)})
- [Parent-part-number-effect table]({link(PARENT_TABLE_PATH)})
- [User-effect data]({link(USER_DATA_PATH)})
- [Date-effect data]({link(DATE_DATA_PATH)})
- [Parent-part-number-effect data]({link(PARENT_DATA_PATH)})

{counterfactual_section.rstrip()}
""",
        encoding="utf-8",
    )
    return REPORT_PATH


@click.command()
@click.option("--refresh-extract", is_flag=True, help="Refresh the cohort-only cache with process start times.")
@click.option("--env-file", type=click.Path(path_type=Path, dir_okay=False), default=Path(".env"))
def main(refresh_extract: bool, env_file: Path) -> None:
    """Fit test-model-final from the cohort-only raw task cache."""
    try:
        if refresh_extract:
            if not env_file.is_file():
                raise ValueError(f"environment file not found: {env_file}")
            settings = fixed_user.parse_dotenv(env_file)
            missing = [key for key in fixed_user.REQUIRED_SETTINGS if key not in settings]
            if missing:
                raise ValueError("missing required settings: " + ", ".join(missing))
            sql = fixed_user.render_sql()
            fixed_user.SQL_PATH.parent.mkdir(parents=True, exist_ok=True)
            fixed_user.SQL_PATH.write_text(sql.rstrip() + "\n", encoding="utf-8")
            core.fetch_to_parquet(settings, sql, fixed_user.RAW_PATH)
            click.echo(f"Refreshed cached raw data: {fixed_user.RAW_PATH}")
        if not fixed_user.RAW_PATH.is_file():
            raise ValueError(
                f"raw data not found: {fixed_user.RAW_PATH}; "
                "run make create-cohort-user-date-model first"
            )
        cached = pd.read_parquet(fixed_user.RAW_PATH)
        if "parent_part_number" not in {column.lower() for column in cached.columns}:
            raise ValueError(
                "cohort-only raw data lacks PARENT_PART_NUMBER; "
                "run make create-cohort-user-date-model to refresh it"
            )
        if "process_start_time" not in {column.lower() for column in cached.columns}:
            raise ValueError(
                "cohort-only raw data lacks PROCESS_START_TIME; "
                "run make create-test-model-final REFRESH_EXTRACT=1"
            )
        raw = fixed_user.prepare_frame(cached)
        design = core.build_fixed_effect_design(
            exp_model.log_duration(raw),
            categorical_effects=CATEGORICAL_EFFECTS,
            base_fixed_columns=core.BASE_FIXED_EFFECT_COLUMNS,
        )
        result = core.fit_final_model(
            design, cell_columns=CELL_COLUMNS, random_columns=RANDOM_COLUMNS
        )
        preceding = result.fixed_effects.set_index("term").loc["SAME_PRECEDING"]
        counterfactual = same_preceding_totals(
            design.frame, log_coefficient=float(preceding["estimate"])
        )
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        design.frame.to_parquet(MODEL_PATH, index=False)
        result.user_effects.to_parquet(USER_DATA_PATH, index=False)
        result.date_effects.to_parquet(DATE_DATA_PATH, index=False)
        result.parent_effects.to_parquet(PARENT_DATA_PATH, index=False)
        FIXED_TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        FIXED_TABLE_PATH.write_text(
            "# test-model-final fixed effects\n\n"
            + core._fixed_effects_markdown(result.fixed_effects) + "\n",
            encoding="utf-8",
        )
        USER_TABLE_PATH.write_text(
            "# test-model-final user random intercepts\n\n"
            + core._random_effects_markdown(result.user_effects, identifier="USER_ID")
            + "\n",
            encoding="utf-8",
        )
        DATE_TABLE_PATH.write_text(
            "# test-model-final date random intercepts\n\n"
            + core._random_effects_markdown(result.date_effects, identifier="D")
            + "\n",
            encoding="utf-8",
        )
        PARENT_TABLE_PATH.write_text(
            "# test-model-final parent part number random intercepts\n\n"
            + core._random_effects_markdown(
                result.parent_effects, identifier="PARENT_PART_NUMBER"
            )
            + "\n",
            encoding="utf-8",
        )
        write_counterfactual_tables(counterfactual)
        base_model.write_diagnostics(
            result,
            chart_dir=CHART_DIR,
            name=NAME,
            outcome_scale="log",
            prediction_filename=PREDICTION_PATH.name,
        )
        exp_model.write_random_effect_densities(result, chart_dir=CHART_DIR)
        core._write_qq_plot(
            core._qq_frame(result.parent_effects),
            PARENT_QQ_PATH,
            "Parent-part-number random intercepts",
            "Parent part number intercept",
        )
        exp_model.write_random_effect_density(
            result.parent_effects,
            PARENT_DENSITY_PATH,
            "Parent-part-number random intercepts",
        )
        with (CHART_DIR / "README.md").open("a", encoding="utf-8") as readme:
            readme.write(
                "\n![Parent part number Q–Q plot](parent_random_intercepts_qq.png)\n\n"
                "![Parent part number intercept density](parent_random_intercepts_density.png)\n"
            )
        write_report(design, result, counterfactual)
    except (OSError, ValueError, np.linalg.LinAlgError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(f"Created {NAME} report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
