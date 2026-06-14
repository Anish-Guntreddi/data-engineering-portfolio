-- Cleaned/typed user dimension staging model.
with source as (
    select * from {{ source('raw', 'users') }}
)

select
    cast(user_id as bigint)      as user_id,
    cast(signup_date as date)    as signup_date,
    lower(trim(country))         as country,
    lower(trim(plan))            as plan
from source
