{# SECOM timestamps look like '19/07/2008 11:55:00'. Dialect-specific parsing, one call site. #}
{% macro parse_run_ts(col) -%}
    {{ return(adapter.dispatch('parse_run_ts')(col)) }}
{%- endmacro %}

{% macro default__parse_run_ts(col) -%}
    to_timestamp({{ col }}, 'dd/MM/yyyy HH:mm:ss')
{%- endmacro %}

{% macro duckdb__parse_run_ts(col) -%}
    strptime({{ col }}, '%d/%m/%Y %H:%M:%S')
{%- endmacro %}
