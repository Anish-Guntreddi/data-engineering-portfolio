-- User dimension enriched with lifetime activity & revenue rollups.
with users as (
    select * from {{ ref('stg_users') }}
),

event_rollup as (
    select
        user_id,
        count(*)                    as n_events,
        min(event_ts)               as first_event_ts,
        max(event_ts)               as last_event_ts
    from {{ ref('stg_events') }}
    group by 1
),

order_rollup as (
    select
        user_id,
        count(*) filter (where status = 'completed')                 as n_completed_orders,
        coalesce(sum(amount) filter (where status = 'completed'), 0)  as lifetime_revenue
    from {{ ref('stg_orders') }}
    group by 1
)

select
    u.user_id,
    u.signup_date,
    u.country,
    u.plan,
    coalesce(e.n_events, 0)                              as n_events,
    e.first_event_ts,
    e.last_event_ts,
    coalesce(o.n_completed_orders, 0)                    as n_completed_orders,
    cast(coalesce(o.lifetime_revenue, 0) as numeric(14, 2)) as lifetime_revenue
from users u
left join event_rollup e on u.user_id = e.user_id
left join order_rollup o on u.user_id = o.user_id
