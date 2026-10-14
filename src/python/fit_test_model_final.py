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


def write_report(
    design: core.FixedEffectDesign,
    result: core.FinalModelResult,
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

## Variance components

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
""",
        encoding="utf-8",
    )
    return REPORT_PATH


@click.command()
def main() -> None:
    """Fit test-model-final from the cohort-only raw task cache."""
    try:
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
        raw = fixed_user.prepare_frame(cached)
        design = core.build_fixed_effect_design(
            exp_model.log_duration(raw),
            categorical_effects=CATEGORICAL_EFFECTS,
            base_fixed_columns=core.BASE_FIXED_EFFECT_COLUMNS,
        )
        result = core.fit_final_model(
            design, cell_columns=CELL_COLUMNS, random_columns=RANDOM_COLUMNS
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
        write_report(design, result)
    except (OSError, ValueError, np.linalg.LinAlgError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(f"Created {NAME} report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
