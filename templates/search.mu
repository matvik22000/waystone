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
    >`!{{ entry.name }}`!
`B{{ v.gray }}
`F{{ v.white }}{{ entry.text }}```F{{ v.white }}`B{{ v.gray }}

{{ v.url("< link >", entry.url) }}
`b
-~
{% endfor -%}
{%- else -%}
`c`!`_No Pages Found!`_`!
For Query `_'{{ query }}'`_

{{ v.btn("Return", ":/page/index.mu") }}
{%- endif -%}

