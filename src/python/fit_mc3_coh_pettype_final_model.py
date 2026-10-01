#!/usr/bin/env python3
"""Fit the final model with a parent-part-number random intercept."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

import altair as alt
import click
from jinja2 import Environment, FileSystemLoader, StrictUndefined
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from scipy.linalg import cho_factor, cho_solve
from scipy.optimize import minimize
from scipy.sparse import coo_matrix
from scipy.stats import boxcox, chi2, norm

from .generate_task_table import REQUIRED_SETTINGS, connect_to_snowflake, parse_dotenv
from .plot_style import FIGURE_BACKGROUND

SOURCE_TABLE = "EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_VALID_DUR_TASKS"
ROOT = Path(__file__).resolve().parents[2]
SQL_DIRECTORY = Path(__file__).resolve().parents[1] / "sql"
SQL_TEMPLATE = "mc3_coh_pettype_final_model.sql.j2"
NAME = "mc3_coh_pettype_final_model"
GENERATED_SQL_PATH = ROOT / "generated" / f"{NAME}.sql"
RAW_DATA_PATH = ROOT / "outputs" / "data" / f"{NAME}_task_data.parquet"
MODEL_DATA_PATH = ROOT / "outputs" / "data" / f"{NAME}_boxcox_data.parquet"
USER_EFFECTS_PATH = ROOT / "outputs" / "data" / f"{NAME}_user_effects.parquet"
DATE_EFFECTS_PATH = ROOT / "outputs" / "data" / f"{NAME}_date_effects.parquet"
PARENT_EFFECTS_PATH = ROOT / "outputs" / "data" / f"{NAME}_parent_part_effects.parquet"
FIXED_TABLE_PATH = ROOT / "outputs" / "tables" / f"{NAME}_fixed_effects.md"
USER_TABLE_PATH = ROOT / "outputs" / "tables" / f"{NAME}_user_effects.md"
DATE_TABLE_PATH = ROOT / "outputs" / "tables" / f"{NAME}_date_effects.md"
PARENT_TABLE_PATH = ROOT / "outputs" / "tables" / f"{NAME}_parent_part_effects.md"
REPORT_PATH = ROOT / "outputs" / "reports" / "md" / f"{NAME}.md"
CHART_DIRECTORY = ROOT / "outputs" / "charts" / "mc3-coh-pettype-final-model"
USER_QQ_PATH = CHART_DIRECTORY / "user_random_intercepts_qq.png"
DATE_QQ_PATH = CHART_DIRECTORY / "date_random_intercepts_qq.png"
PARENT_QQ_PATH = CHART_DIRECTORY / "parent_part_random_intercepts_qq.png"
RESIDUAL_QQ_PATH = CHART_DIRECTORY / "conditional_residuals_qq.png"
PREDICTION_PATH = CHART_DIRECTORY / "predicted_vs_boxcox_actual.png"
README_PATH = CHART_DIRECTORY / "README.md"
RANDOM_COLUMNS = ("user_id", "d", "parent_part_number")
TREATMENT_COLUMNS = ("same_preceding", "same_following", "has_correction")
CELL_COLUMNS = ("mc3", "coh", "pettype")
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
WEEKDAY_COLUMNS = tuple(f"weekday_{day.lower()}" for day in WEEKDAYS[:-1])
BASE_FIXED_EFFECT_COLUMNS = TREATMENT_COLUMNS + WEEKDAY_COLUMNS
CATEGORICAL_EFFECTS = ("approval_channel", "prescription_source")
ETA_BOUNDS = ((-16.0, 16.0),) * 3


@dataclass(frozen=True)
class BoxCoxResult:
    frame: pd.DataFrame
    lambda_: float


@dataclass(frozen=True)
class FixedEffectDesign:
    frame: pd.DataFrame
    columns: tuple[str, ...]
    labels: tuple[str, ...]
    references: dict[str, str]
    levels: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class CrossProducts:
    y: np.ndarray
    x: np.ndarray
    fixed_columns: tuple[str, ...]
    fixed_labels: tuple[str, ...]
    random_codes: tuple[np.ndarray, ...]
    random_levels: tuple[pd.Index, ...]
    random_offsets: np.ndarray
    cell_codes: np.ndarray
    cells: pd.MultiIndex
    n_cell: np.ndarray
    ztz: np.ndarray
    z_y: np.ndarray
    z_x: np.ndarray
    z_cell: np.ndarray
    y_cell: np.ndarray
    x_cell: np.ndarray
    yy: float
    xy: np.ndarray
    xx: np.ndarray
    residual_df: int


@dataclass(frozen=True)
class ProfileEvaluation:
    eta: np.ndarray
    rho: np.ndarray
    nll: float
    sigma2: float
    beta: np.ndarray
    beta_covariance: np.ndarray
    cell_effects: np.ndarray
    random_effects: np.ndarray
    random_effect_variance: np.ndarray | None


@dataclass(frozen=True)
class FinalModelResult:
    fixed_effects: pd.DataFrame
    user_effects: pd.DataFrame
    date_effects: pd.DataFrame
    parent_effects: pd.DataFrame
    residual_quantiles: pd.DataFrame
    prediction_bins: pd.DataFrame
    random_sds: tuple[float, float, float]
    random_sd_cis: tuple[tuple[float, float], ...]
    residual_sd: float
    residual_sd_ci: tuple[float, float]
    conditional_r_squared: float
    conditional_rmse: float
    n_observations: int
    n_cells: int
    n_users: int
    n_dates: int
    n_parent_parts: int
    reml_nll: float
    converged: bool


def render_sql(percentile: float = 0.95) -> str:
    if not 0 < percentile < 1:
        raise ValueError("percentile must be strictly between zero and one")
    environment = Environment(
        loader=FileSystemLoader(SQL_DIRECTORY),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )
    return environment.get_template(SQL_TEMPLATE).render(
        source_table=SOURCE_TABLE,
        percentile=f"{percentile:.12g}",
    )


def normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    normalized.columns = [str(column).lower() for column in normalized.columns]
    required = {
        "user_id",
        "task_id",
        "d",
        "day_of_week",
        "coh",
        "mc3",
        "pettype",
        "parent_part_number",
        "approval_channel",
        "prescription_source",
        "duration_seconds",
        "p95_seconds",
        *TREATMENT_COLUMNS,
    }
    missing = sorted(required.difference(normalized.columns))
    if missing:
        raise ValueError("model data is missing columns: " + ", ".join(missing))
    if normalized.empty:
        raise ValueError("model data is empty")

    normalized["user_id"] = normalized["user_id"].astype("string")
    normalized["task_id"] = normalized["task_id"].astype("string")
    normalized["d"] = pd.to_datetime(normalized["d"], errors="coerce").dt.date
    normalized["day_of_week"] = normalized["day_of_week"].astype("string").str[:3]
    for column in (
        "coh",
        "mc3",
        "pettype",
        "parent_part_number",
        *CATEGORICAL_EFFECTS,
    ):
        normalized[column] = (
            normalized[column]
            .astype("string")
            .str.strip()
            .replace("", pd.NA)
            .fillna("<Missing>")
            .astype(str)
        )
    for column in ("duration_seconds", "p95_seconds", *TREATMENT_COLUMNS):
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    if normalized[list(required)].isna().any().any():
        raise ValueError("model data contains null or nonnumeric required values")
    expected_weekday = pd.to_datetime(normalized["d"]).dt.strftime("%a")
    if not normalized["day_of_week"].reset_index(drop=True).equals(
        expected_weekday.astype("string").reset_index(drop=True)
    ):
        raise ValueError("day_of_week does not match process date")
    if not set(normalized["day_of_week"].unique()).issubset(WEEKDAYS):
        raise ValueError("day_of_week contains an unexpected value")
    if (normalized["duration_seconds"] <= 0).any():
        raise ValueError("duration_seconds must be strictly positive")
    if not (normalized["duration_seconds"] < normalized["p95_seconds"]).all():
        raise ValueError("model data violates the strict global P95 filter")
    for column in TREATMENT_COLUMNS:
        values = set(normalized[column].astype(int).unique())
        if not values.issubset({0, 1}):
            raise ValueError(f"{column} must contain only zero and one")
        normalized[column] = normalized[column].astype(np.int8)
    for day, column in zip(WEEKDAYS[:-1], WEEKDAY_COLUMNS, strict=True):
        normalized[column] = (normalized["day_of_week"] == day).astype(np.int8)
    return normalized


def transform_duration(
    frame: pd.DataFrame,
    *,
    duration_column: str = "duration_seconds",
    lambda_: float | None = None,
) -> BoxCoxResult:
    """Apply one global Box-Cox transform to positive durations."""

    if duration_column not in frame.columns:
        raise ValueError(f"missing duration column: {duration_column}")
    transformed_frame = frame.copy()
    durations = pd.to_numeric(
        transformed_frame[duration_column], errors="coerce"
    ).to_numpy(dtype=np.float64)
    if not np.isfinite(durations).all():
        raise ValueError("duration contains missing or nonfinite values")
    if (durations <= 0).any():
        raise ValueError("Box-Cox durations must be strictly positive")
    if np.unique(durations).size < 2:
        raise ValueError("Box-Cox requires at least two distinct durations")
    if lambda_ is None:
        transformed, fitted_lambda = boxcox(durations)
    else:
        fitted_lambda = float(lambda_)
        transformed = boxcox(durations, lmbda=fitted_lambda)
    transformed_frame["boxcox_duration"] = transformed
    return BoxCoxResult(frame=transformed_frame, lambda_=float(fitted_lambda))


def build_fixed_effect_design(frame: pd.DataFrame) -> FixedEffectDesign:
    """Build treatment, weekday, approval, and source fixed-effect columns."""

    designed = normalize_frame(frame)
    columns = list(BASE_FIXED_EFFECT_COLUMNS)
    labels = [column.upper() for column in BASE_FIXED_EFFECT_COLUMNS]
    references: dict[str, str] = {}
    levels_by_effect: dict[str, tuple[str, ...]] = {}
    for effect in CATEGORICAL_EFFECTS:
        counts = designed[effect].value_counts()
        maximum = counts.max()
        reference = sorted(counts[counts == maximum].index.astype(str))[0]
        levels = tuple(sorted(set(designed[effect].astype(str)) - {reference}))
        references[effect] = reference
        levels_by_effect[effect] = levels
        for index, level in enumerate(levels):
            column = f"{effect}_contrast_{index}"
            designed[column] = (designed[effect] == level).astype(np.int8)
            columns.append(column)
            labels.append(f"{effect.upper()}[{level} vs {reference}]")
    return FixedEffectDesign(
        frame=designed,
        columns=tuple(columns),
        labels=tuple(labels),
        references=references,
        levels=levels_by_effect,
    )


def _cross_products(design: FixedEffectDesign) -> CrossProducts:
    frame = normalize_frame(design.frame)
    y = frame["boxcox_duration"].to_numpy(dtype=np.float64)
    x = frame.loc[:, design.columns].to_numpy(dtype=np.float64)
    if not np.isfinite(y).all() or not np.isfinite(x).all():
        raise ValueError("model outcome and covariates must be finite")
    random_codes_list: list[np.ndarray] = []
    random_levels_list: list[pd.Index] = []
    for column in RANDOM_COLUMNS:
        codes, levels = pd.factorize(frame[column], sort=True)
        random_codes_list.append(codes)
        random_levels_list.append(pd.Index(levels))
    random_codes = tuple(random_codes_list)
    random_levels = tuple(random_levels_list)
    sizes = np.array([len(levels) for levels in random_levels], dtype=np.int64)
    offsets = np.concatenate(([0], np.cumsum(sizes)))
    q = int(offsets[-1])
    n = len(frame)

    ztz = np.zeros((q, q), dtype=np.float64)
    for index, codes in enumerate(random_codes):
        start, end = offsets[index : index + 2]
        counts = np.bincount(codes, minlength=end - start)
        ztz[start + np.arange(end - start), start + np.arange(end - start)] = counts
    for first in range(len(random_codes)):
        for second in range(first + 1, len(random_codes)):
            first_start, first_end = offsets[first : first + 2]
            second_start, second_end = offsets[second : second + 2]
            block = coo_matrix(
                (
                    np.ones(n),
                    (random_codes[first], random_codes[second]),
                ),
                shape=(first_end - first_start, second_end - second_start),
            ).toarray()
            ztz[first_start:first_end, second_start:second_end] = block
            ztz[second_start:second_end, first_start:first_end] = block.T

    z_y_parts = []
    z_x_parts = []
    for index, codes in enumerate(random_codes):
        size = sizes[index]
        z_y_parts.append(np.bincount(codes, weights=y, minlength=size))
        z_x_parts.append(
            np.column_stack(
                [
                    np.bincount(codes, weights=x[:, j], minlength=size)
                    for j in range(x.shape[1])
                ]
            )
        )
    z_y = np.concatenate(z_y_parts)
    z_x = np.vstack(z_x_parts)

    cell_index = pd.MultiIndex.from_frame(frame.loc[:, CELL_COLUMNS])
    cell_codes, cells = pd.factorize(cell_index, sort=True)
    z_cell_parts = []
    for index, codes in enumerate(random_codes):
        z_cell_parts.append(
            coo_matrix(
                (np.ones(n), (cell_codes, codes)),
                shape=(len(cells), sizes[index]),
            ).toarray()
        )
    z_cell = np.hstack(z_cell_parts)
    n_cell = np.bincount(cell_codes).astype(np.float64)
    y_cell = np.bincount(cell_codes, weights=y)
    x_cell = np.column_stack(
        [np.bincount(cell_codes, weights=x[:, j]) for j in range(x.shape[1])]
    )
    residual_df = n - len(cells) - x.shape[1]
    if residual_df <= 0:
        raise ValueError("not enough residual degrees of freedom for the model")
    return CrossProducts(
        y=y,
        x=x,
        fixed_columns=design.columns,
        fixed_labels=design.labels,
        random_codes=random_codes,
        random_levels=random_levels,
        random_offsets=offsets,
        cell_codes=cell_codes,
        cells=cells,
        n_cell=n_cell,
        ztz=ztz,
        z_y=z_y,
        z_x=z_x,
        z_cell=z_cell,
        y_cell=y_cell,
        x_cell=x_cell,
        yy=float(y @ y),
        xy=x.T @ y,
        xx=x.T @ x,
        residual_df=residual_df,
    )


def _evaluate_profile(
    eta: np.ndarray,
    stats: CrossProducts,
    *,
    include_random_variance: bool = False,
) -> ProfileEvaluation:
    eta = np.asarray(eta, dtype=np.float64)
    rho = np.exp(eta)
    sizes = np.diff(stats.random_offsets)
    inverse_g = np.concatenate(
        [np.full(size, 1.0 / rho[index]) for index, size in enumerate(sizes)]
    )
    random_information = stats.ztz.copy()
    random_information.flat[:: len(inverse_g) + 1] += inverse_g
    random_factor = cho_factor(random_information, lower=True, check_finite=False)

    def solve_random(values: np.ndarray) -> np.ndarray:
        return cho_solve(random_factor, values, check_finite=False)

    solved_y = solve_random(stats.z_y)
    solved_x = solve_random(stats.z_x)
    solved_cell = solve_random(stats.z_cell.T)
    yry = stats.yy - float(stats.z_y @ solved_y)
    xry = stats.xy - stats.z_x.T @ solved_y
    xrx = stats.xx - stats.z_x.T @ solved_x
    dy = stats.y_cell - stats.z_cell @ solved_y
    dx = stats.x_cell - stats.z_cell @ solved_x
    cell_information = np.diag(stats.n_cell) - stats.z_cell @ solved_cell
    cell_information = (cell_information + cell_information.T) / 2.0
    cell_factor = cho_factor(cell_information, lower=True, check_finite=False)
    solved_dy = cho_solve(cell_factor, dy, check_finite=False)
    solved_dx = cho_solve(cell_factor, dx, check_finite=False)
    information = xrx - dx.T @ solved_dx
    information = (information + information.T) / 2.0
    information_factor = cho_factor(information, lower=True, check_finite=False)
    rhs = xry - dx.T @ solved_dy
    beta = cho_solve(information_factor, rhs, check_finite=False)
    cell_effects = cho_solve(cell_factor, dy - dx @ beta, check_finite=False)
    rss = yry - float(cell_effects @ dy) - float(beta @ xry)
    if not np.isfinite(rss) or rss <= 0:
        raise ValueError("profile residual sum of squares is not positive")
    sigma2 = rss / stats.residual_df
    logdet_random = 2.0 * float(np.log(np.diag(random_factor[0])).sum())
    logdet_r = float(sizes @ eta) + logdet_random
    logdet_cells = 2.0 * float(np.log(np.diag(cell_factor[0])).sum())
    logdet_fixed = 2.0 * float(np.log(np.diag(information_factor[0])).sum())
    nll = 0.5 * (
        stats.residual_df
        * (np.log(2.0 * np.pi) + 1.0 + np.log(sigma2))
        + logdet_r
        + logdet_cells
        + logdet_fixed
    )
    beta_covariance = sigma2 * cho_solve(
        information_factor,
        np.eye(len(stats.fixed_columns)),
        check_finite=False,
    )
    random_sum = stats.z_y - stats.z_x @ beta - stats.z_cell.T @ cell_effects
    random_effects = solve_random(random_sum)
    random_variance = None
    if include_random_variance:
        random_variance = sigma2 * np.diag(
            solve_random(np.eye(len(inverse_g), dtype=np.float64))
        )
    return ProfileEvaluation(
        eta=eta,
        rho=rho,
        nll=float(nll),
        sigma2=float(sigma2),
        beta=beta,
        beta_covariance=beta_covariance,
        cell_effects=cell_effects,
        random_effects=random_effects,
        random_effect_variance=random_variance,
    )


def _eta_covariance(best: ProfileEvaluation, stats: CrossProducts) -> np.ndarray:
    step = 1e-3
    dimension = len(best.eta)
    hessian = np.empty((dimension, dimension), dtype=np.float64)
    for first in range(dimension):
        direction = np.zeros(dimension)
        direction[first] = step
        hessian[first, first] = (
            _evaluate_profile(best.eta + direction, stats).nll
            - 2.0 * best.nll
            + _evaluate_profile(best.eta - direction, stats).nll
        ) / step**2
        for second in range(first + 1, dimension):
            direction_second = np.zeros(dimension)
            direction_second[second] = step
            value = (
                _evaluate_profile(best.eta + direction + direction_second, stats).nll
                - _evaluate_profile(best.eta + direction - direction_second, stats).nll
                - _evaluate_profile(best.eta - direction + direction_second, stats).nll
                + _evaluate_profile(best.eta - direction - direction_second, stats).nll
            ) / (4.0 * step**2)
            hessian[first, second] = value
            hessian[second, first] = value
    return np.linalg.inv(hessian)


def _random_sd_interval(
    index: int,
    best: ProfileEvaluation,
    stats: CrossProducts,
    eta_covariance: np.ndarray,
) -> tuple[float, float]:
    step = 1e-4

    def log_sd(eta: np.ndarray) -> float:
        evaluation = _evaluate_profile(eta, stats)
        return 0.5 * (eta[index] + np.log(evaluation.sigma2))

    gradient = np.empty(len(best.eta))
    for component in range(len(best.eta)):
        direction = np.zeros(len(best.eta))
        direction[component] = step
        gradient[component] = (
            log_sd(best.eta + direction) - log_sd(best.eta - direction)
        ) / (2.0 * step)
    standard_error = float(np.sqrt(gradient @ eta_covariance @ gradient))
    center = log_sd(best.eta)
    critical = norm.ppf(0.975)
    return (
        float(np.exp(center - critical * standard_error)),
        float(np.exp(center + critical * standard_error)),
    )


def _effect_frame(
    levels: pd.Index,
    codes: np.ndarray,
    effects: np.ndarray,
    variances: np.ndarray,
    identifier: str,
) -> pd.DataFrame:
    standard_errors = np.sqrt(variances)
    return pd.DataFrame(
        {
            identifier: levels.astype(str),
            "task_count": np.bincount(codes),
            "random_intercept": effects,
            "conditional_std_error": standard_errors,
            "ci_lower": effects - norm.ppf(0.975) * standard_errors,
            "ci_upper": effects + norm.ppf(0.975) * standard_errors,
        }
    ).sort_values("random_intercept", ignore_index=True)


def _prediction_bins(predicted: np.ndarray, observed: np.ndarray) -> pd.DataFrame:
    lower = float(min(predicted.min(), observed.min()))
    upper = float(max(predicted.max(), observed.max()))
    edges = np.linspace(lower, upper, 121)
    counts, predicted_edges, actual_edges = np.histogram2d(
        predicted, observed, bins=(edges, edges)
    )
    predicted_indices, actual_indices = np.nonzero(counts)
    return pd.DataFrame(
        {
            "predicted_lower": predicted_edges[predicted_indices],
            "predicted_upper": predicted_edges[predicted_indices + 1],
            "actual_lower": actual_edges[actual_indices],
            "actual_upper": actual_edges[actual_indices + 1],
            "count": counts[predicted_indices, actual_indices].astype(np.int64),
        }
    )


def fit_final_model(design: FixedEffectDesign) -> FinalModelResult:
    stats = _cross_products(design)

    def objective(eta: np.ndarray) -> float:
        try:
            return _evaluate_profile(eta, stats).nll
        except (ValueError, np.linalg.LinAlgError):
            return np.inf

    optimization = minimize(
        objective,
        x0=np.zeros(3),
        bounds=ETA_BOUNDS,
        method="L-BFGS-B",
        options={"ftol": 1e-11, "gtol": 1e-7, "maxiter": 200},
    )
    if not optimization.success or not np.isfinite(optimization.fun):
        raise ValueError(f"REML optimization failed: {optimization.message}")
    best = _evaluate_profile(
        np.asarray(optimization.x), stats, include_random_variance=True
    )
    if best.random_effect_variance is None:
        raise ValueError("random-effect variance was not calculated")
    eta_covariance = _eta_covariance(best, stats)
    random_sd_cis = tuple(
        _random_sd_interval(index, best, stats, eta_covariance)
        for index in range(3)
    )
    standard_errors = np.sqrt(np.diag(best.beta_covariance))
    z_values = best.beta / standard_errors
    fixed_effects = pd.DataFrame(
        {
            "term": stats.fixed_labels,
            "estimate": best.beta,
            "std_error": standard_errors,
            "z_value": z_values,
            "p_value": 2.0 * norm.sf(np.abs(z_values)),
            "ci_lower": best.beta - norm.ppf(0.975) * standard_errors,
            "ci_upper": best.beta + norm.ppf(0.975) * standard_errors,
        }
    )

    effect_frames = []
    for index, identifier in enumerate(("user_id", "d", "parent_part_number")):
        start, end = stats.random_offsets[index : index + 2]
        effect_frames.append(
            _effect_frame(
                stats.random_levels[index],
                stats.random_codes[index],
                best.random_effects[start:end],
                best.random_effect_variance[start:end],
                identifier,
            )
        )
    conditional_residuals = stats.y - stats.x @ best.beta - best.cell_effects[
        stats.cell_codes
    ]
    for index, codes in enumerate(stats.random_codes):
        start, end = stats.random_offsets[index : index + 2]
        conditional_residuals -= best.random_effects[start:end][codes]
    fitted_values = stats.y - conditional_residuals
    residual_sd = float(np.sqrt(best.sigma2))
    probabilities = (np.arange(2_000) + 0.5) / 2_000
    residual_quantiles = pd.DataFrame(
        {
            "theoretical": norm.ppf(probabilities),
            "observed": np.quantile(
                conditional_residuals / residual_sd, probabilities
            ),
        }
    )
    residual_df = stats.residual_df
    return FinalModelResult(
        fixed_effects=fixed_effects,
        user_effects=effect_frames[0],
        date_effects=effect_frames[1],
        parent_effects=effect_frames[2],
        residual_quantiles=residual_quantiles,
        prediction_bins=_prediction_bins(fitted_values, stats.y),
        random_sds=tuple(
            float(np.sqrt(best.rho[index] * best.sigma2)) for index in range(3)
        ),
        random_sd_cis=random_sd_cis,
        residual_sd=residual_sd,
        residual_sd_ci=(
            float(
                np.sqrt(
                    residual_df * best.sigma2 / chi2.ppf(0.975, residual_df)
                )
            ),
            float(
                np.sqrt(
                    residual_df * best.sigma2 / chi2.ppf(0.025, residual_df)
                )
            ),
        ),
        conditional_r_squared=float(
            1.0
            - np.sum(conditional_residuals**2)
            / np.sum((stats.y - stats.y.mean()) ** 2)
        ),
        conditional_rmse=float(np.sqrt(np.mean(conditional_residuals**2))),
        n_observations=len(stats.y),
        n_cells=len(stats.cells),
        n_users=len(stats.random_levels[0]),
        n_dates=len(stats.random_levels[1]),
        n_parent_parts=len(stats.random_levels[2]),
        reml_nll=best.nll,
        converged=bool(optimization.success),
    )


def write_generated_sql(sql: str) -> Path:
    GENERATED_SQL_PATH.parent.mkdir(parents=True, exist_ok=True)
    GENERATED_SQL_PATH.write_text(sql.rstrip() + "\n", encoding="utf-8")
    return GENERATED_SQL_PATH


def fetch_to_parquet(settings: dict[str, str], sql: str, path: Path) -> Path:
    """Stream a Snowflake result into an atomic local Parquet cache."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".tmp.parquet")
    temporary_path.unlink(missing_ok=True)
    writer: pq.ParquetWriter | None = None
    connection = connect_to_snowflake(settings)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(sql)
            columns = [column[0].lower() for column in cursor.description]
            while rows := cursor.fetchmany(100_000):
                batch = pd.DataFrame.from_records(rows, columns=columns)
                table = pa.Table.from_pandas(batch, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(temporary_path, table.schema)
                writer.write_table(table)
        finally:
            cursor.close()
    finally:
        if writer is not None:
            writer.close()
        connection.close()
    if writer is None:
        temporary_path.unlink(missing_ok=True)
        raise ValueError("Snowflake query returned no rows")
    os.replace(temporary_path, path)
    return path


def _fixed_effects_markdown(frame: pd.DataFrame) -> str:
    lines = [
        "| Term | Estimate | SE | z | p-value | 95% CI | Significant |",
        "|---|---:|---:|---:|---:|---:|:---:|",
    ]
    for row in frame.itertuples(index=False):
        p_value = "<1e-300" if row.p_value == 0 else f"{row.p_value:.6g}"
        significant = "Yes" if row.ci_lower > 0 or row.ci_upper < 0 else "No"
        lines.append(
            f"| {row.term} | {row.estimate:.6f} | {row.std_error:.6f} | "
            f"{row.z_value:.4f} | {p_value} | "
            f"[{row.ci_lower:.6f}, {row.ci_upper:.6f}] | {significant} |"
        )
    return "\n".join(lines)


def _random_effects_markdown(frame: pd.DataFrame, *, identifier: str) -> str:
    lines = [
        f"| {identifier} | Tasks | Random intercept | Conditional SE | 95% CI |",
        "|---|---:|---:|---:|---:|",
    ]
    id_column = frame.columns[0]
    for row in frame.itertuples(index=False):
        value = getattr(row, id_column)
        lines.append(
            f"| {value} | {row.task_count:,} | {row.random_intercept:.6f} | "
            f"{row.conditional_std_error:.6f} | "
            f"[{row.ci_lower:.6f}, {row.ci_upper:.6f}] |"
        )
    return "\n".join(lines)


def _qq_frame(effects: pd.DataFrame) -> pd.DataFrame:
    ordered = effects["random_intercept"].sort_values().to_numpy(dtype=float)
    probabilities = (np.arange(len(ordered)) + 0.5) / len(ordered)
    theoretical = norm.ppf(probabilities) * ordered.std(ddof=1) + ordered.mean()
    return pd.DataFrame({"theoretical": theoretical, "observed": ordered})


def _write_qq_plot(frame: pd.DataFrame, path: Path, title: str, y_title: str) -> None:
    lower = float(min(frame.min()))
    upper = float(max(frame.max()))
    identity = alt.Chart(
        pd.DataFrame({"x": [lower, upper], "y": [lower, upper]})
    ).mark_line(color="#b2182b", strokeDash=[6, 4]).encode(x="x:Q", y="y:Q")
    points = alt.Chart(frame).mark_circle(size=45, opacity=0.7).encode(
        x=alt.X("theoretical:Q", title="Theoretical normal quantile"),
        y=alt.Y("observed:Q", title=y_title),
    )
    chart = (points + identity).properties(
        title=title,
        width=700,
        height=520,
    ).configure(background=FIGURE_BACKGROUND).configure_view(
        stroke=None, fill=FIGURE_BACKGROUND
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    chart.save(path, scale_factor=2)


def write_tables(result: FinalModelResult) -> None:
    FIXED_TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXED_TABLE_PATH.write_text(
        "# Final-model fixed effects\n\n"
        + _fixed_effects_markdown(result.fixed_effects)
        + "\n",
        encoding="utf-8",
    )
    for path, title, frame, identifier in (
        (USER_TABLE_PATH, "User random intercepts", result.user_effects, "USER_ID"),
        (DATE_TABLE_PATH, "Date random intercepts", result.date_effects, "Date"),
        (
            PARENT_TABLE_PATH,
            "Parent-part-number random intercepts",
            result.parent_effects,
            "Parent part number",
        ),
    ):
        path.write_text(
            f"# {title}\n\n"
            + _random_effects_markdown(frame, identifier=identifier)
            + "\n",
            encoding="utf-8",
        )


def write_diagnostics(result: FinalModelResult) -> None:
    for frame, path, title, y_title in (
        (
            result.user_effects,
            USER_QQ_PATH,
            "Q–Q plot of estimated user random intercepts",
            "Estimated user random intercept",
        ),
        (
            result.date_effects,
            DATE_QQ_PATH,
            "Q–Q plot of estimated date random intercepts",
            "Estimated date random intercept",
        ),
        (
            result.parent_effects,
            PARENT_QQ_PATH,
            "Q–Q plot of estimated parent-part random intercepts",
            "Estimated parent-part random intercept",
        ),
    ):
        _write_qq_plot(_qq_frame(frame), path, title, y_title)
    _write_qq_plot(
        result.residual_quantiles,
        RESIDUAL_QQ_PATH,
        "Q–Q plot of conditional level-1 residuals",
        "Standardized conditional residual quantile",
    )

    bounds = result.prediction_bins[
        ["predicted_lower", "predicted_upper", "actual_lower", "actual_upper"]
    ].to_numpy()
    lower = float(bounds.min())
    upper = float(bounds.max())
    heatmap = alt.Chart(result.prediction_bins).mark_rect().encode(
        x=alt.X("predicted_lower:Q", title="Conditional prediction (Box-Cox scale)"),
        x2="predicted_upper:Q",
        y=alt.Y("actual_lower:Q", title="Observed duration (Box-Cox scale)"),
        y2="actual_upper:Q",
        color=alt.Color("count:Q", title="Tasks", scale=alt.Scale(type="log", scheme="blues")),
    )
    identity = alt.Chart(
        pd.DataFrame({"predicted": [lower, upper], "actual": [lower, upper]})
    ).mark_line(color="#b2182b", strokeDash=[6, 4], strokeWidth=2).encode(
        x="predicted:Q", y="actual:Q"
    )
    chart = (heatmap + identity).properties(
        title={
            "text": "Conditional predictions versus Box-Cox outcomes",
            "subtitle": (
                f"All {result.n_observations:,} tasks; "
                f"conditional R² = {result.conditional_r_squared:.4f}, "
                f"RMSE = {result.conditional_rmse:.4f}"
            ),
        },
        width=700,
        height=600,
    ).configure(background=FIGURE_BACKGROUND).configure_view(
        stroke=None, fill=FIGURE_BACKGROUND
    )
    PREDICTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    chart.save(PREDICTION_PATH, scale_factor=2)
    README_PATH.write_text(
        "# Final-model diagnostics\n\n"
        "![User Q–Q plot](user_random_intercepts_qq.png)\n\n"
        "![Date Q–Q plot](date_random_intercepts_qq.png)\n\n"
        "![Parent-part Q–Q plot](parent_part_random_intercepts_qq.png)\n\n"
        "![Residual Q–Q plot](conditional_residuals_qq.png)\n\n"
        "![Predicted versus outcome](predicted_vs_boxcox_actual.png)\n",
        encoding="utf-8",
    )


def write_report(
    model_data: pd.DataFrame,
    transform: BoxCoxResult,
    design: FixedEffectDesign,
    result: FinalModelResult,
) -> Path:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report_directory = REPORT_PATH.parent

    def link(path: Path) -> str:
        return os.path.relpath(path, report_directory)

    REPORT_PATH.write_text(
        rf"""# Final MC3/COH/PETTYPE mixed-effects model

## Purpose and analysis sample

This is the final model. It estimates how same-cell sequence position relates
to DUR duration while controlling for correction status, weekday, approval
channel, prescription source, and MC3/COH/PETTYPE cell. It includes crossed
random intercepts for user, process date, and parent part number.

The source is `{SOURCE_TABLE}`. Eligible rows have non-null user, task,
process-start time, `MC3_COH_PETTYPE_SEQN`, and
`MC3_COH_PETTYPE_BATCH_LEN`; sequence and batch length are at least one, and
sequence does not exceed batch length. Duration is
`IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS`.

Let $Y_i$ be the positive imputed duration in seconds for task $i$. One
global cutoff is calculated over all otherwise eligible tasks:

$$
q_{{0.95}}=\mathrm{{APPROX\_PERCENTILE}}(Y,0.95).
$$

The fitted sample keeps tasks satisfying $0<Y_i<q_{{0.95}}$; the upper
bound is strict. MC3, COH, PETTYPE, parent part number, approval channel, and
prescription source blanks are represented by `<Missing>`.

## Derived indicators

For sequence number $S_i$, batch length $L_i$, and correction count
$N_i$, the three binary fixed effects are

$$
P_i=\mathbf{{1}}(L_i>1\ \land\ S_i>1),
\qquad
F_i=\mathbf{{1}}(L_i>1\ \land\ S_i<L_i),
\qquad
C_i=\mathbf{{1}}(N_i>0).
$$

Thus $P_i$ is `SAME_PRECEDING`, $F_i$ is `SAME_FOLLOWING`, and $C_i$
is `HAS_CORRECTION`.

## Outcome transformation

The retained durations receive one global Box-Cox transformation:

$$
Z_i=g_\lambda(Y_i)=
\begin{{cases}}
\dfrac{{Y_i^\lambda-1}}{{\lambda}}, & \lambda\ne0,\\[4pt]
\log(Y_i), & \lambda=0.
\end{{cases}}
$$

The maximum-likelihood transformation estimate is
$\widehat{{\lambda}}={transform.lambda_:.8f}$. All coefficients, random
effects, standard deviations, residuals, RMSE, and diagnostics are therefore
on the Box-Cox scale.

## Complete model formula

Index task, fixed-effect cell, user, date, and parent part by $i,c,u,d,p$.
The model is

$$
\begin{{aligned}}
Z_i={{}}&\gamma_{{c(i)}}+\beta_P P_i+\beta_F F_i+\beta_C C_i\\
&+\sum_{{w\ne\mathrm{{Sun}}}}\delta_w\mathbf{{1}}(W_i=w)\\
&+\sum_{{a\ne a_0}}\theta_a\mathbf{{1}}(A_i=a)
+\sum_{{s\ne s_0}}\phi_s\mathbf{{1}}(R_i=s)\\
&+b_{{u(i)}}+h_{{d(i)}}+r_{{p(i)}}+\epsilon_i.
\end{{aligned}}
$$

Here $\gamma_{{c(i)}}$ is a fixed effect shared by all tasks in the same
MC3 + COH + PETTYPE cell. The model uses a full set of cell effects and no
separate overall intercept. Sunday is the weekday reference. The
data-dependent categorical references are:

- approval channel $a_0$: `{design.references['approval_channel']}`
- prescription source $s_0$: `{design.references['prescription_source']}`

Each reference is the most frequent retained level; lexicographic order breaks
a frequency tie. The crossed random terms and level-1 error are mutually
independent and satisfy

$$
b_u\sim N(0,\sigma_u^2),\qquad
h_d\sim N(0,\sigma_d^2),\qquad
r_p\sim N(0,\sigma_p^2),\qquad
\epsilon_i\sim N(0,\sigma_e^2).
$$

The fixed effects and variance components are estimated jointly by REML. The
conditional fitted value and residual are

$$
\widehat{{Z}}_i=\widehat{{\gamma}}_{{c(i)}}+x_i^T\widehat{{\beta}}
+\widehat{{b}}_{{u(i)}}+\widehat{{h}}_{{d(i)}}+\widehat{{r}}_{{p(i)}},
\qquad e_i=Z_i-\widehat{{Z}}_i.
$$

## Inference and fit statistics

For fixed effect $k$, the report uses

$$
z_k=\frac{{\widehat{{\beta}}_k}}{{\mathrm{{SE}}(\widehat{{\beta}}_k)}},\qquad
p_k=2\Phi(-\lvert z_k\rvert),\qquad
\mathrm{{CI}}_{{95}}=\widehat{{\beta}}_k\pm1.96\,\mathrm{{SE}}(\widehat{{\beta}}_k).
$$

The fixed-effect table labels an estimate `Significant = Yes` when its 95%
confidence interval excludes zero; intervals that cross or touch zero are
marked `No`.

Random-effect SD intervals use an observed-information Wald approximation on
the log-SD scale. The residual-SD interval uses the chi-square distribution.
The reported conditional metrics include all fixed and random effects:

$$
R_c^2=1-\frac{{\sum_i e_i^2}}{{\sum_i(Z_i-\bar Z)^2}},\qquad
RMSE_c=\sqrt{{\frac1n\sum_i e_i^2}}.
$$

## Sample and fit

| Quantity | Value |
|---|---:|
| Tasks | {result.n_observations:,} |
| MC3/COH/PETTYPE cells | {result.n_cells:,} |
| Users | {result.n_users:,} |
| Dates | {result.n_dates:,} |
| Parent part numbers | {result.n_parent_parts:,} |
| Approval-channel levels | {len(design.levels['approval_channel']) + 1:,} |
| Prescription-source levels | {len(design.levels['prescription_source']) + 1:,} |
| Global approximate P95 cutoff (seconds) | {model_data['p95_seconds'].iloc[0]:.6f} |
| Box-Cox lambda | {transform.lambda_:.8f} |
| Conditional R-squared | {result.conditional_r_squared:.6f} |
| Conditional RMSE (Box-Cox scale) | {result.conditional_rmse:.6f} |
| REML negative log-likelihood | {result.reml_nll:.6f} |
| Converged | {result.converged} |

## Fixed effects

{_fixed_effects_markdown(result.fixed_effects)}

## Variance components

| Component | SD | Approximate 95% CI |
|---|---:|---:|
| User random intercept | {result.random_sds[0]:.6f} | [{result.random_sd_cis[0][0]:.6f}, {result.random_sd_cis[0][1]:.6f}] |
| Date random intercept | {result.random_sds[1]:.6f} | [{result.random_sd_cis[1][0]:.6f}, {result.random_sd_cis[1][1]:.6f}] |
| Parent-part random intercept | {result.random_sds[2]:.6f} | [{result.random_sd_cis[2][0]:.6f}, {result.random_sd_cis[2][1]:.6f}] |
| Residual | {result.residual_sd:.6f} | [{result.residual_sd_ci[0]:.6f}, {result.residual_sd_ci[1]:.6f}] |

## Diagnostics

![User Q–Q plot]({link(USER_QQ_PATH)})

![Date Q–Q plot]({link(DATE_QQ_PATH)})

![Parent-part Q–Q plot]({link(PARENT_QQ_PATH)})

![Residual Q–Q plot]({link(RESIDUAL_QQ_PATH)})

![Predicted versus outcome]({link(PREDICTION_PATH)})

## Artifacts

- [Generated SQL]({link(GENERATED_SQL_PATH)})
- [Raw Snowflake data]({link(RAW_DATA_PATH)})
- [Transformed model data]({link(MODEL_DATA_PATH)})
- [Fixed-effect table]({link(FIXED_TABLE_PATH)})
- [User random effects]({link(USER_TABLE_PATH)})
- [Date random effects]({link(DATE_TABLE_PATH)})
- [Parent-part random effects]({link(PARENT_TABLE_PATH)})
""",
        encoding="utf-8",
    )
    return REPORT_PATH


@click.command()
@click.option(
    "--env-file",
    type=click.Path(path_type=Path, dir_okay=False),
    default=Path(".env"),
    show_default=True,
)
@click.option(
    "--redraw-only",
    is_flag=True,
    help="Reuse cached raw data and rerun transformation, fitting, and reporting.",
)
@click.option("--percentile", type=float, default=0.95, show_default=True)
def main(env_file: Path, redraw_only: bool, percentile: float) -> None:
    """Fit the final crossed random-intercept model."""

    try:
        sql = render_sql(percentile)
        write_generated_sql(sql)
        if redraw_only:
            if not RAW_DATA_PATH.is_file():
                raise ValueError(f"cached raw data not found: {RAW_DATA_PATH}")
            click.echo(f"Loaded cached raw data: {RAW_DATA_PATH}")
        else:
            if not env_file.is_file():
                raise ValueError(f"environment file not found: {env_file}")
            settings = parse_dotenv(env_file)
            missing = [key for key in REQUIRED_SETTINGS if key not in settings]
            if missing:
                raise ValueError("missing required settings: " + ", ".join(missing))
            fetch_to_parquet(settings, sql, RAW_DATA_PATH)
            click.echo(f"Downloaded raw data: {RAW_DATA_PATH}")

        raw_data = normalize_frame(pd.read_parquet(RAW_DATA_PATH))
        transformation = transform_duration(raw_data)
        design = build_fixed_effect_design(transformation.frame)
        MODEL_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        design.frame.to_parquet(MODEL_DATA_PATH, index=False)
        result = fit_final_model(design)
        result.user_effects.to_parquet(USER_EFFECTS_PATH, index=False)
        result.date_effects.to_parquet(DATE_EFFECTS_PATH, index=False)
        result.parent_effects.to_parquet(PARENT_EFFECTS_PATH, index=False)
        write_tables(result)
        write_diagnostics(result)
        write_report(design.frame, transformation, design, result)
    except (OSError, ValueError, np.linalg.LinAlgError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(f"Created final-model report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
