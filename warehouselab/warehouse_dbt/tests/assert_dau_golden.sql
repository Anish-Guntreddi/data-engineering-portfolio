-- Singular golden test: DAU for the golden date must equal the baked golden int.
-- dbt singular tests PASS when zero rows are returned. This query returns a row
-- only when the materialised DAU diverges from the golden constant (var).
select
    date,
    dau          as actual_dau,
    {{ var('golden_dau') }} as expected_dau
from {{ ref('fct_daily_active_users') }}
where date = cast('{{ var("golden_date") }}' as date)
  and dau <> {{ var('golden_dau') }}
