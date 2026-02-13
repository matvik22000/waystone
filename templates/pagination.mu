{%- macro to_page(text, target_page) -%}
    {%- set target = target_page -%}
    {%- if target < 0 -%}
        {%- set target = 0 -%}
    {%- endif -%}
    {%- if target > pages_total - 1 -%}
        {%- set target = pages_total - 1 -%}
    {%- endif -%}
    `[{{ text }}`:{{ location }}`{{ location_params | default('') }}page={{ target }}]
{%- endmacro -%}
--
{% if pages_total > 1 %}
    {%- set start_page = page - 2 -%}
    {%- set end_page = page + 2 -%}
    {%- if start_page < 0 -%}
        {%- set start_page = 0 -%}
    {%- endif -%}
    {%- if end_page > pages_total - 1 -%}
        {%- set end_page = pages_total - 1 -%}
    {%- endif -%}
    `c{{ to_page('<<', 0) }} {{ to_page('<', page - 1) }} {% for p in range(start_page, end_page + 1) -%}
    {%- if p == page %}`_{{ p + 1 }}`_ {% else %}{{ to_page(p + 1, p) }} {% endif -%}
    {%- if not loop.last -%}
    {%- endif -%}
{%- endfor -%}
    {%- if end_page < pages_total - 1 %}... {{ to_page(pages_total, pages_total - 1) }}
    {%- endif %} {{ to_page('>', page + 1) }} {{ to_page('>>', pages_total - 1) }}
{%- endif -%}