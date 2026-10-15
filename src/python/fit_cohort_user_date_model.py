#!/usr/bin/env python3
"""Fit cohort/pet-type/user/date fixed cells with no random intercept."""

from __future__ import annotations

import os
from pathlib import Path

import altair as alt
import click
from jinja2 import Environment, FileSystemLoader, StrictUndefined
import numpy as np
import pandas as pd

from . import fit_mc3_coh_pettype_final_model as core
from .generate_task_table import REQUIRED_SETTINGS, parse_dotenv
from .plot_style import FIGURE_BACKGROUND

ROOT = Path(__file__).resolve().parents[2]
NAME = "cohort_user_date_model"
SQL_PATH = ROOT / "generated" / f"{NAME}.sql"
RAW_PATH = ROOT / "data" / f"{NAME}_task_data.parquet"
MODEL_PATH = ROOT / "data" / f"{NAME}_boxcox_data.parquet"
FIXED_TABLE_PATH = ROOT / "outputs" / "tables" / f"{NAME}_fixed_effects.md"
REPORT_PATH = ROOT / "outputs" / "reports" / "md" / f"{NAME}.md"
CHART_DIR = ROOT / "outputs" / "charts" / "cohort-user-date-model"
RESIDUAL_QQ_PATH = CHART_DIR / "conditional_residuals_qq.png"
PREDICTION_PATH = CHART_DIR / "predicted_vs_boxcox_actual.png"

CELL_COLUMNS = ("coh", "pettype", "user_id", "d")
CATEGORICAL_EFFECTS = core.CATEGORICAL_EFFECTS
BASE_FIXED_COLUMNS = core.TREATMENT_COLUMNS


def render_sql(
    percentile: float = 0.95,
    *,
    sequence_field: str = "COHORT_SEQN",
    length_field: str = "COHORT_BATCH_LEN",
) -> str:
    if not 0 < percentile < 1:
        raise ValueError("percentile must be strictly between zero and one")
    environment = Environment(
        loader=FileSystemLoader(core.SQL_DIRECTORY),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )
    return environment.get_template("cohort_user_date_model.sql.j2").render(
        source_table=core.SOURCE_TABLE,
        percentile=f"{percentile:.12g}",
        sequence_field=sequence_field,
        length_field=length_field,
    )


def prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    # The shared normalizer retains the original model's required columns.
    prepared = frame.copy()
    for column in ("mc3", "parent_part_number"):
        if column not in prepared.columns and column.upper() not in prepared.columns:
            prepared[column] = "<Missing>"
    return core.normalize_frame(prepared)


def write_diagnostics(result: core.FinalModelResult) -> None:
    core._write_qq_plot(
        result.residual_quantiles,
        RESIDUAL_QQ_PATH,
        "Q–Q plot of conditional residuals",
        "Standardized conditional residual quantile",
    )
    bins = result.prediction_bins
    bounds = bins[
        ["predicted_lower", "predicted_upper", "actual_lower", "actual_upper"]
    ].to_numpy()
    lower, upper = float(bounds.min()), float(bounds.max())
    heatmap = alt.Chart(bins).mark_rect().encode(
        x=alt.X("predicted_lower:Q", title="Conditional prediction (Box-Cox scale)"),
        x2="predicted_upper:Q",
        y=alt.Y("actual_lower:Q", title="Observed duration (Box-Cox scale)"),
        y2="actual_upper:Q",
        color=alt.Color("count:Q", title="Tasks", scale=alt.Scale(type="log", scheme="blues")),
    )
    identity = alt.Chart(
        pd.DataFrame({"predicted": [lower, upper], "actual": [lower, upper]})
    ).mark_line(color="#b2182b", strokeDash=[6, 4]).encode(
        x="predicted:Q", y="actual:Q"
    )
    chart = (heatmap + identity).properties(
        title="Conditional predictions versus Box-Cox outcomes",
        width=700,
        height=600,
    ).configure(background=FIGURE_BACKGROUND).configure_view(
        stroke=None, fill=FIGURE_BACKGROUND
    )
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    chart.save(PREDICTION_PATH, scale_factor=2)
    (CHART_DIR / "README.md").write_text(
        "# Cohort/pet-type/user/date model diagnostics\n\n"
        "![Residual Q–Q plot](conditional_residuals_qq.png)\n\n"
        "![Predicted versus outcome](predicted_vs_boxcox_actual.png)\n",
        encoding="utf-8",
    )


