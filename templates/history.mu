#!c=0
{% include 'logo.mu' %}
{% include 'header.mu' %}
{% import 'vars.mu' as v %}

`c
{%- if total == 0 -%}
    Your history is empty
{%- else %}
    {% for q in history -%}
        `!{{ v.url(q.q, ":/page/search.mu`query=" + q.q, v.white) }}`! at `_{{ q.time | strftime }}`_
    {% endfor -%}
{% endif %}

{% if has_prev -%}
	{{ v.url("< prev page >", ":/page/history.mu`page=" + ((page - 1) | string )) }}
{% endif -%}
{% if has_next -%}
    {{ v.url("< next page >", ":/page/history.mu`page=" + ((page + 1) | string )) }}
{% endif -%}


