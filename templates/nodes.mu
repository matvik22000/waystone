{%- import 'vars.mu' as v -%}
{% include 'logo.mu' %}
{% include 'header.mu' %}
{%- macro status(node) %}
    {%- if (node.p_dead_high - node.p_dead_low) >= 0.01 -%}
        `_{{ '%.0f' | format((1 - node.p_dead_high) * 100) }}-{{ '%.0f' | format((1 - node.p_dead_low) * 100) }}%`_ {{ v.status_icon(node.p_dead_low, node.p_dead_high) }}
    {%- else -%}
        `_{{ '%.0f' | format((1 - node.p_dead_low) * 100) }}%`_ {{ v.status_icon(node.p_dead_low, node.p_dead_high) }}
    {%- endif -%}
{% endmacro %}

Filter by name:{{ v.input('query', 25, query) }}{{ v.btn('GO!', ':/page/nodes.mu`*') }}``
{%- if mentions_for != "" %} || Nodes, that mentioned `_{{ mentions_for }}`_ {% endif %}
{% for node in nodes %}
``
>Node
    Name:     `!`_`[{{ node["name"] }}`{{ node["dst"] }}:/page/index.mu]`_`!
    Owner:    `_`[{{ node.owner[0] | replace_malformed }}`{{ 'lxmf@' + node.owner[1] }}]`_
    Is Alive: {{ status(node) }}
    Online:   `_{{ node.last_announce }}`_ ({{ node.since_announce }} ago)
    Mentions: `_`[{{ node.citations }}`:/page/nodes.mu`mentions_for={{ node.dst }}]`_
{% endfor %}
{% include 'pagination.mu' -%}
