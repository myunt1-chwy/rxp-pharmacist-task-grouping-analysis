CREATE OR REPLACE TRANSIENT TABLE EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_VALID_DUR_TASKS AS
WITH pet_profiles AS (
    SELECT
        PETPROFILE_ID,
        PETPROFILE_PETTYPE_DESCRIPTION,
        PETPROFILE_MED_CONDITION_LIST
    FROM CHEWYBI.CUSTOMER_PETPROFILES
    WHERE PETPROFILE_ID IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY PETPROFILE_ID
        ORDER BY PETPROFILE_UPDATED_DTTM DESC NULLS LAST,
                 PETPROFILE_CREATED_DTTM DESC NULLS LAST,
                 DW_UPDATE_DTTM DESC NULLS LAST,
                 DW_CREATE_DTTM DESC NULLS LAST,
                 PETPROFILE_PETTYPE_DESCRIPTION DESC NULLS LAST,
                 PETPROFILE_MED_CONDITION_LIST DESC NULLS LAST
    ) = 1
), task_rows AS (
    SELECT
        task.USER_ID,
        task.TASK_ID,
        task.PART_NUMBER,
        COALESCE(NULLIF(TRIM(task.COH), ''), '<Missing>') AS COH,
        COALESCE(NULLIF(TRIM(product.MERCH_CLASSIFICATION3), ''), '<Missing>') AS MC3,
        COALESCE(NULLIF(TRIM(product.PURCHASE_BRAND), ''), '<Missing>') AS PURCHASE_BRAND,
        product.PARENT_PART_NUMBER,
        task.ORDER_ID,
        task.PRESCRIPTION_ID,
        prescriptions.PET_ID AS SEQUENCE_PET_ID,
        COALESCE(
            NULLIF(TRIM(pet_profiles.PETPROFILE_PETTYPE_DESCRIPTION), ''),
            '<Missing>'
        ) AS SEQUENCE_PETTYPE,
        task.RX_USAGE_ID,
        task.PROCESS_START_TIME,
        task.CLOSED_AT,
        task.DWELL_IN_PROGRESS_TO_CLOSED_SECONDS,
        task.IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS,
        task.TASK_TYPE,
        task.IS_REFILL,
        task.HANDOFF_TYPE,
        sequence_summary.N_INTERSECTING_TASKS,
        ROW_NUMBER() OVER (
            PARTITION BY task.USER_ID, task.TASK_ID
            ORDER BY task.PROCESS_START_TIME, task.CLOSED_AT
        ) AS TASK_ROW_NUMBER
    FROM EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASKS AS task
    INNER JOIN EDLDB_DEV.PET_HEALTH_ANALYTICS_SANDBOX.MY_RXP_TASKS_WITH_SEQUENCE AS sequence_summary
        ON sequence_summary.USER_ID = task.USER_ID
       AND sequence_summary.TASK_ID = task.TASK_ID
    LEFT JOIN EDLDB.PDM.PRODUCT AS product
        ON product.PART_NUMBER = task.PART_NUMBER
    LEFT JOIN EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS AS prescriptions
        ON prescriptions.RX_ID = task.PRESCRIPTION_ID
    LEFT JOIN pet_profiles
        ON pet_profiles.PETPROFILE_ID = prescriptions.PET_ID
    WHERE task.USER_ID IS NOT NULL
      AND task.TASK_ID IS NOT NULL
      AND task.PROCESS_START_TIME IS NOT NULL
      AND task.CLOSED_AT IS NOT NULL
      AND task.PROCESS_START_TIME <= task.CLOSED_AT
    QUALIFY TASK_ROW_NUMBER = 1
), task_flags AS (
    SELECT
        task_rows.*,
        ROW_NUMBER() OVER (
            PARTITION BY USER_ID
            ORDER BY PROCESS_START_TIME, CLOSED_AT, TASK_ID
        ) AS GLOBAL_TASK_SEQN,
        IFF(
            TASK_TYPE = 'DUR'
            AND DWELL_IN_PROGRESS_TO_CLOSED_SECONDS IS NOT NULL
            AND DWELL_IN_PROGRESS_TO_CLOSED_SECONDS > 0
            AND LOWER(IS_REFILL) = 'false'
            AND HANDOFF_TYPE IS NULL
            AND N_INTERSECTING_TASKS = 0,
            TRUE,
            FALSE
        ) AS IS_VALID_TASK
    FROM task_rows
), with_previous AS (
    SELECT
        task_flags.*,
        LAG(IS_VALID_TASK) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
        ) AS PREVIOUS_IS_VALID,
        LAG(GLOBAL_TASK_SEQN) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
        ) AS PREVIOUS_GLOBAL_TASK_SEQN,
        LAG(CLOSED_AT) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
        ) AS PREVIOUS_CLOSED_AT,
        LAG(COH) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
        ) AS PREVIOUS_COH,
        LAG(SEQUENCE_PET_ID) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
        ) AS PREVIOUS_SEQUENCE_PET_ID,
        LAG(MC3) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
        ) AS PREVIOUS_MC3,
        LAG(SEQUENCE_PETTYPE) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
        ) AS PREVIOUS_SEQUENCE_PETTYPE,
        LAG(PURCHASE_BRAND) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
        ) AS PREVIOUS_PURCHASE_BRAND,
        LAG(PARENT_PART_NUMBER) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
        ) AS PREVIOUS_PARENT_PART_NUMBER
    FROM task_flags
), valid_tasks AS (
    SELECT
        with_previous.*,
        LAG(GLOBAL_TASK_SEQN) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
        ) AS PREVIOUS_VALID_GLOBAL_TASK_SEQN,
        LAG(CLOSED_AT) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
        ) AS PREVIOUS_VALID_CLOSED_AT,
        LAG(COH) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
        ) AS PREVIOUS_VALID_COH,
        LAG(SEQUENCE_PET_ID) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
        ) AS PREVIOUS_VALID_SEQUENCE_PET_ID,
        LAG(MC3) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
        ) AS PREVIOUS_VALID_MC3,
        LAG(SEQUENCE_PETTYPE) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
        ) AS PREVIOUS_VALID_SEQUENCE_PETTYPE,
        LAG(PURCHASE_BRAND) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
        ) AS PREVIOUS_VALID_PURCHASE_BRAND,
        LAG(PARENT_PART_NUMBER) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
        ) AS PREVIOUS_VALID_PARENT_PART_NUMBER,
        ROW_NUMBER() OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
        ) AS VALID_TASK_SEQN
    FROM with_previous
    WHERE IS_VALID_TASK
), sequence_boundaries AS (
    SELECT
        valid_tasks.*,
        IFF(
            PREVIOUS_VALID_GLOBAL_TASK_SEQN IS NULL
            OR GLOBAL_TASK_SEQN <> PREVIOUS_VALID_GLOBAL_TASK_SEQN + 1
            OR DATEDIFF('second', PREVIOUS_VALID_CLOSED_AT, PROCESS_START_TIME) >= 3600
            OR COH <> PREVIOUS_VALID_COH,
            1,
            0
        ) AS COHORT_SEQUENCE_START,
        IFF(
            PREVIOUS_VALID_GLOBAL_TASK_SEQN IS NULL
            OR GLOBAL_TASK_SEQN <> PREVIOUS_VALID_GLOBAL_TASK_SEQN + 1
            OR DATEDIFF('second', PREVIOUS_VALID_CLOSED_AT, PROCESS_START_TIME) >= 3600
            OR COH <> PREVIOUS_VALID_COH
            OR SEQUENCE_PET_ID IS NULL
            OR PREVIOUS_VALID_SEQUENCE_PET_ID IS NULL
            OR SEQUENCE_PET_ID <> PREVIOUS_VALID_SEQUENCE_PET_ID,
            1,
            0
        ) AS COHORT_PET_SEQUENCE_START,
        IFF(
            PREVIOUS_VALID_GLOBAL_TASK_SEQN IS NULL
            OR GLOBAL_TASK_SEQN <> PREVIOUS_VALID_GLOBAL_TASK_SEQN + 1
            OR DATEDIFF('second', PREVIOUS_VALID_CLOSED_AT, PROCESS_START_TIME) >= 3600
            OR MC3 <> PREVIOUS_VALID_MC3,
            1,
            0
        ) AS MC3_SEQUENCE_START,
        IFF(
            PREVIOUS_VALID_GLOBAL_TASK_SEQN IS NULL
            OR GLOBAL_TASK_SEQN <> PREVIOUS_VALID_GLOBAL_TASK_SEQN + 1
            OR DATEDIFF('second', PREVIOUS_VALID_CLOSED_AT, PROCESS_START_TIME) >= 3600
            OR MC3 <> PREVIOUS_VALID_MC3
            OR SEQUENCE_PETTYPE <> PREVIOUS_VALID_SEQUENCE_PETTYPE,
            1,
            0
        ) AS MC3_PET_SEQUENCE_START,
        IFF(
            PREVIOUS_VALID_GLOBAL_TASK_SEQN IS NULL
            OR GLOBAL_TASK_SEQN <> PREVIOUS_VALID_GLOBAL_TASK_SEQN + 1
            OR DATEDIFF('second', PREVIOUS_VALID_CLOSED_AT, PROCESS_START_TIME) >= 3600
            OR MC3 <> PREVIOUS_VALID_MC3
            OR COH <> PREVIOUS_VALID_COH
            OR SEQUENCE_PETTYPE <> PREVIOUS_VALID_SEQUENCE_PETTYPE,
            1,
            0
        ) AS MC3_COH_PETTYPE_SEQUENCE_START,
        IFF(
            PREVIOUS_VALID_GLOBAL_TASK_SEQN IS NULL
            OR GLOBAL_TASK_SEQN <> PREVIOUS_VALID_GLOBAL_TASK_SEQN + 1
            OR DATEDIFF('second', PREVIOUS_VALID_CLOSED_AT, PROCESS_START_TIME) >= 3600
            OR PURCHASE_BRAND <> PREVIOUS_VALID_PURCHASE_BRAND,
            1,
            0
        ) AS BRAND_SEQUENCE_START,
        IFF(
            PREVIOUS_VALID_GLOBAL_TASK_SEQN IS NULL
            OR GLOBAL_TASK_SEQN <> PREVIOUS_VALID_GLOBAL_TASK_SEQN + 1
            OR DATEDIFF('second', PREVIOUS_VALID_CLOSED_AT, PROCESS_START_TIME) >= 3600
            OR PARENT_PART_NUMBER IS NULL
            OR PREVIOUS_VALID_PARENT_PART_NUMBER IS NULL
            OR PARENT_PART_NUMBER <> PREVIOUS_VALID_PARENT_PART_NUMBER,
            1,
            0
        ) AS PP_SEQUENCE_START
    FROM valid_tasks
), numbered_sequences AS (
    SELECT
        sequence_boundaries.*,
        SUM(COHORT_SEQUENCE_START) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS COHORT_BATCH_SEQN,
        SUM(COHORT_PET_SEQUENCE_START) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS COHORT_PET_BATCH_SEQN,
        SUM(MC3_SEQUENCE_START) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS MC3_SEQN,
        SUM(MC3_PET_SEQUENCE_START) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS MC3_PET_BATCH_SEQN,
        SUM(MC3_COH_PETTYPE_SEQUENCE_START) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS MC3_COH_PETTYPE_BATCH_SEQN,
        SUM(BRAND_SEQUENCE_START) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS BRAND_SEQN,
        SUM(PP_SEQUENCE_START) OVER (
            PARTITION BY USER_ID
            ORDER BY GLOBAL_TASK_SEQN
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS PP_SEQN
    FROM sequence_boundaries
), sequenced_rows AS (
    SELECT
        numbered_sequences.*,
        ROW_NUMBER() OVER (
            PARTITION BY USER_ID, COHORT_BATCH_SEQN
            ORDER BY GLOBAL_TASK_SEQN
        ) AS COHORT_SEQN,
        ROW_NUMBER() OVER (
            PARTITION BY USER_ID, COHORT_PET_BATCH_SEQN
            ORDER BY GLOBAL_TASK_SEQN
        ) AS COHORT_PET_SEQN,
        ROW_NUMBER() OVER (
            PARTITION BY USER_ID, MC3_PET_BATCH_SEQN
            ORDER BY GLOBAL_TASK_SEQN
        ) AS MC3_PET_SEQN,
        ROW_NUMBER() OVER (
            PARTITION BY USER_ID, MC3_COH_PETTYPE_BATCH_SEQN
            ORDER BY GLOBAL_TASK_SEQN
        ) AS MC3_COH_PETTYPE_SEQN,
        COUNT(*) OVER (
            PARTITION BY USER_ID, COHORT_BATCH_SEQN
        ) AS COHORT_BATCH_LEN,
        COUNT(*) OVER (
            PARTITION BY USER_ID, COHORT_PET_BATCH_SEQN
        ) AS COHORT_PET_BATCH_LEN,
        COUNT(*) OVER (
            PARTITION BY USER_ID, MC3_SEQN
        ) AS MC3_BATCH_LEN,
        COUNT(*) OVER (
            PARTITION BY USER_ID, MC3_PET_BATCH_SEQN
        ) AS MC3_PET_BATCH_LEN,
        COUNT(*) OVER (
            PARTITION BY USER_ID, MC3_COH_PETTYPE_BATCH_SEQN
        ) AS MC3_COH_PETTYPE_BATCH_LEN,
        COUNT(*) OVER (
            PARTITION BY USER_ID, BRAND_SEQN
        ) AS BRAND_BATCH_LEN,
        COUNT(*) OVER (
            PARTITION BY USER_ID, PP_SEQN
        ) AS PP_BATCH_LEN
    FROM numbered_sequences
), valid_task_usage_ids AS (
    SELECT DISTINCT
        RX_USAGE_ID
    FROM sequenced_rows
    WHERE RX_USAGE_ID IS NOT NULL
), usage_to_rx AS (
    SELECT
        actions.RX_USAGE_ID,
        MIN(actions.RX_ID) AS RX_ID
    FROM EDLDB.BT_HCA_HCDM.RXP_RX_USAGE_ACTIONS AS actions
    INNER JOIN valid_task_usage_ids
        ON valid_task_usage_ids.RX_USAGE_ID = actions.RX_USAGE_ID
    GROUP BY actions.RX_USAGE_ID
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
), current_task_rx_ids AS (
    SELECT
        sequenced_rows.USER_ID,
        sequenced_rows.TASK_ID,
        sequenced_rows.PROCESS_START_TIME,
        usage_to_rx.RX_ID AS CURRENT_RX_ID,
        prescriptions.PET_ID
    FROM sequenced_rows
    LEFT JOIN usage_to_rx
        ON usage_to_rx.RX_USAGE_ID = sequenced_rows.RX_USAGE_ID
    LEFT JOIN EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS AS prescriptions
        ON prescriptions.RX_ID = usage_to_rx.RX_ID
), prior_approved_rx_counts_by_task AS (
    SELECT
        current_task.USER_ID,
        current_task.TASK_ID,
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
    GROUP BY current_task.USER_ID, current_task.TASK_ID
), corrections AS (
    SELECT
        rx_id,
        order_id,
        order_item_id,
        part_number,
        last_changed_by_user_id AS user_id,
        last_action_name AS action_name,
        last_action_id,
        last_changed_dttm,
        field_name
    FROM EDLDB.PET_HEALTH_ANALYTICS_SANDBOX.FCT__RX_RESULT_FIELD_CHANGE_SUMMARY
    WHERE LOWER(field_name) IN (
        'directions',
        'remainingamount',
        'refillamount',
        'expirationdatetime',
        'prescribedamount',
        'prescribeddatetime',
        'verbaldetail',
        'notes',
        'daysofsupply'
    )
      AND last_changed_by_user_id IS NOT NULL
      AND last_changed_by_role <> 'SYSTEM'
      AND rx_id IS NOT NULL
      AND last_changed_dttm >= '2026-02-01'
      AND last_changed_dttm < '2026-08-01'
), correction_usage_ids AS (
    SELECT
        actions.RX_ID,
        actions.RX_USAGE_ID,
        actions.USER_ID,
        actions.ORDER_ID,
        corrections.LAST_CHANGED_DTTM,
        corrections.PART_NUMBER,
        corrections.FIELD_NAME,
        corrections.ACTION_NAME,
        corrections.LAST_ACTION_ID AS ACTION_ID
    FROM EDLDB.BT_HCA_HCDM.RXP_RX_USAGE_ACTIONS AS actions
    INNER JOIN corrections
        ON corrections.ORDER_ID = actions.ORDER_ID
       AND corrections.ORDER_ITEM_ID = actions.ORDER_ITEM_ID
       AND corrections.RX_ID = actions.RX_ID
    INNER JOIN valid_task_usage_ids
        ON valid_task_usage_ids.RX_USAGE_ID = actions.RX_USAGE_ID
    WHERE actions.USER_ID IS NOT NULL
      AND actions.RX_USAGE_ID IS NOT NULL
      AND actions.RX_ID IS NOT NULL
), correction_fields_by_task AS (
    SELECT
        lifecycle.USER_ID,
        lifecycle.TASK_ID,
        ARRAY_AGG(DISTINCT correction.FIELD_NAME)
            WITHIN GROUP (ORDER BY correction.FIELD_NAME) AS CORRECTION_FIELD_NAMES,
        COUNT(DISTINCT correction.FIELD_NAME) AS NCORRECTION_FIELDS,
        ARRAY_AGG(DISTINCT correction.ACTION_NAME)
            WITHIN GROUP (ORDER BY correction.ACTION_NAME) AS CORRECTION_ACTION_NAMES,
        ARRAY_AGG(DISTINCT correction.ACTION_ID)
            WITHIN GROUP (ORDER BY correction.ACTION_ID) AS CORRECTION_ACTION_IDS
    FROM EDLDB.PET_HEALTH_ANALYTICS_SANDBOX.FCT__TASKS_LIFECYCLE AS lifecycle
    INNER JOIN correction_usage_ids AS correction
        ON correction.ORDER_ID = lifecycle.ORDER_ID
       AND correction.PART_NUMBER = lifecycle.PART_NUMBER
       AND correction.LAST_CHANGED_DTTM BETWEEN lifecycle.STARTED_AT AND lifecycle.TRANSITION_ENDED_AT
       AND (
            (
                LOWER(lifecycle.ASSOCIATED_ENTITY_TYPE) = 'prescription_usage'
                AND lifecycle.ASSOCIATED_ENTITY_ID = correction.RX_USAGE_ID
            )
            OR (
                LOWER(lifecycle.ASSOCIATED_ENTITY_TYPE) = 'prescription'
                AND lifecycle.ASSOCIATED_ENTITY_ID = correction.RX_ID
            )
       )
    WHERE LOWER(lifecycle.TASK_TYPE) = 'dur'
      AND lifecycle.HANDOFF_TYPE IS NULL
      AND lifecycle.TASK_CREATED_AT >= '2026-02-01'
      AND lifecycle.TASK_CREATED_AT < '2026-08-01'
    GROUP BY lifecycle.USER_ID, lifecycle.TASK_ID
), enriched_rows AS (
    SELECT
        sequenced_rows.*,
        prescriptions.ORIGINATION,
        prescriptions.INITIATION_CHANNEL,
        prescriptions.INITIATION_REASON,
        prescriptions.PRESCRIPTION_SOURCE,
        prescriptions.APPROVAL_CHANNEL,
        prescriptions.PET_ID,
        COALESCE(
            prior_approved_rx_counts_by_task.N_PRIOR_APPROVED_RX_IDS,
            0
        ) AS N_PRIOR_APPROVED_RX_IDS,
        COALESCE(
            prior_approved_rx_counts_by_task.N_PRIOR_APPROVED_VET_DIET_RX_IDS,
            0
        ) AS N_PRIOR_APPROVED_VET_DIET_RX_IDS,
        COALESCE(
            prior_approved_rx_counts_by_task.N_PRIOR_APPROVED_NON_VET_DIET_RX_IDS,
            0
        ) AS N_PRIOR_APPROVED_NON_VET_DIET_RX_IDS,
        pet_profiles.PETPROFILE_PETTYPE_DESCRIPTION AS PETTYPE,
        CASE
            WHEN pet_profiles.PETPROFILE_MED_CONDITION_LIST IS NULL
              OR NULLIF(TRIM(pet_profiles.PETPROFILE_MED_CONDITION_LIST), '') IS NULL
              OR LOWER(TRIM(pet_profiles.PETPROFILE_MED_CONDITION_LIST)) = 'none'
            THEN 0
            ELSE ARRAY_SIZE(SPLIT(TRIM(pet_profiles.PETPROFILE_MED_CONDITION_LIST), ','))
        END AS NPET_CONDITIONS,
        COALESCE(
            correction_fields_by_task.CORRECTION_FIELD_NAMES,
            ARRAY_CONSTRUCT()
        ) AS CORRECTION_FIELD_NAMES,
        COALESCE(correction_fields_by_task.NCORRECTION_FIELDS, 0) AS NCORRECTION_FIELDS,
        COALESCE(
            correction_fields_by_task.CORRECTION_ACTION_NAMES,
            ARRAY_CONSTRUCT()
        ) AS CORRECTION_ACTION_NAMES,
        COALESCE(
            correction_fields_by_task.CORRECTION_ACTION_IDS,
            ARRAY_CONSTRUCT()
        ) AS CORRECTION_ACTION_IDS
    FROM sequenced_rows
    LEFT JOIN usage_to_rx
        ON usage_to_rx.RX_USAGE_ID = sequenced_rows.RX_USAGE_ID
    LEFT JOIN EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS AS prescriptions
        ON prescriptions.RX_ID = usage_to_rx.RX_ID
    LEFT JOIN prior_approved_rx_counts_by_task
        ON prior_approved_rx_counts_by_task.USER_ID = sequenced_rows.USER_ID
       AND prior_approved_rx_counts_by_task.TASK_ID = sequenced_rows.TASK_ID
    LEFT JOIN pet_profiles
        ON pet_profiles.PETPROFILE_ID = prescriptions.PET_ID
    LEFT JOIN correction_fields_by_task
        ON correction_fields_by_task.USER_ID = sequenced_rows.USER_ID
       AND correction_fields_by_task.TASK_ID = sequenced_rows.TASK_ID
)
SELECT
    USER_ID,
    TASK_ID,
    COH,
    PART_NUMBER,
    PARENT_PART_NUMBER,
    MC3,
    PURCHASE_BRAND,
    ORDER_ID,
    PRESCRIPTION_ID,
    RX_USAGE_ID,
    ORIGINATION,
    INITIATION_CHANNEL,
    INITIATION_REASON,
    PRESCRIPTION_SOURCE,
    APPROVAL_CHANNEL,
    PET_ID,
    N_PRIOR_APPROVED_RX_IDS,
    N_PRIOR_APPROVED_VET_DIET_RX_IDS,
    N_PRIOR_APPROVED_NON_VET_DIET_RX_IDS,
    PETTYPE,
    NPET_CONDITIONS,
    CORRECTION_FIELD_NAMES,
    NCORRECTION_FIELDS,
    CORRECTION_ACTION_NAMES,
    CORRECTION_ACTION_IDS,
    PROCESS_START_TIME,
    CLOSED_AT,
    IMPUTED_DWELL_IN_PROGRESS_TO_CLOSED_SECONDS,
    GLOBAL_TASK_SEQN,
    VALID_TASK_SEQN,
    COALESCE(NOT PREVIOUS_IS_VALID, FALSE) AS PREVIOUS_TASK_INVALID,
    COHORT_SEQN,
    TO_VARCHAR(USER_ID) || ':' || TO_VARCHAR(COHORT_BATCH_SEQN) AS COHORT_BATCH_ID,
    COHORT_BATCH_LEN,
    COHORT_PET_SEQN,
    TO_VARCHAR(USER_ID) || ':' || TO_VARCHAR(COHORT_PET_BATCH_SEQN) AS COHORT_PET_BATCH_ID,
    COHORT_PET_BATCH_LEN,
    MC3_SEQN,
    TO_VARCHAR(USER_ID) || ':' || TO_VARCHAR(MC3_SEQN) AS MC3_BATCH_ID,
    MC3_BATCH_LEN,
    MC3_PET_SEQN,
    TO_VARCHAR(USER_ID) || ':' || TO_VARCHAR(MC3_PET_BATCH_SEQN) AS MC3_PET_BATCH_ID,
    MC3_PET_BATCH_LEN,
    MC3_COH_PETTYPE_SEQN,
    TO_VARCHAR(USER_ID) || ':' || TO_VARCHAR(MC3_COH_PETTYPE_BATCH_SEQN) AS MC3_COH_PETTYPE_BATCH_ID,
    MC3_COH_PETTYPE_BATCH_LEN,
    BRAND_SEQN,
    TO_VARCHAR(USER_ID) || ':' || TO_VARCHAR(BRAND_SEQN) AS BRAND_BATCH_ID,
    BRAND_BATCH_LEN,
    PP_SEQN,
    TO_VARCHAR(USER_ID) || ':' || TO_VARCHAR(PP_SEQN) AS PP_BATCH_ID,
    PP_BATCH_LEN
FROM enriched_rows
ORDER BY USER_ID, GLOBAL_TASK_SEQN;
