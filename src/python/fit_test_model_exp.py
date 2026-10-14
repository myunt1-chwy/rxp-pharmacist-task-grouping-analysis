#!/usr/bin/env python3
"""Fit test-model-exp with log duration and user/date random intercepts."""

from __future__ import annotations

import os
from pathlib import Path

import altair as alt
import click
import numpy as np
import pandas as pd

from . import fit_cohort_user_date_model as fixed_user
from . import fit_cohort_user_date_pettype_cell_model as pet_model
from . import fit_mc3_coh_pettype_final_model as core
from . import fit_test_model as base_model
from .plot_style import FIGURE_BACKGROUND

ROOT = Path(__file__).resolve().parents[2]
NAME = "test-model-exp"
STEM = "test_model_exp"
MODEL_PATH = ROOT / "data" / f"{STEM}_log_data.parquet"
USER_DATA_PATH = ROOT / "data" / f"{STEM}_user_effects.parquet"
DATE_DATA_PATH = ROOT / "data" / f"{STEM}_date_effects.parquet"
FIXED_TABLE_PATH = ROOT / "outputs" / "tables" / f"{STEM}_fixed_effects.md"
USER_TABLE_PATH = ROOT / "outputs" / "tables" / f"{STEM}_user_effects.md"
DATE_TABLE_PATH = ROOT / "outputs" / "tables" / f"{STEM}_date_effects.md"
REPORT_PATH = ROOT / "outputs" / "reports" / "md" / f"{NAME}.md"
CHART_DIR = ROOT / "outputs" / "charts" / NAME
USER_QQ_PATH = CHART_DIR / "user_random_intercepts_qq.png"
DATE_QQ_PATH = CHART_DIR / "date_random_intercepts_qq.png"
USER_DENSITY_PATH = CHART_DIR / "user_random_intercepts_density.png"
DATE_DENSITY_PATH = CHART_DIR / "date_random_intercepts_density.png"
RESIDUAL_QQ_PATH = CHART_DIR / "conditional_residuals_qq.png"
PREDICTION_PATH = CHART_DIR / "predicted_vs_log_actual.png"

CELL_COLUMNS = base_model.CELL_COLUMNS
RANDOM_COLUMNS = base_model.RANDOM_COLUMNS
CATEGORICAL_EFFECTS = base_model.CATEGORICAL_EFFECTS


def log_duration(frame: pd.DataFrame) -> pd.DataFrame:
    """Place the natural log outcome in the fitting core's outcome column."""
    transformed = frame.copy()
    duration = transformed["duration_seconds"].to_numpy(dtype=np.float64)
    if not np.isfinite(duration).all() or (duration <= 0).any():
        raise ValueError("log durations must be finite and strictly positive")
    transformed["boxcox_duration"] = np.log(duration)
    return transformed


def write_random_effect_densities(
    result: core.FinalModelResult, *, chart_dir: Path = CHART_DIR
) -> None:
    """Plot one estimated intercept per user and per date."""
    for effects, path, title in (
        (result.user_effects, chart_dir / USER_DENSITY_PATH.name, "User random intercepts"),
        (result.date_effects, chart_dir / DATE_DENSITY_PATH.name, "Date random intercepts"),
    ):
        write_random_effect_density(effects, path, title)
    with (chart_dir / "README.md").open("a", encoding="utf-8") as readme:
        readme.write(
            "\n![User intercept density](user_random_intercepts_density.png)\n\n"
            "![Date intercept density](date_random_intercepts_density.png)\n"
        )


