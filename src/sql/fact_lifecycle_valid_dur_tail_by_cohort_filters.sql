-- Recreate the valid above-cutoff population from lifecycle facts and the
-- existing overlap summary, without using MY_RXP_VALID_DUR_TASKS membership.
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
)
SELECT
    COALESCE(NULLIF(TRIM(l.ITEM_COHORT), ''), '<Missing>') AS COHORT,
    COUNT(*) AS N_DURS,
    COUNT(DISTINCT TO_VARCHAR(l.USER_ID) || '|' || TO_VARCHAR(l.TASK_ID)) AS N_TASK_KEYS,
    SUM(l.DWELL_IN_PROGRESS_TO_CLOSED_SECONDS) AS TOTAL_SECONDS,
    ROUND(SUM(l.DWELL_IN_PROGRESS_TO_CLOSED_SECONDS) / 3600.0, 2) AS TOTAL_HOURS
FROM EDLDB.PET_HEALTH_ANALYTICS_SANDBOX.FCT__TASKS_LIFECYCLE AS l
JOIN latest_employees AS e
  ON l.USER_ID = CAST(e.EMPLOYEE_KYRIOS_ID AS VARCHAR)
JOIN EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASKS_WITH_SEQUENCE AS sequence
  ON sequence.USER_ID = l.USER_ID
 AND sequence.TASK_ID = l.TASK_ID
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
  AND LOWER(l.IS_REFILL) = 'false'
  AND l.DWELL_IN_PROGRESS_TO_CLOSED_SECONDS >= 156.608019
  AND sequence.N_INTERSECTING_TASKS = 0
GROUP BY COHORT
ORDER BY N_DURS DESC
