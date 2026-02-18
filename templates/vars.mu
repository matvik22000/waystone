{% set green = '494' %}
{% set gray = '444' %}
{% set lightgray = '777' %}
{% set white = 'AAA' %}
{% set black = '222' %}
{% set blue = '229' %}
{% set red = 'A44' %}

{% macro btn(text, href, bg_color=green) -%}
    {% if bg_color != None %}`B{{ bg_color }}{% endif %}`!`=|`[ {{ text }} `{{ href }}]`=|`!{% if bg_color != None %}`b{% endif %}
{%- endmacro %}

{% macro input(param_name, size=16, placeholder='') -%}
    `B{{ white }}`F{{ black }}`<{{ size }}|{{ param_name }}`{{ placeholder }}>`f`b
{%- endmacro %}

{% macro url(text, href, color=blue) -%}
    `F{{ color }}`_`[{{ text }}`{{ href }}]`_`f
{%- endmacro %}

{% macro status_icon (p_dead_low, p_dead_high) %}
    {%- if p_dead_low >= 0.9 %}🔴{% elif p_dead_high <= 0.15 %}🟢{% else %}🟡{% endif -%}
{% endmacro %}


