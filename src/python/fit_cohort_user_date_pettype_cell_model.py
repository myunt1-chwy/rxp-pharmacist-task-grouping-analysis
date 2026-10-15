#!/usr/bin/env python3
"""Fit cohort_user_date_pettype_cell_model with a user random intercept."""

from __future__ import annotations

import os
from pathlib import Path

import altair as alt
import click
import numpy as np
import pandas as pd

from . import fit_cohort_user_date_model as fixed_user
from . import fit_mc3_coh_pettype_final_model as core
from .plot_style import FIGURE_BACKGROUND

ROOT = Path(__file__).resolve().parents[2]
NAME = "cohort_user_date_pettype_cell_model"
SQL_PATH = ROOT / "generated" / f"{NAME}.sql"
RAW_PATH = ROOT / "data" / f"{NAME}_task_data.parquet"
USER_DATA_PATH = ROOT / "data" / f"{NAME}_user_effects.parquet"
FIXED_TABLE_PATH = ROOT / "outputs" / "tables" / f"{NAME}_fixed_effects.md"
USER_TABLE_PATH = ROOT / "outputs" / "tables" / f"{NAME}_user_effects.md"
REPORT_PATH = ROOT / "outputs" / "reports" / "md" / f"{NAME}.md"
CHART_DIR = ROOT / "outputs" / "charts" / "cohort-user-date-pettype-cell-model"
USER_QQ_PATH = CHART_DIR / "user_random_intercepts_qq.png"
RESIDUAL_QQ_PATH = CHART_DIR / "conditional_residuals_qq.png"
PREDICTION_PATH = CHART_DIR / "predicted_vs_boxcox_actual.png"

CELL_COLUMNS = ("coh", "pettype", "d")
RANDOM_COLUMNS = ("user_id",)
SEQUENCE_FIELD = "COHORT_PET_SEQN"
LENGTH_FIELD = "COHORT_PET_BATCH_LEN"


def count_cells_with_two_each(frame: pd.DataFrame) -> tuple[int, int]:
    """Count observed model cells with at least two tasks per indicator value."""
    cells = frame.groupby(list(CELL_COLUMNS), dropna=False)["same_preceding"].agg(
        ["size", "sum"]
    )
    eligible = (cells["sum"] >= 2) & ((cells["size"] - cells["sum"]) >= 2)
    return int(eligible.sum()), len(cells)