def write_random_effect_density(effects: pd.DataFrame, path: Path, title: str) -> None:
    """Plot equal-weight fitted intercepts for one grouping variable."""
    values = effects["random_intercept"].to_numpy(dtype=float)
    span = float(values.max() - values.min())
    padding = 0.15 * span if span else 0.1
    density = (
        alt.Chart(effects[["random_intercept"]])
        .transform_density(
            "random_intercept",
            as_=["intercept", "density"],
            extent=[float(values.min() - padding), float(values.max() + padding)],
            steps=200,
        )
        .mark_area(color="#4c78a8", opacity=0.65)
        .encode(
            x=alt.X("intercept:Q", title="Estimated random intercept (log seconds)"),
            y=alt.Y("density:Q", title="Density", scale=alt.Scale(domainMin=0)),
        )
    )
    zero = alt.Chart(pd.DataFrame({"zero": [0.0]})).mark_rule(
        color="#b2182b", strokeDash=[6, 4]
    ).encode(x="zero:Q")
    chart = (density + zero).properties(
        title=f"{title} (n={len(values):,})",
        width=700,
        height=420,
    ).configure(background=FIGURE_BACKGROUND).configure_view(
        stroke=None, fill=FIGURE_BACKGROUND
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    chart.save(path, scale_factor=2)


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
        rf"""# test-model-exp

This model has no fixed cells. It uses the same sample and covariates as
[test-model]({link(base_model.REPORT_PATH)}), with natural log duration as the
outcome instead of the fitted Box-Cox transformation.

## Sample and indicators

The source is `{core.SOURCE_TABLE}` through the
[shared cohort-and-pet extract]({link(pet_model.RAW_PATH)}). The strict global
P95 filter retains {n_tasks:,} positive-duration tasks. `SAME_PRECEDING` and
`SAME_FOLLOWING` retain the cohort-and-pet definitions: for within-batch task
position $S_i=$ `COHORT_PET_SEQN` and batch length $L_i=$
`COHORT_PET_BATCH_LEN`, $P_i=\mathbf{{1}}(L_i>1\land S_i>1)$ and
$F_i=\mathbf{{1}}(L_i>1\land S_i<L_i)$. `HAS_CORRECTION` is
$C_i=\mathbf{{1}}(N_i>0)$ for correction count $N_i$.

| Indicator | Value | Tasks | Percent of retained tasks |
|---|---:|---:|---:|
{chr(10).join(indicator_rows)}

## Model formula

With cohort $c_i$, pet type $p_i$, weekday $w_i$, approval channel $a_i$,
prescription source $s_i$, user $u(i)$, and date $d(i)$:

$$
\log(Y_i)=\alpha+\beta_P P_i+\beta_F F_i+\beta_C C_i
 +\gamma_{{c_i}}+\delta_{{p_i}}+\theta_{{w_i}}
 +\phi_{{a_i}}+\psi_{{s_i}}+b_{{u(i)}}+h_{{d(i)}}+\epsilon_i.
$$

There are no fixed cells. Cohort, pet type, weekday, approval channel, and
prescription source are additive fixed effects. Their reference levels are
`{design.references['coh']}`, `{design.references['pettype']}`, Sunday,
`{design.references['approval_channel']}`, and
`{design.references['prescription_source']}`, respectively. User and date are
independent random intercepts: $b_u\sim N(0,\sigma_u^2)$ and
$h_d\sim N(0,\sigma_d^2)$, independently of
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
| Residual | {result.residual_sd:.6f} | [{result.residual_sd_ci[0]:.6f}, {result.residual_sd_ci[1]:.6f}] |

## Interpretation and assumptions

The model assumes additive effects, independent normally distributed user
and date intercepts and residuals, and a common log-scale residual variance.
Unmodeled user and date differences must be unrelated to the included
predictors after adjustment for the random-intercept interpretation. This
remains an observational association. It is not directly comparable to the
paired t-test, which uses a different task population and preceding-task rule.
Coefficients and fit measures on the log scale are not directly comparable to
those on the Box-Cox scale in `test-model`.

## Diagnostics and artifacts

The date random-intercept Q–Q plot departs strongly from a normal line, and
the date intercept density shows a second positive peak. The residual Q–Q
plot curves in both tails. The reported confidence intervals are model-based
approximations under the stated distributional assumptions.

![User random-intercept Q–Q plot]({link(USER_QQ_PATH)})

![Date random-intercept Q–Q plot]({link(DATE_QQ_PATH)})

Each density plot gives one fitted intercept equal weight per user or date;
the dashed vertical line marks zero.

![User random-intercept density]({link(USER_DENSITY_PATH)})

![Date random-intercept density]({link(DATE_DENSITY_PATH)})

![Conditional residual Q–Q plot]({link(RESIDUAL_QQ_PATH)})

![Predicted versus outcome]({link(PREDICTION_PATH)})

- [Shared generated SQL]({link(pet_model.SQL_PATH)})
- [Shared raw task data]({link(pet_model.RAW_PATH)})
- [Log-transformed model data]({link(MODEL_PATH)})
- [Fixed-effect table]({link(FIXED_TABLE_PATH)})
- [User-effect table]({link(USER_TABLE_PATH)})
- [Date-effect table]({link(DATE_TABLE_PATH)})
- [User-effect data]({link(USER_DATA_PATH)})
- [Date-effect data]({link(DATE_DATA_PATH)})
""",
        encoding="utf-8",
    )
    return REPORT_PATH


@click.command()
def main() -> None:
    """Fit test-model-exp from the shared cohort-and-pet raw task cache."""
    try:
        if not pet_model.RAW_PATH.is_file():
            raise ValueError(
                f"raw data not found: {pet_model.RAW_PATH}; "
                "run make create-cohort-user-date-pettype-cell-model first"
            )
        raw = fixed_user.prepare_frame(pd.read_parquet(pet_model.RAW_PATH))
        design = core.build_fixed_effect_design(
            log_duration(raw),
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
        FIXED_TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        FIXED_TABLE_PATH.write_text(
            "# test-model-exp fixed effects\n\n"
            + core._fixed_effects_markdown(result.fixed_effects) + "\n",
            encoding="utf-8",
        )
        USER_TABLE_PATH.write_text(
            "# test-model-exp user random intercepts\n\n"
            + core._random_effects_markdown(result.user_effects, identifier="USER_ID")
            + "\n",
            encoding="utf-8",
        )
        DATE_TABLE_PATH.write_text(
            "# test-model-exp date random intercepts\n\n"
            + core._random_effects_markdown(result.date_effects, identifier="D")
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
        write_random_effect_densities(result)
        write_report(design, result)
    except (OSError, ValueError, np.linalg.LinAlgError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(f"Created {NAME} report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
