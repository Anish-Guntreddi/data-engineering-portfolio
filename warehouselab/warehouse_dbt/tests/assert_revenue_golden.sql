-- Singular golden test: completed revenue (and order count) for the golden date
-- must equal the baked golden constants. Returns a row only on divergence, so
-- zero rows = PASS. A tiny tolerance guards against float rounding.
select
    date,
    revenue                       as actual_revenue,
    {{ var('golden_revenue') }}   as expected_revenue,
    n_orders                      as actual_n_orders,
    {{ var('golden_n_orders') }}  as expected_n_orders
from {{ ref('fct_revenue_by_day') }}
where date = cast('{{ var("golden_date") }}' as date)
  and (
        abs(revenue - {{ var('golden_revenue') }}) > 0.01
        or n_orders <> {{ var('golden_n_orders') }}
      )
