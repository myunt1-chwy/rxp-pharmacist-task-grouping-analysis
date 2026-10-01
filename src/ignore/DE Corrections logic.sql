
with task_base as(
select
        t.USER_ID,
        t.USER_NAME,
        t.EMPLOYEE_MANAGER_NAME,
        t.TASK_CREATED_AT,
        t.CLOSED_AT,
        t.task_type,
        coalesce(i.rx_id,t.ASSOCIATED_ENTITY_ID) as rx_id,
        coalesce(t.PRESCRIPTION_ID, i.rx_id) as PRESCRIPTION_ID,
        t.task_id
from PET_HEALTH_ANALYTICS_SANDBOX.FCT__TASKS_LIFECYCLE t
left join PET_HEALTH_ANALYTICS_SANDBOX.int__de_rx_connect i using (task_id)
where CLOSED_AT::date >= current_date - 90
and task_type like 'DE_%'
)

select
        t.USER_ID,
        t.USER_NAME,
        t.EMPLOYEE_MANAGER_NAME,
        NEW_LEAD,
        AREA_MANAGER,
        OPS_MANAGER,
        e.WH_ID as WH_ID,
        t.TASK_CREATED_AT,
        t.CLOSED_AT,
        t.task_type,
        t.rx_id,
        t.PRESCRIPTION_ID,
        t.task_id,
        c.field_name,
        c.LAST_PREV_VALUE,
        c.CURRENT_VALUE,
        c.LAST_CHANGED_DTTM,
        case when FIELD_NAME in ('directions','remainingAmount','refillAmount','expirationDateTime','prescribedAmount','prescribedDateTime') then 'Yellow'
        when field_name is null then 'Green'
        else 'Red' end as correction_flag
from task_base t
left join PET_HEALTH_ANALYTICS_SANDBOX.fct__rx_result_field_change_summary c on c.rx_id = t.rx_id and LAST_CHANGED_BY_ROLE <> 'SYSTEM'
left join bt_pet_health_rx_operations.rx_dim_employees e on e.EMPLOYEE_KYRIOS_ID::varchar = user_id
left join PET_HEALTH_ANALYTICS_SANDBOX.DE_TEAM_LEAD l on l.USERNAME = e.EMPLOYEE_USER_NAME
where 1=1
and (LAST_CHANGED_BY_ROLE <> 'SYSTEM' or LAST_CHANGED_BY_ROLE is null)
and t.task_id is not null
and  (FIELD_NAME in ('clinicId','directions','expirationDateTime','petId','prescribedAmount','prescribedDateTime','refillAmount','remainingAmount','vetId') or field_name is null)
and (LAST_CHANGED_DTTM > t.CLOSED_AT or LAST_CHANGED_DTTM is null)
and t.closed_at >= current_date - 90
and task_type like 'DE_%'
and task_type <> 'DE_OCR_SUCCESS'
--and field_name is not null


select
*
--from bt_pet_health_rx_operations.rx_dim_employees limit 100
from PET_HEALTH_ANALYTICS_SANDBOX.DE_TEAM_LEAD limit 100

select distinct field_name from PET_HEALTH_ANALYTICS_SANDBOX.fct__rx_result_field_change_summary
