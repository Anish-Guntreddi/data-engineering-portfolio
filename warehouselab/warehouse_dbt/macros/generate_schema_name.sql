{# Use the custom +schema name verbatim (e.g. "staging", "marts") instead of the
   dbt default of prefixing it with the target schema. This gives stable, simple
   schema names that the README and tests can reference directly. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema | trim }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
