# Santhosh Query Analysis

## Purpose

This analysis compares task work time for consecutive DUR tasks allocated to the
same cohort versus a different cohort, separately for Cohorts 1–4. Work time is
`DWELL_IN_PROGRESS_TO_CLOSED_MINUTES`, measured in minutes.

The source query keeps the original filters: transitions on or after
2026-08-01, DUR tasks with final status `CLOSED`, non-null user and start time,
work time between 0.01 and 5 minutes, and known item cohorts. The previous
cohort is calculated within user and transition date, ordered by `STARTED_AT`.
Rows without a previous cohort are excluded. Distribution charts show separate
kernel-density lines for the two allocation patterns after converting work time
from minutes to seconds, with a base-10 logarithmic x-axis.

## Hypothesis test

The primary test is a one-sided Welch two-sample t-test. The null hypothesis is that Same Cohort is not faster than Different Cohort (Same Cohort − Different Cohort ≥ 0); the alternative is that the contrast is less than zero, with alpha = 0.05.

## Cohort 1

![Work-time distribution — Cohort 1](../../charts/santhosh-analysis/santosh-analysis-cohort-1.png)

| Allocation pattern | Tasks | Mean (min) | SD (min) | Median (min) | P25 (min) | P75 (min) |
|---|---:|---:|---:|---:|---:|---:|
| Same Cohort | 455,487 | 0.4884 | 0.6661 | 0.2500 | 0.1333 | 0.5167 |
| Different Cohort | 373,088 | 0.5187 | 0.6881 | 0.2667 | 0.1500 | 0.5667 |

| Quantity | Result |
|---|---:|
| Same Cohort mean (minutes) | 0.4884 |
| Different Cohort mean (minutes) | 0.5187 |
| Mean difference (minutes) | -0.0303 |
| 95% one-sided upper bound | (-∞, -0.0278] |
| Welch t-statistic | -20.2019 |
| Welch degrees of freedom | 786244.1846 |
| One-sided p-value | 4.9709e-91 |

At the 0.05 level, we **reject** the null hypothesis for Cohort 1.

## Cohort 2

![Work-time distribution — Cohort 2](../../charts/santhosh-analysis/santosh-analysis-cohort-2.png)

| Allocation pattern | Tasks | Mean (min) | SD (min) | Median (min) | P25 (min) | P75 (min) |
|---|---:|---:|---:|---:|---:|---:|
| Same Cohort | 307,488 | 0.6254 | 0.7526 | 0.3500 | 0.1833 | 0.7333 |
| Different Cohort | 373,742 | 0.6323 | 0.7605 | 0.3500 | 0.1833 | 0.7333 |

| Quantity | Result |
|---|---:|
| Same Cohort mean (minutes) | 0.6254 |
| Different Cohort mean (minutes) | 0.6323 |
| Mean difference (minutes) | -0.0069 |
| 95% one-sided upper bound | (-∞, -0.0039] |
| Welch t-statistic | -3.7486 |
| Welch degrees of freedom | 658683.7410 |
| One-sided p-value | 8.89116e-05 |

At the 0.05 level, we **reject** the null hypothesis for Cohort 2.

## Cohort 3

![Work-time distribution — Cohort 3](../../charts/santhosh-analysis/santosh-analysis-cohort-3.png)

| Allocation pattern | Tasks | Mean (min) | SD (min) | Median (min) | P25 (min) | P75 (min) |
|---|---:|---:|---:|---:|---:|---:|
| Same Cohort | 9,472 | 0.8202 | 0.8535 | 0.5167 | 0.2667 | 1.0167 |
| Different Cohort | 93,352 | 0.8692 | 0.8818 | 0.5500 | 0.2833 | 1.1000 |

| Quantity | Result |
|---|---:|
| Same Cohort mean (minutes) | 0.8202 |
| Different Cohort mean (minutes) | 0.8692 |
| Mean difference (minutes) | -0.0490 |
| 95% one-sided upper bound | (-∞, -0.0338] |
| Welch t-statistic | -5.3067 |
| Welch degrees of freedom | 11619.9546 |
| One-sided p-value | 5.68372e-08 |

At the 0.05 level, we **reject** the null hypothesis for Cohort 3.

## Cohort 4

![Work-time distribution — Cohort 4](../../charts/santhosh-analysis/santosh-analysis-cohort-4.png)

| Allocation pattern | Tasks | Mean (min) | SD (min) | Median (min) | P25 (min) | P75 (min) |
|---|---:|---:|---:|---:|---:|---:|
| Same Cohort | 14,073 | 1.0330 | 0.9618 | 0.6833 | 0.3667 | 1.3333 |
| Different Cohort | 54,189 | 1.0496 | 0.9534 | 0.7167 | 0.4000 | 1.3333 |

| Quantity | Result |
|---|---:|
| Same Cohort mean (minutes) | 1.0330 |
| Different Cohort mean (minutes) | 1.0496 |
| Mean difference (minutes) | -0.0166 |
| 95% one-sided upper bound | (-∞, -0.0016] |
| Welch t-statistic | -1.8252 |
| Welch degrees of freedom | 21801.7320 |
| One-sided p-value | 0.0339921 |

At the 0.05 level, we **reject** the null hypothesis for Cohort 4.


Each result is an observational comparison of task means and does not establish
that cohort allocation causes the difference.

## Limitations

Welch's test allows unequal variances but treats task rows as independent.
Users and transition dates can contribute multiple tasks, so the p-value and
confidence interval should be interpreted as the requested row-level analysis,
not as a dependence-adjusted estimate. The cohort comparison also inherits the
source query's ordering and filtering choices.

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