def write_report(
    frame: pd.DataFrame,
    transform: core.BoxCoxResult,
    design: core.FixedEffectDesign,
    result: core.FinalModelResult,
) -> Path:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    def link(path: Path) -> str:
        return os.path.relpath(path, REPORT_PATH.parent)

    report = rf"""# Cohort/pet-type/user/date fixed-effects model

## Sample and indicators

The source is `{core.SOURCE_TABLE}`. Eligible valid-DUR tasks have a user,
task, process start, positive imputed dwell duration, and valid `COHORT_SEQN`
and `COHORT_BATCH_LEN` values (both at least one; sequence at most batch length).
One global `APPROX_PERCENTILE(DURATION_SECONDS, 0.95)` cutoff is calculated
before retaining tasks with duration strictly below it. The valid-DUR pipeline
starts a new cohort batch when valid tasks are not consecutive, the break is at
least one hour, or the cohort changes. Missing cohort, pet type, approval
channel, and prescription source are represented by `<Missing>`.

For cohort sequence number $S_i$, cohort batch length $L_i$, and correction
count $N_i$, define

$$
P_i=\mathbf{{1}}(L_i>1\land S_i>1),\quad
F_i=\mathbf{{1}}(L_i>1\land S_i<L_i),\quad
C_i=\mathbf{{1}}(N_i>0).
$$

These are `SAME_PRECEDING`, the `SAME_FOLLOWING` placebo, and `HAS_CORRECTION`.
Each task's positive duration $Y_i$ receives one global Box-Cox transform
$Z_i=g_\lambda(Y_i)=(Y_i^\lambda-1)/\lambda$ (or $\log Y_i$ when
$\lambda=0$). The fitted $\widehat{{\lambda}}$ is {transform.lambda_:.8f}.

## Model formula

Let $c(i)=(\mathrm{{COH}}_i,\mathrm{{PETTYPE}}_i,\mathrm{{USER\_ID}}_i,D_i)$
be the fixed cell, $A_i$ the approval channel, and $R_i$ the prescription
source. The model is

$$
\begin{{aligned}}
Z_i={{}}&\gamma_{{c(i)}}+\beta_P P_i+\beta_F F_i+\beta_C C_i\\
&+\sum_{{a\ne a_0}}\theta_a\mathbf{{1}}(A_i=a)
 +\sum_{{s\ne s_0}}\phi_s\mathbf{{1}}(R_i=s)\\
&+\epsilon_i.
\end{{aligned}}
$$

There is one fixed effect per observed `(COH, PETTYPE, USER_ID, D)` cell and
no overall intercept. Each cell has its own intercept; there is no shared
date effect. Weekday contrasts are determined by date and therefore absorbed
by the cells. Pet type is likewise absorbed. The categorical references are
`{design.references['approval_channel']}` for approval channel and
`{design.references['prescription_source']}` for prescription source (the most
frequent level, with lexicographic tie breaking). The model has no random
effects: $\epsilon_i\sim N(0,\sigma_e^2)$ independently. OLS estimates fixed
effects; the residual SD interval uses a chi-square approximation. Wald 95%
confidence intervals and two-sided normal p-values are reported for fixed
effects. Estimates and diagnostics are on the Box-Cox scale.

## Sample and fit

| Quantity | Value |
|---|---:|
| Tasks | {result.n_observations:,} |
| Cohort/pet-type/user/date cells | {result.n_cells:,} |
| Users | {result.n_users:,} |
| Dates | {result.n_dates:,} |
| Global approximate P95 cutoff (seconds) | {frame['p95_seconds'].iloc[0]:.6f} |
| Box-Cox lambda | {transform.lambda_:.8f} |
| Conditional R-squared | {result.conditional_r_squared:.6f} |
| Conditional RMSE | {result.conditional_rmse:.6f} |
| Restricted negative log-likelihood | {result.reml_nll:.6f} |
| Converged | {result.converged} |

## Fixed effects

{core._fixed_effects_markdown(result.fixed_effects)}

## Variance

| Component | SD | Approximate 95% CI |
|---|---:|---:|
| Residual | {result.residual_sd:.6f} | [{result.residual_sd_ci[0]:.6f}, {result.residual_sd_ci[1]:.6f}] |

## Interpretation and assumptions

The `SAME_PRECEDING` estimate is an adjusted observational association, not a
causal effect. It assumes additive fixed effects and independent normally
distributed residuals with a common variance on the Box-Cox scale. The
`SAME_FOLLOWING` placebo can reveal sequence-related confounding but cannot
establish causal identification. The paired t-test is
also observational; neither analysis identifies a causal effect. Their
estimates are not directly comparable because the task populations and
preceding-task rules differ. Here same cohort means a valid-DUR cohort batch;
the paired test uses the previous task of the day.

## Diagnostics and artifacts

The residual Q–Q plot curves in both tails. Normal-based confidence intervals
should therefore be read as model-based approximations. The
predicted-versus-observed plot shows broad spread around the diagonal.

![Conditional residual Q–Q plot]({link(RESIDUAL_QQ_PATH)})

![Predicted versus outcome]({link(PREDICTION_PATH)})

- [Generated SQL]({link(SQL_PATH)})
- [Raw task data]({link(RAW_PATH)})
- [Transformed model data]({link(MODEL_PATH)})
- [Fixed-effect table]({link(FIXED_TABLE_PATH)})
"""
    REPORT_PATH.write_text(report, encoding="utf-8")
    return REPORT_PATH


