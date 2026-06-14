-- Revenue by day: sum of completed-order amounts per calendar day.
-- Only 'completed' orders count as recognised revenue.
with orders as (
    select * from {{ ref('stg_orders') }}
    where status = 'completed'
)

select
    order_date                              as date,
    cast(sum(amount) as numeric(14, 2))     as revenue,
    count(*)                                as n_orders
from orders
group by 1
order by 1