def write_diagnostics(result: core.FinalModelResult) -> None:
    core._write_qq_plot(
        core._qq_frame(result.user_effects),
        USER_QQ_PATH,
        "Q–Q plot of estimated user random intercepts",
        "Estimated user random intercept",
    )
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
        "# cohort_user_date_pettype_cell_model diagnostics\n\n"
        "![User Q–Q plot](user_random_intercepts_qq.png)\n\n"
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
    joint_counts = frame.groupby(["same_preceding", "same_following"]).size()
    joint_rows = []
    for preceding in (0, 1):
        for following in (0, 1):
            count = int(joint_counts.get((preceding, following), 0))
            joint_rows.append(
                f"| {preceding} | {following} | {count:,} | {count / n_tasks:.2%} |"
            )
    preceding_count = int(frame["same_preceding"].sum())
    following_count = int(frame["same_following"].sum())
    both_count = int(joint_counts.get((1, 1), 0))
    eligible_cells, total_cells = count_cells_with_two_each(frame)

    def link(path: Path) -> str:
        return os.path.relpath(path, REPORT_PATH.parent)

    REPORT_PATH.write_text(
        rf"""# cohort_user_date_pettype_cell_model

Fixed `(COH, PETTYPE, D)` cells with a `USER_ID` random intercept.

## Sample and indicators

This model uses the valid-DUR table and global strict P95 filter as the
[cohort/pet-type/user/date fixed-cell model]({link(fixed_user.REPORT_PATH)}).
The source is `{core.SOURCE_TABLE}`. The raw cache contains positive imputed
DUR durations and valid `{SEQUENCE_FIELD}` and `{LENGTH_FIELD}` values. The
cohort-and-pet batches follow the valid-DUR pipeline's consecutive-task and
one-hour-break rules, and restart when the cohort or pet type changes.
`COHORT_PET_SEQN` is the task position within a batch; the pipeline's
`COHORT_PET_BATCH_SEQN` is an intermediate batch identifier and is not an
output column of the valid-DUR table.
Missing cohort, pet type, approval channel, and prescription source are
represented by `<Missing>`.

For cohort sequence number $S_i$, batch length $L_i$, and correction count
$N_i$, the model includes `SAME_PRECEDING`
$P_i=\mathbf{{1}}(L_i>1\land S_i>1)$, the `SAME_FOLLOWING` placebo
$F_i=\mathbf{{1}}(L_i>1\land S_i<L_i)$, and `HAS_CORRECTION`
$C_i=\mathbf{{1}}(N_i>0)$. One global Box-Cox transform of retained duration
$Y_i$ gives $Z_i=g_\lambda(Y_i)$, with
$\widehat{{\lambda}}={transform.lambda_:.8f}$.

The indicators have the following distribution among the {n_tasks:,} tasks
retained after the global P95 filter. Percentages use all retained tasks as
the denominator. `SAME_PRECEDING` applies to {preceding_count:,} tasks
({preceding_count / n_tasks:.2%}), `SAME_FOLLOWING` to {following_count:,}
({following_count / n_tasks:.2%}), and both indicators to {both_count:,}
({both_count / n_tasks:.2%}).

| Indicator | Value | Tasks | Percent |
|---|---:|---:|---:|
{chr(10).join(indicator_rows)}

Their joint distribution shows how often both indicators apply to a task:

| SAME_PRECEDING | SAME_FOLLOWING | Tasks | Percent |
|---:|---:|---:|---:|
{chr(10).join(joint_rows)}

Among the {total_cells:,} observed `(COH, PETTYPE, D)` cells,
{eligible_cells:,} ({eligible_cells / total_cells:.2%}) contain at least two
tasks with `SAME_PRECEDING = 1` and at least two with `SAME_PRECEDING = 0`
in the retained sample.

## Model formula

Let $c(i)=(\mathrm{{COH}}_i,\mathrm{{PETTYPE}}_i,D_i)$ be the fixed cell,
$u(i)$ the user, $A_i$ the approval channel, and $R_i$ the prescription source:

$$
\begin{{aligned}}
Z_i={{}}&\gamma_{{c(i)}}+\beta_P P_i+\beta_F F_i+\beta_C C_i\\
&+\sum_{{a\ne a_0}}\theta_a\mathbf{{1}}(A_i=a)
 +\sum_{{s\ne s_0}}\phi_s\mathbf{{1}}(R_i=s)\\
&+b_{{u(i)}}+\epsilon_i.
\end{{aligned}}
$$

There is one fixed effect per observed `(COH, PETTYPE, D)` cell and no overall
intercept. Date in the cell absorbs weekday, so no weekday contrast is fitted.
User is the only random intercept:
$b_u\sim N(0,\sigma_u^2)$ and independently
$\epsilon_i\sim N(0,\sigma_e^2)$. The reference approval channel is
`{design.references['approval_channel']}` and the reference prescription source
is `{design.references['prescription_source']}` (the most frequent levels, with
lexicographic tie breaking). REML estimates the fixed effects and variance
components. Fixed-effect intervals and p-values use normal Wald approximations;
the user SD interval uses observed information on the log-SD scale, and the
residual SD interval uses a chi-square approximation. All results are on the
Box-Cox scale.

## Sample and fit

| Quantity | Value |
|---|---:|
| Tasks | {result.n_observations:,} |
| Cohort/pet-type/date cells | {result.n_cells:,} |
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
| Residual | {result.residual_sd:.6f} | [{result.residual_sd_ci[0]:.6f}, {result.residual_sd_ci[1]:.6f}] |

## Interpretation and assumptions

`SAME_PRECEDING` is an adjusted observational association. Neither this model
nor the paired t-test identifies a causal effect. The model assumes additive
fixed effects, normally distributed independent user intercepts and residuals,
and a common residual variance on the Box-Cox scale. The user random-effect
assumption also requires users' unmodeled duration differences to be unrelated
to the included predictors after adjustment. The `SAME_FOLLOWING` placebo can
indicate sequence-related confounding. Compared with the fixed-user model,
this variant replaces user-specific cell intercepts with a shared random user
intercept; its coefficient need not have the same interpretation. The paired
t-test uses a different task population and preceding-task rule.

## Diagnostics and artifacts

![User random-intercept Q–Q plot]({link(USER_QQ_PATH)})

![Conditional residual Q–Q plot]({link(RESIDUAL_QQ_PATH)})

![Predicted versus outcome]({link(PREDICTION_PATH)})

- [Generated SQL]({link(SQL_PATH)})
- [Raw task data]({link(RAW_PATH)})
- [Fixed-effect table]({link(FIXED_TABLE_PATH)})
- [User-effect table]({link(USER_TABLE_PATH)})
- [User-effect data]({link(USER_DATA_PATH)})
""",
        encoding="utf-8",
    )
    return REPORT_PATH


@click.command()
@click.option("--env-file", type=click.Path(path_type=Path, dir_okay=False), default=Path(".env"))
@click.option("--redraw-only", is_flag=True)
def main(env_file: Path, redraw_only: bool) -> None:
    """Fit the user-random variant from its cohort-and-pet extract."""
    try:
        sql = fixed_user.render_sql(
            sequence_field=SEQUENCE_FIELD, length_field=LENGTH_FIELD
        )
        SQL_PATH.parent.mkdir(parents=True, exist_ok=True)
        SQL_PATH.write_text(sql.rstrip() + "\n", encoding="utf-8")
        if redraw_only:
            if not RAW_PATH.is_file():
                raise ValueError(f"cached raw data not found: {RAW_PATH}")
            click.echo(f"Loaded cached raw data: {RAW_PATH}")
        else:
            if not env_file.is_file():
                raise ValueError(f"environment file not found: {env_file}")
            settings = fixed_user.parse_dotenv(env_file)
            missing = [key for key in fixed_user.REQUIRED_SETTINGS if key not in settings]
            if missing:
                raise ValueError("missing required settings: " + ", ".join(missing))
            core.fetch_to_parquet(settings, sql, RAW_PATH)
            click.echo(f"Downloaded raw data: {RAW_PATH}")
        raw = fixed_user.prepare_frame(pd.read_parquet(RAW_PATH))
        transform = core.transform_duration(raw)
        design = core.build_fixed_effect_design(
            transform.frame,
            categorical_effects=fixed_user.CATEGORICAL_EFFECTS,
            base_fixed_columns=fixed_user.BASE_FIXED_COLUMNS,
        )
        result = core.fit_final_model(
            design, cell_columns=CELL_COLUMNS, random_columns=RANDOM_COLUMNS
        )
        USER_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        result.user_effects.to_parquet(USER_DATA_PATH, index=False)
        FIXED_TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        FIXED_TABLE_PATH.write_text(
            "# Cohort/pet-type/date model fixed effects\n\n"
            + core._fixed_effects_markdown(result.fixed_effects) + "\n",
            encoding="utf-8",
        )
        USER_TABLE_PATH.write_text(
            "# User random intercepts\n\n"
            + core._random_effects_markdown(result.user_effects, identifier="USER_ID")
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