@click.command()
@click.option("--env-file", type=click.Path(path_type=Path, dir_okay=False), default=Path(".env"))
@click.option("--redraw-only", is_flag=True)
@click.option("--percentile", type=float, default=0.95, show_default=True)
def main(env_file: Path, redraw_only: bool, percentile: float) -> None:
    """Fit the cohort/pet-type/user/date fixed-cell model."""
    try:
        sql = render_sql(percentile)
        SQL_PATH.parent.mkdir(parents=True, exist_ok=True)
        SQL_PATH.write_text(sql.rstrip() + "\n", encoding="utf-8")
        if redraw_only:
            if not RAW_PATH.is_file():
                raise ValueError(f"cached raw data not found: {RAW_PATH}")
            click.echo(f"Loaded cached raw data: {RAW_PATH}")
        else:
            if not env_file.is_file():
                raise ValueError(f"environment file not found: {env_file}")
            settings = parse_dotenv(env_file)
            missing = [key for key in REQUIRED_SETTINGS if key not in settings]
            if missing:
                raise ValueError("missing required settings: " + ", ".join(missing))
            core.fetch_to_parquet(settings, sql, RAW_PATH)
            click.echo(f"Downloaded raw data: {RAW_PATH}")
        raw = prepare_frame(pd.read_parquet(RAW_PATH))
        transform = core.transform_duration(raw)
        design = core.build_fixed_effect_design(
            transform.frame,
            categorical_effects=CATEGORICAL_EFFECTS,
            base_fixed_columns=BASE_FIXED_COLUMNS,
        )
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        design.frame.to_parquet(MODEL_PATH, index=False)
        result = core.fit_final_model(
            design,
            cell_columns=CELL_COLUMNS,
            random_columns=(),
        )
        FIXED_TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        FIXED_TABLE_PATH.write_text(
            "# Cohort/pet-type/user/date model fixed effects\n\n"
            + core._fixed_effects_markdown(result.fixed_effects) + "\n",
            encoding="utf-8",
        )
        write_diagnostics(result)
        write_report(design.frame, transform, design, result)
    except (OSError, ValueError, np.linalg.LinAlgError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(f"Created cohort/pet-type/user/date model report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
