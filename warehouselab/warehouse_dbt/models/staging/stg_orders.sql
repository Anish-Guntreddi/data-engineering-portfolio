-- Cleaned/typed orders staging model.
-- Adds a derived order_date for day-grain revenue aggregation downstream.
with source as (
    select * from {{ source('raw', 'orders') }}
)

select
    cast(order_id as bigint)          as order_id,
    cast(user_id as bigint)           as user_id,
    cast(amount as numeric(12, 2))    as amount,
    cast(order_ts as timestamp)       as order_ts,
    cast(order_ts as date)            as order_date,
    lower(trim(status))               as status
from source
