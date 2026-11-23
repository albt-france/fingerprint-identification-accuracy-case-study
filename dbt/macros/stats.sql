{#
  Wilson score interval for a proportion k / n (95% by default). Better than the normal interval when the rate is
  small (false-positive rates of 0.1%-2%) or n is small. Returns NULL when n = 0.
    centre = (p + z^2 / 2n) / (1 + z^2 / n)
    half   = z * sqrt(p(1-p)/n + z^2 / 4n^2) / (1 + z^2 / n)
#}
{% macro wilson_lower(k, n, z=1.96) %}
case when {{ n }} > 0 then
    (({{ k }}) * 1.0 / ({{ n }}) + {{ z }}*{{ z }} / (2.0 * ({{ n }}))
     - {{ z }} * sqrt((({{ k }}) * 1.0 / ({{ n }})) * (1 - ({{ k }}) * 1.0 / ({{ n }})) / ({{ n }}) + {{ z }}*{{ z }} / (4.0 * ({{ n }}) * ({{ n }}))))
    / (1 + {{ z }}*{{ z }} / ({{ n }}))
end
{% endmacro %}

{% macro wilson_upper(k, n, z=1.96) %}
case when {{ n }} > 0 then
    (({{ k }}) * 1.0 / ({{ n }}) + {{ z }}*{{ z }} / (2.0 * ({{ n }}))
     + {{ z }} * sqrt((({{ k }}) * 1.0 / ({{ n }})) * (1 - ({{ k }}) * 1.0 / ({{ n }})) / ({{ n }}) + {{ z }}*{{ z }} / (4.0 * ({{ n }}) * ({{ n }}))))
    / (1 + {{ z }}*{{ z }} / ({{ n }}))
end
{% endmacro %}

{# Safe ratio #}
{% macro ratio(k, n) %}case when ({{ n }}) > 0 then ({{ k }}) * 1.0 / ({{ n }}) end{% endmacro %}
