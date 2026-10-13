select
        DATE_TRUNC('HOUR',CONVERT_TIMEZONE('America/New_York', TRANSITION_ENDED_AT)) AS date_hour,
        TASK_TYPE,
        USER_ID,
        USER_NAME,
        count(distinct TASK_ID) as tasks,
        sum(case when DWELL_IN_PROGRESS_TO_CLOSED_MINUTES > 5 and task_type = 'DUR' then 5
                 else NULLIF(DWELL_IN_PROGRESS_TO_CLOSED_MINUTES,0) end)/60 as working_hours,
        count(distinct TASK_ID)/
        (sum(case when DWELL_IN_PROGRESS_TO_CLOSED_MINUTES > 5 and task_type = 'DUR' then 5
                  else NULLIF(DWELL_IN_PROGRESS_TO_CLOSED_MINUTES,0) end)/60) as tph
from PET_HEALTH_ANALYTICS_SANDBOX.fct__tasks_lifecycle
where FINAL_STATUS = 'CLOSED'
and USER_ID is not null
and task_type = 'DUR'
group by all having tph is not null
order by tph desc
limit 10;


with labor_report as
(select
  r.common_date,
  dim.job_role,
  r.employee_id,
  dim.employee_kyrios_id,
  dim.employee_full_name,
  r.metric,
  dim.job_title,
  sum(case when sub = 'TPH' then val else 0 end) as TPH,
  sum(case when sub = 'Transactions' then val else 0 end) as Transactions,
  sum(case when sub = 'Function Hours' then val else 0 end) as function_hours,
from snop_sandbox.rx_performance_data_mart_calc_report r
left join snop_sandbox.rx_dim_employees dim
  on lower(dim.employee_user_name) = lower(r.employee_id)
where common_date >= current_date - 180
    and metric in ('Pharmacist Verification 1', 'PV1/DUR')
    and sub in ('TPH', 'Function Hours', 'Transactions')
    and aggregate_type = 'Daily'
    group by 1,2,3,4,5,6,7),
fact as
(
    select USER_ID as employee_kyrios_id,
    DATE(DATE_TRUNC('DAY',CONVERT_TIMEZONE('America/New_York', TRANSITION_ENDED_AT))) as common_date,
    ITEM_COHORT AS COH,
    count(distinct task_id) as ntask,
    sum(ntask) over (partition by user_id, common_date) as total_ntask,
    sum(DWELL_IN_PROGRESS_TO_CLOSED_SECONDS)  as total_time,
    sum(total_time) over (partition by user_id, common_date)/3600.0 as overall_time
    from PET_HEALTH_ANALYTICS_SANDBOX.fct__tasks_lifecycle
    where TASK_TYPE = 'DUR'
    -- AND DWELL_IN_PROGRESS_TO_CLOSED_SECONDS IS NOT NULL
    -- AND DWELL_IN_PROGRESS_TO_CLOSED_SECONDS > 0
    --and FINAL_STATUS = 'CLOSED'
    and common_date >= current_date - 180
    and user_id <> 'rxp-task-management-service-s2s-client'
    group by  1,2,3 order by 1,2,3
)
select a.*, b.* from labor_report a
    join fact  b on a.employee_kyrios_id = b.employee_kyrios_id
    and a.common_date = b.common_date
    and a.common_date = '2026-10-05'
    and employee_id = 'aloyd2'
    order by a.common_date
    limit 20;



    1WITH u AS (
  SELECT DATE_TRUNC('week', j.FINISHED_RXP)::date wk, j.USAGE_ID, MAX(j.POF_FLAG) pof,
         MAX(IFF(t.ASSOCIATED_ENTITY_ID IS NOT NULL,1,0)) has_task
  FROM EDLDB.PET_HEALTH_ANALYTICS_SANDBOX.FCT__RX_USAGE_JOURNEY j
  LEFT JOIN EDLDB.PET_HEALTH_ANALYTICS_SANDBOX.FCT__TASKS_LIFECYCLE t
         ON t.ASSOCIATED_ENTITY_ID=j.USAGE_ID AND t.TASK_TYPE='DUR'
  WHERE j.DUR_FLAG=1 AND j.FINISHED_RXP>='2026-06-01' AND j.FINISHED_RXP<'2026-09-28' GROUP BY 1,2),
v AS (SELECT wk, COUNT_IF(has_task=0) oracle, COUNT_IF(has_task=0 AND pof=1) oracle_pof, COUNT(*) total FROM u GROUP BY 1),
h AS (SELECT DATE_TRUNC('week',start_time)::date wk,
        SUM(IFF(labor_function='PV1/DUR',seconds,0))/3600 pv1dur_hrs,
        SUM(IFF(labor_function='Pharmacist Verification 1',seconds,0))/3600 pv1_hrs
      FROM chewybi.v_labor_summary_measure
      WHERE labor_function IN ('PV1/DUR','Pharmacist Verification 1') AND COALESCE(on_clock,TRUE)
        AND LOWER(COALESCE(employee_username,''))<>'system'
        AND start_time>='2026-06-01' AND start_time<'2026-09-28' GROUP BY 1)
SELECT v.wk, total, oracle, ROUND(100*oracle/total,1) oracle_pct, oracle_pof,
       ROUND(100*oracle_pof/NULLIF(oracle,0),1) pof_pct_of_oracle,
       ROUND(pv1dur_hrs) pv1dur_hrs, ROUND(pv1_hrs) pv1_hrs
FROM v LEFT JOIN h USING(wk) ORDER BY 1;
