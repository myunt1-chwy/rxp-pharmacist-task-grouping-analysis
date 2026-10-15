WITH base_tasks AS (
    SELECT
        TASK_ID,
        USER_ID,
        COH,
        SHIFT,
        JOB_TITLE,
        WH_ID,
        CASE DAYOFWEEKISO(PROCESS_START_TIME)
            WHEN 1 THEN 'Monday'
            WHEN 2 THEN 'Tuesday'
            WHEN 3 THEN 'Wednesday'
            WHEN 4 THEN 'Thursday'
            WHEN 5 THEN 'Friday'
            WHEN 6 THEN 'Saturday'
            WHEN 7 THEN 'Sunday'
        END AS DAY_OF_WEEK,
        IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS AS DURATION_SECONDS
    FROM EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASKS
    WHERE TASK_TYPE = 'DUR'
      AND COH <> 'Unknown'
      AND LOWER(IS_REFILL) = 'false'
      AND HANDOFF_TYPE IS NULL
), percentile_bounds AS (
    SELECT APPROX_PERCENTILE(DURATION_SECONDS, 0.95) AS P95_SECONDS
    FROM base_tasks
), filtered_tasks AS (
    SELECT base.*
    FROM base_tasks AS base
    CROSS JOIN percentile_bounds
    WHERE base.DURATION_SECONDS < percentile_bounds.P95_SECONDS
), dimensions AS (
    SELECT 'shift' AS DIMENSION_TYPE,
           COH,
           COALESCE(SHIFT, '<Missing>') AS DIMENSION_VALUE,
           TASK_ID,
           USER_ID,
           DURATION_SECONDS
    FROM filtered_tasks
    UNION ALL
    SELECT 'job_title',
           COH,
           COALESCE(JOB_TITLE, '<Missing>'),
           TASK_ID,
           USER_ID,
           DURATION_SECONDS
    FROM filtered_tasks
    UNION ALL
    SELECT 'wh_id',
           COH,
           COALESCE(WH_ID, '<Missing>'),
           TASK_ID,
           USER_ID,
           DURATION_SECONDS
    FROM filtered_tasks
    UNION ALL
    SELECT 'day_of_week',
           COH,
           COALESCE(DAY_OF_WEEK, '<Missing>'),
           TASK_ID,
           USER_ID,
           DURATION_SECONDS
    FROM filtered_tasks
)
SELECT
    DIMENSION_TYPE,
    COH,
    DIMENSION_VALUE,
    COUNT(DISTINCT TASK_ID) AS UNIQUE_TASK_COUNT,
    COUNT(DISTINCT USER_ID) AS UNIQUE_USER_COUNT,
    AVG(DURATION_SECONDS) AS AVERAGE_DURATION_SECONDS,
    MEDIAN(DURATION_SECONDS) AS MEDIAN_DURATION_SECONDS,
    STDDEV_SAMP(DURATION_SECONDS) AS STDDEV_DURATION_SECONDS
FROM dimensions
GROUP BY DIMENSION_TYPE, COH, DIMENSION_VALUE
ORDER BY DIMENSION_TYPE, DIMENSION_VALUE, COH
