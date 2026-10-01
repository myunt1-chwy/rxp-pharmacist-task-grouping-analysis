-- Count distinct prescriptions approved before each valid DUR task.
-- Approval time uses STATE_CHANGED_DATETIME, falling back to
-- ACTION_CREATION_DATETIME when the state-change timestamp is unavailable.
WITH valid_tasks AS (
    SELECT
        TASK_ID,
        PET_ID,
        RX_USAGE_ID,
        PROCESS_START_TIME
    FROM EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_VALID_DUR_TASKS
), current_task_rx_ids AS (
    SELECT
        valid_tasks.TASK_ID,
        valid_tasks.PET_ID,
        valid_tasks.PROCESS_START_TIME,
        MIN(actions.RX_ID) AS CURRENT_RX_ID
    FROM valid_tasks
    LEFT JOIN EDLDB.BT_HCA_HCDM.RXP_RX_USAGE_ACTIONS AS actions
        ON actions.RX_USAGE_ID = valid_tasks.RX_USAGE_ID
    GROUP BY
        valid_tasks.TASK_ID,
        valid_tasks.PET_ID,
        valid_tasks.PROCESS_START_TIME
), approved_rx_by_pet AS (
    SELECT
        PET_ID,
        RX_ID,
        MIN(
            COALESCE(STATE_CHANGED_DATETIME, ACTION_CREATION_DATETIME)
        ) AS APPROVED_AT,
        MAX(IFF(COALESCE(IS_VET_DIET_FLAG, FALSE), 1, 0)) AS IS_VET_DIET_RX
    FROM EDLDB.BT_HCA_HCDM.RXP_RX_USAGE_ACTIONS
    WHERE PET_ID IS NOT NULL
      AND RX_ID IS NOT NULL
      AND UPPER(TO_STATE) = 'APPROVED'
      AND COALESCE(STATE_CHANGED_DATETIME, ACTION_CREATION_DATETIME) IS NOT NULL
    GROUP BY PET_ID, RX_ID
)
SELECT
    current_task.TASK_ID,
    current_task.PET_ID,
    current_task.PROCESS_START_TIME,
    COUNT(DISTINCT approved_rx.RX_ID) AS N_PRIOR_APPROVED_RX_IDS,
    COUNT(
        DISTINCT IFF(
            approved_rx.IS_VET_DIET_RX = 1,
            approved_rx.RX_ID,
            NULL
        )
    ) AS N_PRIOR_APPROVED_VET_DIET_RX_IDS,
    COUNT(
        DISTINCT IFF(
            approved_rx.IS_VET_DIET_RX = 0,
            approved_rx.RX_ID,
            NULL
        )
    ) AS N_PRIOR_APPROVED_NON_VET_DIET_RX_IDS
FROM current_task_rx_ids AS current_task
LEFT JOIN approved_rx_by_pet AS approved_rx
    ON approved_rx.PET_ID = TO_VARCHAR(current_task.PET_ID)
   AND approved_rx.APPROVED_AT < current_task.PROCESS_START_TIME
   AND (
        current_task.CURRENT_RX_ID IS NULL
        OR approved_rx.RX_ID <> current_task.CURRENT_RX_ID
   )
GROUP BY
    current_task.TASK_ID,
    current_task.PET_ID,
    current_task.PROCESS_START_TIME
ORDER BY current_task.PROCESS_START_TIME, current_task.TASK_ID;
