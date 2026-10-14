#!/usr/bin/env python3
"""Fit test-model with global fixed effects and user/date random intercepts."""

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
from .plot_style import FIGURE_BACKGROUND

ROOT = Path(__file__).resolve().parents[2]
NAME = "test-model"
STEM = "test_model"
MODEL_PATH = ROOT / "data" / f"{STEM}_boxcox_data.parquet"
USER_DATA_PATH = ROOT / "data" / f"{STEM}_user_effects.parquet"
DATE_DATA_PATH = ROOT / "data" / f"{STEM}_date_effects.parquet"
FIXED_TABLE_PATH = ROOT / "outputs" / "tables" / f"{STEM}_fixed_effects.md"
USER_TABLE_PATH = ROOT / "outputs" / "tables" / f"{STEM}_user_effects.md"
DATE_TABLE_PATH = ROOT / "outputs" / "tables" / f"{STEM}_date_effects.md"
REPORT_PATH = ROOT / "outputs" / "reports" / "md" / f"{NAME}.md"
CHART_DIR = ROOT / "outputs" / "charts" / NAME
USER_QQ_PATH = CHART_DIR / "user_random_intercepts_qq.png"
DATE_QQ_PATH = CHART_DIR / "date_random_intercepts_qq.png"
RESIDUAL_QQ_PATH = CHART_DIR / "conditional_residuals_qq.png"
PREDICTION_PATH = CHART_DIR / "predicted_vs_boxcox_actual.png"

CELL_COLUMNS: tuple[str, ...] = ()
RANDOM_COLUMNS = ("user_id", "d")
CATEGORICAL_EFFECTS = ("coh", "pettype", "approval_channel", "prescription_source")


def global_intercept(design: core.FixedEffectDesign, result: core.FinalModelResult) -> float:
    """Recover the profiled intercept from the fitted fixed and random effects."""
    frame = design.frame
    beta = result.fixed_effects["estimate"].to_numpy(dtype=float)
    fixed_mean = float(frame.loc[:, design.columns].mean().to_numpy() @ beta)
    random_mean = sum(
        float(effects["task_count"] @ effects["random_intercept"]) / len(frame)
        for effects in (result.user_effects, result.date_effects, result.parent_effects)
        if not effects.empty
    )
    return float(frame["boxcox_duration"].mean() - fixed_mean - random_mean)


def write_diagnostics(
    result: core.FinalModelResult,
    *,
    chart_dir: Path = CHART_DIR,
    name: str = NAME,
    outcome_scale: str = "Box-Cox",
    prediction_filename: str = "predicted_vs_boxcox_actual.png",
) -> None:
    user_qq_path = chart_dir / "user_random_intercepts_qq.png"
    date_qq_path = chart_dir / "date_random_intercepts_qq.png"
    residual_qq_path = chart_dir / "conditional_residuals_qq.png"
    prediction_path = chart_dir / prediction_filename
    for effects, path, title, y_title in (
        (result.user_effects, user_qq_path, "User random intercepts", "User intercept"),
        (result.date_effects, date_qq_path, "Date random intercepts", "Date intercept"),
    ):
        core._write_qq_plot(core._qq_frame(effects), path, title, y_title)
    core._write_qq_plot(
        result.residual_quantiles,
        residual_qq_path,
        "Conditional residuals",
        "Standardized conditional residual quantile",
    )
    bins = result.prediction_bins
    bounds = bins[
        ["predicted_lower", "predicted_upper", "actual_lower", "actual_upper"]
    ].to_numpy()
    lower, upper = float(bounds.min()), float(bounds.max())
    heatmap = alt.Chart(bins).mark_rect().encode(
        x=alt.X("predicted_lower:Q", title=f"Conditional prediction ({outcome_scale} scale)"),
        x2="predicted_upper:Q",
        y=alt.Y("actual_lower:Q", title=f"Observed duration ({outcome_scale} scale)"),
        y2="actual_upper:Q",
        color=alt.Color("count:Q", title="Tasks", scale=alt.Scale(type="log", scheme="blues")),
    )
    identity = alt.Chart(
        pd.DataFrame({"predicted": [lower, upper], "actual": [lower, upper]})
    ).mark_line(color="#b2182b", strokeDash=[6, 4]).encode(
        x="predicted:Q", y="actual:Q"
    )
    chart = (heatmap + identity).properties(
        title=f"Conditional predictions versus {outcome_scale} outcomes",
        width=700,
        height=600,
    ).configure(background=FIGURE_BACKGROUND).configure_view(
        stroke=None, fill=FIGURE_BACKGROUND
    )
    chart_dir.mkdir(parents=True, exist_ok=True)
    chart.save(prediction_path, scale_factor=2)
    (chart_dir / "README.md").write_text(
        f"# {name} diagnostics\n\n"
        "![User Q–Q plot](user_random_intercepts_qq.png)\n\n"
        "![Date Q–Q plot](date_random_intercepts_qq.png)\n\n"
        "![Residual Q–Q plot](conditional_residuals_qq.png)\n\n"
        f"![Predicted versus outcome]({prediction_filename})\n",
        encoding="utf-8",
    )


