{%- import 'vars.mu' as v -%}
{% include 'logo.mu' %}
{% include 'header.mu' %}
``

{% if total > 0 -%}
    `c`!`_Found {{ total }} Pages`_`!
For Query `_'{{ query }}'`_
-~
`a
{% for entry in entries -%}
    >`!{{ entry.name }}`! {{ v.status_icon(entry.p_dead_low, entry.p_dead_high) }} ({{ entry.since_announce }}) ago
`B{{ v.gray }}
`F{{ v.white }}{{ entry.text }}```F{{ v.white }}`B{{ v.gray }}

{{ v.url("< link >", entry.url) }}
`b
-~
{% endfor -%}
{% include 'pagination.mu' %}
{%- else -%}
`c`!`_No Pages Found!`_`!
For Query `_'{{ query }}'`_

{{ v.btn("Return", ":/page/index.mu") }}
{%- endif -%}

