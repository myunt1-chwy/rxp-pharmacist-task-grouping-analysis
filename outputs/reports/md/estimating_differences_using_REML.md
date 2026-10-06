# Estimating Differences Using REML

## Question and estimand

This analysis estimates the difference in DUR work time between Same Cohort and
Different Cohort for users with observations in both allocation patterns. The
effect for user *i* is `d_i = mean_same_i - mean_different_i`.

The directional hypothesis is **Same Cohort − Different Cohort < 0**. A negative
effect means that Same Cohort tasks are faster for that user on average.

## Why REML is used

Users contribute different numbers of tasks, so their user means have different
precision. For each user, the sampling variance of the paired difference is
estimated as `v_i = s_same_i^2 / n_same_i + s_different_i^2 / n_different_i`.

The random-effects model is `d_i = mu + u_i + e_i`, where
`u_i ~ N(0, tau^2)` captures between-user heterogeneity and
`e_i ~ N(0, v_i)` captures sampling error.

REML estimates `tau^2`, the residual between-user variance after accounting
for each user's sampling variance. The random-effects weight is
`1 / (v_i + tau^2)`, so users with more precise means receive more weight,
while genuine user-to-user heterogeneity prevents any single precise user from
dominating.

## REML optimization objective

For each candidate `tau2`, the analysis defines `V_i = v_i + tau2` and
`w_i = 1 / V_i`. The fixed effect at that candidate is the generalized
least-squares weighted mean:

`mu_tau = sum(w_i * d_i) / sum(w_i)`

The function `_reml_objective` minimizes the following criterion:

`J(tau2) = sum(log(V_i)) + log(sum(w_i)) + sum(w_i * (d_i - mu_tau)^2)`

This is minus twice the restricted log likelihood, up to a constant, for a
model with one fixed intercept. The three terms represent the covariance
volume, the fixed-effect adjustment, and the weighted residual sum of squares.

The implementation optimizes the transformed parameter `log_scale` over the
bounded interval `[0, 20]`, using `tau2 = scale * (exp(log_scale) - 1)`.
The transformation enforces `tau2 >= 0`. The exact `tau2 = 0` boundary is
evaluated separately and selected whenever it is at least as good as the
interior optimizer result.

The reported p-value is a lower-tail normal/Wald test of `H0: mu >= 0`
against `H1: mu < 0`. The interval is the corresponding one-sided 95%
upper bound. This is an asymptotic random-effects inference; uncertainty in the
estimated `tau` is not separately included in the Wald standard error.

## Handling users with one task in an allocation pattern

The task-level extract contains 964 paired users. 25
user-pattern cells contain one task, so a within-user variance cannot be computed for those cells.
For those cells only, the analysis uses the pooled residual variance for the
same cohort and allocation pattern. The actual user task count remains in the
denominator of `v_i`. All other cells use the user's own sample variance.

This fallback retains the paired users while making the sparse-cell assumption
explicit. The pooled variance fallback counts are reported by cohort below.

## Cohort 1

| Quantity | Result |
|---|---:|
| Paired users | 289 |
| Median Same Cohort tasks per user | 1315.0 |
| Median Different Cohort tasks per user | 1108.0 |
| Mean unweighted difference (minutes) | -0.0626 |
| REML weighted difference (minutes) | -0.0302 |
| REML standard error (minutes) | 0.0018 |
| Between-user variance, tau² (minutes²) | 0.0002 |
| Between-user SD, tau (minutes) | 0.0152 |
| REML z-statistic | -16.7244 |
| 95% one-sided upper bound (minutes) | (-∞, -0.0272] |
| One-sided p-value | 4.35485e-63 |
| Cells using pooled variance fallback | 4 |

At the 0.05 level, we **reject** the null hypothesis for Cohort 1.

## Cohort 2

