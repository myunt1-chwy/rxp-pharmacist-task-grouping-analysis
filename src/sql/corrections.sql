
with task_base as(
select  t.STARTED_AT,
        t.CLOSED_AT,
        t.task_type,
        coalesce(i.rx_id,t.ASSOCIATED_ENTITY_ID) as rx_id,
        coalesce(t.PRESCRIPTION_ID, i.rx_id) as PRESCRIPTION_ID,
        t.task_id
from PET_HEALTH_ANALYTICS_SANDBOX.FCT__TASKS_LIFECYCLE t
left join PET_HEALTH_ANALYTICS_SANDBOX.int__de_rx_connect i using (task_id)
where CLOSED_AT::date >= current_date - 90
and task_type = 'DUR'
),
corrections as
    (select
        t.STARTED_AT,
        t.CLOSED_AT,
        t.task_type,
        t.rx_id,
        t.PRESCRIPTION_ID,
        t.task_id,
        c.last_action_name,
        c.field_name,
        c.LAST_PREV_VALUE,
        c.CURRENT_VALUE,
        c.LAST_CHANGED_DTTM,
from task_base t
left join PET_HEALTH_ANALYTICS_SANDBOX.fct__rx_result_field_change_summary c on c.rx_id = t.rx_id and LAST_CHANGED_BY_ROLE <> 'SYSTEM'
where 1=1
and t.task_id is not null
and (LAST_CHANGED_DTTM > t.STARTED_AT or LAST_CHANGED_DTTM < t.CLOSED_AT)
and t.closed_at >= current_date - 90
and task_type = 'DUR')
select field_name, count(*) from corrections group by 1 order by 2;



--and field_name is not null


select
*
--from bt_pet_health_rx_operations.rx_dim_employees limit 100
from PET_HEALTH_ANALYTICS_SANDBOX.DE_TEAM_LEAD limit 100

select distinct field_name from PET_HEALTH_ANALYTICS_SANDBOX.fct__rx_result_field_change_summary
