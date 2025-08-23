{%- import 'vars.mu' as v -%}
{% include 'logo.mu' %}

`c|| {{ v.btn('Known Peers List', ':/page/peers.mu') }} || {{ v.btn('Known Nodes List', ':/page/nodes.mu') }} || {{ v.btn('History', ':/page/history.mu') }} ||

``

`c`!Search`! over `_{{ pages }}`_ pages hosted on `_{{ nodes }}`_ nodes`!

--
`a

`_`!Search`_:`!{{ v.input('query', 25) }}{{ v.btn('GO!', ':/page/search.mu`*') }}

--
`c
`B{{ v.lightgray }}`F{{ v.black }}Last queries:
``
`B{{ v.gray }}

{% for q in queries -%}
    {{ v.url(q, ":/page/search.mu`query=" + q) }}{%- if not loop.last %} {% endif -%}
{% endfor %}
{#{{ v.btn('Known Peers List', ':/page/peers.mu') }}`B{{ v.gray }} {{ v.btn('Known Nodes List', ':/page/nodes.mu') }}`B{{ v.gray }} {{ v.btn('History', ':/page/history.mu') }}`B{{ v.gray }}#}
`b
---
{%- include 'footer.mu' -%}