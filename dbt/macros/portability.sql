{#
  Portability macros (adapter.dispatch): the same model compiles for DuckDB (this project) and for ClickHouse
  (the production warehouse of the team). dbt picks <adapter>__<macro> when it exists, else default__<macro>.
#}

{# Approximate distinct count: HyperLogLog-style, cheap on billions of rows #}
{% macro approx_distinct(expr) %}{{ return(adapter.dispatch('approx_distinct', 'fingerprint_accuracy')(expr)) }}{% endmacro %}
{% macro default__approx_distinct(expr) %}approx_count_distinct({{ expr }}){% endmacro %}
{% macro clickhouse__approx_distinct(expr) %}uniq({{ expr }}){% endmacro %}

{# Exact distinct count #}
{% macro exact_distinct(expr) %}{{ return(adapter.dispatch('exact_distinct', 'fingerprint_accuracy')(expr)) }}{% endmacro %}
{% macro default__exact_distinct(expr) %}count(distinct {{ expr }}){% endmacro %}
{% macro clickhouse__exact_distinct(expr) %}uniqExact({{ expr }}){% endmacro %}

{# Week start (Monday) of a date #}
{% macro week_start(expr) %}{{ return(adapter.dispatch('week_start', 'fingerprint_accuracy')(expr)) }}{% endmacro %}
{% macro default__week_start(expr) %}cast(date_trunc('week', {{ expr }}) as date){% endmacro %}
{% macro clickhouse__week_start(expr) %}toMonday({{ expr }}){% endmacro %}

{# Day of a timestamp #}
{% macro to_day(expr) %}{{ return(adapter.dispatch('to_day', 'fingerprint_accuracy')(expr)) }}{% endmacro %}
{% macro default__to_day(expr) %}cast({{ expr }} as date){% endmacro %}
{% macro clickhouse__to_day(expr) %}toDate({{ expr }}){% endmacro %}

{# Conditional count #}
{% macro count_if(cond) %}{{ return(adapter.dispatch('count_if', 'fingerprint_accuracy')(cond)) }}{% endmacro %}
{% macro default__count_if(cond) %}count(*) filter (where {{ cond }}){% endmacro %}
{% macro clickhouse__count_if(cond) %}countIf({{ cond }}){% endmacro %}
