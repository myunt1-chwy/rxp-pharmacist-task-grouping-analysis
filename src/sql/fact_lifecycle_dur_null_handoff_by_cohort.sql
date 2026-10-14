-- Reproduce MY_RXP_TASKS' null-handoff DUR cohort totals directly from the
-- original lifecycle fact and the same latest-employee pharmacist filter.
WITH latest_employees AS (
    SELECT EMPLOYEE_KYRIOS_ID, JOB_TITLE
    FROM EDLDB.BT_PET_HEALTH_RX_OPERATIONS.RX_DIM_EMPLOYEES
    WHERE EMPLOYEE_KYRIOS_ID IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY EMPLOYEE_KYRIOS_ID
        ORDER BY REPORT_DATE DESC NULLS LAST,
                 LAST_UPDATE_TIME DESC NULLS LAST,
                 EMPLOYEE_KEY DESC NULLS LAST
    ) = 1
), fact_durs AS (
    SELECT
        COALESCE(NULLIF(TRIM(l.ITEM_COHORT), ''), '<Missing>') AS COHORT,
        COALESCE(l.DWELL_IN_PROGRESS_TO_CLOSED_SECONDS, 1) AS DURATION_SECONDS
    FROM EDLDB.PET_HEALTH_ANALYTICS_SANDBOX.FCT__TASKS_LIFECYCLE AS l
    JOIN latest_employees AS e
      ON l.USER_ID = CAST(e.EMPLOYEE_KYRIOS_ID AS VARCHAR)
    WHERE e.JOB_TITLE IN (
        'Pharmacist',
        'Area Manager, Pharmacist II',
        'Technical Services Pharmacist',
        'Compounding Pharmacist',
        'Pharmacist Lead',
        'Regional Operations Excellence Rx',
        'Sr Product Manager',
        'Manager, Pharmacy Operations',
        'Director Pharmacy Operations',
        'Chief of Staff Rx Operations',
        'Pharmacist in Charge'
    )
      AND l.TASK_CREATED_AT >= '2026-02-01'
      AND l.TASK_CREATED_AT < '2026-08-01'
      AND l.TASK_TYPE = 'DUR'
      AND l.HANDOFF_TYPE IS NULL
)
SELECT
    IFF(DURATION_SECONDS >= 156.608019,
        'At or above cutoff', 'Below cutoff') AS CUTOFF_GROUP,
    COHORT,
    COUNT(*) AS N_DURS,
    SUM(DURATION_SECONDS) AS TOTAL_SECONDS,
    ROUND(SUM(DURATION_SECONDS) / 3600.0, 2) AS TOTAL_HOURS
FROM fact_durs
GROUP BY CUTOFF_GROUP, COHORT
ORDER BY CUTOFF_GROUP, N_DURS DESC