| Quantity | Result |
|---|---:|
| Paired users | 286 |
| Median Same Cohort tasks per user | 913.5 |
| Median Different Cohort tasks per user | 1117.0 |
| Mean unweighted difference (minutes) | -0.0365 |
| REML weighted difference (minutes) | -0.0069 |
| REML standard error (minutes) | 0.0020 |
| Between-user variance, tau² (minutes²) | 0.0002 |
| Between-user SD, tau (minutes) | 0.0132 |
| REML z-statistic | -3.4930 |
| 95% one-sided upper bound (minutes) | (-∞, -0.0037] |
| One-sided p-value | 0.000238773 |
| Cells using pooled variance fallback | 8 |

At the 0.05 level, we **reject** the null hypothesis for Cohort 2.

## Cohort 3

| Quantity | Result |
|---|---:|
| Paired users | 250 |
| Median Same Cohort tasks per user | 29.5 |
| Median Different Cohort tasks per user | 312.5 |
| Mean unweighted difference (minutes) | -0.0559 |
| REML weighted difference (minutes) | -0.0808 |
| REML standard error (minutes) | 0.0099 |
| Between-user variance, tau² (minutes²) | 0.0058 |
| Between-user SD, tau (minutes) | 0.0764 |
| REML z-statistic | -8.1451 |
| 95% one-sided upper bound (minutes) | (-∞, -0.0645] |
| One-sided p-value | 1.89478e-16 |
| Cells using pooled variance fallback | 11 |

At the 0.05 level, we **reject** the null hypothesis for Cohort 3.

## Cohort 4

| Quantity | Result |
|---|---:|
| Paired users | 139 |
| Median Same Cohort tasks per user | 65.0 |
| Median Different Cohort tasks per user | 349.0 |
| Mean unweighted difference (minutes) | -0.0164 |
| REML weighted difference (minutes) | -0.0394 |
| REML standard error (minutes) | 0.0124 |
| Between-user variance, tau² (minutes²) | 0.0074 |
| Between-user SD, tau (minutes) | 0.0862 |
| REML z-statistic | -3.1847 |
| 95% one-sided upper bound (minutes) | (-∞, -0.0190] |
| One-sided p-value | 0.000724573 |
| Cells using pooled variance fallback | 2 |

At the 0.05 level, we **reject** the null hypothesis for Cohort 4.


## Interpretation and limitations

The REML weighted difference estimates the average difference for the paired-user
population under precision weighting. It is not identical to the unweighted
average difference from the paired t-test, which targets the typical user more
directly. The two estimates are shown together so that changes in estimand are
visible.

The source query limits observations to DUR tasks with final status `CLOSED`,
known cohorts, transitions on or after 2026-08-01, and work time between 0.01
and 5 minutes. The analysis is observational. Task durations within a user may
also be correlated beyond the variance formula above; a task-level mixed model
or cluster bootstrap would be a useful sensitivity analysis.

## Query used

```sql
WITH ordered AS (
  SELECT
    TASK_ID,
    USER_ID,
    ITEM_COHORT,
    STARTED_AT,
    TRANSITION_STARTED_AT::DATE AS dt,
    LAG(ITEM_COHORT) OVER (
      PARTITION BY USER_ID, TRANSITION_STARTED_AT::DATE
      ORDER BY STARTED_AT
    ) AS prev_cohort,
    DWELL_IN_PROGRESS_TO_CLOSED_MINUTES AS work_min
  FROM EDLDB.PET_HEALTH_ANALYTICS_SANDBOX.FCT__TASKS_LIFECYCLE
  WHERE TRANSITION_STARTED_AT >= '2026-08-01'
    AND TASK_TYPE = 'DUR'
    AND FINAL_STATUS = 'CLOSED'
    AND USER_ID IS NOT NULL
    AND STARTED_AT IS NOT NULL
    AND DWELL_IN_PROGRESS_TO_CLOSED_MINUTES BETWEEN 0.01 AND 5
    AND ITEM_COHORT != 'Unknown'
)
SELECT
  TASK_ID AS task_id,
  USER_ID AS user_id,
  dt,
  CASE
    WHEN ITEM_COHORT = prev_cohort THEN 'Same Cohort'
    ELSE 'Different Cohort'
  END AS allocation_pattern,
  ITEM_COHORT AS cohort,
  work_min
FROM ordered
WHERE prev_cohort IS NOT NULL
ORDER BY allocation_pattern, work_min
```