def write_report(
    frame: pd.DataFrame,
    transform: core.BoxCoxResult,
    design: core.FixedEffectDesign,
    result: core.FinalModelResult,
) -> Path:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    intercept = global_intercept(design, result)

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
        rf"""# test-model

No cells: one global intercept, cohort and pet type fixed effects, and user
and date random intercepts.

## Sample and indicators

This model uses the [cohort-and-pet extract]({link(pet_model.RAW_PATH)}) from
`{core.SOURCE_TABLE}` and the same strict global P95 filter. Within each
valid-DUR cohort-and-pet batch, `COHORT_PET_SEQN` is task position and
`COHORT_PET_BATCH_LEN` is batch length. For position $S_i$ and length $L_i$,
`SAME_PRECEDING` is $P_i=\mathbf{{1}}(L_i>1\land S_i>1)$ and the
`SAME_FOLLOWING` placebo is $F_i=\mathbf{{1}}(L_i>1\land S_i<L_i)$.
`HAS_CORRECTION` is $C_i=\mathbf{{1}}(N_i>0)$ for correction count $N_i$.
The {n_tasks:,} retained tasks receive one global Box-Cox transform of
duration, with $\widehat{{\lambda}}={transform.lambda_:.8f}$.

| Indicator | Value | Tasks | Percent of retained tasks |
|---|---:|---:|---:|
{chr(10).join(indicator_rows)}

## Model formula

Let $Z_i=g_\lambda(Y_i)$ be transformed duration, $c_i$ cohort, $p_i$ pet
type, $w_i$ weekday, $a_i$ approval channel, and $s_i$ prescription source.
With one reference level omitted from each categorical effect:

$$
Z_i=\alpha+\beta_P P_i+\beta_F F_i+\beta_C C_i
 +\gamma_{{c_i}}+\delta_{{p_i}}+\theta_{{w_i}}
 +\phi_{{a_i}}+\psi_{{s_i}}+b_{{u(i)}}+h_{{d(i)}}+\epsilon_i.
$$

There are no fixed cells. Cohort, pet type, weekday, approval channel, and
prescription source enter as additive fixed effects. The reference levels are
`{design.references['coh']}` (cohort), `{design.references['pettype']}` (pet
type), Sunday (weekday), `{design.references['approval_channel']}` (approval
channel), and `{design.references['prescription_source']}` (prescription source).
The random intercepts are independent:
$b_u\sim N(0,\sigma_u^2)$, $h_d\sim N(0,\sigma_d^2)$, and
$\epsilon_i\sim N(0,\sigma_e^2)$. REML estimates the model. Fixed-effect
confidence intervals and p-values use normal Wald approximations; random SD
intervals use observed information on the log-SD scale, and the residual SD
interval uses a chi-square approximation. Estimates are on the Box-Cox scale.
The global intercept is $\widehat{{\alpha}}={intercept:.6f}$ for the reference
categories, zero indicator values, and zero random intercepts.

## Sample and fit

| Quantity | Value |
|---|---:|
| Tasks | {result.n_observations:,} |
| Fixed cells | {result.n_cells:,} |
| Global intercept (Box-Cox scale) | {intercept:.6f} |
| Users | {result.n_users:,} |
| Dates | {result.n_dates:,} |
| Global approximate P95 cutoff (seconds) | {frame['p95_seconds'].iloc[0]:.6f} |
| Box-Cox lambda | {transform.lambda_:.8f} |
| Conditional R-squared | {result.conditional_r_squared:.6f} |
| Conditional RMSE | {result.conditional_rmse:.6f} |
| REML negative log-likelihood | {result.reml_nll:.6f} |
| Converged | {result.converged} |

## Fixed effects

{core._fixed_effects_markdown(result.fixed_effects)}

## Variance components

| Component | SD | Approximate 95% CI |
|---|---:|---:|
| User random intercept | {result.random_sds[0]:.6f} | [{result.random_sd_cis[0][0]:.6f}, {result.random_sd_cis[0][1]:.6f}] |
| Date random intercept | {result.random_sds[1]:.6f} | [{result.random_sd_cis[1][0]:.6f}, {result.random_sd_cis[1][1]:.6f}] |
| Residual | {result.residual_sd:.6f} | [{result.residual_sd_ci[0]:.6f}, {result.residual_sd_ci[1]:.6f}] |

## Interpretation and assumptions

`SAME_PRECEDING` is an adjusted observational association, not a causal
effect. The coefficient uses comparisons both within and across cohorts, pet
types, users, and dates after additive adjustment; it has a different
interpretation from the fixed-cell model. The model assumes additive effects,
normally distributed independent user/date intercepts and residuals, and a
common residual variance on the Box-Cox scale. Unmodeled user and date
differences must be unrelated to the included predictors after adjustment
for the random-intercept interpretation. The paired t-test is also
observational and uses a different task population and preceding-task rule.

## Diagnostics and artifacts

The date random-intercept Q–Q plot departs strongly from a normal line, and
the residual Q–Q plot curves in both tails. The reported confidence intervals
are model-based approximations under the stated distributional assumptions.

![User random-intercept Q–Q plot]({link(USER_QQ_PATH)})

![Date random-intercept Q–Q plot]({link(DATE_QQ_PATH)})

![Conditional residual Q–Q plot]({link(RESIDUAL_QQ_PATH)})

![Predicted versus outcome]({link(PREDICTION_PATH)})

- [Shared generated SQL]({link(pet_model.SQL_PATH)})
- [Shared raw task data]({link(pet_model.RAW_PATH)})
- [Transformed model data]({link(MODEL_PATH)})
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
    """Fit test-model from the cohort-and-pet raw task cache."""
    try:
        if not pet_model.RAW_PATH.is_file():
            raise ValueError(
                f"raw data not found: {pet_model.RAW_PATH}; "
                "run make create-cohort-user-date-pettype-cell-model first"
            )
        raw = fixed_user.prepare_frame(pd.read_parquet(pet_model.RAW_PATH))
        transform = core.transform_duration(raw)
        design = core.build_fixed_effect_design(
            transform.frame,
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
            "# test-model fixed effects\n\n"
            + core._fixed_effects_markdown(result.fixed_effects) + "\n",
            encoding="utf-8",
        )
        USER_TABLE_PATH.write_text(
            "# test-model user random intercepts\n\n"
            + core._random_effects_markdown(result.user_effects, identifier="USER_ID")
            + "\n",
            encoding="utf-8",
        )
        DATE_TABLE_PATH.write_text(
            "# test-model date random intercepts\n\n"
            + core._random_effects_markdown(result.date_effects, identifier="D")
            + "\n",
            encoding="utf-8",
        )
        write_diagnostics(result)
        write_report(design.frame, transform, design, result)
    except (OSError, ValueError, np.linalg.LinAlgError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(f"Created {NAME} report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
