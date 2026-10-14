-- Reproduce the null-handoff DUR duration histogram directly from the
-- lifecycle fact with the pharmacist employee and creation-date filters.
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
), durations AS (
    SELECT COALESCE(l.DWELL_IN_PROGRESS_TO_CLOSED_SECONDS, 1) AS DURATION_SECONDS
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
), bucketed AS (
    SELECT
        DURATION_SECONDS,
        CASE
            WHEN DURATION_SECONDS <= 0 THEN 0
            WHEN DURATION_SECONDS < 30 THEN 1
            WHEN DURATION_SECONDS < 60 THEN 2
            WHEN DURATION_SECONDS < 120 THEN 3
            WHEN DURATION_SECONDS < 156.608019 THEN 4
            WHEN DURATION_SECONDS < 300 THEN 5
            WHEN DURATION_SECONDS < 600 THEN 6
            WHEN DURATION_SECONDS < 1800 THEN 7
            WHEN DURATION_SECONDS < 3600 THEN 8
            WHEN DURATION_SECONDS < 14400 THEN 9
            ELSE 10
        END AS BUCKET_ORDER
    FROM durations
)
SELECT
    BUCKET_ORDER,
    COUNT(*) AS N_DURS,
    SUM(DURATION_SECONDS) AS TOTAL_SECONDS,
    ROUND(SUM(DURATION_SECONDS) / 3600.0, 2) AS TOTAL_HOURS,
    MIN(DURATION_SECONDS) AS MIN_SECONDS,
    MAX(DURATION_SECONDS) AS MAX_SECONDS
FROM bucketed
GROUP BY BUCKET_ORDER
ORDER BY BUCKET_ORDER
