-- Daily Active Users: distinct users with >= 1 event on a calendar day.
with events as (
    select * from {{ ref('stg_events') }}
)

select
    event_date                          as date,
    count(distinct user_id)             as dau
from events
group by 1
order by 1
