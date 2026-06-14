-- Cleaned/typed event stream staging model.
-- Adds a derived event_date for day-grain aggregation downstream.
with source as (
    select * from {{ source('raw', 'events') }}
)

select
    cast(event_id as bigint)        as event_id,
    cast(user_id as bigint)         as user_id,
    lower(trim(event_type))         as event_type,
    cast(event_ts as timestamp)     as event_ts,
    cast(event_ts as date)          as event_date,
    trim(session_id)                as session_id
from source
